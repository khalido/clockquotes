# clockquotes — agent guide

A clean, minute-keyed dataset of literary quotes for building [literary clocks](https://www.instructables.com/Literary-Clock-Made-From-E-reader/) — at 17:30, your screen shows a passage from a book that mentions "half past five".

The pitch: anyone should be able to grab one of `quotes.json` / `quotes.jsonl` / `quotes.csv` and wire it into a clock. No accounts, no API, no scraping.

## what's here

- `src/build_quotes.py` — Python module, stdlib only. Fetches upstream sources, dedups, splits each quote around its time phrase, writes the quote outputs.
- `src/enrich_books.py` — companion script. Walks `quotes.jsonl`, looks each unique book up against Open Library, writes `books.json` keyed by title. Uses `httpx`. Idempotent — reruns skip what's already enriched.
- `pyproject.toml` — uv-managed (application mode, not a package). `uv sync` sets up the venv. Python 3.14. One runtime dep: `httpx`.
- `sources/` — committed snapshots of upstream quote data. Build is reproducible offline.
- `quotes.{json,jsonl,csv}` — the quote outputs. Same data, three shapes.
- `books.json` — optional companion. Open Library metadata (covers, descriptions, links) keyed by quote title. ~85% of quote occurrences have an entry.
- `stats.json` — coverage and per-source counts for the quote build. Regenerated on every build.
- `docs/` — internal design notes (sources analysis, build internals, enrichment design, themed-quotes draft). Not user-facing.
- `README.md` — short, user-facing.

## the output schema

```json
{
  "time": "17:30",
  "quote": "It was half-past five before Holmes returned…",
  "before": "It was ",
  "time_phrase": "half-past five",
  "after": " before Holmes returned…",
  "title": "The Sign of Four",
  "author": "Sir Arthur Conan Doyle",
  "nsfw": "sfw",
  "lang": "en",
  "source": "johannesne"
}
```

`before + time_phrase + after` reconstructs the quote — the triple is for highlighted rendering (wrap `time_phrase` in `<mark>` or bold). `before` and `after` are `null` when the time phrase couldn't be located in the quote (rare). `nsfw: "nsfw"` is dropped at build; only `"sfw"` and `"unknown"` are kept.

## build commands

```bash
uv sync                                          # first-time setup
uv run python src/build_quotes.py                # fetch upstream and rebuild
uv run python src/build_quotes.py --no-fetch     # use the committed sources/
uv run python src/build_quotes.py --verify       # sanity-check the outputs
```

The build is deterministic. A no-source-changed run produces a byte-identical diff. Every output is sorted (by time, then author, then title) so diffs are minimal when upstream updates.

## enrichment commands

```bash
uv run python src/enrich_books.py                # fetch missing books from Open Library
uv run python src/enrich_books.py --recheck      # force re-fetch every pair
uv run python src/enrich_books.py --limit 20     # try first N (for testing)
```

Idempotent: subsequent runs only fetch pairs not already in `books.json`. Transient errors recover automatically on rerun. Misses (no confident match) go to `books_misses.txt` (gitignored — working artifact).

Design rationale and future enrichment sources (Hardcover, Wikidata, kid-friendly blurbs, authors): [`docs/enrichment.md`](docs/enrichment.md).

## conventions

- Keep `build_quotes.py` stdlib-only. No runtime dependencies for the core build.
- Enrichment scripts can take deps (`httpx`, eventually an LLM SDK). Add via `uv add`.
- New scripts live alongside the existing ones as `src/<name>.py`. Each is self-contained; copy small helpers between scripts rather than fighting Python's flat-layout import paths.
- Outputs stay deterministic and sorted.
- README is for users — short, direct, no internal narration. Internal design and contributor docs go in `docs/`.
- Voice for any prose written in this repo: short paragraphs, lowercase `##` headings, concrete > abstract, no buzzwords or marketing exclamation marks. Land the take in one sentence, hedges in one sentence, not a paragraph.

## roadmap

Current state: 4,676 quotes across 1,431 minutes (99.4% time coverage). `books.json` enriches 1,491 of 1,870 unique books and covers ~85% of quote occurrences. No half-finished features.

Next moves, in declining order of value-per-effort:

1. **`books_overrides.json` for top unmatched books.** Manual `(title, author) → OLID` for the deep cuts OL search misses. Biggest single gap is Murakami's *Blind Willow, Sleeping Woman* (42 quotes); other top targets named in [`docs/enrichment.md`](docs/enrichment.md). Ten manual entries lifts quote coverage 3–5%, no new tooling.
2. **Authors enrichment.** Mirror `enrich_books.py` shape — walk authors, fetch OL author records, write `authors.json` keyed by author name. Adds bio + photo per author. Same patterns, low risk.
3. **Hardcover.app spike.** Only if a consumer hits the long-tail gap. Modern Goodreads alternative with GraphQL — likely better metadata for contemporary lit than OL. Sign up needed; docs are Cloudflare-walled.
4. **Kid-friendly blurbs via LLM.** Defer until you've used the data and felt the description gap. ~$3 one-time on a cheap model, grounded on OL description + sample quotes from the book to constrain hallucination.
5. **`book_id`-on-quote linkage refactor.** Bake OLID into each quote entry at build time. Cleaner consumer API, removes the title-as-key brittleness (one real collision today: *Honor Among Thieves*). Do when a consumer asks.

Longer-term direction: more **types** of quote datasets in this repo — movie quotes, themed/topical (science, philosophy, art), maybe songs and plays. Sketched in [`docs/themed-quotes.md`](docs/themed-quotes.md). When that lands, the repo gets a refactor — likely one shared `sources/`, separate output triples per dataset (the clock keeps `quotes.*`; movies become `movie-quotes.*`; themed becomes `themed.*`). Flagged here so an agent thinking about file layout doesn't pre-commit to a clock-only structure.

Other parked literary-clock candidates (Russian, Urdu, Hugging Face `gutenberg_time`): see [`docs/sources.md`](docs/sources.md).

## related references

- [`docs/sources.md`](docs/sources.md) — full provenance, evaluated-and-rejected sources, future candidates.
- [`docs/build-notes.md`](docs/build-notes.md) — pipeline internals, how to add a new source.
- [`docs/enrichment.md`](docs/enrichment.md) — book metadata enrichment (Open Library), design decisions, future sources (Hardcover, Wikidata, kid blurbs, authors).
- [`docs/themed-quotes.md`](docs/themed-quotes.md) — design draft for the non-clock quote dataset.
- [`sources/README.md`](sources/README.md) — what's in `sources/` and how each file is fetched.
