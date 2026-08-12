"""Load processed SERPRO VIIRS active-fire hotspot data and build field alerts."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/fire/fire_hotspots.csv")

CONFIDENCE_LABEL = {0: "LOW", 1: "MODERATE", 2: "HIGH"}
ALERT_ACTION = {
    "LOW": "WATCH — retain for monitoring; no immediate field dispatch.",
    "MODERATE": "VERIFY — review satellite context and nearby reports.",
    "HIGH": "FIELD ALERT — prioritize ground verification / patrol follow-up.",
}


def load_fire() -> pd.DataFrame:
    cols = [
        "date", "scope", "longitude", "latitude",
        "brightness_ti4_k", "brightness_ti5_k", "confidence", "source",
        "resolution_m", "processing_time_utc",
    ]
    if not PATH.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(PATH, parse_dates=["date"])
    if "confidence" in df.columns:
        df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    df["confidence_label"] = df["confidence"].map(CONFIDENCE_LABEL).fillna("UNKNOWN")
    df["field_action"] = df["confidence_label"].map(ALERT_ACTION).fillna("REVIEW")
    return df.sort_values(["date", "scope", "confidence"], ascending=[True, True, False])


def build_field_alerts(fire: pd.DataFrame, latest_date=None) -> pd.DataFrame:
    """Return actionable high-confidence alerts, prioritized for Project Area."""
    if fire.empty:
        return pd.DataFrame(columns=[
            "date", "scope", "priority", "latitude", "longitude",
            "source", "confidence", "action",
        ])
    df = fire.copy()
    if latest_date is None:
        latest_date = df["date"].max()
    # Alert window intentionally uses the latest available observation day only.
    df = df[df["date"] == latest_date].copy()
    df = df[df["confidence"] == 2].copy()
    if df.empty:
        return pd.DataFrame(columns=[
            "date", "scope", "priority", "latitude", "longitude",
            "source", "confidence", "action",
        ])
    df["priority"] = df["scope"].map({
        "project_area": "HIGH",
        "carbon_project_zone": "MODERATE",
    }).fillna("MODERATE")
    df["action"] = df["priority"].map({
        "HIGH": "Immediate field verification / patrol dispatch.",
        "MODERATE": "Verify project-zone context and monitor for recurrence.",
    })
    return df[[
        "date", "scope", "priority", "latitude", "longitude",
        "source", "confidence", "action",
    ]].sort_values(["priority", "scope"], ascending=[True, True])
