import json
from urllib.parse import urlencode

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, url_for

import shopify_client as shopify

shop_bp = Blueprint('shop', __name__)


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
    return render_template('shop/index.html', collections=collections)


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
