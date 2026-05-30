import { useCallback, useEffect, useRef, useState } from "react";
import {
  getConversation,
  streamChat,
  type AnalyticsPayload,
  type ChartPayload,
  type HistoryTurn,
  type StoredMessage,
  type ToolStatus,
  type WebSearchPayload,
} from "@/lib/api";
import type { Step } from "@/components/StepIndicator";

export interface ToolCall {
  parent: string;
  tool: string;
  label: string;
  status: ToolStatus;
  detail?: string | null;
  startedAt?: number;
  endedAt?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  fullContent?: string;
  streaming?: boolean;
  steps?: Step[];
  toolCalls?: ToolCall[];
  rawResult?: Record<string, unknown>;
  chart?: ChartPayload | null;
  analytics?: AnalyticsPayload | null;
  webSearch?: WebSearchPayload | null;
  sql?: string | null;
  warnings?: string[];
  intent?: string;
  blockedReason?: string | null;
}

interface UseChatOptions {
  activeConversationId: string | null;
  webSearchEnabled: boolean;
  onConversationCreated?: (id: string, title: string) => void;
}

function storedToMessage(s: StoredMessage): Message {
  const payload = (s.payload as Record<string, unknown>) ?? {};
  return {
    id: s.id,
    role: s.role,
    content: s.content,
    fullContent: s.content,
    streaming: false,
    steps: [],
    toolCalls: (payload.tool_calls as ToolCall[]) ?? [],
    rawResult: (payload.raw_result as Record<string, unknown>) ?? undefined,
    chart: (payload.chart as ChartPayload | null) ?? null,
    analytics: (payload.analytics as AnalyticsPayload | null) ?? null,
    webSearch: (payload.web_search as WebSearchPayload | null) ?? null,
    sql: (payload.sql as string | null) ?? null,
    warnings: (payload.warnings as string[]) ?? [],
    intent: (payload.intent as string) ?? undefined,
    blockedReason: (payload.blocked_reason as string | null) ?? null,
  };
}

const PIPELINE_LABELS: Record<string, string> = {
  classify: "Đang phân loại câu hỏi",
  manager: "Manager đang điều phối",
  sql_agent: "SQL agent: tra cứu dữ liệu",
  retrieval_agent: "Retrieval agent: tra schema",
  insight_agent: "Insight agent: tổng hợp KPI",
  viz_agent: "Viz agent: dựng biểu đồ",
  analytic_agent: "Analytic agent: phân tích",
  time_series_agent: "Time-series agent: trend",
  chat_agent: "Chat agent: chuẩn bị phản hồi",
  synthesize: "Đang tóm tắt kết quả",
};

const TYPEWRITER_INTERVAL_MS = 8;
const TYPEWRITER_CHARS_PER_TICK = 12;

export function useChat(opts: UseChatOptions) {
  const { activeConversationId, webSearchEnabled, onConversationCreated } = opts;
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const typewriterRef = useRef<number | null>(null);
  // Stable refs for values that change but we don't want to invalidate the
  // sendMessage callback every render.
  const conversationIdRef = useRef<string | null>(activeConversationId);
  const webSearchRef = useRef<boolean>(webSearchEnabled);
  const onConvCreatedRef = useRef(onConversationCreated);
  useEffect(() => {
    conversationIdRef.current = activeConversationId;
  }, [activeConversationId]);
  useEffect(() => {
    webSearchRef.current = webSearchEnabled;
  }, [webSearchEnabled]);
  useEffect(() => {
    onConvCreatedRef.current = onConversationCreated;
  }, [onConversationCreated]);

  // Load messages whenever the active conversation changes.
  useEffect(() => {
    let cancelled = false;
    if (!activeConversationId) {
      setMessages([]);
      return;
    }
    setLoadingConversation(true);
    (async () => {
      try {
        const detail = await getConversation(activeConversationId);
        if (cancelled) return;
        setMessages(detail.messages.map(storedToMessage));
      } catch (exc) {
        if (cancelled) return;
        console.warn("[useChat] loadConversation failed:", exc);
        setMessages([]);
      } finally {
        if (!cancelled) setLoadingConversation(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeConversationId]);

  const stopTypewriter = useCallback(() => {
    if (typewriterRef.current !== null) {
      window.clearInterval(typewriterRef.current);
      typewriterRef.current = null;
    }
  }, []);

  const startTypewriter = useCallback(
    (assistantId: string) => {
      stopTypewriter();
      typewriterRef.current = window.setInterval(() => {
        let stillTyping = false;
        setMessages((m) =>
          m.map((msg) => {
            if (msg.id !== assistantId) return msg;
            const target = msg.fullContent ?? "";
            if (msg.content.length >= target.length) return msg;
            stillTyping = true;
            const next = target.slice(0, msg.content.length + TYPEWRITER_CHARS_PER_TICK);
            return { ...msg, content: next };
          }),
        );
        if (!stillTyping) stopTypewriter();
      }, TYPEWRITER_INTERVAL_MS);
    },
    [stopTypewriter],
  );

  const buildHistory = useCallback(
    (current: Message[]): HistoryTurn[] => {
      const turns: HistoryTurn[] = [];
      for (const m of current.slice(-12)) {
        const text = (m.fullContent ?? m.content ?? "").trim();
        if (!text) continue;
        turns.push({ role: m.role, content: text });
      }
      return turns;
    },
    [],
  );

  const sendMessage = useCallback(
    async (
      text: string,
      overrides?: { webSearchEnabled?: boolean; forceWebSearch?: boolean },
    ) => {
      if (!text.trim() || busy) return;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
      };
      const historySnapshot = buildHistory(messages);
      const assistantId = crypto.randomUUID();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        fullContent: "",
        streaming: true,
        steps: [],
        toolCalls: [],
      };
      setMessages((m) => [...m, userMsg, assistantMsg]);
      setBusy(true);

      const controller = new AbortController();
      abortRef.current = controller;

      let receivedToken = false;

      try {
        await streamChat(
          text,
          {},
          (event) => {
            // The first SSE event is always `conversation` — capture the
            // (possibly auto-created) id BEFORE updating messages so the
            // parent can refresh its sidebar.
            if (event.type === "conversation") {
              conversationIdRef.current = event.id;
              onConvCreatedRef.current?.(event.id, event.title);
              return;
            }

            setMessages((m) =>
              m.map((msg) => {
                if (msg.id !== assistantId) return msg;

                if (event.type === "step") {
                  const previous: Step[] = (msg.steps ?? []).map((s) => ({ ...s, status: "done" }));
                  const next: Step[] = [
                    ...previous,
                    {
                      node: event.node,
                      label: PIPELINE_LABELS[event.node] ?? event.label,
                      status: "active",
                    },
                  ];
                  return { ...msg, steps: next, intent: event.intent ?? msg.intent };
                }

                if (event.type === "tool") {
                  const now = Date.now();
                  const calls = msg.toolCalls ?? [];
                  // Match an active "start" row for this (parent, tool) and update its
                  // status in place. Otherwise append a new row.
                  const idx = calls.findIndex(
                    (c) =>
                      c.parent === event.parent &&
                      c.tool === event.tool &&
                      c.status === "start",
                  );
                  const nextCalls: ToolCall[] =
                    idx >= 0
                      ? calls.map((c, i) =>
                          i === idx
                            ? {
                                ...c,
                                status: event.status,
                                label: event.label,
                                detail: event.detail ?? c.detail,
                                endedAt:
                                  event.status === "start" ? undefined : now,
                              }
                            : c,
                        )
                      : [
                          ...calls,
                          {
                            parent: event.parent,
                            tool: event.tool,
                            label: event.label,
                            status: event.status,
                            detail: event.detail ?? null,
                            startedAt: now,
                            endedAt: event.status === "start" ? undefined : now,
                          },
                        ];
                  return { ...msg, toolCalls: nextCalls };
                }

                if (event.type === "token") {
                  receivedToken = true;
                  const nextContent = (msg.content ?? "") + event.text;
                  return {
                    ...msg,
                    content: nextContent,
                    fullContent: nextContent,
                    streaming: true,
                  };
                }

                if (event.type === "final") {
                  const finalAt = Date.now();
                  const steps = (msg.steps ?? []).map((s) => ({ ...s, status: "done" as const }));
                  const toolCalls = (msg.toolCalls ?? []).map((c) =>
                    c.status === "start"
                      ? { ...c, status: "done" as const, endedAt: c.endedAt ?? finalAt }
                      : c,
                  );
                  if (receivedToken) {
                    // Tokens already streamed — just attach metadata + finalize.
                    return {
                      ...msg,
                      streaming: false,
                      steps,
                      toolCalls,
                      rawResult: event.raw_result,
                      chart: event.chart,
                      analytics: event.analytics,
                      webSearch: event.web_search ?? null,
                      sql: event.sql,
                      warnings: event.warnings,
                      intent: event.intent,
                      blockedReason: event.blocked_reason ?? null,
                    };
                  }
                  // No tokens (LLM disabled / fallback) — show via typewriter.
                  return {
                    ...msg,
                    content: msg.content,
                    fullContent: event.result_summary || "(no response)",
                    streaming: true,
                    steps,
                    toolCalls,
                    rawResult: event.raw_result,
                    chart: event.chart,
                    analytics: event.analytics,
                    webSearch: event.web_search ?? null,
                    sql: event.sql,
                    warnings: event.warnings,
                    intent: event.intent,
                    blockedReason: event.blocked_reason ?? null,
                  };
                }

                if (event.type === "error") {
                  return {
                    ...msg,
                    content: `Lỗi: ${event.detail}`,
                    fullContent: `Lỗi: ${event.detail}`,
                    streaming: false,
                  };
                }

                return msg;
              }),
            );

            if (event.type === "final" && !receivedToken) {
              startTypewriter(assistantId);
              const target = event.result_summary || "(no response)";
              const totalMs = (target.length / TYPEWRITER_CHARS_PER_TICK + 4) * TYPEWRITER_INTERVAL_MS;
              window.setTimeout(() => {
                setMessages((m) =>
                  m.map((msg) =>
                    msg.id === assistantId
                      ? { ...msg, content: target, streaming: false }
                      : msg,
                  ),
                );
              }, totalMs + 100);
            }
          },
          controller.signal,
          historySnapshot,
          {
            conversationId: conversationIdRef.current,
            webSearchEnabled:
              overrides?.webSearchEnabled ?? webSearchRef.current,
            forceWebSearch: overrides?.forceWebSearch ?? false,
          },
        );
      } catch (exc) {
        if ((exc as Error).name === "AbortError") return;
        setMessages((m) =>
          m.map((msg) =>
            msg.id === assistantId
              ? {
                  ...msg,
                  content: `Lỗi kết nối: ${(exc as Error).message}`,
                  fullContent: `Lỗi kết nối: ${(exc as Error).message}`,
                  streaming: false,
                }
              : msg,
          ),
        );
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy, messages, buildHistory, startTypewriter],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    stopTypewriter();
    setBusy(false);
  }, [stopTypewriter]);

  const clear = useCallback(() => {
    stopTypewriter();
    setMessages([]);
  }, [stopTypewriter]);

  return { messages, busy, loadingConversation, sendMessage, stop, clear };
}
