import streamlit as st
from streamlit_folium import st_folium
from utils.demo_data import load_demo_data
from utils.ui import setup_page
from utils.map import load_carbon_project_zone, load_project_area, render_map

setup_page()
data = load_demo_data()

st.markdown('<div class="brand">🌿 SERPRO Climate & Carbon Monitoring</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Seruyan Restoration Ecosystem Project (SERPRO) · PT Kalamanthana Alam Lestari</div>', unsafe_allow_html=True)
st.markdown('<div class="status">● Demo analytics · Official project boundaries loaded · Last update: 12 Aug 2026 20:00 WIB</div>', unsafe_allow_html=True)

# Official boundary context
project_area = load_project_area()
project_zone = load_carbon_project_zone()
project_area_ha = 31_685.39
project_zone_area_ha = 150_142.54
area_to_zone_pct = project_area_ha / project_zone_area_ha * 100

st.markdown('<div class="section-title">Project Landscape Summary</div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="landscape-summary">
      <div class="landscape-intro">
        <b>Unified SERPRO Project Landscape</b><br>
        SERPRO Project Area and SERPRO Carbon Project Zone are two official spatial boundaries
        describing the same project landscape. They are spatially overlapping components, not separate projects.
      </div>
      <div class="landscape-grid">
        <div class="landscape-card area-card">
          <div class="landscape-icon">🟢</div>
          <div class="landscape-label">SERPRO Project Area</div>
          <div class="landscape-value">31,685.39 ha</div>
          <div class="landscape-meta">PT KAL concession / project area · KAL_Boundary_Split.kml</div>
        </div>
        <div class="landscape-connector">↔<span>SPATIALLY<br>OVERLAPPING</span></div>
        <div class="landscape-card zone-card">
          <div class="landscape-icon">🟣</div>
          <div class="landscape-label">SERPRO Carbon Project Zone</div>
          <div class="landscape-value">150,142.54 ha</div>
          <div class="landscape-meta">Carbon project boundary · ProjectZone.kmz</div>
        </div>
      </div>
      <div class="landscape-note">
        Official project-area values. The 21.10% figure below is an area ratio only; it is not presented as the geometric overlap percentage.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

summary_map_col, summary_info_col = st.columns([2.4, 1])
with summary_map_col:
    st_folium(
        render_map(data["hotspots"], data["monitoring_points"], focus="All Boundaries"),
        width=None,
        height=430,
        returned_objects=[],
        key="project_landscape_summary_map",
    )
with summary_info_col:
    st.markdown(
        f"""
        <div class="risk-card">
          <div><b>LANDSCAPE RELATIONSHIP</b></div>
          <div class="risk-number">{area_to_zone_pct:.2f}%</div>
          <div class="risk-label">PROJECT AREA / CARBON ZONE</div>
          <hr>
          <p><b>🟢 Project Area</b><br>{project_area_ha:,.2f} ha</p>
          <p><b>🟣 Carbon Project Zone</b><br>{project_zone_area_ha:,.2f} ha</p>
          <div style="padding:10px;border-radius:8px;background:rgba(255,255,255,.09);font-size:.82rem;line-height:1.45;">
            Both boundaries are displayed simultaneously to show their spatial relationship.
            The ratio is an area comparison, not an overlap calculation.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-title">Monitoring Scope</div>', unsafe_allow_html=True)
scope = st.radio(
    "Select analysis scope",
    ["All Boundaries", "SERPRO Project Area", "Carbon Project Zone"],
    horizontal=True,
    label_visibility="collapsed",
)

scope_label = {
    "All Boundaries": "Unified SERPRO project landscape",
    "SERPRO Project Area": "SERPRO concession / project area",
    "Carbon Project Zone": "SERPRO carbon project zone",
}[scope]

# Boundary areas are official supplied values. Live indicators remain demo values until
# source-specific datasets are connected and spatially filtered by the selected scope.
cols = st.columns(6)
metrics = [
    ("🗺️ Project Area", f"{project_area_ha:,.0f} ha", "official KML · 6 blocks"),
    ("🟣 Carbon Zone", f"{project_zone_area_ha:,.0f} ha", "official ProjectZone area"),
    ("🌧 Rainfall", "245 mm", "+18% vs normal"),
    ("🌡 Temperature", "27.8 °C", "+0.6 °C anomaly"),
    ("🔥 Hotspots", "17", "+6 vs previous 7D"),
    ("🟣 Carbon Risk", "68 / 100", "HIGH RISK"),
]
for col, (label, value, delta) in zip(cols, metrics):
    with col:
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-delta">{delta}</div></div>', unsafe_allow_html=True)

st.caption(f"Active scope: **{scope_label}** · Project Area: **{project_area_ha:,.2f} ha** · Carbon Project Zone: **{project_zone_area_ha:,.2f} ha**")

st.markdown('<div class="section-title">Project WebGIS & Climate Risk</div>', unsafe_allow_html=True)
map_col, risk_col = st.columns([2.1, 1])
with map_col:
    st_folium(
        render_map(data["hotspots"], data["monitoring_points"], focus=scope),
        width=None,
        height=500,
        returned_objects=[],
        key="monitoring_scope_map",
    )
with risk_col:
    st.markdown('<div class="risk-card"><div>CLIMATE RISK INDEX</div><div class="risk-number">68</div><div class="risk-label">HIGH RISK</div><hr>', unsafe_allow_html=True)
    for label, value in data["risk_inputs"].items():
        st.markdown(f"**{label.replace('_', ' ').title()}** — {value:.2f}")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Monitoring Trends</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1:
    st.plotly_chart(data["rainfall_chart"], use_container_width=True, config={"displayModeBar": False})
with c2:
    st.plotly_chart(data["fire_chart"], use_container_width=True, config={"displayModeBar": False})
with c3:
    st.plotly_chart(data["ndvi_chart"], use_container_width=True, config={"displayModeBar": False})

st.markdown('<div class="section-title">Recent Alerts</div>', unsafe_allow_html=True)
for _, alert in data["alerts"].iterrows():
    priority = alert["Priority"]
    cls = "alert-high" if priority == "HIGH" else "alert-medium" if priority == "MEDIUM" else "alert-low"
    st.markdown(f'<div class="{cls}"><b>{alert["Type"]}</b> · {alert["Location"]} · {alert["Date"]} · <b>{priority}</b></div>', unsafe_allow_html=True)

st.caption("Boundary note: SERPRO Project Area uses KAL_Boundary_Split.kml; SERPRO Carbon Project Zone uses ProjectZone.kmz. They are spatially overlapping components of the same unified SERPRO project landscape. Monitoring indicators remain demo values until live spatial datasets are connected and filtered by the selected scope.")
