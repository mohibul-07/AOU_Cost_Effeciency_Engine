"""Offline fallback estimator using sqlglot + static catalog.

All output from this module is approximate and clearly labeled as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from aou_cost_engine.catalog import (
    CDR_CATALOG,
    get_column_bytes,
    get_table_total,
)
from aou_cost_engine.core import CostEstimate, bytes_to_cost


@dataclass
class ParsedQuery:
    tables: list[str] = field(default_factory=list)
    columns: dict[str, list[str]] = field(default_factory=dict)
    has_select_star: bool = False
    has_limit: bool = False
    has_where: bool = False
    has_unnest: bool = False
    has_cross_join_unnest: bool = False
    has_approx_functions: bool = False
    subquery_count: int = 0


def parse_sql(sql: str) -> ParsedQuery:
    result = ParsedQuery()
    try:
        parsed = sqlglot.parse_one(sql, read="bigquery")
    except sqlglot.errors.ParseError:
        return result

    for table in parsed.find_all(exp.Table):
        name = table.name
        if table.db:
            name = f"{table.db}.{name}"
        if table.catalog:
            name = f"{table.catalog}.{name}"
        if name and name not in result.tables:
            result.tables.append(name)

    for select in parsed.find_all(exp.Select):
        for expr in select.expressions:
            if isinstance(expr, exp.Star):
                result.has_select_star = True
            elif isinstance(expr, exp.Column):
                table_name = expr.table or ""
                col_name = expr.name
                result.columns.setdefault(table_name, []).append(col_name)

    result.has_limit = parsed.find(exp.Limit) is not None
    result.has_where = parsed.find(exp.Where) is not None

    sql_upper = sql.upper()
    result.has_unnest = "UNNEST" in sql_upper
    result.has_cross_join_unnest = "CROSS JOIN" in sql_upper and "UNNEST" in sql_upper

    for func in parsed.find_all(exp.Anonymous):
        if func.name.upper().startswith("APPROX_"):
            result.has_approx_functions = True
            break

    result.subquery_count = len(list(parsed.find_all(exp.Subquery)))

    return result


UNNEST_MULTIPLIER = 10


def estimate_from_sql(sql: str) -> CostEstimate:
    """Estimate query cost using static catalog. Always approximate."""
    parsed = parse_sql(sql)
    warnings: list[str] = []

    if not parsed.tables:
        return CostEstimate(
            bytes_scanned=0,
            cost_usd=0.0,
            exact=False,
            warnings=["No tables detected in query — cannot estimate cost."],
        )

    total_bytes = 0

    for table in parsed.tables:
        table_key = table.lower().split(".")[-1]

        if table_key not in CDR_CATALOG:
            warnings.append(
                f"Table '{table}' not in catalog — excluded from estimate."
            )
            continue

        if parsed.has_select_star:
            table_total = get_table_total(table_key)
            if table_total:
                total_bytes += table_total
            warnings.append(
                f"SELECT * on '{table}' scans all columns — "
                "consider selecting only needed columns."
            )
        else:
            table_columns = parsed.columns.get("", []) + parsed.columns.get(
                table_key, []
            )
            if not table_columns:
                table_total = get_table_total(table_key)
                if table_total:
                    total_bytes += table_total
            else:
                col_bytes = 0
                for col in table_columns:
                    cb = get_column_bytes(table_key, col)
                    if cb:
                        col_bytes += cb
                    else:
                        warnings.append(
                            f"Column '{col}' not in catalog for '{table}' — excluded."
                        )
                total_bytes += col_bytes

    if parsed.has_cross_join_unnest:
        total_bytes *= UNNEST_MULTIPLIER
        warnings.append(
            f"CROSS JOIN UNNEST detected — estimate multiplied by {UNNEST_MULTIPLIER}× "
            "(actual expansion depends on array cardinality)."
        )

    if parsed.has_limit and not parsed.has_where:
        warnings.append(
            "LIMIT without WHERE does not reduce bytes scanned — "
            "BigQuery performs a full scan before applying the limit."
        )

    if not parsed.has_where:
        warnings.append(
            "No WHERE clause — partition/cluster pruning cannot reduce cost. "
            "If the table is partitioned, adding a date filter may cut cost significantly."
        )
    else:
        warnings.append(
            "Partition/cluster pruning from WHERE clause may reduce actual cost "
            "below this estimate — use dry run for exact numbers."
        )

    warnings.append(
        "This is an approximate estimate from the static catalog. "
        "Use dry run (in-notebook) for exact numbers."
    )

    return CostEstimate(
        bytes_scanned=total_bytes,
        cost_usd=bytes_to_cost(total_bytes),
        exact=False,
        warnings=warnings,
    )
