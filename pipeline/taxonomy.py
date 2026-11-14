"""Book catalog + closed concept taxonomy, and validation between them."""
import json
import os

from . import config


def load_catalog(path: str | None = None) -> list:
    with open(path or config.CATALOG, encoding="utf-8") as f:
        return json.load(f)


def load_taxonomy(book_id: str, tax_dir: str | None = None) -> dict:
    path = os.path.join(tax_dir or config.TAXONOMY_DIR, f"{book_id}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no taxonomy for {book_id}: create {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def lesson_index(catalog: list) -> dict:
    """lesson_id -> {book, chapter, lesson}"""
    out = {}
    for b in catalog:
        for ch in b["chapters"]:
            for les in ch["lessons"]:
                if isinstance(les, dict):
                    out[les["id"]] = {"book": b, "chapter": ch, "lesson": les}
    return out


def validate(book_id: str) -> list:
    """problems in a taxonomy file: unknown lessons, duplicate ids, broken prereqs, cycles"""
    tax = load_taxonomy(book_id)
    lessons = lesson_index(load_catalog())
    problems, ids = [], set()
    concepts = tax["concepts"]
    for c in concepts:
        if c["id"] in ids:
            problems.append(f"duplicate id {c['id']}")
        ids.add(c["id"])
        if c["lesson_id"] not in lessons:
            problems.append(f"{c['id']}: unknown lesson {c['lesson_id']}")
        elif lessons[c["lesson_id"]]["book"]["book_id"] != book_id:
            problems.append(f"{c['id']}: lesson belongs to another book")
        for field in ("title", "key_point"):
            if not c.get(field):
                problems.append(f"{c['id']}: missing {field}")
    for c in concepts:
        for p in c.get("prereqs", []):
            if p not in ids:
                problems.append(f"{c['id']}: unknown prereq {p}")
    # cycle check (prereqs must form a DAG)
    graph = {c["id"]: c.get("prereqs", []) for c in concepts}
    state = {}

    def visit(n, path):
        if state.get(n) == 1:
            problems.append("prereq cycle: " + " -> ".join(path + [n]))
            return
        if state.get(n) == 2:
            return
        state[n] = 1
        for m in graph.get(n, []):
            visit(m, path + [n])
        state[n] = 2

    for n in graph:
        visit(n, [])
    return problems


def concepts_for(book_id: str, chapters: list | None = None) -> list:
    tax = load_taxonomy(book_id)
    out = [c for c in tax["concepts"] if not c.get("retired")]
    if chapters:
        keep = {f"{book_id}_ch{n}_" for n in chapters}
        out = [c for c in out if any(c["lesson_id"].startswith(k) for k in keep)]
    return out
