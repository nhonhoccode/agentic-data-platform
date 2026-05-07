import { useCallback, useRef, useState } from "react";
import { streamChat, type AnalyticsPayload, type ChartPayload, type HistoryTurn } from "@/lib/api";
import type { Step } from "@/components/StepIndicator";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  fullContent?: string;
  streaming?: boolean;
  steps?: Step[];
  rawResult?: Record<string, unknown>;
  chart?: ChartPayload | null;
  analytics?: AnalyticsPayload | null;
  sql?: string | null;
  warnings?: string[];
  intent?: string;
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

const TYPEWRITER_INTERVAL_MS = 12;
const TYPEWRITER_CHARS_PER_TICK = 2;

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const typewriterRef = useRef<number | null>(null);

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
    async (text: string) => {
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
      };
      setMessages((m) => [...m, userMsg, assistantMsg]);
      setBusy(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(
          text,
          {},
          (event) => {
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

                if (event.type === "final") {
                  const steps = (msg.steps ?? []).map((s) => ({ ...s, status: "done" as const }));
                  // Keep streaming=true while the typewriter animates the text.
                  return {
                    ...msg,
                    content: msg.content,
                    fullContent: event.result_summary || "(no response)",
                    streaming: true,
                    steps,
                    rawResult: event.raw_result,
                    chart: event.chart,
                    analytics: event.analytics,
                    sql: event.sql,
                    warnings: event.warnings,
                    intent: event.intent,
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

            if (event.type === "final") {
              startTypewriter(assistantId);
              // After typewriter ideally finishes, mark not streaming.
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

  return { messages, busy, sendMessage, stop, clear };
}
