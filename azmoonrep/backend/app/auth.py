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

def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${h}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)

def make_token(user: dict) -> str:
    payload = {
        "sub": user["username"],
        "uid": str(user["_id"]),
        "role": user.get("role", "student"),
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
    return user

def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "admin only")
    return user
