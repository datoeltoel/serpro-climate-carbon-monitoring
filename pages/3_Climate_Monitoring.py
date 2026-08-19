import streamlit as st

from utils.auth import require_authentication
from utils.enterprise_ui import apply_enterprise_css, hero, render_split_map_analysis

st.set_page_config(page_title="SERPRO · Climate Monitoring", page_icon="🌦️", layout="wide")
apply_enterprise_css()
require_authentication()

hero(
    "🌦️ Climate Monitoring",
    "Integrated climate evidence workspace for CHIRPS rainfall, LST and hotspot/deforestation indicators.",
)

c1, c2, c3 = st.columns(3)
with c1:
    st.selectbox("Monitoring scope", ["SERPRO Project Area", "SERPRO Carbon Project Zone"], key="climate_scope")
with c2:
    st.selectbox("Period", ["Latest 30D", "Latest 90D", "Latest 1Y", "Latest 30Y"], key="climate_period")
with c3:
    st.selectbox("Primary variable", ["Rainfall · CHIRPS", "Land Surface Temperature · LST", "Hotspot / deforestation"], key="climate_variable")

render_split_map_analysis(
    map_title="Climate spatial evidence",
    map_key="climate_monitoring_map",
)

st.caption("BMKG Local Weather Forecast remains an operational forecast product and is maintained separately from historical climate-risk calculations.")
