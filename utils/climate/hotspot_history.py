from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/fire/hotspot_history_2017_2025.csv")


def load_hotspot_history() -> pd.DataFrame:
    cols = ["year", "scope", "hotspot_detections", "source", "resolution_m", "metric", "processing_time_utc"]
    if not PATH.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(PATH)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["hotspot_detections"] = pd.to_numeric(df["hotspot_detections"], errors="coerce").fillna(0)
    return df.sort_values(["year", "scope"])
