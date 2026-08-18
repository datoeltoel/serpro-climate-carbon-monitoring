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

# Dashboard-only palette. Web-map symbology is intentionally kept separate.
TEAL = "#156064"
GREEN = "#00C49A"
YELLOW = "#F8E16C"
PEACH = "#FFC2B4"
ORANGE = "#FB8F67"
INK = "#173F42"
MUTED = "#5F777A"
SURFACE = "#FFFFFF"
SOFT = "#F7FAF9"
BORDER = "#DCE9E6"

# Existing analytical map colors: do not use dashboard palette for map data.
MAP_RED = "#D73027"
MAP_YELLOW = "#FEE08B"
MAP_LIGHT_GREEN = "#91CF60"
MAP_DARK_GREEN = "#1A9850"
MAP_STRESS_LOW = "#FEE08B"
MAP_STRESS_MODERATE = "#F46D43"
MAP_STRESS_HIGH = "#D73027"

st.markdown(
    f"""
<style>
:root {{
  --vm-teal:{TEAL}; --vm-green:{GREEN}; --vm-yellow:{YELLOW};
  --vm-peach:{PEACH}; --vm-orange:{ORANGE}; --vm-ink:{INK};
  --vm-muted:{MUTED}; --vm-surface:{SURFACE}; --vm-soft:{SOFT};
  --vm-border:{BORDER};
}}
[data-testid="stAppViewContainer"] {{
  background:linear-gradient(180deg,#fbfdfc 0%,#f6faf8 100%);
}}
.block-container {{ max-width:1500px; padding-top:1.2rem; padding-bottom:2.5rem; }}
.vm-hero {{
  background:linear-gradient(135deg,#ffffff 0%,#f2faf7 100%);
  border:1px solid var(--vm-border); border-radius:20px;
  padding:20px 24px 18px; margin-bottom:14px;
  box-shadow:0 5px 20px rgba(21,96,100,.06);
}}
.vm-eyebrow {{ color:var(--vm-teal); font-size:.68rem; font-weight:900; letter-spacing:.13em; text-transform:uppercase; }}
.vm-title {{ color:var(--vm-ink); font-size:2rem; font-weight:900; line-height:1.05; margin-top:4px; }}
.vm-subtitle {{ color:var(--vm-muted); font-size:.86rem; margin-top:7px; line-height:1.45; }}
.vm-meta {{ display:inline-block; background:#e8f7f3; color:var(--vm-teal); border:1px solid #c7e9e2; border-radius:999px; padding:6px 10px; margin-top:10px; font-size:.70rem; font-weight:900; }}
.vm-filter {{ background:#fff; border:1px solid var(--vm-border); border-radius:15px; padding:10px 14px 4px; margin-bottom:15px; }}
.vm-section-title {{ color:var(--vm-ink); font-size:1.08rem; font-weight:900; margin:14px 0 9px; }}
.vm-section-caption {{ color:var(--vm-muted); font-size:.75rem; margin:-5px 0 9px; }}
.vm-kpi {{
  background:#fff; border:1px solid var(--vm-border); border-radius:16px;
  padding:14px 15px; min-height:118px; position:relative; overflow:hidden;
  box-shadow:0 3px 14px rgba(21,96,100,.055);
}}
.vm-kpi::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--kpi-color); }}
.vm-kpi-label {{ color:var(--vm-muted); font-size:.67rem; font-weight:900; letter-spacing:.055em; text-transform:uppercase; }}
.vm-kpi-value {{ color:var(--vm-ink); font-size:1.62rem; font-weight:950; line-height:1.08; margin-top:8px; }}
.vm-kpi-sub {{ font-size:.73rem; margin-top:8px; font-weight:850; }}
.vm-card {{ background:#fff; border:1px solid var(--vm-border); border-radius:17px; padding:16px; box-shadow:0 3px 14px rgba(21,96,100,.045); }}
.vm-card-title {{ color:var(--vm-ink); font-size:1rem; font-weight:900; margin-bottom:4px; }}
.vm-card-caption {{ color:var(--vm-muted); font-size:.72rem; line-height:1.4; margin-bottom:10px; }}
.vm-row {{ display:flex; justify-content:space-between; gap:12px; padding:7px 0; border-bottom:1px solid #edf3f1; font-size:.76rem; }}
.vm-label {{ color:var(--vm-muted); }}
.vm-value {{ color:var(--vm-ink); font-weight:850; text-align:right; }}
.vm-badge {{ border-radius:10px; padding:9px 11px; margin-top:11px; font-weight:900; font-size:.76rem; }}
.vm-high {{ background:#FFF0EA; color:#A94A2D; border:1px solid #F9C7B5; }}
.vm-medium {{ background:#FFF9D9; color:#75620A; border:1px solid #F2DF73; }}
.vm-low {{ background:#E8F7F3; color:#126A68; border:1px solid #B9E7DE; }}
.vm-note {{ color:var(--vm-muted); font-size:.72rem; line-height:1.5; }}
.vm-dq-item {{ margin:9px 0; }}
.vm-dq-head {{ display:flex; justify-content:space-between; gap:8px; color:var(--vm-ink); font-size:.74rem; font-weight:850; }}
.vm-dq-track {{ height:7px; background:#edf3f1; border-radius:99px; overflow:hidden; margin-top:5px; }}
.vm-dq-fill {{ height:100%; border-radius:99px; }}
.vm-dq-total {{ background:var(--vm-soft); border:1px solid var(--vm-border); border-radius:10px; padding:9px 11px; margin-top:10px; display:flex; justify-content:space-between; align-items:center; }}
.vm-dq-total-label {{ color:var(--vm-muted); font-size:.72rem; font-weight:700; }}
.vm-dq-total-value {{ color:var(--vm-ink); font-size:1rem; font-weight:950; }}
.vm-status {{ border-radius:12px; padding:10px 12px; margin:7px 0 12px; border:1px solid var(--vm-border); background:var(--vm-soft); color:var(--vm-ink); font-size:.76rem; font-weight:850; line-height:1.4; }}
.vm-mini {{ background:#f9fcfb; border:1px solid #e4efec; border-radius:12px; padding:10px 11px; }}
.vm-mini-label {{ color:var(--vm-muted); font-size:.66rem; font-weight:850; text-transform:uppercase; }}
.vm-mini-value {{ color:var(--vm-ink); font-size:1.05rem; font-weight:950; margin-top:3px; }}
.vm-footer {{ background:linear-gradient(90deg,#f1faf7,#fff7f1); border:1px solid var(--vm-border); border-radius:14px; padding:12px 14px; color:var(--vm-muted); font-size:.72rem; line-height:1.5; }}


/* Vegetation dashboard readability guard: UI only. */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stVerticalBlock"],
[data-testid="stMarkdownContainer"] {{
  color: var(--vm-ink) !important;
}}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] label,
[data-testid="stMarkdownContainer"] div {{
  color: inherit;
}}
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span {{
  color: var(--vm-ink) !important;
  font-weight: 700 !important;
}}
[data-baseweb="select"] *,
[data-baseweb="input"] * {{
  color: var(--vm-ink) !important;
}}
[data-testid="stExpander"] {{
  background: #ffffff !important;
  border: 1px solid var(--vm-border) !important;
  border-radius: 14px !important;
}}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span {{
  color: var(--vm-ink) !important;
  font-weight: 850 !important;
}}
[data-testid="stDataFrame"] {{
  border: 1px solid var(--vm-border) !important;
  border-radius: 12px !important;
  overflow: hidden !important;
  background: #ffffff !important;
}}
[data-testid="stDataFrame"] iframe {{
  background: #ffffff !important;
}}
.stPlotlyChart {{
  border: 1px solid var(--vm-border);
  border-radius: 14px;
  overflow: hidden;
  background: #ffffff;
}}

</style>
""",
    unsafe_allow_html=True,
)

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

scope_keys = sorted(
    set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str))
    | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str))
)
if not scope_keys:
    st.error("Vegetation data has no valid monitoring scope.")
    st.stop()

scope_labels = {
    "carbon_project_zone": "🟣 Carbon Project Zone · reference",
    "project_area": "🟢 SERPRO Project Area · analysis",
}

st.markdown(
    f"""
<div class="vm-hero">
  <div class="vm-eyebrow">SERPRO PROJECT · REMOTE SENSING MRV</div>
  <div class="vm-title">🌿 Vegetation Monitoring</div>
  <div class="vm-subtitle">Monitor vegetation vigor, canopy moisture and spatial stress across the SERPRO Project Area using Sentinel-2.</div>
  <span class="vm-meta">10 m analysis · 100 m web display · 250 m spatial overview · dashboard v2</span>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="vm-filter">', unsafe_allow_html=True)
c_scope, c_period = st.columns([1.1, 1], gap="medium")
with c_scope:
    preferred = "project_area" if "project_area" in scope_keys else scope_keys[0]
    scope = st.selectbox(
        "Monitoring area",
        scope_keys,
        index=scope_keys.index(preferred),
        format_func=lambda x: scope_labels.get(x, x.replace("_", " ").title()),
    )
ndvi_s = ndvi[ndvi.scope.astype(str) == scope].copy() if not ndvi.empty and "scope" in ndvi.columns else pd.DataFrame()
ndmi_s = ndmi[ndmi.scope.astype(str) == scope].copy() if not ndmi.empty and "scope" in ndmi.columns else pd.DataFrame()
all_dates = pd.concat([x["date"] for x in (ndvi_s, ndmi_s) if not x.empty], ignore_index=True).dropna()
with c_period:
    if not all_dates.empty:
        min_date, max_date = all_dates.min().date(), all_dates.max().date()
        date_range = st.date_input("Monitoring period", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    else:
        date_range = None
st.markdown('</div>', unsafe_allow_html=True)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start = pd.Timestamp(date_range[0])
    end = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    ndvi_p = ndvi_s[(ndvi_s.date >= start) & (ndvi_s.date <= end)].copy()
    ndmi_p = ndmi_s[(ndmi_s.date >= start) & (ndmi_s.date <= end)].copy()
else:
    ndvi_p, ndmi_p = ndvi_s.copy(), ndmi_s.copy()
ndvi_p = ndvi_p.sort_values("date") if not ndvi_p.empty else ndvi_p
ndmi_p = ndmi_p.sort_values("date") if not ndmi_p.empty else ndmi_p


def pct_change(df, col, days=30):
    if df.empty or col not in df.columns or len(df) < 2:
        return None
    latest = df.date.max()
    window = df[df.date >= latest - pd.Timedelta(days=days)]
    if len(window) < 2:
        return None
    a, b = float(window.iloc[0][col]), float(window.iloc[-1][col])
    return None if a == 0 else (b - a) / abs(a) * 100


def ndvi_status(v):
    if v is None or pd.isna(v): return "No data", MUTED
    if v >= 0.70: return "Good vigor", GREEN
    if v >= 0.50: return "Moderate vigor", YELLOW
    if v >= 0.30: return "Low vigor", PEACH
    return "Very low vigor", ORANGE


def ndmi_status(v):
    if v is None or pd.isna(v): return "No data", MUTED
    if v >= 0.40: return "Moist", GREEN
    if v >= 0.20: return "Moderate", YELLOW
    if v >= 0: return "Drying", PEACH
    return "Low moisture", ORANGE

latest_ndvi = float(ndvi_p.iloc[-1].ndvi) if not ndvi_p.empty and "ndvi" in ndvi_p.columns else None
latest_ndmi = float(ndmi_p.iloc[-1].ndmi) if not ndmi_p.empty and "ndmi" in ndmi_p.columns else None
ndvi30 = pct_change(ndvi_p, "ndvi")
ndmi30 = pct_change(ndmi_p, "ndmi")
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

stress_color = {"HIGH": ORANGE, "MODERATE": PEACH, "LOW": YELLOW, "STABLE": GREEN}[stress_level]

st.markdown('<div class="vm-section-title">🌱 Current vegetation condition</div>', unsafe_allow_html=True)
st.markdown('<div class="vm-section-caption">The cards below summarize the latest selected monitoring period. Values are index values, not percentages.</div>', unsafe_allow_html=True)

kpis = [
    ("🌿", "NDVI · vegetation vigor", f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—", ndvi_label, ndvi_color),
    ("💧", "NDMI · canopy moisture", f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—", ndmi_label, ndmi_color),
    ("📉", "NDVI change · 30 days", f"{ndvi30:+.1f}%" if ndvi30 is not None else "—", "Compared with 30 days ago", ORANGE if ndvi30 is not None and ndvi30 < 0 else GREEN),
    ("⚠️", "Vegetation stress", stress_level, "NDVI + NDMI screening", stress_color),
]
cols = st.columns(4, gap="small")
for col, (icon, title, value, sub, color) in zip(cols, kpis):
    with col:
        st.markdown(
            f'<div class="vm-kpi" style="--kpi-color:{color}"><div class="vm-kpi-label">{icon} {title}</div><div class="vm-kpi-value">{value}</div><div class="vm-kpi-sub" style="color:{color}">{sub}</div></div>',
            unsafe_allow_html=True,
        )

status_text = {
    "HIGH": "🚨 High stress signal: both NDVI and NDMI declined by at least 10% over the last 30 days. Prioritize field verification.",
    "MODERATE": "⚠️ Moderate stress signal: at least one indicator declined by at least 10%. Review the spatial pattern before field verification.",
    "LOW": "ℹ️ Low stress signal: a recent decline is present, but the moderate threshold has not been reached.",
    "STABLE": "✅ Stable screening result: no negative NDVI/NDMI trend signal was detected under the current screening rules.",
}[stress_level]
st.markdown(f'<div class="vm-status">{status_text}</div>', unsafe_allow_html=True)


def bounds_from_geojson(collection):
    pts = []
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
            if isinstance(ring, list):
                pts.extend([p for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2])
    if not pts: return None
    lons = [float(p[0]) for p in pts]
    lats = [float(p[1]) for p in pts]
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
        clean.append({"type": "Feature", "geometry": geom, "properties": props})
    return {"type": "FeatureCollection", "features": clean}


def map_index_color(field, value):
    try: x = float(value)
    except (TypeError, ValueError): return MAP_RED
    if field == "ndvi":
        if x < 0.30: return MAP_RED
        if x < 0.50: return MAP_YELLOW
        if x < 0.70: return MAP_LIGHT_GREEN
        return MAP_DARK_GREEN
    if x < 0: return MAP_RED
    if x < 0.20: return MAP_YELLOW
    if x < 0.40: return MAP_LIGHT_GREEN
    return MAP_DARK_GREEN


def build_vegetation_map():
    project_area = load_project_area()
    zone = load_carbon_project_zone()
    m = folium.Map(location=[-3.10, 112.62], zoom_start=9, tiles=None, control_scale=True)
    folium.TileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", attr="© OpenStreetMap contributors", name="🗺️ Base Map", overlay=False, show=True).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Tiles © Esri", name="🛰️ Satellite", overlay=False, show=False).add_to(m)

    if project_area.get("features"):
        folium.GeoJson(project_area, name="🟢 SERPRO Project Area · AOI", style_function=lambda _: {"color": GREEN, "weight": 3, "fillOpacity": 0}).add_to(m)
    if zone.get("features"):
        folium.GeoJson(zone, name="🟣 Carbon Project Zone · reference", style_function=lambda _: {"color": TEAL, "weight": 2, "fillOpacity": 0}).add_to(m)

    bounds = raster.get("bounds") or bounds_from_geojson(project_area)
    layers = raster.get("layers", {})
    if raster and bounds and layers:
        labels = [("ndvi", "🌿 NDVI · YTD vigor", True, 0.80), ("ndmi", "💧 NDMI · YTD moisture", False, 0.80), ("stress", "⚠️ Vegetation stress · YTD", False, 0.72)]
        for key, label, show, opacity in labels:
            packed = layers.get(key)
            if packed:
                ImageOverlay(image=raster_data_uri(packed), bounds=bounds, opacity=opacity, name=label, show=show, interactive=False, cross_origin=False, zindex=2, pixelated=False).add_to(m)
    else:
        data = safe_spatial_features()
        def add_layer(field, label, show):
            def style(feature):
                p = feature.get("properties", {}); value = p.get(field)
                if field == "stress":
                    color = {"HIGH": MAP_STRESS_HIGH, "MODERATE": MAP_STRESS_MODERATE, "LOW": MAP_STRESS_LOW, "STABLE": MAP_DARK_GREEN}.get(str(value), MAP_RED)
                else:
                    color = map_index_color(field, value)
                return {"fillColor": color, "color": color, "weight": 0.25, "fillOpacity": 0.72}
            folium.GeoJson(data, name=label, style_function=style, show=show).add_to(m)
        add_layer("ndvi", "🌿 NDVI · overview fallback", True)
        add_layer("ndmi", "💧 NDMI · overview fallback", False)
        add_layer("stress", "⚠️ Stress · overview fallback", False)

    info_data = safe_spatial_features()
    if info_data.get("features"):
        folium.map.CustomPane("vegetationClickPane", z_index=650).add_to(m)
        popup = folium.GeoJsonPopup(
            fields=["ndvi", "ndmi", "stress", "analysis_year", "analysis_start", "analysis_end", "observed_pct", "temporal_fallback_pct", "spatial_interpolation_pct"],
            aliases=["🌿 NDVI", "💧 NDMI", "⚠️ Vegetation Stress", "Analysis Year", "Analysis Start", "Analysis End", "Directly Observed (%)", "Temporal Fallback (%)", "Spatial Interpolation (%)"],
            localize=True, labels=True, sticky=False, max_width=400,
        )
        # Click-only interaction: no duplicate tooltip under the popup.
        click_layer = folium.GeoJson(
            info_data, name="__vegetation_click_info__", control=False, show=True, pane="vegetationClickPane",
            style_function=lambda _: {"fillColor": "#ffffff", "fillOpacity": 0.01, "color": "#ffffff", "weight": 0, "opacity": 0},
            highlight_function=lambda _: {"fillColor": GREEN, "fillOpacity": 0.08, "color": GREEN, "weight": 1, "opacity": 0.35},
            popup=popup,
        )
        click_layer.add_to(m)

        # Map legend keeps the established analytical symbology; dashboard palette is not used here.
        legend_html = f"""
        <div style="position:fixed; z-index:9998; bottom:18px; left:18px; background:rgba(255,255,255,.97); border:1px solid #d9e1df; border-radius:12px; padding:11px 13px; box-shadow:0 3px 12px rgba(0,0,0,.12); font-family:Arial,sans-serif; font-size:11px; line-height:1.55; min-width:260px; max-width:325px; color:#263b38;">
          <div style="font-weight:900; font-size:12px; margin-bottom:7px;">🎨 Vegetation Symbology</div>
          <div style="font-weight:900; margin-top:3px;">🌿 NDVI · YTD vigor</div>
          <div><span style="color:{MAP_RED}">■</span> &lt;0.30 &nbsp; <span style="color:{MAP_YELLOW}">■</span> 0.30–0.49 &nbsp; <span style="color:{MAP_LIGHT_GREEN}">■</span> 0.50–0.69 &nbsp; <span style="color:{MAP_DARK_GREEN}">■</span> ≥0.70</div>
          <div style="font-weight:900; margin-top:7px;">💧 NDMI · YTD moisture</div>
          <div><span style="color:{MAP_RED}">■</span> &lt;0 &nbsp; <span style="color:{MAP_YELLOW}">■</span> 0–0.19 &nbsp; <span style="color:{MAP_LIGHT_GREEN}">■</span> 0.20–0.39 &nbsp; <span style="color:{MAP_DARK_GREEN}">■</span> ≥0.40</div>
          <div style="font-weight:900; margin-top:7px;">⚠️ Vegetation Stress</div>
          <div><span style="color:{MAP_DARK_GREEN}">■</span> Stable &nbsp; <span style="color:{MAP_STRESS_LOW}">■</span> Low &nbsp; <span style="color:{MAP_STRESS_MODERATE}">■</span> Moderate &nbsp; <span style="color:{MAP_STRESS_HIGH}">■</span> High</div>
          <div style="margin-top:7px; color:#647875; font-size:10px;">Klik area Project Area untuk melihat nilai indikator dan kualitas observasi.</div>
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
    items = [("Directly observed", observed, GREEN), ("Temporal fallback", temporal, YELLOW), ("Spatial interpolation", spatial_fill, ORANGE)]
    html = '<div style="margin-top:4px">'
    for label, value, color in items:
        html += f'<div class="vm-dq-item"><div class="vm-dq-head"><span>{label}</span><span>{value:.1f}%</span></div><div class="vm-dq-track"><div class="vm-dq-fill" style="width:{value:.2f}%;background:{color}"></div></div></div>'
    html += f'<div class="vm-dq-total"><span class="vm-dq-total-label">Total coverage</span><span class="vm-dq-total-value">{total:.1f}%</span></div></div>'
    st.markdown(html, unsafe_allow_html=True)


st.markdown('<div class="vm-section-title">🗺️ Spatial vegetation condition</div>', unsafe_allow_html=True)
st.markdown('<div class="vm-section-caption">Click the map to inspect the vegetation indicators. The analytical surface remains 10 m; the browser renders the 100 m raster.</div>', unsafe_allow_html=True)
if spatial.get("features") or raster:
    props = spatial["features"][0].get("properties", {}) if spatial.get("features") else raster
    map_col, info_col = st.columns([2.1, 1], gap="medium")
    with map_col:
        try:
            fmap = build_vegetation_map()
            st_folium(fmap, width=700, height=550, returned_objects=[], key="vegetation_spatial_map", use_container_width=True)
        except Exception as exc:
            st.error("Spatial map could not be rendered. The vegetation indicators remain available below.")
            st.caption(f"Map rendering is isolated from dashboard calculations. {exc}")
    with info_col:
        st.markdown('<div class="vm-card"><div class="vm-card-title">📊 Spatial analysis overview</div><div class="vm-card-caption">How the vegetation map was produced</div>', unsafe_allow_html=True)
        year = int(props.get("analysis_year") or date.today().year)
        start_text = props.get("analysis_start") or f"{year}-01-01"
        end_text = props.get("analysis_end") or "—"
        scenes = int(props.get("scene_count") or 0)
        cloud = float(props.get("mean_cloud_cover_pct") or 0)
        rows = [("Analysis period", f"{start_text} → {end_text}"), ("Composite", f"{year} year-to-date median"), ("Analysis resolution", "10 × 10 m"), ("Web map resolution", "100 m raster"), ("Spatial overview", "250 m GeoJSON"), ("Analysis boundary", "SERPRO Project Area · AOI"), ("Reference boundary", "Carbon Project Zone"), ("Sentinel-2 scenes", f"{scenes:,}"), ("Mean cloud cover", f"{cloud:.1f}%"), ("Method", "Annual YTD + spatial gap fill")]
        for label, value in rows:
            st.markdown(f'<div class="vm-row"><span class="vm-label">{label}</span><span class="vm-value">{value}</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="vm-section-title" style="font-size:.84rem;margin-top:13px">Data quality</div>', unsafe_allow_html=True)
        quality_panel(props)
        observed = float(props.get("observed_pct") or 0)
        if observed >= 85: badge = ("🟢 HIGH CONFIDENCE", "vm-high")
        elif observed >= 60: badge = ("🟡 MODERATE CONFIDENCE", "vm-medium")
        else: badge = ("🟠 LOW CONFIDENCE", "vm-low")
        st.markdown(f'<div class="vm-badge {badge[1]}">{badge[0]}</div>', unsafe_allow_html=True)
        st.markdown('<div class="vm-note">Confidence is the share of the Project Area directly observed by Sentinel-2. Temporal fallback and spatial interpolation are reported separately.</div></div>', unsafe_allow_html=True)
else:
    st.warning("Spatial vegetation layer is not available yet. Run the Update SERPRO Spatial Vegetation workflow.")

st.markdown('<div class="vm-section-title">📈 Recent vegetation trend</div>', unsafe_allow_html=True)
st.markdown('<div class="vm-section-caption">Latest 30 observations for vigor and canopy moisture. Hover over the chart for exact values.</div>', unsafe_allow_html=True)
trend_col, interpretation_col = st.columns([1.65, 1], gap="medium")
with trend_col:
    fig = go.Figure()
    if not ndvi_p.empty:
        fig.add_scatter(x=ndvi_p.tail(30).date, y=ndvi_p.tail(30).ndvi, mode="lines+markers", name="NDVI · vigor", line=dict(color=GREEN, width=2.5), marker=dict(color=TEAL, size=5))
    if not ndmi_p.empty:
        fig.add_scatter(x=ndmi_p.tail(30).date, y=ndmi_p.tail(30).ndmi, mode="lines+markers", name="NDMI · moisture", line=dict(color=ORANGE, width=2.5), marker=dict(color=PEACH, size=5))
    fig.update_layout(height=315, margin=dict(l=10,r=10,t=12,b=10), yaxis_title="Index value", paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, font=dict(color=INK), legend=dict(orientation="h", y=1.08, x=0), hovermode="x unified", xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#E8F0EE"))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with interpretation_col:
    st.markdown('<div class="vm-card"><div class="vm-card-title">🧭 Current interpretation</div><div class="vm-card-caption">A quick reading of the latest indicators</div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        st.markdown(f'<div class="vm-mini"><div class="vm-mini-label">Vegetation vigor</div><div class="vm-mini-value">{ndvi_label}</div><div class="vm-note">NDVI {latest_ndvi:.3f}</div></div>', unsafe_allow_html=True) if latest_ndvi is not None else st.markdown('<div class="vm-mini"><div class="vm-mini-label">Vegetation vigor</div><div class="vm-mini-value">No data</div></div>', unsafe_allow_html=True)
    with b:
        st.markdown(f'<div class="vm-mini"><div class="vm-mini-label">Canopy moisture</div><div class="vm-mini-value">{ndmi_label}</div><div class="vm-note">NDMI {latest_ndmi:.3f}</div></div>', unsafe_allow_html=True) if latest_ndmi is not None else st.markdown('<div class="vm-mini"><div class="vm-mini-label">Canopy moisture</div><div class="vm-mini-value">No data</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="vm-status" style="margin-top:10px">Stress screening: <strong>{stress_level}</strong><br><span class="vm-note">This is a screening indicator and is not standalone evidence of degradation or carbon loss.</span></div></div>', unsafe_allow_html=True)

st.markdown('<div class="vm-section-title">📋 Monitoring details</div>', unsafe_allow_html=True)
d1, d2, d3 = st.columns(3, gap="small")
with d1:
    st.markdown(f'<div class="vm-mini"><div class="vm-mini-label">NDVI change · 30 days</div><div class="vm-mini-value">{ndvi30:+.1f}%</div></div>' if ndvi30 is not None else '<div class="vm-mini"><div class="vm-mini-label">NDVI change · 30 days</div><div class="vm-mini-value">—</div></div>', unsafe_allow_html=True)
with d2:
    st.markdown(f'<div class="vm-mini"><div class="vm-mini-label">NDMI change · 30 days</div><div class="vm-mini-value">{ndmi30:+.1f}%</div></div>' if ndmi30 is not None else '<div class="vm-mini"><div class="vm-mini-label">NDMI change · 30 days</div><div class="vm-mini-value">—</div></div>', unsafe_allow_html=True)
with d3:
    latest_date = all_dates.max().date().isoformat() if not all_dates.empty else "—"
    st.markdown(f'<div class="vm-mini"><div class="vm-mini-label">Latest observation</div><div class="vm-mini-value">{latest_date}</div></div>', unsafe_allow_html=True)

with st.expander("🗃️ Observation data", expanded=False):
    obs1, obs2 = st.tabs(["NDVI observations", "NDMI observations"])
    with obs1:
        st.dataframe(ndvi_p.sort_values("date", ascending=False), use_container_width=True, hide_index=True)
    with obs2:
        st.dataframe(ndmi_p.sort_values("date", ascending=False), use_container_width=True, hide_index=True)

if spatial.get("features"):
    p = spatial["features"][0].get("properties", {})
    st.markdown(
        f'<div class="vm-footer"><strong>ℹ️ Data & quality note:</strong> Sentinel-2 SR Harmonized · native analytical scale 10 m · analytical boundary: SERPRO Project Area · year-to-date spatial composite: {int(p.get("analysis_year") or date.today().year)} · effective period {p.get("analysis_start", "—")} to {p.get("analysis_end", "—")} · mean scene cloud cover {float(p.get("mean_cloud_cover_pct") or 0):.1f}%. The web map uses a 100 m raster derived from the native 10 m analytical surface; the Spatial Analysis Overview remains a 250 m GeoJSON summary.</div>',
        unsafe_allow_html=True,
    )
