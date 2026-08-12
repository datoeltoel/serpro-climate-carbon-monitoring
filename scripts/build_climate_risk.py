"""Build a rainfall-based SERPRO climate risk score.

v1 is intentionally provisional: it uses 30-day rainfall anomaly and any
available SPI-3/SPI-6 values. Vegetation moisture and fire indicators will be
added as separate inputs before this becomes a full operational risk engine.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ANOMALY = Path("data/processed/climate/rainfall/rainfall_anomaly.csv")
SPI = Path("data/processed/climate/rainfall/spi_current.csv")
OUTPUT = Path("data/processed/climate/risk/climate_risk.csv")
META = Path("data/processed/climate/risk/climate_risk_metadata.json")


def anomaly_points(v: float) -> float:
    if not np.isfinite(v):
        return 0.0
    if v <= -50:
        return 4.0
    if v <= -30:
        return 3.0
    if v <= -20:
        return 2.0
    if v < 0:
        return 1.0
    if v >= 50:
        return 0.0
    return 0.0


def spi_points(v: float) -> float:
    if not np.isfinite(v):
        return 0.0
    if v <= -2.0:
        return 4.0
    if v <= -1.5:
        return 3.0
    if v <= -1.0:
        return 2.0
    if v < 0:
        return 1.0
    return 0.0


def risk_label(score: float) -> str:
    if score >= 6:
        return "very_high"
    if score >= 4:
        return "high"
    if score >= 2:
        return "moderate"
    return "low"


def main() -> None:
    if not ANOMALY.exists():
        raise RuntimeError("Rainfall anomaly data is required.")

    anomaly = pd.read_csv(ANOMALY, parse_dates=["date"])
    if anomaly.empty:
        raise RuntimeError("Rainfall anomaly data is empty.")

    latest = anomaly.sort_values("date").groupby("scope", as_index=False).tail(1).copy()

    if SPI.exists():
        spi = pd.read_csv(SPI, parse_dates=["date"])
        latest_spi = spi.sort_values("date").groupby(["scope", "period"], as_index=False).tail(1)
        piv = latest_spi.pivot(index="scope", columns="period", values="spi").reset_index()
        piv.columns.name = None
        piv = piv.rename(columns={"SPI-3": "spi_3", "SPI-6": "spi_6"})
        latest = latest.merge(piv, on="scope", how="left")
    else:
        latest["spi_3"] = np.nan
        latest["spi_6"] = np.nan

    rows = []
    for _, r in latest.iterrows():
        a30 = float(r.get("anomaly_30d_pct", np.nan))
        s3 = float(r.get("spi_3", np.nan))
        s6 = float(r.get("spi_6", np.nan))
        a_points = anomaly_points(a30)
        s_points = max(spi_points(s3), spi_points(s6))
        score = a_points + s_points
        available_inputs = int(np.isfinite(a30)) + int(np.isfinite(s3)) + int(np.isfinite(s6))
        status = "provisional" if available_inputs < 3 else "operational"
        rows.append({
            "date": r["date"].date().isoformat(),
            "scope": r["scope"],
            "anomaly_30d_pct": a30,
            "spi_3": s3,
            "spi_6": s6,
            "rainfall_risk_points": score,
            "risk_level": risk_label(score),
            "risk_basis": status,
            "assessment": "Rainfall-only climate risk; add NDMI and fire indicators for full operational risk.",
        })

    out = pd.DataFrame(rows).sort_values(["date", "scope"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False, float_format="%.4f")
    META.write_text(json.dumps({
        "version": "v1",
        "scope": ["carbon_project_zone", "project_area"],
        "inputs": ["30-day rainfall anomaly", "SPI-3", "SPI-6"],
        "status": "provisional until vegetation moisture and fire indicators are integrated",
        "risk_levels": {"low": "0-1", "moderate": "2-3", "high": "4-5", "very_high": ">=6"},
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(out)} climate risk records to {OUTPUT}")


if __name__ == "__main__":
    main()
