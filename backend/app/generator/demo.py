"""Offline demo generator: exercises the full pipeline without API calls.

Used by `python -m app.cli seed --dry-run` and the end-to-end check. The
questions it writes are clearly marked [DEMO] and are placeholders, not study
material; reject or delete them after trying the Review screen.
"""
from __future__ import annotations

import itertools
import re

from .llm import FakeLLM

_counter = itertools.count(1)

_SERVICES = [
    ("Amazon S3", "Object storage with eleven nines of durability", "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html"),
    ("Amazon DynamoDB", "Serverless key-value and document database", "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html"),
    ("AWS Lambda", "Run code without provisioning servers", "https://docs.aws.amazon.com/lambda/latest/dg/welcome.html"),
    ("Amazon CloudFront", "Content delivery network with edge locations", "https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html"),
    ("Amazon RDS", "Managed relational databases", "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html"),
]


def _question(n: int, domain: str, difficulty: str, multiple: bool) -> dict:
    svc, desc, url = _SERVICES[n % len(_SERVICES)]
    others = [s for s in _SERVICES if s[0] != svc]
    options = [{"letter": "A", "text": svc, "why": f"{svc}: {desc}."}]
    for i, (o, d, _u) in enumerate(others[:3], start=1):
        options.append({"letter": "BCD"[i - 1], "text": o, "why": f"{o} is for something else: {d.lower()}."})
    correct = ["A"]
    text = f"[DEMO #{n}] ({domain}, {difficulty}) Which AWS service best matches this description: {desc.lower()}?"
    if multiple:
        options.append({"letter": "E", "text": f"{svc} with default settings", "why": "Also matches the description."})
        options.append({"letter": "F", "text": "None of the above", "why": "A matching service exists."})
        correct = ["A", "E"]
        text += " (Choose TWO.)"
    return {
        "question": text,
        "question_type": "multiple" if multiple else "single",
        "options": options,
        "correct": correct,
        "explanation": f"{svc} is the AWS service described: {desc.lower()}. This is a demo placeholder.",
        "services": [svc],
        "reference_url": url,
        "task_statement": "demo",
    }


def _responder(system: str, messages: list[dict], schema: dict):
    prompt = messages[0]["content"]
    if "questions" in schema.get("properties", {}):
        count = int(re.search(r"Write (\d+) new", prompt).group(1))
        domain = re.search(r"Domain \d+: ([^(]+)", prompt).group(1).strip()
        difficulty = re.search(r"Difficulty: (\w+)", prompt).group(1).lower()
        qs = []
        for _ in range(count):
            n = next(_counter)
            qs.append(_question(n, domain, difficulty, multiple=difficulty in ("hard", "tough") and n % 3 == 0))
        return {"questions": qs}
    # Verifier: pass everything except every 7th question, to show discards.
    items = re.findall(r'"index": (\d+),\s*"question": "\[DEMO #(\d+)\]', prompt)
    reviews = []
    for idx, n in items:
        bad = int(n) % 7 == 0
        reviews.append({"index": int(idx), "verdict": "fail" if bad else "pass",
                        "issues": ["demo: simulated failed review"] if bad else [], "fixed": None})
    return {"reviews": reviews}


def demo_llm() -> FakeLLM:
    return FakeLLM(_responder)
