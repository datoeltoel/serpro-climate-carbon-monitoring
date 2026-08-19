"""Analyze the long-term CHIRPS monthly rainfall baseline for SERPRO.

Inputs
------
data/processed/climate/rainfall/chirps_monthly_1981_2025.csv

data/processed/climate/rainfall/chirps_climatology_1991_2020.csv

Outputs
-------
data/processed/climate/rainfall/chirps_annual_1981_2025.csv
  Annual rainfall totals and year-on-year change.

data/processed/climate/rainfall/chirps_monthly_30y_1996_2025.csv
  30-year monthly observation series with climatological normal and anomaly.

data/processed/climate/rainfall/chirps_annual_anomaly_1996_2025.csv
  Annual rainfall anomaly relative to the 1991-2020 normal.

data/processed/climate/rainfall/chirps_30y_summary_1996_2025.csv
  Scope-level 30-year statistics and linear trend.

data/processed/climate/rainfall/chirps_analysis_metadata.json
  Reproducibility metadata.

The CHIRPS 1991-2020 normal is retained as the climatological reference.
The 30-year analysis window is 1996-2025 so the dashboard can report a
complete recent 30-year historical period while preserving the standard
1991-2020 climatology as the anomaly baseline.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import linregress

BASE = Path("data/processed/climate/rainfall")
MONTHLY_INPUT = BASE / "chirps_monthly_1981_2025.csv"
CLIM_INPUT = BASE / "chirps_climatology_1991_2020.csv"
ANNUAL_OUTPUT = BASE / "chirps_annual_1981_2025.csv"
MONTHLY_30Y_OUTPUT = BASE / "chirps_monthly_30y_1996_2025.csv"
ANNUAL_ANOM_OUTPUT = BASE / "chirps_annual_anomaly_1996_2025.csv"
SUMMARY_OUTPUT = BASE / "chirps_30y_summary_1996_2025.csv"
METADATA_OUTPUT = BASE / "chirps_analysis_metadata.json"
START_YEAR = 1996
END_YEAR = 2025
NORMAL_START = 1991
NORMAL_END = 2020


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not MONTHLY_INPUT.exists():
        raise FileNotFoundError(f"Missing input: {MONTHLY_INPUT}")
    if not CLIM_INPUT.exists():
        raise FileNotFoundError(f"Missing input: {CLIM_INPUT}")

    monthly = pd.read_csv(MONTHLY_INPUT)
    climatology = pd.read_csv(CLIM_INPUT)

    required_monthly = {"year", "month", "scope", "rainfall_mm"}
    required_clim = {"scope", "month", "normal_mean_mm"}
    if not required_monthly.issubset(monthly.columns):
        raise ValueError(f"CHIRPS monthly file missing columns: {required_monthly - set(monthly.columns)}")
    if not required_clim.issubset(climatology.columns):
        raise ValueError(f"CHIRPS climatology file missing columns: {required_clim - set(climatology.columns)}")

    monthly["year"] = pd.to_numeric(monthly["year"], errors="coerce").astype("Int64")
    monthly["month"] = pd.to_numeric(monthly["month"], errors="coerce").astype("Int64")
    monthly["rainfall_mm"] = pd.to_numeric(monthly["rainfall_mm"], errors="coerce")
    monthly = monthly.dropna(subset=["year", "month", "rainfall_mm"]).copy()
    monthly["year"] = monthly["year"].astype(int)
    monthly["month"] = monthly["month"].astype(int)

    climatology["month"] = pd.to_numeric(climatology["month"], errors="coerce").astype(int)
    climatology["normal_mean_mm"] = pd.to_numeric(climatology["normal_mean_mm"], errors="coerce")
    return monthly, climatology


def add_anomaly(monthly: pd.DataFrame, climatology: pd.DataFrame) -> pd.DataFrame:
    normal = climatology[["scope", "month", "normal_mean_mm"]].copy()
    out = monthly.merge(normal, on=["scope", "month"], how="left", validate="many_to_one")
    out["anomaly_mm"] = out["rainfall_mm"] - out["normal_mean_mm"]
    out["anomaly_pct"] = np.where(
        out["normal_mean_mm"].abs() > 1e-9,
        out["anomaly_mm"] / out["normal_mean_mm"] * 100.0,
        np.nan,
    )
    out["period"] = np.where(
        out["year"].between(START_YEAR, END_YEAR),
        f"{START_YEAR}-{END_YEAR}",
        "outside_30y_window",
    )
    return out


def annual_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    annual = (
        monthly.groupby(["scope", "year"], as_index=False)["rainfall_mm"]
        .sum()
        .rename(columns={"rainfall_mm": "annual_rainfall_mm"})
    )
    annual["yoy_change_mm"] = annual.groupby("scope")["annual_rainfall_mm"].diff()
    annual["yoy_change_pct"] = annual.groupby("scope")["annual_rainfall_mm"].pct_change() * 100.0
    return annual.sort_values(["scope", "year"])


def annual_anomaly(monthly_30y: pd.DataFrame) -> pd.DataFrame:
    # Sum monthly departures from the corresponding normal month. This is
    # equivalent to annual rainfall minus the 12-month climatological normal.
    out = (
        monthly_30y.groupby(["scope", "year"], as_index=False)
        .agg(
            annual_rainfall_mm=("rainfall_mm", "sum"),
            annual_normal_mm=("normal_mean_mm", "sum"),
            months_available=("rainfall_mm", "count"),
        )
    )
    out["annual_anomaly_mm"] = out["annual_rainfall_mm"] - out["annual_normal_mm"]
    out["annual_anomaly_pct"] = np.where(
        out["annual_normal_mm"].abs() > 1e-9,
        out["annual_anomaly_mm"] / out["annual_normal_mm"] * 100.0,
        np.nan,
    )
    out["complete_year"] = out["months_available"] == 12
    return out.sort_values(["scope", "year"])


def summary_30y(monthly_30y: pd.DataFrame, annual_anom: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for scope, grp in annual_anom.groupby("scope"):
        complete = grp[grp["complete_year"]].copy()
        if complete.empty:
            continue
        x = complete["year"].to_numpy(dtype=float)
        y = complete["annual_rainfall_mm"].to_numpy(dtype=float)
        reg = linregress(x, y) if len(complete) >= 2 else None
        normal = float(complete["annual_normal_mm"].mean())
        mean = float(y.mean())
        std = float(y.std(ddof=1)) if len(y) > 1 else 0.0
        wet = complete.loc[complete["annual_rainfall_mm"].idxmax()]
        dry = complete.loc[complete["annual_rainfall_mm"].idxmin()]
        monthly_scope = monthly_30y[monthly_30y["scope"] == scope]
        monthly_normal = monthly_scope.groupby("month")["normal_mean_mm"].first()
        wettest_month = int(monthly_normal.idxmax()) if not monthly_normal.empty else None
        driest_month = int(monthly_normal.idxmin()) if not monthly_normal.empty else None
        rows.append(
            {
                "scope": scope,
                "analysis_period": f"{START_YEAR}-{END_YEAR}",
                "years": int(len(complete)),
                "mean_annual_rainfall_mm": round(mean, 3),
                "annual_std_mm": round(std, 3),
                "annual_cv_pct": round(std / mean * 100.0, 3) if mean else np.nan,
                "mean_annual_normal_mm": round(normal, 3),
                "mean_annual_anomaly_mm": round(float(complete["annual_anomaly_mm"].mean()), 3),
                "mean_annual_anomaly_pct": round(float(complete["annual_anomaly_pct"].mean()), 3),
                "wettest_year": int(wet["year"]),
                "wettest_year_rainfall_mm": round(float(wet["annual_rainfall_mm"]), 3),
                "driest_year": int(dry["year"]),
                "driest_year_rainfall_mm": round(float(dry["annual_rainfall_mm"]), 3),
                "wettest_normal_month": wettest_month,
                "driest_normal_month": driest_month,
                "linear_trend_mm_per_year": round(float(reg.slope), 5) if reg else np.nan,
                "linear_trend_mm_per_decade": round(float(reg.slope * 10), 3) if reg else np.nan,
                "linear_trend_pct_per_decade": round(float(reg.slope * 10 / mean * 100), 3) if reg and mean else np.nan,
                "linear_trend_p_value": round(float(reg.pvalue), 6) if reg else np.nan,
                "trend_r_squared": round(float(reg.rvalue ** 2), 6) if reg else np.nan,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    monthly, climatology = load_inputs()
    enriched = add_anomaly(monthly, climatology)
    annual = annual_summary(monthly)
    monthly_30y = enriched[enriched["year"].between(START_YEAR, END_YEAR)].copy()
    annual_anom = annual_anomaly(monthly_30y)
    summary = summary_30y(monthly_30y, annual_anom)

    for frame, path in [
        (annual, ANNUAL_OUTPUT),
        (monthly_30y.sort_values(["scope", "year", "month"]), MONTHLY_30Y_OUTPUT),
        (annual_anom, ANNUAL_ANOM_OUTPUT),
        (summary, SUMMARY_OUTPUT),
    ]:
        frame.to_csv(path, index=False, float_format="%.4f")

    metadata = {
        "analysis": "CHIRPS long-term historical rainfall baseline",
        "input_monthly": str(MONTHLY_INPUT),
        "input_climatology": str(CLIM_INPUT),
        "source": "UCSB-CHG/CHIRPS/DAILY",
        "analysis_period": f"{START_YEAR}-{END_YEAR}",
        "climatology_period": f"{NORMAL_START}-{NORMAL_END}",
        "scope": sorted(monthly["scope"].astype(str).unique().tolist()),
        "methods": {
            "annual_rainfall": "sum of monthly CHIRPS precipitation",
            "monthly_anomaly": "observed monthly rainfall minus 1991-2020 normal month",
            "annual_anomaly": "sum of monthly departures from 1991-2020 normal",
            "trend": "ordinary least-squares linear regression of annual rainfall versus year",
            "trend_significance": "linear-regression p-value; not a Mann-Kendall test",
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "records": {
            "monthly_30y": int(len(monthly_30y)),
            "annual_30y": int(len(annual_anom)),
            "summary_scopes": int(len(summary)),
        },
    }
    METADATA_OUTPUT.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"CHIRPS analysis complete: {START_YEAR}-{END_YEAR}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
