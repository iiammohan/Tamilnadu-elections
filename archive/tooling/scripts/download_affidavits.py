"""
Download Form 26 affidavit PDFs for all candidates.

Usage
-----
    python -m scripts.download_affidavits                  # all
    python -m scripts.download_affidavits --max 10         # first 10 only

Reads from ``public/data/tn2026_all_candidates.json`` (output of fetch_candidates).
Downloads to ``public/affidavits/<candidate_id>.pdf``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.config import (
    AFFIDAVITS_DIR,
    CANDIDATES_ALL_JSON,
    setup_logging,
)
from scripts.http_client import build_session, throttled_get

log = setup_logging("download_affidavits")


def load_candidates() -> list[dict[str, Any]]:
    """Load the candidate list from the JSON produced by fetch_candidates."""
    if not CANDIDATES_ALL_JSON.exists():
        log.error("Candidate JSON not found: %s", CANDIDATES_ALL_JSON)
        log.error("Run `python -m scripts.fetch_candidates` first.")
        sys.exit(1)
    with open(CANDIDATES_ALL_JSON, encoding="utf-8") as f:
        return json.load(f)


def download_pdf(session, url: str, dest: Path) -> bool:
    """Download a single PDF file. Returns True on success."""
    if dest.exists():
        log.debug("Already downloaded: %s", dest.name)
        return True
    try:
        resp = throttled_get(session, url, timeout=60)
        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower() and not resp.content[:5] == b"%PDF-":
            log.warning("Not a PDF (%s): %s", content_type, url)
            return False
        dest.write_bytes(resp.content)
        log.info("Downloaded %s (%.1f KB)", dest.name, len(resp.content) / 1024)
        return True
    except Exception as exc:
        log.warning("Failed to download %s: %s", url, exc)
        return False


def download_all_affidavits(max_downloads: int | None = None) -> dict[str, str]:
    """
    Download affidavit PDFs for all candidates that have a URL.

    Returns mapping of candidate_id → local PDF path.
    """
    candidates = load_candidates()
    session = build_session()
    AFFIDAVITS_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}
    downloaded = 0
    skipped = 0

    for cand in candidates:
        if max_downloads and downloaded >= max_downloads:
            break

        url = cand.get("affidavit_pdf_url")
        cid = cand.get("candidate_id", "unknown")
        if not url:
            skipped += 1
            continue

        dest = AFFIDAVITS_DIR / f"{cid}.pdf"
        if download_pdf(session, url, dest):
            results[cid] = str(dest)
            downloaded += 1

    log.info(
        "Downloaded %d PDFs, skipped %d (no URL), total candidates %d",
        downloaded, skipped, len(candidates),
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Download affidavit PDFs")
    parser.add_argument(
        "--max", type=int, default=None,
        help="Max PDFs to download (for development)",
    )
    args = parser.parse_args()
    download_all_affidavits(max_downloads=args.max)


if __name__ == "__main__":
    main()
