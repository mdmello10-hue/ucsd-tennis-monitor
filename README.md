# UCSD Tennis Court Monitor

Personal monitor for UCSD Recreation tennis court openings. It checks authenticated booking pages, filters open slots against your Google Calendar busy time, and emails you only when a matching slot newly appears or reopens.

This does not auto-book courts.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env
```

Edit `.env` with:

- UCSD Recreation Public Access username/password.
- Gmail address and Gmail app password.
- Alert destination email.
- Google Calendar ids, usually `primary`.

## Google Calendar Auth

Create a Google OAuth desktop client, download it as `credentials.json`, then run:

```bash
python -m ucsd_tennis_monitor.google_auth
```

The app requests only the Google Calendar FreeBusy scope.

## Validate

```bash
python -m ucsd_tennis_monitor.monitor --once --dry-run
python -m ucsd_tennis_monitor.monitor --test-email
python -m ucsd_tennis_monitor.monitor --once
```

If the UCSD account is routed into Shibboleth/SSO or MFA instead of the Public Access password flow, the monitor exits with a clear message. In that case, switch to a saved browser-session approach before running it unattended.

## Cron

Install the example schedule:

```bash
crontab -e
```

Then paste the line from `cron.example`. It runs once daily on your Mac and appends logs to `.ucsd-tennis-monitor/cron.log`.

## GitHub Actions

Use GitHub Actions when you want the monitor to run even if your Mac is asleep. The workflow in `.github/workflows/ucsd-tennis-monitor.yml` runs daily at 8:00 AM America/Los_Angeles and can also be started manually from the repository's Actions tab.

Add these repository secrets in GitHub under **Settings -> Secrets and variables -> Actions**:

- `UCSD_REC_USERNAME`
- `UCSD_REC_PASSWORD`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `ALERT_TO`
- `GOOGLE_CREDENTIALS_JSON`: contents of local `credentials.json`
- `GOOGLE_TOKEN_JSON`: contents of local `.ucsd-tennis-monitor/google-token.json`

Optional secrets:

- `GOOGLE_CALENDAR_IDS`: defaults to `primary`
- `POLL_DAYS`: defaults to `3`

The first GitHub Actions run may send a fresh summary because it starts with an empty cloud state. After that, the workflow caches `.ucsd-tennis-monitor/state.sqlite3` so it only emails newly opened or reopened slots.

## Notes

UCSD's `robots.txt` disallows generic crawling. This project is intentionally a conservative personal authenticated monitor, using the same booking endpoints the logged-in page requests, and it never attempts to reserve a court.
