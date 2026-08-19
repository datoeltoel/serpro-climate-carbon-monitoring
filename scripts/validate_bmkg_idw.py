from __future__ import annotations

import pandas as pd

from utils.climate.bmkg import BMKG_LOCATIONS, load_bmkg_forecast
from utils.climate.bmkg_idw import interpolate_forecast_to_project_zone


EXPECTED = set(BMKG_LOCATIONS)


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
    surface = interpolate_forecast_to_project_zone(
        forecast,
        value_column="precipitation_mm",
        when=when,
        resolution_m=1000,
        power=2.0,
    )
    if surface.empty or surface["precipitation_mm"].dropna().empty:
        raise SystemExit("IDW validation failed: no interpolated Project Zone values")

    print("BMKG + IDW validation passed")
    print(f"Locations: {len(observed)}/5")
    print(f"Common forecast time: {when}")
    print(f"Grid cells: {len(surface)}")
    print(f"Variable: precipitation_mm")
    print(f"Quality records:\n{quality.to_string(index=False)}")


if __name__ == "__main__":
    main()
