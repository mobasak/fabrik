# Kilo AI Agent System Documentation

**Last Updated:** 2026-04-14

This directory contains all documentation for the Kilo AI agent system used in Fabrik for code generation and review.

> **Kilo CLI version:** 7.0.33+ (fork of OpenCode). Kilo is both a coding agent CLI and a **full LLM gateway** with an HTTP Server API, custom agents, plugins, and access to hundreds of models via Kilo Gateway.

---

## Core Documentation

| Document | Purpose |
|----------|---------|
| **KILO_CLI_REFERENCE.md** | Complete Kilo CLI reference (install, commands, config, HTTP Server API, custom agents, plugins, permissions) |
| **KILO_MODEL_SELECTION.md** | Real-time model selection guide, Auto Model, and leaderboards |
| **KILO_PLATFORM_FEATURES.md** | Slack integration and App Builder features |
| **KILO_AGENT_NAMING.md** | Tier-based naming convention for agent scripts |
| **KILO_UPDATE_SCHEDULE.md** | Update automation schedule and process |
| **KILO_AGENT_SELECTION_GUIDE.md** | Provider highlights and model selection guide |

---

## Quick Reference

### Agent Tiers

| Tier | Purpose | Example |
|------|---------|---------|
| **Prime** | Mission-critical, maximum reasoning | `Prime01-opus46-code-max-i500-o2500.sh` |
| **Strong** | Production-grade coding/review | `Strong01-gpt53codex-code-high-i001-o005.sh` |
| **Balanced** | Cost-effective, good performance | `Balanced04-grok41fast-code-high-i020-o050.sh` |
| **Economy** | Budget-friendly, fast iteration | `Economy01-flash3-code-minimal-i000-o001.sh` |
| **Free** | Zero-cost models via Kilo Gateway | `Free01-minimax21-code-medium-i000-o000.sh` |

### Data Files

| File | Purpose | Status |
|------|---------|--------|
| `scripts/kilo-benchmarks/kilo_agents.db` | **AUTHORITATIVE** SQLite database | Active |
| `scripts/kilo-benchmarks/kilo_all_agents.json` | Complete catalog (319+ models) | Active |
| `scripts/kilo-benchmarks/assignments.json` | Current role assignments | Active |
| `scripts/kilo-benchmarks/README.md` | Database documentation | Active |

### Scripts (scripts/)

| Script | Purpose |
|--------|---------|
| `generate_kilo_agents.py` | Generates tier-based agent scripts |
| `kilo_agent_updater.py` | Updates catalog and pricing |
| `kilo_code_review.py` | Code review (Step 4 in 9-step workflow) |
| `kilo_cost_report.py` | Analyze usage logs, cost summaries by model/filetype |
| `kilo_agent_health.sh` | Verify agent integrity (executable, shebang, syntax) |
| `extract_pricing.py` | Extract input/output pricing |

### Key Capabilities

| Capability | Description |
|------------|-------------|
| **LLM Gateway** | Access 400+ models via Kilo Gateway with unified billing |
| **HTTP Server API** | `kilo serve` exposes full OpenAPI 3.1 REST API for programmatic access |
| **Custom Agents** | Define agents with specific models, system prompts, and tool restrictions |
| **Custom Commands** | Reusable prompt templates for repetitive tasks |
| **Plugins** | Extend with custom tools, hooks, and npm integrations |
| **JSON Output** | `--format json` for machine-parseable event streams with cost/token breakdown |
| **SSE Streaming** | Real-time events via Server-Sent Events for session monitoring |
| **DB-Driven Selection** | SQLite-based model selection with role assignments |
| **Cost Tracking** | Per-model/filetype performance metrics in `.droid/kilo_metrics.jsonl` |

### Active Agents (~/.traycer/cli-agents/)

40 tier-based agents + `save-plan-md.sh`

---

## See Also

- `/opt/fabrik/INDEX.md` - Master file index
- `/opt/fabrik/CHANGELOG.md` - Change history
- `~/.traycer/cli-agents/` - Active agent scripts
