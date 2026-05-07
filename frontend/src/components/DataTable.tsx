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
    <div className="overflow-x-auto rounded-lg border">
      <table className="min-w-full text-sm">
        <thead className="bg-muted">
          <tr>
            {columns.map((col) => (
              <th key={col} className="border-b px-3 py-2 text-left font-medium text-muted-foreground">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, maxRows).map((row, idx) => (
            <tr key={idx} className="hover:bg-muted/40">
              {columns.map((col) => (
                <td key={col} className="border-b px-3 py-1.5">
                  {formatCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > maxRows && (
        <div className="border-t bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
          Hiển thị {maxRows} / {rows.length} dòng
        </div>
      )}
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
