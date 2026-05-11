from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .models import CourtSlot, Facility


DATE_TEXT_FORMATS = (
    "%a, %b %d %Y",
    "%a %b %d %Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%Y-%m-%d",
)

TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([AaPp][Mm])?")
TIME_RANGE_RE = re.compile(
    r"(\d{1,2}(?::\d{2})?\s*(?:[AaPp][Mm])?)\s*(?:-|–|—|to)\s*(\d{1,2}(?::\d{2})?\s*(?:[AaPp][Mm])?)"
)


def parse_dates(html: str, timezone_name: str) -> List[date]:
    soup = BeautifulSoup(html, "html.parser")
    dates = []

    for element in soup.select("[data-year][data-month][data-day]"):
        parsed = _date_from_data_attrs(element)
        if parsed:
            dates.append(parsed)

    for element in soup.select("input[value], button, a, span, div"):
        value = element.get("value") or element.get_text(" ", strip=True)
        parsed = _parse_date_text(value)
        if parsed:
            dates.append(parsed)

    hidden_year = _element_value(soup, "hdnSelectedYear")
    hidden_month = _element_value(soup, "hdnSelectedMonth")
    hidden_day = _element_value(soup, "hdnSelectedDay")
    if hidden_year and hidden_month and hidden_day:
        try:
            dates.append(date(int(hidden_year), int(hidden_month), int(hidden_day)))
        except ValueError:
            pass

    today = datetime.now(ZoneInfo(timezone_name)).date()
    unique = sorted({value for value in dates if value >= today - timedelta(days=1)})
    return unique


def parse_facilities(html: str) -> List[Facility]:
    soup = BeautifulSoup(html, "html.parser")
    facilities = []

    selectors = [
        "[data-facility-id]",
        "[data-facilityId]",
        ".booking-facility-list",
        "#tabBookingFacilities button",
    ]
    seen = set()
    for element in soup.select(",".join(selectors)):
        facility_id = (
            element.get("data-facility-id")
            or element.get("data-facilityid")
            or element.get("data-facilityId")
            or ""
        ).strip()
        if not facility_id or facility_id in seen:
            continue
        name = (
            element.get("data-facility-name")
            or element.get("data-facilityname")
            or element.get("data-facilityName")
            or element.get_text(" ", strip=True)
            or "UCSD Tennis Court"
        ).strip()
        facilities.append(Facility(facility_id=facility_id, name=_clean_text(name)))
        seen.add(facility_id)

    return facilities


def parse_slots(
    html: str,
    slot_date: date,
    facility: Facility,
    timezone_name: str,
    booking_id: str,
    booking_url: str,
    default_duration_minutes: int = 60,
) -> List[CourtSlot]:
    soup = BeautifulSoup(html, "html.parser")
    timezone = ZoneInfo(timezone_name)
    buttons = soup.select("button[data-timeslot-id], button[data-timeslotinstance-id], .booking-slot-action-item button")
    slots = []
    seen = set()

    for button in buttons:
        if _is_unavailable_button(button):
            continue

        parent_text = button.parent.get_text(" ", strip=True) if button.parent else ""
        button_text = button.get_text(" ", strip=True)
        combined_text = " ".join(
            value
            for value in [
                button.get("data-slot-text", ""),
                button.get("aria-label", ""),
                parent_text,
                button_text,
            ]
            if value
        )

        start_end = parse_time_range(combined_text, slot_date, timezone, default_duration_minutes)
        if not start_end:
            continue

        start, end = start_end
        timeslot_id = (button.get("data-timeslot-id") or "").strip()
        timeslot_instance_id = (button.get("data-timeslotinstance-id") or "").strip()
        slot_number = button.get("data-slot-number") or ""
        if not slot_number and button.parent:
            slot_number = button.parent.get("data-slot-number") or ""
        spots_left = _extract_spots_left(button, combined_text)
        if spots_left <= 0:
            continue

        facility_name = (
            button.get("data-facility-name")
            or button.get("data-facilityname")
            or facility.name
            or "UCSD Tennis Court"
        )

        slot = CourtSlot(
            booking_id=booking_id,
            facility_id=facility.facility_id,
            facility_name=_clean_text(facility_name),
            start=start,
            end=end,
            time_label=_clean_text(button.get("data-slot-text") or _time_label(start, end)),
            spots_left=spots_left,
            timeslot_id=timeslot_id,
            timeslot_instance_id=timeslot_instance_id,
            slot_number=str(slot_number).strip(),
            booking_url=booking_url,
        )
        if slot.key not in seen:
            slots.append(slot)
            seen.add(slot.key)

    return sorted(slots, key=lambda item: (item.start, item.facility_name))


def parse_time_range(
    text: str,
    slot_date: date,
    timezone: ZoneInfo,
    default_duration_minutes: int = 60,
) -> Optional[Tuple[datetime, datetime]]:
    text = _clean_text(text)
    match = TIME_RANGE_RE.search(text)
    if match:
        start_token = match.group(1)
        end_token = match.group(2)
        start_time, end_time = _parse_range_tokens(start_token, end_token)
        start = datetime.combine(slot_date, start_time, timezone)
        end = datetime.combine(slot_date, end_time, timezone)
        if end <= start:
            end += timedelta(days=1)
        return start, end

    match = TIME_RE.search(text)
    if match:
        parsed_time, _meridiem = _parse_time_token(match.group(0))
        start = datetime.combine(slot_date, parsed_time, timezone)
        return start, start + timedelta(minutes=default_duration_minutes)

    return None


def _parse_time_token(token: str, fallback_meridiem: Optional[str] = None) -> Tuple[time, Optional[str]]:
    raw_hour, minute, meridiem = _parse_raw_time_token(token)
    meridiem = meridiem or fallback_meridiem or ""

    hour = _hour_24(raw_hour, meridiem)
    return time(hour=hour, minute=minute), meridiem or None


def _parse_range_tokens(start_token: str, end_token: str) -> Tuple[time, time]:
    start_hour, start_minute, start_meridiem = _parse_raw_time_token(start_token)
    end_hour, end_minute, end_meridiem = _parse_raw_time_token(end_token)

    if not start_meridiem and end_meridiem:
        if end_meridiem == "PM" and end_hour == 12 and start_hour < 12:
            start_meridiem = "AM"
        else:
            start_meridiem = end_meridiem
    if not end_meridiem and start_meridiem:
        end_meridiem = start_meridiem

    return (
        time(hour=_hour_24(start_hour, start_meridiem or ""), minute=start_minute),
        time(hour=_hour_24(end_hour, end_meridiem or ""), minute=end_minute),
    )


def _parse_raw_time_token(token: str) -> Tuple[int, int, Optional[str]]:
    match = TIME_RE.search(token.strip())
    if not match:
        raise ValueError("Could not parse time token: %s" % token)
    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridiem = (match.group(3) or "").upper() or None

    return hour, minute, meridiem


def _hour_24(hour: int, meridiem: str) -> int:
    if meridiem == "PM" and hour != 12:
        hour += 12
    if meridiem == "AM" and hour == 12:
        hour = 0
    if hour == 24:
        hour = 0
    return hour


def _date_from_data_attrs(element) -> Optional[date]:
    try:
        return date(
            int(element.get("data-year")),
            int(element.get("data-month")),
            int(element.get("data-day")),
        )
    except (TypeError, ValueError):
        return None


def _parse_date_text(text: str) -> Optional[date]:
    text = _clean_text(text)
    if not text:
        return None

    iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            return None

    candidate = re.sub(r"\b(Today|Tomorrow|Previous|Next|Select|Date)\b", "", text, flags=re.IGNORECASE).strip()
    candidate = re.sub(r"\s+", " ", candidate)
    for fmt in DATE_TEXT_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def _element_value(soup: BeautifulSoup, element_id: str) -> Optional[str]:
    element = soup.find(id=element_id)
    if not element:
        return None
    return element.get("value")


def _is_unavailable_button(button) -> bool:
    disabled = button.has_attr("disabled") or button.get("aria-disabled") == "true"
    text = button.get_text(" ", strip=True).lower()
    unavailable_words = ("full", "unavailable", "closed", "waitlist")
    return disabled or any(word in text for word in unavailable_words)


def _extract_spots_left(button, text: str) -> int:
    for attr in ("data-spots-left", "data-spotsleft", "data-spots", "data-capacity"):
        value = button.get(attr)
        if value:
            try:
                return int(value)
            except ValueError:
                pass

    match = re.search(r"(\d+)\s+(?:spot|spots|space|spaces)\s+(?:left|available)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return 1


def _time_label(start: datetime, end: datetime) -> str:
    return "%s - %s" % (start.strftime("%-I:%M %p"), end.strftime("%-I:%M %p"))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
