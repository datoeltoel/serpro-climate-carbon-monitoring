import streamlit as st

from utils.auth import has_permission, render_user_sidebar, require_authentication
from utils.scope_engine import get_scope

st.set_page_config(
    page_title="SERPRO Climate & Carbon Monitoring",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Authentication must run before rendering the application navigation.
authenticator, username, name, roles = require_authentication()

# -----------------------------------------------------------------------------
# Global project frame
# -----------------------------------------------------------------------------
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

all_pages = {
    "CLIMATE MONITORING": [
        ("climate_monitoring", st.Page("app_pages/historical_climate.py", title="Historical Climate", icon="📊", url_path="historical_climate", default=True)),
        ("climate_monitoring", st.Page("app_pages/bmkg_local_weather_forecast.py", title="BMKG Local Weather Forecast", icon="🌦️", url_path="bmkg_local_weather_forecast")),
    ],
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

# Build only the navigation entries permitted by the authenticated role.
pages = {}
for section, entries in all_pages.items():
    allowed_entries = [page for key, page in entries if has_permission(key, roles)]
    if allowed_entries:
        pages[section] = allowed_entries

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
