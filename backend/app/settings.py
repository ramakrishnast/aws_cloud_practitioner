"""Runtime settings loaded from environment variables / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(REPO_ROOT / ".env")


def _path(env: str, default: Path) -> Path:
    raw = os.getenv(env)
    p = Path(raw).expanduser() if raw else default
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    return p


@dataclass(frozen=True)
class Settings:
    exams_config: Path
    question_bank: Path
    data_dir: Path
    database_url: str
    frontend_dist: Path
    watch_folder: bool
    anthropic_api_key: str | None
    model: str
    verifier_model: str
    effort: str
    use_fallbacks: bool

    @property
    def generator_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    data_dir = _path("CLOUDCERT_DATA_DIR", REPO_ROOT / "data")
    db_url = os.getenv("CLOUDCERT_DATABASE_URL") or f"sqlite:///{data_dir / 'cloudcert.db'}"
    model = os.getenv("CLOUDCERT_MODEL", "claude-opus-5-5")
    return Settings(
        exams_config=_path("CLOUDCERT_EXAMS_CONFIG", REPO_ROOT / "config" / "exams.yaml"),
        question_bank=_path("CLOUDCERT_QUESTION_BANK", REPO_ROOT / "question_bank"),
        data_dir=data_dir,
        database_url=db_url,
        frontend_dist=_path("CLOUDCERT_FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"),
        watch_folder=os.getenv("CLOUDCERT_WATCH", "1") not in ("0", "false", "no"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        model=model,
        verifier_model=os.getenv("CLOUDCERT_VERIFIER_MODEL", model),
        effort=os.getenv("CLOUDCERT_EFFORT", "high"),
        use_fallbacks=os.getenv("CLOUDCERT_FALLBACKS", "1") not in ("0", "false", "no"),
    )
