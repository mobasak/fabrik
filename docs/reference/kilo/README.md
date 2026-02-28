# Kilo AI Agent System Documentation

**Last Updated:** 2026-02-28

This directory contains all documentation for the Kilo AI agent system used in Fabrik for code generation and review.

---

## Core Documentation

| Document | Purpose |
|----------|---------|
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
| **P** (Prime) | Mission-critical, maximum reasoning | `P01-opus46-code-max-i500-o2500.sh` |
| **S** (Strong) | Production-grade coding/review | `S01-gpt53codex-code-high-i001-o005.sh` |
| **B** (Balanced) | Cost-effective, good performance | `B04-grok41fast-code-high-i020-o050.sh` |
| **E** (Economy) | Budget-friendly, fast iteration | `E01-flash3-code-minimal-i000-o001.sh` |

### Data Files (scripts/)

| File | Purpose | Status |
|------|---------|--------|
| `kilo_18_agents_complete.json` | **AUTHORITATIVE** pricing manifest | Active |
| `kilo_all_models.json` | Complete catalog (319 models) | Active |
| `kilo_comprehensive_db.json` | Model database with capabilities | Active |
| `manual_pricing_data.json` | Manual pricing for 12 models | Active |

### Scripts (scripts/)

| Script | Purpose |
|--------|---------|
| `generate_kilo_agents.py` | Generates tier-based agent scripts |
| `kilo_agent_updater.py` | Updates catalog and pricing |
| `kilo_code_review.py` | Code review (Step 4 in 9-step workflow) |
| `extract_pricing.py` | Extract input/output pricing |

### Active Agents (~/.traycer/cli-agents/)

18 tier-based agents + `save-plan-md.sh`

---

## See Also

- `/opt/fabrik/INDEX.md` - Master file index
- `/opt/fabrik/CHANGELOG.md` - Change history
- `~/.traycer/cli-agents/` - Active agent scripts
