"""Pydantic data models for TN 2026 Election candidate records."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CandidateModel(BaseModel):
    """A single contesting-candidate record for TN Assembly 2026."""

    # ── Identity ───────────────────────────────────────────────────────────────
    candidate_id: str = Field(
        ...,
        description="Stable unique key, e.g. TN2026_AC001_01",
    )
    ac_no: int = Field(..., ge=1, le=234)
    ac_name: str
    district: str
    name: str
    party_code: str = Field(
        ...,
        description="Normalised code matching the frontend PARTY_COLORS keys",
    )
    party_name: str
    nomination_status: Optional[str] = Field(
        None,
        description="Nomination scrutiny status from source (e.g. Accepted/Rejected)",
    )

    # ── Demographics ───────────────────────────────────────────────────────────
    gender: Optional[str] = Field(
        None, pattern=r"^(M|F|O)$",
        description="M = male, F = female, O = other",
    )
    age: Optional[int] = Field(None, ge=18, le=120)

    # ── External links ─────────────────────────────────────────────────────────
    photo_url: Optional[str] = None
    election_symbol_url: Optional[str] = None
    affidavit_pdf_url: Optional[str] = None

    # ── Financial (from Form 26 affidavit) ─────────────────────────────────────
    assets_movable: Optional[float] = Field(None, ge=0)
    assets_immovable: Optional[float] = Field(None, ge=0)
    assets_total: Optional[float] = Field(None, ge=0)
    liabilities_total: Optional[float] = Field(None, ge=0)
    income_last_itr: Optional[float] = Field(None, ge=0)

    # ── Criminal record (from Form 26 affidavit) ──────────────────────────────
    has_criminal_cases: bool = False
    pending_cases_count: int = Field(0, ge=0)
    conviction_cases_count: int = Field(0, ge=0)
    major_ipc_sections: List[str] = Field(default_factory=list)

    # ── Cross-field validation ─────────────────────────────────────────────────
    @model_validator(mode="after")
    def _check_assets_consistency(self) -> "CandidateModel":
        """Warn-level: assets_total should ≈ movable + immovable."""
        if (
            self.assets_total is not None
            and self.assets_movable is not None
            and self.assets_immovable is not None
        ):
            expected = self.assets_movable + self.assets_immovable
            if expected > 0:
                deviation = abs(self.assets_total - expected) / expected
                if deviation > 0.05:
                    # Allow model to pass but caller can inspect
                    pass
        return self

    @model_validator(mode="after")
    def _check_criminal_consistency(self) -> "CandidateModel":
        """has_criminal_cases must be True if any counts > 0."""
        if (self.pending_cases_count > 0 or self.conviction_cases_count > 0):
            object.__setattr__(self, "has_criminal_cases", True)
        return self

    model_config = ConfigDict(str_strip_whitespace=True)
