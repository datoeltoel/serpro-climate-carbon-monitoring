import pandas as pd

from utils.mrv_evidence import validate_lulc_evidence


def test_valid_lulc_evidence_and_provenance():
    frame = pd.DataFrame(
        [
            {
                "year": 2025,
                "class_code": "FOR",
                "class_name": "Forest",
                "area_ha": 900,
                "source": "verified_lulc",
                "acquisition_date": "2025-07-01",
                "spatial_resolution_m": 10,
                "classification_method": "Random Forest",
                "accuracy_percent": 90,
                "processing_version": "v1",
            },
            {
                "year": 2025,
                "class_code": "WAT",
                "class_name": "Water",
                "area_ha": 100,
                "source": "verified_lulc",
                "acquisition_date": "2025-07-01",
                "spatial_resolution_m": 10,
                "classification_method": "Random Forest",
                "accuracy_percent": 90,
                "processing_version": "v1",
            },
        ]
    )
    result = validate_lulc_evidence(frame, 1000)
    assert result.valid
    assert result.years == (2025,)
    assert result.total_area_by_year[2025] == 1000
    assert result.provenance_coverage_percent == 100


def test_negative_area_is_rejected():
    frame = pd.DataFrame(
        [[2025, "FOR", "Forest", -1]],
        columns=["year", "class_code", "class_name", "area_ha"],
    )
    result = validate_lulc_evidence(frame, 1000)
    assert not result.valid
    assert any("non-negative" in error for error in result.errors)


def test_missing_columns_are_rejected():
    frame = pd.DataFrame([[2025, "FOR", 1000]], columns=["year", "class_code", "area_ha"])
    result = validate_lulc_evidence(frame, 1000)
    assert not result.valid
    assert any("class_name" in error for error in result.errors)


def test_duplicate_year_class_is_warning_not_silent_acceptance():
    frame = pd.DataFrame(
        [
            [2025, "FOR", "Forest", 500],
            [2025, "FOR", "Forest", 500],
        ],
        columns=["year", "class_code", "class_name", "area_ha"],
    )
    result = validate_lulc_evidence(frame, 1000)
    assert result.valid
    assert any("Duplicate" in warning for warning in result.warnings)
