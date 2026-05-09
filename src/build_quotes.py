"""Take the verified upstream sources and produce the three output files.

Reads from `sources/`, writes `quotes.json`, `quotes.jsonl`, `quotes.csv`,
and `stats.json` at the repo root. Deterministic — a no-source-changed
build produces a byte-identical diff.

Usage:
    uv run python src/build_quotes.py              # fetch + rebuild
    uv run python src/build_quotes.py --no-fetch   # use the committed sources/
    uv run python src/build_quotes.py --verify     # sanity-check the outputs
"""

import csv
import json
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

# src/build_quotes.py → repo root is one parent up.
ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / "sources"

ALL_TIMES = [f"{h:02}:{m:02}" for h in range(24) for m in range(60)]
ALL_TIMES_SET = set(ALL_TIMES)

# Each source declares: where to fetch it, where it lands on disk, and how its
# CSV is shaped. The shape lets us share one loader for all sources.
SOURCES = {
    "johannesne": {
        "url": "https://raw.githubusercontent.com/JohannesNE/literature-clock/master/litclock_annotated.csv",
        "file": SOURCES_DIR / "johannesne.csv",
        "has_header": False,
        "quoting": csv.QUOTE_NONE,
    },
    "scifi-fantasy": {
        "url": "https://raw.githubusercontent.com/brianpipa/literaryclock-scifi-fantasy/master/quote%20to%20image/scifi-fantasy.csv",
        "file": SOURCES_DIR / "scifi-fantasy.csv",
        "has_header": True,
        "quoting": csv.QUOTE_MINIMAL,
    },
}


def fetch_all() -> None:
    SOURCES_DIR.mkdir(exist_ok=True)
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

# Upstream CSV shape — both sources use this column order. Some rows lack
# the trailing nsfw cell; we treat missing as "unknown".
INPUT_COLUMNS = ("time", "time_phrase", "quote", "title", "author", "nsfw")


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
    """Aggressive normalization for dedup. Handles cross-source variation:
    Unicode italic or fancy variants (𝘢𝘭𝘭𝘦𝘨𝘳𝘰 → allegro via NFKD), smart vs
    straight quotes, and whitespace placement (e.g. "2:43:12am" vs "2:43:12
    am" — same content, just different whitespace, both collapse to "24312am").
    """
    text = unicodedata.normalize("NFKD", text)
    text = _NON_ALNUM_RE.sub("", text.lower())
    return text


def dedup_key(time: str, quote: str) -> tuple:
    """Stable dedup key. 120 chars of normalized quote — long enough to be
    distinctive, short enough that small prefix variations don't fragment it.

    Title is intentionally NOT part of the key — different sources spell the
    same book differently ("1Q84" vs "1Q84, Book One", "Slaughterhouse-Five"
    vs "Slaughterhouse 5", "Nineteen Eighty-Four" vs "1984"). At the same
    minute, two different books practically never share the same first 120
    normalized characters of quote text — so quote-prefix alone is enough.
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


def normalize_nsfw(value: str) -> str:
    v = value.lower().strip()
    if v in ("nsfw", "nswf"):  # nswf is a typo in upstream
        return "nsfw"
    if v == "sfw":
        return "sfw"
    return "unknown"


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

            nsfw = normalize_nsfw(nsfw_raw)
            if nsfw == "nsfw":
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
                "nsfw": nsfw,
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


CSV_COLUMNS = [
    "time", "quote", "before", "time_phrase", "after",
    "title", "author", "nsfw", "lang", "source",
]


def write_outputs(by_time, flat) -> None:
    keyed = {t: by_time[t] for t in sorted(by_time)}
    (ROOT / "quotes.json").write_text(
        json.dumps(keyed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    flat_sorted = sorted(flat, key=lambda r: (r["time"], r["author"], r["title"]))
    with (ROOT / "quotes.jsonl").open("w", encoding="utf-8") as f:
        for entry in flat_sorted:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # RFC 4180 CSV — embedded newlines in quote field are properly escaped
    # by csv.writer. Pandas/polars/Excel handle this; naive line-by-line
    # tools (awk -F,) will not. Use JSONL for those.
    with (ROOT / "quotes.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for entry in flat_sorted:
            writer.writerow(entry)


def write_stats(by_time, flat, build_info) -> dict:
    counts = sorted([len(v) for v in by_time.values()], reverse=True)
    covered = set(by_time.keys())
    missing = sorted(ALL_TIMES_SET - covered)

    nsfw_counts: dict[str, int] = defaultdict(int)
    for e in flat:
        nsfw_counts[e["nsfw"]] += 1

    busiest = sorted(
        [(t, len(v)) for t, v in by_time.items()],
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    stats = {
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
        "nsfw_breakdown": dict(nsfw_counts),
        "by_source": build_info["kept_by_source"],
        "build_drops": build_info["drops_by_source"],
        "split_failures": build_info["split_failures"],
        "sources": [
            {"name": name, "url": cfg["url"]} for name, cfg in SOURCES.items()
        ],
    }
    (ROOT / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return stats


def report(stats: dict) -> None:
    print()
    print(f"Entries:    {stats['total_entries']:,}")
    print(f"By source:  {stats['by_source']}")
    print(f"Coverage:   {stats['minutes_covered']}/{stats['minutes_total']} ({stats['coverage_pct']}%)")
    if stats["missing_minutes"]:
        print(f"Missing:    {len(stats['missing_minutes'])} minutes — {stats['missing_minutes']}")
    d = stats["distribution"]
    print(
        f"Per-minute: 1={d['single']}  2={d['two']}  3+={d['three_plus']}  "
        f">5={d['more_than_five']}  max={d['max_per_minute']}"
    )
    print(f"NSFW kept:  {stats['nsfw_breakdown']}")
    print(f"Drops:      {stats['build_drops']}")
    if stats["split_failures"]:
        print(f"Split fails: {stats['split_failures']}")


def verify() -> None:
    keyed = json.loads((ROOT / "quotes.json").read_text(encoding="utf-8"))
    flat = [
        json.loads(line)
        for line in (ROOT / "quotes.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    with (ROOT / "quotes.csv").open(encoding="utf-8", newline="") as f:
        csv_rows = list(csv.DictReader(f))

    keyed_total = sum(len(v) for v in keyed.values())
    if keyed_total != len(flat):
        sys.exit(f"FAIL: quotes.json has {keyed_total} entries, quotes.jsonl has {len(flat)}")
    if len(csv_rows) != len(flat):
        sys.exit(f"FAIL: quotes.csv has {len(csv_rows)} rows, quotes.jsonl has {len(flat)}")

    required = {"quote", "before", "time_phrase", "after", "title", "author", "nsfw", "lang", "source"}
    valid_sources = set(SOURCES)
    for time, entries in keyed.items():
        if not re.match(r"^\d{2}:\d{2}$", time):
            sys.exit(f"FAIL: bad time key {time!r}")
        for e in entries:
            missing = required - e.keys()
            if missing:
                sys.exit(f"FAIL: {time} entry missing keys {missing}")
            if e["source"] not in valid_sources:
                sys.exit(f"FAIL: {time} entry has unknown source {e['source']!r}")
            # before is None iff after is None — both indicate the time
            # phrase couldn't be located in the quote text. Consumers must
            # null-check before string-concatenating.
            if (e["before"] is None) != (e["after"] is None):
                sys.exit(f"FAIL: {time} entry has before/after nullability mismatch")

    print(f"verify ok — {len(keyed)} minutes, {len(flat)} entries (json+jsonl+csv consistent)")


def main() -> None:
    args = sys.argv[1:]
    if "--verify" in args:
        verify()
        return
    if "--no-fetch" not in args:
        fetch_all()
    else:
        for name, cfg in SOURCES.items():
            if not cfg["file"].exists():
                sys.exit(f"--no-fetch given but {cfg['file']} does not exist")

    by_time, flat, info = process()
    write_outputs(by_time, flat)
    stats = write_stats(by_time, flat, info)
    report(stats)


if __name__ == "__main__":
    main()
