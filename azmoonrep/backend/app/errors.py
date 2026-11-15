"""One error shape for the whole API:

    {"detail": "<message a person can read>", "code": "<stable machine code>",
     "request_id": "<id from the log>", "fields": [...]}        # fields: validation only

`detail` is always a string (clients show it as is); `code` is what clients branch on.
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

CODES = {400: "bad_request", 401: "unauthenticated", 403: "forbidden", 404: "not_found",
         405: "method_not_allowed", 409: "conflict", 422: "invalid_input",
         429: "rate_limited", 500: "internal", 502: "upstream_failed", 503: "unavailable"}

DEFAULT_FA = {401: "لطفاً دوباره وارد شو.", 403: "اجازهٔ این کار را نداری.",
              404: "پیدا نشد.", 405: "این درخواست پشتیبانی نمی‌شود.",
              429: "تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره امتحان کن."}


def _rid(request: Request):
    return getattr(request.state, "request_id", None)


def install(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        code = CODES.get(exc.status_code, "error")
        if isinstance(detail, dict):                       # raise HTTPException(.., {"code":..,"detail":..})
            code = detail.get("code", code)
            detail = detail.get("detail")
        if not isinstance(detail, str) or detail in ("Not Found", "Method Not Allowed", "Forbidden"):
            detail = DEFAULT_FA.get(exc.status_code, str(detail))
        return JSONResponse({"detail": detail, "code": code, "request_id": _rid(request)},
                            status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "problem": e["msg"]}
                  for e in exc.errors()]
        names = "، ".join(f["field"] for f in fields if f["field"]) or "ورودی"
        return JSONResponse({"detail": f"ورودی نامعتبر است: {names}", "code": "invalid_input",
                             "fields": fields, "request_id": _rid(request)}, status_code=422)
