"""Phase 5: phone login (OTP), rate limits, health, logging."""
import logging
import re

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.main import app
from app.routers.auth import normalize_phone


@pytest.fixture
def client(fresh_db):
    return TestClient(app)


def _code_from_log(caplog, phone):
    for rec in reversed(caplog.records):
        m = re.search(rf"login code for {phone}: (\d{{5}})", rec.getMessage())
        if m:
            return m.group(1)
    raise AssertionError("no code in log")


@pytest.mark.parametrize("raw,ok", [
    ("09121234567", "09121234567"), ("۰۹۱۲۱۲۳۴۵۶۷", "09121234567"),
    ("+989121234567", "09121234567"), ("0098 912 123 4567", "09121234567"),
    ("9121234567", "09121234567")])
def test_phone_normalization(raw, ok):
    assert normalize_phone(raw) == ok


@pytest.mark.parametrize("bad", ["0912123456", "02112345678", "hello", ""])
def test_bad_phone_rejected(bad):
    with pytest.raises(Exception):
        normalize_phone(bad)


def test_phone_index_allows_many_accounts_without_phone(fresh_db):
    from app import db
    fresh_db.users.insert_many([{"username": "a"}, {"username": "b"}])
    db.ensure_indexes()          # must not fail on existing accounts without a phone


def test_otp_login_creates_student_once(client, caplog, fresh_db):
    caplog.set_level(logging.WARNING, logger="azmoon.sms")
    r = client.post("/auth/otp/request", json={"phone": "۰۹۱۲۱۲۳۴۵۶۷"})
    assert r.status_code == 200 and r.json()["phone"] == "09121234567"
    code = _code_from_log(caplog, "09121234567")
    assert fresh_db.otp_codes.find_one({})["hash"] != code, "codes are stored hashed"
    r = client.post("/auth/otp/verify", json={"phone": "09121234567", "code": code})
    assert r.status_code == 200 and r.json()["new_user"] is True
    token = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["role"] == "student" and me["onboarded"] is False
    # a code works once
    again = client.post("/auth/otp/verify", json={"phone": "09121234567", "code": code})
    assert again.status_code == 400
    assert fresh_db.users.count_documents({"phone": "09121234567"}) == 1


def test_otp_resend_needs_a_minute(client):
    assert client.post("/auth/otp/request", json={"phone": "09120000001"}).status_code == 200
    r = client.post("/auth/otp/request", json={"phone": "09120000001"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_otp_wrong_code_attempts_are_limited(client, caplog):
    caplog.set_level(logging.WARNING, logger="azmoon.sms")
    client.post("/auth/otp/request", json={"phone": "09120000002"})
    real = _code_from_log(caplog, "09120000002")
    wrong = "00000" if real != "00000" else "11111"
    for _ in range(5):
        assert client.post("/auth/otp/verify", json={"phone": "09120000002", "code": wrong}).status_code == 400
    # after 5 misses even the right code is refused: request a new one
    r = client.post("/auth/otp/verify", json={"phone": "09120000002", "code": real})
    assert r.status_code == 429


def test_admin_cannot_use_otp(client, caplog, fresh_db):
    caplog.set_level(logging.WARNING, logger="azmoon.sms")
    fresh_db.users.insert_one({"username": "boss", "phone": "09129999999", "role": "admin"})
    client.post("/auth/otp/request", json={"phone": "09129999999"})
    code = _code_from_log(caplog, "09129999999")
    assert client.post("/auth/otp/verify", json={"phone": "09129999999", "code": code}).status_code == 403


def test_password_login_is_rate_limited_per_account(client):
    client.post("/auth/register", json={"username": "sara", "password": "long-enough-1"})
    codes = [client.post("/auth/login", json={"username": "sara", "password": "wrong-pass"}).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_register_validates_input(client):
    assert client.post("/auth/register", json={"username": "a b", "password": "long-enough-1"}).status_code == 422
    assert client.post("/auth/register", json={"username": "abc", "password": "short"}).status_code == 422


def test_rate_limit_window():
    for _ in range(3):
        ratelimit.hit("t", "k", limit=3, window=60)
    with pytest.raises(Exception):
        ratelimit.hit("t", "k", limit=3, window=60)
    ratelimit.reset("t", "k", 60)
    assert ratelimit.hit("t", "k", limit=3, window=60) == 1


def test_health_and_request_id(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.headers.get("X-Request-ID")


def test_report_spam_is_limited(client, fresh_db):
    from conftest import seed
    seed(fresh_db)
    client.post("/auth/register", json={"username": "reza", "password": "long-enough-1"})
    tok = client.post("/auth/login", json={"username": "reza", "password": "long-enough-1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    first = client.post("/sessions/questions/c1_q0/report", json={"note": "کلید غلط"}, headers=h)
    dup = client.post("/sessions/questions/c1_q0/report", json={"note": "کلید غلط"}, headers=h)
    assert first.status_code == 200 and "در حال بررسی" in dup.json()["message"]
    assert fresh_db.reports.count_documents({}) == 1
