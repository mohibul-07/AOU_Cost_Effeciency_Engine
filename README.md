# AoU Cost Engine

Cost estimation engine for the **All of Us Research Workbench** — know what your query costs *before* you run it.

## What it does

- **Exact cost preview** via BigQuery dry run — no guessing, no scanning, no billing
- **Guardrails** — auto-suggest `maximum_bytes_billed` caps to kill runaway queries before they bill
- **AI optimizer** — Claude-powered query rewrites with verified before/after cost (both dry-run confirmed)
- **Notebook-native** — works as an IPython magic (`%%aou_cost`) right where you write code

## Quick Start

```bash
pip install aou-cost-engine
```

In a Jupyter notebook on the AoU Workbench:

```python
%load_ext aou_cost_engine
```

Then add `%%aou_cost` to any cell:

```python
%%aou_cost
SELECT person_id, condition_concept_id, condition_start_date
FROM `condition_occurrence`
WHERE condition_start_date > '2020-01-01'
```

You'll see:
- Exact bytes scanned and estimated cost (color-coded green/yellow/red)
- Cache eligibility badge
- Warnings for costly patterns (SELECT *, LIMIT without WHERE)
- A suggestion to cap the query with `maximum_bytes_billed`

### Enable AI optimization

```python
%aou_cost_config --ai on
```

Or per-cell:

```python
%%aou_cost --ai
SELECT * FROM measurement
```

The optimizer sends your SQL to Claude, gets a cheaper rewrite, and **dry-runs both versions** so the before/after savings are exact — not the AI's guess.

## Configuration

```python
%aou_cost_config --ai on          # Enable AI optimization
%aou_cost_config --threshold 0.05 # Set cost threshold for AI (default $0.10)
%aou_cost_config --auto-cap on    # Auto-inject byte caps
```

## Offline / fallback mode

When no BigQuery client is available (code review, planning), the engine falls back to a static per-column catalog with `sqlglot` parsing. Output is clearly labeled as **approximate**.

```python
%%aou_cost --fallback
SELECT * FROM cb_variant_to_person
```

## How cost works in BigQuery

- Billing is **per column** (columnar storage) — `SELECT *` costs far more than `SELECT person_id`
- Pricing: **$6.25 per TiB** (2^40 bytes) scanned
- 10 MB minimum per query
- `LIMIT` without `WHERE` does **not** reduce cost
- Cached identical queries (24h, unchanged tables) cost $0

## Environment variables

```
ANTHROPIC_API_KEY=sk-ant-...   # Required for AI optimizer
```

## Development

```bash
git clone https://github.com/mohibul-07/aou-cost-engine.git
cd aou-cost-engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT
