# SERPRO Climate & Carbon Monitoring

Climate intelligence and spatial monitoring platform for the **Seruyan Restoration Ecosystem Project (SERPRO)** by PT Kalamanthana Alam Lestari.

## MVP

The first release focuses on:

- 🌿 Overview dashboard
- 🗺️ Interactive WebGIS
- 🌧 Climate monitoring
- 🔥 Fire monitoring
- 🌿 Vegetation / NDVI monitoring
- 🚨 Alert center
- 📊 Climate Risk Index prototype

> **Current status:** UI/UX and application architecture are in MVP stage. Values and map layers are demo data and are not official project measurements.

## Architecture

```text
Public climate / satellite data
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
│   └── ui.py
├── data/
│   ├── static/
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
5. Official project boundary and monitoring points
6. Automated data refresh through GitHub Actions

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Development roadmap

**MVP → Live climate feeds → automated hotspot monitoring → vegetation change → peatland hydrology → MRV & carbon risk → reporting/export.**
