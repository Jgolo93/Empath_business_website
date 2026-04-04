from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import requests
import os
import json
import time
import hashlib
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask import send_from_directory
from flask_sqlalchemy import SQLAlchemy

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', '3326a6c76241b25be006e1a52c1d197ee23141c9f2')

# Zoho Desk OAuth configuration - TEMPORARILY DISABLED
# To re-enable: Update OAuth credentials and uncomment these lines
# ZOHO_CLIENT_ID = '1000.OCP7ADAC99HLRYU5VPU91VMV1A1VJI'
# ZOHO_CLIENT_SECRET = '3326a6c76241b25be006e1a52c1d197ee23141c9f2'
# ZOHO_REFRESH_TOKEN = '1000.dca392a320b7c2a2bb23b5eb483305d9.a69c286a8e5631b6b7661a25d3603a82'
# ZOHO_DESK_DOMAIN = 'desk.zoho.eu'
# ZOHO_DESK_ORG_ID = '887430547'
# ZOHO_DESK_DEPARTMENT_ID = '1129372000000006907'
# ZOHO_ACCOUNTS_URL = 'https://accounts.zoho.eu'

# Store access token in memory (in production, use a proper cache or database)
# ACCESS_TOKEN_INFO = {
#     'access_token': None,
#     'expires_at': 0
# }

# ========================================
# DATABASE SETUP - PostgreSQL (Neon)
# ========================================

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    "postgresql://neondb_owner:npg_2led5BIEjmnx@ep-misty-resonance-aeq4m318-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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


if __name__ == '__main__':
    app.run()
