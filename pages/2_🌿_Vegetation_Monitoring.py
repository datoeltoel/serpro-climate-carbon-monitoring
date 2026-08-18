from datetime import date

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from folium.raster_layers import ImageOverlay
from streamlit_folium import st_folium

from utils.climate.vegetation import (
    load_ndmi,
    load_ndvi,
    load_vegetation_spatial,
    load_vegetation_spatial_raster,
    raster_data_uri,
)
from utils.map import load_carbon_project_zone, load_project_area
from utils.ui import setup_page

setup_page()

st.markdown("""
<style>
.vm-hero{padding:4px 0 12px}.vm-muted{color:#64748b;font-size:.84rem}
.vm-kpi{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:13px 14px;min-height:108px;box-shadow:0 2px 9px rgba(15,23,42,.05)}.vm-kpi-label{font-size:.70rem;color:#64748b;font-weight:800;text-transform:uppercase;letter-spacing:.04em}.vm-kpi-value{font-size:1.45rem;font-weight:850;line-height:1.15;margin-top:7px;color:#0f172a}.vm-kpi-sub{font-size:.74rem;margin-top:7px;font-weight:700}
.vm-card{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:16px;box-shadow:0 3px 12px rgba(15,23,42,.05)}.vm-card-title{font-size:1rem;font-weight:850;color:#0f172a;margin-bottom:10px}
.vm-section{font-size:.68rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin:14px 0 7px}.vm-row{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid #eef2f7;font-size:.80rem}.vm-label{color:#64748b}.vm-value{color:#0f172a;font-weight:750;text-align:right}
.vm-badge{border-radius:11px;padding:10px 12px;margin-top:12px;font-weight:850;font-size:.82rem}.vm-high{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}.vm-medium{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}.vm-low{background:#ffedd5;color:#9a3412;border:1px solid #fed7aa}.vm-note{font-size:.75rem;color:#64748b;line-height:1.45}
.vm-dq{margin-top:8px}.vm-dq-item{margin:11px 0}.vm-dq-head{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:.78rem;font-weight:750;color:#334155}.vm-dq-value{font-size:.82rem;font-weight:850;color:#0f172a}.vm-dq-track{height:9px;background:#eef2f7;border-radius:99px;overflow:hidden;margin-top:5px}.vm-dq-fill{height:100%;border-radius:99px}.vm-dq-total{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:11px 12px;margin-top:13px;display:flex;justify-content:space-between;align-items:center}.vm-dq-total-label{font-size:.75rem;color:#64748b;font-weight:700}.vm-dq-total-value{font-size:1.05rem;font-weight:900;color:#0f172a}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="vm-hero">', unsafe_allow_html=True)
st.markdown("# 🌿 Vegetation Monitoring")
st.markdown('<div class="vm-muted">SERPRO Project · Sentinel-2 vegetation health, vigor, canopy moisture and spatial stress screening</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

ndmi = load_ndmi()
ndvi = load_ndvi()
spatial = load_vegetation_spatial()
raster = load_vegetation_spatial_raster()
for df in (ndmi, ndvi):
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

if ndmi.empty and ndvi.empty:
    st.info("No NDVI/NDMI data is currently available. Run the vegetation update workflow.")
    st.stop()

scope_keys = sorted(set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str)) | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str)))
if not scope_keys:
    st.error("Vegetation data has no valid monitoring scope.")
    st.stop()

scope_labels = {"carbon_project_zone":"🟣 Carbon Project Zone · reference", "project_area":"🟢 SERPRO Project Area · analysis"}
c_scope, c_period = st.columns([1.15, 1], gap="medium")
with c_scope:
    preferred = "project_area" if "project_area" in scope_keys else scope_keys[0]
    scope = st.selectbox("Monitoring scope", scope_keys, index=scope_keys.index(preferred), format_func=lambda x: scope_labels.get(x, x.replace("_", " ").title()))
ndvi_s = ndvi[ndvi.scope.astype(str) == scope].copy() if not ndvi.empty and "scope" in ndvi.columns else pd.DataFrame()
ndmi_s = ndmi[ndmi.scope.astype(str) == scope].copy() if not ndmi.empty and "scope" in ndmi.columns else pd.DataFrame()
all_dates = pd.concat([x["date"] for x in (ndvi_s, ndmi_s) if not x.empty], ignore_index=True).dropna()
with c_period:
    if not all_dates.empty:
        min_date, max_date = all_dates.min().date(), all_dates.max().date()
        date_range = st.date_input("Monitoring period", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    else:
        date_range = None
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start = pd.Timestamp(date_range[0]); end = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    ndvi_p = ndvi_s[(ndvi_s.date >= start) & (ndvi_s.date <= end)].copy()
    ndmi_p = ndmi_s[(ndmi_s.date >= start) & (ndmi_s.date <= end)].copy()
else:
    ndvi_p, ndmi_p = ndvi_s.copy(), ndmi_s.copy()
ndvi_p = ndvi_p.sort_values("date") if not ndvi_p.empty else ndvi_p
ndmi_p = ndmi_p.sort_values("date") if not ndmi_p.empty else ndmi_p


def pct_change(df, col, days=30):
    if df.empty or col not in df.columns or len(df) < 2:
        return None
    latest = df.date.max(); w = df[df.date >= latest - pd.Timedelta(days=days)]
    if len(w) < 2:
        return None
    a, b = float(w.iloc[0][col]), float(w.iloc[-1][col])
    return None if a == 0 else (b - a) / abs(a) * 100


def ndvi_status(v):
    if v is None or pd.isna(v): return "No data", "#64748b"
    if v >= .70: return "Good vigor", "#15803d"
    if v >= .50: return "Moderate vigor", "#b45309"
    if v >= .30: return "Low vigor", "#c2410c"
    return "Very low vigor", "#b91c1c"


def ndmi_status(v):
    if v is None or pd.isna(v): return "No data", "#64748b"
    if v >= .40: return "Moist", "#15803d"
    if v >= .20: return "Moderate", "#b45309"
    if v >= 0: return "Drying", "#c2410c"
    return "Low moisture", "#b91c1c"

latest_ndvi = float(ndvi_p.iloc[-1].ndvi) if not ndvi_p.empty and "ndvi" in ndvi_p.columns else None
latest_ndmi = float(ndmi_p.iloc[-1].ndmi) if not ndmi_p.empty and "ndmi" in ndmi_p.columns else None
ndvi30 = pct_change(ndvi_p, "ndvi"); ndmi30 = pct_change(ndmi_p, "ndmi")
ndvi_label, ndvi_color = ndvi_status(latest_ndvi); ndmi_label, ndmi_color = ndmi_status(latest_ndmi)
if ndvi30 is not None and ndmi30 is not None and ndvi30 <= -10 and ndmi30 <= -10: stress_level = "HIGH"
elif (ndvi30 is not None and ndvi30 <= -10) or (ndmi30 is not None and ndmi30 <= -10): stress_level = "MODERATE"
elif (ndvi30 is not None and ndvi30 < 0) or (ndmi30 is not None and ndmi30 < 0): stress_level = "LOW"
else: stress_level = "STABLE"
stress_color = {"HIGH":"#b91c1c", "MODERATE":"#b45309", "LOW":"#2563eb", "STABLE":"#15803d"}[stress_level]

st.markdown("### 🌱 Vegetation Condition Overview")
kpis = [("🌿", "NDVI", f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—", ndvi_label, ndvi_color),("💧", "NDMI", f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—", ndmi_label, ndmi_color),("📉", "NDVI · 30D", f"{ndvi30:+.1f}%" if ndvi30 is not None else "—", "vs. 30 days", "#b91c1c" if ndvi30 is not None and ndvi30 < 0 else "#15803d"),("💦", "NDMI · 30D", f"{ndmi30:+.1f}%" if ndmi30 is not None else "—", "vs. 30 days", "#b91c1c" if ndmi30 is not None and ndmi30 < 0 else "#15803d"),("⚠️", "VEGETATION STRESS", stress_level, "NDVI + NDMI screening", stress_color)]
cols = st.columns(5, gap="small")
for col, (icon, title, value, sub, color) in zip(cols, kpis):
    with col:
        st.markdown(f'<div class="vm-kpi"><div class="vm-kpi-label">{icon} {title}</div><div class="vm-kpi-value">{value}</div><div class="vm-kpi-sub" style="color:{color}">{sub}</div></div>', unsafe_allow_html=True)
if stress_level == "HIGH": st.error("🚨 High vegetation stress: both NDVI and NDMI declined by at least 10% over the last 30 days. Prioritize field verification.")
elif stress_level == "MODERATE": st.warning("⚠️ Moderate vegetation stress: at least one indicator declined by 10% or more over the last 30 days. Review spatial context.")
elif stress_level == "LOW": st.info("ℹ️ Low vegetation stress signal: a recent decline is present, but the moderate threshold has not been reached.")
else: st.success("✅ No vegetation stress signal detected under the current screening rules.")


def bounds_from_geojson(collection):
    pts = []
    for feature in collection.get("features", []):
        geom = feature.get("geometry") or {}; coords = geom.get("coordinates", [])
        if geom.get("type") == "Polygon": rings = coords
        elif geom.get("type") == "MultiPolygon": rings = [ring for polygon in coords for ring in polygon]
        else: rings = []
        for ring in rings:
            if isinstance(ring, list): pts.extend([p for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2])
    if not pts: return None
    lons = [float(p[0]) for p in pts]; lats = [float(p[1]) for p in pts]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def safe_spatial_features():
    clean = []
    for feature in spatial.get("features", []):
        if not isinstance(feature, dict) or not feature.get("geometry"): continue
        geom = feature.get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"): continue
        props = dict(feature.get("properties") or {})
        props.setdefault("ndvi", None); props.setdefault("ndmi", None); props.setdefault("stress", "STABLE")
        props.setdefault("analysis_year", None); props.setdefault("analysis_start", None); props.setdefault("analysis_end", None)
        props.setdefault("observed_pct", None); props.setdefault("temporal_fallback_pct", None); props.setdefault("spatial_interpolation_pct", None)
        clean.append({"type":"Feature", "geometry":geom, "properties":props})
    return {"type":"FeatureCollection", "features":clean}


def build_vegetation_map():
    project_area = load_project_area()
    zone = load_carbon_project_zone()
    m = folium.Map(location=[-3.10, 112.62], zoom_start=9, tiles=None, control_scale=True)
    folium.TileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", attr="© OpenStreetMap contributors", name="🗺️ OpenStreetMap", overlay=False, show=True).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Tiles © Esri", name="🛰️ ESRI Satellite Imagery", overlay=False, show=False).add_to(m)
    if project_area.get("features"):
        folium.GeoJson(project_area, name="🟢 SERPRO Project Area · AOI", style_function=lambda _: {"color":"#16a34a","weight":3,"fillOpacity":0}).add_to(m)
    if zone.get("features"):
        folium.GeoJson(zone, name="🟣 Carbon Project Zone · reference", style_function=lambda _: {"color":"#7c3aed","weight":2,"fillOpacity":0}).add_to(m)

    bounds = raster.get("bounds") or bounds_from_geojson(project_area)
    layers = raster.get("layers", {})
    if raster and bounds and layers:
        labels = [("ndvi", "🌿 NDVI · YTD vigor", True, 0.78), ("ndmi", "💧 NDMI · YTD moisture", False, 0.78), ("stress", "⚠️ Vegetation stress · YTD", False, 0.70)]
        for key, label, show, opacity in labels:
            packed = layers.get(key)
            if packed:
                ImageOverlay(
                    image=raster_data_uri(packed), bounds=bounds, opacity=opacity,
                    name=label, show=show, interactive=False, cross_origin=False,
                    zindex=2, pixelated=False,
                ).add_to(m)
    else:
        # Graceful fallback to the existing 250 m spatial overview if the raster package
        # has not yet been generated by GitHub Actions.
        data = safe_spatial_features()
        def add_layer(field, label, show):
            def style(feature):
                p = feature.get("properties", {}); value = p.get(field)
                if field == "stress": color = {"HIGH":"#dc2626","MODERATE":"#f59e0b","LOW":"#eab308","STABLE":"#16a34a"}.get(str(value),"#94a3b8")
                else:
                    try:
                        x = float(value)
                        if field == "ndvi": color = "#b91c1c" if x < .30 else "#f59e0b" if x < .50 else "#84cc16" if x < .70 else "#15803d"
                        else: color = "#b91c1c" if x < 0 else "#f59e0b" if x < .20 else "#84cc16" if x < .40 else "#15803d"
                    except (TypeError, ValueError): color = "#94a3b8"
                return {"fillColor":color,"color":color,"weight":0.25,"fillOpacity":0.68}
            folium.GeoJson(data, name=label, style_function=style, show=show).add_to(m)
        add_layer("ndvi", "🌿 NDVI · overview fallback", True)
        add_layer("ndmi", "💧 NDMI · overview fallback", False)
        add_layer("stress", "⚠️ Stress · overview fallback", False)

    # Robust click interaction for the rendered vegetation raster.
    # ImageOverlay is intentionally non-interactive; this transparent vector
    # pane sits above it and uses the same spatial overview cells for popups.
    info_data = safe_spatial_features()
    if info_data.get("features"):
        folium.map.CustomPane("vegetationClickPane", z_index=650).add_to(m)
        popup = folium.GeoJsonPopup(
            fields=[
                "ndvi", "ndmi", "stress", "analysis_year", "analysis_start", "analysis_end",
                "observed_pct", "temporal_fallback_pct", "spatial_interpolation_pct",
            ],
            aliases=[
                "🌿 NDVI", "💧 NDMI", "⚠️ Vegetation Stress", "Analysis Year", "Analysis Start", "Analysis End",
                "Directly Observed (%)", "Temporal Fallback (%)", "Spatial Interpolation (%)",
            ],
            localize=True,
            labels=True,
            sticky=False,
            max_width=400,
        )
        click_layer = folium.GeoJson(
            info_data,
            name="__vegetation_click_info__",
            control=False,
            show=True,
            pane="vegetationClickPane",
            style_function=lambda _: {
                "fillColor": "#ffffff",
                "fillOpacity": 0.01,
                "color": "#ffffff",
                "weight": 0,
                "opacity": 0,
            },
            highlight_function=lambda _: {
                "fillColor": "#ffffff",
                "fillOpacity": 0.10,
                "color": "#ffffff",
                "weight": 1,
                "opacity": 0.35,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["ndvi", "ndmi", "stress"],
                aliases=["🌿 NDVI", "💧 NDMI", "⚠️ Stress"],
                localize=True,
                sticky=False,
                labels=True,
            ),
            popup=popup,
        )
        click_layer.add_to(m)

        # Persistent map symbology legend. The values match the raster styling.
        legend_html = """
        <div style="position:fixed; z-index:9998; bottom:18px; left:18px; background:rgba(255,255,255,.97); border:1px solid #cbd5e1; border-radius:10px; padding:11px 13px; box-shadow:0 2px 9px rgba(15,23,42,.18); font-family:Arial,sans-serif; font-size:11px; line-height:1.55; min-width:250px; max-width:310px;">
          <div style="font-weight:800; font-size:12px; margin-bottom:7px;">🎨 Vegetation Map Symbology</div>
          <div style="font-weight:800; margin-top:3px;">🌿 NDVI · YTD vigor</div>
          <div><span style="color:#b91c1c">■</span> &lt; 0.30 Very low &nbsp; <span style="color:#f59e0b">■</span> 0.30–0.49 Low</div>
          <div><span style="color:#84cc16">■</span> 0.50–0.69 Moderate &nbsp; <span style="color:#15803d">■</span> ≥ 0.70 Good</div>
          <div style="font-weight:800; margin-top:7px;">💧 NDMI · YTD moisture</div>
          <div><span style="color:#b91c1c">■</span> &lt; 0 Low moisture &nbsp; <span style="color:#f59e0b">■</span> 0–0.19 Drying</div>
          <div><span style="color:#84cc16">■</span> 0.20–0.39 Moderate &nbsp; <span style="color:#15803d">■</span> ≥ 0.40 Moist</div>
          <div style="font-weight:800; margin-top:7px;">⚠️ Vegetation Stress</div>
          <div><span style="color:#16a34a">■</span> Stable &nbsp; <span style="color:#2563eb">■</span> Low &nbsp; <span style="color:#f59e0b">■</span> Moderate &nbsp; <span style="color:#b91c1c">■</span> High</div>
          <div style="margin-top:7px; color:#64748b; font-size:10px;">Klik area Project Area untuk membuka detail NDVI, NDMI, stress dan kualitas observasi.</div>
        </div>
        """
        folium.Element(legend_html).add_to(m)

    if bounds: m.fit_bounds(bounds, padding=(10, 10))
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def quality_panel(props):
    observed = max(0.0, min(100.0, float(props.get("observed_pct") or 0)))
    temporal = max(0.0, min(100.0, float(props.get("temporal_fallback_pct") or 0)))
    spatial_fill = max(0.0, min(100.0, float(props.get("spatial_interpolation_pct") or 0)))
    total = float(props.get("total_coverage_pct") or min(100.0, observed + temporal + spatial_fill))
    items = [("Directly observed", observed, "#16a34a"),("Temporal fallback", temporal, "#f59e0b"),("Spatial interpolation", spatial_fill, "#f97316")]
    html = '<div class="vm-dq">'
    for label, value, color in items:
        html += f'<div class="vm-dq-item"><div class="vm-dq-head"><span>{label}</span><span class="vm-dq-value">{value:.1f}%</span></div><div class="vm-dq-track"><div class="vm-dq-fill" style="width:{value:.2f}%;background:{color}"></div></div></div>'
    html += f'<div class="vm-dq-total"><span class="vm-dq-total-label">Total coverage</span><span class="vm-dq-total-value">{total:.1f}%</span></div></div>'
    st.markdown(html, unsafe_allow_html=True)


st.markdown("### 🗺️ Spatial Vegetation Condition")
if spatial.get("features") or raster:
    props = spatial["features"][0].get("properties", {}) if spatial.get("features") else raster
    map_col, info_col = st.columns([2.15, 1], gap="medium")
    with map_col:
        try:
            fmap = build_vegetation_map()
            st_folium(fmap, width=700, height=540, returned_objects=[], key="vegetation_spatial_map", use_container_width=True)
        except Exception as exc:
            st.error("Spatial map could not be rendered. The vegetation analysis remains available below.")
            st.caption(f"Map rendering is isolated from the dashboard calculations. {exc}")
    with info_col:
        st.markdown('<div class="vm-card"><div class="vm-card-title">📊 Spatial Analysis Overview</div>', unsafe_allow_html=True)
        year = int(props.get("analysis_year") or date.today().year)
        start_text = props.get("analysis_start") or f"{year}-01-01"; end_text = props.get("analysis_end") or "—"
        scenes = int(props.get("scene_count") or 0); cloud = float(props.get("mean_cloud_cover_pct") or 0)
        rows = [("Analysis period",f"{start_text} → {end_text}"),("Composite",f"{year} year-to-date median"),("Spatial resolution","10 × 10 m analysis"),("Web display","100 m raster"),("Spatial overview","250 m GeoJSON"),("Analysis boundary","SERPRO Project Area · AOI"),("Reference boundary","Carbon Project Zone"),("Sentinel-2 scenes",f"{scenes:,}"),("Mean cloud cover",f"{cloud:.1f}%"),("Method","Annual YTD + spatial gap fill")]
        for label, value in rows:
            st.markdown(f'<div class="vm-row"><span class="vm-label">{label}</span><span class="vm-value">{value}</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="vm-section">Data Quality</div>', unsafe_allow_html=True)
        quality_panel(props)
        observed = float(props.get("observed_pct") or 0)
        badge = ("🟢 HIGH CONFIDENCE","vm-high") if observed >= 85 else ("🟡 MODERATE CONFIDENCE","vm-medium") if observed >= 60 else ("🟠 LOW CONFIDENCE","vm-low")
        st.markdown(f'<div class="vm-badge {badge[1]}">{badge[0]}</div>', unsafe_allow_html=True)
        st.markdown('<div class="vm-note">Confidence represents the share of Project Area directly observed by Sentinel-2. Temporal fallback and spatial interpolation are shown separately and are not treated as direct observations.</div></div>', unsafe_allow_html=True)
else:
    st.warning("Spatial vegetation layer is not available yet. Run the Update SERPRO Spatial Vegetation workflow.")

st.markdown("### 📈 Recent Vegetation Trend")
trend_col, interpretation_col = st.columns([1.6, 1], gap="medium")
with trend_col:
    fig = go.Figure()
    if not ndvi_p.empty: fig.add_scatter(x=ndvi_p.tail(30).date, y=ndvi_p.tail(30).ndvi, mode="lines+markers", name="NDVI · vigor")
    if not ndmi_p.empty: fig.add_scatter(x=ndmi_p.tail(30).date, y=ndmi_p.tail(30).ndmi, mode="lines+markers", name="NDMI · moisture")
    fig.update_layout(height=330, margin=dict(l=10,r=10,t=10,b=10), yaxis_title="Index", legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
with interpretation_col:
    st.markdown("### 🧭 Current Interpretation")
    st.metric("Vegetation vigor", ndvi_label, f"NDVI {latest_ndvi:.3f}" if latest_ndvi is not None else None)
    st.metric("Canopy moisture", ndmi_label, f"NDMI {latest_ndmi:.3f}" if latest_ndmi is not None else None)
    st.metric("Combined stress", stress_level)
    st.caption("Combined stress is a conservative screening indicator and is not standalone evidence of degradation or carbon loss.")

st.markdown("### 🚨 Stress Condition")
sa1, sa2, sa3 = st.columns(3)
with sa1: st.metric("NDVI 30D", f"{ndvi30:+.1f}%" if ndvi30 is not None else "—")
with sa2: st.metric("NDMI 30D", f"{ndmi30:+.1f}%" if ndmi30 is not None else "—")
with sa3: st.metric("Screening status", stress_level)

st.markdown("### 🗃️ Observation Data")
obs1, obs2 = st.tabs(["NDVI observations", "NDMI observations"])
with obs1: st.dataframe(ndvi_p.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
with obs2: st.dataframe(ndmi_p.sort_values("date", ascending=False), use_container_width=True, hide_index=True)

if spatial.get("features"):
    st.markdown("### ℹ️ Data & Quality Notes")
    p = spatial["features"][0].get("properties", {})
    st.info(f"Sentinel-2 SR Harmonized · native analysis scale 10 m · analytical boundary: SERPRO Project Area · year-to-date spatial composite: {int(p.get('analysis_year') or date.today().year)} · effective period {p.get('analysis_start','—')} to {p.get('analysis_end','—')} · mean scene cloud cover {float(p.get('mean_cloud_cover_pct') or 0):.1f}%. The map uses a 100 m raster web layer derived from the native 10 m analytical surface; the Spatial Analysis Overview remains available as a 250 m GeoJSON summary.")