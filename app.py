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

# Zoho Desk OAuth configuration
ZOHO_CLIENT_ID = '1000.OCP7ADAC99HLRYU5VPU91VMV1A1VJI'
ZOHO_CLIENT_SECRET = '3326a6c76241b25be006e1a52c1d197ee23141c9f2'
ZOHO_REFRESH_TOKEN = '1000.dca392a320b7c2a2bb23b5eb483305d9.a69c286a8e5631b6b7661a25d3603a82'
ZOHO_DESK_DOMAIN = 'desk.zoho.com'
ZOHO_DESK_ORG_ID = '887430547'
ZOHO_DESK_DEPARTMENT_ID = '1129372000000006907'
ZOHO_ACCOUNTS_URL = 'https://accounts.zoho.com'

# Store access token in memory (in production, use a proper cache or database)
ACCESS_TOKEN_INFO = {
    'access_token': None,
    'expires_at': 0
}

# ========================================
# DATABASE SETUP - PostgreSQL (Neon)
# ========================================

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    "postgresql://neondb_owner:npg_lrP2yC6eDTkX@ep-withered-hill-a4aa78xf-pooler.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require"
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
    standard_services = [
        {'service': 'Remote Assistance', 'standard': 'R150 per session (up to 45 mins)',
         'emergency': 'R300 per session (up to 45 mins)', 'icon': '💬'},
        {'service': 'Diagnostics Only', 'standard': 'R100 flat rate', 'emergency': 'R200 flat rate', 'icon': '🔧'},
        {'service': 'Virus & Malware Removal', 'standard': 'From R250', 'emergency': 'From R400', 'icon': '🛡️'},
        {'service': 'Full Laptop Service', 'standard': 'R350–R500 (incl. cleaning & updates)', 'emergency': 'R550–R700',
         'icon': '🖥️'}
    ]

    additional_services = [
        {'service': 'Google/Microsoft License Reseller', 'price': 'Quote-based', 'icon': '🔑'},
        {'service': 'Data Backup Solutions', 'price': 'Quote-based', 'icon': 'save'},
        {'service': 'Laptop & PC Hardware Upgrades', 'price': 'Quote-based', 'note': 'Cost of parts is required upfront.', 'icon': 'upgrade'},
        {'service': 'Network Setup (Remote)', 'price': 'Quote-based', 'note': 'For small businesses and personal setups.', 'icon': 'wifi'},
        {'service': 'Logo Design', 'price': 'Quote-based', 'icon': 'palette'},
        {'service': 'Tech Consultation (Choosing devices/software)', 'price': 'R150 per consult (30–45 mins)', 'icon': '🧠'},
        {'service': 'Basic Cybersecurity Check (firewall, antivirus)', 'price': 'R250', 'icon': '🔒'},
        {'service': 'Website Help (basic WordPress issues, updates)', 'price': 'R200 – R400 depending on issue', 'icon': '🌐'},
        {'service': 'Phone/Tablet Setup & Optimization', 'price': 'R150 – R300', 'icon': '📱'},
        {'service': 'Monitor / Dual Display Setup', 'price': 'R150 – R250', 'icon': '🖥️'},
        {'service': 'Keyboard & Mouse Troubleshooting', 'price': 'R100', 'icon': '⌨️'},
        {'service': 'Driver & Software Update Pack', 'price': 'R200', 'icon': '🧩'},
        {'service': 'Old PC to New PC Data Transfer (via USB/drive)', 'price': 'R250 – R450', 'icon': '📂'},
        {'service': 'Software Uninstall + Clean Up (bloatware, trialware)', 'price': 'R200', 'icon': '📦'},
        {'service': 'Password Recovery (local PC accounts)', 'price': 'R150 – R300 (depends on case)', 'icon': '🔐'},
        {'service': 'Email Setup (Outlook/Gmail/Thunderbird)', 'price': 'R150 per account', 'icon': '🌍'},
        {'service': 'Parental Controls Setup / Online Safety Settings', 'price': 'R200 – R300', 'icon': '🛡️'},
        {'service': '1-on-1 Training (basic PC usage / Office tools)', 'price': 'R200/hr', 'icon': '🧑‍🏫'},
        {'service': 'IT Audit for Home Office or Small Business', 'price': 'R300 flat or R150/hr', 'icon': '🧾'},
        {'service': 'Removing Pop-Ups / Fake Virus Warnings', 'price': 'R200', 'icon': '🛑'},
        {'service': 'Setting Up Cloud Backup (Google Drive, OneDrive)', 'price': 'R250', 'icon': '🔁'},
        {'service': 'Organizing Files + Storage Clean-Up', 'price': 'R150 – R250', 'icon': '📁'},
        {'service': 'External Hard Drive Setup / Repair Check', 'price': 'R200 – R350', 'icon': '💾'},
        {'service': 'Router Configuration (Static IP, port forwarding)', 'price': 'R300', 'icon': '📡'},
        {'service': 'Custom PC Builds', 'price': 'Quote-based', 'note': 'Cost of parts is required upfront.', 'icon': '🖥️'},
        {'service': 'Courier Service (Laptop/PC)', 'price': 'R150 - R250', 'note': 'Upfront cost for laptop/PC retrieval and delivery.', 'icon': '🚚'}
    ]

    bundles = [
        {'name': 'PC Tune-Up Package', 'services': 'Cleaning, optimization, software updates, virus check',
         'price': 'R400', 'icon': '🔧'},
        {'name': 'Secure Setup Bundle', 'services': 'Antivirus install, firewall check, password & browser hardening',
         'price': 'R350', 'icon': '🛡️'},
        {'name': 'New Device Starter Pack', 'services': 'Software install, user setup, data transfer, training',
         'price': 'R500', 'icon': '💻'}
    ]

    return render_template('pricing.html',
                           standard_services=standard_services,
                           additional_services=additional_services,
                           bundles=bundles)

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
        else:
            return render_template('blog.html')
    except Exception as e:
        if slug == 'cybersecurity-tips-small-business':
            return render_template('blog_cybersecurity_tips.html', view_count=0, like_count=0)
        elif slug == 'it-solutions-productivity-boost':
            return render_template('blog_productivity_boost.html', view_count=0, like_count=0)
        elif slug == 'glens-grass-case-study':
            return render_template('blog_glens_grass_case_study.html', view_count=0, like_count=0)
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

if __name__ == '__main__':
    app.run()