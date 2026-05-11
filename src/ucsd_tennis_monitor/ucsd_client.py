from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Sequence
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .models import CourtSlot, Facility
from .parsing import parse_dates, parse_facilities, parse_slots


class UCSDLoginError(RuntimeError):
    pass


class UCSDScrapeError(RuntimeError):
    pass


class UCSDClient:
    base_url = "https://rec.ucsd.edu"

    def __init__(
        self,
        username: str,
        password: str,
        storage_state_path,
        booking_id: str,
        booking_url: str,
        timezone_name: str,
        headless: bool = True,
    ) -> None:
        self.username = username
        self.password = password
        self.storage_state_path = storage_state_path
        self.booking_id = booking_id
        self.booking_url = booking_url
        self.timezone_name = timezone_name
        self.headless = headless

    def fetch_slots(self, poll_days: int) -> List[CourtSlot]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context_kwargs = {}
            if self.storage_state_path.exists():
                context_kwargs["storage_state"] = str(self.storage_state_path)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            try:
                self._ensure_logged_in(page, context)
                facilities = self._fetch_facilities(context)
                candidate_dates = self._fetch_candidate_dates(context, poll_days)
                slots = []
                for facility in facilities:
                    for slot_date in candidate_dates:
                        html = self._get_text(
                            context,
                            "/booking/%s/slots/%s/%s/%s/%s"
                            % (
                                self.booking_id,
                                facility.facility_id,
                                slot_date.year,
                                slot_date.month,
                                slot_date.day,
                            ),
                        )
                        slots.extend(
                            parse_slots(
                                html=html,
                                slot_date=slot_date,
                                facility=facility,
                                timezone_name=self.timezone_name,
                                booking_id=self.booking_id,
                                booking_url=self.booking_url,
                            )
                        )
                return sorted(slots, key=lambda item: (item.start, item.facility_name))
            finally:
                context.close()
                browser.close()

    def _ensure_logged_in(self, page, context) -> None:
        self._goto(page, self.booking_url)
        if self._page_is_booking_page(page):
            self._save_storage_state(context)
            return

        if not self._page_is_sign_in_page(page):
            raise UCSDLoginError("Unexpected UCSD page while checking login: %s" % page.url)

        self._login_public_access(page)
        if self._page_is_booking_page(page):
            self._save_storage_state(context)
            return

        self._goto(page, self.booking_url)
        if not self._page_is_booking_page(page):
            content = page.content()
            if "Single Sign On" in content or "Shibboleth" in content:
                raise UCSDLoginError(
                    "UCSD routed this account through SSO/MFA. This monitor targets the Public Access "
                    "username/password flow; use a saved browser-session approach for SSO accounts."
                )
            raise UCSDLoginError("UCSD login did not reach the tennis booking page. Current URL: %s" % page.url)
        self._save_storage_state(context)

    def _goto(self, page, url: str) -> None:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except PlaywrightError as exc:
            # Fusion sometimes aborts a navigation while replacing it with an auth redirect.
            # If the browser still lands on a recognizable page, keep going.
            if "net::ERR_ABORTED" not in str(exc):
                raise
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except PlaywrightTimeoutError:
                pass
            if not self._page_is_booking_page(page) and not self._page_is_sign_in_page(page):
                raise

    def _login_public_access(self, page) -> None:
        try:
            page.locator("#txtEmailUsernameLogin").fill(self.username, timeout=10000)
            page.locator("#btnNextSignInFirst").click(timeout=10000)
            page.wait_for_load_state("domcontentloaded", timeout=45000)
        except PlaywrightTimeoutError as exc:
            raise UCSDLoginError(
                "Could not advance UCSD Public Access username step. If this is a UCSD SSO account, "
                "use a saved browser-session approach instead."
            ) from exc

        password_input = page.locator("input[type='password']").first
        try:
            password_input.wait_for(state="visible", timeout=15000)
            password_input.fill(self.password)
        except PlaywrightTimeoutError as exc:
            raise UCSDLoginError(
                "UCSD did not show a Public Access password field. The account may require SSO/MFA."
            ) from exc

        submit = page.locator("button[type='submit'], input[type='submit']").last
        try:
            submit.click(timeout=10000)
            self._wait_for_post_login_redirect(page)
        except PlaywrightTimeoutError as exc:
            raise UCSDLoginError("UCSD Public Access password step timed out.") from exc

    def _wait_for_post_login_redirect(self, page) -> None:
        try:
            page.wait_for_url(lambda url: "account/signin" not in str(url).lower(), timeout=20000)
        except PlaywrightTimeoutError:
            pass
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except PlaywrightTimeoutError:
            pass

    def _fetch_facilities(self, context) -> List[Facility]:
        html = self._get_text(context, "/booking/%s/facilities" % self.booking_id)
        facilities = parse_facilities(html)
        if not facilities:
            raise UCSDScrapeError("Could not find tennis facilities in UCSD booking response.")
        return facilities

    def _fetch_candidate_dates(self, context, poll_days: int) -> List[date]:
        timezone = ZoneInfo(self.timezone_name)
        today = datetime.now(timezone).date()
        max_date = today + timedelta(days=poll_days - 1)
        fallback = [today + timedelta(days=offset) for offset in range(poll_days)]

        html = self._get_text(context, "/booking/%s/dates" % self.booking_id)
        dates = [value for value in parse_dates(html, self.timezone_name) if today <= value <= max_date]
        return dates or fallback

    def _get_text(self, context, path: str) -> str:
        url = path if path.startswith("http") else "%s%s" % (self.base_url, path)
        response = context.request.get(url, timeout=45000)
        text = response.text()
        if response.status >= 400:
            raise UCSDScrapeError("UCSD request failed with HTTP %s for %s" % (response.status, url))
        if "txtEmailUsernameLogin" in text and "Sign In" in text:
            raise UCSDLoginError("UCSD session expired while fetching %s" % url)
        return text

    def _save_storage_state(self, context) -> None:
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(self.storage_state_path))

    def _page_is_sign_in_page(self, page) -> bool:
        return page.locator("#txtEmailUsernameLogin").count() > 0 or "account/signin" in page.url.lower()

    def _page_is_booking_page(self, page) -> bool:
        if "account/signin" in page.url.lower():
            return False
        parsed = urlparse(page.url)
        if parsed.netloc == "rec.ucsd.edu" and parsed.path.lower().rstrip("/") == "/booking":
            return True
        return page.locator("#hdnBookingId, #divBookingSlots, #divBookingFacilities, #NewBooking").count() > 0
