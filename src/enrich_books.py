"""Enrich the clock quote dataset with Open Library metadata.

Idempotent: walks `dist/clock-quotes.json` for unique (title, author) pairs,
looks each up against Open Library, writes `dist/books.json` keyed by Open
Library work ID. On reruns, only fetches pairs that aren't already enriched.
Misses (no confident match) get logged to `dist/books_misses.txt`.

Usage:
    uv run python src/enrich_books.py             # fetch missing
    uv run python src/enrich_books.py --recheck   # force re-fetch every pair
    uv run python src/enrich_books.py --limit 20  # try first N (for testing)
"""

import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
CLOCK_QUOTES = DIST_DIR / "clock-quotes.json"
BOOKS_JSON = DIST_DIR / "books.json"
MISSES_TXT = DIST_DIR / "books_misses.txt"

OL_BASE = "https://openlibrary.org"
COVER_BASE = "https://covers.openlibrary.org/b/id"

# Politeness — OL asks for a real UA so they can contact us if we misbehave.
USER_AGENT = "curios-enrich/0.1 (https://github.com/khalido/curios)"

SEARCH_FIELDS = ",".join([
    "key", "title", "author_name", "cover_i",
    "first_publish_year", "edition_count", "first_sentence",
])
TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)
MAX_WORKERS = 5

# Confidence floor — below this we don't save and log as a miss instead.
# 0.5 keeps "title differs by a subtitle" cases while rejecting partial
# matches like "The Stranger, The Plague (Coles Notes)" against "The Stranger".
CONFIDENCE_BAR = 0.5

# Reject candidates whose title contains study-guide / abridged-edition
# markers — these are derivative works, not the book we want.
_STUDY_GUIDE_RE = re.compile(
    r"\b(coles\s*notes|cliffs\s*notes|cliffsnotes|sparknotes|"
    r"spark\s*notes|study\s+guide|reader'?s?\s+guide|"
    r"condensed|abridged|annotated\s+by)\b",
    re.IGNORECASE,
)


def _tokens(s: str) -> set[str]:
    s = unicodedata.normalize("NFKD", s).lower()
    return set(re.findall(r"\w+", s))


def _author_matches(our_author: str, ol_names: list[str]) -> bool:
    """Any token of length >=3 in our author appears in any candidate name.
    Robust to "Sir Arthur Conan Doyle" vs "Arthur Conan Doyle", to
    "Murakami, Haruki" vs "Haruki Murakami", and to "J.R.R. Tolkien"
    vs "J. R. R. Tolkien"."""
    our_tokens = {t for t in _tokens(our_author) if len(t) >= 3}
    if not our_tokens or not ol_names:
        return False
    blob = " ".join(ol_names).lower()
    return any(t in blob for t in our_tokens)


def _title_score(our_title: str, ol_title: str) -> float:
    a, b = _tokens(our_title), _tokens(ol_title)
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), len(b))


def pick_best(our_title, our_author, candidates):
    """Pick the candidate with author match and highest title overlap.
    Rejects study guides and other derivative works outright. Returns
    (candidate, score) or None if nothing clears CONFIDENCE_BAR."""
    best, best_score = None, 0.0
    for c in candidates:
        cand_title = c.get("title", "")
        if _STUDY_GUIDE_RE.search(cand_title):
            continue
        if not _author_matches(our_author, c.get("author_name", [])):
            continue
        score = _title_score(our_title, cand_title)
        # Tiny bonus (max +0.01) for popular works — breaks ties when
        # OL has split a single book into multiple work records.
        score += min(c.get("edition_count", 0), 50) / 5000
        if score > best_score:
            best, best_score = c, score
    if best is None or best_score < CONFIDENCE_BAR:
        return None
    # Clamp displayed score to [0, 1] — edition-count bonus may push past 1.
    return best, round(min(best_score, 1.0), 3)


def _description_text(work: dict) -> str | None:
    desc = work.get("description")
    if isinstance(desc, dict):
        return desc.get("value")
    return desc


def enrich_one(client: httpx.Client, our_title: str, our_author: str) -> dict | None:
    """Search → pick → fetch work → return enriched book dict, or None on miss."""
    r = client.get(
        f"{OL_BASE}/search.json",
        params={"title": our_title, "author": our_author, "limit": 10, "fields": SEARCH_FIELDS},
    )
    r.raise_for_status()
    candidates = r.json().get("docs", [])

    pick = pick_best(our_title, our_author, candidates)
    if pick is None:
        return None
    cand, score = pick

    work_key = cand["key"]                    # "/works/OL98459W"
    olid = work_key.rsplit("/", 1)[-1]        # "OL98459W"

    r = client.get(f"{OL_BASE}{work_key}.json")
    r.raise_for_status()
    work = r.json()

    cover_id = cand.get("cover_i")
    cover_url = f"{COVER_BASE}/{cover_id}-L.jpg" if cover_id else None

    return {
        "openlibrary_id": olid,
        "openlibrary_url": f"{OL_BASE}/works/{olid}",
        "cover_id": cover_id,
        "cover_url": cover_url,
        # OL's canonical title and author — may differ slightly from the
        # quote's title (which is the dict key in books.json) and author.
        "title": cand.get("title"),
        "author": (cand.get("author_name") or [our_author])[0],
        "first_publish_year": cand.get("first_publish_year"),
        "first_sentence": (cand.get("first_sentence") or [None])[0],
        "description": _description_text(work),
        "subjects": (work.get("subjects") or [])[:8],
        "lookup": {
            # The author we queried with — useful for resolving rare cases
            # where two different books share the same title.
            "from_author": our_author,
            "score": score,
        },
    }


def collect_unique_pairs(path: Path) -> list[tuple[str, str]]:
    """Walk clock-quotes.json, return (title, author) pairs in sorted order."""
    keyed = json.loads(path.read_text(encoding="utf-8"))
    seen: dict[tuple[str, str], None] = {}
    for time in sorted(keyed):
        for e in keyed[time]:
            seen.setdefault((e["title"], e["author"]), None)
    return list(seen)


def main() -> None:
    args = sys.argv[1:]
    recheck = "--recheck" in args
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    books: dict[str, dict] = {}
    if BOOKS_JSON.exists():
        books = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))

    pairs = collect_unique_pairs(CLOCK_QUOTES)
    print(f"Unique (title, author) pairs in clock-quotes.json: {len(pairs):,}")

    # Skip pairs we've already resolved. We dedup on (title, author) — the
    # title alone isn't enough because two books can share a title (e.g.
    # "Honor Among Thieves" by Archer and by Caine).
    seen_pairs = {
        (title, b["lookup"]["from_author"]) for title, b in books.items()
    }
    todo = pairs if recheck else [p for p in pairs if p not in seen_pairs]
    if limit:
        todo = todo[:limit]

    print(f"Already enriched: {len(seen_pairs):,}")
    print(f"To fetch: {len(todo):,}")
    if not todo:
        return

    misses: list[tuple[str, str, str]] = []
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=TIMEOUT, headers=headers) as client:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(enrich_one, client, t, a): (t, a) for t, a in todo}
            for i, fut in enumerate(as_completed(futures), 1):
                t, a = futures[fut]
                try:
                    book = fut.result()
                except Exception as e:
                    misses.append((t, a, f"{type(e).__name__}: {e}"))
                    book = None
                if book is None:
                    if not any(m[:2] == (t, a) for m in misses):
                        misses.append((t, a, "no confident match"))
                else:
                    # Title-keyed. Real collision = same title resolves to a
                    # different OLID → genuinely different books. Otherwise
                    # it's just an author-name spelling variant (J.K. Rowling
                    # vs J. K. Rowling) — both pairs resolve to the same work.
                    existing = books.get(t)
                    if existing and existing["openlibrary_id"] != book["openlibrary_id"]:
                        misses.append((
                            t, a,
                            f"title collision (existing maps to {existing['openlibrary_id']}, this maps to {book['openlibrary_id']})",
                        ))
                    books[t] = book
                if i % 50 == 0 or i == len(todo):
                    print(f"  {i}/{len(todo)} processed, {len(misses)} misses so far")

    BOOKS_JSON.write_text(
        json.dumps(books, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if misses:
        MISSES_TXT.write_text(
            "\n".join(f"{t}\t{a}\t{r}" for t, a, r in misses) + "\n",
            encoding="utf-8",
        )

    print(f"\nbooks.json: {len(books):,} entries")
    print(f"misses logged: {len(misses):,}" + (f" → {MISSES_TXT.name}" if misses else ""))


if __name__ == "__main__":
    main()
