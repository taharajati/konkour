"""Rule-based checks on an extracted question. Each returns a list of problem strings."""
import re

LATIN_WORD = re.compile(r"(?<![\\$\w])[A-Za-z]{3,}(?![\w])")
PLACEHOLDER = re.compile(r"\[(?:متن|گزینه)[^\]]*استخراج نشده|\.\.\.\s*$|TODO|\?\?\?")
PERSIAN = re.compile(r"[؀-ۿ]")
OPTION_IN_SOLUTION = re.compile(r"گزینه(?:ٔ|ی)?\s*([۱-۴1-4])")
FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _outside_math(text: str) -> str:
    return re.sub(r"\$[^$]*\$", " ", text or "")


def latex_balanced(text: str) -> bool:
    t = text or ""
    if t.count("$") % 2:
        return False
    for math in re.findall(r"\$([^$]*)\$", t):
        depth = 0
        for i, ch in enumerate(math):
            if ch == "{" and (i == 0 or math[i - 1] != "\\"):
                depth += 1
            elif ch == "}" and (i == 0 or math[i - 1] != "\\"):
                depth -= 1
                if depth < 0:
                    return False
        if depth:
            return False
    return True


def check_question(q: dict) -> list:
    problems = []
    stem = q.get("stem_md", "")
    if len(stem.strip()) < 8:
        problems.append("صورت سؤال خالی یا خیلی کوتاه است")
    if PLACEHOLDER.search(stem):
        problems.append("صورت سؤال ناقص است (متن جاافتاده)")
    if not latex_balanced(stem):
        problems.append("LaTeX صورت سؤال باز و بسته نمی‌شود")
    if PERSIAN.search(stem):
        latin = [w for w in LATIN_WORD.findall(_outside_math(stem))
                 if w.lower() not in {"venn"}]
        if latin:
            problems.append(f"کلمهٔ لاتین بیرون از فرمول: {', '.join(latin[:3])}")
    if q.get("type") == "mcq":
        opts = q.get("options") or []
        if len(opts) != 4:
            problems.append(f"سؤال تستی باید ۴ گزینه داشته باشد ({len(opts)} گزینه)")
        norm = [re.sub(r"\s+", "", o) for o in opts]
        if len(set(norm)) != len(norm):
            problems.append("گزینهٔ تکراری")
        if any(not o.strip() for o in opts):
            problems.append("گزینهٔ خالی")
        if any(not latex_balanced(o) for o in opts):
            problems.append("LaTeX یکی از گزینه‌ها باز و بسته نمی‌شود")
        if not q.get("options_order_checked", False):
            problems.append("ترتیب گزینه‌ها با شمارهٔ چاپی تطبیق داده نشده")
    if not q.get("legible", True):
        problems.append("استخراج‌کننده متن را کامل نخوانده است")
    return problems


def options_named_in_solution(solution_md: str) -> set:
    """option numbers a worked solution names ("گزینهٔ ۳")"""
    return {int(m.translate(FA_DIGITS)) for m in OPTION_IN_SOLUTION.findall(solution_md or "")}


def decide(key_option: int, solver: dict | None, problems: list, qtype: str) -> tuple:
    """combine the printed key and the independent solver into (status, answer, notes).
    status:
      verified     key and solver agree, no rule problems
      conflict     key and solver disagree: a human must decide
      solver_only  no printed key; solver's answer used, needs review
      needs_fix    rule problems (text, options) even if the answer agrees
      written      written question: no option to verify
    """
    notes = []
    if qtype != "mcq":
        return ("written" if not problems else "needs_fix"), None, notes
    s_opt = (solver or {}).get("solver_option", 0)
    issues = (solver or {}).get("issues", [])
    notes += [f"حل‌کننده: {i}" for i in issues]
    if key_option and s_opt:
        if key_option != s_opt:
            notes.append(f"کلید چاپی گزینهٔ {key_option} است ولی حل مستقل گزینهٔ {s_opt} را پیدا کرد")
            return "conflict", key_option, notes
        status = "verified"
    elif key_option:
        notes.append("حل‌کننده هیچ گزینه‌ای را درست ندانست")
        return "conflict", key_option, notes
    elif s_opt:
        notes.append("کلید چاپی پیدا نشد؛ پاسخ از حل مستقل است")
        status = "solver_only"
    else:
        return "needs_fix", None, notes + ["نه کلید چاپی هست نه پاسخ حل‌کننده"]
    if problems or issues or (solver or {}).get("confidence") == "low":
        return "needs_fix", key_option or s_opt, notes
    return status, key_option or s_opt, notes
