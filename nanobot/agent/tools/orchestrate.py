# nanobot/agent/tools/orchestrate.py
"""OrchestrationTool: multi-agent task orchestration.

Discovered automatically by ToolLoader via pkgutil scan of nanobot.agent.tools.
The heavy logic lives in nanobot.orchestration — this file is the Tool wrapper.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.context import ContextAware, RequestContext, ToolContext
from nanobot.agent.tools.file_state import FileStates
from nanobot.agent.tools.loader import ToolLoader
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.runner import AgentRunner
from nanobot.bus.events import OUTBOUND_META_AGENT_UI, OutboundMessage
from nanobot.orchestration.plan import TaskNode, TaskPlan, TaskStatus
from nanobot.orchestration.planner import TaskPlanner
from nanobot.orchestration.worker import run_worker


@tool_parameters({
    "type": "object",
    "properties": {
        "goal": {
            "type": "string",
            "description": "用户的目标描述，如'给这个项目添加用户登录功能'",
        },
        "context_hint": {
            "type": "string",
            "description": "可选的额外约束或关注点，如'重点关注 auth 模块'",
        },
    },
    "required": ["goal"],
})
class OrchestrationTool(Tool):
    """Multi-agent task orchestration tool.

    Three-phase execution:
    1. Plan: LLM decomposes goal into TaskPlan
    2. Execute: Parallel Worker agents execute tasks
    3. Merge: Build a summary from all Worker outputs
    """

    name = "orchestrate"
    description = (
        "将复杂目标拆解为多个子任务，协调多个专业 Agent 并行执行，最后合并结果。"
        "适用于需要多步骤、多角度处理的复杂工程任务，如'给项目添加完整的新功能'。"
    )
    _scopes = {"core"}

    def __init__(self) -> None:
        super().__init__()
        self._provider: Any = None
        self._model: str = ""
        self._workspace: Path | None = None
        self._ctx: ToolContext | None = None
        self._request_ctx: RequestContext | None = None

    def set_context(self, ctx: RequestContext) -> None:
        """Store the per-request origin so events can be routed to the correct WebSocket chat."""
        self._request_ctx = ctx

    async def _emit_event(self, phase: str, data: dict[str, Any] | None = None) -> None:
        """Publish an orchestration progress event to the WebSocket channel via the bus.

        Events are tagged with ``chat_id`` so the frontend can route them to the
        correct chat panel.  The ``_progress`` marker causes the WebSocket channel
        to treat this as a transient breadcrumb rather than a conversation message.
        """
        if self._ctx is None or self._ctx.bus is None:
            return
        if self._request_ctx is None:
            return
        payload: dict[str, Any] = {
            "kind": "orchestration",
            "phase": phase,
        }
        if data is not None:
            payload["data"] = data
        meta: dict[str, Any] = {
            "_progress": True,
            OUTBOUND_META_AGENT_UI: payload,
        }
        await self._ctx.bus.publish_outbound(
            OutboundMessage(
                channel=self._request_ctx.channel,
                chat_id=self._request_ctx.chat_id,
                content="",
                metadata=meta,
            )
        )

    @classmethod
    def create(cls, ctx: ToolContext) -> OrchestrationTool:
        tool = cls()
        tool._ctx = ctx
        if ctx.provider_snapshot_loader:
            try:
                snapshot = ctx.provider_snapshot_loader()
                tool._provider = snapshot.provider
                tool._model = snapshot.model
            except Exception:
                pass
        tool._workspace = Path(ctx.workspace) if ctx.workspace else Path(".")
        return tool

    async def execute(self, **kwargs: Any) -> str:
        goal = kwargs["goal"]
        context_hint = kwargs.get("context_hint")

        if not self._provider:
            return "Error: No LLM provider configured. Please set up a provider first."

        try:
            return await self._execute_internal(goal, context_hint)
        except Exception as e:
            logger.exception("Orchestration failed")
            return f"编排失败: {e}"

    async def _execute_internal(self, goal: str, context_hint: str | None) -> str:
        # Phase 1: Plan
        planner = TaskPlanner(self._provider, self._model)
        plan = await planner.plan(goal, context_hint)
        await self._emit_event("plan_ready", {
            "goal": plan.goal,
            "task_count": len(plan.tasks),
            "tasks": [{"id": t.id, "title": t.title, "role": t.role} for t in plan.tasks],
        })

        # Phase 2: Execute
        previous_results: dict[str, str] = {}
        worker_tool_registry = self._build_worker_tools()
        runner = AgentRunner(self._provider)
        workspace = self._workspace or Path(".")

        while not plan.is_terminal():
            ready = plan.ready_tasks()
            if not ready and plan.has_running():
                await asyncio.sleep(0.5)
                continue
            if not ready:
                break

            async def _run_one(task: TaskNode) -> None:
                task.status = TaskStatus.RUNNING
                await self._emit_event("task_start", {
                    "task_id": task.id,
                    "title": task.title,
                    "role": task.role,
                })
                result = await run_worker(
                    runner=runner,
                    task=task,
                    workspace=workspace,
                    previous_results=previous_results,
                    tools=worker_tool_registry,
                    model=self._model,
                )
                if result.error:
                    # Retry once
                    logger.warning(
                        "Worker {} failed, retrying: {}", task.id, result.error,
                    )
                    result2 = await run_worker(
                        runner=runner,
                        task=task,
                        workspace=workspace,
                        previous_results=previous_results,
                        tools=worker_tool_registry,
                        model=self._model,
                    )
                    if result2.error:
                        task.status = TaskStatus.FAILED
                        task.error = result2.error
                        await self._emit_event("task_failed", {
                            "task_id": task.id,
                            "title": task.title,
                            "error": result2.error,
                        })
                        return
                    result = result2

                task.status = TaskStatus.COMPLETED
                task.result = result.content
                previous_results[task.id] = result.content
                await self._emit_event("task_done", {
                    "task_id": task.id,
                    "title": task.title,
                })

            await asyncio.gather(*[_run_one(t) for t in ready])

        # Phase 3: Merge
        merged = self._merge_results(plan)
        await self._emit_event("complete", {
            "goal": plan.goal,
            "completed": plan.completed_count(),
            "failed": plan.failed_count(),
            "total": len(plan.tasks),
        })
        return merged

    def _merge_results(self, plan: TaskPlan) -> str:
        completed = [t for t in plan.tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in plan.tasks if t.status == TaskStatus.FAILED]

        parts: list[str] = [f"## 编排完成: {plan.goal}\n"]
        parts.append(f"✅ {len(completed)}/{len(plan.tasks)} 任务成功")

        if failed:
            parts.append(f"❌ {len(failed)} 任务失败:")
            for t in failed:
                parts.append(f"- {t.title}: {t.error or '未知错误'}")

        for t in completed:
            parts.append(f"\n### {t.title}\n{t.result or '(无输出)'}")

        return "\n".join(parts)

    def _build_worker_tools(self) -> ToolRegistry:
        """Build a subagent-scoped tool registry for Workers."""
        registry = ToolRegistry()
        if not self._ctx:
            return registry
        cfg = self._ctx.config
        file_state = FileStates()
        worker_ctx = ToolContext(
            config=cfg,
            workspace=str(self._workspace or "."),
            file_state_store=file_state,
        )
        try:
            ToolLoader().load(worker_ctx, registry, scope="subagent")
        except Exception as e:
            logger.warning("Failed to load worker tools: {}", e)
        return registry
