"""Load processed rainfall anomaly data."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/rainfall/rainfall_anomaly.csv")


def load_anomaly() -> pd.DataFrame:
    if not PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(PATH, parse_dates=["date"])
