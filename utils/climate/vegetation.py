"""Load processed Sentinel-2 vegetation index data."""
from pathlib import Path
import pandas as pd

NDMI_PATH = Path("data/processed/climate/vegetation/ndmi_daily.csv")
NDVI_PATH = Path("data/processed/climate/vegetation/ndvi_daily.csv")
NDVI_ANNUAL_PATH = Path("data/processed/climate/vegetation/ndvi_annual_2015_2025.csv")


def _load(path: Path, value_col: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "scope", value_col, "cloudy_pixel_percentage", "source", "processing_time_utc"])
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.dropna(subset=["date", "scope", value_col]).copy()
    df = (df.groupby(["date", "scope"], as_index=False)
          .agg(**{value_col: (value_col, "mean"),
                  "cloudy_pixel_percentage": ("cloudy_pixel_percentage", "mean"),
                  "source": ("source", "first"),
                  "processing_time_utc": ("processing_time_utc", "max")})
          .sort_values(["date", "scope"]))
    return df


def load_ndmi() -> pd.DataFrame:
    return _load(NDMI_PATH, "ndmi")


def load_ndvi() -> pd.DataFrame:
    return _load(NDVI_PATH, "ndvi")


def load_ndvi_annual() -> pd.DataFrame:
    if not NDVI_ANNUAL_PATH.exists():
        return pd.DataFrame(columns=["year", "scope", "ndvi_mean", "observation_count", "source", "note"])
    df = pd.read_csv(NDVI_ANNUAL_PATH)
    return df.dropna(subset=["year", "scope", "ndvi_mean"]).sort_values(["year", "scope"])
