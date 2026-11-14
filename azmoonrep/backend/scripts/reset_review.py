"""One-off cleanup after the review of 2026-11-14. Run from backend/:
    python -m scripts.reset_review

1. Questions that were approved automatically at import time (no manager approval in
   their history) go back to "pending": self-reported LLM confidence is not evidence.
2. Questions found wrong when compared with their source scan are rejected with a note
   saying what is wrong, so the manager can fix them from the admin panel.
"""
import datetime as dt
from app import db

MANAGER_ACTIONS = {"approved", "bulk_approved"}

KNOWN_WRONG = {
    "g9_sets_002": "گزینه‌ها با اسکن فرق دارند (اسکن: گروهی از ورزشکاران استان تهران / عددهای اول زوج / دو عدد زوج کمتر از ۲۲ / پنج تن از نویسندگان ایران) و کلید غلط است؛ پاسخ «عددهای اول زوج» (گزینه ۲) است.",
    "g9_sets_001": "گزینه‌ها با اسکن فرق دارند (ساختگی‌اند) و کلید غلط است؛ طبق اسکن پاسخ گزینه ۴ است.",
    "g9_sets_012": "گزینه‌ها از سؤال دیگری کپی شده‌اند؛ طبق اسکن پاسخ گزینه ۲ است.",
    "g9_sets_013": "صورت سؤال تغییر کرده ({{},∅} به {{},0}) و ترتیب گزینه‌ها جابه‌جاست؛ طبق اسکن پاسخ گزینه ۳ است.",
    "g9_sets_020": "در صورت سؤال B باید -1≤x<4 باشد نه <3؛ با متن فعلی کلید غلط است.",
    "g9_sets_027": "کلید غلط است: (B−A)∪(A∩B)=B یعنی گزینه ۴.",
    "g9_sets_037": "کلید غیرممکن است (عبارت‌های ۱ و ۲ نادرست‌اند) و حل ادعا می‌کند √4 گنگ است.",
    "g9_sets_039": "صورت سؤال بازنویسی شده (منفی شده و √3، √2 به √4 تبدیل شده) و دو گزینه درست دارد؛ طبق اسکن پاسخ گزینه ۴ است.",
    "g9_sets_045": "گزینه‌ها ساختگی‌اند (اسکن: ۴٫۵، ۴٫۶، ۴٫۸، ۴٫۲ ساعت)؛ طبق اسکن پاسخ گزینه ۳ است.",
    "g9_sets_049": "کلید احتمالاً غلط است: ۲+۱=۳ اول است، پس «عدد اول + ۱ مرکب است» همیشه درست نیست.",
    "g9_sets_050": "ترتیب گزینه‌ها برعکس خوانده شده و کلید (1/a) همیشه گنگ است؛ طبق اسکن پاسخ ab است.",
    "g9_sets_053": "صورت سؤال (جملهٔ آخر 1/(46×51)) و گزینه‌ها با اسکن فرق دارند؛ طبق اسکن پاسخ 8/561 است.",
}

def main():
    now = dt.datetime.utcnow()
    reset = 0
    for q in db.db.questions.find({"review_status": "approved"}):
        actions = {h.get("action") for h in q.get("history", [])}
        if actions & MANAGER_ACTIONS:
            continue
        db.db.questions.update_one(
            {"_id": q["_id"]},
            {"$set": {"review_status": "pending", "reviewed": False},
             "$push": {"history": {"action": "auto_approval_revoked", "by": "system",
                                   "at": now, "note": "تأیید خودکار هنگام ورود لغو شد"}}})
        reset += 1

    rejected = 0
    for pid, note in KNOWN_WRONG.items():
        r = db.db.questions.update_one(
            {"public_id": pid},
            {"$set": {"review_status": "rejected", "reviewed": False,
                      "needs_answer_verification": True, "rejection_note": note,
                      "reviewed_by": "system", "reviewed_at": now},
             "$push": {"history": {"action": "rejected", "by": "system",
                                   "at": now, "note": note}}})
        rejected += r.modified_count
    print(f"auto-approved reset to pending: {reset}; known-wrong rejected: {rejected}")

if __name__ == "__main__":
    main()
