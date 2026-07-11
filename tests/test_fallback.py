"""Tests for the sqlglot-based fallback estimator."""

from aou_cost_engine.fallback import estimate_from_sql, parse_sql


class TestParseSQL:
    def test_simple_select(self):
        parsed = parse_sql("SELECT person_id FROM person")
        assert "person" in parsed.tables
        assert not parsed.has_select_star

    def test_select_star(self):
        parsed = parse_sql("SELECT * FROM person")
        assert parsed.has_select_star

    def test_limit_without_where(self):
        parsed = parse_sql("SELECT * FROM person LIMIT 10")
        assert parsed.has_limit
        assert not parsed.has_where

    def test_limit_with_where(self):
        parsed = parse_sql(
            "SELECT * FROM person WHERE year_of_birth > 1990 LIMIT 10"
        )
        assert parsed.has_limit
        assert parsed.has_where

    def test_unnest(self):
        parsed = parse_sql(
            "SELECT * FROM person CROSS JOIN UNNEST(array_col) AS x"
        )
        assert parsed.has_unnest
        assert parsed.has_cross_join_unnest

    def test_multiple_tables(self):
        parsed = parse_sql(
            "SELECT p.person_id FROM person p "
            "JOIN condition_occurrence c ON p.person_id = c.person_id"
        )
        assert len(parsed.tables) >= 2

    def test_invalid_sql(self):
        parsed = parse_sql("THIS IS NOT SQL AT ALL")
        assert len(parsed.tables) == 0


class TestEstimateFromSql:
    def test_known_table_select_star(self):
        result = estimate_from_sql("SELECT * FROM person")
        assert result.bytes_scanned > 0
        assert not result.exact
        assert any("SELECT *" in w for w in result.warnings)

    def test_known_table_specific_columns(self):
        result = estimate_from_sql(
            "SELECT person_id, year_of_birth FROM person"
        )
        assert result.bytes_scanned > 0
        assert not result.exact

    def test_unknown_table(self):
        result = estimate_from_sql("SELECT * FROM unknown_table")
        assert any("not in catalog" in w for w in result.warnings)

    def test_limit_without_where_warning(self):
        result = estimate_from_sql("SELECT * FROM person LIMIT 10")
        assert any("LIMIT without WHERE" in w for w in result.warnings)

    def test_approximate_label(self):
        result = estimate_from_sql("SELECT person_id FROM person")
        assert not result.exact
        assert any("approximate" in w.lower() for w in result.warnings)

    def test_cross_join_unnest_multiplier(self):
        base = estimate_from_sql("SELECT * FROM person")
        unnest = estimate_from_sql(
            "SELECT * FROM person CROSS JOIN UNNEST(arr) AS x"
        )
        assert unnest.bytes_scanned > base.bytes_scanned

    def test_no_tables(self):
        result = estimate_from_sql("SELECT 1 + 1")
        assert result.bytes_scanned == 0
