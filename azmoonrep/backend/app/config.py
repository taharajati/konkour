import os


def _load_dotenv():
    """development convenience: read KEY=VALUE lines from azmoonrep/.env into the
    environment (real environment variables win). Docker passes variables itself."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_USER = os.getenv("MONGO_USER", "")
MONGO_PASS = os.getenv("MONGO_PASS", "")
MONGO_DB = os.getenv("MONGO_DB", "azmoonrep")
APP_ENV = os.getenv("APP_ENV", "dev")          # dev | prod

# phone login (OTP). SMS_PROVIDER: console (dev: code goes to the log) | kavenegar
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "console")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_TEMPLATE = os.getenv("SMS_TEMPLATE", "azmoonrep-otp")   # provider-side template name
OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "120"))
# password login for students (admins always use passwords). Turn off after the move to OTP.
PASSWORD_LOGIN_FOR_STUDENTS = os.getenv("PASSWORD_LOGIN_FOR_STUDENTS", "1") == "1"


def _jwt_secret() -> str:
    """JWT_SECRET from the environment. For local development only, a random secret
    is generated once and kept in backend/.jwt_secret (never a guessable default:
    anyone who knows the secret can sign an admin token)."""
    env = os.getenv("JWT_SECRET")
    if env:
        if len(env) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 characters")
        return env
    if APP_ENV != "dev":
        raise RuntimeError("JWT_SECRET is required when APP_ENV is not 'dev'")
    import secrets
    path = os.path.join(os.path.dirname(__file__), "..", ".jwt_secret")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            value = f.read().strip()
        if len(value) >= 32:
            return value
    value = secrets.token_urlsafe(48)
    with open(path, "w", encoding="utf-8") as f:
        f.write(value)
    return value

JWT_SECRET = _jwt_secret()
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "72"))

# where imported question folders (figures etc.) are copied and served statically
STATIC_QUESTIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "questions")

DEFAULT_DAILY_LOAD = 20

if APP_ENV != "dev" and SMS_PROVIDER == "console":
    raise RuntimeError("SMS_PROVIDER=console prints login codes to the log; set a real "
                       "provider (e.g. kavenegar) when APP_ENV is not 'dev'")
