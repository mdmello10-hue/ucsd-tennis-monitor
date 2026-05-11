from datetime import date

from ucsd_tennis_monitor.models import Facility
from ucsd_tennis_monitor.parsing import parse_dates, parse_facilities, parse_slots, parse_time_range


def test_parse_dates_from_data_attributes_and_hidden_text():
    html = """
    <button data-year="2026" data-month="5" data-day="10">May 10</button>
    <input id="hdnDateSelectorDateText" value="Mon, May 11 2026" />
    """

    assert parse_dates(html, "America/Los_Angeles")[:2] == [date(2026, 5, 10), date(2026, 5, 11)]


def test_parse_facilities_from_buttons():
    html = """
    <button data-facility-id="court-a" data-facility-name="North Courts">North Courts</button>
    <button data-facility-id="court-b">South Courts</button>
    """

    facilities = parse_facilities(html)

    assert facilities == [
        Facility("court-a", "North Courts"),
        Facility("court-b", "South Courts"),
    ]


def test_parse_available_slots():
    html = """
    <div class="booking-slot-action-item">
      <button
        data-timeslot-id="ts-1"
        data-timeslotinstance-id="tsi-1"
        data-slot-text="8:00 AM - 9:00 AM"
        data-spots-left="2">Book Now</button>
    </div>
    <div class="booking-slot-action-item">
      <button disabled data-slot-text="9:00 AM - 10:00 AM">Full</button>
    </div>
    """

    slots = parse_slots(
        html=html,
        slot_date=date(2026, 5, 10),
        facility=Facility("court-a", "North Courts"),
        timezone_name="America/Los_Angeles",
        booking_id="booking",
        booking_url="https://example.com/book",
    )

    assert len(slots) == 1
    assert slots[0].facility_name == "North Courts"
    assert slots[0].spots_left == 2
    assert slots[0].start.hour == 8
    assert slots[0].end.hour == 9


def test_parse_time_range_infers_pm_for_compact_afternoon_label():
    start, end = parse_time_range("1:00 - 2:00 PM", date(2026, 5, 12), slots_timezone())

    assert start.hour == 13
    assert end.hour == 14


def test_parse_time_range_handles_late_morning_to_noon():
    start, end = parse_time_range("11:00 - 12:00 PM", date(2026, 5, 12), slots_timezone())

    assert start.hour == 11
    assert end.hour == 12


def slots_timezone():
    from zoneinfo import ZoneInfo

    return ZoneInfo("America/Los_Angeles")
