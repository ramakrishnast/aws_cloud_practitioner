"""Prompts for question generation and verification."""
from __future__ import annotations

import json

from ..exams import Domain, Exam

GENERATOR_SYSTEM = """\
You write original practice questions for AWS certification exams. The questions are used by one \
person preparing for the exam on their own machine.

Every question must be your own original work. Never reproduce or paraphrase real exam questions, \
exam dumps, or third-party question banks; build fresh scenarios from the exam guide's task statements \
and your knowledge of AWS.

What a good question looks like:
- It tests one task statement from the exam guide and states the requirement that decides the answer \
(cost, availability, latency, operational overhead, compliance, and so on).
- It reflects current AWS service names, features, and limits. If a fact has changed recently or you \
are unsure of it, write a different question rather than guess.
- Exactly one option (or, for multiple-response, exactly the stated number of options) is defensible \
given the stated requirements. Distractors are plausible: real services or configurations that fail a \
stated requirement, not nonsense.
- Option lengths and styles are similar so the answer cannot be guessed from formatting.
- The explanation says why the answer is correct; each option's "why" says specifically why that \
option is right or wrong.
- reference_url points to the most relevant official AWS documentation page \
(docs.aws.amazon.com or aws.amazon.com).
- services lists the AWS services the question is about, using their official short names \
(for example "Amazon S3", "AWS Lambda").
"""

VERIFIER_SYSTEM = """\
You are a meticulous reviewer of AWS certification practice questions. For each question decide:
- "pass": accurate, unambiguous, exactly one defensible answer set, matches the stated difficulty.
- "fix": salvageable. Return a corrected full question in "fixed" (keep it original, keep the same \
domain and difficulty).
- "fail": cannot be repaired cheaply (wrong premise, outdated service behavior that changes the \
answer, or a scenario where several answers are equally defensible).

Check specifically: ambiguity in the wording; service facts that are outdated or wrong; more than one \
defensible answer (or fewer than required); distractors that are obviously wrong; an answer key that \
does not match the explanation; a reference_url that is not an official AWS documentation page; and \
any sign the question copies a known exam question. List every problem you find in "issues". Use \
"fixed": null unless the verdict is "fix".
"""


def _difficulty_guide(exam: Exam, difficulty: str, descriptions: dict[str, str]) -> str:
    extra = {
        "easy": "One or two sentences. Single-answer.",
        "medium": "A short scenario (2-3 sentences) with one clear deciding requirement. Mostly single-answer.",
        "hard": "A multi-service scenario (3-5 sentences) where options trade off cost, resilience, and "
                "performance. Include some multiple-response questions.",
        "tough": "A long professional-level scenario (5-8 sentences) with constraints from several teams; "
                 "several options look plausible. Roughly a third should be multiple-response.",
    }[difficulty]
    return f"{difficulty.title()}: {descriptions.get(difficulty, '')}. {extra}"


def generation_prompt(
    exam: Exam,
    domain: Domain,
    difficulty: str,
    count: int,
    descriptions: dict[str, str],
    avoid: list[str],
) -> str:
    tasks = "\n".join(f"- {t}" for t in domain.tasks) or "- (see the official exam guide)"
    avoid_block = ""
    if avoid:
        sample = "\n".join(f"- {t[:160]}" for t in avoid[:40])
        avoid_block = f"\nThe bank already has questions like these; cover different ground:\n{sample}\n"
    return (
        f"Exam: {exam.name} ({exam.code})\n"
        f"Domain {domain.id}: {domain.name} ({domain.weight:g}% of the exam)\n"
        f"Task statements for this domain:\n{tasks}\n\n"
        f"Difficulty: {_difficulty_guide(exam, difficulty, descriptions)}\n\n"
        f"Write {count} new question(s). Spread them across the task statements. "
        "Each question has 4 to 6 options lettered from A. Single-answer questions have exactly one "
        "correct letter. Multiple-response questions have two or three correct letters and say "
        "\"(Choose TWO.)\" or \"(Choose THREE.)\" at the end of the question. Put the task statement "
        "number and title in task_statement.\n"
        f"{avoid_block}"
    )


def verification_prompt(exam: Exam, domain: Domain, difficulty: str, questions: list[dict]) -> str:
    return (
        f"Exam: {exam.name} ({exam.code}). Domain {domain.id}: {domain.name}. "
        f"Intended difficulty: {difficulty}.\n\n"
        "Review each question below. Return one review per question, using its index.\n\n"
        + json.dumps([{"index": i, **q} for i, q in enumerate(questions)], indent=1)
    )
