"""Load processed rainfall data for Streamlit."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/rainfall/rainfall_daily.csv")

def load_rainfall() -> pd.DataFrame:
    if not PATH.exists():
        return pd.DataFrame(columns=["date", "scope", "rainfall_mm", "source", "processing_time_utc"])
    df = pd.read_csv(PATH, parse_dates=["date"])
    return df.sort_values(["date", "scope"])

def latest_by_scope(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.sort_values("date").groupby("scope", as_index=False).tail(1)
