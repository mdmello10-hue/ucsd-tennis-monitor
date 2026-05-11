from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

from .calendar_filter import GoogleCalendarClient, filter_slots_without_conflicts
from .config import ConfigError, Settings
from .models import CourtSlot
from .notifier import EmailNotifier
from .state import StateStore
from .ucsd_client import UCSDClient
from .warning_filters import quiet_dependency_warnings


def main(argv: List[str] = None) -> int:
    quiet_dependency_warnings()
    parser = argparse.ArgumentParser(description="Monitor UCSD tennis court openings.")
    parser.add_argument("--once", action="store_true", help="Run one polling pass. Intended for cron.")
    parser.add_argument("--dry-run", action="store_true", help="Print results without sending email or mutating state.")
    parser.add_argument("--test-email", action="store_true", help="Send a single test email and exit.")
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
        if args.test_email:
            settings.validate_for_email()
            EmailNotifier(settings.gmail_user, settings.gmail_app_password, settings.alert_to).send_test()
            print("Sent test email to %s" % settings.alert_to)
            return 0

        settings.validate_for_monitor(dry_run=args.dry_run)
        return run_once(settings, dry_run=args.dry_run)
    except (ConfigError, RuntimeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1


def run_once(settings: Settings, dry_run: bool = False) -> int:
    timezone = ZoneInfo(settings.timezone)
    window_start = datetime.now(timezone)
    window_end = window_start + timedelta(days=settings.poll_days)

    ucsd = UCSDClient(
        username=settings.ucsd_username,
        password=settings.ucsd_password,
        storage_state_path=settings.ucsd_storage_state_path,
        booking_id=settings.booking_id,
        booking_url=settings.booking_url,
        timezone_name=settings.timezone,
        headless=settings.ucsd_headless,
    )
    all_slots = ucsd.fetch_slots(settings.poll_days)
    busy = GoogleCalendarClient(settings.google_token_path, settings.calendar_ids).get_busy_intervals(
        window_start, window_end
    )
    matching_slots = filter_slots_without_conflicts(all_slots, busy)
    state = StateStore(settings.state_db_path)
    candidates = state.notification_candidates(matching_slots)

    if dry_run:
        _print_dry_run(all_slots, matching_slots, candidates)
        return 0

    notified_keys = set()
    if candidates:
        EmailNotifier(settings.gmail_user, settings.gmail_app_password, settings.alert_to).send_slots(candidates)
        notified_keys = {slot.key for slot in candidates}

    state.record_observation(matching_slots, notified_keys=notified_keys)
    print(
        "Checked %s UCSD tennis slots; %s matched calendar; %s notification%s sent."
        % (
            len(all_slots),
            len(matching_slots),
            len(candidates),
            "" if len(candidates) == 1 else "s",
        )
    )
    return 0


def _print_dry_run(all_slots: List[CourtSlot], matching_slots: List[CourtSlot], candidates: List[CourtSlot]) -> None:
    print("UCSD slots found: %s" % len(all_slots))
    print("Calendar-compatible slots: %s" % len(matching_slots))
    print("Would notify for: %s" % len(candidates))
    if candidates:
        print("")
        for slot in candidates:
            print("- %s" % slot.display_line())


if __name__ == "__main__":
    raise SystemExit(main())
