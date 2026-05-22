# tests/orchestration/test_integration.py
"""Integration tests for the full orchestration three-phase flow with mocked LLM providers."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nanobot.agent.tools.context import ToolContext
from nanobot.agent.tools.orchestrate import OrchestrationTool
from nanobot.providers.base import LLMProvider, LLMResponse

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

VALID_PLAN_JSON = json.dumps({
    "tasks": [
        {
            "id": "task-0",
            "title": "需求分析",
            "description": "分析项目结构，确定实现方案",
            "role": "analyst",
            "dependencies": [],
        },
        {
            "id": "task-1",
            "title": "编写代码",
            "description": "实现 hello CLI 功能",
            "role": "developer",
            "dependencies": ["task-0"],
        },
        {
            "id": "task-2",
            "title": "代码审查",
            "description": "审查新代码的质量和安全性",
            "role": "reviewer",
            "dependencies": ["task-1"],
        },
    ]
})

LONG_WORKER_RESPONSE = (
    "Worker task completed successfully. "
    "Created auth.py with login endpoint, added JWT token handling, "
    "and updated the routing configuration. All tests pass."
)


class HappyPathProvider(LLMProvider):
    """LLM provider that returns a valid plan then worker responses.

    The first ``chat()`` call returns a valid JSON plan; subsequent calls
    return simple worker results that cause the runner loop to finalize
    immediately (no tool calls).
    """

    def __init__(self, api_key="sk-test", api_base=None):
        super().__init__(api_key=api_key, api_base=api_base)
        self.call_count = 0

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            return LLMResponse(
                content=VALID_PLAN_JSON,
                finish_reason="stop",
                usage={"total_tokens": 120},
            )
        return LLMResponse(
            content=LONG_WORKER_RESPONSE,
            finish_reason="stop",
            usage={"total_tokens": 80},
        )

    def get_default_model(self):
        return "test-model"


class PlanFailureProvider(LLMProvider):
    """LLM provider that returns garbage JSON so the planner falls back.

    The planner retries up to *max_retries* (default 2, so 3 attempts).
    After those fail, a single-task fallback plan is created and one
    worker is spawned.
    """

    def __init__(self, api_key="sk-test", api_base=None):
        super().__init__(api_key=api_key, api_base=api_base)
        self.call_count = 0

    async def chat(self, messages, tools=None, model=None, **kwargs):
        self.call_count += 1
        # First 3 calls = planner retries (all garbage)
        if self.call_count <= 3:
            return LLMResponse(
                content="not valid json at all {{{[[[",
                finish_reason="stop",
                usage={},
            )
        # Worker responses (must be >= 50 chars to pass run_worker length check)
        return LLMResponse(
            content=LONG_WORKER_RESPONSE,
            finish_reason="stop",
            usage={"total_tokens": 60},
        )

    def get_default_model(self):
        return "test-model"


def _make_ctx(workspace: str, provider: LLMProvider, model: str = "test-model") -> ToolContext:
    """Build a minimal :class:`ToolContext` suitable for orchestration tests."""
    snapshot = MagicMock()
    snapshot.provider = provider
    snapshot.model = model
    return ToolContext(
        config=MagicMock(),
        workspace=workspace,
        provider_snapshot_loader=lambda: snapshot,
        subagent_manager=None,
        file_state_store=MagicMock(),
    )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestration_end_to_end(tmp_path):
    """Full three-phase orchestration: plan -> execute workers -> merge.

    Uses a mock provider that returns valid plan JSON on the first call
    and simple worker responses on subsequent calls.  The runner should
    dispatch three workers (analyst, developer, reviewer) and produce
    a merged summary.
    """
    provider = HappyPathProvider()
    ctx = _make_ctx(str(tmp_path), provider)
    tool = OrchestrationTool.create(ctx)

    result = await tool.execute(goal="给项目添加 hello CLI 功能")

    # Merge phase markers
    assert "编排完成" in result
    assert "hello CLI" in result

    # All 3 tasks should appear in the merged output
    for title in ["需求分析", "编写代码", "代码审查"]:
        assert title in result, f"Expected task '{title}' in merged output"

    # 1 plan call + 3 workers = 4 chat calls
    assert provider.call_count == 4, (
        f"Expected 4 chat calls (1 plan + 3 workers), got {provider.call_count}"
    )


@pytest.mark.asyncio
async def test_orchestration_fallback_on_plan_failure(tmp_path):
    """Graceful fallback when the planner cannot generate a valid plan.

    The provider returns garbage for the 3 planner retries, triggering a
    single-task fallback plan.  That single worker executes and the
    orchestration completes without errors.
    """
    provider = PlanFailureProvider()
    ctx = _make_ctx(str(tmp_path), provider)
    tool = OrchestrationTool.create(ctx)

    result = await tool.execute(goal="实现用户注册功能")

    # Must produce output (not crash)
    assert len(result) > 0, "Expected non-empty result"

    # The outer exception handler message must NOT appear
    assert "编排失败" not in result, (
        "Fallback plan should complete normally without crashing"
    )

    # The fallback plan creates a single "执行任务" task
    assert "编排完成" in result

    # 3 planner attempts (all garbage) + 1 fallback worker = 4 chat calls
    assert provider.call_count >= 4, (
        f"Expected at least 4 chat calls, got {provider.call_count}"
    )
