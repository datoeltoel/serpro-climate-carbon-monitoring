import json
from copy import deepcopy

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from utils.climate.vegetation import (
    load_ndmi,
    load_ndvi,
    load_ndvi_annual,
    load_vegetation_spatial,
)
from utils.map import load_carbon_project_zone, load_project_area
from utils.ui import setup_page

setup_page()

st.markdown(
    """
    <style>
    .veg-kpi{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:14px 15px;min-height:112px;box-shadow:0 2px 8px rgba(15,23,42,.05)}
    .veg-kpi-label{font-size:.72rem;color:#64748b;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
    .veg-kpi-value{font-size:1.55rem;font-weight:800;line-height:1.15;margin-top:7px;color:#0f172a;word-break:break-word}
    .veg-kpi-sub{font-size:.76rem;margin-top:7px;font-weight:700}
    .map-card{border:1px solid #e5e7eb;border-radius:16px;padding:4px;background:#fff}
    @media(max-width:768px){.veg-kpi{min-height:100px;padding:11px}.veg-kpi-value{font-size:1.28rem}.veg-kpi-label{font-size:.66rem}.veg-kpi-sub{font-size:.70rem}}
    </style>
    """, unsafe_allow_html=True,
)

st.markdown("# 🌿 Vegetation Monitoring")
st.caption("SERPRO Project · Sentinel-2 vegetation health, vigor, canopy moisture and spatial stress screening")

ndmi = load_ndmi()
ndvi = load_ndvi()
annual = load_ndvi_annual()
spatial = load_vegetation_spatial()

for df in (ndmi, ndvi):
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

if ndmi.empty and ndvi.empty:
    st.info("No NDVI/NDMI data is currently available. Run the Update SERPRO NDVI and Update SERPRO NDMI workflows.")
    st.stop()

scope_keys = sorted(set(ndmi.get("scope", pd.Series(dtype=str)).dropna().astype(str)) | set(ndvi.get("scope", pd.Series(dtype=str)).dropna().astype(str)))
scope_labels = {"carbon_project_zone":"🟣 Carbon Project Zone","project_area":"🟢 Project Area"}

c_scope, c_period = st.columns([1.15,1], gap="medium")
with c_scope:
    scope = st.selectbox("Monitoring scope", scope_keys, format_func=lambda x: scope_labels.get(x, x.replace("_"," ").title()))
ndvi_s = ndvi[ndvi["scope"].astype(str)==scope].copy() if not ndvi.empty else pd.DataFrame()
ndmi_s = ndmi[ndmi["scope"].astype(str)==scope].copy() if not ndmi.empty else pd.DataFrame()
all_dates = pd.concat([x["date"] for x in (ndvi_s,ndmi_s) if not x.empty], ignore_index=True).dropna()
with c_period:
    if not all_dates.empty:
        min_date,max_date=all_dates.min().date(),all_dates.max().date()
        date_range=st.date_input("Monitoring period",value=(min_date,max_date),min_value=min_date,max_value=max_date)
    else: date_range=None
if isinstance(date_range,(tuple,list)) and len(date_range)==2:
    start=pd.Timestamp(date_range[0]); end=pd.Timestamp(date_range[1])+pd.Timedelta(days=1)-pd.Timedelta(seconds=1)
    ndvi_p=ndvi_s[(ndvi_s.date>=start)&(ndvi_s.date<=end)].copy(); ndmi_p=ndmi_s[(ndmi_s.date>=start)&(ndmi_s.date<=end)].copy()
else: ndvi_p,ndmi_p=ndvi_s.copy(),ndmi_s.copy()
ndvi_p=ndvi_p.sort_values("date") if not ndvi_p.empty else ndvi_p
ndmi_p=ndmi_p.sort_values("date") if not ndmi_p.empty else ndmi_p


def pct_change(df,col,days):
    if df.empty or col not in df.columns or len(df)<2:return None
    latest=df.date.max(); w=df[df.date>=latest-pd.Timedelta(days=days)]
    if len(w)<2:return None
    first,last=float(w.iloc[0][col]),float(w.iloc[-1][col])
    return None if first==0 else (last-first)/abs(first)*100


def ndvi_status(v):
    if v is None or pd.isna(v):return "No data","#64748b"
    if float(v)>=.70:return "Good vigor","#15803d"
    if float(v)>=.50:return "Moderate vigor","#b45309"
    if float(v)>=.30:return "Low vigor","#c2410c"
    return "Very low vigor","#b91c1c"


def ndmi_status(v):
    if v is None or pd.isna(v):return "No data","#64748b"
    if float(v)>=.40:return "Moist","#15803d"
    if float(v)>=.20:return "Moderate","#b45309"
    if float(v)>=0:return "Drying","#c2410c"
    return "Low moisture","#b91c1c"

latest_ndvi=float(ndvi_p.iloc[-1].ndvi) if not ndvi_p.empty else None
latest_ndmi=float(ndmi_p.iloc[-1].ndmi) if not ndmi_p.empty else None
ndvi30=pct_change(ndvi_p,"ndvi",30); ndmi30=pct_change(ndmi_p,"ndmi",30)
ndvi90=pct_change(ndvi_p,"ndvi",90); ndmi90=pct_change(ndmi_p,"ndmi",90)
ndvi_label,ndvi_color=ndvi_status(latest_ndvi); ndmi_label,ndmi_color=ndmi_status(latest_ndmi)
if ndvi30 is not None and ndmi30 is not None and ndvi30<=-10 and ndmi30<=-10: stress_level="HIGH"
elif (ndvi30 is not None and ndvi30<=-10) or (ndmi30 is not None and ndmi30<=-10): stress_level="MODERATE"
elif (ndvi30 is not None and ndvi30<0) or (ndmi30 is not None and ndmi30<0): stress_level="LOW"
else: stress_level="STABLE"
stress_color={"HIGH":"#b91c1c","MODERATE":"#b45309","LOW":"#2563eb","STABLE":"#15803d"}[stress_level]

st.markdown("### 🌱 Vegetation Condition Overview")
kpis=[
("🌿","NDVI",f"{latest_ndvi:.3f}" if latest_ndvi is not None else "—",ndvi_label,ndvi_color),
("💧","NDMI",f"{latest_ndmi:.3f}" if latest_ndmi is not None else "—",ndmi_label,ndmi_color),
("📉","NDVI · 30D",f"{ndvi30:+.1f}%" if ndvi30 is not None else "—","vs. 30 days","#b91c1c" if ndvi30 is not None and ndvi30<0 else "#15803d"),
("💦","NDMI · 30D",f"{ndmi30:+.1f}%" if ndmi30 is not None else "—","vs. 30 days","#b91c1c" if ndmi30 is not None and ndmi30<0 else "#15803d"),
("⚠️","VEGETATION STRESS",stress_level,"NDVI + NDMI screening",stress_color)]
cols=st.columns(5,gap="small")
for col,(icon,title,value,sub,color) in zip(cols,kpis):
    with col: st.markdown(f'<div class="veg-kpi"><div class="veg-kpi-label">{icon} {title}</div><div class="veg-kpi-value">{value}</div><div class="veg-kpi-sub" style="color:{color}">{sub}</div></div>',unsafe_allow_html=True)
if stress_level=="HIGH":st.error("🚨 High vegetation stress: both NDVI and NDMI declined by at least 10% over the last 30 days. Prioritize field verification.")
elif stress_level=="MODERATE":st.warning("⚠️ Moderate vegetation stress: at least one indicator declined by 10% or more over the last 30 days. Review spatial context.")
elif stress_level=="LOW":st.info("ℹ️ Low vegetation stress signal: a recent decline is present, but the moderate threshold has not been reached.")
else:st.success("✅ No vegetation stress signal detected under the current screening rules.")

# -----------------------------------------------------------------------------
# Spatial vegetation map — actual Sentinel-2 composite, no demo points.
# -----------------------------------------------------------------------------
def spatial_layer(data, field, label, palette, legend_title):
    layer_data=deepcopy(data)
    for f in layer_data.get("features",[]):
        v=f.get("properties",{}).get(field)
        f.setdefault("properties",{})["display_value"] = None if v is None else round(float(v),3) if field != "stress" else v
    def style(feature):
        p=feature.get("properties",{}); v=p.get(field)
        if field=="stress":
            color={"HIGH":"#dc2626","MODERATE":"#f59e0b","LOW":"#eab308","STABLE":"#16a34a"}.get(v,"#94a3b8")
        else:
            try:
                x=float(v)
                if field=="ndvi":
                    color="#b91c1c" if x<.3 else "#f59e0b" if x<.5 else "#84cc16" if x<.7 else "#15803d"
                else:
                    color="#b91c1c" if x<0 else "#f59e0b" if x<.2 else "#84cc16" if x<.4 else "#15803d"
            except (TypeError,ValueError): color="#94a3b8"
        return {"fillColor":color,"color":color,"weight":.6,"fillOpacity":.62}
    folium.GeoJson(layer_data,name=label,style_function=style,tooltip=folium.GeoJsonTooltip(fields=["display_value","stress","period_days","scene_count"],aliases=[legend_title,"Stress","Composite period (days)","Scenes"],localize=True,sticky=False)).add_to(m)


def build_vegetation_map():
    global m
    m=folium.Map(location=[-3.10,112.62],zoom_start=9,tiles=None,control_scale=True)
    folium.TileLayer("CartoDB positron",name="Light map",show=True).add_to(m)
    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",attr="Tiles © Esri",name="Satellite imagery",show=False).add_to(m)
    project_area=load_project_area(); zone=load_carbon_project_zone()
    if project_area.get("features"):
        folium.GeoJson(project_area,name="🟢 SERPRO Project Area",style_function=lambda _: {"color":"#16a34a","weight":3,"fillOpacity":0}).add_to(m)
    if zone.get("features"):
        folium.GeoJson(zone,name="🟣 Carbon Project Zone",style_function=lambda _: {"color":"#7c3aed","weight":2,"fillOpacity":0}).add_to(m)
    spatial_layer(spatial,"ndvi","🌿 NDVI · vegetation vigor",None,"NDVI")
    spatial_layer(spatial,"ndmi","💧 NDMI · canopy moisture",None,"NDMI")
    spatial_layer(spatial,"stress","⚠️ Combined vegetation stress",None,"Status")
    folium.LayerControl(collapsed=False).add_to(m)
    return m

st.markdown("### 🗺️ Spatial Vegetation Condition")
if spatial.get("features"):
    map_col, info_col=st.columns([2.15,1],gap="medium")
    with map_col:
        st_folium(build_vegetation_map(),use_container_width=True,height=520,returned_objects=[])
    with info_col:
        st.markdown("#### Map interpretation")
        st.markdown("**NDVI** — vegetation greenness and relative vigor.")
        st.markdown("**NDMI** — vegetation/canopy moisture condition.")
        st.markdown("**Stress** — conservative combined screening of NDVI + NDMI.")
        st.caption("The spatial layer is derived from actual Sentinel-2 Surface Reflectance Harmonized scenes using a 30-day median composite. Grid size: approximately 2 km. It is a screening product, not standalone evidence of degradation or carbon loss.")
        props=spatial["features"][0].get("properties",{})
        st.metric("Sentinel-2 scenes",props.get("scene_count","—"))
        st.metric("Composite period",f"{props.get('period_days','—')} days")
else:
    st.warning("The spatial vegetation layer is not available yet. Run the **Update SERPRO Spatial Vegetation** GitHub Actions workflow to generate the actual Sentinel-2 spatial layer.")

# -----------------------------------------------------------------------------
# Analysis tabs
# -----------------------------------------------------------------------------
tab_overview,tab_trend,tab_stress,tab_data=st.tabs(["Overview","Trends","Stress Analysis","Data & Quality"])
with tab_overview:
    left,right=st.columns([1.55,1],gap="large")
    with left:
        st.markdown("#### 📈 Recent Vegetation Trend")
        fig=go.Figure()
        if not ndvi_p.empty:fig.add_scatter(x=ndvi_p.date,y=ndvi_p.ndvi,mode="lines+markers",name="NDVI · vegetation vigor")
        if not ndmi_p.empty:fig.add_scatter(x=ndmi_p.date,y=ndmi_p.ndmi,mode="lines+markers",name="NDMI · canopy moisture")
        fig.update_layout(height=360,margin=dict(l=10,r=10,t=15,b=10),yaxis_title="Index",hovermode="x unified",legend=dict(orientation="h"))
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
    with right:
        st.markdown("#### 🧭 Current Interpretation")
        st.markdown(f"**Vegetation vigor** · {ndvi_label}"); st.caption(f"NDVI = {latest_ndvi:.3f}" if latest_ndvi is not None else "NDVI = no data")
        st.markdown(f"**Canopy moisture** · {ndmi_label}"); st.caption(f"NDMI = {latest_ndmi:.3f}" if latest_ndmi is not None else "NDMI = no data")
        st.markdown(f"**Combined stress** · {stress_level}"); st.caption("Conservative screening indicator; not standalone evidence of degradation or damage.")
        st.metric("NDVI · 90-day change",f"{ndvi90:+.1f}%" if ndvi90 is not None else "—")
        st.metric("NDMI · 90-day change",f"{ndmi90:+.1f}%" if ndmi90 is not None else "—")

with tab_trend:
    st.markdown("#### 📅 Annual NDVI Trend · 2015–2025")
    annual_s=annual[annual.scope.astype(str)==scope].copy() if not annual.empty else pd.DataFrame()
    if annual_s.empty: st.info("No annual NDVI records are available for this scope.")
    else:
        annual_s["year"]=pd.to_numeric(annual_s.year,errors="coerce"); annual_s["ndvi_mean"]=pd.to_numeric(annual_s.ndvi_mean,errors="coerce")
        annual_s=annual_s.dropna(subset=["year","ndvi_mean"]).sort_values("year"); annual_s=annual_s[(annual_s.year>=2015)&(annual_s.year<=2025)]
        fig=go.Figure(); fig.add_scatter(x=annual_s.year,y=annual_s.ndvi_mean,mode="lines+markers",name="Annual NDVI")
        fig.update_layout(height=370,margin=dict(l=10,r=10,t=15,b=10),xaxis=dict(dtick=1),yaxis_title="Mean NDVI",xaxis_title="Year",hovermode="x unified")
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.caption("Annual NDVI supports long-term vegetation monitoring. 2015 is a partial Sentinel-2 observation year. This is not a carbon-accounting output.")
        a,b,c=st.columns(3); latest_a,first_a=annual_s.iloc[-1],annual_s.iloc[0]
        a.metric("Latest annual NDVI",f"{float(latest_a.ndvi_mean):.3f}",str(int(latest_a.year)))
        b.metric("Change vs. first year",f"{float(latest_a.ndvi_mean-first_a.ndvi_mean):+.3f}")
        obs=pd.to_numeric(annual_s.get("observation_count",pd.Series(dtype=float)),errors="coerce").fillna(0).sum(); c.metric("Annual observations",f"{int(obs):,}")

    st.markdown("#### 📆 Monthly Vegetation Trend")
    frames=[]
    if not ndvi_s.empty:
        x=ndvi_s.copy(); x["month"]=x.date.dt.to_period("M").dt.to_timestamp(); frames.append(x.groupby("month",as_index=False).ndvi.mean().rename(columns={"ndvi":"NDVI"}))
    if not ndmi_s.empty:
        x=ndmi_s.copy(); x["month"]=x.date.dt.to_period("M").dt.to_timestamp(); frames.append(x.groupby("month",as_index=False).ndmi.mean().rename(columns={"ndmi":"NDMI"}))
    if frames:
        mm=frames[0]
        if len(frames)>1:mm=pd.merge(mm,frames[1],on="month",how="outer")
        fig=go.Figure()
        if "NDVI" in mm:fig.add_scatter(x=mm.month,y=mm.NDVI,mode="lines+markers",name="NDVI")
        if "NDMI" in mm:fig.add_scatter(x=mm.month,y=mm.NDMI,mode="lines+markers",name="NDMI")
        fig.update_layout(height=330,margin=dict(l=10,r=10,t=15,b=10),yaxis_title="Index",hovermode="x unified")
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.caption("Monthly values use available scene-level zonal observations. Missing months are not interpolated.")

with tab_stress:
    st.markdown("#### 🚨 Vegetation Stress Screening")
    st.caption("Screening rule: ≥10% decline in one index over 30 days = Moderate; ≥10% decline in both NDVI and NDMI = High.")
    if not ndvi_p.empty or not ndmi_p.empty:
        stress=pd.merge(ndvi_p[["date","ndvi"]] if not ndvi_p.empty else pd.DataFrame(columns=["date","ndvi"]),ndmi_p[["date","ndmi"]] if not ndmi_p.empty else pd.DataFrame(columns=["date","ndmi"]),on="date",how="outer").sort_values("date")
        stress["ndvi_change_pct"]=stress.ndvi.pct_change()*100; stress["ndmi_change_pct"]=stress.ndmi.pct_change()*100; stress["stress"]="Stable"
        stress.loc[(stress.ndvi_change_pct<=-10)|(stress.ndmi_change_pct<=-10),"stress"]="Moderate"; stress.loc[(stress.ndvi_change_pct<=-10)&(stress.ndmi_change_pct<=-10),"stress"]="High"
        fig=go.Figure()
        for level in ["High","Moderate","Stable"]:
            d=stress[stress.stress==level]
            if not d.empty:fig.add_scatter(x=d.date,y=d.ndvi,mode="markers",name=level)
        fig.update_layout(height=320,margin=dict(l=10,r=10,t=15,b=10),yaxis_title="NDVI",hovermode="x unified")
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.markdown("#### Recommended Follow-up")
        if stress_level=="HIGH":st.error("FIELD REVIEW · Check fire/hotspot activity, land-cover change, hydrological conditions and field observations.")
        elif stress_level=="MODERATE":st.warning("REVIEW · Check recent trend, seasonality, cloud quality, land-cover context and nearby fire/hydrological signals.")
        elif stress_level=="LOW":st.info("MONITOR · Continue observation and compare the next valid scenes before escalating field priority.")
        else:st.success("NO ACTION · Continue routine monitoring.")

with tab_data:
    st.markdown("#### 📋 Observation Data")
    if not ndvi_p.empty:
        st.markdown("**NDVI observations**"); st.dataframe(ndvi_p[[c for c in ["date","ndvi","cloudy_pixel_percentage","source"] if c in ndvi_p.columns]].sort_values("date",ascending=False),use_container_width=True,hide_index=True)
    if not ndmi_p.empty:
        st.markdown("**NDMI observations**"); st.dataframe(ndmi_p[[c for c in ["date","ndmi","cloudy_pixel_percentage","source"] if c in ndmi_p.columns]].sort_values("date",ascending=False),use_container_width=True,hide_index=True)
    st.markdown("#### ℹ️ Interpretation Guide")
    st.markdown("- **NDVI (Normalized Difference Vegetation Index):** vegetation greenness and relative vigor.\n- **NDMI (Normalized Difference Moisture Index):** vegetation/canopy moisture conditions.\n- **Combined stress:** conservative screening using both indicators; not standalone evidence of degradation.\n- Interpret vegetation signals together with rainfall, fire activity, hydrology, land-cover change, cloud quality and field observations.")
    st.caption("Data source: Copernicus Sentinel-2 Surface Reflectance Harmonized. NDVI = (B8 − B4) / (B8 + B4); NDMI = (B8 − B11) / (B8 + B11).")
