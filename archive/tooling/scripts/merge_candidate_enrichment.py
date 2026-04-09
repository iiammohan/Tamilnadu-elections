from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "public" / "data"
NEW_PATH = DATA_DIR / "tn2026_all_candidates.json"
OLD_PATH = DATA_DIR / "tn2026_all_candidates.pre_refresh_backup.json"
OUT_PATH = NEW_PATH

ENRICH_FIELDS = [
    "affidavit_pdf_url",
    "age",
    "gender",
    "assets_movable",
    "assets_immovable",
    "assets_total",
    "liabilities_total",
    "income_last_itr",
    "has_criminal_cases",
    "pending_cases_count",
    "conviction_cases_count",
    "major_ipc_sections",
]


def _norm(s: str | None) -> str:
    return (s or "").strip().upper()


def _key(row: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(row.get("ac_no", 0) or 0),
        _norm(row.get("name")),
        _norm(row.get("party_name")),
    )


def merge() -> None:
    if not NEW_PATH.exists() or not OLD_PATH.exists():
        raise SystemExit("Missing new/old candidate JSON for merge")

    with NEW_PATH.open("r", encoding="utf-8") as f:
        new_rows: list[dict[str, Any]] = json.load(f)

    with OLD_PATH.open("r", encoding="utf-8") as f:
        old_rows: list[dict[str, Any]] = json.load(f)

    old_map = {_key(r): r for r in old_rows}

    merged_count = 0
    for row in new_rows:
        prev = old_map.get(_key(row))
        if not prev:
            continue
        for field in ENRICH_FIELDS:
            old_val = prev.get(field)
            new_val = row.get(field)
            if old_val is None:
                continue
            if field in {"has_criminal_cases", "pending_cases_count", "conviction_cases_count", "major_ipc_sections"}:
                row[field] = old_val
                continue
            if new_val in (None, "", []):
                row[field] = old_val
        merged_count += 1

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(new_rows, f, ensure_ascii=False, indent=2)

    print(f"Merged enrichment for {merged_count} rows")


if __name__ == "__main__":
    merge()
