"""Assemble a test from the question pool according to domain weights."""
from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Hashable, Sequence
from typing import TypeVar

from ..exams import DIFFICULTIES, Exam

K = TypeVar("K", bound=Hashable)


def apportion(total: int, weights: dict[K, float]) -> dict[K, int]:
    """Split `total` across keys proportionally (largest-remainder method).

    Always sums to exactly `total`; ties are broken by larger weight, then key order.
    """
    if total <= 0 or not weights:
        return {k: 0 for k in weights}
    wsum = sum(max(w, 0) for w in weights.values())
    if wsum <= 0:
        keys = list(weights)
        base = {k: total // len(keys) for k in keys}
        for k in keys[: total - sum(base.values())]:
            base[k] += 1
        return base
    quotas = {k: total * max(w, 0) / wsum for k, w in weights.items()}
    result = {k: int(q) for k, q in quotas.items()}
    leftover = total - sum(result.values())
    order = sorted(weights, key=lambda k: (-(quotas[k] - result[k]), -weights[k]))
    for k in order[:leftover]:
        result[k] += 1
    return result


def _allocate_with_capacity(total: int, weights: dict[K, float], capacity: dict[K, int]) -> dict[K, int]:
    """Apportion `total` by weight, never exceeding each key's capacity.

    Shortfalls in one bucket are redistributed to the others by weight.
    """
    alloc = {k: 0 for k in weights}
    remaining = min(total, sum(capacity.get(k, 0) for k in weights))
    active = {k: w for k, w in weights.items() if capacity.get(k, 0) > 0}
    while remaining > 0 and active:
        share = apportion(remaining, active)
        progressed = 0
        for k, n in share.items():
            room = capacity[k] - alloc[k]
            take = min(n, room)
            alloc[k] += take
            progressed += take
        remaining -= progressed
        active = {k: w for k, w in active.items() if alloc[k] < capacity[k]}
        if progressed == 0:  # pragma: no cover - defensive
            break
    return alloc


def assemble(
    pool: Sequence,
    exam: Exam,
    count: int,
    difficulty: str = "mixed",
    rng: random.Random | None = None,
    domain_ids: Sequence[int] | None = None,
) -> tuple[list, list[str]]:
    """Pick `count` questions from `pool`.

    - Domains are weighted per the exam guide (or restricted to `domain_ids`).
    - difficulty="mixed" blends Easy/Medium/Hard/Tough per the exam's difficulty_blend;
      otherwise only that difficulty is used.
    - If a domain/difficulty bucket runs short, the gap is filled from the others.

    Returns (questions in random order, notes about any shortfall).
    """
    rng = rng or random.Random()
    notes: list[str] = []
    difficulty = (difficulty or "mixed").lower()
    if difficulty != "mixed":
        pool = [q for q in pool if q.difficulty == difficulty]

    domains = [d for d in exam.domains if domain_ids is None or d.id in domain_ids]
    by_domain: dict[int, list] = defaultdict(list)
    for q in pool:
        by_domain[q.domain_id].append(q)

    weights = {d.id: d.weight for d in domains}
    capacity = {d.id: len(by_domain.get(d.id, [])) for d in domains}
    targets = apportion(count, weights)
    alloc = _allocate_with_capacity(count, weights, capacity)

    available = sum(capacity.values())
    if available < count:
        notes.append(f"Only {available} matching question(s) available; the test has {available} instead of {count}.")
    for d in domains:
        if alloc[d.id] < targets[d.id] and available >= count:
            notes.append(f"Domain {d.id} ({d.name}) had only {capacity[d.id]} question(s); "
                         "the gap was filled from other domains.")

    blend = {k: exam.difficulty_blend.get(k, 25.0) for k in DIFFICULTIES}
    chosen: list = []
    for d in domains:
        n = alloc[d.id]
        if n == 0:
            continue
        cands = list(by_domain[d.id])
        rng.shuffle(cands)
        if difficulty == "mixed":
            by_diff: dict[str, list] = defaultdict(list)
            for q in cands:
                by_diff[q.difficulty].append(q)
            dcap = {k: len(by_diff.get(k, [])) for k in DIFFICULTIES}
            dalloc = _allocate_with_capacity(n, blend, dcap)
            for k in DIFFICULTIES:
                chosen.extend(by_diff[k][: dalloc[k]])
        else:
            chosen.extend(cands[:n])

    rng.shuffle(chosen)
    return chosen, notes
