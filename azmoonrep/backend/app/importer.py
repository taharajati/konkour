"""Import books (books_catalog.json) and prepared question folders into MongoDB.

Question folder layout (the pilot bank layout):
  <questions_root>/<grade>/<bank_name>/<q_folder>/
      meta.json, question.md, answer.md, [figures...]

Concepts are derived from each question's meta: (grade, topic, subtopic).
"""
import json
import os
import re
import shutil
import hashlib
import datetime as dt
from pymongo import UpdateOne
from . import clock, db
from .config import STATIC_QUESTIONS_DIR


def slug(text: str) -> str:
    # keep Persian letters, replace unsafe chars
    s = re.sub(r"[^\w\u0600-\u06FF]+", "_", text or "")
    return s.strip("_")[:80]


def _normalize(text: str) -> set:
    """word set of a Persian string, ignoring common filler words"""
    stop = {"و", "در", "به", "های", "با", "از", "آن", "این", "برای", "مبحث", "فصل"}
    words = re.findall(r"[\w\u0600-\u06FF]+", (text or "").replace("‌", " "))
    return {w for w in words if w not in stop and len(w) > 1}


def best_chapter_for(grade, topic, subtopic):
    """pick the chapter (any book) whose title/lessons overlap most with the concept words"""
    words = _normalize(f"{topic} {subtopic} {topic}")
    best, best_score = None, 0
    for ch in db.db.chapters.find():
        ch_words = _normalize(ch["title"]) | set()
        for les in ch.get("lessons", []):
            ch_words |= _normalize(les)
        score = len(words & ch_words)
        # prefer same-grade books slightly
        book = db.db.books.find_one({"book_id": ch["book_id"]})
        if book and book.get("grade") == grade:
            score += 0.5
        if score > best_score:
            best, best_score = ch, score
    return best if best_score >= 1 else None


def prune_orphan_concepts() -> dict:
    """drop legacy free-text concepts that no question and no student uses any more
    (left behind after the bank moved to taxonomy concept ids)"""
    removed = 0
    for c in db.db.concepts.find({"source": {"$ne": "taxonomy"}}, {"concept_id": 1}):
        cid = c["concept_id"]
        if db.db.questions.count_documents({"concept_id": cid}, limit=1):
            continue
        if db.db.concept_state.count_documents({"concept_id": cid}, limit=1):
            continue
        db.db.concepts.delete_one({"_id": c["_id"]})
        removed += 1
    return {"orphan_concepts_removed": removed}


def link_concepts_to_chapters():
    """backfill book_id/chapter_id on existing concepts + their questions"""
    updated = 0
    for c in db.db.concepts.find({"chapter_id": {"$exists": False}}):
        ch = best_chapter_for(c.get("grade"), c.get("topic"), c.get("subtopic"))
        if not ch:
            continue
        book = db.db.books.find_one({"book_id": ch["book_id"]})
        db.db.concepts.update_one(
            {"concept_id": c["concept_id"]},
            {"$set": {"book_id": ch["book_id"], "chapter_id": ch["chapter_id"],
                      "book_name": book["name"], "chapter_title": ch["title"]}})
        db.db.questions.update_many(
            {"concept_id": c["concept_id"]},
            {"$set": {"book_id": ch["book_id"], "chapter_id": ch["chapter_id"]}})
        updated += 1
    return {"concepts_linked": updated}


def import_books(books_json_path: str) -> dict:
    with open(books_json_path, encoding="utf-8") as f:
        catalog = json.load(f)
    chapters_ops = []
    book_ids = []
    for order, b in enumerate(catalog):
        book_id = b.get("book_id") or (b.get("file") or "").replace(".pdf", "") or slug(b["book"])
        book_ids.append(book_id)
        db.db.books.update_one(
            {"book_id": book_id},
            {"$set": {"book_id": book_id, "name": b["book"],
                      "grade": b.get("grade") or _grade_fa_to_num(b.get("paaye")),
                      "paaye": b.get("paaye"), "reshte": b.get("reshte"),
                      "dore": b.get("dore"), "order": order,
                      "updated_at": clock.now_utc()}},
            upsert=True)
        for ch in b.get("chapters", []):
            ch_id = f"{book_id}_ch{ch['n']}"
            lessons = ch.get("lessons", [])
            chapters_ops.append(UpdateOne(
                {"chapter_id": ch_id},
                {"$set": {"chapter_id": ch_id, "book_id": book_id,
                          "number": ch["n"], "title": ch["title"],
                          # lessons: titles (old catalog format) or {id, n, title}
                          "lessons": [l["title"] if isinstance(l, dict) else l for l in lessons],
                          "lesson_items": [l for l in lessons if isinstance(l, dict)]}},
                upsert=True))
    # one update per chapter (a few dozen): simpler than bulk_write and works on mongomock
    for op in chapters_ops:
        db.db.chapters.update_one(op._filter, op._doc, upsert=True)
    return {"books": len(book_ids), "chapters": len(chapters_ops)}


def import_taxonomy(taxonomy_dir: str) -> dict:
    """closed concept list per book (taxonomy/<book_id>.json) -> concepts collection.
    Concepts get their book/chapter/lesson links and curriculum order from here, not
    from guessing on free-text tags."""
    if not os.path.isdir(taxonomy_dir):
        return {"concepts": 0, "note": f"no taxonomy folder at {taxonomy_dir}"}
    n = 0
    for name in sorted(os.listdir(taxonomy_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(taxonomy_dir, name), encoding="utf-8") as f:
            tax = json.load(f)
        book = db.db.books.find_one({"book_id": tax["book_id"]})
        if not book:
            raise ValueError(f"taxonomy {name}: book {tax['book_id']} not imported yet")
        for c in tax["concepts"]:
            ch_n = int(re.search(r"_ch(\d+)_", c["lesson_id"]).group(1))
            chapter = db.db.chapters.find_one({"chapter_id": f"{tax['book_id']}_ch{ch_n}"}) or {}
            lesson = next((l for l in chapter.get("lesson_items", [])
                           if l.get("id") == c["lesson_id"]), {})
            db.db.concepts.update_one(
                {"concept_id": c["id"]},
                {"$set": {"concept_id": c["id"], "title": c["title"],
                          "key_point": c.get("key_point"),
                          "lesson_id": c["lesson_id"], "lesson_title": lesson.get("title"),
                          "book_id": tax["book_id"], "book_name": book["name"],
                          "chapter_id": chapter.get("chapter_id"),
                          "chapter_title": chapter.get("title"),
                          "grade": book.get("grade"),
                          "prereq_ids": c.get("prereqs", []),
                          "retired": bool(c.get("retired")),
                          # book order, then the concept's order inside the book
                          "order_in_curriculum": book.get("order", 0) * 10000 + c["order"],
                          "source": "taxonomy",
                          "updated_at": clock.now_utc()}},
                upsert=True)
            n += 1
    return {"concepts": n}


def _grade_fa_to_num(paaye: str | None) -> int | None:
    m = {"نهم": 9, "دهم": 10, "یازدهم": 11, "دوازدهم": 12}
    return m.get(paaye or "")


CONTENT_FIELDS = ("stem_md", "options", "answer", "solution_md", "difficulty", "concept_id",
                  "secondary_concept_ids")


def clean_stem(md: str, has_options: bool) -> str:
    """figures are shown from meta.json, never from image links inside the text.
    bank question.md starts with «# سؤال N» and lists the options for human readers;
    students get the options separately, so drop both from the stem"""
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md or "")
    lines = md.strip().splitlines()
    if lines and re.match(r"^#\s*سؤال\s*[\d۰-۹]+", lines[0]):
        lines = lines[1:]
    if has_options:
        while lines and (not lines[-1].strip() or re.match(r"^\s*[1-6۱-۶]\)\s", lines[-1])):
            lines.pop()
    return "\n".join(lines).strip()


def import_questions(questions_root: str) -> dict:
    imported, skipped, unmapped = 0, 0, 0
    for grade_dir in sorted(os.listdir(questions_root)):
        grade_path = os.path.join(questions_root, grade_dir)
        m = re.fullmatch(r"(?:grade)?(\d+)", grade_dir, re.IGNORECASE)
        if not os.path.isdir(grade_path) or not m:
            continue
        grade = int(m.group(1))
        for bank_name in sorted(os.listdir(grade_path)):
            bank_path = os.path.join(grade_path, bank_name)
            if not os.path.isdir(bank_path):
                continue
            for qfolder in sorted(os.listdir(bank_path)):
                qpath = os.path.join(bank_path, qfolder)
                meta_file = os.path.join(qpath, "meta.json")
                if not os.path.isfile(meta_file):
                    continue
                meta = json.load(open(meta_file, encoding="utf-8"))
                qmd_file = os.path.join(qpath, "question.md")
                stem = open(qmd_file, encoding="utf-8").read() if os.path.isfile(qmd_file) else ""
                ans_file = os.path.join(qpath, "answer.md")
                solution = open(ans_file, encoding="utf-8").read() if os.path.isfile(ans_file) else ""

                # public_id becomes a folder name under static/: keep it to safe chars
                public_id = slug(meta.get("id") or qfolder)
                if not public_id:
                    skipped += 1
                    continue
                topic = meta.get("topic") or "عمومی"
                sub = meta.get("subtopic") or "عمومی"

                concept_doc = None
                if "concept_id" in meta:
                    # tagged against the closed taxonomy. null = not mapped yet: import
                    # the question but leave it unservable until the manager sets one
                    concept_id = meta["concept_id"]
                    if concept_id:
                        concept_doc = db.db.concepts.find_one({"concept_id": concept_id})
                        if not concept_doc:
                            raise ValueError(f"{qfolder}: concept {concept_id} is not in the "
                                             "taxonomy; import the taxonomy first")
                    else:
                        unmapped += 1
                else:
                    # legacy free-text tags (old bank folders without concept_id)
                    concept_id = f"g{grade}_{slug(topic)}_{slug(sub)}"
                    book_name, chapter_title = _guess_book(grade, topic)
                    _ensure_concept(concept_id, grade, book_name, chapter_title, topic, sub)

                # copy ONLY figure images into the public static dir. meta.json and
                # answer.md hold the answer key, and source_page/question_shot are
                # publisher scans: none of them may be publicly downloadable.
                dest = os.path.join(STATIC_QUESTIONS_DIR, public_id)
                wanted = None
                if "option_figures" in meta or meta.get("figure_source"):
                    wanted = list(meta.get("figures") or []) + \
                        [f for f in meta.get("option_figures") or [] if f]
                published = _publish_figures(qpath, dest, wanted)
                opt_names = meta.get("option_figures") or []
                figures = [v for k, v in published.items() if k not in opt_names]
                option_figures = [published.get(n) if n else None for n in opt_names] \
                    if any(opt_names) else None

                ans_opt = meta.get("answer_option")
                conf = meta.get("answer_confidence")
                solution = clean_solution(solution, ans_opt)
                content = {
                    "concept_id": concept_id,
                    "secondary_concept_ids": meta.get("secondary_concept_ids", []),
                    "difficulty": meta.get("difficulty") or _difficulty_heuristic(meta),
                    "stem_md": clean_stem(stem, bool(meta.get("options"))),
                    "options": meta.get("options"),
                    "answer": {"option": ans_opt},
                    "solution_md": solution,
                }
                raw_src = meta.get("source")
                src_kind = (raw_src.get("kind") if isinstance(raw_src, dict) else raw_src) or "bank"
                if src_kind not in ("bank", "ai_generated", "konkur"):
                    src_kind = "bank"
                doc = {
                    "public_id": public_id,
                    "grade": grade,
                    "topic": topic, "subtopic": sub,
                    "book_id": (concept_doc or {}).get("book_id") or meta.get("book_id"),
                    "chapter_id": (concept_doc or {}).get("chapter_id"),
                    "type": meta.get("question_type", "multiple_choice_4"),
                    "verification": meta.get("verification"),
                    "figures": figures,                  # [{file, w, h}]
                    "option_figures": option_figures,    # per option, or None
                    "needs_answer_verification": conf == "low"
                                                 or meta.get("needs_answer_verification", False),
                    "answer_confidence": conf,
                    "source": src_kind,
                    "source_meta": raw_src if isinstance(raw_src, dict) else None,
                    "storage_path": dest,
                    # private bank folder: scans are served to admins only, from here
                    "source_path": os.path.abspath(qpath),
                    "imported_at": clock.now_utc(),
                }
                # every imported question starts as pending and needs a manager's
                # approval (DESIGN principle 5). Self-reported LLM confidence is not
                # evidence of correctness. On re-import, keep the manager's decision.
                # A manager's edits in the admin panel win over the bank files: content
                # of an edited question is only set when the question is new.
                existing = db.db.questions.find_one({"public_id": public_id},
                                                    {"edited_at": 1})
                if existing and existing.get("edited_at"):
                    # the manager may have moved it to another concept: book/chapter follow that
                    update = {"$set": {k: v for k, v in doc.items()
                                       if k not in ("book_id", "chapter_id")},
                              "$setOnInsert": {}}
                else:
                    update = {"$set": {**doc, **content}, "$setOnInsert": {}}
                update["$setOnInsert"].update({"review_status": "pending", "reviewed": False})
                if existing and existing.get("edited_at"):
                    update["$setOnInsert"].update(content)
                db.db.questions.update_one({"public_id": public_id}, update, upsert=True)
                imported += 1
    return {"imported": imported, "skipped": skipped, "unmapped_concept": unmapped}


PRIVATE_IMAGES = {"source_page.png", "question_shot.png"}
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


def image_size(path: str):
    """(width, height) of a PNG / JPEG / GIF from its header; None if unknown.
    The frontend reserves the figure's box from these, so the page never jumps."""
    import struct
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", head[6:10])
            if head[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    marker = f.read(4)
                    if len(marker) < 4 or marker[0] != 0xFF:
                        return None
                    size = struct.unpack(">H", marker[2:4])[0]
                    if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                        h, w = struct.unpack(">HH", f.read(5)[1:5])
                        return w, h
                    f.seek(size - 2, 1)
    except (OSError, struct.error):
        pass
    return None


def _publish_figures(src_dir: str, dest_dir: str, names: list | None = None) -> dict:
    """copy figure images from a bank folder into the public static folder.

    Files are stored under a name made from their content hash, so a changed figure
    gets a new URL (browsers and CDNs can cache figures forever) and the bank's file
    names never leak. Returns {bank name: {"file", "w", "h"}}. Anything else in the
    destination (older copies, answer keys, scans) is removed."""
    if not os.path.isdir(src_dir):
        return {}
    if names is None:
        names = sorted(f for f in os.listdir(src_dir)
                       if f.lower().endswith(IMAGE_EXTS) and f not in PRIVATE_IMAGES)
    out = {}
    os.makedirs(dest_dir, exist_ok=True)
    for name in names:
        src = os.path.join(src_dir, os.path.basename(name))
        if name in PRIVATE_IMAGES or not name.lower().endswith(IMAGE_EXTS) or not os.path.isfile(src):
            continue
        with open(src, "rb") as fh:
            digest = hashlib.sha1(fh.read()).hexdigest()[:16]
        hashed = digest + os.path.splitext(name)[1].lower()
        shutil.copy2(src, os.path.join(dest_dir, hashed))
        size = image_size(src)
        out[name] = {"file": hashed, "w": size[0] if size else None, "h": size[1] if size else None}
    keep = {v["file"] for v in out.values()}
    for name in os.listdir(dest_dir):
        p = os.path.join(dest_dir, name)
        if os.path.isfile(p) and name not in keep:
            os.remove(p)
    return out

def purge_private_static_files() -> int:
    """remove answer keys / scans from every folder under the static questions dir"""
    removed = 0
    if not os.path.isdir(STATIC_QUESTIONS_DIR):
        return 0
    for root, _dirs, files in os.walk(STATIC_QUESTIONS_DIR):
        for name in files:
            if name in PRIVATE_IMAGES or not name.lower().endswith(IMAGE_EXTS):
                os.remove(os.path.join(root, name))
                removed += 1
    return removed


def _guess_book(grade: int, topic: str):
    """map (grade, topic) to the most likely book/chapter from imported books"""
    b = db.db.books.find_one({"grade": grade})
    if not b:
        return None, None
    ch = db.db.chapters.find_one({"book_id": b["book_id"], "title": {"$regex": topic[:6]}})
    return b["name"], (ch or {}).get("title")


def _ensure_concept(concept_id, grade, book_name, chapter_title, topic, sub):
    existing = db.db.concepts.find_one({"concept_id": concept_id})
    if existing:
        return
    order = db.db.concepts.count_documents({})
    db.db.concepts.insert_one({
        "concept_id": concept_id,
        "title": f"{sub} ({topic})",
        "grade": grade, "book_name": book_name, "chapter_title": chapter_title,
        "topic": topic, "subtopic": sub,
        "order_in_curriculum": order,
        "created_at": clock.now_utc()})


def clean_solution(text: str | None, ans_opt) -> str:
    """student-facing solution: no meta-commentary about the source answer key,
    no leftover question marks or editorial reminders, and always ends with one clear answer."""
    text = (text or "").strip()
    # drop leading «**گزینهٔ درست: N**» and standalone «حل:» headers
    text = re.sub(r"^\s*\**\s*گزینه(?:ٔ|ی)?\s*درست\s*[:：]\s*[۱-۶1-6]\s*\**\s*(?:\([^)]*\))?\s*\n*", "", text)
    text = re.sub(r"^\s*حل\s*[:：]\s*\n*", "", text)
    # drop «طبق پاسخنامه ...» and «مطابق پاسخنامه ...» clauses
    text = re.sub(r"[؛;.]?\s*\(?\s*(?:طبق|مطابق)\s*(?:پاسخنامه|پاسخ‌نامه|کتاب)[^.؛!\n]*[.؛)!]?", "", text)
    text = re.sub(r"\s*\([^)]*(?:پاسخنامه|پاسخ‌نامه|تصویر مرجع|اسکن)[^)]*\)", "", text)
    # unverified / editorial reminders are manager-only flags
    text = re.sub(r"\*?\*?پاسخ تأیید نشده\.?\*?\*?", "", text)
    text = re.sub(r"[^\n]*(?:نیازمند تأیید|تصویر مرجع|جستجو\s*شود|بازبینی تصویر|بررسی دقیق در تصویر)[^\n]*", "", text)
    text = re.sub(r"\s*\((?:اطمینان|تأیید|confidence)[^)]*\)", "", text)
    # strip trailing dangling «گزینهٔ درست» or «..» artifacts
    text = re.sub(r"(?:؛|\.)?\s*گزینه(?:ٔ|ی)?\s*(?:صحیح|درست)\s*[:：]?\s*$", "", text)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    text = re.sub(r"\s*\(\s*\)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if ans_opt is not None and not re.search(r"پاسخ درست[:：]", text):
        text = f"{text}\n\n**پاسخ درست: گزینهٔ {ans_opt}**".strip()
    if not text:
        text = "حل این سؤال به‌زودی تکمیل می‌شود."
    return text


def _difficulty_heuristic(meta: dict) -> int:
    conf = meta.get("answer_confidence")
    if meta.get("figures") or any(meta.get("option_figures") or []):
        return 4          # geometry/figure questions tend to be harder
    if conf == "low":
        return 3
    return 3              # neutral default until calibrated (§7)
