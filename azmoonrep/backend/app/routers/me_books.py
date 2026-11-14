from fastapi import APIRouter, Depends
from .. import db, auth, clock

router = APIRouter(prefix="/me", tags=["me"])

MASTERY_FA = {0: "نیاموخته", 1: "در حال یادگیری", 2: "یاد گرفته", 3: "مسلط"}


def _category(st: dict | None) -> str:
    """wrong = answered last wrong; learned = mastery>=2; review = learning (mastery 1); else new"""
    if not st or st.get("total_answers", 0) == 0:
        return "new"
    if st.get("mastery_level", 0) >= 2:
        return "learned"
    if st.get("lapses", 0) > 0 and st.get("streak", 0) == 0:
        return "wrong"
    return "review"


@router.get("/books")
def my_books(user: dict = Depends(auth.current_user)):
    """per-book card data: today's questions, accuracy, stacked progress breakdown"""
    scope_books = user.get("scope_book_ids") or []
    scope_chapters = set(user.get("scope_chapter_ids") or [])

    q = {"book_id": {"$in": scope_books}} if scope_books else {}
    books = list(db.db.books.find(q))
    if not books and scope_books:
        return []

    states = {s["concept_id"]: s for s in
              db.db.concept_state.find({"student_id": user["_id"]})}

    # today's pending slots per concept (across all per-book sessions)
    today = clock.today_str()
    pending_by_concept = {}
    for session in db.db.sessions.find({"student_id": user["_id"], "date": today}):
        for sl in session["slots"]:
            if sl["status"] == "pending":
                pending_by_concept[sl["concept_id"]] = pending_by_concept.get(sl["concept_id"], 0) + 1

    out = []
    for b in books:
        cq = {"book_id": b["book_id"]}
        if scope_chapters:
            cq = {"$or": [{"chapter_id": {"$in": list(scope_chapters)}},
                          {"$and": [{"chapter_id": None}, {"book_id": b["book_id"]}]}]}
        concepts = list(db.db.concepts.find(cq, {"concept_id": 1, "title": 1, "chapter_id": 1}))
        if not concepts:
            # book without mapped concepts: show it with zeros
            concepts = []

        cats = {"learned": 0, "review": 0, "wrong": 0, "new": 0}
        today_q = 0
        acc_a = acc_c = 0
        for c in concepts:
            cid = c["concept_id"]
            cat = _category(states.get(cid))
            cats[cat] += 1
            today_q += pending_by_concept.get(cid, 0)
            st = states.get(cid)
            if st:
                acc_a += st.get("total_answers", 0)
                acc_c += st.get("total_correct", 0)

        total = len(concepts)
        out.append({
            "book_id": b["book_id"], "name": b["name"], "grade": b.get("grade"),
            "cover": f"/static/books/{b['book_id']}.png",
            "concepts_total": total,
            "today_questions": today_q,
            "accuracy": round(acc_c / acc_a, 2) if acc_a else None,
            "progress": {
                "learned": round(cats["learned"] / total, 2) if total else 0,
                "review": round(cats["review"] / total, 2) if total else 0,
                "wrong": round(cats["wrong"] / total, 2) if total else 0,
                "new": round(cats["new"] / total, 2) if total else 0,
            },
            "counts": cats,
        })
    out.sort(key=lambda x: x["grade"] or 0)
    return out
