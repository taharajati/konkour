"""Progress page, mistakes list, change password, admin overview and user tools."""
from fastapi.testclient import TestClient

from app import auth, scheduler
from app.main import app
from tests.conftest import seed, set_day


def _login(c, username, password):
    return {"Authorization": "Bearer " + c.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]}


def _student(fresh_db, c):
    c.post("/auth/register", json={"username": "kian", "password": "long-enough-1"})
    return fresh_db.users.find_one({"username": "kian"}), _login(c, "kian", "long-enough-1")


def test_progress_counts_and_activity(fresh_db):
    c = TestClient(app)
    seed(fresh_db)
    user, h = _student(fresh_db, c)
    q = fresh_db.questions.find_one({"concept_id": "c1", "review_status": "approved"})
    fresh_db.responses.insert_one({"student_id": user["_id"], "question_id": q["_id"], "concept_id": "c1",
                                   "correct": False, "context": "daily", "answered_at": scheduler.clock.now_utc()})
    scheduler.update_concept_state(user["_id"], "c1", False, 1000, 40000)
    p = c.get("/auth/me/progress", headers=h).json()
    assert p["total"] >= 1 and p["new"] == p["total"] - 1 and p["learning"] == 1
    assert p["activity"][-1]["answered"] == 1 and len(p["activity"]) == 35
    assert p["weak"][0]["concept_id"] == "c1" and p["weak"][0]["lapses"] == 1
    assert p["streak_days"] == 1 and p["due_tomorrow"] == 1


def test_wrong_list_has_titles_and_stems(fresh_db):
    c = TestClient(app)
    seed(fresh_db)
    user, h = _student(fresh_db, c)
    q = fresh_db.questions.find_one({"concept_id": "c1", "review_status": "approved"})
    fresh_db.responses.insert_one({"student_id": user["_id"], "question_id": q["_id"], "concept_id": "c1",
                                   "correct": False, "context": "daily", "answered_at": scheduler.clock.now_utc()})
    out = c.get("/auth/me/wrong", headers=h).json()
    assert out and out[0]["public_id"] == q["public_id"] and out[0]["stem"]


def test_change_password(fresh_db):
    c = TestClient(app)
    user, h = _student(fresh_db, c)
    assert c.post("/auth/password", json={"current": "wrong-one-1", "new": "another-long-1"}, headers=h).status_code == 400
    assert c.post("/auth/password", json={"current": "long-enough-1", "new": "short"}, headers=h).status_code == 422
    r = c.post("/auth/password", json={"current": "long-enough-1", "new": "another-long-1"}, headers=h)
    assert r.status_code == 200
    assert c.get("/auth/me", headers=h).status_code == 401, "old token is dead after a password change"
    assert c.get("/auth/me", headers={"Authorization": "Bearer " + r.json()["access_token"]}).status_code == 200
    assert c.post("/auth/login", json={"username": "kian", "password": "another-long-1"}).status_code == 200


def _admin(fresh_db, c):
    fresh_db.users.insert_one({"username": "boss", "role": "admin", "password_hash": auth.hash_password("admin-pass-1")})
    return _login(c, "boss", "admin-pass-1")


def test_admin_overview_users_and_reset(fresh_db):
    c = TestClient(app)
    seed(fresh_db)
    user, sh = _student(fresh_db, c)
    ah = _admin(fresh_db, c)
    ov = c.get("/admin/overview", headers=ah).json()
    assert ov["users"]["students"] >= 1 and ov["content"]["key_points"] >= 1 and "learning" in ov
    assert c.get("/admin/overview", headers=sh).status_code == 403
    users = c.get("/admin/users", headers=ah).json()
    assert any(u["username"] == "kian" for u in users["items"])
    assert c.get("/admin/users?search=zzz", headers=ah).json()["total"] == 0
    r = c.post("/admin/users/kian/reset-password", headers=ah)
    temp = r.json()["temp_password"]
    assert c.get("/auth/me", headers=sh).status_code == 401
    assert c.post("/auth/login", json={"username": "kian", "password": temp}).status_code == 200
    assert c.post("/admin/users/boss/reset-password", headers=ah).status_code == 404, "admins are not reset here"
