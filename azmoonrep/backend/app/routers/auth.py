import datetime as dt
import hashlib
import hmac
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, Field

from .. import auth, clock, db, ratelimit, scheduler, sms
from ..config import (DEFAULT_DAILY_LOAD, JWT_SECRET, OTP_ENABLED, OTP_TTL_SECONDS,
                      PASSWORD_LOGIN_FOR_STUDENTS)
from ..logging_setup import audit, client_ip

router = APIRouter(prefix="/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,32}$")
MIN_PASSWORD = 8


class Credentials(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)

class Register(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)
    grade: int | None = None
    display_name: str | None = Field(default=None, max_length=40)

@router.post("/register")
def register(body: Register, request: Request):
    if not PASSWORD_LOGIN_FOR_STUDENTS:
        raise HTTPException(403, "ثبت‌نام فقط با شمارهٔ موبایل ممکن است.")
    ratelimit.hit("register-ip", client_ip(request), limit=10, window=3600)
    body.username = body.username.strip().lower()
    if not USERNAME_RE.match(body.username):
        raise HTTPException(422, "نام کاربری باید ۳ تا ۳۲ حرف انگلیسی، عدد یا _ . - باشد.")
    if len(body.password) < MIN_PASSWORD:
        raise HTTPException(422, f"رمز عبور باید دست‌کم {MIN_PASSWORD} کاراکتر باشد.")
    if db.db.users.find_one({"username": body.username}):
        raise HTTPException(409, "این نام کاربری قبلاً گرفته شده است.")
    doc = {"username": body.username,
           "password_hash": auth.hash_password(body.password),
           "role": "student",
           "grade": body.grade,
           "display_name": (body.display_name or body.username).strip()[:40],
           "created_at": clock.now_utc()}
    try:
        res = db.db.users.insert_one(doc)
    except DuplicateKeyError:                      # two sign-ups with the same name at once
        raise HTTPException(409, "این نام کاربری قبلاً گرفته شده است.")
    return {"id": str(res.inserted_id), "username": body.username, "role": "student"}

LOGIN_WINDOW = 900

@router.post("/login")
def login(body: Credentials, request: Request):
    ip = client_ip(request)
    name = body.username.strip().lower()
    ratelimit.hit("login-ip", ip, limit=120, window=LOGIN_WINDOW)
    # per account: only FAILED attempts count, so the owner's own good logins never add up
    # and a stranger needs 10 wrong guesses (not just traffic) to slow down guessing
    ratelimit.blocked("login-user", name, limit=10, window=LOGIN_WINDOW)
    user = db.db.users.find_one({"username": name}) or db.db.users.find_one({"username": body.username})
    if not user or not user.get("password_hash"):
        auth.burn_time()
        ratelimit.fail("login-user", name, LOGIN_WINDOW)
        raise HTTPException(401, "نام کاربری یا رمز عبور اشتباه است.")
    if not auth.verify_password(body.password, user["password_hash"]):
        ratelimit.fail("login-user", name, LOGIN_WINDOW)
        raise HTTPException(401, "نام کاربری یا رمز عبور اشتباه است.")
    if auth.needs_rehash(user["password_hash"]):
        db.db.users.update_one({"_id": user["_id"]},
                               {"$set": {"password_hash": auth.hash_password(body.password)}})
    if user.get("role") != "admin" and not PASSWORD_LOGIN_FOR_STUDENTS:
        raise HTTPException(403, "ورود دانش‌آموزان فقط با شمارهٔ موبایل است.")
    ratelimit.reset("login-user", name, LOGIN_WINDOW)
    if user.get("role") == "admin":
        audit(user["username"], "admin_login", detail=ip)
    return {"access_token": auth.make_token(user), "role": user.get("role", "student"),
            "display_name": user.get("display_name", body.username)}

# ---------------------------------------------------------------- phone login (OTP)

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
OTP_MAX_ATTEMPTS = 5


def normalize_phone(raw: str) -> str:
    """Iranian mobile in 09xxxxxxxxx form; accepts Persian digits, spaces, +98/0098/98"""
    p = re.sub(r"[\s\-()]", "", (raw or "").translate(FA_DIGITS))
    p = re.sub(r"^(\+98|0098|98)", "0", p)
    if re.fullmatch(r"9\d{9}", p):
        p = "0" + p
    if not re.fullmatch(r"09\d{9}", p):
        raise HTTPException(422, "شمارهٔ موبایل معتبر نیست (مثل ۰۹۱۲۱۲۳۴۵۶۷).")
    return p


def _code_hash(phone: str, code: str) -> str:
    return hmac.new(JWT_SECRET.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


class OtpRequest(BaseModel):
    phone: str = Field(max_length=32)

class OtpVerify(BaseModel):
    phone: str = Field(max_length=32)
    code: str = Field(max_length=12)

@router.post("/otp/request")
def otp_request(body: OtpRequest, request: Request):
    if not OTP_ENABLED:
        raise HTTPException(404, "ورود با پیامک فعال نیست.")
    phone = normalize_phone(body.phone)
    ip = client_ip(request)
    ratelimit.hit("otp-phone-min", phone, limit=1, window=60,
                  message="کد قبلی تازه فرستاده شده؛ یک دقیقه صبر کن.")
    ratelimit.hit("otp-phone-hour", phone, limit=5, window=3600)
    ratelimit.hit("otp-ip-hour", ip, limit=20, window=3600)
    code = f"{secrets.randbelow(100000):05d}"
    now = clock.now_utc()
    db.db.otp_codes.update_one(
        {"phone": phone},
        {"$set": {"hash": _code_hash(phone, code), "attempts": 0, "created_at": now,
                  "expires_at": now + dt.timedelta(seconds=OTP_TTL_SECONDS)}},
        upsert=True)
    try:
        sms.send_code(phone, code)
    except sms.SMSError as e:
        db.db.otp_codes.delete_one({"phone": phone})
        raise HTTPException(502, "ارسال پیامک ممکن نشد؛ کمی بعد دوباره امتحان کن.") from e
    # same answer whether or not an account exists for this number
    return {"ok": True, "ttl": OTP_TTL_SECONDS, "phone": phone}

@router.post("/otp/verify")
def otp_verify(body: OtpVerify, request: Request):
    if not OTP_ENABLED:
        raise HTTPException(404, "ورود با پیامک فعال نیست.")
    phone = normalize_phone(body.phone)
    ratelimit.hit("otp-verify-ip", client_ip(request), limit=40, window=3600)
    code = body.code.translate(FA_DIGITS).strip()
    rec = db.db.otp_codes.find_one({"phone": phone})
    if not rec or rec["expires_at"] < clock.now_utc():
        raise HTTPException(400, "کد منقضی شده؛ دوباره درخواست کن.")
    if rec.get("attempts", 0) >= OTP_MAX_ATTEMPTS:
        db.db.otp_codes.delete_one({"_id": rec["_id"]})
        raise HTTPException(429, "تعداد تلاش‌ها زیاد شد؛ کد تازه بگیر.")
    if not hmac.compare_digest(rec["hash"], _code_hash(phone, code)):
        db.db.otp_codes.update_one({"_id": rec["_id"]}, {"$inc": {"attempts": 1}})
        left = OTP_MAX_ATTEMPTS - rec.get("attempts", 0) - 1
        raise HTTPException(400, f"کد اشتباه است ({left} تلاش دیگر).")
    db.db.otp_codes.delete_one({"_id": rec["_id"]})   # one code, one login

    user = db.db.users.find_one({"phone": phone})
    new_user = user is None
    if new_user:
        doc = {"username": phone, "phone": phone, "role": "student",
               "display_name": "دانش‌آموز", "onboarded": False, "created_at": clock.now_utc()}
        doc["_id"] = db.db.users.insert_one(doc).inserted_id
        user = doc
    if user.get("role") == "admin":
        raise HTTPException(403, "مدیرها با نام کاربری و رمز وارد می‌شوند.")
    return {"access_token": auth.make_token(user), "role": "student", "new_user": new_user,
            "display_name": user.get("display_name")}

@router.post("/logout-all")
def logout_everywhere(user: dict = Depends(auth.current_user)):
    """invalidate every token of this account (lost phone, shared computer)"""
    db.db.users.update_one({"_id": user["_id"]}, {"$inc": {"token_version": 1}})
    audit(user["username"], "logout_all")
    return {"ok": True}

@router.get("/me/stats")
def my_stats(user: dict = Depends(auth.current_user)):
    return scheduler.student_stats(user["_id"])

@router.get("/me/progress")
def my_progress(book_id: str | None = None, user: dict = Depends(auth.current_user)):
    """progress over the whole plan, or scoped to one book (book switcher)"""
    if book_id:
        chapters = [c["chapter_id"] for c in
                    db.db.chapters.find({"book_id": book_id}, {"chapter_id": 1})]
        u = dict(user)
        u["scope_chapter_ids"] = chapters
        return scheduler.student_progress(u)
    return scheduler.student_progress(user)

@router.get("/me/dangerous")
def my_dangerous(limit: int = 8, user: dict = Depends(auth.current_user)):
    """key points the student was CONFIDENT about and still got wrong — the
    highest-value study targets ("dangerous key points")"""
    rows = list(db.db.responses.aggregate([
        {"$match": {"student_id": user["_id"], "correct": False, "confidence": "sure"}},
        {"$group": {"_id": "$concept_id", "n": {"$sum": 1},
                    "last_at": {"$max": "$answered_at"}}},
        {"$sort": {"n": -1, "last_at": -1}},
        {"$limit": max(1, min(limit, 20))}]))
    if not rows:
        return []
    concepts = {c["concept_id"]: c for c in db.db.concepts.find(
        {"concept_id": {"$in": [r["_id"] for r in rows]}},
        {"concept_id": 1, "title": 1, "chapter_title": 1, "book_name": 1})}
    out = [{"concept_id": r["_id"],
            "title": concepts.get(r["_id"], {}).get("title", r["_id"]),
            "chapter_title": concepts.get(r["_id"], {}).get("chapter_title"),
            "book_name": concepts.get(r["_id"], {}).get("book_name"),
            "confident_wrong": r["n"]}
           for r in rows]
    return out

@router.get("/me/wrong")
def my_wrong(user: dict = Depends(auth.current_user)):
    wrong = [q for q in scheduler.last_wrong_questions(user["_id"], limit=50)
             if q.get("review_status") == "approved"]
    titles = {c["concept_id"]: c for c in db.db.concepts.find(
        {"concept_id": {"$in": list({q.get("concept_id") for q in wrong})}},
        {"concept_id": 1, "title": 1, "chapter_title": 1})}
    out = []
    for q in reversed(wrong):                     # most recent mistake first
        c = titles.get(q.get("concept_id"), {})
        stem = re.sub(r"\s+", " ", q.get("stem_md") or "").strip()
        out.append({"public_id": q.get("public_id"), "concept_id": q.get("concept_id"),
                    "concept_title": c.get("title"), "chapter_title": c.get("chapter_title"),
                    "topic": q.get("topic"), "subtopic": q.get("subtopic"),
                    "stem": stem[:140] + ("…" if len(stem) > 140 else "")})
    return out

class PasswordChange(BaseModel):
    current: str = Field(max_length=128)
    new: str = Field(max_length=128)

@router.post("/password")
def change_password(body: PasswordChange, user: dict = Depends(auth.current_user)):
    key = str(user["_id"])
    ratelimit.blocked("pw-change", key, limit=5, window=900)
    if not user.get("password_hash") or not auth.verify_password(body.current, user["password_hash"]):
        ratelimit.fail("pw-change", key, 900)
        raise HTTPException(400, "رمز فعلی اشتباه است.")
    if len(body.new) < MIN_PASSWORD:
        raise HTTPException(422, f"رمز تازه باید دست‌کم {MIN_PASSWORD} کاراکتر باشد.")
    if body.new == body.current:
        raise HTTPException(422, "رمز تازه باید با رمز فعلی فرق کند.")
    db.db.users.update_one({"_id": user["_id"]},
                           {"$set": {"password_hash": auth.hash_password(body.new)},
                            "$inc": {"token_version": 1}})       # every other device is signed out
    audit(user["username"], "password_changed")
    fresh = db.db.users.find_one({"_id": user["_id"]})
    return {"ok": True, "access_token": auth.make_token(fresh)}

@router.get("/me")
def me(user: dict = Depends(auth.current_user)):
    return {"username": user["username"], "role": user.get("role"), "onboarded": user.get("onboarded", False),
            "display_name": user.get("display_name"), "grade": user.get("grade"),
            "scope_book_ids": user.get("scope_book_ids", []),
            "scope_chapter_ids": user.get("scope_chapter_ids", []),
            "daily_load": user.get("daily_load") or DEFAULT_DAILY_LOAD,
            "exam_date": user.get("exam_date")}

DAILY_LOADS = (10, 20, 40)

class Settings(BaseModel):
    daily_load: int | None = None
    exam_date: str | None = None        # "YYYY-MM-DD" (Gregorian), "" to clear
    display_name: str | None = None

@router.patch("/settings")
def update_settings(body: Settings, user: dict = Depends(auth.current_user)):
    upd = {}
    if body.daily_load is not None:
        if body.daily_load not in DAILY_LOADS:
            raise HTTPException(422, "daily_load must be 10, 20 or 40")
        upd["daily_load"] = body.daily_load
    if body.exam_date is not None:
        if body.exam_date:
            try:
                dt.date.fromisoformat(body.exam_date)
            except ValueError:
                raise HTTPException(422, "exam_date must be YYYY-MM-DD")
        upd["exam_date"] = body.exam_date or None
    if body.display_name is not None:
        name = body.display_name.strip()[:40]
        if name:
            upd["display_name"] = name
    if upd:
        db.db.users.update_one({"_id": user["_id"]}, {"$set": upd})
    if "daily_load" in upd:
        # rebuild today's queue with the new size, unless the student already started it
        for s in db.db.sessions.find({"student_id": user["_id"], "date": clock.today_str()}):
            if not any(sl["status"] == "answered" for sl in s["slots"]):
                db.db.sessions.delete_one({"_id": s["_id"]})
    return {"ok": True, **upd}

class Scope(BaseModel):
    book_ids: list[str] = []
    chapter_ids: list[str] = []
    onboarded: bool = True
    daily_load: int | None = None
    exam_date: str | None = None

@router.patch("/scope")
def set_scope(body: Scope, user: dict = Depends(auth.current_user)):
    upd = {"scope_book_ids": body.book_ids, "scope_chapter_ids": body.chapter_ids,
           "onboarded": body.onboarded}
    if body.daily_load is not None:
        if body.daily_load not in DAILY_LOADS:
            raise HTTPException(422, "daily_load must be 10, 20 or 40")
        upd["daily_load"] = body.daily_load
    if body.exam_date:
        try:
            dt.date.fromisoformat(body.exam_date)
        except ValueError:
            raise HTTPException(422, "exam_date must be YYYY-MM-DD")
        upd["exam_date"] = body.exam_date
    db.db.users.update_one({"_id": user["_id"]}, {"$set": upd})
    # the plan changed → today's pre-generated queue is stale; regenerate on next request
    db.db.sessions.delete_many({"student_id": user["_id"],
                                "date": clock.today_str()})
    return {"ok": True}
