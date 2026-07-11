"""Tests for the AI optimizer module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from aou_cost_engine.core import CostEstimate
from aou_cost_engine.optimizer import (
    OptimizationResult,
    _estimate_api_cost,
    optimize_query,
)


def _mock_bq_client(original_bytes: int, optimized_bytes: int):
    client = MagicMock()
    call_count = [0]

    def side_effect(sql, job_config=None):
        job = MagicMock()
        if job_config and job_config.dry_run:
            if call_count[0] < 2:
                job.total_bytes_processed = original_bytes
            else:
                job.total_bytes_processed = optimized_bytes
            call_count[0] += 1
        return job

    client.query.side_effect = side_effect
    return client


def _mock_anthropic_client(response_dict: dict):
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(response_dict))]
    response.usage.input_tokens = 500
    response.usage.output_tokens = 200
    client.messages.create.return_value = response
    return client


class TestEstimateApiCost:
    def test_basic(self):
        cost = _estimate_api_cost(1000, 500)
        assert cost > 0
        assert cost < 0.05


class TestOptimizeQuery:
    def test_below_threshold_skips(self):
        client = MagicMock()
        job = MagicMock()
        job.total_bytes_processed = 1000
        client.query.return_value = job

        result = optimize_query(
            "SELECT 1", client, cost_threshold=1.00
        )
        assert result.skipped is True
        assert result.skip_reason is not None

    def test_dry_run_failure(self):
        client = MagicMock()
        client.query.side_effect = Exception("Permission denied")

        result = optimize_query("SELECT * FROM t", client)
        assert result.error is not None
        assert "Permission denied" in result.error

    def test_successful_optimization(self):
        bq_client = _mock_bq_client(
            original_bytes=10_000_000_000,
            optimized_bytes=2_000_000_000,
        )
        ai_client = _mock_anthropic_client({
            "optimized_sql": "SELECT person_id FROM person",
            "explanation": "Removed unnecessary columns",
            "confidence": "high",
            "semantically_equivalent": True,
            "semantic_notes": "",
            "strategies_applied": ["column_pruning"],
        })

        result = optimize_query(
            "SELECT * FROM person",
            bq_client,
            ai_client,
            cost_threshold=0.0,
        )
        assert not result.skipped
        assert result.error is None
        assert result.optimized_sql == "SELECT person_id FROM person"
        assert result.confidence == "high"
        assert result.semantically_equivalent is True
        assert result.savings_bytes > 0

    def test_invalid_ai_response(self):
        bq_client = _mock_bq_client(10_000_000_000, 10_000_000_000)

        ai_client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text="not valid json")]
        response.usage.input_tokens = 500
        response.usage.output_tokens = 200
        ai_client.messages.create.return_value = response

        result = optimize_query(
            "SELECT * FROM person",
            bq_client,
            ai_client,
            cost_threshold=0.0,
        )
        assert result.error is not None
        assert "parse" in result.error.lower()

    def test_optimized_query_fails_dry_run(self):
        call_count = [0]
        bq_client = MagicMock()

        def side_effect(sql, job_config=None):
            job = MagicMock()
            if job_config and job_config.dry_run:
                call_count[0] += 1
                if call_count[0] <= 2:
                    job.total_bytes_processed = 10_000_000_000
                else:
                    raise Exception("Invalid column reference")
            return job

        bq_client.query.side_effect = side_effect

        ai_client = _mock_anthropic_client({
            "optimized_sql": "SELECT bad_col FROM person",
            "explanation": "Pruned columns",
            "confidence": "high",
            "semantically_equivalent": True,
            "semantic_notes": "",
            "strategies_applied": ["column_pruning"],
        })

        result = optimize_query(
            "SELECT * FROM person",
            bq_client,
            ai_client,
            cost_threshold=0.0,
        )
        assert result.error is not None
        assert "validation" in result.error.lower() or "failed" in result.error.lower()


class TestOptimizationResult:
    def test_savings_calculations(self):
        result = OptimizationResult(
            original_sql="SELECT * FROM t",
            optimized_sql="SELECT id FROM t",
            original_estimate=CostEstimate(
                bytes_scanned=10_000_000_000, cost_usd=0.057, exact=True
            ),
            optimized_estimate=CostEstimate(
                bytes_scanned=2_000_000_000, cost_usd=0.011, exact=True
            ),
            explanation="Pruned columns",
            confidence="high",
            semantically_equivalent=True,
            semantic_notes="",
            strategies_applied=["column_pruning"],
            api_cost_usd=0.01,
        )
        assert result.savings_bytes == 8_000_000_000
        assert result.savings_usd == pytest.approx(0.046)
        assert result.savings_pct == pytest.approx(80.0)
