# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas>=2", "lxml", "html5lib"]
# ///
"""Scrape the Guardian's 2011 crowd-sourced literary clock table.

This is a historical / reference snapshot, not a live source for the build
pipeline. JohannesNE/literature-clock has long since absorbed and improved on
this list (~600 entries here vs ~3,600 there). We keep a copy in `sources/`
so the dataset is preserved if the Guardian ever takes the page down.

Run:
    uv run src/fetch_guardian.py
"""

import pandas as pd

from common import SOURCES_DIR

URL = "https://www.theguardian.com/books/table/2011/apr/21/literary-clock"
OUT = SOURCES_DIR / "clock" / "guardian-2011.csv"


def main() -> None:
    print(f"Fetching {URL}")
    tables = pd.read_html(URL)
    df = tables[0]

    df = df.rename(
        columns={
            "Time of quote": "time",
            "Quote": "quote",
            "Title of book": "title",
            "Author": "author",
        }
    )
    if "Your username" in df.columns:
        df = df.drop(columns=["Your username"])

    df = df.dropna(subset=["quote"]).copy()
    # Times come in as e.g. "07:10:00h" — normalize to HH:MM
    df["time"] = (
        df["time"].astype(str).str.replace(".", ":", regex=False).str.slice(0, 5)
    )
    df = df.sort_values("time").reset_index(drop=True)

    df.to_csv(OUT, index=False)
    print(f"  wrote {OUT.name}: {len(df):,} rows, {OUT.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()
