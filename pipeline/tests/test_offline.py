"""Offline tests: no network, no API key. A fake provider stands in for the model.
Run from the workspace root:  python -m pipeline.tests.test_offline <pdf>"""
import json
import os
import shutil
import sys
import tempfile

from pipeline import bank, checks, config, stages, taxonomy
from pipeline.llm import CachedLLM, LLMError, Provider


class FakeProvider(Provider):
    """returns canned answers by prompt kind; counts calls"""
    def __init__(self):
        self.calls = 0

    def generate_json(self, system, content, schema, model, effort):
        self.calls += 1
        usage = {"input_tokens": 10, "output_tokens": 10}
        if "page_kind" in schema["properties"]:
            n = self.calls
            return {"page_kind": "questions", "answers": [
                        {"printed_number": n, "option": 2, "solution_md": "حل: گزینهٔ ۲"}],
                    "questions": [{
                        "printed_number": n, "type": "mcq",
                        "stem_md": f"کدام مجموعه برابر $\\{{1,2\\}}$ است؟ ({n})",
                        "options": ["$\\{1\\}$", "$\\{2,1\\}$", "$\\{3\\}$", "$\\emptyset$"],
                        "options_order_checked": True, "has_figure": False, "figure_bbox": [],
                        "points": 0, "source_note": "", "continues_from_previous": False,
                        "legible": True}]}, usage
        if "solver_option" in schema["properties"]:
            return {"solver_option": 2, "issues": [], "solution_md": "ترتیب مهم نیست. پاسخ: گزینهٔ ۲",
                    "confidence": "high"}, usage
        ids = schema["properties"]["primary"]["enum"]
        return {"primary": "G9_RIAZI_ch1_l2_k1", "secondary": [], "difficulty": 1,
                "reason": "برابری مجموعه‌ها"} if "G9_RIAZI_ch1_l2_k1" in ids else \
               {"primary": "none", "secondary": [], "difficulty": 1, "reason": ""}, usage


def test_checks():
    assert checks.latex_balanced("$\\frac{1}{2}$ و $\\{a\\}$")
    assert not checks.latex_balanced("$\\frac{1}{2$")
    good = {"stem_md": "کدام گزینه درست است؟", "type": "mcq", "options": ["a1", "b2", "c3", "d4"],
            "options_order_checked": True, "legible": True}
    assert checks.check_question(good) == []
    bad = dict(good, options=["x", "x", "y"], stem_md="متناظر would دارد")
    p = checks.check_question(bad)
    assert any("۴ گزینه" in s for s in p) and any("تکراری" in s for s in p) and any("لاتین" in s for s in p)
    assert checks.options_named_in_solution("پس گزینهٔ ۳ درست است") == {3}
    assert checks.decide(2, {"solver_option": 2, "issues": [], "confidence": "high"}, [], "mcq")[0] == "verified"
    assert checks.decide(2, {"solver_option": 3, "issues": [], "confidence": "high"}, [], "mcq")[0] == "conflict"
    assert checks.decide(0, {"solver_option": 3, "issues": [], "confidence": "high"}, [], "mcq")[0] == "solver_only"
    assert checks.decide(2, {"solver_option": 2, "issues": ["دو گزینه درست"], "confidence": "high"}, [], "mcq")[0] == "needs_fix"
    print("checks OK")


def test_taxonomy():
    problems = taxonomy.validate("G9_RIAZI")
    assert not problems, problems
    assert len(taxonomy.concepts_for("G9_RIAZI", [1])) == 16
    print("taxonomy OK:", len(taxonomy.concepts_for("G9_RIAZI")), "concepts")


def test_pipeline(pdf):
    tmp = tempfile.mkdtemp(prefix="pipe_test_")
    old_bank = config.BANK_ROOT
    try:
        work = os.path.join(tmp, "work")
        blocks = stages.prepare(pdf, work)
        assert blocks, "no blocks"
        # without --yes and with an empty cache, nothing may be called
        locked = CachedLLM(FakeProvider(), stages.paths(work)["llm"], "t", allow_calls=False)
        try:
            stages.extract(locked, work)
            raise AssertionError("expected LLMError without permission")
        except LLMError:
            pass
        fake = FakeProvider()
        llm = CachedLLM(fake, stages.paths(work)["llm"], "t", allow_calls=True)
        stages.extract(llm, work)
        qs = stages.assemble(work)
        stages.solve(llm, work)
        qs = stages.tag(llm, work, "G9_RIAZI", [1, 2])
        assert all(q["status"] == "verified" for q in qs), {q["key"]: q["status"] for q in qs}
        assert all(q["concept_id"] == "G9_RIAZI_ch1_l2_k1" for q in qs)
        first_calls = fake.calls
        # rerun: everything from cache, zero new calls
        llm2 = CachedLLM(fake, stages.paths(work)["llm"], "t", allow_calls=False)
        stages.extract(llm2, work); stages.assemble(work); stages.solve(llm2, work)
        stages.tag(llm2, work, "G9_RIAZI", [1, 2])
        assert fake.calls == first_calls and llm2.cache_hits > 0
        stages.report(work)
        config.BANK_ROOT = os.path.join(tmp, "bank")
        res = bank.write(work, 9, "test_bank", "G9_RIAZI", "t9")
        assert res["written"] == len(qs), res
        res2 = bank.write(work, 9, "test_bank", "G9_RIAZI", "t9")
        assert res2["written"] == 0 and res2["skipped_existing"] == len(qs)
        meta = json.load(open(os.path.join(res["folder"], f"t9_{qs[0]['key']}", "meta.json"), encoding="utf-8"))
        assert meta["answer_confidence"] == "high" and meta["concept_id"] == "G9_RIAZI_ch1_l2_k1"
        print(f"pipeline OK: {len(blocks)} blocks, {len(qs)} questions, {first_calls} fake calls, rerun cached")
    finally:
        config.BANK_ROOT = old_bank
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    test_checks()
    test_taxonomy()
    if len(sys.argv) > 1:
        test_pipeline(sys.argv[1])
