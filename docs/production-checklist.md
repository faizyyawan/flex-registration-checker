# Production Checklist

Before registration opens:

1. Run `python -m flex_watch test-alert`.
2. Confirm Android `ntfy` notification arrives.
3. Confirm PC alarm sound plays.
4. Run `python -m unittest discover -v`.
5. Run `python -m flex_watch start`.
6. Solve CAPTCHA once.
7. Confirm watcher logs `Home page verified.`
8. Leave the terminal and browser open.

When registration opens, do not press `Ctrl+C` until you finish registering.
