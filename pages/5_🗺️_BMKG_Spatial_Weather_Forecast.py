import base64
import io
import json
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import streamlit as st
from branca.colormap import LinearColormap
from folium.plugins import Fullscreen
from folium.raster_layers import ImageOverlay
from PIL import Image
from scipy.ndimage import zoom
from streamlit_folium import st_folium

from utils.climate.bmkg import load_bmkg_forecast
from utils.ui import setup_page

setup_page()

BASE = Path(__file__).resolve().parents[1]
BMKG_DIR = BASE / "data" / "processed" / "climate" / "bmkg"
SURFACES = {
    "project_area": BMKG_DIR / "forecast_surface_project_area_latest.geojson",
    "carbon_project_zone": BMKG_DIR / "forecast_surface_project_zone_latest.geojson",
}

VARIABLES = {
    "Precipitation (mm)": "precipitation_mm",
    "Temperature (°C)": "temperature_c",
    "Humidity (%)": "humidity_pct",
    "Cloud cover (%)": "cloud_cover_pct",
    "Wind speed (m/s)": "wind_speed_ms",
}

st.markdown("""
<style>
.hero{background:linear-gradient(135deg,#f5faf9,#fff);border:1px solid #dce9e6;border-radius:18px;padding:20px 24px;margin-bottom:16px}
.eyebrow{color:#156064;font-size:.7rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
.title{color:#16383a;font-size:2rem;font-weight:900;margin-top:3px}
.subtitle{color:#5e7779;font-size:.86rem;margin-top:5px}
.note{color:#5e7779;font-size:.76rem;margin:-2px 0 10px}
</style>
""", unsafe_allow_html=True)


def load_surface(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for feature in payload.get("features", []):
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") == "Point" and len(coords) >= 2:
            rows.append({**(feature.get("properties") or {}), "longitude": coords[0], "latitude": coords[1]})
    df = pd.DataFrame(rows)
    if "forecast_datetime" in df.columns:
        df["forecast_datetime"] = pd.to_datetime(df["forecast_datetime"], errors="coerce")
    return df


def excel_bytes(df: pd.DataFrame) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="BMKG_IDW")
    return out.getvalue()


def smooth_raster_image(df: pd.DataFrame, value_col: str):
    grid = df.pivot_table(index="latitude", columns="longitude", values=value_col, aggfunc="mean")
    grid = grid.sort_index().sort_index(axis=1)
    arr = grid.to_numpy(dtype=float)
    valid = np.isfinite(arr)
    if not valid.any():
        return None, None

    # Fill only missing clipped cells for interpolation; their alpha remains zero.
    filled = arr.copy()
    if not valid.all():
        yy, xx = np.where(valid)
        vals = arr[valid]
        for y, x in zip(*np.where(~valid)):
            d2 = (yy - y) ** 2 + (xx - x) ** 2
            filled[y, x] = vals[np.argmin(d2)]

    factor = max(5, min(12, int(900 / max(arr.shape))))
    smooth = zoom(filled, factor, order=3)
    alpha = zoom(valid.astype(float), factor, order=1)

    vmin = float(np.nanmin(arr))
    vmax = float(np.nanmax(arr))
    span = vmax - vmin
    norm = np.zeros_like(smooth) if span <= 0 else np.clip((smooth - vmin) / span, 0, 1)

    # Viridis-like continuous ramp.
    stops = np.array([0.0, .25, .5, .75, 1.0])
    colors = np.array([[68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]], dtype=float)
    rgb = np.stack([np.interp(norm, stops, colors[:, i]) for i in range(3)], axis=-1).astype(np.uint8)
    rgba = np.dstack([rgb, (np.clip(alpha, 0, 1) * 225).astype(np.uint8)])

    image = Image.fromarray(rgba, mode="RGBA")
    # Final resampling removes the visible square-cell/block effect without changing the underlying values.
    image = image.resize((max(500, image.width), max(500, image.height)), Image.Resampling.BICUBIC)
    bounds = [[float(grid.index.min()), float(grid.columns.min())], [float(grid.index.max()), float(grid.columns.max())]]
    return image, bounds


st.markdown("""
<div class="hero">
  <div class="eyebrow">SERPRO PROJECT · CLIMATE & CARBON MONITORING</div>
  <div class="title">🗺️ BMKG Spatial Weather Forecast</div>
  <div class="subtitle">Interactive IDW forecast surface with smooth raster rendering, zoom controls and click-to-inspect forecast cells.</div>
</div>
""", unsafe_allow_html=True)

scope = st.selectbox(
    "Monitoring area",
    ["project_area", "carbon_project_zone"],
    format_func=lambda x: "🟢 SERPRO Project Area · analysis" if x == "project_area" else "🟣 Carbon Project Zone · reference",
)

path = SURFACES[scope]
if not path.exists():
    st.warning("BMKG spatial forecast surface is not available yet. Run Apply BMKG Climate Integration first.")
    st.stop()

df = load_surface(path)
if df.empty:
    st.warning("No BMKG spatial forecast cells are available.")
    st.stop()

timestamps = sorted(df["forecast_datetime"].dropna().unique()) if "forecast_datetime" in df.columns else []
selected_ts = st.selectbox(
    "Forecast time",
    timestamps,
    format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y · %H:%M"),
)
variable_label = st.selectbox("Forecast variable", list(VARIABLES.keys()))
value_col = VARIABLES[variable_label]

view = df[df["forecast_datetime"] == selected_ts].copy()
view[value_col] = pd.to_numeric(view[value_col], errors="coerce")
view = view.dropna(subset=["longitude", "latitude", value_col]).sort_values(["latitude", "longitude"])
if view.empty:
    st.info("No valid values for the selected variable and forecast time.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Forecast cells", f"{len(view):,}")
m2.metric("Minimum", f"{view[value_col].min():.2f}")
m3.metric("Mean", f"{view[value_col].mean():.2f}")
m4.metric("Maximum", f"{view[value_col].max():.2f}")

st.markdown("### Interactive forecast map")
st.markdown('<div class="note">The colored surface is a smoothed visual rendering of the existing 1 km IDW grid. The underlying forecast values are unchanged. Click anywhere on a grid location to inspect the exact cell value and coordinates.</div>', unsafe_allow_html=True)

image, bounds = smooth_raster_image(view, value_col)
if image is None:
    st.error("Could not build the raster visualization.")
    st.stop()

center = [view["latitude"].mean(), view["longitude"].mean()]
m = folium.Map(location=center, zoom_start=10, tiles=None, control_scale=True, scrollWheelZoom=True, doubleClickZoom=True, zoom_control=True)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=True).add_to(m)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Tiles © Esri",
    name="Satellite imagery · Esri",
    show=False,
).add_to(m)
Fullscreen().add_to(m)

ImageOverlay(
    image=image,
    bounds=bounds,
    opacity=0.82,
    interactive=False,
    cross_origin=False,
    zindex=2,
    name=f"Smooth raster · {variable_label}",
).add_to(m)

# Transparent click targets retain the exact original grid values and metadata.
cell_layer = folium.FeatureGroup(name="Clickable forecast cells", show=True)
for _, row in view.iterrows():
    value = float(row[value_col])
    popup_html = (
        f"<div style='min-width:220px'>"
        f"<b>BMKG IDW Forecast Cell</b><hr style='margin:6px 0'>"
        f"<b>Variable:</b> {variable_label}<br>"
        f"<b>Value:</b> {value:.3f}<br>"
        f"<b>Forecast time:</b> {pd.Timestamp(row['forecast_datetime']).strftime('%d %b %Y · %H:%M')}<br>"
        f"<b>Latitude:</b> {float(row['latitude']):.6f}<br>"
        f"<b>Longitude:</b> {float(row['longitude']):.6f}<br>"
        f"<b>Boundary:</b> {row.get('boundary', scope.replace('_', ' ').title())}<br>"
        f"<b>Source:</b> BMKG ADM4 forecast points + IDW<br>"
        f"<span style='color:#5e7779'>Forecast surface, not direct station observation.</span>"
        f"</div>"
    )
    folium.CircleMarker(
        location=[float(row["latitude"]), float(row["longitude"])],
        radius=6,
        color="#ffffff",
        weight=1,
        opacity=0.01,
        fill=True,
        fill_color="#ffffff",
        fill_opacity=0.01,
        popup=folium.Popup(popup_html, max_width=320),
        tooltip=f"{variable_label}: {value:.3f} · {float(row['latitude']):.5f}, {float(row['longitude']):.5f}",
    ).add_to(cell_layer)
cell_layer.add_to(m)

# Five original BMKG ADM4 locations are shown separately for provenance.
bmkg_df, _ = load_bmkg_forecast()
if not bmkg_df.empty:
    loc_layer = folium.FeatureGroup(name="📍 BMKG ADM4 forecast locations", show=True)
    latest_loc = bmkg_df.sort_values("local_datetime").groupby("location", as_index=False).tail(1)
    for _, row in latest_loc.iterrows():
        if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
            continue
        popup = (
            f"<b>{row['location']}</b><br>ADM4: {row.get('adm4','—')}<br>"
            f"Latitude: {float(row['latitude']):.6f}<br>Longitude: {float(row['longitude']):.6f}<br>"
            f"Temperature: {float(row['temperature_c']):.1f} °C<br>"
            f"Humidity: {float(row['humidity_pct']):.0f}%<br>"
            f"Precipitation: {float(row['precipitation_mm']):.2f} mm"
        )
        folium.CircleMarker(
            location=[float(row["latitude"]), float(row["longitude"])],
            radius=6,
            color="#156064",
            fill=True,
            fill_color="#00C49A",
            fill_opacity=0.95,
            popup=folium.Popup(popup, max_width=300),
            tooltip=str(row["location"]),
        ).add_to(loc_layer)
    loc_layer.add_to(m)

colormap = LinearColormap(
    colors=["#440154", "#3B528B", "#21918C", "#5DC863", "#FDE725"],
    vmin=float(view[value_col].min()),
    vmax=float(view[value_col].max()) if float(view[value_col].max()) > float(view[value_col].min()) else float(view[value_col].min()) + 1e-6,
)
colormap.caption = variable_label
colormap.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

st_folium(m, use_container_width=True, height=650, returned_objects=[])

st.markdown("### Data download & reproducibility")
download = view[[c for c in ["latitude", "longitude", "forecast_datetime", "precipitation_mm", "temperature_c", "humidity_pct", "cloud_cover_pct", "wind_speed_ms", "boundary", "source", "interpretation"] if c in view.columns]].copy()
excel = excel_bytes(download)
csv = download.to_csv(index=False).encode("utf-8-sig")
d1, d2, d3 = st.columns(3)
with d1:
    st.download_button("⬇ Download Excel", excel, file_name=f"SERPRO_BMKG_IDW_{scope}_{pd.Timestamp(selected_ts).strftime('%Y%m%d_%H%M')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="bmkg_map_excel")
with d2:
    st.download_button("⬇ Download CSV", csv, file_name=f"SERPRO_BMKG_IDW_{scope}_{pd.Timestamp(selected_ts).strftime('%Y%m%d_%H%M')}.csv", mime="text/csv", key="bmkg_map_csv")
with d3:
    st.download_button("🗺️ Download GeoJSON", path.read_bytes(), file_name=path.name, mime="application/geo+json", key="bmkg_map_geojson")

st.markdown(
    "<div style='background:#f5faf9;border:1px solid #dce9e6;border-radius:12px;padding:12px 14px;color:#5e7779;font-size:.74rem;'>"
    "<b>Map behavior:</b> zoom in/out, pan, switch basemap, toggle layers, and click a forecast grid location for a popup. "
    "The smooth raster is visualization-only; downloaded values remain the original IDW grid. Latitude and longitude are preserved for GIS recreation."
    "</div>",
    unsafe_allow_html=True,
)
