"""Exam catalogue loaded from config/exams.yaml."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .settings import get_settings

DIFFICULTIES = ("easy", "medium", "hard", "tough")


@dataclass(frozen=True)
class Domain:
    id: int
    name: str
    weight: float
    tasks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Exam:
    key: str  # e.g. "saa-c03" (also the question_bank subfolder name)
    name: str
    short_name: str
    code: str
    question_count: int
    time_limit_minutes: int
    passing_score: int
    estimated_raw_cut_pct: float
    guide_url: str
    difficulty_blend: dict[str, float]
    domains: tuple[Domain, ...]

    def domain(self, ref: str | int | None) -> Domain | None:
        """Resolve a domain from its name, number, or "Domain N" label."""
        if ref is None:
            return None
        s = str(ref).strip()
        if not s:
            return None
        m = re.fullmatch(r"(?:domain\s*)?(\d+)(?:[.:)\s-].*)?", s, flags=re.I)
        if m:
            num = int(m.group(1))
            for d in self.domains:
                if d.id == num:
                    return d
        norm = _norm(s)
        for d in self.domains:
            if _norm(d.name) == norm:
                return d
        return None


@dataclass(frozen=True)
class Catalogue:
    exams: dict[str, Exam]
    difficulties: dict[str, str]
    drill_min: int = 10
    drill_max: int = 25
    timer_warnings_minutes: tuple[int, ...] = (15, 5)
    srs_intervals_days: tuple[float, ...] = field(default=(0, 1, 3, 7, 14, 30))

    def exam(self, ref: str | None) -> Exam | None:
        """Resolve an exam from its key ("saa-c03") or code ("SAA-C03")."""
        if not ref:
            return None
        k = ref.strip().lower()
        if k in self.exams:
            return self.exams[k]
        for e in self.exams.values():
            if e.code.lower() == k:
                return e
        return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("&", "and")).strip()


def load_catalogue(path: Path) -> Catalogue:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    exams: dict[str, Exam] = {}
    for key, e in raw["exams"].items():
        domains = tuple(
            Domain(id=int(d["id"]), name=d["name"], weight=float(d["weight"]), tasks=tuple(d.get("tasks", [])))
            for d in e["domains"]
        )
        total = sum(d.weight for d in domains)
        if abs(total - 100) > 0.01:
            raise ValueError(f"Domain weights for {key} sum to {total}, expected 100")
        exams[key] = Exam(
            key=key,
            name=e["name"],
            short_name=e.get("short_name", e["name"]),
            code=e["code"],
            question_count=int(e["question_count"]),
            time_limit_minutes=int(e["time_limit_minutes"]),
            passing_score=int(e["passing_score"]),
            estimated_raw_cut_pct=float(e.get("estimated_raw_cut_pct", 70)),
            guide_url=e.get("guide_url", ""),
            difficulty_blend={k: float(v) for k, v in e.get("difficulty_blend", {}).items()},
            domains=domains,
        )
    practice = raw.get("practice", {}) or {}
    return Catalogue(
        exams=exams,
        difficulties=raw.get("difficulties", {k: k for k in DIFFICULTIES}),
        drill_min=int(practice.get("drill_min_questions", 10)),
        drill_max=int(practice.get("drill_max_questions", 25)),
        timer_warnings_minutes=tuple(practice.get("timer_warnings_minutes", [15, 5])),
        srs_intervals_days=tuple(float(x) for x in practice.get("srs_intervals_days", [0, 1, 3, 7, 14, 30])),
    )


@lru_cache
def get_catalogue() -> Catalogue:
    return load_catalogue(get_settings().exams_config)
