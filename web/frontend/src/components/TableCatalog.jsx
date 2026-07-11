import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "";

export default function TableCatalog() {
  const [tables, setTables] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/tables`)
      .then((res) => res.json())
      .then(setTables)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4 text-center text-sm text-gray-500">
        Loading catalog...
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-700">
          CDR Table Catalog (Approximate Sizes)
        </h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Per-column sizes used by the offline fallback estimator. Actual sizes depend on CDR version.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="px-4 py-2 font-medium text-gray-600">Table</th>
              <th className="px-4 py-2 font-medium text-gray-600 text-right">
                Approx Rows
              </th>
              <th className="px-4 py-2 font-medium text-gray-600 text-right">
                Approx Size
              </th>
              <th className="px-4 py-2 font-medium text-gray-600 text-right">
                Columns
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {tables.map((t) => (
              <tr key={t.name} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-mono text-xs text-gray-800">
                  {t.name}
                </td>
                <td className="px-4 py-2 text-right text-gray-600">
                  {t.approx_rows.toLocaleString()}
                </td>
                <td className="px-4 py-2 text-right font-medium text-gray-800">
                  {t.approx_size}
                </td>
                <td className="px-4 py-2 text-right text-gray-600">
                  {t.column_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
