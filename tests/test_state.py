from datetime import datetime
from zoneinfo import ZoneInfo

from ucsd_tennis_monitor.models import CourtSlot
from ucsd_tennis_monitor.state import StateStore


TZ = ZoneInfo("America/Los_Angeles")


def make_slot(hour=10):
    return CourtSlot(
        booking_id="booking",
        facility_id="facility",
        facility_name="Main Courts",
        start=datetime(2026, 5, 10, hour, tzinfo=TZ),
        end=datetime(2026, 5, 10, hour + 1, tzinfo=TZ),
        time_label="",
        spots_left=1,
        timeslot_id="ts-%s" % hour,
        timeslot_instance_id="tsi-%s" % hour,
    )


def test_state_sends_first_run_once_and_reopen(tmp_path):
    store = StateStore(tmp_path / "state.sqlite3")
    slot = make_slot()

    assert store.notification_candidates([slot]) == [slot]
    store.record_observation([slot], notified_keys={slot.key})

    assert store.notification_candidates([slot]) == []
    store.record_observation([])

    assert store.notification_candidates([slot]) == [slot]
