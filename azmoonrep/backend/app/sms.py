"""Sending login codes by SMS. One small interface, one adapter per provider.

console    development only: the code is written to the log (refused in prod, see config)
kavenegar  Kavenegar "verify/lookup" with a pre-approved template; the template must
           contain %token%. Not tested against the live service from here: send yourself
           a code on staging before switching production to it.
"""
import json
import logging
import urllib.parse
import urllib.request

from .config import SMS_API_KEY, SMS_PROVIDER, SMS_TEMPLATE

log = logging.getLogger("azmoon.sms")


class SMSError(RuntimeError):
    pass


def send_code(phone: str, code: str) -> None:
    if SMS_PROVIDER == "console":
        log.warning(f"[dev] login code for {phone}: {code}")
        return
    if SMS_PROVIDER == "kavenegar":
        return _kavenegar(phone, code)
    raise SMSError(f"unknown SMS_PROVIDER {SMS_PROVIDER!r}")


def _kavenegar(phone: str, code: str) -> None:
    if not SMS_API_KEY:
        raise SMSError("SMS_API_KEY is not set")
    q = urllib.parse.urlencode({"receptor": phone, "token": code, "template": SMS_TEMPLATE})
    url = f"https://api.kavenegar.com/v1/{urllib.parse.quote(SMS_API_KEY)}/verify/lookup.json?{q}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            body = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 - network or HTTP error: report, never log the key
        raise SMSError(f"kavenegar request failed: {type(e).__name__}") from None
    status = (body.get("return") or {}).get("status")
    if status != 200:
        raise SMSError(f"kavenegar status {status}: {(body.get('return') or {}).get('message')}")
