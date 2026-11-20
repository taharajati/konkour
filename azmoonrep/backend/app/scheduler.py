"""Repetition engine: concept state updates (DESIGN §5.1), the daily queue (§5.2),
question selection (§5.3), same-day remediation (§5.4) and practice mode (§11.4).

Rules that matter for "learn every key point with the fewest questions":
- One scheduled review per concept per day. A second correct answer the same day, or
  a correct answer before the concept is due (weak-concept reinforcement), is counted
  but does not move the concept up the 1 -> 3 -> 7 day ladder: only spaced success
  counts as evidence of memory.
- A wrong answer always counts (once per day), whenever it happens.
- Mastered concepts are not dropped: they come back for a maintenance check at most
  every MAX_INTERVAL days, and a miss there demotes them.
- Days are Tehran days (see clock.py).
"""
import datetime as dt
import random
import re

from pymongo.errors import DuplicateKeyError

from . import clock, db
from .config import DEFAULT_DAILY_LOAD

SERVABLE = {"review_status": "approved"}   # students only ever see manager-approved questions
MAX_INTERVAL = 90.0     # days; also the maintenance-check period for mastered concepts
WEAK_RECENT_DAYS = 7
MAX_WEAK = 3
SEEN_BUFFER = 30

# ---------------------------------------------------------------- concept state (§5.1)


def due_day(st: dict) -> str:
    """Tehran day the concept is due ("YYYY-MM-DD"); older states only have due_date"""
    if st.get("due_day"):
        return st["due_day"]
    d = st.get("due_date")
    if isinstance(d, dt.datetime):
        return clock.day_of(d).isoformat()
    return clock.today_str()


def mastery_level(st: dict) -> int:
    if st["streak"] >= 3 and st["interval_days"] >= 21:
        return 3
    if st["streak"] >= 2 and st["interval_days"] >= 7:
        return 2
    if st["total_answers"] >= 1:
        return 1
    return 0


IDLE_MS = 180_000    # beyond 3 minutes the tab was probably left open: the time says nothing


def _grade_of(correct: bool, time_ms: int, expected_ms: int) -> str:
    if not correct:
        return "again"
    return "hard" if 2 * max(expected_ms, 1) < time_ms <= IDLE_MS else "good"


def update_concept_state(student_id, concept_id, correct: bool, time_ms: int, expected_ms: int,
                         scheduled: bool = True) -> dict:
    """scheduled: the slot was a due review or a first-time concept (not reinforcement
    or remediation). Returns the new state."""
    today = clock.today()
    today_s = today.isoformat()
    now = clock.now_utc()
    st = db.db.concept_state.find_one({"student_id": student_id, "concept_id": concept_id})
    first_time = st is None
    if first_time:
        st = {"ease": 2.5, "interval_days": 0.0, "streak": 0, "lapses": 0,
              "total_answers": 0, "total_correct": 0, "mastery_level": 0}

    grade = _grade_of(correct, time_ms, expected_ms)
    prior_interval = st["interval_days"]
    reviewed_today = st.get("last_review_day") == today_s
    is_due = first_time or due_day(st) <= today_s

    if grade == "again":
        # a miss always counts, but only once per day
        apply = not (reviewed_today and st.get("last_grade") == "again")
    else:
        apply = scheduled and is_due and not reviewed_today

    if apply:
        ease, interval, streak = st["ease"], st["interval_days"], st["streak"]
        if grade == "again":
            streak = 0
            st["lapses"] += 1
            ease = max(1.3, ease - 0.2)
            interval = 1.0
        elif grade == "hard":
            # slow but right: stay on the same rung of the ladder (a streak step without the
            # matching interval would let the next success skip the 3-day check)
            ease = max(1.3, ease - 0.05)
            interval = max(1.0, interval)
        else:
            streak += 1
            ease = min(3.2, ease + 0.1)
            interval = {1: 1.0, 2: 3.0, 3: 7.0}.get(streak, interval * ease)
        interval = min(MAX_INTERVAL, interval)
        due = today + dt.timedelta(days=max(1, round(interval)))
        st.update({"ease": ease, "interval_days": interval, "streak": streak,
                   "due_day": due.isoformat(),
                   "due_date": dt.datetime.combine(due, dt.time()),   # legacy readers
                   "last_review_day": today_s, "last_grade": grade})

    st["total_answers"] += 1
    st["total_correct"] += 1 if correct else 0
    st["last_answer_day"] = today_s
    st["mastery_level"] = mastery_level(st)
    if st["mastery_level"] >= 2 and "answers_to_first_pass" not in st:
        st["answers_to_first_pass"] = st["total_answers"]      # old definition, kept to compare
    if apply and correct and prior_interval >= 7 and "answers_to_learned" not in st:
        # product metric: questions needed until the student answered correctly after a gap
        # of 7+ days (the 3- and 7-day checks survived), not just until the ladder said so
        st["answers_to_learned"] = st["total_answers"]
        st["learned_day"] = today_s
    st["updated_at"] = now
    # never $set seen_question_ids here: it is $push-ed separately and must not be
    # overwritten with a stale copy
    fields = {k: v for k, v in st.items()
              if k not in ("_id", "student_id", "concept_id", "seen_question_ids")}
    db.db.concept_state.update_one(
        {"student_id": student_id, "concept_id": concept_id},
        {"$set": fields, "$setOnInsert": {"seen_question_ids": []}}, upsert=True)
    st["applied"] = apply
    st["prior_interval"] = prior_interval
    return st


def key_point(concept_id: str) -> dict | None:
    """the key point's short lesson card (taxonomy key_point), if it has one"""
    c = db.db.concepts.find_one({"concept_id": concept_id}, {"title": 1, "key_point": 1})
    if not c or not c.get("key_point"):
        return None
    return {"title": c["title"], "text": c["key_point"]}

CALIBRATION_MIN_N = 20  # DESIGN §7: switch to empirical difficulty/time after >=20 responses

# ---------------------------------------------------------------- option order (§11.7)

POSITIONAL = re.compile(r"(همه|هیچ|گزینه|موارد|هر\s*دو|نمودار\s*[۱-۶1-6]|شکل\s*[۱-۶1-6]|الف\s*\)|ب\s*\)|پ\s*\)|ج\s*\)|د\s*\)|ت\s*\))")
# «گزینهٔ ۲»، «گزینه‌های ۱ و ۳»، «گزینهٔ درست: ۲»، «گزینه (۲)»
OPTION_REF_SINGLE = re.compile(r"(گزینه(?:ٔ|ی|‌ی)?\s*(?:درست\s*[:：]?\s*)?\(?)\s*([۱-۶1-6])(\)?)")
OPTION_REF_LIST = re.compile(r"(گزینه(?:‌های|های)\s*)([۱-۶1-6](?:\s*(?:،|,|و)\s*[۱-۶1-6])+)")
FA = "۰۱۲۳۴۵۶۷۸۹"


def can_shuffle(q: dict) -> bool:
    """options like «همهٔ موارد» or «گزینه‌های ۱ و ۲» point at positions: keep order"""
    opts = q.get("options") or []
    if q.get("type", "multiple_choice_4") != "multiple_choice_4" or len(opts) < 2:
        return False
    return not any(POSITIONAL.search(o or "") for o in opts)


def make_perm(q: dict) -> list | None:
    """perm[i] = original (1-based) option shown at display position i+1"""
    opts = q.get("options") or []
    if not opts:
        return None
    perm = list(range(1, len(opts) + 1))
    if can_shuffle(q):
        random.shuffle(perm)
    return perm


def figure_view(public_id: str, f) -> dict | None:
    """a stored figure ({file, w, h}; plain file name in older documents) as the client
    sees it: url plus pixel size, so the page can reserve its box before it loads"""
    if not f:
        return None
    if isinstance(f, str):
        f = {"file": f}
    return {"url": f"/static/questions/{public_id}/{f['file']}", "w": f.get("w"), "h": f.get("h")}


def question_figures(q: dict, perm: list | None = None) -> dict:
    """figures of a question for display. option_figures follow the slot's option order."""
    pid = q.get("public_id")
    of = q.get("option_figures")
    if of and perm and len(perm) == len(of):
        of = [of[p - 1] for p in perm]
    return {"figures": [figure_view(pid, f) for f in q.get("figures") or []],
            "option_figures": [figure_view(pid, f) for f in of] if of else None}


def display_options(q: dict, perm: list | None) -> list | None:
    opts = q.get("options")
    if not opts or not perm:
        return opts
    return [opts[p - 1] for p in perm]


def to_original(display_opt, perm):
    if not perm or isinstance(display_opt, bool) or not isinstance(display_opt, int):
        return display_opt
    if display_opt == 0 or not 1 <= display_opt <= len(perm):
        return display_opt               # 0 = «نمی‌دانم»; out of range fails in grade()
    return perm[display_opt - 1]


def to_display(original_opt, perm):
    if not perm or original_opt is None or original_opt not in perm:
        return original_opt
    return perm.index(original_opt) + 1


def remap_solution(text: str | None, perm: list | None) -> str | None:
    """«گزینهٔ ۲» or «گزینه‌های ۱ و ۳» in a solution refers to the original order:
    renumber for this student's shuffled display order."""
    if not text or not perm:
        return text

    def _map_digit(d: str) -> str:
        n = int(d.translate(str.maketrans(FA, "0123456789")))
        if not 1 <= n <= len(perm):
            return d
        shown = to_display(n, perm)
        return FA[shown] if d in FA else str(shown)

    def repl_list(m):
        body = re.sub(r"[۱-۶1-6]", lambda dm: _map_digit(dm.group(0)), m.group(2))
        return m.group(1) + body

    def repl_single(m):
        return m.group(1) + _map_digit(m.group(2)) + m.group(3)

    text = OPTION_REF_LIST.sub(repl_list, text)
    return OPTION_REF_SINGLE.sub(repl_single, text)

# ---------------------------------------------------------------- daily queue (§5.2)


def _concept_index() -> dict:
    return {c["concept_id"]: c for c in db.db.concepts.find(
        {}, {"concept_id": 1, "book_id": 1, "chapter_id": 1, "lesson_id": 1,
             "prereq_ids": 1, "order_in_curriculum": 1, "retired": 1})}


def _servable_counts() -> dict:
    return {r["_id"]: r["n"] for r in db.db.questions.aggregate([
        {"$match": SERVABLE}, {"$group": {"_id": "$concept_id", "n": {"$sum": 1}}}])}


def build_daily_queue(student: dict, load: int | None = None, book_id: str | None = None,
                      chapter_id: str | None = None):
    student_id = student["_id"]
    today_s = clock.today_str()
    key = {"student_id": student_id, "date": today_s, "book_id": book_id,
           "chapter_id": chapter_id}
    existing = db.db.sessions.find_one(key)
    if existing:
        return existing

    load = load or student.get("daily_load") or DEFAULT_DAILY_LOAD
    concepts = _concept_index()
    servable = _servable_counts()
    scope_chapters = set(student.get("scope_chapter_ids") or [])
    scope_books = set(student.get("scope_book_ids") or [])

    def in_scope(cid):
        c = concepts.get(cid)
        if not c or c.get("retired"):
            return False
        if chapter_id and c.get("chapter_id") != chapter_id:
            return False
        if book_id and c.get("book_id") != book_id:
            return False
        if not scope_chapters and not scope_books:
            return True
        if c.get("chapter_id"):
            return c["chapter_id"] in scope_chapters
        return c.get("book_id") in scope_books

    # concepts and questions already in today's other sessions (per-book / per-chapter
    # sessions): never serve the same concept or question twice in one day
    used_concepts, used_qids = set(), set()
    for s in db.db.sessions.find({"student_id": student_id, "date": today_s}):
        for sl in s["slots"]:
            used_concepts.add(sl["concept_id"]); used_qids.add(sl["question_id"])

    trial_seen = student.get("trial_seen") or {}
    if trial_seen.get("day") == today_s:
        used_qids |= set(trial_seen.get("question_ids") or [])

    states = {s["concept_id"]: s for s in db.db.concept_state.find({"student_id": student_id})}
    candidates = [s for cid, s in states.items()
                  if in_scope(cid) and cid not in used_concepts]

    # 1. due (mastered concepts included: that is their maintenance check)
    due = [s for s in candidates if due_day(s) <= today_s]
    due.sort(key=lambda s: (due_day(s), -s.get("lapses", 0)))
    due_ids = [s["concept_id"] for s in due]

    # 2. weak: still learning, practised in the last week but not today, not yet due
    recent = (clock.today() - dt.timedelta(days=WEAK_RECENT_DAYS)).isoformat()
    weak = [s for s in candidates
            if s.get("mastery_level") == 1 and s["concept_id"] not in due_ids
            and recent <= (s.get("last_answer_day") or "") < today_s]
    weak.sort(key=lambda s: due_day(s))
    weak_ids = [s["concept_id"] for s in weak[:MAX_WEAK]]

    # 3. new: curriculum order, prerequisites met, only concepts with approved questions
    new_ids = []
    for cid, c in sorted(concepts.items(), key=lambda kv: kv[1].get("order_in_curriculum", 0)):
        if cid in states or cid in used_concepts or not in_scope(cid) or not servable.get(cid):
            continue
        prereqs_ok = all(p in states or p in new_ids or not servable.get(p)
                         for p in c.get("prereq_ids") or [])
        if not prereqs_ok:
            continue
        new_ids.append(cid)
        if len(new_ids) >= load:
            break

    review_pool = [(cid, "review") for cid in due_ids] + [(cid, "weak") for cid in weak_ids]
    # Reserve ~20% for new concepts, but never starve due reviews on small loads (load>=2 -> >=1 review)
    overdue_count = sum(1 for cid in due_ids if due_day(states[cid]) < today_s)
    if not review_pool:
        n_new = min(len(new_ids), load)
    else:
        min_new = max(1, round(load * 0.2)) if load <= 4 else max(2, round(load * 0.2))
        max_for_new = max(0, load - max(1 if due_ids else 0, min(overdue_count, load)))
        n_new = min(len(new_ids), min_new, max_for_new)
    n_review = load - n_new

    slots, in_queue, picked = [], set(), set(used_qids)
    lesson_of = {cid: c.get("lesson_id") for cid, c in concepts.items()}

    def add(cid, kind, q, repeat):
        in_queue.add(cid); picked.add(q["_id"])
        slots.append({"concept_id": cid, "question_id": q["_id"], "kind": kind,
                      "scheduled": kind in ("review", "new"), "repeat": repeat,
                      "overdue": kind == "review" and cid in states and due_day(states[cid]) < today_s,
                      "perm": make_perm(q), "status": "pending"})

    # one slot per concept per day (§5.2 rule 5, tightened)
    for cid, kind in review_pool:
        if len(slots) >= n_review:
            break
        q, repeat = pick_question(student_id, cid, exclude_ids=picked)
        if q is None:
            continue
        if repeat:
            # Never skip an actually due/overdue review with a sibling swap — otherwise its due_day
            # never advances and it becomes permanently stuck. Only weak reinforcement slots swap.
            if kind == "weak":
                sib = _sibling_question(student_id, cid, lesson_of, states, in_queue | used_concepts,
                                        picked, in_scope)
                if sib:
                    scid, sq = sib
                    add(scid, "review" if scid in states else "new", sq, False)
                    continue
        add(cid, kind, q, repeat)

    # Top up remaining capacity with new concepts if review_pool was smaller than n_review
    for cid in new_ids:
        if len(slots) >= load:
            break
        if cid in in_queue:
            continue
        q, repeat = pick_question(student_id, cid, exclude_ids=picked)
        if q is not None:
            add(cid, "new", q, repeat)

    # If still under load (e.g. few new concepts), fill from remaining due/weak reviews
    if len(slots) < load:
        for cid, kind in review_pool:
            if len(slots) >= load:
                break
            if cid in in_queue:
                continue
            q, repeat = pick_question(student_id, cid, exclude_ids=picked)
            if q is not None:
                add(cid, kind, q, repeat)

    # order: overdue reviews (shuffled), other reviews (shuffled), then new key points in
    # curriculum order: a new point may build on the one taught just before it
    first = [s for s in slots if s["overdue"]]
    reviews = [s for s in slots if not s["overdue"] and s["kind"] != "new"]
    new = [s for s in slots if s["kind"] == "new"]
    random.shuffle(first); random.shuffle(reviews)
    order = {cid: i for i, cid in enumerate(new_ids)}
    new.sort(key=lambda s: order.get(s["concept_id"], len(order)))
    slots = first + reviews + new

    doc = {**key, "created_at": clock.now_utc(), "slots": slots}
    try:
        db.db.sessions.insert_one(doc)
    except DuplicateKeyError:
        pass        # a concurrent request built it first: use that one
    return db.db.sessions.find_one(key)


def _sibling_question(student_id, cid, lesson_of, states, taken, picked, in_scope):
    lesson = lesson_of.get(cid)
    if not lesson:
        return None
    for scid, slesson in lesson_of.items():
        if slesson != lesson or scid == cid or scid in taken or not in_scope(scid):
            continue
        if states.get(scid, {}).get("mastery_level", 0) >= 2:
            continue
        q, repeat = pick_question(student_id, scid, exclude_ids=picked)
        if q is not None and not repeat:
            return scid, q
    return None


def pick_question(student_id, concept_id, exclude_ids=None):
    """unseen approved question nearest to the target difficulty (§5.3).
    Returns (question, is_repeat) or (None, False). exclude_ids are never returned,
    even as a repeat (they are already in today's queue)."""
    st = db.db.concept_state.find_one({"student_id": student_id, "concept_id": concept_id})
    exclude = set(exclude_ids or [])
    seen = set((st or {}).get("seen_question_ids", []) or [])
    qs = [q for q in db.db.questions.find({"concept_id": concept_id, **SERVABLE})
          if q["_id"] not in exclude and _has_key(q)]
    if not qs:
        return None, False
    # questions already answered in free practice have shown their key: prefer fresh ones
    practiced = {r["question_id"] for r in db.db.responses.find(
        {"student_id": student_id, "concept_id": concept_id, "context": "practice"},
        {"question_id": 1})}
    unseen = [q for q in qs if q["_id"] not in seen and q["_id"] not in practiced] \
        or [q for q in qs if q["_id"] not in seen]
    if unseen:
        level = (st or {}).get("mastery_level", 0)
        target = {0: 1, 1: 2, 2: 3, 3: 4}.get(level, 3)
        if (st or {}).get("streak", 0) == 0:
            target = max(1, target - 1)   # struggling student: easier variant
        unseen.sort(key=lambda q: (abs(effective_difficulty(q) - target),
                                   0 if q.get("source", "bank") == "bank" else 1,
                                   random.random()))
        return unseen[0], False
    # every question seen: the least recently seen one (front of the ring buffer)
    order = {qid: i for i, qid in enumerate((st or {}).get("seen_question_ids", []))}
    qs.sort(key=lambda q: order.get(q["_id"], -1))
    return qs[0], True


def _has_key(q: dict) -> bool:
    if q.get("type", "multiple_choice_4") != "multiple_choice_4":
        return True
    return (q.get("answer") or {}).get("option") is not None

# ---------------------------------------------------------------- grading


def effective_difficulty(question: dict) -> int:
    """empirical difficulty overrides heuristic once calibrated (DESIGN §7)"""
    emp = question.get("empirical_difficulty")
    if isinstance(emp, (int, float)) and 1 <= emp <= 5:
        return int(round(emp))
    return int(question.get("difficulty") or 3)


def expected_time(question: dict) -> int:
    emp_ms = question.get("median_time_ms")
    if isinstance(emp_ms, (int, float)) and 5_000 <= emp_ms <= 300_000:
        return int(emp_ms)
    if question.get("type") == "tashrihi":
        return 90_000
    return {1: 25_000, 2: 30_000, 3: 40_000, 4: 55_000, 5: 75_000}.get(
        effective_difficulty(question), 40_000)


def maybe_calibrate_question(question_id) -> dict | None:
    """After >= CALIBRATION_MIN_N responses, compute empirical difficulty (1=easy..5=hard)
    and median solve time (trimmed to sensible window) on the question document."""
    resps = list(db.db.responses.find(
        {"question_id": question_id}, {"correct": 1, "time_ms": 1}))
    n = len(resps)
    if n < CALIBRATION_MIN_N:
        return None
    correct_rate = sum(1 for r in resps if r.get("correct")) / n
    # DESIGN §7: high correct_rate -> easier (1), low correct_rate -> harder (5)
    emp_diff = max(1, min(5, 1 + round(4 * (1.0 - correct_rate))))
    valid_times = sorted(r["time_ms"] for r in resps
                         if isinstance(r.get("time_ms"), (int, float)) and 2_000 <= r["time_ms"] <= 300_000)
    med_ms = valid_times[len(valid_times) // 2] if valid_times else None
    upd = {"empirical_difficulty": emp_diff, "empirical_correct_rate": round(correct_rate, 3),
           "empirical_n": n}
    if med_ms is not None:
        upd["median_time_ms"] = int(med_ms)
    db.db.questions.update_one({"_id": question_id}, {"$set": upd})
    return upd


def grade(q: dict, selected_option):
    """selected_option in ORIGINAL numbering. Returns (correct_option, correct).
    Raises ValueError on an invalid answer. 0 means «نمی‌دانم» (counted as wrong)."""
    if q.get("type", "multiple_choice_4") == "multiple_choice_4":
        correct_opt = (q.get("answer") or {}).get("option")
        if correct_opt is None:
            raise ValueError("question has no answer key")
        n = len(q.get("options") or [])
        if isinstance(selected_option, bool) or not isinstance(selected_option, int) \
                or not 0 <= selected_option <= n:
            raise ValueError("invalid option")
        return correct_opt, selected_option == correct_opt
    # tashrihi: self-graded in MVP (client sends did_correct as a bool)
    return None, bool(selected_option)


def _feedback(q: dict, perm, correct_opt, correct: bool) -> dict:
    return {"correct": correct,
            "correct_option": to_display(correct_opt, perm),
            "solution_md": remap_solution(q.get("solution_md"), perm)}


def answer_slot(student: dict, session: dict, index: int, selected_option, time_ms: int):
    """selected_option is in DISPLAY numbering (what the student saw)"""
    slots = session["slots"]
    if index < 0 or index >= len(slots):
        raise ValueError("bad slot index")
    slot = slots[index]
    if slot["status"] != "pending":
        raise ValueError("slot already answered")
    q = db.db.questions.find_one({"_id": slot["question_id"]})
    if not q:
        raise ValueError("question missing")
    perm = slot.get("perm")
    original = to_original(selected_option, perm)
    correct_opt, correct = grade(q, original)

    # claim the slot atomically before any side effect: two concurrent submits
    # (double click, Enter + click) must not update the schedule twice
    claimed = db.db.sessions.update_one(
        {"_id": session["_id"], f"slots.{index}.status": "pending"},
        {"$set": {f"slots.{index}.status": "answered", f"slots.{index}.correct": correct}})
    if claimed.modified_count == 0:
        raise ValueError("slot already answered")

    st = update_concept_state(student["_id"], slot["concept_id"], correct, time_ms,
                              expected_time(q),
                              scheduled=slot.get("scheduled", slot.get("kind") != "remediation")
                              and slot.get("kind") not in ("remediation", "weak"))

    db.db.responses.insert_one({
        "student_id": student["_id"], "question_id": q["_id"],
        "concept_id": slot["concept_id"], "correct": correct,
        "time_ms": time_ms, "selected_option": original,
        "selected_display": selected_option, "kind": slot.get("kind"),
        # for the retention metric: was this a spaced check after a long interval?
        "prior_interval_days": st.get("prior_interval"), "schedule_applied": st.get("applied"),
        "context": "daily", "answered_at": clock.now_utc()})
    maybe_calibrate_question(q["_id"])

    db.db.concept_state.update_one(
        {"student_id": student["_id"], "concept_id": slot["concept_id"]},
        {"$push": {"seen_question_ids": {"$each": [q["_id"]], "$slice": -SEEN_BUFFER}}})

    # same-day remediation (§5.4): once per concept per day, always a different question
    remediation = False
    if not correct and slot.get("kind") != "remediation":
        today_qids = set()
        for s in db.db.sessions.find({"student_id": student["_id"], "date": session["date"]}):
            today_qids |= {sl["question_id"] for sl in s["slots"]}
        remedial_q, repeat = pick_question(student["_id"], slot["concept_id"],
                                           exclude_ids=today_qids | {q["_id"]})
        if remedial_q is not None:
            r = db.db.sessions.update_one(
                {"_id": session["_id"],
                 f"remediation_done.{slot['concept_id']}": {"$exists": False}},
                {"$push": {"slots": {"concept_id": slot["concept_id"],
                                      "question_id": remedial_q["_id"],
                                      "kind": "remediation", "scheduled": False,
                                      "repeat": repeat, "perm": make_perm(remedial_q),
                                      "status": "pending"}},
                 "$set": {f"remediation_done.{slot['concept_id']}": True}})
            remediation = r.modified_count == 1

    out = _feedback(q, perm, correct_opt, correct)
    out.update({"next_due": st.get("due_day") or due_day(st),
                "schedule_changed": st.get("applied", False),
                "remediation": remediation})   # «امروز در پایان جلسه دوباره می‌بینیم»
    if not correct:
        out["key_point"] = key_point(slot["concept_id"])   # re-teach the point after a miss
    return out

# ---------------------------------------------------------------- placement test
# One question per untouched key point of a chapter, the hardest approved one: a strong
# student proves what they already know in ~1 question per point instead of ~5, and
# those points start further up the ladder. A miss changes nothing: the point stays new
# and is taught normally (key-point card, then questions).

PLACEMENT_HARD = 3      # difficulty from which a correct answer counts as "learned"


def place(student_id, concept_id, question_id, level: str = "learning") -> int:
    """start a key point further up the ladder because the student already showed they
    know it (trial or placement). Never touches a point the student has already started.
    Returns 1 if the state was created."""
    # one 4-option answer is ~25% guessable: even "learned" must still come back after 3 days
    # (the confirmation), and only the 7-day gap after that can make it "learned"
    interval, streak = (3.0, 2) if level == "learned" else (3.0, 1)
    due = clock.today() + dt.timedelta(days=int(interval))
    st = {"ease": 2.5, "interval_days": interval, "streak": streak, "lapses": 0,
          "total_answers": 1, "total_correct": 1, "due_day": due.isoformat(),
          "due_date": dt.datetime.combine(due, dt.time()),
          "last_review_day": clock.today_str(), "last_answer_day": clock.today_str(),
          "last_grade": "good", "placed": level, "updated_at": clock.now_utc()}
    st["mastery_level"] = mastery_level(st)
    r = db.db.concept_state.update_one(
        {"student_id": student_id, "concept_id": concept_id},
        {"$setOnInsert": {**st, "seen_question_ids": [question_id]}}, upsert=True)
    return 1 if r.upserted_id is not None else 0


def build_placement_session(student: dict, chapter_id: str):
    sid = student["_id"]
    attempted = {s["concept_id"] for s in db.db.concept_state.find(
        {"student_id": sid}, {"concept_id": 1})}
    slots = []
    for c in db.db.concepts.find({"chapter_id": chapter_id, "retired": {"$ne": True}}) \
            .sort("order_in_curriculum", 1):
        if c["concept_id"] in attempted:
            continue
        # multiple choice only: a self-graded written answer is weak evidence for skipping
        qs = [q for q in db.db.questions.find({"concept_id": c["concept_id"], **SERVABLE,
                                               "type": "multiple_choice_4"})
              if _has_key(q)]
        if not qs:
            continue
        qs.sort(key=lambda q: (-q.get("difficulty", 3), random.random()))
        q = qs[0]
        slots.append({"concept_id": c["concept_id"], "question_id": q["_id"],
                      "kind": "placement", "perm": make_perm(q), "status": "pending"})
    if not slots:
        return None
    db.db.placement_sessions.delete_many({"student_id": sid})
    doc = {"student_id": sid, "chapter_id": chapter_id, "kind": "placement",
           "created_at": clock.now_utc(), "slots": slots}
    db.db.placement_sessions.insert_one(doc)
    return doc


def get_placement_session(student_id):
    return db.db.placement_sessions.find_one({"student_id": student_id})


def answer_placement_slot(student, session, index, selected_option, time_ms):
    slots = session["slots"]
    if index < 0 or index >= len(slots):
        raise ValueError("bad slot index")
    slot = slots[index]
    if slot["status"] != "pending":
        raise ValueError("slot already answered")
    q = db.db.questions.find_one({"_id": slot["question_id"]})
    if not q:
        raise ValueError("question missing")
    perm = slot.get("perm")
    original = to_original(selected_option, perm)
    correct_opt, correct = grade(q, original)

    placed = None
    if correct:
        quick = time_ms <= 2 * expected_time(q)
        placed = "learned" if q.get("difficulty", 3) >= PLACEMENT_HARD and quick else "learning"
    claimed = db.db.placement_sessions.update_one(
        {"_id": session["_id"], f"slots.{index}.status": "pending"},
        {"$set": {f"slots.{index}.status": "answered", f"slots.{index}.correct": correct,
                  f"slots.{index}.placed": placed}})
    if claimed.modified_count == 0:
        raise ValueError("slot already answered")

    if placed:
        interval, streak = (3.0, 2) if placed == "learned" else (3.0, 1)   # see place()
        due = clock.today() + dt.timedelta(days=int(interval))
        st = {"ease": 2.5, "interval_days": interval, "streak": streak, "lapses": 0,
              "total_answers": 1, "total_correct": 1, "due_day": due.isoformat(),
              "due_date": dt.datetime.combine(due, dt.time()),
              "last_review_day": clock.today_str(), "last_answer_day": clock.today_str(),
              "last_grade": "good", "placed": placed, "updated_at": clock.now_utc()}
        st["mastery_level"] = mastery_level(st)
        # only if the student has not started this point in the meantime
        db.db.concept_state.update_one(
            {"student_id": student["_id"], "concept_id": slot["concept_id"]},
            {"$setOnInsert": {**st, "seen_question_ids": [q["_id"]]}}, upsert=True)

    db.db.responses.insert_one({
        "student_id": student["_id"], "question_id": q["_id"],
        "concept_id": slot["concept_id"], "correct": correct, "time_ms": time_ms,
        "selected_option": original, "selected_display": selected_option,
        "context": "placement", "placed": placed, "answered_at": clock.now_utc()})
    done = sum(1 for s in slots if s["status"] == "answered") + 1
    out = _feedback(q, perm, correct_opt, correct)
    out.update({"done": done, "total": len(slots), "placed": placed})
    if not correct:
        out["key_point"] = key_point(slot["concept_id"])
    return out

# ---------------------------------------------------------------- practice mode (§11.4)


def build_practice_session(student_id, concept_ids, count=10, question_ids=None, wrong_only=False):
    if wrong_only:
        qs = [q for q in last_wrong_questions(student_id, limit=count)
              if q.get("review_status") == "approved"]
    elif question_ids:
        # only questions this student has already answered: asking for arbitrary ids would
        # show the answer key before the question comes up in the daily plan
        answered = {r["question_id"] for r in db.db.responses.find(
            {"student_id": student_id}, {"question_id": 1})}
        qs = [q for q in db.db.questions.find({"public_id": {"$in": question_ids}, **SERVABLE})
              if q["_id"] in answered]
    elif concept_ids:
        qs = list(db.db.questions.find({"concept_id": {"$in": concept_ids}, **SERVABLE}))
    else:
        qs = []
    qs = [q for q in qs if _has_key(q)]
    if not qs:
        return None
    random.shuffle(qs)
    slots = [{"concept_id": q["concept_id"], "question_id": q["_id"],
              "kind": "practice", "perm": make_perm(q), "status": "pending"}
             for q in qs[:count]]
    db.db.practice_sessions.delete_many({"student_id": student_id})
    doc = {"student_id": student_id, "kind": "practice",
           "created_at": clock.now_utc(), "slots": slots}
    db.db.practice_sessions.insert_one(doc)
    return doc


def get_practice_session(student_id):
    return db.db.practice_sessions.find_one({"student_id": student_id})


def answer_practice_slot(student, session, index, selected_option, time_ms):
    slots = session["slots"]
    if index < 0 or index >= len(slots):
        raise ValueError("bad slot index")
    slot = slots[index]
    if slot["status"] != "pending":
        raise ValueError("slot already answered")
    q = db.db.questions.find_one({"_id": slot["question_id"]})
    if not q:
        raise ValueError("question missing")
    perm = slot.get("perm")
    original = to_original(selected_option, perm)
    correct_opt, correct = grade(q, original)
    time_ms = max(0, min(int(time_ms or 0), 600_000))

    claimed = db.db.practice_sessions.update_one(
        {"_id": session["_id"], f"slots.{index}.status": "pending"},
        {"$set": {f"slots.{index}.status": "answered", f"slots.{index}.correct": correct}})
    if claimed.modified_count == 0:
        raise ValueError("slot already answered")

    # recorded for stats/calibration; scheduling untouched (§11.4)
    db.db.responses.insert_one({
        "student_id": student["_id"], "question_id": q["_id"],
        "concept_id": slot["concept_id"], "correct": correct,
        "time_ms": time_ms, "selected_option": original, "selected_display": selected_option,
        "context": "practice", "answered_at": clock.now_utc()})
    maybe_calibrate_question(q["_id"])
    done = sum(1 for s in slots if s["status"] == "answered") + 1
    out = _feedback(q, perm, correct_opt, correct)
    out.update({"done": done, "total": len(slots)})
    if not correct:
        out["key_point"] = key_point(slot["concept_id"])
    return out

# ---------------------------------------------------------------- today's plan (DESIGN §9.1)


def plan_summary(student: dict, session: dict) -> dict:
    """what the student must know before pressing start: counts, time, yesterday's
    misses, and the week so far"""
    sid = student["_id"]
    today = clock.today()
    yesterday = (today - dt.timedelta(days=1)).isoformat()
    cids = list({sl["concept_id"] for sl in session["slots"]})
    states = {s["concept_id"]: s for s in db.db.concept_state.find(
        {"student_id": sid, "concept_id": {"$in": cids}})}
    missed_yesterday = sorted(cid for cid, s in states.items()
                              if s.get("last_review_day") == yesterday
                              and s.get("last_grade") == "again")
    qdocs = {q["_id"]: q for q in db.db.questions.find(
        {"_id": {"$in": [sl["question_id"] for sl in session["slots"]]}},
        {"type": 1, "difficulty": 1})}
    pending_ms = sum(expected_time(qdocs.get(sl["question_id"], {}))
                     for sl in session["slots"] if sl["status"] == "pending")
    kinds = {}
    for sl in session["slots"]:
        if sl["status"] == "pending":          # the counts describe what is LEFT, like the big number
            kinds[sl.get("kind", "review")] = kinds.get(sl.get("kind", "review"), 0) + 1

    # week strip: last 7 Tehran days, answered daily questions per day
    start = today - dt.timedelta(days=6)
    since = dt.datetime.combine(start, dt.time()) - dt.timedelta(hours=4)
    per_day = {}
    for r in db.db.responses.find({"student_id": sid, "context": "daily",
                                   "answered_at": {"$gte": since}}, {"answered_at": 1}):
        d = clock.day_of(r["answered_at"])
        if d >= start:
            per_day[d] = per_day.get(d, 0) + 1
    done_days = {s["date"] for s in db.db.sessions.find(
        {"student_id": sid, "date": {"$gte": start.isoformat()}, "book_id": None,
         "chapter_id": None}, {"date": 1, "slots.status": 1})
        if s["slots"] and all(x["status"] == "answered" for x in s["slots"])}
    week = []
    for i in range(7):
        d = start + dt.timedelta(days=i)
        week.append({"date": d.isoformat(), "weekday": d.weekday(),
                     "answered": per_day.get(d, 0), "done": d.isoformat() in done_days,
                     "today": d == today})
    # the chapter the student is working through: of the first new slot, else the first slot
    focus = None
    lead = next((sl for sl in session["slots"] if sl.get("kind") == "new"),
                session["slots"][0] if session["slots"] else None)
    if lead:
        c = db.db.concepts.find_one({"concept_id": lead["concept_id"]},
                                    {"chapter_id": 1, "chapter_title": 1})
        if c and c.get("chapter_id"):
            ids = [x["concept_id"] for x in db.db.concepts.find(
                {"chapter_id": c["chapter_id"], "retired": {"$ne": True}}, {"concept_id": 1})]
            learned = db.db.concept_state.count_documents(
                {"student_id": sid, "concept_id": {"$in": ids}, "mastery_level": {"$gte": 2}})
            started = db.db.concept_state.count_documents(
                {"student_id": sid, "concept_id": {"$in": ids}})
            focus = {"chapter_id": c["chapter_id"], "chapter_title": c.get("chapter_title"),
                     "total": len(ids), "learned": learned, "started": started}
    return {"focus": focus,
            "review_count": kinds.get("review", 0) + kinds.get("weak", 0),
            "new_count": kinds.get("new", 0),
            "remediation_count": kinds.get("remediation", 0),
            "est_minutes": max(1, round(pending_ms / 60000)) if pending_ms else 0,
            "missed_yesterday": missed_yesterday,
            "streak_days": student_stats(sid)["streak_days"],
            "week": week}

# ---------------------------------------------------------------- stats


def last_wrong_questions(student_id, limit=30):
    """distinct questions whose most recent response was wrong"""
    last = {}
    for r in db.db.responses.find({"student_id": student_id},
                                  {"question_id": 1, "correct": 1}).sort("answered_at", 1):
        last[r["question_id"]] = r["correct"]
    wrong_ids = [qid for qid, ok in last.items() if not ok][-limit:]
    if not wrong_ids:
        return []
    return list(db.db.questions.find({"_id": {"$in": wrong_ids}}))


def student_progress(student: dict) -> dict:
    """everything the «پیشرفت» page shows: how many key points are learned, 5 weeks of
    activity, the weakest key points and what is due tomorrow"""
    sid = student["_id"]
    today = clock.today()
    today_s = today.isoformat()
    tomorrow_s = (today + dt.timedelta(days=1)).isoformat()

    servable = set(db.db.questions.distinct("concept_id", SERVABLE))
    cq = {"source": "taxonomy", "retired": {"$ne": True}}
    if student.get("scope_chapter_ids"):
        cq["chapter_id"] = {"$in": student["scope_chapter_ids"]}
    concepts = {c["concept_id"]: c for c in db.db.concepts.find(cq) if c["concept_id"] in servable}
    states = {s["concept_id"]: s for s in db.db.concept_state.find({"student_id": sid})
              if s["concept_id"] in concepts}
    learned = sum(1 for s in states.values() if s.get("mastery_level", 0) >= 2)
    started = len(states)

    # activity: answered / correct per Tehran day over the last 35 days
    since = clock.now_utc() - dt.timedelta(days=35)
    per_day: dict[str, list] = {}
    for r in db.db.responses.find({"student_id": sid, "answered_at": {"$gte": since}},
                                  {"answered_at": 1, "correct": 1}):
        d = clock.day_of(r["answered_at"]).isoformat()
        cell = per_day.setdefault(d, [0, 0])
        cell[0] += 1
        cell[1] += 1 if r.get("correct") else 0
    activity = []
    for i in range(34, -1, -1):
        d = (today - dt.timedelta(days=i)).isoformat()
        a, c = per_day.get(d, [0, 0])
        activity.append({"date": d, "answered": a, "correct": c})

    # streaks over all days with an answer
    all_days = sorted({clock.day_of(r["answered_at"]) for r in db.db.responses.find(
        {"student_id": sid}, {"answered_at": 1})})
    best = run = 0
    prev = None
    for d in all_days:
        run = run + 1 if prev is not None and d - prev == dt.timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    stats = student_stats(sid)

    weak = sorted((s for s in states.values() if s.get("lapses", 0) > 0),
                  key=lambda s: (-s["lapses"], s["concept_id"]))[:5]
    weak_out = [{"concept_id": s["concept_id"], "title": concepts[s["concept_id"]].get("title"),
                 "chapter_title": concepts[s["concept_id"]].get("chapter_title"),
                 "lapses": s["lapses"],
                 "status": "learned" if s.get("mastery_level", 0) >= 2 else "learning"}
                for s in weak]
    return {
        "total": len(concepts), "learned": learned, "learning": started - learned,
        "new": len(concepts) - started,
        "due_today": sum(1 for s in states.values() if due_day(s) <= today_s),
        "due_tomorrow": sum(1 for s in states.values() if due_day(s) == tomorrow_s),
        "activity": activity, "days_active": len(all_days),
        "streak_days": stats["streak_days"], "best_streak": best,
        "total_answered": stats["total_answered"], "accuracy": stats["accuracy"],
        "week_answered": stats["week_answered"], "week_accuracy": stats["week_accuracy"],
        "weak": weak_out,
        "avg_questions_to_learn": (round(sum(s["answers_to_learned"] for s in states.values()
                                             if "answers_to_learned" in s) /
                                         max(1, sum(1 for s in states.values() if "answers_to_learned" in s)), 1)
                                   if any("answers_to_learned" in s for s in states.values()) else None),
    }


def student_stats(student_id):
    days = sorted({clock.day_of(r["answered_at"]) for r in
                   db.db.responses.find({"student_id": student_id,
                                         "context": {"$ne": "practice"}},
                                        {"answered_at": 1})})
    today = clock.today()
    streak = 0
    if days and days[-1] >= today - dt.timedelta(days=1):
        cursor, have = days[-1], set(days)
        while cursor in have:
            streak += 1
            cursor -= dt.timedelta(days=1)
    total = db.db.responses.count_documents({"student_id": student_id})
    correct = db.db.responses.count_documents({"student_id": student_id, "correct": True})
    week_ago = clock.now_utc() - dt.timedelta(days=7)
    w_total = db.db.responses.count_documents(
        {"student_id": student_id, "answered_at": {"$gte": week_ago}})
    w_correct = db.db.responses.count_documents(
        {"student_id": student_id, "correct": True, "answered_at": {"$gte": week_ago}})
    return {"streak_days": streak, "total_answered": total,
            "total_correct": correct,
            "accuracy": round(correct / total, 2) if total else None,
            "week_answered": w_total,
            "week_accuracy": round(w_correct / w_total, 2) if w_total else None,
            "wrong_count": len(last_wrong_questions(student_id, limit=999))}
