// webui/src/components/orchestration/OrchestrationCard.tsx
import { useState } from "react";
import { ChevronRight, GitBranch } from "lucide-react";
import type { OrchestrationPlan } from "@/lib/types";
import { TaskDAGView } from "./TaskDAGView";
import { OrchestrationResult } from "./OrchestrationResult";
import { cn } from "@/lib/utils";

interface OrchestrationCardProps {
  plan: OrchestrationPlan;
  phase: "plan" | "executing" | "complete";
  summary?: string;
  isStreaming?: boolean;
}

export function OrchestrationCard({
  plan,
  phase,
  summary,
  isStreaming,
}: OrchestrationCardProps) {
  const isActive = phase === "plan" || phase === "executing";
  const [expanded, setExpanded] = useState(isActive);
  const completed = plan.tasks.filter((t) => t.status === "completed").length;
  const total = plan.tasks.length;

  return (
    <div className="my-2 rounded-lg border border-border/60 bg-card/50 overflow-hidden">
      {/* Header bar -- always visible */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className={cn(
          "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-muted/40",
          isActive && "cursor-default hover:bg-transparent",
        )}
      >
        <GitBranch
          className={cn("h-4 w-4 shrink-0", isActive && "text-blue-500")}
        />
        <span className="flex-1 font-medium text-foreground min-w-0 truncate">
          {isActive ? "编排中" : "编排完成"} · {plan.goal}
        </span>
        <span className="text-xs text-muted-foreground tabular-nums shrink-0">
          {completed}/{total}
        </span>
        {!isActive && (
          <ChevronRight
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
              expanded && "rotate-90",
            )}
          />
        )}
      </button>

      {/* Expanded body */}
      {(expanded || isActive) && (
        <div className="px-3 pb-3 space-y-3">
          <div
            className={cn(
              "rounded-md border border-border/30 bg-muted/20 p-2",
              isStreaming && "animate-pulse",
            )}
          >
            <TaskDAGView plan={plan} />
          </div>

          {isActive && (
            <p className="text-xs text-muted-foreground">
              {phase === "plan"
                ? "拆解中..."
                : `执行中 (${completed}/${total} 完成)`}
            </p>
          )}

          {phase === "complete" && (
            <OrchestrationResult plan={plan} summary={summary} />
          )}
        </div>
      )}
    </div>
  );
}
