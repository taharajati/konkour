# AzmoonRep

Spaced repetition of key points (نکته) for Iranian school math, with a question bank that a
manager reviews before students see it. FastAPI + MongoDB backend, React (Vite) frontend.

## Layout

```
azmoonrep/
  backend/
    app/
      main.py           app, /health, static mounts, request logging
      config.py         settings from environment variables
      db.py             Mongo connection + indexes (incl. TTL for rate limits / login codes)
      clock.py          "today" = Tehran day
      scheduler.py      daily queue, spaced ladder, placement test, practice, grading
      importer.py       catalog + taxonomy + question bank import
      ratelimit.py      shared fixed-window limits (Mongo)
      sms.py            login-code SMS (console in dev, Kavenegar)
      logging_setup.py  JSON logs, request ids, audit log
      routers/          auth (password + phone OTP), sessions, curriculum, admin
    scripts/            seed_manager, import_data, reset_review, demo_server
    tests/              pytest on in-memory Mongo
  frontend/             React app + nginx.conf for production
  docker-compose.yml    mongo + api + web
```

## Try it without MongoDB

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt uvicorn
.venv/Scripts/python -m scripts.demo_server      # in-memory DB filled from ../../question_bank
cd ../frontend && npm install && npm run dev     # http://127.0.0.1:5173
```

Logins: student `demo` / `demo-pass-123`, admin `admin` / `admin-pass-123`. Phone login also
works: the code is printed in the API log (`SMS_PROVIDER=console`).

## Run for development (real MongoDB)

```bash
cd backend
pip install -r requirements.txt
python -m scripts.seed_manager            # admin account (asks for a password, 10+ chars)
python -m scripts.import_data             # catalog + taxonomy + question bank
python -m scripts.reset_review            # once: revoke old auto-approvals, reject known-wrong questions
uvicorn app.main:app --reload --port 8000
```

Imported questions start as **pending**; only manager-approved questions are served.

## Deploy (Docker)

```bash
cp .env.example .env                      # fill MONGO_PASS, JWT_SECRET, SMS_API_KEY
docker compose up -d --build              # web on http://<host>:8080
docker compose exec api python -m scripts.seed_manager admin
docker compose exec api python -m scripts.import_data
```

- Put TLS (HTTPS) in front of the `web` container (Caddy, Traefik or the host's nginx).
- MongoDB has no published port; back up the `mongo-data` volume (e.g. nightly `mongodump`).
- `GET /health` reports API + database status; the API container has a Docker health check.
- Logs are one JSON object per line on stdout (`docker compose logs api`); admin actions are
  logged by the `azmoon.audit` logger.

## Login

- Students: phone number + 5-digit SMS code (`/auth/otp/request`, `/auth/otp/verify`).
  Codes are stored hashed, expire in 2 minutes, allow 5 attempts, one resend per minute,
  5 per hour per number and 20 per hour per IP.
- Admins: username + password only (OTP is refused for admin accounts).
- `PASSWORD_LOGIN_FOR_STUDENTS=0` (the Docker default) closes username/password sign-up and
  login for students.
- Password login: 30 tries / 15 min per IP and 10 per account; nginx adds 10/min per IP on
  `/api/auth/`.

### SMS provider

`SMS_PROVIDER=kavenegar` uses Kavenegar's verify/lookup API with a template that contains
`%token%` (create and get it approved in the Kavenegar panel, then set `SMS_TEMPLATE`).
The adapter has not been tested against the live service: send yourself a code on a staging
server before going live. Other providers: add a function to `app/sms.py`.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q tests
```

In-memory MongoDB (mongomock) and a frozen clock, no server needed. Covered: the Tehran day
boundary, one slot per key point per day, no repeated question in a day, prerequisites, the
spaced ladder, maintenance checks, option shuffling and solution renumbering, remediation,
double submits, key-point cards, the placement test, learning metrics, phone login, rate
limits and the HTTP API.

## Secrets

- `JWT_SECRET` (32+ chars) is required when `APP_ENV` is not `dev`; in dev a random secret is
  generated into `backend/.jwt_secret` (never commit it, nor `.env`).
- `APP_ENV=prod` refuses to start with `SMS_PROVIDER=console`.
- Only figure images are public under `/static/questions`. Answer keys and publisher scans
  stay in the private bank folder; admins see scans via `/admin/questions/{id}/scan/...`.
