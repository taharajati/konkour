"""Try before signing up: three real questions on the landing page, no account.

Stateless: the questions and their option order travel in a signed token, so nothing is
stored for anonymous visitors. After sign-up, /trial/claim re-grades the answers, gives
credit for the key points answered correctly, and sets the default study plan.
"""
import datetime as dt
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import auth, clock, db, ratelimit, scheduler
from ..config import DEFAULT_DAILY_LOAD, JWT_SECRET
from ..logging_setup import client_ip

router = APIRouter(prefix="/trial", tags=["trial"])
N_QUESTIONS = 3
DAILY_LOADS = (10, 20, 40)


def _read(token: str) -> dict:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(400, "این آزمون آزمایشی منقضی شده؛ صفحه را تازه کن.")
    if data.get("typ") != "trial":
        raise HTTPException(400, "invalid trial token")
    return data


def _servable_concepts(grade: int | None, book_ids: list | None = None) -> list:
    q = {"source": "taxonomy", "retired": {"$ne": True}}
    if book_ids:
        q["book_id"] = {"$in": book_ids}
    elif grade:
        q["grade"] = grade
    out = []
    for c in db.db.concepts.find(q).sort("order_in_curriculum", 1):
        qs = [x for x in db.db.questions.find({"concept_id": c["concept_id"], **scheduler.SERVABLE,
                                               "type": "multiple_choice_4"})
              if scheduler._has_key(x) and not x.get("figures") and not x.get("option_figures")]
        if qs:
            qs.sort(key=lambda x: x.get("difficulty", 3))
            out.append((c, qs[0]))
    return out


class StartBody(BaseModel):
    grade: int | None = None
    book_ids: list[str] = Field(default=[], max_length=8)

@router.post("/start")
def start(body: StartBody, request: Request):
    ratelimit.hit("trial-ip", client_ip(request), limit=60, window=3600)
    # the student chose books: only their questions (never fall back to another grade's)
    pool = _servable_concepts(body.grade, body.book_ids) if body.book_ids \
        else (_servable_concepts(body.grade) or _servable_concepts(None))
    if not pool:
        raise HTTPException(404, "no approved questions yet")
    # spread over the curriculum: first, middle, last
    n = min(N_QUESTIONS, len(pool))
    idx = sorted({round(i * (len(pool) - 1) / max(1, n - 1)) for i in range(n)})
    picked = [pool[i] for i in idx]
    perms = [scheduler.make_perm(q) for _, q in picked]
    grade = picked[0][0].get("grade")
    token = jwt.encode({"typ": "trial", "q": [q["public_id"] for _, q in picked], "p": perms,
                        "g": grade, "exp": int(time.time()) + 6 * 3600}, JWT_SECRET, algorithm="HS256")
    return {"token": token, "grade": grade,
            "questions": [{"stem_md": q.get("stem_md"),
                           "options": scheduler.display_options(q, perm),
                           "concept_title": c["title"]}
                          for (c, q), perm in zip(picked, perms)]}


class AnswerBody(BaseModel):
    token: str = Field(max_length=4000)
    index: int
    selected_option: int

def _grade(data: dict, index: int, selected: int):
    if not 0 <= index < len(data["q"]):
        raise HTTPException(404, "no such question")
    q = db.db.questions.find_one({"public_id": data["q"][index]})
    if not q:
        raise HTTPException(404, "question missing")
    perm = data["p"][index]
    try:
        correct_opt, correct = scheduler.grade(q, scheduler.to_original(selected, perm))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return q, perm, correct_opt, correct

@router.post("/answer")
def answer(body: AnswerBody, request: Request):
    ratelimit.hit("trial-ip", client_ip(request), limit=60, window=3600)
    q, perm, correct_opt, correct = _grade(_read(body.token), body.index, body.selected_option)
    return {"correct": correct, "correct_option": scheduler.to_display(correct_opt, perm),
            "solution_md": scheduler.remap_solution(q.get("solution_md"), perm),
            "key_point": scheduler.key_point(q["concept_id"])}


def default_scope(grade: int | None, book_ids: list | None = None) -> dict:
    """the books the student chose (else all books of the grade); chapters that already have
    approved questions (all chapters, if none yet)"""
    if book_ids:
        books = list(db.db.books.find({"book_id": {"$in": book_ids}}))
    else:
        books = list(db.db.books.find({"grade": grade})) if grade else []
    if not books:
        return {"scope_book_ids": [], "scope_chapter_ids": []}
    book_ids = [b["book_id"] for b in books]
    ready = {c.get("chapter_id") for c, _ in _servable_concepts(grade, [b["book_id"] for b in books])}
    chapters = [ch["chapter_id"] for ch in db.db.chapters.find({"book_id": {"$in": book_ids}})]
    with_q = [c for c in chapters if c in ready]
    return {"scope_book_ids": book_ids, "scope_chapter_ids": with_q or chapters}


class ClaimBody(BaseModel):
    token: str | None = Field(default=None, max_length=4000)
    answers: list[int] = Field(default=[], max_length=10)
    grade: int | None = None
    book_ids: list[str] = Field(default=[], max_length=8)
    daily_load: int = DEFAULT_DAILY_LOAD
    display_name: str | None = Field(default=None, max_length=40)

@router.post("/claim")
def claim(body: ClaimBody, user: dict = Depends(auth.current_user)):
    """after sign-up: keep the trial answers and set the default plan (once)"""
    if user.get("role") != "student":
        raise HTTPException(403, "students only")
    credited = 0
    seen_today = []
    data = _read(body.token) if body.token else None
    if data and not user.get("trial_claimed"):
        for i, selected in enumerate(body.answers[:len(data["q"])]):
            q, _perm, _opt, correct = _grade(data, i, selected)
            seen_today.append(q["_id"])
            db.db.responses.insert_one({
                "student_id": user["_id"], "question_id": q["_id"], "concept_id": q["concept_id"],
                "correct": correct, "time_ms": 0, "context": "trial", "answered_at": clock.now_utc()})
            if correct:
                credited += scheduler.place(user["_id"], q["concept_id"], q["_id"], "learning")
    upd = {"trial_claimed": True}
    if seen_today:
        # today's first session must not open with the questions just answered on the landing page
        upd["trial_seen"] = {"day": clock.today_str(), "question_ids": seen_today}
    if body.display_name and body.display_name.strip():
        upd["display_name"] = body.display_name.strip()[:40]
    if not user.get("onboarded"):
        grade = body.grade or (data or {}).get("g")
        upd.update(default_scope(grade, body.book_ids))
        upd.update({"grade": grade, "onboarded": True,
                    "daily_load": body.daily_load if body.daily_load in DAILY_LOADS else DEFAULT_DAILY_LOAD})
        db.db.sessions.delete_many({"student_id": user["_id"], "date": clock.today_str()})
    db.db.users.update_one({"_id": user["_id"]}, {"$set": upd})
    return {"ok": True, "credited": credited}
