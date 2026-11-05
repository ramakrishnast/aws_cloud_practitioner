"""Scoring: correctness, estimated scaled score, breakdowns."""
from __future__ import annotations

from collections.abc import Iterable

from ..exams import DIFFICULTIES, Exam

LETTERS = "ABCDEF"


def parse_selection(value: str | Iterable[str] | None) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        parts = value.replace(";", ",").split(",")
    else:
        parts = list(value)
    return frozenset(p.strip().upper() for p in parts if p and p.strip())


def is_correct(selected: str | Iterable[str] | None, correct: str | Iterable[str]) -> bool:
    """All-or-nothing: the selection must equal the set of correct letters.

    Multiple-response questions get no partial credit: missing one correct
    letter, or adding an incorrect one, scores zero.
    """
    sel = parse_selection(selected)
    ans = parse_selection(correct)
    return bool(sel) and sel == ans


def scaled_score(raw_pct: float, exam: Exam) -> int:
    """Estimate a 100-1000 scaled score from raw percent correct.

    AWS does not publish its scaling. This piecewise-linear estimate maps
    0% -> 100, the configured raw cut (e.g. 72%) -> the passing score, and
    100% -> 1000. It is an estimate only.
    """
    raw = max(0.0, min(100.0, raw_pct))
    cut = min(max(exam.estimated_raw_cut_pct, 1.0), 99.0)
    passing = exam.passing_score
    if raw <= cut:
        score = 100 + (passing - 100) * raw / cut
    else:
        score = passing + (1000 - passing) * (raw - cut) / (100 - cut)
    return int(round(score))


def breakdown(items: Iterable[tuple[int, str, bool]], exam: Exam) -> dict:
    """items: (domain_id, difficulty, correct) per question."""
    dom = {d.id: {"id": d.id, "name": d.name, "weight": d.weight, "total": 0, "correct": 0} for d in exam.domains}
    diff = {k: {"difficulty": k, "total": 0, "correct": 0} for k in DIFFICULTIES}
    for domain_id, difficulty, ok in items:
        if domain_id in dom:
            dom[domain_id]["total"] += 1
            dom[domain_id]["correct"] += int(ok)
        if difficulty in diff:
            diff[difficulty]["total"] += 1
            diff[difficulty]["correct"] += int(ok)
    for row in [*dom.values(), *diff.values()]:
        row["pct"] = round(100 * row["correct"] / row["total"], 1) if row["total"] else None
    return {"by_domain": list(dom.values()), "by_difficulty": list(diff.values())}
