"""
Validation tests for the TN 2026 election data pipeline.

Run:  pytest scripts/validation_tests.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.config import CANDIDATES_ALL_JSON, CANDIDATES_BY_AC_JSON, DATA_OUT_DIR, TOTAL_ACS
from scripts.models import CandidateModel
from scripts.party_map import VALID_CODES, normalise_party


# ── party_map tests ────────────────────────────────────────────────────────────


class TestPartyMap:
    """Verify party-name normalisation."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Dravida Munnetra Kazhagam", "DMK"),
            ("dravida munnetra kazhagam", "DMK"),
            ("DMK", "DMK"),
            ("All India Anna Dravida Munnetra Kazhagam", "AIADMK"),
            ("AIADMK", "AIADMK"),
            ("Bharatiya Janata Party", "BJP"),
            ("Indian National Congress", "INC"),
            ("Independent", "IND"),
            ("IND", "IND"),
            ("Communist Party of India (Marxist)", "CPI(M)"),
            ("Communist Party of India", "CPI"),
            ("Naam Tamilar Katchi", "NTK"),
            ("Tamilaga Vetri Kazhagam", "TVK"),
            ("Social Democratic Party of India", "SDPI"),
            ("Some Random Party", "Others"),
            ("  dmk  ", "DMK"),
        ],
    )
    def test_normalise_party(self, raw: str, expected: str) -> None:
        assert normalise_party(raw) == expected

    def test_all_valid_codes_returned(self) -> None:
        """Every mapped value should be in VALID_CODES."""
        from scripts.party_map import _RAW_MAP

        for code in _RAW_MAP.values():
            assert code in VALID_CODES, f"{code} not in VALID_CODES"


# ── CandidateModel tests ──────────────────────────────────────────────────────


class TestCandidateModel:
    """Verify Pydantic model validation."""

    def _base_data(self, **overrides) -> dict:
        base = {
            "candidate_id": "TN2026_AC001_01",
            "ac_no": 1,
            "ac_name": "Gummidipoondi",
            "district": "THIRUVALLUR",
            "name": "Test Candidate",
            "party_code": "DMK",
            "party_name": "Dravida Munnetra Kazhagam",
        }
        base.update(overrides)
        return base

    def test_valid_minimal(self) -> None:
        m = CandidateModel(**self._base_data())
        assert m.candidate_id == "TN2026_AC001_01"
        assert m.has_criminal_cases is False

    def test_valid_full(self) -> None:
        m = CandidateModel(
            **self._base_data(
                gender="M",
                age=45,
                assets_movable=100000,
                assets_immovable=200000,
                assets_total=300000,
                liabilities_total=50000,
                income_last_itr=500000,
                has_criminal_cases=True,
                pending_cases_count=2,
                conviction_cases_count=0,
                major_ipc_sections=["420", "120B"],
            )
        )
        assert m.assets_total == 300000
        assert m.has_criminal_cases is True

    def test_criminal_auto_set(self) -> None:
        """has_criminal_cases should auto-set to True if counts > 0."""
        m = CandidateModel(
            **self._base_data(
                has_criminal_cases=False,
                pending_cases_count=3,
            )
        )
        assert m.has_criminal_cases is True

    def test_invalid_ac_no(self) -> None:
        with pytest.raises(Exception):
            CandidateModel(**self._base_data(ac_no=0))
        with pytest.raises(Exception):
            CandidateModel(**self._base_data(ac_no=235))

    def test_invalid_gender(self) -> None:
        with pytest.raises(Exception):
            CandidateModel(**self._base_data(gender="X"))

    def test_strips_whitespace(self) -> None:
        m = CandidateModel(**self._base_data(name="  John Doe  "))
        assert m.name == "John Doe"


# ── JSON output validation (only runs if files exist) ─────────────────────────


@pytest.mark.skipif(
    not CANDIDATES_ALL_JSON.exists(),
    reason="No candidate JSON — run the pipeline first",
)
class TestJsonOutput:
    """Validate the generated JSON files."""

    def test_all_candidates_is_list(self) -> None:
        with open(CANDIDATES_ALL_JSON, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_all_candidates_validate(self) -> None:
        with open(CANDIDATES_ALL_JSON, encoding="utf-8") as f:
            data = json.load(f)
        errors = 0
        for row in data:
            try:
                CandidateModel(**row)
            except Exception:
                errors += 1
        assert errors == 0, f"{errors} records failed Pydantic validation"

    def test_by_constituency_keys(self) -> None:
        with open(CANDIDATES_BY_AC_JSON, encoding="utf-8") as f:
            by_ac = json.load(f)
        assert isinstance(by_ac, dict)
        # Every key should be a string of a number 1-234
        for key in by_ac:
            assert key.isdigit()
            assert 1 <= int(key) <= TOTAL_ACS

    def test_party_codes_valid(self) -> None:
        with open(CANDIDATES_ALL_JSON, encoding="utf-8") as f:
            data = json.load(f)
        invalid = set()
        for c in data:
            code = c.get("party_code", "")
            if code not in VALID_CODES:
                invalid.add(code)
        assert not invalid, f"Invalid party codes found: {invalid}"

    def test_summary_json(self) -> None:
        summary_path = DATA_OUT_DIR / "tn2026_summary.json"
        if not summary_path.exists():
            pytest.skip("Summary JSON not generated yet")
        with open(summary_path, encoding="utf-8") as f:
            stats = json.load(f)
        assert "total_candidates" in stats
        assert stats["total_candidates"] > 0
        assert "constituencies_covered" in stats
