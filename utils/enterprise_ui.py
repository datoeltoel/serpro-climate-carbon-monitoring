"""Reusable UI primitives for the enterprise SERPRO dashboard."""
from __future__ import annotations

import folium
import streamlit as st
from streamlit_folium import st_folium


def apply_enterprise_css() -> None:
    st.markdown(
        """
        <style>
        .serpro-hero {
            border: 1px solid rgba(110, 180, 150, .28);
            border-radius: 18px;
            padding: 20px 24px;
            margin-bottom: 18px;
            background: linear-gradient(135deg, rgba(19, 66, 55, .72), rgba(18, 42, 54, .78));
        }
        .serpro-hero .eyebrow {
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .12em;
            text-transform: uppercase;
            opacity: .72;
        }
        .serpro-hero h1 { margin: 6px 0 4px; }
        .serpro-hero p { margin: 0; opacity: .78; }
        .analysis-panel {
            border: 1px solid rgba(130, 160, 170, .24);
            border-radius: 16px;
            padding: 14px;
            background: rgba(255,255,255,.025);
        }
        .section-label {
            font-size: .76rem;
            font-weight: 800;
            letter-spacing: .08em;
            text-transform: uppercase;
            opacity: .68;
            margin-bottom: 6px;
        }
        div[data-testid="stMetric"] {
            border: 1px solid rgba(130,160,170,.20);
            border-radius: 14px;
            padding: 10px 12px;
            background: rgba(255,255,255,.025);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, eyebrow: str = "SERPRO PROJECT · MRV CARBON MONITORING") -> None:
    st.markdown(
        f"""
        <div class="serpro-hero">
          <div class="eyebrow">{eyebrow}</div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_split_map_analysis(
    map_title: str = "Spatial overview",
    center: tuple[float, float] = (-2.35, 112.55),
    zoom: int = 9,
    map_key: str = "enterprise_map",
) -> None:
    """Render the Phase-2 fixed 60/40 map-analysis frame.

    The map is intentionally a lightweight basemap in Phase 1/2. Domain raster
    layers and click events are added in Phase 3 without changing the layout.
    """
    map_col, analysis_col = st.columns([3, 2], gap="medium")

    with map_col:
        st.markdown(f"**{map_title}**")
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles="CartoDB dark_matter",
            control_scale=True,
            prefer_canvas=True,
        )
        folium.Marker(center, tooltip="SERPRO monitoring centre").add_to(m)
        st_folium(m, height=620, width=None, key=map_key, returned_objects=[])

    with analysis_col:
        st.markdown('<div class="analysis-panel">', unsafe_allow_html=True)
        st.markdown("<div class='section-label'>Analysis workspace</div>", unsafe_allow_html=True)
        tab_overview, tab_stats, tab_metadata = st.tabs(["Overview", "Statistics", "Metadata"])
        with tab_overview:
            st.info("Phase 1/2 layout is active. Domain-specific analytical layers will be connected in the next implementation phase.")
        with tab_stats:
            st.metric("Spatial records", "—")
            st.metric("Latest processing", "—")
        with tab_metadata:
            st.write("Coordinate reference system: EPSG:4326")
            st.write("Map interaction: prepared for Phase 3 bidirectional selection.")
        st.markdown('</div>', unsafe_allow_html=True)
