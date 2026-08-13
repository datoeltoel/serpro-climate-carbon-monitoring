"""Load processed Sentinel-2 NDVI data for SERPRO."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/vegetation/ndvi_daily.csv")


def load_ndvi() -> pd.DataFrame:
    if not PATH.exists():
        return pd.DataFrame(columns=[
            "date", "scope", "ndvi", "cloudy_pixel_percentage",
            "source", "processing_time_utc"
        ])
    df = pd.read_csv(PATH, parse_dates=["date"])
    # Multiple Sentinel-2 scenes can occur on the same day. Aggregate to one
    # daily observation per monitoring scope for dashboard analysis.
    df = df.dropna(subset=["date", "scope", "ndvi"]).copy()
    df = (
        df.groupby(["date", "scope"], as_index=False)
        .agg(
            ndvi=("ndvi", "mean"),
            cloudy_pixel_percentage=("cloudy_pixel_percentage", "mean"),
            source=("source", "first"),
            processing_time_utc=("processing_time_utc", "max"),
        )
        .sort_values(["date", "scope"])
    )
    return df
