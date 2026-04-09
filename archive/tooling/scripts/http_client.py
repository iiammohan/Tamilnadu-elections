"""
Shared HTTP client with rate-limiting, retries, and session management.
"""

from __future__ import annotations

import time
from typing import Optional

import urllib3

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scripts.config import (
    HTTP_HEADERS,
    HTTP_TIMEOUT,
    MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
    RETRY_BACKOFF_FACTOR,
    setup_logging,
)

# Indian government sites (NIC/NICCA) use CAs not in the default trust store.
# Suppress the InsecureRequestWarning since we intentionally skip verification.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = setup_logging("http_client")

# Minimal headers — do NOT set a browser User-Agent; Akamai blocks Chrome UA
# when the TLS fingerprint doesn't match.  The default python-requests UA works.
_BROWSER_HEADERS: dict[str, str] = {
    **HTTP_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def build_session(verify_ssl: bool = False) -> requests.Session:
    """
    Return a ``requests.Session`` pre-configured with retries and headers.

    Parameters
    ----------
    verify_ssl : bool
        Whether to verify SSL certificates.  Defaults to ``False`` because
        Indian government portals use NIC CA certificates that are not in
        the standard trust store.
    """
    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)
    session.verify = verify_ssl
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_last_request_ts: float = 0.0


def throttled_get(
    session: requests.Session,
    url: str,
    *,
    params: Optional[dict] = None,
    timeout: int = HTTP_TIMEOUT,
    **kwargs,
) -> requests.Response:
    """GET with rate-limiting between consecutive calls."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < REQUEST_DELAY_SECONDS:
        time.sleep(REQUEST_DELAY_SECONDS - elapsed)
    _last_request_ts = time.monotonic()
    log.debug("GET %s", url)
    resp = session.get(url, params=params, timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp


def throttled_post(
    session: requests.Session,
    url: str,
    *,
    data: Optional[dict] = None,
    timeout: int = HTTP_TIMEOUT,
    **kwargs,
) -> requests.Response:
    """POST with rate-limiting between consecutive calls."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < REQUEST_DELAY_SECONDS:
        time.sleep(REQUEST_DELAY_SECONDS - elapsed)
    _last_request_ts = time.monotonic()
    log.debug("POST %s", url)
    resp = session.post(url, data=data, timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp


def warm_session(session: requests.Session, base_url: str) -> None:
    """
    Visit the portal homepage to establish cookies / session tokens
    before scraping deeper pages.
    """
    try:
        resp = session.get(base_url, timeout=HTTP_TIMEOUT)
        log.info("Warmed session on %s (status %d, cookies: %d)",
                 base_url, resp.status_code, len(session.cookies))
    except Exception as exc:
        log.warning("Failed to warm session on %s: %s", base_url, exc)
