"""Shared fixtures. Environment is set before any app module is imported."""
from __future__ import annotations

import csv
import os
import random
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="cloudcert-test-"))
os.environ["CLOUDCERT_DATA_DIR"] = str(_TMP / "data")
os.environ["CLOUDCERT_QUESTION_BANK"] = str(_TMP / "bank")
os.environ["CLOUDCERT_FRONTEND_DIST"] = str(_TMP / "no-dist")
os.environ["CLOUDCERT_WATCH"] = "0"
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest  # noqa: E402

from app import clock  # noqa: E402
from app.bank.csvio import COLUMNS  # noqa: E402
from app.bank.normalize import text_hash  # noqa: E402
from app.db import SessionLocal, init_engine  # noqa: E402
from app.exams import get_catalogue  # noqa: E402
from app.models import Question  # noqa: E402


@pytest.fixture
def catalogue():
    return get_catalogue()


@pytest.fixture
def db():
    init_engine("sqlite:///:memory:")
    s = SessionLocal()
    yield s
    s.close()
    clock.set_now(None)


@pytest.fixture
def bank(tmp_path) -> Path:
    root = tmp_path / "bank"
    for k in ("clf-c02", "saa-c03", "sap-c02"):
        (root / k).mkdir(parents=True)
    return root


def row(**kw) -> dict:
    base = {
        "exam": "SAA-C03",
        "domain": "Design Resilient Architectures",
        "difficulty": "Medium",
        "question_type": "single",
        "question": "Which service decouples producers and consumers with a managed message queue?",
        "option_a": "Amazon SQS",
        "option_b": "Amazon EBS",
        "option_c": "AWS Glue",
        "option_d": "Amazon Athena",
        "correct": "A",
        "explanation": "Amazon SQS is a managed message queue.",
        "services": "Amazon SQS",
        "reference_url": "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html",
    }
    base.update(kw)
    return base


def write_csv(path: Path, rows: list[dict], extra_cols: tuple[str, ...] = ()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = COLUMNS + list(extra_cols)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return path


def add_questions(session, exam: str, per_cell: int = 5, status: str = "active", qtype: str = "single") -> list:
    """Add `per_cell` questions for every domain x difficulty of an exam."""
    cat = get_catalogue()
    e = cat.exam(exam)
    out = []
    for d in e.domains:
        for diff in ("easy", "medium", "hard", "tough"):
            for i in range(per_cell):
                text = f"{exam} d{d.id} {diff} question {i} {random.random()}"
                q = Question(exam=e.key, domain_id=d.id, difficulty=diff,
                             question_type=qtype, text=text, text_hash=text_hash(text),
                             options=["opt A", "opt B", "opt C", "opt D", "opt E"],
                             correct="A,C" if qtype == "multiple" else "B",
                             explanation="because", services=["Amazon S3"] if i % 2 else ["AWS Lambda"],
                             status=status)
                session.add(q)
                out.append(q)
    session.commit()
    return out
