# clockquotes

A clean, minute-keyed dataset of literary quotes for building "literary clocks" — the trick where at 17:30 your screen shows a passage from a book that mentions "half past five".

Inspired by [tjaap's e-reader clock](https://www.instructables.com/Literary-Clock-Made-From-E-reader/). The bulk of the data comes from [JohannesNE/literature-clock](https://github.com/JohannesNE/literature-clock), with sci-fi/fantasy additions from [brianpipa/literaryclock-scifi-fantasy](https://github.com/brianpipa/literaryclock-scifi-fantasy). This repo's job is to fetch every available source, dedup across them, and emit clean JSON shapes that any consumer (web, embedded, mobile) can pick up.

> **Aside:** when we surveyed the literary-clock landscape, we found ~100 forks of JohannesNE on GitHub, plus several "alternative" datasets — but on inspection, **almost every one of them is just a snapshot or machine translation of JohannesNE**. Genuine independent curation is rare. The two real datasets we found were brianpipa's sci-fi/fantasy set (above) and a Russian-language collection — and that's about it for the open-source landscape.

## Dataset at a glance

After fetching from both sources, dropping explicit-NSFW entries, and deduping across sources:

- **4,676 quotes** across **1,431 of 1,440 minutes** — **99.4% coverage**, 9 minutes empty.
- **17%** of covered minutes have exactly one quote (down from 49.6% with JohannesNE alone).
- **38%** have exactly two, **45%** have three or more, **8%** have more than five.
- Source breakdown: `johannesne` 3,459 entries, `scifi-fantasy` 1,217 entries (~87% of brianpipa's set was novel content not in JohannesNE — the rest were duplicates already in JohannesNE, just spelled or formatted differently).
- Busiest minute: `00:00` with 55 quotes — every literary "midnight" piles up here.
- **Data quality:** 100% of kept entries have title and author populated. The build rejects ~6 malformed rows from upstream (unbalanced quotes / column-count mismatches that would silently corrupt downstream entries) — those are counted under `build_drops.malformed` in `stats.json`.

Live numbers regenerate into [`stats.json`](stats.json) on every build.

## What you get

Every output is regenerated from `sources/` by a single Python script. The build is deterministic and the outputs are committed, so you can also just grab them from raw GitHub URLs without running anything.

| File | Shape | Use |
| --- | --- | --- |
| `quotes.json` | `{ "HH:MM": [ {entry}, ... ] }` | Random-access lookup by current time |
| `quotes.jsonl` | One entry per line, sorted by time/author/title | Streaming, line-by-line ingest, diff-readable |
| `quotes.csv` | Flat table, RFC 4180, same columns as JSONL fields | Spreadsheet browsing, pandas/polars/R, Google Sheets |
| `stats.json` | Coverage, distribution, NSFW counts | Sanity check / dataset metadata |

The `quote` field can contain real `\n` newlines (from `<br>` tags in the upstream). JSON and JSONL handle this transparently; the CSV is RFC 4180 compliant — pandas/polars/Excel parse it correctly, but naive line-by-line tools (`awk -F,`) will mis-split on those rows. Use JSONL for line-streaming.

### Entry schema

```json
{
  "time": "17:30",
  "quote": "It was half-past five before Holmes returned…",
  "annot": "half-past five",
  "prefix": "It was ",
  "suffix": " before Holmes returned…",
  "title": "The Sign of Four",
  "author": "Sir Arthur Conan Doyle",
  "nsfw": "sfw",
  "lang": "en",
  "source": "johannesne"
}
```

- `time` — 24-hour `HH:MM`. Display formatting (12h/24h) is the consumer's call.
- `prefix` / `annot` / `suffix` — the quote split around the time mention so you can render the time bold.
  Both `prefix` and `suffix` are `null` if the time mention couldn't be located in the quote text (rare).
- `nsfw` — `"sfw"` or `"unknown"`. Explicit `"nsfw"` entries are dropped at build time.
- `lang` — currently always `"en"`. Reserved for future multi-language entries.
- `source` — which upstream the entry came from. Use it to filter ("sci-fi clock mode") or just ignore it.

Quote text is **plain text**: HTML `<br>` tags from the upstream are converted to real `\n` newlines, other tags are stripped. Consumers can render newlines however they like.

`quotes.json` keys are the same shape with the `time` field omitted from each entry (it's the key).

## Use it

The outputs at the repo root are committed and stable across builds — sorted, deterministic, diff-clean when upstream updates. Three options:

**Fetch directly** (public, served by GitHub's CDN):

```
https://raw.githubusercontent.com/khalido/clockquotes/main/quotes.json
https://raw.githubusercontent.com/khalido/clockquotes/main/quotes.jsonl
https://raw.githubusercontent.com/khalido/clockquotes/main/quotes.csv
```

**Vendor at build time** (recommended for production — no runtime network dependency):

```bash
curl -o quotes.json https://raw.githubusercontent.com/khalido/clockquotes/main/quotes.json
```

**Or clone and pin** to a commit if you want reproducibility.

### Code examples

Pick a random quote for the current minute. The same recipe works for any consumer — load `quotes.json`, key by `HH:MM`, pick from the array:

```typescript
// TypeScript / Node / browser
const URL = "https://raw.githubusercontent.com/khalido/clockquotes/main/quotes.json";
const quotes: Record<string, Entry[]> = await fetch(URL).then(r => r.json());

function quoteForNow(d = new Date()): Entry | null {
  const key = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  const slot = quotes[key];
  return slot ? slot[Math.floor(Math.random() * slot.length)] : null;
}

const q = quoteForNow();
// Render with time mention bolded — pick the format your UI wants:
const html     = q && `${q.prefix}<time>${q.annot}</time>${q.suffix}`;
const markdown = q && `${q.prefix}**${q.annot}**${q.suffix}`;
const plain    = q && q.quote;
```

```python
# Python
import json, random
from datetime import datetime
from urllib.request import urlopen

URL = "https://raw.githubusercontent.com/khalido/clockquotes/main/quotes.json"
quotes = json.load(urlopen(URL))

def quote_for_now(now=None):
    now = now or datetime.now()
    slot = quotes.get(now.strftime("%H:%M"))
    return random.choice(slot) if slot else None

q = quote_for_now()
if q:
    print(f"{q['prefix']}**{q['annot']}**{q['suffix']}")
    print(f"  — {q['title']}, {q['author']}")
```

```bash
# Shell — pick a random quote at the current minute via jq
NOW=$(date +%H:%M)
curl -s https://raw.githubusercontent.com/khalido/clockquotes/main/quotes.json \
  | jq -r --arg t "$NOW" '.[$t] | .[]? | "\(.quote)\n  — \(.title), \(.author)"' \
  | shuf -n1
```

### Empty-minute fallback

About **0.6% of minutes have no quote** (9 minutes out of 1,440). If you want continuous coverage, fall back to the previous minute, the bucket of "any nearby minute", or a generic quote API. The `stats.json` file lists exactly which minutes are empty.

## Rebuild

Requires [uv](https://docs.astral.sh/uv/). The script declares its Python version with PEP 723 inline metadata — no separate `pyproject.toml`.

```bash
uv run build.py              # fetch upstream and rebuild outputs
uv run build.py --no-fetch   # skip the fetch, use sources/johannesne.csv
uv run build.py --verify     # reload outputs and sanity-check the schema
```

## Sources

### Currently in the build

| Source | Entries | Notes |
| --- | ---: | --- |
| [JohannesNE/literature-clock](https://github.com/JohannesNE/literature-clock) | ~3,600 | The canonical, actively-maintained literary-clock dataset. Pipe-separated CSV. |
| [brianpipa/literaryclock-scifi-fantasy](https://github.com/brianpipa/literaryclock-scifi-fantasy) | ~1,400 | A focused sci-fi/fantasy curation. ~87% of its entries are not in JohannesNE — strong genuine additions. |

### Evaluated and rejected

| Source | Verdict |
| --- | --- |
| [oncherrytrees/literature-clock](https://github.com/oncherrytrees/literature-clock) | 404, repo deleted. |
| [jweissbock/literature-clock](https://github.com/jweissbock/literature-clock) | 404, repo deleted. |
| [jadonn/literary-clock](https://github.com/jadonn/literary-clock) | A ~1,400-entry stripped fork of JohannesNE. No NSFW column, broken quote escaping, all entries already in JohannesNE. |
| [cdmoro/literature-clock](https://github.com/cdmoro/literature-clock) (non-English files) | Initially looked promising — turned out to be machine-translated JohannesNE in 5 languages, not native curation. |
| [ligurio/litclock](https://github.com/ligurio/litclock) (English file) | JohannesNE snapshot. The Russian file (~1,700 native entries) is genuine — worth integrating if/when bilingual support is needed. |
| [elegantalchemist/literaryclock](https://github.com/elegantalchemist/literaryclock) | Self-described as "hugely expanded JohannesNE" — derivative, not independent. |
| ~100 other forks | Stale snapshots of JohannesNE. |

**Bottom line:** the open-source landscape is essentially one well-maintained dataset (JohannesNE) plus brianpipa's sci-fi/fantasy expansion. Genuine independent curation is rare.

### Future candidates

- **[Hugging Face `gutenberg_time`](https://huggingface.co/datasets/community-datasets/gutenberg_time)** — 52K Gutenberg novels machine-annotated for time references at hour granularity. Big and independent of JohannesNE, but would need a custom minute-extraction pass to use here.
- **Songs / movies / plays** — clocks dialog is everywhere in plays (Shakespeare's bell, Beckett's "Time enough"), film, and song lyrics. No structured datasets exist; would be a curation project from scratch.
- **Urdu** (parked starter set in [`sources/urdu.jsonl`](sources/urdu.jsonl)) — 34 hand-curated, Rekhta-verified shers. Not yet wired into the build; held for a future bilingual mode. Classical Urdu poetry uses time-of-day buckets (subah, sham, raat) rather than clock hours, so integration needs a small bucket→HH:MM mapping (documented in [`sources/README.md`](sources/README.md)).

## Related projects

Other literary-clock implementations in the wild — useful for ideas, comparison, and to see how others render the same dataset.

### Web

- **[bigjobby.com/time](https://bigjobby.com/time/)** — clean web version, hand-curated set, simple aesthetic.
- **[literature-clock.jenevoldsen.com](https://literature-clock.jenevoldsen.com/)** — long-running web version by the maintainer of the upstream JohannesNE dataset.
- **[literatureclock.netlify.app](https://literatureclock.netlify.app/)** — fork with multi-language support (e.g. Portuguese-BR) and a few extra UI features.
- **[ticktockquotes.com](https://github.com/0plus1/ticktockquotes.com)** — open-source web version, similar dataset.

### Hardware / physical

- **[Author Clock](https://www.authorandco.com/products/author-clock)** — commercial e-paper desk clock with oak frame, ~13,000 hand-picked quotes. Vol 1 (4.3″) $209, Vol 2 (7.8″) $369. The polished commercial take on the same idea.
- **[Literary Clock Made From E-Reader](https://www.instructables.com/Literary-Clock-Made-From-E-reader/)** — tjaap's original Kindle hack. Patient zero for the genre — most other projects, including this one's pipeline, can be traced back to it.
- **[khalido/pi-pico-clock](https://github.com/khalido/pi-pico-clock)** — Raspberry Pi Pico W + 320×240 LCD. The repo whose data prep work spawned `clockquotes`.

### Origins & discussion

- **[The Guardian — "Christian Marclay's The Clock: a literary version" (Apr 2011)](https://www.theguardian.com/books/booksblog/2011/apr/15/christian-marclay-the-clock-literature)** — the call to action that kicked the whole genre off. The Guardian's books blog, riffing on Marclay's 24-hour film, asked readers to send in literary quotes that mention specific times.
- **[The Guardian — followup (Jul 2013)](https://www.theguardian.com/books/booksblog/2013/jul/03/guardian-literary-clock)** — two years later, what the project had grown into.
- **[Guardian 2011 crowd-sourced list](https://www.theguardian.com/books/table/2011/apr/21/literary-clock)** — the resulting dataset, ~600 entries. Mostly subsumed by JohannesNE.
- **[Hacker News thread (Jun 2024)](https://news.ycombinator.com/item?id=40644960)** — wide-ranging modern discussion, including links to other implementations.

## Build notes

The pipeline is one Python script (`build.py`), no dependencies beyond stdlib + `uv`. On every run it:

1. **Fetches** each source to `sources/<name>.csv` (committed snapshots for reproducibility — pass `--no-fetch` to skip the network round-trip).
2. **Parses** each source with its own CSV config (JohannesNE uses `csv.QUOTE_NONE` because embedded `"` chars break standard quoting; brianpipa uses standard double-quoting).
3. **Cleans** each quote: converts `<br>` tags to real newlines, strips other HTML, normalizes whitespace.
4. **Drops** explicit-NSFW entries (and the `"nswf"` typo) — keeps `"sfw"` and `"unknown"`.
5. **Splits** each quote around its time mention into `prefix` / `annot` / `suffix` for highlighted rendering.
6. **Dedups** across sources using `(time, normalized_quote[:120])` as the key. Normalization strips HTML, whitespace, punctuation, and applies Unicode NFKD — so "Slaughterhouse-Five" and "Slaughterhouse 5", or smart-quoted vs straight-quoted versions of the same passage, collide correctly. Title is intentionally NOT in the key — different sources spell the same book differently ("1984" vs "Nineteen Eighty-Four"), and at the same minute, two different books practically never share the same first 120 normalized characters of quote text.
7. **Tags** each entry with its `source` so downstream consumers can filter (e.g. "sci-fi mode only").
8. **Writes** `quotes.json`, `quotes.jsonl`, `quotes.csv`, and `stats.json`. Coverage, NSFW counts, and per-source breakdowns are reported on stdout and in `stats.json` — easy to track when upstream updates.

### Adding a new source

1. Add a snapshot to `sources/<name>.<ext>` (and to `build.py`'s `SOURCES` dict if you want it auto-fetched).
2. Make sure the loader yields the standard 6-column shape (`time | annot | quote | title | author | nsfw`).
3. Run `uv run build.py` — dedup will handle overlap with existing sources.

If a new source uses non-standard time semantics (like time-of-day buckets — see Urdu in `sources/urdu.jsonl`), you'll also need a bucket→HH:MM mapping step. Not wired up yet.

## License

Code is MIT (see `LICENSE`). The quote excerpts in `sources/` and the generated outputs are short fragments of copyrighted books used as time annotations, mirrored from JohannesNE's public dataset — see that project for sourcing context.
