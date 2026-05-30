import type { AnalyticsPayload } from "@/lib/api";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";

interface AnalyticsPanelProps {
  analytics: AnalyticsPayload;
}

export function AnalyticsPanel({ analytics }: AnalyticsPanelProps) {
  const ts = analytics.time_series as
    | {
        trend?: string;
        metric?: string;
        first?: { t: string; value: number };
        last?: { t: string; value: number };
        delta?: number;
        pct_change?: number;
        peak?: { t: string; value: number };
        trough?: { t: string; value: number };
      }
    | undefined;

  const drill = analytics.drill_down as
    | { dimension?: string; metric?: string; groups?: Array<{ group: string; sum: number; count: number }> }
    | undefined;

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {ts && ts.trend && ts.trend !== "no_data" && ts.trend !== "no_time_axis" && (
        <div className="rounded-md border-2 border-black bg-cyan-200 p-3 neo-shadow">
          <div className="mb-2 flex items-center gap-2 text-sm font-black uppercase">
            {ts.trend === "up" && <TrendingUp className="h-5 w-5" strokeWidth={3} />}
            {ts.trend === "down" && <TrendingDown className="h-5 w-5" strokeWidth={3} />}
            {ts.trend === "flat" && <Minus className="h-5 w-5" strokeWidth={3} />}
            <span>Xu hướng {ts.metric}</span>
          </div>
          <div className="space-y-1 text-xs font-bold">
            {ts.pct_change !== null && ts.pct_change !== undefined && (
              <div>
                Biến động: <span className="rounded-sm border-2 border-black bg-white px-1.5 py-0.5">{ts.pct_change > 0 ? "+" : ""}{ts.pct_change}%</span>
              </div>
            )}
            {ts.peak && (
              <div>Đỉnh: {String(ts.peak.t)} → {ts.peak.value.toLocaleString("vi-VN")}</div>
            )}
            {ts.trough && (
              <div>Đáy: {String(ts.trough.t)} → {ts.trough.value.toLocaleString("vi-VN")}</div>
            )}
          </div>
        </div>
      )}

      {drill && drill.groups && drill.groups.length > 0 && (
        <div className="rounded-md border-2 border-black bg-lime-200 p-3 neo-shadow">
          <div className="mb-2 text-sm font-black uppercase">
            Top theo {drill.dimension} ({drill.metric || "đếm"})
          </div>
          <ul className="space-y-1 text-xs font-bold">
            {drill.groups.slice(0, 6).map((g) => (
              <li key={g.group} className="flex justify-between border-b border-black/30 last:border-b-0 py-0.5">
                <span className="truncate">{g.group}</span>
                <span>{g.sum.toLocaleString("vi-VN")}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
