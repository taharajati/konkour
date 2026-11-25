import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .. import db, auth, clock, ratelimit, scheduler
from bson import ObjectId

router = APIRouter(prefix="/sessions", tags=["sessions"])

def public_question(q: dict, perm: list | None = None) -> dict:
    """what the student sees: options in this slot's shuffled order, no answer"""
    cid = q.get("concept_id")
    c = db.db.concepts.find_one({"concept_id": cid},
                                {"title": 1, "chapter_title": 1, "book_name": 1}) if cid else None
    src = q.get("source_meta") or (q.get("source") if isinstance(q.get("source"), dict) else None)
    return {
        "question_id": q.get("public_id") or str(q["_id"]),
        "stem_md": q.get("stem_md"),
        "options": scheduler.display_options(q, perm),
        "type": q.get("type", "multiple_choice_4"),
        "difficulty": scheduler.effective_difficulty(q),
        **scheduler.question_figures(q, perm),
        "concept_id": cid,
        "concept_title": (c or {}).get("title"),
        "chapter_title": (c or {}).get("chapter_title"),
        "book_name": (c or {}).get("book_name"),
        "exam_source": (src or {}).get("exam_label"),
    }

def _fix(s):
    return str(s) if isinstance(s, ObjectId) else s

class DailyBody(BaseModel):
    book_id: str | None = None
    chapter_id: str | None = None

@router.post("/daily")
def daily(body: DailyBody | None = None, user: dict = Depends(auth.current_user)):
    if user.get("role") != "student":
        raise HTTPException(403, "students only")
    book_id = body.book_id if body else None
    chapter_id = body.chapter_id if body else None
    s = scheduler.build_daily_queue(user, book_id=book_id, chapter_id=chapter_id)
    concepts = {c["concept_id"]: c for c in db.db.concepts.find(
        {"concept_id": {"$in": [sl["concept_id"] for sl in s["slots"]]}})}
    plan = scheduler.plan_summary(user, s)
    missed = set(plan["missed_yesterday"])
    slots = [{"index": i, "kind": sl["kind"], "status": sl["status"],
              "correct": sl.get("correct"), "concept_id": sl["concept_id"],
              "missed_yesterday": sl["concept_id"] in missed,
              "concept_title": concepts.get(sl["concept_id"], {}).get("title", sl["concept_id"]),
              "chapter_title": concepts.get(sl["concept_id"], {}).get("chapter_title"),
              "book_name": concepts.get(sl["concept_id"], {}).get("book_name")}
             for i, sl in enumerate(s["slots"])]
    done = sum(1 for sl in s["slots"] if sl["status"] == "answered")
    return {"date": s["date"], "book_id": s.get("book_id"),
            "chapter_id": s.get("chapter_id"), "total": len(s["slots"]),
            "done": done, "slots": slots,
            "concepts": sorted(concepts.keys()), **plan}

@router.get("/daily")
def daily_get(book_id: str | None = None, chapter_id: str | None = None,
              user: dict = Depends(auth.current_user)):
    return daily(DailyBody(book_id=book_id, chapter_id=chapter_id), user)

@router.get("/daily/question/{index}")
def slot_question(index: int, book_id: str | None = None, chapter_id: str | None = None,
                  user: dict = Depends(auth.current_user)):
    s = _find_daily(user["_id"], book_id, chapter_id)
    if not s or not 0 <= index < len(s["slots"]):
        raise HTTPException(404, "no such slot")
    slot = s["slots"][index]
    if slot["status"] != "pending":
        raise HTTPException(409, "already answered")
    q = db.db.questions.find_one({"_id": slot["question_id"]})
    if not q:
        raise HTTPException(404, "question missing")
    out = public_question(q, slot.get("perm"))
    out["index"] = index
    out["kind"] = slot["kind"]
    if slot.get("repeat"):
        out["repeat"] = True
    # first meeting with a key point: teach it before testing it
    if slot["kind"] == "new" and not db.db.concept_state.find_one(
            {"student_id": user["_id"], "concept_id": slot["concept_id"]}, {"_id": 1}):
        out["key_point"] = scheduler.key_point(slot["concept_id"])
    return out

class AnswerBody(BaseModel):
    selected_option: int | bool
    time_ms: int = 30_000
    confidence: str | None = None   # "sure" | "unsure" | None (placement, legacy clients)

@router.post("/daily/answer/{index}")
def slot_answer(index: int, body: AnswerBody, book_id: str | None = None,
                chapter_id: str | None = None,
                user: dict = Depends(auth.current_user)):
    s = _find_daily(user["_id"], book_id, chapter_id)
    if not s:
        raise HTTPException(404, "no session — POST /sessions/daily first")
    try:
        result = scheduler.answer_slot(user, s, index, body.selected_option, body.time_ms,
                                       confidence=body.confidence)
    except ValueError as e:
        raise HTTPException(409, str(e))
    s = db.db.sessions.find_one({"_id": s["_id"]})
    result["done"] = sum(1 for sl in s["slots"] if sl["status"] == "answered")
    result["total"] = len(s["slots"])
    return result

def _find_daily(student_id, book_id, chapter_id=None):
    return db.db.sessions.find_one(
        {"student_id": student_id, "date": clock.today_str(),
         "book_id": book_id, "chapter_id": chapter_id})

# ---------- written (tashrihi) questions: see the solution, then grade yourself ----------

@router.get("/{mode}/solution/{index}")
def written_solution(mode: str, index: int, book_id: str | None = None,
                     chapter_id: str | None = None, user: dict = Depends(auth.current_user)):
    """the worked solution of a pending WRITTEN question, so the student can compare their
    own work and then answer «درست حل کردم» / «اشتباه بود». Never for multiple choice."""
    if mode == "daily":
        s = _find_daily(user["_id"], book_id, chapter_id)
    elif mode == "practice":
        s = scheduler.get_practice_session(user["_id"])
    else:
        raise HTTPException(404, "no such mode")
    if not s or not 0 <= index < len(s["slots"]):
        raise HTTPException(404, "no such slot")
    slot = s["slots"][index]
    if slot["status"] != "pending":
        raise HTTPException(409, "already answered")
    q = db.db.questions.find_one({"_id": slot["question_id"]})
    if not q:
        raise HTTPException(404, "question missing")
    if q.get("type", "multiple_choice_4") == "multiple_choice_4":
        raise HTTPException(403, "solutions of multiple-choice questions come after answering")
    return {"solution_md": q.get("solution_md") or "حل این سؤال هنوز ثبت نشده است."}

# ---------- placement test (one question per untouched key point of a chapter) ----------

class PlacementBody(BaseModel):
    chapter_id: str

@router.post("/placement")
def start_placement(body: PlacementBody, user: dict = Depends(auth.current_user)):
    s = scheduler.build_placement_session(user, body.chapter_id)
    if not s:
        raise HTTPException(404, "no untouched key points with approved questions in this chapter")
    return _slot_list(s)

@router.get("/placement")
def placement_status(user: dict = Depends(auth.current_user)):
    s = scheduler.get_placement_session(user["_id"])
    if not s:
        raise HTTPException(404, "no placement test")
    return _slot_list(s)

@router.get("/placement/question/{index}")
def placement_question(index: int, user: dict = Depends(auth.current_user)):
    s = scheduler.get_placement_session(user["_id"])
    if not s or not 0 <= index < len(s["slots"]):
        raise HTTPException(404, "no placement test")
    slot = s["slots"][index]
    if slot["status"] != "pending":
        raise HTTPException(409, "already answered")
    q = db.db.questions.find_one({"_id": slot["question_id"]})
    if not q:
        raise HTTPException(404, "question missing")
    out = public_question(q, slot.get("perm"))
    out.update({"index": index, "kind": "placement"})
    return out

@router.post("/placement/answer/{index}")
def placement_answer(index: int, body: AnswerBody, user: dict = Depends(auth.current_user)):
    s = scheduler.get_placement_session(user["_id"])
    if not s:
        raise HTTPException(404, "no placement test")
    try:
        return scheduler.answer_placement_slot(user, s, index, body.selected_option, body.time_ms)
    except ValueError as e:
        raise HTTPException(409, str(e))

def _slot_list(s):
    return {"total": len(s["slots"]),
            "done": sum(1 for sl in s["slots"] if sl["status"] == "answered"),
            "slots": [{"index": i, "status": sl["status"], "kind": sl.get("kind"),
                       "correct": sl.get("correct"), "placed": sl.get("placed")}
                      for i, sl in enumerate(s["slots"])]}

# ---------- practice (student-picked topics) ----------

class PracticeBody(BaseModel):
    concept_ids: list[str] = []
    chapter_ids: list[str] = []
    book_ids: list[str] = []
    question_ids: list[str] = []
    wrong_only: bool = False
    count: int = 10

@router.post("/practice")
def start_practice(body: PracticeBody, user: dict = Depends(auth.current_user)):
    concept_ids = list(body.concept_ids)
    if body.chapter_ids:
        for c in db.db.concepts.find({"chapter_id": {"$in": body.chapter_ids}}):
            concept_ids.append(c["concept_id"])
    if body.book_ids:
        for c in db.db.concepts.find({"book_id": {"$in": body.book_ids}}):
            concept_ids.append(c["concept_id"])
    s = scheduler.build_practice_session(user["_id"], list(set(concept_ids)), body.count,
                                         question_ids=body.question_ids,
                                         wrong_only=body.wrong_only)
    if not s:
        raise HTTPException(404, "no questions for the selected topics")
    return {"total": len(s["slots"]), "slots": [
        {"index": i, "status": sl["status"]} for i, sl in enumerate(s["slots"])]}

@router.get("/practice")
def practice_status(user: dict = Depends(auth.current_user)):
    s = scheduler.get_practice_session(user["_id"])
    if not s:
        raise HTTPException(404, "no practice session")
    # never return raw slots: they hold ObjectIds (not JSON-serializable) and question ids
    return {"total": len(s["slots"]),
            "done": sum(1 for sl in s["slots"] if sl["status"] == "answered"),
            "slots": [{"index": i, "status": sl["status"], "kind": sl.get("kind", "practice"),
                       "correct": sl.get("correct")}
                      for i, sl in enumerate(s["slots"])]}

@router.get("/practice/question/{index}")
def practice_question(index: int, user: dict = Depends(auth.current_user)):
    s = scheduler.get_practice_session(user["_id"])
    if not s or not 0 <= index < len(s["slots"]):
        raise HTTPException(404, "no practice session")
    slot = s["slots"][index]
    if slot["status"] != "pending":
        raise HTTPException(409, "already answered")
    q = db.db.questions.find_one({"_id": slot["question_id"]})
    if not q:
        raise HTTPException(404, "question missing")
    out = public_question(q, slot.get("perm"))
    out["index"] = index
    out["kind"] = "practice"
    return out

@router.post("/practice/answer/{index}")
def practice_answer(index: int, body: AnswerBody, user: dict = Depends(auth.current_user)):
    s = scheduler.get_practice_session(user["_id"])
    if not s:
        raise HTTPException(404, "no practice session")
    try:
        return scheduler.answer_practice_slot(user, s, index, body.selected_option, body.time_ms)
    except ValueError as e:
        raise HTTPException(409, str(e))

@router.delete("/practice")
def drop_practice(user: dict = Depends(auth.current_user)):
    db.db.practice_sessions.delete_many({"student_id": user["_id"]})
    return {"ok": True}

class ReportBody(BaseModel):
    note: str

@router.post("/questions/{question_id}/report")
def report_question(question_id: str, body: ReportBody,
                    user: dict = Depends(auth.current_user)):
    q = db.db.questions.find_one({"public_id": question_id})
    if not q:
        raise HTTPException(404, "question not found")
    note = body.note.strip()[:1000]
    if not note:
        raise HTTPException(422, "متن گزارش خالی است.")
    ratelimit.hit("report-user", str(user["_id"]), limit=10, window=3600)
    if db.db.reports.find_one({"question_public_id": question_id, "student_id": user["_id"],
                               "status": "open"}):
        return {"ok": True, "message": "گزارش قبلی‌ات دربارهٔ این سؤال هنوز در حال بررسی است."}
    db.db.reports.insert_one({
        "question_public_id": question_id, "student_id": user["_id"],
        "student_name": user.get("display_name") or user["username"],
        "note": note, "status": "open",
        "created_at": clock.now_utc()})
    return {"ok": True, "message": "گزارش شما ثبت شد. ممنون!"}

# ---------- summary ----------

@router.get("/summary/{date}")
def summary(date: str, user: dict = Depends(auth.current_user)):
    s = db.db.sessions.find_one({"student_id": user["_id"], "date": date})
    if not s:
        raise HTTPException(404, "no session that day")
    answered = [sl for sl in s["slots"] if sl["status"] == "answered"]
    return {"date": date, "total": len(s["slots"]),
            "answered": len(answered),
            "correct": sum(1 for sl in answered if sl.get("correct"))}

# ---------- exam simulator (آزمون آزمایشی): timed, no hints, result maps to key points ----------

class ExamStartBody(BaseModel):
    count: int = 20
    book_id: str | None = None
    minutes_per_question: int = 1
    minutes: int | None = None      # explicit exam duration wins over minutes_per_question


def _exam(eid, student_id):
    e = db.db.exam_sessions.find_one({"_id": ObjectId(eid)})
    if not e or e["student_id"] != student_id:
        raise HTTPException(404, "no such exam")
    return e


@router.post("/exam/start")
def exam_start(body: ExamStartBody | None = None, user: dict = Depends(auth.current_user)):
    if user.get("role") != "student":
        raise HTTPException(403, "students only")
    body = body or ExamStartBody()
    count = max(5, min(body.count, 40))
    cq = dict(scheduler.SERVABLE)
    cq["type"] = {"$ne": "tashrihi"}                    # multiple choice only: machine-gradable
    if body.book_id:
        cq["book_id"] = body.book_id
    elif user.get("scope_chapter_ids"):
        cq["chapter_id"] = {"$in": user["scope_chapter_ids"]}
    if not cq.get("chapter_id") and not body.book_id:
        raise HTTPException(400, "برنامهٔ مطالعه‌ات خالی است؛ اول کتاب‌ها را انتخاب کن")

    # one random question per concept first, then fill up with extras
    by_concept: dict = {}
    for q in db.db.questions.find(cq, {"concept_id": 1}):
        by_concept.setdefault(q.get("concept_id"), []).append(q["_id"])
    import random as _random
    concept_ids = list(by_concept.keys())
    _random.shuffle(concept_ids)
    picked = []
    for cid in concept_ids:
        if len(picked) >= count:
            break
        picked.append(_random.choice(by_concept[cid]))
    if len(picked) < 5:
        raise HTTPException(400, "برای آزمون سؤال کافی آماده نیست")
    _random.shuffle(picked)

    docs = list(db.db.questions.find({"_id": {"$in": picked}},
                                     {"concept_id": 1, "chapter_id": 1, "book_id": 1}))
    slots = [{"question_id": d["_id"], "concept_id": d.get("concept_id"),
              "chapter_id": d.get("chapter_id"), "book_id": d.get("book_id"),
              "status": "pending", "selected_display": None, "correct": None}
             for d in docs]
    minutes = max(5, min(body.minutes, 180)) if body.minutes else max(5, count * body.minutes_per_question)
    now = clock.now_utc()
    res = db.db.exam_sessions.insert_one({
        "student_id": user["_id"], "created_at": now,
        "deadline": now + dt.timedelta(minutes=minutes),
        "total": len(slots), "finished": False, "slots": slots})
    return {"exam_id": str(res.inserted_id), "total": len(slots),
            "deadline": (now + dt.timedelta(minutes=minutes)).isoformat() + "Z"}


@router.get("/exam/{eid}")
def exam_meta(eid: str, user: dict = Depends(auth.current_user)):
    e = _exam(eid, user["_id"])
    return {"total": e["total"], "finished": e["finished"],
            "answered": sum(1 for sl in e["slots"] if sl["status"] == "answered"),
            "deadline": e["deadline"].isoformat() + "Z"}


@router.get("/exam/{eid}/question/{index}")
def exam_question(eid: str, index: int, user: dict = Depends(auth.current_user)):
    e = _exam(eid, user["_id"])
    if e["finished"]:
        raise HTTPException(409, "این آزمون تمام شده است")
    if clock.now_utc() > e["deadline"]:
        raise HTTPException(409, "زمان آزمون تمام شد")
    if not 0 <= index < len(e["slots"]):
        raise HTTPException(404, "no such slot")
    sl = e["slots"][index]
    q = db.db.questions.find_one({"_id": sl["question_id"]})
    if not q:
        raise HTTPException(404, "question missing")
    out = public_question(q, perm=None)          # stable, unshuffled: exam conditions
    out["index"] = index
    return out


@router.post("/exam/{eid}/answer/{index}")
def exam_answer(eid: str, index: int, body: AnswerBody,
                user: dict = Depends(auth.current_user)):
    e = _exam(eid, user["_id"])
    if e["finished"]:
        raise HTTPException(409, "این آزمون تمام شده است")
    if clock.now_utc() > e["deadline"]:
        raise HTTPException(409, "زمان آزمون تمام شد")
    sl = e["slots"][index]
    if sl["status"] != "pending":
        raise HTTPException(409, "already answered")
    q = db.db.questions.find_one({"_id": sl["question_id"]})
    if not q:
        raise HTTPException(404, "question missing")
    original = scheduler.to_original(body.selected_option, None)
    correct_opt, correct = scheduler.grade(q, original)
    db.db.exam_sessions.update_one(
        {"_id": e["_id"], f"slots.{index}.status": "pending"},
        {"$set": {f"slots.{index}.status": "answered",
                  f"slots.{index}.selected_display": body.selected_option,
                  f"slots.{index}.selected": original,
                  f"slots.{index}.correct": correct,
                  f"slots.{index}.time_ms": body.time_ms}})
    # diagnostic only: exam answers do NOT move the review schedule
    s = db.db.exam_sessions.find_one({"_id": e["_id"]})
    return {"answered": sum(1 for sl in s["slots"] if sl["status"] == "answered"),
            "total": len(s["slots"])}


@router.post("/exam/{eid}/finish")
def exam_finish(eid: str, user: dict = Depends(auth.current_user)):
    e = _exam(eid, user["_id"])
    if not e["finished"]:
        # grade any pending slots as skipped (time ran out)
        db.db.exam_sessions.update_one(
            {"_id": e["_id"], "finished": False},
            {"$set": {"finished": True,
                      "slots.$[p].status": "skipped"}},
            array_filters=[{"p.status": "pending"}])
        e = db.db.exam_sessions.find_one({"_id": e["_id"]})
    concepts = {c["concept_id"]: c for c in db.db.concepts.find(
        {"concept_id": {"$in": [sl["concept_id"] for sl in e["slots"] if sl.get("concept_id")]}},
        {"title": 1, "chapter_title": 1, "book_name": 1})
        if c.get("concept_id")}
    answered = [sl for sl in e["slots"] if sl["status"] == "answered"]
    per_concept: dict = {}
    for sl in answered:
        c = per_concept.setdefault(sl["concept_id"], {"correct": 0, "wrong": 0})
        c["correct" if sl["correct"] else "wrong"] += 1
    items = [{"concept_id": cid,
              "title": (concepts.get(cid) or {}).get("title", cid),
              "chapter_title": (concepts.get(cid) or {}).get("chapter_title"),
              "book_name": (concepts.get(cid) or {}).get("book_name"),
              **v} for cid, v in per_concept.items()]
    wrong = [{"concept_id": it["concept_id"], "title": it["title"]}
             for it in items if it["wrong"] > 0]
    items.sort(key=lambda it: (it["correct"] / (it["correct"] + it["wrong"])))
    return {"total": e["total"], "answered": len(answered),
            "skipped": e["total"] - len(answered),
            "correct": sum(1 for sl in answered if sl["correct"]),
            "items": items,
            "wrong_concept_ids": [w["concept_id"] for w in wrong]}
