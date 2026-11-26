"""Add new books' content to a live database without changing anything already in it.
    python -m scripts.add_content --books PHY10,CHE10 --banks grade10/ai_generated_phy10           # dry run
    python -m scripts.add_content --books PHY10,CHE10 --banks grade10/ai_generated_phy10 --write

Unlike import_data (which re-imports everything and overwrites what changed in the files),
this only inserts:
  * concepts of the named taxonomy books whose id is not in the database yet
  * question folders of the named banks whose public_id is not in the database yet
  * the lesson list of a chapter, only where that chapter has no lessons at all
New generated questions that passed their checks are approved; no other question is touched.
Running it twice does nothing the second time.

Paths come from BOOKS_JSON, TAXONOMY_DIR and QUESTIONS_ROOT, as in import_data."""
import argparse
import json
import os
import shutil
import tempfile

from app import clock, db
from app.importer import import_questions, import_taxonomy, slug

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__ if "__file__" in globals() else "."), "..", "..", ".."))
BY = "add-content"


def paths():
    return (os.getenv("BOOKS_JSON", os.path.join(WORKSPACE, "main books", "books_catalog.json")),
            os.getenv("TAXONOMY_DIR", os.path.join(WORKSPACE, "taxonomy")),
            os.getenv("QUESTIONS_ROOT", os.path.join(WORKSPACE, "question_bank")))


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def plan(book_ids, banks):
    """what is missing from the database; raises if the files do not fit what is there"""
    books_json, tax_dir, root = paths()
    catalog = {b.get("book_id"): b for b in read(books_json)}

    chapters = []
    for book_id in book_ids:
        if not db.db.books.find_one({"book_id": book_id}):
            raise SystemExit(f"book {book_id} is not in the database; nothing was written")
        for ch in catalog[book_id]["chapters"]:
            chapter_id = f"{book_id}_ch{ch['n']}"
            have = db.db.chapters.find_one({"chapter_id": chapter_id})
            if not have:
                raise SystemExit(f"chapter {chapter_id} is not in the database; nothing was written")
            lessons = ch.get("lessons", [])
            if lessons and not have.get("lessons") and not have.get("lesson_items"):
                chapters.append((chapter_id,
                                 [l["title"] if isinstance(l, dict) else l for l in lessons],
                                 [l for l in lessons if isinstance(l, dict)]))

    taxonomies = []
    for book_id in book_ids:
        tax = read(os.path.join(tax_dir, f"{book_id}.json"))
        ids = [c["id"] for c in tax["concepts"]]
        have = set(db.db.concepts.distinct("concept_id", {"concept_id": {"$in": ids}}))
        missing = [c for c in tax["concepts"] if c["id"] not in have]
        if missing:
            taxonomies.append({**tax, "concepts": missing})

    questions = []   # (bank, folder, public_id)
    seen = set()
    for bank in banks:
        bank_path = os.path.join(root, *bank.split("/"))
        for folder in sorted(os.listdir(bank_path)):
            meta_file = os.path.join(bank_path, folder, "meta.json")
            if not os.path.isfile(meta_file):
                continue
            public_id = slug(read(meta_file).get("id") or folder)
            if not public_id or public_id in seen:
                raise SystemExit(f"{bank}/{folder}: empty or repeated id; nothing was written")
            seen.add(public_id)
            questions.append((bank, folder, public_id))
    have = set(db.db.questions.distinct("public_id", {"public_id": {"$in": list(seen)}}))
    new = [q for q in questions if q[2] not in have]
    return chapters, taxonomies, new, len(questions) - len(new)


def write(chapters, taxonomies, questions):
    root = paths()[2]
    for chapter_id, lessons, items in chapters:
        db.db.chapters.update_one(
            {"chapter_id": chapter_id, "lessons": {"$in": [None, []]}},
            {"$set": {"lessons": lessons, "lesson_items": items}})

    with tempfile.TemporaryDirectory() as tmp:
        # the importer reads whole folders, so give it folders holding only the new things
        tax_tmp = os.path.join(tmp, "taxonomy")
        os.makedirs(tax_tmp)
        for tax in taxonomies:
            with open(os.path.join(tax_tmp, f"{tax['book_id']}.json"), "w", encoding="utf-8") as f:
                json.dump(tax, f, ensure_ascii=False)
        print("taxonomy:", import_taxonomy(tax_tmp))

        bank_tmp = os.path.join(tmp, "bank")
        os.makedirs(bank_tmp)
        for bank, folder, _ in questions:
            parts = bank.split("/") + [folder]
            shutil.copytree(os.path.join(root, *parts), os.path.join(bank_tmp, *parts))
        print("questions:", import_questions(bank_tmp))

    for bank, folder, public_id in questions:
        db.db.questions.update_one(
            {"public_id": public_id},
            {"$set": {"source_path": os.path.abspath(os.path.join(root, *bank.split("/"), folder))}})

    now = clock.now_utc()
    res = db.db.questions.update_many(
        {"public_id": {"$in": [q[2] for q in questions]}, "source": "ai_generated",
         "review_status": "pending", "verification.status": {"$in": ["verified", "code_checked"]},
         "needs_answer_verification": {"$ne": True}},
        {"$set": {"review_status": "approved", "reviewed": True, "reviewed_by": BY, "reviewed_at": now},
         "$push": {"history": {"action": "bulk_approved", "by": BY, "at": now,
                               "note": "generated question, key recomputed by code"}}})
    print("approved:", res.modified_count)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", required=True)
    ap.add_argument("--banks", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    chapters, taxonomies, questions, skipped = plan(a.books.split(","), a.banks.split(","))
    print("chapters to give lessons:", len(chapters))
    print("new concepts:", {t["book_id"]: len(t["concepts"]) for t in taxonomies})
    print("new questions:", len(questions), "| already there (left alone):", skipped)
    if a.write:
        write(chapters, taxonomies, questions)
    else:
        print("dry run: nothing written")


if __name__ == "__main__":
    main()
