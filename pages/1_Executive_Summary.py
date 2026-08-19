import streamlit as st

from utils.auth import require_authentication
from utils.enterprise_ui import apply_enterprise_css, hero, render_split_map_analysis

st.set_page_config(page_title="SERPRO · Executive Summary", page_icon="📊", layout="wide")
apply_enterprise_css()
require_authentication()

hero(
    "📊 Executive Summary",
    "Management-level overview of carbon, climate and operational MRV indicators.",
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Carbon project zone", "150,142.54 ha")
k2.metric("Project area", "31,685.38 ha")
k3.metric("Latest carbon stock", "—")
k4.metric("Climate risk status", "—")

render_split_map_analysis(
    map_title="SERPRO monitoring landscape",
    map_key="executive_summary_map",
)
