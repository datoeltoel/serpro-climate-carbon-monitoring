# Official SERPRO Boundary Layers

The WebGIS uses two official spatial concepts that belong to the **same unified SERPRO project landscape** and are spatially overlapping:

1. **SERPRO Project Area (Concession)** — the PT Kalamanthana Alam Lestari concession / project-area footprint, sourced from `KAL_Boundary_Split.kml`.
2. **SERPRO Carbon Project Zone** — the wider carbon-project footprint for the Seruyan Restoration Ecosystem Project (SERPRO), sourced from `ProjectZone.kmz` and represented in the public WebGIS by `serpro_carbon_project_zone_web.geojson`.

The layers have different spatial roles and areas, but they are not unrelated geographies. The dashboard may use either layer as an analysis scope while preserving their common project-landscape relationship.

Official areas:
- SERPRO Project Area: **31,685.385 ha**
- SERPRO Carbon Project Zone: **150,142.54 ha**

The public WebGIS geometries are generalized for rendering performance. Source filenames, spatial roles, and official project-zone area are retained in `boundary_metadata.json`.
