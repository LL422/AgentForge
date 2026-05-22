# nanobot/orchestration/worker.py
"""Phase 2: Worker Agent execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.runner import AgentRunner, AgentRunResult, AgentRunSpec
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.orchestration.plan import TaskNode
from nanobot.orchestration.roles import WORKER_ROLES


@dataclass
class WorkerResult:
    content: str
    error: str | None = None
    tools_used: list[str] = field(default_factory=list)


def build_worker_prompt(
    task: TaskNode,
    workspace: Path,
    previous_results: dict[str, str] | None = None,
) -> str:
    role_def = WORKER_ROLES[task.role]
    parts: list[str] = [
        role_def["system_prompt"],
        f"## 当前工作区\n{workspace}",
        f"## 你的任务\n{task.description}",
    ]
    if task.dependencies and previous_results:
        context_lines: list[str] = []
        for dep_id in task.dependencies:
            if dep_id in previous_results:
                context_lines.append(
                    f"### 前置任务 {dep_id} 的输出\n{previous_results[dep_id]}"
                )
        if context_lines:
            parts.append("## 前置任务的输出\n" + "\n\n".join(context_lines))
    return "\n\n".join(parts)


async def run_worker(
    runner: AgentRunner,
    task: TaskNode,
    workspace: Path,
    previous_results: dict[str, str],
    tools: ToolRegistry,
    model: str,
    max_iterations: int = 15,
    max_tool_result_chars: int = 80_000,
) -> WorkerResult:
    prompt = build_worker_prompt(task, workspace, previous_results)
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": prompt},
    ]

    async def _do_run() -> AgentRunResult:
        return await runner.run(AgentRunSpec(
            initial_messages=messages,
            tools=tools,
            model=model,
            max_iterations=max_iterations,
            max_tool_result_chars=max_tool_result_chars,
            fail_on_tool_error=True,
        ))

    # First attempt
    result = await _do_run()

    # Retry on empty/short output
    if result.final_content and len(result.final_content.strip()) < 50:
        logger.info(
            "Worker {} output too short ({} chars), retrying",
            task.id, len(result.final_content),
        )
        messages.append({"role": "assistant", "content": result.final_content or ""})
        messages.append({"role": "user", "content": "请给出更详细、完整的回答。"})
        result = await _do_run()

    if result.stop_reason in ("error", "tool_error"):
        error_msg = result.error or "Worker execution failed"
        return WorkerResult(content="", error=error_msg)

    final = result.final_content or ""
    if len(final.strip()) < 50:
        return WorkerResult(content=final, error="Worker output too short")

    return WorkerResult(
        content=final,
        tools_used=list(result.tools_used) if result.tools_used else [],
    )
