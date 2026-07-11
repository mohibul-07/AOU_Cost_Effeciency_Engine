"""FastAPI backend for AoU Cost Engine web app.

This is the offline/fallback version — no BigQuery dry run available.
Uses sqlglot + static catalog for approximate estimation,
and Claude for AI optimization.
"""

from __future__ import annotations

import json
import os
import re
from enum import Enum
from typing import Optional

import anthropic
import sqlglot
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from aou_cost_engine.catalog import CDR_CATALOG, TABLE_ROW_COUNTS
from aou_cost_engine.classifier import CellType, classify_cell, extract_sql
from aou_cost_engine.core import BYTES_PER_TIB, COST_PER_TIB, MIN_BYTES_BILLED, bytes_to_cost, format_bytes
from aou_cost_engine.fallback import estimate_from_sql
from aou_cost_engine.guardrails import (
    CostLevel,
    classify_cost_threshold,
    detect_limit_without_where,
    detect_select_star,
    generate_warnings,
    suggest_byte_cap,
)

app = FastAPI(
    title="AoU Cost Engine",
    description="Offline BigQuery cost estimation for All of Us Research Workbench",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EstimateRequest(BaseModel):
    code: str = Field(..., description="Python or SQL code to estimate")


class OptimizeRequest(BaseModel):
    sql: str = Field(..., description="SQL query to optimize")


class CostBreakdown(BaseModel):
    bytes_scanned: int
    bytes_display: str
    cost_usd: float
    cost_display: str
    exact: bool
    cache_eligible: bool
    cell_type: str
    cost_level: str
    warnings: list[str]
    cap_suggestion: Optional[dict] = None


class OptimizationResponse(BaseModel):
    original_sql: str
    optimized_sql: str
    original_bytes: int
    original_cost: float
    optimized_bytes: int
    optimized_cost: float
    savings_bytes: int
    savings_pct: float
    savings_usd: float
    explanation: str
    confidence: str
    semantically_equivalent: bool
    semantic_notes: str
    strategies_applied: list[str]
    api_cost_usd: float
    error: Optional[str] = None


class TableInfo(BaseModel):
    name: str
    approx_rows: int
    approx_size: str
    column_count: int


OPTIMIZATION_PROMPT = """\
You are a BigQuery SQL optimization expert for the All of Us Research Workbench.
Your goal is to rewrite the given query to scan fewer bytes while producing the same results.

Optimization strategies (in order of impact):
1. **Column pruning**: Replace SELECT * with only the columns actually needed.
2. **Predicate pushdown**: Add or tighten WHERE clauses, especially on partition/cluster columns.
3. **UNNEST optimization**: For CROSS JOIN UNNEST on array columns, filter BEFORE unnesting.
4. **Approximation**: Use APPROX_COUNT_DISTINCT, APPROX_QUANTILES where exactness isn't needed. ALWAYS flag this as a semantic change.
5. **Query restructuring**: CTEs, better join ordering, materialized subqueries.

Rules:
- The optimized query MUST produce the same results unless you use approximation functions.
- Do NOT change column names, output schema, or row ordering unless the original doesn't specify ORDER BY.
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


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/estimate", response_model=CostBreakdown)
def estimate(req: EstimateRequest):
    code = req.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Empty code")

    cell_type = classify_cell(code)
    sql = extract_sql(code)

    if cell_type != CellType.BIGQUERY or sql is None:
        if sql is None:
            sql = code
        cell_type_str = cell_type.value

        if cell_type == CellType.BIGQUERY or any(
            kw in code.upper() for kw in ("SELECT", "WITH", "INSERT")
        ):
            estimate_result = estimate_from_sql(sql)
        else:
            return CostBreakdown(
                bytes_scanned=0,
                bytes_display="0 B",
                cost_usd=0.0,
                cost_display="$0.00",
                exact=False,
                cache_eligible=False,
                cell_type=cell_type_str,
                cost_level="green",
                warnings=[
                    f"Cell classified as '{cell_type_str}'. "
                    "Cost estimation is only available for BigQuery queries. "
                    "For compute cells, cost depends on VM runtime."
                ],
            )
    else:
        estimate_result = estimate_from_sql(sql)

    level = classify_cost_threshold(estimate_result.cost_usd)

    cap_suggestion = None
    if level in (CostLevel.YELLOW, CostLevel.RED) and estimate_result.bytes_scanned > 0:
        cap_bytes = suggest_byte_cap(estimate_result.bytes_scanned)
        cap_cost = bytes_to_cost(cap_bytes)
        cap_suggestion = {
            "cap_bytes": cap_bytes,
            "cap_bytes_display": format_bytes(cap_bytes),
            "cap_cost_usd": round(cap_cost, 4),
        }

    return CostBreakdown(
        bytes_scanned=estimate_result.bytes_scanned,
        bytes_display=estimate_result.bytes_display,
        cost_usd=round(estimate_result.cost_usd, 6),
        cost_display=estimate_result.cost_display,
        exact=False,
        cache_eligible=False,
        cell_type=cell_type.value,
        cost_level=level.value,
        warnings=estimate_result.warnings,
        cap_suggestion=cap_suggestion,
    )


@app.post("/api/optimize", response_model=OptimizationResponse)
def optimize(req: OptimizeRequest):
    sql = req.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Empty SQL")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not configured on server",
        )

    original_estimate = estimate_from_sql(sql)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=OPTIMIZATION_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Optimize this BigQuery SQL query:\n\n{sql}",
                }
            ],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI API error: {exc}")

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    api_cost = (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)

    raw_text = response.content[0].text.strip()
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        return OptimizationResponse(
            original_sql=sql,
            optimized_sql=sql,
            original_bytes=original_estimate.bytes_scanned,
            original_cost=original_estimate.cost_usd,
            optimized_bytes=original_estimate.bytes_scanned,
            optimized_cost=original_estimate.cost_usd,
            savings_bytes=0,
            savings_pct=0.0,
            savings_usd=0.0,
            explanation="",
            confidence="low",
            semantically_equivalent=True,
            semantic_notes="",
            strategies_applied=[],
            api_cost_usd=round(api_cost, 4),
            error=f"Failed to parse AI response",
        )

    optimized_sql = result.get("optimized_sql", sql)
    optimized_estimate = estimate_from_sql(optimized_sql)

    savings_bytes = original_estimate.bytes_scanned - optimized_estimate.bytes_scanned
    savings_pct = (
        (savings_bytes / original_estimate.bytes_scanned * 100)
        if original_estimate.bytes_scanned > 0
        else 0.0
    )

    return OptimizationResponse(
        original_sql=sql,
        optimized_sql=optimized_sql,
        original_bytes=original_estimate.bytes_scanned,
        original_cost=round(original_estimate.cost_usd, 6),
        optimized_bytes=optimized_estimate.bytes_scanned,
        optimized_cost=round(optimized_estimate.cost_usd, 6),
        savings_bytes=savings_bytes,
        savings_pct=round(savings_pct, 1),
        savings_usd=round(original_estimate.cost_usd - optimized_estimate.cost_usd, 6),
        explanation=result.get("explanation", ""),
        confidence=result.get("confidence", "medium"),
        semantically_equivalent=result.get("semantically_equivalent", True),
        semantic_notes=result.get("semantic_notes", ""),
        strategies_applied=result.get("strategies_applied", []),
        api_cost_usd=round(api_cost, 4),
    )


@app.get("/api/tables", response_model=list[TableInfo])
def list_tables():
    tables = []
    for name, columns in CDR_CATALOG.items():
        total = columns.get("_table_total", 0)
        col_count = len([c for c in columns if not c.startswith("_")])
        rows = TABLE_ROW_COUNTS.get(name, 0)
        tables.append(
            TableInfo(
                name=name,
                approx_rows=rows,
                approx_size=format_bytes(total),
                column_count=col_count,
            )
        )
    return sorted(tables, key=lambda t: -CDR_CATALOG[t.name].get("_table_total", 0))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
