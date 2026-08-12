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
    if not PATH.exists():
        return pd.DataFrame(columns=["date", "scope", "longitude", "latitude", "brightness_ti4_k", "brightness_ti5_k", "confidence", "source", "resolution_m", "processing_time_utc"])
    df = pd.read_csv(PATH, parse_dates=["date"])
    # Support legacy files that used brightness_temperature_k.
    if "brightness_ti4_k" not in df.columns:
        if "brightness_temperature_k" in df.columns:
            df["brightness_ti4_k"] = df["brightness_temperature_k"]
        else:
            df["brightness_ti4_k"] = pd.NA
    if "brightness_ti5_k" not in df.columns:
        df["brightness_ti5_k"] = pd.NA
    if "confidence" in df.columns:
        if df["confidence"].dtype == object:
            mapping = {"LOW": 0, "NOMINAL": 1, "MODERATE": 1, "HIGH": 2}
            df["confidence"] = df["confidence"].map(mapping).fillna(pd.to_numeric(df["confidence"], errors="coerce"))
        df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    else:
        df["confidence"] = pd.NA
    df["confidence_label"] = df["confidence"].map(CONFIDENCE_LABEL).fillna("UNKNOWN")
    df["field_action"] = df["confidence_label"].map(ALERT_ACTION).fillna("REVIEW")
    return df.sort_values(["date", "scope", "confidence"], ascending=[True, True, False])


def build_field_alerts(fire: pd.DataFrame, latest_date=None) -> pd.DataFrame:
    if fire.empty:
        return pd.DataFrame()
    df = fire.copy()
    latest_date = df["date"].max() if latest_date is None else latest_date
    df = df[(df["date"] == latest_date) & (df["confidence"] == 2)].copy()
    if df.empty:
        return pd.DataFrame()
    df["priority"] = df["scope"].map({"project_area": "HIGH", "carbon_project_zone": "MODERATE"}).fillna("MODERATE")
    df["action"] = df["priority"].map({"HIGH": "Immediate field verification / patrol dispatch.", "MODERATE": "Verify project-zone context and monitor for recurrence."})
    return df[["date", "scope", "priority", "latitude", "longitude", "source", "confidence", "action"]]
