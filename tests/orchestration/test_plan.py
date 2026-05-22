# tests/orchestration/test_plan.py
import pytest
from nanobot.orchestration.plan import (
    TaskStatus,
    TaskNode,
    TaskPlan,
    validate_plan,
    PlanValidationError,
)


class TestTaskNode:
    def test_create_pending_node(self):
        node = TaskNode(
            id="task-0",
            title="分析代码",
            description="阅读并分析现有代码结构",
            role="analyst",
            dependencies=[],
        )
        assert node.status == TaskStatus.PENDING
        assert node.result is None
        assert node.error is None

    def test_dependencies_default(self):
        node = TaskNode(
            id="task-1",
            title="写代码",
            description="实现功能",
            role="developer",
        )
        assert node.dependencies == []


class TestTaskPlan:
    def test_ready_tasks_empty_deps(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(id="t0", title="a", description="a", role="analyst"),
            TaskNode(id="t1", title="b", description="b", role="developer"),
        ])
        ready = plan.ready_tasks()
        assert len(ready) == 2
        assert {t.id for t in ready} == {"t0", "t1"}

    def test_ready_tasks_with_deps_pending(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(id="t0", title="a", description="a", role="analyst"),
            TaskNode(id="t1", title="b", description="b", role="developer", dependencies=["t0"]),
        ])
        ready = plan.ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t0"

    def test_ready_tasks_after_completion(self):
        t0 = TaskNode(id="t0", title="a", description="a", role="analyst")
        t1 = TaskNode(id="t1", title="b", description="b", role="developer", dependencies=["t0"])
        plan = TaskPlan(goal="test", tasks=[t0, t1])
        t0.status = TaskStatus.COMPLETED
        ready = plan.ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t1"

    def test_ready_excludes_running_and_failed(self):
        t0 = TaskNode(id="t0", title="a", description="a", role="analyst")
        t0.status = TaskStatus.RUNNING
        plan = TaskPlan(goal="test", tasks=[t0])
        assert len(plan.ready_tasks()) == 0

    def test_is_terminal_all_completed(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(
                id="t0", title="a", description="a", role="analyst",
                status=TaskStatus.COMPLETED,
            ),
        ])
        assert plan.is_terminal()
        assert plan.is_success()

    def test_is_terminal_with_failed(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(
                id="t0", title="a", description="a", role="analyst",
                status=TaskStatus.FAILED,
            ),
            TaskNode(
                id="t1", title="b", description="b", role="developer",
                dependencies=["t0"],
            ),
        ])
        assert plan.is_terminal()
        assert not plan.is_success()

    def test_is_terminal_still_running(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(
                id="t0", title="a", description="a", role="analyst",
                status=TaskStatus.RUNNING,
            ),
        ])
        assert not plan.is_terminal()

    def test_has_running(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(
                id="t0", title="a", description="a", role="analyst",
                status=TaskStatus.RUNNING,
            ),
            TaskNode(id="t1", title="b", description="b", role="developer"),
        ])
        assert plan.has_running()

    def test_to_dict(self):
        plan = TaskPlan(goal="add login", tasks=[
            TaskNode(id="t0", title="analyze", description="analyze auth", role="analyst"),
        ])
        d = plan.to_dict()
        assert d["goal"] == "add login"
        assert len(d["tasks"]) == 1
        assert d["tasks"][0]["id"] == "t0"
        assert d["tasks"][0]["role"] == "analyst"


class TestValidatePlan:
    def test_valid_plan(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(id="t0", title="a", description="a", role="analyst"),
            TaskNode(id="t1", title="b", description="b", role="developer", dependencies=["t0"]),
        ])
        validate_plan(plan)  # does not raise

    def test_cycle_detection(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(id="t0", title="a", description="a", role="analyst", dependencies=["t1"]),
            TaskNode(id="t1", title="b", description="b", role="developer", dependencies=["t0"]),
        ])
        with pytest.raises(PlanValidationError, match="cycle"):
            validate_plan(plan)

    def test_missing_dependency_reference(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(id="t0", title="a", description="a", role="analyst", dependencies=["t99"]),
        ])
        with pytest.raises(PlanValidationError, match="not found"):
            validate_plan(plan)

    def test_too_many_tasks(self):
        tasks = [TaskNode(id=f"t{i}", title="x", description="x", role="analyst") for i in range(7)]
        plan = TaskPlan(goal="test", tasks=tasks)
        with pytest.raises(PlanValidationError, match="6"):
            validate_plan(plan)

    def test_unknown_role(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(id="t0", title="a", description="a", role="hacker"),
        ])
        with pytest.raises(PlanValidationError, match="role"):
            validate_plan(plan)

    def test_no_entry_point(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(id="t0", title="a", description="a", role="analyst", dependencies=["t1"]),
            TaskNode(id="t1", title="b", description="b", role="developer", dependencies=["t0"]),
        ])
        with pytest.raises(PlanValidationError):
            validate_plan(plan)

    def test_self_dependency(self):
        plan = TaskPlan(goal="test", tasks=[
            TaskNode(id="t0", title="a", description="a", role="analyst", dependencies=["t0"]),
        ])
        with pytest.raises(PlanValidationError):
            validate_plan(plan)
