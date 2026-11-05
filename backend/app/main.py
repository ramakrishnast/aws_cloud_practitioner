"""FastAPI application: API + built frontend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import attempts, bank, exams, generate
from .bank.importer import scan_bank
from .bank.watcher import BankWatcher
from .db import SessionLocal, init_engine
from .engine.attempts import expire_overdue
from .exams import get_catalogue
from .settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("cloudcert")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_engine()
    settings.question_bank.mkdir(parents=True, exist_ok=True)
    session = SessionLocal()
    try:
        res = scan_bank(session, settings.question_bank, trigger="startup")
        log.info("Startup import: %d file(s) imported, %d unchanged", len(res.reports), len(res.unchanged_files))
        expire_overdue(session, get_catalogue())
    finally:
        session.close()
    watcher = None
    if settings.watch_folder:
        watcher = BankWatcher(settings.question_bank)
        watcher.start()
    try:
        yield
    finally:
        if watcher:
            watcher.stop()


app = FastAPI(title="CloudCert Lab", version="1.0.0", lifespan=lifespan)
for r in (exams.router, bank.router, attempts.router, generate.router):
    app.include_router(r)


_dist = get_settings().frontend_dist
if (_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str, request: Request):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = (_dist / full_path).resolve()
    if full_path and candidate.is_file() and _dist.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = _dist / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {"detail": "Frontend not built. Run `make run` (or `npm run build` in frontend/), "
                   "or use `make dev` and open http://localhost:5173."},
        status_code=503,
    )
