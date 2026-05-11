from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Facility:
    facility_id: str
    name: str


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime
    calendar_id: str = "primary"


@dataclass(frozen=True)
class CourtSlot:
    booking_id: str
    facility_id: str
    facility_name: str
    start: datetime
    end: datetime
    time_label: str
    spots_left: int
    timeslot_id: str = ""
    timeslot_instance_id: str = ""
    slot_number: str = ""
    booking_url: str = "https://rec.ucsd.edu/booking/9f19b678-58ce-4dfc-bd78-7166bde9e265"

    @property
    def key(self) -> str:
        return "|".join(
            [
                self.booking_id,
                self.facility_id,
                self.start.isoformat(),
                self.end.isoformat(),
                self.timeslot_id,
                self.timeslot_instance_id,
            ]
        )

    def display_line(self) -> str:
        date_text = self.start.strftime("%a %b %-d, %Y")
        start_text = self.start.strftime("%-I:%M %p")
        end_text = self.end.strftime("%-I:%M %p")
        return "%s, %s-%s, %s (%s spot%s)" % (
            date_text,
            start_text,
            end_text,
            self.facility_name,
            self.spots_left,
            "" if self.spots_left == 1 else "s",
        )
