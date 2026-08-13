"""Load processed Sentinel-2 vegetation index data."""
from pathlib import Path
import pandas as pd

NDMI_PATH = Path("data/processed/climate/vegetation/ndmi_daily.csv")
NDVI_PATH = Path("data/processed/climate/vegetation/ndvi_daily.csv")


def _load(path: Path, value_col: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "scope", value_col, "cloudy_pixel_percentage", "source", "processing_time_utc"])
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["date", "scope"])


def load_ndmi() -> pd.DataFrame:
    return _load(NDMI_PATH, "ndmi")


def load_ndvi() -> pd.DataFrame:
    return _load(NDVI_PATH, "ndvi")
