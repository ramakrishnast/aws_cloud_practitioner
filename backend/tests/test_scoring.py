import pytest
from conftest import add_questions

from app.engine.attempts import AttemptError, create_attempt, save_answer, submit
from app.engine.scoring import breakdown, is_correct, scaled_score


def test_single_answer():
    assert is_correct("B", "B")
    assert is_correct(["b"], "B")
    assert not is_correct("A", "B")
    assert not is_correct("", "B")
    assert not is_correct(None, "B")


def test_multiple_response_requires_all_letters_no_partial_credit():
    assert is_correct("A,D", "A,D")
    assert is_correct(["D", "A"], "A,D")
    assert not is_correct("A", "A,D")  # missing one
    assert not is_correct("A,D,E", "A,D")  # extra one
    assert not is_correct("A,C", "A,D")  # one wrong


def test_scaled_score_mapping(catalogue):
    saa = catalogue.exam("saa-c03")  # pass 720 at raw 72%
    assert scaled_score(0, saa) == 100
    assert scaled_score(72, saa) == 720
    assert scaled_score(100, saa) == 1000
    assert scaled_score(71.9, saa) < 720 <= scaled_score(72.1, saa)
    scores = [scaled_score(p, saa) for p in range(0, 101, 5)]
    assert scores == sorted(scores)
    clf = catalogue.exam("clf-c02")
    assert scaled_score(70, clf) == 700


def test_breakdown(catalogue):
    exam = catalogue.exam("clf-c02")
    b = breakdown([(1, "easy", True), (1, "hard", False), (2, "easy", True)], exam)
    d1 = next(d for d in b["by_domain"] if d["id"] == 1)
    assert (d1["total"], d1["correct"], d1["pct"]) == (2, 1, 50.0)
    easy = next(d for d in b["by_difficulty"] if d["difficulty"] == "easy")
    assert easy["pct"] == 100.0
    d4 = next(d for d in b["by_domain"] if d["id"] == 4)
    assert d4["pct"] is None


def test_submit_scores_multiple_response_strictly(db, catalogue):
    add_questions(db, "saa-c03", per_cell=2, qtype="multiple")  # correct = A,C
    a = create_attempt(db, catalogue, "saa-c03", "practice", count=4, feedback="end")
    save_answer(db, a, catalogue, 0, ["A", "C"])  # correct
    save_answer(db, a, catalogue, 1, ["A"])  # partial -> wrong
    save_answer(db, a, catalogue, 2, ["A", "C", "D"])  # extra -> wrong
    submit(db, a, catalogue)
    assert a.correct_count == 1
    assert a.raw_pct == 25.0
    assert a.scaled_score == scaled_score(25.0, catalogue.exam("saa-c03"))
    assert a.passed is False


def test_immediate_feedback_locks_answer(db, catalogue):
    add_questions(db, "clf-c02", per_cell=2)
    a = create_attempt(db, catalogue, "clf-c02", "practice", count=5)
    assert a.feedback == "immediate"
    ans = save_answer(db, a, catalogue, 0, ["B"], reveal=True)
    assert ans.revealed and ans.is_correct
    with pytest.raises(AttemptError):
        save_answer(db, a, catalogue, 0, ["A"])


def test_full_mode_cannot_reveal(db, catalogue):
    add_questions(db, "clf-c02", per_cell=5)
    a = create_attempt(db, catalogue, "clf-c02", "full")
    with pytest.raises(AttemptError) as e:
        save_answer(db, a, catalogue, 0, ["B"], reveal=True)
    assert e.value.status_code == 403


def test_single_answer_rejects_two_selections(db, catalogue):
    add_questions(db, "clf-c02", per_cell=2)
    a = create_attempt(db, catalogue, "clf-c02", "practice", count=3)
    with pytest.raises(AttemptError):
        save_answer(db, a, catalogue, 0, ["A", "B"])
    with pytest.raises(AttemptError):
        save_answer(db, a, catalogue, 0, ["F"])  # only 5 options
