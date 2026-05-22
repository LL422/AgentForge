// webui/src/tests/orchestration-card.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OrchestrationCard } from "@/components/orchestration/OrchestrationCard";
import type { OrchestrationPlan } from "@/lib/types";

const activePlan: OrchestrationPlan = {
  goal: "add login",
  tasks: [
    {
      id: "t0",
      title: "分析",
      description: "x",
      role: "analyst",
      status: "completed",
      dependencies: [],
      result: "done",
    },
    {
      id: "t1",
      title: "编码",
      description: "x",
      role: "developer",
      status: "running",
      dependencies: ["t0"],
    },
  ],
};

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
      result: "done",
    },
    {
      id: "t1",
      title: "编码",
      description: "x",
      role: "developer",
      status: "completed",
      dependencies: ["t0"],
      result: "done",
    },
  ],
};

describe("OrchestrationCard", () => {
  it("renders SVG in executing phase", () => {
    const { container } = render(
      <OrchestrationCard plan={activePlan} phase="executing" />,
    );
    expect(container.querySelector("svg")).toBeTruthy();
  });

  it("shows goal text", () => {
    render(
      <OrchestrationCard
        plan={completedPlan}
        phase="complete"
        summary="All done"
      />,
    );
    expect(screen.getByText(/add login/)).toBeDefined();
  });

  it("shows completed count", () => {
    render(<OrchestrationCard plan={completedPlan} phase="complete" />);
    expect(screen.getByText(/2\/2/)).toBeDefined();
  });
});
