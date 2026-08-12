import streamlit as st
from streamlit_folium import st_folium
from utils.demo_data import load_demo_data
from utils.scope_engine import get_scope, scope_options, SPATIAL_RELATIONSHIP
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
project_area_scope = get_scope("SERPRO Project Area")
project_zone_scope = get_scope("SERPRO Carbon Project Zone")
project_area_ha = project_area_scope.area_ha
project_zone_area_ha = project_zone_scope.area_ha
containment = min(100.0, SPATIAL_RELATIONSHIP["project_area_containment_percent"])
zone_share = SPATIAL_RELATIONSHIP["project_area_share_of_carbon_zone_percent"]

st.markdown('<div class="section-title">Project Landscape Summary</div>', unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="landscape-summary">
      <div class="landscape-intro">
        <b>Unified SERPRO Project Landscape</b><br>
        The Carbon Project Zone is the primary spatial envelope of the SERPRO landscape, with the Project Area forming a contained sub-area.
      </div>
      <div class="landscape-grid">
        <div class="landscape-card zone-card">
          <div class="landscape-icon">🟣</div>
          <div class="landscape-label">SERPRO Carbon Project Zone</div>
          <div class="landscape-value">{project_zone_area_ha:,.2f} ha</div>
          <div class="landscape-meta">Primary project-zone envelope · ProjectZone.kmz</div>
        </div>
        <div class="landscape-connector">↓<span>CONTAINS</span></div>
        <div class="landscape-card area-card">
          <div class="landscape-icon">🟢</div>
          <div class="landscape-label">SERPRO Project Area</div>
          <div class="landscape-value">{project_area_ha:,.2f} ha</div>
          <div class="landscape-meta">PT KAL concession / project area · KAL_Boundary_Split.kml</div>
        </div>
      </div>
      <div class="landscape-note">
        Spatial analysis confirms the Project Area is effectively fully contained within the Carbon Project Zone.
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
          <div><b>SPATIAL RELATIONSHIP</b></div>
          <div class="risk-number">≈{containment:.0f}%</div>
          <div class="risk-label">PROJECT AREA WITHIN CARBON ZONE</div>
          <hr>
          <p><b>Intersection</b><br>{SPATIAL_RELATIONSHIP['intersection_area_ha']:,.5f} ha</p>
          <p><b>Union</b><br>{SPATIAL_RELATIONSHIP['union_area_ha']:,.6f} ha</p>
          <p><b>Project Area share of Carbon Zone</b><br>{zone_share:.2f}%</p>
          <div style="padding:10px;border-radius:8px;background:rgba(255,255,255,.09);font-size:.82rem;line-height:1.45;">
            Geometry differences below practical mapping precision are treated as tolerance, not meaningful land area.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Simple monitoring-scope selector. The previous Scope Engine diagram has been removed.
st.markdown('<div class="section-title">Monitoring Scope</div>', unsafe_allow_html=True)
scope = st.selectbox(
    "Select monitoring scope",
    scope_options(),
    index=1,
    format_func=lambda x: {
        "SERPRO Project Landscape": "🌐 SERPRO Project Landscape",
        "SERPRO Carbon Project Zone": "🟣 Carbon Project Zone",
        "SERPRO Project Area": "🟢 Project Area",
    }[x],
)
selected_scope = get_scope(scope)

st.caption(
    f"Active scope: **{selected_scope.label}** · Area: **{selected_scope.area_ha:,.2f} ha** · {selected_scope.role}"
)

cols = st.columns(6)
metrics = [
    ("🗺️ Landscape", f"{project_zone_area_ha:,.0f} ha", "Carbon Zone envelope"),
    ("🟣 Carbon Zone", f"{project_zone_area_ha:,.0f} ha", "official ProjectZone area"),
    ("🟢 Project Area", f"{project_area_ha:,.0f} ha", f"{zone_share:.2f}% of Carbon Zone"),
    ("🌧 Rainfall", "245 mm", "+18% vs normal"),
    ("🔥 Hotspots", "17", "+6 vs previous 7D"),
    ("🟣 Carbon Risk", "68 / 100", "HIGH RISK"),
]
for col, (label, value, delta) in zip(cols, metrics):
    with col:
        st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-delta">{delta}</div></div>', unsafe_allow_html=True)

st.markdown('<div class="section-title">Project WebGIS & Climate Risk</div>', unsafe_allow_html=True)
map_col, risk_col = st.columns([2.1, 1])
with map_col:
    focus = "All Boundaries" if scope == "SERPRO Project Landscape" else scope
    st_folium(
        render_map(data["hotspots"], data["monitoring_points"], focus=focus),
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

st.caption("Scope note: SERPRO Carbon Project Zone is the primary monitoring envelope; SERPRO Project Area is a contained subset. Monitoring indicators remain demo values until live spatial datasets are connected and filtered by scope.")
