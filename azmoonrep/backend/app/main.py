import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, logging_setup
from .config import APP_ENV, STATIC_QUESTIONS_DIR
from .routers import admin, auth, curriculum, me_books, sessions, trial

logging_setup.setup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(STATIC_QUESTIONS_DIR, exist_ok=True)
    # older imports copied meta.json / answer.md / scans into the public folder
    from .importer import purge_private_static_files
    removed = purge_private_static_files()
    if removed:
        logging_setup.log.warning(f"removed {removed} private files from public static folder")
    db.ensure_indexes()
    logging_setup.log.info(f"started (env={APP_ENV})")
    yield


# API docs only outside production
docs = {} if APP_ENV == "dev" else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="AzmoonRep API", version="0.2.0", lifespan=lifespan, **docs)
app.middleware("http")(logging_setup.request_logger)

BOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "books")
os.makedirs(BOOKS_DIR, exist_ok=True)
os.makedirs(STATIC_QUESTIONS_DIR, exist_ok=True)
app.mount("/static/books", StaticFiles(directory=BOOKS_DIR), name="books")
app.mount("/static/questions", StaticFiles(directory=STATIC_QUESTIONS_DIR), name="questions")

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(curriculum.router)
app.include_router(me_books.router)
app.include_router(admin.router)
app.include_router(trial.router)


@app.get("/")
def root():
    return {"app": "AzmoonRep"}


@app.get("/health")
def health():
    """liveness + database reachability, for Docker / load balancer checks"""
    try:
        db.db.command("ping")
        return {"ok": True, "db": "ok"}
    except Exception as e:  # noqa: BLE001 - any db failure means "not healthy"
        return JSONResponse({"ok": False, "db": type(e).__name__}, status_code=503)
