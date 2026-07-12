import base64
import logging

import requests

from extensions import require_env

logger = logging.getLogger(__name__)

_SMS_PORTAL_AUTH_URL = 'https://rest.smsportal.com/v1/authentication'
_SMS_PORTAL_SEND_URL = 'https://rest.smsportal.com/v1/bulkmessages'

_cached_token = None


def _get_token():
    global _cached_token
    if _cached_token:
        return _cached_token

    client_id = require_env('SMS_PORTAL_CLIENT_ID')
    client_secret = require_env('SMS_PORTAL_CLIENT_SECRET')
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    response = requests.post(
        _SMS_PORTAL_AUTH_URL,
        headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'},
        json={'grant_type': 'client_credentials'},
        timeout=15,
    )
    response.raise_for_status()
    _cached_token = response.json()['token']
    return _cached_token


# South African business — default the dialing code for locally-formatted
# numbers (e.g. a customer typing "082 123 4567") since SMSPortal requires the
# full international format (+27821234567) to route the message at all.
_DEFAULT_DIALING_CODE = '27'


def clean_phone_number(phone):
    if not phone:
        return ''
    digits = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
    if not digits:
        return ''

    if digits.startswith('+'):
        return digits
    if digits.startswith('00'):
        return '+' + digits[2:]
    if digits.startswith('0'):
        # Local SA format (0821234567) — drop the trunk 0, prefix +27.
        return '+' + _DEFAULT_DIALING_CODE + digits[1:]
    if digits.startswith(_DEFAULT_DIALING_CODE):
        return '+' + digits
    # Anything else (already has some other country code but no +, e.g. from
    # copy-paste) — best effort, just add the +.
    return '+' + digits


def send_sms(phone, message):
    """Best-effort SMS send via SMSPortal — logs and returns False on failure
    rather than raising, matching send_referral_email's fire-and-forget style."""
    phone = clean_phone_number(phone)
    if not phone:
        return False

    try:
        token = _get_token()
        response = requests.post(
            _SMS_PORTAL_SEND_URL,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={'messages': [{'content': message, 'destination': phone}]},
            timeout=15,
        )
        response.raise_for_status()
        logger.info(f"SMS sent to {phone[-4:]}")
        return True
    except Exception as e:
        logger.error(f"[SMS FAILED] to=...{phone[-4:]} error={e}")
        return False
