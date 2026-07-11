import { useState } from "react";
import CodeEditor from "./components/CodeEditor";
import CostBreakdown from "./components/CostBreakdown";
import OptimizationPanel from "./components/OptimizationPanel";
import TableCatalog from "./components/TableCatalog";

const EXAMPLE_QUERIES = [
  {
    label: "Simple person query",
    code: "SELECT person_id, year_of_birth\nFROM person\nWHERE year_of_birth > 1990",
  },
  {
    label: "Expensive SELECT *",
    code: "SELECT *\nFROM measurement\nLIMIT 1000",
  },
  {
    label: "Variant table (very expensive)",
    code: "SELECT *\nFROM cb_variant_to_person\nWHERE gene_symbol = 'BRCA1'",
  },
  {
    label: "Multi-table join",
    code: "SELECT p.person_id, c.condition_concept_id, m.value_as_number\nFROM person p\nJOIN condition_occurrence c ON p.person_id = c.person_id\nJOIN measurement m ON p.person_id = m.person_id\nWHERE c.condition_start_date > '2020-01-01'",
  },
];

export default function App() {
  const [code, setCode] = useState(EXAMPLE_QUERIES[0].code);
  const [estimate, setEstimate] = useState(null);
  const [optimization, setOptimization] = useState(null);
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [error, setError] = useState(null);
  const [showCatalog, setShowCatalog] = useState(false);

  async function handleEstimate() {
    setLoading(true);
    setError(null);
    setEstimate(null);
    setOptimization(null);
    try {
      const res = await fetch("/api/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error ${res.status}`);
      }
      setEstimate(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleOptimize() {
    setOptimizing(true);
    setOptimization(null);
    try {
      const res = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: code }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error ${res.status}`);
      }
      setOptimization(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setOptimizing(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              AoU Cost Engine
            </h1>
            <p className="text-sm text-gray-500">
              BigQuery cost estimation for All of Us Research Workbench
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowCatalog(!showCatalog)}
              className="text-sm px-3 py-1.5 rounded-md border border-gray-300 text-gray-600 hover:bg-gray-50 transition-colors"
            >
              {showCatalog ? "Hide" : "Show"} Table Catalog
            </button>
            <span className="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded-full font-medium">
              Offline Mode — Approximate Estimates
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {showCatalog && (
          <div className="mb-6">
            <TableCatalog />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Input */}
          <div className="space-y-4">
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700">
                  Query Input
                </h2>
                <div className="flex gap-2 flex-wrap justify-end">
                  {EXAMPLE_QUERIES.map((ex, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setCode(ex.code);
                        setEstimate(null);
                        setOptimization(null);
                      }}
                      className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
                    >
                      {ex.label}
                    </button>
                  ))}
                </div>
              </div>
              <CodeEditor value={code} onChange={setCode} />
              <div className="px-4 py-3 border-t border-gray-100 flex gap-3">
                <button
                  onClick={handleEstimate}
                  disabled={loading || !code.trim()}
                  className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? "Estimating..." : "Estimate Cost"}
                </button>
                <button
                  onClick={handleOptimize}
                  disabled={optimizing || !code.trim()}
                  className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {optimizing ? "Optimizing..." : "AI Optimize"}
                </button>
              </div>
            </div>
          </div>

          {/* Right: Results */}
          <div className="space-y-4">
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {loading && (
              <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
                <div className="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
                <p className="text-sm text-gray-500">
                  Analyzing query with static catalog...
                </p>
              </div>
            )}

            {estimate && <CostBreakdown data={estimate} />}

            {optimizing && (
              <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
                <div className="animate-spin h-8 w-8 border-2 border-emerald-600 border-t-transparent rounded-full mx-auto mb-3" />
                <p className="text-sm text-gray-500">
                  Claude is analyzing your query for optimizations...
                </p>
              </div>
            )}

            {optimization && (
              <OptimizationPanel
                data={optimization}
                onApply={() => {
                  setCode(optimization.optimized_sql);
                  setOptimization(null);
                  setEstimate(null);
                }}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
