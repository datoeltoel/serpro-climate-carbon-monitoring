from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScopeName = Literal[
    "SERPRO Project Landscape",
    "SERPRO Carbon Project Zone",
    "SERPRO Project Area",
]


@dataclass(frozen=True)
class Scope:
    name: ScopeName
    parent: ScopeName | None
    area_ha: float
    description: str


SCOPES: dict[str, Scope] = {
    "SERPRO Project Landscape": Scope(
        name="SERPRO Project Landscape",
        parent=None,
        area_ha=150142.543553,
        description="Unified SERPRO landscape represented by the Carbon Project Zone envelope.",
    ),
    "SERPRO Carbon Project Zone": Scope(
        name="SERPRO Carbon Project Zone",
        parent="SERPRO Project Landscape",
        area_ha=150142.5436,
        description="Official carbon project zone supplied in ProjectZone.kmz.",
    ),
    "SERPRO Project Area": Scope(
        name="SERPRO Project Area",
        parent="SERPRO Carbon Project Zone",
        area_ha=31685.38489,
        description="PT Kalamanthana Alam Lestari concession/project area from KAL_Boundary_Split.kml.",
    ),
}


def get_scope(name: str) -> Scope:
    """Return a configured monitoring scope."""
    if name not in SCOPES:
        raise KeyError(f"Unknown scope: {name}")
    return SCOPES[name]


def scope_options() -> list[str]:
    """Return scopes in hierarchy order for UI controls."""
    return [
        "SERPRO Project Landscape",
        "SERPRO Carbon Project Zone",
        "SERPRO Project Area",
    ]


def containment_percent(child_area_ha: float, parent_area_ha: float) -> float:
    """Calculate child area as a percentage of parent area."""
    if parent_area_ha <= 0:
        return 0.0
    return child_area_ha / parent_area_ha * 100.0


SPATIAL_RELATIONSHIP = {
    "intersection_area_ha": 31685.38491,
    "union_area_ha": 150142.543553,
    "project_area_ha": 31685.38489,
    "carbon_project_zone_area_ha": 150142.5436,
    "intersection_as_percent_of_project_area": 100.0000000631,
    "intersection_as_percent_of_carbon_zone": 21.1035354472,
    "project_area_as_percent_of_carbon_zone": 21.1035354339,
    "project_area_only_area_ha": 0.00002,
    "carbon_zone_only_area_ha": 118457.15869,
}
