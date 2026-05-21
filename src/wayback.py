"""Wayback Machine helper for the scrapers.

Some sources block bots — TVTropes sits behind a Cloudflare challenge — so a
scraper fetches the page's archived snapshot instead. A `fetch_*.py` scraper
imports it as a sibling module: `from wayback import fetch_via_wayback`.

Kept separate from `common.py` (the stdlib-only build core) because it takes
an httpx dependency and is used only by the scrapers, never by the build.
"""

import re

import httpx

AVAILABILITY_API = "https://archive.org/wayback/available"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def fetch_via_wayback(url: str) -> str:
    """Fetch `url` through the Wayback Machine, returning the archived HTML.

    Asks the availability API for a snapshot — any snapshot is fine, it returns
    the closest — then fetches it with the `id_` modifier so Wayback serves the
    original page without its injected toolbar. Raises RuntimeError if the page
    has never been archived.
    """
    # The availability API only matches a scheme-less URL.
    bare = url.split("://", 1)[-1]
    resp = httpx.get(AVAILABILITY_API, params={"url": bare}, timeout=30)
    resp.raise_for_status()
    snap = resp.json().get("archived_snapshots", {}).get("closest")
    if not snap or not snap.get("available"):
        raise RuntimeError(f"no Wayback snapshot available for {url}")
    raw = re.sub(r"/web/(\d+)/", r"/web/\1id_/", snap["url"])
    page = httpx.get(raw, headers={"User-Agent": UA}, follow_redirects=True, timeout=60)
    page.raise_for_status()
    return page.text
