export type ToolStatus = "start" | "done" | "error";

export interface WebSearchResult {
  title: string;
  url: string;
  snippet: string;
  score?: number | null;
}

export interface WebSearchPayload {
  query: string;
  answer: string | null;
  results: WebSearchResult[];
  count: number;
  error?: string | null;
  reason?: string | null;
}

export type ChatStreamEvent =
  | {
      type: "conversation";
      id: string;
      title: string;
    }
  | {
      type: "step";
      node: string;
      label: string;
      intent?: string | null;
      selected_tools?: string[];
    }
  | {
      type: "tool";
      parent: string;
      tool: string;
      label: string;
      status: ToolStatus;
      detail?: string | null;
    }
  | {
      type: "token";
      text: string;
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
      web_search: WebSearchPayload | null;
      completed_agents: string[];
      web_search_enabled?: boolean;
      blocked_reason?: string | null;
    }
  | { type: "error"; detail: string };

export interface StreamChatOptions {
  conversationId?: string | null;
  webSearchEnabled?: boolean;
  /** Bypass the domain filter for this one request (used by OOD CTA). */
  forceWebSearch?: boolean;
}

export interface ConversationMeta {
  id: string;
  title: string;
  updated_at: number;
  message_count: number;
}

export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  payload: Record<string, unknown> | null;
  created_at: number;
  sequence_no: number;
}

export interface ConversationDetail {
  conversation: {
    id: string;
    title: string;
    created_at: number;
    updated_at: number;
  };
  messages: StoredMessage[];
}

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

import { authHeaders } from "./session";

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
  opts: StreamChatOptions = {},
): Promise<void> {
  const body = JSON.stringify({
    message,
    context,
    history,
    conversation_id: opts.conversationId ?? null,
    web_search_enabled: !!opts.webSearchEnabled || !!opts.forceWebSearch,
    force_web_search: !!opts.forceWebSearch,
  });

  let response: Response;
  try {
    response = await fetch(`${PROXY_BASE}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...authHeaders(),
      },
      body,
      signal,
      cache: "no-store",
    });
  } catch (err) {
    // Stream connection failed — fall back to non-streaming POST.
    return await fallbackPostChat(message, context, onEvent, err, history, opts);
  }

  if (!response.ok || !response.body) {
    return await fallbackPostChat(
      message,
      context,
      onEvent,
      new Error(`Stream HTTP ${response.status}`),
      history,
      opts,
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
    await fallbackPostChat(message, context, onEvent, err, history, opts);
  }
}

async function fallbackPostChat(
  message: string,
  context: Record<string, unknown>,
  onEvent: (event: ChatStreamEvent) => void,
  origError: unknown,
  history: HistoryTurn[] = [],
  opts: StreamChatOptions = {},
): Promise<void> {
  console.warn("[stream] falling back to /chat", origError);
  try {
    const response = await fetch(`${PROXY_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        message,
        context,
        history,
        conversation_id: opts.conversationId ?? null,
        web_search_enabled: !!opts.webSearchEnabled || !!opts.forceWebSearch,
        force_web_search: !!opts.forceWebSearch,
      }),
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
      web_search: extractWebSearch(json.blocks ?? []),
      completed_agents: [],
      web_search_enabled: !!opts.webSearchEnabled,
      blocked_reason: null,
    });
  } catch (err) {
    onEvent({
      type: "error",
      detail: `Stream + fallback đều fail: ${(err as Error).message ?? err}`,
    });
  }
}

// ---------------------------------------------------------------------------
// Conversation CRUD helpers
// ---------------------------------------------------------------------------

export async function listConversations(): Promise<ConversationMeta[]> {
  const resp = await fetch(`${PROXY_BASE}/conversations`, {
    headers: { ...authHeaders() },
  });
  if (!resp.ok) throw new Error(`listConversations HTTP ${resp.status}`);
  const json = await resp.json();
  return (json.conversations as ConversationMeta[]) ?? [];
}

export async function createConversation(title?: string): Promise<ConversationMeta> {
  const resp = await fetch(`${PROXY_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ title: title ?? null }),
  });
  if (!resp.ok) throw new Error(`createConversation HTTP ${resp.status}`);
  const json = await resp.json();
  return {
    id: json.id,
    title: json.title,
    updated_at: json.created_at ?? Date.now() / 1000,
    message_count: 0,
  };
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const resp = await fetch(`${PROXY_BASE}/conversations/${id}`, {
    headers: { ...authHeaders() },
  });
  if (!resp.ok) throw new Error(`getConversation HTTP ${resp.status}`);
  return (await resp.json()) as ConversationDetail;
}

export async function deleteConversation(id: string): Promise<void> {
  const resp = await fetch(`${PROXY_BASE}/conversations/${id}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  if (!resp.ok) throw new Error(`deleteConversation HTTP ${resp.status}`);
}

export async function renameConversation(id: string, title: string): Promise<void> {
  const resp = await fetch(`${PROXY_BASE}/conversations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ title }),
  });
  if (!resp.ok) throw new Error(`renameConversation HTTP ${resp.status}`);
}

export interface SearchHit {
  id: string;
  title: string;
  updated_at: number;
  message_count: number;
  snippet: string | null;
}

export async function searchConversations(q: string): Promise<SearchHit[]> {
  const resp = await fetch(
    `${PROXY_BASE}/conversations/search/q?q=${encodeURIComponent(q)}`,
    { headers: { ...authHeaders() } },
  );
  if (!resp.ok) throw new Error(`searchConversations HTTP ${resp.status}`);
  const json = await resp.json();
  return (json.results as SearchHit[]) ?? [];
}

export async function exportConversation(id: string): Promise<unknown> {
  const resp = await fetch(`${PROXY_BASE}/conversations/${id}/export`, {
    headers: { ...authHeaders() },
  });
  if (!resp.ok) throw new Error(`exportConversation HTTP ${resp.status}`);
  return await resp.json();
}

function extractRawFromBlocks(blocks: Array<{ type: string; payload?: Record<string, unknown> }>):
  Record<string, unknown> {
  const table = blocks.find((b) => b.type === "table");
  const rows = (table?.payload?.rows as unknown[]) ?? [];
  return { data: rows };
}

function extractWebSearch(
  blocks: Array<{ type: string; payload?: Record<string, unknown> }>,
): WebSearchPayload | null {
  const ws = blocks.find((b) => b.type === "web_search");
  if (!ws?.payload) return null;
  const payload = ws.payload as Record<string, unknown>;
  return {
    query: (payload.query as string) ?? "",
    answer: (payload.answer as string | null) ?? null,
    results: (payload.results as WebSearchResult[]) ?? [],
    count: (payload.count as number) ?? 0,
    error: (payload.error as string | null) ?? null,
    reason: (payload.reason as string | null) ?? null,
  };
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
    headers: { ...authHeaders() },
    body: form,
  });
  const json = await response.json();
  if (!response.ok) return { ok: false, detail: json.detail ?? "upload_failed" };
  return { ok: true, ...json };
}
