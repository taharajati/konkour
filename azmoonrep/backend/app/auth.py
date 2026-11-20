import time
import hashlib
import hmac
import os
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from . import db
from .config import JWT_SECRET, JWT_EXPIRE_HOURS

bearer = HTTPBearer(auto_error=False)

PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "600000"))     # OWASP 2023; older accounts keep 100k until their next login

def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()

def hash_password(password: str, salt: str | None = None) -> str:
    """new format: pbkdf2$<iterations>$<salt>$<hash>"""
    salt = salt or os.urandom(16).hex()
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${_pbkdf2(password, salt, PBKDF2_ITERATIONS)}"

def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    try:
        if parts[0] == "pbkdf2" and len(parts) == 4:
            return hmac.compare_digest(_pbkdf2(password, parts[2], int(parts[1])), parts[3])
        if len(parts) == 2:                    # legacy: salt$hash, 100k iterations
            return hmac.compare_digest(_pbkdf2(password, parts[0], 100_000), parts[1])
    except (ValueError, TypeError):
        pass
    return False

def needs_rehash(stored: str) -> bool:
    return not stored.startswith(f"pbkdf2${PBKDF2_ITERATIONS}$")

_DUMMY_HASH = hash_password("not-a-real-password", "0" * 32)

def burn_time():
    """same work for unknown usernames, so response time does not reveal which exist"""
    verify_password("x", _DUMMY_HASH)

def make_token(user: dict) -> str:
    payload = {
        "sub": user["username"],
        "uid": str(user["_id"]),
        "role": user.get("role", "student"),
        "tv": user.get("token_version", 0),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(401, "not authenticated")
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token")
    user = db.db.users.find_one({"username": payload["sub"]})
    if not user:
        raise HTTPException(401, "user not found")
    # "log out everywhere" bumps token_version: older tokens stop working at once
    if payload.get("tv", 0) != user.get("token_version", 0):
        raise HTTPException(401, "invalid or expired token")
    return user

def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "admin only")
    return user
