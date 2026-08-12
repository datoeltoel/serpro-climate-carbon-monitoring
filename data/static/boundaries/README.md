# Official SERPRO Boundary Layers

The WebGIS uses two official spatial concepts and keeps them separate:

1. **SERPRO Project Area (Concession)** — the full PT Kalamanthana Alam Lestari concession/project area, sourced from `KAL_Boundary_Split.kml` and preserved as the official concession source layer.
2. **SERPRO Carbon Project Zone** — the carbon project boundary for the Seruyan Restoration Ecosystem Project (SERPRO), sourced from `ProjectZone.kmz` and represented in the public WebGIS by `serpro_carbon_project_zone_web.geojson`.

These layers are not synonyms. Carbon/MRV indicators should use the Carbon Project Zone by default, while concession-level monitoring can use the full SERPRO Project Area.

The public WebGIS geometries are generalized for rendering performance. Source filenames and roles are retained in `boundary_metadata.json`.
