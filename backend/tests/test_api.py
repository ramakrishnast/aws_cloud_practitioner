import pytest
from conftest import row, write_csv
from fastapi.testclient import TestClient

import app.main as main
from app.db import init_engine
from app.settings import get_settings


@pytest.fixture
def client(monkeypatch):
    init_engine("sqlite:///:memory:")
    monkeypatch.setattr(main, "init_engine", lambda *a, **k: None)
    bank = get_settings().question_bank
    for k in ("clf-c02", "saa-c03", "sap-c02"):
        (bank / k).mkdir(parents=True, exist_ok=True)
    rows = []
    for d in range(1, 5):
        for i in range(4):
            rows.append(row(domain=str(d), difficulty=["Easy", "Medium", "Hard", "Tough"][i],
                            question=f"API test question for domain {d} number {i}: which option is a queue?"))
    write_csv(bank / "saa-c03" / "api.csv", rows)
    with TestClient(main.app) as c:
        yield c
    (bank / "saa-c03" / "api.csv").unlink()


def test_exams_endpoint(client):
    data = client.get("/api/exams").json()
    keys = [e["key"] for e in data["exams"]]
    assert keys == ["clf-c02", "saa-c03", "sap-c02"]
    saa = next(e for e in data["exams"] if e["key"] == "saa-c03")
    assert saa["active_questions"] == 16
    assert saa["readiness"]["status"] == "insufficient"


def test_full_exam_hides_answers_until_submit(client):
    a = client.post("/api/attempts", json={"exam": "saa-c03", "mode": "full"}).json()
    assert a["total"] == 16 and a["time_limit_sec"] == 130 * 60
    assert any("Only 16" in n for n in a["notes"])
    first = a["answers"][0]
    assert "feedback" not in first and "correct" not in first["question"]
    r = client.put(f"/api/attempts/{a['id']}/answers/0", json={"selected": ["A"], "flagged": True})
    assert r.status_code == 200
    assert "feedback" not in r.json()["answer"]
    assert client.get(f"/api/attempts/{a['id']}/results").status_code == 409
    res = client.post(f"/api/attempts/{a['id']}/submit").json()
    assert res["status"] == "submitted"
    assert res["correct_count"] == 1
    assert res["score_is_estimate"] is True
    assert res["answers"][0]["feedback"]["correct"] == ["A"]
    assert len(res["breakdown"]["by_domain"]) == 4
    hist = client.get("/api/attempts").json()
    assert hist[0]["id"] == a["id"]


def test_practice_reveal(client):
    a = client.post("/api/attempts", json={"exam": "saa-c03", "mode": "practice", "count": 5}).json()
    r = client.put(f"/api/attempts/{a['id']}/answers/0", json={"selected": ["B"], "reveal": True}).json()
    fb = r["answer"]["feedback"]
    assert fb["is_correct"] is False and fb["correct"] == ["A"]


def test_drill_requires_domain_or_service(client):
    r = client.post("/api/attempts", json={"exam": "saa-c03", "mode": "drill"})
    assert r.status_code == 400
    r = client.post("/api/attempts", json={"exam": "saa-c03", "mode": "drill", "service": "Amazon SQS", "count": 10})
    assert r.status_code == 200 and r.json()["total"] == 10


def test_import_now_and_edit_writes_back(client):
    bank = get_settings().question_bank
    p = write_csv(bank / "saa-c03" / "extra.csv", [row(question="Which service sends push notifications to "
                                                         "mobile devices and fans out messages?",
                                                         option_a="Amazon SNS", status="pending")],
                  extra_cols=("status",))
    rep = client.post("/api/import", json={}).json()
    assert any(r["path"] == "saa-c03/extra.csv" and r["inserted"] == 1 for r in rep["reports"])
    pending = client.get("/api/questions", params={"exam": "saa-c03", "status": "pending"}).json()
    assert pending["total"] == 1
    qid = pending["items"][0]["id"]
    r = client.post(f"/api/questions/{qid}/status", json={"status": "approve"})
    assert r.status_code == 200 and r.json()["question"]["status"] == "active"
    assert "active" in p.read_text()
    bad = client.put(f"/api/questions/{qid}", json={"correct": ["F"]})
    assert bad.status_code == 422
    p.unlink()


def test_generate_without_key_is_clear_error(client):
    r = client.post("/api/generate", json={"exam": "saa-c03", "domain_id": 1, "difficulty": "easy", "count": 2})
    assert r.status_code == 400 and "ANTHROPIC_API_KEY" in r.json()["detail"]
