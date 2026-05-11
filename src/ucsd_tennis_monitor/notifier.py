from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Iterable, List

from .models import CourtSlot


class EmailNotifier:
    def __init__(self, gmail_user: str, gmail_app_password: str, alert_to: str) -> None:
        self.gmail_user = gmail_user
        self.gmail_app_password = gmail_app_password
        self.alert_to = alert_to

    def send_slots(self, slots: Iterable[CourtSlot]) -> None:
        slot_list = list(slots)
        if not slot_list:
            return

        message = EmailMessage()
        message["From"] = self.gmail_user
        message["To"] = self.alert_to
        message["Subject"] = _subject_for_slots(slot_list)
        message.set_content(format_slots_email(slot_list))

        self._send_message(message)

    def send_test(self) -> None:
        message = EmailMessage()
        message["From"] = self.gmail_user
        message["To"] = self.alert_to
        message["Subject"] = "UCSD Tennis monitor test email"
        message.set_content("This is a test email from the UCSD Tennis court availability monitor.")
        self._send_message(message)

    def _send_message(self, message: EmailMessage) -> None:
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
                smtp.starttls()
                smtp.login(self.gmail_user, self.gmail_app_password)
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            raise RuntimeError(
                "Gmail SMTP rejected GMAIL_USER/GMAIL_APP_PASSWORD. Use the Gmail address as "
                "GMAIL_USER and a Gmail app password, not your normal Google password."
            ) from exc


def format_slots_email(slots: List[CourtSlot]) -> str:
    lines = [
        "UCSD tennis court opening%s found:" % ("" if len(slots) == 1 else "s"),
        "",
    ]
    for slot in sorted(slots, key=lambda item: (item.start, item.facility_name)):
        lines.append("- %s" % slot.display_line())
    lines.extend(
        [
            "",
            "Book here:",
            slots[0].booking_url,
            "",
            "Sent at %s." % datetime.now().astimezone().strftime("%Y-%m-%d %I:%M %p %Z"),
        ]
    )
    return "\n".join(lines)


def _subject_for_slots(slots: List[CourtSlot]) -> str:
    first = sorted(slots, key=lambda item: item.start)[0]
    return "UCSD Tennis: %s opening%s starting %s" % (
        len(slots),
        "" if len(slots) == 1 else "s",
        first.start.strftime("%a %-I:%M %p"),
    )
