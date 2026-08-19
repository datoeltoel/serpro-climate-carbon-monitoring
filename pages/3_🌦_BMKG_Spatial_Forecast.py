import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.ui import setup_page

setup_page()

BASE = Path(__file__).resolve().parents[1]
BMKG_DIR = BASE / "data" / "processed" / "climate" / "bmkg"
SURFACES = {
    "SERPRO Carbon Project Zone": BMKG_DIR / "forecast_surface_project_zone_latest.geojson",
    "SERPRO Project Area": BMKG_DIR / "forecast_surface_project_area_latest.geojson",
}

st.markdown(
    """
    <style>
    .hero { background: linear-gradient(135deg,#F5FAF9 0%,#FFFFFF 72%); border:1px solid #DDE9E7; border-radius:18px; padding:22px 24px; margin-bottom:16px; }
    .eyebrow { color:#156064; font-size:.72rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
    .title { color:#16383A; font-size:2rem; font-weight:850; margin:2px 0 4px; }
    .subtitle { color:#5E7779; font-size:.92rem; margin:0; }
    .note { background:#F5FAF9; border:1px solid #DDE9E7; border-radius:14px; padding:12px 15px; color:#5E7779; font-size:.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">SERPRO Project · Operational Forecast</div>
      <div class="title">🌦 BMKG Spatial Weather Forecast</div>
      <p class="subtitle">Five BMKG ADM4 forecast locations interpolated with IDW and clipped to the SERPRO monitoring boundaries.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info("BMKG forecast is operational supporting information only. It is not historical climate data and is not included in the Climate Risk calculation.")

scope = st.selectbox("Monitoring boundary", list(SURFACES.keys()))
path = SURFACES[scope]

if not path.exists():
    st.error(f"Forecast surface is not available yet: {path.name}")
    st.stop()

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2:
            rows.append({**props, "longitude": coords[0], "latitude": coords[1]})
    df = pd.DataFrame(rows)
except Exception as exc:
    st.error(f"Could not read BMKG spatial forecast: {exc}")
    st.stop()

if df.empty:
    st.warning("No BMKG spatial forecast cells are available.")
    st.stop()

if "forecast_datetime" in df:
    df["forecast_datetime"] = pd.to_datetime(df["forecast_datetime"], errors="coerce")

variables = {
    "Precipitation (mm)": "precipitation_mm",
    "Temperature (°C)": "temperature_c",
    "Humidity (%)": "humidity_pct",
    "Cloud cover (%)": "cloud_cover_pct",
    "Wind speed (m/s)": "wind_speed_ms",
}

c1, c2 = st.columns([1, 1])
with c1:
    variable_label = st.selectbox("Forecast variable", list(variables.keys()))
with c2:
    timestamps = sorted(df["forecast_datetime"].dropna().unique()) if "forecast_datetime" in df else []
    selected_ts = st.selectbox("Forecast time", timestamps, format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y · %H:%M")) if timestamps else None

if selected_ts is not None:
    view = df[df["forecast_datetime"] == selected_ts].copy()
else:
    view = df.copy()

value_col = variables[variable_label]
view[value_col] = pd.to_numeric(view[value_col], errors="coerce")
view = view.dropna(subset=["longitude", "latitude", value_col])

if view.empty:
    st.warning("No valid forecast cells for the selected variable/time.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Forecast cells", f"{len(view):,}")
with m2:
    st.metric("Minimum", f"{view[value_col].min():.2f}")
with m3:
    st.metric("Mean", f"{view[value_col].mean():.2f}")
with m4:
    st.metric("Maximum", f"{view[value_col].max():.2f}")

fig = px.scatter_mapbox(
    view,
    lat="latitude",
    lon="longitude",
    color=value_col,
    color_continuous_scale="Viridis",
    hover_data={
        "latitude": ":.5f",
        "longitude": ":.5f",
        value_col: ":.2f",
        "forecast_datetime": True,
    },
    zoom=9,
    height=620,
    labels={value_col: variable_label},
)
fig.update_traces(marker={"size": 8, "opacity": 0.72})
fig.update_layout(
    mapbox_style="open-street-map",
    margin={"l": 0, "r": 0, "t": 10, "b": 0},
    coloraxis_colorbar={"title": variable_label},
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown(
    f'<div class="note"><b>Source:</b> BMKG ADM4 forecast points + IDW · <b>Boundary:</b> {scope} · <b>Interpretation:</b> spatially interpolated forecast surface, not direct station observation.</div>',
    unsafe_allow_html=True,
)

with st.expander("Spatial forecast data"):
    columns = [c for c in ["latitude", "longitude", value_col, "forecast_datetime", "precipitation_mm", "temperature_c", "humidity_pct", "cloud_cover_pct", "wind_speed_ms"] if c in view.columns]
    st.dataframe(view[columns].sort_values(["latitude", "longitude"]), use_container_width=True, hide_index=True)
