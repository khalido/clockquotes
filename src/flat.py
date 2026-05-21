"""Build pipeline for the flat content datasets — everything except the clock.

tv / movie / book quotes, puzzles, and facts all share a shape: a flat list of
entries, hand-curated or scraped into JSONL snapshots under `sources/<type>/`.
This module reads every `*.jsonl` snapshot for a type, validates, dedups,
sorts, and writes the type's `dist/` file as a flat array.

Entries are flat — no `{meta, payload}` envelope. Every type shares the fields
`source`, `rating`, `lang` at the top level; the rest are type-specific. Flat
keeps the data trivial to parse on constrained consumers (Pi Pico etc.).

There is no fetch step — scrapers (`sources/<type>/fetch_*.py`) produce the
snapshots out of band; the build only reads them.

Run via the `build.py` runner, or stand-alone:
    uv run python src/flat.py tv        # build one type
    uv run python src/flat.py --verify tv
"""

import json
import sys
from collections import defaultdict

from common import DIST_DIR, RATINGS, SOURCES_DIR, clean_text, normalize_for_key, write_json

# Per-type config:
#   text     — the entry's primary text field (cleaned, and used for dedup).
#   output   — the dist/ filename. Quote types keep a `-quotes` suffix; puzzles
#              and facts aren't quotes, so they get their own name.
#   required — fields every entry must carry. `source` and `rating` are
#              required for every type; `lang` defaults to "en" if absent.
#   sort     — key tuple for deterministic output ordering.
# Any field beyond `required` passes through untouched, so per-type extras
# (episode, year, answer, image, tags) need no code change here.
TYPES = {
    "tv": {
        "text": "quote",
        "output": "tv-quotes.json",
        "required": ["quote", "speaker", "show", "rating", "source"],
        "sort": ("show", "episode", "speaker", "quote"),
    },
    "movie": {
        "text": "quote",
        "output": "movie-quotes.json",
        "required": ["quote", "speaker", "movie", "rating", "source"],
        "sort": ("movie", "speaker", "quote"),
    },
    "book": {
        "text": "quote",
        "output": "book-quotes.json",
        "required": ["quote", "author", "title", "rating", "source"],
        "sort": ("author", "title", "quote"),
    },
    "comic": {
        "text": "quote",
        "output": "comic-quotes.json",
        # `speaker` is optional — many comic entries are multi-speaker
        # exchanges, with the speaker labels inline in the quote text.
        "required": ["quote", "comic", "rating", "source"],
        "sort": ("comic", "quote"),
    },
    "puzzle": {
        "text": "question",
        "output": "puzzles.json",
        # `answer` is intentionally optional — a consumer can show the question
        # and reveal the answer separately, and some puzzles are open-ended.
        "required": ["question", "category", "rating", "source"],
        "sort": ("category", "question"),
    },
    "fact": {
        "text": "fact",
        "output": "facts.json",
        "required": ["fact", "rating", "source"],
        # `category` is optional for facts (unlike puzzles), so it's not in the
        # sort key — sort on the one field every fact is guaranteed to carry.
        "sort": ("fact",),
    },
}


def _snapshots(type_name: str):
    """Yield the JSONL snapshot files for a type, sorted for determinism."""
    return sorted((SOURCES_DIR / type_name).glob("*.jsonl"))


def process(type_name: str):
    cfg = TYPES[type_name]
    required = cfg["required"]
    text_field = cfg["text"]
    entries: list[dict] = []
    seen: set[str] = set()
    kept_by_source: dict[str, int] = defaultdict(int)
    drops: dict[str, int] = defaultdict(int)

    for snapshot in _snapshots(type_name):
        for lineno, line in enumerate(snapshot.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                sys.exit(f"FAIL: {snapshot.name}:{lineno} is not valid JSON")

            missing = [f for f in required if not raw.get(f)]
            if missing:
                sys.exit(f"FAIL: {snapshot.name}:{lineno} missing {missing}")
            if raw["rating"] not in RATINGS:
                sys.exit(
                    f"FAIL: {snapshot.name}:{lineno} bad rating {raw['rating']!r}"
                )

            raw[text_field] = clean_text(raw[text_field])
            key = normalize_for_key(raw[text_field])[:120]
            if key in seen:
                drops["duplicates"] += 1
                continue
            seen.add(key)

            raw.setdefault("lang", "en")
            entries.append(raw)
            kept_by_source[raw["source"]] += 1

    entries.sort(key=lambda e: tuple(str(e.get(k, "")) for k in cfg["sort"]))
    return entries, dict(kept_by_source), dict(drops)


def stats(type_name: str, entries: list[dict], kept_by_source: dict, drops: dict) -> dict:
    rating_counts: dict[str, int] = defaultdict(int)
    for e in entries:
        rating_counts[e["rating"]] += 1
    return {
        "total_entries": len(entries),
        "by_source": kept_by_source,
        "rating_breakdown": dict(rating_counts),
        "build_drops": drops,
    }


def build(type_name: str) -> dict | None:
    """Build a flat type's `dist/` file. Returns the per-type stats dict, or
    None if the type has no snapshots yet (nothing to build).
    """
    if type_name not in TYPES:
        sys.exit(f"unknown type {type_name!r} — known: {', '.join(TYPES)}")
    if not _snapshots(type_name):
        print(f"{type_name + ':':<11} no sources/{type_name}/*.jsonl — skipped")
        return None

    cfg = TYPES[type_name]
    entries, kept_by_source, drops = process(type_name)
    write_json(DIST_DIR / cfg["output"], entries)
    st = stats(type_name, entries, kept_by_source, drops)
    print(
        f"{type_name + ':':<11} {st['total_entries']:,} entries  "
        f"sources={st['by_source']}  ratings={st['rating_breakdown']}"
    )
    return st


def verify(type_name: str) -> None:
    cfg = TYPES[type_name]
    path = DIST_DIR / cfg["output"]
    if not path.exists():
        print(f"{type_name + ':':<11} no {path.name} — skipped")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        sys.exit(f"FAIL: {path.name} is not a JSON array")
    for i, e in enumerate(data):
        missing = [f for f in cfg["required"] if not e.get(f)]
        if missing:
            sys.exit(f"FAIL: {path.name}[{i}] missing {missing}")
        if e["rating"] not in RATINGS:
            sys.exit(f"FAIL: {path.name}[{i}] bad rating {e['rating']!r}")
    print(f"{type_name} verify ok — {len(data)} entries")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--verify"]
    if not args:
        sys.exit(f"usage: python src/flat.py [--verify] <{'|'.join(TYPES)}>")
    if "--verify" in sys.argv[1:]:
        verify(args[0])
    else:
        build(args[0])
