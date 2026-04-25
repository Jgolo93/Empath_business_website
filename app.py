from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
import os
import hashlib
import random
import string
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = '3326a6c76241b25be006e1a52c1d197ee23141c9f2'

# ── Database ──────────────────────────────────────────────────────
DATABASE_URL = "postgresql://neondb_owner:npg_2led5BIEjmnx@ep-misty-resonance-aeq4m318-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {'connect_timeout': 10}
}

db = SQLAlchemy(app)

# ── Email (Zoho Mail) ───────────────────────────────────────────────
app.config['MAIL_SERVER']         = 'smtp.zoho.com'
app.config['MAIL_PORT']           = 587
app.config['MAIL_USE_TLS']        = True
app.config['MAIL_USERNAME']       = 'jason.goliath@empathtechnologysolutions.com'
app.config['MAIL_PASSWORD']       = '4dubCZHtMXbk'
app.config['MAIL_DEFAULT_SENDER'] = 'Empath Technology Solutions <jason.goliath@empathtechnologysolutions.com>'
mail = Mail(app)

# ========================================
# DATABASE MODELS
# ========================================

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


# ========================================
# ROUTES
# ========================================

@app.route('/')
def home():
    marketing_cards = [
        {'title': 'Is your computer running slow?', 'content': 'Let us run diagnostics to see what we can do to improve your PC speed.', 'icon': 'speed'},
        {'title': 'Quick Support', 'content': 'Do you have a quick problem on your mobile you would like to resolve?', 'icon': 'support_agent'},
        {'title': 'PC Upgrades', 'content': 'Would you like to upgrade your computer for better performance?', 'icon': 'upgrade'},
        {'title': 'Virus Protection', 'content': 'Keep your data safe with our comprehensive virus removal services.', 'icon': 'security'},
        {'title': 'Tech Consultation', 'content': 'Not sure what device or software to choose? Let our experts guide you.', 'icon': 'psychology'},
        {'title': 'Remote Assistance', 'content': 'Get help without leaving your home or office. Quick, efficient support.', 'icon': 'computer'}
    ]
    return render_template('index.html', marketing_cards=marketing_cards)

@app.route('/pricing')
def pricing():
    return redirect(url_for('create_ticket'), code=301)

@app.route('/how-it-works')
def how_it_works():
    steps = [
        {'title': 'Create a Support Ticket', 'description': 'Fill out our simple support form to let us know what issues you\'re experiencing.', 'icon': 'confirmation_number'},
        {'title': 'Remote Support', 'description': 'Our technicians can connect to your device remotely to diagnose and fix many issues without you needing to leave home.', 'icon': 'computer'},
        {'title': 'On-site Service', 'description': 'For more complex issues, we can arrange for your PC to be booked in for servicing at our workshop.', 'icon': 'build'},
        {'title': 'Problem Solved', 'description': 'We\'ll ensure your technology is working properly before completing the service.', 'icon': 'check_circle'}
    ]
    return render_template('how_it_works.html', steps=steps)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('.', 'sitemap.xml')

@app.route('/zohoverify/verifyforzoho.html')
def zohoverify():
    return render_template('verifyforzoho.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/shop')
def shop():
    return redirect(url_for('home'), code=301)

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/blog/cybersecurity-tips-small-business')
def cybersecurity_tips():
    return render_template('blog_cybersecurity_tips.html')

@app.route('/blog/it-solutions-productivity-boost')
def productivity_boost():
    return render_template('blog_productivity_boost.html')

@app.route('/blog/glens-grass-case-study')
def glens_grass_case_study():
    return render_template('blog_glens_grass_case_study.html')

@app.route('/blog/world-of-testing')
def world_of_testing():
    return render_template('blog_world_of_testing.html')

@app.route('/blog/robot-framework-browser-library')
def robot_framework_browser_library():
    return render_template('blog_robot_framework.html')

@app.route('/blog/<slug>')
def blog_post(slug):
    try:
        stat = BlogPostStats.query.filter_by(post_slug=slug).first()
        view_count = stat.view_count if stat else 0
        like_count = BlogLike.query.filter_by(post_slug=slug).count()
    except Exception:
        view_count = 0
        like_count = 0

    templates = {
        'cybersecurity-tips-small-business': 'blog_cybersecurity_tips.html',
        'it-solutions-productivity-boost': 'blog_productivity_boost.html',
        'glens-grass-case-study': 'blog_glens_grass_case_study.html',
        'world-of-testing': 'blog_world_of_testing.html',
        'robot-framework-browser-library': 'blog_robot_framework.html',
    }
    template = templates.get(slug)
    if template:
        return render_template(template, view_count=view_count, like_count=like_count)
    return render_template('blog.html')

@app.route('/create-ticket')
def create_ticket():
    return render_template('create_ticket.html')

@app.route('/ticket-success')
def ticket_success():
    ticket_id = request.args.get('id', 'Unknown')
    subject = request.args.get('subject', 'Your support request')
    return render_template('ticket_success.html', ticket_id=ticket_id, subject=subject)

@app.route('/oauth/callback')
def oauth_callback():
    code = request.args.get('code')
    accounts_server = request.args.get('accounts-server')
    client_id = '1000.OCP7ADAC99HLRYU5VPU91VMV1A1VJI'
    client_secret = '3326a6c76241b25be006e1a52c1d197ee23141c9f2'
    redirect_uri = 'https://www.empathtechnologysolutions.com/oauth/callback'
    token_url = f"{accounts_server}/oauth/v2/token"
    payload = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': code
    }
    response = requests.post(token_url, data=payload)
    token_data = response.json()
    return f"<h2>Token Exchange Result</h2><pre>{token_data}</pre>"

# ========================================
# API ROUTES
# ========================================

@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        source = data.get('source', 'footer')
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        existing = Subscriber.query.filter_by(email=email).first()
        if existing:
            if existing.is_active:
                return jsonify({'success': True, 'message': 'Already subscribed!'}), 200
            else:
                existing.is_active = True
                db.session.commit()
                return jsonify({'success': True, 'message': 'Welcome back!'}), 200
        subscriber = Subscriber(email=email, source=source)
        db.session.add(subscriber)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Successfully subscribed!', 'subscriber': subscriber.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/blog/like', methods=['POST'])
def like_blog_post():
    try:
        data = request.get_json()
        post_slug = data.get('post_slug')
        if not post_slug:
            return jsonify({'success': False, 'error': 'Post slug is required'}), 400
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '')
        user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:64]
        existing = BlogLike.query.filter_by(post_slug=post_slug, ip_address=ip_address, user_agent_hash=user_agent_hash).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
            count = BlogLike.query.filter_by(post_slug=post_slug).count()
            return jsonify({'success': True, 'liked': False, 'count': count}), 200
        like = BlogLike(post_slug=post_slug, ip_address=ip_address, user_agent_hash=user_agent_hash)
        db.session.add(like)
        db.session.commit()
        count = BlogLike.query.filter_by(post_slug=post_slug).count()
        return jsonify({'success': True, 'liked': True, 'count': count}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/blog/likes/<post_slug>', methods=['GET'])
def get_blog_likes(post_slug):
    try:
        count = BlogLike.query.filter_by(post_slug=post_slug).count()
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '')
        user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:64]
        has_liked = BlogLike.query.filter_by(post_slug=post_slug, ip_address=ip_address, user_agent_hash=user_agent_hash).first() is not None
        return jsonify({'success': True, 'count': count, 'hasLiked': has_liked}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/blog/view/<post_slug>', methods=['POST'])
def track_blog_view(post_slug):
    try:
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '')
        referrer = request.headers.get('Referer', '')
        view = PageView(page_path=f'/blog/{post_slug}', ip_address=ip_address, user_agent=user_agent, referrer=referrer)
        db.session.add(view)
        db.session.commit()
        stat = BlogPostStats.query.filter_by(post_slug=post_slug).first()
        if stat:
            stat.view_count += 1
        else:
            stat = BlogPostStats(post_slug=post_slug, view_count=1)
            db.session.add(stat)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/blog/stats/<post_slug>', methods=['GET'])
def get_blog_stats(post_slug):
    try:
        likes = BlogLike.query.filter_by(post_slug=post_slug).count()
        stat = BlogPostStats.query.filter_by(post_slug=post_slug).first()
        views = stat.view_count if stat else 0
        return jsonify({'success': True, 'likes': likes, 'views': views}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================
# LEAD MAGNET ROUTES
# ========================================

import re
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

@app.route('/api/leads', methods=['POST'])
def submit_lead():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        if not name:
            return jsonify({'success': False, 'error': 'Please enter your full name'}), 400
        if not email:
            return jsonify({'success': False, 'error': 'Please enter your email address'}), 400
        if not EMAIL_REGEX.match(email):
            return jsonify({'success': False, 'error': 'Please enter a valid email address'}), 400
        max_retries = 3
        for attempt in range(max_retries):
            try:
                db.session.close()
                existing = Lead.query.filter_by(email=email, source='lead_magnet').first()
                if existing:
                    return jsonify({'success': True, 'lead_id': existing.id, 'exists': True}), 200
                lead = Lead(name=name, email=email, source='lead_magnet')
                db.session.add(lead)
                db.session.commit()
                return jsonify({'success': True, 'lead_id': lead.id, 'exists': False}), 201
            except Exception as db_error:
                db.session.rollback()
                if attempt < max_retries - 1 and ('SSL' in str(db_error) or 'connection' in str(db_error).lower()):
                    import time
                    time.sleep(0.5)
                    continue
                raise
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Something went wrong. Please try again.'}), 500


@app.route('/download/the-journey')
def download_lead_magnet():
    try:
        email = request.args.get('email', '').strip().lower()
        if not email:
            return jsonify({'success': False, 'error': 'Email required'}), 400
        lead = Lead.query.filter_by(email=email, source='lead_magnet').first()
        if not lead:
            return jsonify({'success': False, 'error': 'Please submit your details first'}), 403
        lead.downloaded = True
        db.session.commit()
        return send_from_directory(
            os.path.join(os.path.dirname(__file__), 'static', 'pdfs'),
            'the-journey.pdf',
            as_attachment=True,
            download_name='The Journey - By Jason Goliath.pdf'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========================================
# HELPER
# ========================================

def send_referral_email(to_address, subject, template_name, context):
    try:
        print(f"[EMAIL SENDING] to={to_address} subject={subject} template={template_name}")
        html_body = render_template(template_name, **context)
        msg = Message(subject=subject, recipients=[to_address], html=html_body)
        mail.send(msg)
        print(f"[EMAIL SENT SUCCESS] to={to_address}")
    except Exception as e:
        print(f"[EMAIL FAILED] to={to_address} template={template_name} error={e}")
        app.logger.error(f"[EMAIL FAILED] to={to_address} template={template_name} error={e}")


# ========================================
# REFERRAL PROGRAMME ROUTES
# ========================================

@app.route('/referrer-signup')
def referrer_signup_page():
    return render_template('signup.html')


@app.route('/api/referrer-signup', methods=['POST'])
def referrer_signup():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data received'}), 400
    required = ['first_name', 'last_name', 'email', 'phone']
    for field in required:
        if not data.get(field, '').strip():
            return jsonify({'error': f'{field} is required'}), 400
    if Referrer.query.filter_by(email=data['email'].strip().lower()).first():
        return jsonify({'error': 'This email address is already registered'}), 409
    if Referrer.query.filter_by(phone=data['phone'].strip()).first():
        return jsonify({'error': 'This phone number is already registered'}), 409
    code = generate_referral_code(data['first_name'])
    attempts = 0
    while Referrer.query.filter_by(referral_code=code).first():
        code = generate_referral_code(data['first_name'])
        attempts += 1
        if attempts > 10:
            return jsonify({'error': 'Could not generate unique code, try again'}), 500
    referrer = Referrer(
        first_name    = data['first_name'].strip(),
        last_name     = data['last_name'].strip(),
        email         = data['email'].strip().lower(),
        phone         = data['phone'].strip(),
        referral_code = code,
    )
    db.session.add(referrer)
    db.session.commit()
    send_referral_email(
        to_address    = referrer.email,
        subject       = f"Welcome! Your referral code is {code}",
        template_name = 'emails/01_welcome.html',
        context       = {'referrer': referrer}
    )
    return jsonify({'referral_code': code, 'message': 'Signup successful'}), 201


@app.route('/api/referral-intake', methods=['GET', 'POST'])
def referral_intake():
    app.logger.info(f"Request method: {request.method}")
    app.logger.info(f"Request headers: {dict(request.headers)}")

    raw = request.get_data(as_text=True)
    app.logger.info(f"Request raw data: {raw}")

    data = {}
    if raw:
        try:
            import json
            data = json.loads(raw)
        except Exception:
            pass

    if not data:
        data = request.get_json(force=True, silent=True) or {}
    if not data:
        data = request.form.to_dict() or {}
    if not data:
        data = request.args.to_dict() or {}

    app.logger.info(f"Received referral intake data: {data}")

    customer_name = (
        data.get('customer_name', '') or
        data.get('Name1.First', '') or
        data.get('Name', '') or
        data.get('name', '') or
        ''
    ).strip()

    customer_phone = (
        data.get('customer_phone', '') or
        data.get('PhoneNumber', '') or
        data.get('Phone', '') or
        data.get('phone', '') or
        data.get('Mobile', '') or
        ''
    ).strip()

    customer_email = (
        data.get('customer_email', '') or
        data.get('Email', '') or
        data.get('email', '') or
        ''
    ).strip()

    referral_code = (
        data.get('referral_code', '') or
        data.get('refferral_code', '') or
        data.get('SingleLine2', '') or
        data.get('Referral_Code', '') or
        data.get('Referral Code', '') or
        data.get('code', '') or
        ''
    ).strip().upper()

    if not customer_name or not customer_phone:
        app.logger.error(f"Missing required fields. Name: '{customer_name}', Phone: '{customer_phone}'")
        return jsonify({'error': 'customer_name and customer_phone are required', 'received_data': data}), 400

    referrer = None
    if referral_code:
        try:
            db.session.close()
            referrer = Referrer.query.filter_by(referral_code=referral_code).first()
        except Exception as e:
            app.logger.error(f"DB error looking up referrer: {e}")

    try:
        referral = Referral(
            referrer_id    = referrer.id if referrer else None,
            customer_name  = customer_name,
            customer_email = customer_email or None,
            customer_phone = customer_phone,
            referral_code  = referral_code or None,
            status         = Referral.STATUS_PENDING,
        )
        db.session.add(referral)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Database error saving referral: {e}")
        db.session.rollback()
        return jsonify({'error': 'Database connection error, please try again'}), 500

    if referrer:
        send_referral_email(
            to_address    = referrer.email,
            subject       = f"Update: {customer_name} has submitted their details",
            template_name = 'emails/02_submitted.html',
            context       = {'referrer': referrer, 'referral': referral}
        )

    return jsonify({'status': 'received', 'referral_id': referral.id}), 200


@app.route('/api/zoho-desk-webhook', methods=['POST'])
def zoho_desk_webhook():
    secret = request.headers.get('X-Webhook-Secret', '')
    if secret != 'zoho_webhook_secret_empath_2025_secure':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON body'}), 400
    ticket_id      = str(data.get('ticketId', '')).strip()
    zoho_status    = data.get('status', '').strip().lower().replace(' ', '_')
    customer_phone = data.get('customerPhone', '').strip()
    STATUS_MAP = {
        'open':        Referral.STATUS_OPEN,
        'in_progress': Referral.STATUS_IN_PROG,
        'on_hold':     Referral.STATUS_ON_HOLD,
        'resolved':    Referral.STATUS_RESOLVED,
    }
    internal_status = STATUS_MAP.get(zoho_status)
    if not internal_status:
        return jsonify({'skipped': True, 'reason': f'No mapping for status: {zoho_status}'}), 200
    referral = None
    if ticket_id:
        referral = Referral.query.filter_by(zoho_ticket_id=ticket_id).first()
    if not referral and customer_phone:
        referral = Referral.query.filter_by(customer_phone=customer_phone).order_by(Referral.created_at.desc()).first()
    if not referral:
        return jsonify({'error': 'Referral not found'}), 404
    if ticket_id:
        referral.zoho_ticket_id = ticket_id
    referral.status = internal_status
    db.session.commit()
    EMAIL_MAP = {
        Referral.STATUS_OPEN:    ('emails/03_ticket_open.html',  'Update on your referral — ticket opened'),
        Referral.STATUS_IN_PROG: ('emails/04_in_progress.html',  'Update on your referral — consultant working with your contact'),
        Referral.STATUS_ON_HOLD: ('emails/05_on_hold.html',      'Update on your referral — waiting on your contact'),
        Referral.STATUS_RESOLVED:('emails/06_resolved.html',     'Great news — your referral has been resolved!'),
    }
    if internal_status in EMAIL_MAP and referral.referrer:
        template, subject = EMAIL_MAP[internal_status]
        send_referral_email(
            to_address    = referral.referrer.email,
            subject       = subject,
            template_name = template,
            context       = {'referrer': referral.referrer, 'referral': referral}
        )
    return jsonify({'updated': internal_status, 'referral_id': referral.id}), 200


@app.route('/api/mark-signed-up/<int:referral_id>', methods=['POST'])
def mark_signed_up(referral_id):
    secret = request.headers.get('X-Admin-Secret', '')
    if secret != 'admin_secret_empath_2025_secure':
        return jsonify({'error': 'Unauthorized'}), 401
    referral = db.session.get(Referral, referral_id)
    if not referral:
        return jsonify({'error': 'Referral not found'}), 404
    referral.status       = Referral.STATUS_SIGNED_UP
    referral.signed_up_at = datetime.utcnow()
    db.session.commit()
    if referral.referrer:
        send_referral_email(
            to_address    = referral.referrer.email,
            subject       = f"They signed up! Your referral of {referral.customer_name} was a success",
            template_name = 'emails/06_resolved.html',
            context       = {'referrer': referral.referrer, 'referral': referral}
        )
    return jsonify({'status': 'signed_up', 'referral_id': referral_id}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
