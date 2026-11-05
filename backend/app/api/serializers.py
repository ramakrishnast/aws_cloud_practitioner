"""Convert models to API response dicts."""
from __future__ import annotations

from ..engine.attempts import remaining_seconds
from ..engine.scoring import breakdown
from ..exams import Catalogue
from ..models import Attempt, AttemptAnswer, ImportReport, Question

LETTERS = "ABCDEF"
CHOOSE = {2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE"}


def _dt(v):
    return v.isoformat() + "Z" if v else None


def question_public(q: Question) -> dict:
    """Question as shown during a test: no answer, no explanation."""
    k = q.choose_count
    return {
        "id": q.id,
        "question_type": q.question_type,
        "text": q.text,
        "options": [{"letter": LETTERS[i], "text": t} for i, t in enumerate(q.options)],
        "choose": k if q.question_type == "multiple" else 1,
        "choose_label": f"Choose {CHOOSE.get(k, str(k))}" if q.question_type == "multiple" else None,
    }


def question_full(q: Question, catalogue: Catalogue) -> dict:
    exam = catalogue.exam(q.exam)
    domain = exam.domain(q.domain_id) if exam else None
    return {
        **question_public(q),
        "exam": q.exam,
        "domain_id": q.domain_id,
        "domain_name": domain.name if domain else None,
        "difficulty": q.difficulty,
        "correct": q.correct_letters,
        "explanation": q.explanation,
        "services": q.services or [],
        "reference_url": q.reference_url,
        "status": q.status,
        "source": q.source,
        "source_file": q.source_file,
        "source_row": q.source_row,
        "updated_at": _dt(q.updated_at),
    }


def answer_state(a: AttemptAnswer, catalogue: Catalogue, reveal: bool) -> dict:
    q = a.question
    d = {
        "position": a.position,
        "question": question_public(q),
        "selected": [x for x in a.selected.split(",") if x],
        "flagged": a.flagged,
        "revealed": a.revealed,
        "time_spent_sec": round(a.time_spent_sec or 0, 1),
    }
    if reveal or a.revealed:
        full = question_full(q, catalogue)
        d["feedback"] = {
            "is_correct": a.is_correct,
            "correct": full["correct"],
            "explanation": full["explanation"],
            "reference_url": full["reference_url"],
            "domain_id": full["domain_id"],
            "domain_name": full["domain_name"],
            "difficulty": full["difficulty"],
            "services": full["services"],
        }
    return d


def attempt_summary(a: Attempt, catalogue: Catalogue) -> dict:
    exam = catalogue.exam(a.exam)
    domain = exam.domain(a.domain_id) if exam and a.domain_id else None
    return {
        "id": a.id,
        "exam": a.exam,
        "exam_code": exam.code if exam else a.exam,
        "exam_name": exam.name if exam else a.exam,
        "mode": a.mode,
        "difficulty": a.difficulty,
        "domain_id": a.domain_id,
        "domain_name": domain.name if domain else None,
        "service": a.service,
        "feedback": a.feedback,
        "status": a.status,
        "started_at": _dt(a.started_at),
        "submitted_at": _dt(a.submitted_at),
        "deadline_at": _dt(a.deadline_at),
        "time_limit_sec": a.time_limit_sec,
        "remaining_sec": remaining_seconds(a),
        "auto_submitted": a.auto_submitted,
        "duration_sec": a.duration_sec,
        "total": a.total,
        "correct_count": a.correct_count,
        "raw_pct": a.raw_pct,
        "scaled_score": a.scaled_score,
        "passing_score": exam.passing_score if exam else None,
        "passed": a.passed,
        "notes": a.notes or [],
    }


def attempt_state(a: Attempt, catalogue: Catalogue) -> dict:
    done = a.status == "submitted"
    return {
        **attempt_summary(a, catalogue),
        "timer_warnings_minutes": list(catalogue.timer_warnings_minutes),
        "answers": [answer_state(x, catalogue, reveal=done) for x in a.answers],
    }


def attempt_results(a: Attempt, catalogue: Catalogue) -> dict:
    exam = catalogue.exam(a.exam)
    items = [(x.question.domain_id, x.question.difficulty, bool(x.is_correct)) for x in a.answers]
    answered = sum(1 for x in a.answers if x.selected)
    avg = (a.duration_sec / a.total) if a.duration_sec and a.total else None
    return {
        **attempt_state(a, catalogue),
        "answered": answered,
        "avg_time_per_question_sec": round(avg, 1) if avg else None,
        "breakdown": breakdown(items, exam) if exam else None,
        "score_is_estimate": True,
    }


def import_report(r: ImportReport) -> dict:
    return {
        "id": r.id,
        "path": r.path,
        "trigger": r.trigger,
        "created_at": _dt(r.created_at),
        "total_rows": r.total_rows,
        "inserted": r.inserted,
        "updated": r.updated,
        "unchanged": r.unchanged,
        "skipped": r.skipped,
        "errors": r.errors or [],
        "fatal": r.fatal or None,
    }
