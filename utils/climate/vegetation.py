"""Load processed Sentinel-2 vegetation data."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/vegetation/ndmi_daily.csv")


def load_ndmi() -> pd.DataFrame:
    if not PATH.exists():
        return pd.DataFrame(columns=["date", "scope", "ndmi", "cloudy_pixel_percentage", "source", "processing_time_utc"])
    df = pd.read_csv(PATH, parse_dates=["date"])
    return df.sort_values(["date", "scope"])
