"""Exam readiness from the last three full simulations."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..exams import Exam
from ..models import Attempt

WINDOW = 3
MARGIN = 50  # points above the passing score that count as a comfortable margin


def readiness(session: Session, exam: Exam) -> dict:
    attempts = session.scalars(
        select(Attempt)
        .where(Attempt.exam == exam.key, Attempt.mode == "full", Attempt.status == "submitted")
        .order_by(Attempt.submitted_at.desc())
        .limit(WINDOW)
    ).all()
    scores = [a.scaled_score or 0 for a in attempts]
    passing = exam.passing_score
    base = {"passing_score": passing, "scores": scores, "window": WINDOW}
    if len(scores) < WINDOW:
        need = WINDOW - len(scores)
        avg = round(sum(scores) / len(scores)) if scores else None
        return {**base, "status": "insufficient", "average": avg,
                "label": "Not enough data",
                "message": f"Take {need} more full simulation{'s' if need > 1 else ''} to get a readiness estimate."}
    avg = round(sum(scores) / len(scores))
    low = min(scores)
    if avg >= passing + MARGIN and low >= passing:
        status, label, msg = "ready", "Ready", "Your last three simulations cleared the passing line with margin."
    elif avg >= passing:
        status, label, msg = "almost", "Almost ready", "You are averaging a pass, but without much margin. Keep drilling weak domains."
    elif avg >= passing - 80:
        status, label, msg = "developing", "Getting close", "You are within reach of the passing line. Focus on your weakest domains."
    else:
        status, label, msg = "not_ready", "Not ready yet", "Keep practising. Use domain drills and weak-area review."
    return {**base, "status": status, "average": avg, "label": label, "message": msg}
