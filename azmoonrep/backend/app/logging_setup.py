"""Structured (one JSON object per line) logging for the API.

- every request: method, path, status, duration, request id (also returned in the
  X-Request-ID header, so a student's error report can be matched to the log line)
- every unhandled error: full traceback in the log, a plain message to the client
- an "audit" logger for admin actions (approve, reject, edit, import)
"""
import json
import logging
import os
import sys
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {"t": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
                "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for key in ("request_id", "method", "path", "status", "ms", "user", "action",
                    "target", "detail", "ip"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(LEVEL)
    # uvicorn's own access log duplicates ours
    logging.getLogger("uvicorn.access").disabled = True


log = logging.getLogger("azmoon")
audit_log = logging.getLogger("azmoon.audit")


def audit(user: str, action: str, target: str = "", detail: str | None = None):
    audit_log.info(f"{action} {target}", extra={"user": user, "action": action,
                                               "target": target, "detail": detail})


def client_ip(request: Request) -> str:
    """the real client address. X-Forwarded-For is trusted only behind our own proxy
    (TRUST_PROXY=1), otherwise anyone could fake it to dodge rate limits."""
    if os.getenv("TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


async def request_logger(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.request_id = rid
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error", extra={"request_id": rid, "method": request.method,
                                                "path": request.url.path})
        response = JSONResponse({"detail": "خطای داخلی سرور", "request_id": rid}, status_code=500)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    if not request.url.path.startswith("/static"):
        log.info(f"{request.method} {request.url.path} {response.status_code}",
                 extra={"request_id": rid, "method": request.method, "path": request.url.path,
                        "status": response.status_code, "ms": ms, "ip": client_ip(request)})
    return response
