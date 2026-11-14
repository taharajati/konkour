"""Write pipeline results into the question bank, and apply concept maps to old folders.

The bank folder is the source of truth the app imports from. This module never deletes
anything, and it never overwrites a question folder unless asked to; a folder whose
meta.json has "locked": true (edited by hand) is never touched.
"""
import json
import os
import shutil

from . import config
from .pdfwork import load_json, save_json
from .stages import paths

STATUS_TO_CONFIDENCE = {"verified": "high", "solver_only": "medium", "written": "medium"}


def _question_md(q: dict, figure_name: str | None) -> str:
    md = f"# سؤال {q['printed_number']}\n\n{q['stem_md'].strip()}\n"
    if figure_name:
        md += f"\n![شکل]({figure_name})\n"
    if q["type"] == "mcq":
        md += "\n" + "\n".join(f"{i}) {o}" for i, o in enumerate(q["options"], start=1)) + "\n"
    return md


def _answer_md(q: dict) -> tuple:
    src = (q.get("source_solution_md") or "").strip()
    solver = ((q.get("solver") or {}).get("solution_md") or "").strip()
    if src:
        text, origin = src, "printed"
    elif solver:
        text, origin = solver, "solver"
    else:
        text, origin = "", "none"
    if q.get("answer_option"):
        text = f"**گزینهٔ درست: {q['answer_option']}**\n\n{text}".strip()
    return text + "\n", origin


def write(work: str, grade: int, bank_name: str, book_id: str, id_prefix: str,
          overwrite: bool = False) -> dict:
    p = paths(work)
    qs = load_json(p["questions"], [])
    meta_src = load_json(p["blocks_json"], {})
    root = os.path.join(config.BANK_ROOT, f"grade{grade}", bank_name)
    os.makedirs(root, exist_ok=True)
    written = skipped = locked = 0
    manifest = []
    for q in qs:
        qid = f"{id_prefix}_{q['key']}"
        folder = os.path.join(root, qid)
        meta_file = os.path.join(folder, "meta.json")
        old = load_json(meta_file)
        if old and old.get("locked"):
            locked += 1; continue
        if old and not overwrite:
            skipped += 1; continue
        os.makedirs(folder, exist_ok=True)
        fig_name = None
        if q.get("figure_file"):
            fig_name = "figure.png"
            shutil.copy2(q["figure_file"], os.path.join(folder, fig_name))
        shutil.copy2(q["block_file"], os.path.join(folder, "question_shot.png"))
        with open(os.path.join(folder, "question.md"), "w", encoding="utf-8") as f:
            f.write(_question_md(q, fig_name))
        answer_text, solution_origin = _answer_md(q)
        with open(os.path.join(folder, "answer.md"), "w", encoding="utf-8") as f:
            f.write(answer_text)
        status = q.get("status", "unverified")
        solver = q.get("solver") or {}
        meta = {
            "id": qid,
            "printed_question_number": q["printed_number"],
            "grade": grade,
            "book_id": book_id,
            "concept_id": q.get("concept_id"),
            "secondary_concept_ids": q.get("secondary_concept_ids", []),
            "question_type": "multiple_choice_4" if q["type"] == "mcq" else "tashrihi",
            "options": q["options"] if q["type"] == "mcq" else None,
            "answer_option": q.get("answer_option"),
            "answer_confidence": STATUS_TO_CONFIDENCE.get(status, "low"),
            "needs_answer_verification": status not in ("verified", "written"),
            "difficulty": q.get("difficulty"),
            "points": q.get("points") or None,
            "figures": [fig_name] if fig_name else [],
            "question_screenshot": "question_shot.png",
            "source": {"pdf": os.path.basename(meta_src.get("pdf", "")),
                       "blocks": q["blocks"], "note": q.get("source_note") or None},
            "verification": {
                "status": status,
                "key_option": q.get("key_option") or None,
                "solver_option": solver.get("solver_option") or None,
                "solver_confidence": solver.get("confidence"),
                "notes": (q.get("problems") or []) + (q.get("verify_notes") or []),
                "solution_origin": solution_origin,
            },
            "pipeline": {"prompt_version": config.PROMPT_VERSION,
                         "extract_model": config.EXTRACT_MODEL,
                         "solver_model": config.SOLVER_MODEL,
                         "tag_model": config.TAG_MODEL},
            "latex_enabled": True,
        }
        save_json(meta_file, meta)
        manifest.append({"id": qid, "status": status, "concept_id": meta["concept_id"]})
        written += 1
    save_json(os.path.join(root, "manifest.json"),
              {"source_work": os.path.abspath(work), "questions": manifest})
    return {"written": written, "skipped_existing": skipped, "locked": locked, "folder": root}


def apply_map(bank_folder: str, map_file: str) -> dict:
    """write concept_id / secondary_concept_ids from a mapping file into meta.json files"""
    with open(map_file, encoding="utf-8") as f:
        m = json.load(f)
    prefix = m.get("prefix", "")
    done = unmapped = missing = 0
    for qid, ids in m["map"].items():
        meta_file = os.path.join(bank_folder, qid, "meta.json")
        meta = load_json(meta_file)
        if meta is None:
            missing += 1; continue
        if ids:
            meta["concept_id"] = prefix + ids[0]
            meta["secondary_concept_ids"] = [prefix + x for x in ids[1:]]
            done += 1
        else:
            meta["concept_id"] = None
            meta["secondary_concept_ids"] = []
            unmapped += 1
        save_json(meta_file, meta)
    return {"mapped": done, "unmapped": unmapped, "missing_folders": missing}
