# enrichment

How we attach book metadata (covers, descriptions, links) to the quote dataset.

## current pipeline

`src/enrich_books.py` walks `dist/clock-quotes.json` for unique (title, author) pairs, looks each up against Open Library, writes `dist/books.json` keyed by the **quote's title** (verbatim).

```bash
uv run python src/enrich_books.py             # fetch missing
uv run python src/enrich_books.py --recheck   # force re-fetch every pair
uv run python src/enrich_books.py --limit 20  # try first N (for testing)
```

Idempotent: rerunning only fetches pairs not already in `dist/books.json`. Misses go to `dist/books_misses.txt`.

## why open library

Free, no API key, no rate-limit drama, generous CORS. Two endpoints (`/search.json`, `/works/<OLID>.json`) plus a deterministic cover URL pattern give us everything we need. AGPL-licensed `openlibrary-client` Python library is a write client for OL contributors — overkill for read-only enrichment. We hit the JSON endpoints with `httpx` directly.

What we save per book:

```json
{
  "openlibrary_id": "OL98459W",
  "openlibrary_url": "https://openlibrary.org/works/OL98459W",
  "cover_id": 12727001,
  "cover_url": "https://covers.openlibrary.org/b/id/12727001-L.jpg",
  "title": "Slaughterhouse-Five",
  "author": "Kurt Vonnegut",
  "first_publish_year": 1968,
  "first_sentence": "All this happened, more or less.",
  "description": "Slaughterhouse-Five is one of the world's great anti-war books...",
  "subjects": [...],
  "lookup": { "from_author": "...", "score": 1.0 }
}
```

## key design decisions

**Title-as-key.** `books["Slaughterhouse-Five"]` is the consumer API. Titles aren't globally unique (one collision in current data: *Honor Among Thieves* — Jeffrey Archer thriller vs Rachel Caine sci-fi), but in practice the collision rate is <0.1%. We last-write-wins on real collisions and log to `dist/books_misses.txt`. Spurious "collisions" from author-name spelling variants (J.K. vs J. K. Rowling) are filtered by checking OLID equality — same OLID = same book.

**Work level only, not editions.** Open Library has Works (the abstract book) and Editions (specific printings). We stay at the Work level — `OLxxxxW`. The cover image we use is a representative edition's cover, returned in the search hit as `cover_i`.

**Confidence bar 0.5.** Below this we don't save and log as a miss. Higher than 0.5 lets through "title differs by a subtitle" cases ("The Sign of Four" vs "The Sign of the Four"). Lower than 0.5 lets through partial matches like "The Stranger, The Plague (Coles Notes)" hijacking "The Stranger".

**Reject derivative works.** A regex filter drops candidates whose title contains "study guide", "Cliffs Notes", "Sparknotes", "Coles Notes", "reader's guide", "condensed", "abridged", or "annotated by". These are derivative works that hijack ranking on canonical titles.

**Accept whatever edition OL ranks first.** When OL has fragmented a single book across many work IDs (e.g. *1984* exists as ~10 separate works), we accept whatever the matcher picks. The book is still the book; we don't try to find a canonical first edition. Spending complexity here doesn't change what consumers see.

## future enrichment sources

**[Hardcover.app API](https://docs.hardcover.app/api/getting-started/)** — modern Goodreads alternative with a documented GraphQL API. Likely better metadata for contemporary books than Open Library, including community ratings, genre tags, series info, and richer descriptions. Free tier with API key. Worth a spike when we want to fill OL's gaps — particularly for the ~330 books OL didn't confidently match. Caveat: their docs page is behind Cloudflare bot challenge so a real spike means signing up and trying it, not browsing API docs.

**Wikipedia / Wikidata** — for canonical works (classics especially). Wikidata book entities cross-link OL, ISBN, Goodreads. Could resolve OL-fragmented works back to a single canonical entity. Higher-quality structured data for famous books, sparser for obscure ones.

**Google Books** — backup for descriptions and covers when OL is sparse. Free tier requires an API key + Google Cloud project (1k req/day shared on the public anon project gets exhausted within hours). Not worth setting up unless OL gaps are biting hard.

**Authors enrichment.** Open Library has author entries (`OLxxxxA`) with bio, birth/death dates, photos. Same script shape as `enrich_books.py` would build an `authors.json`. Useful for an "about the author" UI element. Not built — no clear consumer use case yet.

**Kid-friendly blurbs via LLM.** OL descriptions are publisher marketing copy, written for adult literary readers. Sketched in earlier conversation: rewrite each book's blurb for a 12–14 year old in a family setting using a cheap model (DeepSeek, Haiku) via OpenRouter. Grounded on the OL description + 2–3 of our quotes from that book to constrain hallucination. Estimate: ~$3 one-time cost for the full set. Defer until we've seen what consumers actually want from the data.

**Linkage refactor.** Long term, each clock entry should carry `book_id: "OL98459W"` directly. That removes the title-as-key brittleness, eliminates the *Honor Among Thieves* collision case, and makes book-to-quote a clean foreign-key relationship. Done as a build-time pass after enrichment: `clock.py` reads `dist/books.json`, looks up each quote's OLID by title, bakes it into the entry. Not done yet — wanted to see real enrichment data first.

## current state

After enrichment sweeps: **1,491 / 1,870 unique books matched (~80%), covering ~85% of quote occurrences** — popular titles carry more quotes, so quote-level coverage runs ahead of book-level. Among matches, 87% have a cover, 58% a description, 30% a first sentence. Higher coverage on the top 1k popular books, sparser in the long tail.

Top unmatched books by quote count — candidates for a manual `books_overrides.json`:

- *Blind Willow, Sleeping Woman* — Haruki Murakami (42 quotes)
- *1Q84* — Haruki Murakami (21)
- *A Matter of Honor* — Jeffrey Archer (16)
- *Original Sin* — P.D. James (16)
- *The Voices of Time* — J.G. Ballard (16)

Murakami's translated short story collections are the biggest single category — likely a translation/transliteration mismatch with OL's index. Adding ten override entries here would lift quote coverage by 3–5% with no new tooling.
