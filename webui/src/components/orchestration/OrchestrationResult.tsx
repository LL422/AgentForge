// webui/src/components/orchestration/OrchestrationResult.tsx
import { CheckCircle2, XCircle } from "lucide-react";
import type { OrchestrationPlan } from "@/lib/types";

interface Props {
  plan: OrchestrationPlan;
  summary?: string;
}

export function OrchestrationResult({ plan, summary }: Props) {
  const completed = plan.tasks.filter((t) => t.status === "completed").length;
  const failed = plan.tasks.filter((t) => t.status === "failed").length;
  const allSuccess = failed === 0;

  return (
    <div className="rounded-lg border border-border/60 bg-card p-3 space-y-2 text-sm">
      {/* Header */}
      <div className="flex items-center gap-2">
        {allSuccess ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
        ) : (
          <XCircle className="h-4 w-4 text-amber-500" />
        )}
        <span className="font-medium text-foreground">
          {allSuccess ? "编排完成" : "部分完成"} · {plan.goal}
        </span>
        <span className="text-muted-foreground tabular-nums">
          {completed}/{plan.tasks.length} 成功
          {failed > 0 && ` · ${failed} 失败`}
        </span>
      </div>

      {/* Summary */}
      {summary && (
        <p className="text-muted-foreground text-xs leading-relaxed">{summary}</p>
      )}

      {/* Per-task results */}
      <ul className="space-y-1.5">
        {plan.tasks.map((t) => (
          <li key={t.id} className="flex items-start gap-2 text-xs">
            {t.status === "completed" ? (
              <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0 text-emerald-500" />
            ) : t.status === "failed" ? (
              <XCircle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-red-500" />
            ) : (
              <span className="h-3.5 w-3.5 mt-0.5 shrink-0 rounded-full bg-muted-foreground/30" />
            )}
            <div className="min-w-0">
              <span className="font-medium">{t.title}</span>
              {t.error && <span className="ml-2 text-red-500">{t.error}</span>}
              {t.result && t.status === "completed" && (
                <p className="text-muted-foreground truncate">{t.result.slice(0, 120)}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
