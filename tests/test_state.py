"""Mood transitions and hunger decay -- pure logic, no real Mac needed."""

import time
import pytest

from berry.state import MAX_HUNGER, PetState, apply_decay, mood


def test_manual_sleep_overrides_everything():
    state = PetState(manual_sleep=True, hunger=100.0)
    assert mood(state, cpu_percent=90) == "sleeping"


def test_sleeping_after_hours_idle():
    six_hours_ago = time.time() - 6.5 * 3600
    state = PetState(last_interaction=six_hours_ago, hunger=100.0)
    assert mood(state) == "sleeping"


def test_hungry_below_threshold():
    state = PetState(hunger=10.0, last_interaction=time.time())
    assert mood(state) == "hungry"


def test_hungry_overrides_running():
    # hunger is checked before cpu, on purpose -- a starving pet doesn't
    # care that your CPU is busy.
    state = PetState(hunger=10.0, last_interaction=time.time())
    assert mood(state, cpu_percent=95) == "hungry"


def test_running_when_cpu_high():
    state = PetState(hunger=50.0, last_interaction=time.time())
    assert mood(state, cpu_percent=75) == "running"


def test_happy_above_threshold():
    state = PetState(hunger=80.0, last_interaction=time.time())
    assert mood(state) == "happy"


def test_idle_is_the_default():
    state = PetState(hunger=50.0, last_interaction=time.time())
    assert mood(state) == "idle"


def test_decay_reduces_hunger_over_time():
    an_hour_ago = time.time() - 3600
    state = PetState(hunger=MAX_HUNGER, last_fed=an_hour_ago)
    decayed = apply_decay(state)
    assert decayed.hunger < MAX_HUNGER


def test_decay_never_increases_hunger():
    # feeding is the only thing allowed to raise hunger back up
    just_fed = time.time()
    state = PetState(hunger=MAX_HUNGER, last_fed=just_fed)
    decayed = apply_decay(state)
    assert decayed.hunger <= MAX_HUNGER

def test_idle_multiplier_does_not_apply_retroactively(monkeypatch):
    """Going idle *now* shouldn't multiply decay for hours spent active earlier."""
    import berry.state as state_module

    monkeypatch.setattr(state_module, "_idle_seconds_macos", lambda: None)
    one_hour_ago = time.time() - 3600
    state = PetState(hunger=100.0, last_fed=one_hour_ago, last_decay_at=one_hour_ago)
    state = apply_decay(state)
    after_active_hour = state.hunger
    assert after_active_hour == pytest.approx(
        100.0 - state_module.HUNGER_DECAY_PER_HOUR, abs=0.5
    )

    monkeypatch.setattr(state_module, "_idle_seconds_macos", lambda: 400)
    state.last_decay_at = time.time() - 3600
    state = apply_decay(state)

    expected = after_active_hour - state_module.HUNGER_DECAY_PER_HOUR * 1.5
    assert state.hunger == pytest.approx(expected, abs=0.5)
