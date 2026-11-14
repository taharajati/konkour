"""One definition of "now" and "today" for the whole app.

Students live in Iran: a study day starts at local midnight (Asia/Tehran), not at UTC
midnight (03:30 Tehran time). Timestamps are still stored as naive UTC datetimes, which
is what pymongo returns by default; only *days* are Tehran days, stored as "YYYY-MM-DD".
"""
import datetime as dt
import os
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("APP_TZ", "Asia/Tehran"))

# tests can freeze time by setting this to an aware datetime
_frozen: dt.datetime | None = None


def now_utc() -> dt.datetime:
    """naive UTC datetime, for storing timestamps"""
    if _frozen is not None:
        return _frozen.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def today() -> dt.date:
    """the student's calendar day (Tehran)"""
    if _frozen is not None:
        return _frozen.astimezone(TZ).date()
    return dt.datetime.now(TZ).date()


def today_str() -> str:
    return today().isoformat()


def day_of(ts: dt.datetime) -> dt.date:
    """Tehran calendar day of a stored naive-UTC timestamp"""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts.astimezone(TZ).date()


def freeze(at: dt.datetime | None) -> None:
    global _frozen
    _frozen = at
