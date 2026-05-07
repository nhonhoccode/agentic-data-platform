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
            "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs",
            step.status === "active" && "border-primary bg-primary/10 text-primary",
            step.status === "done" && "border-emerald-300 bg-emerald-50 text-emerald-700",
            step.status === "pending" && "border-border text-muted-foreground",
          )}
        >
          {step.status === "active" && <Loader2 className="h-3 w-3 animate-spin" />}
          {step.status === "done" && <CheckCircle2 className="h-3 w-3" />}
          {step.status === "pending" && <Circle className="h-3 w-3" />}
          <span>{step.label}</span>
        </div>
      ))}
    </div>
  );
}
