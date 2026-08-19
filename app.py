import streamlit as st

from utils.scope_engine import get_scope

st.set_page_config(
    page_title="SERPRO Climate & Carbon Monitoring",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Global project frame
# -----------------------------------------------------------------------------
project_area = get_scope("SERPRO Project Area")
project_zone = get_scope("SERPRO Carbon Project Zone")

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


pages = {
    "CLIMATE MONITORING": [
        st.Page(
            "app_pages/historical_climate.py",
            title="Historical Climate",
            icon="📊",
            url_path="historical_climate",
            default=True,
        ),
        st.Page(
            "app_pages/bmkg_local_weather_forecast.py",
            title="BMKG Local Weather Forecast",
            icon="🌦️",
            url_path="bmkg_local_weather_forecast",
        ),
    ],
    "VEGETATION MONITORING": [
        st.Page(
            "app_pages/vegetation_monitoring.py",
            title="Vegetation Monitoring",
            icon="🌿",
            url_path="vegetation_monitoring",
        ),
    ],
    "FIRE MONITORING": [
        st.Page(
            "app_pages/fire_monitoring.py",
            title="Fire Monitoring",
            icon="🔥",
            url_path="fire_monitoring",
        ),
    ],
    "CLIMATE RISK": [
        st.Page(
            "app_pages/climate_risk.py",
            title="Climate Risk",
            icon="⚠️",
            url_path="climate_risk",
        ),
    ],
}

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
