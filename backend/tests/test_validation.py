import pytest
from conftest import row, write_csv

from app.bank.importer import import_file
from app.bank.validation import RowError, validate_row


def test_valid_row(catalogue):
    v = validate_row(row(), catalogue)
    assert v.exam == "saa-c03"
    assert v.domain_id == 2
    assert v.difficulty == "medium"
    assert v.correct == "A"
    assert v.options == ["Amazon SQS", "Amazon EBS", "AWS Glue", "Amazon Athena"]
    assert v.status == "active"


def test_domain_by_number_and_label(catalogue):
    assert validate_row(row(domain="2"), catalogue).domain_id == 2
    assert validate_row(row(domain="Domain 3"), catalogue).domain_id == 3
    assert validate_row(row(domain="design resilient architectures"), catalogue).domain_id == 2


def reasons(raw, catalogue, folder=None):
    with pytest.raises(RowError) as e:
        validate_row(raw, catalogue, folder)
    return " | ".join(e.value.reasons)


def test_required_fields(catalogue):
    r = reasons(row(question="", explanation="", correct=""), catalogue)
    assert "'question' is required" in r
    assert "'explanation' is required" in r
    assert "'correct' is required" in r


def test_correct_letter_must_exist(catalogue):
    assert "not among the options" in reasons(row(correct="E"), catalogue)


def test_invalid_domain_for_exam(catalogue):
    # A CLF-C02 domain is not valid for SAA-C03
    assert "is not a domain of SAA-C03" in reasons(row(domain="Cloud Concepts"), catalogue)


def test_invalid_difficulty_and_type(catalogue):
    r = reasons(row(difficulty="Insane", question_type="essay"), catalogue)
    assert "difficulty 'Insane'" in r
    assert "question_type 'essay'" in r


def test_unknown_exam(catalogue):
    assert "unknown exam" in reasons(row(exam="XYZ-C01"), catalogue)


def test_single_vs_multiple_letter_counts(catalogue):
    assert "exactly one correct letter" in reasons(row(correct="A,B"), catalogue)
    assert "at least two correct letters" in reasons(row(question_type="multiple", correct="A"), catalogue)
    v = validate_row(row(question_type="multiple", correct="D, A"), catalogue)
    assert v.correct == "A,D"


def test_options_contiguous_and_minimum(catalogue):
    assert "contiguous" in reasons(row(option_c="", option_e="Extra"), catalogue)
    assert "at least 3 options" in reasons(row(option_c="", option_d=""), catalogue)
    assert "identical text" in reasons(row(option_b="Amazon SQS"), catalogue)


def test_folder_mismatch(catalogue):
    assert "does not match folder" in reasons(row(), catalogue, folder="clf-c02")


def test_reference_url_and_status(catalogue):
    assert "reference_url" in reasons(row(reference_url="docs.aws.amazon.com"), catalogue)
    assert "status" in reasons(row(status="maybe"), catalogue)
    assert validate_row(row(status="pending"), catalogue).status == "pending"


def test_import_report_lists_row_numbers(db, bank, catalogue):
    path = write_csv(bank / "saa-c03" / "mixed.csv", [
        row(),
        row(question="Which service stores objects durably and cheaply for archival?", correct="Z"),
        row(question="Pick a domain that does not exist for this exam ok?", domain="Billing"),
        row(question="Valid second question about load balancing traffic across targets?",
            option_a="Elastic Load Balancing"),
    ])
    rep = import_file(db, path, bank, catalogue=catalogue)
    assert rep.inserted == 2
    assert rep.skipped == 2
    rows = {e["row"]: e["reason"] for e in rep.errors}
    assert set(rows) == {3, 4}  # header is row 1
    assert "not among the options" in rows[3]
    assert "not a domain" in rows[4]


def test_missing_header_is_fatal(db, bank, catalogue):
    p = bank / "saa-c03" / "bad.csv"
    p.write_text("exam,question\nSAA-C03,hello\n")
    rep = import_file(db, p, bank, catalogue=catalogue)
    assert rep.fatal.startswith("Missing required column")
    assert rep.inserted == 0
