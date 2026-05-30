import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  Sparkles,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolCall } from "@/hooks/useChat";

const PARENT_LABELS: Record<string, string> = {
  sql_agent: "SQL agent",
  viz_agent: "Viz agent",
  analytic_agent: "Analytic agent",
  time_series_agent: "Time-series agent",
  retrieval_agent: "Retrieval agent",
  insight_agent: "Insight agent",
  chat_agent: "Chat agent",
  web_search_agent: "Web search agent",
};

interface ToolTimelineProps {
  toolCalls: ToolCall[];
  streaming?: boolean;
}

interface ParentGroup {
  parent: string;
  calls: ToolCall[];
}

function groupByParent(toolCalls: ToolCall[]): ParentGroup[] {
  const groups: ParentGroup[] = [];
  const indexByParent = new Map<string, number>();
  for (const call of toolCalls) {
    const idx = indexByParent.get(call.parent);
    if (idx === undefined) {
      indexByParent.set(call.parent, groups.length);
      groups.push({ parent: call.parent, calls: [call] });
    } else {
      groups[idx].calls.push(call);
    }
  }
  return groups;
}

function formatElapsed(ms: number): string {
  // Anything under 100ms reads as "instant" — show a friendlier glyph instead
  // of a noisy 0ms / 12ms.
  if (ms < 100) return "<0.1s";
  if (ms < 1000) return `${Math.round(ms / 100) / 10}s`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function useEllipsis(active: boolean): string {
  // Cycle through ".", "..", "..." every 350ms while active. Acts as a
  // breathing indicator on running tools.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setTick((t) => (t + 1) % 4), 350);
    return () => window.clearInterval(id);
  }, [active]);
  return ".".repeat(tick);
}

function useLiveTick(active: boolean): number {
  // Re-render every 100ms while active so elapsed counters stay current.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) {
      setNow(Date.now());
      return;
    }
    const id = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}

export function ToolTimeline({ toolCalls, streaming }: ToolTimelineProps) {
  const hasActive = toolCalls.some((c) => c.status === "start");
  const isWorking = streaming === true || hasActive;
  const now = useLiveTick(hasActive);
  const dots = useEllipsis(hasActive);

  // Auto-collapse once streaming finishes. Tracking the transition via a ref
  // so manually expanding a finished timeline stays expanded.
  const [expanded, setExpanded] = useState(true);
  const prevWorking = useRef(isWorking);
  useEffect(() => {
    if (prevWorking.current && !isWorking) {
      setExpanded(false);
    }
    prevWorking.current = isWorking;
  }, [isWorking]);

  if (!toolCalls || toolCalls.length === 0) return null;

  const doneCount = toolCalls.filter((c) => c.status === "done").length;
  const errorCount = toolCalls.filter((c) => c.status === "error").length;
  const totalCount = toolCalls.length;
  const totalElapsed = toolCalls.reduce((acc, c) => {
    if (c.startedAt === undefined) return acc;
    const end = c.status === "start" ? now : c.endedAt ?? now;
    return acc + Math.max(0, end - c.startedAt);
  }, 0);

  // Collapsed: ultra-minimal one-line "Đã suy nghĩ trong Xs" — Claude.ai style.
  // No box, no neo-shadow — just a small subtle inline chip that sits above the
  // assistant's answer. Click to expand the full timeline below it.
  if (!expanded) {
    const elapsedLabel =
      totalElapsed >= 100 ? ` trong ${formatElapsed(totalElapsed)}` : "";
    const stepHint = totalCount > 1 ? ` · ${totalCount} bước` : "";
    const label = errorCount > 0
      ? `Đã suy nghĩ${elapsedLabel}${stepHint} · ${errorCount} lỗi`
      : `Đã suy nghĩ${elapsedLabel}${stepHint}`;
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="group -mb-1 inline-flex items-center gap-1.5 self-start rounded-full px-2 py-0.5 text-[11px] font-medium italic text-zinc-500 hover:bg-zinc-100 hover:text-black"
      >
        {errorCount > 0 ? (
          <XCircle className="h-3 w-3 text-red-600" strokeWidth={3} />
        ) : (
          <Sparkles
            className="h-3 w-3 text-pink-500 group-hover:text-pink-600"
            strokeWidth={3}
          />
        )}
        <span>{label}</span>
        <ChevronDown
          className="h-3 w-3 transition-transform group-hover:translate-y-0.5"
          strokeWidth={3}
        />
      </button>
    );
  }

  const groups = groupByParent(toolCalls);

  return (
    <div className="flex flex-col gap-2 rounded-md border-2 border-black bg-white p-3 text-sm neo-shadow-sm">
      {!isWorking && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="flex items-center justify-between gap-2 border-b border-zinc-200 pb-1.5 text-[10px] font-medium italic text-zinc-500 hover:text-black"
        >
          <span className="flex items-center gap-1.5">
            {errorCount > 0 ? (
              <XCircle className="h-3 w-3 text-red-600" strokeWidth={3} />
            ) : (
              <Sparkles className="h-3 w-3 text-pink-500" strokeWidth={3} />
            )}
            <span>
              Đã suy nghĩ
              {totalElapsed >= 100 && ` trong ${formatElapsed(totalElapsed)}`}
              {totalCount > 1 && ` · ${totalCount} bước`}
            </span>
          </span>
          <span className="flex items-center gap-1 not-italic uppercase tracking-tight">
            Thu gọn
            <ChevronUp className="h-3 w-3" strokeWidth={3} />
          </span>
        </button>
      )}
      {groups.map((group, gi) => (
        <div key={`${group.parent}-${gi}`} className="border-l-2 border-black pl-3">
          <div className="mb-1.5 text-xs font-bold uppercase tracking-tight">
            {PARENT_LABELS[group.parent] ?? group.parent}
          </div>
          <ul className="flex flex-col gap-1">
            {group.calls.map((call, ci) => {
              const isStart = call.status === "start";
              const elapsed =
                call.startedAt !== undefined
                  ? (isStart ? now : call.endedAt ?? now) - call.startedAt
                  : null;
              return (
                <li
                  key={`${call.tool}-${ci}`}
                  className={cn(
                    "flex items-start gap-2 rounded-sm leading-tight transition-colors",
                    isStart && "bg-pink-100 px-1 py-0.5 animate-pulse",
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 inline-flex h-4 w-4 flex-shrink-0 items-center justify-center",
                      call.status === "error" && "text-red-600",
                      call.status === "done" && "text-lime-600",
                      isStart && "text-pink-500",
                    )}
                  >
                    {isStart && (
                      <Loader2 className="h-4 w-4 animate-spin" strokeWidth={3} />
                    )}
                    {call.status === "done" && (
                      <CheckCircle2 className="h-4 w-4" strokeWidth={3} />
                    )}
                    {call.status === "error" && (
                      <XCircle className="h-4 w-4" strokeWidth={3} />
                    )}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="font-semibold">
                        {call.label}
                        {isStart && (
                          <span className="inline-block w-4 text-pink-500">
                            {dots}
                          </span>
                        )}
                      </span>
                      {elapsed !== null && (elapsed >= 100 || isStart) && (
                        <span
                          className={cn(
                            "ml-auto flex-shrink-0 font-mono text-[10px] tabular-nums",
                            isStart ? "text-pink-600" : "text-zinc-400",
                          )}
                        >
                          {formatElapsed(elapsed)}
                        </span>
                      )}
                    </div>
                    {call.detail && (
                      <div className="mt-0.5 break-words font-mono text-[11px] italic text-zinc-500">
                        {call.detail}
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
