import random
from collections import Counter

from conftest import add_questions
from sqlalchemy import select

from app.engine.assembly import apportion, assemble
from app.models import Question


def test_apportion_sums_and_follows_weights():
    out = apportion(65, {1: 24, 2: 30, 3: 34, 4: 12})
    assert sum(out.values()) == 65
    assert out == {1: 16, 2: 19, 3: 22, 4: 8}
    assert apportion(75, {1: 26, 2: 29, 3: 25, 4: 20}) == {1: 19, 2: 22, 3: 19, 4: 15}
    assert sum(apportion(7, {"a": 1, "b": 1, "c": 1}).values()) == 7
    assert apportion(0, {1: 50, 2: 50}) == {1: 0, 2: 0}


def test_full_exam_uses_domain_weights(db, catalogue):
    add_questions(db, "clf-c02", per_cell=10)
    pool = list(db.scalars(select(Question)))
    exam = catalogue.exam("clf-c02")
    chosen, notes = assemble(pool, exam, exam.question_count, "mixed", random.Random(1))
    assert len(chosen) == 65
    assert len({q.id for q in chosen}) == 65
    by_dom = Counter(q.domain_id for q in chosen)
    assert by_dom == {1: 16, 2: 19, 3: 22, 4: 8}
    assert notes == []


def test_mixed_difficulty_follows_blend(db, catalogue):
    add_questions(db, "sap-c02", per_cell=40)
    pool = list(db.scalars(select(Question)))
    exam = catalogue.exam("sap-c02")
    chosen, _ = assemble(pool, exam, 75, "mixed", random.Random(2))
    by_diff = Counter(q.difficulty for q in chosen)
    # Blend is easy 5 / medium 25 / hard 40 / tough 30 (per-domain rounding)
    assert by_diff["tough"] > by_diff["easy"]
    assert by_diff["hard"] >= by_diff["medium"]


def test_single_difficulty_filter(db, catalogue):
    add_questions(db, "saa-c03", per_cell=10)
    pool = list(db.scalars(select(Question)))
    chosen, _ = assemble(pool, catalogue.exam("saa-c03"), 20, "hard", random.Random(3))
    assert len(chosen) == 20
    assert {q.difficulty for q in chosen} == {"hard"}


def test_shortfall_redistributed_to_other_domains(db, catalogue):
    add_questions(db, "saa-c03", per_cell=10)
    # Leave only 3 questions in domain 1
    d1 = list(db.scalars(select(Question).where(Question.domain_id == 1)))
    for q in d1[3:]:
        db.delete(q)
    db.commit()
    pool = list(db.scalars(select(Question)))
    chosen, notes = assemble(pool, catalogue.exam("saa-c03"), 65, "mixed", random.Random(4))
    assert len(chosen) == 65
    assert Counter(q.domain_id for q in chosen)[1] == 3
    assert any("Domain 1" in n for n in notes)


def test_small_pool_returns_everything_with_note(db, catalogue):
    add_questions(db, "saa-c03", per_cell=1)  # 16 questions
    pool = list(db.scalars(select(Question)))
    chosen, notes = assemble(pool, catalogue.exam("saa-c03"), 65, "mixed", random.Random(5))
    assert len(chosen) == 16
    assert "Only 16" in notes[0]


def test_domain_restriction(db, catalogue):
    add_questions(db, "saa-c03", per_cell=5)
    pool = list(db.scalars(select(Question)))
    chosen, _ = assemble(pool, catalogue.exam("saa-c03"), 15, "mixed", random.Random(6), domain_ids=[3])
    assert len(chosen) == 15 and {q.domain_id for q in chosen} == {3}
