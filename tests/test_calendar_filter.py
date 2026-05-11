from datetime import datetime
from zoneinfo import ZoneInfo

from ucsd_tennis_monitor.calendar_filter import filter_slots_without_conflicts, intervals_overlap
from ucsd_tennis_monitor.models import BusyInterval, CourtSlot


TZ = ZoneInfo("America/Los_Angeles")


def slot(start_hour, end_hour):
    return CourtSlot(
        booking_id="booking",
        facility_id="facility",
        facility_name="Main Courts",
        start=datetime(2026, 5, 10, start_hour, tzinfo=TZ),
        end=datetime(2026, 5, 10, end_hour, tzinfo=TZ),
        time_label="",
        spots_left=1,
    )


def test_exact_boundaries_do_not_overlap():
    assert intervals_overlap(
        datetime(2026, 5, 10, 10, tzinfo=TZ),
        datetime(2026, 5, 10, 11, tzinfo=TZ),
        datetime(2026, 5, 10, 9, tzinfo=TZ),
        datetime(2026, 5, 10, 10, tzinfo=TZ),
    ) is False
    assert intervals_overlap(
        datetime(2026, 5, 10, 10, tzinfo=TZ),
        datetime(2026, 5, 10, 11, tzinfo=TZ),
        datetime(2026, 5, 10, 11, tzinfo=TZ),
        datetime(2026, 5, 10, 12, tzinfo=TZ),
    ) is False


def test_partial_overlap_blocks_slot():
    available = [slot(10, 11), slot(12, 13)]
    busy = [BusyInterval(datetime(2026, 5, 10, 10, 30, tzinfo=TZ), datetime(2026, 5, 10, 11, 30, tzinfo=TZ))]

    assert filter_slots_without_conflicts(available, busy) == [available[1]]
