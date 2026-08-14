from __future__ import annotations

import argparse
import asyncio
import sys

from .config import load_config
from .watcher import FlexWatcher, test_alert


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m flex_watch")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("start", help="login if needed, then watch registration")
    subparsers.add_parser("test-alert", help="test PC alarm and ntfy notification")
    subparsers.add_parser("check-once", help="check registration page once")
    subparsers.add_parser("login-only", help="open browser and complete manual login")
    return parser


async def run(command: str) -> int:
    config = load_config(
        require_credentials=command not in {"test-alert"},
        require_registration_url=False,
    )
    watcher = FlexWatcher(config)

    if command == "start":
        await watcher.start()
        return 0
    if command == "test-alert":
        await test_alert(config)
        return 0
    if command == "check-once":
        await watcher.check_once()
        return 0
    if command == "login-only":
        await watcher.login_only()
        return 0
    raise ValueError(f"Unknown command: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run(args.command))
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        return 1
