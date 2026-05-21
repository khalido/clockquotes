# sources/

Raw upstream data, committed as snapshots — one folder per dataset. The build
reads only these snapshots, so it's reproducible offline and survives an
upstream disappearing.

`sources/` holds data only — `*.csv` and `*.jsonl` snapshots. The scrapers
that produced them live in `src/fetch_*.py`; a scraper and its snapshot are a
pair, the scraper kept so the scrape is reproducible.

## clock/

| File | Rows | Used by build? | Description |
| --- | ---: | --- | --- |
| [`johannesne.csv`](clock/johannesne.csv) | ~3,600 | ✅ | Pipe-separated CSV: `time \| time_phrase \| quote \| title \| author \| nsfw`. From [JohannesNE/literature-clock](https://github.com/JohannesNE/literature-clock) — the canonical, actively-maintained literary-clock dataset. |
| [`scifi-fantasy.csv`](clock/scifi-fantasy.csv) | ~1,400 | ✅ | Same shape as JohannesNE, RFC 4180 quoted. From [brianpipa/literaryclock-scifi-fantasy](https://github.com/brianpipa/literaryclock-scifi-fantasy) — a focused sci-fi/fantasy curation. ~87% not in JohannesNE. |
| [`urdu.jsonl`](clock/urdu.jsonl) | 34 | ❌ parked | Hand-curated Urdu shers, verified against [Rekhta.org](https://www.rekhta.org/). Bucketed by time-of-day. Not yet wired into the build — see the mapping below. |
| [`guardian-2011.csv`](clock/guardian-2011.csv) | 935 | ❌ historical | The original Guardian 2011 crowd-sourced list. Long since absorbed by JohannesNE; preserved in case the Guardian takes the [page](https://www.theguardian.com/books/table/2011/apr/21/literary-clock) down. Produced by `src/fetch_guardian.py`. |

`johannesne.csv` and `scifi-fantasy.csv` are re-fetched on every `uv run python src/build.py` (by `clock.py` itself, not a scraper). Pass `--no-fetch` to use the committed snapshots.

## tv/

| File | Rows | Used by build? | Description |
| --- | ---: | --- | --- |
| [`bluey.jsonl`](tv/bluey.jsonl) | 89 | ✅ | Bluey quotes scraped from [cubbyathome.com](https://www.cubbyathome.com/bluey-quotes-80049565). All `rating: "kids"`. Produced by `src/fetch_bluey.py`. |

The build picks up every `*.jsonl` in `tv/` automatically. A `movie/` and `book/` folder follow the same pattern — create them when you add the first source for those datasets.

## comic/

| File | Rows | Used by build? | Description |
| --- | ---: | --- | --- |
| [`calvin-hobbes.jsonl`](comic/calvin-hobbes.jsonl) | 122 | ✅ | Calvin and Hobbes quotes scraped from [TVTropes](https://tvtropes.org/pmwiki/pmwiki.php/Quotes/CalvinAndHobbes). All `rating: "family"`. Produced by `src/fetch_calvin_hobbes.py` (TVTropes is bot-blocked, so it fetches via the Wayback Machine). |

## urdu bucket → HH:MM mapping

The Urdu source uses time-of-day buckets, not minute precision — classical
Urdu poetry references times-of-day ("subah", "sham", "raat"), not clock
numbers. When wired into the build, each bucket maps to a canonical minute:

| Bucket | Time | Notes |
| --- | --- | --- |
| `sahar` | 05:15 | pre-dawn |
| `subah` | 06:30 | morning |
| `dopahar` | 12:00 | midday |
| `sham` | 18:00 | evening |
| `raat` | 21:00 | night |

Each entry carries both the mapped `time` and the original `bucket` so the
mapping stays re-tunable without re-editing entries.

## adding a new source

See [`docs/build-notes.md`](../docs/build-notes.md#adding-a-new-source) and the
"adding a source" section of [`AGENTS.md`](../AGENTS.md).
