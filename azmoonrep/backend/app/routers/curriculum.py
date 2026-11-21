from fastapi import APIRouter, Depends
from .. import db, auth

router = APIRouter(prefix="/curriculum", tags=["curriculum"])

def _category(st):
    if not st or st.get("total_answers", 0) == 0:
        return "new"
    if st.get("mastery_level", 0) >= 2:
        return "learned"
    if st.get("lapses", 0) > 0 and st.get("streak", 0) == 0:
        return "wrong"
    return "review"


MASTERY_FA = {0: "نیاموخته", 1: "در حال یادگیری", 2: "یاد گرفته", 3: "مسلط"}

@router.get("/catalog")
def catalog():
    """public (no login): grades -> books with how much of each is ready, for the first screen"""
    approved = {r["_id"]: r["n"] for r in db.db.questions.aggregate(
        [{"$match": {"review_status": "approved"}}, {"$group": {"_id": "$concept_id", "n": {"$sum": 1}}}])}
    by_grade: dict = {}
    for b in db.db.books.find().sort([("grade", 1), ("order", 1)]):
        concepts = [c["concept_id"] for c in db.db.concepts.find(
            {"book_id": b["book_id"], "source": "taxonomy", "retired": {"$ne": True}}, {"concept_id": 1})]
        ready = [c for c in concepts if approved.get(c)]
        by_grade.setdefault(b.get("grade"), []).append({
            "book_id": b["book_id"], "name": b["name"], "field": b.get("reshte"),
            "chapters": db.db.chapters.count_documents({"book_id": b["book_id"]}),
            "key_points": len(concepts), "ready_key_points": len(ready),
            "approved_questions": sum(approved[c] for c in ready)})
    return {"grades": [{"grade": g, "books": bs} for g, bs in sorted(by_grade.items(), key=lambda x: (x[0] is None, x[0]))]}


@router.get("/books")
def books(user: dict = Depends(auth.current_user)):
    out = []
    for b in db.db.books.find().sort("grade", 1):
        chapters = list(db.db.chapters.find({"book_id": b["book_id"]}).sort("number", 1))
        out.append({"book_id": b["book_id"], "name": b["name"], "grade": b.get("grade"),
                    "chapters": [{"number": ch["number"], "title": ch["title"]}
                                 for ch in chapters]})
    return out

@router.get("/book-cards")
def book_cards(user: dict = Depends(auth.current_user)):
    """books with cover images + chapters + question counts, for the onboarding picker"""
    counts = {r["_id"]: r["n"] for r in db.db.questions.aggregate(
        [{"$group": {"_id": "$chapter_id", "n": {"$sum": 1}}}])}
    concept_counts = {r["_id"]: r["n"] for r in db.db.concepts.aggregate(
        [{"$group": {"_id": "$chapter_id", "n": {"$sum": 1}}}])}
    out = []
    for b in db.db.books.find().sort("grade", 1):
        chapters = list(db.db.chapters.find({"book_id": b["book_id"]}).sort("number", 1))
        out.append({
            "book_id": b["book_id"], "name": b["name"], "grade": b.get("grade"),
            "cover": f"/static/books/{b['book_id']}.png",
            "chapters": [{"chapter_id": ch["chapter_id"], "number": ch["number"],
                          "title": ch["title"],
                          "question_count": counts.get(ch["chapter_id"], 0),
                          "concept_count": concept_counts.get(ch["chapter_id"], 0)}
                         for ch in chapters]})
    return out


@router.get("/topics")
def topics(user: dict = Depends(auth.current_user)):
    """grade → chapter (or legacy topic) → concepts, with approved-question counts"""
    counts = {}
    for row in db.db.questions.aggregate(
            [{"$match": {"review_status": "approved"}},
             {"$group": {"_id": "$concept_id", "n": {"$sum": 1}}}]):
        counts[row["_id"]] = row["n"]

    tree = {}
    for c in db.db.concepts.find({"retired": {"$ne": True}}).sort("order_in_curriculum", 1):
        if not counts.get(c["concept_id"]):
            continue        # nothing a student could practise yet
        g = tree.setdefault(c.get("grade") or 9, {})
        group = c.get("chapter_title") or c.get("topic") or "عمومی"
        if c.get("book_name") and c.get("chapter_title"):
            group = f"{c['book_name']} · {c['chapter_title']}"
        t = g.setdefault(group, [])
        t.append({"concept_id": c["concept_id"], "title": c["title"],
                  "subtopic": c.get("subtopic"), "questions": counts.get(c["concept_id"], 0)})
    out = [{"grade": g,
            "topics": [{"topic": t, "concepts": cs} for t, cs in tmap.items()]}
           for g, tmap in tree.items()]
    out.sort(key=lambda x: x["grade"] or 0)
    return out


@router.get("/progress")
def progress(user: dict = Depends(auth.current_user)):
    """per-concept mastery + aggregated chapter/book view (in-scope/attempted only)"""
    states = list(db.db.concept_state.find({"student_id": user["_id"]}))
    by_concept = {s["concept_id"]: s for s in states}
    scope_chapters = set(user.get("scope_chapter_ids") or [])
    scope_books = set(user.get("scope_book_ids") or [])
    concepts = list(db.db.concepts.find())
    if scope_chapters or scope_books:
        concepts = [c for c in concepts
                    if c["concept_id"] in by_concept
                    or c.get("chapter_id") in scope_chapters
                    or c.get("book_id") in scope_books]
    else:
        concepts = [c for c in concepts if c["concept_id"] in by_concept]
    tree = {}
    for c in concepts:
        st = by_concept.get(c["concept_id"])
        lvl = (st or {}).get("mastery_level", 0)
        key = (c.get("grade"), c.get("book_name"), c.get("chapter_title"))
        tree.setdefault(key, []).append({
            "concept_id": c["concept_id"], "title": c["title"],
            "mastery": lvl, "mastery_fa": MASTERY_FA[lvl],
            "due": str((st or {}).get("due_date", "")),
        })
    out = []
    for (grade, book, chapter), items in sorted(tree.items(), key=lambda kv: str(kv[0])):
        avg = sum(i["mastery"] for i in items) / len(items)
        out.append({"grade": grade, "book": book, "chapter": chapter,
                    "mastery_avg": round(avg, 2), "concepts": items})
    return out


@router.get("/books/{book_id}/chapters")
def chapters_progress(book_id: str, user: dict = Depends(auth.current_user)):
    """chapters with per-chapter concept breakdown (learned/review/wrong/new) for the path UI"""
    states = {s["concept_id"]: s for s in
              db.db.concept_state.find({"student_id": user["_id"]})}
    chapters = list(db.db.chapters.find({"book_id": book_id}).sort("number", 1))
    scope_chapters = set(user.get("scope_chapter_ids") or [])
    if scope_chapters:
        chapters = [ch for ch in chapters if ch["chapter_id"] in scope_chapters]

    servable = {r["_id"] for r in db.db.questions.aggregate([
        {"$match": {"review_status": "approved"}}, {"$group": {"_id": "$concept_id"}}])}
    out = []
    for ch in chapters:
        concepts = list(db.db.concepts.find({"chapter_id": ch["chapter_id"],
                                             "retired": {"$ne": True}})
                        .sort("order_in_curriculum", 1))
        cats = {"learned": 0, "review": 0, "wrong": 0, "new": 0}
        clist = []
        placeable = 0
        for c in concepts:
            st = states.get(c["concept_id"])
            cat = _category(st)
            cats[cat] += 1
            if st is None and c["concept_id"] in servable:
                placeable += 1
            clist.append({"concept_id": c["concept_id"], "title": c["title"],
                          "status": cat, "mastery_fa": MASTERY_FA[(st or {}).get("mastery_level", 0)]})
        total = len(concepts)
        out.append({"chapter_id": ch["chapter_id"], "number": ch["number"], "title": ch["title"],
                    "total": total,
                    "progress": {k: (round(v / total, 2) if total else 0) for k, v in cats.items()},
                    "counts": cats,
                    # untouched key points a placement test can cover
                    "placement_available": placeable,
                    "concepts": clist})
    return out
