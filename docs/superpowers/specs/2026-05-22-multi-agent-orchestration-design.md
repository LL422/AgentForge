# 多 Agent 协作任务编排系统 — 设计文档

**日期**: 2026-05-22
**目标**: 在 nanobot 基础上实现多 Agent 协作任务编排，用于求职展示
**模式**: 编排者-工作者 (Orchestrator-Worker)

---

## 一、总体架构

### 原则

不做 fork，不改 nanobot 核心代码。通过 Tool 扩展点自然融入现有 AgentLoop，新增代码集中在 `nanobot/orchestration/` 和 `webui/src/components/orchestration/`。

### 分层

```
前端 (WebUI) ──WebSocket──→ nanobot AgentLoop (不改动)
                                │
                          RUN 阶段调用:
                          ┌──────────────────────┐
                          │  OrchestrationTool    │
                          │  ├── TaskPlanner (LLM) │
                          │  ├── Worker 调度       │
                          │  └── 结果合并 (LLM)    │
                          └──────────────────────┘
                                │
                    复用: SubagentManager · Tool系统 · Session · MessageBus
```

### 为什么是 Tool 而非独立 AgentLoop

- 两种形态冲突时产生消息分发、会话割裂、状态同步问题
- Tool 是 nanobot 最稳定的扩展点（`execute(**kwargs)` → 返回字符串）
- Tool 自动被 `ToolLoader` 发现和 `ToolRegistry` 注册，LLM 自动可调用
- 流式输出通过现有 WebSocket 通道推送，无需新建通信通道
- 测试只需 `tool.execute(kwargs)`，不需要启动完整 AgentLoop

---

## 二、OrchestrationTool 核心设计

### 工具参数

```json
{
  "goal": "给这个项目添加用户登录功能",
  "context_hint": "重点关注 auth 模块"
}
```

### execute() 三阶段流程

```
用户目标 → Phase 1 (拆解, 3-5s) → Phase 2 (执行, 20-120s) → Phase 3 (合并, 3-5s) → 返回结果
```

**Phase 1 — 任务拆解**: 调用 LLM 将目标拆解为 2-6 个子任务，输出结构化 TaskPlan。流式推送 `plan_ready` 事件给前端。

**Phase 2 — 调度执行**: 找出依赖已满足的任务，并行创建 Worker 执行。每个 Worker 完成/失败时推送事件。循环直到所有任务到达终态。

**Phase 3 — 结果合并**: 汇总所有 Worker 输出，调用 LLM 生成最终摘要。推送 `complete` 事件。LLM 合并失败时跳过该步骤，直接拼接原始输出。

### TaskPlan 数据模型

```python
class TaskStatus(enum.Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskNode(pydantic.BaseModel):
    id: str                    # "task-0"
    title: str                 # "分析现有认证逻辑"
    description: str           # Worker 详细任务描述
    role: str                  # analyst | developer | reviewer | tester
    status: TaskStatus
    dependencies: list[str]    # 依赖的 task id 列表
    result: str | None
    error: str | None
```

---

## 三、Worker 角色定义

```python
WORKER_ROLES = {
    "analyst": {
        "display_name": "需求分析",
        "tools": ["read_file", "grep", "find_files", "web_search"],
        "system_prompt": "你是需求分析师。阅读代码、理解架构、输出分析报告。不要修改任何文件。"
    },
    "developer": {
        "display_name": "代码实现",
        "tools": ["read_file", "write_file", "edit_file", "exec", "grep", "find_files"],
        "system_prompt": "你是开发者。根据分析报告编写代码实现需求。"
    },
    "reviewer": {
        "display_name": "代码审查",
        "tools": ["read_file", "grep", "find_files", "exec"],
        "system_prompt": "你是代码审查者。只审查代码质量、安全性和风格，不要修改代码。"
    },
    "tester": {
        "display_name": "测试编写",
        "tools": ["read_file", "write_file", "edit_file", "exec", "grep"],
        "system_prompt": "你是测试工程师。根据需求和实现编写测试用例。"
    }
}
```

### Plan 拆解规则

- 第一个任务默认 analyst 角色（先分析再动手）
- 最后一个任务默认 reviewer 角色（最终审查）
- 最多 6 个任务
- 可并行的任务不设置不必要依赖
- dependencies 中的 ID 必须在前面的任务中已定义

---

## 四、Plan 确认与执行流程

### 默认策略：自动执行，用户可干预

```
用户发送目标 → Phase 1 拆解 → 前端展示 DAG → 自动开始 Phase 2
                                            ↘ 用户可选"暂停"修改 Plan
```

不设"确认 Plan 后执行"的阻塞步骤。用户走神时任务不会卡住。

### 用户可做的 Plan 修改

- 修改单个任务的 title/description/role
- 删除任务（自动调整后代依赖）
- 添加新任务
- 修改后点"确认修改"，后端重新 validate → 继续执行

### 执行算法

```python
async def _execute_plan(plan):
    while not plan.is_terminal():
        ready = plan.ready_tasks()  # dependencies all COMPLETED
        if not ready and plan.has_running():
            await self._wait_next_completion()
            continue
        if not ready and not plan.has_running():
            break  # 死锁：FAILED 任务阻塞了后续
        # 并行启动所有 ready 任务
        await asyncio.gather(*[self._run_worker(t) for t in ready])
```

### Worker 执行

通过 `SubagentManager.spawn()` 创建子 Agent：

- 传入角色 system_prompt + 任务描述 + 前置任务输出
- 角色限定的工具集（analyst/reviewer 没有 write_file 权限）
- 最大迭代 15 轮
- 超时 2 分钟（复用 `NANOBOT_LLM_TIMEOUT_S`）

---

## 五、LLM 模型配置

```json
{
  "orchestration": {
    "orchestrator_model": null,     // null = 跟随主 Agent 模型 (Phase 1 + 3)
    "worker_model": null,           // null = 跟随主 Agent (Phase 2)
    "worker_provider": null         // null = 跟随主 Provider
  }
}
```

- Phase 1（拆解）和 Phase 3（合并）需要强推理 → 用 orchestrator_model
- Phase 2（Worker 执行）是窄任务 → 可配更便宜的 worker_model 降本
- 所有选项默认 null，不做额外配置要求

---

## 六、前端设计

### 新增组件 (3 个)

**OrchestrationCard** — 编排消息卡片容器

- 执行中展开：显示 DAG 图 + Worker 进度
- 完成后折叠为一行摘要："✅ 编排完成 · 添加登录功能 · 4/4 任务成功"
- 点击展开查看详情

**TaskDAGView** — 只读 DAG 图 + 点击节点编辑

- 纯 SVG 渲染节点和依赖箭头
- 节点颜色表示状态（灰=等待, 绿=运行中, 蓝=完成, 红=失败）
- 点击节点 → 弹出编辑框（修改 title/description/role）
- 不需要拖拽边功能

**OrchestrationResult** — 结果汇总

- 折叠态：一行文本摘要（成功数、生成文件数）
- 展开态：完整摘要 + 文件变更列表 + 失败任务信息 + 重试按钮

### 复用现有组件

- Worker 工具调用 → 复用 `AgentActivityCluster`，按 `task_id` 分组
- 不对现有 AgentActivityCluster 做破坏性修改

### 新增 WebSocket 事件

| 事件 | 时机 |
|------|------|
| `orchestration.plan_ready` | Phase 1 完成，携带 TaskPlan |
| `orchestration.plan_confirmed` | 用户确认/修改 Plan |
| `orchestration.task_start` | Worker 开始执行 |
| `orchestration.task_progress` | Worker 流式输出 |
| `orchestration.task_done` | Worker 完成 |
| `orchestration.task_failed` | Worker 失败 |
| `orchestration.complete` | Phase 3 完成 |

---

## 七、错误处理

### Worker 失败

```
失败 → 自动重试 1 次 → 仍失败标记 FAILED
  ├── 不影响其他独立 Worker 继续执行
  ├── 依赖该 Worker 的任务永久 PENDING（不执行）
  └── Phase 3 明确告知用户哪些失败
```

### Plan 验证

5 层校验：循环依赖检测 → 引用完整性 → 任务数量上限(6) → 角色合法性 → 至少一个入口任务。校验失败 → 重新请求 LLM 生成(最多 2 次) → 仍失败则告知用户。

### 超时与取消

- 整体编排超时：5 分钟，返回部分结果
- 单 Worker 超时：2 分钟，标记 FAILED
- 用户取消：复用 `/stop` 机制，已完成的结果保留，返回"已取消，完成 2/4 个任务"

### 崩溃恢复

复用 nanobot checkpoint 机制：

- 每次 Worker 完成后写入 session metadata
- 重启后检测未完成编排，还原 TaskPlan，继续执行
- 前端重连后收到 plan_ready 事件（含已完成任务进度）

### LLM 调用降级

- Phase 1 重试 1 次 → 仍失败告知用户
- Phase 3 重试 1 次 → 仍失败跳过 LLM 合并，直接拼接原始输出

### Worker 空输出

输出少于 50 字符 → 自动补 1 次（追加"请给出详细回答"）→ 仍为空则标记 FAILED

---

## 八、文件结构

```
nanobot/
├── orchestration/              # 新增
│   ├── __init__.py
│   ├── tool.py                 # OrchestrationTool
│   ├── plan.py                 # TaskPlan, TaskNode, TaskStatus
│   ├── planner.py              # TaskPlanner (Phase 1 LLM 拆解)
│   ├── worker.py               # Worker 创建与执行
│   └── roles.py                # WORKER_ROLES 定义
└── templates/orchestration/    # 新增
    └── plan.md                 # Phase 1 prompt 模板

webui/src/
├── components/
│   └── orchestration/          # 新增
│       ├── OrchestrationCard.tsx
│       ├── TaskDAGView.tsx
│       └── OrchestrationResult.tsx
└── lib/
    └── types.ts                # 扩展: 新增编排事件类型
```

---

## 九、待定项

以下内容实施阶段再细化：

- Phase 1 prompt 模板的精确措辞
- TaskDAGView 的 SVG 节点坐标布局算法（层次布局 vs 力导向）
- Worker 结果传给后续 Worker 的上下文构建策略（完整传递 vs 摘要传递）
- 是否需要 Worker 间的对比/辩论模式（如 reviewer 和 developer 同时审查互相校验）
