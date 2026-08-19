from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from utils.climate.bmkg import BMKG_LOCATIONS, load_bmkg_forecast
from utils.climate.bmkg_idw import (
    PROJECT_AREA_PATH,
    PROJECT_ZONE_PATH,
    interpolate_forecast_to_project_zone,
)

OUT_DIR = Path("data/processed/climate/bmkg")
RAW_OUT = OUT_DIR / "forecast_latest.csv"
META_OUT = OUT_DIR / "forecast_metadata.json"
ZONE_SURFACE_OUT = OUT_DIR / "forecast_surface_project_zone_latest.geojson"
AREA_SURFACE_OUT = OUT_DIR / "forecast_surface_project_area_latest.geojson"
# Backward-compatible alias: the existing dashboard map can continue to read the
# generic surface, which represents the Carbon Project Zone.
LEGACY_SURFACE_OUT = OUT_DIR / "forecast_surface_latest.geojson"

SURFACE_VARIABLES = {
    "precipitation_mm": "precipitation_mm",
    "temperature_c": "temperature_c",
    "humidity_pct": "humidity_pct",
    "cloud_cover_pct": "cloud_cover_pct",
    "wind_speed_ms": "wind_speed_ms",
}

BOUNDARIES = {
    "project_zone": {
        "path": PROJECT_ZONE_PATH,
        "label": "SERPRO Carbon Project Zone",
        "output": ZONE_SURFACE_OUT,
    },
    "project_area": {
        "path": PROJECT_AREA_PATH,
        "label": "SERPRO Project Area",
        "output": AREA_SURFACE_OUT,
    },
}


def build_surface(forecast: pd.DataFrame, forecast_time: pd.Timestamp, boundary: dict) -> object:
    surface = None
    for output_name, column in SURFACE_VARIABLES.items():
        try:
            part = interpolate_forecast_to_project_zone(
                forecast,
                value_column=column,
                when=forecast_time,
                resolution_m=1000,
                power=2.0,
                boundary_path=boundary["path"],
                boundary_label=boundary["label"],
            )
            part = part.rename(columns={column: output_name})
            keep = ["geometry", output_name]
            part = part[keep]
            surface = part if surface is None else surface.join(part.drop(columns="geometry"))
        except ValueError as exc:
            print(f"Skipping {boundary['label']} / {column}: {exc}")

    if surface is None or surface.empty:
        raise SystemExit(f"BMKG ingestion failed: IDW surface could not be built for {boundary['label']}")

    surface["forecast_datetime"] = forecast_time.isoformat()
    surface["source"] = "BMKG ADM4 forecast points + IDW"
    surface["boundary"] = boundary["label"]
    surface["interpretation"] = "Forecast surface clipped to project boundary; not direct station observation"
    surface.to_file(boundary["output"], driver="GeoJSON")
    return surface


def main() -> None:
    forecast, meta = load_bmkg_forecast(timeout=30)
    if forecast.empty:
        raise SystemExit("BMKG ingestion failed: no forecast records returned")

    expected = set(BMKG_LOCATIONS)
    observed = set(forecast["location"].dropna().unique())
    missing = expected - observed
    if missing:
        raise SystemExit(f"BMKG ingestion failed: missing locations: {sorted(missing)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    forecast = forecast.sort_values(["location", "local_datetime"]).copy()
    forecast.to_csv(RAW_OUT, index=False)

    common_times: set[pd.Timestamp] | None = None
    for _, group in forecast.groupby("location"):
        times = set(pd.to_datetime(group["local_datetime"], errors="coerce").dropna())
        common_times = times if common_times is None else common_times & times
    if not common_times:
        raise SystemExit("BMKG ingestion failed: no common forecast timestamp across five villages")

    forecast_time = max(common_times)
    surfaces = {}
    for key, boundary in BOUNDARIES.items():
        surfaces[key] = build_surface(forecast, forecast_time, boundary)

    # Keep the historical generic output as the Project Zone product so existing
    # consumers do not break while the dashboard migrates to explicit scope files.
    surfaces["project_zone"].to_file(LEGACY_SURFACE_OUT, driver="GeoJSON")

    quality = meta.get("quality")
    quality_records = quality.to_dict(orient="records") if quality is not None else []
    metadata = {
        "source": "BMKG Open Data",
        "data_type": "forecast",
        "endpoint_type": "3-day weather forecast",
        "native_interval": "3-hour",
        "pilot_locations": list(BMKG_LOCATIONS.keys()),
        "forecast_timestamp_used_for_idw": forecast_time.isoformat(),
        "idw_power": 2.0,
        "idw_resolution_m": 1000,
        "boundaries": {
            "project_zone": "SERPRO Carbon Project Zone",
            "project_area": "SERPRO Project Area",
        },
        "interpretation": "Forecast conditions from five BMKG ADM4 pilot villages are spatially interpolated with IDW and clipped separately to the SERPRO Project Area and Carbon Project Zone. These are forecast surfaces, not direct station observations, and are excluded from historical Climate Risk calculations.",
        "fetched_at_utc": meta.get("fetched_at_utc"),
        "quality": quality_records,
        "outputs": {
            "project_zone": str(ZONE_SURFACE_OUT),
            "project_area": str(AREA_SURFACE_OUT),
            "legacy_project_zone": str(LEGACY_SURFACE_OUT),
        },
    }
    META_OUT.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("BMKG forecast ingestion completed")
    print(f"Locations: {len(observed)}/5")
    print(f"Forecast timestamp: {forecast_time}")
    print(f"Raw records: {len(forecast)}")
    for key, surface in surfaces.items():
        print(f"{key} IDW cells: {len(surface)}")
    print(f"Project Zone output: {ZONE_SURFACE_OUT}")
    print(f"Project Area output: {AREA_SURFACE_OUT}")


if __name__ == "__main__":
    main()
