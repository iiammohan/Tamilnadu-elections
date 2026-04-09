"""
Parse Form 26 affidavit PDFs to extract financial and criminal-record data.

Usage
-----
    python -m scripts.parse_affidavits               # parse all downloaded PDFs
    python -m scripts.parse_affidavits --max 10       # first 10 only
    python -m scripts.parse_affidavits --file TN2026_AC001_01.pdf

Reads from  ``public/affidavits/<candidate_id>.pdf``
Updates     ``public/data/tn2026_all_candidates.json`` in-place with financial fields.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from scripts.config import (
    AFFIDAVITS_DIR,
    CANDIDATES_ALL_JSON,
    CANDIDATES_BY_AC_JSON,
    DATA_OUT_DIR,
    setup_logging,
)

log = setup_logging("parse_affidavits")

# Lazy-import pdfplumber so the rest of the pipeline works even if it's missing
try:
    import pdfplumber  # type: ignore
except ImportError:
    pdfplumber = None  # type: ignore
    log.warning("pdfplumber not installed — PDF parsing will be unavailable")


# ── Currency helpers ───────────────────────────────────────────────────────────

_CURRENCY_RE = re.compile(
    r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE
)
_NUMBER_RE = re.compile(r"([\d,]+(?:\.\d{1,2})?)")


def _parse_currency(text: str) -> Optional[float]:
    """Extract the first currency amount from *text*."""
    m = _CURRENCY_RE.search(text)
    if m:
        return float(m.group(1).replace(",", ""))
    m = _NUMBER_RE.search(text)
    if m:
        val = float(m.group(1).replace(",", ""))
        if val > 0:
            return val
    return None


# ── Section detection ──────────────────────────────────────────────────────────

# Keywords in Form 26 sections (English).  We scan full page text for these.
_SECTION_MARKERS = {
    "movable": [
        "movable assets",
        "movable asset",
        "details of movable",
    ],
    "immovable": [
        "immovable assets",
        "immovable asset",
        "details of immovable",
    ],
    "liabilities": [
        "liabilities",
        "total liabilities",
    ],
    "income": [
        "total income",
        "income as per last",
        "income tax return",
        "last itr",
    ],
    "criminal": [
        "criminal cases",
        "pending criminal",
        "fir no",
        "case no",
        "ipc section",
        "criminal antecedents",
    ],
}


def _detect_sections(full_text: str) -> dict[str, list[str]]:
    """
    Identify which broad sections are present and return
    the relevant text chunks for each.
    """
    lower = full_text.lower()
    sections: dict[str, list[str]] = {}
    for key, markers in _SECTION_MARKERS.items():
        for marker in markers:
            idx = lower.find(marker)
            if idx != -1:
                # Take a window of text around the marker
                start = max(0, idx - 200)
                end = min(len(full_text), idx + 2000)
                sections.setdefault(key, []).append(full_text[start:end])
    return sections


# ── PDF parsing ────────────────────────────────────────────────────────────────


def parse_affidavit_pdf(pdf_path: Path) -> dict[str, Any]:
    """
    Extract financial and criminal-record fields from a Form 26 PDF.

    Returns a dict that can be merged into the candidate record.
    """
    result: dict[str, Any] = {
        "assets_movable": None,
        "assets_immovable": None,
        "assets_total": None,
        "liabilities_total": None,
        "income_last_itr": None,
        "has_criminal_cases": False,
        "pending_cases_count": 0,
        "conviction_cases_count": 0,
        "major_ipc_sections": [],
    }

    if pdfplumber is None:
        log.error("pdfplumber not installed — cannot parse %s", pdf_path.name)
        return result

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
    except Exception as exc:
        log.warning("Failed to read PDF %s: %s", pdf_path.name, exc)
        return result

    if not full_text.strip():
        log.warning("Empty text from %s", pdf_path.name)
        return result

    sections = _detect_sections(full_text)

    # ── Movable assets ─────────────────────────────────────────────────────
    for chunk in sections.get("movable", []):
        total_match = re.search(
            r"total\s*(?:value\s*(?:of\s*)?)?(?:movable\s*)?(?:assets?\s*)?[:\-]?\s*"
            r"(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
            chunk, re.IGNORECASE,
        )
        if total_match:
            result["assets_movable"] = float(total_match.group(1).replace(",", ""))
            break
        # Fallback: last currency amount in the chunk
        amounts = _CURRENCY_RE.findall(chunk)
        if amounts:
            result["assets_movable"] = float(amounts[-1].replace(",", ""))
            break

    # ── Immovable assets ───────────────────────────────────────────────────
    for chunk in sections.get("immovable", []):
        total_match = re.search(
            r"total\s*(?:value\s*(?:of\s*)?)?(?:immovable\s*)?(?:assets?\s*)?[:\-]?\s*"
            r"(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
            chunk, re.IGNORECASE,
        )
        if total_match:
            result["assets_immovable"] = float(total_match.group(1).replace(",", ""))
            break
        amounts = _CURRENCY_RE.findall(chunk)
        if amounts:
            result["assets_immovable"] = float(amounts[-1].replace(",", ""))
            break

    # ── Total assets ───────────────────────────────────────────────────────
    if result["assets_movable"] is not None and result["assets_immovable"] is not None:
        result["assets_total"] = result["assets_movable"] + result["assets_immovable"]

    # ── Liabilities ────────────────────────────────────────────────────────
    for chunk in sections.get("liabilities", []):
        val = _parse_currency(chunk)
        if val is not None:
            result["liabilities_total"] = val
            break

    # ── Income ─────────────────────────────────────────────────────────────
    for chunk in sections.get("income", []):
        val = _parse_currency(chunk)
        if val is not None:
            result["income_last_itr"] = val
            break

    # ── Criminal cases ─────────────────────────────────────────────────────
    if sections.get("criminal"):
        result["has_criminal_cases"] = True
        full_criminal = " ".join(sections["criminal"])
        lower_criminal = full_criminal.lower()

        # Count FIR/case numbers
        fir_count = len(re.findall(r"fir\s*no", lower_criminal, re.I))
        case_count = len(re.findall(r"case\s*no", lower_criminal, re.I))
        result["pending_cases_count"] = max(fir_count, case_count, 1)

        # Check for "no criminal cases" / "nil"
        if re.search(r"(no\s+criminal|nil|not\s+applicable)", lower_criminal, re.I):
            result["has_criminal_cases"] = False
            result["pending_cases_count"] = 0

        # Extract IPC sections
        ipc_matches = re.findall(
            r"(?:section|sec\.?|u/s)\s*([\d]+(?:\s*/\s*[\d]+)*)\s*(?:of\s*)?(?:ipc|bnss|bharatiya)",
            full_criminal, re.IGNORECASE,
        )
        # Also match standalone "IPC 302" or "IPC-420"
        ipc_matches += re.findall(
            r"ipc\s*[-:]?\s*([\d]+(?:\s*/\s*[\d]+)*)",
            full_criminal, re.IGNORECASE,
        )
        result["major_ipc_sections"] = sorted(set(
            m.strip() for m in ipc_matches if m.strip()
        ))

    return result


# ── Batch processing ───────────────────────────────────────────────────────────


def parse_all_affidavits(
    max_parse: int | None = None,
    single_file: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Parse all downloaded PDFs and return a mapping of candidate_id → parsed data.
    """
    results: dict[str, dict[str, Any]] = {}

    if single_file:
        path = AFFIDAVITS_DIR / single_file
        if not path.exists():
            log.error("File not found: %s", path)
            return results
        cid = path.stem
        results[cid] = parse_affidavit_pdf(path)
        log.info("Parsed %s", single_file)
        return results

    pdfs = sorted(AFFIDAVITS_DIR.glob("*.pdf"))
    if not pdfs:
        log.warning("No PDFs found in %s", AFFIDAVITS_DIR)
        return results

    parsed = 0
    for pdf_path in pdfs:
        if max_parse and parsed >= max_parse:
            break
        cid = pdf_path.stem
        data = parse_affidavit_pdf(pdf_path)
        results[cid] = data
        parsed += 1

    log.info("Parsed %d PDF affidavits", parsed)
    return results


def merge_parsed_data(parsed: dict[str, dict[str, Any]]) -> None:
    """
    Merge parsed affidavit data back into the all-candidates JSON.
    """
    if not CANDIDATES_ALL_JSON.exists():
        log.error("Candidate JSON not found: %s", CANDIDATES_ALL_JSON)
        return

    with open(CANDIDATES_ALL_JSON, encoding="utf-8") as f:
        candidates = json.load(f)

    updated = 0
    for cand in candidates:
        cid = cand.get("candidate_id")
        if cid in parsed:
            cand.update(parsed[cid])
            updated += 1

    with open(CANDIDATES_ALL_JSON, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)
    log.info("Merged affidavit data for %d candidates", updated)

    # Also rebuild the by-constituency JSON
    from collections import defaultdict
    by_ac: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        by_ac[str(c["ac_no"])].append(c)
    with open(CANDIDATES_BY_AC_JSON, "w", encoding="utf-8") as f:
        json.dump(by_ac, f, ensure_ascii=False, indent=2)
    log.info("Rebuilt %s", CANDIDATES_BY_AC_JSON)


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse affidavit PDFs")
    parser.add_argument(
        "--max", type=int, default=None,
        help="Max PDFs to parse (for development)",
    )
    parser.add_argument(
        "--file", type=str, default=None,
        help="Parse a single PDF file by name",
    )
    args = parser.parse_args()

    parsed = parse_all_affidavits(max_parse=args.max, single_file=args.file)
    if parsed:
        merge_parsed_data(parsed)


if __name__ == "__main__":
    main()
