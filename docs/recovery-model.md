# Recovery Model

The watcher treats the portal as a small state machine:

- Login stage: wait for Home after the user submits login/CAPTCHA.
- Login error: if a server/yellow error page appears before Home, return to Login and restart.
- Home stage: verify the portal menu exists.
- Registration stage: click the live Course Registration link and wait for the generated `dump` URL.
- Registration error: if a server/yellow error page appears after the click, return to Home and retry.
- Inactive registration: wait `CLOSED_RELOAD_SECONDS`, go Home, and click Course Registration again.
- Open registration: alarm, then stop automation so the browser stays on the registration page.
