from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from utils.climate.bmkg import BMKG_LOCATIONS, load_bmkg_forecast
from utils.climate.bmkg_idw import interpolate_forecast_to_project_zone

OUT_DIR = Path("data/processed/climate/bmkg")
RAW_OUT = OUT_DIR / "forecast_latest.csv"
META_OUT = OUT_DIR / "forecast_metadata.json"
SURFACE_OUT = OUT_DIR / "forecast_surface_latest.geojson"

SURFACE_VARIABLES = {
    "precipitation_mm": "precipitation_mm",
    "temperature_c": "temperature_c",
    "humidity_pct": "humidity_pct",
    "cloud_cover_pct": "cloud_cover_pct",
    "wind_speed_ms": "wind_speed_ms",
}


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

    # Use the latest common forecast timestamp so the spatial product always
    # represents the newest comparable forecast across all five pilot villages.
    forecast_time = max(common_times)
    surface = None
    for output_name, column in SURFACE_VARIABLES.items():
        try:
            part = interpolate_forecast_to_project_zone(
                forecast,
                value_column=column,
                when=forecast_time,
                resolution_m=1000,
                power=2.0,
            )
            part = part.rename(columns={column: output_name})
            keep = ["geometry", output_name]
            part = part[keep]
            surface = part if surface is None else surface.join(part.drop(columns="geometry"))
        except ValueError as exc:
            print(f"Skipping {column}: {exc}")

    if surface is None or surface.empty:
        raise SystemExit("BMKG ingestion failed: IDW surface could not be built")

    surface["forecast_datetime"] = forecast_time.isoformat()
    surface["source"] = "BMKG ADM4 forecast points + IDW"
    surface["interpretation"] = "Forecast surface; not direct station observation"
    surface.to_file(SURFACE_OUT, driver="GeoJSON")

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
        "project_zone": "SERPRO Carbon Project Zone",
        "interpretation": "Forecast conditions interpolated from five BMKG ADM4 pilot villages using IDW. Not direct station observations and excluded from historical Climate Risk calculations.",
        "fetched_at_utc": meta.get("fetched_at_utc"),
        "quality": quality_records,
    }
    META_OUT.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("BMKG forecast ingestion completed")
    print(f"Locations: {len(observed)}/5")
    print(f"Forecast timestamp: {forecast_time}")
    print(f"Raw records: {len(forecast)}")
    print(f"IDW grid cells: {len(surface)}")
    print(f"Raw output: {RAW_OUT}")
    print(f"Surface output: {SURFACE_OUT}")


if __name__ == "__main__":
    main()
