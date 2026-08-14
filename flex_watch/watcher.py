from __future__ import annotations

import asyncio
import datetime as dt
import random
from urllib.parse import urljoin

from playwright.async_api import Error as PlaywrightError, Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from .alerts import urgent_alarm
from .config import Config, LOG_DIR, PROFILE_DIR
from .detector import PageState, detect_state


LOGIN_URL = "https://flexstudent.nu.edu.pk/Login"
HOME_URL = "https://flexstudent.nu.edu.pk/Home"
BARE_REGISTRATION_URL = "https://flexstudent.nu.edu.pk/Student/CourseRegistration"


class FlexWatcher:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.registration_url = self._initial_registration_url(config.registration_url)
        LOG_DIR.mkdir(exist_ok=True)
        self.log_path = LOG_DIR / f"watch-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    def _initial_registration_url(self, configured_url: str) -> str:
        if not configured_url or "/Student/CourseRegistrationBS" in configured_url:
            return BARE_REGISTRATION_URL
        return configured_url

    def log(self, message: str) -> None:
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {message}"
        print(line, flush=True)
        self.log_path.parent.mkdir(exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    async def _new_context(self):
        playwright = await async_playwright().start()
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1366, "height": 850},
        )
        timeout_ms = int(self.config.navigation_timeout_seconds * 1000)
        context.set_default_timeout(timeout_ms)
        context.set_default_navigation_timeout(timeout_ms)
        return playwright, context

    async def _ensure_login(self, page: Page) -> None:
        await self._safe_goto(page, LOGIN_URL)
        await self._fill_login(page)
        self.log("Solve reCAPTCHA in browser, then click Sign In.")

        while True:
            await asyncio.sleep(2)
            state = await self._current_state(page)

            if state.is_home:
                self.log("Home page verified.")
                return

            if state.is_error:
                self.log("Error after login. Returning to login screen.")
                await self._safe_goto(page, LOGIN_URL)
                await self._fill_login(page)
                self.log("Solve reCAPTCHA again if Flex asks, then click Sign In.")
                continue

            if "/login" not in page.url.lower():
                try:
                    await self._safe_goto(page, HOME_URL)
                    state = await self._current_state(page)
                    if state.is_home:
                        self.log("Home page verified.")
                        return
                    if state.is_error:
                        self.log("Home failed after login. Returning to login screen.")
                        await self._safe_goto(page, LOGIN_URL)
                        await self._fill_login(page)
                except Exception as exc:
                    self.log(f"Home verification failed: {exc}")

    async def _fill_login(self, page: Page) -> None:
        try:
            await page.fill("input[name='username']", self.config.flex_username)
            await page.fill("input[name='password']", self.config.flex_password)
        except Exception as exc:
            self.log(f"Login form fill skipped/failed: {exc}")

    async def login_only(self) -> None:
        playwright, context = await self._new_context()
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await self._ensure_login(page)
            self.registration_url = await self._resolve_registration_url(page)
            await self._safe_goto(page, self.registration_url)
            self.log(f"Current page: {page.url}")
            self.log("Press Enter to close browser.")
            await asyncio.to_thread(input)
        finally:
            await context.close()
            await playwright.stop()

    async def check_once(self) -> PageState:
        playwright, context = await self._new_context()
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await self._safe_goto(page, self.registration_url)
            state = detect_state(page.url, await page.content())
            if state.is_login and self.config.flex_username and self.config.flex_password:
                await self._ensure_login(page)
                self.registration_url = await self._resolve_registration_url(page)
                await self._safe_goto(page, self.registration_url)
            state = detect_state(page.url, await page.content())
            self.log(f"State: {state.status}; {state.reason}; url={page.url}")
            return state
        finally:
            await context.close()
            await playwright.stop()

    async def start(self) -> None:
        playwright, context = await self._new_context()
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await self._safe_goto(page, self.registration_url)
            state = detect_state(page.url, await page.content())
            if state.is_login:
                await self._ensure_login(page)
            self.registration_url = await self._resolve_registration_url(page)

            self.log("Watcher active. Keep PC awake. Press Ctrl+C to stop.")
            last_keepalive = 0.0
            last_status = ""

            while True:
                try:
                    await self._open_registration(page)
                    content = await page.content()
                    state = detect_state(page.url, content)
                except PlaywrightTimeoutError:
                    state = PageState("unknown", "page load timeout")
                except Exception as exc:
                    state = PageState("unknown", f"load error: {exc}")

                status_line = f"{state.status}: {state.reason}"
                if status_line != last_status:
                    self.log(status_line)
                    if state.status in {"unknown", "error"}:
                        await self._save_unknown_page(page)
                    last_status = status_line

                if state.is_login:
                    await urgent_alarm(
                        "Flex session expired",
                        "Flex redirected to login. Solve CAPTCHA again before registration opens.",
                        ntfy_topic_url=self.config.ntfy_topic_url,
                        link=LOGIN_URL,
                        sound_path=self.config.alarm_sound_path,
                    )
                    await self._ensure_login(page)
                    self.registration_url = await self._resolve_registration_url(page)
                    last_keepalive = asyncio.get_running_loop().time()

                if state.is_open:
                    await urgent_alarm(
                        "Flex registration open",
                        "Course registration appears open. Open Flex now.",
                        ntfy_topic_url=self.config.ntfy_topic_url,
                        link=self.registration_url,
                        sound_path=self.config.alarm_sound_path,
                    )
                    self.log("Watcher stopped on registration page. Browser stays open.")
                    self.log("Register in the open browser. Leave this terminal open.")
                    await asyncio.Event().wait()

                if state.is_error:
                    self.log(f"Site error/loading issue. Retrying in {int(self.config.error_retry_seconds)}s.")
                    await asyncio.sleep(self.config.error_retry_seconds)
                    continue

                now = asyncio.get_running_loop().time()
                if now - last_keepalive >= self.config.keepalive_seconds:
                    await self._keepalive(page)
                    last_keepalive = now

                sleep_seconds = self.config.closed_reload_seconds if state.is_closed else self.config.poll_seconds
                jitter = random.uniform(0, min(2.0, sleep_seconds / 10))
                self.log(f"Next reload in {int(sleep_seconds + jitter)}s.")
                await asyncio.sleep(sleep_seconds + jitter)
        finally:
            await context.close()
            await playwright.stop()

    async def _keepalive(self, page: Page) -> None:
        try:
            await page.evaluate("() => document.title")
            self.log("Keepalive OK.")
        except Exception as exc:
            self.log(f"Keepalive failed: {exc}")

    async def _safe_goto(self, page: Page, url: str) -> None:
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(self.config.navigation_timeout_seconds * 1000),
            )
        except PlaywrightTimeoutError:
            self.log(f"Navigation timeout: {url}")
            raise
        except PlaywrightError as exc:
            self.log(f"Navigation/browser error: {exc}")
            raise

    async def _resolve_registration_url(self, page: Page) -> str:
        discovered = await self._find_registration_link(page)
        if discovered:
            self.log(f"Using generated registration link: {discovered}")
            return discovered

        try:
            await self._safe_goto(page, HOME_URL)
            discovered = await self._find_registration_link(page)
            if discovered:
                self.log(f"Using generated registration link: {discovered}")
                return discovered
        except Exception as exc:
            self.log(f"Home link scan failed: {exc}")

        self.log("No generated registration link found yet.")
        discovered = await self._click_registration_menu(page)
        if discovered:
            self.log(f"Clicked registration menu: {discovered}")
            return discovered

        self.log("In browser, open/click Course Registration once; watcher will capture its URL.")
        discovered = await self._wait_for_registration_link(page, timeout_seconds=180)
        if discovered:
            self.log(f"Captured registration link: {discovered}")
            return discovered

        # Some Flex deployments accept the route without dump and generate/validate server-side.
        if (
            self.config.registration_url
            and "dump=" not in self.config.registration_url
            and "/Login" not in self.config.registration_url
            and "/Student/CourseRegistrationBS" not in self.config.registration_url
        ):
            self.log(f"Using configured registration route: {self.config.registration_url}")
            return self.config.registration_url

        self.log(f"Using bare registration route: {BARE_REGISTRATION_URL}")
        return BARE_REGISTRATION_URL

    async def _find_registration_link(self, page: Page) -> str:
        if "/Student/CourseRegistration" in page.url:
            return page.url

        links = await page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]'))
                .map((a) => ({
                    href: a.getAttribute('href'),
                    text: (a.innerText || a.textContent || '').trim()
                }))
                .filter((item) => item.href)"""
        )
        for item in links:
            href = item["href"]
            text = item["text"].lower()
            if "/Student/CourseRegistration" in href and "course registration" in text:
                return urljoin(page.url, href)
        for item in links:
            href = item["href"]
            if "/Student/CourseRegistration" in href:
                return urljoin(page.url, href)
        return ""

    async def _click_registration_menu(self, page: Page) -> str:
        locator = page.locator('a[href*="/Student/CourseRegistration"]').filter(has_text="Course Registration").first
        try:
            await locator.click()
            await page.wait_for_url(
                "**/Student/CourseRegistration**",
                timeout=int(self.config.navigation_timeout_seconds * 1000),
            )
            return page.url
        except Exception:
            return ""

    async def _open_registration(self, page: Page) -> None:
        await self._safe_goto(page, HOME_URL)
        state = await self._current_state(page)
        if state.is_error:
            self.log("Home showed error while trying registration.")
            return
        if state.is_login:
            return

        discovered = await self._find_registration_link(page)
        if discovered:
            self.registration_url = discovered
            await self._safe_goto(page, discovered)
            state = await self._current_state(page)
            if state.is_error:
                self.log("Registration page showed error. Returning to Home.")
                await self._safe_goto(page, HOME_URL)
            return

        clicked = await self._click_registration_menu(page)
        if clicked:
            self.registration_url = clicked
            state = await self._current_state(page)
            if state.is_error:
                self.log("Registration click showed error. Returning to Home.")
                await self._safe_goto(page, HOME_URL)
            return

        await self._safe_goto(page, self.registration_url)

    async def _current_state(self, page: Page) -> PageState:
        return detect_state(page.url, await page.content())

    async def _wait_for_registration_link(self, page: Page, timeout_seconds: float) -> str:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            try:
                discovered = await self._find_registration_link(page)
            except Exception:
                discovered = ""
            if discovered:
                return discovered
            await asyncio.sleep(1)
        return ""

    async def _save_unknown_page(self, page: Page) -> None:
        try:
            path = LOG_DIR / f"unknown-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.html"
            html = await page.content()
            path.write_text(html, encoding="utf-8")
            self.log(f"Saved unknown page: {path}")
        except Exception as exc:
            self.log(f"Failed to save unknown page: {exc}")


async def test_alert(config: Config) -> None:
    link = config.registration_url
    if not link or "/Student/CourseRegistrationBS" in link:
        link = BARE_REGISTRATION_URL
    await urgent_alarm(
        "Flex watcher test alert",
        "PC alarm and Android ntfy test.",
        ntfy_topic_url=config.ntfy_topic_url,
        link=link,
        sound_path=config.alarm_sound_path,
        repeat_phone_seconds=30,
    )
