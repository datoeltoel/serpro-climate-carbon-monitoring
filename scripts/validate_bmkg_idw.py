from __future__ import annotations

import pandas as pd

from utils.climate.bmkg import BMKG_LOCATIONS, load_bmkg_forecast
from utils.climate.bmkg_idw import (
    PROJECT_AREA_PATH,
    PROJECT_ZONE_PATH,
    interpolate_forecast_to_project_zone,
)

EXPECTED = set(BMKG_LOCATIONS)
BOUNDARIES = {
    "Project Zone": PROJECT_ZONE_PATH,
    "Project Area": PROJECT_AREA_PATH,
}


def main() -> None:
    forecast, meta = load_bmkg_forecast(timeout=20)
    quality = meta["quality"]
    if forecast.empty:
        raise SystemExit("BMKG validation failed: no forecast records returned")

    observed = set(forecast["location"].dropna().unique())
    missing = EXPECTED - observed
    if missing:
        raise SystemExit(f"BMKG validation failed: missing locations: {sorted(missing)}")

    coord_check = forecast.groupby("location")[["latitude", "longitude"]].first()
    if coord_check.isna().any().any():
        raise SystemExit("BMKG validation failed: one or more village coordinates are missing")

    common_times = None
    for _, group in forecast.groupby("location"):
        times = set(pd.to_datetime(group["local_datetime"], errors="coerce").dropna())
        common_times = times if common_times is None else common_times & times
    if not common_times:
        raise SystemExit("BMKG validation failed: no common forecast timestamp across five villages")

    when = sorted(common_times)[0]
    for boundary_label, boundary_path in BOUNDARIES.items():
        surface = interpolate_forecast_to_project_zone(
            forecast,
            value_column="precipitation_mm",
            when=when,
            resolution_m=1000,
            power=2.0,
            boundary_path=boundary_path,
            boundary_label=boundary_label,
        )
        if surface.empty or surface["precipitation_mm"].dropna().empty:
            raise SystemExit(f"IDW validation failed: no interpolated values inside {boundary_label}")
        if set(surface["boundary"].dropna().unique()) != {boundary_label}:
            raise SystemExit(f"IDW validation failed: boundary label mismatch for {boundary_label}")
        print(f"{boundary_label}: {len(surface)} clipped grid cells")

    print("BMKG + IDW boundary clipping validation passed")
    print(f"Locations: {len(observed)}/5")
    print(f"Common forecast time: {when}")
    print(f"Quality records:\n{quality.to_string(index=False)}")


if __name__ == "__main__":
    main()
