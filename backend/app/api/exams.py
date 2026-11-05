"""Exam catalogue, dashboard stats, and trends."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import clock
from ..db import get_db
from ..engine import srs
from ..engine.attempts import expire_overdue
from ..engine.readiness import readiness
from ..exams import DIFFICULTIES, get_catalogue
from ..models import Attempt, Question
from ..settings import get_settings

router = APIRouter(prefix="/api", tags=["exams"])


@router.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "generator_enabled": s.generator_enabled, "model": s.model,
            "question_bank": str(s.question_bank)}


def _exam_payload(db: Session, exam, detailed: bool = False) -> dict:
    cat = get_catalogue()
    rows = db.execute(
        select(Question.domain_id, Question.difficulty, Question.status, func.count())
        .where(Question.exam == exam.key)
        .group_by(Question.domain_id, Question.difficulty, Question.status)
    ).all()
    active = Counter()
    by_domain = Counter()
    by_diff = Counter()
    pending = 0
    for d, df, st, c in rows:
        if st == "active":
            active["total"] += c
            by_domain[d] += c
            by_diff[df] += c
        elif st == "pending":
            pending += c
    payload = {
        "key": exam.key,
        "code": exam.code,
        "name": exam.name,
        "short_name": exam.short_name,
        "question_count": exam.question_count,
        "time_limit_minutes": exam.time_limit_minutes,
        "passing_score": exam.passing_score,
        "guide_url": exam.guide_url,
        "difficulty_blend": exam.difficulty_blend,
        "domains": [
            {"id": d.id, "name": d.name, "weight": d.weight, "tasks": list(d.tasks), "active": by_domain.get(d.id, 0)}
            for d in exam.domains
        ],
        "active_questions": active["total"],
        "pending_questions": pending,
        "by_difficulty": {k: by_diff.get(k, 0) for k in DIFFICULTIES},
        "readiness": readiness(db, exam),
        "review": srs.summary(db, exam.key, clock.utcnow()),
        "drill_min": cat.drill_min,
        "drill_max": cat.drill_max,
    }
    if detailed:
        services = Counter()
        for (svc,) in db.execute(select(Question.services).where(Question.exam == exam.key,
                                                                    Question.status == "active")):
            for s in svc or []:
                services[s] += 1
        payload["services"] = [{"name": k, "count": v} for k, v in sorted(services.items(), key=lambda x: (-x[1], x[0]))]
    return payload


@router.get("/exams")
def list_exams(db: Session = Depends(get_db)):
    cat = get_catalogue()
    expire_overdue(db, cat)
    in_progress = db.scalars(select(Attempt).where(Attempt.status == "in_progress")
                             .order_by(Attempt.started_at.desc())).all()
    return {
        "exams": [_exam_payload(db, e) for e in cat.exams.values()],
        "difficulties": cat.difficulties,
        "in_progress": [{"id": a.id, "exam": a.exam, "mode": a.mode, "total": a.total,
                         "started_at": a.started_at.isoformat() + "Z"} for a in in_progress],
    }


@router.get("/exams/{key}")
def get_exam(key: str, db: Session = Depends(get_db)):
    exam = get_catalogue().exam(key)
    if exam is None:
        raise HTTPException(404, f"Unknown exam {key}")
    return _exam_payload(db, exam, detailed=True)


@router.get("/stats/trend")
def trend(db: Session = Depends(get_db)):
    """Scaled scores over time for every submitted attempt, grouped by exam."""
    cat = get_catalogue()
    out: dict[str, list] = {k: [] for k in cat.exams}
    for a in db.scalars(select(Attempt).where(Attempt.status == "submitted").order_by(Attempt.submitted_at)):
        if a.exam in out:
            out[a.exam].append({"id": a.id, "date": a.submitted_at.isoformat() + "Z", "mode": a.mode,
                                "scaled_score": a.scaled_score, "raw_pct": a.raw_pct})
    return out
