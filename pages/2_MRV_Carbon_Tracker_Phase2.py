"""Phase 2 MRV Carbon Tracker workspace.

This page introduces auditable data contracts and calculation primitives.
It never invents project carbon values when evidence is unavailable.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.mrv_engine import area_coverage, biomass_to_carbon_tonnes, carbon_to_co2e_tonnes
from utils.scope_engine import SCOPE_OPTIONS

st.set_page_config(page_title="MRV Carbon Tracker · SERPRO", page_icon="🌳", layout="wide")

st.title("🌳 MRV Carbon Tracker")
st.caption("Phase 2 · evidence-driven carbon accounting workspace")

st.info(
    "Phase 2 starts with a controlled MRV data contract. Official project boundaries are available; "
    "LULC, biomass and SOC values are only calculated when an evidence dataset is supplied."
)

scope_label = st.selectbox("Monitoring scope", list(SCOPE_OPTIONS), index=2)
scope = SCOPE_OPTIONS[scope_label]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Official scope", f"{scope.area_ha:,.2f} ha")
c2.metric("LULC baseline", "Input required")
c3.metric("AGB / biomass", "Input required")
c4.metric("SOC / peat", "Input required")

st.markdown("### Phase 2 implementation status")
status_rows = pd.DataFrame(
    [
        ["Official spatial scope", "Available", "Scope Engine"],
        ["LULC baseline & change", "Ready for evidence", "CSV contract"],
        ["AGB / biomass", "Ready for evidence", "Calculation primitive"],
        ["SOC / peat carbon", "Schema pending", "Next implementation slice"],
        ["Carbon pools", "Schema pending", "Next implementation slice"],
        ["Baseline / project / leakage", "Deferred", "Accounting layer"],
        ["QA/QC & uncertainty", "Foundation ready", "Calculation primitive"],
    ],
    columns=["Domain", "Status", "Implementation"],
)
st.dataframe(status_rows, use_container_width=True, hide_index=True)

st.markdown("### 1 · LULC evidence intake")
st.caption(
    "Upload a CSV for the selected scope. Required columns: year, class_code, class_name, area_ha. "
    "The calculation is session-only and does not modify repository data."
)

lulc_template = "year,class_code,class_name,area_ha\n2025,EXAMPLE,Replace_with_verified_class,0\n"
st.download_button(
    "Download LULC CSV template",
    data=lulc_template,
    file_name="serpro_lulc_evidence_template.csv",
    mime="text/csv",
)

lulc_file = st.file_uploader("LULC evidence CSV", type=["csv"], key="mrv_lulc_upload")
if lulc_file is not None:
    try:
        lulc = pd.read_csv(lulc_file)
        required = {"year", "class_code", "class_name", "area_ha"}
        missing = required - set(lulc.columns)
        if missing:
            st.error(f"Missing required columns: {', '.join(sorted(missing))}")
        elif lulc.empty:
            st.error("The LULC evidence file is empty.")
        else:
            lulc["year"] = pd.to_numeric(lulc["year"], errors="coerce")
            lulc["area_ha"] = pd.to_numeric(lulc["area_ha"], errors="coerce")
            if lulc[["year", "area_ha"]].isna().any().any() or (lulc["area_ha"] < 0).any():
                st.error("Year/area contains invalid values. Area must be numeric and non-negative.")
            else:
                totals = lulc.groupby("year", as_index=False)["area_ha"].sum().sort_values("year")
                latest_year = int(totals.iloc[-1]["year"])
                latest_total = float(totals.iloc[-1]["area_ha"])
                coverage = area_coverage(latest_total, scope.area_ha)

                m1, m2, m3 = st.columns(3)
                m1.metric("Latest LULC year", latest_year)
                m2.metric("Mapped area", f"{latest_total:,.2f} ha")
                m3.metric("Coverage", f"{coverage.coverage_percent:,.2f}%")

                if abs(coverage.delta_ha) > max(1.0, scope.area_ha * 0.01):
                    st.warning(
                        f"Mapped area differs from the official scope by {coverage.delta_ha:,.2f} ha. "
                        "Check masking, class exclusions and geometry before using the dataset for carbon accounting."
                    )
                else:
                    st.success("LULC area is within the initial 1% coverage tolerance for this scope.")

                st.dataframe(
                    lulc.sort_values(["year", "class_code"]),
                    use_container_width=True,
                    hide_index=True,
                )

                if len(totals) >= 2:
                    baseline_year = int(totals.iloc[0]["year"])
                    baseline_total = float(totals.iloc[0]["area_ha"])
                    change = latest_total - baseline_total
                    st.markdown("#### LULC area change screening")
                    a1, a2, a3 = st.columns(3)
                    a1.metric("Baseline year", baseline_year)
                    a2.metric("Latest year", latest_year)
                    a3.metric("Net mapped-area change", f"{change:+,.2f} ha")

                st.download_button(
                    "Download validated LULC table",
                    data=lulc.to_csv(index=False).encode("utf-8"),
                    file_name="serpro_lulc_validated_session.csv",
                    mime="text/csv",
                )
    except Exception as exc:
        st.error(f"Unable to read LULC evidence: {exc}")

st.markdown("### 2 · Carbon-pool evidence calculator")
left, right = st.columns(2, gap="large")
with left:
    biomass_t = st.number_input("Dry biomass (t)", min_value=0.0, value=0.0, step=100.0)
    carbon_fraction = st.number_input("Carbon fraction", min_value=0.0, max_value=1.0, value=0.47, step=0.01)
    carbon_t = biomass_to_carbon_tonnes(biomass_t, carbon_fraction)
    st.metric("Biomass → carbon", f"{carbon_t:,.2f} t C")
with right:
    st.metric("Carbon → CO₂e", f"{carbon_to_co2e_tonnes(carbon_t):,.2f} t CO₂e")
    st.caption("Conversion uses the explicit 44/12 molecular-weight ratio. Methodology-specific eligibility is not implied.")

st.markdown("### 3 · MRV evidence boundary")
st.warning(
    "No VCS/VCU quantity is reported by this Phase 2 foundation. Before production carbon accounting, "
    "we still need verified LULC classes, AGB/biomass evidence, SOC/peat parameters, carbon-pool rules, "
    "baseline/project/leakage definitions, uncertainty treatment and methodology-specific QA/QC."
)
