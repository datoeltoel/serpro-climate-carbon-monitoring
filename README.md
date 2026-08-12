# SERPRO Climate & Carbon Monitoring 

Climate intelligence and spatial monitoring platform for the **Seruyan Restoration Ecosystem Project (SERPRO)** by PT Kalamanthana Alam Lestari.
** Disclimer, this website is just for portfolio @2026 | Ziyadatul Hikmah

## Boundary and scope model

The WebGIS uses two official spatial layers within one unified SERPRO project landscape:

- **SERPRO Carbon Project Zone** — the primary spatial envelope supplied in `ProjectZone.kmz` (official area: 150,142.5436 ha).
- **SERPRO Project Area** — the contained PT Kalamanthana Alam Lestari concession/project-area subset from `KAL_Boundary_Split.kml` (official area: 31,685.38489 ha).

Spatial analysis supplied by the project GIS confirms that the Project Area is effectively fully contained within the Carbon Project Zone. The intersection is approximately equal to the Project Area, within numerical geometry tolerance.

The Overview dashboard implements a hierarchical **Scope Engine**:

```text
SERPRO Project Landscape
        ↓
SERPRO Carbon Project Zone
        ↓
SERPRO Project Area
```

Scope-specific analytics can later be spatially filtered using the same hierarchy for rainfall, temperature, fire, vegetation, hydrology, disturbance and MRV indicators.

## MVP

The first release focuses on:

- 🌿 Overview dashboard
- 🗺️ Interactive WebGIS
- 🧭 Project Landscape Summary
- 🧭 Hierarchical Scope Engine
- 🌧 Climate monitoring
- 🔥 Fire monitoring
- 🌿 Vegetation / NDVI monitoring
- 🚨 Alert center
- 📊 Climate Risk Index prototype

> **Current status:** UI/UX and application architecture are in MVP stage. Monitoring values are demo data; the two WebGIS boundary layers and spatial relationship metrics are official project inputs supplied for this application.

## Architecture

```text
Official boundaries + spatial relationship
                 ↓
            Scope Engine
                 ↓
       Climate / satellite data
                 ↓
          Data processing
                 ↓
        GitHub / data store
                 ↓
             Streamlit
                 ↓
       WebGIS + analytics + alerts
```

## Repository structure

```text
├── app.py
├── pages/
│   ├── 1_🌧_Climate_Monitoring.py
│   ├── 2_🔥_Fire_Monitoring.py
│   └── 3_🌿_Vegetation_Monitoring.py
├── utils/
│   ├── demo_data.py
│   ├── map.py
│   ├── scope_engine.py
│   └── ui.py
├── data/
│   ├── static/boundaries/
│   └── processed/
├── scripts/
├── .github/workflows/
├── requirements.txt
└── README.md
```

## Planned live-data integrations

1. CHIRPS — rainfall
2. ERA5-Land — temperature / climate variables
3. VIIRS — near-real-time fire hotspots
4. Sentinel-2 — vegetation indices
5. Monitoring points
6. Automated data refresh through GitHub Actions

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Development roadmap

**MVP → Scope-aware live climate feeds → automated hotspot monitoring → vegetation change → peatland hydrology → MRV & carbon risk → reporting/export.**
