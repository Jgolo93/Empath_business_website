import logging

from flask import current_app, render_template
from flask_mail import Message

from extensions import mail

logger = logging.getLogger(__name__)


def send_referral_email(to_address, subject, template_name, context):
    try:
        html_body = render_template(template_name, **context)
        msg = Message(subject=subject, recipients=[to_address], html=html_body)
        mail.send(msg)
        logger.info(f"Email sent to {to_address}: {subject} (template: {template_name})")
    except Exception as e:
        logger.error(f"Email failed to {to_address} (template: {template_name}): {e}")
        current_app.logger.error(f"[EMAIL FAILED] to={to_address} template={template_name} error={e}")
