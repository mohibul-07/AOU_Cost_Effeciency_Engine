"""Dry-run-first BigQuery cost estimation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

BYTES_PER_TIB = 2**40
COST_PER_TIB = 6.25
MIN_BYTES_BILLED = 10 * 1024 * 1024  # 10 MB per-query minimum


@dataclass
class CostEstimate:
    bytes_scanned: int
    cost_usd: float
    exact: bool
    cache_eligible: bool = False
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def bytes_display(self) -> str:
        return format_bytes(self.bytes_scanned)

    @property
    def cost_display(self) -> str:
        if self.cost_usd < 0.01:
            return f"${self.cost_usd:.4f}"
        return f"${self.cost_usd:.2f}"


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"


def bytes_to_cost(bytes_scanned: int) -> float:
    billable = max(bytes_scanned, MIN_BYTES_BILLED)
    tib = billable / BYTES_PER_TIB
    return tib * COST_PER_TIB


def estimate_bq_cost(
    sql: str,
    client,
    *,
    check_cache: bool = True,
) -> CostEstimate:
    """Run a BigQuery dry run and return exact cost estimate.

    Args:
        sql: The SQL query to estimate.
        client: An authenticated BigQuery client.
        check_cache: If True, also check whether the query is cache-eligible.
    """
    try:
        from google.cloud import bigquery

        worst_case_job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                dry_run=True,
                use_query_cache=False,
            ),
        )
        bytes_scanned = worst_case_job.total_bytes_processed

        cache_eligible = False
        if check_cache:
            cached_job = client.query(
                sql,
                job_config=bigquery.QueryJobConfig(dry_run=True),
            )
            cache_eligible = cached_job.total_bytes_processed == 0

        warnings = []
        sql_upper = sql.upper()
        if "LIMIT" in sql_upper and "WHERE" not in sql_upper:
            warnings.append(
                "LIMIT without WHERE does not reduce bytes scanned — "
                "BigQuery performs a full scan before applying the limit."
            )

        return CostEstimate(
            bytes_scanned=bytes_scanned,
            cost_usd=bytes_to_cost(bytes_scanned),
            exact=True,
            cache_eligible=cache_eligible,
            warnings=warnings,
        )
    except Exception as exc:
        return CostEstimate(
            bytes_scanned=0,
            cost_usd=0.0,
            exact=False,
            error=f"Dry run failed: {exc}",
        )
