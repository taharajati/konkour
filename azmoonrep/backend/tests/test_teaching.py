"""Phase 3: key-point cards, re-teaching after a miss, placement test, learning metrics."""
from fastapi.testclient import TestClient

from app import scheduler
from app.main import app
from app.routers.admin import learning_metrics
from conftest import seed, set_day


def _add_key_points(mem):
    for cid in ("c1", "c2", "c3", "c4"):
        mem.concepts.update_one({"concept_id": cid},
                                {"$set": {"key_point": f"نکتهٔ {cid}: $a+b$"}})


def _login(client):
    client.post("/auth/register", json={"username": "ali", "password": "secret-pass-1"})
    tok = client.post("/auth/login", json={"username": "ali", "password": "secret-pass-1"}).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {tok}"


def _right(mem, slot):
    q = mem.questions.find_one({"_id": slot["question_id"]})
    return scheduler.to_display(q["answer"]["option"], slot.get("perm"))


# ------------------------------------------------------------------ key-point card

def test_key_point_card_only_on_first_meeting(fresh_db):
    seed(fresh_db); _add_key_points(fresh_db)
    client = TestClient(app); _login(client)
    q = client.post("/sessions/daily", json={}).json()
    idx = q["slots"][0]["index"]
    item = client.get(f"/sessions/daily/question/{idx}").json()
    assert item["kind"] == "new" and item["key_point"]["text"].startswith("نکتهٔ")
    s = fresh_db.sessions.find_one({})
    client.post(f"/sessions/daily/answer/{idx}", json={"selected_option": _right(fresh_db, s["slots"][idx]), "time_ms": 3000})
    # a second slot of a concept the student has now met carries no card
    fresh_db.sessions.update_one({"_id": s["_id"]}, {"$push": {"slots": {
        **s["slots"][idx], "status": "pending", "question_id": s["slots"][idx]["question_id"]}}})
    later = client.get(f"/sessions/daily/question/{len(s['slots'])}").json()
    assert "key_point" not in later


def test_miss_reteaches_the_key_point(fresh_db):
    student = seed(fresh_db); _add_key_points(fresh_db)
    s = scheduler.build_daily_queue(student, load=1)
    slot = s["slots"][0]
    wrong = (_right(fresh_db, slot) % 4) + 1
    out = scheduler.answer_slot(student, s, 0, wrong, 2000)
    assert not out["correct"] and out["key_point"]["title"] == slot["concept_id"]


# ------------------------------------------------------------------ placement

def test_placement_one_hard_question_per_untouched_point(fresh_db):
    student = seed(fresh_db)
    fresh_db.questions.update_one({"public_id": "c1_q2"}, {"$set": {"difficulty": 4}})
    scheduler.update_concept_state(student["_id"], "c4", True, 1000, 40000)   # already started
    p = scheduler.build_placement_session(student, "B_ch1")
    cids = [sl["concept_id"] for sl in p["slots"]]
    assert cids == ["c1", "c2", "c3"], "curriculum order, untouched points only"
    first = fresh_db.questions.find_one({"_id": p["slots"][0]["question_id"]})
    assert first["public_id"] == "c1_q2", "the hardest approved question gives the most evidence"


def test_placement_credit_and_no_penalty(fresh_db):
    student = seed(fresh_db)
    fresh_db.questions.update_many({"concept_id": "c1"}, {"$set": {"difficulty": 4}})
    p = scheduler.build_placement_session(student, "B_ch1")
    get = lambda: fresh_db.placement_sessions.find_one({})
    # c1: hard question right and quick -> placed as learned, still confirmed after 3 days
    out = scheduler.answer_placement_slot(student, get(), 0, _right(fresh_db, p["slots"][0]), 5000)
    assert out["placed"] == "learned"
    st = fresh_db.concept_state.find_one({"concept_id": "c1"})
    assert st["streak"] == 2 and st["mastery_level"] == 1 and st["due_day"] == "2026-11-17", "3-day confirmation first"
    assert "answers_to_learned" not in st, "placement credit is not counted as taught"
    # c2: medium question right -> learning, back in 3 days
    out = scheduler.answer_placement_slot(student, get(), 1, _right(fresh_db, p["slots"][1]), 5000)
    assert out["placed"] == "learning"
    assert fresh_db.concept_state.find_one({"concept_id": "c2"})["due_day"] == "2026-11-17"
    # c3: «نمی‌دانم» -> nothing recorded in the schedule, taught normally later
    out = scheduler.answer_placement_slot(student, get(), 2, 0, 5000)
    assert out["placed"] is None and out["correct"] is False
    assert fresh_db.concept_state.find_one({"concept_id": "c3"}) is None
    # today's queue then starts c3 (and c4) as new, not c1/c2
    s = scheduler.build_daily_queue(student, load=20)
    assert {sl["concept_id"] for sl in s["slots"]} == {"c3", "c4"}
    # a week later c1 comes back for its check
    set_day(7)
    fresh_db.sessions.delete_many({})
    s = scheduler.build_daily_queue(student, load=20)
    assert any(sl["concept_id"] == "c1" and sl["kind"] == "review" for sl in s["slots"])


def test_placement_over_http(fresh_db):
    seed(fresh_db)
    client = TestClient(app); _login(client)
    r = client.post("/sessions/placement", json={"chapter_id": "B_ch1"})
    assert r.status_code == 200 and r.json()["total"] == 4
    item = client.get("/sessions/placement/question/0").json()
    assert "answer" not in item and item["kind"] == "placement"
    a = client.post("/sessions/placement/answer/0", json={"selected_option": 0, "time_ms": 1000})
    assert a.status_code == 200 and a.json()["placed"] is None
    assert client.post("/sessions/placement/answer/0", json={"selected_option": 0, "time_ms": 1000}).status_code == 409
    chapters = client.get("/curriculum/books/B/chapters").json()
    assert chapters == [] or chapters[0]["placement_available"] >= 0


# ------------------------------------------------------------------ metrics

def test_questions_to_learn_metric(fresh_db):
    sid = "stu"
    up = scheduler.update_concept_state
    for day, ok in ((0, True), (1, False), (2, True), (3, True), (6, True)):
        set_day(day)
        up(sid, "m1", ok, 1000, 40000, scheduled=True)
    st = fresh_db.concept_state.find_one({"concept_id": "m1"})
    assert st["mastery_level"] >= 2 and st["answers_to_first_pass"] == 5
    assert "answers_to_learned" not in st, "the 7-day gap has not been survived yet"
    set_day(13)                                            # correct after the 7-day gap
    up(sid, "m1", True, 1000, 40000, scheduled=True)
    st = fresh_db.concept_state.find_one({"concept_id": "m1"})
    assert st["answers_to_learned"] == 6
    m = learning_metrics()
    assert m["key_points_learned"] == 1 and m["median_questions_to_learn"] == 6
