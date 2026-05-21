# build notes

What the pipeline does and how to extend it.

## pipeline

`src/build.py` is the runner. It builds each dataset through its own module
and writes an aggregated `dist/stats.json`. All build code is stdlib-only.

- `src/clock.py` — the clock dataset. Minute-keyed, its own shape.
- `src/flat.py` — the tv/movie/book datasets. Flat arrays, one shared shape.
- `src/common.py` — helpers shared by both (`clean_text`, ratings, `write_json`).

```bash
uv run python src/build.py              # build everything
uv run python src/build.py --only tv    # build one dataset
uv run python src/build.py --no-fetch   # use committed clock sources/
uv run python src/build.py --verify     # check the outputs
```

## clock pipeline (`clock.py`)

On every run it:

1. **Fetches** each upstream CSV to `sources/clock/<name>.csv`. Snapshots are committed for reproducibility — `--no-fetch` skips the network.
2. **Parses** each source with its own CSV config. JohannesNE uses `csv.QUOTE_NONE` because embedded `"` chars break standard quoting; brianpipa uses standard double-quoting.
3. **Cleans** each quote: `<br>` tags become real newlines, other HTML is stripped, whitespace normalized.
4. **Drops** explicit-NSFW entries (and the `"nswf"` typo). The upstream `nsfw` column then maps onto the canonical `rating` field: `sfw→family`, everything surviving else → `unrated`.
5. **Splits** each quote around its time phrase into `before` / `time_phrase` / `after` for highlighted rendering.
6. **Dedups** across sources using `(time, normalized_quote[:120])`. Normalization strips HTML, whitespace, punctuation, and applies Unicode NFKD — so "Slaughterhouse-Five" and "Slaughterhouse 5", or smart- vs straight-quoted versions, collide correctly. Title is intentionally not in the key.
7. **Writes** `dist/clock-quotes.json`.

## flat pipeline (`flat.py`)

The tv/movie/book datasets share one shape — a flat list of entries — so they
share one builder. For a given type it:

1. Reads every `sources/<type>/*.jsonl` snapshot. There is **no fetch step** — scrapers produce snapshots out of band; the build only reads them.
2. Validates each entry against the type's required fields (`TYPES` dict) and a valid `rating`. A malformed entry fails the build loudly with a file:line.
3. Cleans the `quote` text, dedups on normalized quote prefix, sorts, writes `dist/<type>-quotes.json`.

Any field beyond the required set passes through untouched — so per-type
extras (`season`, `episode_title`, `year`, `tags`) need no code change.

## adding a new source

**A clock source** (a CSV in the `time | time_phrase | quote | title | author | nsfw` shape):

1. Add a snapshot under `sources/clock/` and an entry to the `SOURCES` dict in `src/clock.py`.
2. Make sure the loader yields the standard 6-column shape.
3. Run `uv run python src/build.py --only clock` — dedup handles overlap.

A source with non-standard time semantics (time-of-day buckets — see Urdu in
`sources/clock/urdu.jsonl`) also needs a bucket→HH:MM mapping step. Not wired
up yet.

**A tv/comic/movie/book source** — write `src/fetch_<name>.py`, scrape, write
a `sources/<type>/<name>.jsonl` snapshot. The build picks it up automatically;
no change to `flat.py`. Scrapers run under the `scrape` dependency-group
(`uv run --group scrape python src/fetch_<name>.py`).

## known artifacts

**Dangling seconds in clock `after`.** ~53 entries have time-mentions with
seconds — e.g. *"At 10:23:47, the Reactor 2 safety subsystem..."*. Upstream
annotates the time as `10:23`, so the split lands `time_phrase: "10:23"` and
`after: ":47, the Reactor 2..."`. Reconstruction is still correct
(`before + time_phrase + after === quote`), but a consumer wrapping
`time_phrase` in `<mark>` sees the orphan `:47` outside the highlight.
Intentional — the clock minute is what matters for keying. Don't "fix" by
folding `:NN` into `time_phrase` unless a UI consumer asks.
