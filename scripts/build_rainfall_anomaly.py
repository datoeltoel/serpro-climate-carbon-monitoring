"""Compare current GPM rainfall with CHIRPS 1991-2020 climatology."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CURRENT = Path("data/processed/climate/rainfall/rainfall_daily.csv")
CLIM = Path("data/processed/climate/rainfall/chirps_climatology_1991_2020.csv")
OUTPUT = Path("data/processed/climate/rainfall/rainfall_anomaly.csv")


def classify(anomaly_pct: float) -> str:
    if anomaly_pct >= 50:
        return "very_wet"
    if anomaly_pct >= 20:
        return "wet"
    if anomaly_pct > -20:
        return "normal"
    if anomaly_pct > -50:
        return "dry"
    return "drought"


def main() -> None:
    if not CURRENT.exists() or not CLIM.exists():
        raise RuntimeError("Current rainfall and CHIRPS climatology files are required.")

    cur = pd.read_csv(CURRENT, parse_dates=["date"])
    clim = pd.read_csv(CLIM)
    cur["month"] = cur["date"].dt.month

    merged = cur.merge(clim, on=["scope", "month"], how="left", validate="many_to_one")
    if merged["normal_mean_mm"].isna().any():
        raise RuntimeError("Missing CHIRPS climatology for one or more current rainfall records.")

    merged["anomaly_mm"] = merged["rainfall_mm"] - merged["normal_mean_mm"]
    merged["anomaly_pct"] = merged["anomaly_mm"] / merged["normal_mean_mm"] * 100.0
    merged["z_score"] = merged["anomaly_mm"] / merged["normal_std_mm"]
    merged["percentile_estimate"] = (
        (merged["rainfall_mm"] - merged["p10_mm"]) /
        (merged["p90_mm"] - merged["p10_mm"]) * 80.0 + 10.0
    ).clip(0, 100)
    merged["climate_status"] = merged["anomaly_pct"].apply(classify)
    merged["baseline_period"] = merged["normal_period"]
    merged["current_source"] = merged["source"]

    cols = [
        "date", "scope", "rainfall_mm", "normal_mean_mm", "normal_std_mm",
        "anomaly_mm", "anomaly_pct", "z_score", "percentile_estimate",
        "p10_mm", "p25_mm", "median_mm", "p75_mm", "p90_mm",
        "climate_status", "baseline_period", "current_source", "processing_time_utc",
    ]
    out = merged[cols].sort_values(["date", "scope"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False, float_format="%.4f")

    metadata = {
        "baseline_source": "CHIRPS v2 Final",
        "baseline_period": "1991-2020",
        "current_source": "GPM IMERG V07",
        "status_method": "monthly rainfall anomaly percent against CHIRPS 1991-2020 mean",
        "status_thresholds_pct": {
            "very_wet": ">= +50%",
            "wet": "+20% to < +50%",
            "normal": "> -20% to < +20%",
            "dry": "-50% to <= -20%",
            "drought": "<= -50%",
        },
    }
    Path(OUTPUT.parent / "rainfall_anomaly_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(out)} anomaly records to {OUTPUT}")


if __name__ == "__main__":
    main()
