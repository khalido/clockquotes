# dist/

Generated datasets — the deliverables. **Don't hand-edit the `.json` files**;
they're rebuilt by `uv run python src/build.py`. Grab one and wire it into a
dashboard, kiosk, or daily brief.

Fetch any built file directly without cloning the repo:

```
https://raw.githubusercontent.com/khalido/curios/main/dist/<filename>
```

## shared fields

Every entry, in every dataset, carries the same three fields — so a consumer
can treat any dataset uniformly:

- `source` — where the entry came from. Useful for filtering.
- `rating` — audience rating, an ordered scale: `kids` < `family` < `mature`,
  plus `unrated`. `kids` = young children (Bluey); `family` = general and teen
  content (~PG-13); `mature` = adults only; `unrated` = not yet graded (kept by
  default, not a danger signal). The usual filter is "drop `mature`"; a
  kids'-only consumer keeps just `kids`.
- `lang` — language code, currently always `"en"`.

Entries are **flat** — no `{meta, payload}` envelope. Shared fields and
type-specific fields sit side by side, so parsing stays trivial on constrained
consumers (Pi Pico and similar).

Each file below is type-homogeneous (`puzzles.json` is all puzzles), so the
content type is the filename — entries don't repeat it.

## clock-quotes.json — built

Literary quotes that mention a time of day, for [literary clocks](https://www.instructables.com/Literary-Clock-Made-From-E-reader/). Keyed `"HH:MM" → [entries]` — look up the current minute, pick an entry.

```json
{
  "17:30": [
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
  ]
}
```

`before + time_phrase + after` reconstructs `quote` — wrap `time_phrase` in
`<mark>` for highlighted rendering. `before`/`after` are `null` when the phrase
couldn't be located (rare). The HH:MM keying is clock-specific; every other
dataset is a flat array.

## tv-quotes.json — built

Quotes from TV shows. Flat array. `season` / `episode_title` are `null` when
the source doesn't pin the quote to an episode.

```json
[
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
]
```

## comic-quotes.json — built

Quotes from comic strips. Flat array. Most entries are multi-speaker exchanges
— the speaker labels are inline in `quote` (newline-separated), and `speaker`
is `null`; a single-speaker quote sets `speaker`. `date` is the strip's
publication date (ISO), `null` when the source doesn't give one.

```json
[
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
]
```

## movie-quotes.json — planned

Movie quotes. Flat array. Same shape as tv, with `movie` and optional `year`
in place of `show`/`season`/`episode_title`.

```json
[
  {
    "quote": "…",
    "speaker": "…",
    "movie": "…",
    "year": 1994,
    "rating": "family",
    "lang": "en",
    "source": "…"
  }
]
```

## book-quotes.json — planned

General (non-time-keyed) book quotes — distinct from `clock-quotes.json`. Flat
array.

```json
[
  {
    "quote": "…",
    "author": "…",
    "title": "…",
    "tags": ["…"],
    "rating": "family",
    "lang": "en",
    "source": "…"
  }
]
```

## puzzles.json — planned

Puzzles and riddles. Flat array. `answer` is **optional** — a consumer can
print the `question` and reveal or look up the `answer` separately.

```json
[
  {
    "question": "A bat and a ball cost $1.10 together. The bat costs $1.00 more than the ball. How much is the ball?",
    "answer": "5 cents",
    "category": "trap",
    "rating": "family",
    "lang": "en",
    "source": "Kahneman CRT"
  }
]
```

## facts.json — planned

Short interesting facts. Flat array. `image` and `category` are optional.

```json
[
  {
    "fact": "A day on Venus is longer than its year — it rotates slower than it orbits the Sun.",
    "category": "space",
    "image": "https://…",
    "rating": "family",
    "lang": "en",
    "source": "…"
  }
]
```

## books.json — built

Not a quote dataset — Open Library **metadata** enriching the books behind the
clock dataset. Keyed by quote title; lookup is `books[quote.title]`. Roughly
85% of clock-quote occurrences have an entry. See [`docs/enrichment.md`](../docs/enrichment.md).

```json
{
  "Slaughterhouse-Five": {
    "openlibrary_url": "https://openlibrary.org/works/OL98459W",
    "cover_url": "https://covers.openlibrary.org/b/id/12727001-L.jpg",
    "author": "Kurt Vonnegut",
    "first_publish_year": 1968,
    "first_sentence": "All this happened, more or less.",
    "description": "…"
  }
}
```

## stats.json — built

Build report — per-dataset counts, coverage, and per-source breakdowns.
Regenerated on every build.
