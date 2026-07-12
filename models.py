import random
import string

from extensions import db


class Subscriber(db.Model):
    __tablename__ = 'subscribers'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=True)
    subscribed_at = db.Column(db.DateTime, default=db.func.now())
    is_active = db.Column(db.Boolean, default=True)
    source = db.Column(db.String(50), default='footer')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'subscribed_at': self.subscribed_at.isoformat() if self.subscribed_at else None,
            'is_active': self.is_active,
            'source': self.source
        }


class BlogLike(db.Model):
    __tablename__ = 'blog_likes'
    id = db.Column(db.Integer, primary_key=True)
    post_slug = db.Column(db.String(100), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent_hash = db.Column(db.String(64), nullable=True)
    liked_at = db.Column(db.DateTime, default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint('post_slug', 'ip_address', 'user_agent_hash', name='unique_blog_like'),
    )


class BlogPostStats(db.Model):
    __tablename__ = 'blog_post_stats'
    post_slug = db.Column(db.String(100), primary_key=True)
    like_count = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class PageView(db.Model):
    __tablename__ = 'page_views'
    id = db.Column(db.Integer, primary_key=True)
    page_path = db.Column(db.String(200), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    viewed_at = db.Column(db.DateTime, default=db.func.now())
    referrer = db.Column(db.String(500), nullable=True)


class StockNotification(db.Model):
    __tablename__ = 'stock_notifications'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    # Plain numeric Shopify variant id (not the Storefront API GID) — this is what
    # the products/update webhook payload uses, so storing it this way avoids
    # converting formats on every webhook delivery.
    variant_id = db.Column(db.String(40), nullable=False, index=True)
    product_handle = db.Column(db.String(200), nullable=False)
    product_title = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    notified_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('email', 'variant_id', name='unique_notify_email_variant'),
    )


class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    subscribed_at = db.Column(db.DateTime, default=db.func.now())
    source = db.Column(db.String(50), default='lead_magnet')
    downloaded = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint('email', 'source', name='unique_lead_source'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'subscribed_at': self.subscribed_at.isoformat() if self.subscribed_at else None,
            'downloaded': self.downloaded
        }


def generate_referral_code(first_name):
    clean = ''.join(c for c in first_name.upper() if c.isalpha())[:8]
    suffix = ''.join(random.choices(string.digits, k=4))
    return f"REF-{clean}-{suffix}"


class Referrer(db.Model):
    __tablename__ = 'referrers'
    id            = db.Column(db.Integer, primary_key=True)
    first_name    = db.Column(db.String(80),  nullable=False)
    last_name     = db.Column(db.String(80),  nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    phone         = db.Column(db.String(30),  unique=True, nullable=False)
    referral_code = db.Column(db.String(30),  unique=True, nullable=False)
    created_at    = db.Column(db.DateTime,    default=db.func.now())
    is_active     = db.Column(db.Boolean,     default=True)
    referrals     = db.relationship('Referral', backref='referrer', lazy=True)

    def __repr__(self):
        return f'<Referrer {self.referral_code}>'


class Referral(db.Model):
    __tablename__ = 'referrals'

    STATUS_PENDING   = 'pending'
    STATUS_OPEN      = 'open'
    STATUS_IN_PROG   = 'in_progress'
    STATUS_ON_HOLD   = 'on_hold'
    STATUS_SIGNED_UP = 'signed_up'
    STATUS_RESOLVED  = 'resolved'

    id             = db.Column(db.Integer, primary_key=True)
    referrer_id    = db.Column(db.Integer, db.ForeignKey('referrers.id'), nullable=True)
    customer_name  = db.Column(db.String(160), nullable=False)
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(30), nullable=False)
    status         = db.Column(db.String(30), default='pending')
    zoho_ticket_id = db.Column(db.String(50))
    referral_code  = db.Column(db.String(30))
    notes          = db.Column(db.Text)
    created_at     = db.Column(db.DateTime, default=db.func.now())
    updated_at     = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    signed_up_at   = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Referral {self.customer_name} [{self.status}]>'
