"""Question bank: import, import reports, browse, edit, and review."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..bank.csvio import question_to_row, read_rows, write_rows
from ..bank.importer import IMPORT_LOCK, file_sha256, import_file, scan_bank
from ..bank.normalize import text_hash
from ..bank.validation import RowError, validate_row
from ..db import get_db
from ..exams import get_catalogue
from ..models import ImportReport, Question, SourceFile
from ..settings import get_settings
from .serializers import import_report, question_full

router = APIRouter(prefix="/api", tags=["bank"])


class ImportRequest(BaseModel):
    force: bool = False


@router.post("/import")
def import_now(body: ImportRequest | None = None, db: Session = Depends(get_db)):
    root = get_settings().question_bank
    res = scan_bank(db, root, trigger="manual", force=bool(body and body.force))
    return {"reports": [import_report(r) for r in res.reports], "unchanged_files": res.unchanged_files}


@router.post("/import/upload")
async def upload_csv(exam: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    cat = get_catalogue()
    e = cat.exam(exam)
    if e is None:
        raise HTTPException(400, f"Unknown exam {exam}")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file.filename or "upload.csv").name)
    if not name.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    root = get_settings().question_bank
    dest = root / e.key / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())
    rep = import_file(db, dest, root, trigger="upload", force=True)
    return {"saved_to": dest.relative_to(root).as_posix(), "report": import_report(rep) if rep else None}


@router.get("/import/reports")
def reports(limit: int = 30, db: Session = Depends(get_db)):
    rows = db.scalars(select(ImportReport).order_by(ImportReport.id.desc()).limit(min(limit, 200))).all()
    return [import_report(r) for r in rows]


@router.get("/questions")
def list_questions(
    exam: str | None = None,
    status: str | None = None,
    domain_id: int | None = None,
    difficulty: str | None = None,
    q: str | None = None,
    source: str | None = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    cat = get_catalogue()
    stmt = select(Question)
    if exam:
        e = cat.exam(exam)
        stmt = stmt.where(Question.exam == (e.key if e else exam))
    if status:
        stmt = stmt.where(Question.status == status)
    if domain_id:
        stmt = stmt.where(Question.domain_id == domain_id)
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty.lower())
    if source:
        stmt = stmt.where(Question.source == source)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Question.text.ilike(like), Question.explanation.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    page_size = max(1, min(page_size, 200))
    rows = db.scalars(stmt.order_by(Question.id.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [question_full(x, cat) for x in rows]}


@router.get("/questions/{qid}")
def get_question(qid: int, db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if q is None:
        raise HTTPException(404, "Question not found")
    return question_full(q, get_catalogue())


class QuestionEdit(BaseModel):
    domain_id: int | None = None
    difficulty: str | None = None
    question_type: str | None = None
    text: str | None = None
    options: list[str] | None = None
    correct: list[str] | None = None
    explanation: str | None = None
    services: list[str] | None = None
    reference_url: str | None = None
    status: str | None = None


def _write_back(q: Question, old_hash: str, root: Path) -> str | None:
    """Mirror an edit into the question's CSV so the file stays the source of truth."""
    if not q.source_file:
        return "Question has no source file; change saved to the database only."
    path = root / q.source_file
    if not path.exists():
        return f"{q.source_file} no longer exists; change saved to the database only."
    _header, rows = read_rows(path)
    out, found = [], False
    for _n, row in rows:
        if not found and text_hash(row.get("question", "")) == old_hash:
            out.append(question_to_row(q))
            found = True
        else:
            out.append(row)
    if not found:
        return "Could not find the row in its CSV; change saved to the database only."
    write_rows(path, out, include_status=True)
    return None


@router.put("/questions/{qid}")
def edit_question(qid: int, body: QuestionEdit, db: Session = Depends(get_db)):
    cat = get_catalogue()
    root = get_settings().question_bank
    with IMPORT_LOCK:
        q = db.get(Question, qid)
        if q is None:
            raise HTTPException(404, "Question not found")
        exam = cat.exam(q.exam)
        merged = question_to_row(q)
        upd = body.model_dump(exclude_none=True)
        if "domain_id" in upd:
            d = exam.domain(upd["domain_id"]) if exam else None
            merged["domain"] = d.name if d else str(upd["domain_id"])
        for src, dst in (("difficulty", "difficulty"), ("question_type", "question_type"), ("text", "question"),
                         ("explanation", "explanation"), ("reference_url", "reference_url"), ("status", "status")):
            if src in upd:
                merged[dst] = upd[src]
        if "options" in upd:
            for i, col in enumerate("abcdef"):
                merged[f"option_{col}"] = upd["options"][i] if i < len(upd["options"]) else ""
        if "correct" in upd:
            merged["correct"] = ",".join(upd["correct"])
        if "services" in upd:
            merged["services"] = ";".join(upd["services"])
        try:
            v = validate_row(merged, cat, q.exam)
        except RowError as e:
            raise HTTPException(422, {"errors": e.reasons}) from None
        new_hash = text_hash(v.text)
        if new_hash != q.text_hash:
            clash = db.scalar(select(Question).where(Question.exam == q.exam, Question.text_hash == new_hash,
                                                     Question.id != q.id))
            if clash:
                raise HTTPException(409, f"Another question (#{clash.id}) already has this text")
        old_hash = q.text_hash
        q.domain_id, q.difficulty, q.question_type = v.domain_id, v.difficulty, v.question_type
        q.text, q.text_hash, q.options, q.correct = v.text, new_hash, v.options, v.correct
        q.explanation, q.services, q.reference_url, q.status = v.explanation, v.services, v.reference_url, v.status
        warning = _write_back(q, old_hash, root)
        if q.source_file and (root / q.source_file).exists():
            sf = db.get(SourceFile, q.source_file)
            digest = file_sha256(root / q.source_file)
            if sf:
                sf.sha256 = digest
            else:
                db.add(SourceFile(path=q.source_file, sha256=digest))
        db.commit()
        return {"question": question_full(q, cat), "warning": warning}


class StatusChange(BaseModel):
    status: str  # active | pending | rejected


@router.post("/questions/{qid}/status")
def set_status(qid: int, body: StatusChange, db: Session = Depends(get_db)):
    status = {"approve": "active", "approved": "active", "reject": "rejected"}.get(body.status, body.status)
    if status not in ("active", "pending", "rejected"):
        raise HTTPException(400, "status must be active, pending, or rejected")
    return edit_question(qid, QuestionEdit(status=status), db)
