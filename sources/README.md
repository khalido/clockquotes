# sources/

Raw upstream data, committed as snapshots. Build is reproducible offline, and we have a copy if any source disappears upstream.

| File | Rows | Used by build? | Description |
| --- | ---: | --- | --- |
| [`johannesne.csv`](johannesne.csv) | ~3,600 | ✅ | Pipe-separated CSV: `time \| time_phrase \| quote \| title \| author \| nsfw`. From [JohannesNE/literature-clock](https://github.com/JohannesNE/literature-clock) — the canonical, actively-maintained literary-clock dataset. |
| [`scifi-fantasy.csv`](scifi-fantasy.csv) | ~1,400 | ✅ | Pipe-separated CSV with the same shape as JohannesNE, but RFC 4180 quoted. From [brianpipa/literaryclock-scifi-fantasy](https://github.com/brianpipa/literaryclock-scifi-fantasy) — a focused sci-fi/fantasy curation. ~87% of these entries are not in JohannesNE. |
| [`urdu.jsonl`](urdu.jsonl) | 34 | ❌ parked | Hand-curated Urdu shers, every entry verified against [Rekhta.org](https://www.rekhta.org/). Bucketed by time-of-day (subah / dopahar / sham / raat) and mapped to canonical HH:MM. **Not yet wired into the build** — kept here as a starter set for future bilingual expansion. |
| [`guardian-2011.csv`](guardian-2011.csv) | 935 | ❌ historical | The original Guardian 2011 crowd-sourced list — the data that started the whole genre. CSV with columns `time, quote, title, author`. Long since absorbed and improved on by JohannesNE; preserved in case the Guardian takes the [page](https://www.theguardian.com/books/table/2011/apr/21/literary-clock) down. |
| [`fetch_guardian.py`](fetch_guardian.py) | — | — | One-off scraper that produces `guardian-2011.csv` from the live Guardian page. Run with `uv run sources/fetch_guardian.py`. |

## urdu bucket → HH:MM mapping

The Urdu source uses time-of-day buckets, not minute precision. Classical Urdu poetry doesn't reference clock numbers ("panch baje") — it references times-of-day ("subah", "sham", "raat"). When this source is wired into the build, each bucket maps to a canonical minute:

| Bucket | Time | Notes |
| --- | --- | --- |
| `sahar` | 05:15 | pre-dawn |
| `subah` | 06:30 | morning |
| `dopahar` | 12:00 | midday |
| `sham` | 18:00 | evening |
| `raat` | 21:00 | night |

Each entry in `urdu.jsonl` carries both the mapped `time` and the original `bucket` field so the mapping is re-tunable without re-editing entries.

## re-fetching

- `johannesne.csv` and `scifi-fantasy.csv` are re-fetched on every `uv run python src/build_quotes.py`. Pass `--no-fetch` to use the committed snapshots.
- `guardian-2011.csv` only re-fetches when you explicitly run `uv run sources/fetch_guardian.py`. The Guardian page hasn't changed in over a decade.
- `urdu.jsonl` is hand-curated — never auto-fetched.

## adding a new source

See [`docs/build-notes.md`](../docs/build-notes.md#adding-a-new-source).
