"""Tests for the guardrails module."""

from aou_cost_engine.guardrails import (
    CostLevel,
    classify_cost_threshold,
    detect_limit_without_where,
    detect_select_star,
    generate_warnings,
    inject_byte_cap,
    suggest_byte_cap,
)


class TestCostThreshold:
    def test_green(self):
        assert classify_cost_threshold(0.001) == CostLevel.GREEN

    def test_yellow(self):
        assert classify_cost_threshold(0.05) == CostLevel.YELLOW

    def test_red(self):
        assert classify_cost_threshold(1.00) == CostLevel.RED

    def test_boundary_green_yellow(self):
        assert classify_cost_threshold(0.01) == CostLevel.YELLOW

    def test_boundary_yellow_red(self):
        assert classify_cost_threshold(0.50) == CostLevel.YELLOW
        assert classify_cost_threshold(0.51) == CostLevel.RED


class TestSuggestByteCap:
    def test_default_headroom(self):
        cap = suggest_byte_cap(1_000_000_000)
        assert cap == 1_200_000_000

    def test_custom_headroom(self):
        cap = suggest_byte_cap(1_000_000_000, headroom=1.5)
        assert cap == 1_500_000_000


class TestInjectByteCap:
    def test_bigquery_magic(self):
        code = "%%bigquery df\nSELECT * FROM person"
        result = inject_byte_cap(code, 1_000_000_000)
        assert "--maximum_bytes_billed 1000000000" in result

    def test_bigquery_magic_already_has_cap(self):
        code = "%%bigquery df --maximum_bytes_billed 500\nSELECT * FROM person"
        result = inject_byte_cap(code, 1_000_000_000)
        assert result == code  # no double injection

    def test_query_job_config(self):
        code = 'config = QueryJobConfig(dry_run=True)\nclient.query(sql, job_config=config)'
        result = inject_byte_cap(code, 1_000_000_000)
        assert "maximum_bytes_billed=1000000000" in result

    def test_query_job_config_empty(self):
        code = "config = QueryJobConfig()"
        result = inject_byte_cap(code, 500_000_000)
        assert "maximum_bytes_billed=500000000" in result


class TestDetectors:
    def test_limit_without_where(self):
        assert detect_limit_without_where("SELECT * FROM t LIMIT 10") is True

    def test_limit_with_where(self):
        assert (
            detect_limit_without_where("SELECT * FROM t WHERE x > 1 LIMIT 10")
            is False
        )

    def test_select_star(self):
        assert detect_select_star("SELECT * FROM t") is True

    def test_no_select_star(self):
        assert detect_select_star("SELECT id, name FROM t") is False


class TestGenerateWarnings:
    def test_high_cost_warning(self):
        warnings = generate_warnings("SELECT * FROM t", 2 * 1024**4, 12.50)
        assert any("HIGH COST" in w for w in warnings)

    def test_select_star_warning(self):
        warnings = generate_warnings("SELECT * FROM t", 100, 0.001)
        assert any("SELECT *" in w for w in warnings)

    def test_limit_without_where_warning(self):
        warnings = generate_warnings("SELECT * FROM t LIMIT 10", 100, 0.001)
        assert any("LIMIT without WHERE" in w for w in warnings)
