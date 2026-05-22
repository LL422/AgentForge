# tests/orchestration/test_planner.py
import json

import pytest

from nanobot.orchestration.planner import TaskPlanner
from nanobot.orchestration.plan import TaskPlan
from nanobot.providers.base import LLMResponse


class FakeProvider:
    """Mock LLM provider that returns a canned JSON response."""

    def __init__(self, response_text: str):
        self._response_text = response_text

    async def chat(self, messages, tools=None, model=None, max_tokens=4096,
                   temperature=0.7, reasoning_effort=None, tool_choice=None, **kwargs):
        return LLMResponse(
            content=self._response_text,
            finish_reason="stop",
            usage={"total_tokens": 100},
        )

    def get_default_model(self):
        return "test-model"


VALID_PLAN_JSON = json.dumps({
    "tasks": [
        {"id": "task-0", "title": "分析代码", "description": "分析现有结构",
         "role": "analyst", "dependencies": []},
        {"id": "task-1", "title": "实现登录", "description": "写登录端点",
         "role": "developer", "dependencies": ["task-0"]},
        {"id": "task-2", "title": "写测试", "description": "编写测试",
         "role": "tester", "dependencies": ["task-1"]},
        {"id": "task-3", "title": "代码审查", "description": "审查改动",
         "role": "reviewer", "dependencies": ["task-1"]},
    ]
})


@pytest.mark.asyncio
async def test_plan_success():
    """Happy path: valid JSON returns a properly structured TaskPlan."""
    provider = FakeProvider(VALID_PLAN_JSON)
    planner = TaskPlanner(provider, model="test-model")
    plan = await planner.plan("添加用户登录")
    assert isinstance(plan, TaskPlan)
    assert plan.goal == "添加用户登录"
    assert len(plan.tasks) == 4
    assert plan.tasks[0].role == "analyst"
    assert plan.tasks[-1].role == "reviewer"


@pytest.mark.asyncio
async def test_plan_retry_on_invalid_json():
    """Garbage LLM output triggers fallback after retries are exhausted."""
    provider = FakeProvider("not json at all")
    planner = TaskPlanner(provider, model="test-model", max_retries=1)
    plan = await planner.plan("test goal")
    assert isinstance(plan, TaskPlan)
    assert len(plan.tasks) == 1


@pytest.mark.asyncio
async def test_fallback_plan():
    """Direct fallback call yields a single developer task."""
    planner = TaskPlanner(None, model="test-model")
    plan = planner._fallback_plan("添加登录")
    assert isinstance(plan, TaskPlan)
    assert len(plan.tasks) >= 1
    assert plan.tasks[0].role == "developer"
