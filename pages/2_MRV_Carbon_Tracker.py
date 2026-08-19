"""Enterprise MRV Carbon Tracker shell.

Phase 1 deliberately preserves existing analytical engines. Carbon accounting,
methodology-specific calculations and database integration are future phases.
"""
import streamlit as st

st.set_page_config(page_title="MRV Carbon Tracker · SERPRO", page_icon="🌳", layout="wide")

st.title("🌳 MRV Carbon Tracker")
st.caption("Enterprise MRV shell for carbon accounting and evidence integration.")

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader("MRV evidence workspace")
    st.info("Phase 1 establishes the page contract. Existing vegetation, climate and fire analytical modules remain unchanged.")
with right:
    st.subheader("Planned evidence domains")
    st.markdown("- LULC and change detection\n- AGB / biomass\n- SOC and peat carbon\n- Carbon pools\n- Baseline / project / leakage\n- QA/QC and uncertainty")

st.markdown("### Methodology boundary")
st.warning("This Phase 1 shell does not calculate VCS/VCU quantities and does not claim methodology compliance. VM0007/VM0047 integration is intentionally deferred to the MRV implementation phase.")
