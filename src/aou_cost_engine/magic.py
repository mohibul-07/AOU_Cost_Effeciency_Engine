"""IPython magics for AoU Cost Engine.

Usage in a Jupyter notebook:
    %load_ext aou_cost_engine

    %%aou_cost
    SELECT person_id, condition_concept_id
    FROM `condition_occurrence`
    WHERE condition_start_date > '2020-01-01'

    %aou_cost_config --threshold 0.05 --ai on
"""

from __future__ import annotations

from IPython.core.magic import Magics, cell_magic, line_magic, magics_class
from IPython.core.magic_arguments import (
    argument,
    magic_arguments,
    parse_argstring,
)

from aou_cost_engine.classifier import CellType, classify_cell, extract_sql
from aou_cost_engine.core import CostEstimate, estimate_bq_cost
from aou_cost_engine.display import display_estimate, display_optimization
from aou_cost_engine.fallback import estimate_from_sql
from aou_cost_engine.guardrails import (
    CostLevel,
    classify_cost_threshold,
    format_byte_cap_suggestion,
    suggest_byte_cap,
)
from aou_cost_engine.optimizer import optimize_query


@magics_class
class AouCostMagics(Magics):
    def __init__(self, shell):
        super().__init__(shell)
        self._ai_enabled = False
        self._cost_threshold = 0.10
        self._auto_cap = False

    def _get_bq_client(self):
        ns = self.shell.user_ns
        for name in ("client", "bq_client", "bigquery_client"):
            obj = ns.get(name)
            if obj is not None and hasattr(obj, "query"):
                return obj
        from google.cloud import bigquery
        try:
            return bigquery.Client()
        except Exception:
            return None

    def _get_anthropic_client(self):
        ns = self.shell.user_ns
        for name in ("anthropic_client", "ai_client"):
            obj = ns.get(name)
            if obj is not None and hasattr(obj, "messages"):
                return obj
        try:
            import anthropic
            return anthropic.Anthropic()
        except Exception:
            return None

    @cell_magic
    @magic_arguments()
    @argument("--ai", action="store_true", help="Enable AI optimization for this cell")
    @argument("--no-ai", action="store_true", help="Disable AI optimization for this cell")
    @argument("--cap", action="store_true", help="Auto-inject maximum_bytes_billed")
    @argument("--threshold", type=float, help="Cost threshold for AI optimization (USD)")
    @argument("--fallback", action="store_true", help="Force catalog fallback (no dry run)")
    def aou_cost(self, line, cell):
        """Estimate the cost of a notebook cell before running it."""
        args = parse_argstring(self.aou_cost, line)

        code = cell.strip()
        cell_type = classify_cell(code)

        if cell_type != CellType.BIGQUERY:
            from IPython.display import display, HTML
            display(HTML(
                '<div style="padding:8px;background:#e2e3e5;border-radius:4px;font-size:13px">'
                f'Cell classified as <strong>{cell_type.value}</strong> — '
                'cost estimation is only available for BigQuery cells. '
                'For compute cells, cost depends on VM runtime (not estimable pre-execution).'
                '</div>'
            ))
            return

        sql = extract_sql(code)
        if not sql:
            sql = code

        use_ai = args.ai or (self._ai_enabled and not args.no_ai)
        threshold = args.threshold if args.threshold is not None else self._cost_threshold

        if args.fallback:
            estimate = estimate_from_sql(sql)
        else:
            bq_client = self._get_bq_client()
            if bq_client is not None:
                estimate = estimate_bq_cost(sql, bq_client)
                if estimate.error:
                    estimate = estimate_from_sql(sql)
                    estimate.warnings.insert(0, f"Dry run failed, using catalog fallback: {estimate.error or 'unknown error'}")
            else:
                estimate = estimate_from_sql(sql)
                estimate.warnings.insert(0, "No BigQuery client found — using approximate catalog estimate.")

        display_estimate(estimate)

        level = classify_cost_threshold(estimate.cost_usd)
        if level in (CostLevel.YELLOW, CostLevel.RED) and estimate.bytes_scanned > 0:
            from IPython.display import display, HTML
            suggestion = format_byte_cap_suggestion(estimate.bytes_scanned, estimate.cost_usd)
            display(HTML(
                f'<div style="padding:8px;background:#fff3cd;border-radius:4px;font-size:13px;margin:4px 0">'
                f'{suggestion}'
                f'</div>'
            ))

        if use_ai and estimate.cost_usd >= threshold and not estimate.error:
            bq_client = self._get_bq_client()
            anthropic_client = self._get_anthropic_client()
            if bq_client and anthropic_client:
                result = optimize_query(
                    sql, bq_client, anthropic_client, cost_threshold=threshold
                )
                if not result.skipped and not result.error:
                    display_optimization(
                        original_bytes=result.original_estimate.bytes_scanned,
                        optimized_bytes=result.optimized_estimate.bytes_scanned,
                        original_cost=result.original_estimate.cost_usd,
                        optimized_cost=result.optimized_estimate.cost_usd,
                        optimized_sql=result.optimized_sql,
                        explanation=result.explanation,
                        confidence=result.confidence,
                        semantically_equivalent=result.semantically_equivalent,
                        api_cost=result.api_cost_usd,
                    )
                elif result.error:
                    from IPython.display import display, HTML
                    display(HTML(
                        f'<div style="padding:8px;background:#f8d7da;border-radius:4px;font-size:13px">'
                        f'AI optimization error: {result.error}'
                        f'</div>'
                    ))

    @line_magic
    @magic_arguments()
    @argument("--ai", choices=["on", "off"], help="Enable/disable AI optimization")
    @argument("--threshold", type=float, help="Cost threshold for AI (USD)")
    @argument("--auto-cap", choices=["on", "off"], help="Auto-inject byte caps")
    def aou_cost_config(self, line):
        """Configure AoU Cost Engine settings."""
        args = parse_argstring(self.aou_cost_config, line)

        if args.ai:
            self._ai_enabled = args.ai == "on"
        if args.threshold is not None:
            self._cost_threshold = args.threshold
        if args.auto_cap:
            self._auto_cap = args.auto_cap == "on"

        from IPython.display import display, HTML
        display(HTML(
            '<div style="padding:8px;background:#d4edda;border-radius:4px;font-size:13px">'
            f'AoU Cost Engine config updated: '
            f'AI={"on" if self._ai_enabled else "off"}, '
            f'threshold=${self._cost_threshold:.2f}, '
            f'auto-cap={"on" if self._auto_cap else "off"}'
            '</div>'
        ))
