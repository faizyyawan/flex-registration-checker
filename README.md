# Flex Registration Watcher

Local watcher for Flex course registration. It does not bypass CAPTCHA. You log in normally, solve reCAPTCHA once, then the app keeps the browser session warm and alerts when registration appears open.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Edit `.env` with your Flex credentials and a private `ntfy` topic URL. `REGISTRATION_URL` is only a fallback; the watcher prefers the fresh generated `CourseRegistration` link it finds after login.

On Android, install `ntfy`, subscribe to the same topic, and set that subscription to a loud/urgent sound.

## Commands

```powershell
python -m flex_watch test-alert
python -m flex_watch login-only
python -m flex_watch check-once
python -m flex_watch start
```

`start` opens Chromium, fills username/password, waits for you to solve reCAPTCHA, finds the current registration link from Flex, then watches it. If the link is hidden behind the portal menu, click Course Registration once in the browser and the watcher will capture the generated URL. Keep the PC awake.

When registration says `not active yet`, the watcher waits `CLOSED_RELOAD_SECONDS` (default 60 seconds), goes back to Flex Home, grabs the fresh Course Registration link, and reloads.

If Flex is slow, the watcher waits up to `NAVIGATION_TIMEOUT_SECONDS` (default 120 seconds). If an ASP.NET yellow error page appears after login, it returns to the login screen and restarts login. If an error appears after clicking Course Registration, it returns to Home and retries the registration flow. Unknown/error HTML is saved under `logs/`.

If an unexpected/unknown state appears, the watcher sends an urgent phone notification and plays `UNEXPECTED_ALARM_SOUND_PATH` (default example: `C:\Windows\Media\Ring10.wav`) so you can intervene.

## Notes

- If Flex uses idle timeout, polling/keepalive should keep the session alive.
- If Flex uses absolute timeout, the app cannot prevent expiry; it will alarm when it sees a redirect to login.
- This app only alerts. It does not auto-register.
