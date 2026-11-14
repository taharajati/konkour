"""New question variants for key points that have too few questions (DESIGN §6).

Input: the JSON from the admin panel (GET /admin/generation/export): key points with how
many questions they still need and a few approved examples.

For each needed question:
  1. generate      one variant from the key point + examples          (paid call)
  2. solve         an independent solve without the answer            (paid call)
  3. check         rule checks, 4 distinct options, answer in range
  4. dedupe        text similarity against the examples and everything already written
                   for this key point (character 3-gram Jaccard; a stand-in for
                   embeddings, good enough for "same question with other wording")
  5. keep only if the solver agrees with the generator and nothing failed

Kept questions are written to question_bank/grade<N>/generated_<date>/ with
source "ai_generated" and verification "verified". Like every other question they are
imported as pending and served only after a manager approves them.
"""
import datetime as dt
import json
import os
import re

from . import checks, config, prompts
from .pdfwork import save_json

MAX_TRIES_PER_QUESTION = 3
SIMILARITY_LIMIT = 0.8


def _norm(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").lower())
    return re.sub(r"[\\{}$]", "", t)


def similarity(a: str, b: str) -> float:
    def grams(s):
        s = _norm(s)
        return {s[i:i + 3] for i in range(max(0, len(s) - 2))}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def _full_text(q: dict) -> str:
    return q.get("stem_md", "") + " " + " ".join(q.get("options") or [])


def _examples_text(item: dict) -> str:
    parts = []
    for i, ex in enumerate(item.get("examples", []), start=1):
        opts = "\n".join(f"{j}) {o}" for j, o in enumerate(ex.get("options") or [], start=1))
        parts.append(f"نمونهٔ {i} (دشواری {ex.get('difficulty')}):\n{ex['stem_md']}\n{opts}\n"
                     f"پاسخ: گزینهٔ {ex['answer_option']}\nحل: {ex.get('solution_md') or ''}")
    return "\n\n".join(parts) or "(نمونه‌ای در بانک نیست؛ فقط از روی نکته بنویس)"


def generate_for(llm, item: dict, log=print) -> list:
    """returns accepted questions for one key point"""
    accepted, rejected = [], []
    existing = [_full_text(ex) for ex in item.get("examples", [])]
    for n in range(item["need"]):
        for attempt in range(MAX_TRIES_PER_QUESTION):
            avoid = "\n".join(f"- {t[:160]}" for t in existing[-12:])
            user = (f"نکته: {item['title']} (درس: {item.get('lesson_title') or ''}، پایهٔ {item.get('grade')})\n"
                    f"{item.get('key_point') or ''}\n\n{_examples_text(item)}\n\n"
                    f"سؤال‌های موجود:\n{avoid}\n\n"
                    f"سؤال جدید شمارهٔ {n + 1} را بنویس. تلاش {attempt + 1}.")
            g = llm.generate_json(f"gen {item['concept_id']} #{n + 1}.{attempt + 1}",
                                  prompts.GEN_SYSTEM, [{"text": user}], prompts.GEN_SCHEMA,
                                  config.EXTRACT_MODEL, config.EXTRACT_EFFORT)
            q = {"type": "mcq", "stem_md": g["stem_md"], "options": g["options"],
                 "options_order_checked": True, "legible": True}
            problems = checks.check_question(q)
            if not 1 <= g["answer_index"] <= len(g["options"]):
                problems.append("answer_index out of range")
            if any(re.search(r"همه|هیچ|گزینه", o) for o in g["options"]):
                problems.append("an option refers to other options")
            sim = max((similarity(_full_text(q), t) for t in existing), default=0.0)
            if sim >= SIMILARITY_LIMIT:
                problems.append(f"too similar to an existing question ({sim:.2f})")
            if problems:
                rejected.append({"why": problems, "q": g})
                continue
            qtext = q["stem_md"] + "\n" + "\n".join(f"{i}) {o}" for i, o in enumerate(q["options"], 1))
            s = llm.generate_json(f"gen-solve {item['concept_id']} #{n + 1}.{attempt + 1}",
                                  prompts.SOLVE_SYSTEM, [{"text": "سؤال:\n" + qtext}],
                                  prompts.SOLVE_SCHEMA, config.SOLVER_MODEL, config.SOLVER_EFFORT)
            status, answer, notes = checks.decide(g["answer_index"], s, [], "mcq")
            if status != "verified":
                rejected.append({"why": notes or [status], "q": g})
                continue
            accepted.append({**q, "answer_option": answer, "solution_md": g["solution_md"],
                             "difficulty": g["difficulty"], "solver": s})
            existing.append(_full_text(q))
            break
        else:
            log(f"  {item['concept_id']}: question {n + 1} failed {MAX_TRIES_PER_QUESTION} tries")
    item["_rejected"] = rejected
    return accepted


def write_generated(item: dict, questions: list, bank_name: str) -> list:
    grade = item.get("grade") or 9
    root = os.path.join(config.BANK_ROOT, f"grade{grade}", bank_name)
    os.makedirs(root, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    written = []
    for i, q in enumerate(questions, start=1):
        qid = f"gen_{item['concept_id']}_{stamp}_{i}".lower()
        folder = os.path.join(root, qid)
        os.makedirs(folder, exist_ok=False)
        with open(os.path.join(folder, "question.md"), "w", encoding="utf-8") as f:
            f.write(q["stem_md"].strip() + "\n\n" +
                    "\n".join(f"{j}) {o}" for j, o in enumerate(q["options"], start=1)) + "\n")
        with open(os.path.join(folder, "answer.md"), "w", encoding="utf-8") as f:
            f.write(q["solution_md"].strip() + "\n")
        save_json(os.path.join(folder, "meta.json"), {
            "id": qid, "grade": grade, "book_id": item.get("book_id"),
            "concept_id": item["concept_id"], "secondary_concept_ids": [],
            "question_type": "multiple_choice_4", "options": q["options"],
            "answer_option": q["answer_option"], "answer_confidence": "high",
            "needs_answer_verification": False, "difficulty": q["difficulty"], "figures": [],
            "source": {"kind": "ai_generated",
                       "from_examples": [e["public_id"] for e in item.get("examples", [])]},
            "verification": {"status": "verified", "key_option": q["answer_option"],
                             "solver_option": q["solver"]["solver_option"],
                             "solver_confidence": q["solver"]["confidence"],
                             "notes": ["سؤال تولیدشده با هوش مصنوعی؛ حل مستقل با کلید یکی است"],
                             "solution_origin": "generator"},
            "pipeline": {"prompt_version": config.PROMPT_VERSION,
                         "generator_model": config.EXTRACT_MODEL,
                         "solver_model": config.SOLVER_MODEL},
            "latex_enabled": True})
        written.append(qid)
    return written


def run(llm, export_file: str, work_dir: str, only: list | None = None, log=print) -> dict:
    with open(export_file, encoding="utf-8") as f:
        export = json.load(f)
    items = [it for it in export["items"] if not only or it["concept_id"] in only]
    bank_name = "generated_" + dt.date.today().strftime("%Y%m%d")
    summary = {"key_points": len(items), "written": 0, "rejected": 0, "folders": []}
    report = []
    for it in items:
        log(f"{it['concept_id']}: need {it['need']}")
        qs = generate_for(llm, it, log)
        ids = write_generated(it, qs, bank_name)
        summary["written"] += len(ids)
        summary["rejected"] += len(it["_rejected"])
        summary["folders"] += ids
        report.append({"concept_id": it["concept_id"], "need": it["need"], "written": len(ids),
                       "rejected": it["_rejected"]})
    save_json(os.path.join(work_dir, "generation_report.json"), report)
    return summary


def estimate(export_file: str) -> dict:
    with open(export_file, encoding="utf-8") as f:
        need = sum(it["need"] for it in json.load(f)["items"])
    calls = need * 2 * 1.5                       # generate + solve, ~1.5 tries each
    usd = calls * (3000 / 1e6 * 4 + 2500 / 1e6 * 20)
    return {"questions_needed": need, "calls": int(calls), "usd": round(usd, 2)}
