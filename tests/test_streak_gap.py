# lightweight pure test if python
def compute_streak(dates, today):
    days = {d[:10] for d in dates}
    cursor = today[:10]
    streak = 0
    from datetime import datetime, timedelta
    while cursor in days:
        streak += 1
        cursor = (datetime.fromisoformat(cursor).date() - timedelta(days=1)).isoformat()
    return streak

def test_gap_resets():
    assert compute_streak(["2026-07-01", "2026-07-03"], "2026-07-03") == 1
