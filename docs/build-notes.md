# build notes

What the pipeline does and how to extend it.

## pipeline

`src/build_quotes.py` is one Python module, stdlib only. Run via `uv run python src/build_quotes.py`. On every run it:

1. **Fetches** each source to `sources/<name>.csv`. Snapshots are committed for reproducibility — pass `--no-fetch` to skip the network.
2. **Parses** each source with its own CSV config. JohannesNE uses `csv.QUOTE_NONE` because embedded `"` chars break standard quoting; brianpipa uses standard double-quoting.
3. **Cleans** each quote: converts `<br>` tags to real newlines, strips other HTML, normalizes whitespace.
4. **Drops** explicit-NSFW entries (and the `"nswf"` typo). Keeps `"sfw"` and `"unknown"`.
5. **Splits** each quote around its time phrase into `before` / `time_phrase` / `after` for highlighted rendering.
6. **Dedups** across sources using `(time, normalized_quote[:120])` as the key. Normalization strips HTML, whitespace, punctuation, and applies Unicode NFKD — so "Slaughterhouse-Five" and "Slaughterhouse 5", or smart-quoted vs straight-quoted versions of the same passage, collide correctly. Title is intentionally not in the key — different sources spell the same book differently ("1984" vs "Nineteen Eighty-Four"), and at the same minute two different books practically never share the same first 120 normalized characters.
7. **Tags** each entry with its `source` so consumers can filter ("sci-fi mode only").
8. **Writes** `quotes.json`, `quotes.jsonl`, `quotes.csv`, and `stats.json`. Per-source breakdowns land on stdout and in `stats.json`.

## adding a new source

1. Add a snapshot to `sources/<name>.<ext>` and to `build_quotes.py`'s `SOURCES` dict.
2. Make sure the loader yields the standard 6-column shape: `time | time_phrase | quote | title | author | nsfw`.
3. Run `uv run python src/build_quotes.py` — dedup handles overlap with existing sources.

If a new source uses non-standard time semantics (like time-of-day buckets — see Urdu in `sources/urdu.jsonl`), you'll also need a bucket→HH:MM mapping step. Not wired up yet.

## known artifacts

**Dangling seconds in `after`.** ~53 entries (1.13%) have time-mentions with seconds — e.g. *"At 10:23:47, the Reactor 2 safety subsystem..."*. Upstream annotates the time as `10:23` (HH:MM), so our split lands `time_phrase: "10:23"` and `after: ":47, the Reactor 2..."`. Reconstruction is correct (`before + time_phrase + after === quote`), but a consumer wrapping `time_phrase` in `<mark>` will see the orphan `:47` outside the highlight. Intentional — the clock minute is what matters for keying, and the seconds read naturally as quote prose. Don't "fix" by folding `:NN` into `time_phrase` unless a UI consumer specifically asks.
