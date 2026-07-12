import json
import os
import re
from urllib.parse import urlencode

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, url_for

import shopify_client as shopify
from email_utils import send_referral_email
from extensions import db
from models import StockNotification
from sms_utils import clean_phone_number, send_sms

shop_bp = Blueprint('shop', __name__)

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


@shop_bp.errorhandler(shopify.ShopifyError)
@shop_bp.errorhandler(RuntimeError)
def handle_shop_unavailable(error):
    current_app.logger.error(f"Shop unavailable: {error}")
    return render_template('shop/unavailable.html'), 503


def _parse_selected_filters():
    """Each selected facet value is passed back as ?filter=<the value's raw `input` JSON>,
    exactly as Shopify returned it — this keeps the route agnostic to whatever facets
    Search & Discovery has configured (tags, price, availability, variant options, ...)."""
    selected = []
    for raw in request.args.getlist('filter'):
        try:
            selected.append(json.loads(raw))
        except (TypeError, ValueError):
            continue
    return selected


def _build_filter_facets(collection_data, selected_filters, sort_key):
    """Turn Shopify's raw `filters` field into ready-to-render facets: each value carries
    a precomputed `checked` flag and the exact query string to toggle it. Doing the
    add/remove-filter set logic here (rather than in Jinja) avoids fragile JSON string
    comparisons in the template, since Shopify's own JSON serialization of `input` won't
    necessarily byte-match a re-serialized Python dict.
    """
    selected_keys = {json.dumps(f, sort_keys=True) for f in selected_filters}
    facets = []
    for facet in (collection_data.get('products', {}).get('filters') or []):
        values = []
        for v in facet.get('values', []):
            try:
                parsed_input = json.loads(v['input'])
            except (TypeError, ValueError, KeyError):
                continue
            key = json.dumps(parsed_input, sort_keys=True)
            checked = key in selected_keys
            if checked:
                new_selected = [f for f in selected_filters if json.dumps(f, sort_keys=True) != key]
            else:
                new_selected = selected_filters + [parsed_input]
            query = [('sort', sort_key)] + [('filter', json.dumps(f, sort_keys=True)) for f in new_selected]
            values.append({
                'label': v['label'],
                'count': v['count'],
                'checked': checked,
                'query_string': urlencode(query),
            })
        facets.append({'label': facet['label'], 'options': values})
    return facets


@shop_bp.route('/shop')
def index():
    collections = shopify.get_collections()

    by_handle = {c['handle']: c for c in collections}
    hero_categories = [by_handle[h] for h in shopify.FEATURED_CATEGORY_HANDLES[:5] if h in by_handle]

    featured_products = []
    try:
        new_arrivals = shopify.get_collection_products('new-arrivals', first=12, sort_key='BEST_SELLING')
        featured_products = [edge['node'] for edge in new_arrivals['products']['edges']] if new_arrivals else []
    except (shopify.ShopifyError, RuntimeError):
        pass  # New Arrivals carousel just doesn't render — rest of /shop isn't dependent on it.

    deal_products = []
    try:
        deals = shopify.get_collection_products('deals', first=12, sort_key='BEST_SELLING')
        deal_products = [edge['node'] for edge in deals['products']['edges']] if deals else []
    except (shopify.ShopifyError, RuntimeError):
        pass  # Deals carousel just doesn't render — rest of /shop isn't dependent on it.

    return render_template(
        'shop/index.html',
        collections=collections,
        hero_categories=hero_categories,
        featured_products=featured_products,
        deal_products=deal_products,
    )


@shop_bp.route('/shop/<collection_handle>')
def collection(collection_handle):
    after = request.args.get('after')
    sort_key = request.args.get('sort', 'BEST_SELLING')
    selected_filters = _parse_selected_filters()
    collection_data = shopify.get_collection_products(
        collection_handle, after=after, sort_key=sort_key, filters=selected_filters,
    )
    facets = _build_filter_facets(collection_data, selected_filters, sort_key)
    return render_template(
        'shop/collection.html',
        collection=collection_data,
        sort_key=sort_key,
        facets=facets,
        has_active_filters=bool(selected_filters),
    )


@shop_bp.route('/shop/search')
def search():
    query = request.args.get('q', '').strip()
    after = request.args.get('after')
    results = shopify.search_products(query, after=after) if query else None
    return render_template('shop/search.html', query=query, results=results)


@shop_bp.route('/shop/product/<handle>')
def product(handle):
    product_data = shopify.get_product(handle)
    recommendations = []
    if product_data:
        try:
            recommendations = shopify.get_product_recommendations(product_data['id'])
        except shopify.ShopifyError:
            recommendations = []
    return render_template(
        'shop/product.html',
        product=product_data,
        recommendations=recommendations,
        product_schema=_build_product_schema(product_data) if product_data else None,
    )


def _build_product_schema(product_data):
    """https://schema.org/Product — still a fully live Google rich-result feature
    (unlike FAQPage), shows price/availability directly in search results."""
    images = [edge['node']['url'] for edge in product_data['images']['edges']]
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': product_data['title'],
        'description': product_data['description'],
        'sku': product_data['handle'],
        'offers': {
            '@type': 'Offer',
            'url': url_for('shop.product', handle=product_data['handle'], _external=True),
            'priceCurrency': product_data['priceRange']['minVariantPrice']['currencyCode'],
            'price': product_data['priceRange']['minVariantPrice']['amount'],
            'availability': (
                'https://schema.org/InStock' if product_data['availableForSale']
                else 'https://schema.org/OutOfStock'
            ),
        },
    }
    if images:
        schema['image'] = images
    if product_data.get('vendor'):
        schema['brand'] = {'@type': 'Brand', 'name': product_data['vendor']}
    return schema


@shop_bp.route('/shop/policies/<slug>')
def policy(slug):
    policy_data = shopify.get_shop_policies().get(slug)
    if not policy_data:
        abort(404)
    return render_template('shop/policy.html', policy=policy_data)


@shop_bp.route('/shop/cart')
def cart():
    cart_id = session.get('shopify_cart_id')
    cart_data = shopify.get_cart(cart_id) if cart_id else None
    return render_template('shop/cart.html', cart=cart_data)


@shop_bp.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    data = request.get_json(silent=True) or {}
    variant_id = data.get('variant_id')
    quantity = int(data.get('quantity', 1))
    if not variant_id:
        return jsonify({'success': False, 'error': 'variant_id is required'}), 400

    cart_id = session.get('shopify_cart_id')
    try:
        if cart_id:
            cart_data = shopify.add_to_cart(cart_id, variant_id, quantity)
        else:
            cart_data = shopify.create_cart(variant_id, quantity)
            session['shopify_cart_id'] = cart_data['id']
    except (shopify.ShopifyError, RuntimeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 502

    return jsonify({'success': True, 'totalQuantity': cart_data['totalQuantity'], 'checkoutUrl': cart_data['checkoutUrl']}), 200


@shop_bp.route('/api/cart/remove', methods=['POST'])
def api_cart_remove():
    data = request.get_json(silent=True) or {}
    line_id = data.get('line_id')
    if not line_id:
        return jsonify({'success': False, 'error': 'line_id is required'}), 400

    cart_id = session.get('shopify_cart_id')
    if not cart_id:
        return jsonify({'success': False, 'error': 'No cart in session'}), 400

    try:
        cart_data = shopify.remove_from_cart(cart_id, [line_id])
    except (shopify.ShopifyError, RuntimeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 502

    return jsonify({'success': True, 'totalQuantity': cart_data['totalQuantity']}), 200


@shop_bp.route('/api/cart/clear', methods=['POST'])
def api_cart_clear():
    cart_id = session.get('shopify_cart_id')
    if not cart_id:
        return jsonify({'success': True, 'totalQuantity': 0}), 200

    cart_data = shopify.get_cart(cart_id)
    line_ids = [edge['node']['id'] for edge in cart_data['lines']['edges']] if cart_data else []
    if not line_ids:
        return jsonify({'success': True, 'totalQuantity': 0}), 200

    try:
        cart_data = shopify.remove_from_cart(cart_id, line_ids)
    except (shopify.ShopifyError, RuntimeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 502

    return jsonify({'success': True, 'totalQuantity': cart_data['totalQuantity']}), 200


@shop_bp.route('/api/notify-stock', methods=['POST'])
def api_notify_stock():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    phone = clean_phone_number(data.get('phone'))
    variant_gid = (data.get('variant_id') or '').strip()
    product_handle = (data.get('product_handle') or '').strip()
    product_title = (data.get('product_title') or '').strip()

    if not EMAIL_REGEX.match(email):
        return jsonify({'success': False, 'error': 'Please enter a valid email address.'}), 400
    if phone and not re.match(r'^\+?[0-9]{9,15}$', phone):
        return jsonify({'success': False, 'error': 'Please enter a valid phone number.'}), 400
    if not variant_gid or not product_handle or not product_title:
        return jsonify({'success': False, 'error': 'Missing product information.'}), 400

    # Storefront API hands us a GID (gid://shopify/ProductVariant/123) — the
    # products/update webhook payload that triggers the notification uses the
    # plain numeric id, so normalize to that now rather than on every webhook delivery.
    variant_id = variant_gid.rsplit('/', 1)[-1]

    existing = StockNotification.query.filter_by(email=email, variant_id=variant_id).first()
    if not existing:
        db.session.add(StockNotification(
            email=email,
            phone=phone or None,
            variant_id=variant_id,
            product_handle=product_handle,
            product_title=product_title,
        ))
        db.session.commit()
    elif phone and existing.phone != phone:
        existing.phone = phone
        db.session.commit()

    return jsonify({'success': True}), 200


@shop_bp.route('/webhooks/products/update', methods=['POST'])
def webhook_products_update():
    # Shopify doesn't give us a signing secret for webhooks created outside a
    # registered app's Admin API credentials, so this checks the shop-domain
    # header as a basic sanity gate rather than a full HMAC verification.
    shop_domain = request.headers.get('X-Shopify-Shop-Domain', '')
    if shop_domain != os.environ.get('SHOPIFY_STORE_DOMAIN', ''):
        abort(401)

    payload = request.get_json(silent=True) or {}
    product_title = payload.get('title', '')
    product_handle = payload.get('handle', '')

    for variant in payload.get('variants', []):
        variant_id = str(variant.get('id', ''))
        qty = variant.get('inventory_quantity')
        if not variant_id or qty is None or qty <= 0:
            continue

        pending = StockNotification.query.filter_by(variant_id=variant_id, notified_at=None).all()
        for note in pending:
            product_url = url_for('shop.product', handle=product_handle, _external=True)
            send_referral_email(
                note.email,
                f"Back in stock: {product_title}",
                'emails/07_back_in_stock.html',
                {'product_title': product_title, 'product_url': product_url},
            )
            if note.phone:
                send_sms(
                    note.phone,
                    f"Good news! {product_title} is back in stock at Empath Technology Solutions. "
                    f"Grab it here: {product_url}",
                )
            note.notified_at = db.func.now()
        if pending:
            db.session.commit()

    return jsonify({'received': True}), 200
