"""Pipeline stages. Each stage writes its result into the work folder, so stages can be
re-run one at a time and every intermediate result can be inspected."""
import os

from . import checks, config, prompts, taxonomy
from .pdfwork import crop_fraction, cut_blocks, load_json, render_pages, save_json


def paths(work: str) -> dict:
    return {k: os.path.join(work, v) for k, v in {
        "pages": "pages", "blocks": "blocks", "figures": "figures", "llm": "llm_cache",
        "blocks_json": "blocks.json", "extracted": "extracted.json",
        "questions": "questions.json", "report": "report.md"}.items()}


# ------------------------------------------------------------------ offline stages

def prepare(pdf: str, work: str) -> list:
    p = paths(work)
    pages = render_pages(pdf, p["pages"], config.RENDER_DPI)
    blocks = cut_blocks(pages, p["blocks"])
    save_json(p["blocks_json"], {"pdf": os.path.abspath(pdf), "pages": len(pages),
                                 "blocks": blocks})
    return blocks


def estimate(blocks: list, n_questions_guess: int | None = None) -> dict:
    """rough call count and token/cost estimate, printed before any paid call"""
    nq = n_questions_guess or max(1, int(len(blocks) * 1.5))
    calls = len(blocks) + 2 * nq             # extract per block, solve + tag per question
    tok_in = len(blocks) * 2500 + nq * (1500 + 2500)
    tok_out = len(blocks) * 1500 + nq * (2500 + 300)
    # claude-opus-5-5: $4 / MTok in, $20 / MTok out (thinking tokens bill as output)
    usd = tok_in / 1e6 * 4 + tok_out / 1e6 * 20
    return {"blocks": len(blocks), "questions_guess": nq, "calls": calls,
            "input_tokens": tok_in, "output_tokens": tok_out, "usd": round(usd, 2)}


# ------------------------------------------------------------------ LLM stages

def extract(llm, work: str) -> list:
    p = paths(work)
    meta = load_json(p["blocks_json"])
    out = []
    for b in meta["blocks"]:
        with open(b["file"], "rb") as f:
            png = f.read()
        res = llm.generate_json(
            f"extract {b['id']}", prompts.EXTRACT_SYSTEM,
            [{"image_png": png},
             {"text": prompts.EXTRACT_USER.format(page=b["page"], pages=meta["pages"],
                                                  block=b["id"])}],
            prompts.EXTRACT_SCHEMA, config.EXTRACT_MODEL, config.EXTRACT_EFFORT)
        out.append({"block": b, "result": res})
    save_json(p["extracted"], out)
    return out


def assemble(work: str) -> list:
    """merge per-block results into one list of questions with their printed answers"""
    p = paths(work)
    extracted = load_json(p["extracted"], [])
    questions, answers = [], {}
    for item in extracted:
        b, res = item["block"], item["result"]
        for a in res.get("answers", []):
            answers.setdefault(a["printed_number"], []).append(a)
        for q in res.get("questions", []):
            prev = questions[-1] if questions else None
            if q.get("continues_from_previous") and prev and \
                    q.get("printed_number") in (0, prev["printed_number"]):
                prev["stem_md"] = (prev["stem_md"] + "\n\n" + q["stem_md"]).strip()
                if q.get("options"):
                    prev["options"] = q["options"]
                prev["blocks"].append(b["id"])
                continue
            q = dict(q)
            q["blocks"] = [b["id"]]
            q["block_file"] = b["file"]
            questions.append(q)
    # stable keys: printed number, with a suffix if a number repeats
    seen = {}
    for q in questions:
        n = q["printed_number"]
        seen[n] = seen.get(n, 0) + 1
        q["key"] = f"q{n:03d}" + ("" if seen[n] == 1 else f"_{seen[n]}")
        got = answers.get(n, []) if n else []
        q["key_option"] = next((a["option"] for a in got if a["option"]), 0)
        q["source_solution_md"] = next((a["solution_md"] for a in got if a["solution_md"].strip()), "")
        q["problems"] = checks.check_question(q)
        named = checks.options_named_in_solution(q["source_solution_md"])
        if q["key_option"] and named and q["key_option"] not in named:
            q["problems"].append(f"حل چاپی به گزینهٔ {sorted(named)} اشاره می‌کند ولی کلید {q['key_option']} است")
        if q.get("has_figure") and len(q.get("figure_bbox") or []) == 4:
            fig = os.path.join(p["figures"], f"{q['key']}.png")
            os.makedirs(p["figures"], exist_ok=True)
            with open(fig, "wb") as f:
                f.write(crop_fraction(q["block_file"], q["figure_bbox"]))
            q["figure_file"] = fig
        elif q.get("has_figure"):
            q["problems"].append("سؤال شکل دارد ولی محل شکل مشخص نشد")
    save_json(p["questions"], questions)
    return questions


def _question_text(q: dict) -> str:
    parts = [q["stem_md"]]
    for i, o in enumerate(q.get("options") or [], start=1):
        parts.append(f"{i}) {o}")
    return "\n".join(parts)


def solve(llm, work: str) -> list:
    p = paths(work)
    questions = load_json(p["questions"], [])
    for q in questions:
        content = [{"text": "سؤال:\n" + _question_text(q)}]
        if q.get("figure_file"):
            with open(q["figure_file"], "rb") as f:
                content.insert(0, {"image_png": f.read()})
        q["solver"] = llm.generate_json(f"solve {q['key']}", prompts.SOLVE_SYSTEM, content,
                                        prompts.SOLVE_SCHEMA, config.SOLVER_MODEL,
                                        config.SOLVER_EFFORT)
        q["status"], q["answer_option"], q["verify_notes"] = checks.decide(
            q["key_option"], q["solver"], q["problems"], q["type"])
    save_json(p["questions"], questions)
    return questions


def tag(llm, work: str, book_id: str, chapters: list | None) -> list:
    p = paths(work)
    questions = load_json(p["questions"], [])
    concepts = taxonomy.concepts_for(book_id, chapters)
    lessons = taxonomy.lesson_index(taxonomy.load_catalog())
    listing = "\n".join(
        f"{c['id']}: {c['title']} (درس: {lessons.get(c['lesson_id'], {}).get('lesson', {}).get('title', '')})"
        for c in concepts)
    schema = prompts.tag_schema([c["id"] for c in concepts])
    for q in questions:
        res = llm.generate_json(
            f"tag {q['key']}", prompts.TAG_SYSTEM,
            [{"text": f"فهرست مفهوم‌ها:\n{listing}\n\nسؤال:\n{_question_text(q)}"}],
            schema, config.TAG_MODEL, config.TAG_EFFORT)
        q["concept_id"] = None if res["primary"] == "none" else res["primary"]
        q["secondary_concept_ids"] = [c for c in res["secondary"]
                                      if c != "none" and c != q["concept_id"]]
        q["difficulty"] = res["difficulty"]
        q["tag_reason"] = res["reason"]
        if not q["concept_id"]:
            q.setdefault("problems", []).append("هیچ مفهومی از فهرست به این سؤال نخورد")
    save_json(p["questions"], questions)
    return questions


# ------------------------------------------------------------------ report

def report(work: str) -> str:
    p = paths(work)
    qs = load_json(p["questions"], [])
    counts = {}
    for q in qs:
        counts[q.get("status", "unverified")] = counts.get(q.get("status", "unverified"), 0) + 1
    per_concept = {}
    for q in qs:
        if q.get("concept_id"):
            per_concept[q["concept_id"]] = per_concept.get(q["concept_id"], 0) + 1
    keys = [q.get("answer_option") for q in qs if q.get("answer_option")]
    dist = {k: keys.count(k) for k in sorted(set(keys))}
    lines = [f"# گزارش پایپ‌لاین: {os.path.basename(work)}", "",
             f"- تعداد سؤال: {len(qs)}",
             f"- وضعیت‌ها: {counts}",
             f"- توزیع کلیدها: {dist}", "", "## مفهوم‌ها", ""]
    lines += [f"- {c}: {n}" for c, n in sorted(per_concept.items())]
    lines += ["", "## سؤال‌هایی که بازبینی می‌خواهند", ""]
    for q in qs:
        if q.get("status") in ("verified", "written") and not q.get("problems"):
            continue
        notes = (q.get("problems") or []) + (q.get("verify_notes") or [])
        lines.append(f"- **{q['key']}** ({q.get('status', '?')}): " + "؛ ".join(notes))
    text = "\n".join(lines) + "\n"
    with open(p["report"], "w", encoding="utf-8") as f:
        f.write(text)
    return text
