"""Tests for the static CDR catalog."""

from aou_cost_engine.catalog import (
    CDR_CATALOG,
    get_column_bytes,
    get_select_star_bytes,
    get_table_total,
)


class TestCatalog:
    def test_known_table(self):
        assert "person" in CDR_CATALOG
        assert "measurement" in CDR_CATALOG
        assert "cb_variant_to_person" in CDR_CATALOG

    def test_table_has_total(self):
        for table in CDR_CATALOG:
            assert "_table_total" in CDR_CATALOG[table]

    def test_get_column_bytes_known(self):
        result = get_column_bytes("person", "person_id")
        assert result is not None
        assert result > 0

    def test_get_column_bytes_unknown_table(self):
        assert get_column_bytes("nonexistent", "col") is None

    def test_get_column_bytes_unknown_column(self):
        assert get_column_bytes("person", "nonexistent_col") is None

    def test_get_column_bytes_qualified_name(self):
        result = get_column_bytes("dataset.person", "person_id")
        assert result is not None

    def test_get_table_total(self):
        total = get_table_total("measurement")
        assert total is not None
        assert total == 400 * 1024**3

    def test_get_select_star_bytes(self):
        result = get_select_star_bytes("person")
        assert result is not None
        assert result == 200 * 1024**2

    def test_variant_table_is_largest(self):
        variant_total = get_table_total("cb_variant_to_person")
        person_total = get_table_total("person")
        assert variant_total > person_total
