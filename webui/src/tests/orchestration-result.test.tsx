// webui/src/tests/orchestration-result.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OrchestrationResult } from "@/components/orchestration/OrchestrationResult";
import type { OrchestrationPlan } from "@/lib/types";

const completedPlan: OrchestrationPlan = {
  goal: "add login",
  tasks: [
    {
      id: "t0",
      title: "分析",
      description: "x",
      role: "analyst",
      status: "completed",
      dependencies: [],
      result: "分析完成",
    },
    {
      id: "t1",
      title: "编码",
      description: "x",
      role: "developer",
      status: "completed",
      dependencies: ["t0"],
      result: "编码完成",
    },
  ],
};

const mixedPlan: OrchestrationPlan = {
  goal: "add login",
  tasks: [
    {
      id: "t0",
      title: "分析",
      description: "x",
      role: "analyst",
      status: "completed",
      dependencies: [],
      result: "ok",
    },
    {
      id: "t1",
      title: "编码",
      description: "x",
      role: "developer",
      status: "failed",
      dependencies: ["t0"],
      error: "timeout",
    },
  ],
};

describe("OrchestrationResult", () => {
  it("shows completed task count", () => {
    render(<OrchestrationResult plan={completedPlan} summary="done" />);
    // Should show "2/2 成功"
    expect(screen.getByText(/2\/2/)).toBeDefined();
  });

  it("shows failed task error", () => {
    render(<OrchestrationResult plan={mixedPlan} summary="partial" />);
    expect(screen.getByText(/timeout/)).toBeDefined();
  });

  it("renders task titles", () => {
    render(<OrchestrationResult plan={completedPlan} />);
    expect(screen.getByText("分析")).toBeDefined();
    expect(screen.getByText("编码")).toBeDefined();
  });
});
