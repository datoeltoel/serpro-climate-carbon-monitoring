"""Validation helpers for auditable MRV evidence datasets.

Phase 2.1 keeps evidence intake deterministic and methodology-neutral. The
helpers validate structure, numeric fields, duplicate records and scope
coverage without producing project carbon values.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

REQUIRED_LULC_COLUMNS = {
    "year",
    "class_code",
    "class_name",
    "area_ha",
}
OPTIONAL_PROVENANCE_COLUMNS = {
    "source",
    "acquisition_date",
    "spatial_resolution_m",
    "classification_method",
    "accuracy_percent",
    "processing_version",
}


@dataclass(frozen=True)
class EvidenceValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    row_count: int
    years: tuple[int, ...]
    total_area_by_year: dict[int, float]
    provenance_coverage_percent: float


def _missing(columns: Iterable[str], required: set[str]) -> list[str]:
    return sorted(required - set(columns))


def validate_lulc_evidence(
    frame: pd.DataFrame,
    official_area_ha: float,
    coverage_tolerance_percent: float = 1.0,
) -> EvidenceValidation:
    """Validate a LULC evidence table before MRV calculations consume it."""
    errors: list[str] = []
    warnings: list[str] = []
    if official_area_ha <= 0:
        errors.append("Official scope area must be greater than zero.")

    missing = _missing(frame.columns, REQUIRED_LULC_COLUMNS)
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return EvidenceValidation(False, tuple(errors), tuple(warnings), len(frame), (), {}, 0.0)
    if frame.empty:
        errors.append("Evidence file is empty.")
        return EvidenceValidation(False, tuple(errors), tuple(warnings), 0, (), {}, 0.0)

    work = frame.copy()
    work["year"] = pd.to_numeric(work["year"], errors="coerce")
    work["area_ha"] = pd.to_numeric(work["area_ha"], errors="coerce")
    if work["year"].isna().any():
        errors.append("Year contains non-numeric or missing values.")
    if work["area_ha"].isna().any():
        errors.append("area_ha contains non-numeric or missing values.")
    if (work["area_ha"] < 0).any():
        errors.append("area_ha must be non-negative.")
    if work["class_code"].isna().any() or (work["class_code"].astype(str).str.strip() == "").any():
        errors.append("class_code contains missing or blank values.")
    if work["class_name"].isna().any() or (work["class_name"].astype(str).str.strip() == "").any():
        errors.append("class_name contains missing or blank values.")

    duplicate_keys = work.duplicated(subset=["year", "class_code"], keep=False)
    if duplicate_keys.any():
        warnings.append("Duplicate year/class_code records detected; aggregate them before treating the table as canonical evidence.")

    years: tuple[int, ...] = ()
    totals: dict[int, float] = {}
    if not work["year"].isna().any() and not work["area_ha"].isna().any():
        work["year"] = work["year"].astype(int)
        years = tuple(sorted(work["year"].unique().tolist()))
        totals = {int(year): float(area) for year, area in work.groupby("year")["area_ha"].sum().items()}
        if official_area_ha > 0:
            for year, total in totals.items():
                delta_pct = abs(total - official_area_ha) / official_area_ha * 100.0
                if delta_pct > coverage_tolerance_percent:
                    warnings.append(
                        f"Year {year} mapped area differs from official scope by {delta_pct:.2f}% (outside {coverage_tolerance_percent:.2f}% tolerance)."
                    )

    provenance_columns = [column for column in OPTIONAL_PROVENANCE_COLUMNS if column in work.columns]
    provenance_coverage = 0.0
    if provenance_columns:
        populated = work[provenance_columns].notna().any(axis=1)
        provenance_coverage = float(populated.mean() * 100.0)
        if provenance_coverage < 100.0:
            warnings.append(f"Provenance metadata is populated for {provenance_coverage:.2f}% of rows.")
    else:
        warnings.append("No provenance metadata columns were supplied.")

    return EvidenceValidation(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(dict.fromkeys(warnings)),
        row_count=len(work),
        years=years,
        total_area_by_year=totals,
        provenance_coverage_percent=provenance_coverage,
    )
