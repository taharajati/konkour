"""Offline tests for variant generation and key-point drafting (fake model, no cost).
Run from the workspace root:  python -m pipeline.tests.test_generate"""
import json
import os
import shutil
import sys
import tempfile

from pipeline import config, draft, generate, taxonomy
from pipeline.llm import CachedLLM, Provider


class FakeGen(Provider):
    """first variant copies the example (must be rejected as too similar), the second is
    new but the solver disagrees (rejected), the third is good"""
    def __init__(self):
        self.n = 0

    def generate_json(self, system, content, schema, model, effort):
        u = {"input_tokens": 1, "output_tokens": 1}
        if "answer_index" in schema["properties"]:
            self.n += 1
            if self.n == 1:
                return {"stem_md": "کسر $0.\\overline{36}$ کدام است؟", "options": ["$\\frac{4}{11}$", "$\\frac{9}{25}$", "$\\frac{36}{100}$", "$\\frac{6}{11}$"],
                        "answer_index": 1, "solution_md": "پاسخ: گزینهٔ ۱", "difficulty": 2}, u
            stem = f"عدد $0.\\overline{{{12 + self.n}}}$ با کدام کسر برابر است؟ (متن تازه {self.n})"
            opts = [f"$\\frac{{{self.n}}}{{{d}}}$" for d in (99, 100, 90, 9)]
            return {"stem_md": stem, "options": opts,
                    "answer_index": 1, "solution_md": "پاسخ: گزینهٔ ۱", "difficulty": 2}, u
        if "solver_option" in schema["properties"]:
            return {"solver_option": 2 if self.n == 2 else 1, "issues": [],
                    "solution_md": "...", "confidence": "high"}, u
        return {"lessons": [{"lesson_id": "C110211_ch1_l1", "key_points": [
                    {"title": "نکتهٔ الف", "key_point": "متن الف", "prereq_titles": []},
                    {"title": "نکتهٔ ب", "key_point": "متن ب", "prereq_titles": ["نکتهٔ الف"]}]},
                {"lesson_id": "BOGUS", "key_points": [{"title": "x", "key_point": "y", "prereq_titles": []}]}]}, u


def test_generate():
    tmp = tempfile.mkdtemp(prefix="gen_test_")
    old = config.BANK_ROOT
    try:
        config.BANK_ROOT = os.path.join(tmp, "bank")
        export = {"items": [{"concept_id": "G9_RIAZI_ch2_l1_k3", "title": "تبدیل اعشار متناوب به کسر",
                             "key_point": "...", "book_id": "G9_RIAZI", "grade": 9, "lesson_title": "عددهای گویا",
                             "need": 1, "examples": [{"public_id": "ex1", "stem_md": "کسر $0.\\overline{36}$ کدام است؟",
                                                      "options": ["$\\frac{4}{11}$", "$\\frac{9}{25}$", "$\\frac{36}{100}$", "$\\frac{6}{11}$"],
                                                      "answer_option": 1, "solution_md": "", "difficulty": 2}]}]}
        f = os.path.join(tmp, "export.json")
        json.dump(export, open(f, "w", encoding="utf-8"), ensure_ascii=False)
        fake = FakeGen()
        llm = CachedLLM(fake, os.path.join(tmp, "cache"), "t")
        out = generate.run(llm, f, tmp, log=lambda *a: None)
        assert out["written"] == 1 and out["rejected"] == 2, out
        folder = os.path.join(config.BANK_ROOT, "grade9")
        bank = os.listdir(folder)[0]
        qdir = os.path.join(folder, bank, os.listdir(os.path.join(folder, bank))[0])
        meta = json.load(open(os.path.join(qdir, "meta.json"), encoding="utf-8"))
        assert meta["source"]["kind"] == "ai_generated" and meta["concept_id"] == "G9_RIAZI_ch2_l1_k3"
        report = json.load(open(os.path.join(tmp, "generation_report.json"), encoding="utf-8"))
        whys = " ".join(" ".join(r["why"]) for r in report[0]["rejected"])
        assert "similar" in whys and "حل مستقل" in whys
        print("generate OK:", out)
    finally:
        config.BANK_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_draft(pdf_dir):
    tmp = tempfile.mkdtemp(prefix="draft_test_")
    old = config.TAXONOMY_DIR
    try:
        config.TAXONOMY_DIR = tmp
        llm = CachedLLM(FakeGen(), os.path.join(tmp, "cache"), "t")
        res = draft.draft_chapter(llm, "C110211", 1, (7, 9), log=lambda *a: None)
        assert res["added"] == 2 and not res["problems"], res
        tax = json.load(open(os.path.join(tmp, "C110211.json"), encoding="utf-8"))
        a, b = tax["concepts"]
        assert a["id"] == "C110211_ch1_l1_k1" and b["prereqs"] == [a["id"]]
        again = draft.draft_chapter(llm, "C110211", 1, (7, 9), log=lambda *a: None)
        assert again["skipped"], "an existing chapter is never redrafted"
        print("draft OK")
    finally:
        config.TAXONOMY_DIR = old
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    test_generate()
    test_draft(None)
