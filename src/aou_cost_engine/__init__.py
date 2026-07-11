"""AoU Cost Engine — dry-run-first BigQuery cost estimation for All of Us Research Workbench."""

__version__ = "0.1.0"

from aou_cost_engine.core import estimate_bq_cost, format_bytes
from aou_cost_engine.classifier import classify_cell, CellType
from aou_cost_engine.guardrails import (
    suggest_byte_cap,
    inject_byte_cap,
    classify_cost_threshold,
    CostLevel,
)
from aou_cost_engine.fallback import estimate_from_sql
from aou_cost_engine.optimizer import optimize_query

__all__ = [
    "estimate_bq_cost",
    "format_bytes",
    "classify_cell",
    "CellType",
    "suggest_byte_cap",
    "inject_byte_cap",
    "classify_cost_threshold",
    "CostLevel",
    "estimate_from_sql",
    "optimize_query",
]


def load_ipython_extension(ipython):
    from aou_cost_engine.magic import AouCostMagics

    ipython.register_magics(AouCostMagics)
