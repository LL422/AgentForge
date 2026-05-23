# AgentForge

<div align="center">

**Multi-Agent Task Orchestration Framework — built on [nanobot](https://github.com/HKUDS/nanobot)**

<img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
<img src="https://img.shields.io/badge/license-MIT-green" alt="License">
<img src="https://img.shields.io/badge/React-18-blue" alt="React">
<img src="https://img.shields.io/badge/TypeScript-5.7-blue" alt="TypeScript">

</div>

AgentForge extends the nanobot AI agent framework with a **multi-agent task orchestration system**. Describe a complex goal — the Orchestrator agent decomposes it into a structured task plan, dispatches specialized Worker agents to execute tasks in parallel, and merges the results. The entire process is visualized in real-time through an interactive WebUI.

## Why AgentForge

Single-agent AI assistants hit a wall with complex, multi-step engineering tasks. They lose context, skip steps, or produce shallow results. AgentForge solves this by breaking work into focused sub-tasks handled by role-specialized agents:

- **Analyst** reads and understands the problem
- **Developer** writes the implementation
- **Tester** creates test cases
- **Reviewer** audits quality and security

Each agent has a role-specific toolset and system prompt. They run in parallel where possible, pass context through dependencies, and the Orchestrator synthesizes their outputs into a coherent result.

## Architecture

```
┌─────────────────────────────────────────┐
│               WebUI (React)              │
│   TaskDAGView · AgentTimeline · Result   │
└──────────────────┬──────────────────────┘
                   │ WebSocket
┌──────────────────▼──────────────────────┐
│         nanobot AgentLoop (unchanged)    │
│                                         │
│   在 RUN 阶段调用 OrchestrationTool       │
│   ┌───────────────────────────────────┐ │
│   │  Phase 1: TaskPlanner (LLM 拆解)   │ │
│   │  Phase 2: Worker 并行调度          │ │
│   │  Phase 3: 结果合并                 │ │
│   └───────────────────────────────────┘ │
│                                         │
│   复用: SubagentManager · Tool · Session │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│         nanobot 基础设施                 │
│  45+ LLM Providers · 16 Chat Channels   │
│  Memory System · MCP · Cron · Sandbox   │
└─────────────────────────────────────────┘
```

**Key design decisions:**
- **Tool-based integration** — OrchestrationTool extends nanobot's `Tool` ABC; auto-discovered and invoked by the existing AgentLoop without modifying core code
- **Orchestrator-Worker pattern** — one Orchestrator decomposes goals, specialized Workers execute in parallel
- **DAG-based task planning** — tasks form a directed acyclic graph with dependency-driven parallel execution
- **Crash resilience** — checkpoint-based recovery; failed Workers don't block independent tasks

## Features

### Core (from nanobot)
- **Ultra-lightweight agent loop** — small, readable core with a clean state machine
- **45+ LLM providers** — Anthropic, OpenAI, DeepSeek, Ollama, vLLM, and more
- **16 chat channels** — Telegram, Discord, Slack, WeChat, Feishu, WhatsApp, WebSocket, and more
- **Memory system** — two-phase Dream consolidation with persistent MEMORY.md
- **Tool ecosystem** — file I/O, shell execution, web search, MCP servers, cron, image generation
- **OpenAI-compatible API** — `/v1/chat/completions` endpoint for programmatic access
- **Session management** — per-user conversation isolation with automatic context compaction

### Orchestration (AgentForge extension)
- **Multi-agent task decomposition** — LLM-powered goal-to-task breakdown
- **4 specialized Worker roles** — Analyst, Developer, Tester, Reviewer with scoped toolkits
- **DAG-based scheduling** — dependency-aware parallel execution with cycle detection
- **Real-time DAG visualization** — SVG-based task graph with live status updates
- **Automatic retry & fallback** — failed Workers retry once; failed planning falls back to single-agent mode
- **Collapsible result panel** — per-task status with error details and file change summaries

## Quick Start

### 1. Installation

```bash
git clone https://github.com/LL422/AgentForge.git
cd AgentForge
pip install -e .
```

### 2. Configure

```bash
nanobot onboard
```

Edit `~/.nanobot/config.json` with your LLM provider:

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  },
  "agents": {
    "defaults": {
      "provider": "openrouter",
      "model": "anthropic/claude-opus-4-6"
    }
  }
}
```

### 3. Start the Gateway

```bash
nanobot gateway
```

Visit `http://127.0.0.1:8765` to open the WebUI.

### 4. Use Orchestration

In the WebUI chat, describe a complex goal and the agent will automatically invoke the orchestration tool:

> "给这个项目添加一个完整的用户认证系统，包括注册、登录、JWT token 管理，以及对应的单元测试"

The Orchestrator will:
1. Decompose the goal into a structured task plan
2. Display the DAG visualization in real-time
3. Run Analyst → Developer + Tester → Reviewer in dependency order
4. Merge all outputs into a comprehensive result

You can also use `/orchestrate` command to explicitly trigger orchestration mode.

## Multi-Agent Orchestration Guide

### How It Works

The `orchestrate` tool follows a three-phase execution:

| Phase | Description | Duration |
|-------|-------------|----------|
| **Plan** | LLM analyzes the goal and produces a structured TaskPlan with 2-6 sub-tasks | 3-5s |
| **Execute** | Ready tasks (all dependencies met) run in parallel via specialized Workers | 20-120s |
| **Merge** | All Worker outputs are aggregated into a final summary | instant |

### Worker Roles

| Role | Capabilities | Write Access |
|------|-------------|-------------|
| `analyst` | read_file, grep, find_files, web_search | No |
| `developer` | read_file, write_file, edit_file, exec, grep, find_files | Yes |
| `tester` | read_file, write_file, edit_file, exec, grep | Yes |
| `reviewer` | read_file, grep, find_files, exec | No |

### Task Plan Rules

- First task is always `analyst` (understand before acting)
- Last task is always `reviewer` (final quality gate)
- Maximum 6 tasks per plan
- Independent tasks run in parallel automatically
- Each Worker receives context from its completed dependencies

### Error Handling

- **Worker failure**: automatic retry (1x), then marked FAILED — independent tasks continue
- **Plan failure**: automatic retry (2x), then falls back to single-agent direct execution
- **Cancellation**: `/stop` preserves completed task results
- **Crash recovery**: checkpoint-based — restart continues from last completed task

### Configuration

Optional orchestration-specific settings in `~/.nanobot/config.json`:

```json
{
  "tools": {
    "orchestration": {
      "orchestrator_model": null,
      "worker_model": null,
      "worker_provider": null
    }
  }
}
```

- `orchestrator_model` — model for planning and merging (default: follows main agent model)
- `worker_model` — model for Worker agents (default: follows main agent model)
- `worker_provider` — provider for Workers (default: follows main provider)

## Development

```bash
# Python: run orchestration tests
pytest tests/orchestration/ -v

# WebUI: dev server
cd webui && bun run dev

# WebUI: run tests
cd webui && bun run test
```

## Project Structure (Orchestration Extension)

```
nanobot/orchestration/       # Backend — orchestration engine
├── plan.py                  # TaskPlan, TaskNode, TaskStatus, validation
├── roles.py                 # WORKER_ROLES (analyst/developer/tester/reviewer)
├── planner.py               # TaskPlanner — LLM-based goal decomposition
├── worker.py                # Worker executor — AgentRunner integration
└── templates/orchestration/
    └── plan.md              # Planning prompt template

webui/src/
├── components/orchestration/  # Frontend — orchestration UI
│   ├── TaskDAGView.tsx        # SVG DAG visualization
│   ├── OrchestrationResult.tsx # Per-task result panel
│   └── OrchestrationCard.tsx  # Collapsible container
├── hooks/useNanobotStream.ts  # Real-time event handling
└── lib/types.ts              # TypeScript event types
```

## Based on nanobot

AgentForge is built on top of [nanobot](https://github.com/HKUDS/nanobot), an open-source AI agent framework by [Xubin Ren](https://github.com/re-bin). The orchestration system is implemented as an extension module — it does not modify nanobot core code, making it compatible with future upstream updates.

## License

MIT — see [LICENSE](./LICENSE) for details.
