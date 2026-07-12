import os

from dotenv import load_dotenv
from flask import Flask, session

import shopify_client as shopify
from extensions import db, mail, normalize_db_url, require_env

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.secret_key = require_env('FLASK_SECRET_KEY')

    # ── Database ──────────────────────────────────────────────────────
    app.config['SQLALCHEMY_DATABASE_URI'] = normalize_db_url(require_env('DATABASE_URL'))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # ── Email (Zoho Mail) ────────────────────────────────────────────
    app.config['MAIL_SERVER']         = 'smtp.zoho.com'
    app.config['MAIL_PORT']           = 587
    app.config['MAIL_USE_TLS']        = True
    app.config['MAIL_USERNAME']       = require_env('MAIL_USERNAME')
    app.config['MAIL_PASSWORD']       = require_env('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get(
        'MAIL_DEFAULT_SENDER',
        'Empath Technology Solutions <jason.goliath@empathtechnologysolutions.com>'
    )

    db.init_app(app)
    mail.init_app(app)

    from blueprints.main import main_bp
    from blueprints.blog import blog_bp
    from blueprints.support import support_bp
    from blueprints.referrals import referrals_bp
    from blueprints.shop import shop_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(referrals_bp)
    app.register_blueprint(shop_bp)

    @app.context_processor
    def inject_shop_policies():
        try:
            return {'shop_policies': shopify.get_shop_policies()}
        except (shopify.ShopifyError, RuntimeError):
            return {'shop_policies': []}  # Shop unreachable — footer just omits this column.

    @app.context_processor
    def inject_footer_categories():
        try:
            by_handle = {c['handle']: c for c in shopify.get_collections(first=50)}
            categories = [by_handle[h] for h in shopify.FEATURED_CATEGORY_HANDLES if h in by_handle]
            return {'footer_categories': categories}
        except (shopify.ShopifyError, RuntimeError):
            return {'footer_categories': []}  # Shop unreachable — footer just omits this column.

    @app.context_processor
    def inject_cart_count():
        cart_id = session.get('shopify_cart_id')
        if not cart_id:
            return {'cart_count': 0}
        try:
            cart_data = shopify.get_cart(cart_id)
            return {'cart_count': cart_data['totalQuantity'] if cart_data else 0}
        except (shopify.ShopifyError, RuntimeError):
            return {'cart_count': 0}  # Shop unreachable — floating cart badge just omits the count.

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
