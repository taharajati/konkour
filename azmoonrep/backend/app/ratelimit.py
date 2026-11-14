"""Fixed-window rate limits stored in MongoDB, so every API replica shares the counts.

    ratelimit.hit("login-ip", ip, limit=20, window=900)   # raises 429 when exceeded

Counter documents expire through a TTL index (see db.ensure_indexes).
"""
import datetime as dt
import math

from fastapi import HTTPException

from . import clock, db


def hit(name: str, key: str, limit: int, window: int, message: str | None = None):
    now = clock.now_utc()
    epoch = now.timestamp()
    start = math.floor(epoch / window) * window
    doc_id = f"{name}:{key}:{start}"
    res = db.db.rate_limits.find_one_and_update(
        {"_id": doc_id},
        {"$inc": {"n": 1},
         "$setOnInsert": {"expires_at": now + dt.timedelta(seconds=window + 60)}},
        upsert=True, return_document=True)
    n = (res or {}).get("n", 1)
    if n > limit:
        retry = int(start + window - epoch) + 1
        raise HTTPException(429, message or "تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره امتحان کن.",
                            headers={"Retry-After": str(retry)})
    return n


def reset(name: str, key: str, window: int):
    """clear the current window (e.g. after a successful login)"""
    epoch = clock.now_utc().timestamp()
    start = math.floor(epoch / window) * window
    db.db.rate_limits.delete_one({"_id": f"{name}:{key}:{start}"})
