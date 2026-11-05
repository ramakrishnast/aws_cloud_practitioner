from datetime import datetime, timedelta

import pytest
from conftest import add_questions

from app import clock
from app.engine.attempts import (
    AttemptError,
    create_attempt,
    enforce_deadline,
    expire_overdue,
    remaining_seconds,
    save_answer,
)

T0 = datetime(2026, 1, 1, 9, 0, 0)


@pytest.fixture
def full_attempt(db, catalogue):
    add_questions(db, "saa-c03", per_cell=10)
    clock.set_now(T0)
    return create_attempt(db, catalogue, "saa-c03", "full")


def test_full_simulation_uses_exam_limits(full_attempt, catalogue):
    exam = catalogue.exam("saa-c03")
    assert full_attempt.total == exam.question_count == 65
    assert full_attempt.time_limit_sec == 130 * 60
    assert full_attempt.deadline_at == T0 + timedelta(minutes=130)
    assert full_attempt.feedback == "end"
    assert remaining_seconds(full_attempt) == 130 * 60


def test_answers_accepted_before_deadline(db, full_attempt, catalogue):
    clock.set_now(T0 + timedelta(minutes=129))
    ans = save_answer(db, full_attempt, catalogue, 0, ["B"])
    assert ans.selected == "B"
    assert full_attempt.status == "in_progress"


def test_auto_submit_when_time_runs_out(db, full_attempt, catalogue):
    clock.set_now(T0 + timedelta(minutes=10))
    save_answer(db, full_attempt, catalogue, 0, ["B"])  # correct
    save_answer(db, full_attempt, catalogue, 1, ["A"])  # wrong
    clock.set_now(T0 + timedelta(minutes=131))
    with pytest.raises(AttemptError) as e:
        save_answer(db, full_attempt, catalogue, 2, ["B"])
    assert e.value.status_code == 409
    assert full_attempt.status == "submitted"
    assert full_attempt.auto_submitted is True
    assert full_attempt.correct_count == 1
    # Duration is capped at the time limit, not the late request time
    assert full_attempt.duration_sec == 130 * 60
    # Unanswered questions count as incorrect
    assert full_attempt.raw_pct == pytest.approx(100 / 65, abs=0.01)


def test_enforce_deadline_on_read(db, full_attempt, catalogue):
    clock.set_now(T0 + timedelta(minutes=130, seconds=1))
    assert enforce_deadline(db, full_attempt, catalogue) is False  # inside grace window
    clock.set_now(T0 + timedelta(minutes=131))
    assert enforce_deadline(db, full_attempt, catalogue) is True
    assert full_attempt.status == "submitted"


def test_expire_overdue_sweeps_abandoned_tests(db, full_attempt, catalogue):
    clock.set_now(T0 + timedelta(hours=5))
    assert expire_overdue(db, catalogue) == 1
    assert full_attempt.auto_submitted


def test_untimed_practice_never_expires(db, catalogue):
    add_questions(db, "clf-c02", per_cell=3)
    clock.set_now(T0)
    a = create_attempt(db, catalogue, "clf-c02", "practice", count=10)
    assert a.deadline_at is None
    clock.set_now(T0 + timedelta(days=3))
    assert enforce_deadline(db, a, catalogue) is False
    save_answer(db, a, catalogue, 0, ["B"])
