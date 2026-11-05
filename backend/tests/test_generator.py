import copy

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.generator.demo import demo_llm
from app.generator.llm import FakeLLM, LLMError
from app.generator.schemas import GenBatch, GenQuestion
from app.generator.service import call_structured, generate_questions, plan_seed
from app.models import Question

GOOD = {
    "question": "A company needs a managed queue so its order service and email service can scale independently. "
                "Which service should it use?",
    "question_type": "single",
    "options": [
        {"letter": "A", "text": "Amazon SQS", "why": "Managed queue that decouples producers and consumers."},
        {"letter": "B", "text": "Amazon EBS", "why": "Block storage, not messaging."},
        {"letter": "C", "text": "AWS Glue", "why": "ETL service, not messaging."},
        {"letter": "D", "text": "Amazon Athena", "why": "Interactive query service."},
    ],
    "correct": ["A"],
    "explanation": "Amazon SQS provides a fully managed message queue for decoupling.",
    "services": ["Amazon SQS"],
    "reference_url": "https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html",
    "task_statement": "2.1",
}


def q(**kw):
    d = copy.deepcopy(GOOD)
    d.update(kw)
    return d


def test_schema_accepts_good_question():
    g = GenQuestion.model_validate(GOOD)
    assert g.correct == ["A"]
    assert "Correct." in g.full_explanation() and "Incorrect." in g.full_explanation()


@pytest.mark.parametrize("bad", [
    q(correct=["E"]),
    q(correct=["A", "B"]),
    q(question_type="multiple", correct=["A"]),
    q(options=GOOD["options"][:3]),
    q(reference_url="https://example.com/sqs"),
    q(options=[{**o, "letter": "ABCE"[i]} for i, o in enumerate(GOOD["options"])]),
])
def test_schema_rejects_bad_questions(bad):
    with pytest.raises(ValidationError):
        GenQuestion.model_validate(bad)


def test_multiple_response_gets_choose_label():
    opts = GOOD["options"] + [{"letter": "E", "text": "Amazon SNS", "why": "Pub/sub fan-out also decouples."},
                              {"letter": "F", "text": "AWS Batch", "why": "Batch compute."}]
    g = GenQuestion.model_validate(q(question_type="multiple", options=opts, correct=["E", "A"]))
    assert g.correct == ["A", "E"]
    assert g.question.endswith("(Choose TWO.)")


def test_retries_on_malformed_json_then_succeeds():
    outputs = iter(["{not json", {"questions": [q(correct=["Z"])]}, {"questions": [GOOD]}])
    llm = FakeLLM(lambda s, m, sc: next(outputs))
    res = call_structured(llm, "m", "sys", "prompt", {}, GenBatch, backoff_sec=0)
    assert len(res.questions) == 1
    assert len(llm.calls) == 3
    # The validation error is fed back to the model on retry
    assert "failed validation" in llm.calls[1]["messages"][-1]["content"]


def test_gives_up_after_max_attempts():
    llm = FakeLLM(lambda s, m, sc: "nope")
    with pytest.raises(LLMError):
        call_structured(llm, "m", "sys", "prompt", {}, GenBatch, backoff_sec=0)
    assert len(llm.calls) == 3


def test_verifier_keeps_pass_applies_fix_drops_fail(db, bank, catalogue):
    second = q(question="A team wants to run containers without managing servers or clusters. "
                        "Which option meets this need?",
               options=[{"letter": "A", "text": "AWS Fargate", "why": "Serverless compute for containers."},
                        {"letter": "B", "text": "Amazon EC2", "why": "You manage instances."},
                        {"letter": "C", "text": "Amazon EMR", "why": "Big data clusters."},
                        {"letter": "D", "text": "AWS Outposts", "why": "On-premises racks."}],
               services=["AWS Fargate"])
    third = q(question="Which service is a bad question that the verifier will reject outright today?")
    fixed = q(question="A fixed version of the container question: which serverless compute engine runs "
                       "containers without managing servers?",
              options=second["options"])

    def responder(system, messages, schema):
        if "questions" in schema["properties"]:
            return {"questions": [GOOD, second, third]}
        return {"reviews": [
            {"index": 0, "verdict": "pass", "issues": [], "fixed": None},
            {"index": 1, "verdict": "fix", "issues": ["ambiguous"], "fixed": fixed},
            {"index": 2, "verdict": "fail", "issues": ["two defensible answers"], "fixed": None},
        ]}

    res = generate_questions(db, FakeLLM(responder), catalogue, bank, "saa-c03", 2, "medium", 3, "m")
    assert len(res.accepted) == 2
    assert res.fixed == 1
    assert res.discarded[0]["issues"] == ["two defensible answers"]
    assert res.csv_path.startswith("saa-c03/generated/")
    stored = db.scalars(select(Question)).all()
    assert len(stored) == 2
    assert {s.status for s in stored} == {"pending"}
    assert {s.source for s in stored} == {"generated"}
    assert any(s.text.startswith("A fixed version") for s in stored)


def test_generated_duplicates_are_skipped(db, bank, catalogue):
    def responder(system, messages, schema):
        if "questions" in schema["properties"]:
            return {"questions": [GOOD]}
        return {"reviews": [{"index": 0, "verdict": "pass", "issues": [], "fixed": None}]}

    generate_questions(db, FakeLLM(responder), catalogue, bank, "saa-c03", 2, "medium", 1, "m")
    res = generate_questions(db, FakeLLM(responder), catalogue, bank, "saa-c03", 2, "medium", 1, "m")
    assert res.accepted == [] and res.duplicates >= 1


def test_demo_pipeline_end_to_end(db, bank, catalogue):
    res = generate_questions(db, demo_llm(), catalogue, bank, "clf-c02", 3, "hard", 8, "demo")
    assert len(res.accepted) >= 6
    assert all(q.status == "pending" for q in db.scalars(select(Question)))


def test_plan_seed_follows_weights(catalogue):
    exam = catalogue.exam("saa-c03")
    plan = plan_seed(exam, 100)
    assert sum(n for _, _, n in plan) == 100
    per_domain = {}
    for d, _diff, n in plan:
        per_domain[d] = per_domain.get(d, 0) + n
    assert per_domain == {1: 30, 2: 26, 3: 24, 4: 20}
