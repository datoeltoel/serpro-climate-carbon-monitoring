import streamlit as st

from utils.auth import has_permission, render_user_sidebar, require_authentication
from utils.scope_engine import get_scope

st.set_page_config(
    page_title="SERPRO Climate & Carbon Monitoring",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

authenticator, username, name, roles = require_authentication()

project_area = get_scope("SERPRO Project Area")
project_zone = get_scope("SERPRO Carbon Project Zone")

render_user_sidebar(authenticator, name, roles)

with st.sidebar:
    st.markdown("### 🌿 PT KALAMANTHANA ALAM LESTARI")
    st.markdown("**CLIMATE & CARBON**  \n**MONITORING SYSTEM**")
    st.markdown("---")
    st.markdown("#### Project Info")
    st.markdown(f"**Carbon Project Zone**  \n{project_zone.area_ha:,.2f} ha")
    st.markdown(f"**Project Area**  \n{project_area.area_ha:,.2f} ha")
    st.markdown("**Location**  \nSeruyan, Central Kalimantan")
    st.markdown("**Status**  \nLive connected")
    st.markdown("---")
    st.markdown("#### Data Sources")
    st.caption("GPM IMERG · CHIRPS · VIIRS S-NPP / NOAA-20 · Sentinel-2 · MODIS · BMKG Open Data")

# F1-01: one deterministic navigation registry. Existing analytical modules
# remain registered and are not deleted/recalculated during this refactor.
enterprise_pages = {
    "EXECUTIVE SUMMARY": [
        ("executive_summary", st.Page("pages/1_Executive_Summary.py", title="Executive Summary", icon="📊", url_path="executive_summary", default=True)),
    ],
    "MRV CARBON TRACKER": [
        ("mrv_carbon_tracker", st.Page("pages/2_MRV_Carbon_Tracker.py", title="MRV Carbon Tracker", icon="🌳", url_path="mrv_carbon_tracker")),
    ],
    "CLIMATE MONITORING": [
        ("climate_monitoring", st.Page("pages/3_Climate_Monitoring.py", title="Climate Monitoring", icon="🌦️", url_path="climate_monitoring")),
        ("climate_monitoring", st.Page("app_pages/historical_climate.py", title="Historical Climate", icon="📊", url_path="historical_climate")),
        ("climate_monitoring", st.Page("app_pages/bmkg_local_weather_forecast.py", title="BMKG Local Weather Forecast", icon="🌦️", url_path="bmkg_local_weather_forecast")),
    ],
    "SPATIAL DATA CATALOG": [
        ("spatial_data_catalog", st.Page("pages/4_Spatial_Data_Catalog.py", title="Spatial Data Catalog", icon="🗺️", url_path="spatial_data_catalog")),
    ],
}

operational_pages = {
    "VEGETATION MONITORING": [
        ("vegetation_monitoring", st.Page("app_pages/vegetation_monitoring.py", title="Vegetation Monitoring", icon="🌿", url_path="vegetation_monitoring")),
    ],
    "FIRE MONITORING": [
        ("fire_monitoring", st.Page("app_pages/fire_monitoring.py", title="Fire Monitoring", icon="🔥", url_path="fire_monitoring")),
    ],
    "CLIMATE RISK": [
        ("climate_risk", st.Page("app_pages/climate_risk.py", title="Climate Risk", icon="⚠️", url_path="climate_risk")),
    ],
}

# Reuse existing RBAC permission keys. F1-01 does not alter authentication or
# the permission matrix; enterprise pages inherit the relevant domain access.
enterprise_allowed = {
    "executive_summary": bool(roles),
    "mrv_carbon_tracker": has_permission("vegetation_monitoring", roles),
    "climate_monitoring": has_permission("climate_monitoring", roles),
    "spatial_data_catalog": has_permission("vegetation_monitoring", roles),
}

navigation = {}
for section, entries in enterprise_pages.items():
    allowed = [page for key, page in entries if enterprise_allowed[key]]
    if allowed:
        navigation[section] = allowed

for section, entries in operational_pages.items():
    allowed = [page for key, page in entries if has_permission(key, roles)]
    if allowed:
        navigation[section] = allowed

# Single source of truth: exactly one Streamlit navigation call.
pg = st.navigation(navigation, position="sidebar", expanded=True)
pg.run()
