"""Pre-launch hardening: login lockout, usernames, password hashes, practice key-peeking."""
import hashlib

from fastapi.testclient import TestClient

from app import auth, scheduler
from app.main import app
from tests.conftest import seed


def _client():
    return TestClient(app)


def test_usernames_are_case_insensitive(fresh_db):
    c = _client()
    assert c.post("/auth/register", json={"username": "Kian", "password": "long-enough-1"}).status_code == 200
    assert c.post("/auth/register", json={"username": "kian", "password": "long-enough-1"}).status_code == 409
    assert fresh_db.users.find_one({})["username"] == "kian"
    assert c.post("/auth/login", json={"username": "KIAN", "password": "long-enough-1"}).status_code == 200


def test_only_failed_logins_lock_an_account(fresh_db):
    c = _client()
    c.post("/auth/register", json={"username": "kian", "password": "long-enough-1"})
    for _ in range(15):                                    # good logins never add up
        assert c.post("/auth/login", json={"username": "kian", "password": "long-enough-1"}).status_code == 200
    for _ in range(10):
        assert c.post("/auth/login", json={"username": "kian", "password": "nope-nope"}).status_code == 401
    r = c.post("/auth/login", json={"username": "kian", "password": "long-enough-1"})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_legacy_hash_verifies_and_is_upgraded_on_login(fresh_db):
    salt = "ab" * 16
    legacy = f"{salt}${hashlib.pbkdf2_hmac('sha256', b'old-password', salt.encode(), 100_000).hex()}"
    assert auth.verify_password("old-password", legacy) and not auth.verify_password("other", legacy)
    fresh_db.users.insert_one({"username": "olduser", "password_hash": legacy, "role": "student"})
    assert _client().post("/auth/login", json={"username": "olduser", "password": "old-password"}).status_code == 200
    new = fresh_db.users.find_one({"username": "olduser"})["password_hash"]
    assert new.startswith("pbkdf2$") and auth.verify_password("old-password", new)


def test_practice_cannot_ask_for_arbitrary_question_ids(fresh_db):
    student = seed(fresh_db)
    some = fresh_db.questions.find_one({"review_status": "approved"})
    assert scheduler.build_practice_session(student["_id"], [], 5, question_ids=[some["public_id"]]) is None


def test_practiced_question_is_not_the_daily_pick(fresh_db):
    student = seed(fresh_db)
    qs = list(fresh_db.questions.find({"concept_id": "c1", "review_status": "approved"}))
    first = qs[0]
    fresh_db.responses.insert_one({"student_id": student["_id"], "question_id": first["_id"],
                                   "concept_id": "c1", "correct": False, "context": "practice"})
    for _ in range(20):
        q, repeat = scheduler.pick_question(student["_id"], "c1")
        assert q["_id"] != first["_id"] and not repeat


def test_bulk_approve_refuses_unverified_keys(fresh_db):
    seed(fresh_db)
    q = fresh_db.questions.find_one({"review_status": "approved"})
    fresh_db.questions.update_one({"_id": q["_id"]}, {"$set": {"review_status": "pending",
                                                                "needs_answer_verification": True}})
    fresh_db.users.insert_one({"username": "boss", "role": "admin", "password_hash": auth.hash_password("admin-pass-1")})
    c = _client()
    tok = c.post("/auth/login", json={"username": "boss", "password": "admin-pass-1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/admin/questions/bulk-review", json={"public_ids": [q["public_id"]], "approved": True}, headers=h)
    assert r.status_code == 422 and q["public_id"] in r.json()["detail"]
    assert fresh_db.questions.find_one({"_id": q["_id"]})["review_status"] == "pending"
