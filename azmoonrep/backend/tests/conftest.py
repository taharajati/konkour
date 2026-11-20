"""Tests run against an in-memory MongoDB (mongomock): no server, no network."""
import datetime as dt
import os
import sys

import mongomock
import pytest

os.environ.setdefault("PBKDF2_ITERATIONS", "2000")   # fast hashes in tests
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import clock, db  # noqa: E402

TEHRAN_NOON = dt.datetime(2026, 11, 14, 8, 30, tzinfo=dt.timezone.utc)   # 12:00 Tehran


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch, tmp_path):
    mem = mongomock.MongoClient().azmoon_test
    monkeypatch.setattr(db, "db", mem)
    from app import importer
    monkeypatch.setattr(importer, "STATIC_QUESTIONS_DIR", str(tmp_path / "static"))
    db.ensure_indexes()
    # mongomock enforces TTL indexes against the real clock; with the frozen test clock
    # every counter would look expired at once
    for coll in (mem.rate_limits, mem.otp_codes):
        coll.drop_index("expires_at_1")
    clock.freeze(TEHRAN_NOON)
    yield mem
    clock.freeze(None)


def set_day(days_after: int, hour_utc: float = 8.5):
    clock.freeze(TEHRAN_NOON.replace(hour=0, minute=0) + dt.timedelta(days=days_after, hours=hour_utc))


def seed(mem, per_concept=3, extra_pending=True):
    """two lessons; c3 needs c1. Each concept: approved questions + one pending one"""
    concepts = [("c1", "L1", 1, []), ("c2", "L1", 2, []), ("c3", "L2", 3, ["c1"]),
                ("c4", "L2", 4, [])]
    for cid, lesson, order, prereqs in concepts:
        mem.concepts.insert_one({"concept_id": cid, "title": cid, "lesson_id": lesson,
                                 "book_id": "B", "chapter_id": "B_ch1", "source": "taxonomy",
                                 "order_in_curriculum": order, "prereq_ids": prereqs})
        for i in range(per_concept):
            mem.questions.insert_one({
                "public_id": f"{cid}_q{i}", "concept_id": cid, "type": "multiple_choice_4",
                "difficulty": 2, "stem_md": f"{cid} سؤال {i}",
                "options": ["الف ۱", "ب ۲", "پ ۳", "ت ۴"], "answer": {"option": 3},
                "solution_md": "پس گزینهٔ ۳ درست است.", "review_status": "approved"})
        if extra_pending:
            mem.questions.insert_one({
                "public_id": f"{cid}_pending", "concept_id": cid, "type": "multiple_choice_4",
                "difficulty": 2, "stem_md": "تأیید نشده", "options": ["a", "b", "c", "d"],
                "answer": {"option": 1}, "review_status": "pending"})
    student = {"username": "s1", "role": "student", "onboarded": True}
    student["_id"] = mem.users.insert_one(student).inserted_id
    return student
