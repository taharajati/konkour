"""Phase 6: generation export, written (tashrihi) questions, pilot report."""
import csv
import io

from fastapi.testclient import TestClient

from app import auth, scheduler
from app.main import app
from conftest import seed


def _admin_client(mem):
    mem.users.insert_one({"username": "boss", "role": "admin",
                          "password_hash": auth.hash_password("admin-pass-123")})
    c = TestClient(app)
    tok = c.post("/auth/login", json={"username": "boss", "password": "admin-pass-123"}).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    return c


def test_generation_export_lists_short_key_points(fresh_db):
    seed(fresh_db)                         # 3 approved + 1 pending per concept
    c = _admin_client(fresh_db)
    data = c.get("/admin/generation/export?min_approved=5&max_examples=2").json()
    item = next(i for i in data["items"] if i["concept_id"] == "c1")
    assert item["need"] == 1               # 5 - 3 approved - 1 pending
    assert len(item["examples"]) == 2 and item["examples"][0]["answer_option"] == 3
    assert c.get("/admin/generation/export?min_approved=4").json()["items"] == []


def _written(mem, concept="c1"):
    mem.questions.insert_one({"public_id": "w1", "concept_id": concept, "type": "tashrihi",
                              "stem_md": "ثابت کنید ...", "options": None, "answer": {},
                              "solution_md": "حل کامل", "review_status": "approved",
                              "difficulty": 3})


def test_written_question_self_graded(fresh_db):
    seed(fresh_db, per_concept=0, extra_pending=False)
    _written(fresh_db)
    c = TestClient(app)
    c.post("/auth/register", json={"username": "ali", "password": "long-enough-1"})
    tok = c.post("/auth/login", json={"username": "ali", "password": "long-enough-1"}).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    q = c.post("/sessions/daily", json={}).json()
    assert q["total"] == 1
    item = c.get("/sessions/daily/question/0").json()
    assert item["type"] == "tashrihi" and item["options"] is None
    sol = c.get("/sessions/daily/solution/0")
    assert sol.status_code == 200 and sol.json()["solution_md"] == "حل کامل"
    r = c.post("/sessions/daily/answer/0", json={"selected_option": True, "time_ms": 60000})
    assert r.status_code == 200 and r.json()["correct"] is True


def test_mcq_solution_not_revealed_before_answer(fresh_db):
    seed(fresh_db)
    c = TestClient(app)
    c.post("/auth/register", json={"username": "ali", "password": "long-enough-1"})
    tok = c.post("/auth/login", json={"username": "ali", "password": "long-enough-1"}).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    c.post("/sessions/daily", json={})
    assert c.get("/sessions/daily/solution/0").status_code == 403


def test_placement_skips_written_questions(fresh_db):
    student = seed(fresh_db, per_concept=0, extra_pending=False)
    _written(fresh_db)
    assert scheduler.build_placement_session(student, "B_ch1") is None


def test_pilot_report_csv(fresh_db):
    student = seed(fresh_db)
    fresh_db.users.update_one({"_id": student["_id"]}, {"$set": {"username": "09121234567"}})
    s = scheduler.build_daily_queue(student, load=2)
    slot = s["slots"][0]
    q = fresh_db.questions.find_one({"_id": slot["question_id"]})
    scheduler.answer_slot(student, s, 0, scheduler.to_display(3, slot["perm"]), 1000)
    c = _admin_client(fresh_db)
    r = c.get("/admin/pilot-report.csv")
    assert r.status_code == 200 and r.text.startswith("﻿")
    rows = list(csv.DictReader(io.StringIO(r.text.lstrip("﻿"))))
    assert len(rows) == 1
    assert rows[0]["student"] == "0912***67", "phone numbers are masked"
    assert rows[0]["daily_answers"] == "1" and rows[0]["accuracy"] == "1.0"
