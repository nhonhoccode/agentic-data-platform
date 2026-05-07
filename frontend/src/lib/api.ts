export type ChatStreamEvent =
  | {
      type: "step";
      node: string;
      label: string;
      intent?: string | null;
      selected_tools?: string[];
    }
  | {
      type: "final";
      intent: string;
      selected_tools: string[];
      sql: string | null;
      result_summary: string;
      confidence: number;
      warnings: string[];
      raw_result: Record<string, unknown>;
      chart: ChartPayload | null;
      analytics: AnalyticsPayload | null;
      completed_agents: string[];
    }
  | { type: "error"; detail: string };

export interface ChartPayload {
  chart_type: "bar" | "line";
  label_column: string;
  value_column: string;
  series: Array<{ x: string; y: number }>;
  title: string;
}

export interface AnalyticsPayload {
  time_series?: Record<string, unknown>;
  drill_down?: Record<string, unknown>;
  correlation?: Record<string, unknown>;
}

const PROXY_BASE = "/ui/proxy";

export interface HistoryTurn {
  role: "user" | "assistant";
  content: string;
}

export async function streamChat(
  message: string,
  context: Record<string, unknown>,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
  history: HistoryTurn[] = [],
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${PROXY_BASE}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ message, context, history }),
      signal,
      cache: "no-store",
    });
  } catch (err) {
    // Stream connection failed — fall back to non-streaming POST.
    return await fallbackPostChat(message, context, onEvent, err, history);
  }

  if (!response.ok || !response.body) {
    return await fallbackPostChat(
      message,
      context,
      onEvent,
      new Error(`Stream HTTP ${response.status}`),
      history,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const event = parseSSE(block);
        if (event) onEvent(event);
      }
    }
    // Drain final buffer (in case server didn't send terminating \n\n)
    if (buffer.trim()) {
      const event = parseSSE(buffer);
      if (event) onEvent(event);
    }
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    // Mid-stream failure — try fallback so user still gets an answer.
    await fallbackPostChat(message, context, onEvent, err, history);
  }
}

async function fallbackPostChat(
  message: string,
  context: Record<string, unknown>,
  onEvent: (event: ChatStreamEvent) => void,
  origError: unknown,
  history: HistoryTurn[] = [],
): Promise<void> {
  console.warn("[stream] falling back to /chat", origError);
  try {
    const response = await fetch(`${PROXY_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context, history }),
    });
    const json = await response.json();
    if (!response.ok) {
      onEvent({ type: "error", detail: json.detail ?? `HTTP ${response.status}` });
      return;
    }
    const trace = json.trace ?? {};
    onEvent({
      type: "final",
      intent: trace.inferred_intent ?? "unknown",
      selected_tools: trace.selected_tools ?? [],
      sql: trace.sql ?? null,
      result_summary: json.assistant_message ?? "",
      confidence: trace.confidence ?? 0,
      warnings: trace.warnings ?? [],
      raw_result: extractRawFromBlocks(json.blocks ?? []),
      chart: extractChart(json.blocks ?? []),
      analytics: null,
      completed_agents: [],
    });
  } catch (err) {
    onEvent({
      type: "error",
      detail: `Stream + fallback đều fail: ${(err as Error).message ?? err}`,
    });
  }
}

function extractRawFromBlocks(blocks: Array<{ type: string; payload?: Record<string, unknown> }>):
  Record<string, unknown> {
  const table = blocks.find((b) => b.type === "table");
  const rows = (table?.payload?.rows as unknown[]) ?? [];
  return { data: rows };
}

function extractChart(
  blocks: Array<{ type: string; title?: string; payload?: Record<string, unknown> }>,
): ChartPayload | null {
  const fig = blocks.find((b) => b.type === "figure");
  if (!fig?.payload) return null;
  const series = fig.payload.series as Array<{ x: string; y: number }> | undefined;
  if (!series || series.length === 0) return null;
  return {
    chart_type: (fig.payload.chart as string) === "line" ? "line" : "bar",
    label_column: (fig.payload.label_column as string) ?? "x",
    value_column: (fig.payload.value_column as string) ?? "y",
    series,
    title: fig.title ?? "",
  };
}

function parseSSE(block: string): ChatStreamEvent | null {
  const lines = block.split(/\r?\n/);
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (dataLines.length === 0) return null;
  const data = dataLines.join("\n").trim();
  if (!data || data.startsWith(":")) return null;
  try {
    return JSON.parse(data) as ChatStreamEvent;
  } catch (err) {
    console.warn("[stream] bad JSON:", data.slice(0, 200), err);
    return null;
  }
}

export async function uploadFile(file: File): Promise<{ ok: boolean; detail?: string; rows_loaded?: number; table?: string }>
{
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${PROXY_BASE}/upload`, {
    method: "POST",
    body: form,
  });
  const json = await response.json();
  if (!response.ok) return { ok: false, detail: json.detail ?? "upload_failed" };
  return { ok: true, ...json };
}
