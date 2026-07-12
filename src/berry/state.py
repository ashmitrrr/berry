"""Pet state: hunger, mood, and persistence to ~/.berry/state.json."""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

STATE_DIR = Path.home() / ".berry"
STATE_FILE = STATE_DIR / "state.json"

MAX_HUNGER = 100.0
HUNGER_DECAY_PER_HOUR = 8.0
SLEEP_AFTER_HOURS_IDLE = 6.0


@dataclass
class PetState:
    species: str = "cat"
    name: str = "Fizz"
    hunger: float = 100.0
    last_fed: float = 0.0
    last_interaction: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _ensure_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


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
    """Recompute hunger based on time elapsed since last feeding."""
    hours_elapsed = (time.time() - state.last_fed) / 3600
    decayed = max(0.0, MAX_HUNGER - hours_elapsed * HUNGER_DECAY_PER_HOUR)
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


def mood(state: PetState) -> str:
    hours_idle = (time.time() - state.last_interaction) / 3600
    if hours_idle > SLEEP_AFTER_HOURS_IDLE:
        return "sleeping"
    if state.hunger < 20:
        return "hungry"
    if state.hunger > 70:
        return "happy"
    return "idle"
