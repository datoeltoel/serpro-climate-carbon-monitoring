import io
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.climate.rainfall import load_rainfall
from utils.climate.anomaly import load_anomaly
from utils.climate.spi import load_spi
from utils.climate.risk import load_risk
from utils.climate.bmkg import load_bmkg_forecast
from utils.ui import setup_page

setup_page()

BASE = Path(__file__).resolve().parents[1]
BMKG_DIR = BASE / "data" / "processed" / "climate" / "bmkg"
BMKG_SURFACES = {
    "project_area": BMKG_DIR / "forecast_surface_project_area_latest.geojson",
    "carbon_project_zone": BMKG_DIR / "forecast_surface_project_zone_latest.geojson",
}

st.markdown(
    """
    <style>
    :root{--deep:#156064;--green:#00C49A;--yellow:#F8E16C;--coral:#FFC2B4;--orange:#FB8F67;--ink:#16383A;--muted:#5E7779;--line:#DDE9E7;--soft:#F5FAF9}
    .hero{background:linear-gradient(135deg,#F5FAF9 0%,#FFF 72%);border:1px solid var(--line);border-radius:18px;padding:22px 24px;margin-bottom:16px}
    .eyebrow{color:var(--deep);font-size:.72rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase}.title{color:var(--ink);font-size:2rem;font-weight:850;margin:2px 0 4px}.subtitle{color:var(--muted);font-size:.92rem;margin:0}
    .section{color:var(--ink);font-size:1.18rem;font-weight:800;margin:22px 0 8px}.note{color:var(--muted);font-size:.78rem;margin:-3px 0 10px}.info{background:var(--soft);border:1px solid var(--line);border-radius:14px;padding:13px 16px;color:var(--muted);font-size:.78rem}
    </style>
    """,
    unsafe_allow_html=True,
)


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Data") -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    return output.getvalue()


def add_downloads(df: pd.DataFrame, stem: str, sheet_name: str = "Data", key_prefix: str = "download") -> None:
    if df is None or df.empty:
        return
    excel_bytes = to_excel_bytes(df, sheet_name)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("⬇ Download Excel", excel_bytes, file_name=f"{stem}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{key_prefix}_xlsx")
    with d2:
        st.download_button("⬇ Download CSV", csv_bytes, file_name=f"{stem}.csv", mime="text/csv", key=f"{key_prefix}_csv")


def load_spatial_surface(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {}) or {}
        geom = feature.get("geometry", {}) or {}
        coords = geom.get("coordinates", []) or []
        if geom.get("type") == "Point" and len(coords) >= 2:
            rows.append({**props, "longitude": coords[0], "latitude": coords[1]})
    return pd.DataFrame(rows)

rainfall = load_rainfall()
anomaly = load_anomaly()
spi = load_spi()
risk = load_risk()
bmkg_df, bmkg_meta = load_bmkg_forecast()

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">SERPRO Project · Climate & Carbon Monitoring</div>
      <div class="title">🌧 Climate Monitoring</div>
      <p class="subtitle">Historical climate evidence and operational BMKG local weather forecast, kept separate for transparent monitoring and reproducible analysis.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if rainfall.empty:
    st.warning("Belum ada data rainfall otomatis. Jalankan Update SERPRO Rainfall di GitHub Actions terlebih dahulu.")
    st.stop()

rainfall["date"] = pd.to_datetime(rainfall["date"], errors="coerce")
rainfall = rainfall.dropna(subset=["date"]).sort_values("date")
valid_scopes = [s for s in ["project_area", "carbon_project_zone"] if s in rainfall["scope"].unique()]
if not valid_scopes:
    st.error("Tidak ditemukan monitoring scope yang valid pada data rainfall.")
    st.stop()

st.markdown('<div class="section">Monitoring area & period</div>', unsafe_allow_html=True)
f1, f2, f3 = st.columns([1.3, 1, .9])
with f1:
    scope = st.selectbox("Monitoring area", valid_scopes, format_func=lambda x: {"project_area":"🟢 SERPRO Project Area · analysis","carbon_project_zone":"🟣 Carbon Project Zone · reference"}.get(x, x.replace("_", " ").title()))
scoped_all = rainfall[rainfall["scope"] == scope].copy().sort_values("date")
min_date, max_date = scoped_all["date"].min().date(), scoped_all["date"].max().date()
with f2:
    start_date = st.date_input("Start date", value=max(min_date, max_date - pd.Timedelta(days=29)), min_value=min_date, max_value=max_date)
with f3:
    end_date = st.date_input("End date", value=max_date, min_value=min_date, max_value=max_date)
preset = st.selectbox("Quick range", ["Custom", "Latest 7D", "Latest 30D", "Latest 90D", "Year to date"], index=2)
if preset != "Custom":
    start_date = {"Latest 7D": max(min_date, max_date - pd.Timedelta(days=6)), "Latest 30D": max(min_date, max_date - pd.Timedelta(days=29)), "Latest 90D": max(min_date, max_date - pd.Timedelta(days=89)), "Year to date": max(min_date, pd.Timestamp(max_date.year, 1, 1).date())}[preset]
    end_date = max_date
if start_date > end_date:
    st.error("Start date harus lebih kecil atau sama dengan End date.")
    st.stop()
scoped = scoped_all[(scoped_all["date"].dt.date >= start_date) & (scoped_all["date"].dt.date <= end_date)].copy()

# -----------------------------------------------------------------------------
# 1. BMKG LOCAL WEATHER FORECAST
# -----------------------------------------------------------------------------
st.markdown('<div class="section">📡 BMKG Local Weather Forecast</div>', unsafe_allow_html=True)
st.markdown('<div class="note">Operational 3-day forecast from BMKG ADM4 pilot villages. Forecast data are not historical observations and are excluded from Climate Risk calculations.</div>', unsafe_allow_html=True)
if bmkg_df.empty:
    st.warning("BMKG forecast is temporarily unavailable. Historical climate analytics remain unchanged.")
else:
    locs = sorted(bmkg_df["location"].dropna().unique().tolist())
    selected_bmkg = st.selectbox("BMKG location", ["All locations"] + locs, key="bmkg_location")
    local_view = bmkg_df.copy() if selected_bmkg == "All locations" else bmkg_df[bmkg_df["location"] == selected_bmkg].copy()
    if not local_view.empty:
        latest = local_view.sort_values("local_datetime").groupby("location", as_index=False).tail(1)
        cols = st.columns(min(5, max(1, len(latest))))
        for col, (_, row) in zip(cols, latest.iterrows()):
            weather = row.get("weather_desc_en") or row.get("weather_desc") or "—"
            with col:
                st.metric(str(row["location"]), f"{row['temperature_c']:.1f} °C" if pd.notna(row.get("temperature_c")) else "—", weather)

        forecast_cols = ["location", "adm4", "latitude", "longitude", "local_datetime", "temperature_c", "humidity_pct", "precipitation_mm", "wind_speed_ms", "wind_direction", "cloud_cover_pct", "visibility", "weather_desc_en", "analysis_date"]
        available = [c for c in forecast_cols if c in local_view.columns]
        forecast_raw = local_view[available].sort_values(["location", "local_datetime"]).copy()
        forecast_display = forecast_raw.rename(columns={"local_datetime":"Local time", "temperature_c":"Temp (°C)", "humidity_pct":"RH (%)", "precipitation_mm":"Precipitation (mm)", "wind_speed_ms":"Wind (m/s)", "wind_direction":"Wind direction", "cloud_cover_pct":"Cloud (%)", "weather_desc_en":"Weather"})
        st.dataframe(forecast_display, use_container_width=True, hide_index=True)
        add_downloads(forecast_raw, f"SERPRO_BMKG_Forecast_{pd.Timestamp.now().strftime('%Y%m%d')}", "BMKG Forecast", "bmkg_forecast")
        q = bmkg_meta.get("quality")
        if q is not None and not q.empty:
            with st.expander("BMKG data quality & provenance"):
                st.dataframe(q, use_container_width=True, hide_index=True)
                st.write(f"Fetched (UTC): {bmkg_meta.get('fetched_at_utc', '—')}")
                st.caption("Latitude and longitude are included in the download so the five ADM4 forecast locations can be recreated in GIS applications.")

# -----------------------------------------------------------------------------
# 2. BMKG SPATIAL FORECAST
# -----------------------------------------------------------------------------
st.markdown('<div class="section">🗺️ BMKG Spatial Weather Forecast</div>', unsafe_allow_html=True)
st.markdown('<div class="note">Five BMKG ADM4 forecast points interpolated using IDW and clipped to the selected SERPRO boundary. This represents forecast conditions, not direct station observations.</div>', unsafe_allow_html=True)
spatial_path = BMKG_SURFACES.get(scope)
if spatial_path is None or not spatial_path.exists():
    st.info("BMKG spatial forecast surface is not available yet for the selected monitoring area.")
else:
    try:
        spatial_df = load_spatial_surface(spatial_path)
    except Exception as exc:
        spatial_df = pd.DataFrame()
        st.warning(f"Could not read BMKG spatial forecast: {exc}")
    if not spatial_df.empty:
        if "forecast_datetime" in spatial_df.columns:
            spatial_df["forecast_datetime"] = pd.to_datetime(spatial_df["forecast_datetime"], errors="coerce")
        variables = {"Precipitation (mm)":"precipitation_mm", "Temperature (°C)":"temperature_c", "Humidity (%)":"humidity_pct", "Cloud cover (%)":"cloud_cover_pct", "Wind speed (m/s)":"wind_speed_ms"}
        c1, c2 = st.columns(2)
        with c1:
            variable_label = st.selectbox("Forecast variable", list(variables.keys()), key="bmkg_spatial_variable")
        with c2:
            timestamps = sorted(spatial_df["forecast_datetime"].dropna().unique()) if "forecast_datetime" in spatial_df.columns else []
            selected_ts = st.selectbox("Forecast time", timestamps, format_func=lambda x: pd.Timestamp(x).strftime("%d %b %Y · %H:%M"), key="bmkg_spatial_time") if timestamps else None
        spatial_view = spatial_df[spatial_df["forecast_datetime"] == selected_ts].copy() if selected_ts is not None else spatial_df.copy()
        value_col = variables[variable_label]
        if value_col in spatial_view.columns:
            spatial_view[value_col] = pd.to_numeric(spatial_view[value_col], errors="coerce")
            spatial_view = spatial_view.dropna(subset=["longitude", "latitude", value_col])
        if spatial_view.empty:
            st.info("No valid BMKG spatial forecast cells for the selected variable/time.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Forecast cells", f"{len(spatial_view):,}")
            m2.metric("Minimum", f"{spatial_view[value_col].min():.2f}")
            m3.metric("Mean", f"{spatial_view[value_col].mean():.2f}")
            m4.metric("Maximum", f"{spatial_view[value_col].max():.2f}")
            fig = px.scatter_mapbox(spatial_view, lat="latitude", lon="longitude", color=value_col, color_continuous_scale="Viridis", hover_data={"latitude":":.5f", "longitude":":.5f", value_col:":.2f", "forecast_datetime":True}, zoom=9, height=520, labels={value_col:variable_label})
            fig.update_traces(marker={"size":8,"opacity":0.72})
            fig.update_layout(mapbox_style="open-street-map", margin={"l":0,"r":0,"t":10,"b":0}, coloraxis_colorbar={"title":variable_label})
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            st.caption(f"Source: BMKG ADM4 forecast points + IDW · Boundary: {scope.replace('_',' ').title()} · 1 km grid.")
            spatial_download_cols = [c for c in ["latitude","longitude","forecast_datetime","precipitation_mm","temperature_c","humidity_pct","cloud_cover_pct","wind_speed_ms"] if c in spatial_view.columns]
            spatial_download = spatial_view[spatial_download_cols].sort_values(["latitude","longitude"]).copy()
            add_downloads(spatial_download, f"SERPRO_BMKG_IDW_{scope}_{pd.Timestamp(selected_ts).strftime('%Y%m%d_%H%M') if selected_ts is not None else 'latest'}", "IDW Surface", "bmkg_spatial")
            with st.expander("Spatial forecast data"):
                st.dataframe(spatial_download, use_container_width=True, hide_index=True)
            geojson_bytes = spatial_path.read_bytes()
            st.download_button("🗺️ Download GeoJSON", geojson_bytes, file_name=spatial_path.name, mime="application/geo+json", key="bmkg_geojson")

# -----------------------------------------------------------------------------
# 3. HISTORICAL CLIMATE
# -----------------------------------------------------------------------------
st.markdown('<div class="section">📊 Historical Climate</div>', unsafe_allow_html=True)
st.markdown('<div class="note">Historical rainfall, anomaly, drought/wetness indicators and climate risk. BMKG forecast is deliberately excluded from these calculations.</div>', unsafe_allow_html=True)
if scoped.empty:
    st.warning("Tidak ada data pada periode yang dipilih.")
    st.stop()
latest_row = scoped.iloc[-1]
latest_date = latest_row["date"]
latest_value = float(latest_row["rainfall_mm"])
selected_30d = float(scoped.tail(30)["rainfall_mm"].sum())
source = str(latest_row.get("source", "—"))
processed_at = str(latest_row.get("processing_time_utc", "—"))
source_label = {"NASA/GPM_L3/IMERG_V07":"NASA GPM IMERG V07"}.get(source, source)

k1,k2,k3,k4 = st.columns(4)
k1.metric("Latest rainfall", f"{latest_value:.2f} mm", f"{latest_date.date()}")
k2.metric("Rainfall · 30 days", f"{selected_30d:.1f} mm")
anom_latest = None
selected_anom = pd.DataFrame()
if not anomaly.empty:
    anomaly["date"] = pd.to_datetime(anomaly["date"], errors="coerce")
    selected_anom = anomaly[(anomaly["scope"] == scope) & (anomaly["date"] >= pd.Timestamp(start_date)) & (anomaly["date"] <= pd.Timestamp(end_date))].sort_values("date")
    if not selected_anom.empty and pd.notna(selected_anom.iloc[-1].get("anomaly_30d_pct")):
        anom_latest = float(selected_anom.iloc[-1]["anomaly_30d_pct"])
k3.metric("30-day anomaly", f"{anom_latest:+.1f}%" if anom_latest is not None else "—")
risk_level = "—"
selected_risk = pd.DataFrame()
if not risk.empty:
    risk["date"] = pd.to_datetime(risk["date"], errors="coerce")
    selected_risk = risk[(risk["scope"] == scope) & (risk["date"] <= pd.Timestamp(end_date))].sort_values("date")
    if not selected_risk.empty:
        risk_level = str(selected_risk.iloc[-1].get("risk_level", "—")).replace("_", " ").title()
k4.metric("Climate risk", risk_level)

st.markdown('<div class="section">📈 Rainfall trend</div>', unsafe_allow_html=True)
fig = px.line(scoped, x="date", y="rainfall_mm", markers=True, labels={"date":"Date","rainfall_mm":"Rainfall (mm/day)"})
fig.update_layout(height=360, margin=dict(l=10,r=10,t=20,b=10), hovermode="x unified")
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
add_downloads(scoped, f"SERPRO_Historical_Rainfall_{scope}_{start_date}_{end_date}", "Rainfall", "hist_rainfall")

if not selected_anom.empty:
    st.markdown('<div class="section">📊 Rainfall anomaly</div>', unsafe_allow_html=True)
    fig2 = px.line(selected_anom, x="date", y="anomaly_30d_pct", markers=True, labels={"date":"Date","anomaly_30d_pct":"30-day anomaly (%)"})
    fig2.add_hline(y=0, line_dash="dash")
    fig2.update_layout(height=310, margin=dict(l=10,r=10,t=20,b=10), hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})
    add_downloads(selected_anom, f"SERPRO_Rainfall_Anomaly_{scope}_{start_date}_{end_date}", "Anomaly", "anomaly")

st.markdown('<div class="section">💧 Drought / wetness indicators</div>', unsafe_allow_html=True)
if spi.empty:
    st.info("SPI-3/SPI-6 belum tersedia untuk periode ini.")
else:
    spi["date"] = pd.to_datetime(spi["date"], errors="coerce")
    current_spi = spi[(spi["scope"] == scope) & (spi["date"] <= pd.Timestamp(end_date))].sort_values("date")
    if current_spi.empty:
        st.info("SPI-3/SPI-6 belum tersedia untuk periode ini.")
    else:
        latest_spi_date = current_spi["date"].max()
        latest_spi = current_spi[current_spi["date"] == latest_spi_date]
        s3 = latest_spi[latest_spi["period"] == "SPI-3"]
        s6 = latest_spi[latest_spi["period"] == "SPI-6"]
        sp1,sp2,sp3,sp4 = st.columns(4)
        sp1.metric("SPI-3", f"{float(s3.iloc[0]['spi']):+.2f}" if not s3.empty and pd.notna(s3.iloc[0].get("spi")) else "—")
        sp2.metric("SPI-3 status", str(s3.iloc[0].get("spi_status","Insufficient data")).replace("_"," ").title() if not s3.empty else "Insufficient data")
        sp3.metric("SPI-6", f"{float(s6.iloc[0]['spi']):+.2f}" if not s6.empty and pd.notna(s6.iloc[0].get("spi")) else "—")
        sp4.metric("SPI-6 status", str(s6.iloc[0].get("spi_status","Insufficient data")).replace("_"," ").title() if not s6.empty else "Insufficient data")
        st.caption(f"Latest SPI calculation: {latest_spi_date.date()} · Below zero = drier-than-normal; above zero = wetter-than-normal.")
        add_downloads(current_spi, f"SERPRO_SPI_{scope}_{latest_spi_date.strftime('%Y%m%d')}", "SPI", "spi")

if not selected_risk.empty:
    st.markdown('<div class="section">⚠️ Climate Risk Assessment</div>', unsafe_allow_html=True)
    st.dataframe(selected_risk, use_container_width=True, hide_index=True)
    add_downloads(selected_risk, f"SERPRO_Climate_Risk_{scope}_{start_date}_{end_date}", "Climate Risk", "risk")

st.markdown('<div class="section">ℹ️ Data Quality & Information</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="info">
<b>Historical rainfall source:</b> {source_label} · <b>Monitoring area:</b> {scope.replace('_',' ').title()} · <b>Selected period:</b> {start_date} → {end_date} · <b>Observations:</b> {len(scoped)} · <b>Latest processing:</b> {processed_at}.<br><br>
<b>BMKG:</b> five ADM4 pilot-village forecasts, refreshed routinely, spatially interpolated with IDW and clipped to Project Area / Carbon Project Zone. BMKG forecast is operational information only and is <b>not included</b> in historical rainfall, anomaly, SPI or Climate Risk calculations.
</div>
""", unsafe_allow_html=True)

with st.expander("Download standard & reproducibility"):
    st.markdown("**Spatial downloads include latitude and longitude whenever the dataset has point/grid geometry.** BMKG ADM4 and IDW outputs can therefore be recreated in QGIS, ArcGIS, Google Earth Engine, Python or R. Spatial forecast is also available as GeoJSON for direct GIS use.")
    st.markdown("**Recommended formats:** Excel for analysis/reporting, CSV for interoperability, GeoJSON for spatial GIS workflows.")

st.caption("SERPRO Climate Monitoring · Historical evidence and operational forecast are intentionally separated for transparent interpretation and auditability.")
