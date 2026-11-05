"""Question-text normalization used for deduplication."""
from __future__ import annotations

import hashlib
import re
import unicodedata


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Two questions whose text differs only in case, punctuation, quotes, or
    spacing normalize to the same string and are treated as the same question.
    """
    s = unicodedata.normalize("NFKC", text or "").lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def text_hash(text: str) -> str:
    return hashlib.sha1(normalize_text(text).encode("utf-8")).hexdigest()
