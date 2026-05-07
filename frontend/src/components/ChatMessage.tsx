import type { Message } from "@/hooks/useChat";
import { Markdown } from "./Markdown";
import { ChartView } from "./ChartView";
import { DataTable } from "./DataTable";
import { StepIndicator } from "./StepIndicator";
import { AnalyticsPanel } from "./AnalyticsPanel";
import { Bot, User, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const rows = extractRows(message.rawResult);

  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      <div
        className={cn(
          "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div className={cn("flex max-w-[85%] flex-col gap-2", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm",
            isUser ? "bg-primary text-primary-foreground" : "bg-muted",
          )}
        >
          {isUser ? (
            <span>{message.content}</span>
          ) : message.streaming ? (
            <span>
              {message.content}
              <span className="animate-blink">▋</span>
            </span>
          ) : (
            <Markdown content={message.content || "_(không có nội dung)_"} />
          )}
        </div>

        {!isUser && message.steps && message.steps.length > 0 && <StepIndicator steps={message.steps} />}

        {!isUser && message.chart && <ChartView chart={message.chart} />}

        {!isUser && rows.length > 0 && <DataTable rows={rows} />}

        {!isUser && message.analytics && <AnalyticsPanel analytics={message.analytics} />}

        {!isUser && message.sql && (
          <details className="rounded-lg border p-2 text-xs">
            <summary className="cursor-pointer font-medium text-muted-foreground">SQL đã chạy</summary>
            <pre className="mt-2 overflow-x-auto rounded bg-zinc-900 p-2 text-zinc-100">{message.sql}</pre>
          </details>
        )}

        {!isUser && message.warnings && message.warnings.length > 0 && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            <ul className="space-y-0.5">
              {message.warnings.map((w, i) => (
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
