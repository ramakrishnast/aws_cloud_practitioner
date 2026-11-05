from datetime import datetime, timedelta

import pytest
from conftest import add_questions

from app import clock
from app.engine import srs
from app.engine.attempts import AttemptError, create_attempt, save_answer, submit
from app.models import ReviewItem

T0 = datetime(2026, 2, 1, 8, 0)
INTERVALS = (0, 1, 3, 7, 14, 30)


def test_wrong_answer_due_now_correct_promotes(db):
    q = add_questions(db, "clf-c02", per_cell=1)[0]
    item = srs.record_result(db, q, correct=False, flagged=False, now=T0, intervals=INTERVALS)
    assert item.box == 0 and item.due_at == T0 and item.wrong_count == 1
    srs.record_result(db, q, correct=True, flagged=False, now=T0, intervals=INTERVALS)
    assert item.box == 1 and item.due_at == T0 + timedelta(days=1)
    srs.record_result(db, q, correct=True, flagged=False, now=T0, intervals=INTERVALS)
    assert item.box == 2 and item.due_at == T0 + timedelta(days=3)
    srs.record_result(db, q, correct=False, flagged=False, now=T0, intervals=INTERVALS)
    assert item.box == 0 and item.wrong_count == 2


def test_correct_unflagged_new_question_not_tracked(db):
    q = add_questions(db, "clf-c02", per_cell=1)[0]
    assert srs.record_result(db, q, True, False, T0, INTERVALS) is None


def test_flagged_correct_comes_back_later_than_wrong(db):
    qs = add_questions(db, "clf-c02", per_cell=1)
    wrong = srs.record_result(db, qs[0], False, False, T0, INTERVALS)
    flagged = srs.record_result(db, qs[1], True, True, T0, INTERVALS)
    assert wrong.due_at < flagged.due_at
    db.commit()
    queue = srs.review_queue(db, "clf-c02", 10, T0)
    assert [q.id for q in queue][:2] == [qs[0].id, qs[1].id]


def test_weak_mode_uses_review_queue(db, catalogue):
    add_questions(db, "clf-c02", per_cell=2)
    clock.set_now(T0)
    with pytest.raises(AttemptError):
        create_attempt(db, catalogue, "clf-c02", "weak")
    a = create_attempt(db, catalogue, "clf-c02", "practice", count=6, feedback="end")
    save_answer(db, a, catalogue, 0, ["A"])  # wrong (correct is B)
    save_answer(db, a, catalogue, 1, ["B"], flagged=True)  # right but flagged
    save_answer(db, a, catalogue, 2, ["B"])  # right
    submit(db, a, catalogue)
    # unanswered 3-5 are wrong too
    assert db.query(ReviewItem).count() == 5
    w = create_attempt(db, catalogue, "clf-c02", "weak", count=10)
    ids = [x.question_id for x in w.answers]
    assert a.answers[0].question_id in ids
    assert a.answers[2].question_id not in ids
