from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .models import CourtSlot


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def notification_candidates(self, current_slots: Sequence[CourtSlot]) -> List[CourtSlot]:
        with self._connect() as conn:
            candidates = []
            for slot in current_slots:
                row = conn.execute("SELECT status FROM slot_state WHERE slot_key = ?", (slot.key,)).fetchone()
                if row is None or row["status"] != "open":
                    candidates.append(slot)
            return candidates

    def record_observation(self, current_slots: Sequence[CourtSlot], notified_keys: Optional[Set[str]] = None) -> None:
        notified_keys = notified_keys or set()
        now = _utc_now()
        current_keys = {slot.key for slot in current_slots}

        with self._connect() as conn:
            previous_open = {
                row["slot_key"]
                for row in conn.execute("SELECT slot_key FROM slot_state WHERE status = 'open'").fetchall()
            }
            for slot_key in previous_open - current_keys:
                conn.execute(
                    "UPDATE slot_state SET status = 'closed', last_seen_at = ? WHERE slot_key = ?",
                    (now, slot_key),
                )

            for slot in current_slots:
                existing = conn.execute(
                    "SELECT first_seen_at, last_notified_at FROM slot_state WHERE slot_key = ?",
                    (slot.key,),
                ).fetchone()
                first_seen_at = existing["first_seen_at"] if existing else now
                previous_notified_at = existing["last_notified_at"] if existing else None
                last_notified_at = now if slot.key in notified_keys else previous_notified_at
                conn.execute(
                    """
                    INSERT INTO slot_state (
                        slot_key, status, first_seen_at, last_seen_at, last_notified_at, payload_json
                    )
                    VALUES (?, 'open', ?, ?, ?, ?)
                    ON CONFLICT(slot_key) DO UPDATE SET
                        status = 'open',
                        last_seen_at = excluded.last_seen_at,
                        last_notified_at = excluded.last_notified_at,
                        payload_json = excluded.payload_json
                    """,
                    (slot.key, first_seen_at, now, last_notified_at, json.dumps(_slot_payload(slot), sort_keys=True)),
                )

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS slot_state (
                    slot_key TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK(status IN ('open', 'closed')),
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_notified_at TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn


def _slot_payload(slot: CourtSlot) -> Dict[str, object]:
    return {
        "booking_id": slot.booking_id,
        "facility_id": slot.facility_id,
        "facility_name": slot.facility_name,
        "start": slot.start.isoformat(),
        "end": slot.end.isoformat(),
        "time_label": slot.time_label,
        "spots_left": slot.spots_left,
        "timeslot_id": slot.timeslot_id,
        "timeslot_instance_id": slot.timeslot_instance_id,
        "slot_number": slot.slot_number,
        "booking_url": slot.booking_url,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
