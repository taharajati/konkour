import datetime as dt

import pytest

from app import clock, scheduler
from conftest import TEHRAN_NOON, seed, set_day


def _answer(mem, student, session, slot_index, correct: bool, time_ms=10_000):
    """answer a slot in display numbering, choosing right or wrong on purpose"""
    s = mem.sessions.find_one({"_id": session["_id"]})
    slot = s["slots"][slot_index]
    q = mem.questions.find_one({"_id": slot["question_id"]})
    right = scheduler.to_display(q["answer"]["option"], slot.get("perm"))
    choice = right if correct else (right % 4) + 1
    return scheduler.answer_slot(student, s, slot_index, choice, time_ms)


# ------------------------------------------------------------------ time

def test_day_is_tehran_day():
    clock.freeze(dt.datetime(2026, 11, 14, 21, 0, tzinfo=dt.timezone.utc))   # 00:30 Tehran
    assert clock.today_str() == "2026-11-15"
    clock.freeze(dt.datetime(2026, 11, 14, 20, 0, tzinfo=dt.timezone.utc))   # 23:30 Tehran
    assert clock.today_str() == "2026-11-14"


# ------------------------------------------------------------------ queue

def test_queue_unique_questions_and_concepts(fresh_db):
    student = seed(fresh_db)
    s = scheduler.build_daily_queue(student, load=20)
    qids = [sl["question_id"] for sl in s["slots"]]
    cids = [sl["concept_id"] for sl in s["slots"]]
    assert len(qids) == len(set(qids)), "same question twice in one day"
    assert len(cids) == len(set(cids)), "more than one slot per concept"
    served = {fresh_db.questions.find_one({"_id": q})["review_status"] for q in qids}
    assert served == {"approved"}


def test_new_concepts_follow_curriculum_and_prerequisites(fresh_db):
    student = seed(fresh_db)
    # c3 now needs c4, which comes later in the curriculum and was never attempted
    fresh_db.concepts.update_one({"concept_id": "c3"}, {"$set": {"prereq_ids": ["c4"]}})
    s = scheduler.build_daily_queue(student, load=20)
    assert {sl["concept_id"] for sl in s["slots"]} == {"c1", "c2", "c4"}
    # once c4 has been attempted, c3 opens up
    fresh_db.sessions.delete_many({})
    scheduler.update_concept_state(student["_id"], "c4", True, 1000, 40000)
    s = scheduler.build_daily_queue(student, load=20)
    assert "c3" in {sl["concept_id"] for sl in s["slots"]}


def test_load_limits_new_concepts_in_curriculum_order(fresh_db):
    student = seed(fresh_db)
    s = scheduler.build_daily_queue(student, load=2)
    assert {sl["concept_id"] for sl in s["slots"]} == {"c1", "c2"}


def test_new_concepts_are_served_in_curriculum_order(fresh_db):
    student = seed(fresh_db)
    s = scheduler.build_daily_queue(student, load=20)
    assert [sl["concept_id"] for sl in s["slots"]] == ["c1", "c2", "c3", "c4"]


def test_concept_without_approved_questions_is_skipped(fresh_db):
    student = seed(fresh_db)
    fresh_db.questions.update_many({"concept_id": "c2"}, {"$set": {"review_status": "pending"}})
    s = scheduler.build_daily_queue(student, load=20)
    assert "c2" not in {sl["concept_id"] for sl in s["slots"]}


def test_session_is_built_once(fresh_db):
    student = seed(fresh_db)
    a = scheduler.build_daily_queue(student)
    b = scheduler.build_daily_queue(student)
    assert a["_id"] == b["_id"]
    assert fresh_db.sessions.count_documents({}) == 1


def test_no_concept_twice_across_scoped_sessions(fresh_db):
    student = seed(fresh_db)
    a = scheduler.build_daily_queue(student)
    b = scheduler.build_daily_queue(student, chapter_id="B_ch1")
    ca = {sl["concept_id"] for sl in a["slots"]}
    cb = {sl["concept_id"] for sl in b["slots"]}
    assert not ca & cb


# ------------------------------------------------------------------ answering

def test_double_submit_records_once(fresh_db):
    student = seed(fresh_db)
    s = scheduler.build_daily_queue(student)
    stale = fresh_db.sessions.find_one({"_id": s["_id"]})   # both requests read this copy
    slot = stale["slots"][0]
    q = fresh_db.questions.find_one({"_id": slot["question_id"]})
    choice = scheduler.to_display(q["answer"]["option"], slot["perm"])
    scheduler.answer_slot(student, stale, 0, choice, 5000)
    with pytest.raises(ValueError):
        scheduler.answer_slot(student, stale, 0, choice, 5000)
    assert fresh_db.responses.count_documents({}) == 1
    st = fresh_db.concept_state.find_one({"concept_id": slot["concept_id"]})
    assert st["total_answers"] == 1


def test_invalid_answers_rejected(fresh_db):
    student = seed(fresh_db)
    s = scheduler.build_daily_queue(student)
    for bad in (5, -1, True, "2"):
        with pytest.raises(ValueError):
            scheduler.answer_slot(student, s, 0, bad, 1000)
    assert fresh_db.responses.count_documents({}) == 0


def test_dont_know_counts_as_wrong(fresh_db):
    student = seed(fresh_db)
    s = scheduler.build_daily_queue(student)
    out = scheduler.answer_slot(student, s, 0, 0, 1000)
    assert out["correct"] is False and out["correct_option"] in (1, 2, 3, 4)


def test_shuffled_options_grade_and_solution(fresh_db):
    student = seed(fresh_db)
    s = scheduler.build_daily_queue(student)
    slot = s["slots"][0]
    q = fresh_db.questions.find_one({"_id": slot["question_id"]})
    perm = slot["perm"]
    shown = scheduler.display_options(q, perm)
    right_display = scheduler.to_display(3, perm)
    assert shown[right_display - 1] == q["options"][2]
    out = scheduler.answer_slot(student, s, 0, right_display, 1000)
    assert out["correct"] and out["correct_option"] == right_display
    fa = "۰۱۲۳۴۵۶۷۸۹"
    assert f"گزینهٔ {fa[right_display]}" in out["solution_md"]


def test_solution_option_numbers_follow_the_shuffle():
    perm = [3, 1, 4, 2]       # display 1 shows original 3, display 2 shows original 1 ...
    text = "**گزینهٔ درست: 2**\nپس گزینهٔ ۳ درست است و گزینه 4 غلط."
    out = scheduler.remap_solution(text, perm)
    assert out == "**گزینهٔ درست: 4**\nپس گزینهٔ ۱ درست است و گزینه 3 غلط."


def test_clean_solution_keeps_one_answer_line():
    from app.importer import clean_solution
    out = clean_solution("**گزینهٔ درست: 2**\n\nحل: چون ...", 2)
    assert out.count("گزینهٔ") == 1 and out.endswith("**پاسخ درست: گزینهٔ 2**")


def test_positional_options_not_shuffled():
    q = {"type": "multiple_choice_4", "options": ["۱", "۲", "۳", "همهٔ موارد"]}
    assert not scheduler.can_shuffle(q)
    assert scheduler.make_perm(q) == [1, 2, 3, 4]


def test_remediation_adds_a_different_question_once(fresh_db):
    student = seed(fresh_db)
    s = scheduler.build_daily_queue(student, load=1)
    first_q = s["slots"][0]["question_id"]
    out = _answer(fresh_db, student, s, 0, correct=False)
    assert out["remediation"]
    s = fresh_db.sessions.find_one({"_id": s["_id"]})
    assert len(s["slots"]) == 2
    assert s["slots"][1]["kind"] == "remediation" and s["slots"][1]["question_id"] != first_q
    _answer(fresh_db, student, s, 1, correct=False)
    s = fresh_db.sessions.find_one({"_id": s["_id"]})
    assert len(s["slots"]) == 2, "remediation must happen once per concept per day"


def test_no_remediation_when_family_exhausted(fresh_db):
    student = seed(fresh_db, per_concept=1, extra_pending=False)
    s = scheduler.build_daily_queue(student, load=1)
    out = _answer(fresh_db, student, s, 0, correct=False)
    assert not out["remediation"]


# ------------------------------------------------------------------ the ladder

def _state(mem, cid):
    return mem.concept_state.find_one({"concept_id": cid})


def test_spaced_ladder_and_early_reviews():
    sid, cid = "stu", "c1"
    up = scheduler.update_concept_state
    st = up(sid, cid, True, 1000, 40000, scheduled=True)               # day 0, first time
    assert st["interval_days"] == 1 and st["due_day"] == "2026-11-15"
    st = up(sid, cid, True, 1000, 40000, scheduled=True)               # same day again
    assert st["streak"] == 1 and not st["applied"], "second success same day must not count"
    set_day(1)
    st = up(sid, cid, True, 1000, 40000, scheduled=True)               # due day
    assert st["streak"] == 2 and st["interval_days"] == 3
    set_day(2)
    st = up(sid, cid, True, 1000, 40000, scheduled=False)              # early (weak slot)
    assert st["streak"] == 2 and st["total_answers"] == 4
    set_day(4)
    st = up(sid, cid, True, 1000, 40000, scheduled=True)
    assert st["streak"] == 3 and st["interval_days"] == 7
    set_day(5)
    st = up(sid, cid, False, 1000, 40000, scheduled=False)             # a miss always counts
    assert st["streak"] == 0 and st["interval_days"] == 1 and st["lapses"] == 1
    st = up(sid, cid, False, 1000, 40000, scheduled=False)             # once per day
    assert st["lapses"] == 1


def test_mastered_concept_returns_for_maintenance(fresh_db):
    student = seed(fresh_db)
    fresh_db.concept_state.insert_one({
        "student_id": student["_id"], "concept_id": "c2", "ease": 3.0, "interval_days": 90.0,
        "streak": 6, "lapses": 0, "total_answers": 6, "total_correct": 6, "mastery_level": 3,
        "due_day": "2026-11-10", "seen_question_ids": []})
    s = scheduler.build_daily_queue(student)
    review = [sl for sl in s["slots"] if sl["concept_id"] == "c2"]
    assert review and review[0]["kind"] == "review"
    assert s["slots"][0]["concept_id"] == "c2", "overdue reviews come first"


def test_interval_capped():
    st = None
    for day in range(0, 400, 1):
        set_day(day)
        cur = scheduler.db.db.concept_state.find_one({"concept_id": "cap"})
        if cur and scheduler.due_day(cur) > clock.today_str():
            continue
        st = scheduler.update_concept_state("s", "cap", True, 1000, 40000, scheduled=True)
    assert st["interval_days"] <= scheduler.MAX_INTERVAL


def test_legacy_state_without_due_day(fresh_db):
    student = seed(fresh_db)
    fresh_db.concept_state.insert_one({
        "student_id": student["_id"], "concept_id": "c1", "ease": 2.5, "interval_days": 1.0,
        "streak": 1, "lapses": 0, "total_answers": 1, "total_correct": 1, "mastery_level": 1,
        "due_date": dt.datetime(2026, 11, 13, 21, 0), "seen_question_ids": []})   # 00:30 Tehran 14th
    assert scheduler.due_day(fresh_db.concept_state.find_one({"concept_id": "c1"})) == "2026-11-14"
    s = scheduler.build_daily_queue(student)
    assert any(sl["concept_id"] == "c1" and sl["kind"] == "review" for sl in s["slots"])

def test_solution_option_list_remapping():
    perm = [3, 1, 4, 2]       # display 1<-3, 2<-1, 3<-4, 4<-2
    text = "گزینه‌های ۱ و ۳ نادرست‌اند و گزینهٔ 2 درست است."
    out = scheduler.remap_solution(text, perm)
    assert out == "گزینه‌های ۲ و ۱ نادرست‌اند و گزینهٔ 4 درست است."


def test_due_review_not_starved_by_sibling_swap(fresh_db):
    student = seed(fresh_db, per_concept=1, extra_pending=False)
    # student saw c1_q0 yesterday and c1 is due today; c2 in same lesson L1 is unseen
    fresh_db.concept_state.insert_one({
        "student_id": student["_id"], "concept_id": "c1", "ease": 2.5, "interval_days": 1.0,
        "streak": 1, "lapses": 0, "total_answers": 1, "total_correct": 1, "mastery_level": 1,
        "due_day": "2026-11-14", "last_review_day": "2026-11-13",
        "seen_question_ids": [fresh_db.questions.find_one({"public_id": "c1_q0"})["_id"]],
    })
    s = scheduler.build_daily_queue(student, load=2)
    cids = [sl["concept_id"] for sl in s["slots"]]
    assert "c1" in cids, "due concept must be served so its due_day can advance"


def test_empirical_difficulty_and_time_calibration(fresh_db):
    student = seed(fresh_db)
    q = fresh_db.questions.find_one({"public_id": "c1_q0"})
    for i in range(20):
        fresh_db.responses.insert_one({
            "student_id": student["_id"], "question_id": q["_id"], "concept_id": "c1",
            "correct": i < 2, "time_ms": 62_000, "answered_at": clock.now_utc()})
    cal = scheduler.maybe_calibrate_question(q["_id"])
    assert cal["empirical_difficulty"] == 5 and cal["median_time_ms"] == 62_000
    updated = fresh_db.questions.find_one({"_id": q["_id"]})
    assert scheduler.effective_difficulty(updated) == 5
    assert scheduler.expected_time(updated) == 62_000
