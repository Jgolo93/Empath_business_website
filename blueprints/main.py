import os
import re
import time

from flask import Blueprint, jsonify, redirect, render_template, request, send_from_directory, url_for

import shopify_client as shopify
from extensions import db
from models import Lead, Subscriber

main_bp = Blueprint('main', __name__)

BRANDS_CARRIED = ['Acer', 'ASRock', 'ASUS', 'Giada', 'MINISFORUM', 'Nplay', 'PCBuilder']

# Curated subset of shop collections to feature on the homepage — the highest-traffic,
# most broadly appealing categories rather than the full catalog (kept in this display order).
FEATURED_CATEGORY_HANDLES = [
    'computers', 'components', 'networking-security', 'storage-drives',
    'computer-peripherals', 'power-supplies', 'tv-audio', 'appliances',
]

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


@main_bp.route('/')
def home():
    marketing_cards = [
        {'title': 'Is your computer running slow?', 'content': 'Let us run diagnostics to see what we can do to improve your PC speed.', 'icon': 'speed'},
        {'title': 'Quick Support', 'content': 'Do you have a quick problem on your mobile you would like to resolve?', 'icon': 'support_agent'},
        {'title': 'PC Upgrades', 'content': 'Would you like to upgrade your computer for better performance?', 'icon': 'upgrade'},
        {'title': 'Virus Protection', 'content': 'Keep your data safe with our comprehensive virus removal services.', 'icon': 'security'},
        {'title': 'Tech Consultation', 'content': 'Not sure what device or software to choose? Let our experts guide you.', 'icon': 'psychology'},
        {'title': 'Remote Assistance', 'content': 'Get help without leaving your home or office. Quick, efficient support.', 'icon': 'computer'}
    ]
    featured_products = []
    featured_categories = []
    try:
        collection = shopify.get_collection_products('new-arrivals', first=8, sort_key='BEST_SELLING')
        featured_products = [edge['node'] for edge in collection['products']['edges']] if collection else []
    except (shopify.ShopifyError, RuntimeError):
        pass  # Shop section just doesn't render — rest of the homepage isn't Shopify-dependent.

    try:
        all_collections = {c['handle']: c for c in shopify.get_collections(first=50)}
        featured_categories = [all_collections[h] for h in FEATURED_CATEGORY_HANDLES if h in all_collections]
    except (shopify.ShopifyError, RuntimeError):
        pass

    return render_template(
        'index.html',
        marketing_cards=marketing_cards,
        featured_products=featured_products,
        featured_categories=featured_categories,
        brands_carried=BRANDS_CARRIED,
    )


@main_bp.route('/pricing')
def pricing():
    return redirect(url_for('support.create_ticket'), code=301)


@main_bp.route('/how-it-works')
def how_it_works():
    steps = [
        {'title': 'Create a Support Ticket', 'description': 'Fill out our simple support form to let us know what issues you\'re experiencing.', 'icon': 'confirmation_number'},
        {'title': 'Remote Support', 'description': 'Our technicians can connect to your device remotely to diagnose and fix many issues without you needing to leave home.', 'icon': 'computer'},
        {'title': 'On-site Service', 'description': 'For more complex issues, we can arrange for your PC to be booked in for servicing at our workshop.', 'icon': 'build'},
        {'title': 'Problem Solved', 'description': 'We\'ll ensure your technology is working properly before completing the service.', 'icon': 'check_circle'}
    ]
    return render_template('how_it_works.html', steps=steps)


@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/sitemap.xml')
def sitemap():
    return send_from_directory(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sitemap.xml')


@main_bp.route('/zohoverify/verifyforzoho.html')
def zohoverify():
    return render_template('verifyforzoho.html')


@main_bp.route('/terms')
def terms():
    return render_template('terms.html')


@main_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')


@main_bp.route('/subscribe', methods=['POST'])
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


@main_bp.route('/api/leads', methods=['POST'])
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
                    time.sleep(0.5)
                    continue
                raise
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Something went wrong. Please try again.'}), 500


@main_bp.route('/download/the-journey')
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
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'pdfs'),
            'the-journey.pdf',
            as_attachment=True,
            download_name='The Journey - By Jason Goliath.pdf'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
