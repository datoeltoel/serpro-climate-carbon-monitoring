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

# Dashboard palette only. Existing web-map analytical symbology is unchanged.
TEAL = "#156064"
GREEN = "#00C49A"
YELLOW = "#F8E16C"
PEACH = "#FFC2B4"
ORANGE = "#FB8F67"
INK = "#173F42"
MUTED = "#5F777A"
BORDER = "#DCE9E6"
SOFT = "#F7FAF9"
WHITE = "#FFFFFF"
MAP_RED = "#D73027"
MAP_YELLOW = "#FEE08B"
MAP_LIGHT_GREEN = "#91CF60"
MAP_DARK_GREEN = "#1A9850"
MAP_STRESS_LOW = "#FEE08B"
MAP_STRESS_MODERATE = "#F46D43"
MAP_STRESS_HIGH = "#D73027"

st.markdown(f"""
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stMainBlockContainer"], [data-testid="stMarkdownContainer"] {{
  color:{INK} !important;
}}
[data-testid="stAppViewContainer"] {{ background:linear-gradient(180deg,#fbfdfc 0%,#f5faf8 100%) !important; }}
.block-container {{ max-width:1500px !important; padding-top:1rem !important; padding-bottom:2.5rem !important; }}
.vm-hero {{ background:linear-gradient(135deg,#ffffff 0%,#f0faf7 100%); border:1px solid {BORDER}; border-radius:20px; padding:20px 24px; margin-bottom:14px; box-shadow:0 5px 20px rgba(21,96,100,.06); }}
.vm-kicker {{ color:{TEAL}; font-size:.68rem; font-weight:900; letter-spacing:.13em; text-transform:uppercase; }}
.vm-title {{ color:{INK}; font-size:2rem; font-weight:900; line-height:1.05; margin-top:4px; }}
.vm-subtitle {{ color:{MUTED}; font-size:.86rem; line-height:1.45; margin-top:7px; }}
.vm-meta {{ display:inline-block; background:#e8f7f3; color:{TEAL}; border:1px solid #c7e9e2; border-radius:999px; padding:6px 10px; margin-top:10px; font-size:.70rem; font-weight:900; }}
.vm-section {{ color:{INK}; font-size:1.1rem; font-weight:900; margin:17px 0 7px; }}
.vm-caption {{ color:{MUTED}; font-size:.75rem; line-height:1.4; margin-bottom:9px; }}
.vm-card {{ background:{WHITE}; border:1px solid {BORDER}; border-radius:17px; padding:15px; box-shadow:0 3px 14px rgba(21,96,100,.045); }}
.vm-card-title {{ color:{INK}; font-size:1rem; font-weight:900; margin-bottom:5px; }}
.vm-card-sub {{ color:{MUTED}; font-size:.72rem; line-height:1.4; margin-bottom:9px; }}
.kpi {{ background:#fff; border:1px solid {BORDER}; border-radius:16px; min-height:122px; padding:14px 16px; box-shadow:0 3px 14px rgba(21,96,100,.055); border-left:5px solid var(--accent); }}
.kpi-label {{ color:{MUTED}; font-size:.68rem; font-weight:900; text-transform:uppercase; letter-spacing:.05em; }}
.kpi-value {{ color:{INK}; font-size:1.72rem; font-weight:950; margin-top:8px; line-height:1.05; }}
.kpi-sub {{ font-size:.74rem; font-weight:850; margin-top:8px; }}
.row {{ display:flex; justify-content:space-between; gap:12px; padding:7px 0; border-bottom:1px solid #edf3f1; font-size:.76rem; }}
.label {{ color:{MUTED}; }} .value {{ color:{INK}; font-weight:850; text-align:right; }}
.badge {{ border-radius:10px; padding:8px 10px; margin-top:10px; font-size:.75rem; font-weight:900; }}
.good {{ background:#e8f7f3; color:#126a68; border:1px solid #b9e7de; }}
.warn {{ background:#fff9d9; color:#75620a; border:1px solid #f2df73; }}
.alert {{ background:#fff0ea; color:#a94a2d; border:1px solid #f9c7b5; }}
.mini {{ background:#f9fcfb; border:1px solid #e4efec; border-radius:12px; padding:10px 11px; margin-bottom:8px; }}
.mini-label {{ color:{MUTED}; font-size:.66rem; font-weight:850; text-transform:uppercase; }}
.mini-value {{ color:{INK}; font-size:1.05rem; font-weight:950; margin-top:3px; }}
.note {{ color:{MUTED}; font-size:.72rem; line-height:1.5; }}
.dq-head {{ display:flex; justify-content:space-between; color:{INK}; font-size:.74rem; font-weight:850; margin-top:9px; }}
.dq-track {{ height:7px; background:#edf3f1; border-radius:99px; overflow:hidden; margin-top:5px; }}
.dq-fill {{ height:100%; border-radius:99px; }}
.dq-total {{ background:{SOFT}; border:1px solid {BORDER}; border-radius:10px; padding:9px 11px; display:flex; justify-content:space-between; margin-top:10px; }}
.footer {{ background:linear-gradient(90deg,#f1faf7,#fff7f1); border:1px solid {BORDER}; border-radius:14px; padding:12px 14px; color:{MUTED}; font-size:.72rem; line-height:1.5; margin-top:14px; }}
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span {{ color:{INK} !important; font-weight:750 !important; }}
[data-baseweb="select"] *, [data-baseweb="input"] * {{ color:{INK} !important; }}
[data-testid="stExpander"], [data-testid="stDataFrame"] {{ background:#fff !important; border:1px solid {BORDER} !important; border-radius:13px !important; }}
[data-testid="stDataFrame"] iframe {{ background:#fff !important; }}
</style>
""", unsafe_allow_html=True)

ndvi = load_ndvi()
ndmi = load_ndmi()
spatial = load_vegetation_spatial()
raster = load_vegetation_spatial_raster()

for df in (ndvi, ndmi):
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

if ndvi.empty and ndmi.empty:
    st.info("No NDVI/NDMI observations are available yet. Run the vegetation update workflow.")
    st.stop()

scopes = sorted(set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str)) | set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str)))
scope = "project_area" if "project_area" in scopes else scopes[0]

st.markdown(f"""
<div class="vm-hero">
  <div class="vm-kicker">SERPRO PROJECT · REMOTE SENSING MRV</div>
  <div class="vm-title">🌿 Vegetation Monitoring</div>
  <div class="vm-subtitle">A clear operational view of vegetation vigor, canopy moisture and spatial stress across the SERPRO Project Area.</div>
  <span class="vm-meta">10 m analytical surface · 100 m web map · 250 m spatial overview</span>
</div>
""", unsafe_allow_html=True)

c1, c2 = st.columns([1.1, 1], gap="medium")
with c1:
    scope = st.selectbox("Monitoring area", scopes, index=scopes.index(scope), format_func=lambda x: {"project_area":"🟢 SERPRO Project Area · analysis","carbon_project_zone":"🟣 Carbon Project Zone · reference"}.get(x, x.replace("_"," ").title()))
ndvi_s = ndvi[ndvi.scope.astype(str) == scope].copy() if "scope" in ndvi.columns else ndvi.copy()
ndmi_s = ndmi[ndmi.scope.astype(str) == scope].copy() if "scope" in ndmi.columns else ndmi.copy()
all_dates = pd.concat([x["date"] for x in (ndvi_s, ndmi_s) if not x.empty], ignore_index=True).dropna()
with c2:
    if not all_dates.empty:
        lo, hi = all_dates.min().date(), all_dates.max().date()
        period = st.date_input("Monitoring period", value=(lo, hi), min_value=lo, max_value=hi)
    else:
        period = None

if isinstance(period, (tuple, list)) and len(period) == 2:
    start = pd.Timestamp(period[0]); end = pd.Timestamp(period[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    ndvi_p = ndvi_s[(ndvi_s.date >= start) & (ndvi_s.date <= end)].sort_values("date").copy()
    ndmi_p = ndmi_s[(ndmi_s.date >= start) & (ndmi_s.date <= end)].sort_values("date").copy()
else:
    ndvi_p, ndmi_p = ndvi_s.sort_values("date"), ndmi_s.sort_values("date")

def change30(df, field):
    if df.empty or field not in df.columns or len(df) < 2: return None
    latest = df.date.max(); w = df[df.date >= latest - pd.Timedelta(days=30)]
    if len(w) < 2: return None
    a, b = float(w.iloc[0][field]), float(w.iloc[-1][field])
    return None if a == 0 else (b-a)/abs(a)*100

def vigor(v):
    if v is None: return "No data", MUTED
    if v >= .70: return "Good vigor", GREEN
    if v >= .50: return "Moderate", YELLOW
    if v >= .30: return "Low vigor", PEACH
    return "Very low", ORANGE

def moisture(v):
    if v is None: return "No data", MUTED
    if v >= .40: return "Moist", GREEN
    if v >= .20: return "Moderate", YELLOW
    if v >= 0: return "Drying", PEACH
    return "Low moisture", ORANGE

latest_ndvi = float(ndvi_p.iloc[-1].ndvi) if not ndvi_p.empty and "ndvi" in ndvi_p.columns else None
latest_ndmi = float(ndmi_p.iloc[-1].ndmi) if not ndmi_p.empty and "ndmi" in ndmi_p.columns else None
ndvi30 = change30(ndvi_p, "ndvi"); ndmi30 = change30(ndmi_p, "ndmi")
ndvi_label, ndvi_color = vigor(latest_ndvi); ndmi_label, ndmi_color = moisture(latest_ndmi)
if ndvi30 is not None and ndmi30 is not None and ndvi30 <= -10 and ndmi30 <= -10: stress = "HIGH"
elif (ndvi30 is not None and ndvi30 <= -10) or (ndmi30 is not None and ndmi30 <= -10): stress = "MODERATE"
elif (ndvi30 is not None and ndvi30 < 0) or (ndmi30 is not None and ndmi30 < 0): stress = "LOW"
else: stress = "STABLE"
stress_color = {"HIGH":ORANGE,"MODERATE":PEACH,"LOW":YELLOW,"STABLE":GREEN}[stress]

st.markdown('<div class="vm-section">🌱 Current vegetation condition</div><div class="vm-caption">Latest values from the selected monitoring area. NDVI and NDMI are index values, not percentages.</div>', unsafe_allow_html=True)
kpis = [
    ("🌿 NDVI · vegetation vigor", f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—", ndvi_label, ndvi_color),
    ("💧 NDMI · canopy moisture", f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—", ndmi_label, ndmi_color),
    ("📉 NDVI change · 30 days", f"{ndvi30:+.1f}%" if ndvi30 is not None else "—", "Compared with 30 days ago", ORANGE if ndvi30 is not None and ndvi30 < 0 else GREEN),
    ("⚠️ Vegetation stress", stress, "NDVI + NDMI screening", stress_color),
]
cols = st.columns(4, gap="small")
for col, (label, value, sub, accent) in zip(cols, kpis):
    with col:
        st.markdown(f'<div class="kpi" style="--accent:{accent}"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub" style="color:{accent}">{sub}</div></div>', unsafe_allow_html=True)

status = {"HIGH":"🚨 High stress signal: both indicators declined ≥10% over the last 30 days. Prioritize field verification.","MODERATE":"⚠️ Moderate stress signal: at least one indicator declined ≥10%. Review the spatial pattern.","LOW":"ℹ️ Low stress signal: a recent decline is present, but the moderate threshold has not been reached.","STABLE":"✅ Stable screening result: no negative NDVI/NDMI trend signal was detected."}[stress]
st.markdown(f'<div class="badge {"alert" if stress=="HIGH" else "warn" if stress=="MODERATE" else "good"}">{status}</div>', unsafe_allow_html=True)

# Spatial map: existing 100 m raster and 250 m GeoJSON are reused. Analytical calculations stay 10 m.
def bounds_from_geojson(fc):
    pts=[]
    for f in (fc or {}).get("features", []):
        g=f.get("geometry") or {}; c=g.get("coordinates",[])
        rings = c if g.get("type")=="Polygon" else [r for p in c for r in p] if g.get("type")=="MultiPolygon" else []
        for ring in rings:
            pts.extend([p for p in ring if isinstance(p,(list,tuple)) and len(p)>=2])
    if not pts: return None
    return [[min(p[1] for p in pts), min(p[0] for p in pts)],[max(p[1] for p in pts), max(p[0] for p in pts)]]

def clean_features():
    out=[]
    for f in spatial.get("features",[]):
        if not f.get("geometry"): continue
        p=dict(f.get("properties") or {})
        for k in ["ndvi","ndmi","stress","analysis_year","analysis_start","analysis_end","observed_pct","temporal_fallback_pct","spatial_interpolation_pct"]: p.setdefault(k,None)
        out.append({"type":"Feature","geometry":f["geometry"],"properties":p})
    return {"type":"FeatureCollection","features":out}

def build_map():
    pa=load_project_area(); zone=load_carbon_project_zone(); fc=clean_features()
    b=raster.get("bounds") or bounds_from_geojson(pa)
    m=folium.Map(location=[-3.10,112.62], zoom_start=9, tiles=None, control_scale=True)
    folium.TileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",attr="© OpenStreetMap contributors",name="🗺️ OpenStreetMap",overlay=False,show=True).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",attr="Tiles © Esri",name="🛰️ Satellite imagery",overlay=False,show=False).add_to(m)
    if pa.get("features"): folium.GeoJson(pa,name="🟢 SERPRO Project Area · AOI",style_function=lambda _: {"color":GREEN,"weight":3,"fillOpacity":0}).add_to(m)
    if zone.get("features"): folium.GeoJson(zone,name="🟣 Carbon Project Zone · reference",style_function=lambda _: {"color":TEAL,"weight":2,"fillOpacity":0}).add_to(m)
    layers=raster.get("layers",{})
    if b and layers:
        for key,label,show,opacity in [("ndvi","🌿 NDVI · YTD vigor",True,.82),("ndmi","💧 NDMI · YTD moisture",False,.82),("stress","⚠️ Vegetation stress · YTD",False,.75)]:
            packed=layers.get(key)
            if packed: ImageOverlay(image=raster_data_uri(packed),bounds=b,opacity=opacity,name=label,show=show,interactive=False,cross_origin=False,zindex=2).add_to(m)
    if fc.get("features"):
        popup=folium.GeoJsonPopup(fields=["ndvi","ndmi","stress","analysis_year","analysis_start","analysis_end","observed_pct","temporal_fallback_pct","spatial_interpolation_pct"],aliases=["🌿 NDVI","💧 NDMI","⚠️ Stress","Analysis year","Analysis start","Analysis end","Directly observed (%)","Temporal fallback (%)","Spatial interpolation (%)"],localize=True,labels=True,max_width=380)
        folium.GeoJson(fc,name="Vegetation values · click",show=True,control=False,style_function=lambda _: {"fillColor":"#ffffff","fillOpacity":.01,"weight":0,"opacity":0},highlight_function=lambda _: {"fillColor":GREEN,"fillOpacity":.08,"color":GREEN,"weight":1},popup=popup).add_to(m)
        legend=f'''<div style="position:fixed;z-index:9998;bottom:18px;left:18px;background:rgba(255,255,255,.97);border:1px solid #d9e1df;border-radius:12px;padding:11px 13px;box-shadow:0 3px 12px rgba(0,0,0,.12);font:11px Arial;color:#263b38;min-width:255px"><b style="font-size:12px">🎨 Vegetation symbology</b><br><b>🌿 NDVI</b><br><span style="color:{MAP_RED}">■</span> &lt;0.30 &nbsp; <span style="color:{MAP_YELLOW}">■</span> 0.30–0.49 &nbsp; <span style="color:{MAP_LIGHT_GREEN}">■</span> 0.50–0.69 &nbsp; <span style="color:{MAP_DARK_GREEN}">■</span> ≥0.70<br><b>💧 NDMI</b><br><span style="color:{MAP_RED}">■</span> &lt;0 &nbsp; <span style="color:{MAP_YELLOW}">■</span> 0–0.19 &nbsp; <span style="color:{MAP_LIGHT_GREEN}">■</span> 0.20–0.39 &nbsp; <span style="color:{MAP_DARK_GREEN}">■</span> ≥0.40<br><b>⚠️ Stress</b><br><span style="color:{MAP_DARK_GREEN}">■</span> Stable &nbsp; <span style="color:{MAP_STRESS_LOW}">■</span> Low &nbsp; <span style="color:{MAP_STRESS_MODERATE}">■</span> Moderate &nbsp; <span style="color:{MAP_STRESS_HIGH}">■</span> High</div>'''
        folium.Element(legend).add_to(m)
    if b: m.fit_bounds(b,padding=(10,10))
    folium.LayerControl(collapsed=False).add_to(m)
    return m

st.markdown('<div class="vm-section">🗺️ Spatial vegetation condition</div><div class="vm-caption">10 m analytical surface → 100 m browser raster. Click the Project Area to inspect NDVI, NDMI, stress and data quality.</div>', unsafe_allow_html=True)
map_col, side_col = st.columns([2.1,1], gap="medium")
with map_col:
    try: st_folium(build_map(), width=700, height=540, returned_objects=[], key="vegetation_map_v2", use_container_width=True)
    except Exception as exc: st.error(f"Map rendering failed: {exc}")
with side_col:
    p=spatial.get("features",[{}])[0].get("properties",{}) if spatial.get("features") else {}
    st.markdown('<div class="vm-card"><div class="vm-card-title">📊 Spatial analysis overview</div><div class="vm-card-sub">Processing and data-quality summary</div>', unsafe_allow_html=True)
    year=int(p.get("analysis_year") or date.today().year); start=p.get("analysis_start") or f"{year}-01-01"; end=p.get("analysis_end") or "—"; scenes=int(p.get("scene_count") or 0); cloud=float(p.get("mean_cloud_cover_pct") or 0)
    for a,b in [("Analysis period",f"{start} → {end}"),("Composite",f"{year} year-to-date median"),("Analysis resolution","10 × 10 m"),("Web display","100 m raster"),("Spatial overview","250 m GeoJSON"),("Analysis boundary","SERPRO Project Area · AOI"),("Reference boundary","Carbon Project Zone"),("Sentinel-2 scenes",f"{scenes:,}"),("Mean cloud cover",f"{cloud:.1f}%"),("Method","Annual YTD + spatial gap fill")]: st.markdown(f'<div class="row"><span class="label">{a}</span><span class="value">{b}</span></div>',unsafe_allow_html=True)
    obs=float(p.get("observed_pct") or 0); temporal=float(p.get("temporal_fallback_pct") or 0); interp=float(p.get("spatial_interpolation_pct") or 0); total=float(p.get("total_coverage_pct") or min(100,obs+temporal+interp))
    st.markdown('<div class="vm-card-title" style="margin-top:12px">Data quality</div>',unsafe_allow_html=True)
    for label,val,col in [("Directly observed",obs,GREEN),("Temporal fallback",temporal,YELLOW),("Spatial interpolation",interp,ORANGE)]: st.markdown(f'<div class="dq-head"><span>{label}</span><span>{val:.1f}%</span></div><div class="dq-track"><div class="dq-fill" style="width:{val:.2f}%;background:{col}"></div></div>',unsafe_allow_html=True)
    st.markdown(f'<div class="dq-total"><span class="label">Total coverage</span><b class="value">{total:.1f}%</b></div>',unsafe_allow_html=True)
    badge="HIGH CONFIDENCE" if obs>=85 else "MODERATE CONFIDENCE" if obs>=60 else "LOW CONFIDENCE"; cls="good" if obs>=85 else "warn" if obs>=60 else "alert"
    st.markdown(f'<div class="badge {cls}">🟢 {badge}</div><div class="note">Confidence is the share of the Project Area directly observed by Sentinel-2. Fallback and interpolation are reported separately.</div></div>',unsafe_allow_html=True)

st.markdown('<div class="vm-section">📈 Recent vegetation trend</div><div class="vm-caption">The trend is derived from the native 10 m analytical observations. Web display resolution does not change these values.</div>',unsafe_allow_html=True)
trend_col, interp_col=st.columns([1.6,1],gap="medium")
with trend_col:
    fig=go.Figure()
    if not ndvi_p.empty: fig.add_scatter(x=ndvi_p.tail(30).date,y=ndvi_p.tail(30).ndvi,mode="lines+markers",name="NDVI · vigor",line=dict(color=TEAL,width=2.5),marker=dict(color=GREEN,size=5))
    if not ndmi_p.empty: fig.add_scatter(x=ndmi_p.tail(30).date,y=ndmi_p.tail(30).ndmi,mode="lines+markers",name="NDMI · moisture",line=dict(color=ORANGE,width=2.5),marker=dict(color=PEACH,size=5))
    fig.update_layout(height=300,margin=dict(l=12,r=12,t=20,b=10),paper_bgcolor=WHITE,plot_bgcolor=WHITE,font=dict(color=INK),hovermode="x unified",legend=dict(orientation="h",y=1.08,x=0),xaxis=dict(showgrid=False),yaxis=dict(gridcolor="#E8F0EE"),yaxis_title="Index value")
    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
with interp_col:
    st.markdown('<div class="vm-card"><div class="vm-card-title">🧭 Current interpretation</div><div class="vm-card-sub">A quick reading for operational monitoring</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="mini"><div class="mini-label">Vegetation vigor</div><div class="mini-value">{ndvi_label}</div><div class="note">NDVI {latest_ndvi:.3f}</div></div>' if latest_ndvi is not None else '<div class="mini"><div class="mini-label">Vegetation vigor</div><div class="mini-value">No data</div></div>',unsafe_allow_html=True)
    st.markdown(f'<div class="mini"><div class="mini-label">Canopy moisture</div><div class="mini-value">{ndmi_label}</div><div class="note">NDMI {latest_ndmi:.3f}</div></div>' if latest_ndmi is not None else '<div class="mini"><div class="mini-label">Canopy moisture</div><div class="mini-value">No data</div></div>',unsafe_allow_html=True)
    cls="alert" if stress=="HIGH" else "warn" if stress=="MODERATE" else "good"
    st.markdown(f'<div class="badge {cls}">⚠️ Combined stress: {stress}</div><div class="note">Screening indicator only; not standalone evidence of degradation or carbon loss.</div></div>',unsafe_allow_html=True)

st.markdown('<div class="vm-section">📋 Monitoring details</div>',unsafe_allow_html=True)
a,b,c=st.columns(3,gap="small")
with a: st.markdown(f'<div class="mini"><div class="mini-label">NDVI change · 30 days</div><div class="mini-value">{ndvi30:+.1f}%</div></div>' if ndvi30 is not None else '<div class="mini"><div class="mini-label">NDVI change · 30 days</div><div class="mini-value">—</div></div>',unsafe_allow_html=True)
with b: st.markdown(f'<div class="mini"><div class="mini-label">NDMI change · 30 days</div><div class="mini-value">{ndmi30:+.1f}%</div></div>' if ndmi30 is not None else '<div class="mini"><div class="mini-label">NDMI change · 30 days</div><div class="mini-value">—</div></div>',unsafe_allow_html=True)
with c: st.markdown(f'<div class="mini"><div class="mini-label">Latest observation</div><div class="mini-value">{all_dates.max().date().isoformat() if not all_dates.empty else "—"}</div></div>',unsafe_allow_html=True)

with st.expander("🗃️ Observation data · click to expand", expanded=False):
    t1,t2=st.tabs(["NDVI observations","NDMI observations"])
    with t1: st.dataframe(ndvi_p.sort_values("date",ascending=False),use_container_width=True,hide_index=True)
    with t2: st.dataframe(ndmi_p.sort_values("date",ascending=False),use_container_width=True,hide_index=True)

if spatial.get("features"):
    p=spatial["features"][0].get("properties",{})
    st.markdown(f'<div class="footer"><b>ℹ️ Data & quality note:</b> Sentinel-2 SR Harmonized · native analytical scale 10 m · analytical boundary: SERPRO Project Area · year-to-date spatial composite: {int(p.get("analysis_year") or date.today().year)} · effective period {p.get("analysis_start","—")} to {p.get("analysis_end","—")} · mean scene cloud cover {float(p.get("mean_cloud_cover_pct") or 0):.1f}%. The map is rendered from the 100 m web raster; the Spatial Analysis Overview remains a 250 m GeoJSON summary.</div>',unsafe_allow_html=True)
