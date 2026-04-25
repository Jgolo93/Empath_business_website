"""
================================================================================
REFERRAL SYNC - POLL ZOHO DESK FOR TICKET STATUS & UPDATE REFERRAL DB
================================================================================
This script runs via cron to:
1. Fetch active tickets from Zoho Desk
2. Match tickets to referrals by phone number or ticket ID
3. Update referral status based on ticket status
4. Send referral emails when status changes
================================================================================
"""

import requests
import os
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from flask_mail import Mail, Message
from flask import Flask, render_template

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── DATABASE CONFIG ───────────────────────────────────────────────────────
DATABASE_URL = "postgresql://neondb_owner:npg_2led5BIEjmnx@ep-misty-resonance-aeq4m318-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# ── ZOHO DESK CREDENTIALS ───────────────────────────────────────────────────
ZOHO_ORG_ID = '887430547'
ZOHO_CLIENT_ID = '1000.OCP7ADAC99HLRYU5VPU91VMV1A1VJI'
ZOHO_CLIENT_SECRET = '3326a6c76241b25be006e1a52c1d197ee23141c9f2'
ZOHO_REFRESH_TOKEN = '1000.688f80d0c13bf90c0e441746486681a9.4ecc8a486d5e1751fd655d6266969f71'
ZOHO_ACCOUNTS_URL = 'https://accounts.zoho.com'
ZOHO_API_DOMAIN = 'https://desk.zoho.com'

ZOHO_ACCESS_TOKEN = None

# ── EMAIL CONFIG (ZOHO MAIL) ───────────────────────────────────────────────
MAIL_SERVER = 'smtp.zoho.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'jason.goliath@empathtechnologysolutions.com'
MAIL_PASSWORD = '4dubCZHtMXbk'
MAIL_DEFAULT_SENDER = 'Empath Technology Solutions <jason.goliath@empathtechnologysolutions.com>'

# ── STATUS MAPPINGS ───────────────────────────────────────────────────────
# Zoho Desk status → Internal referral status
STATUS_MAP = {
    'Open': 'open',
    'In Progress': 'in_progress',
    'On Hold': 'on_hold',
    'Waiting For Feedback': 'awaiting_feedback',
    'Awaiting Feedback': 'awaiting_feedback',
    'Closed': 'resolved',
    'Resolved': 'resolved',
    'Done': 'signed_up',  # Commission is paid when status is Done (after customer pays)
}

# ── ZOHO TOKEN REFRESH ─────────────────────────────────────────────────────
def refresh_zoho_access_token():
    url = f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token"
    params = {
        'refresh_token': ZOHO_REFRESH_TOKEN,
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'grant_type': 'refresh_token'
    }
    try:
        resp = requests.post(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            token = data.get('access_token')
            if token:
                logger.info('✅ Successfully refreshed Zoho access token')
                return token
            else:
                logger.error(f"❌ Refresh response missing access_token: {data}")
                return None
        else:
            logger.error(f"❌ Zoho refresh failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        logger.error(f"❌ Exception while refreshing Zoho token: {e}")
        return None

def get_zoho_access_token():
    global ZOHO_ACCESS_TOKEN
    ZOHO_ACCESS_TOKEN = refresh_zoho_access_token()
    return ZOHO_ACCESS_TOKEN

# ── DATABASE FUNCTIONS ─────────────────────────────────────────────────────
def get_db_connection():
    """Get a database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None

def get_referral_by_phone(phone):
    """Find a referral by customer phone number"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Clean phone number (remove spaces, dashes, etc.)
            clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
            cur.execute(
                "SELECT * FROM referrals WHERE REPLACE(customer_phone, ' ', '') = REPLACE(%s, ' ', '') ORDER BY created_at DESC LIMIT 1",
                (clean_phone,)
            )
            return cur.fetchone()
    except Exception as e:
        logger.error(f"❌ Error fetching referral by phone: {e}")
        return None
    finally:
        conn.close()

def get_referral_by_ticket_id(ticket_id):
    """Find a referral by Zoho ticket ID"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM referrals WHERE zoho_ticket_id = %s", (str(ticket_id),))
            return cur.fetchone()
    except Exception as e:
        logger.error(f"❌ Error fetching referral by ticket ID: {e}")
        return None
    finally:
        conn.close()

def get_referral_by_phone_no_ticket(phone):
    """Find referral by phone number ONLY if they don't have a ticket ID linked"""
    if not phone:
        return None
    
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Clean phone number for comparison
            clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
            cur.execute(
                "SELECT * FROM referrals WHERE REPLACE(customer_phone, ' ', '') = REPLACE(%s, ' ', '') AND zoho_ticket_id IS NULL ORDER BY created_at DESC LIMIT 1",
                (clean_phone,)
            )
            return cur.fetchone()
    except Exception as e:
        logger.error(f"❌ Error fetching referral by phone (no ticket): {e}")
        return None
    finally:
        conn.close()

def update_referral_status(referral_id, new_status, ticket_id=None):
    """Update referral status and optionally link ticket ID"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            if ticket_id:
                cur.execute(
                    "UPDATE referrals SET status = %s, zoho_ticket_id = %s, updated_at = NOW() WHERE id = %s",
                    (new_status, str(ticket_id), referral_id)
                )
            else:
                cur.execute(
                    "UPDATE referrals SET status = %s, updated_at = NOW() WHERE id = %s",
                    (new_status, referral_id)
                )
            conn.commit()
            logger.info(f"✅ Updated referral {referral_id} to status: {new_status}")
            return True
    except Exception as e:
        logger.error(f"❌ Error updating referral status: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_referrer_details(referrer_id):
    """Get referrer details for email sending"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM referrers WHERE id = %s", (referrer_id,))
            return cur.fetchone()
    except Exception as e:
        logger.error(f"❌ Error fetching referrer details: {e}")
        return None
    finally:
        conn.close()

# ── EMAIL FUNCTIONS ───────────────────────────────────────────────────────
def send_referral_email(to_address, subject, template_name, context):
    """Send referral email using Flask-Mail with HTML template rendering"""
    try:
        import os
        # Create a minimal Flask app for mail with template folder
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app = Flask(__name__, template_folder=os.path.join(current_dir, 'templates'))
        app.config['MAIL_SERVER'] = MAIL_SERVER
        app.config['MAIL_PORT'] = MAIL_PORT
        app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
        app.config['MAIL_USERNAME'] = MAIL_USERNAME
        app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
        app.config['MAIL_DEFAULT_SENDER'] = MAIL_DEFAULT_SENDER
        
        mail = Mail(app)
        
        with app.app_context():
            # Render HTML template
            html_body = render_template(template_name, **context)
            
            # Create message with both HTML and plain text
            msg = Message(
                subject=subject,
                recipients=[to_address],
                sender=MAIL_DEFAULT_SENDER,
                html=html_body
            )
            
            # Add plain text fallback
            referral_name = context.get('referral', {}).get('customer_name', 'your referral')
            msg.body = f"Update regarding {referral_name}. Please view this email in an HTML-capable client."
            
            mail.send(msg)
            logger.info(f"✅ Email sent to {to_address}: {subject} (HTML template: {template_name})")
            return True
    except Exception as e:
        logger.error(f"❌ Error sending email: {e}")
        return False

# ── FETCH TICKETS FROM ZOHO DESK ─────────────────────────────────────────
def fetch_all_active_tickets():
    """Fetch all active tickets from Zoho Desk"""
    try:
        url = f"{ZOHO_API_DOMAIN}/api/v1/tickets?sortBy=-modifiedTime&limit=100"
        token = get_zoho_access_token()
        if not token:
            logger.error('❌ No Zoho access token available')
            return []

        response = requests.get(
            url,
            headers={
                'orgId': ZOHO_ORG_ID,
                'Authorization': f'Zoho-oauthtoken {token}'
            },
            timeout=20
        )

        if response.status_code != 200:
            logger.error(f"❌ Zoho API error: {response.status_code} - {response.text}")
            return []

        data = response.json()
        raw_tickets = data.get('data', [])
        logger.info(f"🔎 Zoho returned {len(raw_tickets)} tickets")

        tickets = []
        for t in raw_tickets:
            if isinstance(t, str):
                try:
                    import json
                    t = json.loads(t)
                except Exception:
                    continue
            elif not isinstance(t, dict):
                continue
            tickets.append(t)

        logger.info(f"✅ Processed {len(tickets)} valid tickets")
        return tickets

    except Exception as error:
        logger.error(f"❌ Error fetching tickets: {error}")
        return []

# ── PROCESS TICKET ─────────────────────────────────────────────────────────
def process_ticket(ticket):
    """Process a single ticket and update referral if matched"""
    ticket_id = ticket.get('id')
    ticket_number = ticket.get('ticketNumber')
    status = (ticket.get('status') or '').strip()
    phone = ticket.get('phone')
    
    if not status:
        return f"⏭️ #{ticket_number}: No status"
    
    # Map Zoho status to internal status
    internal_status = STATUS_MAP.get(status, status.lower().replace(' ', '_'))
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing Ticket #{ticket_number}")
    logger.info(f"  Status: {status} → {internal_status}")
    logger.info(f"  Phone: {phone}")
    
    # Try to find referral by ticket ID first (most specific)
    referral = get_referral_by_ticket_id(ticket_id)
    
    if not referral and phone:
        # Only match by phone if no ticket ID match AND referral doesn't already have a ticket ID
        # This prevents multiple tickets with same phone from updating same referral
        referral = get_referral_by_phone_no_ticket(phone)
    
    if not referral:
        return f"⏭️ #{ticket_number}: No matching referral"
    
    logger.info(f"  ✓ Matched referral ID: {referral['id']}")
    logger.info(f"  Current referral status: {referral['status']}")
    
    # Check if status changed
    if referral['status'] == internal_status:
        return f"⏭️ #{ticket_number}: Status unchanged ({internal_status})"
    
    # Update the referral status
    update_referral_status(referral['id'], internal_status, ticket_id)
    
    # Update referral object with new status for email
    referral['status'] = internal_status
    referral['zoho_ticket_id'] = ticket_id
    
    # Send email to referrer if they exist
    if referral['referrer_id']:
        referrer = get_referrer_details(referral['referrer_id'])
        if referrer:
            # Determine which email template to use
            template_map = {
                'open': 'emails/03_ticket_open.html',
                'in_progress': 'emails/04_in_progress.html',
                'on_hold': 'emails/05_on_hold.html',
                'awaiting_feedback': 'emails/05_on_hold.html',  # Use on_hold template for awaiting feedback
                'resolved': 'emails/06_resolved.html',  # Use resolved template for resolved status
                'signed_up': 'emails/06_resolved.html',  # Commission email when Done (customer paid)
            }

            template_name = template_map.get(internal_status)
            if template_name:
                # Consistent subjects based on status
                subject_map = {
                    'open': f"Support Ticket Opened for {referral['customer_name']}",
                    'in_progress': f"Support in Progress for {referral['customer_name']}",
                    'on_hold': f"Support on Hold for {referral['customer_name']}",
                    'awaiting_feedback': f"Awaiting Feedback from {referral['customer_name']}",
                    'resolved': f"Support Completed for {referral['customer_name']}",
                    'signed_up': f"Commission Paid! {referral['customer_name']} has signed up and paid",
                }
                
                subject = subject_map.get(internal_status, f"Update: {referral['customer_name']}'s ticket status changed to {status}")

                send_referral_email(
                    to_address=referrer['email'],
                    subject=subject,
                    template_name=template_name,
                    context={'referrer': referrer, 'referral': referral}
                )
    
    return f"✅ #{ticket_number}: Updated to {internal_status}"

# ── MAIN ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 80)
    print(f"🚀 REFERRAL SYNC - ZOHO DESK POLLING")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    print("\n🔍 Fetching tickets from Zoho Desk...")
    tickets = fetch_all_active_tickets()

    if not tickets:
        print("   No tickets to process. All done! ✨")
        return

    print(f"\n⚙️ Processing {len(tickets)} tickets...\n")
    updated_count = 0

    for i, ticket in enumerate(tickets, 1):
        result = process_ticket(ticket)
        print(f"[{i}/{len(tickets)}] {result}")
        if "✅" in result:
            updated_count += 1

    print("\n" + "=" * 80)
    print(f"✨ COMPLETED SUCCESSFULLY!")
    print(f"📊 Summary:")
    print(f"   - Tickets processed: {len(tickets)}")
    print(f"   - Referrals updated: {updated_count}")
    print("=" * 80)

if __name__ == "__main__":
    main()
