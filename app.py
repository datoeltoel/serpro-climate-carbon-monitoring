import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path
from streamlit_folium import st_folium

from utils.demo_data import load_demo_data
from utils.scope_engine import get_scope, scope_options, SPATIAL_RELATIONSHIP
from utils.ui import setup_page
from utils.map import load_carbon_project_zone, load_project_area, render_map
from utils.climate.fire import load_fire
from utils.climate.anomaly import load_anomaly
from utils.climate.vegetation import load_ndmi
from utils.climate.rainfall import load_rainfall

setup_page()
data = load_demo_data()

st.markdown('<div class="brand">🌿 SERPRO Climate & Carbon Monitoring <span class="prototype-badge">PROTOTYPE</span></div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Seruyan Restoration Ecosystem Project (SERPRO) · PT Kalamanthana Alam Lestari</div>', unsafe_allow_html=True)
st.markdown('<div class="status">● Prototype · Official project boundaries loaded · Live climate/fire modules connected incrementally</div>', unsafe_allow_html=True)

project_area = load_project_area()
project_zone = load_carbon_project_zone()
project_area_scope = get_scope("SERPRO Project Area")
project_zone_scope = get_scope("SERPRO Carbon Project Zone")
project_area_ha = project_area_scope.area_ha
project_zone_area_ha = project_zone_scope.area_ha
containment = min(100.0, SPATIAL_RELATIONSHIP["project_area_containment_percent"])
zone_share = SPATIAL_RELATIONSHIP["project_area_share_of_carbon_zone_percent"]

st.markdown('<div class="section-title">Project Landscape Summary</div>', unsafe_allow_html=True)
st.markdown(f'''<div class="landscape-summary">
<div class="landscape-intro"><b>Unified SERPRO Project Landscape</b><br>The Carbon Project Zone is the primary spatial envelope of the SERPRO landscape, with the Project Area forming a contained sub-area.</div>
<div class="landscape-grid">
<div class="landscape-card zone-card"><div class="landscape-icon">🟣</div><div class="landscape-label">SERPRO Carbon Project Zone</div><div class="landscape-value">{project_zone_area_ha:,.2f} ha</div><div class="landscape-meta">Primary project-zone envelope · ProjectZone.kmz</div></div>
<div class="landscape-connector">↓<span>CONTAINS</span></div>
<div class="landscape-card area-card"><div class="landscape-icon">🟢</div><div class="landscape-label">SERPRO Project Area</div><div class="landscape-value">{project_area_ha:,.2f} ha</div><div class="landscape-meta">PT KAL concession / project area · KAL_Boundary_Split.kml</div></div>
</div>
<div class="landscape-note">Spatial analysis confirms the Project Area is effectively fully contained within the Carbon Project Zone.</div>
</div>''', unsafe_allow_html=True)

summary_map_col, summary_info_col = st.columns([2.4, 1])
with summary_map_col:
    st_folium(render_map(data["hotspots"], data["monitoring_points"], focus="All Boundaries"), width=None, height=430, returned_objects=[], key="project_landscape_summary_map")
with summary_info_col:
    st.markdown(f'''<div class="risk-card"><div><b>SPATIAL RELATIONSHIP</b></div><div class="risk-number">≈{containment:.0f}%</div><div class="risk-label">PROJECT AREA WITHIN CARBON ZONE</div><hr><p><b>Intersection</b><br>{SPATIAL_RELATIONSHIP['intersection_area_ha']:,.5f} ha</p><p><b>Union</b><br>{SPATIAL_RELATIONSHIP['union_area_ha']:,.6f} ha</p><p><b>Project Area share of Carbon Zone</b><br>{zone_share:.2f}%</p></div>''', unsafe_allow_html=True)

st.markdown('<div class="section-title">Monitoring Scope</div>', unsafe_allow_html=True)
scope = st.selectbox("Select monitoring scope", scope_options(), index=1, format_func=lambda x: {"SERPRO Project Landscape":"🌐 SERPRO Project Landscape","SERPRO Carbon Project Zone":"🟣 Carbon Project Zone","SERPRO Project Area":"🟢 Project Area"}[x])
selected_scope = get_scope(scope)
st.caption(f"Active scope: **{selected_scope.label}** · Area: **{selected_scope.area_ha:,.2f} ha** · {selected_scope.role}")

cols = st.columns(6)
metrics = [("🗺️ Landscape", f"{project_zone_area_ha:,.0f} ha", "Carbon Zone envelope"),("🟣 Carbon Zone", f"{project_zone_area_ha:,.0f} ha", "official ProjectZone area"),("🟢 Project Area", f"{project_area_ha:,.0f} ha", f"{zone_share:.2f}% of Carbon Zone"),("🌧 Rainfall", "Live", "GPM IMERG"),("🔥 Hotspots", "Live", "VIIRS"),("🟣 Carbon Risk", "Live", "screening")]
for col, (label, value, delta) in zip(cols, metrics):
    with col:
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-delta">{delta}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Project WebGIS & Climate Risk</div>', unsafe_allow_html=True)
map_col, risk_col = st.columns([2.1, 1])
with map_col:
    focus = "All Boundaries" if scope == "SERPRO Project Landscape" else scope
    st_folium(render_map(data["hotspots"], data["monitoring_points"], focus=focus), width=None, height=500, returned_objects=[], key="monitoring_scope_map")
with risk_col:
    st.markdown('<div class="risk-card"><div>CLIMATE RISK INDEX</div><div class="risk-number">LIVE</div><div class="risk-label">See Climate Risk page</div><hr><p>Use the dedicated Climate Risk module for the integrated screening score.</p></div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# LIVE TREND EXPLORER
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">📈 Monitoring Trends</div>', unsafe_allow_html=True)
st.caption("Annual and monthly trends are sourced from connected processed datasets. Monthly availability depends on the selected indicator.")

trend_col1, trend_col2, trend_col3 = st.columns([1.4, 1.2, 1.2])
with trend_col1:
    trend_indicator = st.selectbox("Indicator", ["Rainfall", "Hotspots", "Burned Area", "NDMI"], key="trend_indicator")
with trend_col2:
    granularity = st.selectbox("Aggregation", ["Monthly", "Annual"], key="trend_granularity")
with trend_col3:
    trend_scope = st.selectbox("Trend scope", ["carbon_project_zone", "project_area"], index=0, format_func=lambda x: "Carbon Project Zone" if x == "carbon_project_zone" else "Project Area", key="trend_scope")

trend_df = pd.DataFrame()
trend_source = ""

if trend_indicator == "Rainfall":
    path = Path("data/processed/climate/rainfall/chirps_monthly_1981_2025.csv")
    if path.exists():
        rain_hist = pd.read_csv(path)
        rain_hist = rain_hist[rain_hist["scope"] == trend_scope].copy()
        rain_hist["year"] = pd.to_numeric(rain_hist["year"], errors="coerce")
        rain_hist["month"] = pd.to_numeric(rain_hist["month"], errors="coerce")
        rain_hist["date"] = pd.to_datetime(dict(year=rain_hist["year"], month=rain_hist["month"], day=1), errors="coerce")
        if granularity == "Monthly":
            trend_df = rain_hist[["date", "rainfall_mm"]].sort_values("date")
            trend_source = "CHIRPS v2 Final · monthly historical rainfall · 1981–2025"
            ylabel = "Rainfall (mm/month)"
        else:
            trend_df = rain_hist.groupby("year", as_index=False)["rainfall_mm"].sum().rename(columns={"year":"date"})
            trend_source = "CHIRPS v2 Final · annual sum of monthly rainfall · 1981–2025"
            ylabel = "Rainfall (mm/year)"
    else:
        st.warning("Historical CHIRPS monthly dataset belum tersedia.")
        ylabel = "Rainfall"

elif trend_indicator == "Hotspots":
    if granularity == "Annual":
        path = Path("data/processed/climate/fire/hotspot_history_2017_2025.csv")
        if path.exists():
            hist = pd.read_csv(path)
            hist = hist[hist["scope"] == trend_scope].copy()
            trend_df = hist[["year", "hotspot_detections"]].rename(columns={"year":"date"}).sort_values("date")
            trend_source = "MODIS Terra MOD14A1.061 · annual fire-pixel detections · 2017–2025"
            ylabel = "Hotspot detections"
    else:
        fire = load_fire()
        if not fire.empty:
            fire["date"] = pd.to_datetime(fire["date"], errors="coerce")
            fire = fire[fire["scope"] == trend_scope].copy()
            trend_df = fire.assign(month=fire["date"].dt.to_period("M").dt.to_timestamp()).groupby("month").size().reset_index(name="hotspot_detections").rename(columns={"month":"date"})
            trend_source = "NASA LANCE VIIRS S-NPP + NOAA-20 · current connected observations"
            ylabel = "Hotspot observations"
        else:
            ylabel = "Hotspot observations"
            st.info("Belum ada live hotspot data untuk tren bulanan.")

elif trend_indicator == "Burned Area":
    if granularity == "Annual":
        path = Path("data/processed/climate/fire/burned_area_annual_2016_2025.csv")
        if path.exists():
            burn = pd.read_csv(path)
            burn = burn[burn["scope"] == trend_scope].copy()
            trend_df = burn[["year", "burned_area_ha"]].rename(columns={"year":"date"}).sort_values("date")
            trend_source = "MODIS MCD64A1.061 · annual burned area · 2016–2025"
            ylabel = "Burned area (ha)"
    else:
        ylabel = "Burned area (ha)"
        st.info("Burned Area tersedia saat ini sebagai seri tahunan 2016–2025. Pilih Aggregation = Annual.")

else:  # NDMI
    ndmi = load_ndmi()
    if not ndmi.empty:
        ndmi = ndmi[ndmi["scope"] == trend_scope].copy()
        ndmi["date"] = pd.to_datetime(ndmi["date"], errors="coerce")
        if granularity == "Monthly":
            trend_df = ndmi.assign(month=ndmi["date"].dt.to_period("M").dt.to_timestamp()).groupby("month", as_index=False)["ndmi"].mean().rename(columns={"month":"date"}).sort_values("date")
            trend_source = "Sentinel-2 SR Harmonized · monthly mean NDMI from connected scenes"
            ylabel = "NDMI"
        else:
            trend_df = ndmi.assign(year=ndmi["date"].dt.year).groupby("year", as_index=False)["ndmi"].mean().rename(columns={"year":"date"}).sort_values("date")
            trend_source = "Sentinel-2 SR Harmonized · annual mean NDMI from connected scenes"
            ylabel = "NDMI"
    else:
        ylabel = "NDMI"
        st.info("Belum ada connected NDMI data untuk tren.")

if not trend_df.empty:
    trend_df = trend_df.copy()
    numeric_cols = [c for c in trend_df.columns if c != "date"]
    value_col = numeric_cols[0]
    if granularity == "Monthly":
        min_date = pd.to_datetime(trend_df["date"]).min().date()
        max_date = pd.to_datetime(trend_df["date"]).max().date()
        date_range = st.date_input("Filter trend period", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="trend_date_range")
        if isinstance(date_range, tuple) and len(date_range) == 2:
            trend_df["date"] = pd.to_datetime(trend_df["date"])
            trend_df = trend_df[(trend_df["date"].dt.date >= date_range[0]) & (trend_df["date"].dt.date <= date_range[1])]
    else:
        years = sorted(pd.Series(trend_df["date"]).astype(int).unique())
        if len(years) > 1:
            selected_years = st.slider("Filter year", min_value=int(min(years)), max_value=int(max(years)), value=(int(min(years)), int(max(years))), key="trend_year_range")
            trend_df = trend_df[(trend_df["date"] >= selected_years[0]) & (trend_df["date"] <= selected_years[1])]

    if not trend_df.empty:
        x = pd.to_datetime(trend_df["date"]) if granularity == "Monthly" else trend_df["date"]
        fig = px.line(trend_df, x=x, y=value_col, markers=True, labels={"x":"Date", value_col:ylabel}, title=f"{trend_indicator} · {granularity} · {trend_scope.replace('_',' ').title()}")
        fig.update_layout(height=360, margin=dict(l=20,r=20,t=55,b=20), hovermode="x unified")
        if granularity == "Monthly":
            fig.update_xaxes(rangeslider_visible=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"Source: {trend_source}")
    else:
        st.info("Tidak ada observasi pada filter yang dipilih.")

# -----------------------------------------------------------------------------
# Recent live alerts
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">🚨 Recent Alerts</div>', unsafe_allow_html=True)
alerts_live = []
try:
    fire = load_fire()
    if not fire.empty:
        fire_latest = fire[fire["date"] == fire["date"].max()].copy()
        fire_latest = fire_latest[fire_latest["confidence"] == 2]
        for _, row in fire_latest.head(5).iterrows():
            scope_label = {"project_area":"SERPRO Project Area","carbon_project_zone":"SERPRO Carbon Project Zone"}.get(str(row.get("scope")), str(row.get("scope","SERPRO")))
            priority = "HIGH" if row.get("scope") == "project_area" else "MODERATE"
            alerts_live.append({"type":"🔥 High-confidence hotspot","location":scope_label,"date":pd.to_datetime(row["date"]).strftime("%d %b %Y"),"level":priority,"action":"FIELD ALERT" if priority=="HIGH" else "VERIFY","detail":f"VIIRS · {float(row['latitude']):.4f}, {float(row['longitude']):.4f}"})
except Exception:
    pass

try:
    anom = load_anomaly()
    if not anom.empty and "anomaly_30d_pct" in anom.columns:
        anom["date"] = pd.to_datetime(anom["date"], errors="coerce")
        latest_anom_date = anom["date"].max()
        for _, row in anom[anom["date"] == latest_anom_date].iterrows():
            value = row.get("anomaly_30d_pct")
            if pd.notna(value) and float(value) <= -30:
                scope_label = {"project_area":"SERPRO Project Area","carbon_project_zone":"SERPRO Carbon Project Zone"}.get(str(row.get("scope")), str(row.get("scope","SERPRO")))
                alerts_live.append({"type":"🌧 Rainfall anomaly","location":scope_label,"date":latest_anom_date.strftime("%d %b %Y"),"level":"MODERATE","action":"REVIEW","detail":f"30-day anomaly {float(value):+.1f}%"})
except Exception:
    pass

try:
    ndmi = load_ndmi()
    if not ndmi.empty and "ndmi" in ndmi.columns:
        ndmi["date"] = pd.to_datetime(ndmi["date"], errors="coerce")
        for scope_key, group in ndmi.groupby("scope"):
            group = group.sort_values("date")
            if len(group) < 2:
                continue
            latest = group.iloc[-1]
            prev = group.iloc[-2]
            change = float(latest["ndmi"]) - float(prev["ndmi"])
            if change <= -0.08:
                scope_label = {"project_area":"SERPRO Project Area","carbon_project_zone":"SERPRO Carbon Project Zone"}.get(str(scope_key), str(scope_key))
                alerts_live.append({"type":"🌿 NDMI decline","location":scope_label,"date":pd.to_datetime(latest["date"]).strftime("%d %b %Y"),"level":"MODERATE","action":"REVIEW","detail":f"NDMI change {change:+.3f}"})
except Exception:
    pass

if not alerts_live:
    st.success("No active live alerts in the connected monitoring modules for the latest available observations.")
else:
    level_styles = {"HIGH":("#D32F2F","#FFF6F6"),"MODERATE":("#F9A825","#FFFCF2"),"LOW":("#4C8BF5","#F5F9FF")}
    for alert in alerts_live[:8]:
        accent, bg = level_styles.get(alert["level"], ("#4C8BF5","#F5F9FF"))
        st.markdown(f'''<div style="border-left:5px solid {accent};background:{bg};padding:12px 14px;border-radius:8px;margin:7px 0;"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;"><div><b>{alert['type']}</b><br><span style="font-size:.82rem;color:#5F6D67;">{alert['location']} · {alert['date']} · {alert['detail']}</span></div><div style="white-space:nowrap;text-align:right;"><b style="color:{accent};">{alert['level']}</b><br><span style="font-size:.74rem;color:#65736D;">→ {alert['action']}</span></div></div></div>''', unsafe_allow_html=True)

st.caption("Prototype status: Recent Alerts are generated only from connected live monitoring outputs. Trend Explorer uses connected historical datasets where available; demo/sample trends are no longer used for the analytical charts.")
