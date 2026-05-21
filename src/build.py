"""Build runner — produces every quote dataset in `dist/`.

Each quote type has its own pipeline:
  - clock  → dist/clock-quotes.json   (minute-keyed, src/clock.py)
  - tv     → dist/tv-quotes.json      (flat, src/flat.py)
  - movie  → dist/movie-quotes.json   (flat, src/flat.py)
  - book   → dist/book-quotes.json    (flat, src/flat.py)
  - comic  → dist/comic-quotes.json   (flat, src/flat.py)

`dist/stats.json` aggregates coverage and counts for every type.

Usage:
    uv run python src/build.py                 # build everything
    uv run python src/build.py --only tv       # build one type
    uv run python src/build.py --no-fetch      # use committed clock sources/
    uv run python src/build.py --verify        # sanity-check the outputs
"""

import json
import sys

import clock
import flat
from common import DIST_DIR, write_json

FLAT_TYPES = list(flat.TYPES)  # tv, movie, book, comic, puzzle, fact
ALL_TYPES = ["clock", *FLAT_TYPES]


def main() -> None:
    args = sys.argv[1:]

    only = None
    if "--only" in args:
        i = args.index("--only")
        try:
            only = args[i + 1]
        except IndexError:
            sys.exit("--only needs a type: " + ", ".join(ALL_TYPES))
        if only not in ALL_TYPES:
            sys.exit(f"unknown type {only!r} — known: {', '.join(ALL_TYPES)}")
    types = [only] if only else ALL_TYPES

    if "--verify" in args:
        for t in types:
            if t == "clock":
                clock.verify()
            else:
                flat.verify(t)
        return

    fetch = "--no-fetch" not in args
    all_stats: dict[str, dict] = {}
    for t in types:
        if t == "clock":
            all_stats["clock"] = clock.build(fetch=fetch)
        else:
            st = flat.build(t)
            if st is not None:
                all_stats[t] = st

    # stats.json always reflects the full set of outputs — merge into any
    # existing file so an `--only` build doesn't drop the other types' stats.
    out = DIST_DIR / "stats.json"
    if out.exists() and only:
        merged = json.loads(out.read_text(encoding="utf-8"))
        merged.update(all_stats)
        all_stats = merged
    write_json(out, all_stats)


if __name__ == "__main__":
    main()
