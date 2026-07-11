export default function OptimizationPanel({ data, onApply }) {
  if (data.error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-red-800 mb-1">
          Optimization Error
        </h3>
        <p className="text-xs text-red-700">{data.error}</p>
      </div>
    );
  }

  const hasSavings = data.savings_bytes > 0;

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">
          AI-Optimized Query
        </h3>
        <span className="text-xs text-gray-400">
          API cost: ${data.api_cost_usd.toFixed(4)}
        </span>
      </div>

      {/* Savings */}
      <div className="px-4 py-4">
        {hasSavings ? (
          <div className="text-center mb-4">
            <div className="text-2xl font-bold text-emerald-600">
              Save {formatBytes(data.savings_bytes)} ({data.savings_pct}%)
            </div>
            <div className="text-sm text-gray-500">
              ${data.original_cost.toFixed(4)} → ${data.optimized_cost.toFixed(4)}
              {" "}(−${data.savings_usd.toFixed(4)})
            </div>
          </div>
        ) : (
          <div className="text-center mb-4">
            <div className="text-lg font-semibold text-gray-600">
              Query is already optimal
            </div>
          </div>
        )}

        {/* Meta badges */}
        <div className="flex gap-2 flex-wrap mb-4">
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
            data.confidence === "high"
              ? "bg-emerald-100 text-emerald-700"
              : data.confidence === "medium"
              ? "bg-amber-100 text-amber-700"
              : "bg-red-100 text-red-700"
          }`}>
            Confidence: {data.confidence}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
            data.semantically_equivalent
              ? "bg-emerald-100 text-emerald-700"
              : "bg-red-100 text-red-700"
          }`}>
            {data.semantically_equivalent
              ? "Semantically Equivalent"
              : "Semantics May Differ"}
          </span>
          {data.strategies_applied.map((s, i) => (
            <span
              key={i}
              className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700"
            >
              {s.replace(/_/g, " ")}
            </span>
          ))}
        </div>

        {/* Explanation */}
        {data.explanation && (
          <div className="mb-4">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              What changed
            </h4>
            <p className="text-sm text-gray-700">{data.explanation}</p>
          </div>
        )}

        {data.semantic_notes && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-md">
            <p className="text-xs text-amber-800">
              <strong>Semantic note:</strong> {data.semantic_notes}
            </p>
          </div>
        )}

        {/* Optimized SQL */}
        {hasSavings && (
          <>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Optimized Query
            </h4>
            <pre className="bg-gray-900 text-green-400 text-sm p-4 rounded-md overflow-x-auto font-mono whitespace-pre-wrap mb-3">
              {data.optimized_sql}
            </pre>
            <button
              onClick={onApply}
              className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-md hover:bg-emerald-700 transition-colors"
            >
              Use Optimized Query
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function formatBytes(n) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let val = n;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return i === 0 ? `${val} B` : `${val.toFixed(1)} ${units[i]}`;
}
