"""Load integrated SERPRO climate risk v2 data."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/risk/climate_risk_v2.csv")


def load_integrated_risk() -> pd.DataFrame:
    if not PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(PATH, parse_dates=["date"])
