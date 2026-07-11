import os

import requests
from flask import Blueprint, current_app, render_template, request

from extensions import require_env

support_bp = Blueprint('support', __name__)


@support_bp.route('/create-ticket')
def create_ticket():
    return render_template('create_ticket.html')


@support_bp.route('/ticket-success')
def ticket_success():
    ticket_id = request.args.get('id', 'Unknown')
    subject = request.args.get('subject', 'Your support request')
    return render_template('ticket_success.html', ticket_id=ticket_id, subject=subject)


@support_bp.route('/oauth/callback')
def oauth_callback():
    code = request.args.get('code')
    accounts_server = request.args.get('accounts-server')
    client_id = require_env('ZOHO_CLIENT_ID')
    client_secret = require_env('ZOHO_CLIENT_SECRET')
    redirect_uri = os.environ.get(
        'ZOHO_OAUTH_REDIRECT_URI',
        'https://www.empathtechnologysolutions.com/oauth/callback'
    )
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
    if 'access_token' not in token_data:
        current_app.logger.error(f"Zoho OAuth token exchange failed: {token_data}")
        return "<h2>Authorization failed</h2><p>Check server logs for details.</p>", 502
    current_app.logger.info("Zoho OAuth token exchange succeeded.")
    return "<h2>Authorization complete</h2><p>You can close this window.</p>"
