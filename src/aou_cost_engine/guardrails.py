"""Cost guardrails — byte caps, threshold warnings, and protective checks."""

from __future__ import annotations

import re
from enum import Enum

from aou_cost_engine.core import BYTES_PER_TIB, COST_PER_TIB, bytes_to_cost


class CostLevel(Enum):
    GREEN = "green"    # < $0.01
    YELLOW = "yellow"  # $0.01 – $0.50
    RED = "red"        # > $0.50


THRESHOLDS = {
    CostLevel.GREEN: 0.01,
    CostLevel.YELLOW: 0.50,
}


def classify_cost_threshold(cost_usd: float) -> CostLevel:
    if cost_usd < THRESHOLDS[CostLevel.GREEN]:
        return CostLevel.GREEN
    if cost_usd <= THRESHOLDS[CostLevel.YELLOW]:
        return CostLevel.YELLOW
    return CostLevel.RED


def suggest_byte_cap(bytes_scanned: int, headroom: float = 1.2) -> int:
    """Suggest a maximum_bytes_billed value with headroom above actual scan."""
    return int(bytes_scanned * headroom)


def format_byte_cap_suggestion(bytes_scanned: int, cost_usd: float) -> str:
    cap = suggest_byte_cap(bytes_scanned)
    cap_cost = bytes_to_cost(cap)
    from aou_cost_engine.core import format_bytes

    return (
        f"This query scans ~{format_bytes(bytes_scanned)} (~{cost_usd:.2f}). "
        f"Add maximum_bytes_billed cap at {format_bytes(cap)} "
        f"(~${cap_cost:.2f}) to prevent overruns?"
    )


def inject_byte_cap(code: str, cap_bytes: int) -> str:
    """Inject maximum_bytes_billed into BigQuery job configuration in code.

    Handles three patterns:
    1. %%bigquery magic — adds --maximum_bytes_billed flag
    2. QueryJobConfig() — adds maximum_bytes_billed parameter
    3. client.query() without config — wraps with a job config
    """
    if re.match(r"\s*%%bigquery", code):
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("%%bigquery"):
                if "--maximum_bytes_billed" not in line:
                    lines[i] = f"{line.rstrip()} --maximum_bytes_billed {cap_bytes}"
                break
        return "\n".join(lines)

    config_pattern = re.compile(
        r"(QueryJobConfig\s*\()([^)]*)\)", re.DOTALL
    )
    match = config_pattern.search(code)
    if match:
        if "maximum_bytes_billed" not in match.group(0):
            existing_args = match.group(2).strip()
            if existing_args:
                new_args = f"{existing_args}, maximum_bytes_billed={cap_bytes}"
            else:
                new_args = f"maximum_bytes_billed={cap_bytes}"
            return code[: match.start()] + f"QueryJobConfig({new_args})" + code[match.end() :]
        return code

    query_pattern = re.compile(r"(\.query\s*\(\s*)(.*?)(\s*\))", re.DOTALL)
    match = query_pattern.search(code)
    if match:
        existing = match.group(2).strip()
        injection = (
            f"from google.cloud.bigquery import QueryJobConfig\n"
            f"_cost_cap_config = QueryJobConfig(maximum_bytes_billed={cap_bytes})\n"
        )
        new_call = f"{match.group(1)}{existing}, job_config=_cost_cap_config{match.group(3)}"
        return injection + code[: match.start()] + new_call + code[match.end() :]

    return code


def detect_limit_without_where(sql: str) -> bool:
    sql_upper = sql.upper()
    return "LIMIT" in sql_upper and "WHERE" not in sql_upper


def detect_select_star(sql: str) -> bool:
    return bool(re.search(r"SELECT\s+\*", sql, re.IGNORECASE))


def generate_warnings(
    sql: str, bytes_scanned: int, cost_usd: float
) -> list[str]:
    warnings = []
    level = classify_cost_threshold(cost_usd)

    if level == CostLevel.RED:
        warnings.append(
            f"HIGH COST: This query will scan ~{bytes_scanned:,} bytes (~${cost_usd:.2f}). "
            "Consider adding filters or selecting fewer columns."
        )

    if detect_select_star(sql):
        warnings.append(
            "SELECT * scans all columns. BigQuery billing is columnar — "
            "selecting only needed columns can dramatically reduce cost."
        )

    if detect_limit_without_where(sql):
        warnings.append(
            "LIMIT without WHERE does not reduce cost — "
            "BigQuery performs a full column scan before applying LIMIT."
        )

    return warnings
