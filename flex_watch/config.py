from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PROFILE_DIR = ROOT / ".playwright-profile"
LOG_DIR = ROOT / "logs"


@dataclass(frozen=True)
class Config:
    flex_username: str
    flex_password: str
    registration_url: str
    ntfy_topic_url: str
    poll_seconds: float = 7.0
    closed_reload_seconds: float = 60.0
    keepalive_seconds: float = 180.0
    navigation_timeout_seconds: float = 120.0
    error_retry_seconds: float = 5.0
    alarm_sound_path: str = ""
    unexpected_alarm_sound_path: str = ""


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _float_value(values: dict[str, str], key: str, default: float) -> float:
    raw = values.get(key, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return value


def load_config(require_credentials: bool = True, require_registration_url: bool = True) -> Config:
    values = _parse_env(ENV_PATH)
    missing = []
    if require_registration_url and not values.get("REGISTRATION_URL"):
        missing.append("REGISTRATION_URL")
    if require_credentials:
        for key in ("FLEX_USERNAME", "FLEX_PASSWORD"):
            if not values.get(key):
                missing.append(key)
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing {names}. Create/edit {ENV_PATH}")

    return Config(
        flex_username=values.get("FLEX_USERNAME", ""),
        flex_password=values.get("FLEX_PASSWORD", ""),
        registration_url=values.get("REGISTRATION_URL", "https://flexstudent.nu.edu.pk/Student/CourseRegistration"),
        ntfy_topic_url=values.get("NTFY_TOPIC_URL", ""),
        poll_seconds=_float_value(values, "POLL_SECONDS", 7.0),
        closed_reload_seconds=_float_value(values, "CLOSED_RELOAD_SECONDS", 60.0),
        keepalive_seconds=_float_value(values, "KEEPALIVE_SECONDS", 180.0),
        navigation_timeout_seconds=_float_value(values, "NAVIGATION_TIMEOUT_SECONDS", 120.0),
        error_retry_seconds=_float_value(values, "ERROR_RETRY_SECONDS", 5.0),
        alarm_sound_path=values.get("ALARM_SOUND_PATH", ""),
        unexpected_alarm_sound_path=values.get("UNEXPECTED_ALARM_SOUND_PATH", ""),
    )
