"""AI-powered query optimizer using Claude."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

import anthropic

from aou_cost_engine.core import CostEstimate, bytes_to_cost, estimate_bq_cost

OPTIMIZATION_PROMPT = """\
You are a BigQuery SQL optimization expert for the All of Us Research Workbench.
Your goal is to rewrite the given query to scan fewer bytes while producing the same results.

Optimization strategies (in order of impact):
1. **Column pruning**: Replace SELECT * with only the columns actually needed.
2. **Predicate pushdown**: Add or tighten WHERE clauses, especially on partition/cluster columns (e.g., date columns, person_id).
3. **UNNEST optimization**: For CROSS JOIN UNNEST on array columns, filter BEFORE unnesting when possible.
4. **Approximation**: Use APPROX_COUNT_DISTINCT, APPROX_QUANTILES where exactness isn't needed. ALWAYS flag this as a semantic change.
5. **Query restructuring**: CTEs, better join ordering, materialized subqueries.
6. **Caching / materialization**: Suggest saving intermediate results to avoid re-scanning large tables.

Rules:
- The optimized query MUST produce the same results unless you use approximation functions (flag those explicitly).
- Do NOT change column names, output schema, or row ordering unless the original doesn't specify ORDER BY.
- Preserve all JOINs and filtering logic unless you can prove a filter is redundant.
- If the query is already optimal, say so.

Respond with ONLY a JSON object (no markdown fences):
{
  "optimized_sql": "the optimized SQL query",
  "explanation": "plain-English explanation of what changed and why",
  "confidence": "high" | "medium" | "low",
  "semantically_equivalent": true | false,
  "semantic_notes": "if not equivalent, explain what differs",
  "strategies_applied": ["list", "of", "strategies", "used"]
}
"""

DEFAULT_COST_THRESHOLD = 0.10
MODEL = "claude-haiku-4-5-20251001"


@dataclass
class OptimizationResult:
    original_sql: str
    optimized_sql: str
    original_estimate: CostEstimate
    optimized_estimate: CostEstimate
    explanation: str
    confidence: str
    semantically_equivalent: bool
    semantic_notes: str
    strategies_applied: list[str]
    api_cost_usd: float
    skipped: bool = False
    skip_reason: Optional[str] = None
    error: Optional[str] = None

    @property
    def savings_bytes(self) -> int:
        return self.original_estimate.bytes_scanned - self.optimized_estimate.bytes_scanned

    @property
    def savings_usd(self) -> float:
        return self.original_estimate.cost_usd - self.optimized_estimate.cost_usd

    @property
    def savings_pct(self) -> float:
        if self.original_estimate.bytes_scanned == 0:
            return 0.0
        return self.savings_bytes / self.original_estimate.bytes_scanned * 100


def _estimate_api_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)


def optimize_query(
    sql: str,
    bq_client,
    anthropic_client: anthropic.Anthropic | None = None,
    *,
    cost_threshold: float = DEFAULT_COST_THRESHOLD,
    api_key: str | None = None,
) -> OptimizationResult:
    """Optimize a SQL query using Claude and verify with dry run.

    Args:
        sql: The original SQL query.
        bq_client: An authenticated BigQuery client for dry-run verification.
        anthropic_client: Pre-configured Anthropic client (preferred).
        cost_threshold: Minimum cost in USD to trigger optimization.
        api_key: Anthropic API key (used only if anthropic_client is None).
    """
    original_estimate = estimate_bq_cost(sql, bq_client)

    if original_estimate.error:
        return OptimizationResult(
            original_sql=sql,
            optimized_sql=sql,
            original_estimate=original_estimate,
            optimized_estimate=original_estimate,
            explanation="",
            confidence="low",
            semantically_equivalent=True,
            semantic_notes="",
            strategies_applied=[],
            api_cost_usd=0.0,
            error=f"Cannot optimize: {original_estimate.error}",
        )

    if original_estimate.cost_usd < cost_threshold:
        return OptimizationResult(
            original_sql=sql,
            optimized_sql=sql,
            original_estimate=original_estimate,
            optimized_estimate=original_estimate,
            explanation="",
            confidence="high",
            semantically_equivalent=True,
            semantic_notes="",
            strategies_applied=[],
            api_cost_usd=0.0,
            skipped=True,
            skip_reason=f"Cost ${original_estimate.cost_usd:.4f} is below threshold ${cost_threshold:.2f}",
        )

    if anthropic_client is None:
        anthropic_client = anthropic.Anthropic(api_key=api_key)

    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"Optimize this BigQuery SQL query:\n\n{sql}",
            }
        ],
        system=OPTIMIZATION_PROMPT,
    )

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    api_cost = _estimate_api_cost(input_tokens, output_tokens)

    raw_text = response.content[0].text.strip()
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if json_match:
        raw_text = json_match.group(0)

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        return OptimizationResult(
            original_sql=sql,
            optimized_sql=sql,
            original_estimate=original_estimate,
            optimized_estimate=original_estimate,
            explanation="",
            confidence="low",
            semantically_equivalent=True,
            semantic_notes="",
            strategies_applied=[],
            api_cost_usd=api_cost,
            error=f"Failed to parse AI response: {raw_text[:200]}",
        )

    optimized_sql = result.get("optimized_sql", sql)
    optimized_estimate = estimate_bq_cost(optimized_sql, bq_client)

    if optimized_estimate.error:
        return OptimizationResult(
            original_sql=sql,
            optimized_sql=optimized_sql,
            original_estimate=original_estimate,
            optimized_estimate=original_estimate,
            explanation=result.get("explanation", ""),
            confidence="low",
            semantically_equivalent=False,
            semantic_notes=f"Optimized query failed dry run: {optimized_estimate.error}",
            strategies_applied=result.get("strategies_applied", []),
            api_cost_usd=api_cost,
            error=f"Optimized query failed validation: {optimized_estimate.error}",
        )

    return OptimizationResult(
        original_sql=sql,
        optimized_sql=optimized_sql,
        original_estimate=original_estimate,
        optimized_estimate=optimized_estimate,
        explanation=result.get("explanation", ""),
        confidence=result.get("confidence", "medium"),
        semantically_equivalent=result.get("semantically_equivalent", True),
        semantic_notes=result.get("semantic_notes", ""),
        strategies_applied=result.get("strategies_applied", []),
        api_cost_usd=api_cost,
    )
