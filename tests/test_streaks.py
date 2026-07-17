"""Tests for berry.streaks.compute_streak (issue #4)."""

from berry.streaks import compute_streak


def test_consecutive_days_streak():
    dates = ["2026-07-14", "2026-07-15", "2026-07-16"]
    assert compute_streak(dates, today="2026-07-16") == 3


def test_gap_breaks_streak():
    dates = ["2026-07-01", "2026-07-03"]
    assert compute_streak(dates, today="2026-07-03") == 1


def test_no_feed_today_gives_zero_streak():
    dates = ["2026-07-14", "2026-07-15"]
    assert compute_streak(dates, today="2026-07-16") == 0


def test_empty_history_gives_zero_streak():
    assert compute_streak([], today="2026-07-16") == 0