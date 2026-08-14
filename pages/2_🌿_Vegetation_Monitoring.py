from copy import deepcopy

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from utils.climate.vegetation import load_ndmi, load_ndvi, load_vegetation_spatial
from utils.map import load_carbon_project_zone, load_project_area
from utils.ui import setup_page

setup_page()

st.markdown("""
<style>
.veg-kpi{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:14px 15px;min-height:112px;box-shadow:0 2px 8px rgba(15,23,42,.05)}
.veg-kpi-label{font-size:.72rem;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.veg-kpi-value{font-size:1.55rem;font-weight:800;line-height:1.15;margin-top:7px;color:#0f172a;word-break:break-word}
.veg-kpi-sub{font-size:.76rem;margin-top:7px;font-weight:700}
.spatial-card{background:linear-gradient(145deg,#ffffff 0%,#f8fafc 100%);border:1px solid #e2e8f0;border-radius:18px;padding:18px;box-shadow:0 5px 18px rgba(15,23,42,.07);margin-bottom:10px}
.spatial-card-title{font-size:1rem;font-weight:800;color:#0f172a;margin-bottom:12px}
.spatial-section{font-size:.68rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin:14px 0 7px}
.spatial-row{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid #eef2f7;font-size:.82rem}
.spatial-label{color:#64748b}.spatial-value{color:#0f172a;font-weight:750;text-align:right}
.confidence{border-radius:12px;padding:11px 12px;margin-top:14px;font-weight:800;font-size:.84rem}
.conf-high{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}.conf-medium{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}.conf-low{background:#ffedd5;color:#9a3412;border:1px solid #fed7aa}
@media(max-width:768px){.veg-kpi{min-height:100px;padding:11px}.veg-kpi-value{font-size:1.28rem}.veg-kpi-label{font-size:.66rem}.veg-kpi-sub{font-size:.70rem}}
</style>
""", unsafe_allow_html=True)

st.markdown("# 🌿 Vegetation Monitoring")
st.caption("SERPRO Project · Sentinel-2 vegetation health, vigor, canopy moisture and spatial stress screening")

ndmi = load_ndmi()
ndvi = load_ndvi()
spatial = load_vegetation_spatial()
for df in (ndmi, ndvi):
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

if ndmi.empty and ndvi.empty:
    st.info("No NDVI/NDMI data is currently available. Run the vegetation update workflows.")
    st.stop()

scope_keys = sorted(set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str)) | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str)))
if not scope_keys:
    st.error("Vegetation data has no valid monitoring scope.")
    st.stop()
scope_labels = {"carbon_project_zone":"🟣 Carbon Project Zone", "project_area":"🟢 Project Area"}
c_scope, c_period = st.columns([1.15, 1], gap="medium")
with c_scope:
    scope = st.selectbox("Monitoring scope", scope_keys, index=scope_keys.index("carbon_project_zone") if "carbon_project_zone" in scope_keys else 0, format_func=lambda x: scope_labels.get(x, x.replace("_", " ").title()))
ndvi_s = ndvi[ndvi["scope"].astype(str) == scope].copy() if not ndvi.empty else pd.DataFrame()
ndmi_s = ndmi[ndmi["scope"].astype(str) == scope].copy() if not ndmi.empty else pd.DataFrame()
all_dates = pd.concat([x["date"] for x in (ndvi_s, ndmi_s) if not x.empty], ignore_index=True).dropna()
with c_period:
    if not all_dates.empty:
        min_date, max_date = all_dates.min().date(), all_dates.max().date()
        date_range = st.date_input("Monitoring period", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    else:
        date_range = None

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start = pd.Timestamp(date_range[0])
    end = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    ndvi_p = ndvi_s[(ndvi_s.date >= start) & (ndvi_s.date <= end)].copy()
    ndmi_p = ndmi_s[(ndmi_s.date >= start) & (ndmi_s.date <= end)].copy()
else:
    ndvi_p, ndmi_p = ndvi_s.copy(), ndmi_s.copy()
ndvi_p = ndvi_p.sort_values("date") if not ndvi_p.empty else ndvi_p
ndmi_p = ndmi_p.sort_values("date") if not ndmi_p.empty else ndmi_p


def pct_change(df, col, days):
    if df.empty or col not in df.columns or len(df) < 2:
        return None
    latest = df.date.max()
    w = df[df.date >= latest - pd.Timedelta(days=days)]
    if len(w) < 2:
        return None
    first, last = float(w.iloc[0][col]), float(w.iloc[-1][col])
    return None if first == 0 else (last - first) / abs(first) * 100


def ndvi_status(v):
    if v is None or pd.isna(v): return "No data", "#64748b"
    if float(v) >= .70: return "Good vigor", "#15803d"
    if float(v) >= .50: return "Moderate vigor", "#b45309"
    if float(v) >= .30: return "Low vigor", "#c2410c"
    return "Very low vigor", "#b91c1c"


def ndmi_status(v):
    if v is None or pd.isna(v): return "No data", "#64748b"
    if float(v) >= .40: return "Moist", "#15803d"
    if float(v) >= .20: return "Moderate", "#b45309"
    if float(v) >= 0: return "Drying", "#c2410c"
    return "Low moisture", "#b91c1c"

latest_ndvi = float(ndvi_p.iloc[-1].ndvi) if not ndvi_p.empty else None
latest_ndmi = float(ndmi_p.iloc[-1].ndmi) if not ndmi_p.empty else None
ndvi30 = pct_change(ndvi_p, "ndvi", 30)
ndmi30 = pct_change(ndmi_p, "ndmi", 30)
ndvi_label, ndvi_color = ndvi_status(latest_ndvi)
ndmi_label, ndmi_color = ndmi_status(latest_ndmi)
if ndvi30 is not None and ndmi30 is not None and ndvi30 <= -10 and ndmi30 <= -10:
    stress_level = "HIGH"
elif (ndvi30 is not None and ndvi30 <= -10) or (ndmi30 is not None and ndmi30 <= -10):
    stress_level = "MODERATE"
elif (ndvi30 is not None and ndvi30 < 0) or (ndmi30 is not None and ndmi30 < 0):
    stress_level = "LOW"
else:
    stress_level = "STABLE"
stress_color = {"HIGH":"#b91c1c", "MODERATE":"#b45309", "LOW":"#2563eb", "STABLE":"#15803d"}[stress_level]

st.markdown("### 🌱 Vegetation Condition Overview")
kpis = [
    ("🌿", "NDVI", f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—", ndvi_label, ndvi_color),
    ("💧", "NDMI", f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—", ndmi_label, ndmi_color),
    ("📉", "NDVI · 30D", f"{ndvi30:+.1f}%" if ndvi30 is not None else "—", "vs. 30 days", "#b91c1c" if ndvi30 is not None and ndvi30 < 0 else "#15803d"),
    ("💦", "NDMI · 30D", f"{ndmi30:+.1f}%" if ndmi30 is not None else "—", "vs. 30 days", "#b91c1c" if ndmi30 is not None and ndmi30 < 0 else "#15803d"),
    ("⚠️", "VEGETATION STRESS", stress_level, "NDVI + NDMI screening", stress_color),
]
cols = st.columns(5, gap="small")
for col, (icon, title, value, sub, color) in zip(cols, kpis):
    with col:
        st.markdown(f'<div class="veg-kpi"><div class="veg-kpi-label">{icon} {title}</div><div class="veg-kpi-value">{value}</div><div class="veg-kpi-sub" style="color:{color}">{sub}</div></div>', unsafe_allow_html=True)
if stress_level == "HIGH":
    st.error("🚨 High vegetation stress: both NDVI and NDMI declined by at least 10% over the last 30 days. Prioritize field verification.")
elif stress_level == "MODERATE":
    st.warning("⚠️ Moderate vegetation stress: at least one indicator declined by 10% or more over the last 30 days. Review spatial context.")
elif stress_level == "LOW":
    st.info("ℹ️ Low vegetation stress signal: a recent decline is present, but the moderate threshold has not been reached.")
else:
    st.success("✅ No vegetation stress signal detected under the current screening rules.")


def bounds_from_geojson(collection):
    points = []
    for feature in collection.get("features", []):
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates", [])
        if geom.get("type") == "Polygon":
            rings = coords
        elif geom.get("type") == "MultiPolygon":
            rings = [ring for polygon in coords for ring in polygon]
        else:
            rings = []
        for ring in rings:
            points.extend(ring)
    if not points:
        return None
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def build_vegetation_map():
    m = folium.Map(location=[-3.10, 112.62], zoom_start=9, tiles=None, control_scale=True)
    folium.TileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", attr="© OpenStreetMap contributors", name="OpenStreetMap", overlay=False, show=True).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Tiles © Esri", name="Satellite imagery · Esri World Imagery", overlay=False, show=False).add_to(m)

    project_area = load_project_area()
    zone = load_carbon_project_zone()
    if project_area.get("features"):
        folium.GeoJson(project_area, name="🟢 SERPRO Project Area", style_function=lambda _: {"color":"#16a34a", "weight":3, "fillOpacity":0}).add_to(m)
    if zone.get("features"):
        folium.GeoJson(zone, name="🟣 Carbon Project Zone", style_function=lambda _: {"color":"#7c3aed", "weight":2.5, "fillOpacity":0}).add_to(m)

    def add_spatial_layer(field, label, title):
        layer_data = deepcopy(spatial)
        for feature in layer_data.get("features", []):
            props = feature.setdefault("properties", {})
            props.setdefault("stress", "STABLE")
            props.setdefault("period_days", props.get("requested_period_days", 90))
            props.setdefault("scene_count", 0)
            props.setdefault("mean_cloud_cover_pct", 0)
            value = props.get(field)
            props["display_value"] = None if value is None else (str(value) if field == "stress" else round(float(value), 3))
        def style(feature):
            props = feature.get("properties", {})
            value = props.get(field)
            if field == "stress":
                color = {"HIGH":"#dc2626", "MODERATE":"#f59e0b", "LOW":"#eab308", "STABLE":"#16a34a"}.get(value, "#94a3b8")
            else:
                try:
                    x = float(value)
                    color = ("#b91c1c" if x < .3 else "#f59e0b" if x < .5 else "#84cc16" if x < .7 else "#15803d") if field == "ndvi" else ("#b91c1c" if x < 0 else "#f59e0b" if x < .2 else "#84cc16" if x < .4 else "#15803d")
                except (TypeError, ValueError):
                    color = "#94a3b8"
            return {"fillColor": color, "color": color, "weight": .5, "fillOpacity": .68}
        folium.GeoJson(layer_data, name=label, style_function=style, tooltip=folium.GeoJsonTooltip(fields=["display_value", "stress", "period_days", "scene_count", "mean_cloud_cover_pct"], aliases=[title, "Stress", "Composite (days)", "Scenes", "Mean cloud cover (%)"], localize=True, sticky=False)).add_to(m)

    add_spatial_layer("ndvi", "🌿 NDVI · vegetation vigor", "NDVI")
    add_spatial_layer("ndmi", "💧 NDMI · canopy moisture", "NDMI")
    add_spatial_layer("stress", "⚠️ Combined vegetation stress", "Status")

    zone_bounds = bounds_from_geojson(zone)
    if zone_bounds:
        m.fit_bounds(zone_bounds, padding=(12, 12))
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def quality_chart(props):
    observed = float(props.get("observed_pct") or 0)
    temporal = float(props.get("temporal_fallback_pct") or 0)
    spatial_fill = float(props.get("spatial_interpolation_pct") or 0)
    total = float(props.get("total_coverage_pct") or observed + temporal + spatial_fill)
    fig = go.Figure(go.Bar(
        x=[observed, temporal, spatial_fill],
        y=["Observed", "Temporal fallback", "Spatial interpolation"],
        orientation="h",
        text=[f"{observed:.1f}%", f"{temporal:.1f}%", f"{spatial_fill:.1f}%"],
        textposition="outside",
        marker_color=["#16a34a", "#eab308", "#f97316"],
    ))
    fig.update_layout(height=190, margin=dict(l=5, r=55, t=5, b=5), xaxis=dict(range=[0, 105], title="Coverage (%)"), yaxis=dict(autorange="reversed"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown(f"**Total coverage: {total:.1f}%**")


st.markdown("### 🗺️ Spatial Vegetation Condition")
if spatial.get("features"):
    props = spatial["features"][0].get("properties", {})
    map_col, info_col = st.columns([2.15, 1], gap="medium")
    with map_col:
        st_folium(build_vegetation_map(), use_container_width=True, height=520, returned_objects=[], key="vegetation_spatial_map")
    with info_col:
        st.markdown('<div class="spatial-card"><div class="spatial-card-title">📊 Spatial Analysis Overview</div>', unsafe_allow_html=True)
        start_text = props.get("analysis_start") or props.get("composite_start") or "—"
        end_text = props.get("analysis_end") or props.get("composite_end") or "—"
        effective = int(props.get("period_days") or props.get("requested_period_days") or 90)
        requested = int(props.get("requested_period_days") or 90)
        scenes = int(props.get("scene_count") or 0)
        rows = [("Analysis period", f"{start_text} → {end_text}"), ("Effective composite", f"{effective} days"), ("Spatial resolution", "10 × 10 m analysis"), ("Web display grid", f"{int(props.get('display_grid_m') or 100)} m"), ("Boundary", "Carbon Project Zone"), ("Sentinel-2 scenes", f"{scenes:,}"), ("Mean cloud cover", f"{float(props.get('mean_cloud_cover_pct') or 0):.1f}%"), ("Requested period", f"{requested} days")]
        for label, value in rows:
            st.markdown(f'<div class="spatial-row"><span class="spatial-label">{label}</span><span class="spatial-value">{value}</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="spatial-section">Data Quality</div>', unsafe_allow_html=True)
        quality_chart(props)
        observed = float(props.get("observed_pct") or 0)
        if observed >= 85:
            badge = ("🟢 HIGH CONFIDENCE", "conf-high")
        elif observed >= 60:
            badge = ("🟡 MODERATE CONFIDENCE", "conf-medium")
        else:
            badge = ("🟠 LOW CONFIDENCE", "conf-low")
        st.markdown(f'<div class="confidence {badge[1]}">{badge[0]}</div>', unsafe_allow_html=True)
        st.caption("Confidence reflects the share of pixels directly observed by Sentinel-2. Temporal fallback and spatial interpolation are estimated values and are reported separately.")
        st.markdown('</div>', unsafe_allow_html=True)
else:
    st.warning("Spatial vegetation layer is not available yet. Run the Update SERPRO Spatial Vegetation workflow.")

st.markdown("### 📈 Recent Vegetation Trend")
trend_col, interpretation_col = st.columns([1.6, 1], gap="medium")
with trend_col:
    fig = go.Figure()
    if not ndvi_p.empty:
        fig.add_scatter(x=ndvi_p.tail(30).date, y=ndvi_p.tail(30).ndvi, mode="lines+markers", name="NDVI · vigor")
    if not ndmi_p.empty:
        fig.add_scatter(x=ndmi_p.tail(30).date, y=ndmi_p.tail(30).ndmi, mode="lines+markers", name="NDMI · moisture")
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Index", legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with interpretation_col:
    st.markdown("### 🧭 Current Interpretation")
    st.metric("Vegetation vigor", ndvi_label, f"NDVI {latest_ndvi:.3f}" if latest_ndvi is not None else None)
    st.metric("Canopy moisture", ndmi_label, f"NDMI {latest_ndmi:.3f}" if latest_ndmi is not None else None)
    st.metric("Combined stress", stress_level)
    st.caption("Combined stress is a conservative screening indicator and is not standalone evidence of degradation or carbon loss.")

st.markdown("### 🔎 Stress Analysis")
sa1, sa2, sa3 = st.columns(3)
with sa1:
    st.metric("NDVI 30D", f"{ndvi30:+.1f}%" if ndvi30 is not None else "—")
with sa2:
    st.metric("NDMI 30D", f"{ndmi30:+.1f}%" if ndmi30 is not None else "—")
with sa3:
    st.metric("Screening status", stress_level)

st.markdown("### 🗃️ Observation Data")
obs1, obs2 = st.tabs(["NDVI observations", "NDMI observations"])
with obs1:
    st.dataframe(ndvi_p.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
with obs2:
    st.dataframe(ndmi_p.sort_values("date", ascending=False), use_container_width=True, hide_index=True)

if spatial.get("features"):
    st.markdown("### ℹ️ Data & Quality Notes")
    p = spatial["features"][0].get("properties", {})
    st.info(
        f"Sentinel-2 SR Harmonized · analysis scale 10 m · Carbon Project Zone boundary · "
        f"effective composite {int(p.get('period_days') or 90)} days · mean scene cloud cover {float(p.get('mean_cloud_cover_pct') or 0):.1f}%. "
        "The web map displays the complete Carbon Project Zone. Direct observations, temporal fallback and spatial interpolation are explicitly separated in the quality summary."
    )
