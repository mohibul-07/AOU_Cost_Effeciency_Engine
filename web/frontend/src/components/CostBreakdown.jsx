const LEVEL_STYLES = {
  green: {
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    badge: "bg-emerald-600",
    text: "text-emerald-900",
    label: "LOW COST",
  },
  yellow: {
    bg: "bg-amber-50",
    border: "border-amber-200",
    badge: "bg-amber-500",
    text: "text-amber-900",
    label: "MODERATE COST",
  },
  red: {
    bg: "bg-red-50",
    border: "border-red-200",
    badge: "bg-red-600",
    text: "text-red-900",
    label: "HIGH COST",
  },
};

export default function CostBreakdown({ data }) {
  const style = LEVEL_STYLES[data.cost_level] || LEVEL_STYLES.green;

  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} overflow-hidden`}>
      {/* Header */}
      <div className="px-4 py-3 flex items-center gap-2 flex-wrap">
        <span className={`text-xs font-bold text-white px-2.5 py-0.5 rounded-full ${style.badge}`}>
          {style.label}
        </span>
        <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded">
          {data.exact ? "EXACT (dry run)" : "APPROXIMATE (catalog)"}
        </span>
        {data.cache_eligible && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
            CACHE ELIGIBLE ($0)
          </span>
        )}
        <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded">
          {data.cell_type}
        </span>
      </div>

      {/* Stats */}
      <div className="px-4 py-4 grid grid-cols-2 gap-4">
        <div className="text-center">
          <div className={`text-2xl font-bold ${style.text}`}>
            {data.bytes_display}
          </div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mt-1">
            Bytes Scanned
          </div>
        </div>
        <div className="text-center">
          <div className={`text-2xl font-bold ${style.text}`}>
            {data.cost_display}
          </div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mt-1">
            Est. Cost (USD)
          </div>
        </div>
      </div>

      {/* Byte cap suggestion */}
      {data.cap_suggestion && (
        <div className="mx-4 mb-3 p-3 bg-amber-100 rounded-md border border-amber-300">
          <p className="text-xs text-amber-800">
            <strong>Guardrail suggestion:</strong> Add{" "}
            <code className="text-xs bg-amber-200 px-1 rounded">
              maximum_bytes_billed = {data.cap_suggestion.cap_bytes}
            </code>{" "}
            (cap at {data.cap_suggestion.cap_bytes_display}, ~$
            {data.cap_suggestion.cap_cost_usd.toFixed(4)}) to prevent cost overruns.
          </p>
        </div>
      )}

      {/* Warnings */}
      {data.warnings.length > 0 && (
        <div className="px-4 pb-3">
          <div className="bg-white/50 rounded-md p-3 space-y-1.5">
            {data.warnings.map((w, i) => (
              <div key={i} className="text-xs text-gray-700 flex gap-1.5">
                <span className="shrink-0">&#9888;</span>
                <span>{w}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!data.exact && (
        <div className="px-4 pb-3">
          <p className="text-xs text-gray-500 italic">
            * Dollar figures are estimates based on $6.25/TiB. Use the in-notebook
            magic (%%aou_cost) for exact dry-run numbers.
          </p>
        </div>
      )}
    </div>
  );
}
