"""Compare current GPM rainfall with CHIRPS daily climatology.

Daily anomaly is compared with the matching calendar day in the 1991-2020
CHIRPS climatology. Rolling 7-day and 30-day anomalies are also calculated
from comparable daily baseline sums. The climate status is based on the
30-day anomaly when a complete 30-day current window is available.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CURRENT = Path("data/processed/climate/rainfall/rainfall_daily.csv")
DAILY_CLIM = Path("data/processed/climate/rainfall/chirps_daily_climatology_1991_2020.csv")
OUTPUT = Path("data/processed/climate/rainfall/rainfall_anomaly.csv")
META = Path("data/processed/climate/rainfall/rainfall_anomaly_metadata.json")


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


def add_rolling_metrics(df: pd.DataFrame, clim: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["scope", "date"]).copy()
    clim_key = clim[["month", "day", "scope", "normal_mean_mm"]].copy()

    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df = df.merge(clim_key, on=["scope", "month", "day"], how="left", validate="many_to_one")
    if df["normal_mean_mm"].isna().any():
        raise RuntimeError("Missing daily CHIRPS climatology for one or more current rainfall records.")
    df = df.rename(columns={"normal_mean_mm": "daily_normal_mean_mm"})
    df["daily_anomaly_mm"] = df["rainfall_mm"] - df["daily_normal_mean_mm"]
    df["daily_anomaly_pct"] = df["daily_anomaly_mm"] / df["daily_normal_mean_mm"] * 100.0

    out = []
    for scope, group in df.groupby("scope", sort=False):
        group = group.sort_values("date").copy()
        group["obs_count_7d"] = group["rainfall_mm"].rolling(7, min_periods=7).count()
        group["obs_count_30d"] = group["rainfall_mm"].rolling(30, min_periods=30).count()
        group["rainfall_7d_mm"] = group["rainfall_mm"].rolling(7, min_periods=1).sum()
        group["rainfall_30d_mm"] = group["rainfall_mm"].rolling(30, min_periods=1).sum()
        group["normal_7d_mm"] = group["daily_normal_mean_mm"].rolling(7, min_periods=1).sum()
        group["normal_30d_mm"] = group["daily_normal_mean_mm"].rolling(30, min_periods=1).sum()
        group["anomaly_7d_mm"] = group["rainfall_7d_mm"] - group["normal_7d_mm"]
        group["anomaly_30d_mm"] = group["rainfall_30d_mm"] - group["normal_30d_mm"]
        group["anomaly_7d_pct"] = group["anomaly_7d_mm"] / group["normal_7d_mm"] * 100.0
        group["anomaly_30d_pct"] = group["anomaly_30d_mm"] / group["normal_30d_mm"] * 100.0
        group["climate_status"] = group.apply(
            lambda r: classify(float(r["anomaly_30d_pct"])) if r["obs_count_30d"] == 30 else "insufficient_data",
            axis=1,
        )
        out.append(group)
    return pd.concat(out, ignore_index=True)


def main() -> None:
    if not CURRENT.exists() or not DAILY_CLIM.exists():
        raise RuntimeError("Current rainfall and daily CHIRPS climatology files are required.")

    cur = pd.read_csv(CURRENT, parse_dates=["date"])
    clim = pd.read_csv(DAILY_CLIM)
    result = add_rolling_metrics(cur, clim)

    # Keep historical/statistical fields needed by the dashboard and audit trail.
    result = result[
        [
            "date", "scope", "rainfall_mm", "daily_normal_mean_mm",
            "daily_anomaly_mm", "daily_anomaly_pct", "rainfall_7d_mm", "normal_7d_mm",
            "anomaly_7d_mm", "anomaly_7d_pct", "rainfall_30d_mm", "normal_30d_mm",
            "anomaly_30d_mm", "anomaly_30d_pct", "obs_count_7d", "obs_count_30d",
            "climate_status", "source", "processing_time_utc",
        ]
    ].sort_values(["date", "scope"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False, float_format="%.4f")

    metadata = {
        "historical_source": "CHIRPS v2 Final",
        "baseline_period": "1991-2020",
        "current_source": "NASA GPM IMERG V07",
        "daily_comparison": "same calendar month-day",
        "status_basis": "30-day rainfall anomaly percent when 30 current observations are available",
        "status_thresholds_pct": {
            "very_wet": ">= +50%",
            "wet": "+20% to < +50%",
            "normal": "> -20% to < +20%",
            "dry": "-50% to <= -20%",
            "drought": "<= -50%",
            "insufficient_data": "fewer than 30 current daily observations",
        },
        "records": int(len(result)),
    }
    META.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {len(result)} anomaly records to {OUTPUT}")


if __name__ == "__main__":
    main()
