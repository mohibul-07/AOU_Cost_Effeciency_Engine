"""Vercel serverless entry point — self-contained FastAPI app.

Inlines all needed logic from the aou_cost_engine package to avoid
path/bundling issues in Vercel's Python runtime.
"""

from __future__ import annotations

import json
import os
import re
from enum import Enum
from typing import Optional

import sqlglot
from sqlglot import exp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants (from core.py)
# ---------------------------------------------------------------------------
BYTES_PER_TIB = 2**40
COST_PER_TIB = 6.25
MIN_BYTES_BILLED = 10 * 1024 * 1024

GB = 1024**3
MB = 1024**2

# ---------------------------------------------------------------------------
# Catalog (from catalog.py)
# ---------------------------------------------------------------------------
CDR_CATALOG = {
    "person": {
        "person_id": 3*MB, "gender_concept_id": 3*MB, "year_of_birth": 3*MB,
        "month_of_birth": 3*MB, "day_of_birth": 3*MB, "birth_datetime": 5*MB,
        "race_concept_id": 3*MB, "ethnicity_concept_id": 3*MB, "location_id": 3*MB,
        "provider_id": 3*MB, "care_site_id": 3*MB, "person_source_value": 8*MB,
        "gender_source_value": 5*MB, "gender_source_concept_id": 3*MB,
        "race_source_value": 5*MB, "race_source_concept_id": 3*MB,
        "ethnicity_source_value": 5*MB, "ethnicity_source_concept_id": 3*MB,
        "_table_total": 200*MB,
    },
    "condition_occurrence": {
        "condition_occurrence_id": 760*MB, "person_id": 760*MB,
        "condition_concept_id": 760*MB, "condition_start_date": 760*MB,
        "condition_start_datetime": int(1.1*GB), "condition_end_date": 760*MB,
        "condition_end_datetime": int(1.1*GB), "condition_type_concept_id": 760*MB,
        "condition_status_concept_id": 760*MB, "stop_reason": 500*MB,
        "provider_id": 760*MB, "visit_occurrence_id": 760*MB,
        "visit_detail_id": 760*MB, "condition_source_value": int(1.5*GB),
        "condition_source_concept_id": 760*MB, "condition_status_source_value": 500*MB,
        "_table_total": 15*GB,
    },
    "measurement": {
        "measurement_id": 20*GB, "person_id": 20*GB, "measurement_concept_id": 20*GB,
        "measurement_date": 20*GB, "measurement_datetime": 30*GB,
        "measurement_time": 15*GB, "measurement_type_concept_id": 20*GB,
        "operator_concept_id": 20*GB, "value_as_number": 20*GB,
        "value_as_concept_id": 20*GB, "unit_concept_id": 20*GB,
        "range_low": 20*GB, "range_high": 20*GB, "provider_id": 20*GB,
        "visit_occurrence_id": 20*GB, "visit_detail_id": 20*GB,
        "measurement_source_value": 40*GB, "measurement_source_concept_id": 20*GB,
        "unit_source_value": 30*GB, "value_source_value": 30*GB,
        "_table_total": 400*GB,
    },
    "cb_variant_to_person": {
        "vid": 100*GB, "person_id": 100*GB, "variant_type": 50*GB,
        "consequence": 80*GB, "aa_change": 60*GB, "contig": 50*GB,
        "position": 100*GB, "ref_allele": 60*GB, "alt_allele": 60*GB,
        "clinical_significance": 80*GB, "gvs_all_ac": 100*GB,
        "gvs_all_an": 100*GB, "gvs_all_af": 100*GB, "gene_symbol": 60*GB,
        "transcript": 80*GB, "_table_total": int(2.2*1024*GB),
    },
    "drug_exposure": {
        "drug_exposure_id": 1600*MB, "person_id": 1600*MB,
        "drug_concept_id": 1600*MB, "drug_exposure_start_date": 1600*MB,
        "drug_exposure_start_datetime": int(2.4*GB), "drug_exposure_end_date": 1600*MB,
        "drug_exposure_end_datetime": int(2.4*GB), "verbatim_end_date": 1600*MB,
        "drug_type_concept_id": 1600*MB, "stop_reason": 1000*MB,
        "refills": 1600*MB, "quantity": 1600*MB, "days_supply": 1600*MB,
        "sig": int(2.5*GB), "route_concept_id": 1600*MB, "lot_number": 500*MB,
        "provider_id": 1600*MB, "visit_occurrence_id": 1600*MB,
        "visit_detail_id": 1600*MB, "drug_source_value": int(3*GB),
        "drug_source_concept_id": 1600*MB, "route_source_value": 1000*MB,
        "dose_unit_source_value": 1000*MB, "_table_total": 30*GB,
    },
    "observation": {
        "observation_id": 5*GB, "person_id": 5*GB, "observation_concept_id": 5*GB,
        "observation_date": 5*GB, "observation_datetime": 7*GB,
        "observation_type_concept_id": 5*GB, "value_as_number": 5*GB,
        "value_as_string": 10*GB, "value_as_concept_id": 5*GB,
        "qualifier_concept_id": 5*GB, "unit_concept_id": 5*GB,
        "provider_id": 5*GB, "visit_occurrence_id": 5*GB, "visit_detail_id": 5*GB,
        "observation_source_value": 8*GB, "observation_source_concept_id": 5*GB,
        "unit_source_value": 5*GB, "qualifier_source_value": 5*GB,
        "_table_total": 80*GB,
    },
    "procedure_occurrence": {
        "procedure_occurrence_id": int(1.2*GB), "person_id": int(1.2*GB),
        "procedure_concept_id": int(1.2*GB), "procedure_date": int(1.2*GB),
        "procedure_datetime": int(1.8*GB), "procedure_type_concept_id": int(1.2*GB),
        "modifier_concept_id": int(1.2*GB), "quantity": int(1.2*GB),
        "provider_id": int(1.2*GB), "visit_occurrence_id": int(1.2*GB),
        "visit_detail_id": int(1.2*GB), "procedure_source_value": int(2*GB),
        "procedure_source_concept_id": int(1.2*GB), "modifier_source_value": 800*MB,
        "_table_total": 18*GB,
    },
}

TABLE_ROW_COUNTS = {
    "person": 415_000, "condition_occurrence": 95_000_000,
    "measurement": 2_500_000_000, "cb_variant_to_person": 12_000_000_000,
    "drug_exposure": 200_000_000, "observation": 600_000_000,
    "procedure_occurrence": 120_000_000,
}

CDR_TABLES = {
    "person", "condition_occurrence", "measurement", "cb_variant_to_person",
    "drug_exposure", "observation", "procedure_occurrence", "visit_occurrence",
    "death", "device_exposure", "observation_period", "specimen", "concept",
    "concept_ancestor", "concept_relationship",
}

# ---------------------------------------------------------------------------
# Helpers (from core.py, catalog.py, classifier.py, guardrails.py)
# ---------------------------------------------------------------------------

def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"

def bytes_to_cost(bytes_scanned: int) -> float:
    billable = max(bytes_scanned, MIN_BYTES_BILLED)
    return (billable / BYTES_PER_TIB) * COST_PER_TIB

def get_column_bytes(table: str, column: str):
    t = CDR_CATALOG.get(table.lower().split(".")[-1])
    return t.get(column.lower()) if t else None

def get_table_total(table: str):
    t = CDR_CATALOG.get(table.lower().split(".")[-1])
    return t.get("_table_total") if t else None


class CellType(Enum):
    BIGQUERY = "bigquery"
    COMPUTE = "compute"
    IO = "io"
    UNKNOWN = "unknown"

BQ_MAGIC_PATTERN = re.compile(r"^\s*%%bigquery\b", re.MULTILINE)
READ_GBQ_PATTERN = re.compile(r"\bread_gbq\s*\(")
CLIENT_QUERY_PATTERN = re.compile(r"\.query\s*\(")
SQL_KEYWORDS = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE\s+TABLE|MERGE|WITH)\b", re.IGNORECASE
)
CDR_REF_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in CDR_TABLES) + r")\b", re.IGNORECASE
)
IO_PATTERN = re.compile(
    r"\b(read_csv|to_csv|read_parquet|to_parquet|read_json|to_json|open\s*\(|"
    r"write_disposition|\.save\s*\(|\.to_gbq\s*\(|\.extract_table\s*\()", re.IGNORECASE
)
HIGH_COMPUTE = re.compile(
    r"\b(\.fit\s*\(|\.train\s*\(|GridSearchCV|cross_val|\.predict\s*\()", re.IGNORECASE
)
MEDIUM_COMPUTE = re.compile(
    r"\b(\.merge\s*\(|\.groupby\s*\(|\.apply\s*\(|\.pivot|\.resample|\.rolling)", re.IGNORECASE
)
LOW_COMPUTE = re.compile(
    r"\b(\.plot\s*\(|\.hist\s*\(|\.describe\s*\(|print\s*\(|display\s*\()", re.IGNORECASE
)

def classify_cell(code: str) -> CellType:
    if BQ_MAGIC_PATTERN.search(code):
        return CellType.BIGQUERY
    if READ_GBQ_PATTERN.search(code):
        return CellType.BIGQUERY
    if CLIENT_QUERY_PATTERN.search(code) and (SQL_KEYWORDS.search(code) or CDR_REF_PATTERN.search(code)):
        return CellType.BIGQUERY
    if SQL_KEYWORDS.search(code) and CDR_REF_PATTERN.search(code):
        return CellType.BIGQUERY
    if IO_PATTERN.search(code):
        return CellType.IO
    if HIGH_COMPUTE.search(code) or MEDIUM_COMPUTE.search(code) or LOW_COMPUTE.search(code):
        return CellType.COMPUTE
    return CellType.UNKNOWN

def extract_sql(code: str):
    bq_match = BQ_MAGIC_PATTERN.search(code)
    if bq_match:
        lines = code.split("\n")
        sql_lines = [line for line in lines if not BQ_MAGIC_PATTERN.match(line)]
        sql = "\n".join(sql_lines).strip()
        return sql if sql else None
    triple_quote = re.search(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', code, re.DOTALL)
    if triple_quote:
        sql = (triple_quote.group(1) or triple_quote.group(2)).strip()
        if SQL_KEYWORDS.match(sql):
            return sql
    single_quote = re.search(r'"([^"]*(?:SELECT|WITH)[^"]*)"', code, re.IGNORECASE)
    if single_quote:
        return single_quote.group(1).strip()
    if SQL_KEYWORDS.match(code.strip()):
        return code.strip()
    return None


class CostLevel(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"

def classify_cost_threshold(cost_usd: float) -> CostLevel:
    if cost_usd < 0.01:
        return CostLevel.GREEN
    if cost_usd <= 0.50:
        return CostLevel.YELLOW
    return CostLevel.RED

def suggest_byte_cap(bytes_scanned: int, headroom: float = 1.2) -> int:
    return int(bytes_scanned * headroom)


# ---------------------------------------------------------------------------
# Fallback estimator (from fallback.py)
# ---------------------------------------------------------------------------
UNNEST_MULTIPLIER = 10

class CostEstimate:
    def __init__(self, bytes_scanned, cost_usd, exact, cache_eligible=False, warnings=None, error=None):
        self.bytes_scanned = bytes_scanned
        self.cost_usd = cost_usd
        self.exact = exact
        self.cache_eligible = cache_eligible
        self.warnings = warnings or []
        self.error = error

    @property
    def bytes_display(self) -> str:
        return format_bytes(self.bytes_scanned)

    @property
    def cost_display(self) -> str:
        if self.cost_usd < 0.01:
            return f"${self.cost_usd:.4f}"
        return f"${self.cost_usd:.2f}"


def parse_sql(sql: str):
    tables, columns = [], {}
    has_select_star = has_limit = has_where = has_unnest = has_cross_join_unnest = False
    try:
        parsed = sqlglot.parse_one(sql, read="bigquery")
    except sqlglot.errors.ParseError:
        return tables, columns, has_select_star, has_limit, has_where, has_cross_join_unnest

    for table in parsed.find_all(exp.Table):
        name = table.name
        if table.db:
            name = f"{table.db}.{name}"
        if name and name not in tables:
            tables.append(name)

    for select in parsed.find_all(exp.Select):
        for expr in select.expressions:
            if isinstance(expr, exp.Star):
                has_select_star = True
            elif isinstance(expr, exp.Column):
                table_name = expr.table or ""
                columns.setdefault(table_name, []).append(expr.name)

    has_limit = parsed.find(exp.Limit) is not None
    has_where = parsed.find(exp.Where) is not None
    sql_upper = sql.upper()
    has_unnest = "UNNEST" in sql_upper
    has_cross_join_unnest = "CROSS JOIN" in sql_upper and "UNNEST" in sql_upper

    return tables, columns, has_select_star, has_limit, has_where, has_cross_join_unnest


def estimate_from_sql(sql: str) -> CostEstimate:
    tables, columns, has_select_star, has_limit, has_where, has_cross_join_unnest = parse_sql(sql)
    warnings = []

    if not tables:
        return CostEstimate(bytes_scanned=0, cost_usd=0.0, exact=False,
                            warnings=["No tables detected in query — cannot estimate cost."])

    total_bytes = 0
    for table in tables:
        table_key = table.lower().split(".")[-1]
        if table_key not in CDR_CATALOG:
            warnings.append(f"Table '{table}' not in catalog — excluded from estimate.")
            continue
        if has_select_star:
            tt = get_table_total(table_key)
            if tt:
                total_bytes += tt
            warnings.append(f"SELECT * on '{table}' scans all columns — consider selecting only needed columns.")
        else:
            table_columns = columns.get("", []) + columns.get(table_key, [])
            if not table_columns:
                tt = get_table_total(table_key)
                if tt:
                    total_bytes += tt
            else:
                for col in table_columns:
                    cb = get_column_bytes(table_key, col)
                    if cb:
                        total_bytes += cb
                    else:
                        warnings.append(f"Column '{col}' not in catalog for '{table}' — excluded.")

    if has_cross_join_unnest:
        total_bytes *= UNNEST_MULTIPLIER
        warnings.append(f"CROSS JOIN UNNEST detected — estimate multiplied by {UNNEST_MULTIPLIER}×.")

    if has_limit and not has_where:
        warnings.append("LIMIT without WHERE does not reduce bytes scanned — BigQuery performs a full scan before applying the limit.")

    if not has_where:
        warnings.append("No WHERE clause — partition/cluster pruning cannot reduce cost. If the table is partitioned, adding a date filter may cut cost significantly.")
    else:
        warnings.append("Partition/cluster pruning from WHERE clause may reduce actual cost below this estimate — use dry run for exact numbers.")

    warnings.append("This is an approximate estimate from the static catalog. Use dry run (in-notebook) for exact numbers.")

    return CostEstimate(bytes_scanned=total_bytes, cost_usd=bytes_to_cost(total_bytes), exact=False, warnings=warnings)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="AoU Cost Engine", version="0.1.0")

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
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    return {
        "status": "ok",
        "version": "0.1.0",
        "anthropic_key_set": bool(api_key),
        "anthropic_key_prefix": api_key[:10] + "..." if api_key else "NOT SET",
    }


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
                bytes_scanned=0, bytes_display="0 B", cost_usd=0.0,
                cost_display="$0.00", exact=False, cache_eligible=False,
                cell_type=cell_type_str, cost_level="green",
                warnings=[f"Cell classified as '{cell_type_str}'. Cost estimation is only available for BigQuery queries."],
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
        exact=False, cache_eligible=False,
        cell_type=cell_type.value, cost_level=level.value,
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
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured on server")

    original_estimate = estimate_from_sql(sql)

    try:
        import httpx
        with httpx.Client(timeout=25.0) as http_client:
            api_response = http_client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 2048,
                    "system": OPTIMIZATION_PROMPT,
                    "messages": [{"role": "user", "content": f"Optimize this BigQuery SQL query:\n\n{sql}"}],
                },
            )
        if api_response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Anthropic API {api_response.status_code}: {api_response.text[:300]}")
        response_data = api_response.json()
        raw_text = response_data["content"][0]["text"].strip()
        input_tokens = response_data["usage"]["input_tokens"]
        output_tokens = response_data["usage"]["output_tokens"]
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        raise HTTPException(status_code=500, detail=f"AI API error: {type(exc).__name__}: {exc}\n{traceback.format_exc()[-500:]}")

    api_cost = (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)

    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if json_match:
        raw_text = json_match.group(0)

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        return OptimizationResponse(
            original_sql=sql, optimized_sql=sql,
            original_bytes=original_estimate.bytes_scanned,
            original_cost=original_estimate.cost_usd,
            optimized_bytes=original_estimate.bytes_scanned,
            optimized_cost=original_estimate.cost_usd,
            savings_bytes=0, savings_pct=0.0, savings_usd=0.0,
            explanation="", confidence="low",
            semantically_equivalent=True, semantic_notes="",
            strategies_applied=[], api_cost_usd=round(api_cost, 4),
            error="Failed to parse AI response",
        )

    optimized_sql = result.get("optimized_sql", sql)
    optimized_estimate = estimate_from_sql(optimized_sql)

    savings_bytes = original_estimate.bytes_scanned - optimized_estimate.bytes_scanned
    savings_pct = (savings_bytes / original_estimate.bytes_scanned * 100) if original_estimate.bytes_scanned > 0 else 0.0

    return OptimizationResponse(
        original_sql=sql, optimized_sql=optimized_sql,
        original_bytes=original_estimate.bytes_scanned,
        original_cost=round(original_estimate.cost_usd, 6),
        optimized_bytes=optimized_estimate.bytes_scanned,
        optimized_cost=round(optimized_estimate.cost_usd, 6),
        savings_bytes=savings_bytes, savings_pct=round(savings_pct, 1),
        savings_usd=round(original_estimate.cost_usd - optimized_estimate.cost_usd, 6),
        explanation=result.get("explanation") or "",
        confidence=result.get("confidence") or "medium",
        semantically_equivalent=result.get("semantically_equivalent", True),
        semantic_notes=result.get("semantic_notes") or "",
        strategies_applied=result.get("strategies_applied") or [],
        api_cost_usd=round(api_cost, 4),
    )


@app.get("/api/tables", response_model=list[TableInfo])
def list_tables():
    tables = []
    for name, columns in CDR_CATALOG.items():
        total = columns.get("_table_total", 0)
        col_count = len([c for c in columns if not c.startswith("_")])
        rows = TABLE_ROW_COUNTS.get(name, 0)
        tables.append(TableInfo(name=name, approx_rows=rows, approx_size=format_bytes(total), column_count=col_count))
    return sorted(tables, key=lambda t: -CDR_CATALOG[t.name].get("_table_total", 0))
