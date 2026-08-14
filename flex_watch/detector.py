from __future__ import annotations

from dataclasses import dataclass


LOGIN_MARKERS = (
    "sign in",
    "roll no.",
    "g-recaptcha",
    "forgotten password",
)

CLOSED_MARKERS = (
    "not active yet",
    "registration is closed",
    "course registration is closed",
    "registration closed",
    "not open",
    "not started",
    "not available",
    "no registration",
    "currently unavailable",
    "access denied",
)

OPEN_MARKERS = (
    "courseregform",
    "registerchkbox",
    "register",
    "course registration",
    "offered courses",
    "available seats",
    "section",
)

ERROR_MARKERS = (
    "server error in",
    "runtime error",
    "exception details",
    "stack trace",
    "request timed out",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "internal server error",
)

HOME_MARKERS = (
    "hello mr",
    'id="m_ver_menu"',
    "/student/courseregistration",
    "course registration",
    "/login/logout",
    "my profile",
)


@dataclass(frozen=True)
class PageState:
    status: str
    reason: str

    @property
    def is_open(self) -> bool:
        return self.status == "open"

    @property
    def is_login(self) -> bool:
        return self.status == "login"

    @property
    def is_closed(self) -> bool:
        return self.status == "closed"

    @property
    def is_error(self) -> bool:
        return self.status == "error"

    @property
    def is_home(self) -> bool:
        return self.status == "home"


def detect_state(url: str, html: str) -> PageState:
    lower_url = url.lower()
    lower_html = html.lower()

    if "/login" in lower_url or any(marker in lower_html for marker in LOGIN_MARKERS):
        return PageState("login", "redirected to login")

    for marker in ERROR_MARKERS:
        if marker in lower_html:
            return PageState("error", f"server/load error marker: {marker}")

    if "registration" in lower_html and "not active yet" in lower_html:
        return PageState("closed", "registration not active yet")

    for marker in CLOSED_MARKERS:
        if marker in lower_html:
            return PageState("closed", f"closed marker: {marker}")

    if "/home" in lower_url or (
        "/student/courseregistration" not in lower_url
        and any(marker in lower_html for marker in HOME_MARKERS)
    ):
        return PageState("home", "portal home detected")

    has_registration_form = 'id="courseregform"' in lower_html or "id='courseregform'" in lower_html
    has_registration_control = any(
        token in lower_html
        for token in (
            "registerchkbox",
            'class="section',
            "class='section",
            'id="submit"',
            "id='submit'",
        )
    )
    if has_registration_form and has_registration_control:
        return PageState("open", "registration form controls detected")

    has_open_marker = any(marker in lower_html for marker in OPEN_MARKERS)
    has_form_control = any(token in lower_html for token in ("<select", "<button", "type=\"submit\"", "type='submit'"))
    if has_open_marker and has_form_control:
        return PageState("open", "registration controls detected")

    return PageState("unknown", "no decisive marker")
