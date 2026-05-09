# clockquotes

Minute-keyed literary quotes for building [literary clocks](https://www.instructables.com/Literary-Clock-Made-From-E-reader/). At 17:30, your screen shows a passage from a book that mentions "half past five".

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

**4,676 quotes across 1,431 of 1,440 minutes — 99.4% coverage.** 9 minutes empty. Live numbers in [`stats.json`](stats.json).

## get it

| File | Shape | Use |
| --- | --- | --- |
| [`quotes.json`](quotes.json) | `{ "HH:MM": [entry, ...] }` | Lookup by current minute |
| [`quotes.jsonl`](quotes.jsonl) | One entry per line, sorted | Streaming, diff-readable |
| [`quotes.csv`](quotes.csv) | Flat table, RFC 4180 | Spreadsheets, pandas/polars |
| [`books.json`](books.json) | `{ "<title>": {entry} }` keyed by quote title | Cover URLs, descriptions, OL links — `books[quote.title]` |

The `quote` field can contain real `\n` newlines (from `<br>` upstream). JSON and JSONL handle this transparently. The CSV is RFC 4180 — pandas/polars/Excel parse it correctly; naive `awk -F,` will mis-split.

## schema

- `time` — `"HH:MM"` 24-hour. Display formatting (12h/24h) is yours.
- `quote` — full passage, plain text.
- `before` / `time_phrase` / `after` — quote split around the time mention, in reading order. The `time_phrase` covers `"midnight"`, `"half past five"`, `"3:14 a.m."` — anything pointing at the time. `before` and `after` are `null` if the phrase couldn't be located in the quote (rare).
- `nsfw` — `"sfw"` or `"unknown"`. Explicit `"nsfw"` is dropped at build.
- `lang` — currently always `"en"`.
- `source` — which upstream the entry came from. Useful for filtering ("sci-fi mode only").

## book enrichment

`books.json` is the optional companion to `quotes.json` — Open Library metadata keyed by quote title. Roughly **85% of quote occurrences have an enriched book entry** (covers, descriptions, OL links); the long tail of obscure books doesn't, and the consumer should fall back gracefully.

```json
{
  "Slaughterhouse-Five": {
    "openlibrary_id": "OL98459W",
    "openlibrary_url": "https://openlibrary.org/works/OL98459W",
    "cover_url": "https://covers.openlibrary.org/b/id/12727001-L.jpg",
    "title": "Slaughterhouse-Five",
    "author": "Kurt Vonnegut",
    "first_publish_year": 1968,
    "first_sentence": "All this happened, more or less.",
    "description": "Slaughterhouse-Five is one of the world's great anti-war books...",
    "subjects": ["American science fiction", "bombing of Dresden", "..."]
  }
}
```

Lookup is a single dict access: `const book = books[quote.title]`. The cover URL serves the L size; swap `-L.jpg` for `-S.jpg` or `-M.jpg` if you want smaller. Not every entry has every field — null-check before rendering. Design notes and provenance: [`docs/enrichment.md`](docs/enrichment.md).

## rebuild

Requires [uv](https://docs.astral.sh/uv/). First-time setup: `uv sync`.

```bash
uv run python src/build_quotes.py              # fetch upstream and rebuild
uv run python src/build_quotes.py --no-fetch   # use committed snapshots in sources/
uv run python src/build_quotes.py --verify     # check the existing outputs
```

## sources

Two open datasets, deduped across them:

- [JohannesNE/literature-clock](https://github.com/JohannesNE/literature-clock) — 3,459 entries kept. The canonical literary-clock dataset.
- [brianpipa/literaryclock-scifi-fantasy](https://github.com/brianpipa/literaryclock-scifi-fantasy) — 1,217 entries kept. Sci-fi/fantasy, ~87% novel content.

Full provenance, evaluated-and-rejected list, future candidates: [`docs/sources.md`](docs/sources.md). Build pipeline internals: [`docs/build-notes.md`](docs/build-notes.md).

## related

Other literary clocks in the wild:

- [literature-clock.jenevoldsen.com](https://literature-clock.jenevoldsen.com/) — long-running web version by JohannesNE.
- [Author Clock](https://www.authorandco.com/products/author-clock) — commercial e-paper desk clock.
- [The Guardian's 2011 call to action](https://www.theguardian.com/books/booksblog/2011/apr/15/christian-marclay-the-clock-literature) — what kicked the genre off.

## license

Code is MIT. Quote excerpts in `sources/` are short fragments of copyrighted books used as time annotations, mirrored from JohannesNE's public dataset — see that project for sourcing context.
