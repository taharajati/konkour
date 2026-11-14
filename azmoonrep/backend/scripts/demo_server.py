"""Run the API on an in-memory database filled from the real bank: no MongoDB needed.
For trying the app locally and for UI checks. Everything is lost when it stops.

    python -m scripts.demo_server          # http://localhost:8000, then `npm run dev`

Logins: student `demo` / `demo-pass-123` (onboarded, grade 9 chapters 1-2),
        admin `admin` / `admin-pass-123`.
Questions the review found wrong stay rejected; every other mapped question is approved
so there is something to practise. This is a demo shortcut, not a review.
"""
import os

import mongomock
import uvicorn

os.environ.setdefault("JWT_SECRET", "demo-secret-" + "d" * 40)

from app import auth, clock, db  # noqa: E402

db.db = mongomock.MongoClient().azmoon_demo

from app import importer  # noqa: E402
from app.main import app  # noqa: E402
from scripts.import_data import BOOKS, QUESTIONS, TAXONOMY  # noqa: E402
from scripts.reset_review import KNOWN_WRONG  # noqa: E402


def seed():
    db.ensure_indexes()
    print("books:", importer.import_books(BOOKS))
    print("taxonomy:", importer.import_taxonomy(TAXONOMY))
    print("questions:", importer.import_questions(QUESTIONS))
    db.db.questions.update_many(
        {"public_id": {"$nin": list(KNOWN_WRONG)}, "concept_id": {"$ne": None},
         "answer.option": {"$ne": None}},
        {"$set": {"review_status": "approved", "reviewed": True}})
    db.db.questions.update_many({"public_id": {"$in": list(KNOWN_WRONG)}},
                                {"$set": {"review_status": "rejected"}})
    now = clock.now_utc()
    db.db.users.insert_many([
        {"username": "demo", "password_hash": auth.hash_password("demo-pass-123"),
         "role": "student", "display_name": "دانش‌آموز نمونه", "grade": 9, "onboarded": True,
         "scope_book_ids": ["G9_RIAZI"], "scope_chapter_ids": ["G9_RIAZI_ch1", "G9_RIAZI_ch2"],
         "daily_load": 10, "created_at": now},
        {"username": "admin", "password_hash": auth.hash_password("admin-pass-123"),
         "role": "admin", "display_name": "مدیر", "created_at": now},
    ])
    print("approved questions:", db.db.questions.count_documents({"review_status": "approved"}))


if __name__ == "__main__":
    seed()
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")), access_log=False)
