"""Load current SPI-3/SPI-6 data for Streamlit."""
from pathlib import Path
import pandas as pd

PATH = Path("data/processed/climate/rainfall/spi_current.csv")


def load_spi() -> pd.DataFrame:
    if not PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(PATH, parse_dates=["date"])
