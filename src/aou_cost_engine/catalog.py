"""Static per-column size catalog for common AoU CDR tables.

Used only by the fallback estimator when dry run is unavailable.
Sizes are approximate and based on CDR v7 schema estimates.
"""

from __future__ import annotations

GB = 1024**3
MB = 1024**2

CDR_CATALOG: dict[str, dict[str, int]] = {
    "person": {
        "person_id": 3 * MB,
        "gender_concept_id": 3 * MB,
        "year_of_birth": 3 * MB,
        "month_of_birth": 3 * MB,
        "day_of_birth": 3 * MB,
        "birth_datetime": 5 * MB,
        "race_concept_id": 3 * MB,
        "ethnicity_concept_id": 3 * MB,
        "location_id": 3 * MB,
        "provider_id": 3 * MB,
        "care_site_id": 3 * MB,
        "person_source_value": 8 * MB,
        "gender_source_value": 5 * MB,
        "gender_source_concept_id": 3 * MB,
        "race_source_value": 5 * MB,
        "race_source_concept_id": 3 * MB,
        "ethnicity_source_value": 5 * MB,
        "ethnicity_source_concept_id": 3 * MB,
        "_table_total": 200 * MB,
    },
    "condition_occurrence": {
        "condition_occurrence_id": 760 * MB,
        "person_id": 760 * MB,
        "condition_concept_id": 760 * MB,
        "condition_start_date": 760 * MB,
        "condition_start_datetime": int(1.1 * GB),
        "condition_end_date": 760 * MB,
        "condition_end_datetime": int(1.1 * GB),
        "condition_type_concept_id": 760 * MB,
        "condition_status_concept_id": 760 * MB,
        "stop_reason": 500 * MB,
        "provider_id": 760 * MB,
        "visit_occurrence_id": 760 * MB,
        "visit_detail_id": 760 * MB,
        "condition_source_value": int(1.5 * GB),
        "condition_source_concept_id": 760 * MB,
        "condition_status_source_value": 500 * MB,
        "_table_total": 15 * GB,
    },
    "measurement": {
        "measurement_id": 20 * GB,
        "person_id": 20 * GB,
        "measurement_concept_id": 20 * GB,
        "measurement_date": 20 * GB,
        "measurement_datetime": 30 * GB,
        "measurement_time": 15 * GB,
        "measurement_type_concept_id": 20 * GB,
        "operator_concept_id": 20 * GB,
        "value_as_number": 20 * GB,
        "value_as_concept_id": 20 * GB,
        "unit_concept_id": 20 * GB,
        "range_low": 20 * GB,
        "range_high": 20 * GB,
        "provider_id": 20 * GB,
        "visit_occurrence_id": 20 * GB,
        "visit_detail_id": 20 * GB,
        "measurement_source_value": 40 * GB,
        "measurement_source_concept_id": 20 * GB,
        "unit_source_value": 30 * GB,
        "value_source_value": 30 * GB,
        "_table_total": 400 * GB,
    },
    "cb_variant_to_person": {
        "vid": 100 * GB,
        "person_id": 100 * GB,
        "variant_type": 50 * GB,
        "consequence": 80 * GB,
        "aa_change": 60 * GB,
        "contig": 50 * GB,
        "position": 100 * GB,
        "ref_allele": 60 * GB,
        "alt_allele": 60 * GB,
        "clinical_significance": 80 * GB,
        "gvs_all_ac": 100 * GB,
        "gvs_all_an": 100 * GB,
        "gvs_all_af": 100 * GB,
        "gene_symbol": 60 * GB,
        "transcript": 80 * GB,
        "_table_total": int(2.2 * 1024 * GB),
    },
    "drug_exposure": {
        "drug_exposure_id": 1600 * MB,
        "person_id": 1600 * MB,
        "drug_concept_id": 1600 * MB,
        "drug_exposure_start_date": 1600 * MB,
        "drug_exposure_start_datetime": int(2.4 * GB),
        "drug_exposure_end_date": 1600 * MB,
        "drug_exposure_end_datetime": int(2.4 * GB),
        "verbatim_end_date": 1600 * MB,
        "drug_type_concept_id": 1600 * MB,
        "stop_reason": 1000 * MB,
        "refills": 1600 * MB,
        "quantity": 1600 * MB,
        "days_supply": 1600 * MB,
        "sig": int(2.5 * GB),
        "route_concept_id": 1600 * MB,
        "lot_number": 500 * MB,
        "provider_id": 1600 * MB,
        "visit_occurrence_id": 1600 * MB,
        "visit_detail_id": 1600 * MB,
        "drug_source_value": int(3 * GB),
        "drug_source_concept_id": 1600 * MB,
        "route_source_value": 1000 * MB,
        "dose_unit_source_value": 1000 * MB,
        "_table_total": 30 * GB,
    },
    "observation": {
        "observation_id": 5 * GB,
        "person_id": 5 * GB,
        "observation_concept_id": 5 * GB,
        "observation_date": 5 * GB,
        "observation_datetime": 7 * GB,
        "observation_type_concept_id": 5 * GB,
        "value_as_number": 5 * GB,
        "value_as_string": 10 * GB,
        "value_as_concept_id": 5 * GB,
        "qualifier_concept_id": 5 * GB,
        "unit_concept_id": 5 * GB,
        "provider_id": 5 * GB,
        "visit_occurrence_id": 5 * GB,
        "visit_detail_id": 5 * GB,
        "observation_source_value": 8 * GB,
        "observation_source_concept_id": 5 * GB,
        "unit_source_value": 5 * GB,
        "qualifier_source_value": 5 * GB,
        "_table_total": 80 * GB,
    },
    "procedure_occurrence": {
        "procedure_occurrence_id": int(1.2 * GB),
        "person_id": int(1.2 * GB),
        "procedure_concept_id": int(1.2 * GB),
        "procedure_date": int(1.2 * GB),
        "procedure_datetime": int(1.8 * GB),
        "procedure_type_concept_id": int(1.2 * GB),
        "modifier_concept_id": int(1.2 * GB),
        "quantity": int(1.2 * GB),
        "provider_id": int(1.2 * GB),
        "visit_occurrence_id": int(1.2 * GB),
        "visit_detail_id": int(1.2 * GB),
        "procedure_source_value": int(2 * GB),
        "procedure_source_concept_id": int(1.2 * GB),
        "modifier_source_value": 800 * MB,
        "_table_total": 18 * GB,
    },
}

TABLE_ROW_COUNTS: dict[str, int] = {
    "person": 415_000,
    "condition_occurrence": 95_000_000,
    "measurement": 2_500_000_000,
    "cb_variant_to_person": 12_000_000_000,
    "drug_exposure": 200_000_000,
    "observation": 600_000_000,
    "procedure_occurrence": 120_000_000,
}


def get_column_bytes(table: str, column: str) -> int | None:
    table_lower = table.lower().split(".")[-1]
    table_data = CDR_CATALOG.get(table_lower)
    if table_data is None:
        return None
    return table_data.get(column.lower())


def get_table_total(table: str) -> int | None:
    table_lower = table.lower().split(".")[-1]
    table_data = CDR_CATALOG.get(table_lower)
    if table_data is None:
        return None
    return table_data.get("_table_total")


def get_select_star_bytes(table: str) -> int | None:
    return get_table_total(table)
