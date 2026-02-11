from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import requests
import os
import json
import time
import hashlib
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask import send_from_directory
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
        {'service': 'Tech Consultation (Choosing devices/software)', 'price': 'R150 per consult (30–45 mins)',
         'icon': '🧠'},
        {'service': 'Basic Cybersecurity Check (firewall, antivirus)', 'price': 'R250', 'icon': '🔒'},
        {'service': 'Website Help (basic WordPress issues, updates)', 'price': 'R200 – R400 depending on issue',
         'icon': '🌐'},
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

if __name__ == '__main__':
    app.run()
