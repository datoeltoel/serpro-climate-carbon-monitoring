# Phase 2.1 — MRV Data Foundation

## Objective
Create an auditable evidence layer before any production carbon accounting.

## LULC evidence contract

Required fields:

- `year`
- `class_code`
- `class_name`
- `area_ha`

Recommended provenance fields:

- `source`
- `acquisition_date`
- `spatial_resolution_m`
- `classification_method`
- `accuracy_percent`
- `processing_version`

## Acceptance rules

1. Scope area must be positive.
2. Year and area must be numeric.
3. Area must be non-negative.
4. Class code and class name cannot be blank.
5. Duplicate `year + class_code` records are flagged for aggregation review.
6. Coverage is compared with the selected official SERPRO scope.
7. Coverage outside the initial 1% tolerance is a warning, not an automatic carbon-accounting approval.
8. Provenance completeness is reported.
9. Uploaded evidence remains session-only; repository data is not modified by the Streamlit intake.
10. No VCS/VCU quantity is inferred from incomplete evidence.

## Next slices

- verified LULC production dataset and change matrix
- AGB/biomass evidence contract
- SOC/peat evidence contract
- carbon-pool rules
- baseline/project/leakage accounting
