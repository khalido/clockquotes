# curios

A curated library of content datasets for dashboards, kiosks, and daily briefs. Quote datasets and a puzzle pool today — facts and trivia planned. Plain JSON files — no accounts, no API. Grab a file from [`dist/`](dist/) and wire it in.

Fetch a dataset directly without cloning:

```
https://raw.githubusercontent.com/khalido/curios/refs/heads/main/dist/clock-quotes.json
```

Swap the filename for any built file in the table below.

## the datasets

| Dataset | File | Shape | What it is |
| --- | --- | --- | --- |
| clock | [`dist/clock-quotes.json`](dist/clock-quotes.json) | `{ "HH:MM": [entry, ...] }` | Literary quotes that mention a time of day — for [literary clocks](https://www.instructables.com/Literary-Clock-Made-From-E-reader/). At 17:30 the screen shows a passage that says "half past five". |
| tv | [`dist/tv-quotes.json`](dist/tv-quotes.json) | `[entry, ...]` | Quotes from TV shows, tagged with show, speaker, episode. |
| comic | [`dist/comic-quotes.json`](dist/comic-quotes.json) | `[entry, ...]` | Quotes from comic strips, with speaker and strip date. |
| movie | — | `[entry, ...]` | Movie quotes. Planned, no entries yet. |
| book | — | `[entry, ...]` | General (non-time-keyed) book quotes. Planned, no entries yet. |
| puzzle | — | `[entry, ...]` | Puzzles and riddles, with optional answers. Planned, no entries yet. |
| fact | — | `[entry, ...]` | Short interesting facts. Planned, no entries yet. |

Every dataset also has metadata in [`dist/stats.json`](dist/stats.json) — counts, coverage, per-source breakdowns. The full per-file schema with examples lives in [`dist/README.md`](dist/README.md).

## clock

**4,676 quotes across 1,431 of 1,440 minutes — 99.4% coverage.** 9 minutes empty.

```json
{
  "quote": "It was half-past five before Holmes returned…",
  "before": "It was ",
  "time_phrase": "half-past five",
  "after": " before Holmes returned…",
  "title": "The Sign of Four",
  "author": "Sir Arthur Conan Doyle",
  "rating": "family",
  "lang": "en",
  "source": "johannesne"
}
```

`dist/clock-quotes.json` is keyed `"HH:MM" → [entries]`. Look up the current minute, pick an entry.

- `before` / `time_phrase` / `after` — the quote split around the time mention, in reading order; `before + time_phrase + after` reconstructs `quote`. Wrap `time_phrase` in `<mark>` for highlighted rendering. Both `before` and `after` are `null` when the phrase couldn't be located in the quote (rare) — null-check before concatenating.
- The `quote` field can contain real `\n` newlines (from `<br>` upstream).

## tv

```json
{
  "quote": "Remember, I'll always be here for you, even if you can't see me, because I love you.",
  "speaker": "Chilli",
  "show": "Bluey",
  "season": 2,
  "episode_title": "Sleepytime",
  "tags": ["family"],
  "rating": "kids",
  "lang": "en",
  "source": "bluey-cubbyathome",
  "source_url": "https://www.cubbyathome.com/bluey-quotes-80049565"
}
```

`dist/tv-quotes.json` is a flat array. `season` and `episode_title` are `null` when the source doesn't pin the quote to an episode.

## comic

```json
{
  "quote": "Hobbes: Whatcha doin'?\nCalvin: I'm writing my autobiography.\nHobbes: But you're just six years old.\nCalvin: I've only got one sheet of paper.",
  "speaker": null,
  "comic": "Calvin and Hobbes",
  "date": "1987-01-05",
  "tags": ["art"],
  "rating": "family",
  "lang": "en",
  "source": "calvin-hobbes-tvtropes",
  "source_url": "https://tvtropes.org/pmwiki/pmwiki.php/Quotes/CalvinAndHobbes"
}
```

`dist/comic-quotes.json` is a flat array. Most entries are multi-speaker exchanges — the speaker labels sit inline in `quote` (newline-separated) and `speaker` is `null`; single-speaker quotes set `speaker`. `date` is the strip's publication date, `null` when unknown.

## shared fields

Entries are **flat** — shared fields and type-specific fields sit side by side, with no nested `{ meta, payload }` envelope. That keeps parsing trivial on constrained consumers (a Pi Pico printing a daily brief). Each `dist/` file is type-homogeneous, so the content type is the filename — entries don't repeat it.

Three fields are common to every entry of every dataset:

- `rating` — audience rating, an ordered scale `kids` < `family` < `mature`, plus `unrated`. `kids` is young children (Bluey); `family` covers general and teen content (~PG-13); `mature` is adults-only; `unrated` is not-yet-graded — kept by default, not a danger signal. The usual filter is "drop `mature`"; a kids'-only consumer keeps just `kids`.
- `lang` — language code, currently always `"en"`.
- `source` — which source the entry came from. Useful for filtering.

Quote datasets (clock, tv, comic, movie, book) additionally share a `quote` field. Type-specific fields vary — see [`dist/README.md`](dist/README.md) for each dataset's full schema.

## book enrichment

[`dist/books.json`](dist/books.json) is an optional companion to the clock dataset — Open Library metadata keyed by quote title. Roughly **85% of clock-quote occurrences have an enriched book entry** (covers, descriptions, OL links); the long tail of obscure books doesn't, so fall back gracefully.

```json
{
  "Slaughterhouse-Five": {
    "openlibrary_url": "https://openlibrary.org/works/OL98459W",
    "cover_url": "https://covers.openlibrary.org/b/id/12727001-L.jpg",
    "author": "Kurt Vonnegut",
    "first_publish_year": 1968,
    "first_sentence": "All this happened, more or less.",
    "description": "Slaughterhouse-Five is one of the world's great anti-war books..."
  }
}
```

Lookup is a single dict access: `books[quote.title]`. The cover URL serves the `-L` size — swap for `-S`/`-M` if you want smaller. Not every entry has every field. Design notes: [`docs/enrichment.md`](docs/enrichment.md).

## rebuild

Requires [uv](https://docs.astral.sh/uv/). First-time setup: `uv sync`.

```bash
uv run python src/build.py                 # build every dataset
uv run python src/build.py --only tv       # build one
uv run python src/build.py --no-fetch      # use committed sources/, skip the network
uv run python src/build.py --verify        # check the existing outputs
```

The build is deterministic — a no-source-changed run produces a byte-identical diff.

## sources

Each dataset is built from snapshots committed under [`sources/`](sources/), so the build is reproducible offline.

- clock — [JohannesNE/literature-clock](https://github.com/JohannesNE/literature-clock) (3,459 kept) and [brianpipa/literaryclock-scifi-fantasy](https://github.com/brianpipa/literaryclock-scifi-fantasy) (1,217 kept), deduped across both.
- tv — scraped one page at a time; the Bluey set is from [cubbyathome.com](https://www.cubbyathome.com/bluey-quotes-80049565).
- comic — the Calvin and Hobbes set is from [TVTropes](https://tvtropes.org/pmwiki/pmwiki.php/Quotes/CalvinAndHobbes).

Full provenance and how to add a source: [`sources/README.md`](sources/README.md), [`docs/sources.md`](docs/sources.md), [`docs/build-notes.md`](docs/build-notes.md).

## license

Code is MIT. Quote excerpts are short fragments of copyrighted works used as dataset annotations — see each upstream source for its own sourcing context.
