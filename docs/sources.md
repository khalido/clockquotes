# sources

Where the data comes from, what was rejected, what's still on the table.

## in the build

| Source | Entries kept | Notes |
| --- | ---: | --- |
| [JohannesNE/literature-clock](https://github.com/JohannesNE/literature-clock) | 3,459 | The canonical literary-clock dataset, actively maintained. Pipe-separated CSV. |
| [brianpipa/literaryclock-scifi-fantasy](https://github.com/brianpipa/literaryclock-scifi-fantasy) | 1,217 | Sci-fi/fantasy curation. ~87% of entries are not in JohannesNE. |

## evaluated and rejected

Surveyed ~100 forks of JohannesNE on GitHub plus several "alternative" datasets. Almost every one was a snapshot or machine translation of JohannesNE. Genuine independent curation is rare.

| Source | Verdict |
| --- | --- |
| [oncherrytrees/literature-clock](https://github.com/oncherrytrees/literature-clock) | 404, repo deleted. |
| [jweissbock/literature-clock](https://github.com/jweissbock/literature-clock) | 404, repo deleted. |
| [jadonn/literary-clock](https://github.com/jadonn/literary-clock) | ~1,400-entry stripped fork of JohannesNE. No NSFW column, broken quote escaping, all entries already in JohannesNE. |
| [cdmoro/literature-clock](https://github.com/cdmoro/literature-clock) | Machine-translated JohannesNE in 5 languages. Not native curation. |
| [ligurio/litclock](https://github.com/ligurio/litclock) | English file is JohannesNE snapshot. Russian file (~1,700 native entries) is genuine — worth integrating for bilingual support. |
| [elegantalchemist/literaryclock](https://github.com/elegantalchemist/literaryclock) | Self-described "hugely expanded JohannesNE". Derivative. |
| ~100 other forks | Stale snapshots of JohannesNE. |

The open-source landscape is essentially one well-maintained dataset (JohannesNE) plus brianpipa's sci-fi/fantasy expansion. Everything else is downstream of those two.

## future candidates

- **[Hugging Face `gutenberg_time`](https://huggingface.co/datasets/community-datasets/gutenberg_time)** — 52K Gutenberg novels machine-annotated for time references at hour granularity. Big and independent. Needs a custom minute-extraction pass.
- **Songs / movies / plays** — clocks dialog is everywhere in plays (Shakespeare's bell, Beckett's "Time enough"), film, and song lyrics. No structured datasets exist; would be curation from scratch.
- **Urdu** (parked in [`sources/urdu.jsonl`](../sources/urdu.jsonl)) — 34 hand-curated, Rekhta-verified shers. Not yet wired into the build. Classical Urdu poetry uses time-of-day buckets (subah, sham, raat) rather than clock hours, so integration needs a small bucket→HH:MM mapping.
