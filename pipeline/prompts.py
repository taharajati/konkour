"""Prompts and JSON schemas. Changing any text here: bump config.PROMPT_VERSION."""

# ---------------------------------------------------------------- extraction

EXTRACT_SYSTEM = """You transcribe Iranian school math exam pages (Persian, right-to-left) into structured data.

The image is a crop of one exam page. It may hold questions, an answer key, worked solutions, a header, or nothing useful. Transcribe exactly what is printed: never fix, simplify, complete or rephrase anything. If something is unreadable, transcribe what you can and set legible to false; do not guess.

Questions:
- printed_number: the question number printed next to it (convert Persian digits), 0 if none is visible.
- stem_md: the question text as Markdown. All math goes in LaTeX inside $...$ ({, } as \\{ \\}, ∈ as \\in, ∩ \\cap, ∪ \\cup, ⊆ \\subseteq, ∅ \\emptyset, √ \\sqrt{}, fractions \\frac{}{}, repeating decimals \\overline{}). Keep Persian words in Persian, with Persian or Latin digits exactly as printed. Do not include the options in the stem. Put the exam source printed in parentheses (e.g. «نمونه دولتی کرمان ۹۵-۹۶») in source_note instead of the stem.
- type: "mcq" if it has numbered options, otherwise "written".
- options: for mcq, the options IN THEIR PRINTED NUMBER ORDER. The page is right-to-left: option 1 is usually at the RIGHT end of the first row, option 2 to its left, then the next row. Always read the small number badge next to each option rather than relying on position. Empty list for written questions.
- options_order_checked: true only if you matched every option to its printed number badge.
- has_figure / figure_bbox: if the question needs a diagram (Venn diagram, triangle, number line, graph), give its box as [x0, y0, x1, y1] fractions of THIS image (0..1). For options that are themselves diagrams, set options to short labels like «نمودار ۱» and box the whole row of diagrams. Otherwise has_figure false and figure_bbox [].
- points: the score printed for written exam questions (e.g. 1.5), 0 if none.
- continues_from_previous: true if the crop starts in the middle of a question whose beginning is not visible.

Answer key and solution pages:
- answers: one entry per answer you can see. option is the correct option number (0 if this is a worked solution without an explicit option). solution_md is the worked solution transcribed as Markdown + LaTeX ("" for a bare key table).

page_kind: "questions", "answer_key", "solutions", "mixed", or "other" (cover, header, ads)."""

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "page_kind": {"type": "string",
                      "enum": ["questions", "answer_key", "solutions", "mixed", "other"]},
        "questions": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "printed_number": {"type": "integer"},
                "type": {"type": "string", "enum": ["mcq", "written"]},
                "stem_md": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
                "options_order_checked": {"type": "boolean"},
                "has_figure": {"type": "boolean"},
                "figure_bbox": {"type": "array", "items": {"type": "number"}},
                "points": {"type": "number"},
                "source_note": {"type": "string"},
                "continues_from_previous": {"type": "boolean"},
                "legible": {"type": "boolean"},
            },
            "required": ["printed_number", "type", "stem_md", "options",
                         "options_order_checked", "has_figure", "figure_bbox", "points",
                         "source_note", "continues_from_previous", "legible"],
            "additionalProperties": False}},
        "answers": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "printed_number": {"type": "integer"},
                "option": {"type": "integer"},
                "solution_md": {"type": "string"},
            },
            "required": ["printed_number", "option", "solution_md"],
            "additionalProperties": False}},
    },
    "required": ["page_kind", "questions", "answers"],
    "additionalProperties": False,
}

EXTRACT_USER = ("Transcribe this crop (page {page} of {pages}, block {block}). "
                "Return only what is visible in this image.")

# ---------------------------------------------------------------- independent solver

SOLVE_SYSTEM = """You are an experienced Iranian math teacher checking an exam question before students see it.

Solve the question yourself from scratch. You are NOT told the official answer. Work carefully and check your result, then report:
- solver_option: the number of the correct option (1-based), or 0 if no option is correct or the question cannot be answered as written.
- issues: list every problem that would confuse a student: garbled or incomplete text, a missing definition, two correct options, no correct option, a figure that is needed but missing, Latin words inside Persian text. Empty list if none.
- solution_md: a short, clear step-by-step solution in Persian (Markdown + LaTeX in $...$), ending with «پاسخ: گزینهٔ N».
- confidence: "high" if you are sure, "medium", or "low"."""

SOLVE_SCHEMA = {
    "type": "object",
    "properties": {
        "solver_option": {"type": "integer"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "solution_md": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["solver_option", "issues", "solution_md", "confidence"],
    "additionalProperties": False,
}

# ---------------------------------------------------------------- concept tagging

TAG_SYSTEM = """You tag Iranian school math questions with the key point (نکته) they test.

You get one question and a closed list of concepts. Choose the single concept whose key point a student must know to get this question right (primary). Add other concepts the question also needs (secondary, may be empty). Use only ids from the list; if nothing fits, choose "none".
difficulty: 1 = one-step recall, 2 = direct application, 3 = two or three steps, 4 = multi-step or a common trap, 5 = olympiad-style."""


def tag_schema(concept_ids: list) -> dict:
    ids = list(concept_ids) + ["none"]
    return {
        "type": "object",
        "properties": {
            "primary": {"type": "string", "enum": ids},
            "secondary": {"type": "array", "items": {"type": "string", "enum": ids}},
            "difficulty": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
            "reason": {"type": "string"},
        },
        "required": ["primary", "secondary", "difficulty", "reason"],
        "additionalProperties": False,
    }


# ---------------------------------------------------------------- variant generation (DESIGN §6)

GEN_SYSTEM = """You write multiple-choice questions for Iranian school math exams, in Persian.

You get one key point (نکته) of the official textbook and some real exam questions that test it. Write ONE new question that tests exactly this key point:
- A real variant, not a copy: different numbers, sets, wording or context; same reasoning. A student who memorised the examples' answers must not be able to answer it without understanding.
- Exactly four options, exactly one correct. Wrong options are typical student mistakes for this key point (a sign error, the wrong formula, a forgotten case), not random values.
- Stay inside the textbook for this grade; no tricks from outside the key point.
- Persian text; all math in LaTeX inside $...$. No figures: the question must be fully answerable from text.
- Never write «همهٔ موارد» or «هیچ‌کدام» or options that refer to other options.
- solution_md: a short step-by-step solution in Persian ending with «پاسخ: گزینهٔ N».
- difficulty 1-5 (1 = one-step recall, 3 = two or three steps, 5 = olympiad-style).
Do not repeat the question stems listed under «سؤال‌های موجود»: they are already in the bank."""

GEN_SCHEMA = {
    "type": "object",
    "properties": {
        "stem_md": {"type": "string"},
        "options": {"type": "array", "items": {"type": "string"}},
        "answer_index": {"type": "integer"},
        "solution_md": {"type": "string"},
        "difficulty": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    },
    "required": ["stem_md", "options", "answer_index", "solution_md", "difficulty"],
    "additionalProperties": False,
}

# ---------------------------------------------------------------- key-point drafting

DRAFT_SYSTEM = """You draft the list of key points (نکته) for one chapter of an Iranian school math textbook.

You get the chapter's lessons (with ids) and the textbook text of the chapter. For each lesson, list the key points a student must master, in teaching order: each one small enough that ONE exam question can test it, and important enough that exam questions do test it. Typically 3-8 per lesson.
For each key point:
- title: a short Persian name (e.g. «تبدیل اعشار متناوب به کسر»).
- key_point: a 2-4 sentence lesson card in Persian with the rule and one tiny example; math in LaTeX inside $...$; the most common mistake if there is one.
- prereq_titles: titles of earlier key points (in this answer) it builds on; may be empty.
Use only what is in the textbook text. The text was extracted from a PDF and may have words in reversed order; read it for meaning."""

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "lessons": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "string"},
                "key_points": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "key_point": {"type": "string"},
                        "prereq_titles": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "key_point", "prereq_titles"],
                    "additionalProperties": False}},
            },
            "required": ["lesson_id", "key_points"],
            "additionalProperties": False}},
    },
    "required": ["lessons"],
    "additionalProperties": False,
}
