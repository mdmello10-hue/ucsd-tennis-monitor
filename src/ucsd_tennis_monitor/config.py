from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


DEFAULT_BOOKING_ID = "9f19b678-58ce-4dfc-bd78-7166bde9e265"
DEFAULT_BOOKING_URL = "https://rec.ucsd.edu/booking/%s" % DEFAULT_BOOKING_ID


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    ucsd_username: str
    ucsd_password: str
    gmail_user: str
    gmail_app_password: str
    alert_to: str
    calendar_ids: List[str]
    poll_days: int
    timezone: str
    state_db_path: Path
    google_credentials_path: Path
    google_token_path: Path
    ucsd_storage_state_path: Path
    ucsd_headless: bool
    booking_id: str = DEFAULT_BOOKING_ID
    booking_url: str = DEFAULT_BOOKING_URL

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        calendar_ids = [
            value.strip()
            for value in os.environ.get("GOOGLE_CALENDAR_IDS", "primary").split(",")
            if value.strip()
        ]
        if not calendar_ids:
            calendar_ids = ["primary"]

        return cls(
            ucsd_username=os.environ.get("UCSD_REC_USERNAME", "").strip(),
            ucsd_password=os.environ.get("UCSD_REC_PASSWORD", ""),
            gmail_user=os.environ.get("GMAIL_USER", "").strip(),
            gmail_app_password=os.environ.get("GMAIL_APP_PASSWORD", ""),
            alert_to=os.environ.get("ALERT_TO", "").strip(),
            calendar_ids=calendar_ids,
            poll_days=int(os.environ.get("POLL_DAYS", "3")),
            timezone=os.environ.get("TIMEZONE", "America/Los_Angeles").strip(),
            state_db_path=Path(os.environ.get("STATE_DB_PATH", ".ucsd-tennis-monitor/state.sqlite3")),
            google_credentials_path=Path(os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")),
            google_token_path=Path(os.environ.get("GOOGLE_TOKEN_PATH", ".ucsd-tennis-monitor/google-token.json")),
            ucsd_storage_state_path=Path(
                os.environ.get("UCSD_STORAGE_STATE_PATH", ".ucsd-tennis-monitor/ucsd-storage-state.json")
            ),
            ucsd_headless=os.environ.get("UCSD_HEADLESS", "true").lower() not in {"0", "false", "no"},
        )

    def validate_for_monitor(self, dry_run: bool = False) -> None:
        missing = []
        if not self.ucsd_username:
            missing.append("UCSD_REC_USERNAME")
        if not self.ucsd_password:
            missing.append("UCSD_REC_PASSWORD")
        if not dry_run:
            if not self.gmail_user:
                missing.append("GMAIL_USER")
            if not self.gmail_app_password:
                missing.append("GMAIL_APP_PASSWORD")
            if not self.alert_to:
                missing.append("ALERT_TO")
        if missing:
            raise ConfigError("Missing required environment variables: %s" % ", ".join(missing))

        if self.poll_days < 1:
            raise ConfigError("POLL_DAYS must be at least 1")

    def validate_for_email(self) -> None:
        missing = []
        if not self.gmail_user:
            missing.append("GMAIL_USER")
        if not self.gmail_app_password:
            missing.append("GMAIL_APP_PASSWORD")
        if not self.alert_to:
            missing.append("ALERT_TO")
        if missing:
            raise ConfigError("Missing required environment variables: %s" % ", ".join(missing))
