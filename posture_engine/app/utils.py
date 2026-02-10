# Helper utilities
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
def unix_ms_to_ist(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(IST)
def ms_to_minutes(ms: int) -> float:
    return ms / 1000 / 60


def classify_value(value, ranges):
    value = abs(value)
    for level, (low, high) in ranges.items():
        if low <= value <= high:
            return level
    return "bad"

