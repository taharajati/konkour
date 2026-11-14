# Question-bank pipeline

Turns an exam PDF into question folders in `question_bank/`, with every answer key checked
and every question tagged with a key point from the closed list in `taxonomy/`.

```
PDF ─ prepare ─▶ page images ─▶ question blocks (cut at the table rules)       free
      extract ─▶ one model call per block: stem, options in printed order,
                 figures, answer-key and solution pages                          paid
      assemble ▶ questions + printed keys + printed solutions, rule checks       free
      solve ───▶ independent solve without the key                              paid
      tag ─────▶ one concept from the closed list (enforced by JSON schema)     paid
      report ──▶ work/<pdf>/report.md                                           free
      write ───▶ question_bank/grade<N>/<bank>/<id>/ (never overwrites)         free
```

Every question gets a `verification.status`:

| status | meaning | what the manager does |
|---|---|---|
| `verified` | printed key and independent solve agree, no rule problems | spot-check and approve |
| `conflict` | key and solve disagree | decide from the scan |
| `solver_only` | no printed key found | check the solution |
| `needs_fix` | garbled text, wrong option count, two correct options… | fix in the admin panel |
| `written` | written (non-multiple-choice) question | check the solution |

Nothing is served to students until the manager approves it in the admin panel, whatever
the status says.

## Setup

```bash
python -m venv pipeline/.venv
pipeline/.venv/Scripts/python -m pip install -r pipeline/requirements.txt
```

Credentials: `ANTHROPIC_API_KEY`, or an `ant auth login` profile. Models and effort are in
`config.py` (environment variables override them).

## Use (from the workspace root)

```bash
python -m pipeline estimate "konkur_math_tests/9/<file>.pdf"
python -m pipeline run "konkur_math_tests/9/<file>.pdf" --book G9_RIAZI --chapters 1,2 --grade 9 --yes
python -m pipeline write "konkur_math_tests/9/<file>.pdf" --book G9_RIAZI --grade 9 --bank real_numbers_test6 --prefix g9_real6
```

Without `--yes`, only cached model answers are used, so nothing is billed by accident.
Model answers are cached per block and question under `work/<pdf>/llm_cache/`: re-running
after a code change costs nothing. Changing a prompt? Bump `PROMPT_VERSION` in `config.py`.

## New variants for thin key points

Admin panel → آمار → «فهرست نکته‌های نیازمند سؤال» downloads `generation-export.json`:
every key point with fewer than 5 approved questions, with up to 3 approved examples.

```bash
python -m pipeline generate generation-export.json            # prints the estimate, cached answers only
python -m pipeline generate generation-export.json --yes      # paid: generate + independent solve
```

Each variant is kept only if it passes the rule checks, is not a near-copy of an example or
an earlier variant (3-gram similarity < 0.8), and an independent solve agrees with its key.
Kept variants go to `question_bank/grade<N>/generated_<date>/` with source `ai_generated`;
rejected ones and why are in `work/generation/generation_report.json`. Import, then approve
in the admin panel like any other question.

## Key points for a new chapter

```bash
python -m pipeline draft-taxonomy --book C110211 --chapters 4 --pages 75-99 --yes
```

Reads the chapter pages (PDF page numbers, from the book's table of contents) and adds a
draft key-point list for each lesson to `taxonomy/<book_id>.json`. A chapter that already
has key points is skipped, so ids never change. Have a teacher review the draft before
tagging questions against it.

## Taxonomy

`taxonomy/<book_id>.json` is the closed list of key points per lesson (ids never change;
retire instead of deleting). Check it with `python -m pipeline validate-taxonomy G9_RIAZI`.
Old bank folders get concept ids from a mapping file:
`python -m pipeline apply-map <bank folder> taxonomy/mappings/<file>.json`.

## Tests

```bash
python -m pipeline.tests.test_offline "konkur_math_tests/9/<file>.pdf"
```

Uses a fake model: no network, no key, no cost.
