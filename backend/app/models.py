"""Database models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .clock import utcnow
from .db import Base

LETTERS = "ABCDEF"


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("exam", "text_hash", name="uq_question_exam_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam: Mapped[str] = mapped_column(String(16), index=True)
    domain_id: Mapped[int] = mapped_column(Integer, index=True)
    difficulty: Mapped[str] = mapped_column(String(10), index=True)
    question_type: Mapped[str] = mapped_column(String(10))  # single | multiple
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(40), index=True)
    options: Mapped[list[str]] = mapped_column(JSON)  # option texts in A..F order
    correct: Mapped[str] = mapped_column(String(16))  # "B" or "A,D"
    explanation: Mapped[str] = mapped_column(Text, default="")
    services: Mapped[list[str]] = mapped_column(JSON, default=list)
    reference_url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)  # active|pending|rejected
    source: Mapped[str] = mapped_column(String(12), default="csv")  # csv | generated
    source_file: Mapped[str] = mapped_column(Text, default="")  # path relative to question_bank
    source_row: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    @property
    def correct_letters(self) -> list[str]:
        return [c for c in self.correct.split(",") if c]

    @property
    def choose_count(self) -> int:
        return len(self.correct_letters)


class SourceFile(Base):
    """Tracks imported CSV files so unchanged files are skipped."""

    __tablename__ = "source_files"

    path: Mapped[str] = mapped_column(Text, primary_key=True)  # relative to question_bank
    sha256: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ImportReport(Base):
    __tablename__ = "import_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(String(12), default="manual")  # manual|watcher|startup|cli
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict]] = mapped_column(JSON, default=list)  # [{row, reason}]
    fatal: Mapped[str] = mapped_column(Text, default="")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam: Mapped[str] = mapped_column(String(16), index=True)
    mode: Mapped[str] = mapped_column(String(10))  # full|practice|drill|weak
    difficulty: Mapped[str] = mapped_column(String(10))  # easy..tough|mixed
    domain_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feedback: Mapped[str] = mapped_column(String(10), default="end")  # immediate|end
    status: Mapped[str] = mapped_column(String(12), default="in_progress")  # in_progress|submitted
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    time_limit_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    auto_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    scaled_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list)

    answers: Mapped[list[AttemptAnswer]] = relationship(
        back_populates="attempt", order_by="AttemptAnswer.position", cascade="all, delete-orphan"
    )


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "position", name="uq_answer_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    selected: Mapped[str] = mapped_column(String(16), default="")  # "A,C"
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    revealed: Mapped[bool] = mapped_column(Boolean, default=False)  # immediate-feedback modes
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    time_spent_sec: Mapped[float] = mapped_column(Float, default=0)

    attempt: Mapped[Attempt] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship()


class ReviewItem(Base):
    """Spaced-repetition state for a question (Leitner boxes)."""

    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), unique=True)
    exam: Mapped[str] = mapped_column(String(16), index=True)
    box: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    right_streak: Mapped[int] = mapped_column(Integer, default=0)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    question: Mapped[Question] = relationship()
