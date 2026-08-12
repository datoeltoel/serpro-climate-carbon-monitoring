"""Build historical and current rainfall SPI-3/SPI-6 indicators.

Historical distribution: CHIRPS v2 Final monthly rainfall, 1981-2025.
Current rainfall: GPM IMERG daily rainfall, aggregated to monthly.
SPI is only reported for current periods when enough current monthly history exists.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gamma, norm

HIST = Path("data/processed/climate/rainfall/chirps_monthly_1981_2025.csv")
CURRENT = Path("data/processed/climate/rainfall/rainfall_daily.csv")
OUTPUT = Path("data/processed/climate/rainfall/spi_current.csv")
HIST_OUTPUT = Path("data/processed/climate/rainfall/spi_historical_1981_2025.csv")
META = Path("data/processed/climate/rainfall/spi_metadata.json")


def fit_spi(values: pd.Series, target: float) -> float:
    vals = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) < 20 or not np.isfinite(target):
        return np.nan
    zero_prob = float(np.mean(vals <= 0))
    positive = vals[vals > 0]
    if len(positive) < 10 or target < 0:
        return np.nan
    shape, _, scale = gamma.fit(positive, floc=0)
    cdf = zero_prob + (1.0 - zero_prob) * gamma.cdf(target, shape, loc=0, scale=scale)
    cdf = float(np.clip(cdf, 1e-6, 1 - 1e-6))
    return float(norm.ppf(cdf))


def classify_spi(value: float) -> str:
    if not np.isfinite(value):
        return "insufficient_data"
    if value >= 2.0:
        return "extremely_wet"
    if value >= 1.5:
        return "very_wet"
    if value >= 1.0:
        return "wet"
    if value > -1.0:
        return "normal"
    if value > -1.5:
        return "moderate_dry"
    if value > -2.0:
        return "severe_drought"
    return "extreme_drought"


def historical_spi(hist: pd.DataFrame, window: int) -> pd.DataFrame:
    out = []
    for scope, group in hist.groupby("scope"):
        group = group.sort_values(["year", "month"]).copy()
        group["date"] = pd.to_datetime(dict(year=group.year, month=group.month, day=1))
        group[f"rainfall_{window}m_mm"] = group["rainfall_mm"].rolling(window, min_periods=window).sum()
        group["month_key"] = group["month"]
        for month, mg in group.groupby("month_key"):
            idx = mg.index
            for i in idx:
                target = group.loc[i, f"rainfall_{window}m_mm"]
                if pd.isna(target):
                    continue
                # Compare each calendar month to the historical distribution of the same ending month.
                sample = mg[f"rainfall_{window}m_mm"].dropna()
                spi = fit_spi(sample, float(target))
                out.append({
                    "date": group.loc[i, "date"].date().isoformat(),
                    "scope": scope,
                    "period": f"SPI-{window}",
                    "rainfall_accum_mm": float(target),
                    "spi": spi,
                    "spi_status": classify_spi(spi),
                    "source": "CHIRPS v2 Final",
                })
    return pd.DataFrame(out)


def current_spi(hist: pd.DataFrame, cur: pd.DataFrame, window: int) -> pd.DataFrame:
    if cur.empty:
        return pd.DataFrame()
    monthly = cur.copy()
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly["year"] = monthly["date"].dt.year
    monthly["month"] = monthly["date"].dt.month
    monthly = monthly.groupby(["scope", "year", "month"], as_index=False)["rainfall_mm"].sum()
    out = []
    for scope, group in monthly.groupby("scope"):
        group = group.sort_values(["year", "month"]).copy()
        group["date"] = pd.to_datetime(dict(year=group.year, month=group.month, day=1))
        group["accum"] = group["rainfall_mm"].rolling(window, min_periods=window).sum()
        hist_scope = hist[hist["scope"] == scope].copy()
        hist_scope["date"] = pd.to_datetime(dict(year=hist_scope.year, month=hist_scope.month, day=1))
        hist_scope[f"accum"] = hist_scope["rainfall_mm"].rolling(window, min_periods=window).sum()
        for _, row in group.iterrows():
            target = row["accum"]
            if pd.isna(target):
                spi = np.nan
            else:
                # Match the ending calendar month against historical accumulated rainfall.
                sample = hist_scope.loc[hist_scope["month"] == row["month"], "accum"].dropna()
                spi = fit_spi(sample, float(target))
            out.append({
                "date": row["date"].date().isoformat(),
                "scope": scope,
                "period": f"SPI-{window}",
                "rainfall_accum_mm": float(target) if pd.notna(target) else np.nan,
                "spi": spi,
                "spi_status": classify_spi(spi),
                "source": "NASA GPM IMERG V07 + CHIRPS historical distribution",
            })
    return pd.DataFrame(out)


def main() -> None:
    if not HIST.exists() or not CURRENT.exists():
        raise RuntimeError("CHIRPS monthly history and GPM daily rainfall files are required.")
    hist = pd.read_csv(HIST)
    cur = pd.read_csv(CURRENT, parse_dates=["date"])

    historical = pd.concat([historical_spi(hist, 3), historical_spi(hist, 6)], ignore_index=True)
    current = pd.concat([current_spi(hist, cur, 3), current_spi(hist, cur, 6)], ignore_index=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    current.to_csv(OUTPUT, index=False, float_format="%.4f")
    historical.to_csv(HIST_OUTPUT, index=False, float_format="%.4f")

    metadata = {
        "historical_source": "CHIRPS v2 Final",
        "historical_period": "1981-2025",
        "current_source": "NASA GPM IMERG V07",
        "indices": ["SPI-3", "SPI-6"],
        "current_rule": "SPI is reported only when enough current monthly observations exist for the requested accumulation window.",
        "classification": {
            "extremely_wet": ">= 2.0",
            "very_wet": "1.5 to < 2.0",
            "wet": "1.0 to < 1.5",
            "normal": "> -1.0 to < 1.0",
            "moderate_dry": "-1.5 to <= -1.0",
            "severe_drought": "-2.0 to <= -1.5",
            "extreme_drought": "<= -2.0",
        },
        "current_records": int(len(current)),
        "historical_records": int(len(historical)),
    }
    META.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {len(current)} current SPI records to {OUTPUT}")
    print(f"Wrote {len(historical)} historical SPI records to {HIST_OUTPUT}")


if __name__ == "__main__":
    main()
