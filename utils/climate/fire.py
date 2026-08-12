"""Load processed SERPRO active-fire hotspot data."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/fire/fire_hotspots.csv")


def load_fire() -> pd.DataFrame:
    cols = [
        "date", "scope", "longitude", "latitude",
        "brightness_temperature_k", "confidence", "source",
        "resolution_m", "processing_time_utc",
    ]
    if not PATH.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(PATH, parse_dates=["date"])
    return df.sort_values(["date", "scope"])
