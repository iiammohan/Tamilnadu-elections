"""
Scrape candidate data from the ECI Affidavit portal for TN Assembly 2026.

Strategy
--------
1.  POST to ``/CandidateCustomFilter`` with state=S22 to get paginated
    candidate listing cards (10 per page).  Each card contains:
    name, party, status (Accepted/Rejected), constituency, photo URL,
    and a link to the candidate's profile page.
2.  Visit each **accepted** candidate's ``/show-profile/…`` page to
    collect age, gender, father's name.
3.  Deduplicate repeated filings by (name, ac_no, party) so same-name
    candidates from different parties are preserved.
4.  Validate via Pydantic and export JSON.

Usage
-----
    python -m scripts.fetch_candidates              # all TN constituencies
    python -m scripts.fetch_candidates --ac 116 121 # specific ACs only
    python -m scripts.fetch_candidates --max 3       # first 3 pages (dev)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from scripts.config import (
    CANDIDATES_ALL_JSON,
    CANDIDATES_BY_AC_JSON,
    DATA_OUT_DIR,
    ECI_AFFIDAVIT_BASE_URL,
    ECI_ELECTION_PARAM,
    ECI_ELECTION_TYPE,
    ECI_FILTER_URL,
    ECI_PHASE,
    ECI_STATE_CODE,
    TOTAL_ACS,
    setup_logging,
)
from scripts.http_client import build_session, throttled_get, throttled_post
from scripts.models import CandidateModel
from scripts.party_map import normalise_party

log = setup_logging("fetch_candidates")

# ── ECI listing helpers ────────────────────────────────────────────────────────


def _get_csrf(session) -> str:
    """GET the ECI homepage and return the CSRF meta token."""
    resp = throttled_get(session, ECI_AFFIDAVIT_BASE_URL)
    soup = BeautifulSoup(resp.text, "lxml")
    meta = soup.find("meta", {"name": "csrf-token"})
    if not meta:
        raise RuntimeError("CSRF token not found on ECI homepage")
    return meta["content"]


def _build_filter_payload(csrf: str, const_id: str = "") -> dict[str, str]:
    """Build the POST body for CandidateCustomFilter."""
    return {
        "_token": csrf,
        "electionType": ECI_ELECTION_TYPE,
        "election": ECI_ELECTION_PARAM,
        "states": ECI_STATE_CODE,
        "phase": ECI_PHASE,
        "constId": const_id,
    }


def _get_constituency_map(session, csrf: str) -> dict[str, str]:
    """
    POST the filter for TN and return {ac_number: constituency_name}
    from the constId dropdown.
    """
    payload = _build_filter_payload(csrf)
    resp = throttled_post(session, ECI_FILTER_URL, data=payload)
    soup = BeautifulSoup(resp.text, "lxml")
    sel = soup.find("select", {"id": "constId"}) or soup.find(
        "select", {"name": "constId"}
    )
    result = {}
    if sel:
        for opt in sel.find_all("option"):
            val = opt.get("value", "").strip()
            if val and val.isdigit():
                result[val] = opt.text.strip()
    log.info("Loaded %d constituencies from ECI dropdown", len(result))
    return result


# ── Parse a listing-table row ──────────────────────────────────────────────────


def _parse_listing_row(tr: Tag) -> Optional[dict[str, Any]]:
    """
    Extract name, party, status, constituency, photo_url, profile_url
    from a single ``<tr>`` in the ECI ``data-tab`` table.
    """
    h4 = tr.find("h4")
    if not h4:
        return None
    name = h4.get_text(strip=True)

    party = status = constituency = ""
    for p in tr.find_all("p"):
        strong = p.find("strong")
        if not strong:
            continue
        label = strong.get_text(strip=True).rstrip(":").strip()
        value = p.get_text(strip=True).replace(strong.get_text(strip=True), "").strip()
        if label == "Party":
            party = value
        elif label == "Status":
            status = value
        elif label == "Constituency":
            constituency = value

    if not name or not constituency:
        return None

    img = tr.find("img", src=True)
    photo_url = img["src"] if img else None

    profile_link = tr.find("a", href=re.compile(r"show-profile"))
    profile_url = profile_link["href"] if profile_link else None

    party_code = normalise_party(party)

    return {
        "name": name.strip(),
        "party_name": party.strip(),
        "party_code": party_code,
        "status": status.strip(),
        "ac_name": constituency.strip().title(),
        "photo_url": photo_url,
        "profile_url": profile_url,
    }


# ── Scrape filtered listing (paginated) ───────────────────────────────────────


def _scrape_filtered_listing(
    session,
    csrf: str,
    const_id: str = "",
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    POST filter and paginate through all results.
    Returns raw dicts from listing rows.
    """
    payload = _build_filter_payload(csrf, const_id)
    rows: list[dict[str, Any]] = []
    page = 1

    while True:
        if max_pages and page > max_pages:
            log.info("Reached max_pages=%d, stopping", max_pages)
            break

        url = f"{ECI_FILTER_URL}?page={page}" if page > 1 else ECI_FILTER_URL
        resp = throttled_post(session, url, data=payload)
        soup = BeautifulSoup(resp.text, "lxml")

        # Refresh CSRF from response
        new_csrf = soup.find("meta", {"name": "csrf-token"})
        if new_csrf:
            payload["_token"] = new_csrf["content"]

        table = soup.find("table", id="data-tab")
        if not table:
            log.warning("No data-tab table on page %d", page)
            break

        page_rows = []
        for tr in table.find_all("tr")[1:]:  # skip header row
            parsed = _parse_listing_row(tr)
            if parsed:
                page_rows.append(parsed)

        if not page_rows:
            txt = table.get_text(strip=True)
            if "No Data" in txt:
                log.info("No more data on page %d", page)
            break

        rows.extend(page_rows)
        log.info("Page %d: %d candidates", page, len(page_rows))

        next_link = soup.find("a", href=re.compile(rf"page={page + 1}"))
        if not next_link:
            break
        page += 1

    return rows


# ── Scrape individual profile page ────────────────────────────────────────────


def _scrape_profile(session, profile_url: str) -> dict[str, Any]:
    """
    Visit a candidate's profile page and extract age, gender, father's name,
    and election symbol image URL.
    """
    extra: dict[str, Any] = {}
    try:
        resp = throttled_get(session, profile_url)
        soup = BeautifulSoup(resp.text, "lxml")

        detail = soup.find("div", class_="detail-person") or soup

        for el in detail.find_all(["div", "p", "span", "strong"]):
            t = el.get_text(" ", strip=True)
            if not t or len(t) > 300:
                continue

            if t.startswith("Gender:") and "gender" not in extra:
                g = t.replace("Gender:", "").strip().lower()
                if "female" in g:
                    extra["gender"] = "F"
                elif "male" in g:
                    extra["gender"] = "M"
                else:
                    extra["gender"] = "O"
            elif t.startswith("Age:") and "age" not in extra:
                m = re.search(r"Age:\s*(\d+)", t)
                if m:
                    extra["age"] = int(m.group(1))
            elif "Father" in t and "father_name" not in extra:
                m = re.search(
                    r"Father's\s*/\s*Husband's\s*Name:\s*(.+?)(?:\s+Name:|\s*$)",
                    t,
                )
                if m:
                    extra["father_name"] = m.group(1).strip()

        # Election symbol image (if exposed by profile markup)
        if "election_symbol_url" not in extra:
            sym_img = (
                detail.find("img", src=re.compile(r"symbol", re.I))
                or detail.find("img", alt=re.compile(r"symbol", re.I))
                or detail.find("img", class_=re.compile(r"symbol", re.I))
            )
            if sym_img and sym_img.get("src"):
                extra["election_symbol_url"] = sym_img["src"]

        # Form 26 affidavit PDF token is currently provided in hidden input(s)
        # like: <input id="pdfUrl15551" value="<encrypted_token>">.
        if "affidavit_pdf_url" not in extra:
            pdf_input = soup.find("input", id=re.compile(r"^pdfUrl\d+", re.I))
            if pdf_input and pdf_input.get("value"):
                token = pdf_input["value"].strip()
                if token:
                    extra["affidavit_pdf_url"] = (
                        f"{ECI_AFFIDAVIT_BASE_URL}/affidavit-pdf-download/{token}"
                    )

    except Exception as exc:
        log.debug("Error scraping profile %s: %s", profile_url[:60], exc)

    return extra


# ── Deduplication ──────────────────────────────────────────────────────────────


def _status_rank(status: str | None) -> int:
    """Return ordering rank for nomination status during dedup selection."""
    s = (status or "").strip().lower()
    if s == "accepted":
        return 3
    if "accepted" in s:
        return 2
    if s == "rejected":
        return 0
    return 1


def _deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate repeated filings for the same candidate + party in an AC.

    Important: key includes party so same-name candidates across parties are
    preserved (e.g. Egmore/Pennagaram style collisions).
    """
    by_key: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        party_key = (r.get("party_name") or r.get("party_code") or "").upper()
        key = (r["name"].upper(), int(r.get("ac_no", 0) or 0), party_key)
        by_key[key].append(r)

    result: list[dict[str, Any]] = []
    for entries in by_key.values():
        best = max(
            entries,
            key=lambda e: (
                _status_rank(e.get("status")),
                1 if e.get("profile_url") else 0,
                1 if e.get("photo_url") else 0,
            ),
        )
        result.append(best)

    log.info("Dedup: %d raw → %d unique candidates", len(rows), len(result))
    return result


# ── Assign IDs & fill defaults ─────────────────────────────────────────────────


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
    row["nomination_status"] = row.get("status")
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
    row.pop("profile_url", None)
    row.pop("status", None)
    row.pop("father_name", None)
    return row


# ── Main orchestration ─────────────────────────────────────────────────────────


def scrape_all_candidates(
    ac_list: Optional[list[int]] = None,
    max_pages: Optional[int] = None,
    scrape_details: bool = True,
) -> list[dict[str, Any]]:
    """
    Scrape candidate data from ECI portal.

    Parameters
    ----------
    ac_list : list[int], optional
        Only scrape these AC numbers.  If None, scrape all.
    max_pages : int, optional
        Max pages per constituency (for dev/testing).
    scrape_details : bool
        If True, visit each accepted candidate's profile for age/gender.
    """
    session = build_session()
    csrf = _get_csrf(session)
    const_map = _get_constituency_map(session, csrf)

    if not const_map:
        log.error("No constituencies found — check ECI portal / filter params")
        return []

    if ac_list:
        target_acs = {str(ac): const_map.get(str(ac), f"AC-{ac}") for ac in ac_list}
    else:
        target_acs = const_map

    all_rows: list[dict[str, Any]] = []

    for ac_id, ac_name in sorted(target_acs.items(), key=lambda x: int(x[0])):
        log.info("Scraping AC %s: %s", ac_id, ac_name)
        csrf = _get_csrf(session)  # refresh CSRF per AC
        rows = _scrape_filtered_listing(
            session, csrf, const_id=ac_id, max_pages=max_pages,
        )
        for r in rows:
            r["ac_no"] = int(ac_id)
        all_rows.extend(rows)
        log.info("AC %s: %d raw entries", ac_id, len(rows))

    log.info("Total raw candidates scraped: %d", len(all_rows))

    all_rows = _deduplicate(all_rows)

    if scrape_details:
        log.info("Scraping %d profile pages for age/gender…", len(all_rows))
        for i, row in enumerate(all_rows):
            url = row.get("profile_url")
            if url:
                extra = _scrape_profile(session, url)
                row.update(extra)
                if (i + 1) % 50 == 0:
                    log.info("  …scraped %d / %d profiles", i + 1, len(all_rows))

    return all_rows


def validate_and_export(raw_rows: list[dict[str, Any]]) -> None:
    """Validate raw rows via Pydantic, then write JSON output files."""
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

    DATA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CANDIDATES_ALL_JSON, "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)
    log.info("Wrote %s (%d candidates)", CANDIDATES_ALL_JSON, len(valid))

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
        "--ac", type=int, nargs="+", default=None,
        help="Specific AC numbers to scrape (e.g. --ac 116 121)",
    )
    parser.add_argument(
        "--max", type=int, default=None,
        help="Max pages per constituency (for development)",
    )
    parser.add_argument(
        "--no-details", action="store_true",
        help="Skip scraping individual profile pages",
    )
    args = parser.parse_args()

    raw = scrape_all_candidates(
        ac_list=args.ac,
        max_pages=args.max,
        scrape_details=not args.no_details,
    )
    if not raw:
        log.error("No candidates scraped. Check network/portal availability.")
        sys.exit(1)
    validate_and_export(raw)


if __name__ == "__main__":
    main()
