"""End-to-end through the HTTP API (FastAPI TestClient + in-memory Mongo)."""
from fastapi.testclient import TestClient

from app import scheduler
from app.main import app
from conftest import seed


def _client_for(mem):
    client = TestClient(app)
    r = client.post("/auth/register", json={"username": "ali", "password": "secret-pass-1"})
    assert r.status_code == 200, r.text
    token = client.post("/auth/login",
                        json={"username": "ali", "password": "secret-pass-1"}).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def test_daily_flow_over_http(fresh_db):
    seed(fresh_db)
    with TestClient(app) as _:
        pass
    client = _client_for(fresh_db)
    q = client.post("/sessions/daily", json={})
    assert q.status_code == 200, q.text
    first = next(sl for sl in q.json()["slots"] if sl["status"] == "pending")
    item = client.get(f"/sessions/daily/question/{first['index']}").json()
    assert "answer" not in item and "solution_md" not in item, "answer leaked before submit"
    # find the right display option the way only the server can
    s = fresh_db.sessions.find_one({})
    slot = s["slots"][first["index"]]
    real = fresh_db.questions.find_one({"_id": slot["question_id"]})
    right = scheduler.to_display(real["answer"]["option"], slot["perm"])
    assert item["options"][right - 1] == real["options"][real["answer"]["option"] - 1]
    r = client.post(f"/sessions/daily/answer/{first['index']}", json={"selected_option": right, "time_ms": 4000})
    assert r.status_code == 200 and r.json()["correct"] is True
    again = client.post(f"/sessions/daily/answer/{first['index']}", json={"selected_option": right, "time_ms": 4000})
    assert again.status_code == 409
    assert client.get("/sessions/daily/question/-1").status_code == 404


def test_static_mount_has_no_answer_keys(fresh_db, tmp_path):
    from app import importer
    d = tmp_path / "static" / "q1"
    d.mkdir(parents=True)
    for name in ("meta.json", "answer.md", "question_shot.png", "fig.png"):
        (d / name).write_text("x")
    removed = importer.purge_private_static_files()
    assert removed == 3 and sorted(p.name for p in d.iterdir()) == ["fig.png"]
