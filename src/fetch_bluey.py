"""One-off scraper: Bluey quotes from cubbyathome.com.

Fetches the live page, parses it with BeautifulSoup, and writes the snapshot
`sources/tv/bluey.jsonl`. The build (`src/flat.py`) only ever reads that
snapshot — this script is kept purely so the scrape is reproducible if the
page changes.

    uv run --group scrape python src/fetch_bluey.py

Page layout: <h3> section headings, each followed by an <ol> of <li> quotes
shaped `"quote text" -Speaker ("Episode Title," Season N)`. The attribution
tail is messy — missing parens/quotes, and some quotes cite "multiple
episodes" with no season — so it's parsed leniently. Episode title and
season are null when the source doesn't give them.
"""

import json
import re
import sys

import httpx
from bs4 import BeautifulSoup

from common import SOURCES_DIR

URL = "https://www.cubbyathome.com/bluey-quotes-80049565"
OUT = SOURCES_DIR / "tv" / "bluey.jsonl"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# The attribution starts at the last ` -`/` –` in the <li>; everything before
# it is the quote. (Quote text uses em-dashes `—`, never a spaced hyphen, so
# this split is safe for this page.)
DASH_RE = re.compile(r"\s+[-–]\s*")


def section_tag(heading: str) -> str:
    """Turn an <h3> like 'Bluey Quotes About Family' into a tag like 'family'."""
    text = heading.lower()
    for drop in ("bluey", "quotes", "about", "that"):
        text = text.replace(drop, "")
    return " ".join(text.split())


def parse_li(text: str, tag: str) -> dict | None:
    """Parse one <li> into a quote entry, or None if it has no attribution."""
    dashes = list(DASH_RE.finditer(text))
    if not dashes:
        return None
    split = dashes[-1]
    quote = text[: split.start()].strip()
    attr = text[split.end() :].strip()

    # Strip one matched pair of outer curly quotes — but only for a single
    # utterance. Multi-line dialogue (“A” “B”) is left intact.
    if quote.startswith("“") and quote.endswith("”") and quote.count("”") == 1:
        quote = quote[1:-1].strip()

    # attr is `Speaker (“Episode Title,” Season N)` with most punctuation
    # optional. Pull each piece out independently so a missing one is just null.
    season_m = re.search(r"Season\s*(\d+)", attr)
    episode_m = re.search(r"“([^”,]+)", attr)
    speaker = re.split(r"[(“]", attr)[0].strip().rstrip(",").strip()

    return {
        "quote": quote,
        "speaker": speaker,
        "show": "Bluey",
        "season": int(season_m.group(1)) if season_m else None,
        "episode_title": episode_m.group(1).strip() if episode_m else None,
        "tags": [tag] if tag else [],
        "rating": "kids",
        "lang": "en",
        "source": "bluey-cubbyathome",
        "source_url": URL,
    }


def main() -> None:
    print(f"Fetching {URL}")
    resp = httpx.get(URL, headers={"User-Agent": UA}, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    entries: list[dict] = []
    skipped: list[str] = []
    for h3 in soup.select("div.Post__html h3"):
        tag = section_tag(h3.get_text(" ", strip=True))
        # The h3 and its quote list live in separate Post__html blocks; the
        # list is the next <ol> in document order.
        ol = h3.find_next("ol")
        if ol is None:
            continue
        for li in ol.find_all("li"):
            text = li.get_text(" ", strip=True)
            entry = parse_li(text, tag)
            if entry:
                entries.append(entry)
            else:
                skipped.append(text)

    if not entries:
        sys.exit("FAIL: parsed 0 quotes — page layout may have changed")

    with OUT.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"wrote {OUT} — {len(entries)} quotes")
    if skipped:
        print(f"skipped {len(skipped)} unparseable <li>:")
        for s in skipped:
            print(f"  {s[:100]}")


if __name__ == "__main__":
    main()
