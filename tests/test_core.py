"""Tests for the core dry-run estimation engine."""

from unittest.mock import MagicMock, patch

import pytest

from aou_cost_engine.core import (
    BYTES_PER_TIB,
    CostEstimate,
    bytes_to_cost,
    estimate_bq_cost,
    format_bytes,
    MIN_BYTES_BILLED,
)


class TestFormatBytes:
    def test_bytes(self):
        assert format_bytes(500) == "500 B"

    def test_kilobytes(self):
        assert format_bytes(1536) == "1.5 KB"

    def test_megabytes(self):
        assert format_bytes(10 * 1024 * 1024) == "10.0 MB"

    def test_gigabytes(self):
        assert format_bytes(5 * 1024**3) == "5.0 GB"

    def test_terabytes(self):
        assert format_bytes(2 * 1024**4) == "2.0 TB"


class TestBytesToCost:
    def test_minimum_billing(self):
        cost = bytes_to_cost(100)
        expected = (MIN_BYTES_BILLED / BYTES_PER_TIB) * 6.25
        assert cost == pytest.approx(expected)

    def test_one_tib(self):
        cost = bytes_to_cost(BYTES_PER_TIB)
        assert cost == pytest.approx(6.25)

    def test_zero_bytes(self):
        cost = bytes_to_cost(0)
        assert cost > 0  # 10 MB minimum applies

    def test_large_query(self):
        two_tib = 2 * BYTES_PER_TIB
        cost = bytes_to_cost(two_tib)
        assert cost == pytest.approx(12.50)


class TestEstimateBqCost:
    def _mock_client(self, bytes_processed: int, cached_bytes: int = 0):
        client = MagicMock()

        def side_effect(sql, job_config=None):
            job = MagicMock()
            if job_config and job_config.dry_run:
                if job_config.use_query_cache is False:
                    job.total_bytes_processed = bytes_processed
                else:
                    job.total_bytes_processed = cached_bytes
            return job

        client.query.side_effect = side_effect
        return client

    def test_basic_estimate(self):
        client = self._mock_client(1_000_000_000)
        result = estimate_bq_cost("SELECT * FROM t", client)
        assert result.exact is True
        assert result.bytes_scanned == 1_000_000_000
        assert result.cost_usd > 0

    def test_cache_eligible(self):
        client = self._mock_client(1_000_000_000, cached_bytes=0)
        result = estimate_bq_cost("SELECT * FROM t", client)
        assert result.cache_eligible is True

    def test_not_cache_eligible(self):
        client = self._mock_client(1_000_000_000, cached_bytes=1_000_000_000)
        result = estimate_bq_cost("SELECT * FROM t", client)
        assert result.cache_eligible is False

    def test_limit_without_where_warning(self):
        client = self._mock_client(5_000_000_000)
        result = estimate_bq_cost("SELECT * FROM t LIMIT 100", client)
        assert any("LIMIT without WHERE" in w for w in result.warnings)

    def test_limit_with_where_no_warning(self):
        client = self._mock_client(500_000_000)
        result = estimate_bq_cost(
            "SELECT * FROM t WHERE id > 5 LIMIT 100", client
        )
        assert not any("LIMIT without WHERE" in w for w in result.warnings)

    def test_dry_run_failure(self):
        client = MagicMock()
        client.query.side_effect = Exception("Bad SQL")
        result = estimate_bq_cost("INVALID SQL", client)
        assert result.exact is False
        assert result.error is not None
        assert "Bad SQL" in result.error


class TestCostEstimate:
    def test_bytes_display(self):
        est = CostEstimate(bytes_scanned=1_000_000_000, cost_usd=0.005, exact=True)
        assert "MB" in est.bytes_display or "GB" in est.bytes_display

    def test_cost_display_small(self):
        est = CostEstimate(bytes_scanned=100, cost_usd=0.001, exact=True)
        assert est.cost_display == "$0.0010"

    def test_cost_display_large(self):
        est = CostEstimate(bytes_scanned=BYTES_PER_TIB, cost_usd=6.25, exact=True)
        assert est.cost_display == "$6.25"
