"""Reading and writing question CSV files."""
from __future__ import annotations

import csv
import io
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

OPTION_COLUMNS = [f"option_{c}" for c in "abcdef"]
COLUMNS = [
    "exam",
    "domain",
    "difficulty",
    "question_type",
    "question",
    *OPTION_COLUMNS,
    "correct",
    "explanation",
    "services",
    "reference_url",
]
# Optional trailing column. Generated questions are written with status=pending.
STATUS_COLUMN = "status"
REQUIRED_HEADER = set(COLUMNS) - {"option_e", "option_f", "services", "reference_url"}


class CsvFormatError(Exception):
    pass


def _clean_header(name: str | None) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def read_rows(path: Path) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    """Return (header, [(spreadsheet_row_number, row_dict), ...]).

    Row numbers match what a spreadsheet shows: the header is row 1, so the
    first data row is row 2. Fully blank rows are dropped.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="cp1252")
        except UnicodeDecodeError as e:  # pragma: no cover - rare
            raise CsvFormatError(f"File is not UTF-8 text: {e}") from e
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        raw_header = next(reader)
    except StopIteration:
        raise CsvFormatError("File is empty") from None
    header = [_clean_header(h) for h in raw_header]
    missing = sorted(REQUIRED_HEADER - set(header))
    if missing:
        raise CsvFormatError("Missing required column(s): " + ", ".join(missing))
    rows: list[tuple[int, dict[str, str]]] = []
    for i, values in enumerate(reader, start=2):
        if not any(v.strip() for v in values):
            continue
        row = {h: (values[j].strip() if j < len(values) else "") for j, h in enumerate(header) if h}
        if len(values) > len(header) and any(v.strip() for v in values[len(header):]):
            row["__extra__"] = "1"
        rows.append((i, row))
    return header, rows


def write_rows(path: Path, rows: Iterable[dict[str, str]], include_status: bool = True) -> None:
    """Atomically write rows (dicts keyed by COLUMNS [+ status])."""
    cols = COLUMNS + ([STATUS_COLUMN] if include_status else [])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".csv", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore", quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def question_to_row(q) -> dict[str, str]:
    """Convert a Question model (or similar object) to a CSV row dict."""
    from ..exams import get_catalogue

    exam = get_catalogue().exam(q.exam)
    domain = exam.domain(q.domain_id) if exam else None
    row = {
        "exam": exam.code if exam else q.exam,
        "domain": domain.name if domain else str(q.domain_id),
        "difficulty": q.difficulty,
        "question_type": q.question_type,
        "question": q.text,
        "correct": q.correct,
        "explanation": q.explanation,
        "services": ";".join(q.services or []),
        "reference_url": q.reference_url or "",
        STATUS_COLUMN: q.status,
    }
    for i, col in enumerate(OPTION_COLUMNS):
        row[col] = q.options[i] if i < len(q.options) else ""
    return row
