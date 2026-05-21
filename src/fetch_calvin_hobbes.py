"""One-off scraper: Calvin and Hobbes quotes from TVTropes.

TVTropes sits behind a Cloudflare bot challenge — a direct fetch 403s — so this
scraper goes through the Wayback Machine (see `wayback.py`) and parses the
archived snapshot. The build (`src/flat.py`) only ever reads the committed
`sources/comic/calvin-hobbes.jsonl` snapshot; this script is kept purely so the
scrape is reproducible.

    uv run --group scrape python src/fetch_calvin_hobbes.py

Page layout: <h2> thematic section headings (Advertising, Art, Authority, ...),
each followed by <div class="indent"> quote blocks. A block is a single quote
or a multi-speaker exchange — speaker labels in <strong>, lines split by <br> —
and ends with an attribution line like `—Calvin and Hobbes, 08 May 1992`. The
section heading becomes the entry's `tags`; the attribution gives the strip
date and, for single-speaker quotes, the speaker.
"""

import datetime as dt
import json
import re
import sys

from bs4 import BeautifulSoup

from common import SOURCES_DIR
from wayback import fetch_via_wayback

PAGE = "https://tvtropes.org/pmwiki/pmwiki.php/Quotes/CalvinAndHobbes"
OUT = SOURCES_DIR / "comic" / "calvin-hobbes.jsonl"

# Attribution — the last line of a quote block, e.g. `—Calvin and Hobbes, 08
# May 1992`. The `who` is a single speaker or an "X and Y" exchange; the
# trailing `, <date>` is optional (some attributions give no date).
ATTR_RE = re.compile(r"^[—–]\s*(.+)$")
ATTR_DATE_RE = re.compile(r"^(.*?),\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})$")
QUOTE_PAIRS = (('"', '"'), ("“", "”"))


def parse_date(text: str) -> str | None:
    """`08 May 1992` -> `1992-05-08`; None if it doesn't parse."""
    try:
        return dt.datetime.strptime(text, "%d %B %Y").date().isoformat()
    except ValueError:
        return None


def strip_outer_quotes(text: str) -> str:
    """Drop one matched pair of wrapping quotes from a single-line quote."""
    if "\n" in text:
        return text
    for lo, hi in QUOTE_PAIRS:
        inner = text[1:-1]
        if len(text) > 1 and text.startswith(lo) and text.endswith(hi):
            if lo not in inner and hi not in inner:
                return inner.strip()
    return text


def parse_block(div, theme: str) -> dict | None:
    """Parse one <div class="indent"> into a comic quote entry, or None.

    The attribution sits in a nested <div class="indent">; it's pulled out
    first so it doesn't bleed into the quote text. A few blocks have no
    attribution at all — those keep `speaker` and `date` null.
    """
    nested = div.find("div", class_="indent")
    attr_text = nested.get_text(" ", strip=True) if nested else None
    if nested:
        nested.extract()

    for br in div.find_all("br"):
        br.replace_with("\n")
    lines = [ln.strip() for ln in div.get_text().split("\n") if ln.strip()]
    if not lines:
        return None

    speaker = None
    date = None
    attr = ATTR_RE.match(attr_text) if attr_text else None
    if attr:
        who = attr.group(1).strip()
        dm = ATTR_DATE_RE.match(who)
        if dm:
            who, date = dm.group(1).strip(), parse_date(dm.group(2))
        # "X and Y" is an exchange — the speaker labels are already inline in
        # the quote text, so leave `speaker` null. A lone name is the speaker.
        if " and " not in who.lower():
            speaker = who

    if not lines:
        return None
    return {
        "quote": strip_outer_quotes("\n".join(lines)),
        "speaker": speaker,
        "comic": "Calvin and Hobbes",
        "date": date,
        "tags": [theme] if theme else [],
        "rating": "family",
        "lang": "en",
        "source": "calvin-hobbes-tvtropes",
        "source_url": PAGE,
    }


def main() -> None:
    print(f"Fetching {PAGE} via the Wayback Machine")
    soup = BeautifulSoup(fetch_via_wayback(PAGE), "lxml")

    art = soup.find("div", id="main-article")
    if art is None:
        sys.exit("FAIL: no #main-article — page layout may have changed")

    entries: list[dict] = []
    theme = ""
    for el in art.find_all(["h2", "div"], recursive=False):
        if el.name == "h2":
            theme = el.get_text(strip=True).lower()
        elif "indent" in (el.get("class") or []):
            entry = parse_block(el, theme)
            if entry:
                entries.append(entry)

    if not entries:
        sys.exit("FAIL: parsed 0 quotes — page layout may have changed")

    with OUT.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} — {len(entries)} quotes")


if __name__ == "__main__":
    main()
