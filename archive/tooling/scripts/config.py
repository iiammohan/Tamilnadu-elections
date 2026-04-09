"""Configuration constants for the TN 2026 Election data pipeline."""

import logging
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT_DIR / "public"
DATA_OUT_DIR = PUBLIC_DIR / "data"
PHOTOS_DIR = PUBLIC_DIR / "photos"
AFFIDAVITS_DIR = PUBLIC_DIR / "affidavits"

# Ensure output dirs exist
DATA_OUT_DIR.mkdir(parents=True, exist_ok=True)
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
AFFIDAVITS_DIR.mkdir(parents=True, exist_ok=True)

# ── Output file names ─────────────────────────────────────────────────────────
CANDIDATES_BY_AC_JSON = DATA_OUT_DIR / "tn2026_by_constituency.json"
CANDIDATES_ALL_JSON = DATA_OUT_DIR / "tn2026_all_candidates.json"

# ── URLs ───────────────────────────────────────────────────────────────────────
CEO_TN_NOMINATIONS_URL = (
    "https://www.electionapps.tn.gov.in/NOM2026/pu_nom/public_report.aspx"
)
ECI_AFFIDAVIT_BASE_URL = "https://affidavit.eci.gov.in"
ECI_FILTER_URL = f"{ECI_AFFIDAVIT_BASE_URL}/CandidateCustomFilter"

# ── ECI election identifiers ──────────────────────────────────────────────────
ECI_ELECTION_TYPE = "32-AC-GENERAL-3-60"
ECI_ELECTION_PARAM = "32-AC-GENERAL-3-60 "   # trailing space required by ECI
ECI_STATE_CODE = "S22"                         # Tamil Nadu
ECI_PHASE = "2"                                # Phase 1

# ── Rate limiting ──────────────────────────────────────────────────────────────
REQUEST_DELAY_SECONDS = 0.15         # seconds between HTTP requests
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0           # exponential back-off multiplier

# ── Scraper ────────────────────────────────────────────────────────────────────
HTTP_TIMEOUT = 30                    # seconds
# NOTE: Akamai CDN on affidavit.eci.gov.in blocks Chrome-like UAs when the
# TLS fingerprint doesn't match a real browser.  The default python-requests
# UA passes because no browser behaviour is expected for it.
USER_AGENT = None  # use requests library default
HTTP_HEADERS: dict[str, str] = {}

# ── State / election identifiers ──────────────────────────────────────────────
STATE_NAME = "Tamil Nadu"
ELECTION_TYPE = "General Election to Legislative Assembly"
ELECTION_YEAR = 2026
TOTAL_ACS = 234

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
LOG_LEVEL = logging.INFO


def setup_logging(name: str = "tn2026") -> logging.Logger:
    """Return a configured logger for pipeline modules."""
    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
    return logging.getLogger(name)
