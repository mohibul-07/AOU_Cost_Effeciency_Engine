"""Cell type classification for AoU notebook cells."""

from __future__ import annotations

import re
from enum import Enum


class CellType(Enum):
    BIGQUERY = "bigquery"
    COMPUTE = "compute"
    IO = "io"
    UNKNOWN = "unknown"


class ComputeTier(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


CDR_TABLES = {
    "person",
    "condition_occurrence",
    "measurement",
    "cb_variant_to_person",
    "drug_exposure",
    "observation",
    "procedure_occurrence",
    "visit_occurrence",
    "death",
    "device_exposure",
    "observation_period",
    "specimen",
    "concept",
    "concept_ancestor",
    "concept_relationship",
}

BQ_MAGIC_PATTERN = re.compile(r"^\s*%%bigquery\b", re.MULTILINE)
READ_GBQ_PATTERN = re.compile(r"\bread_gbq\s*\(")
CLIENT_QUERY_PATTERN = re.compile(r"\.query\s*\(")
SQL_KEYWORDS = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE\s+TABLE|MERGE|WITH)\b", re.IGNORECASE
)
CDR_REF_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in CDR_TABLES) + r")\b", re.IGNORECASE
)

HIGH_COMPUTE = re.compile(
    r"\b(\.fit\s*\(|\.train\s*\(|GridSearchCV|cross_val|\.predict\s*\()", re.IGNORECASE
)
MEDIUM_COMPUTE = re.compile(
    r"\b(\.merge\s*\(|\.groupby\s*\(|\.apply\s*\(|\.pivot|\.resample|\.rolling)",
    re.IGNORECASE,
)
LOW_COMPUTE = re.compile(
    r"\b(\.plot\s*\(|\.hist\s*\(|\.describe\s*\(|print\s*\(|display\s*\()",
    re.IGNORECASE,
)
IO_PATTERN = re.compile(
    r"\b(read_csv|to_csv|read_parquet|to_parquet|read_json|to_json|open\s*\(|"
    r"write_disposition|\.save\s*\(|\.to_gbq\s*\(|\.extract_table\s*\()",
    re.IGNORECASE,
)


def classify_cell(code: str) -> CellType:
    if BQ_MAGIC_PATTERN.search(code):
        return CellType.BIGQUERY
    if READ_GBQ_PATTERN.search(code):
        return CellType.BIGQUERY
    if CLIENT_QUERY_PATTERN.search(code) and (
        SQL_KEYWORDS.search(code) or CDR_REF_PATTERN.search(code)
    ):
        return CellType.BIGQUERY
    if SQL_KEYWORDS.search(code) and CDR_REF_PATTERN.search(code):
        return CellType.BIGQUERY
    if IO_PATTERN.search(code):
        return CellType.IO
    if HIGH_COMPUTE.search(code) or MEDIUM_COMPUTE.search(code) or LOW_COMPUTE.search(code):
        return CellType.COMPUTE
    return CellType.UNKNOWN


def estimate_compute_tier(code: str) -> ComputeTier:
    if HIGH_COMPUTE.search(code):
        return ComputeTier.HIGH
    if MEDIUM_COMPUTE.search(code):
        return ComputeTier.MEDIUM
    return ComputeTier.LOW


def extract_sql(code: str) -> str | None:
    """Try to extract a SQL string from a code cell."""
    bq_match = BQ_MAGIC_PATTERN.search(code)
    if bq_match:
        lines = code.split("\n")
        sql_lines = []
        for line in lines:
            if BQ_MAGIC_PATTERN.match(line):
                continue
            sql_lines.append(line)
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
