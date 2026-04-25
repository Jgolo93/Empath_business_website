# Referral Sync App

This application synchronizes Zoho Desk tickets with the referral database and sends email notifications to referrers when ticket statuses change.

## Features

- Fetches active tickets from Zoho Desk
- Matches tickets to referrals by phone number or ticket ID
- Updates referral status based on ticket status
- Sends HTML email notifications with consistent styling
- Supports multiple status templates (Open, In Progress, On Hold, Resolved)

## Environment Variables

The following environment variables are configured in `vercel.json`:

- `DATABASE_URL` - PostgreSQL connection string
- `ZOHO_ORG_ID` - Zoho Desk organization ID
- `ZOHO_CLIENT_ID` - Zoho API client ID
- `ZOHO_CLIENT_SECRET` - Zoho API client secret
- `ZOHO_REFRESH_TOKEN` - Zoho API refresh token
- `ZOHO_API_DOMAIN` - Zoho Desk API domain
- `MAIL_SERVER` - SMTP server for email sending
- `MAIL_PORT` - SMTP port
- `MAIL_USE_TLS` - Use TLS for SMTP
- `MAIL_USERNAME` - SMTP username
- `MAIL_PASSWORD` - SMTP password
- `MAIL_DEFAULT_SENDER` - Default email sender
- `FLASK_ENV` - Flask environment
- `SECRET_KEY` - Flask secret key

## Deployment

This app is deployed to Vercel via GitHub Actions.

### GitHub Actions Workflow

The workflow `.github/workflows/deploy-referral-sync.yml`:

- Triggers on push to main branch when files in `referral-sync/` change
- Sets up Python 3.11
- Installs dependencies from requirements.txt
- Runs tests (if any)
- Deploys to Vercel using Vercel CLI

### Vercel Configuration

The `vercel.json` file configures:

- Python build environment
- Environment variables
- Routing configuration

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the sync script
python referral_sync.py
```

## Email Templates

Email templates are located in `templates/emails/`:

- `02_submitted.html` - New referral submission
- `03_ticket_open.html` - Ticket opened
- `04_in_progress.html` - Ticket in progress
- `05_on_hold.html` - Ticket on hold
- `06_resolved.html` - Ticket resolved/commission paid

All templates extend `base_email.html` for consistent styling with the Empath Technology Solutions branding.

## Status Mapping

Zoho Desk statuses are mapped to internal referral statuses:

- Open → `open`
- In Progress → `in_progress`
- On Hold → `on_hold`
- Closed → `resolved`
- Done → `signed_up`

## Cron Job

For production deployment, set up a cron job to run the sync script regularly:

```bash
# Run every 15 minutes
*/15 * * * * /usr/bin/python3 /path/to/referral-sync/referral_sync.py >> /var/log/referral_sync.log 2>&1
```

## License

Proprietary - Empath Technology Solutions
