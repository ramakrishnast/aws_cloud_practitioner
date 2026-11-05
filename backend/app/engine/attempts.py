"""Attempt lifecycle: create, answer, auto-submit on deadline, submit."""
from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..exams import DIFFICULTIES, Catalogue
from ..models import Attempt, AttemptAnswer, Question
from . import srs
from .assembly import assemble
from .scoring import is_correct, parse_selection, scaled_score

MODES = ("full", "practice", "drill", "weak")
GRACE_SEC = 3  # network latency allowance after the deadline
PRACTICE_DEFAULT = 20
PRACTICE_MAX = 150


class AttemptError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _active_pool(session: Session, exam: str, domain_id: int | None = None, service: str | None = None):
    stmt = select(Question).where(Question.exam == exam, Question.status == "active")
    if domain_id:
        stmt = stmt.where(Question.domain_id == domain_id)
    pool = list(session.scalars(stmt))
    if service:
        s = service.strip().lower()
        pool = [q for q in pool if any(t.lower() == s for t in (q.services or []))]
    return pool


def create_attempt(
    session: Session,
    catalogue: Catalogue,
    exam_key: str,
    mode: str,
    difficulty: str = "mixed",
    count: int | None = None,
    domain_id: int | None = None,
    service: str | None = None,
    time_limit_min: float | None = None,
    feedback: str | None = None,
    rng: random.Random | None = None,
) -> Attempt:
    exam = catalogue.exam(exam_key)
    if exam is None:
        raise AttemptError(f"Unknown exam '{exam_key}'", 404)
    mode = (mode or "").lower()
    if mode not in MODES:
        raise AttemptError(f"mode must be one of {', '.join(MODES)}")
    difficulty = (difficulty or "mixed").lower()
    if difficulty not in (*DIFFICULTIES, "mixed"):
        raise AttemptError("difficulty must be easy, medium, hard, tough, or mixed")
    now = clock.utcnow()
    notes: list[str] = []

    if mode == "full":
        count = exam.question_count
        time_limit_sec: int | None = exam.time_limit_minutes * 60
        feedback = "end"
        pool = _active_pool(session, exam.key)
        chosen, notes = assemble(pool, exam, count, difficulty, rng)
    elif mode == "practice":
        count = max(1, min(int(count or PRACTICE_DEFAULT), PRACTICE_MAX))
        time_limit_sec = int(time_limit_min * 60) if time_limit_min else None
        feedback = feedback if feedback in ("immediate", "end") else "immediate"
        pool = _active_pool(session, exam.key)
        chosen, notes = assemble(pool, exam, count, difficulty, rng)
    elif mode == "drill":
        if not domain_id and not service:
            raise AttemptError("Domain drills need a domain or an AWS service tag")
        if domain_id and exam.domain(domain_id) is None:
            raise AttemptError(f"Domain {domain_id} is not part of {exam.code}")
        count = max(catalogue.drill_min, min(int(count or catalogue.drill_min), catalogue.drill_max))
        time_limit_sec = int(time_limit_min * 60) if time_limit_min else None
        feedback = feedback if feedback in ("immediate", "end") else "immediate"
        pool = _active_pool(session, exam.key, domain_id, service)
        chosen, notes = assemble(pool, exam, count, difficulty, rng, domain_ids=[domain_id] if domain_id else None)
    else:  # weak
        count = max(1, min(int(count or PRACTICE_DEFAULT), PRACTICE_MAX))
        time_limit_sec = int(time_limit_min * 60) if time_limit_min else None
        feedback = feedback if feedback in ("immediate", "end") else "immediate"
        difficulty = "mixed"
        chosen = srs.review_queue(session, exam.key, count, now)
        if 0 < len(chosen) < count:
            notes.append(f"Only {len(chosen)} question(s) are in your review queue.")

    if not chosen:
        if mode == "weak":
            raise AttemptError("Nothing to review yet: questions you miss or flag will appear here.", 409)
        raise AttemptError("No active questions match these settings. Import or approve questions first.", 409)

    attempt = Attempt(
        exam=exam.key,
        mode=mode,
        difficulty=difficulty,
        domain_id=domain_id,
        service=service,
        feedback=feedback or "end",
        started_at=now,
        time_limit_sec=time_limit_sec,
        deadline_at=now + timedelta(seconds=time_limit_sec) if time_limit_sec else None,
        total=len(chosen),
        notes=notes,
    )
    session.add(attempt)
    session.flush()
    for i, q in enumerate(chosen):
        session.add(AttemptAnswer(attempt_id=attempt.id, question_id=q.id, position=i))
    session.commit()
    session.refresh(attempt)
    return attempt


def remaining_seconds(attempt: Attempt) -> float | None:
    if attempt.deadline_at is None or attempt.status != "in_progress":
        return None
    return max(0.0, (attempt.deadline_at - clock.utcnow()).total_seconds())


def enforce_deadline(session: Session, attempt: Attempt, catalogue: Catalogue) -> bool:
    """Auto-submit an attempt whose time has run out. Returns True if it did."""
    if attempt.status != "in_progress" or attempt.deadline_at is None:
        return False
    if clock.utcnow() >= attempt.deadline_at + timedelta(seconds=GRACE_SEC):
        submit(session, attempt, catalogue, auto=True)
        return True
    return False


def get_answer(attempt: Attempt, position: int) -> AttemptAnswer:
    for a in attempt.answers:
        if a.position == position:
            return a
    raise AttemptError(f"Question {position + 1} is not part of this test", 404)


def save_answer(
    session: Session,
    attempt: Attempt,
    catalogue: Catalogue,
    position: int,
    selected: list[str] | str | None = None,
    flagged: bool | None = None,
    time_spent_delta: float = 0,
    reveal: bool = False,
) -> AttemptAnswer:
    if enforce_deadline(session, attempt, catalogue):
        raise AttemptError("Time is up. Your test was submitted automatically.", 409)
    if attempt.status != "in_progress":
        raise AttemptError("This test has already been submitted.", 409)
    ans = get_answer(attempt, position)
    q = ans.question

    if selected is not None:
        sel = parse_selection(selected)
        valid = set("ABCDEF"[: len(q.options)])
        bad = sorted(sel - valid)
        if bad:
            raise AttemptError(f"Option(s) {', '.join(bad)} do not exist for this question")
        if q.question_type == "single" and len(sel) > 1:
            raise AttemptError("This question has a single answer")
        new = ",".join(sorted(sel))
        if ans.revealed and new != ans.selected:
            raise AttemptError("The answer is locked after it has been checked.", 409)
        ans.selected = new
    if flagged is not None:
        ans.flagged = bool(flagged)
    if time_spent_delta:
        ans.time_spent_sec = (ans.time_spent_sec or 0) + max(0.0, min(float(time_spent_delta), 3600.0))

    if reveal:
        if attempt.feedback != "immediate":
            raise AttemptError("Answers are shown at the end of this test.", 403)
        if not ans.selected:
            raise AttemptError("Select an answer first.")
        if not ans.revealed:
            ans.revealed = True
            ans.is_correct = is_correct(ans.selected, q.correct)
            srs.record_result(session, q, ans.is_correct, ans.flagged, clock.utcnow(), catalogue.srs_intervals_days)
    session.commit()
    return ans


def submit(session: Session, attempt: Attempt, catalogue: Catalogue, auto: bool = False) -> Attempt:
    if attempt.status != "in_progress":
        return attempt
    exam = catalogue.exam(attempt.exam)
    now = clock.utcnow()
    correct = 0
    for ans in attempt.answers:
        q = ans.question
        ok = is_correct(ans.selected, q.correct)
        if not ans.revealed:
            srs.record_result(session, q, ok, ans.flagged, now, catalogue.srs_intervals_days)
        ans.is_correct = ok
        correct += int(ok)
    end = now
    if attempt.deadline_at is not None and end > attempt.deadline_at:
        end = attempt.deadline_at
    attempt.duration_sec = max(0.0, (end - attempt.started_at).total_seconds())
    attempt.correct_count = correct
    attempt.raw_pct = round(100 * correct / attempt.total, 2) if attempt.total else 0.0
    if exam:
        attempt.scaled_score = scaled_score(attempt.raw_pct, exam)
        attempt.passed = attempt.scaled_score >= exam.passing_score
    attempt.status = "submitted"
    attempt.submitted_at = now
    attempt.auto_submitted = auto
    session.commit()
    return attempt


def expire_overdue(session: Session, catalogue: Catalogue) -> int:
    """Auto-submit every overdue attempt (called on startup and from list views)."""
    overdue = session.scalars(
        select(Attempt).where(
            Attempt.status == "in_progress",
            Attempt.deadline_at.is_not(None),
            Attempt.deadline_at <= clock.utcnow() - timedelta(seconds=GRACE_SEC),
        )
    ).all()
    for a in overdue:
        submit(session, a, catalogue, auto=True)
    return len(overdue)


def question_stats(session: Session, exam: str) -> dict:
    rows = session.execute(
        select(Question.domain_id, Question.difficulty, Question.status, func.count())
        .where(Question.exam == exam)
        .group_by(Question.domain_id, Question.difficulty, Question.status)
    ).all()
    return {"rows": [{"domain_id": d, "difficulty": df, "status": s, "count": c} for d, df, s, c in rows]}
