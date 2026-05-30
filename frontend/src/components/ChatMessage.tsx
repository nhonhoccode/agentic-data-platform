import type { Message } from "@/hooks/useChat";
import { Markdown } from "./Markdown";
import { ChartView } from "./ChartView";
import { DataTable } from "./DataTable";
import { ToolTimeline } from "./ToolTimeline";
import { WebSearchResults } from "./WebSearchResults";
import { AnalyticsPanel } from "./AnalyticsPanel";
import { Bot, User, AlertTriangle, Code2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: Message;
  /** Called when user clicks "Vẫn tra cứu Internet" on an OOD block */
  onRetryWithForceSearch?: (query: string) => void;
  /** Called when user clicks "Bật & hỏi lại" on a toggle-off block */
  onTurnOnToggle?: (query: string) => void;
  /** True when current user has `web_search` feature granted */
  webSearchAllowed?: boolean;
}

// Warnings that are already surfaced visually by a dedicated block — hide
// from the generic warnings panel to avoid duplicate orange noise.
const REDUNDANT_WARNING_PREFIXES = [
  "out_of_domain:",
  "web_search_blocked:",
  "web_search_disabled:",
  "sql_empty_fallback_to_web_search",
];

export function ChatMessage({
  message,
  onRetryWithForceSearch,
  onTurnOnToggle,
  webSearchAllowed = true,
}: ChatMessageProps) {
  const isUser = message.role === "user";
  const rows = extractRows(message.rawResult);
  const visibleWarnings = (message.warnings ?? []).filter(
    (w) => !REDUNDANT_WARNING_PREFIXES.some((p) => w.startsWith(p)),
  );

  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md border-2 border-black neo-shadow-sm",
          isUser ? "bg-cyan-300" : "bg-pink-400",
        )}
      >
        {isUser ? (
          <User className="h-5 w-5 text-black" strokeWidth={3} />
        ) : (
          <Bot className="h-5 w-5 text-black" strokeWidth={3} />
        )}
      </div>

      <div className={cn("flex max-w-[85%] flex-col gap-2", isUser && "items-end")}>
        {/* Agent thought process sits ABOVE the answer — Claude.ai style. While
            streaming this shows the full live timeline; once done it collapses
            to a subtle "Đã suy nghĩ trong Xs" chip the user can click to expand. */}
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <ToolTimeline toolCalls={message.toolCalls} streaming={message.streaming} />
        )}

        <div
          className={cn(
            "rounded-md border-2 border-black px-4 py-3 text-sm font-medium neo-shadow",
            isUser ? "bg-yellow-300" : "bg-white",
          )}
        >
          {isUser ? (
            <span className="font-bold">{message.content}</span>
          ) : (
            <span className="block">
              <Markdown content={message.content || (message.streaming ? "" : "_(không có nội dung)_")} />
              {message.streaming && (
                <span className="ml-0.5 inline-block animate-blink align-baseline font-bold">▋</span>
              )}
            </span>
          )}
        </div>

        {!isUser && message.webSearch && (
          <WebSearchResults
            webSearch={message.webSearch}
            onRetryWithForceSearch={onRetryWithForceSearch}
            onTurnOnToggle={onTurnOnToggle}
            webSearchAllowed={webSearchAllowed}
          />
        )}

        {!isUser && message.chart && <ChartView chart={message.chart} />}

        {!isUser && rows.length > 0 && <DataTable rows={rows} />}

        {!isUser && message.analytics && <AnalyticsPanel analytics={message.analytics} />}

        {!isUser && message.sql && (
          <details className="rounded-md border-2 border-black bg-white p-2 text-xs neo-shadow-sm">
            <summary className="flex cursor-pointer items-center gap-1.5 font-bold uppercase tracking-wide">
              <Code2 className="h-3.5 w-3.5" strokeWidth={3} />
              SQL đã chạy
            </summary>
            <pre className="mt-2 overflow-x-auto rounded-sm border-2 border-black bg-zinc-900 p-2 text-zinc-100">
              {message.sql}
            </pre>
          </details>
        )}

        {!isUser && visibleWarnings.length > 0 && (
          <div className="flex items-start gap-2 rounded-md border-2 border-black bg-orange-300 p-2 text-xs text-black neo-shadow-sm">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" strokeWidth={3} />
            <ul className="space-y-0.5 font-bold">
              {visibleWarnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function extractRows(raw: Record<string, unknown> | undefined): Record<string, unknown>[] {
  if (!raw) return [];
  for (const key of ["data", "series", "matches"]) {
    const v = raw[key];
    if (Array.isArray(v) && v.length && typeof v[0] === "object") return v as Record<string, unknown>[];
  }
  return [];
}
