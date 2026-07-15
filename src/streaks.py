"""Feeding streak tracking (issue #4)."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def compute_streak(feed_dates: list[str], today: str | None = None) -> int:
    days = {d[:10] for d in feed_dates}
    cursor = (today or date.today().isoformat())[:10]
    streak = 0
    while cursor in days:
        streak += 1
        cursor = (datetime.fromisoformat(cursor).date() - timedelta(days=1)).isoformat()
    return streak
