"""Load SERPRO climate risk outputs."""
from pathlib import Path
import pandas as pd

V2_PATH = Path("data/processed/climate/risk/climate_risk_v2.csv")
V1_PATH = Path("data/processed/climate/risk/climate_risk.csv")


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, parse_dates=["date"])
    except (ValueError, KeyError):
        return pd.read_csv(path)


def load_integrated_risk() -> pd.DataFrame:
    """Load integrated Climate Risk v2 output when available."""
    return _load(V2_PATH)


def load_risk() -> pd.DataFrame:
    """Backward-compatible risk loader for the Climate Monitoring page.

    Prefer integrated v2 output; fall back to the earlier v1 output so the
    climate dashboard does not fail while risk pipelines are being refreshed.
    """
    df = _load(V2_PATH)
    if not df.empty:
        return df
    return _load(V1_PATH)
