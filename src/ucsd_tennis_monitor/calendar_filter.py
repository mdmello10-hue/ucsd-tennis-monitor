from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List, Sequence

from .models import BusyInterval, CourtSlot

FREEBUSY_SCOPE = "https://www.googleapis.com/auth/calendar.freebusy"
SCOPES = [FREEBUSY_SCOPE]


class GoogleCalendarAuthError(RuntimeError):
    pass


class GoogleCalendarClient:
    def __init__(self, token_path, calendar_ids: Sequence[str]) -> None:
        self.token_path = token_path
        self.calendar_ids = list(calendar_ids)

    def get_busy_intervals(self, start: datetime, end: datetime) -> List[BusyInterval]:
        from googleapiclient.discovery import build

        credentials = self._load_credentials()
        service = build("calendar", "v3", credentials=credentials)
        body = {
            "timeMin": _to_rfc3339(start),
            "timeMax": _to_rfc3339(end),
            "items": [{"id": calendar_id} for calendar_id in self.calendar_ids],
        }
        response = service.freebusy().query(body=body).execute()
        return parse_freebusy_response(response)

    def _load_credentials(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        if not self.token_path.exists():
            raise GoogleCalendarAuthError(
                "Google token not found at %s. Run: python -m ucsd_tennis_monitor.google_auth" % self.token_path
            )
        credentials = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(credentials.to_json())
        if not credentials.valid:
            raise GoogleCalendarAuthError(
                "Google Calendar credentials are invalid. Run: python -m ucsd_tennis_monitor.google_auth"
            )
        return credentials


def parse_freebusy_response(response: Dict) -> List[BusyInterval]:
    intervals = []
    calendars = response.get("calendars", {})
    for calendar_id, calendar_data in calendars.items():
        errors = calendar_data.get("errors") or []
        if errors:
            messages = ", ".join(error.get("reason", "unknown") for error in errors)
            raise GoogleCalendarAuthError("FreeBusy failed for calendar %s: %s" % (calendar_id, messages))
        for busy in calendar_data.get("busy", []):
            intervals.append(
                BusyInterval(
                    start=parse_rfc3339(busy["start"]),
                    end=parse_rfc3339(busy["end"]),
                    calendar_id=calendar_id,
                )
            )
    return sorted(intervals, key=lambda item: item.start)


def filter_slots_without_conflicts(slots: Iterable[CourtSlot], busy_intervals: Iterable[BusyInterval]) -> List[CourtSlot]:
    busy = list(busy_intervals)
    filtered = []
    for slot in slots:
        if not any(intervals_overlap(slot.start, slot.end, interval.start, interval.end) for interval in busy):
            filtered.append(slot)
    return filtered


def intervals_overlap(start: datetime, end: datetime, busy_start: datetime, busy_end: datetime) -> bool:
    return start < busy_end and busy_start < end


def parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
