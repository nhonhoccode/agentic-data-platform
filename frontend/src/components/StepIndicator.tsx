import { CheckCircle2, Loader2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Step {
  node: string;
  label: string;
  status: "pending" | "active" | "done";
}

interface StepIndicatorProps {
  steps: Step[];
}

export function StepIndicator({ steps }: StepIndicatorProps) {
  if (steps.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {steps.map((step, idx) => (
        <div
          key={`${step.node}-${idx}`}
          className={cn(
            "flex items-center gap-1.5 rounded-md border-2 border-black px-2.5 py-1 text-xs font-bold neo-shadow-sm",
            step.status === "active" && "bg-pink-300 animate-pulse",
            step.status === "done" && "bg-lime-300",
            step.status === "pending" && "bg-white text-zinc-500",
          )}
        >
          {step.status === "active" && <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={3} />}
          {step.status === "done" && <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={3} />}
          {step.status === "pending" && <Circle className="h-3.5 w-3.5" strokeWidth={3} />}
          <span className="uppercase tracking-tight">{step.label}</span>
        </div>
      ))}
    </div>
  );
}
