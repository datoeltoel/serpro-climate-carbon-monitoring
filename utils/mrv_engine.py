"""Small, auditable calculation primitives for the Phase 2 MRV layer.

The functions in this module intentionally operate only on supplied evidence.
No project carbon stock is inferred when an input dataset is missing.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoverageResult:
    total_area_ha: float
    official_area_ha: float
    coverage_percent: float
    delta_ha: float


def safe_float(value: object) -> float:
    """Convert a numeric-like value to float, raising a clear error otherwise."""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected numeric value, got {value!r}") from exc


def area_coverage(total_area_ha: float, official_area_ha: float) -> CoverageResult:
    """Compare an evidence dataset's summed area with the official scope area."""
    total = safe_float(total_area_ha)
    official = safe_float(official_area_ha)
    if official <= 0:
        raise ValueError("Official scope area must be greater than zero")
    return CoverageResult(
        total_area_ha=total,
        official_area_ha=official,
        coverage_percent=(total / official) * 100.0,
        delta_ha=total - official,
    )


def biomass_to_carbon_tonnes(biomass_t: float, carbon_fraction: float = 0.47) -> float:
    """Convert dry biomass tonnes to tonnes of carbon using an explicit fraction."""
    biomass = safe_float(biomass_t)
    fraction = safe_float(carbon_fraction)
    if biomass < 0 or not 0 <= fraction <= 1:
        raise ValueError("Biomass must be non-negative and carbon fraction must be 0..1")
    return biomass * fraction


def carbon_to_co2e_tonnes(carbon_t: float) -> float:
    """Convert tonnes C to tonnes CO2e using the molecular-weight ratio 44/12."""
    carbon = safe_float(carbon_t)
    if carbon < 0:
        raise ValueError("Carbon stock must be non-negative")
    return carbon * (44.0 / 12.0)


def relative_uncertainty_percent(values: list[float], uncertainty_percent: list[float]) -> float:
    """Combine independent relative uncertainties by root-sum-of-squares."""
    if len(values) != len(uncertainty_percent) or not values:
        raise ValueError("Values and uncertainty arrays must have the same non-zero length")
    weighted = 0.0
    total = 0.0
    for value, uncertainty in zip(values, uncertainty_percent):
        v = abs(safe_float(value))
        u = safe_float(uncertainty)
        if u < 0:
            raise ValueError("Uncertainty cannot be negative")
        total += v
        weighted += (v * u / 100.0) ** 2
    if total == 0:
        return 0.0
    return (weighted**0.5 / total) * 100.0
