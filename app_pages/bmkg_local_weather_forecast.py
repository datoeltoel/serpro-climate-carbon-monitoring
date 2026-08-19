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

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">SERPRO PROJECT · CLIMATE MONITORING</div>
      <div class="title">🌦️ BMKG Local Weather Forecast</div>
      <div class="subtitle">Operational BMKG ADM4 forecast for the five pilot locations, with a separate 1 km IDW spatial surface. Forecast data are not historical observations and are excluded from Climate Risk calculations.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

bmkg, meta = load_bmkg_forecast()
if not bmkg.empty:
    bmkg["local_datetime"] = pd.to_datetime(bmkg["local_datetime"], errors="coerce")

forecast_tab, spatial_tab, data_tab = st.tabs(["Local Forecast", "Spatial Forecast", "Data & Provenance"])

with forecast_tab:
    if bmkg.empty:
        st.warning("BMKG forecast is temporarily unavailable. Run the BMKG ingestion workflow first.")
    else:
        locations = sorted(bmkg["location"].dropna().unique().tolist())
        selected = st.selectbox("BMKG location", ["All locations"] + locations, key="bmkg_location_page")
        local = bmkg.copy() if selected == "All locations" else bmkg[bmkg["location"] == selected].copy()
        latest = local.sort_values("local_datetime").groupby("location", as_index=False).tail(1)
        cols = st.columns(min(5, max(1, len(latest))))
        for col, (_, row) in zip(cols, latest.iterrows()):
            weather = row.get("weather_desc_en") or row.get("weather_desc") or "—"
            with col:
                st.metric(str(row["location"]), f"{row['temperature_c']:.1f} °C" if pd.notna(row.get("temperature_c")) else "—", weather)

        display_cols = [c for c in ["location", "adm4", "latitude", "longitude", "local_datetime", "temperature_c", "humidity_pct", "precipitation_mm", "wind_speed_ms", "wind_direction", "cloud_cover_pct", "visibility", "weather_desc_en", "analysis_date"] if c in local.columns]
        display = local[display_cols].sort_values(["location", "local_datetime"]).copy()
        display = display.rename(columns={
            "local_datetime": "Local time", "temperature_c": "Temp (°C)", "humidity_pct": "RH (%)",
            "precipitation_mm": "Precipitation (mm)", "wind_speed_ms": "Wind (m/s)",
            "wind_direction": "Wind direction", "cloud_cover_pct": "Cloud (%)", "weather_desc_en": "Weather",
        })
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button("⬇ Download BMKG Forecast CSV", display.to_csv(index=False).encode("utf-8-sig"), file_name=f"SERPRO_BMKG_Forecast_{pd.Timestamp.now():%Y%m%d}.csv", mime="text/csv", key="bmkg_local_csv")

with spatial_tab:
    scope = st.selectbox("Forecast boundary", list(SURFACES.keys()), index=0, key="bmkg_boundary")
    path = SURFACES[scope]
    if not path.exists():
        st.warning("BMKG spatial forecast surface is not available yet. Run the BMKG ingestion workflow first.")
        st.stop()

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for feature in payload.get("features", []):
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") == "Point" and len(coords) >= 2:
            rows.append({**(feature.get("properties") or {}), "longitude": float(coords[0]), "latitude": float(coords[1])})
    surface = pd.DataFrame(rows)
    if surface.empty:
        st.warning("No BMKG spatial forecast cells are available for this boundary.")
        st.stop()
    surface["forecast_datetime"] = pd.to_datetime(surface["forecast_datetime"], errors="coerce")
    timestamps = sorted(surface["forecast_datetime"].dropna().unique())
    t1, t2 = st.columns(2)
    with t1:
        variable_label = st.selectbox("Forecast variable", list(VARIABLES.keys()), key="bmkg_raster_variable")
    with t2:
        selected_ts = st.selectbox("Forecast time", timestamps, format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y · %H:%M WIB"), key="bmkg_raster_time")
    value_col, unit, palette = VARIABLES[variable_label]
    view = surface[surface["forecast_datetime"] == selected_ts].copy()
    view[value_col] = pd.to_numeric(view[value_col], errors="coerce")
    view = view.dropna(subset=["latitude", "longitude", value_col]).sort_values(["latitude", "longitude"])
    if view.empty:
        st.info("No valid values for the selected variable and forecast time.")
        st.stop()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Forecast cells", f"{len(view):,}", "1 km IDW grid")
    m2.metric("Minimum", f"{view[value_col].min():.2f}", unit)
    m3.metric("Mean", f"{view[value_col].mean():.2f}", unit)
    m4.metric("Maximum", f"{view[value_col].max():.2f}", unit)

    def boundary_geometry(collection):
        geoms = [shape(f["geometry"]) for f in collection.get("features", []) if f.get("geometry")]
        return unary_union(geoms) if geoms else None

    def make_raster(df, boundary):
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
        factor = max(4, min(8, int(900 / max(arr.shape))))
        smooth = zoom(filled, factor, order=3)
        raster_valid = zoom(valid.astype(float), factor, order=1)
        lats = np.linspace(float(grid.index.min()), float(grid.index.max()), smooth.shape[0])
        lons = np.linspace(float(grid.columns.min()), float(grid.columns.max()), smooth.shape[1])
        lon_mesh, lat_mesh = np.meshgrid(lons, lats)
        geom = boundary_geometry(boundary)
        if geom is not None and not geom.is_empty:
            raster_valid *= contains_xy(geom, lon_mesh, lat_mesh).astype(float)
        return smooth, np.clip(raster_valid, 0, 1), [[float(lats.min()), float(lons.min())], [float(lats.max()), float(lons.max())]], float(np.nanmin(arr)), float(np.nanmax(arr))

    def png_uri(arr, alpha, vmin, vmax):
        span = vmax - vmin
        norm = np.zeros_like(arr) if span <= 0 else np.clip((arr - vmin) / span, 0, 1)
        stops = np.linspace(0, 1, len(palette))
        rgb_stops = np.array([[int(c[i:i+2], 16) for i in (1, 3, 5)] for c in palette], dtype=float)
        rgb = np.stack([np.interp(norm, stops, rgb_stops[:, i]) for i in range(3)], axis=-1).astype(np.uint8)
        rgba = np.dstack([rgb, (np.clip(alpha, 0, 1) * 215).astype(np.uint8)])
        image = Image.fromarray(rgba, mode="RGBA")
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    area = load_project_area()
    zone = load_carbon_project_zone()
    selected_boundary = area if scope == "SERPRO Project Area" else zone
    raster = make_raster(view, selected_boundary)

    m = folium.Map(location=[view.latitude.mean(), view.longitude.mean()], zoom_start=10, tiles=None, control_scale=True, scrollWheelZoom=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=True).add_to(m)
    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Tiles © Esri", name="Satellite imagery · Esri", show=False).add_to(m)
    Fullscreen(position="topleft").add_to(m)
    MiniMap(toggle_display=True, position="bottomright").add_to(m)

    if area.get("features"):
        folium.GeoJson(area, name="🟢 SERPRO Project Area", style_function=lambda _: {"color": "#0B6B4B", "weight": 3, "fillColor": "#0B6B4B", "fillOpacity": 0.02}).add_to(m)
    if zone.get("features"):
        folium.GeoJson(zone, name="🟣 SERPRO Carbon Project Zone", style_function=lambda _: {"color": "#7A4FA3", "weight": 2.5, "fillColor": "#7A4FA3", "fillOpacity": 0.015}).add_to(m)

    if raster is not None:
        arr, alpha, bounds, vmin, vmax = raster
        ImageOverlay(image=png_uri(arr, alpha, vmin, vmax), bounds=bounds, opacity=0.78, interactive=False, zindex=10, name=f"🌈 Raster · {variable_label}").add_to(m)
        LinearColormap(colors=palette, vmin=vmin, vmax=vmax if vmax > vmin else vmin + 1e-9, caption=f"{variable_label} · IDW raster").add_to(m)

    # Transparent click targets preserve exact original IDW values without
    # visually adding point symbols over the continuous raster.
    clicks = folium.FeatureGroup(name="🖱️ Clickable forecast cells", show=True)
    for _, row in view.iterrows():
        value = float(row[value_col])
        popup = f"<b>🌦️ Forecast Information</b><br>Variable: {variable_label}<br>Value: {value:.3f} {unit}<br>Forecast time: {pd.Timestamp(row['forecast_datetime']):%d %b %Y · %H:%M WIB}<br>Latitude: {float(row.latitude):.6f}<br>Longitude: {float(row.longitude):.6f}<br>Boundary: {scope}<br>Source: BMKG ADM4 forecast points + IDW<br><hr><span style='color:#617774'>Forecast surface, not direct station observation.</span>"
        folium.CircleMarker(location=[float(row.latitude), float(row.longitude)], radius=9, color="#ffffff", weight=0, opacity=0, fill=True, fill_color="#ffffff", fill_opacity=0, popup=folium.Popup(popup, max_width=330), tooltip=f"{variable_label}: {value:.3f} {unit}").add_to(clicks)
    clicks.add_to(m)

    if not bmkg.empty:
        locs = bmkg.copy()
        locs["time_delta"] = (locs["local_datetime"] - pd.Timestamp(selected_ts)).abs()
        selected_locs = locs.sort_values("time_delta").drop_duplicates("location")
        ref = folium.FeatureGroup(name="📍 BMKG ADM4 locations", show=True)
        for _, row in selected_locs.iterrows():
            if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
                continue
            popup = f"<b>📍 {row.location}</b><br>ADM4: {row.adm4}<br>Temperature: {float(row.temperature_c):.1f} °C<br>Humidity: {float(row.humidity_pct):.0f}%<br>Precipitation: {float(row.precipitation_mm):.2f} mm<br>Weather: {row.get('weather_desc_en') or row.get('weather_desc') or '—'}<br>Wind: {float(row.wind_speed_ms):.1f} m/s"
            folium.CircleMarker(location=[float(row.latitude), float(row.longitude)], radius=5, color="#0c4f52", fill=True, fill_color="#00b894", fill_opacity=0.95, popup=folium.Popup(popup, max_width=300), tooltip=str(row.location)).add_to(ref)
        ref.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    st.markdown("**Continuous raster visualization**", unsafe_allow_html=True)
    st.caption("The raster is generated from the existing 1 km IDW grid, smoothly rendered for display and clipped to the official selected SERPRO boundary. Popup/download values remain the original IDW grid values.")
    st_folium(m, use_container_width=True, height=690, returned_objects=[], key="bmkg_spatial_map_page")

    spatial_download_cols = [c for c in ["latitude", "longitude", "forecast_datetime", "precipitation_mm", "temperature_c", "humidity_pct", "cloud_cover_pct", "wind_speed_ms", "boundary", "source", "interpretation"] if c in view.columns]
    spatial_download = view[spatial_download_cols].sort_values(["latitude", "longitude"]).copy()
    st.download_button("🗺️ Download spatial GeoJSON", path.read_bytes(), file_name=path.name, mime="application/geo+json", key="bmkg_geojson_page")
    st.download_button("⬇ Download spatial CSV", spatial_download.to_csv(index=False).encode("utf-8-sig"), file_name=f"SERPRO_BMKG_IDW_{scope.replace(' ', '_')}_{pd.Timestamp(selected_ts):%Y%m%d_%H%M}.csv", mime="text/csv", key="bmkg_spatial_csv_page")

with data_tab:
    if bmkg.empty:
        st.info("No BMKG forecast data available.")
    else:
        q = meta.get("quality") if isinstance(meta, dict) else None
        if q is not None and not q.empty:
            st.markdown("### Data quality & provenance")
            st.dataframe(q, use_container_width=True, hide_index=True)
        st.write(f"Fetched (UTC): {meta.get('fetched_at_utc', '—') if isinstance(meta, dict) else '—'}")
        st.caption("Source: BMKG Open Data · 3-day local forecast · approximately 3-hour interval · five pilot ADM4 locations. Forecast-only dataset; it is not used in Historical Climate or Climate Risk calculations.")
