import os

from dotenv import load_dotenv
from flask import Flask

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

    import models  # noqa: F401 — registers all tables on db.metadata before create_all() below

    # No migration framework in this project — tables are declared in models.py and
    # created here if missing. create_all() only adds missing tables/never touches
    # existing ones, so this is safe to run on every cold start. Failures are logged
    # rather than raised so a momentarily-unreachable DB doesn't take down the whole
    # app (routes that don't touch the DB should keep working either way).
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.error(f"db.create_all() failed at startup: {e}")

    from blueprints.main import main_bp
    from blueprints.blog import blog_bp
    from blueprints.support import support_bp
    from blueprints.referrals import referrals_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(blog_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(referrals_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
