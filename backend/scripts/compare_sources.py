"""
Compares how many SAP PP/QM jobs Adzuna vs. Jooble actually return for
your real keywords/locations, right now, with your real API keys.

I can't run this myself and hand you a number -- this sandbox has no
network access to api.adzuna.com or jooble.org. This script is the
honest alternative: run it yourself once both keys are in .env, and
you'll have the real comparison in under a minute.

Usage:
    python -m scripts.compare_sources
    python -m scripts.compare_sources --query "SAP PP" --location "Germany"

What it reports, per (keyword, location) combo and in total:
    - How many jobs each source returns
    - How many of Jooble's results are net-new (not already found by
      Adzuna, by job_url) -- this is the number that actually matters:
      total volume alone double-counts jobs both sources already agree on.
"""
import argparse
import logging

import app.env  # noqa: F401
from app.config import KEYWORDS, LOCATIONS
from collectors.adzuna import AdzunaCollector
from collectors.jooble import JoobleCollector

logging.basicConfig(level=logging.WARNING)  # keep requests/urllib3 quiet; we print our own summary


def compare(keywords, locations):
    adzuna = AdzunaCollector()
    jooble = JoobleCollector()

    total_adzuna = 0
    total_jooble = 0
    total_jooble_new = 0
    rows = []

    for kw in keywords:
        for loc in locations:
            try:
                adzuna_jobs = adzuna.fetch_jobs(query=kw, location=loc)
            except Exception as exc:
                print(f"  [adzuna error] {kw!r} / {loc!r}: {exc}")
                adzuna_jobs = []

            try:
                jooble_jobs = jooble.fetch_jobs(query=kw, location=loc)
            except Exception as exc:
                print(f"  [jooble error] {kw!r} / {loc!r}: {exc}")
                jooble_jobs = []

            adzuna_urls = {j["job_url"] for j in adzuna_jobs if j.get("job_url")}
            jooble_new = [j for j in jooble_jobs if j.get("job_url") not in adzuna_urls]

            total_adzuna += len(adzuna_jobs)
            total_jooble += len(jooble_jobs)
            total_jooble_new += len(jooble_new)

            rows.append((kw, loc, len(adzuna_jobs), len(jooble_jobs), len(jooble_new)))

    print()
    print(f"{'Keyword':<28} {'Location':<14} {'Adzuna':>8} {'Jooble':>8} {'Jooble net-new':>15}")
    print("-" * 78)
    for kw, loc, a, j, jn in rows:
        print(f"{kw:<28} {loc:<14} {a:>8} {j:>8} {jn:>15}")
    print("-" * 78)
    print(f"{'TOTAL':<28} {'':<14} {total_adzuna:>8} {total_jooble:>8} {total_jooble_new:>15}")
    print()
    print(f"Jooble contributed {total_jooble_new} net-new postings on top of Adzuna's {total_adzuna}")
    print(f"({total_jooble - total_jooble_new} of Jooble's {total_jooble} were duplicates Adzuna already had)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare Adzuna vs Jooble yield")
    parser.add_argument("--query", default=None, help="Single keyword (default: sweep all of app/config.py's KEYWORDS)")
    parser.add_argument("--location", default=None, help="Single location (default: sweep all of app/config.py's LOCATIONS)")
    args = parser.parse_args()

    kws = [args.query] if args.query else KEYWORDS
    locs = [args.location] if args.location else LOCATIONS
    compare(kws, locs)
