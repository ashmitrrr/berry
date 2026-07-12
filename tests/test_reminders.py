"""Reminder time parsing -- 'in 10m', 'in 2h', '15:30', and the rest."""

from datetime import datetime, timedelta

import pytest

from berry.reminders import parse_when


def test_parse_minutes():
    due = parse_when("in 10m")
    delta = due - datetime.now()
    assert timedelta(minutes=9, seconds=50) < delta <= timedelta(minutes=10, seconds=5)


def test_parse_hours():
    due = parse_when("in 2h")
    delta = due - datetime.now()
    assert timedelta(hours=1, minutes=59) < delta <= timedelta(hours=2, minutes=1)


def test_parse_seconds():
    due = parse_when("in 90s")
    delta = due - datetime.now()
    assert timedelta(seconds=85) < delta <= timedelta(seconds=95)


def test_parse_clock_time():
    due = parse_when("15:30")
    assert due.hour == 15
    assert due.minute == 30


def test_clock_time_in_the_past_rolls_to_tomorrow():
    past = (datetime.now() - timedelta(hours=1)).strftime("%H:%M")
    due = parse_when(past)
    assert due > datetime.now()


def test_invalid_input_raises():
    with pytest.raises(ValueError):
        parse_when("whenever")


def test_invalid_clock_time_raises():
    with pytest.raises(ValueError):
        parse_when("25:99")
