"""Background generation jobs for the Review screen."""
from __future__ import annotations

import itertools
import logging
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import SessionLocal
from ..exams import get_catalogue
from ..generator.llm import AnthropicLLM, LLMClient
from ..generator.service import generate_questions, plan_seed
from ..settings import get_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/generate", tags=["generate"])

_jobs: dict[int, dict] = {}
_ids = itertools.count(1)
_lock = threading.Lock()
# Tests can replace this to avoid real API calls.
llm_factory = None


def _llm() -> LLMClient:
    if llm_factory is not None:
        return llm_factory()
    s = get_settings()
    if not s.anthropic_api_key:
        raise HTTPException(400, "Set ANTHROPIC_API_KEY in .env to use the question generator.")
    return AnthropicLLM(s.anthropic_api_key, effort=s.effort, use_fallbacks=s.use_fallbacks)


class GenerateRequest(BaseModel):
    exam: str
    domain_id: int
    difficulty: str
    count: int = 5


class SeedRequest(BaseModel):
    exam: str
    total: int = 100


def _start(kind: str, plan: list[tuple[str, int, str, int]]) -> dict:
    llm = _llm()
    s = get_settings()
    with _lock:
        jid = next(_ids)
        job = {"id": jid, "kind": kind, "status": "running", "log": [], "results": [],
               "started_at": datetime.utcnow().isoformat() + "Z", "finished_at": None,
               "planned": sum(p[3] for p in plan)}
        _jobs[jid] = job

    def say(msg: str) -> None:
        job["log"].append(msg)
        del job["log"][:-200]

    def run() -> None:
        session = SessionLocal()
        try:
            for exam, domain_id, difficulty, count in plan:
                res = generate_questions(session, llm, get_catalogue(), s.question_bank, exam, domain_id,
                                         difficulty, count, s.model, s.verifier_model, progress=say)
                job["results"].append(res.summary())
                if res.errors and not res.accepted:
                    say("Stopped: " + res.errors[-1])
                    job["status"] = "failed"
                    return
            job["status"] = "done"
        except Exception as e:  # pragma: no cover - surfaced to the UI
            log.exception("Generation job failed")
            say(f"Error: {e}")
            job["status"] = "failed"
        finally:
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"
            session.close()

    threading.Thread(target=run, daemon=True).start()
    return job


@router.post("")
def generate(body: GenerateRequest):
    cat = get_catalogue()
    exam = cat.exam(body.exam)
    if exam is None or exam.domain(body.domain_id) is None:
        raise HTTPException(400, "Unknown exam or domain")
    if body.difficulty.lower() not in ("easy", "medium", "hard", "tough"):
        raise HTTPException(400, "difficulty must be easy, medium, hard, or tough")
    count = max(1, min(body.count, 25))
    return _start("generate", [(exam.key, body.domain_id, body.difficulty.lower(), count)])


@router.post("/seed")
def seed(body: SeedRequest):
    exam = get_catalogue().exam(body.exam)
    if exam is None:
        raise HTTPException(400, "Unknown exam")
    plan = [(exam.key, d, diff, n) for d, diff, n in plan_seed(exam, max(1, min(body.total, 300)))]
    return _start("seed", plan)


@router.get("/jobs")
def jobs():
    return sorted(_jobs.values(), key=lambda j: -j["id"])[:20]


@router.get("/jobs/{job_id}")
def job(job_id: int):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    return _jobs[job_id]
