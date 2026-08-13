"""Load processed Sentinel-2 vegetation index data."""
from pathlib import Path
import pandas as pd

NDMI_PATH = Path("data/processed/climate/vegetation/ndmi_daily.csv")
NDVI_PATH = Path("data/processed/climate/vegetation/ndvi_daily.csv")


def _load(path: Path, value_col: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=[
            "date", "scope", value_col, "cloudy_pixel_percentage",
            "source", "processing_time_utc"
        ])
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.dropna(subset=["date", "scope", value_col]).copy()
    # Multiple Sentinel-2 scenes can occur on the same calendar day. Aggregate
    # to a single daily observation per SERPRO monitoring scope for stable
    # trends, alerts, and index comparisons.
    df = (
        df.groupby(["date", "scope"], as_index=False)
        .agg(
            **{
                value_col: (value_col, "mean"),
                "cloudy_pixel_percentage": ("cloudy_pixel_percentage", "mean"),
                "source": ("source", "first"),
                "processing_time_utc": ("processing_time_utc", "max"),
            }
        )
        .sort_values(["date", "scope"])
    )
    return df


def load_ndmi() -> pd.DataFrame:
    return _load(NDMI_PATH, "ndmi")


def load_ndvi() -> pd.DataFrame:
    return _load(NDVI_PATH, "ndvi")
