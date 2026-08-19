from datetime import date
from io import BytesIO

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

# -----------------------------------------------------------------------------
# Dashboard palette only. Existing analytical web-map symbology is preserved.
# -----------------------------------------------------------------------------
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
  --vm-muted:{MUTED}; --vm-border:{BORDER}; --vm-soft:{SOFT};
}}
[data-testid="stAppViewContainer"] {{
  background:linear-gradient(180deg,#fbfdfc 0%,#f5faf8 100%);
}}
.block-container {{ max-width:1480px; padding-top:1rem; padding-bottom:2.2rem; }}

.vm-hero {{
  background:linear-gradient(135deg,#ffffff 0%,#effaf6 100%);
  border:1px solid var(--vm-border); border-radius:20px;
  padding:20px 24px 17px; margin-bottom:12px;
  box-shadow:0 4px 18px rgba(21,96,100,.06);
}}
.vm-eyebrow {{ color:var(--vm-teal); font-size:.68rem; font-weight:900; letter-spacing:.12em; text-transform:uppercase; }}
.vm-title {{ color:var(--vm-ink); font-size:2rem; font-weight:900; line-height:1.08; margin-top:4px; }}
.vm-subtitle {{ color:var(--vm-muted); font-size:.82rem; line-height:1.45; margin-top:6px; max-width:780px; }}
.vm-pipeline {{
  display:flex; align-items:center; justify-content:flex-end; gap:9px;
  color:var(--vm-muted); font-size:.66rem; font-weight:800;
  margin-top:2px;
}}
.vm-pipeline b {{ color:var(--vm-teal); font-size:.92rem; }}
.vm-pipeline span {{ background:#f5faf8; border:1px solid var(--vm-border); border-radius:10px; padding:8px 10px; }}

.vm-section {{ color:var(--vm-ink); font-size:1.08rem; font-weight:900; margin:17px 0 8px; }}
.vm-caption {{ color:var(--vm-muted); font-size:.72rem; margin:-2px 0 9px; line-height:1.45; }}
.vm-card {{
  background:#fff; border:1px solid var(--vm-border); border-radius:16px;
  padding:15px; box-shadow:0 3px 13px rgba(21,96,100,.045);
}}
.vm-card-title {{ color:var(--vm-ink); font-size:1rem; font-weight:900; margin-bottom:3px; }}
.vm-card-sub {{ color:var(--vm-muted); font-size:.70rem; line-height:1.4; margin-bottom:9px; }}

.vm-kpi {{
  background:#fff; border:1px solid var(--vm-border); border-radius:16px;
  min-height:116px; padding:14px 15px; position:relative; overflow:hidden;
  box-shadow:0 3px 13px rgba(21,96,100,.045);
}}
.vm-kpi:before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--kpi); }}
.vm-kpi-label {{ color:var(--vm-muted); font-size:.65rem; font-weight:900; text-transform:uppercase; letter-spacing:.05em; }}
.vm-kpi-value {{ color:var(--vm-ink); font-size:1.62rem; font-weight:950; line-height:1.08; margin-top:8px; }}
.vm-kpi-note {{ color:var(--vm-muted); font-size:.70rem; margin-top:6px; }}
.vm-dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; background:var(--dot); }}

.vm-row {{ display:flex; justify-content:space-between; gap:10px; padding:6px 0; border-bottom:1px solid #edf3f1; font-size:.72rem; }}
.vm-row:last-child {{ border-bottom:0; }}
.vm-label {{ color:var(--vm-muted); }}
.vm-value {{ color:var(--vm-ink); font-weight:850; text-align:right; }}
.vm-note {{ color:var(--vm-muted); font-size:.70rem; line-height:1.5; }}

.vm-dq {{ margin-top:8px; }}
.vm-dq-head {{ display:flex; justify-content:space-between; color:var(--vm-ink); font-size:.70rem; font-weight:850; }}
.vm-dq-track {{ height:7px; background:#edf3f1; border-radius:99px; overflow:hidden; margin-top:4px; margin-bottom:8px; }}
.vm-dq-fill {{ height:100%; border-radius:99px; }}
.vm-total {{ display:flex; justify-content:space-between; background:#f7faf9; border:1px solid var(--vm-border); border-radius:10px; padding:8px 10px; margin-top:10px; }}
.vm-total span:first-child {{ color:var(--vm-muted); font-size:.70rem; }}
.vm-total span:last-child {{ color:var(--vm-ink); font-weight:950; }}
.vm-confidence {{ margin-top:10px; padding:9px 10px; border-radius:10px; background:#e9f9ef; border:1px solid #c8ecd5; color:#176d3d; font-size:.70rem; font-weight:900; }}

.vm-stress-box {{ border:1px solid var(--vm-border); border-radius:13px; padding:12px; background:#fff; }}
.vm-stress-level {{ font-size:1.35rem; font-weight:950; color:var(--vm-ink); }}
.vm-guide {{ display:grid; gap:7px; margin-top:9px; }}
.vm-guide-row {{ display:grid; grid-template-columns:9px 74px 1fr; align-items:center; gap:7px; font-size:.68rem; }}
.vm-guide-dot {{ width:9px; height:9px; border-radius:50%; }}
.vm-guide-name {{ font-weight:900; color:var(--vm-ink); }}
.vm-guide-text {{ color:var(--vm-muted); }}

.vm-download {{ background:#fff; border:1px solid var(--vm-border); border-radius:16px; padding:13px 15px; }}
.vm-download-title {{ color:var(--vm-ink); font-weight:900; font-size:.95rem; }}
.vm-download-sub {{ color:var(--vm-muted); font-size:.70rem; margin-top:3px; }}

.vm-footer {{ background:linear-gradient(90deg,#effaf6,#fff8f2); border:1px solid var(--vm-border); border-radius:13px; padding:11px 13px; color:var(--vm-muted); font-size:.69rem; line-height:1.5; }}

/* Readability guard: target dashboard widgets only, not the map itself. */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span {{ color:var(--vm-ink) !important; font-weight:750 !important; }}
[data-baseweb="select"] * {{ color:var(--vm-ink) !important; }}
[data-testid="stDataFrame"] {{ border:1px solid var(--vm-border); border-radius:12px; overflow:hidden; }}
[data-testid="stDataFrame"] iframe {{ background:#fff !important; }}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Data loading: unchanged pipeline / loaders.
# -----------------------------------------------------------------------------
ndmi = load_ndmi()
ndvi = load_ndvi()
spatial = load_vegetation_spatial()
raster = load_vegetation_spatial_raster()

for frame in (ndmi, ndvi):
    if not frame.empty and "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")

if ndmi.empty and ndvi.empty:
    st.info("No NDVI/NDMI observations are currently available. Run the vegetation update workflow.")
    st.stop()

scope_keys = sorted(
    set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str))
    | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str))
)
if not scope_keys:
    st.error("Vegetation data has no valid monitoring scope.")
    st.stop()

scope_labels = {
    "project_area": "SERPRO Project Area · analysis",
    "carbon_project_zone": "Carbon Project Zone · reference",
}

# -----------------------------------------------------------------------------
# Header + filters.
# -----------------------------------------------------------------------------
st.markdown(
    """
<div class="vm-hero">
  <div class="vm-eyebrow">SERPRO PROJECT · CLIMATE & CARBON MONITORING</div>
  <div class="vm-title">🌿 Vegetation Monitoring</div>
  <div class="vm-subtitle">Monitor vegetation vigor, canopy moisture and vegetation stress using Sentinel-2 observations across the selected monitoring area.</div>
</div>
""",
    unsafe_allow_html=True,
)

f1, f2 = st.columns([1.1, 1], gap="medium")
with f1:
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

with f2:
    if not all_dates.empty:
        min_date = all_dates.min().date()
        max_date = all_dates.max().date()
        date_range = st.date_input(
            "Monitoring period",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
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


def pct_change(frame, column, days=30):
    if frame.empty or column not in frame.columns or len(frame) < 2:
        return None
    latest = frame.date.max()
    window = frame[frame.date >= latest - pd.Timedelta(days=days)]
    if len(window) < 2:
        return None
    a = float(window.iloc[0][column])
    b = float(window.iloc[-1][column])
    return None if a == 0 else (b - a) / abs(a) * 100


def ndvi_status(value):
    if value is None or pd.isna(value):
        return "No data", MUTED
    if value >= 0.70:
        return "Good vigor", GREEN
    if value >= 0.50:
        return "Moderate vigor", YELLOW
    if value >= 0.30:
        return "Low vigor", PEACH
    return "Very low vigor", ORANGE


def ndmi_status(value):
    if value is None or pd.isna(value):
        return "No data", MUTED
    if value >= 0.40:
        return "Moist", GREEN
    if value >= 0.20:
        return "Moderate", YELLOW
    if value >= 0:
        return "Drying", PEACH
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

stress_color = {
    "HIGH": MAP_STRESS_HIGH,
    "MODERATE": MAP_STRESS_MODERATE,
    "LOW": MAP_STRESS_LOW,
    "STABLE": MAP_DARK_GREEN,
}[stress_level]

# -----------------------------------------------------------------------------
# KPI cards: intentionally simple and readable.
# -----------------------------------------------------------------------------
st.markdown('<div class="vm-section">🌱 Current vegetation condition</div>', unsafe_allow_html=True)
st.markdown('<div class="vm-caption">Latest values for the selected monitoring area. Index values are not percentages.</div>', unsafe_allow_html=True)

kpis = [
    ("🌿", "NDVI", f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—", ndvi_label, GREEN),
    ("💧", "NDMI", f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—", ndmi_label, "#3E8ED0"),
    ("📈", "NDVI change · 30 days", f"{ndvi30:+.1f}%" if ndvi30 is not None else "—", "vs. 30 days ago", ORANGE if ndvi30 is not None and ndvi30 < 0 else GREEN),
    ("🛡️", "Vegetation stress status", stress_level, "NDVI + NDMI screening", stress_color),
]

kcols = st.columns(4, gap="small")
for col, (icon, title, value, note, color) in zip(kcols, kpis):
    with col:
        st.markdown(
            f'<div class="vm-kpi" style="--kpi:{color}"><div class="vm-kpi-label">{icon} {title}</div><div class="vm-kpi-value">{value}</div><div class="vm-kpi-note"><span class="vm-dot" style="--dot:{color}"></span>{note}</div></div>',
            unsafe_allow_html=True,
        )

# -----------------------------------------------------------------------------
# Spatial map + spatial overview.
# -----------------------------------------------------------------------------
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
            if isinstance(ring, list):
                points.extend([p for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2])
    if not points:
        return None
    lons = [float(p[0]) for p in points]
    lats = [float(p[1]) for p in points]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def clean_spatial():
    features = []
    for feature in spatial.get("features", []):
        if not isinstance(feature, dict) or not feature.get("geometry"):
            continue
        geom = feature.get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        props = dict(feature.get("properties") or {})
        for key in (
            "ndvi", "ndmi", "stress", "analysis_year", "analysis_start",
            "analysis_end", "observed_pct", "temporal_fallback_pct",
            "spatial_interpolation_pct", "total_coverage_pct",
        ):
            props.setdefault(key, None)
        features.append({"type": "Feature", "geometry": geom, "properties": props})
    return {"type": "FeatureCollection", "features": features}


def index_color(field, value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return MAP_RED
    if field == "ndvi":
        if x < 0.30:
            return MAP_RED
        if x < 0.50:
            return MAP_YELLOW
        if x < 0.70:
            return MAP_LIGHT_GREEN
        return MAP_DARK_GREEN
    if x < 0:
        return MAP_RED
    if x < 0.20:
        return MAP_YELLOW
    if x < 0.40:
        return MAP_LIGHT_GREEN
    return MAP_DARK_GREEN


def build_map():
    project_area = load_project_area()
    zone = load_carbon_project_zone()
    fmap = folium.Map(location=[-3.10, 112.62], zoom_start=9, tiles=None, control_scale=True)
    folium.TileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors", name="OpenStreetMap", overlay=False, show=True,
    ).add_to(fmap)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri", name="ESRI Satellite Imagery", overlay=False, show=False,
    ).add_to(fmap)

    if project_area.get("features"):
        folium.GeoJson(
            project_area, name="🟢 SERPRO Project Area · AOI",
            style_function=lambda _: {"color": GREEN, "weight": 3, "fillOpacity": 0},
        ).add_to(fmap)
    if zone.get("features"):
        folium.GeoJson(
            zone, name="🟣 Carbon Project Zone · reference",
            style_function=lambda _: {"color": TEAL, "weight": 2, "fillOpacity": 0},
        ).add_to(fmap)

    bounds = raster.get("bounds") or bounds_from_geojson(project_area)
    layers = raster.get("layers", {})
    if raster and bounds and layers:
        for key, label, show, opacity in (
            ("ndvi", "🌿 NDVI · YTD vigor", True, 0.80),
            ("ndmi", "💧 NDMI · YTD moisture", False, 0.80),
            ("stress", "⚠️ Vegetation stress · YTD", False, 0.72),
        ):
            packed = layers.get(key)
            if packed:
                ImageOverlay(
                    image=raster_data_uri(packed), bounds=bounds, opacity=opacity,
                    name=label, show=show, interactive=False, cross_origin=False,
                    zindex=2, pixelated=False,
                ).add_to(fmap)
    else:
        data = clean_spatial()
        for field, label, show in (("ndvi", "🌿 NDVI · overview", True), ("ndmi", "💧 NDMI · overview", False), ("stress", "⚠️ Vegetation stress · overview", False)):
            def style(feature, field=field):
                props = feature.get("properties", {})
                if field == "stress":
                    color = {"HIGH": MAP_STRESS_HIGH, "MODERATE": MAP_STRESS_MODERATE, "LOW": MAP_STRESS_LOW, "STABLE": MAP_DARK_GREEN}.get(str(props.get("stress")), MAP_RED)
                else:
                    color = index_color(field, props.get(field))
                return {"fillColor": color, "color": color, "weight": .25, "fillOpacity": .72}
            folium.GeoJson(data, name=label, style_function=style, show=show).add_to(fmap)

    # Clickable project-area cells: popup data are sourced from the existing spatial dataset.
    data = clean_spatial()
    if data.get("features"):
        popup = folium.GeoJsonPopup(
            fields=[
                "ndvi", "ndmi", "stress", "analysis_year", "analysis_start", "analysis_end",
                "observed_pct", "temporal_fallback_pct", "spatial_interpolation_pct",
            ],
            aliases=[
                "🌿 NDVI", "💧 NDMI", "⚠️ Vegetation Stress", "Analysis Year", "Analysis Start", "Analysis End",
                "Directly Observed (%)", "Temporal Fallback (%)", "Spatial Interpolation (%)",
            ],
            localize=True, labels=True, sticky=False, max_width=390,
        )
        folium.GeoJson(
            data,
            name="__vegetation_click_info__",
            control=False, show=True,
            style_function=lambda _: {"fillColor": "#ffffff", "fillOpacity": .01, "color": "#ffffff", "weight": 0, "opacity": 0},
            highlight_function=lambda _: {"fillColor": GREEN, "fillOpacity": .08, "color": GREEN, "weight": 1, "opacity": .35},
            popup=popup,
        ).add_to(fmap)

        legend_html = f"""
        <div style="position:fixed; z-index:9998; bottom:18px; left:18px; background:rgba(255,255,255,.97); border:1px solid #d9e1df; border-radius:12px; padding:10px 12px; box-shadow:0 3px 12px rgba(0,0,0,.12); font-family:Arial,sans-serif; font-size:10px; line-height:1.5; min-width:260px; color:#263b38;">
          <div style="font-weight:900;font-size:11px;margin-bottom:5px;">🎨 Map Symbology</div>
          <div style="font-weight:900;">🌿 NDVI · YTD vigor</div>
          <div><span style="color:{MAP_RED}">■</span> &lt;0.30 &nbsp; <span style="color:{MAP_YELLOW}">■</span> 0.30–0.49 &nbsp; <span style="color:{MAP_LIGHT_GREEN}">■</span> 0.50–0.69 &nbsp; <span style="color:{MAP_DARK_GREEN}">■</span> ≥0.70</div>
          <div style="font-weight:900;margin-top:5px;">💧 NDMI · YTD moisture</div>
          <div><span style="color:{MAP_RED}">■</span> &lt;0 &nbsp; <span style="color:{MAP_YELLOW}">■</span> 0–0.19 &nbsp; <span style="color:{MAP_LIGHT_GREEN}">■</span> 0.20–0.39 &nbsp; <span style="color:{MAP_DARK_GREEN}">■</span> ≥0.40</div>
          <div style="font-weight:900;margin-top:5px;">⚠️ Stress</div>
          <div><span style="color:{MAP_DARK_GREEN}">■</span> Stable &nbsp; <span style="color:{MAP_STRESS_LOW}">■</span> Low &nbsp; <span style="color:{MAP_STRESS_MODERATE}">■</span> Moderate &nbsp; <span style="color:{MAP_STRESS_HIGH}">■</span> High</div>
        </div>
        """
        folium.Element(legend_html).add_to(fmap)

    if bounds:
        fmap.fit_bounds(bounds, padding=(10, 10))
    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap


st.markdown('<div class="vm-section">🗺️ Spatial vegetation condition</div>', unsafe_allow_html=True)
st.markdown('<div class="vm-caption">The map displays the 100 m web raster derived from the native 10 m analytical surface. Click a project-area cell to inspect its indicators.</div>', unsafe_allow_html=True)

map_col, overview_col = st.columns([1.75, 1], gap="medium")
with map_col:
    if spatial.get("features") or raster:
        try:
            st_folium(build_map(), width=None, height=535, returned_objects=[], key="vegetation_spatial_map_v3")
        except Exception as exc:
            st.error("The spatial vegetation map could not be rendered.")
            st.caption(f"Map rendering is isolated from the vegetation calculations. {exc}")
    else:
        st.warning("Spatial vegetation layer is not available yet. Run the Update SERPRO Spatial Vegetation workflow.")

with overview_col:
    props = spatial.get("features", [{}])[0].get("properties", {}) if spatial.get("features") else raster.get("metadata", {})
    year = int(props.get("analysis_year") or date.today().year)
    start_text = props.get("analysis_start") or f"{year}-01-01"
    end_text = props.get("analysis_end") or (all_dates.max().date().isoformat() if not all_dates.empty else "—")
    scenes = int(props.get("scene_count") or 0)
    cloud = float(props.get("mean_cloud_cover_pct") or 0)
    observed = max(0.0, min(100.0, float(props.get("observed_pct") or 0)))
    temporal = max(0.0, min(100.0, float(props.get("temporal_fallback_pct") or 0)))
    spatial_fill = max(0.0, min(100.0, float(props.get("spatial_interpolation_pct") or 0)))
    total = float(props.get("total_coverage_pct") or min(100.0, observed + temporal + spatial_fill))

    st.markdown('<div class="vm-card"><div class="vm-card-title">📊 Spatial Analysis Overview</div><div class="vm-card-sub">How the current vegetation map was produced</div>', unsafe_allow_html=True)
    rows = [
        ("Analysis period", f"{start_text} → {end_text}"),
        ("Composite", f"{year} year-to-date median"),
        ("Analysis resolution", "10 × 10 m"),
        ("Web map display", "100 m raster"),
        ("Spatial overview", "250 m GeoJSON"),
        ("Analysis boundary", "SERPRO Project Area · AOI"),
        ("Reference boundary", "Carbon Project Zone"),
        ("Sentinel-2 scenes", f"{scenes:,}"),
        ("Mean cloud cover", f"{cloud:.1f}%"),
        ("Method", "Annual YTD + spatial gap fill"),
    ]
    for label, value in rows:
        st.markdown(f'<div class="vm-row"><span class="vm-label">{label}</span><span class="vm-value">{value}</span></div>', unsafe_allow_html=True)

    st.markdown('<div style="height:5px"></div><div class="vm-card-title" style="font-size:.86rem">Data quality</div>', unsafe_allow_html=True)
    for label, value, color in (("Directly observed", observed, GREEN), ("Temporal fallback", temporal, YELLOW), ("Spatial interpolation", spatial_fill, ORANGE)):
        st.markdown(f'<div class="vm-dq"><div class="vm-dq-head"><span>{label}</span><span>{value:.1f}%</span></div><div class="vm-dq-track"><div class="vm-dq-fill" style="width:{value:.2f}%;background:{color}"></div></div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="vm-total"><span>Total coverage</span><span>{total:.1f}%</span></div>', unsafe_allow_html=True)
    if observed >= 85:
        st.markdown('<div class="vm-confidence">🟢 HIGH CONFIDENCE</div>', unsafe_allow_html=True)
    elif observed >= 60:
        st.markdown('<div class="vm-confidence" style="background:#fff9d9;color:#75620a;border-color:#f2df73">🟡 MODERATE CONFIDENCE</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="vm-confidence" style="background:#fff0ea;color:#a94a2d;border-color:#f9c7b5">🟠 LOW CONFIDENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="vm-note" style="margin-top:7px">Confidence represents the share of the Project Area directly observed by Sentinel-2. Temporal fallback and spatial interpolation are reported separately.</div></div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Trend + stress overview.
# -----------------------------------------------------------------------------
st.markdown('<div class="vm-section">📈 Recent vegetation trend</div>', unsafe_allow_html=True)
st.markdown('<div class="vm-caption">Latest observations of vegetation vigor and canopy moisture. Hover the chart for exact values.</div>', unsafe_allow_html=True)
trend_col, stress_col = st.columns([1.65, 1], gap="medium")

with trend_col:
    fig = go.Figure()
    if not ndvi_p.empty:
        fig.add_scatter(
            x=ndvi_p.tail(30).date, y=ndvi_p.tail(30).ndvi,
            mode="lines+markers", name="NDVI · vigor",
            line=dict(color=TEAL, width=2.5), marker=dict(color=GREEN, size=5),
        )
    if not ndmi_p.empty:
        fig.add_scatter(
            x=ndmi_p.tail(30).date, y=ndmi_p.tail(30).ndmi,
            mode="lines+markers", name="NDMI · moisture",
            line=dict(color="#3E8ED0", width=2.5), marker=dict(color=ORANGE, size=5),
        )
    fig.update_layout(
        height=300, margin=dict(l=10, r=10, t=12, b=10),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(color=INK, size=11), hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0),
        xaxis=dict(showgrid=False), yaxis=dict(title="Index value", gridcolor="#E8F0EE"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with stress_col:
    st.markdown('<div class="vm-card"><div class="vm-card-title">🧭 Vegetation Stress Status Overview</div><div class="vm-card-sub">Combined screening from recent NDVI and NDMI change.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="vm-stress-box"><div class="vm-stress-level"><span class="vm-dot" style="--dot:{stress_color}"></span>{stress_level}</div><div class="vm-note" style="margin-top:4px">{("No significant stress signal detected." if stress_level == "STABLE" else "A recent decline is present; review the spatial pattern before field verification." if stress_level in ("LOW", "MODERATE") else "Strong decline signal detected. Prioritize field verification.")}</div></div>', unsafe_allow_html=True)
    guide = [
        ("STABLE", MAP_DARK_GREEN, "No negative trend signal."),
        ("LOW", MAP_STRESS_LOW, "Recent decline, low screening concern."),
        ("MODERATE", MAP_STRESS_MODERATE, "Monitor spatial pattern."),
        ("HIGH", MAP_STRESS_HIGH, "Field verification recommended."),
    ]
    st.markdown('<div class="vm-guide">' + ''.join(f'<div class="vm-guide-row"><span class="vm-guide-dot" style="background:{c}"></span><span class="vm-guide-name">{n}</span><span class="vm-guide-text">{t}</span></div>' for n,c,t in guide) + '</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Observation data + downloads.
# -----------------------------------------------------------------------------
st.markdown('<div class="vm-section">🗃️ Observation Data</div>', unsafe_allow_html=True)
st.markdown('<div class="vm-caption">Latest available observations for the selected monitoring area. Download the same filtered data for reporting or further analysis.</div>', unsafe_allow_html=True)

obs_col1, obs_col2 = st.columns([1, 1], gap="small")
with obs_col1:
    st.markdown(f'<div class="vm-card"><div class="vm-card-title">🌿 NDVI observations</div><div class="vm-card-sub">{len(ndvi_p):,} records</div></div>', unsafe_allow_html=True)
with obs_col2:
    st.markdown(f'<div class="vm-card"><div class="vm-card-title">💧 NDMI observations</div><div class="vm-card-sub">{len(ndmi_p):,} records</div></div>', unsafe_allow_html=True)

combined = pd.merge(
    ndvi_p.rename(columns={"ndvi": "ndvi"}),
    ndmi_p.rename(columns={"ndmi": "ndmi"}),
    on=["date", "scope"], how="outer", suffixes=("_ndvi", "_ndmi"),
)
for col in ["cloudy_pixel_percentage_ndvi", "cloudy_pixel_percentage_ndmi"]:
    if col not in combined.columns:
        combined[col] = pd.NA
combined["cloudy_pixel_percentage"] = combined[["cloudy_pixel_percentage_ndvi", "cloudy_pixel_percentage_ndmi"]].mean(axis=1)
combined = combined[[c for c in ["date", "scope", "ndvi", "ndmi", "cloudy_pixel_percentage", "source_ndvi", "source_ndmi", "processing_time_utc_ndvi", "processing_time_utc_ndmi"] if c in combined.columns]].sort_values("date", ascending=False)

ndvi_download = ndvi_p.sort_values("date", ascending=False).copy()
ndmi_download = ndmi_p.sort_values("date", ascending=False).copy()
combined_download = combined.copy()

csv_bytes = combined_download.to_csv(index=False).encode("utf-8-sig")
excel_buffer = BytesIO()
with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    ndvi_download.to_excel(writer, index=False, sheet_name="NDVI")
    ndmi_download.to_excel(writer, index=False, sheet_name="NDMI")
    combined_download.to_excel(writer, index=False, sheet_name="Combined")
excel_buffer.seek(0)

b1, b2, b3 = st.columns([1.4, 1, 1], gap="small")
with b1:
    st.markdown('<div class="vm-download"><div class="vm-download-title">Download observations</div><div class="vm-download-sub">Filtered to the selected monitoring area and period.</div></div>', unsafe_allow_html=True)
with b2:
    st.download_button(
        "⬇️ Download Excel",
        data=excel_buffer.getvalue(),
        file_name=f"SERPRO_Vegetation_Observations_{scope}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
with b3:
    st.download_button(
        "⬇️ Download CSV",
        data=csv_bytes,
        file_name=f"SERPRO_Vegetation_Observations_{scope}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with st.expander("View observation table", expanded=True):
    tab_ndvi, tab_ndmi = st.tabs(["NDVI observations", "NDMI observations"])
    with tab_ndvi:
        st.dataframe(ndvi_download, use_container_width=True, hide_index=True)
    with tab_ndmi:
        st.dataframe(ndmi_download, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# Data note: explicitly documents the unchanged analysis/display architecture.
# -----------------------------------------------------------------------------
if spatial.get("features"):
    p = spatial["features"][0].get("properties", {})
    analysis_year = int(p.get("analysis_year") or date.today().year)
    st.markdown(
        f'<div class="vm-footer"><strong>ℹ️ Data & quality note:</strong> Sentinel-2 SR Harmonized · native analytical scale 10 m · analytical boundary: SERPRO Project Area · year-to-date spatial composite: {analysis_year} · effective period {p.get("analysis_start", "—")} to {p.get("analysis_end", "—")} · mean scene cloud cover {float(p.get("mean_cloud_cover_pct") or 0):.1f}%. The web map is displayed at 100 m from the native 10 m analytical surface; the Spatial Analysis Overview remains available as a 250 m GeoJSON summary. Dashboard colors are independent from map analytical symbology.</div>',
        unsafe_allow_html=True,
    )
