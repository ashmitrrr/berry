"""Check-in scheduling and greeting -- the pure parts.

The panels themselves (key focus, Enter/Esc handling, the background
reply thread) need a real Mac and are hand-verified, per the project
convention for AppKit code.
"""

from berry.checkin import CHECKIN_COOLDOWN_SECS, due_for_checkin, greeting_text


def test_first_checkin_is_always_due():
    # a fresh menubar session starts with last_checkin = 0.0
    assert due_for_checkin(0.0, 1_000_000.0)


def test_checkin_within_cooldown_is_suppressed():
    now = 10_000.0
    assert not due_for_checkin(now - CHECKIN_COOLDOWN_SECS / 2, now)


def test_checkin_after_cooldown_is_due():
    now = 10_000.0
    assert due_for_checkin(now - CHECKIN_COOLDOWN_SECS - 1, now)


def test_greeting_mentions_the_pet_by_name():
    assert "berry" in greeting_text("berry")
    assert "how are you" in greeting_text("berry")
