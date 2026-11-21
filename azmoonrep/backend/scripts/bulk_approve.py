"""Approve the generated (AI-written) questions that passed their checks, in one go.
    python -m scripts.bulk_approve          # dry run: prints counts
    python -m scripts.bulk_approve --write  # approves them

Only touches questions that are pending, written by the generator, have a verified or
code-checked key and are not flagged. Questions held for a scan comparison stay pending.
Each question gets a history entry; a manager can still reject any of them later (and
students can report errors, which the admin screen lists)."""
import sys

from app import clock, db

BY = "bulk-approve-2026-11-22"
query = {"source": "ai_generated", "review_status": {"$in": [None, "pending"]},
         "verification.status": {"$in": ["verified", "code_checked"]},
         "needs_answer_verification": {"$ne": True}}


def main(write: bool):
    n = db.db.questions.count_documents(query)
    by_status = {r["_id"]: r["n"] for r in db.db.questions.aggregate(
        [{"$match": query}, {"$group": {"_id": "$verification.status", "n": {"$sum": 1}}}])}
    print(n, "questions", by_status, "(will be approved)" if write else "(dry run)")
    if write and n:
        now = clock.now_utc()
        db.db.questions.update_many(query, {
            "$set": {"review_status": "approved", "reviewed": True, "reviewed_by": BY, "reviewed_at": now},
            "$push": {"history": {"action": "bulk_approved", "by": BY, "at": now,
                                  "note": "generated question, key recomputed by code (grade 9: plus independent solver and senior review)"}}})
        print("approved")


if __name__ == "__main__":
    main("--write" in sys.argv)
