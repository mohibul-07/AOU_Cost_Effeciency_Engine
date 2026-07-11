"""Rich notebook display formatting for cost estimates."""

from __future__ import annotations

from IPython.display import HTML, display

from aou_cost_engine.core import CostEstimate, format_bytes
from aou_cost_engine.guardrails import CostLevel, classify_cost_threshold


COLORS = {
    CostLevel.GREEN: {"bg": "#d4edda", "border": "#28a745", "text": "#155724"},
    CostLevel.YELLOW: {"bg": "#fff3cd", "border": "#ffc107", "text": "#856404"},
    CostLevel.RED: {"bg": "#f8d7da", "border": "#dc3545", "text": "#721c24"},
}

BADGE_LABELS = {
    CostLevel.GREEN: "LOW COST",
    CostLevel.YELLOW: "MODERATE COST",
    CostLevel.RED: "HIGH COST",
}


def _css() -> str:
    return """
    <style>
    .aou-cost-container {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
        font-size: 14px;
        line-height: 1.5;
    }
    .aou-cost-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }
    .aou-cost-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }
    .aou-cost-exact {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        background: #e2e3e5;
        color: #383d41;
    }
    .aou-cost-cache {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        background: #cce5ff;
        color: #004085;
    }
    .aou-cost-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
        margin-bottom: 12px;
    }
    .aou-cost-stat {
        text-align: center;
    }
    .aou-cost-stat-value {
        font-size: 24px;
        font-weight: 700;
    }
    .aou-cost-stat-label {
        font-size: 11px;
        text-transform: uppercase;
        opacity: 0.7;
    }
    .aou-cost-warnings {
        margin-top: 12px;
        padding: 8px 12px;
        background: rgba(0,0,0,0.05);
        border-radius: 4px;
        font-size: 13px;
    }
    .aou-cost-warning-item {
        margin: 4px 0;
    }
    .aou-cost-error {
        background: #f8d7da;
        border: 1px solid #dc3545;
        color: #721c24;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
    }
    .aou-cost-cap-btn {
        display: inline-block;
        margin-top: 8px;
        padding: 6px 16px;
        border-radius: 4px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
    }
    .aou-opt-container {
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 16px;
        margin: 8px 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .aou-opt-header {
        font-size: 16px;
        font-weight: 700;
        margin-bottom: 12px;
    }
    .aou-opt-savings {
        font-size: 20px;
        font-weight: 700;
        color: #28a745;
        margin-bottom: 8px;
    }
    .aou-opt-meta {
        font-size: 12px;
        color: #6c757d;
        margin-bottom: 12px;
    }
    .aou-opt-diff {
        background: #f8f9fa;
        border-radius: 4px;
        padding: 12px;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 13px;
        white-space: pre-wrap;
        overflow-x: auto;
        margin-bottom: 12px;
    }
    .aou-opt-explanation {
        font-size: 13px;
        margin-bottom: 8px;
    }
    </style>
    """


def render_estimate(estimate: CostEstimate) -> str:
    if estimate.error:
        return f"""
        {_css()}
        <div class="aou-cost-error">
            <strong>Cost Estimation Error</strong><br>
            {estimate.error}
        </div>
        """

    level = classify_cost_threshold(estimate.cost_usd)
    colors = COLORS[level]
    badge = BADGE_LABELS[level]

    exact_badge = (
        '<span class="aou-cost-exact">EXACT (dry run)</span>'
        if estimate.exact
        else '<span class="aou-cost-exact">APPROXIMATE (catalog)</span>'
    )

    cache_badge = ""
    if estimate.cache_eligible:
        cache_badge = '<span class="aou-cost-cache">CACHE ELIGIBLE ($0)</span>'

    warnings_html = ""
    if estimate.warnings:
        items = "".join(
            f'<div class="aou-cost-warning-item">&#9888; {w}</div>'
            for w in estimate.warnings
        )
        warnings_html = f'<div class="aou-cost-warnings">{items}</div>'

    dollar_label = "Est. Cost (USD)" if not estimate.exact else "Cost (USD)*"
    dollar_note = ""
    if estimate.exact:
        dollar_note = (
            '<div style="font-size: 11px; opacity: 0.6; margin-top: 4px;">'
            "*AoU credit mapping unverified — bytes are exact, dollars are estimated"
            "</div>"
        )

    return f"""
    {_css()}
    <div class="aou-cost-container" style="background:{colors['bg']};border:1px solid {colors['border']};color:{colors['text']}">
        <div class="aou-cost-header">
            <span class="aou-cost-badge" style="background:{colors['border']};color:white">{badge}</span>
            {exact_badge}
            {cache_badge}
        </div>
        <div class="aou-cost-stats">
            <div class="aou-cost-stat">
                <div class="aou-cost-stat-value">{estimate.bytes_display}</div>
                <div class="aou-cost-stat-label">Bytes Scanned</div>
            </div>
            <div class="aou-cost-stat">
                <div class="aou-cost-stat-value">{estimate.cost_display}</div>
                <div class="aou-cost-stat-label">{dollar_label}</div>
            </div>
        </div>
        {dollar_note}
        {warnings_html}
    </div>
    """


def render_optimization(
    original_bytes: int,
    optimized_bytes: int,
    original_cost: float,
    optimized_cost: float,
    optimized_sql: str,
    explanation: str,
    confidence: str,
    semantically_equivalent: bool,
    api_cost: float,
) -> str:
    savings_bytes = original_bytes - optimized_bytes
    savings_pct = (savings_bytes / original_bytes * 100) if original_bytes > 0 else 0
    savings_usd = original_cost - optimized_cost

    equiv_badge = (
        '<span style="color:#28a745;font-weight:600">Semantically Equivalent</span>'
        if semantically_equivalent
        else '<span style="color:#dc3545;font-weight:600">Semantics May Differ — Review Carefully</span>'
    )

    return f"""
    {_css()}
    <div class="aou-opt-container">
        <div class="aou-opt-header">AI-Optimized Query</div>
        <div class="aou-opt-savings">
            Save {format_bytes(savings_bytes)} ({savings_pct:.0f}%) — ${savings_usd:.4f}
        </div>
        <div class="aou-opt-meta">
            Confidence: <strong>{confidence}</strong> | {equiv_badge} |
            API cost: ${api_cost:.4f}
        </div>
        <div class="aou-opt-explanation">{explanation}</div>
        <div class="aou-opt-diff">{optimized_sql}</div>
    </div>
    """


def display_estimate(estimate: CostEstimate) -> None:
    display(HTML(render_estimate(estimate)))


def display_optimization(**kwargs) -> None:
    display(HTML(render_optimization(**kwargs)))
