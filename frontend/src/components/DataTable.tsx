import { useMemo } from "react";

interface DataTableProps {
  rows: Record<string, unknown>[];
  maxRows?: number;
}

export function DataTable({ rows, maxRows = 50 }: DataTableProps) {
  const columns = useMemo(() => {
    const set = new Set<string>();
    for (const row of rows.slice(0, 100)) Object.keys(row).forEach((k) => set.add(k));
    return Array.from(set);
  }, [rows]);

  if (!rows.length) return null;

  return (
    <div className="rounded-md border-2 border-black bg-white neo-shadow">
      <div className="max-h-80 overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 z-10 bg-yellow-300 border-b-2 border-black">
            <tr>
              {columns.map((col) => (
                <th key={col} className="border-r-2 border-black last:border-r-0 px-3 py-2 text-left font-black uppercase tracking-tight text-black">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, maxRows).map((row, idx) => (
              <tr key={idx} className="border-b-2 border-black last:border-b-0 hover:bg-yellow-100 font-medium">
                {columns.map((col) => (
                  <td key={col} className="border-r-2 border-black last:border-r-0 px-3 py-1.5">
                    {formatCell(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t-2 border-black bg-lime-200 px-3 py-1.5 text-xs font-bold">
        {rows.length > maxRows
          ? `Hiển thị ${maxRows} / ${rows.length} dòng • cuộn trong bảng`
          : `${rows.length} dòng • cuộn trong bảng`}
      </div>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
