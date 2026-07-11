import hmac
import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template, request

from email_utils import send_referral_email
from extensions import db, require_env
from models import Referral, Referrer, generate_referral_code

referrals_bp = Blueprint('referrals', __name__)


@referrals_bp.route('/referrer-signup')
def referrer_signup_page():
    return render_template('signup.html')


@referrals_bp.route('/api/referrer-signup', methods=['POST'])
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


@referrals_bp.route('/api/referral-intake', methods=['GET', 'POST'])
def referral_intake():
    current_app.logger.info(f"Request method: {request.method}")
    current_app.logger.info(f"Request headers: {dict(request.headers)}")

    raw = request.get_data(as_text=True)
    current_app.logger.info(f"Request raw data: {raw}")

    data = {}
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            pass

    if not data:
        data = request.get_json(force=True, silent=True) or {}
    if not data:
        data = request.form.to_dict() or {}
    if not data:
        data = request.args.to_dict() or {}

    current_app.logger.info(f"Received referral intake data: {data}")

    def clean(val):
        val = (val or '').strip()
        # discard Zoho unreplaced placeholders
        if val.startswith('<') and val.endswith('>'):
            return ''
        return val

    customer_name = clean(
        data.get('customer_name') or
        data.get('Name1.First') or
        data.get('Name') or
        data.get('name')
    )

    customer_phone = clean(
        data.get('customer_phone') or
        data.get('PhoneNumber') or
        data.get('Phone') or
        data.get('phone') or
        data.get('Mobile')
    )

    customer_email = clean(
        data.get('customer_email') or
        data.get('Email') or
        data.get('email')
    )

    referral_code = clean(
        data.get('referral_code') or
        data.get('refferral_code') or
        data.get('SingleLine2') or
        data.get('Referral_Code') or
        data.get('code')
    ).upper()

    if not customer_name or not customer_phone:
        current_app.logger.error(f"Missing required fields. Name: '{customer_name}', Phone: '{customer_phone}'")
        return jsonify({'error': 'customer_name and customer_phone are required', 'received_data': data}), 400

    referrer = None
    if referral_code:
        try:
            db.session.close()
            referrer = Referrer.query.filter_by(referral_code=referral_code).first()
        except Exception as e:
            current_app.logger.error(f"DB error looking up referrer: {e}")

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
        current_app.logger.error(f"Database error saving referral: {e}")
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


@referrals_bp.route('/api/zoho-desk-webhook', methods=['POST'])
def zoho_desk_webhook():
    secret = request.headers.get('X-Webhook-Secret', '')
    if not hmac.compare_digest(secret, require_env('ZOHO_DESK_WEBHOOK_SECRET')):
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


@referrals_bp.route('/api/mark-signed-up/<int:referral_id>', methods=['POST'])
def mark_signed_up(referral_id):
    secret = request.headers.get('X-Admin-Secret', '')
    if not hmac.compare_digest(secret, require_env('ADMIN_API_SECRET')):
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
