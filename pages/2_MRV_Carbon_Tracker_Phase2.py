"""Phase 2 MRV Carbon Tracker workspace.

Phase 2.1 adds an auditable LULC evidence contract and validation layer.
It never invents project carbon values when evidence is unavailable.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.mrv_engine import biomass_to_carbon_tonnes, carbon_to_co2e_tonnes
from utils.mrv_evidence import OPTIONAL_PROVENANCE_COLUMNS, validate_lulc_evidence
from utils.scope_engine import SCOPE_OPTIONS

st.set_page_config(page_title="MRV Carbon Tracker · SERPRO", page_icon="🌳", layout="wide")

st.title("🌳 MRV Carbon Tracker")
st.caption("Phase 2.1 · evidence-driven MRV data foundation")
st.info("This workspace validates supplied MRV evidence against the official SERPRO spatial scope. It does not create project carbon values when evidence is unavailable. Uploaded files remain session-only.")

scope_label = st.selectbox("Monitoring scope", list(SCOPE_OPTIONS), index=2)
scope = SCOPE_OPTIONS[scope_label]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Official scope", f"{scope.area_ha:,.2f} ha")
c2.metric("LULC evidence", "Input required")
c3.metric("AGB / biomass", "Input required")
c4.metric("SOC / peat", "Input required")

st.markdown("### Phase 2.1 implementation status")
status_rows = pd.DataFrame([
    ["Official spatial scope", "Available", "Scope Engine"],
    ["LULC evidence contract", "Implemented", "Schema + validator"],
    ["LULC coverage / completeness", "Implemented", "Scope + provenance QA"],
    ["LULC change matrix", "Next slice", "Evidence-derived"],
    ["AGB / biomass", "Next slice", "Evidence contract"],
    ["SOC / peat carbon", "Next slice", "Evidence contract"],
    ["Carbon pools", "Pending", "Accounting layer"],
    ["Baseline / project / leakage", "Deferred", "Accounting layer"],
], columns=["Domain", "Status", "Implementation"])
st.dataframe(status_rows, use_container_width=True, hide_index=True)

st.markdown("### 1 · LULC evidence intake")
st.caption("Required: year, class_code, class_name, area_ha. Recommended provenance: " + ", ".join(sorted(OPTIONAL_PROVENANCE_COLUMNS)))

lulc_template = "year,class_code,class_name,area_ha,source,acquisition_date,spatial_resolution_m,classification_method,accuracy_percent,processing_version\n2025,EXAMPLE,Replace_with_verified_class,0,verified_source,YYYY-MM-DD,10,methodology_and_algorithm,0.0,v1\n"
st.download_button("Download LULC evidence template", data=lulc_template, file_name="serpro_lulc_evidence_template.csv", mime="text/csv")

lulc_file = st.file_uploader("LULC evidence CSV", type=["csv"], key="mrv_lulc_upload")
if lulc_file is not None:
    try:
        lulc = pd.read_csv(lulc_file)
        validation = validate_lulc_evidence(lulc, scope.area_ha)
        if validation.valid:
            st.success(f"Evidence structure valid · {validation.row_count:,} rows · {len(validation.years)} year(s)")
        else:
            st.error("Evidence validation failed. Correct the errors before using this dataset.")
        for error in validation.errors:
            st.error(error)
        for warning in validation.warnings:
            st.warning(warning)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Rows", f"{validation.row_count:,}")
        m2.metric("Years", ", ".join(map(str, validation.years)) if validation.years else "—")
        m3.metric("Provenance", f"{validation.provenance_coverage_percent:,.1f}%")
        latest_year = validation.years[-1] if validation.years else None
        latest_total = validation.total_area_by_year.get(latest_year, 0.0) if latest_year else 0.0
        coverage_pct = latest_total / scope.area_ha * 100.0 if scope.area_ha > 0 else 0.0
        m4.metric("Latest coverage", f"{coverage_pct:,.2f}%")

        if validation.valid:
            coverage_rows = []
            for year, total in validation.total_area_by_year.items():
                coverage_rows.append({"year": year, "mapped_area_ha": round(total, 4), "official_scope_ha": round(scope.area_ha, 4), "coverage_percent": round(total / scope.area_ha * 100.0, 4), "delta_ha": round(total - scope.area_ha, 4)})
            st.markdown("#### Evidence coverage by year")
            st.dataframe(pd.DataFrame(coverage_rows), use_container_width=True, hide_index=True)
            st.markdown("#### Class-level evidence")
            st.dataframe(lulc.sort_values(["year", "class_code"]), use_container_width=True, hide_index=True)
            st.download_button("Download validated LULC session table", data=lulc.to_csv(index=False).encode("utf-8"), file_name="serpro_lulc_validated_session.csv", mime="text/csv")
    except Exception as exc:
        st.error(f"Unable to read LULC evidence: {exc}")

st.markdown("### 2 · Carbon-pool calculation primitive")
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
st.warning("Phase 2.1 does not report a VCS/VCU quantity. Production carbon accounting still requires verified LULC change evidence, AGB/biomass evidence, SOC/peat parameters, carbon-pool rules, baseline/project/leakage definitions, uncertainty treatment and methodology-specific QA/QC.")
