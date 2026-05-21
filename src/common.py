"""Shared helpers for the quote builds.

Imported by the sibling build modules (`clock.py`, `flat.py`, `build.py`).
Python puts a script's own directory on `sys.path`, so `import common` works
from any script run as `python src/<name>.py` — no packaging needed.
"""

import json
import re
import unicodedata
from pathlib import Path

# src/common.py → repo root is one parent up.
ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"
DIST_DIR = ROOT / "dist"

# Content rating — an ordered audience scale. A consumer filters content to
# its audience either by dropping `mature` (general use — keeps everything
# else) or by allowlisting the low tiers (a kids' toy keeps only `kids`).
#   kids   — young children, unsupervised (Bluey)
#   family — mixed-age audiences; general and teen content (~PG-13, Calvin
#            and Hobbes)
#   mature — adults only; not safe for kids
RATING_ORDER = ["kids", "family", "mature"]
# `unrated` is a valid rating but sits off the scale — not yet graded. It is
# not a danger signal: general use keeps it; a strict consumer may drop it.
RATINGS = set(RATING_ORDER) | {"unrated"}


_BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_INLINE_WS_RE = re.compile(r"[^\S\n]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def clean_text(text: str) -> str:
    """Strip HTML to plain text. <br> variants become real newlines; any other
    tag (<b>, <font>, <time>, junk like <CChen0197>) is dropped but its inner
    text is kept. Runs of inline whitespace are collapsed; newlines preserved.
    """
    text = _BR_TAG_RE.sub("\n", text)
    text = _ANY_TAG_RE.sub("", text)
    text = _INLINE_WS_RE.sub(" ", text)
    return text.strip()


def normalize_for_key(text: str) -> str:
    """Aggressive normalization for dedup. Handles Unicode italic/fancy variants
    (NFKD), smart vs straight quotes, and whitespace placement — all collapse to
    a bare lowercase alphanumeric run.
    """
    text = unicodedata.normalize("NFKD", text)
    return _NON_ALNUM_RE.sub("", text.lower())


def write_json(path: Path, obj) -> None:
    """Write `obj` as pretty UTF-8 JSON with a trailing newline. Deterministic —
    a no-data-changed build produces a byte-identical diff.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
