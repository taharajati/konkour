"""Try-before-signup: stateless trial, then claim into a new account."""
from fastapi.testclient import TestClient

from app import scheduler
from app.main import app
from conftest import seed


def _prep(mem):
    seed(mem)
    mem.books.insert_one({"book_id": "B", "name": "کتاب", "grade": 9})
    mem.chapters.insert_one({"chapter_id": "B_ch1", "book_id": "B", "number": 1, "title": "فصل"})
    mem.chapters.insert_one({"chapter_id": "B_ch2", "book_id": "B", "number": 2, "title": "خالی"})
    mem.concepts.update_many({}, {"$set": {"grade": 9, "key_point": "نکته"}})


def test_trial_then_claim(fresh_db):
    _prep(fresh_db)
    c = TestClient(app)
    t = c.post("/trial/start", json={}).json()
    assert len(t["questions"]) == 3 and t["grade"] == 9
    assert all("answer" not in q and len(q["options"]) == 4 for q in t["questions"])
    # the right display option for question 0, worked out from the DB like the server does
    import jwt
    from app.config import JWT_SECRET
    data = jwt.decode(t["token"], JWT_SECRET, algorithms=["HS256"])
    right = [scheduler.to_display(3, p) for p in data["p"]]
    fb = c.post("/trial/answer", json={"token": t["token"], "index": 0, "selected_option": right[0]}).json()
    assert fb["correct"] and fb["key_point"]["text"] == "نکته"
    wrong = (right[1] % 4) + 1
    assert c.post("/trial/answer", json={"token": t["token"], "index": 1, "selected_option": wrong}).json()["correct"] is False
    assert fresh_db.responses.count_documents({}) == 0, "nothing is stored for anonymous visitors"

    c.post("/auth/register", json={"username": "neda", "password": "long-enough-1"})
    tok = c.post("/auth/login", json={"username": "neda", "password": "long-enough-1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/trial/claim", headers=h, json={"token": t["token"], "answers": [right[0], wrong, 0],
                                                "daily_load": 10, "display_name": "ندا"}).json()
    assert r["credited"] == 1
    me = c.get("/auth/me", headers=h).json()
    assert me["onboarded"] and me["daily_load"] == 10 and me["display_name"] == "ندا"
    assert me["scope_book_ids"] == ["B"] and me["scope_chapter_ids"] == ["B_ch1"], "only chapters with questions"
    st = fresh_db.concept_state.find_one({"concept_id": data and fresh_db.questions.find_one({"public_id": data["q"][0]})["concept_id"]})
    assert st["placed"] == "learning" and st["due_day"] == "2026-11-17"
    # claiming twice gives no second credit
    again = c.post("/trial/claim", headers=h, json={"token": t["token"], "answers": [right[0]]}).json()
    assert again["credited"] == 0
    plan = c.post("/sessions/daily", headers=h, json={}).json()
    assert plan["total"] > 0 and plan["focus"]["chapter_id"] == "B_ch1"
    trial_ids = {fresh_db.questions.find_one({"public_id": p})["_id"] for p in data["q"]}
    today_ids = {sl["question_id"] for sl in fresh_db.sessions.find_one({})["slots"]}
    assert not trial_ids & today_ids, "the first session must not repeat the landing questions"


def test_trial_unavailable_without_approved_questions(fresh_db):
    c = TestClient(app)
    assert c.post("/trial/start", json={}).status_code == 404


def test_claim_without_trial_sets_default_plan(fresh_db):
    _prep(fresh_db)
    c = TestClient(app)
    c.post("/auth/register", json={"username": "omid", "password": "long-enough-1"})
    tok = c.post("/auth/login", json={"username": "omid", "password": "long-enough-1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert c.post("/trial/claim", headers=h, json={"grade": 9}).status_code == 200
    me = c.get("/auth/me", headers=h).json()
    assert me["onboarded"] and me["daily_load"] == 20 and me["scope_book_ids"] == ["B"]


def test_catalog_and_book_choice(fresh_db):
    _prep(fresh_db)
    fresh_db.concepts.update_many({}, {"$set": {"book_id": "B"}})
    c = TestClient(app)
    cat = c.get("/curriculum/catalog").json()                  # public: no login
    book = cat["grades"][0]["books"][0]
    assert cat["grades"][0]["grade"] == 9 and book["book_id"] == "B"
    assert book["key_points"] >= 1 and book["ready_key_points"] >= 1 and book["chapters"] == 2
    # a chosen book with no approved questions must not fall back to another book's questions
    fresh_db.books.insert_one({"book_id": "Z", "name": "خالی", "grade": 10})
    assert c.post("/trial/start", json={"grade": 10, "book_ids": ["Z"]}).status_code == 404
    t = c.post("/trial/start", json={"grade": 9, "book_ids": ["B"]})
    assert t.status_code == 200 and len(t.json()["questions"]) == 3
    # the account's plan follows the chosen books
    c.post("/auth/register", json={"username": "kian", "password": "long-enough-1"})
    tok = c.post("/auth/login", json={"username": "kian", "password": "long-enough-1"}).json()["access_token"]
    h = {"Authorization": "Bearer " + tok}
    assert c.post("/trial/claim", headers=h, json={"grade": 10, "book_ids": ["Z"]}).status_code == 200
    me = c.get("/auth/me", headers=h).json()
    assert me["scope_book_ids"] == ["Z"]
