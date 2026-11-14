"""Question-bank pipeline CLI. Run from the workspace root (D:\\beh):

  python -m pipeline prepare  <pdf>                      render pages, cut question blocks (free)
  python -m pipeline estimate <pdf>                      calls and cost before spending
  python -m pipeline run      <pdf> --book G9_RIAZI --chapters 1,2 --grade 9 --bank <name> --prefix <id> [--yes]
  python -m pipeline report   <pdf>
  python -m pipeline write    <pdf> --book ... --grade 9 --bank <name> --prefix <id> [--overwrite]
  python -m pipeline validate-taxonomy G9_RIAZI
  python -m pipeline apply-map <bank folder> <map json>
  python -m pipeline generate <export.json> [--only id,id] [--yes]   new variants (export from admin panel)
  python -m pipeline draft-taxonomy --book C110211 --chapters 4 --pages 75-99 [--yes]

`run` does prepare -> extract -> assemble -> solve -> tag -> report. LLM answers are
cached per block/question under the work folder; without --yes only cached answers are
used, so nothing is billed by accident.
"""
import argparse
import os
import re
import sys

from . import bank, config, stages, taxonomy
from .llm import AnthropicProvider, CachedLLM, LLMError


def work_dir(pdf: str) -> str:
    name = os.path.splitext(os.path.basename(pdf))[0]
    slug = re.sub(r"[^\w\u0600-\u06FF]+", "_", name).strip("_")
    return os.path.join(config.WORK_DIR, slug)


def make_llm(work: str, allow: bool) -> CachedLLM:
    provider = AnthropicProvider() if allow else None
    return CachedLLM(provider, stages.paths(work)["llm"], config.PROMPT_VERSION,
                     allow_calls=allow)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="pipeline")
    ap.add_argument("cmd", choices=["prepare", "estimate", "run", "report", "write",
                                    "validate-taxonomy", "apply-map", "generate",
                                    "draft-taxonomy"])
    ap.add_argument("--only", help="generate: comma list of concept ids")
    ap.add_argument("--pages", help="draft-taxonomy: PDF page range of the chapter, e.g. 75-99")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--book")
    ap.add_argument("--chapters", help="comma list, e.g. 1,2")
    ap.add_argument("--grade", type=int)
    ap.add_argument("--bank", help="bank folder name under question_bank/grade<N>/")
    ap.add_argument("--prefix", help="question id prefix, e.g. g9_real2")
    ap.add_argument("--yes", action="store_true", help="allow paid LLM calls")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args(argv)
    chapters = [int(x) for x in a.chapters.split(",")] if a.chapters else None

    if a.cmd == "validate-taxonomy":
        problems = taxonomy.validate(a.args[0])
        print("\n".join(problems) if problems else "taxonomy OK")
        return 1 if problems else 0
    if a.cmd == "apply-map":
        print(bank.apply_map(a.args[0], a.args[1]))
        return 0
    if a.cmd == "generate":
        from . import generate
        print("estimate:", generate.estimate(a.args[0]))
        work = os.path.join(config.WORK_DIR, "generation")
        llm = make_llm(work, a.yes)
        try:
            print(generate.run(llm, a.args[0], work,
                               only=a.only.split(",") if a.only else None))
        except LLMError as e:
            print(f"stopped: {e}")
            return 2
        finally:
            print(f"LLM: {llm.calls} paid calls, {llm.cache_hits} cached")
        return 0
    if a.cmd == "draft-taxonomy":
        from . import draft
        if not (a.book and chapters and len(chapters) == 1 and a.pages):
            ap.error("draft-taxonomy needs --book, one --chapters N and --pages A-B")
        first, last = (int(x) for x in a.pages.split("-"))
        work = os.path.join(config.WORK_DIR, f"draft_{a.book}")
        llm = make_llm(work, a.yes)
        try:
            print(draft.draft_chapter(llm, a.book, chapters[0], (first, last)))
        except LLMError as e:
            print(f"stopped: {e}")
            return 2
        return 0

    pdf = a.args[0]
    work = work_dir(pdf)
    if a.cmd in ("prepare", "estimate", "run"):
        blocks = stages.prepare(pdf, work)
        print(f"{len(blocks)} blocks -> {work}")
        if a.cmd != "run":
            print("estimate:", stages.estimate(blocks))
            return 0
        if not (a.book and a.grade):
            ap.error("run needs --book and --grade")
        print("estimate:", stages.estimate(blocks))
        llm = make_llm(work, a.yes)
        try:
            stages.extract(llm, work)
            qs = stages.assemble(work)
            print(f"{len(qs)} questions assembled")
            stages.solve(llm, work)
            stages.tag(llm, work, a.book, chapters)
        except LLMError as e:
            print(f"stopped: {e}")
            return 2
        finally:
            print(f"LLM: {llm.calls} paid calls, {llm.cache_hits} cached, "
                  f"{llm.tokens_in} in / {llm.tokens_out} out tokens")
        print(stages.report(work))
        return 0
    if a.cmd == "report":
        print(stages.report(work))
        return 0
    if a.cmd == "write":
        if not (a.book and a.grade and a.bank and a.prefix):
            ap.error("write needs --book --grade --bank --prefix")
        print(bank.write(work, a.grade, a.bank, a.book, a.prefix, overwrite=a.overwrite))
        return 0


if __name__ == "__main__":
    sys.exit(main())
