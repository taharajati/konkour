import os
from pymongo import MongoClient, ASCENDING
from .config import MONGO_URL, MONGO_USER, MONGO_PASS, MONGO_DB

_client_kwargs = {}
if MONGO_USER:
    _client_kwargs = {"username": MONGO_USER, "password": MONGO_PASS,
                      "authSource": os.getenv("MONGO_AUTH_SOURCE", "admin")}

client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000, **_client_kwargs)
db = client[MONGO_DB]

def ensure_indexes():
    db.users.create_index([("username", ASCENDING)], unique=True)
    db.questions.create_index([("concept_id", ASCENDING)])
    db.questions.create_index([("public_id", ASCENDING)], unique=True)
    db.concepts.create_index([("concept_id", ASCENDING)], unique=True)
    db.concept_state.create_index([("student_id", ASCENDING), ("concept_id", ASCENDING)], unique=True)
    db.concept_state.create_index([("student_id", ASCENDING), ("due_date", ASCENDING)])
    for old in ("student_id_1_date_1", "student_id_1_date_1_book_id_1"):
        try:
            db.sessions.drop_index(old)          # upgrade: replaced by the unique key below
        except Exception:
            pass
    # one session per student, day and scope: concurrent "start today" requests can't
    # create duplicates. Sessions are rebuilt daily, so old duplicates can be cleared.
    _dedupe_sessions()
    db.sessions.create_index([("student_id", ASCENDING), ("date", ASCENDING),
                              ("book_id", ASCENDING), ("chapter_id", ASCENDING)],
                             unique=True, name="session_key")
    db.practice_sessions.create_index([("student_id", ASCENDING)], unique=True)
    db.placement_sessions.create_index([("student_id", ASCENDING)], unique=True)
    db.responses.create_index([("student_id", ASCENDING), ("answered_at", ASCENDING)])
    db.responses.create_index([("question_id", ASCENDING)])
    db.concepts.create_index([("chapter_id", ASCENDING)])
    db.concepts.create_index([("book_id", ASCENDING)])
    db.concepts.create_index([("order_in_curriculum", ASCENDING)])
    db.chapters.create_index([("book_id", ASCENDING)])
    db.books.create_index([("book_id", ASCENDING)], unique=True)
    # rate-limit counters and login codes delete themselves when they expire
    db.rate_limits.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    db.otp_codes.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    db.otp_codes.create_index([("phone", ASCENDING)], unique=True)
    # sparse: accounts without a phone (admins, old username accounts) are not indexed.
    # Never store phone: None, or two such accounts would collide.
    db.users.create_index([("phone", ASCENDING)], unique=True, sparse=True)


def _dedupe_sessions():
    """keep the session with the most answers for each key, drop the other copies"""
    groups = db.sessions.aggregate([
        {"$group": {"_id": {"s": "$student_id", "d": "$date", "b": "$book_id",
                            "c": "$chapter_id"},
                    "ids": {"$push": "$_id"}, "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 1}}}])
    for g in groups:
        docs = list(db.sessions.find({"_id": {"$in": g["ids"]}}, {"slots.status": 1}))
        docs.sort(key=lambda d: -sum(1 for s in d.get("slots", []) if s.get("status") == "answered"))
        db.sessions.delete_many({"_id": {"$in": [d["_id"] for d in docs[1:]]}})
