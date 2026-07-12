import os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

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
    is_postgres = url.startswith('postgres://') or url.startswith('postgresql://')
    if not is_postgres:
        return url  # e.g. local sqlite:///... for dev — leave untouched.

    if url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url[len('postgres://'):]
    else:
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]

    # connect_timeout as an engine connect_args kwarg breaks with some
    # SQLAlchemy/psycopg3 version combos (SQLAlchemy ends up instantiating
    # psycopg.Connection directly, which doesn't accept it) — passing it as a
    # libpq DSN query parameter instead sidesteps that entirely.
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.setdefault('connect_timeout', '10')
    return urlunsplit(parts._replace(query=urlencode(query)))
