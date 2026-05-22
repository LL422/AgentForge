// webui/src/tests/task-dag-view.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TaskDAGView } from "@/components/orchestration/TaskDAGView";
import type { OrchestrationPlan } from "@/lib/types";

const samplePlan: OrchestrationPlan = {
  goal: "add login",
  tasks: [
    {
      id: "task-0",
      title: "分析",
      description: "分析现有代码",
      role: "analyst",
      status: "completed",
      dependencies: [],
    },
    {
      id: "task-1",
      title: "编码",
      description: "实现登录",
      role: "developer",
      status: "running",
      dependencies: ["task-0"],
    },
    {
      id: "task-2",
      title: "测试",
      description: "编写测试",
      role: "tester",
      status: "pending",
      dependencies: ["task-1"],
    },
    {
      id: "task-3",
      title: "审查",
      description: "代码审查",
      role: "reviewer",
      status: "pending",
      dependencies: ["task-1"],
    },
  ],
};

describe("TaskDAGView", () => {
  it("renders all task nodes", () => {
    render(<TaskDAGView plan={samplePlan} />);
    // SVG <text> elements for role labels and titles may share
    // the same Chinese characters, so we use getAllByText.
    expect(screen.getAllByText("分析").length).toBeGreaterThan(0);
    expect(screen.getAllByText("编码").length).toBeGreaterThan(0);
    expect(screen.getAllByText("测试").length).toBeGreaterThan(0);
    expect(screen.getAllByText("审查").length).toBeGreaterThan(0);
  });

  it("renders an SVG element", () => {
    const { container } = render(<TaskDAGView plan={samplePlan} />);
    expect(container.querySelector("svg")).toBeTruthy();
  });

  it("renders a single task without crashing", () => {
    const singlePlan: OrchestrationPlan = {
      goal: "test",
      tasks: [
        {
          id: "t0",
          title: "单任务",
          description: "x",
          role: "developer",
          status: "pending",
          dependencies: [],
        },
      ],
    };
    render(<TaskDAGView plan={singlePlan} />);
    expect(screen.getByText("单任务")).toBeDefined();
  });
});
