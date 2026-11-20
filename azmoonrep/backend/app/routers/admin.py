import os
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .. import db, auth, clock, scheduler
from ..logging_setup import audit

router = APIRouter(prefix="/admin", tags=["admin"])

class ImportPaths(BaseModel):
    books_json: str | None = None      # path to books_catalog.json
    taxonomy_dir: str | None = None    # folder with <book_id>.json concept lists
    questions_root: str | None = None  # path to question_bank root (grade folders inside)

class BulkReviewBody(BaseModel):
    public_ids: list[str]
    approved: bool
    note: str | None = None

@router.post("/import")
def run_import(body: ImportPaths, user: dict = Depends(auth.require_admin)):
    from .. import importer
    audit(user["username"], "import", body.questions_root or "", body.books_json)
    result = {}
    try:
        if body.books_json:
            result["books"] = importer.import_books(body.books_json)
        if body.taxonomy_dir:
            result["taxonomy"] = importer.import_taxonomy(body.taxonomy_dir)
        if body.questions_root:
            result["questions"] = importer.import_questions(body.questions_root)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(422, str(e))
    # legacy concepts must be attached to a book/chapter, or scoped students never get them
    result["link"] = importer.link_concepts_to_chapters()
    result["prune"] = importer.prune_orphan_concepts()
    return result


@router.get("/concepts")
def list_concepts(book_id: str | None = None, user: dict = Depends(auth.require_admin)):
    """taxonomy concepts with how many questions each has (approved / all):
    the coverage view for 'every key point has enough questions'"""
    q = {"source": "taxonomy"}
    if book_id:
        q["book_id"] = book_id
    counts = {r["_id"]: r for r in db.db.questions.aggregate([
        {"$group": {"_id": "$concept_id", "all": {"$sum": 1},
                    "approved": {"$sum": {"$cond": [{"$eq": ["$review_status", "approved"]}, 1, 0]}}}}])}
    out = []
    for c in db.db.concepts.find(q).sort("order_in_curriculum", 1):
        n = counts.get(c["concept_id"], {})
        out.append({"concept_id": c["concept_id"], "title": c["title"],
                    "book_id": c.get("book_id"), "book_name": c.get("book_name"),
                    "grade": c.get("grade"),
                    "chapter_title": c.get("chapter_title"),
                    "lesson_title": c.get("lesson_title"),
                    "questions": n.get("all", 0), "approved": n.get("approved", 0)})
    unmapped = db.db.questions.count_documents({"concept_id": None})
    return {"concepts": out, "unmapped_questions": unmapped}


SCAN_FILES = {"question": "question_shot.png", "page": "source_page.png"}

@router.get("/generation/export")
def generation_export(min_approved: int = 5, max_examples: int = 3, book_id: str | None = None,
                      user: dict = Depends(auth.require_admin)):
    """key points with fewer than `min_approved` approved questions, each with up to
    `max_examples` approved multiple-choice examples. The question pipeline reads this
    file (`python -m pipeline generate <file>`) and writes new variants to the bank as
    pending questions for review."""
    q = {"source": "taxonomy", "retired": {"$ne": True}}
    if book_id:
        q["book_id"] = book_id
    items = []
    for c in db.db.concepts.find(q).sort("order_in_curriculum", 1):
        approved = list(db.db.questions.find(
            {"concept_id": c["concept_id"], "review_status": "approved",
             "type": "multiple_choice_4", "answer.option": {"$ne": None}}))
        pending = db.db.questions.count_documents(
            {"concept_id": c["concept_id"], "review_status": {"$in": [None, "pending"]}})
        need = min_approved - len(approved) - pending
        if need <= 0:
            continue
        approved.sort(key=lambda d: d.get("difficulty", 3))
        step = max(1, len(approved) // max_examples)
        examples = approved[::step][:max_examples]       # spread over difficulties
        items.append({
            "concept_id": c["concept_id"], "title": c["title"],
            "key_point": c.get("key_point"), "book_id": c.get("book_id"),
            "grade": c.get("grade"), "lesson_title": c.get("lesson_title"),
            "need": need, "approved": len(approved), "pending": pending,
            "examples": [{"public_id": d["public_id"], "stem_md": d.get("stem_md"),
                          "options": d.get("options"), "answer_option": d["answer"]["option"],
                          "solution_md": d.get("solution_md"), "difficulty": d.get("difficulty")}
                         for d in examples]})
    audit(user["username"], "generation_export", book_id or "all", f"{len(items)} key points")
    return {"min_approved": min_approved, "items": items}


@router.get("/questions/{public_id}/scan/{which}")
def question_scan(public_id: str, which: str, user: dict = Depends(auth.require_admin)):
    """publisher scan of a question, for admin review only (never in public static)"""
    name = SCAN_FILES.get(which)
    if not name:
        raise HTTPException(404, "unknown scan")
    d = db.db.questions.find_one({"public_id": public_id}, {"source_path": 1})
    src = (d or {}).get("source_path")
    if not src:
        raise HTTPException(404, "no source folder recorded — re-run the import")
    path = os.path.join(src, name)
    if not os.path.isfile(path):
        raise HTTPException(404, "scan not found")
    return FileResponse(path, media_type="image/png")

@router.get("/questions")
def list_questions(status: str = "all", concept_id: str | None = None,
                   chapter_id: str | None = None, search: str | None = None,
                   sort: str = "created",
                   skip: int = 0, limit: int = 50,
                   user: dict = Depends(auth.require_admin)):
    """status: all | approved | pending | pending_verified | rejected | flagged ; sort: created | difficulty | served | correct_rate"""
    q: dict = {}
    if concept_id:
        q["concept_id"] = concept_id
    if chapter_id:
        q["chapter_id"] = None if chapter_id == "__none" else chapter_id
    if search:
        import re as _re
        rx = {"$regex": _re.escape(search), "$options": "i"}
        q["$or"] = [{"stem_md": rx}, {"topic": rx}, {"subtopic": rx},
                    {"public_id": rx}, {"solution_md": rx}]
    if status == "approved":
        q["review_status"] = "approved"
    elif status == "rejected":
        q["review_status"] = "rejected"
    elif status == "pending":
        q["review_status"] = {"$in": [None, "pending"]}
    elif status == "pending_verified":
        q["review_status"] = {"$in": [None, "pending"]}
        q["verification.status"] = "verified"
        q["needs_answer_verification"] = {"$ne": True}
    elif status == "flagged":
        q["needs_answer_verification"] = True
    total = db.db.questions.count_documents(q)

    sort_map = {"created": [("_id", -1)], "difficulty": [("difficulty", 1), ("_id", 1)]}
    sort_key = sort_map.get(sort, [("_id", -1)])
    docs = list(db.db.questions.find(q, {"stem_md": 0, "solution_md": 0}) \
                .sort(sort_key).skip(skip).limit(limit))

    # response stats for this page
    ids = [d["_id"] for d in docs]
    served = {r["_id"]: r for r in db.db.responses.aggregate([
        {"$match": {"question_id": {"$in": ids}}},
        {"$group": {"_id": "$question_id",
                    "n": {"$sum": 1}, "c": {"$sum": {"$cond": ["$correct", 1, 0]}}}}])}
    items = []
    concept_titles = {c["concept_id"]: c.get("title") for c in db.db.concepts.find(
        {"concept_id": {"$in": list({d.get("concept_id") for d in docs if d.get("concept_id")})}},
        {"concept_id": 1, "title": 1})}
    for d in docs:
        st = served.get(d["_id"], {})
        n, c = st.get("n", 0), st.get("c", 0)
        rate = round(c / n, 2) if n else None
        items.append({
            "public_id": d.get("public_id"), "concept_id": d.get("concept_id"),
            "concept_title": concept_titles.get(d.get("concept_id")),
            "topic": d.get("topic"), "subtopic": d.get("subtopic"),
            "chapter_id": d.get("chapter_id"), "grade": d.get("grade"),
            "difficulty": d.get("difficulty"),
            "empirical_difficulty": d.get("empirical_difficulty"),
            "review_status": d.get("review_status", "pending"),
            "verification_status": (d.get("verification") or {}).get("status"),
            "answer_option": (d.get("answer") or {}).get("option"),
            "needs_answer_verification": d.get("needs_answer_verification", False),
            "has_figure": bool(d.get("figures") or d.get("option_figures")),
            "served": n, "correct_rate": rate,
            "outlier": bool(n >= 10 and (rate is None or rate < 0.15 or rate > 0.95))})
    return {"total": total, "items": items}


@router.post("/questions/bulk-review")
def bulk_review(body: BulkReviewBody, user: dict = Depends(auth.require_admin)):
    audit(user["username"], "bulk_approved" if body.approved else "bulk_rejected",
          ",".join(body.public_ids[:50]), body.note)
    if not body.public_ids:
        raise HTTPException(422, "no questions selected")
    if not body.approved and not (body.note and body.note.strip()):
        raise HTTPException(422, "bulk rejection requires a note")
    if body.approved:
        flagged = [d["public_id"] for d in db.db.questions.find(
            {"public_id": {"$in": body.public_ids}, "needs_answer_verification": True},
            {"public_id": 1})]
        if flagged:
            raise HTTPException(
                422, "این سؤال‌ها کلیدِ تأییدنشده دارند و گروهی تأیید نمی‌شوند؛ تک‌تک با اسکن مقایسه کن: "
                     + ", ".join(flagged[:10]))
    now = clock.now_utc()
    db.db.questions.update_many(
        {"public_id": {"$in": body.public_ids}},
        {"$set": {"review_status": "approved" if body.approved else "rejected",
                  "reviewed": body.approved,
                  "reviewed_by": user["username"], "reviewed_at": now,
                  **({} if body.approved else {"rejection_note": body.note.strip()})},
         "$push": {"history": {"action": "bulk_approved" if body.approved else "bulk_rejected",
                               "by": user["username"], "at": now,
                               "note": body.note if not body.approved else None}}},
    )
    return {"updated": len(body.public_ids),
            "review_status": "approved" if body.approved else "rejected"}


@router.get("/questions/duplicates")
def find_duplicates(user: dict = Depends(auth.require_admin)):
    """near-identical stems within the same concept (normalized text)"""
    import re as _re
    def norm(s):
        s = _re.sub(r"\$[^$]*\$", "MATH", s or "")
        s = _re.sub(r"[\d۰-۹]+", "#", s)
        return "".join(sorted(set(_re.findall(r"[\w\u0600-\u06FF]+", s))))
    groups = {}
    for d in db.db.questions.find({}, {"public_id": 1, "concept_id": 1, "stem_md": 1}):
        key = (d.get("concept_id"), norm(d.get("stem_md"))[:200])
        groups.setdefault(key, []).append(d["public_id"])
    dupes = [g for g in groups.values() if len(g) > 1]
    return {"groups": [{"concept_id": k[0], "public_ids": v} for k, v in dupes]}


@router.get("/questions/{public_id}")
def question_detail(public_id: str, user: dict = Depends(auth.require_admin)):
    d = db.db.questions.find_one({"public_id": public_id})
    if not d:
        raise HTTPException(404, "question not found")
    served = db.db.responses.count_documents({"question_id": d["_id"]})
    correct = db.db.responses.count_documents({"question_id": d["_id"], "correct": True})
    return {
        "public_id": d.get("public_id"),
        "concept_id": d.get("concept_id"), "topic": d.get("topic"),
        "subtopic": d.get("subtopic"), "grade": d.get("grade"),
        "chapter_id": d.get("chapter_id"),
        "difficulty": d.get("difficulty"), "type": d.get("type"),
        "stem_md": d.get("stem_md"), "options": d.get("options"),
        "answer": d.get("answer"), "solution_md": d.get("solution_md"),
        "review_status": d.get("review_status", "pending"),
        "rejection_note": d.get("rejection_note"),
        "needs_answer_verification": d.get("needs_answer_verification", False),
        "verification": d.get("verification"),
        "concept_title": (db.db.concepts.find_one({"concept_id": d.get("concept_id")},
                                                  {"title": 1}) or {}).get("title"),
        **scheduler.question_figures(d),
        "screenshot": f"/admin/questions/{public_id}/scan/question",
        "source_page": f"/admin/questions/{public_id}/scan/page",
        "served": served, "correct": correct,
        "correct_rate": round(correct / served, 2) if served else None,
        "history": d.get("history", []),
    }


class EditBody(BaseModel):
    stem_md: str | None = None
    options: list[str] | None = None
    answer_option: int | None = None
    solution_md: str | None = None
    difficulty: int | None = None
    concept_id: str | None = None

@router.patch("/questions/{public_id}")
def edit_question(public_id: str, body: EditBody,
                  user: dict = Depends(auth.require_admin)):
    d = db.db.questions.find_one({"public_id": public_id})
    if not d:
        raise HTTPException(404, "question not found")
    update: dict = {"edited_by": user["username"], "edited_at": clock.now_utc()}
    if body.stem_md is not None: update["stem_md"] = body.stem_md
    if body.solution_md is not None: update["solution_md"] = body.solution_md
    if body.difficulty is not None:
        if not 1 <= body.difficulty <= 5: raise HTTPException(422, "difficulty 1..5")
        update["difficulty"] = body.difficulty
    if body.options is not None:
        if not 2 <= len(body.options) <= 6: raise HTTPException(422, "2..6 options")
        update["options"] = body.options
    if body.answer_option is not None:
        if not 1 <= body.answer_option <= len(update.get("options") or d.get("options") or []):
            raise HTTPException(422, "answer option out of range")
        update["answer"] = {"option": body.answer_option}
    if body.concept_id is not None:
        c = db.db.concepts.find_one({"concept_id": body.concept_id})
        if not c:
            raise HTTPException(422, "unknown concept")
        update.update({"concept_id": c["concept_id"], "book_id": c.get("book_id"),
                       "chapter_id": c.get("chapter_id")})
    db.db.questions.update_one({"public_id": public_id}, {"$set": update})
    _push_history(public_id, "edited", user["username"])
    return {"public_id": public_id, "ok": True}

def _push_history(public_id: str, action: str, by: str, note: str | None = None):
    audit(by, action, public_id, note)
    db.db.questions.update_one(
        {"public_id": public_id},
        {"$push": {"history": {"action": action, "by": by,
                               "at": clock.now_utc(), "note": note}}})


class ReviewBody(BaseModel):
    approved: bool
    note: str | None = None

@router.post("/questions/{public_id}/review")
def review_question(public_id: str, body: ReviewBody,
                    user: dict = Depends(auth.require_admin)):
    d = db.db.questions.find_one({"public_id": public_id})
    if not d:
        raise HTTPException(404, "question not found")
    update: dict = {
        "review_status": "approved" if body.approved else "rejected",
        "reviewed": body.approved,
        "reviewed_by": user["username"],
        "reviewed_at": clock.now_utc(),
    }
    if not body.approved:
        if not (body.note and body.note.strip()):
            raise HTTPException(422, "rejection requires a note describing what to fix")
        update["rejection_note"] = body.note.strip()
    else:
        update["rejection_note"] = None
        update["needs_answer_verification"] = False
    db.db.questions.update_one({"public_id": public_id}, {"$set": update})
    _push_history(public_id, "approved" if body.approved else "rejected",
                  user["username"], body.note)
    return {"public_id": public_id, "review_status": update["review_status"]}


@router.get("/reports")
def list_reports(status: str = "open", user: dict = Depends(auth.require_admin)):
    docs = db.db.reports.find({"status": status}).sort("created_at", -1).limit(200)
    out = []
    for r in docs:
        q = db.db.questions.find_one({"public_id": r["question_public_id"]},
                                     {"topic": 1, "subtopic": 1})
        out.append({"id": str(r["_id"]), "question_public_id": r["question_public_id"],
                    "student": r.get("student_name"), "note": r["note"],
                    "status": r["status"],
                    "topic": (q or {}).get("topic"),
                    "created_at": str(r.get("created_at", ""))[:16]})
    return out

class ReportResolveBody(BaseModel):
    status: str  # resolved | dismissed

@router.post("/reports/{report_id}/resolve")
def resolve_report(report_id: str, body: ReportResolveBody,
                   user: dict = Depends(auth.require_admin)):
    from bson import ObjectId
    from bson.errors import InvalidId
    if body.status not in ("resolved", "dismissed"):
        raise HTTPException(422, "status must be resolved|dismissed")
    try:
        oid = ObjectId(report_id)
    except InvalidId:
        raise HTTPException(404, "report not found")
    rep = db.db.reports.find_one({"_id": oid})
    if not rep:
        raise HTTPException(404, "report not found")
    db.db.reports.update_one({"_id": oid},
                             {"$set": {"status": body.status,
                                       "resolved_by": user["username"]}})
    if body.status == "resolved":
        # a confirmed student report re-opens the question for review (fix #7)
        db.db.questions.update_one(
            {"public_id": rep["question_public_id"]},
            {"$set": {"review_status": "pending", "reviewed": False,
                      "needs_answer_verification": True},
             "$push": {"history": {"action": "student_report_confirmed",
                                   "by": user["username"],
                                   "at": clock.now_utc(),
                                   "note": rep["note"]}}})
    return {"ok": True}


def learning_metrics() -> dict:
    """the two numbers the product is judged on:
    - questions to learn a key point (mastery 2), for points learned in the app
      (placement-credited points are counted separately)
    - retention: correct rate on scheduled reviews that came after a long gap
      (interval >= 21 days), i.e. does the student still know it a month later"""
    taught = sorted(s["answers_to_learned"] for s in db.db.concept_state.find(
        {"answers_to_learned": {"$exists": True}, "placed": {"$exists": False}},
        {"answers_to_learned": 1}))
    median = None
    if taught:
        mid = len(taught) // 2
        median = taught[mid] if len(taught) % 2 else (taught[mid - 1] + taught[mid]) / 2
    long_checks = list(db.db.responses.find(
        {"context": "daily", "schedule_applied": True, "prior_interval_days": {"$gte": 21}},
        {"correct": 1}))
    kept = sum(1 for r in long_checks if r["correct"])
    placed = db.db.concept_state.count_documents({"placed": {"$exists": True}})
    placement_answers = db.db.responses.count_documents({"context": "placement"})
    return {
        "key_points_learned": len(taught),
        "median_questions_to_learn": median,
        "mean_questions_to_learn": round(sum(taught) / len(taught), 2) if taught else None,
        "placed_by_placement_test": placed,
        "placement_questions_answered": placement_answers,
        "long_gap_reviews": len(long_checks),
        "retention_after_21_days": round(kept / len(long_checks), 2) if long_checks else None,
    }


@router.get("/pilot-report.csv")
def pilot_report(user: dict = Depends(auth.require_admin)):
    """one row per student, for the pilot: activity, accuracy, questions needed to learn
    a key point, retention after long gaps. UTF-8 with BOM so Excel shows Persian."""
    import csv
    import io
    import statistics
    from fastapi.responses import Response
    from .. import clock

    def mask(s: str) -> str:
        return s[:4] + "***" + s[-2:] if s and s.isdigit() and len(s) > 6 else s

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["student", "name", "joined", "active_days", "last_active",
                "daily_answers", "practice_answers", "placement_answers", "accuracy",
                "key_points_started", "key_points_learned", "median_questions_to_learn",
                "placed_by_test", "long_gap_reviews", "retention_21d"])
    for s in db.db.users.find({"role": "student"}):
        sid = s["_id"]
        resp = list(db.db.responses.find({"student_id": sid},
                                         {"answered_at": 1, "context": 1, "correct": 1,
                                          "prior_interval_days": 1, "schedule_applied": 1}))
        days = sorted({clock.day_of(r["answered_at"]) for r in resp})
        ctx = lambda c: sum(1 for r in resp if r.get("context") == c)  # noqa: E731
        states = list(db.db.concept_state.find({"student_id": sid}))
        taught = [st["answers_to_learned"] for st in states
                  if "answers_to_learned" in st and "placed" not in st]
        long_gap = [r for r in resp if r.get("context") == "daily" and r.get("schedule_applied")
                    and (r.get("prior_interval_days") or 0) >= 21]
        w.writerow([
            mask(s.get("username", "")), s.get("display_name", ""),
            str(s.get("created_at", ""))[:10], len(days), days[-1].isoformat() if days else "",
            ctx("daily"), ctx("practice"), ctx("placement"),
            round(sum(1 for r in resp if r["correct"]) / len(resp), 2) if resp else "",
            len(states), sum(1 for st in states if st.get("mastery_level", 0) >= 2),
            statistics.median(taught) if taught else "",
            sum(1 for st in states if "placed" in st),
            len(long_gap),
            round(sum(1 for r in long_gap if r["correct"]) / len(long_gap), 2) if long_gap else ""])
    audit(user["username"], "pilot_report")
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=pilot-report.csv"})


@router.get("/overview")
def overview(user: dict = Depends(auth.require_admin)):
    """the dashboard: users, activity, content readiness and the product metrics"""
    now = clock.now_utc()
    d1, d7 = now - dt.timedelta(hours=24), now - dt.timedelta(days=7)
    users, resp, qs = db.db.users, db.db.responses, db.db.questions

    status_counts = {r["_id"] or "pending": r["n"] for r in qs.aggregate(
        [{"$group": {"_id": "$review_status", "n": {"$sum": 1}}}])}
    approved_by_concept = {r["_id"]: r["n"] for r in qs.aggregate(
        [{"$match": {"review_status": "approved"}}, {"$group": {"_id": "$concept_id", "n": {"$sum": 1}}}])}
    concepts = list(db.db.concepts.find({"source": "taxonomy", "retired": {"$ne": True}},
                                        {"concept_id": 1, "title": 1, "chapter_title": 1}))
    rows = [{"concept_id": c["concept_id"], "title": c.get("title"), "chapter_title": c.get("chapter_title"),
             "approved": approved_by_concept.get(c["concept_id"], 0)} for c in concepts]
    thin = sorted((r for r in rows if r["approved"] < 5), key=lambda r: r["approved"])
    w_total = resp.count_documents({"answered_at": {"$gte": d7}})
    w_correct = resp.count_documents({"answered_at": {"$gte": d7}, "correct": True})
    recent = list(users.find({"role": "student"}, {"username": 1, "display_name": 1, "created_at": 1,
                                                   "onboarded": 1}).sort("created_at", -1).limit(8))
    return {
        "users": {
            "students": users.count_documents({"role": "student"}),
            "new_7d": users.count_documents({"role": "student", "created_at": {"$gte": d7}}),
            "active_24h": len(resp.distinct("student_id", {"answered_at": {"$gte": d1}})),
            "active_7d": len(resp.distinct("student_id", {"answered_at": {"$gte": d7}})),
            "recent": [{"username": u["username"], "display_name": u.get("display_name"),
                        "created_at": u.get("created_at"), "onboarded": u.get("onboarded", False)}
                       for u in recent]},
        "activity": {"answers_24h": resp.count_documents({"answered_at": {"$gte": d1}}),
                     "answers_7d": w_total, "accuracy_7d": round(w_correct / w_total, 2) if w_total else None,
                     "answers_total": resp.count_documents({})},
        "content": {"questions": status_counts, "key_points": len(rows),
                    "key_points_ready": sum(1 for r in rows if r["approved"] >= 5),
                    "key_points_empty": sum(1 for r in rows if r["approved"] == 0),
                    "thin": thin[:8],
                    "flagged": qs.count_documents({"needs_answer_verification": True}),
                    "open_reports": db.db.reports.count_documents({"status": "open"})},
        "learning": learning_metrics(),
        "paths": {"books_json": os.getenv("BOOKS_JSON", ""), "taxonomy_dir": os.getenv("TAXONOMY_DIR", ""),
                  "questions_root": os.getenv("QUESTIONS_ROOT", "")},
    }


@router.get("/users")
def list_users(search: str = "", skip: int = 0, limit: int = 30,
               user: dict = Depends(auth.require_admin)):
    import re as _re
    q: dict = {"role": "student"}
    if search.strip():
        rx = {"$regex": _re.escape(search.strip()), "$options": "i"}
        q["$or"] = [{"username": rx}, {"display_name": rx}]
    total = db.db.users.count_documents(q)
    page = list(db.db.users.find(q).sort("created_at", -1).skip(max(0, skip)).limit(min(max(1, limit), 100)))
    ids = [u["_id"] for u in page]
    stats = {r["_id"]: r for r in db.db.responses.aggregate([
        {"$match": {"student_id": {"$in": ids}}},
        {"$group": {"_id": "$student_id", "n": {"$sum": 1}, "ok": {"$sum": {"$cond": ["$correct", 1, 0]}},
                    "last": {"$max": "$answered_at"}}}])}
    learned = {r["_id"]: r["n"] for r in db.db.concept_state.aggregate([
        {"$match": {"student_id": {"$in": ids}, "mastery_level": {"$gte": 2}}},
        {"$group": {"_id": "$student_id", "n": {"$sum": 1}}}])}
    return {"total": total, "items": [{
        "username": u["username"], "display_name": u.get("display_name"), "grade": u.get("grade"),
        "created_at": u.get("created_at"), "onboarded": u.get("onboarded", False),
        "answered": stats.get(u["_id"], {}).get("n", 0),
        "accuracy": round(stats[u["_id"]]["ok"] / stats[u["_id"]]["n"], 2) if u["_id"] in stats else None,
        "last_active": stats.get(u["_id"], {}).get("last"),
        "learned": learned.get(u["_id"], 0)} for u in page]}


@router.post("/users/{username}/reset-password")
def reset_password(username: str, user: dict = Depends(auth.require_admin)):
    """for a student who forgot the password (there is no SMS): a temporary one, shown once"""
    import secrets as _secrets
    target = db.db.users.find_one({"username": username.strip().lower(), "role": "student"})
    if not target:
        raise HTTPException(404, "دانش‌آموز پیدا نشد.")
    temp = _secrets.token_urlsafe(9)
    db.db.users.update_one({"_id": target["_id"]},
                           {"$set": {"password_hash": auth.hash_password(temp)},
                            "$inc": {"token_version": 1}})
    audit(user["username"], "password_reset", target["username"])
    return {"username": target["username"], "temp_password": temp}


@router.get("/stats")
def stats(user: dict = Depends(auth.require_admin)):
    def count(col, q=None): return db.db[col].count_documents(q or {})
    flagged = list(db.db.questions.find({"needs_answer_verification": True},
                                        {"public_id": 1, "concept_id": 1}).limit(50))
    return {
        "users": count("users"), "students": count("users", {"role": "student"}),
        "books": count("books"), "chapters": count("chapters"),
        "concepts": count("concepts"), "questions": count("questions"),
        "responses": count("responses"),
        "unreviewed_questions": count("questions", {"reviewed": False}),
        "learning": learning_metrics(),
        "flagged_sample": [{"public_id": f.get("public_id"), "concept_id": f.get("concept_id")}
                           for f in flagged],
    }
