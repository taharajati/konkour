"""Draft the key-point list (taxonomy) for one chapter from the textbook PDF.

    python -m pipeline draft-taxonomy --book C110211 --chapters 4 --pages 75-99 [--yes]

Reads the chapter's pages from the book PDF (text layer), asks the model for key points
per lesson, and adds them to taxonomy/<book_id>.json with stable ids
<lesson_id>_k<N>. Existing concepts are never changed or renumbered: a chapter that
already has concepts is skipped. The result is a draft for a math teacher to review
(edit titles, merge or split points) before questions are tagged against it.
"""
import json
import os

import pymupdf

from . import config, prompts, taxonomy
from .pdfwork import save_json


def chapter_text(pdf_path: str, first: int, last: int, max_chars: int = 120_000) -> str:
    doc = pymupdf.open(pdf_path)
    parts = []
    for i in range(first - 1, min(last, doc.page_count)):
        parts.append(f"--- صفحهٔ {i + 1} ---\n{doc[i].get_text()}")
    text = "\n".join(parts)
    return text[:max_chars]


def draft_chapter(llm, book_id: str, chapter_n: int, pages: tuple, log=print) -> dict:
    catalog = taxonomy.load_catalog()
    book = next((b for b in catalog if b.get("book_id") == book_id), None)
    if not book:
        raise SystemExit(f"book {book_id} not in the catalog")
    if not book.get("file"):
        raise SystemExit(f"book {book_id} has no PDF in the catalog")
    chapter = next((c for c in book["chapters"] if c["n"] == chapter_n), None)
    if not chapter:
        raise SystemExit(f"chapter {chapter_n} not in {book_id}")

    path = os.path.join(config.TAXONOMY_DIR, f"{book_id}.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            tax = json.load(f)
    else:
        tax = {"book_id": book_id, "version": 1,
               "status": "draft: needs review by a math teacher before it is treated as final",
               "concepts": []}
    prefix = f"{book_id}_ch{chapter_n}_"
    if any(c["lesson_id"].startswith(prefix) for c in tax["concepts"]):
        log(f"chapter {chapter_n} already has key points in {path}: skipped")
        return {"added": 0, "skipped": True}

    pdf = os.path.join(os.path.dirname(config.CATALOG), book["file"])
    text = chapter_text(pdf, *pages)
    lessons = "\n".join(f"{l['id']}: {l['title']}" for l in chapter["lessons"])
    res = llm.generate_json(
        f"draft {book_id} ch{chapter_n}", prompts.DRAFT_SYSTEM,
        [{"text": f"کتاب: {book['book']} (پایهٔ {book.get('paaye')})\n"
                  f"فصل {chapter_n}: {chapter['title']}\nدرس‌ها:\n{lessons}\n\nمتن فصل:\n{text}"}],
        prompts.DRAFT_SCHEMA, config.TAG_MODEL, "high")

    valid_lessons = {l["id"] for l in chapter["lessons"]}
    order = max((c["order"] for c in tax["concepts"]), default=0)
    by_title, added = {}, []
    for les in res["lessons"]:
        if les["lesson_id"] not in valid_lessons:
            log(f"  model returned unknown lesson {les['lesson_id']}: ignored")
            continue
        for k, kp in enumerate(les["key_points"], start=1):
            order += 1
            cid = f"{les['lesson_id']}_k{k}"
            c = {"id": cid, "lesson_id": les["lesson_id"], "order": order,
                 "prereqs": [], "title": kp["title"].strip(), "key_point": kp["key_point"].strip(),
                 "_prereq_titles": kp["prereq_titles"], "draft": True}
            by_title[c["title"]] = cid
            added.append(c)
    for c in added:
        c["prereqs"] = [by_title[t] for t in c.pop("_prereq_titles") if t in by_title and by_title[t] != c["id"]]
    tax["concepts"].extend(added)
    save_json(path, tax)
    problems = taxonomy.validate(book_id)
    log(f"added {len(added)} key points to {path}" + (f"; problems: {problems}" if problems else ""))
    return {"added": len(added), "problems": problems, "file": path}
