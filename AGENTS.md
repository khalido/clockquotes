# curios — agent guide

A curated library of content datasets for dashboards, kiosks, and daily briefs. Each dataset is a plain JSON file in `dist/` — anyone can grab one and wire it in. No accounts, no API.

The built datasets today are all quote types (clock, tv, comic, with movie/book planned). The project scope is broader — puzzles, facts, and trivia are planned (see roadmap); the name `curios` reflects that, not just quotes. The clock dataset is the original and most mature.

## the datasets

| Dataset | Output | Shape | State |
| --- | --- | --- | --- |
| clock | `dist/clock-quotes.json` | `{ "HH:MM": [entry] }` | 4,676 quotes, 99.4% minute coverage |
| tv | `dist/tv-quotes.json` | `[entry]` flat array | 89 quotes (Bluey) |
| comic | `dist/comic-quotes.json` | `[entry]` flat array | 122 quotes (Calvin and Hobbes) |
| movie | `dist/movie-quotes.json` | `[entry]` flat array | no sources yet |
| book | `dist/book-quotes.json` | `[entry]` flat array | no sources yet |
| puzzle | `dist/puzzles.json` | `[entry]` flat array | type built, no sources yet |
| fact | `dist/facts.json` | `[entry]` flat array | type built, no sources yet |

`book` is general, non-time-keyed book quotes — distinct from `clock`, which is literary quotes that happen to mention a time. `dist/books.json` is separate again: Open Library *metadata* enriching the clock dataset, not a quote set.

## layout

All Python lives in `src/` — the build pipeline, the enrichment script, and
the one-off scrapers. `sources/` is pure data: committed upstream snapshots.

```
src/
  build.py        runner — builds every dataset, or one via --only
  clock.py        the clock pipeline (minute-keyed, its own shape)
  flat.py         the tv/comic/movie/book pipeline (flat arrays, shared shape)
  common.py       shared helpers — clean_text, ratings, write_json, paths
  enrich_books.py Open Library enrichment for the clock dataset
  wayback.py      scraper helper — fetch a page via the Wayback Machine
  fetch_*.py      one-off scrapers (fetch_bluey, fetch_calvin_hobbes, ...) —
                  each fetches + parses a source into a sources/<type>/
                  snapshot. Not part of the build; kept so the scrape repeats.
sources/
  clock/          johannesne.csv, scifi-fantasy.csv, guardian-2011.csv, urdu.jsonl
  tv/             bluey.jsonl
  comic/          calvin-hobbes.jsonl
                  (a movie/ and book/ folder get created when first sourced)
dist/             all outputs, plus a README.md documenting each file's schema
docs/             internal design notes, not user-facing
```

`src/` is a flat layout, not a package. Python puts a script's own directory on `sys.path`, so any `src/` module imports its siblings directly — `build.py` does `import clock, flat, common`, and a scraper does `from common import SOURCES_DIR` / `from wayback import fetch_via_wayback`. No packaging needed.

## the schemas

Every entry, every dataset, carries `rating`, `lang`, `source`. Quote datasets (clock/tv/comic/movie/book) also share `quote`.

`rating` is an ordered audience scale — `kids` < `family` < `mature` — plus an off-scale `unrated` (not yet graded; not a danger signal). `kids` is young children, `family` is mixed-age/general/teen (~PG-13), `mature` is adults-only. `RATING_ORDER` in `common.py` is the canonical order; consumers filter by dropping `mature` or allowlisting the low tiers.

**clock** — minute-keyed. `before + time_phrase + after` reconstructs `quote` for highlighted rendering; `before`/`after` are `null` when the time phrase couldn't be located. The upstream `nsfw` column maps in: `sfw→family`, `unknown→unrated`, explicit `nsfw` is dropped at build.

```json
{ "quote": "...", "before": "It was ", "time_phrase": "half-past five",
  "after": " before...", "title": "...", "author": "...",
  "rating": "family", "lang": "en", "source": "johannesne" }
```

**tv** — flat. Required: `quote`, `speaker`, `show`, `rating`, `source`. Optional extras pass through untouched (`season`, `episode_title`, `tags`, `source_url`).

```json
{ "quote": "...", "speaker": "Chilli", "show": "Bluey", "season": 2,
  "episode_title": "Sleepytime", "tags": ["family"], "rating": "kids",
  "lang": "en", "source": "bluey-cubbyathome", "source_url": "https://..." }
```

**comic** — flat. Required: `quote`, `comic`, `rating`, `source`. `speaker` is optional — comic entries are often multi-speaker exchanges, with the speaker labels inline in `quote` (newline-separated); single-speaker quotes set `speaker`. `date` (the strip's publication date, ISO) and `tags` pass through.

```json
{ "quote": "Hobbes: Whatcha doin'?\nCalvin: I'm writing my autobiography.",
  "speaker": null, "comic": "Calvin and Hobbes", "date": "1987-01-05",
  "tags": ["art"], "rating": "family", "lang": "en",
  "source": "calvin-hobbes-tvtropes", "source_url": "https://..." }
```

**movie / book** — flat, same machinery. movie requires `quote, speaker, movie, rating, source`; book requires `quote, author, title, rating, source`.

**puzzle / fact** — flat, same machinery. puzzle requires `question, category, rating, source` (`answer` optional — a consumer shows the question and reveals the answer separately); fact requires `fact, rating, source`.

Entries are flat — no `{meta, payload}` envelope. The shared fields and type-specific fields sit at the same level, which keeps parsing trivial on constrained consumers (Pi Pico etc.); the envelope's only real win — a uniform `type` discriminator — is moot when each `dist/` file is type-homogeneous. Per-type config (required fields, primary text field, output filename, sort key) is the `TYPES` dict in `flat.py`. The full per-file schema with examples is [`dist/README.md`](dist/README.md) — keep that in sync when a schema changes.

## build commands

```bash
uv sync                                    # first-time setup
uv run python src/build.py                 # build every dataset
uv run python src/build.py --only tv       # build one dataset
uv run python src/build.py --no-fetch      # use committed clock sources/
uv run python src/build.py --verify        # sanity-check the outputs
```

Only the clock build fetches from the network (its two upstream CSVs). The tv/comic/movie/book builds only ever read committed `sources/<type>/*.jsonl` snapshots — scraping happens out of band (see below). The build is deterministic: a no-source-changed run produces a byte-identical diff. Every output is sorted.

`dist/stats.json` aggregates per-dataset counts. An `--only` build merges into the existing file rather than dropping the other datasets' stats.

## enrichment commands

```bash
uv run python src/enrich_books.py            # fetch missing books from Open Library
uv run python src/enrich_books.py --recheck  # force re-fetch every pair
uv run python src/enrich_books.py --limit 20 # try first N (for testing)
```

Walks `dist/clock-quotes.json`, looks each unique book up against Open Library, writes `dist/books.json`. Idempotent — reruns skip what's already enriched. Misses go to `dist/books_misses.txt` (gitignored — working artifact). Design notes: [`docs/enrichment.md`](docs/enrichment.md).

## adding a source

**A new clock source** (a CSV in the literary-clock shape): add it to the `SOURCES` dict in `src/clock.py`. See [`docs/build-notes.md`](docs/build-notes.md#adding-a-new-source).

**A new flat source** (tv/comic/movie/book/puzzle/fact, usually a scrape): write a one-off scraper at `src/fetch_<name>.py` that fetches, parses, and writes a `sources/<type>/<name>.jsonl` snapshot (derive the path from `common.SOURCES_DIR`). The build picks up every `*.jsonl` in the type's folder automatically — no code change in `flat.py`. The scraper and its snapshot are a pair: the snapshot is what the build reads and what's committed; the scraper is kept only so the scrape is reproducible.

Scrapers may use dependencies the build can't — they live in the `scrape` dependency-group (`beautifulsoup4`, `lxml`). Install and run with `uv run --group scrape python src/fetch_<name>.py`. Use BeautifulSoup for HTML parsing; these are one-off jobs where ergonomics beat speed. If a site blocks bots (TVTropes is behind a Cloudflare challenge), fetch the page through the Wayback Machine with `fetch_via_wayback()` from `wayback.py` — `src/fetch_calvin_hobbes.py` shows the pattern.

## conventions

- The build core (`build.py`, `clock.py`, `flat.py`, `common.py`) is stdlib-only — it reads committed snapshots, never the network for tv/comic/movie/book. The clock fetch uses `urllib`. Scrapers and `enrich_books.py` may take deps; add via `uv add` (`--group scrape` for scrapers).
- Snapshots in `sources/` are committed so the build reproduces offline.
- Outputs stay deterministic and sorted.
- One output format per dataset: JSON. (No jsonl/csv — a `--csv` flag is a one-function add if a consumer ever needs it.)
- README is for users — short, direct, no internal narration. Internal design goes in `docs/`.
- Voice for prose in this repo: short paragraphs, lowercase `##` headings, concrete > abstract, no buzzwords or marketing exclamation marks. Land the take in one sentence, hedges in one sentence, not a paragraph.

## roadmap

No half-finished features. In declining order of value-per-effort:

1. **More tv/comic/movie/book sources.** The flat pipeline is built and proven on Bluey (tv) and Calvin and Hobbes (comic). Each new source is one scraper + one snapshot. Kids want more quotes — more kids' shows (`rating: "kids"`) is the obvious next move.
2. **Puzzle and fact sources.** The `puzzle` and `fact` types are built into `flat.py` (flat schema, no envelope — see `dist/README.md`); what's left is sources. Curate a proper puzzle source from scratch — `chota-bot`'s handful of puzzles are a stopgap, not worth importing — and a space-facts pool to replace chota's live `bootprint` API. Don't bake selection (by-minute / by-day) into the data — that's a consumer concern.
3. **`books_overrides.json` for top unmatched books.** Manual `(title, author) → OLID` for deep cuts OL search misses. Biggest gap: Murakami's *Blind Willow, Sleeping Woman* (42 quotes). Ten entries lifts clock-quote book coverage 3–5%. See [`docs/enrichment.md`](docs/enrichment.md).
4. **Authors enrichment.** Mirror `enrich_books.py` — walk authors, fetch OL author records, write `authors.json`. Adds bio + photo per author.
5. **Episode numbers for tv.** The Bluey source gives season + episode title but no `SxEy` number. A small title→number map (Bluey episodes are well documented) would let tv entries carry a proper `episode` field.
6. **Kid-friendly blurbs via LLM.** Rewrite OL book descriptions for younger readers, grounded on the OL text + sample quotes. ~$3 one-time on a cheap model. Defer until the description gap actually bites.

## related references

- [`docs/sources.md`](docs/sources.md) — clock-source provenance, evaluated-and-rejected list, future candidates.
- [`docs/build-notes.md`](docs/build-notes.md) — pipeline internals, how to add a source.
- [`docs/enrichment.md`](docs/enrichment.md) — Open Library book enrichment, design decisions.
- [`docs/themed-quotes.md`](docs/themed-quotes.md) — original design draft for the non-clock datasets; mostly superseded now that the flat pipeline is built.
- [`sources/README.md`](sources/README.md) — what's in `sources/` and where each snapshot comes from.
