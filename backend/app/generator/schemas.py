"""Pydantic models (and matching JSON schemas) for generated questions."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

LETTERS = "ABCDEF"
CHOOSE_WORDS = {2: "TWO", 3: "THREE"}


class GenOption(BaseModel):
    letter: str
    text: str = Field(min_length=1)
    why: str = Field(min_length=1, description="Why this option is right or wrong")

    @field_validator("letter")
    @classmethod
    def _letter(cls, v: str) -> str:
        v = v.strip().upper().rstrip(").")
        if v not in LETTERS:
            raise ValueError(f"letter must be one of {LETTERS}")
        return v


class GenQuestion(BaseModel):
    question: str = Field(min_length=20)
    question_type: Literal["single", "multiple"]
    options: list[GenOption]
    correct: list[str]
    explanation: str = Field(min_length=20)
    services: list[str] = Field(default_factory=list)
    reference_url: str
    task_statement: str = ""

    @field_validator("correct")
    @classmethod
    def _correct(cls, v: list[str]) -> list[str]:
        out = sorted({x.strip().upper() for x in v if x and x.strip()})
        return out

    @field_validator("reference_url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^https://([a-z0-9-]+\.)*(aws\.amazon\.com|amazon\.com|amazonaws\.com)(/\S*)?$", v):
            raise ValueError("reference_url must be an https:// link to official AWS documentation")
        return v

    @model_validator(mode="after")
    def _consistency(self) -> GenQuestion:
        n = len(self.options)
        if not 4 <= n <= 6:
            raise ValueError(f"questions need 4-6 options (got {n})")
        letters = [o.letter for o in self.options]
        if letters != list(LETTERS[:n]):
            raise ValueError(f"option letters must be {', '.join(LETTERS[:n])} in order (got {', '.join(letters)})")
        if len({o.text.strip().lower() for o in self.options}) != n:
            raise ValueError("options must all be different")
        bad = [c for c in self.correct if c not in letters]
        if bad:
            raise ValueError(f"correct letters {bad} are not among the options")
        if self.question_type == "single" and len(self.correct) != 1:
            raise ValueError("single-answer questions need exactly one correct letter")
        if self.question_type == "multiple":
            k = len(self.correct)
            if k not in CHOOSE_WORDS:
                raise ValueError("multiple-response questions need two or three correct letters")
            if k >= n - 1:
                raise ValueError("multiple-response questions need at least two incorrect options")
            word = CHOOSE_WORDS[k]
            if not re.search(rf"choose\s+{word}", self.question, flags=re.I):
                self.question = self.question.rstrip() + f" (Choose {word}.)"
        return self

    def full_explanation(self) -> str:
        """Explanation plus a per-option rationale, as stored in the CSV."""
        lines = [self.explanation.strip(), "", "Why each option is right or wrong:"]
        for o in self.options:
            tag = "Correct" if o.letter in self.correct else "Incorrect"
            lines.append(f"{o.letter}) {tag}. {o.why.strip()}")
        return "\n".join(lines)


class GenBatch(BaseModel):
    questions: list[GenQuestion]


class Review(BaseModel):
    index: int
    verdict: Literal["pass", "fix", "fail"]
    issues: list[str] = Field(default_factory=list)
    fixed: GenQuestion | None = None


class ReviewBatch(BaseModel):
    reviews: list[Review]


# --- JSON schemas sent to the API as structured-output formats ---------------

_OPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "letter": {"type": "string", "enum": list(LETTERS)},
        "text": {"type": "string"},
        "why": {"type": "string"},
    },
    "required": ["letter", "text", "why"],
    "additionalProperties": False,
}

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "question_type": {"type": "string", "enum": ["single", "multiple"]},
        "options": {"type": "array", "items": _OPTION_SCHEMA},
        "correct": {"type": "array", "items": {"type": "string", "enum": list(LETTERS)}},
        "explanation": {"type": "string"},
        "services": {"type": "array", "items": {"type": "string"}},
        "reference_url": {"type": "string"},
        "task_statement": {"type": "string"},
    },
    "required": ["question", "question_type", "options", "correct", "explanation", "services",
                 "reference_url", "task_statement"],
    "additionalProperties": False,
}

BATCH_SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": QUESTION_SCHEMA}},
    "required": ["questions"],
    "additionalProperties": False,
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "verdict": {"type": "string", "enum": ["pass", "fix", "fail"]},
                    "issues": {"type": "array", "items": {"type": "string"}},
                    "fixed": {"anyOf": [QUESTION_SCHEMA, {"type": "null"}]},
                },
                "required": ["index", "verdict", "issues", "fixed"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["reviews"],
    "additionalProperties": False,
}
