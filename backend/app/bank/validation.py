"""Row-level validation for question CSVs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..exams import DIFFICULTIES, Catalogue
from .csvio import OPTION_COLUMNS

LETTERS = "ABCDEF"
STATUSES = {"active": "active", "approved": "active", "pending": "pending", "pending review": "pending",
            "pending_review": "pending", "rejected": "rejected", "": "active"}
QTYPES = {"single": "single", "single-choice": "single", "single_choice": "single", "mc": "single",
          "multiple": "multiple", "multi": "multiple", "multiple-response": "multiple",
          "multiple_response": "multiple", "mr": "multiple"}
MIN_OPTIONS = 3


class RowError(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass
class ValidRow:
    exam: str  # exam key, e.g. "saa-c03"
    domain_id: int
    difficulty: str
    question_type: str
    text: str
    options: list[str]
    correct: str  # sorted letters, comma separated
    explanation: str
    services: list[str] = field(default_factory=list)
    reference_url: str = ""
    status: str = "active"


def parse_letters(value: str) -> list[str]:
    parts = [p for p in re.split(r"[\s,;/|]+", (value or "").strip().upper()) if p]
    # Allow "AD" shorthand as well as "A,D"
    if len(parts) == 1 and len(parts[0]) > 1 and all(c in LETTERS for c in parts[0]):
        parts = list(parts[0])
    return parts


def validate_row(raw: dict[str, str], catalogue: Catalogue, folder_exam: str | None = None) -> ValidRow:
    """Validate a CSV row. Raises RowError listing every problem found."""
    reasons: list[str] = []
    get = lambda k: (raw.get(k) or "").strip()  # noqa: E731

    if raw.get("__extra__"):
        reasons.append("row has more cells than the header (check for unquoted commas)")

    for col in ("exam", "domain", "difficulty", "question_type", "question", "correct", "explanation"):
        if not get(col):
            reasons.append(f"'{col}' is required")

    exam = catalogue.exam(get("exam")) if get("exam") else None
    if get("exam") and exam is None:
        reasons.append(f"unknown exam '{get('exam')}' (expected one of: "
                       + ", ".join(e.code for e in catalogue.exams.values()) + ")")
    if exam and folder_exam and exam.key != folder_exam:
        reasons.append(f"exam '{get('exam')}' does not match folder '{folder_exam}/'")

    domain_id = 0
    if exam and get("domain"):
        d = exam.domain(get("domain"))
        if d is None:
            reasons.append(f"'{get('domain')}' is not a domain of {exam.code} (valid: "
                           + "; ".join(f"{x.id} {x.name}" for x in exam.domains) + ")")
        else:
            domain_id = d.id

    difficulty = get("difficulty").lower()
    if difficulty and difficulty not in DIFFICULTIES:
        reasons.append(f"difficulty '{get('difficulty')}' must be one of Easy, Medium, Hard, Tough")

    qtype = QTYPES.get(get("question_type").lower())
    if get("question_type") and qtype is None:
        reasons.append(f"question_type '{get('question_type')}' must be 'single' or 'multiple'")

    # Options: contiguous from A, at least MIN_OPTIONS, no duplicates.
    values = [get(c) for c in OPTION_COLUMNS]
    last = max((i for i, v in enumerate(values) if v), default=-1)
    options = values[: last + 1]
    gaps = [OPTION_COLUMNS[i] for i, v in enumerate(options) if not v]
    if gaps:
        reasons.append(f"{', '.join(gaps)} empty but a later option is filled (options must be contiguous)")
    if len(options) < MIN_OPTIONS:
        reasons.append(f"at least {MIN_OPTIONS} options are required (found {len([v for v in options if v])})")
    lowered = [v.lower() for v in options if v]
    if len(set(lowered)) != len(lowered):
        reasons.append("two options have identical text")

    letters = parse_letters(get("correct"))
    available = LETTERS[: len(options)]
    if get("correct"):
        bad = [x for x in letters if x not in available]
        if bad:
            reasons.append(f"correct answer(s) {', '.join(bad)} not among the options ({', '.join(available) or 'none'})")
        if len(set(letters)) != len(letters):
            reasons.append("correct answer lists the same letter twice")
        if qtype == "single" and len(set(letters)) != 1:
            reasons.append("single-answer questions need exactly one correct letter")
        if qtype == "multiple":
            n = len(set(letters))
            if n < 2:
                reasons.append("multiple-response questions need at least two correct letters")
            elif n >= len(options):
                reasons.append("multiple-response questions need at least one incorrect option")

    url = get("reference_url")
    if url and not re.match(r"^https?://\S+$", url):
        reasons.append("reference_url must start with http:// or https://")

    status_raw = get("status").lower()
    status = STATUSES.get(status_raw)
    if status is None:
        reasons.append(f"status '{get('status')}' must be active, pending, or rejected")

    if reasons:
        raise RowError(reasons)

    services = [s.strip() for s in re.split(r"[;\n]+", get("services")) if s.strip()]
    return ValidRow(
        exam=exam.key,  # type: ignore[union-attr]
        domain_id=domain_id,
        difficulty=difficulty,
        question_type=qtype,  # type: ignore[arg-type]
        text=get("question"),
        options=options,
        correct=",".join(sorted(set(letters))),
        explanation=get("explanation"),
        services=services,
        reference_url=url,
        status=status or "active",
    )
