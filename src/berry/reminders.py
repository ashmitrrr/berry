"""Reminder storage and simple natural-time parsing.

Reminders are stored in ~/.berry/reminders.json so both the
interactive CLI and the background daemon read/write the same state.
"""

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

STATE_DIR = Path.home() / ".berry"
REMINDERS_FILE = STATE_DIR / "reminders.json"

_DURATION_RE = re.compile(r"^in\s+(\d+)\s*(s|sec|secs|m|min|mins|h|hr|hrs|hour|hours)$")
_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


@dataclass
class Reminder:
    id: str
    text: str
    due_at: float  # unix timestamp
    fired: bool = False


def _ensure_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load() -> list[dict]:
    _ensure_dir()
    if not REMINDERS_FILE.exists():
        return []
    return json.loads(REMINDERS_FILE.read_text())


def _save(items: list[dict]) -> None:
    _ensure_dir()
    REMINDERS_FILE.write_text(json.dumps(items, indent=2))


def parse_when(when: str) -> datetime:
    """Parse 'in 10m', 'in 2h', 'in 90s', or 'HH:MM' into a datetime.

    Clock times in the past today roll over to tomorrow.
    """
    cleaned = when.strip().lower()

    m = _DURATION_RE.match(cleaned)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("s"):
            delta = timedelta(seconds=amount)
        elif unit.startswith("m"):
            delta = timedelta(minutes=amount)
        else:
            delta = timedelta(hours=amount)
        return datetime.now() + delta

    m = _CLOCK_RE.match(cleaned)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"'{when}' isn't a valid time of day.")
        now = datetime.now()
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    raise ValueError(
        f"Couldn't understand time '{when}'. Try 'in 10m', 'in 2h', or '15:30'."
    )


def add_reminder(text: str, due_at: datetime) -> Reminder:
    items = _load()
    r = Reminder(id=uuid.uuid4().hex[:8], text=text, due_at=due_at.timestamp())
    items.append(asdict(r))
    _save(items)
    return r


def all_reminders() -> list[dict]:
    return sorted(_load(), key=lambda r: r["due_at"])


def pending_reminders() -> list[dict]:
    return [r for r in all_reminders() if not r["fired"]]


def due_reminders() -> list[dict]:
    now = time.time()
    return [r for r in _load() if not r["fired"] and r["due_at"] <= now]


def mark_fired(reminder_id: str) -> None:
    items = _load()
    for r in items:
        if r["id"] == reminder_id:
            r["fired"] = True
    _save(items)
