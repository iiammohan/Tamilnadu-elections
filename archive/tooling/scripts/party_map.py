"""
Party-name normalisation for the TN 2026 Election pipeline.

Maps the verbose party names that appear on ECI / CEO TN portals to the short
codes used in the frontend (PARTY_COLORS keys in app.js).
"""

from __future__ import annotations

# ── Canonical short codes ──────────────────────────────────────────────────────
# These MUST match the keys in `PARTY_COLORS` (public/app.js).
VALID_CODES: set[str] = {
    "DMK", "AIADMK", "BJP", "INC", "PMK", "VCK",
    "CPI(M)", "CPI", "DMDK", "MDMK", "IUML", "AMMK",
    "TMC(M)", "NTK", "KMDK", "TVK", "MNM", "SDPI",
    "BSP", "IND", "NOTA", "Others",
}

# ── Mapping table ──────────────────────────────────────────────────────────────
# Keys are lowered+stripped versions of the strings found on ECI/CEO portals.
# Values are the canonical short codes above.
_RAW_MAP: dict[str, str] = {
    # DMK
    "dravida munnetra kazhagam": "DMK",
    "dmk": "DMK",
    # AIADMK
    "all india anna dravida munnetra kazhagam": "AIADMK",
    "aiadmk": "AIADMK",
    "a.i.a.d.m.k.": "AIADMK",
    "all india anna dravida munnetra kalagam": "AIADMK",
    # BJP
    "bharatiya janata party": "BJP",
    "bjp": "BJP",
    # INC
    "indian national congress": "INC",
    "inc": "INC",
    "congress": "INC",
    # PMK
    "pattali makkal katchi": "PMK",
    "pmk": "PMK",
    # VCK
    "viduthalai chiruthaigal katchi": "VCK",
    "vck": "VCK",
    # CPI(M)
    "communist party of india (marxist)": "CPI(M)",
    "communist party of india(marxist)": "CPI(M)",
    "cpi(m)": "CPI(M)",
    "cpim": "CPI(M)",
    # CPI
    "communist party of india": "CPI",
    "cpi": "CPI",
    # DMDK
    "desiya murpokku dravida kazhagam": "DMDK",
    "dmdk": "DMDK",
    # MDMK
    "marumalarchi dravida munnetra kazhagam": "MDMK",
    "mdmk": "MDMK",
    # IUML
    "indian union muslim league": "IUML",
    "iuml": "IUML",
    # AMMK
    "amma makkal munnetra kazhagam": "AMMK",
    "ammk": "AMMK",
    # APDMK (not AMMK — separate unrecognised party)
    "anna puratchi thalaivar amma dravida munnetra kazhagam": "Others",
    # TMC(M)
    "tamil maanila congress (moopanar)": "TMC(M)",
    "tamil maanila congress(moopanar)": "TMC(M)",
    "tmc(m)": "TMC(M)",
    # NTK
    "naam tamilar katchi": "NTK",
    "ntk": "NTK",
    "naam tamizhar katchi": "NTK",
    # KMDK
    "kongunadu makkal desiya katchi": "KMDK",
    "kmdk": "KMDK",
    # TVK
    "tamilaga vetri kazhagam": "TVK",
    "tamilaga vettri kazhagam": "TVK",
    "tvk": "TVK",
    # MNM
    "makkal needhi maiam": "MNM",
    "mnm": "MNM",
    # SDPI
    "social democratic party of india": "SDPI",
    "sdpi": "SDPI",
    # BSP
    "bahujan samaj party": "BSP",
    "bsp": "BSP",
    # Independent
    "independent": "IND",
    "ind": "IND",
    "ind.": "IND",
    # NOTA
    "none of the above": "NOTA",
    "nota": "NOTA",
}

# Full-name lookup (code → official English name)
PARTY_FULL_NAMES: dict[str, str] = {
    "DMK": "Dravida Munnetra Kazhagam",
    "AIADMK": "All India Anna Dravida Munnetra Kazhagam",
    "BJP": "Bharatiya Janata Party",
    "INC": "Indian National Congress",
    "PMK": "Pattali Makkal Katchi",
    "VCK": "Viduthalai Chiruthaigal Katchi",
    "CPI(M)": "Communist Party of India (Marxist)",
    "CPI": "Communist Party of India",
    "DMDK": "Desiya Murpokku Dravida Kazhagam",
    "MDMK": "Marumalarchi Dravida Munnetra Kazhagam",
    "IUML": "Indian Union Muslim League",
    "AMMK": "Amma Makkal Munnetra Kazhagam",
    "TMC(M)": "Tamil Maanila Congress (Moopanar)",
    "NTK": "Naam Tamilar Katchi",
    "KMDK": "Kongunadu Makkal Desiya Katchi",
    "TVK": "Tamilaga Vetri Kazhagam",
    "MNM": "Makkal Needhi Maiam",
    "SDPI": "Social Democratic Party of India",
    "IND": "Independent",
    "Others": "Others",
}


def normalise_party(raw: str) -> str:
    """
    Return the canonical party code for a raw ECI/CEO string.

    Falls back to ``"Others"`` for unrecognised parties.
    """
    key = raw.strip().lower()
    code = _RAW_MAP.get(key)
    if code:
        return code
    # Try prefix matching for edge cases like "BJP(TN STATE)"
    for k, v in _RAW_MAP.items():
        if key.startswith(k):
            return v
    return "Others"


def party_full_name(code: str) -> str:
    """Return the official English party name for a canonical code."""
    return PARTY_FULL_NAMES.get(code, code)
