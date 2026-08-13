import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from utils.ui import setup_page
from utils.scope_engine import get_scope, scope_options
from utils.climate.vegetation import load_ndvi, load_ndvi_annual, load_ndmi

setup_page()
st.markdown("# 🌿 Vegetation Monitoring")
st.caption("Sentinel-2 SR Harmonized · NDVI vegetation vigor and NDMI vegetation moisture")

scope = st.selectbox("Monitoring scope", scope_options(), index=1, format_func=lambda x: {"SERPRO Project Landscape":"🌐 SERPRO Project Landscape", "SERPRO Carbon Project Zone":"🟣 Carbon Project Zone", "SERPRO Project Area":"🟢 Project Area"}[x])
selected = get_scope(scope)
active_scope = "carbon_project_zone" if scope == "SERPRO Project Landscape" else selected.key

ndvi = load_ndvi(); annual = load_ndvi_annual(); ndmi = load_ndmi()
ndvi = ndvi[ndvi["scope"] == active_scope].copy() if not ndvi.empty else ndvi
annual = annual[annual["scope"] == active_scope].copy() if not annual.empty else annual
ndmi = ndmi[ndmi["scope"] == active_scope].copy() if not ndmi.empty else ndmi

if not annual.empty:
    annual["year"] = annual["year"].astype(int)
    annual = annual.sort_values("year")

st.markdown("## 📈 Annual NDVI Trend · 2015–2025")
st.caption("Annual mean of valid Sentinel-2 scene-level zonal means. 2015 is a partial Sentinel-2 observation year.")
if annual.empty:
    st.warning("Annual NDVI dataset is not available yet. Run **Update SERPRO NDVI** from GitHub Actions.")
else:
    fig = go.Figure()
    fig.add_scatter(x=annual["year"], y=annual["ndvi_mean"], mode="lines+markers", name="NDVI")
    fig.add_hline(y=0, line_dash="dot")
    fig.update_layout(height=380, margin=dict(l=20,r=20,t=20,b=20), xaxis=dict(dtick=1), yaxis_title="NDVI", xaxis_title="Year", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    latest = annual.iloc[-1]
    first = annual.iloc[0]
    change = float(latest["ndvi_mean"] - first["ndvi_mean"])
    c1,c2,c3 = st.columns(3)
    c1.metric("Latest annual NDVI", f"{latest['ndvi_mean']:.3f}", f"{int(latest['year'])}")
    c2.metric("Change vs first year", f"{change:+.3f}")
    c3.metric("Annual observations", f"{int(annual['observation_count'].sum()):,}")

    st.markdown("### Annual records")
    display = annual[["year","ndvi_mean","observation_count","note"]].copy()
    display.columns = ["Year","NDVI Mean","Observations","Coverage"]
    st.dataframe(display, use_container_width=True, hide_index=True)

st.markdown("## 🌿 NDVI vs NDMI")
if not ndvi.empty or not ndmi.empty:
    fig = go.Figure()
    if not ndvi.empty:
        d = ndvi.tail(60)
        fig.add_scatter(x=d["date"], y=d["ndvi"], mode="lines+markers", name="NDVI · vigor")
    if not ndmi.empty:
        d = ndmi.tail(60)
        fig.add_scatter(x=d["date"], y=d["ndmi"], mode="lines+markers", name="NDMI · moisture")
    fig.update_layout(height=330, margin=dict(l=20,r=20,t=20,b=20), yaxis_title="Index", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
else:
    st.info("No recent vegetation observations available for the selected scope.")

st.info("NDVI is interpreted as vegetation vigor/greenness; NDMI as vegetation moisture. The annual NDVI series is a monitoring indicator and is not used directly in the integrated Climate Risk score yet.")
