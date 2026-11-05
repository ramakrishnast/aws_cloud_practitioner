"""Test attempts: start, answer, submit, results, history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..engine.attempts import AttemptError, create_attempt, enforce_deadline, expire_overdue, save_answer, submit
from ..exams import get_catalogue
from ..models import Attempt
from .serializers import answer_state, attempt_results, attempt_state, attempt_summary

router = APIRouter(prefix="/api/attempts", tags=["attempts"])


def _err(e: AttemptError):
    return HTTPException(e.status_code, str(e))


def _load(db: Session, attempt_id: int) -> Attempt:
    a = db.get(Attempt, attempt_id)
    if a is None:
        raise HTTPException(404, "Test not found")
    return a


class StartRequest(BaseModel):
    exam: str
    mode: str = "full"
    difficulty: str = "mixed"
    count: int | None = None
    domain_id: int | None = None
    service: str | None = None
    time_limit_min: float | None = None
    feedback: str | None = None


@router.post("")
def start(body: StartRequest, db: Session = Depends(get_db)):
    cat = get_catalogue()
    try:
        a = create_attempt(db, cat, body.exam, body.mode, body.difficulty, body.count, body.domain_id,
                           body.service, body.time_limit_min, body.feedback)
    except AttemptError as e:
        raise _err(e) from None
    return attempt_state(a, cat)


@router.get("")
def history(exam: str | None = None, mode: str | None = None, limit: int = 200, db: Session = Depends(get_db)):
    cat = get_catalogue()
    expire_overdue(db, cat)
    stmt = select(Attempt).order_by(Attempt.started_at.desc()).limit(min(limit, 1000))
    if exam:
        stmt = stmt.where(Attempt.exam == exam)
    if mode:
        stmt = stmt.where(Attempt.mode == mode)
    return [attempt_summary(a, cat) for a in db.scalars(stmt)]


@router.get("/{attempt_id}")
def get_attempt(attempt_id: int, db: Session = Depends(get_db)):
    cat = get_catalogue()
    a = _load(db, attempt_id)
    enforce_deadline(db, a, cat)
    return attempt_state(a, cat)


class AnswerRequest(BaseModel):
    selected: list[str] | None = None
    flagged: bool | None = None
    time_spent_delta: float = 0
    reveal: bool = False


@router.put("/{attempt_id}/answers/{position}")
def answer(attempt_id: int, position: int, body: AnswerRequest, db: Session = Depends(get_db)):
    cat = get_catalogue()
    a = _load(db, attempt_id)
    try:
        ans = save_answer(db, a, cat, position, body.selected, body.flagged, body.time_spent_delta, body.reveal)
    except AttemptError as e:
        raise _err(e) from None
    return {"answer": answer_state(ans, cat, reveal=False), "remaining_sec": attempt_summary(a, cat)["remaining_sec"]}


@router.post("/{attempt_id}/submit")
def submit_attempt(attempt_id: int, db: Session = Depends(get_db)):
    cat = get_catalogue()
    a = _load(db, attempt_id)
    if not enforce_deadline(db, a, cat):
        submit(db, a, cat)
    return attempt_results(a, cat)


@router.get("/{attempt_id}/results")
def results(attempt_id: int, db: Session = Depends(get_db)):
    cat = get_catalogue()
    a = _load(db, attempt_id)
    enforce_deadline(db, a, cat)
    if a.status != "submitted":
        raise HTTPException(409, "Submit the test to see results")
    return attempt_results(a, cat)


@router.delete("/{attempt_id}")
def delete_attempt(attempt_id: int, db: Session = Depends(get_db)):
    a = _load(db, attempt_id)
    db.delete(a)
    db.commit()
    return {"deleted": attempt_id}
