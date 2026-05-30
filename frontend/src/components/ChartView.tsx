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
    <div className="rounded-md border-2 border-black bg-white p-2 neo-shadow">
      <Suspense
        fallback={
          <div className="flex h-[320px] items-center justify-center font-bold">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" strokeWidth={3} />
            <span className="text-xs uppercase">Đang tải biểu đồ...</span>
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
              marker: {
                color: "#facc15",
                line: { color: "#000", width: 2 },
              },
              line: { color: "#000", width: 3 },
            } as Plotly.Data,
          ]}
          layout={{
            title: { text: chart.title, font: { size: 14, family: "Space Grotesk, system-ui", color: "#000", weight: 800 } as any },
            margin: { l: 60, r: 20, t: 45, b: 80 },
            autosize: true,
            height: 320,
            xaxis: { tickangle: -30, automargin: true, gridcolor: "#000", linecolor: "#000", linewidth: 2 },
            yaxis: { gridcolor: "#000", linecolor: "#000", linewidth: 2 },
            plot_bgcolor: "transparent",
            paper_bgcolor: "transparent",
            font: { family: "Space Grotesk, system-ui", color: "#000" },
          }}
          useResizeHandler
          style={{ width: "100%" }}
          config={{ displayModeBar: false, responsive: true }}
        />
      </Suspense>
    </div>
  );
}
