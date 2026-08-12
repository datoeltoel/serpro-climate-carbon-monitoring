"""Build integrated SERPRO climate risk from rainfall, SPI, NDMI, and fire.

Risk v2 is an operational screening index, not a fire-danger model or carbon
accounting metric. It combines recent meteorological stress, vegetation
moisture trend, and active-fire density using explicit component scores.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ANOMALY = Path("data/processed/climate/rainfall/rainfall_anomaly.csv")
SPI = Path("data/processed/climate/rainfall/spi_current.csv")
NDMI = Path("data/processed/climate/vegetation/ndmi_daily.csv")
FIRE = Path("data/processed/climate/fire/fire_hotspots.csv")
OUTPUT = Path("data/processed/climate/risk/climate_risk_v2.csv")
META = Path("data/processed/climate/risk/climate_risk_v2_metadata.json")

AREAS_HA = {
    "carbon_project_zone": 150142.5436,
    "project_area": 31685.38489,
}


def score_anomaly(v: float) -> float:
    if not np.isfinite(v):
        return np.nan
    if v <= -50:
        return 4.0
    if v <= -30:
        return 3.0
    if v <= -20:
        return 2.0
    if v < 0:
        return 1.0
    return 0.0


def score_spi(v: float) -> float:
    if not np.isfinite(v):
        return 0.0
    if v <= -2:
        return 4.0
    if v <= -1.5:
        return 3.0
    if v <= -1:
        return 2.0
    if v < 0:
        return 1.0
    return 0.0


def score_ndmi_change(pct_change: float) -> float:
    if not np.isfinite(pct_change):
        return 0.0
    if pct_change <= -20:
        return 3.0
    if pct_change <= -10:
        return 2.0
    if pct_change <= -5:
        return 1.0
    return 0.0


def score_fire_density(density_per_10k: float) -> float:
    if not np.isfinite(density_per_10k):
        return 0.0
    if density_per_10k >= 2:
        return 4.0
    if density_per_10k >= 1:
        return 3.0
    if density_per_10k >= 0.5:
        return 2.0
    if density_per_10k > 0:
        return 1.0
    return 0.0


def risk_label(score: float) -> str:
    if score >= 9:
        return "very_high"
    if score >= 6:
        return "high"
    if score >= 3:
        return "moderate"
    return "low"


def latest_anomaly() -> pd.DataFrame:
    df = pd.read_csv(ANOMALY, parse_dates=["date"])
    if df.empty:
        return pd.DataFrame(columns=["scope", "date", "anomaly_30d_pct", "spi_3", "spi_6"])
    out = df.sort_values("date").groupby("scope", as_index=False).tail(1)[["scope", "date", "anomaly_30d_pct"]].copy()
    if SPI.exists():
        spi = pd.read_csv(SPI, parse_dates=["date"])
        if not spi.empty:
            s = spi.sort_values("date").groupby(["scope", "period"], as_index=False).tail(1)
            p = s.pivot(index="scope", columns="period", values="spi").reset_index()
            p.columns.name = None
            p = p.rename(columns={"SPI-3": "spi_3", "SPI-6": "spi_6"})
            out = out.merge(p, on="scope", how="left")
    if "spi_3" not in out:
        out["spi_3"] = np.nan
    if "spi_6" not in out:
        out["spi_6"] = np.nan
    return out


def ndmi_metrics() -> dict[str, dict[str, float]]:
    if not NDMI.exists():
        return {}
    df = pd.read_csv(NDMI, parse_dates=["date"])
    if df.empty:
        return {}
    result = {}
    for scope, g in df.groupby("scope"):
        g = g.sort_values("date")
        latest = float(g.iloc[-1]["ndmi"])
        cutoff = g.iloc[-1]["date"] - pd.Timedelta(days=30)
        prior = g[g["date"] >= cutoff]
        baseline = float(prior.iloc[0]["ndmi"]) if len(prior) else latest
        pct = ((latest - baseline) / abs(baseline) * 100) if baseline != 0 else np.nan
        result[scope] = {"ndmi_latest": latest, "ndmi_change_30d_pct": pct}
    return result


def fire_metrics() -> dict[str, dict[str, float]]:
    if not FIRE.exists():
        return {}
    df = pd.read_csv(FIRE, parse_dates=["date"])
    if df.empty:
        return {}
    result = {}
    latest_date = df["date"].max()
    cutoff = latest_date - pd.Timedelta(days=7)
    for scope, g in df.groupby("scope"):
        count_7d = int((g["date"] >= cutoff).sum())
        area = AREAS_HA.get(scope, np.nan)
        density = (count_7d / area * 10000) if np.isfinite(area) else np.nan
        result[scope] = {"hotspots_7d": count_7d, "hotspot_density_7d_per_10kha": density}
    return result


def main() -> None:
    if not ANOMALY.exists():
        raise RuntimeError("Rainfall anomaly data is required.")

    base = latest_anomaly()
    ndmi = ndmi_metrics()
    fire = fire_metrics()
    rows = []

    for _, r in base.iterrows():
        scope = r["scope"]
        a30 = float(r.get("anomaly_30d_pct", np.nan))
        s3 = float(r.get("spi_3", np.nan))
        s6 = float(r.get("spi_6", np.nan))
        nm = ndmi.get(scope, {})
        fm = fire.get(scope, {})
        ndmi_latest = float(nm.get("ndmi_latest", np.nan))
        ndmi_change = float(nm.get("ndmi_change_30d_pct", np.nan))
        hotspots = float(fm.get("hotspots_7d", 0))
        density = float(fm.get("hotspot_density_7d_per_10kha", 0))

        a_score = score_anomaly(a30)
        spi_score = max(score_spi(s3), score_spi(s6))
        ndmi_score = score_ndmi_change(ndmi_change)
        fire_score = score_fire_density(density)
        score = sum(x for x in [a_score, spi_score, ndmi_score, fire_score] if np.isfinite(x))
        available = sum([
            np.isfinite(a30), np.isfinite(s3) or np.isfinite(s6),
            np.isfinite(ndmi_change), np.isfinite(density)
        ])
        basis = "operational" if available >= 3 else "provisional"

        rows.append({
            "date": pd.Timestamp(r["date"]).date().isoformat(),
            "scope": scope,
            "rainfall_anomaly_30d_pct": a30,
            "spi_3": s3,
            "spi_6": s6,
            "ndmi_latest": ndmi_latest,
            "ndmi_change_30d_pct": ndmi_change,
            "hotspots_7d": int(hotspots),
            "hotspot_density_7d_per_10kha": density,
            "rainfall_score": a_score if np.isfinite(a_score) else 0,
            "drought_score": spi_score,
            "vegetation_score": ndmi_score,
            "fire_score": fire_score,
            "integrated_risk_score": score,
            "risk_level": risk_label(score),
            "risk_basis": basis,
            "assessment": "Integrated climate screening from rainfall, SPI, NDMI trend, and active-fire density.",
        })

    out = pd.DataFrame(rows).sort_values(["date", "scope"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False, float_format="%.4f")
    META.write_text(json.dumps({
        "version": "v2",
        "inputs": ["30-day rainfall anomaly", "SPI-3", "SPI-6", "NDMI 30-day change", "FIRMS 7-day hotspot density"],
        "risk_levels": {"low": "0-2", "moderate": "3-5", "high": "6-8", "very_high": ">=9"},
        "note": "Screening index for monitoring prioritization; not a calibrated fire-danger or carbon-accounting metric.",
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(out)} integrated climate risk records to {OUTPUT}")


if __name__ == "__main__":
    main()
