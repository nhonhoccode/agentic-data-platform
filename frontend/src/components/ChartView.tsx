import { lazy, Suspense } from "react";
import type { ChartPayload } from "@/lib/api";
import { Loader2 } from "lucide-react";

const Plot = lazy(() =>
  import("react-plotly.js").then((mod) => ({ default: mod.default })),
);

interface ChartViewProps {
  chart: ChartPayload;
}

export function ChartView({ chart }: ChartViewProps) {
  const x = chart.series.map((p) => p.x);
  const y = chart.series.map((p) => p.y);

  return (
    <div className="rounded-lg border bg-background p-2">
      <Suspense
        fallback={
          <div className="flex h-[320px] items-center justify-center text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            <span className="text-xs">Đang tải biểu đồ...</span>
          </div>
        }
      >
        <Plot
          data={[
            {
              x,
              y,
              type: chart.chart_type === "line" ? "scatter" : "bar",
              mode: chart.chart_type === "line" ? "lines+markers" : undefined,
              marker: { color: "#3b82f6" },
              line: { color: "#3b82f6", width: 2 },
            } as Plotly.Data,
          ]}
          layout={{
            title: { text: chart.title, font: { size: 13 } },
            margin: { l: 50, r: 20, t: 40, b: 80 },
            autosize: true,
            height: 320,
            xaxis: { tickangle: -30, automargin: true },
            plot_bgcolor: "transparent",
            paper_bgcolor: "transparent",
          }}
          useResizeHandler
          style={{ width: "100%" }}
          config={{ displayModeBar: false, responsive: true }}
        />
      </Suspense>
    </div>
  );
}
