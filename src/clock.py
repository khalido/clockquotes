"""Literary-clock pipeline — minute-keyed quotes for building literary clocks.

Reads the CSV snapshots in `sources/clock/`, dedups, splits each quote around
its time phrase, writes `dist/clock-quotes.json` (keyed `HH:MM → entries`).
Deterministic — a no-source-changed build produces a byte-identical diff.

Run via the `build.py` runner, or stand-alone:
    uv run python src/clock.py            # fetch + rebuild
    uv run python src/clock.py --no-fetch # use the committed sources/
"""

import csv
import json
import re
import sys
import urllib.request
from collections import defaultdict

from common import (
    DIST_DIR,
    SOURCES_DIR,
    clean_text,
    normalize_for_key,
    write_json,
)

CLOCK_DIR = SOURCES_DIR / "clock"
OUTPUT = DIST_DIR / "clock-quotes.json"

ALL_TIMES = [f"{h:02}:{m:02}" for h in range(24) for m in range(60)]
ALL_TIMES_SET = set(ALL_TIMES)

# Each source declares: where to fetch it, where it lands on disk, and how its
# CSV is shaped. The shape lets us share one loader for all sources.
SOURCES = {
    "johannesne": {
        "url": "https://raw.githubusercontent.com/JohannesNE/literature-clock/master/litclock_annotated.csv",
        "file": CLOCK_DIR / "johannesne.csv",
        "has_header": False,
        "quoting": csv.QUOTE_NONE,
    },
    "scifi-fantasy": {
        "url": "https://raw.githubusercontent.com/brianpipa/literaryclock-scifi-fantasy/master/quote%20to%20image/scifi-fantasy.csv",
        "file": CLOCK_DIR / "scifi-fantasy.csv",
        "has_header": True,
        "quoting": csv.QUOTE_MINIMAL,
    },
}


def fetch_all() -> None:
    CLOCK_DIR.mkdir(parents=True, exist_ok=True)
    for name, cfg in SOURCES.items():
        print(f"Fetching {name}: {cfg['url']}")
        target = cfg["file"]
        # Atomic write — a partial fetch must not overwrite the committed
        # snapshot in place (--no-fetch would silently use the corrupt copy).
        tmp = target.with_suffix(target.suffix + ".tmp")
        urllib.request.urlretrieve(cfg["url"], tmp)
        tmp.replace(target)
        kb = target.stat().st_size / 1024
        print(f"  saved {target.name} ({kb:.0f} KB)")


def load_source(name: str):
    """Yield raw stripped cell lists from a source CSV. Caller validates shape.

    JohannesNE uses raw pipe-split (no quoting). scifi-fantasy uses standard
    CSV double-quoting. Header rows are skipped if present.
    """
    cfg = SOURCES[name]
    with cfg["file"].open(encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="|", quoting=cfg["quoting"])
        if cfg["has_header"]:
            next(reader, None)
        for row in reader:
            yield [c.strip() for c in row]


# Tokens we know how to handle in the upstream nsfw column. "nsfw" and the
# typo "nswf" are recognized so we drop them cleanly; anything else means
# the row is malformed (a quote bled into this cell during CSV parsing).
KNOWN_NSFW_TOKENS = {"", "sfw", "unknown", "nsfw", "nswf"}


def dedup_key(time: str, quote: str) -> tuple:
    """Stable dedup key. 120 chars of normalized quote — long enough to be
    distinctive, short enough that small prefix variations don't fragment it.

    Title is intentionally NOT part of the key — different sources spell the
    same book differently. At the same minute, two different books practically
    never share the same first 120 normalized characters of quote text.
    """
    return (time, normalize_for_key(quote)[:120])


def split_around_phrase(quote: str, time_phrase: str):
    """Split quote into (before, after) around time_phrase.
    Returns (None, None) if time_phrase isn't found in quote."""
    if not time_phrase:
        return None, None
    parts = re.split(re.escape(time_phrase), quote, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None, None
    return parts[0], parts[1]


def rating_from_nsfw(value: str) -> str | None:
    """Map the upstream nsfw column to a canonical rating. `nsfw` rows return
    None — the caller drops them. `sfw` → `family` ("not explicit" is the
    family tier; these aren't vetted specifically for young children).
    Anything else → `unrated`.
    """
    v = value.lower().strip()
    if v in ("nsfw", "nswf"):  # nswf is a typo in upstream
        return None
    if v == "sfw":
        return "family"
    return "unrated"


def process():
    by_time: dict[str, list[dict]] = defaultdict(list)
    flat: list[dict] = []
    seen: set[tuple] = set()

    drops_by_source = {name: defaultdict(int) for name in SOURCES}
    kept_by_source = {name: 0 for name in SOURCES}
    split_failures = 0

    for source_name in SOURCES:
        for cells in load_source(source_name):
            drops = drops_by_source[source_name]

            # Allow 5 or 6 columns — older rows lack the nsfw flag.
            # Anything else is malformed (e.g. brianpipa's CSV has rows
            # where the nsfw cell starts with `"unknown` but never closes,
            # so csv greedily consumes the next row(s) into one giant cell).
            if not (5 <= len(cells) <= 6):
                drops["malformed"] += 1
                continue
            cells = cells + [""] * (6 - len(cells))
            time, phrase_raw, quote_raw, title_raw, author_raw, nsfw_raw = cells

            # Reject rows whose nsfw cell isn't a recognized token — almost
            # always a sign the CSV parser merged adjacent rows.
            nsfw_lower = nsfw_raw.lower()
            if "\n" in nsfw_lower or nsfw_lower not in KNOWN_NSFW_TOKENS:
                drops["malformed"] += 1
                continue

            if time not in ALL_TIMES_SET:
                drops["invalid_time"] += 1
                continue

            rating = rating_from_nsfw(nsfw_raw)
            if rating is None:
                drops["dropped_nsfw"] += 1
                continue

            quote = clean_text(quote_raw)
            title = clean_text(title_raw)
            author = clean_text(author_raw)
            time_phrase = clean_text(phrase_raw)

            key = dedup_key(time, quote)
            if key in seen:
                drops["duplicates"] += 1
                continue
            seen.add(key)

            before, after = split_around_phrase(quote, time_phrase)
            if before is None:
                split_failures += 1

            # Field order: full quote first, then the before/phrase/after triple
            # in reading order so consumers can render them with a single concat.
            entry = {
                "quote": quote,
                "before": before,
                "time_phrase": time_phrase,
                "after": after,
                "title": title,
                "author": author,
                "rating": rating,
                "lang": "en",
                "source": source_name,
            }
            by_time[time].append(entry)
            flat.append({"time": time, **entry})
            kept_by_source[source_name] += 1

    return by_time, flat, {
        "kept_by_source": kept_by_source,
        "drops_by_source": {k: dict(v) for k, v in drops_by_source.items()},
        "split_failures": split_failures,
    }


def stats(by_time, flat, build_info) -> dict:
    counts = sorted([len(v) for v in by_time.values()], reverse=True)
    covered = set(by_time.keys())
    missing = sorted(ALL_TIMES_SET - covered)

    rating_counts: dict[str, int] = defaultdict(int)
    for e in flat:
        rating_counts[e["rating"]] += 1

    busiest = sorted(
        [(t, len(v)) for t, v in by_time.items()],
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    return {
        "total_entries": len(flat),
        "minutes_covered": len(covered),
        "minutes_total": len(ALL_TIMES),
        "coverage_pct": round(len(covered) / len(ALL_TIMES) * 100, 2),
        "missing_minutes": missing,
        "distribution": {
            "single": sum(1 for c in counts if c == 1),
            "two": sum(1 for c in counts if c == 2),
            "three_plus": sum(1 for c in counts if c >= 3),
            "more_than_five": sum(1 for c in counts if c > 5),
            "max_per_minute": counts[0] if counts else 0,
            "busiest_minutes": [{"time": t, "count": c} for t, c in busiest],
        },
        "rating_breakdown": dict(rating_counts),
        "by_source": build_info["kept_by_source"],
        "build_drops": build_info["drops_by_source"],
        "split_failures": build_info["split_failures"],
        "sources": [
            {"name": name, "url": cfg["url"]} for name, cfg in SOURCES.items()
        ],
    }


def report(st: dict) -> None:
    print(f"clock:      {st['total_entries']:,} entries")
    print(f"  by source:  {st['by_source']}")
    print(
        f"  coverage:   {st['minutes_covered']}/{st['minutes_total']} "
        f"({st['coverage_pct']}%)"
    )
    if st["missing_minutes"]:
        print(f"  missing:    {len(st['missing_minutes'])} minutes")
    d = st["distribution"]
    print(
        f"  per-minute: 1={d['single']}  2={d['two']}  3+={d['three_plus']}  "
        f">5={d['more_than_five']}  max={d['max_per_minute']}"
    )
    print(f"  ratings:    {st['rating_breakdown']}")
    print(f"  drops:      {st['build_drops']}")
    if st["split_failures"]:
        print(f"  split fails: {st['split_failures']}")


def build(fetch: bool = True) -> dict:
    """Build `dist/clock-quotes.json`. Returns the per-type stats dict."""
    if fetch:
        fetch_all()
    else:
        for name, cfg in SOURCES.items():
            if not cfg["file"].exists():
                sys.exit(f"--no-fetch given but {cfg['file']} does not exist")

    by_time, flat, info = process()
    keyed = {t: by_time[t] for t in sorted(by_time)}
    write_json(OUTPUT, keyed)
    st = stats(by_time, flat, info)
    report(st)
    return st


def verify() -> None:
    keyed = json.loads(OUTPUT.read_text(encoding="utf-8"))
    required = {
        "quote", "before", "time_phrase", "after",
        "title", "author", "rating", "lang", "source",
    }
    valid_sources = set(SOURCES)
    total = 0
    for time, entries in keyed.items():
        if not re.match(r"^\d{2}:\d{2}$", time):
            sys.exit(f"FAIL: bad time key {time!r}")
        for e in entries:
            total += 1
            missing = required - e.keys()
            if missing:
                sys.exit(f"FAIL: {time} entry missing keys {missing}")
            if e["source"] not in valid_sources:
                sys.exit(f"FAIL: {time} entry has unknown source {e['source']!r}")
            if e["rating"] not in ("family", "unrated"):
                sys.exit(f"FAIL: {time} entry has bad rating {e['rating']!r}")
            # before is None iff after is None — both indicate the time
            # phrase couldn't be located. Consumers must null-check.
            if (e["before"] is None) != (e["after"] is None):
                sys.exit(f"FAIL: {time} entry has before/after nullability mismatch")
    print(f"clock verify ok — {len(keyed)} minutes, {total} entries")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--verify" in args:
        verify()
    else:
        build(fetch="--no-fetch" not in args)
