"""Pet state: hunger, mood, and persistence to ~/.berry/state.json."""

import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

STATE_DIR = Path.home() / ".berry"
STATE_FILE = STATE_DIR / "state.json"

MAX_HUNGER = 100.0
HUNGER_DECAY_PER_HOUR = 8.0
SLEEP_AFTER_HOURS_IDLE = 6.0

_IDLE_THRESHOLD_SECS = 300   # 5 minutes of system HID idle
_IDLE_DECAY_MULTIPLIER = 1.5  # hunger drains 50% faster when nobody's at the keyboard

# Cache ioreg result for 30s — it's a subprocess call we don't want at 1 Hz.
_idle_cache: tuple[float, float | None] = (0.0, None)
_IDLE_CACHE_TTL = 30.0


@dataclass
class PetState:
    species: str = "cat"
    name: str = "Fizz"
    hunger: float = 100.0
    last_fed: float = 0.0
    last_interaction: float = 0.0
    manual_sleep: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _ensure_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _idle_seconds_macos() -> float | None:
    """Return system HID idle time in seconds, or None on any failure."""
    global _idle_cache
    now = time.time()
    if now - _idle_cache[0] < _IDLE_CACHE_TTL:
        return _idle_cache[1]
    result = None
    try:
        proc = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            capture_output=True, text=True, timeout=2,
        )
        m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', proc.stdout)
        if m:
            result = int(m.group(1)) / 1_000_000_000  # nanoseconds → seconds
    except Exception:
        pass
    _idle_cache = (now, result)
    return result


def load_state() -> PetState:
    _ensure_dir()
    if not STATE_FILE.exists():
        now = time.time()
        state = PetState(last_fed=now, last_interaction=now)
        save_state(state)
        return state
    data = json.loads(STATE_FILE.read_text())
    return PetState(**data)


def save_state(state: PetState) -> None:
    _ensure_dir()
    STATE_FILE.write_text(json.dumps(state.to_dict(), indent=2))


def apply_decay(state: PetState) -> PetState:
    """Recompute hunger; applies 1.5× rate when HID idle > 5 min."""
    hours_elapsed = (time.time() - state.last_fed) / 3600
    rate = HUNGER_DECAY_PER_HOUR
    idle = _idle_seconds_macos()
    if idle is not None and idle > _IDLE_THRESHOLD_SECS:
        rate *= _IDLE_DECAY_MULTIPLIER
    decayed = max(0.0, MAX_HUNGER - hours_elapsed * rate)
    state.hunger = min(state.hunger, decayed)
    return state


def feed(state: PetState) -> PetState:
    state.hunger = MAX_HUNGER
    state.last_fed = time.time()
    state.last_interaction = time.time()
    save_state(state)
    return state


def touch(state: PetState) -> PetState:
    """Record an interaction (any command counts) so the pet doesn't sleep."""
    state.last_interaction = time.time()
    save_state(state)
    return state


def nap(state: PetState) -> PetState:
    """Set the manual sleep flag so mood() returns 'sleeping' regardless of hunger/CPU."""
    state.manual_sleep = True
    save_state(state)
    return state


def wake(state: PetState) -> PetState:
    """Clear the manual sleep flag and reset the idle timer."""
    state.manual_sleep = False
    state.last_interaction = time.time()
    save_state(state)
    return state


def mood(state: PetState, cpu_percent: float | None = None) -> str:
    if state.manual_sleep:
        return "sleeping"
    hours_idle = (time.time() - state.last_interaction) / 3600
    if hours_idle > SLEEP_AFTER_HOURS_IDLE:
        return "sleeping"
    if state.hunger < 20:
        return "hungry"
    if cpu_percent is not None and cpu_percent > 50:
        return "running"
    if state.hunger > 70:
        return "happy"
    return "idle"
