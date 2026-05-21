# Themed quotes — design note

> **Status: mostly superseded.** The non-clock datasets are built — see the
> `flat.py` pipeline (`tv`, `movie`, `book` types) and `AGENTS.md`. The repo
> was renamed `curios`; outputs are per-type JSON files in `dist/`, not the
> grouped `themed.json` sketched below. This file is kept for the design
> reasoning that still holds — notably "why not merge into clock-quotes" and
> the verification/curation open questions, which apply to the `book` dataset.

## Idea

A second dataset alongside the literary clock — a general collection of curated quotes from books, movies, science, philosophy, history, art, etc. **Not time-keyed.** Different consumer use case: an "interesting quote" screen on a home dash or kiosk, distinct from the clock screen that consumes `quotes.json`.

Same repo, separate output files. The repo name `clockquotes` will be slightly off-label for this — accepted as a tradeoff for keeping discovery and tooling simple.

## Schema

Each entry is flat (no `before`/`time_phrase`/`after` — those are clock-specific):

```json
{
  "quote": "Imagination is more important than knowledge.",
  "author": "Albert Einstein",
  "source_title": "What Life Means to Einstein (Saturday Evening Post interview)",
  "source_type": "interview",
  "category": "science",
  "tags": ["imagination", "creativity"],
  "lang": "en",
  "source_url": "https://..."
}
```

- `source_type` — `book` | `movie` | `show` | `speech` | `interview` | `song` | `essay` | `poem` | other.
- `category` — high-level grouping (`science`, `philosophy`, `history`, `movies`, `art`, …). The list is open; pick one per entry.
- `tags` — free-form, optional, for finer filtering.
- `source_url` — recommended for verification. Especially important if any entries are LLM-suggested — same hallucination risk we saw with Urdu poetry.

NSFW / safety field: probably not needed if entries are hand-curated. Add if/when we automate.

## Sources

Handcrafted to start. Same `sources/` folder, same flat-naming convention as the existing literary-clock sources:

```
sources/themed-movies.jsonl
sources/themed-science.jsonl
sources/themed-philosophy.jsonl
...
```

(Or one file per category — `sources/themed-<category>.jsonl` — kept as JSONL because hand-edits are easier line-by-line than navigating big arrays.)

If we ever automate, candidates worth checking:
- Goodreads quote pages (per author, per book) — scrape-friendly
- IMDb "memorable quotes" pages — similar
- Wikiquote — public domain, well-structured per topic
- LLM-suggested then human-verified, like the Urdu agent did

## Outputs

```
themed.json    # grouped: { "science": [...], "philosophy": [...], ... }
themed.jsonl   # flat, one entry per line, sorted by category/author
themed.csv     # flat table for spreadsheet browsing
themed-stats.json
```

Same triplet pattern as the literary clock outputs. The JSON is grouped-by-category for easy browsing; the JSONL/CSV are flat for streaming/import.

## Build integration

Extend `build.py` with a second pipeline (`process_themed()`) and a second writer (`write_themed_outputs()`). Don't fork into a separate script — single entry point keeps the build maintainable. The literary-clock and themed pipelines share zero data; only the runner.

```bash
uv run build.py            # builds both
uv run build.py --clock-only
uv run build.py --themed-only
```

## Why not merge into the existing `quotes.json`?

Considered. Rejected because:
- Different keying — `quotes.json` is keyed `HH:MM → entries`. Themed quotes don't have a time. A unified shape would require either inventing fake times for themed entries or making `time` optional and breaking lookup semantics.
- Different consumer — chota-bot's clock screen wants minute-precise lookup with random pick. The themed screen wants category-filtered random pick. Different access patterns.
- Different schema — `before`/`time_phrase`/`after` are dead weight on themed entries.

Two clean datasets > one muddled one.

## Open questions

Decide before building:

1. **One `themed.json` or per-category files like `themed-science.json`?** — leaning one combined file with category grouping, but consumers fetching only one category would prefer per-category files (smaller, faster). Could do both.
2. **Tag taxonomy** — open-ended free-form, or a controlled vocabulary? Free-form is easier to grow; controlled is easier to filter cleanly.
3. **Verification policy** — every entry needs `source_url`? Or just LLM-curated ones? Or none?
4. **Should the literary clock entries also appear in `themed.json` with `category: "literary"`?** — leaning no (different schemas), but a "literary" mode on the themed screen would be nice. Could be done by re-indexing `clock-quotes.json` at consumer time without duplicating data.
5. **Curation cadence** — append-as-I-think-of-them in a single `themed.jsonl`, or themed sprints (a week of "philosophy curation", then a week of "science")?

## Related work in this repo

- The Urdu source (`sources/urdu.jsonl`) already follows the JSONL-with-source-URL hand-curation pattern this would borrow.
- The Urdu agent's discipline around verification (Rekhta URLs, "verified" vs "unverified" tagging) is the model to follow if we ever LLM-curate any of this.
