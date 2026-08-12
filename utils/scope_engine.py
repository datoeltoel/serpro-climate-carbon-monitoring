"""Official SERPRO spatial scope definitions and relationships."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Scope:
    key: str
    label: str
    area_ha: float
    role: str

CARBON_PROJECT_ZONE = Scope("carbon_project_zone", "SERPRO Carbon Project Zone", 150_142.5436, "Primary carbon-project spatial envelope.")
PROJECT_AREA = Scope("project_area", "SERPRO Project Area", 31_685.38489, "PT Kalamanthana Alam Lestari concession / project area.")
SPATIAL_RELATIONSHIP = {
    "intersection_area_ha": 31_685.38491,
    "union_area_ha": 150_142.543553,
    "project_area_only_area_ha": 0.00002,
    "carbon_zone_only_area_ha": 118_457.15869,
    "project_area_containment_percent": 100.0000000631,
    "project_area_share_of_carbon_zone_percent": 21.1035354339,
}
SCOPE_OPTIONS = {"SERPRO Project Landscape": None, CARBON_PROJECT_ZONE.label: CARBON_PROJECT_ZONE, PROJECT_AREA.label: PROJECT_AREA}

def get_scope(label: str) -> Scope | None:
    return SCOPE_OPTIONS.get(label)

def scope_options() -> list[str]:
    return list(SCOPE_OPTIONS.keys())
