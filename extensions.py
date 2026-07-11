import os

from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
mail = Mail()


def require_env(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env locally, or set it in your host's dashboard."
        )
    return value


def normalize_db_url(url):
    """Point plain postgres:// / postgresql:// URLs at the psycopg3 driver.

    Neon (and most providers) hand out driver-less URLs like postgresql://...,
    which SQLAlchemy would otherwise default to psycopg2. We install psycopg3
    instead (it has a prebuilt wheel for newer Python versions psycopg2-binary
    doesn't yet), so redirect here rather than requiring every DATABASE_URL to
    be edited by hand.
    """
    if url.startswith('postgres://'):
        return 'postgresql+psycopg://' + url[len('postgres://'):]
    if url.startswith('postgresql://'):
        return 'postgresql+psycopg://' + url[len('postgresql://'):]
    return url
