"""Generate -> verify -> save as pending-review CSV -> import."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import clock
from ..bank.csvio import STATUS_COLUMN, write_rows
from ..bank.importer import import_file
from ..bank.normalize import text_hash
from ..engine.assembly import apportion
from ..exams import DIFFICULTIES, Catalogue, Exam
from ..models import Question
from .llm import LLMClient, LLMError, LLMRetryable
from .prompts import GENERATOR_SYSTEM, VERIFIER_SYSTEM, generation_prompt, verification_prompt
from .schemas import BATCH_SCHEMA, REVIEW_SCHEMA, GenBatch, GenQuestion, ReviewBatch

log = logging.getLogger(__name__)

BATCH_SIZE = 5
MAX_ATTEMPTS = 3

Progress = Callable[[str], None]


@dataclass
class GenerationResult:
    exam: str
    domain_id: int
    difficulty: str
    requested: int
    accepted: list[GenQuestion] = field(default_factory=list)
    fixed: int = 0
    discarded: list[dict] = field(default_factory=list)  # {question, issues}
    duplicates: int = 0
    csv_path: str | None = None
    import_report_id: int | None = None
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "exam": self.exam,
            "domain_id": self.domain_id,
            "difficulty": self.difficulty,
            "requested": self.requested,
            "accepted": len(self.accepted),
            "fixed_by_verifier": self.fixed,
            "discarded": self.discarded,
            "duplicates_skipped": self.duplicates,
            "csv_path": self.csv_path,
            "import_report_id": self.import_report_id,
            "errors": self.errors,
        }


def call_structured(
    llm: LLMClient,
    model: str,
    system: str,
    prompt: str,
    schema: dict,
    model_cls: type[BaseModel],
    attempts: int = MAX_ATTEMPTS,
    backoff_sec: float = 2.0,
) -> BaseModel:
    """Call the model and validate its JSON with Pydantic, retrying on bad output.

    Malformed JSON or schema violations are fed back to the model so the retry
    can correct them. Transient API errors are retried with backoff.
    """
    messages: list[dict] = [{"role": "user", "content": prompt}]
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            text = llm.complete_json(model=model, system=system, messages=messages, schema=schema)
        except LLMRetryable as e:
            last_error = str(e)
            log.warning("Attempt %d/%d failed: %s", attempt, attempts, e)
            if attempt < attempts:
                time.sleep(backoff_sec * attempt)
            continue
        try:
            return model_cls.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = f"{type(e).__name__}: {e}"
            log.warning("Attempt %d/%d returned invalid output: %s", attempt, attempts, last_error[:300])
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": text[:20000] or "(empty)"},
                {"role": "user", "content": "That output failed validation:\n" + last_error[:4000]
                    + "\nReturn the complete corrected JSON."},
            ]
    raise LLMError(f"No valid output after {attempts} attempts. Last error: {last_error[:500]}")


def _existing_texts(session: Session, exam: str, domain_id: int) -> tuple[set[str], list[str]]:
    rows = session.execute(select(Question.text_hash, Question.text).where(Question.exam == exam)).all()
    hashes = {h for h, _ in rows}
    same_domain = session.scalars(
        select(Question.text).where(Question.exam == exam, Question.domain_id == domain_id).limit(60)
    ).all()
    return hashes, list(same_domain)


def generate_questions(
    session: Session,
    llm: LLMClient,
    catalogue: Catalogue,
    bank_root: Path,
    exam_key: str,
    domain_id: int,
    difficulty: str,
    count: int,
    model: str,
    verifier_model: str | None = None,
    progress: Progress | None = None,
) -> GenerationResult:
    exam = catalogue.exam(exam_key)
    if exam is None:
        raise ValueError(f"Unknown exam {exam_key}")
    domain = exam.domain(domain_id)
    if domain is None:
        raise ValueError(f"Domain {domain_id} is not part of {exam.code}")
    difficulty = difficulty.lower()
    if difficulty not in DIFFICULTIES:
        raise ValueError("difficulty must be easy, medium, hard, or tough")
    say = progress or (lambda _m: None)
    result = GenerationResult(exam.key, domain.id, difficulty, count)
    hashes, avoid = _existing_texts(session, exam.key, domain.id)

    remaining = count
    rounds = 0
    while remaining > 0 and rounds < max(3, (count // BATCH_SIZE) * 2 + 2):
        rounds += 1
        n = min(BATCH_SIZE, remaining)
        say(f"Generating {n} {difficulty} question(s) for {exam.code} domain {domain.id}…")
        prompt = generation_prompt(exam, domain, difficulty, n, catalogue.difficulties,
                                   avoid + [q.question for q in result.accepted])
        try:
            batch = call_structured(llm, model, GENERATOR_SYSTEM, prompt, BATCH_SCHEMA, GenBatch)
        except LLMError as e:
            result.errors.append(str(e))
            break
        fresh: list[GenQuestion] = []
        for q in batch.questions[:n]:
            h = text_hash(q.question)
            if h in hashes:
                result.duplicates += 1
                continue
            hashes.add(h)
            fresh.append(q)
        if not fresh:
            continue

        say(f"Verifying {len(fresh)} question(s)…")
        verified = verify_questions(llm, verifier_model or model, exam, domain, difficulty, fresh, result)
        result.accepted.extend(verified)
        remaining = count - len(result.accepted)

    if result.accepted:
        path = save_pending_csv(bank_root, exam, domain.id, difficulty, result.accepted)
        result.csv_path = path.relative_to(bank_root).as_posix()
        rep = import_file(session, path, bank_root, trigger="generator", catalogue=catalogue)
        result.import_report_id = rep.id if rep else None
        say(f"Saved {len(result.accepted)} question(s) to {result.csv_path} for review.")
    return result


def verify_questions(
    llm: LLMClient,
    model: str,
    exam: Exam,
    domain,
    difficulty: str,
    questions: list[GenQuestion],
    result: GenerationResult,
) -> list[GenQuestion]:
    """Second pass: keep passes, apply fixes, drop failures."""
    payload = [q.model_dump() for q in questions]
    try:
        reviews = call_structured(llm, model, VERIFIER_SYSTEM, verification_prompt(exam, domain, difficulty, payload),
                                  REVIEW_SCHEMA, ReviewBatch)
    except LLMError as e:
        result.errors.append(f"Verification failed, batch discarded: {e}")
        for q in questions:
            result.discarded.append({"question": q.question, "issues": ["not verified"]})
        return []
    by_index = {r.index: r for r in reviews.reviews}
    kept: list[GenQuestion] = []
    for i, q in enumerate(questions):
        r = by_index.get(i)
        if r is None:
            result.discarded.append({"question": q.question, "issues": ["verifier returned no verdict"]})
        elif r.verdict == "pass":
            kept.append(q)
        elif r.verdict == "fix" and r.fixed is not None:
            kept.append(r.fixed)
            result.fixed += 1
        else:
            result.discarded.append({"question": q.question, "issues": r.issues or ["failed review"]})
    return kept


def save_pending_csv(bank_root: Path, exam: Exam, domain_id: int, difficulty: str,
                     questions: list[GenQuestion]) -> Path:
    stamp = clock.utcnow().strftime("%Y%m%d-%H%M%S")
    folder = bank_root / exam.key / "generated"
    path = folder / f"{stamp}-d{domain_id}-{difficulty}.csv"
    i = 1
    while path.exists():
        i += 1
        path = folder / f"{stamp}-d{domain_id}-{difficulty}-{i}.csv"
    domain = exam.domain(domain_id)
    rows = []
    for q in questions:
        row = {
            "exam": exam.code,
            "domain": domain.name if domain else str(domain_id),
            "difficulty": difficulty,
            "question_type": q.question_type,
            "question": q.question,
            "correct": ",".join(q.correct),
            "explanation": q.full_explanation(),
            "services": ";".join(q.services),
            "reference_url": q.reference_url,
            STATUS_COLUMN: "pending",
        }
        for o in q.options:
            row[f"option_{o.letter.lower()}"] = o.text
        rows.append(row)
    write_rows(path, rows, include_status=True)
    return path


def plan_seed(exam: Exam, total: int) -> list[tuple[int, str, int]]:
    """Split `total` questions across domains (by weight) and difficulties (by blend)."""
    plan: list[tuple[int, str, int]] = []
    per_domain = apportion(total, {d.id: d.weight for d in exam.domains})
    blend = {k: exam.difficulty_blend.get(k, 25.0) for k in DIFFICULTIES}
    for d in exam.domains:
        for diff, n in apportion(per_domain[d.id], blend).items():
            if n:
                plan.append((d.id, diff, n))
    return plan
