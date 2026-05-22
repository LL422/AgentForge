# tests/orchestration/test_worker.py
from pathlib import Path

from nanobot.orchestration.worker import build_worker_prompt
from nanobot.orchestration.plan import TaskNode


def test_build_worker_prompt_includes_role_and_task():
    workspace = Path("/home/user/project")
    prompt = build_worker_prompt(
        task=TaskNode(
            id="task-0",
            title="分析代码",
            description="分析 auth 模块的实现",
            role="analyst",
        ),
        workspace=workspace,
    )
    assert "需求分析" in prompt  # in system_prompt via "需求分析师"
    assert "分析 auth 模块的实现" in prompt
    assert str(workspace) in prompt


def test_build_worker_prompt_includes_previous_results():
    prompt = build_worker_prompt(
        task=TaskNode(
            id="task-1",
            title="实现登录",
            description="创建登录端点",
            role="developer",
            dependencies=["task-0"],
        ),
        workspace=Path("/tmp"),
        previous_results={"task-0": "分析结果: 使用 JWT 认证"},
    )
    assert "分析结果: 使用 JWT 认证" in prompt
    assert "前置任务" in prompt


def test_build_worker_prompt_no_previous_when_no_deps():
    prompt = build_worker_prompt(
        task=TaskNode(
            id="task-0",
            title="独立任务",
            description="无需依赖",
            role="analyst",
        ),
        workspace=Path("/tmp"),
        previous_results={},
    )
    assert "前置任务" not in prompt
