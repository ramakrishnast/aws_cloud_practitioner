from conftest import row, write_csv
from sqlalchemy import func, select

from app.bank.importer import import_file, scan_bank
from app.bank.normalize import normalize_text, text_hash
from app.models import Question


def count(db):
    return db.scalar(select(func.count()).select_from(Question))


def test_normalization_ignores_case_punctuation_space():
    a = "Which  service is BEST for queues?"
    b = "which service is best for queues"
    assert normalize_text(a) == normalize_text(b)
    assert text_hash(a) == text_hash(b)
    assert text_hash(a) != text_hash("Which service is best for topics?")


def test_reimport_unchanged_file_is_skipped(db, bank, catalogue):
    p = write_csv(bank / "saa-c03" / "a.csv", [row()])
    assert import_file(db, p, bank, catalogue=catalogue).inserted == 1
    assert import_file(db, p, bank, catalogue=catalogue) is None
    assert count(db) == 1


def test_updated_csv_updates_instead_of_duplicating(db, bank, catalogue):
    p = write_csv(bank / "saa-c03" / "a.csv", [row()])
    import_file(db, p, bank, catalogue=catalogue)
    # Same question, different punctuation/case + new explanation and difficulty
    write_csv(p, [row(question=row()["question"].upper().rstrip("?") + " ?", explanation="New text", difficulty="Hard")])
    rep = import_file(db, p, bank, catalogue=catalogue)
    assert rep.inserted == 0 and rep.updated == 1
    assert count(db) == 1
    q = db.scalar(select(Question))
    assert q.explanation == "New text" and q.difficulty == "hard"


def test_duplicate_within_file_is_reported(db, bank, catalogue):
    p = write_csv(bank / "saa-c03" / "a.csv", [row(), row(question=row()["question"].lower())])
    rep = import_file(db, p, bank, catalogue=catalogue)
    assert rep.inserted == 1
    assert rep.errors[0]["row"] == 3
    assert "duplicate of row 2" in rep.errors[0]["reason"]


def test_duplicate_across_files_updates_single_record(db, bank, catalogue):
    write_csv(bank / "saa-c03" / "a.csv", [row()])
    write_csv(bank / "saa-c03" / "b.csv", [row(explanation="From file b")])
    scan_bank(db, bank, catalogue=catalogue)
    assert count(db) == 1
    q = db.scalar(select(Question))
    assert q.source_file in ("saa-c03/a.csv", "saa-c03/b.csv")


def test_same_text_in_different_exams_is_not_a_duplicate(db, bank, catalogue):
    write_csv(bank / "saa-c03" / "a.csv", [row()])
    write_csv(bank / "sap-c02" / "a.csv", [row(exam="SAP-C02", domain="Design for New Solutions")])
    scan_bank(db, bank, catalogue=catalogue)
    assert count(db) == 2


def test_row_removed_from_file_is_removed(db, bank, catalogue):
    second = row(question="Which service provides managed Kubernetes control planes on AWS?",
                 option_a="Amazon EKS")
    p = write_csv(bank / "saa-c03" / "a.csv", [row(), second])
    import_file(db, p, bank, catalogue=catalogue)
    assert count(db) == 2
    write_csv(p, [row()])
    import_file(db, p, bank, catalogue=catalogue)
    assert count(db) == 1


def test_template_files_are_ignored_by_scan(db, bank, catalogue):
    write_csv(bank / "saa-c03" / "TEMPLATE.csv", [row()])
    res = scan_bank(db, bank, catalogue=catalogue)
    assert res.reports == [] and count(db) == 0
