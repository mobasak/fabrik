# Kilo AI Agent System Documentation

**Last Updated:** 2026-05-20

This directory contains documentation for the Kilo AI agent system used in Fabrik for code generation, review, and automated development workflows.

> **Kilo Code** is built on OpenCode (MIT-licensed). Install via `npm install -g @kilocode/cli`. Available as VS Code extension, JetBrains plugin, and standalone CLI. Access to **500+ models** via Kilo Gateway (403 active in our DB as of May 2026) with pay-as-you-go pricing (zero markup) or BYOK (Bring Your Own Key).

---

## Core Documentation

| Document | Purpose | Status |
|----------|---------|--------|
| **KILO_CLI_REFERENCE.md** | CLI reference manual — every command, flag, config option, endpoint, programmatic patterns | Active (updated May 2026, includes April changes) |
| **KILO_USAGE_GUIDE.md** | CLI how-to guide — skills, MCP, workflows, autonomous mode, serve mode, sessions, fabrik patterns | Active |
| **KILO_REVIEW_GUIDE.md** | Complete code review guide — pipeline architecture, daily workflow, micro-spec format, semantic batching, issue tracking, token-lean defaults, escalation. References `scripts/kilo_code_review.py`. | Active |
| **KILO_USE_CASES.md** | Kilo as AI infrastructure — 11 non-coding domains (content, translation, ETL, research, vision, audio, legal, marketing, automation) with economics and ROI rankings | Active |
| **KILO_MODEL_SELECTION.md** | Model selection guide, Auto Model, leaderboard integration | Active |
| ~~KILO_PLATFORM_FEATURES.md~~ | Slack + App Builder (web GUI only, not CLI) | Archived (2026-04-14) |
| **KILO_AGENT_NAMING.md** | Role-based naming convention for agent scripts | Active |
| **KILO_AGENT_SELECTION_GUIDE.md** | Provider highlights and model selection | Active |
| **KILO_MODEL_CAPABILITIES.md** | Detailed model capability matrix (context, vision, tools, reasoning) | Auto-generated from DB |
| **KILO_UPDATE_SCHEDULE.md** | Update automation schedule | Active |
| **KILO_USAGE_GUIDE.md** | Usage patterns and workflows | Active |
| **KILO_PERFORMANCE_TUNING.md** | Token optimization, context management | Active |
| **KILO_TROUBLESHOOTING.md** | Common issues and fixes | Active |

---

## Key Capabilities (May 2026)

| Capability | Description |
|------------|-------------|
| **500+ Models** | Access via Kilo Gateway — Claude, GPT-5, Gemini, Llama, Qwen, open-source. BYOK supported. |
| **Subagents** | Agents delegate to subagents automatically. Replaces deprecated Orchestrator mode. |
| **Snapshots** | Git-based working directory snapshots before/after agent edits. Revert any change. |
| **Granular Permissions** | Per-tool Allow/Ask/Deny for bash, read, edit, glob, grep. Pattern-based rules. |
| **Agent Manager** | Run multiple agents simultaneously (VS Code / Cloud). |
| **HTTP Server API** | `kilo serve` exposes OpenAPI 3.1 REST API. Attach via `kilo attach <url>`. |
| **Local Code Review** | `/local-review` and `/local-review-uncommitted` for AI-powered branch analysis. |
| **Autonomous Mode** | `--auto` flag for CI/CD. Exit codes: 0 success, 124 timeout, 1 error. |
| **Session Management** | `--continue` resumes last session. `/fork` branches a conversation. |
| **MCP Servers** | Model Context Protocol integration for extended tool access. |
| **JSON Output** | `--format json` for machine-parseable event streams with cost/token breakdown. |
| **SSE Streaming** | Real-time events via Server-Sent Events for session monitoring. |
| **DB-Driven Selection** | SQLite-based model selection with role assignments (fabrik-specific). |
| **Cost Tracking** | Per-model/filetype metrics in `.droid/kilo_metrics.jsonl`. |

### Deprecated (April 2026)

- **Orchestrator Mode** — replaced by automatic subagent delegation
- **Profiles** — replaced by model favoriting (starring)
- **Code Indexing** — temporarily unavailable, under active development
- **Old checkpoint system** — replaced by Snapshots

---

## Active Agents (`~/.traycer/cli-agents/`)

Role-based agents + `coding-auto.sh` (auto-routing). The live roster (roles, counts, and per-role models) is **auto-generated daily** and changes as the model leaderboard updates — see **[KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md)** for the current assignments rather than relying on a static table here.

**Naming convention:** `{role}-{priority}-{model}-{tier}-o{output_cost}-ppd{price_per_day}.sh`

---

## Scripts

### Active (`scripts/`)

| Script | Purpose |
|--------|---------|
| `kilo_code_review.py` | Code review (Step 4 in Traycer workflow) |
| `kilo_cost_report.py` | Usage analysis, cost summaries by model/filetype |
| `kilo_cost_tracker.py` | Real-time cost tracking |
| `kilo_auto_route.py` | Automatic model routing by task type |
| `kilo_dispatch.py` | Dispatch tasks to appropriate agents |
| `kilo_consult.py` | Consult mode for targeted questions |
| `kilo_model_sync.py` | Sync model catalog from Kilo Gateway |
| `kilo_model_sync_startup.sh` | Startup sync trigger |
| `kilo_docs_enforcer.py` | Documentation standards enforcement |
| `kilo_terminal_runner.py` | Terminal-based agent runner |
| `kilo_agent_health.sh` | Agent integrity check (executable, shebang, syntax) |
| `generate_kilo_agents.py` | Generate role-based agent scripts from DB |

### Benchmark System (`scripts/kilo-benchmarks/`)

| File | Purpose |
|------|---------|
| `kilo_agents.db` | **Authoritative** SQLite database — all models, pricing, benchmarks |
| `kilo_all_agents.json` | Complete catalog (JSON export) |
| `kilo_selected_agents.json` | Filtered selection for active use |
| `assignments.json` | Current role-to-model assignments |
| `shortlists.json` | Provider shortlists |
| `role_configs.yaml` | Role definitions and constraints |
| `update_kilo_benchmarks.py` | Scrape and update benchmark data |
| `scrape_artificial_analysis.py` | Artificial Analysis leaderboard scraper |
| `scrape_benchlm.py` | BenchLM scraper |
| `compute_assignments.py` | Compute optimal role assignments from benchmarks |
| `agent_selector.py` | Model selection logic |
| `classify_ticket.py` | Classify tickets by complexity for agent routing |

---

## See Also

- `docs/traycer/kilo_selected_agents.md` — Current selected agents documentation
- `scripts/kilo-benchmarks/kilo_agents.sql` — Database schema
- `.windsurf/rules/core/50-code-review.md` — Code review rules (references Kilo workflow)
- `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` — Local Ollama setup for the 4 local agents
