from copy import deepcopy
from datetime import date

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
.vm-hero{padding:4px 0 12px}.vm-muted{color:#64748b;font-size:.84rem}
.vm-kpi{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:13px 14px;min-height:108px;box-shadow:0 2px 9px rgba(15,23,42,.05)}
.vm-kpi-label{font-size:.70rem;color:#64748b;font-weight:800;text-transform:uppercase;letter-spacing:.04em}.vm-kpi-value{font-size:1.45rem;font-weight:850;line-height:1.15;margin-top:7px;color:#0f172a}.vm-kpi-sub{font-size:.74rem;margin-top:7px;font-weight:700}
.vm-card{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:16px;box-shadow:0 3px 12px rgba(15,23,42,.05)}.vm-card-title{font-size:1rem;font-weight:850;color:#0f172a;margin-bottom:10px}
.vm-section{font-size:.68rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin:14px 0 7px}.vm-row{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid #eef2f7;font-size:.80rem}.vm-label{color:#64748b}.vm-value{color:#0f172a;font-weight:750;text-align:right}
.vm-badge{border-radius:11px;padding:10px 12px;margin-top:12px;font-weight:850;font-size:.82rem}.vm-high{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}.vm-medium{background:#fef9c3;color:#854d0e;border:1px solid #fde68a}.vm-low{background:#ffedd5;color:#9a3412;border:1px solid #fed7aa}.vm-note{font-size:.75rem;color:#64748b;line-height:1.45}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="vm-hero">', unsafe_allow_html=True)
st.markdown("# 🌿 Vegetation Monitoring")
st.markdown('<div class="vm-muted">SERPRO Project · Sentinel-2 vegetation health, vigor, canopy moisture and spatial stress screening</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

ndmi = load_ndmi(); ndvi = load_ndvi(); spatial = load_vegetation_spatial()
for df in (ndmi, ndvi):
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

if ndmi.empty and ndvi.empty:
    st.info("No NDVI/NDMI data is currently available. Run the vegetation update workflow.")
    st.stop()

scope_keys = sorted(set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str)) | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str)))
if not scope_keys:
    st.error("Vegetation data has no valid monitoring scope."); st.stop()
scope_labels = {"carbon_project_zone":"🟣 Carbon Project Zone · reference", "project_area":"🟢 SERPRO Project Area · analysis"}

c_scope, c_period = st.columns([1.15,1], gap="medium")
with c_scope:
    preferred = "project_area" if "project_area" in scope_keys else scope_keys[0]
    scope = st.selectbox("Monitoring scope", scope_keys, index=scope_keys.index(preferred), format_func=lambda x: scope_labels.get(x, x.replace("_"," ").title()))
ndvi_s = ndvi[ndvi.scope.astype(str)==scope].copy() if not ndvi.empty and "scope" in ndvi.columns else pd.DataFrame()
ndmi_s = ndmi[ndmi.scope.astype(str)==scope].copy() if not ndmi.empty and "scope" in ndmi.columns else pd.DataFrame()
all_dates = pd.concat([x["date"] for x in (ndvi_s,ndmi_s) if not x.empty], ignore_index=True).dropna()
with c_period:
    if not all_dates.empty:
        min_date,max_date=all_dates.min().date(),all_dates.max().date(); date_range=st.date_input("Monitoring period", value=(min_date,max_date), min_value=min_date,max_value=max_date)
    else: date_range=None
if isinstance(date_range,(tuple,list)) and len(date_range)==2:
    start=pd.Timestamp(date_range[0]); end=pd.Timestamp(date_range[1])+pd.Timedelta(days=1)-pd.Timedelta(seconds=1)
    ndvi_p=ndvi_s[(ndvi_s.date>=start)&(ndvi_s.date<=end)].copy(); ndmi_p=ndmi_s[(ndmi_s.date>=start)&(ndmi_s.date<=end)].copy()
else: ndvi_p,ndmi_p=ndvi_s.copy(),ndmi_s.copy()
ndvi_p=ndvi_p.sort_values("date") if not ndvi_p.empty else ndvi_p; ndmi_p=ndmi_p.sort_values("date") if not ndmi_p.empty else ndmi_p

def pct_change(df,col,days=30):
    if df.empty or col not in df.columns or len(df)<2:return None
    latest=df.date.max(); w=df[df.date>=latest-pd.Timedelta(days=days)]
    if len(w)<2:return None
    a,b=float(w.iloc[0][col]),float(w.iloc[-1][col]); return None if a==0 else (b-a)/abs(a)*100

def ndvi_status(v):
    if v is None or pd.isna(v): return "No data","#64748b"
    if v>=.70:return "Good vigor","#15803d"
    if v>=.50:return "Moderate vigor","#b45309"
    if v>=.30:return "Low vigor","#c2410c"
    return "Very low vigor","#b91c1c"

def ndmi_status(v):
    if v is None or pd.isna(v): return "No data","#64748b"
    if v>=.40:return "Moist","#15803d"
    if v>=.20:return "Moderate","#b45309"
    if v>=0:return "Drying","#c2410c"
    return "Low moisture","#b91c1c"

latest_ndvi=float(ndvi_p.iloc[-1].ndvi) if not ndvi_p.empty and "ndvi" in ndvi_p.columns else None
latest_ndmi=float(ndmi_p.iloc[-1].ndmi) if not ndmi_p.empty and "ndmi" in ndmi_p.columns else None
ndvi30=pct_change(ndvi_p,"ndvi"); ndmi30=pct_change(ndmi_p,"ndmi")
ndvi_label,ndvi_color=ndvi_status(latest_ndvi); ndmi_label,ndmi_color=ndmi_status(latest_ndmi)
if ndvi30 is not None and ndmi30 is not None and ndvi30<=-10 and ndmi30<=-10: stress_level="HIGH"
elif (ndvi30 is not None and ndvi30<=-10) or (ndmi30 is not None and ndmi30<=-10): stress_level="MODERATE"
elif (ndvi30 is not None and ndvi30<0) or (ndmi30 is not None and ndmi30<0): stress_level="LOW"
else: stress_level="STABLE"
stress_color={"HIGH":"#b91c1c","MODERATE":"#b45309","LOW":"#2563eb","STABLE":"#15803d"}[stress_level]

st.markdown("### 🌱 Vegetation Condition Overview")
kpis=[("🌿","NDVI",f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—",ndvi_label,ndvi_color),("💧","NDMI",f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—",ndmi_label,ndmi_color),("📉","NDVI · 30D",f"{ndvi30:+.1f}%" if ndvi30 is not None else "—","vs. 30 days","#b91c1c" if ndvi30 is not None and ndvi30<0 else "#15803d"),("💦","NDMI · 30D",f"{ndmi30:+.1f}%" if ndmi30 is not None else "—","vs. 30 days","#b91c1c" if ndmi30 is not None and ndmi30<0 else "#15803d"),("⚠️","VEGETATION STRESS",stress_level,"NDVI + NDMI screening",stress_color)]
cols=st.columns(5,gap="small")
for col,(icon,title,value,sub,color) in zip(cols,kpis):
    with col: st.markdown(f'<div class="vm-kpi"><div class="vm-kpi-label">{icon} {title}</div><div class="vm-kpi-value">{value}</div><div class="vm-kpi-sub" style="color:{color}">{sub}</div></div>',unsafe_allow_html=True)
if stress_level=="HIGH":st.error("🚨 High vegetation stress: both NDVI and NDMI declined by at least 10% over the last 30 days. Prioritize field verification.")
elif stress_level=="MODERATE":st.warning("⚠️ Moderate vegetation stress: at least one indicator declined by 10% or more over the last 30 days. Review spatial context.")
elif stress_level=="LOW":st.info("ℹ️ Low vegetation stress signal: a recent decline is present, but the moderate threshold has not been reached.")
else:st.success("✅ No vegetation stress signal detected under the current screening rules.")


def bounds_from_geojson(collection):
    points=[]
    for feature in collection.get("features",[]):
        geom=feature.get("geometry") or {}; coords=geom.get("coordinates",[])
        rings=coords if geom.get("type")=="Polygon" else [ring for polygon in coords for ring in polygon] if geom.get("type")=="MultiPolygon" else []
        for ring in rings: points.extend(ring)
    if not points:return None
    return [[min(p[1] for p in points),min(p[0] for p in points)],[max(p[1] for p in points),max(p[0] for p in points)]]


def build_vegetation_map():
    m=folium.Map(location=[-3.10,112.62],zoom_start=9,tiles=None,control_scale=True)
    folium.TileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",attr="© OpenStreetMap contributors",name="🗺️ OpenStreetMap",overlay=False,show=True).add_to(m)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",attr="Tiles © Esri",name="🛰️ ESRI Satellite Imagery",overlay=False,show=False).add_to(m)
    project_area=load_project_area(); zone=load_carbon_project_zone()
    if project_area.get("features"): folium.GeoJson(project_area,name="🟢 SERPRO Project Area · AOI",style_function=lambda _: {"color":"#16a34a","weight":3,"fillOpacity":0}).add_to(m)
    if zone.get("features"): folium.GeoJson(zone,name="🟣 Carbon Project Zone · reference",style_function=lambda _: {"color":"#7c3aed","weight":2,"fillOpacity":0}).add_to(m)

    def add_spatial_layer(field,label,title,show):
        data=deepcopy(spatial)
        for feature in data.get("features",[]):
            p=feature.setdefault("properties",{}); p.setdefault("stress","STABLE"); p["display_value"]=p.get(field)
        def style(feature):
            p=feature.get("properties",{}); value=p.get(field)
            if field=="stress": color={"HIGH":"#dc2626","MODERATE":"#f59e0b","LOW":"#eab308","STABLE":"#16a34a"}.get(value,"#94a3b8")
            else:
                try:
                    x=float(value); color=("#b91c1c" if x<.3 else "#f59e0b" if x<.5 else "#84cc16" if x<.7 else "#15803d") if field=="ndvi" else ("#b91c1c" if x<0 else "#f59e0b" if x<.2 else "#84cc16" if x<.4 else "#15803d")
                except (TypeError,ValueError): color="#94a3b8"
            return {"fillColor":color,"color":color,"weight":.35,"fillOpacity":.72}
        folium.GeoJson(data,name=label,style_function=style,show=show,tooltip=folium.GeoJsonTooltip(fields=["display_value","stress","analysis_year","scene_count","mean_cloud_cover_pct"],aliases=[title,"Stress","Year","Scenes","Mean cloud cover (%)"],localize=True,sticky=False)).add_to(m)

    add_spatial_layer("ndvi","🌿 NDVI · annual YTD vigor","NDVI",True)
    add_spatial_layer("ndmi","💧 NDMI · annual YTD moisture","NDMI",False)
    add_spatial_layer("stress","⚠️ Vegetation stress · annual YTD","Stress",False)
    b=bounds_from_geojson(project_area)
    if b:m.fit_bounds(b,padding=(12,12))
    folium.LayerControl(collapsed=False).add_to(m)
    return m


def quality_chart(props):
    observed=float(props.get("observed_pct") or 0); temporal=float(props.get("temporal_fallback_pct") or 0); spatial_fill=float(props.get("spatial_interpolation_pct") or 0); total=float(props.get("total_coverage_pct") or observed+temporal+spatial_fill)
    fig=go.Figure()
    for value,name,text in [(observed,"Observed",f"Observed {observed:.1f}%"),(temporal,"Temporal fallback",f"Temporal {temporal:.1f}%"),(spatial_fill,"Spatial interpolation",f"Spatial {spatial_fill:.1f}%")]:
        fig.add_bar(x=[value],y=["Project Area coverage"],name=name,orientation="h",text=[text],textposition="inside")
    fig.update_layout(barmode="stack",height=95,margin=dict(l=5,r=5,t=5,b=5),xaxis=dict(range=[0,100],title="Coverage (%)"),yaxis=dict(showticklabels=False),legend=dict(orientation="h",y=-.45),showlegend=True)
    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
    st.markdown(f"**Total coverage: {total:.1f}%**")

st.markdown("### 🗺️ Spatial Vegetation Condition")
if spatial.get("features"):
    props=spatial["features"][0].get("properties",{}); map_col,info_col=st.columns([2.15,1],gap="medium")
    with map_col:
        try: st_folium(build_vegetation_map(),width=900,height=540,returned_objects=[],key="vegetation_spatial_map")
        except Exception as exc: st.error("Spatial map could not be rendered, but the monitoring dashboard remains available."); st.caption(f"Map rendering detail: {type(exc).__name__}")
    with info_col:
        st.markdown('<div class="vm-card"><div class="vm-card-title">📊 Spatial Analysis Overview</div>',unsafe_allow_html=True)
        year=int(props.get("analysis_year") or date.today().year); start_text=props.get("analysis_start") or f"{year}-01-01"; end_text=props.get("analysis_end") or "—"; scenes=int(props.get("scene_count") or 0); cloud=float(props.get("mean_cloud_cover_pct") or 0); grid=int(props.get("display_grid_m") or 100)
        rows=[("Analysis period",f"{start_text} → {end_text}"),("Composite",f"{year} year-to-date median"),("Spatial resolution","10 × 10 m analysis"),("Web display grid",f"{grid} m"),("Analysis boundary","SERPRO Project Area · AOI"),("Reference boundary","Carbon Project Zone"),("Sentinel-2 scenes",f"{scenes:,}"),("Mean cloud cover",f"{cloud:.1f}%"),("Method","Annual YTD + spatial gap fill")]
        for label,value in rows: st.markdown(f'<div class="vm-row"><span class="vm-label">{label}</span><span class="vm-value">{value}</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="vm-section">Data Quality</div>',unsafe_allow_html=True); quality_chart(props)
        observed=float(props.get("observed_pct") or 0); badge=("🟢 HIGH CONFIDENCE","vm-high") if observed>=85 else ("🟡 MODERATE CONFIDENCE","vm-medium") if observed>=60 else ("🟠 LOW CONFIDENCE","vm-low")
        st.markdown(f'<div class="vm-badge {badge[1]}">{badge[0]}</div>',unsafe_allow_html=True)
        st.markdown('<div class="vm-note">Confidence reflects the share of Project Area directly observed by Sentinel-2. Any spatial interpolation is reported separately and is not treated as direct observation.</div></div>',unsafe_allow_html=True)
else: st.warning("Spatial vegetation layer is not available yet. Run the Update SERPRO Spatial Vegetation workflow.")

st.markdown("### 📈 Recent Vegetation Trend")
trend_col,interpretation_col=st.columns([1.6,1],gap="medium")
with trend_col:
    fig=go.Figure()
    if not ndvi_p.empty:fig.add_scatter(x=ndvi_p.tail(30).date,y=ndvi_p.tail(30).ndvi,mode="lines+markers",name="NDVI · vigor")
    if not ndmi_p.empty:fig.add_scatter(x=ndmi_p.tail(30).date,y=ndmi_p.tail(30).ndmi,mode="lines+markers",name="NDMI · moisture")
    fig.update_layout(height=330,margin=dict(l=10,r=10,t=10,b=10),yaxis_title="Index",legend=dict(orientation="h")); st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
with interpretation_col:
    st.markdown("### 🧭 Current Interpretation"); st.metric("Vegetation vigor",ndvi_label,f"NDVI {latest_ndvi:.3f}" if latest_ndvi is not None else None); st.metric("Canopy moisture",ndmi_label,f"NDMI {latest_ndmi:.3f}" if latest_ndmi is not None else None); st.metric("Combined stress",stress_level); st.caption("Combined stress is a conservative screening indicator and is not standalone evidence of degradation or carbon loss.")

st.markdown("### 🚨 Stress Condition")
sa1,sa2,sa3=st.columns(3)
with sa1:st.metric("NDVI 30D",f"{ndvi30:+.1f}%" if ndvi30 is not None else "—")
with sa2:st.metric("NDMI 30D",f"{ndmi30:+.1f}%" if ndmi30 is not None else "—")
with sa3:st.metric("Screening status",stress_level)

st.markdown("### 🗃️ Observation Data")
obs1,obs2=st.tabs(["NDVI observations","NDMI observations"])
with obs1:st.dataframe(ndvi_p.sort_values("date",ascending=False),use_container_width=True,hide_index=True)
with obs2:st.dataframe(ndmi_p.sort_values("date",ascending=False),use_container_width=True,hide_index=True)

if spatial.get("features"):
    st.markdown("### ℹ️ Data & Quality Notes")
    p=spatial["features"][0].get("properties",{})
    st.info(f"Sentinel-2 SR Harmonized · native analysis scale 10 m · analytical boundary: SERPRO Project Area · year-to-date spatial composite: {int(p.get('analysis_year') or date.today().year)} · effective period {p.get('analysis_start','—')} to {p.get('analysis_end','—')} · mean scene cloud cover {float(p.get('mean_cloud_cover_pct') or 0):.1f}%. The map provides three switchable spatial layers (NDVI, NDMI and vegetation stress) over OpenStreetMap or ESRI Satellite Imagery. Direct observations and spatial interpolation are reported separately in the Data Quality summary.")
