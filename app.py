import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path
from streamlit_folium import st_folium
from utils.scope_engine import get_scope, scope_options
from utils.ui import setup_page
from utils.map import render_map
from utils.climate.fire import load_fire
from utils.climate.anomaly import load_anomaly
from utils.climate.vegetation import load_ndmi, load_ndvi
from utils.climate.rainfall import load_rainfall
from utils.climate.risk import load_integrated_risk
setup_page()
project_area_scope=get_scope("SERPRO Project Area"); project_zone_scope=get_scope("SERPRO Carbon Project Zone")
project_area_ha=project_area_scope.area_ha; project_zone_area_ha=project_zone_scope.area_ha
rain=load_rainfall(); fire=load_fire(); ndmi=load_ndmi(); ndvi=load_ndvi(); risk=load_integrated_risk(); anom=load_anomaly()
for df in [rain,fire,ndmi,ndvi,risk,anom]:
    if not df.empty and "date" in df.columns: df["date"]=pd.to_datetime(df["date"],errors="coerce")
st.markdown('<div class="app-header"><div><div class="brand">🌿 SERPRO Climate & Carbon Monitoring <span class="prototype-badge">PROTOTYPE</span></div><div class="subtitle">Seruyan Restoration Ecosystem Project (SERPRO) · PT Kalamanthana Alam Lestari</div></div><div class="top-status"><span>Live monitoring</span><span class="status-pill">● Data connected</span></div></div>',unsafe_allow_html=True)
with st.sidebar:
    st.markdown("### 🌿 PT KALAMANTHANA ALAM LESTARI"); st.markdown("**CLIMATE & CARBON**  \n**MONITORING SYSTEM**"); st.markdown("---"); st.markdown("#### Project Info")
    st.markdown(f"**Carbon Project Zone**  \n{project_zone_area_ha:,.2f} ha"); st.markdown(f"**Project Area**  \n{project_area_ha:,.2f} ha"); st.markdown("**Location**  \nSeruyan, Central Kalimantan"); st.markdown("**Status**  \nPrototype · Live connected"); st.markdown("---"); st.markdown("#### Data Sources"); st.caption("GPM IMERG · CHIRPS · VIIRS S-NPP / NOAA-20 · Sentinel-2 · MODIS")
scope=st.selectbox("Monitoring scope",scope_options(),index=1,format_func=lambda x:{"SERPRO Project Landscape":"🌐 SERPRO Project Landscape","SERPRO Carbon Project Zone":"🟣 Carbon Project Zone","SERPRO Project Area":"🟢 Project Area"}[x]); selected_scope=get_scope(scope); active_scope="carbon_project_zone" if scope=="SERPRO Project Landscape" else selected_scope.key
st.markdown(f'<div style="font-size:.76rem;color:#66756E;margin-bottom:8px;">Active scope: <b>{selected_scope.label}</b> · {selected_scope.area_ha:,.2f} ha</div>',unsafe_allow_html=True)
def scoped(df): return pd.DataFrame() if df.empty or "scope" not in df.columns else df[df["scope"].astype(str)==active_scope].copy()
r=scoped(rain).sort_values("date"); f=scoped(fire).sort_values("date"); n=scoped(ndmi).sort_values("date"); v=scoped(ndvi).sort_values("date"); rk=scoped(risk).sort_values("date")
r7=r.tail(7); rainfall_7d=float(r7["rainfall_mm"].sum()) if not r7.empty else None; rainfall_latest=float(r.iloc[-1]["rainfall_mm"]) if not r.empty else None
f_latest=f["date"].max() if not f.empty else None; f7=f[f["date"]>=f_latest-pd.Timedelta(days=6)] if f_latest is not None else pd.DataFrame(); hotspots_7d=len(f7); hotspots_24=len(f[f["date"]==f_latest]) if f_latest is not None else 0
ndmi_latest=float(n.iloc[-1]["ndmi"]) if not n.empty else None; ndmi_date=n.iloc[-1]["date"] if not n.empty else None; ndvi_latest=float(v.iloc[-1]["ndvi"]) if not v.empty else None; ndvi_date=v.iloc[-1]["date"] if not v.empty else None
n7=n[n["date"]>=n["date"].max()-pd.Timedelta(days=6)] if not n.empty else pd.DataFrame(); v7=v[v["date"]>=v["date"].max()-pd.Timedelta(days=6)] if not v.empty else pd.DataFrame(); ndmi_change=float(n7.iloc[-1]["ndmi"]-n7.iloc[0]["ndmi"]) if len(n7)>=2 else None; ndvi_change=float(v7.iloc[-1]["ndvi"]-v7.iloc[0]["ndvi"]) if len(v7)>=2 else None
rk_latest=rk.iloc[-1] if not rk.empty else None; risk_score=float(rk_latest["integrated_risk_score"]) if rk_latest is not None and pd.notna(rk_latest.get("integrated_risk_score")) else None; risk_level=str(rk_latest.get("risk_level","")).replace("_"," ").upper() if rk_latest is not None else None; risk_date=rk_latest["date"] if rk_latest is not None else None
last_candidates=[d for d in [r.iloc[-1]["date"] if not r.empty else None,f_latest,ndmi_date,ndvi_date,risk_date] if d is not None and pd.notna(d)]; last_update=max(last_candidates) if last_candidates else None
st.markdown(f'<div style="font-size:.76rem;color:#63736B;margin:0 0 8px 2px;">Last update: <b>{last_update.strftime("%d %b %Y") if last_update is not None else "—"}</b></div>',unsafe_allow_html=True)
kpis=[("🌧️","RAINFALL","7 DAYS",f"{rainfall_7d:,.2f} mm" if rainfall_7d is not None else "—",f"Latest {rainfall_latest:,.2f} mm" if rainfall_latest is not None else "No data"),("🔥","FIRE HOTSPOT","7 DAYS",f"{hotspots_7d:,}",f"24H · {hotspots_24:,}"),("🌿","NDVI","LATEST",f"{ndvi_latest:.3f}" if ndvi_latest is not None else "—",f"7D {ndvi_change:+.3f}" if ndvi_change is not None else "No data"),("💧","NDMI","LATEST",f"{ndmi_latest:.3f}" if ndmi_latest is not None else "—",f"7D {ndmi_change:+.3f}" if ndmi_change is not None else "No data"),("🟣","CARBON RISK","INDEX",f"{risk_score:.1f} / 15" if risk_score is not None else "—",risk_level or "No data")]
cols=st.columns(5)
for col,(icon,label,period,value,sub) in zip(cols,kpis):
    with col: st.markdown(f'<div class="kpi-card"><div class="kpi-top"><span class="kpi-icon">{icon}</span><span>{label}<br><small>{period}</small></span></div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>',unsafe_allow_html=True)
map_col,risk_col=st.columns([2.1,0.9])
with map_col:
    st.markdown('<div class="panel-title">🗺️ PROJECT AREA MAP</div><div class="panel-sub">Official boundaries + current VIIRS detections. Demo monitoring points excluded.</div>',unsafe_allow_html=True); st_folium(render_map(f.tail(300),pd.DataFrame(),focus="All Boundaries"),width=None,height=500,returned_objects=[],key="overview_map")
with risk_col:
    if risk_score is not None:
        pct=min(100,max(0,risk_score/15*100)); label=risk_level or "SCREENING"; color="#C62828" if label in ["HIGH","VERY HIGH"] else "#B26A00" if label=="MODERATE" else "#18864B"; st.markdown('<div class="risk-panel"><div class="panel-title">CLIMATE RISK INDEX</div>',unsafe_allow_html=True); st.markdown(f'<div class="risk-score">{risk_score:.1f}</div><div class="risk-label" style="color:{color}">{label}</div><div class="risk-track"><div class="risk-marker" style="left:{max(2,min(98,pct))}%"></div></div><div style="font-size:.72rem;color:#6F7C75;">/ 15 · Assessment {risk_date.strftime("%d %b %Y")}</div>',unsafe_allow_html=True)
        for name,key in [("Rainfall","rainfall_score"),("Drought","drought_score"),("Vegetation stress","vegetation_score"),("Fire activity","fire_score")]:
            val=rk_latest.get(key)
            if pd.notna(val):
                vv=float(val); st.markdown(f'<div class="risk-row"><span>{name}</span><strong>{vv:.1f}</strong></div><div style="height:6px;background:#E9EFEC;border-radius:8px;margin-bottom:7px"><div style="height:6px;width:{min(100,vv/4*100):.0f}%;background:#E89A16;border-radius:8px"></div></div>',unsafe_allow_html=True)
        st.markdown('</div>',unsafe_allow_html=True)
    else: st.info("No integrated risk output.")
tr1,tr2,tr3=st.columns(3)
with tr1:
    st.markdown('<div class="trend-card"><div class="panel-title">RAINFALL TREND</div><div class="panel-sub">Latest 7 connected observations</div>',unsafe_allow_html=True)
    if not r7.empty:
        fig=go.Figure(); fig.add_bar(x=r7.date,y=r7.rainfall_mm,name="Rainfall"); fig.update_layout(height=220,margin=dict(l=10,r=10,t=10,b=10),showlegend=False); st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
    st.markdown('</div>',unsafe_allow_html=True)
with tr2:
    st.markdown('<div class="trend-card"><div class="panel-title">FIRE HOTSPOT TREND</div><div class="panel-sub">VIIRS · latest 7 days · real confidence</div>',unsafe_allow_html=True)
    if not f7.empty:
        ff=f7.copy(); ff["level"]=ff["confidence"].map({0:"Low",1:"Moderate",2:"High"}); tab=ff.pivot_table(index=ff.date.dt.date,columns="level",values="confidence",aggfunc="size",fill_value=0).reset_index(); fig=go.Figure()
        for level in ["High","Moderate","Low"]:
            if level in tab.columns: fig.add_bar(x=tab.date,y=tab[level],name=level)
        fig.update_layout(barmode="stack",height=220,margin=dict(l=10,r=10,t=10,b=10),legend=dict(orientation="h")); st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
    st.markdown('</div>',unsafe_allow_html=True)
with tr3:
    st.markdown('<div class="trend-card"><div class="panel-title">🌿 VEGETATION TREND</div><div class="panel-sub">Sentinel-2 · NDVI vigor vs NDMI moisture</div>',unsafe_allow_html=True)
    if not v.empty or not n.empty:
        fig=go.Figure()
        if not v.empty: fig.add_scatter(x=v.tail(30).date,y=v.tail(30).ndvi,mode="lines+markers",name="NDVI · vigor")
        if not n.empty: fig.add_scatter(x=n.tail(30).date,y=n.tail(30).ndmi,mode="lines+markers",name="NDMI · moisture")
        fig.update_layout(height=220,margin=dict(l=10,r=10,t=10,b=10),legend=dict(orientation="h"),yaxis_title="Index"); st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False}); st.markdown(f'<div class="trend-stat"><div><div class="trend-stat-label">NDVI</div><div class="trend-stat-value">{ndvi_latest:.3f}</div></div><div><div class="trend-stat-label">NDMI</div><div class="trend-stat-value">{ndmi_latest:.3f}</div></div><div><div class="trend-stat-label">7D NDVI</div><div class="trend-stat-value">{ndvi_change:+.3f}</div></div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
alerts=[]
if not f.empty and f_latest is not None:
    hi=f[(f.date==f_latest)&(f.confidence==2)].head(3)
    for _,row in hi.iterrows(): alerts.append(("🔥","High-confidence hotspot",f"{row.latitude:.4f}, {row.longitude:.4f} · {str(row.get('source','VIIRS'))}",f_latest,"HIGH","FIELD ALERT"))
if not anom.empty and "anomaly_30d_pct" in anom.columns:
    a=anom[anom.scope.astype(str)==active_scope].sort_values("date")
    if not a.empty and pd.notna(a.iloc[-1].anomaly_30d_pct) and float(a.iloc[-1].anomaly_30d_pct)<=-30: alerts.append(("🌧","Rainfall anomaly",f"30-day anomaly {float(a.iloc[-1].anomaly_30d_pct):+.1f}%",a.iloc[-1].date,"MODERATE","REVIEW"))
if ndmi_change is not None and ndmi_change<=-0.08: alerts.append(("💧","NDMI moisture decline",f"7-day change {ndmi_change:+.3f}",ndmi_date,"MODERATE","REVIEW"))
if ndvi_change is not None and ndvi_change<=-0.10: alerts.append(("🌿","NDVI vegetation decline",f"7-day change {ndvi_change:+.3f}",ndvi_date,"MODERATE" if ndvi_change>-0.20 else "HIGH","REVIEW" if ndvi_change>-0.20 else "FIELD REVIEW"))
if ndvi_change is not None and ndmi_change is not None and ndvi_change<=-0.10 and ndmi_change<=-0.08: alerts.append(("🌿","Combined vegetation stress",f"NDVI {ndvi_change:+.3f} · NDMI {ndmi_change:+.3f}",ndvi_date,"HIGH","FIELD REVIEW"))
st.markdown('<div class="alert-list"><div class="panel-title">🚨 RECENT ALERTS</div>',unsafe_allow_html=True)
if alerts:
    for icon,title,detail,dt,level,action in alerts[:6]:
        badge='badge-high' if level=='HIGH' else 'badge-moderate' if level=='MODERATE' else 'badge-low'; dts=dt.strftime('%d %b %H:%M') if hasattr(dt,'strftime') else str(dt); st.markdown(f'<div class="alert-item"><div><div class="alert-title">{icon} {title}</div><div class="alert-meta">{detail} · {dts} · → {action}</div></div><span class="alert-badge {badge}">{level}</span></div>',unsafe_allow_html=True)
else: st.success("No active live alerts for the selected scope.")
st.markdown('</div>',unsafe_allow_html=True)
burn_path=Path("data/processed/climate/fire/burned_area_annual_2016_2025.csv")
if burn_path.exists():
    burn=pd.read_csv(burn_path); burn=burn[burn["scope"]==active_scope].copy()
    if not burn.empty:
        peak=burn.loc[burn.burned_area_ha.idxmax()]; latest_burn=burn.sort_values("year").iloc[-1]; st.markdown('<div class="panel" style="margin-top:10px"><div class="panel-title">🔥 BURNED AREA HISTORY · 2016–2025</div><div class="panel-sub">MODIS MCD64A1.061 · annual burned area</div>',unsafe_allow_html=True); fig=go.Figure(); fig.add_bar(x=burn.year,y=burn.burned_area_ha,name="Burned area"); fig.update_layout(height=245,margin=dict(l=10,r=10,t=10,b=10),showlegend=False,yaxis_title="ha"); st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False}); st.markdown(f'<div class="trend-stat"><div><div class="trend-stat-label">LATEST YEAR</div><div class="trend-stat-value">{float(latest_burn.burned_area_ha):,.1f} ha</div></div><div><div class="trend-stat-label">PEAK YEAR</div><div class="trend-stat-value">{int(peak.year)} · {float(peak.burned_area_ha):,.1f} ha</div></div><div><div class="trend-stat-label">SOURCE</div><div class="trend-stat-value">MCD64A1 · 500 m</div></div></div></div>',unsafe_allow_html=True)
st.markdown('<div class="footer-bar"><div class="footer-grid"><div><span>Project</span>SERPRO · Seruyan Restoration Ecosystem Project</div><div><span>Official boundaries</span>Project Area + Carbon Project Zone</div><div><span>Data sources</span>GPM · CHIRPS · VIIRS · Sentinel-2 · MODIS</div><div><span>Prototype</span>Screening interface · not final carbon accounting</div></div></div>',unsafe_allow_html=True)
