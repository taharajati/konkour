"""Data migrations: small, ordered, run once each, recorded in `schema_migrations`.

Add a function to MIGRATIONS (never reorder or edit one that has shipped). They run at
startup before the API serves requests; each must be safe to run on an empty database
and idempotent enough to be re-run after a crash halfway.
"""
import datetime as dt
import logging

from . import clock, db

log = logging.getLogger("azmoon.migrations")


def m001_due_day(d):
    """concept_state: Tehran `due_day` string for states that only have the old due_date"""
    n = 0
    for st in d.concept_state.find({"due_day": {"$exists": False}, "due_date": {"$exists": True}}):
        due = st["due_date"]
        if isinstance(due, dt.datetime):
            d.concept_state.update_one({"_id": st["_id"]},
                                       {"$set": {"due_day": clock.day_of(due).isoformat()}})
            n += 1
    return n


def m002_figure_objects(d):
    """questions.figures: plain file names -> {file, w, h} (sizes filled by the next import)"""
    n = 0
    for q in d.questions.find({"figures.0": {"$type": "string"}}, {"figures": 1}):
        figs = [{"file": f, "w": None, "h": None} if isinstance(f, str) else f for f in q["figures"]]
        d.questions.update_one({"_id": q["_id"]}, {"$set": {"figures": figs}})
        n += 1
    return n


def m003_token_version(d):
    """users: token_version for "log out everywhere" """
    return d.users.update_many({"token_version": {"$exists": False}},
                               {"$set": {"token_version": 0}}).modified_count


MIGRATIONS = [("001_due_day", m001_due_day),
              ("002_figure_objects", m002_figure_objects),
              ("003_token_version", m003_token_version)]


def run() -> list:
    done = {m["_id"] for m in db.db.schema_migrations.find({}, {"_id": 1})}
    applied = []
    for name, fn in MIGRATIONS:
        if name in done:
            continue
        changed = fn(db.db)
        db.db.schema_migrations.insert_one({"_id": name, "applied_at": clock.now_utc(),
                                            "changed": changed})
        log.info(f"migration {name}: {changed} documents")
        applied.append(name)
    return applied
