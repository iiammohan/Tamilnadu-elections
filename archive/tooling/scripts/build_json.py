"""
Build final JSON output files from candidate data.

This is the "glue" script that orchestrates the full pipeline:
  1. Scrape candidates  (fetch_candidates)
  2. Download affidavits (download_affidavits)
  3. Parse affidavits    (parse_affidavits)
  4. Export final JSON    (this module)

Usage
-----
    python -m scripts.build_json                     # scrape + export (no affidavits)
    python -m scripts.build_json --with-affidavits   # include PDF download/parse
    python -m scripts.build_json --skip-scrape       # rebuild JSON from existing data
    python -m scripts.build_json --skip-affidavits   # force skip PDF download/parse
    python -m scripts.build_json --dev               # dev mode: 5 pages, 10 PDFs
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Any

from scripts.config import (
    CANDIDATES_ALL_JSON,
    CANDIDATES_BY_AC_JSON,
    DATA_OUT_DIR,
    TOTAL_ACS,
    setup_logging,
)

log = setup_logging("build_json")


def build_summary_stats(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate statistics for the overview dashboard."""
    total = len(candidates)
    by_party: dict[str, int] = defaultdict(int)
    by_district: dict[str, int] = defaultdict(int)
    acs_covered: set[int] = set()

    total_assets = 0.0
    assets_count = 0
    criminal_count = 0
    gender_counts = {"M": 0, "F": 0, "O": 0, "Unknown": 0}

    for c in candidates:
        by_party[c.get("party_code", "Others")] += 1
        by_district[c.get("district", "Unknown")] += 1
        acs_covered.add(c.get("ac_no", 0))

        if c.get("assets_total") is not None:
            total_assets += c["assets_total"]
            assets_count += 1

        if c.get("has_criminal_cases"):
            criminal_count += 1

        g = c.get("gender") or "Unknown"
        gender_counts[g] = gender_counts.get(g, 0) + 1

    avg_assets = total_assets / assets_count if assets_count else 0

    return {
        "total_candidates": total,
        "constituencies_covered": len(acs_covered),
        "total_constituencies": TOTAL_ACS,
        "candidates_by_party": dict(sorted(by_party.items(), key=lambda x: -x[1])),
        "candidates_by_district": dict(sorted(by_district.items(), key=lambda x: -x[1])),
        "gender_distribution": gender_counts,
        "avg_assets_total": round(avg_assets, 2),
        "candidates_with_criminal_cases": criminal_count,
        "criminal_percentage": round(criminal_count / total * 100, 1) if total else 0,
    }


def export_json() -> None:
    """Read the all-candidates JSON and produce final output files."""
    if not CANDIDATES_ALL_JSON.exists():
        log.error("No candidates JSON found at %s", CANDIDATES_ALL_JSON)
        sys.exit(1)

    with open(CANDIDATES_ALL_JSON, encoding="utf-8") as f:
        candidates = json.load(f)

    log.info("Loaded %d candidates from %s", len(candidates), CANDIDATES_ALL_JSON)

    # Rebuild by-constituency grouping
    by_ac: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        by_ac[str(c["ac_no"])].append(c)

    with open(CANDIDATES_BY_AC_JSON, "w", encoding="utf-8") as f:
        json.dump(by_ac, f, ensure_ascii=False, indent=2)
    log.info("Wrote %s (%d ACs)", CANDIDATES_BY_AC_JSON, len(by_ac))

    # Summary stats
    stats = build_summary_stats(candidates)
    stats_path = DATA_OUT_DIR / "tn2026_summary.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    log.info("Wrote %s", stats_path)

    # ── Top-lists for quick dashboard consumption ──────────────────────────
    # Richest candidates
    with_assets = [c for c in candidates if c.get("assets_total") is not None]
    richest = sorted(with_assets, key=lambda c: c["assets_total"], reverse=True)[:20]
    richest_path = DATA_OUT_DIR / "tn2026_richest.json"
    with open(richest_path, "w", encoding="utf-8") as f:
        json.dump(richest, f, ensure_ascii=False, indent=2)
    log.info("Wrote %s (%d entries)", richest_path, len(richest))

    # Candidates with criminal cases
    criminal = [c for c in candidates if c.get("has_criminal_cases")]
    criminal = sorted(criminal, key=lambda c: c.get("pending_cases_count", 0), reverse=True)
    criminal_path = DATA_OUT_DIR / "tn2026_criminal.json"
    with open(criminal_path, "w", encoding="utf-8") as f:
        json.dump(criminal, f, ensure_ascii=False, indent=2)
    log.info("Wrote %s (%d entries)", criminal_path, len(criminal))


def run_full_pipeline(
    skip_scrape: bool = False,
    skip_affidavits: bool = True,
    dev_mode: bool = False,
) -> None:
    """Run the full ETL pipeline end-to-end."""
    if not skip_scrape:
        from scripts.fetch_candidates import scrape_all_candidates, validate_and_export

        max_pages = 5 if dev_mode else None
        raw = scrape_all_candidates(max_pages=max_pages)
        if not raw:
            log.error("No candidates scraped.")
            sys.exit(1)
        validate_and_export(raw)

    if not skip_affidavits:
        from scripts.download_affidavits import download_all_affidavits
        from scripts.parse_affidavits import merge_parsed_data, parse_all_affidavits

        max_dl = 10 if dev_mode else None
        download_all_affidavits(max_downloads=max_dl)
        parsed = parse_all_affidavits(max_parse=max_dl)
        if parsed:
            merge_parsed_data(parsed)

    export_json()
    log.info("Pipeline complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final JSON output")
    parser.add_argument("--skip-scrape", action="store_true")
    parser.add_argument("--skip-affidavits", action="store_true")
    parser.add_argument(
        "--with-affidavits",
        action="store_true",
        help="Download and parse affidavits (opt-in)",
    )
    parser.add_argument("--dev", action="store_true", help="Dev mode (limited scraping)")
    args = parser.parse_args()

    # Affidavit processing is disabled by default unless explicitly enabled.
    effective_skip_affidavits = args.skip_affidavits or (not args.with_affidavits)

    run_full_pipeline(
        skip_scrape=args.skip_scrape,
        skip_affidavits=effective_skip_affidavits,
        dev_mode=args.dev,
    )


if __name__ == "__main__":
    main()
