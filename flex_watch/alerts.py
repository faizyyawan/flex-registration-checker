from __future__ import annotations

import asyncio
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def send_ntfy(topic_url: str, title: str, message: str, link: str = "") -> None:
    if not topic_url:
        return

    headers = {
        "Title": title,
        "Priority": "urgent",
        "Tags": "warning",
    }
    if link:
        headers["Click"] = link

    data = message.encode("utf-8")
    request = urllib.request.Request(topic_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"ntfy failed: {exc}", flush=True)


async def urgent_alarm(
    title: str,
    message: str,
    *,
    ntfy_topic_url: str = "",
    link: str = "",
    sound_path: str = "",
    repeat_phone_seconds: float = 60.0,
) -> None:
    print("", flush=True)
    print("=" * 72, flush=True)
    print(title, flush=True)
    print(message, flush=True)
    if link:
        print(link, flush=True)
    print("Press Enter to stop alarm.", flush=True)
    print("=" * 72, flush=True)

    stop_event = asyncio.Event()

    async def wait_for_enter() -> None:
        await asyncio.to_thread(sys.stdin.readline)
        stop_event.set()

    async def phone_loop() -> None:
        while not stop_event.is_set():
            await asyncio.to_thread(send_ntfy, ntfy_topic_url, title, message, link)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=repeat_phone_seconds)
            except asyncio.TimeoutError:
                continue

    async def sound_loop() -> None:
        if sys.platform != "win32":
            while not stop_event.is_set():
                print("\a", end="", flush=True)
                await asyncio.sleep(1)
            return

        import winsound

        sound = Path(sound_path) if sound_path else None
        if sound and sound.exists():
            winsound.PlaySound(
                str(sound),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
            )
            await stop_event.wait()
            winsound.PlaySound(None, winsound.SND_PURGE)
            return

        while not stop_event.is_set():
            winsound.Beep(2500, 700)
            await asyncio.sleep(0.15)
            winsound.Beep(3200, 700)
            await asyncio.sleep(0.15)

    started = time.monotonic()
    await asyncio.gather(wait_for_enter(), phone_loop(), sound_loop())
    elapsed = int(time.monotonic() - started)
    print(f"Alarm stopped after {elapsed}s.", flush=True)
