"""Load processed annual burned-area history."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/fire/burned_area_annual_2016_2025.csv")


def load_burned_area() -> pd.DataFrame:
    cols = ["year", "scope", "burned_area_ha", "processing_time_utc", "source", "resolution_m"]
    if not PATH.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_csv(PATH).sort_values(["year", "scope"])
