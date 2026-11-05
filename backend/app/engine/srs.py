"""Spaced repetition for weak-area review (Leitner boxes).

- Wrong answer  -> box 0, due immediately (comes back soonest).
- Flagged but correct -> at most box 1 (due after the box-1 interval).
- Correct on a question already in review -> promoted one box; interval grows.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from ..models import Question, ReviewItem


def _interval(box: int, intervals: tuple[float, ...]) -> timedelta:
    box = max(0, min(box, len(intervals) - 1))
    return timedelta(days=intervals[box])


def record_result(
    session: Session,
    question: Question,
    correct: bool,
    flagged: bool,
    now: datetime,
    intervals: tuple[float, ...],
) -> ReviewItem | None:
    item = session.scalar(select(ReviewItem).where(ReviewItem.question_id == question.id))
    if not correct:
        if item is None:
            item = ReviewItem(question_id=question.id, exam=question.exam)
            session.add(item)
        item.box = 0
        item.wrong_count = (item.wrong_count or 0) + 1
        item.right_streak = 0
        item.due_at = now
    elif flagged:
        if item is None:
            item = ReviewItem(question_id=question.id, exam=question.exam, box=1, wrong_count=0, right_streak=0)
            session.add(item)
        else:
            item.box = min(item.box or 0, 1)
        item.due_at = now + _interval(item.box, intervals)
    elif item is not None:
        item.box = min((item.box or 0) + 1, len(intervals) - 1)
        item.right_streak = (item.right_streak or 0) + 1
        item.due_at = now + _interval(item.box, intervals)
    else:
        return None
    item.flagged = flagged
    item.last_reviewed_at = now
    return item


def review_queue(session: Session, exam: str, limit: int, now: datetime) -> list[Question]:
    """Due items first (lowest box, oldest due), then the weakest not-yet-due items."""
    is_due = case((ReviewItem.due_at <= now, 0), else_=1)
    rows = session.execute(
        select(Question)
        .join(ReviewItem, ReviewItem.question_id == Question.id)
        .where(ReviewItem.exam == exam, Question.status == "active")
        .order_by(is_due, ReviewItem.box, ReviewItem.due_at, ReviewItem.wrong_count.desc())
        .limit(limit)
    ).scalars().all()
    return list(rows)


def summary(session: Session, exam: str, now: datetime) -> dict:
    items = session.scalars(
        select(ReviewItem).join(Question, Question.id == ReviewItem.question_id)
        .where(ReviewItem.exam == exam, Question.status == "active")
    ).all()
    return {
        "total": len(items),
        "due": sum(1 for i in items if i.due_at <= now),
        "by_box": [sum(1 for i in items if i.box == b) for b in range(6)],
    }
