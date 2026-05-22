# nanobot/orchestration/plan.py
"""Task plan data model for multi-agent orchestration."""
from __future__ import annotations

import enum
from typing import Any

import pydantic


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskNode(pydantic.BaseModel):
    id: str
    title: str
    description: str
    role: str = "analyst"
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = pydantic.Field(default_factory=list)
    result: str | None = None
    error: str | None = None


class TaskPlan(pydantic.BaseModel):
    goal: str
    tasks: list[TaskNode]

    def ready_tasks(self) -> list[TaskNode]:
        """Return tasks whose dependencies are all COMPLETED and status is PENDING or READY."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        ready: list[TaskNode] = []
        for t in self.tasks:
            if t.status not in (TaskStatus.PENDING, TaskStatus.READY):
                continue
            if all(dep in completed_ids for dep in t.dependencies):
                ready.append(t)
        return ready

    def has_running(self) -> bool:
        return any(t.status == TaskStatus.RUNNING for t in self.tasks)

    def is_terminal(self) -> bool:
        """True when no task can make further progress (all done or blocked by failure)."""
        failed_ids = {t.id for t in self.tasks if t.status == TaskStatus.FAILED}
        # Propagate failure transitively: any task whose dep is failed/blocked is blocked
        blocked = set(failed_ids)
        changed = True
        while changed:
            changed = False
            for t in self.tasks:
                if t.id in blocked:
                    continue
                if any(dep in blocked for dep in t.dependencies):
                    blocked.add(t.id)
                    changed = True
        for t in self.tasks:
            if t.id in blocked:
                continue
            if t.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                return False
        return True

    def is_success(self) -> bool:
        return all(t.status == TaskStatus.COMPLETED for t in self.tasks)

    def completed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)

    def failed_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "role": t.role,
                    "status": t.status.value,
                    "dependencies": list(t.dependencies),
                    "result": t.result,
                    "error": t.error,
                }
                for t in self.tasks
            ],
        }


class PlanValidationError(Exception):
    pass


def validate_plan(plan: TaskPlan) -> None:
    task_ids = {t.id for t in plan.tasks}

    # 1. Max tasks
    if len(plan.tasks) > 6:
        raise PlanValidationError(f"Max 6 tasks, got {len(plan.tasks)}")

    # 2. No duplicate ids
    if len(task_ids) != len(plan.tasks):
        raise PlanValidationError("Duplicate task IDs")

    # 3. Role validity
    from nanobot.orchestration.roles import WORKER_ROLES
    for t in plan.tasks:
        if t.role not in WORKER_ROLES:
            raise PlanValidationError(f"Unknown role: {t.role}")

    # 4. Dependency reference integrity
    for t in plan.tasks:
        for dep in t.dependencies:
            if dep == t.id:
                raise PlanValidationError(f"Task {t.id} depends on itself")
            if dep not in task_ids:
                raise PlanValidationError(f"Dependency {dep!r} not found for task {t.id}")

    # 5. Cycle detection via topological sort (Kahn's algorithm)
    in_degree: dict[str, int] = {t.id: len(t.dependencies) for t in plan.tasks}
    adj: dict[str, list[str]] = {t.id: [] for t in plan.tasks}
    for t in plan.tasks:
        for dep in t.dependencies:
            adj[dep].append(t.id)

    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    sorted_count = 0
    while queue:
        node = queue.pop()
        sorted_count += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if sorted_count != len(plan.tasks):
        raise PlanValidationError("cycle detected in task dependencies")
