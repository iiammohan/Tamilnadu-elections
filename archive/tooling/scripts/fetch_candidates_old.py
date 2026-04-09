"""
Scrape candidate data from the ECI Affidavit portal for TN Assembly 2026.

Usage
-----
    python -m scripts.fetch_candidates          # scrape all pages
    python -m scripts.fetch_candidates --max 5  # first 5 pages only (dev)

Output: ``public/data/tn2026_all_candidates.json``  (flat list)
        ``public/data/tn2026_by_constituency.json``  (keyed by AC number)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from typing import Any, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup, Tag

from scripts.config import (
    CANDIDATES_ALL_JSON,
    CANDIDATES_BY_AC_JSON,
    DATA_OUT_DIR,
    ECI_AFFIDAVIT_BASE_URL,
    ECI_AFFIDAVIT_LIST_URL,
    STATE_NAME,
    TOTAL_ACS,
    setup_logging,
)
from scripts.http_client import build_session, throttled_get, warm_session
from scripts.models import CandidateModel
from scripts.party_map import normalise_party

log = setup_logging("fetch_candidates")

# ── ECI affidavit portal helpers ───────────────────────────────────────────────

# The ECI portal paginates candidates.  The listing page is at:
#   https://affidavit.eci.gov.in/CandidateDetails
# with GET params:  StateCode=S22  (Tamil Nadu code on ECI)
#   + page=1,2,3...
# Each page shows ~10 candidates with columns:
#   S.No, Candidate Name, Party, Constituency Name, Constituency No.,
#   View Affidavit (link to PDF)
# We also get the candidate photo from the detail page.

ECI_STATE_CODE = "S22"          # Tamil Nadu on ECI portal
ECI_ELECTION_TYPE = "AE"        # Assembly Election
ROWS_PER_PAGE = 10

# Regex to extract AC number from constituency string like "1 - Gummidipoondi"
_AC_NO_RE = re.compile(r"^(\d{1,3})\s*[-–]")


def _parse_ac_no(raw: str) -> Optional[int]:
    """Extract the numeric AC number from strings like '1 - Gummidipoondi'."""
    m = _AC_NO_RE.match(raw.strip())
    if m:
        return int(m.group(1))
    return None


def _parse_ac_name(raw: str) -> str:
    """Extract constituency name from '1 - Gummidipoondi' → 'Gummidipoondi'."""
    parts = re.split(r"\s*[-–]\s*", raw.strip(), maxsplit=1)
    return parts[1].strip().title() if len(parts) > 1 else raw.strip().title()


def _build_listing_url(page: int) -> str:
    """Build the URL for a specific page of the ECI candidate listing."""
    params = {
        "StateCode": ECI_STATE_CODE,
        "ElectionType": ECI_ELECTION_TYPE,
        "page": page,
    }
    return f"{ECI_AFFIDAVIT_LIST_URL}?{urlencode(params)}"


# ── Scraping logic ─────────────────────────────────────────────────────────────


def _scrape_listing_page(
    session, page: int
) -> tuple[list[dict[str, Any]], bool]:
    """
    Scrape one page of the ECI candidate listing.

    Returns (rows, has_next_page).
    Each row is a raw dict before Pydantic validation.
    """
    url = _build_listing_url(page)
    log.info("Fetching page %d: %s", page, url)
    try:
        resp = throttled_get(session, url)
    except Exception as exc:
        log.error("Failed to fetch page %d: %s", page, exc)
        return [], False

    soup = BeautifulSoup(resp.text, "lxml")

    # Find the main data table — ECI portal typically uses <table class="table">
    table = soup.find("table", class_="table")
    if not table:
        # Try any table with candidate data
        tables = soup.find_all("table")
        table = tables[0] if tables else None
    if not table:
        log.warning("No table found on page %d", page)
        return [], False

    rows: list[dict[str, Any]] = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        row = _parse_table_row(tds)
        if row:
            rows.append(row)

    # Pagination: check for a "next" link
    has_next = _has_next_page(soup, page)
    log.info("Page %d: found %d candidates, has_next=%s", page, len(rows), has_next)
    return rows, has_next


def _parse_table_row(tds: list[Tag]) -> Optional[dict[str, Any]]:
    """
    Parse a single <tr> from the ECI candidate listing table.

    Expected columns (order may vary):
      S.No | Candidate Name | Party | Constituency | View Affidavit
    """
    try:
        # Extract text from each cell
        cells = [td.get_text(strip=True) for td in tds]

        # Find the constituency cell (contains AC number like "1 - Gummidipoondi")
        ac_no = None
        ac_name = ""
        constituency_raw = ""
        candidate_name = ""
        party_raw = ""
        affidavit_url = None
        photo_url = None

        # Try the standard ECI table layout
        # Column 0: S.No
        # Column 1: Candidate Name
        # Column 2: Party
        # Column 3: Constituency
        # Column 4: View/Download button

        if len(cells) >= 5:
            candidate_name = cells[1].strip()
            party_raw = cells[2].strip()
            constituency_raw = cells[3].strip()
        elif len(cells) >= 4:
            candidate_name = cells[0].strip()
            party_raw = cells[1].strip()
            constituency_raw = cells[2].strip()

        if not candidate_name or not constituency_raw:
            return None

        ac_no = _parse_ac_no(constituency_raw)
        ac_name = _parse_ac_name(constituency_raw)

        if ac_no is None:
            # Try to find AC number in another column
            for cell in cells:
                ac_no = _parse_ac_no(cell)
                if ac_no:
                    ac_name = _parse_ac_name(cell)
                    break

        if ac_no is None:
            log.debug("Skipping row, no AC number found: %s", cells)
            return None

        # Extract affidavit PDF link
        for td in tds:
            link = td.find("a", href=True)
            if link:
                href = link["href"]
                if "pdf" in href.lower() or "affidavit" in href.lower() or "download" in href.lower():
                    affidavit_url = urljoin(ECI_AFFIDAVIT_BASE_URL, href)
                    break
            # Also check for onclick handlers with URLs
            btn = td.find("button", onclick=True) or td.find("a", onclick=True)
            if btn:
                onclick = btn.get("onclick", "")
                url_match = re.search(r"['\"]([^'\"]+\.pdf[^'\"]*)['\"]", onclick, re.I)
                if url_match:
                    affidavit_url = urljoin(ECI_AFFIDAVIT_BASE_URL, url_match.group(1))

        # Extract photo URL if embedded
        for td in tds:
            img = td.find("img", src=True)
            if img:
                photo_url = urljoin(ECI_AFFIDAVIT_BASE_URL, img["src"])
                break

        party_code = normalise_party(party_raw)

        return {
            "ac_no": ac_no,
            "ac_name": ac_name,
            "name": candidate_name,
            "party_raw": party_raw,
            "party_code": party_code,
            "party_name": party_raw,
            "affidavit_pdf_url": affidavit_url,
            "photo_url": photo_url,
        }
    except Exception as exc:
        log.debug("Error parsing row: %s", exc)
        return None


def _has_next_page(soup: BeautifulSoup, current_page: int) -> bool:
    """Check if there's a next page in the pagination controls."""
    # Look for pagination links
    pager = soup.find("ul", class_="pagination") or soup.find("div", class_="pagination")
    if pager:
        next_link = pager.find("a", string=re.compile(r"next|›|»|>", re.I))
        if next_link:
            return True
        # Check for a page number > current
        for a in pager.find_all("a", href=True):
            text = a.get_text(strip=True)
            if text.isdigit() and int(text) > current_page:
                return True

    # Also check for "Next" button anywhere
    next_btn = soup.find("a", string=re.compile(r"^next$", re.I))
    if next_btn and not next_btn.get("disabled"):
        return True

    return False


# ── Detail page scraping ──────────────────────────────────────────────────────


def _scrape_candidate_detail(session, detail_url: str) -> dict[str, Any]:
    """
    Scrape a candidate's detail/affidavit page for extra fields.

    Returns dict with optional keys: gender, age, photo_url, affidavit_pdf_url,
    district, etc.
    """
    extra: dict[str, Any] = {}
    try:
        resp = throttled_get(session, detail_url)
        soup = BeautifulSoup(resp.text, "lxml")

        # Look for structured data in definition lists or tables
        for row in soup.find_all(["tr", "dl", "div"]):
            text = row.get_text(" ", strip=True).lower()

            # Age
            age_match = re.search(r"age\s*[:\-]?\s*(\d{2,3})", text)
            if age_match and "age" not in extra:
                extra["age"] = int(age_match.group(1))

            # Gender
            if "gender" in text:
                if "female" in text:
                    extra["gender"] = "F"
                elif "male" in text:
                    extra["gender"] = "M"
                elif "other" in text or "transgender" in text:
                    extra["gender"] = "O"

            # District
            dist_match = re.search(r"district\s*[:\-]?\s*([A-Za-z\s]+)", text)
            if dist_match and "district" not in extra:
                extra["district"] = dist_match.group(1).strip().upper()

        # Photo
        for img in soup.find_all("img", src=True):
            src = img["src"].lower()
            if "photo" in src or "candidate" in src or "passport" in src:
                extra["photo_url"] = urljoin(ECI_AFFIDAVIT_BASE_URL, img["src"])
                break

        # Affidavit PDF link
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                extra["affidavit_pdf_url"] = urljoin(ECI_AFFIDAVIT_BASE_URL, href)
                break

    except Exception as exc:
        log.debug("Error scraping detail page %s: %s", detail_url, exc)

    return extra


# ── Main orchestration ─────────────────────────────────────────────────────────


def scrape_all_candidates(
    max_pages: Optional[int] = None,
    scrape_details: bool = False,
) -> list[dict[str, Any]]:
    """
    Scrape all candidate rows from the ECI portal.

    Parameters
    ----------
    max_pages : int, optional
        Stop after this many pages (for development/testing).
    scrape_details : bool
        If True, also hit each candidate's detail page for extra fields.

    Returns
    -------
    list[dict]
        Raw candidate dicts (pre-validation).
    """
    session = build_session()
    # Warm session to pick up cookies / anti-bot tokens
    warm_session(session, ECI_AFFIDAVIT_BASE_URL)
    all_rows: list[dict[str, Any]] = []
    page = 1

    while True:
        if max_pages and page > max_pages:
            log.info("Reached max_pages=%d, stopping.", max_pages)
            break

        rows, has_next = _scrape_listing_page(session, page)
        all_rows.extend(rows)

        if not has_next or not rows:
            break
        page += 1

    log.info("Total raw candidates scraped: %d", len(all_rows))
    return all_rows


def _assign_candidate_ids(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign stable candidate_id values like TN2026_AC001_01."""
    counter: dict[int, int] = defaultdict(int)
    for row in rows:
        ac = row.get("ac_no", 0)
        counter[ac] += 1
        row["candidate_id"] = f"TN2026_AC{ac:03d}_{counter[ac]:02d}"
    return rows


def _fill_defaults(row: dict[str, Any]) -> dict[str, Any]:
    """Fill in required fields with defaults if missing."""
    row.setdefault("district", "")
    row.setdefault("gender", None)
    row.setdefault("age", None)
    row.setdefault("photo_url", None)
    row.setdefault("affidavit_pdf_url", None)
    row.setdefault("assets_movable", None)
    row.setdefault("assets_immovable", None)
    row.setdefault("assets_total", None)
    row.setdefault("liabilities_total", None)
    row.setdefault("income_last_itr", None)
    row.setdefault("has_criminal_cases", False)
    row.setdefault("pending_cases_count", 0)
    row.setdefault("conviction_cases_count", 0)
    row.setdefault("major_ipc_sections", [])
    # Remove intermediate fields
    row.pop("party_raw", None)
    return row


def validate_and_export(raw_rows: list[dict[str, Any]]) -> None:
    """
    Validate raw rows via Pydantic, then write JSON output files.
    """
    rows = _assign_candidate_ids(raw_rows)
    rows = [_fill_defaults(r) for r in rows]

    valid: list[dict[str, Any]] = []
    errors = 0
    for row in rows:
        try:
            model = CandidateModel(**row)
            valid.append(model.model_dump(mode="json"))
        except Exception as exc:
            errors += 1
            log.warning("Validation error for %s: %s", row.get("name", "?"), exc)

    log.info("Validated %d candidates (%d errors)", len(valid), errors)

    # ── Write flat list ────────────────────────────────────────────────────
    DATA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES_ALL_JSON, "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)
    log.info("Wrote %s (%d candidates)", CANDIDATES_ALL_JSON, len(valid))

    # ── Write grouped by AC ────────────────────────────────────────────────
    by_ac: dict[str, list[dict]] = defaultdict(list)
    for c in valid:
        by_ac[str(c["ac_no"])].append(c)
    with open(CANDIDATES_BY_AC_JSON, "w", encoding="utf-8") as f:
        json.dump(by_ac, f, ensure_ascii=False, indent=2)
    log.info("Wrote %s (%d constituencies)", CANDIDATES_BY_AC_JSON, len(by_ac))


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape TN 2026 candidate data")
    parser.add_argument(
        "--max", type=int, default=None,
        help="Max pages to scrape (for development)",
    )
    parser.add_argument(
        "--details", action="store_true",
        help="Also scrape individual candidate detail pages",
    )
    args = parser.parse_args()

    raw = scrape_all_candidates(max_pages=args.max, scrape_details=args.details)
    if not raw:
        log.error("No candidates scraped. Check network/portal availability.")
        sys.exit(1)
    validate_and_export(raw)


if __name__ == "__main__":
    main()
