"""
Thin wrapper around the Shopify Storefront API (GraphQL).

Uses the public Storefront API, not the Admin API — this is the correct API for a
customer-facing storefront (safe to call with a storefront access token, read access
to published products/collections, and cart/checkout creation). Checkout itself hands
off to Shopify's hosted checkout via the cart's `checkoutUrl` — this works on any
Shopify plan (a fully custom in-house checkout generally requires Shopify Plus).

Required env vars: SHOPIFY_STORE_DOMAIN, SHOPIFY_STOREFRONT_ACCESS_TOKEN.
See .env.example for where to generate the storefront access token.
"""
import os

import requests

from extensions import require_env

API_VERSION = os.environ.get('SHOPIFY_API_VERSION', '2025-10')


class ShopifyError(Exception):
    pass


def _endpoint():
    domain = require_env('SHOPIFY_STORE_DOMAIN')
    return f"https://{domain}/api/{API_VERSION}/graphql.json"


def _headers():
    return {
        'Content-Type': 'application/json',
        'X-Shopify-Storefront-Access-Token': require_env('SHOPIFY_STOREFRONT_ACCESS_TOKEN'),
    }


def _run(query, variables=None):
    response = requests.post(
        _endpoint(),
        headers=_headers(),
        json={'query': query, 'variables': variables or {}},
        timeout=15,
    )
    if response.status_code != 200:
        raise ShopifyError(f"Shopify Storefront API returned {response.status_code}: {response.text}")
    payload = response.json()
    if payload.get('errors'):
        raise ShopifyError(f"Shopify Storefront API GraphQL errors: {payload['errors']}")
    return payload['data']


PRODUCT_CARD_FIELDS = """
    id
    handle
    title
    availableForSale
    featuredImage { url altText }
    priceRange {
        minVariantPrice { amount currencyCode }
        maxVariantPrice { amount currencyCode }
    }
    variants(first: 1) {
        edges { node { id availableForSale } }
    }
"""

_COLLECTIONS_QUERY = f"""
query Collections($first: Int!) {{
    collections(first: $first, sortKey: TITLE) {{
        edges {{
            node {{
                id
                handle
                title
                description
                image {{ url altText }}
            }}
        }}
    }}
}}
"""


def get_collections(first=20):
    data = _run(_COLLECTIONS_QUERY, {'first': first})
    return [edge['node'] for edge in data['collections']['edges']]


_COLLECTION_PRODUCTS_QUERY = f"""
query CollectionProducts($handle: String!, $first: Int!, $after: String, $sortKey: ProductCollectionSortKeys, $reverse: Boolean, $filters: [ProductFilter!]) {{
    collection(handle: $handle) {{
        id
        handle
        title
        description
        products(first: $first, after: $after, sortKey: $sortKey, reverse: $reverse, filters: $filters) {{
            filters {{
                id
                label
                type
                values {{ id label count input }}
            }}
            edges {{
                cursor
                node {{ {PRODUCT_CARD_FIELDS} }}
            }}
            pageInfo {{ hasNextPage endCursor }}
        }}
    }}
}}
"""


def get_collection_products(handle, first=24, after=None, sort_key='BEST_SELLING', reverse=False, filters=None):
    data = _run(_COLLECTION_PRODUCTS_QUERY, {
        'handle': handle, 'first': first, 'after': after, 'sortKey': sort_key, 'reverse': reverse,
        'filters': filters or [],
    })
    return data['collection']


_SEARCH_PRODUCTS_QUERY = f"""
query SearchProducts($query: String!, $first: Int!, $after: String) {{
    products(first: $first, after: $after, query: $query, sortKey: RELEVANCE) {{
        edges {{
            cursor
            node {{ {PRODUCT_CARD_FIELDS} }}
        }}
        pageInfo {{ hasNextPage endCursor }}
    }}
}}
"""


def search_products(query, first=24, after=None):
    data = _run(_SEARCH_PRODUCTS_QUERY, {'query': query, 'first': first, 'after': after})
    return data['products']


_PRODUCT_RECOMMENDATIONS_QUERY = f"""
query ProductRecommendations($productId: ID!) {{
    productRecommendations(productId: $productId) {{ {PRODUCT_CARD_FIELDS} }}
}}
"""


def get_product_recommendations(product_id):
    data = _run(_PRODUCT_RECOMMENDATIONS_QUERY, {'productId': product_id})
    return data['productRecommendations'] or []


_SHOP_POLICIES_QUERY = """
query ShopPolicies {
    shop {
        privacyPolicy { title body }
        refundPolicy { title body }
        termsOfService { title body }
        shippingPolicy { title body }
    }
}
"""

_POLICY_SLUGS = {
    'privacyPolicy': 'privacy',
    'refundPolicy': 'refund',
    'termsOfService': 'terms',
    'shippingPolicy': 'shipping',
}

_policies_cache = None  # Policies change rarely — cache for the life of the process rather than
                         # re-fetching from Shopify on every single page render (this powers the
                         # sitewide footer, not just /shop pages). Failed fetches aren't cached,
                         # so a transient Shopify outage self-heals on the next request.


def get_shop_policies():
    """Returns {slug: {title, body}}, rendered on our own /shop/policies/<slug> page
    (not linked out to Shopify's unbranded checkout.shopify.com policy pages) so it
    matches the rest of the site."""
    global _policies_cache
    if _policies_cache is None:
        data = _run(_SHOP_POLICIES_QUERY)
        shop = data['shop']
        _policies_cache = {
            _POLICY_SLUGS[key]: value for key, value in shop.items() if value
        }
    return _policies_cache


_PRODUCT_QUERY = """
query Product($handle: String!) {
    product(handle: $handle) {
        id
        handle
        title
        description
        descriptionHtml
        availableForSale
        vendor
        images(first: 8) { edges { node { url altText } } }
        priceRange {
            minVariantPrice { amount currencyCode }
            maxVariantPrice { amount currencyCode }
        }
        variants(first: 25) {
            edges {
                node {
                    id
                    title
                    availableForSale
                    quantityAvailable
                    price { amount currencyCode }
                    selectedOptions { name value }
                }
            }
        }
    }
}
"""


def get_product(handle):
    data = _run(_PRODUCT_QUERY, {'handle': handle})
    return data['product']


_CART_CREATE_MUTATION = """
mutation CartCreate($lines: [CartLineInput!]) {
    cartCreate(input: { lines: $lines }) {
        cart { id checkoutUrl totalQuantity }
        userErrors { field message }
    }
}
"""

_CART_LINES_ADD_MUTATION = """
mutation CartLinesAdd($cartId: ID!, $lines: [CartLineInput!]!) {
    cartLinesAdd(cartId: $cartId, lines: $lines) {
        cart { id checkoutUrl totalQuantity }
        userErrors { field message }
    }
}
"""

_CART_LINES_REMOVE_MUTATION = """
mutation CartLinesRemove($cartId: ID!, $lineIds: [ID!]!) {
    cartLinesRemove(cartId: $cartId, lineIds: $lineIds) {
        cart { id checkoutUrl totalQuantity }
        userErrors { field message }
    }
}
"""

_CART_QUERY = """
query Cart($id: ID!) {
    cart(id: $id) {
        id
        checkoutUrl
        totalQuantity
        cost {
            totalAmount { amount currencyCode }
            subtotalAmount { amount currencyCode }
        }
        lines(first: 100) {
            edges {
                node {
                    id
                    quantity
                    merchandise {
                        ... on ProductVariant {
                            id
                            title
                            price { amount currencyCode }
                            product { title handle featuredImage { url altText } }
                        }
                    }
                }
            }
        }
    }
}
"""


def create_cart(variant_id, quantity=1):
    data = _run(_CART_CREATE_MUTATION, {'lines': [{'merchandiseId': variant_id, 'quantity': quantity}]})
    result = data['cartCreate']
    if result['userErrors']:
        raise ShopifyError(f"cartCreate errors: {result['userErrors']}")
    return result['cart']


def add_to_cart(cart_id, variant_id, quantity=1):
    data = _run(_CART_LINES_ADD_MUTATION, {
        'cartId': cart_id,
        'lines': [{'merchandiseId': variant_id, 'quantity': quantity}],
    })
    result = data['cartLinesAdd']
    if result['userErrors']:
        raise ShopifyError(f"cartLinesAdd errors: {result['userErrors']}")
    return result['cart']


def remove_from_cart(cart_id, line_ids):
    data = _run(_CART_LINES_REMOVE_MUTATION, {'cartId': cart_id, 'lineIds': line_ids})
    result = data['cartLinesRemove']
    if result['userErrors']:
        raise ShopifyError(f"cartLinesRemove errors: {result['userErrors']}")
    return result['cart']


def get_cart(cart_id):
    data = _run(_CART_QUERY, {'id': cart_id})
    return data['cart']
