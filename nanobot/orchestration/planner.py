# nanobot/orchestration/planner.py
"""Phase 1: LLM-based task decomposition.

TaskPlanner uses an LLM provider to decompose a user goal into a structured
:class:`~nanobot.orchestration.plan.TaskPlan`.  On failure it falls back to a
single-task plan so the caller always gets a valid plan.
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from nanobot.orchestration.plan import (
    PlanValidationError,
    TaskNode,
    TaskPlan,
    validate_plan,
)
from nanobot.utils.prompt_templates import render_template


class TaskPlanner:
    """Decompose a user goal into a :class:`TaskPlan` via an LLM provider."""

    def __init__(self, provider: Any, model: str, max_retries: int = 2) -> None:
        self._provider = provider
        self._model = model
        self._max_retries = max_retries

    async def plan(self, goal: str, context_hint: str | None = None) -> TaskPlan:
        """Decompose *goal* into a structured task plan.

        Parameters
        ----------
        goal:
            The high-level goal to decompose.
        context_hint:
            Optional extra context appended to the prompt.

        Returns
        -------
        TaskPlan
            A validated plan, or a single-task fallback plan on failure.
        """
        prompt = render_template("orchestration/plan.md", goal=goal)
        if context_hint:
            prompt += f"\n\n## 额外注意事项\n{context_hint}"

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": prompt},
        ]

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._provider.chat(
                    messages=messages,
                    tools=None,
                    model=self._model,
                )
                plan = self._parse_response(response.content, goal)
                validate_plan(plan)
                return plan
            except (PlanValidationError, json.JSONDecodeError, Exception) as e:
                logger.warning("Plan attempt {} failed: {}", attempt + 1, e)
                if attempt == self._max_retries:
                    return self._fallback_plan(goal, str(e))

        return self._fallback_plan(goal)

    def _parse_response(self, content: str, goal: str) -> TaskPlan:
        """Parse LLM JSON content into a TaskPlan."""
        data = json.loads(content)
        tasks_raw = data.get("tasks", [data] if isinstance(data, dict) else [])
        tasks = [
            TaskNode(
                id=t.get("id", f"task-{i}"),
                title=t.get("title", "未命名任务"),
                description=t.get("description", ""),
                role=t.get("role", "analyst"),
                dependencies=t.get("dependencies", []),
            )
            for i, t in enumerate(tasks_raw)
        ]
        return TaskPlan(goal=goal, tasks=tasks)

    def _fallback_plan(self, goal: str, error: str = "") -> TaskPlan:
        """Return a single-task fallback plan."""
        return TaskPlan(
            goal=goal,
            tasks=[
                TaskNode(
                    id="task-0",
                    title="执行任务",
                    description=(
                        f"{goal}\n\n计划拆解失败: {error}" if error else goal
                    ),
                    role="developer",
                    dependencies=[],
                )
            ],
        )
