"""Command-line tools.

    python -m app.cli import [PATH ...] [--force]
    python -m app.cli generate --exam saa-c03 --domain 2 --difficulty hard --count 5
    python -m app.cli seed [--exam all] [--per-exam 100] [--dry-run]
    python -m app.cli stats
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bank.importer import import_file, scan_bank
from .db import SessionLocal, init_engine
from .exams import get_catalogue
from .settings import get_settings


def _print_report(rep) -> None:
    status = "FAILED" if rep.fatal else "ok"
    print(f"[{status}] {rep.path}: {rep.total_rows} rows, {rep.inserted} new, {rep.updated} updated, "
          f"{rep.unchanged} unchanged, {rep.skipped} skipped")
    if rep.fatal:
        print(f"    {rep.fatal}")
    for e in rep.errors or []:
        where = f"row {e['row']}" if e["row"] else "note"
        print(f"    {where}: {e['reason']}")


def cmd_import(args) -> int:
    s = get_settings()
    session = SessionLocal()
    try:
        if args.paths:
            for p in args.paths:
                rep = import_file(session, Path(p), s.question_bank, trigger="cli", force=True)
                if rep:
                    _print_report(rep)
        else:
            res = scan_bank(session, s.question_bank, trigger="cli", force=args.force)
            for rep in res.reports:
                _print_report(rep)
            print(f"{len(res.reports)} file(s) imported, {len(res.unchanged_files)} unchanged.")
    finally:
        session.close()
    return 0


def _llm(dry_run: bool):
    if dry_run:
        from .generator.demo import demo_llm

        return demo_llm()
    s = get_settings()
    if not s.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set. Add it to .env (see .env.example), or use --dry-run.", file=sys.stderr)
        sys.exit(2)
    from .generator.llm import AnthropicLLM

    return AnthropicLLM(s.anthropic_api_key, effort=s.effort, use_fallbacks=s.use_fallbacks)


def _run_plan(plan, dry_run: bool) -> int:
    from .generator.service import generate_questions

    s = get_settings()
    llm = _llm(dry_run)
    session = SessionLocal()
    total = 0
    try:
        for exam, domain_id, difficulty, count in plan:
            res = generate_questions(session, llm, get_catalogue(), s.question_bank, exam, domain_id, difficulty,
                                     count, s.model, s.verifier_model, progress=lambda m: print("  " + m))
            total += len(res.accepted)
            for d in res.discarded:
                print(f"  discarded: {d['question'][:80]}… ({'; '.join(d['issues'])})")
            for e in res.errors:
                print(f"  error: {e}", file=sys.stderr)
            if res.errors and not res.accepted:
                return 1
    finally:
        session.close()
    print(f"Done. {total} question(s) saved with status 'pending'. Approve them in the Review screen.")
    return 0


def cmd_generate(args) -> int:
    return _run_plan([(args.exam, args.domain, args.difficulty, args.count)], args.dry_run)


def cmd_seed(args) -> int:
    from .generator.service import plan_seed

    cat = get_catalogue()
    keys = list(cat.exams) if args.exam == "all" else [args.exam]
    plan = []
    for k in keys:
        exam = cat.exam(k)
        if exam is None:
            print(f"Unknown exam {k}", file=sys.stderr)
            return 2
        for d, diff, n in plan_seed(exam, args.per_exam):
            plan.append((exam.key, d, diff, n))
    print(f"Seed plan: {sum(p[3] for p in plan)} question(s) in {len(plan)} batch group(s).")
    return _run_plan(plan, args.dry_run)


def cmd_stats(_args) -> int:
    from sqlalchemy import func, select

    from .models import Question

    session = SessionLocal()
    try:
        rows = session.execute(select(Question.exam, Question.status, func.count())
                               .group_by(Question.exam, Question.status)).all()
        for exam, status, n in sorted(rows):
            print(f"{exam:8} {status:9} {n}")
    finally:
        session.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cloudcert", description="CloudCert Lab tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("import", help="Import CSVs (all of question_bank/ by default)")
    pi.add_argument("paths", nargs="*")
    pi.add_argument("--force", action="store_true", help="Re-import files even if unchanged")
    pi.set_defaults(func=cmd_import)

    pg = sub.add_parser("generate", help="Generate questions with Claude (saved as pending review)")
    pg.add_argument("--exam", required=True)
    pg.add_argument("--domain", type=int, required=True)
    pg.add_argument("--difficulty", required=True, choices=["easy", "medium", "hard", "tough"])
    pg.add_argument("--count", type=int, default=5)
    pg.add_argument("--dry-run", action="store_true", help="Use the offline demo generator (no API calls)")
    pg.set_defaults(func=cmd_generate)

    ps = sub.add_parser("seed", help="Generate a starter set spread by domain weights and difficulty")
    ps.add_argument("--exam", default="all")
    ps.add_argument("--per-exam", type=int, default=100)
    ps.add_argument("--dry-run", action="store_true", help="Use the offline demo generator (no API calls)")
    ps.set_defaults(func=cmd_seed)

    pt = sub.add_parser("stats", help="Question counts by exam and status")
    pt.set_defaults(func=cmd_stats)

    args = p.parse_args(argv)
    init_engine()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
