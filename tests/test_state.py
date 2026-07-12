"""Mood transitions and hunger decay -- pure logic, no real Mac needed."""

import time

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
