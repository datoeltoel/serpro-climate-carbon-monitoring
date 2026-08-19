import streamlit as st

from utils.auth import require_authentication, require_role
from utils.enterprise_ui import apply_enterprise_css, hero, render_split_map_analysis

st.set_page_config(page_title="SERPRO · MRV Carbon Tracker", page_icon="🌳", layout="wide")
apply_enterprise_css()
require_authentication()
require_role("gis_specialist", "forestry_planner", "mrv_specialist")

hero(
    "🌳 MRV Carbon Tracker",
    "MRV workspace for LULC, AGB, SOC and carbon-pool evidence. Scientific calculation engines remain modular for Phase 4.",
)

left, right = st.columns(2)
with left:
    st.selectbox("Monitoring scope", ["SERPRO Project Area", "SERPRO Carbon Project Zone"], key="mrv_scope")
with right:
    st.selectbox("Assessment period", ["Latest available", "Custom period"], key="mrv_period")

render_split_map_analysis(
    map_title="Carbon spatial inventory",
    map_key="mrv_carbon_map",
)
