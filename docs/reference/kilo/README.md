# Kilo AI Agent System Documentation

**Last Updated:** 2026-03-23

This directory contains all documentation for the Kilo AI agent system used in Fabrik for code generation and review.

---

## Core Documentation

| Document | Purpose |
|----------|---------|
| **KILO_CLI_REFERENCE.md** | Complete Kilo CLI reference (install, commands, config, permissions) |
| **KILO_MODEL_SELECTION.md** | Real-time model selection guide, Auto Model, and leaderboards |
| **KILO_IMPROVEMENTS_PROPOSAL.md** | Proposed enhancements to agent scripts and code review system |
| **KILO_PLATFORM_FEATURES.md** | Slack integration and App Builder features |
| **KILO_AGENT_NAMING.md** | Tier-based naming convention for agent scripts |
| **KILO_UPDATE_SCHEDULE.md** | Update automation schedule and process |
| **KILO_EXTRACTION_SUMMARY.md** | Extraction summary and statistics |
| **KILO_AGENT_SELECTION_GUIDE.md** | Provider highlights and model selection guide |
| **MANUAL_PRICING_GUIDE.md** | Guide for manually collecting token pricing |

---

## Quick Reference

### Agent Tiers

| Tier | Purpose | Example |
|------|---------|---------|
| **Prime** | Mission-critical, maximum reasoning | `Prime01-opus46-code-max-i500-o2500.sh` |
| **Strong** | Production-grade coding/review | `Strong01-gpt53codex-code-high-i001-o005.sh` |
| **Balanced** | Cost-effective, good performance | `Balanced04-grok41fast-code-high-i020-o050.sh` |
| **Economy** | Budget-friendly, fast iteration | `Economy01-flash3-code-minimal-i000-o001.sh` |

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

### Recent Enhancements (2026-03-23)

| Feature | Location | Description |
|---------|----------|-------------|
| **Escalation Fix** | `kilo_code_review.py` | Fixed `'str' object has no attribute 'get'` crash in `format_gate_results_compact` |
| **DB-Driven Selection** | `scripts/kilo-benchmarks/` | SQLite-based model selection with role assignments |
| **Live Streaming** | `kilo_docs_enforcer.py` | Real-time AI output streaming in verbose mode |
| **Doc Auto-Generation** | `kilo_docs_enforcer.py` | Generates missing docs using Kilo agents |
| **Mypy Recovery** | `final_gate.py` | Auto-clears cache on timeout, retries with --no-incremental |
| **Cost Tracking** | `.droid/kilo_metrics.jsonl` | Per-model/filetype performance metrics |

### Active Agents (~/.traycer/cli-agents/)

40 tier-based agents + `save-plan-md.sh`

---

## See Also

- `/opt/fabrik/INDEX.md` - Master file index
- `/opt/fabrik/CHANGELOG.md` - Change history
- `~/.traycer/cli-agents/` - Active agent scripts
