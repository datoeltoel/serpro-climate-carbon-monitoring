from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/risk/climate_risk.csv")


def load_risk() -> pd.DataFrame:
    if not PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(PATH, parse_dates=["date"])
