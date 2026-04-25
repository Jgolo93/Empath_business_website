from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
import os
import hashlib
import random
import string
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = '3326a6c76241b25be006e1a52c1d197ee23141c9f2'

# ── Database ──────────────────────────────────────────────────────
# Hardcoded to override .env placeholder
DATABASE_URL = "postgresql://neondb_owner:npg_2led5BIEjmnx@ep-misty-resonance-aeq4m318-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Create tables if they don't exist
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        app.logger.error(f"Database connection error: {e}")

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
    """Email subscribers for newsletter"""
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
    """Track likes on blog posts"""
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
    """Aggregated stats for blog posts"""
    __tablename__ = 'blog_post_stats'

    post_slug = db.Column(db.String(100), primary_key=True)
    like_count = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class PageView(db.Model):
    """Track page views"""
    __tablename__ = 'page_views'

    id = db.Column(db.Integer, primary_key=True)
    page_path = db.Column(db.String(200), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    viewed_at = db.Column(db.DateTime, default=db.func.now())
    referrer = db.Column(db.String(500), nullable=True)




class Lead(db.Model):
    """Lead magnet subscribers"""
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
    """Generate a human-readable unique referral code like REF-JASON-4821"""
    clean = ''.join(c for c in first_name.upper() if c.isalpha())[:8]
    suffix = ''.join(random.choices(string.digits, k=4))
    return f"REF-{clean}-{suffix}"


class Referrer(db.Model):
    """A person who refers customers to the business."""
    __tablename__ = 'referrers'

    id            = db.Column(db.Integer, primary_key=True)
    first_name    = db.Column(db.String(80),  nullable=False)
    last_name     = db.Column(db.String(80),  nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    phone         = db.Column(db.String(30),  unique=True, nullable=False)
    referral_code = db.Column(db.String(30),  unique=True, nullable=False)
    created_at    = db.Column(db.DateTime,    default=db.func.now())
    is_active     = db.Column(db.Boolean,     default=True)

    referrals = db.relationship('Referral', backref='referrer', lazy=True)

    def __repr__(self):
        return f'<Referrer {self.referral_code}>'


class Referral(db.Model):
    """A customer referred by a Referrer. Tracks their journey."""
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
    updated_at     = db.Column(db.DateTime, default=db.func.now(),
                               onupdate=db.func.now())
    signed_up_at   = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Referral {self.customer_name} [{self.status}]>'


# Create tables safely — won't crash the app if DB is temporarily unreachable
try:
    with app.app_context():
        db.create_all()
except Exception as e:
    print(f"Warning: Could not create database tables: {e}")

# ========================================
# ROUTES
# ========================================

@app.route('/')
def home():
    marketing_cards = [
        {
            'title': 'Is your computer running slow?',
            'content': 'Let us run diagnostics to see what we can do to improve your PC speed.',
            'icon': 'speed'
        },
        {
            'title': 'Quick Support',
            'content': 'Do you have a quick problem on your mobile you would like to resolve?',
            'icon': 'support_agent'
        },
        {
            'title': 'PC Upgrades',
            'content': 'Would you like to upgrade your computer for better performance?',
            'icon': 'upgrade'
        },
        {
            'title': 'Virus Protection',
            'content': 'Keep your data safe with our comprehensive virus removal services.',
            'icon': 'security'
        },
        {
            'title': 'Tech Consultation',
            'content': 'Not sure what device or software to choose? Let our experts guide you.',
            'icon': 'psychology'
        },
        {
            'title': 'Remote Assistance',
            'content': 'Get help without leaving your home or office. Quick, efficient support.',
            'icon': 'computer'
        }
    ]
    return render_template('index.html', marketing_cards=marketing_cards)

@app.route('/pricing')
def pricing():
    # Redirect to contact page for custom quotes
    return redirect(url_for('create_ticket'), code=301)

@app.route('/how-it-works')
def how_it_works():
    steps = [
        {
            'title': 'Create a Support Ticket',
            'description': 'Fill out our simple support form to let us know what issues you\'re experiencing.',
            'icon': 'confirmation_number'
        },
        {
            'title': 'Remote Support',
            'description': 'Our technicians can connect to your device remotely to diagnose and fix many issues without you needing to leave home.',
            'icon': 'computer'
        },
        {
            'title': 'On-site Service',
            'description': 'For more complex issues, we can arrange for your PC to be booked in for servicing at our workshop.',
            'icon': 'build'
        },
        {
            'title': 'Problem Solved',
            'description': 'We\'ll ensure your technology is working properly before completing the service.',
            'icon': 'check_circle'
        }
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

# Shop redirect (old shop endpoint removed, redirect to home)
@app.route('/shop')
def shop():
    return redirect(url_for('home'), code=301)

# Blog Routes
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

        if slug == 'cybersecurity-tips-small-business':
            return render_template('blog_cybersecurity_tips.html', view_count=view_count, like_count=like_count)
        elif slug == 'it-solutions-productivity-boost':
            return render_template('blog_productivity_boost.html', view_count=view_count, like_count=like_count)
        elif slug == 'glens-grass-case-study':
            return render_template('blog_glens_grass_case_study.html', view_count=view_count, like_count=like_count)
        elif slug == 'world-of-testing':
            return render_template('blog_world_of_testing.html', view_count=view_count, like_count=like_count)
        elif slug == 'robot-framework-browser-library':
            return render_template('blog_robot_framework.html', view_count=view_count, like_count=like_count)
        else:
            return render_template('blog.html')
    except Exception as e:
        if slug == 'cybersecurity-tips-small-business':
            return render_template('blog_cybersecurity_tips.html', view_count=0, like_count=0)
        elif slug == 'it-solutions-productivity-boost':
            return render_template('blog_productivity_boost.html', view_count=0, like_count=0)
        elif slug == 'glens-grass-case-study':
            return render_template('blog_glens_grass_case_study.html', view_count=0, like_count=0)
        elif slug == 'world-of-testing':
            return render_template('blog_world_of_testing.html', view_count=0, like_count=0)
        elif slug == 'robot-framework-browser-library':
            return render_template('blog_robot_framework.html', view_count=0, like_count=0)
        else:
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
    location = request.args.get('location')
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

    return f"""
    <h2>Token Exchange Result</h2>
    <pre>{token_data}</pre>
    """

# ========================================
# API ROUTES
# ========================================

@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Handle email subscription"""
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
    """Toggle like on blog post"""
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

        existing = BlogLike.query.filter_by(
            post_slug=post_slug,
            ip_address=ip_address,
            user_agent_hash=user_agent_hash
        ).first()

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
    """Get like count for a blog post"""
    try:
        count = BlogLike.query.filter_by(post_slug=post_slug).count()

        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '')
        user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:64]

        has_liked = BlogLike.query.filter_by(
            post_slug=post_slug,
            ip_address=ip_address,
            user_agent_hash=user_agent_hash
        ).first() is not None

        return jsonify({'success': True, 'count': count, 'hasLiked': has_liked}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/blog/view/<post_slug>', methods=['POST'])
def track_blog_view(post_slug):
    """Track a view for a blog post"""
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
    """Get likes and views for a blog post"""
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
    """Handle lead magnet form submission"""
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

        # Retry logic for SSL connection issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Create new connection for each attempt
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
                    time.sleep(0.5)  # Brief delay before retry
                    continue
                raise

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Something went wrong. Please try again.'}), 500


@app.route('/download/the-journey')
def download_lead_magnet():
    """Serve the lead magnet PDF after verifying lead submission"""
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
# ZOHO DESK API - TEMPORARILY DISABLED
# ========================================
# To re-enable: Update OAuth credentials above and uncomment all code below

# def get_zoho_access_token():
#     """Get a valid access token, refreshing if necessary"""
#     global ACCESS_TOKEN_INFO
#
#     if ACCESS_TOKEN_INFO['access_token'] and time.time() < (ACCESS_TOKEN_INFO['expires_at'] - 300):
#         return ACCESS_TOKEN_INFO['access_token']
#
#     token_url = f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token"
#
#     payload = {
#         'grant_type': 'refresh_token',
#         'client_id': ZOHO_CLIENT_ID,
#         'client_secret': ZOHO_CLIENT_SECRET,
#         'refresh_token': ZOHO_REFRESH_TOKEN
#     }
#
#     try:
#         response = requests.post(token_url, data=payload, timeout=30)
#         print(f"Token refresh status: {response.status_code}")
#         print(f"Token response: {response.text[:500]}")
#
#         if response.status_code == 200:
#             token_data = response.json()
#             ACCESS_TOKEN_INFO['access_token'] = token_data['access_token']
#             expires_in = token_data.get('expires_in', 3600)
#             ACCESS_TOKEN_INFO['expires_at'] = time.time() + expires_in
#             return ACCESS_TOKEN_INFO['access_token']
#         else:
#             print(f"Token refresh failed: {response.text}")
#             return None
#
#     except Exception as e:
#         print(f"Exception during token refresh: {e}")
#         import traceback
#         traceback.print_exc()
#         return None
#
#
# @app.route('/api/tickets', methods=['POST'])
# def create_zoho_ticket():
#     """Create a ticket in Zoho Desk via API"""
#     try:
#         data = request.get_json()
#
#         required_fields = ['firstName', 'lastName', 'email', 'subject', 'description']
#         for field in required_fields:
#             if not data.get(field):
#                 return jsonify({'success': False, 'error': f'{field} is required'}), 400
#
#         # Get consent data
#         consent_newsletter = data.get('consentNewsletter', False)
#         consent_sms = data.get('consentSMS', False)
#
#         access_token = get_zoho_access_token()
#         if not access_token:
#             return jsonify({'success': False, 'error': 'Unable to authenticate with Zoho Desk. Please contact support.'}), 500
#
#         # Build description with consent info
#         description = data.get('description', '')
#         consent_info = []
#         if consent_newsletter:
#             consent_info.append("Newsletter consent: YES")
#         else:
#             consent_info.append("Newsletter consent: NO")
#         if consent_sms:
#             consent_info.append("SMS consent: YES")
#         else:
#             consent_info.append("SMS consent: NO")
#
#         # Add consent info to description
#         description += "\n\n---\n" + "\n".join(consent_info)
#
#         ticket_data = {
#             'subject': data.get('subject'),
#             'description': description,
#             'email': data.get('email'),
#             'lastName': data.get('lastName'),
#             'firstName': data.get('firstName'),
#             'departmentId': ZOHO_DESK_DEPARTMENT_ID,
#             'priority': data.get('priority', 'Medium'),
#             'channel': 'Web'
#         }
#
#         if data.get('phone'):
#             ticket_data['phone'] = data.get('phone')
#         if data.get('company'):
#             ticket_data['company'] = data.get('company')
#
#         headers = {
#             'Authorization': f'Zoho-oauthtoken {access_token}',
#             'orgId': ZOHO_DESK_ORG_ID,
#             'Content-Type': 'application/json'
#         }
#
#         ticket_url = f'https://{ZOHO_DESK_DOMAIN}/api/v1/tickets'
#
#         response = requests.post(
#             ticket_url,
#             headers=headers,
#             json=ticket_data,
#             timeout=30
#         )
#
#         if response.status_code in [200, 201]:
#             result = response.json()
#             ticket_id = result.get('id')
#             ticket_number = result.get('ticketNumber', 'Unknown')
#
#             return jsonify({
#                 'success': True,
#                 'ticketId': ticket_id,
#                 'ticketNumber': ticket_number,
#                 'message': 'Ticket created successfully'
#             }), 201
#         else:
#             error_data = response.json()
#             print(f"Zoho API error: {response.status_code} - {error_data}")
#             return jsonify({
#                 'success': False,
#                 'error': f'Zoho API error: {error_data}'
#             }), 500
#
#     except Exception as e:
#         print(f"Error creating ticket: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({'success': False, 'error': 'An error occurred while creating the ticket'}), 500



# Helper function to send referral emails
def send_referral_email(to_address, subject, template_name, context):
    """
    Renders a Jinja2 email template and sends it via Flask-Mail.
    template_name is a path like 'emails/01_welcome.html'
    context is a dict passed to the template as variables.
    Fails silently with a log — never crash the main request.
    """
    try:
        print(f"[EMAIL SENDING] to={to_address} subject={subject} template={template_name}")
        html_body = render_template(template_name, **context)
        msg = Message(
            subject    = subject,
            recipients = [to_address],
            html       = html_body
        )
        mail.send(msg)
        print(f"[EMAIL SENT SUCCESS] to={to_address}")
    except Exception as e:
        print(f"[EMAIL FAILED] to={to_address} template={template_name} error={e}")
        app.logger.error(f"[EMAIL FAILED] to={to_address} template={template_name} error={e}")


# ========================================
# REFERRAL PROGRAMME ROUTES
# ========================================

# --- ROUTE 1: Serve the referrer signup page ---
@app.route('/referrer-signup')
def referrer_signup_page():
    """Serves the HTML page where referrers register."""
    return render_template('signup.html')


# --- ROUTE 2: Process the referrer signup form submission ---
@app.route('/api/referrer-signup', methods=['POST'])
def referrer_signup():
    """
    Accepts JSON: {first_name, last_name, email, phone}
    Creates a Referrer row, generates their code, sends welcome email.
    Returns JSON: {referral_code, message} or {error}
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data received'}), 400

    required = ['first_name', 'last_name', 'email', 'phone']
    for field in required:
        if not data.get(field, '').strip():
            return jsonify({'error': f'{field} is required'}), 400

    # Check for duplicates — phone and email must be unique
    if Referrer.query.filter_by(email=data['email'].strip().lower()).first():
        return jsonify({'error': 'This email address is already registered'}), 409
    if Referrer.query.filter_by(phone=data['phone'].strip()).first():
        return jsonify({'error': 'This phone number is already registered'}), 409

    # Generate a unique code — loop to handle the tiny chance of collision
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


# --- ROUTE 3: Zoho Forms webhook — fires when a prospect submits the contact form ---
@app.route('/api/referral-intake', methods=['GET', 'POST'])
def referral_intake():
    """
    Called by Zoho Forms webhook when a prospect submits the contact form.
    Expected JSON keys: customer_name, customer_phone, customer_email (optional),
                        referral_code (optional — the code entered by the prospect)
    Creates a Referral row linked to the Referrer who owns that code.
    Sends the referrer an email saying their person has submitted.
    """
    try:
        data = request.get_json()
    except Exception as e:
        app.logger.error(f"Error parsing JSON: {e}")
        data = request.form.to_dict()
    
    # If still empty, try args
    if not data:
        data = request.args.to_dict()

    # Log incoming data for debugging
    app.logger.info(f"Received referral intake data: {data}")

    # Try multiple possible field names from Zoho Forms
    customer_name = (
        data.get('customer_name', '') or 
        data.get('Name', '') or 
        data.get('name', '') or
        ''
    ).strip()
    
    customer_phone = (
        data.get('customer_phone', '') or 
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
        data.get('Referral_Code', '') or 
        data.get('Referral Code', '') or 
        data.get('code', '') or
        ''
    ).strip().upper()

    if not customer_name or not customer_phone:
        app.logger.error(f"Missing required fields. Name: '{customer_name}', Phone: '{customer_phone}'")
        return jsonify({'error': 'customer_name and customer_phone are required', 'received_data': data}), 400

    # Find the referrer by code — if no valid code just log unlinked
    referrer = None
    if referral_code:
        referrer = Referrer.query.filter_by(referral_code=referral_code).first()

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

    # Only email the referrer if we successfully linked to one
    if referrer:
        send_referral_email(
            to_address    = referrer.email,
            subject       = f"Update: {customer_name} has submitted their details",
            template_name = 'emails/02_submitted.html',
            context       = {'referrer': referrer, 'referral': referral}
        )

    return jsonify({'status': 'received', 'referral_id': referral.id}), 200


# --- ROUTE 4: Zoho Desk webhook — fires on every ticket status change ---
@app.route('/api/zoho-desk-webhook', methods=['POST'])
def zoho_desk_webhook():
    """
    Called by Zoho Desk Workflow Automation when a ticket status changes.
    Requires header: X-Webhook-Secret matching env var ZOHO_WEBHOOK_SECRET.

    Expected JSON body from Zoho Desk:
    {
      "ticketId": "123456",
      "status": "In Progress",
      "customerPhone": "0821234567"
    }

    This route:
    1. Validates the secret header
    2. Maps Zoho Desk status strings to internal status constants
    3. Finds the Referral row by ticket ID (or falls back to phone number)
    4. Updates the status
    5. Emails the referrer with the appropriate status update email
    """
    # Validate the shared secret so random people can't call this
    secret = request.headers.get('X-Webhook-Secret', '')
    if secret != 'zoho_webhook_secret_empath_2025_secure':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON body'}), 400

    ticket_id      = str(data.get('ticketId', '')).strip()
    zoho_status    = data.get('status', '').strip().lower().replace(' ', '_')
    customer_phone = data.get('customerPhone', '').strip()

    # Map Zoho Desk status strings → internal status constants
    # Add more mappings here if Zoho uses different status names in your setup
    STATUS_MAP = {
        'open':        Referral.STATUS_OPEN,
        'in_progress': Referral.STATUS_IN_PROG,
        'on_hold':     Referral.STATUS_ON_HOLD,
        'resolved':    Referral.STATUS_RESOLVED,
    }

    internal_status = STATUS_MAP.get(zoho_status)
    if not internal_status:
        # We don't have an email for this status — that's fine, just skip
        return jsonify({'skipped': True, 'reason': f'No mapping for status: {zoho_status}'}), 200

    # Try to find the referral by ticket ID first
    referral = None
    if ticket_id:
        referral = Referral.query.filter_by(zoho_ticket_id=ticket_id).first()

    # Fallback: match by customer phone number (needed when ticket ID is new)
    if not referral and customer_phone:
        referral = Referral.query.filter_by(
            customer_phone=customer_phone
        ).order_by(Referral.created_at.desc()).first()

    if not referral:
        return jsonify({'error': 'Referral not found'}), 404

    # Save the ticket ID now that we have it (for future status updates)
    if ticket_id:
        referral.zoho_ticket_id = ticket_id

    referral.status = internal_status
    db.session.commit()

    # Send the appropriate email to the referrer
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


# --- ROUTE 5: Admin endpoint — mark a customer as signed up ---
@app.route('/api/mark-signed-up/<int:referral_id>', methods=['POST'])
def mark_signed_up(referral_id):
    """
    Called manually by your team when a customer signs the service contract.
    This is NOT triggered by Zoho — your team calls it via Postman or
    an internal tool when they confirm a sign-up.

    Requires header: X-Admin-Secret matching env var ADMIN_SECRET

    Example curl call:
    curl -X POST https://yoursite.com/api/mark-signed-up/42 \
         -H "X-Admin-Secret: your-secret-here"
    """
    secret = request.headers.get('X-Admin-Secret', '')
    if secret != 'admin_secret_empath_2025_secure':
        return jsonify({'error': 'Unauthorized'}), 401

    referral = db.session.get(Referral, referral_id)
    if not referral:
        return jsonify({'error': 'Referral not found'}), 404

    referral.status      = Referral.STATUS_SIGNED_UP
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
