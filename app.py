"""SERPRO Climate & Carbon Monitoring enterprise entrypoint."""
from __future__ import annotations

import streamlit as st

from utils.auth import has_permission, require_authentication, render_user_sidebar

st.set_page_config(
    page_title="SERPRO Climate & Carbon Monitoring",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)


authenticator, username, name, roles = require_authentication()

with st.sidebar:
    st.markdown("## 🌿 SERPRO")
    st.caption("Climate & Carbon Monitoring · MRV")
    st.markdown("---")
    st.markdown("**PT KALAMANthana ALAM LESTARI**")
    st.caption("Seruyan Restoration Ecosystem Project")
    st.markdown("**Carbon Project Zone**  \n150,142.54 ha")
    st.markdown("**Project Area**  \n31,685.38 ha")
    st.markdown("---")

render_user_sidebar(authenticator, name, roles)

pages_by_key = {
    "executive_summary": st.Page(
        "pages/1_Executive_Summary.py",
        title="Executive Summary",
        icon="📊",
        url_path="executive-summary",
        default=True,
    ),
    "mrv_carbon_tracker": st.Page(
        "pages/2_MRV_Carbon_Tracker.py",
        title="MRV Carbon Tracker",
        icon="🌳",
        url_path="mrv-carbon-tracker",
    ),
    "climate_monitoring": st.Page(
        "pages/3_Climate_Monitoring.py",
        title="Climate Monitoring",
        icon="🌦️",
        url_path="climate-monitoring",
    ),
    "spatial_data_catalog": st.Page(
        "pages/4_Spatial_Data_Catalog.py",
        title="Spatial Data Catalog",
        icon="🗺️",
        url_path="spatial-data-catalog",
    ),
}

# Keep the existing BMKG operational forecast available during the transition.
# It is intentionally hidden from the main enterprise navigation and will be
# embedded/linked from Climate Monitoring in the next UI phase.
bmkg_page = st.Page(
    "app_pages/bmkg_local_weather_forecast.py",
    title="BMKG Local Weather Forecast",
    icon="🌦️",
    url_path="bmkg-local-weather-forecast",
    visibility="hidden",
)

navigation = {
    "MRV CARBON MONITORING": [
        page for key, page in pages_by_key.items() if has_permission(key, roles)
    ],
    "OPERATIONAL FORECAST": [bmkg_page],
}

pg = st.navigation(navigation, position="sidebar", expanded=True)
pg.run()
