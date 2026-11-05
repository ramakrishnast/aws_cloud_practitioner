"""Import question CSVs into the database (validate, dedupe, upsert)."""
from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..exams import Catalogue, get_catalogue
from ..models import AttemptAnswer, ImportReport, Question, SourceFile
from .csvio import CsvFormatError, read_rows
from .normalize import text_hash
from .validation import RowError, validate_row

log = logging.getLogger(__name__)

# Serialises imports triggered by the watcher, the API, and the CLI.
IMPORT_LOCK = threading.RLock()

UPDATABLE = ("domain_id", "difficulty", "question_type", "text", "options", "correct", "explanation",
             "services", "reference_url", "status")


@dataclass
class ScanResult:
    reports: list[ImportReport] = field(default_factory=list)
    unchanged_files: list[str] = field(default_factory=list)


def is_bank_csv(path: Path) -> bool:
    name = path.name
    return (
        path.suffix.lower() == ".csv"
        and not name.startswith((".", "~$"))
        and not name.upper().startswith("TEMPLATE")
    )


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _folder_exam(rel: str, catalogue: Catalogue) -> str | None:
    first = rel.split("/", 1)[0].lower()
    return first if first in catalogue.exams and "/" in rel else None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_file(
    session: Session,
    path: Path,
    bank_root: Path,
    trigger: str = "manual",
    force: bool = False,
    catalogue: Catalogue | None = None,
) -> ImportReport | None:
    """Import one CSV. Returns None when the file is unchanged since last import."""
    catalogue = catalogue or get_catalogue()
    with IMPORT_LOCK:
        rel = _rel(path, bank_root)
        try:
            digest = file_sha256(path)
        except FileNotFoundError:
            return None
        known = session.get(SourceFile, rel)
        if known and known.sha256 == digest and not force:
            return None

        report = ImportReport(path=rel, trigger=trigger, errors=[], total_rows=0, inserted=0, updated=0,
                              unchanged=0, skipped=0, fatal="")
        source = "generated" if "/generated/" in f"/{rel}" else "csv"
        try:
            _header, rows = read_rows(path)
        except CsvFormatError as e:
            report.fatal = str(e)
            session.add(report)
            session.commit()
            return report

        report.total_rows = len(rows)
        folder_exam = _folder_exam(rel, catalogue)
        seen: dict[tuple[str, str], int] = {}
        kept_ids: set[int] = set()
        errors: list[dict] = []

        for rownum, raw in rows:
            try:
                v = validate_row(raw, catalogue, folder_exam)
            except RowError as e:
                errors.append({"row": rownum, "reason": str(e)})
                continue
            h = text_hash(v.text)
            key = (v.exam, h)
            if key in seen:
                errors.append({"row": rownum, "reason": f"duplicate of row {seen[key]} in this file"})
                continue
            seen[key] = rownum

            q = session.scalar(select(Question).where(Question.exam == v.exam, Question.text_hash == h))
            values = {
                "domain_id": v.domain_id,
                "difficulty": v.difficulty,
                "question_type": v.question_type,
                "text": v.text,
                "options": v.options,
                "correct": v.correct,
                "explanation": v.explanation,
                "services": v.services,
                "reference_url": v.reference_url,
                "status": v.status,
            }
            if q is None:
                q = Question(exam=v.exam, text_hash=h, source=source, source_file=rel, source_row=rownum, **values)
                session.add(q)
                session.flush()
                report.inserted += 1
            else:
                changed = any(getattr(q, k) != values[k] for k in UPDATABLE)
                if changed:
                    for k in UPDATABLE:
                        setattr(q, k, values[k])
                    report.updated += 1
                else:
                    report.unchanged += 1
                q.source_file, q.source_row = rel, rownum
                if q.source != "generated":
                    q.source = source
            kept_ids.add(q.id)

        # Questions that used to live in this file but are gone now (deleted or
        # reworded rows): drop them if never used in a test, otherwise retire.
        stale = session.scalars(
            select(Question).where(Question.source_file == rel, Question.id.notin_(kept_ids or {-1}))
        ).all()
        retired = 0
        for q in stale:
            used = session.scalar(select(AttemptAnswer.id).where(AttemptAnswer.question_id == q.id).limit(1))
            if used:
                if q.status != "retired":
                    q.status = "retired"
                    retired += 1
            else:
                session.delete(q)
                retired += 1
        if retired:
            errors.append({"row": 0, "reason": f"{retired} question(s) no longer in this file were removed or retired"})

        report.errors = errors
        report.skipped = len([e for e in errors if e["row"]])
        if known:
            known.sha256 = digest
        else:
            session.add(SourceFile(path=rel, sha256=digest))
        session.add(report)
        session.commit()
        log.info("Imported %s: +%d ~%d =%d skipped %d", rel, report.inserted, report.updated,
                 report.unchanged, report.skipped)
        return report


def scan_bank(
    session: Session,
    bank_root: Path,
    trigger: str = "manual",
    force: bool = False,
    catalogue: Catalogue | None = None,
) -> ScanResult:
    """Import every CSV under question_bank/<exam>/ (recursively)."""
    catalogue = catalogue or get_catalogue()
    result = ScanResult()
    for key in catalogue.exams:
        folder = bank_root / key
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.csv")):
            if not is_bank_csv(path):
                continue
            rep = import_file(session, path, bank_root, trigger=trigger, force=force, catalogue=catalogue)
            if rep is None:
                result.unchanged_files.append(_rel(path, bank_root))
            else:
                result.reports.append(rep)
    return result
