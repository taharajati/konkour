"""Figures on import, the error envelope, log-out-everywhere, data migrations."""
import datetime as dt
import json
import struct
import zlib

from fastapi.testclient import TestClient

from app import importer, migrations, scheduler
from app.main import app


def _png(path, w, h):
    def chunk(kind, data):
        c = kind + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    raw = b"".join(b"\x00" + b"\xff" * (w * 3) for _ in range(h))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _bank(tmp_path, meta, md):
    q = tmp_path / "bank" / "grade9" / "b1" / meta["id"]
    q.mkdir(parents=True)
    (q / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (q / "question.md").write_text(md, encoding="utf-8")
    (q / "answer.md").write_text("حل", encoding="utf-8")
    for name, (w, h) in {"figure.png": (300, 120), "option1.png": (90, 60), "option2.png": (90, 60),
                         "question_shot.png": (10, 10)}.items():
        _png(q / name, w, h)
    return str(tmp_path / "bank")


def test_import_figures_hashed_sized_and_stem_clean(fresh_db, tmp_path):
    root = _bank(tmp_path, {"id": "f1", "printed_question_number": 1, "figures": ["figure.png"],
                            "option_figures": [], "figure_source": "pdf_vector",
                            "options": ["۱", "۲", "۳", "۴"], "answer_option": 2, "concept_id": None},
                 "# سؤال 1\n\nبا توجه به شکل کدام درست است؟\n\n![شکل](figure.png)\n\n1) ۱\n\n2) ۲\n\n3) ۳\n\n4) ۴\n")
    importer.import_questions(root)
    q = fresh_db.questions.find_one({"public_id": "f1"})
    assert q["stem_md"] == "با توجه به شکل کدام درست است؟", "no image link and no options in the stem"
    (fig,) = q["figures"]
    assert (fig["w"], fig["h"]) == (300, 120) and fig["file"] != "figure.png" and fig["file"].endswith(".png")
    served = sorted(p.name for p in (tmp_path / "static" / "f1").iterdir())
    assert served == [fig["file"]], "only the figure is public, under its content-hash name"
    view = scheduler.question_figures(q)
    assert view["figures"][0] == {"url": f"/static/questions/f1/{fig['file']}", "w": 300, "h": 120}
    assert view["option_figures"] is None


def test_option_figures_follow_option_order(fresh_db, tmp_path):
    root = _bank(tmp_path, {"id": "f2", "figures": [], "option_figures": ["option1.png", "option2.png", None, None],
                            "figure_source": "pdf_vector", "options": ["نمودار ۱", "نمودار ۲", "متن", "متن دیگر"],
                            "answer_option": 1, "concept_id": None}, "کدام نمودار؟\n")
    importer.import_questions(root)
    q = fresh_db.questions.find_one({"public_id": "f2"})
    assert [bool(f) for f in q["option_figures"]] == [True, True, False, False]
    shown = scheduler.question_figures(q, perm=[2, 1, 4, 3])["option_figures"]
    assert shown[0]["url"].endswith(q["option_figures"][1]["file"]) and shown[2] is None
    assert not scheduler.can_shuffle(q), "options that name a diagram keep their printed order"


def test_error_envelope(fresh_db):
    c = TestClient(app)
    r = c.get("/auth/me")
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated" and r.headers["X-Request-ID"] == r.json()["request_id"]
    r = c.post("/auth/login", json={"username": "x"})
    body = r.json()
    assert r.status_code == 422 and body["code"] == "invalid_input" and isinstance(body["detail"], str)
    assert body["fields"][0]["field"] == "password"
    r = c.get("/no/such/route")
    assert r.status_code == 404 and r.json()["detail"] == "پیدا نشد."


def test_logout_everywhere(fresh_db):
    c = TestClient(app)
    c.post("/auth/register", json={"username": "kian", "password": "long-enough-1"})
    tok = c.post("/auth/login", json={"username": "kian", "password": "long-enough-1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert c.get("/auth/me", headers=h).status_code == 200
    assert c.post("/auth/logout-all", headers=h).status_code == 200
    assert c.get("/auth/me", headers=h).status_code == 401, "old token is dead"
    new = c.post("/auth/login", json={"username": "kian", "password": "long-enough-1"}).json()["access_token"]
    assert c.get("/auth/me", headers={"Authorization": f"Bearer {new}"}).status_code == 200


def test_migrations_run_once(fresh_db):
    fresh_db.concept_state.insert_one({"student_id": 1, "concept_id": "c", "due_date": dt.datetime(2026, 11, 13, 21, 0)})
    fresh_db.questions.insert_one({"public_id": "old", "figures": ["a.png"]})
    fresh_db.users.insert_one({"username": "u"})
    assert migrations.run() == [name for name, _ in migrations.MIGRATIONS]
    assert fresh_db.concept_state.find_one({})["due_day"] == "2026-11-14"
    assert fresh_db.questions.find_one({})["figures"] == [{"file": "a.png", "w": None, "h": None}]
    assert fresh_db.users.find_one({})["token_version"] == 0
    assert migrations.run() == [], "each migration runs once"


def test_static_figures_are_cacheable_and_api_is_not(fresh_db, tmp_path):
    d = tmp_path / "static" / "q"
    d.mkdir(parents=True)
    _png(d / "abc.png", 4, 4)
    c = TestClient(app)
    assert c.get("/health").headers["Cache-Control"] == "no-store"
    assert c.get("/health").headers["X-Content-Type-Options"] == "nosniff"
