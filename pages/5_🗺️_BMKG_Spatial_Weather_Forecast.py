import base64
import io
import json
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import streamlit as st
from branca.colormap import LinearColormap
from folium.plugins import Fullscreen, MiniMap
from folium.raster_layers import ImageOverlay
from folium.vector_layers import Rectangle
from PIL import Image
from scipy.ndimage import zoom
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import unary_union
from streamlit_folium import st_folium

from utils.climate.bmkg import load_bmkg_forecast
from utils.map import load_carbon_project_zone, load_project_area
from utils.ui import setup_page

setup_page()

BASE = Path(__file__).resolve().parents[1]
BMKG_DIR = BASE / "data" / "processed" / "climate" / "bmkg"
SURFACES = {
    "SERPRO Project Area": BMKG_DIR / "forecast_surface_project_area_latest.geojson",
    "SERPRO Carbon Project Zone": BMKG_DIR / "forecast_surface_project_zone_latest.geojson",
}
VARIABLES = {
    "Precipitation (mm)": ("precipitation_mm", "mm", ["#313695", "#4575b4", "#74add1", "#abd9e9", "#ffffbf", "#fdae61", "#d73027"]),
    "Temperature (°C)": ("temperature_c", "°C", ["#313695", "#74add1", "#ffffbf", "#fdae61", "#d73027"]),
    "Relative Humidity (%)": ("humidity_pct", "%", ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
    "Wind Speed (m/s)": ("wind_speed_ms", "m/s", ["#f7fcf5", "#c7e9c0", "#74c476", "#238b45", "#00441b"]),
    "Cloud Cover (%)": ("cloud_cover_pct", "%", ["#fff7bc", "#fec44f", "#fe9929", "#d95f0e", "#993404"]),
}

st.markdown("""
<style>
.breadcrumb{font-size:.74rem;color:#71817d;margin-bottom:4px}
.hero{background:linear-gradient(135deg,#f7fbfa,#fff);border:1px solid #dce9e6;border-radius:18px;padding:18px 22px;margin-bottom:14px}
.eyebrow{color:#176266;font-size:.68rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
.title{color:#16383a;font-size:2rem;font-weight:900;line-height:1.1}
.subtitle{color:#617774;font-size:.84rem;margin-top:6px}
.note{color:#617774;font-size:.75rem;margin:0 0 9px}
.info{background:#f3f8f7;border:1px solid #d8e8e4;border-radius:11px;padding:10px 12px;color:#58706c;font-size:.73rem}
.section-title{font-weight:850;color:#173c3d;font-size:1.05rem;margin:13px 0 3px}
</style>
""", unsafe_allow_html=True)


def load_surface(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for feature in payload.get("features", []):
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") == "Point" and len(coords) >= 2:
            rows.append({**(feature.get("properties") or {}), "longitude": float(coords[0]), "latitude": float(coords[1])})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["forecast_datetime"] = pd.to_datetime(df["forecast_datetime"], errors="coerce")
    return df


def excel_bytes(df):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="BMKG_Forecast")
    return out.getvalue()


def boundary_geometry(collection):
    geoms = [shape(f["geometry"]) for f in collection.get("features", []) if f.get("geometry")]
    return unary_union(geoms) if geoms else None


def make_raster(df, value_col, boundary):
    """Render the existing 1 km IDW grid as a continuous raster.

    Smoothing is visualization-only. Original grid values are unchanged.
    """
    grid = df.pivot_table(index="latitude", columns="longitude", values=value_col, aggfunc="mean").sort_index().sort_index(axis=1)
    arr = grid.to_numpy(dtype=float)
    valid = np.isfinite(arr)
    if not valid.any():
        return None

    filled = arr.copy()
    if not valid.all():
        yy, xx = np.where(valid)
        vals = arr[valid]
        for y, x in zip(*np.where(~valid)):
            d2 = (yy - y) ** 2 + (xx - x) ** 2
            filled[y, x] = vals[np.argmin(d2)]

    factor = max(5, min(10, int(1000 / max(arr.shape))))
    smooth = zoom(filled, factor, order=3)
    mask = zoom(valid.astype(float), factor, order=1)
    lats = np.linspace(float(grid.index.min()), float(grid.index.max()), smooth.shape[0])
    lons = np.linspace(float(grid.columns.min()), float(grid.columns.max()), smooth.shape[1])
    lon_mesh, lat_mesh = np.meshgrid(lons, lats)

    geom = boundary_geometry(boundary)
    if geom is not None and not geom.is_empty:
        mask *= contains_xy(geom, lon_mesh, lat_mesh).astype(float)

    return {
        "array": smooth,
        "alpha": np.clip(mask, 0, 1),
        "bounds": [[float(lats.min()), float(lons.min())], [float(lats.max()), float(lons.max())]],
        "vmin": float(np.nanmin(arr)),
        "vmax": float(np.nanmax(arr)),
    }


def raster_rgba(raster, colors):
    arr, alpha = raster["array"], raster["alpha"]
    vmin, vmax = raster["vmin"], raster["vmax"]
    span = vmax - vmin
    norm = np.zeros_like(arr) if span <= 0 else np.clip((arr - vmin) / span, 0, 1)
    stops = np.linspace(0, 1, len(colors))
    stop_rgb = np.array([[int(c[i:i+2], 16) for i in (1, 3, 5)] for c in colors], dtype=float)
    rgb = np.stack([np.interp(norm, stops, stop_rgb[:, i]) for i in range(3)], axis=-1).astype(np.uint8)
    return np.dstack([rgb, (np.clip(alpha, 0, 1) * 220).astype(np.uint8)])


def cell_half_size(view):
    lats = np.sort(view.latitude.unique())
    lons = np.sort(view.longitude.unique())
    dy = float(np.median(np.diff(lats))) if len(lats) > 1 else 0.009
    dx = float(np.median(np.diff(lons))) if len(lons) > 1 else 0.009
    return dx / 2, dy / 2


st.markdown('<div class="breadcrumb">⌂ Climate Monitoring &nbsp;›&nbsp; <b>BMKG Local Weather Forecast</b></div>', unsafe_allow_html=True)
st.markdown("""<div class="hero"><div class="eyebrow">SERPRO PROJECT · CLIMATE & CARBON MONITORING</div>
<div class="title">🗺️ BMKG Spatial Weather Forecast</div>
<div class="subtitle">Five BMKG ADM4 forecast points interpolated using IDW and clipped to the selected SERPRO boundary. This represents forecast conditions, not direct station observations.</div></div>""", unsafe_allow_html=True)

scope = st.selectbox("Boundary", list(SURFACES.keys()), index=0)
path = SURFACES[scope]
if not path.exists():
    st.warning("BMKG spatial forecast surface is not available yet. Run the BMKG ingestion workflow first.")
    st.stop()

surface = load_surface(path)
if surface.empty:
    st.warning("No BMKG spatial forecast cells are available for this boundary.")
    st.stop()

timestamps = sorted(surface.forecast_datetime.dropna().unique())
selected_ts = st.selectbox("Forecast time", timestamps, format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y · %H:%M WIB"))
variable_label = st.selectbox("Forecast variable", list(VARIABLES.keys()), index=0)
value_col, unit, palette = VARIABLES[variable_label]

view = surface[surface.forecast_datetime == selected_ts].copy()
view[value_col] = pd.to_numeric(view[value_col], errors="coerce")
view = view.dropna(subset=["latitude", "longitude", value_col]).sort_values(["latitude", "longitude"])
if view.empty:
    st.info("No valid values for the selected variable and forecast time.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Forecast cells", f"{len(view):,}", "1 km IDW grid")
c2.metric("Minimum", f"{view[value_col].min():.2f}", unit)
c3.metric("Mean", f"{view[value_col].mean():.2f}", unit)
c4.metric("Maximum", f"{view[value_col].max():.2f}", unit)

st.markdown('<div class="section-title">Interactive forecast map</div>', unsafe_allow_html=True)
st.markdown('<div class="note">Continuous raster visualization of the existing 1 km IDW grid. Zoom, pan, switch basemaps/layers, and click a grid cell to inspect the exact original value and coordinates.</div>', unsafe_allow_html=True)

m = folium.Map(location=[view.latitude.mean(), view.longitude.mean()], zoom_start=10, tiles=None, control_scale=True, scrollWheelZoom=True, zoom_control=True)
folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=True).add_to(m)
folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Tiles © Esri", name="Satellite imagery · Esri", show=False).add_to(m)
Fullscreen(position="topleft").add_to(m)
MiniMap(toggle_display=True, position="bottomright").add_to(m)

area, zone = load_project_area(), load_carbon_project_zone()
selected_boundary = area if scope == "SERPRO Project Area" else zone
if area.get("features"):
    folium.GeoJson(area, name="🟢 SERPRO Project Area", style_function=lambda _: {"color":"#0B6B4B","weight":3,"fillOpacity":0.02}, tooltip="SERPRO Project Area").add_to(m)
if zone.get("features"):
    folium.GeoJson(zone, name="🟣 SERPRO Carbon Project Zone", style_function=lambda _: {"color":"#7A4FA3","weight":2.5,"fillOpacity":0.015}, tooltip="SERPRO Carbon Project Zone").add_to(m)

# TRUE continuous raster. No point symbols are used for the forecast grid.
raster = make_raster(view, value_col, selected_boundary)
if raster is not None:
    ImageOverlay(image=raster_rgba(raster, palette), bounds=raster["bounds"], opacity=0.82, interactive=False, cross_origin=False, zindex=10, name=f"🌈 Raster · {variable_label}").add_to(m)

# Transparent cell hit-areas preserve exact popup interaction without visible dots.
dx2, dy2 = cell_half_size(view)
cells = folium.FeatureGroup(name="🖱️ Clickable forecast cells", show=True)
for _, row in view.iterrows():
    value = float(row[value_col])
    popup = f"""<div style='min-width:245px'><h4 style='margin:0 0 8px;color:#16383a'>🌦️ Forecast Information</h4>
<b>Variable:</b> {variable_label}<br><b>Value:</b> {value:.3f} {unit}<br>
<b>Forecast time:</b> {pd.Timestamp(row.forecast_datetime).strftime("%d %b %Y · %H:%M WIB")}<br>
<b>Latitude:</b> {float(row.latitude):.6f}<br><b>Longitude:</b> {float(row.longitude):.6f}<br>
<b>Boundary:</b> {scope}<br><b>Source:</b> BMKG ADM4 forecast points + IDW<br>
<hr style='margin:7px 0'><span style='color:#617774'>Forecast surface, not direct station observation.</span></div>"""
    Rectangle(bounds=[[float(row.latitude)-dy2, float(row.longitude)-dx2], [float(row.latitude)+dy2, float(row.longitude)+dx2]], color="#00000000", weight=0, fill=True, fill_color="#000000", fill_opacity=0, popup=folium.Popup(popup, max_width=330), tooltip=f"{variable_label}: {value:.3f} {unit}").add_to(cells)
cells.add_to(m)

# Five BMKG ADM4 reference locations.
bmkg, meta = load_bmkg_forecast()
if not bmkg.empty:
    bmkg["local_datetime"] = pd.to_datetime(bmkg["local_datetime"], errors="coerce")
    target = pd.Timestamp(selected_ts)
    bmkg["time_delta"] = (bmkg["local_datetime"] - target).abs()
    selected_loc = bmkg.sort_values("time_delta").drop_duplicates("location")
    locs = folium.FeatureGroup(name="📍 BMKG ADM4 locations", show=True)
    for _, row in selected_loc.iterrows():
        if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
            continue
        popup = f"""<b>📍 {row.location}</b><br>ADM4: {row.adm4}<br>
Latitude: {float(row.latitude):.6f}<br>Longitude: {float(row.longitude):.6f}<br>
Temperature: {float(row.temperature_c):.1f} °C<br>Humidity: {float(row.humidity_pct):.0f}%<br>
Precipitation: {float(row.precipitation_mm):.2f} mm<br>Weather: {row.weather_desc_en or row.weather_desc or '—'}<br>
Wind: {float(row.wind_speed_ms):.1f} m/s"""
        folium.CircleMarker([float(row.latitude), float(row.longitude)], radius=6, color="#0c4f52", fill=True, fill_color="#00b894", fill_opacity=.95, popup=folium.Popup(popup, max_width=300), tooltip=str(row.location)).add_to(locs)
    locs.add_to(m)

if raster is not None:
    LinearColormap(colors=palette, vmin=raster["vmin"], vmax=raster["vmax"] if raster["vmax"] > raster["vmin"] else raster["vmin"] + 1e-9, caption=f"{variable_label} · IDW raster").add_to(m)
folium.LayerControl(collapsed=False).add_to(m)
st_folium(m, use_container_width=True, height=690, returned_objects=[], key="bmkg_spatial_map_v3")

st.markdown('<div class="info"><b>Interpretation:</b> The colored surface is a continuous raster visualization generated from the existing 1 km IDW grid and clipped to the selected SERPRO boundary. Popup/download values remain the original forecast grid values. BMKG forecast data are <b>not used in historical rainfall, SPI, anomaly, or climate-risk calculations</b>.</div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Forecast data download</div>', unsafe_allow_html=True)
cols = [c for c in ["location","adm4","latitude","longitude","forecast_datetime","precipitation_mm","temperature_c","humidity_pct","cloud_cover_pct","wind_speed_ms","weather_desc_en","boundary","source","interpretation"] if c in view.columns]
download = view[cols].copy()
excel = excel_bytes(download)
c1, c2, c3 = st.columns(3)
with c1:
    st.download_button("⬇ Download Excel", excel, file_name=f"SERPRO_BMKG_IDW_{scope.replace(' ','_')}_{pd.Timestamp(selected_ts).strftime('%Y%m%d_%H%M')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
with c2:
    st.download_button("⬇ Download CSV", download.to_csv(index=False).encode("utf-8-sig"), file_name=f"SERPRO_BMKG_IDW_{pd.Timestamp(selected_ts).strftime('%Y%m%d_%H%M')}.csv", mime="text/csv", use_container_width=True)
with c3:
    st.download_button("🗺️ Download GeoJSON", path.read_bytes(), file_name=path.name, mime="application/geo+json", use_container_width=True)

with st.expander("ℹ️ Data quality & metadata"):
    q = meta.get("quality", pd.DataFrame())
    if not q.empty:
        ok = int((q["status"] == "OK").sum())
        total = len(q)
        st.write(f"**BMKG ADM4 sources available:** {ok}/{total}")
        st.dataframe(q, use_container_width=True, hide_index=True)
    st.caption("Source: BMKG Open Data · 3-day local forecast · approximately 3-hour interval · five pilot ADM4 locations.")
