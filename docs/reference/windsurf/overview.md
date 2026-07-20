# Windsurf Reference

**Last Updated:** 2026-05-21

Documentation for Windsurf IDE + Cascade AI as used in the Fabrik workflow.

---

## Contents

| Document | Description | Auto-updated? |
|---|---|---|
| [cascade-guide.md](../../archive/cascade-guide.md) | Cascade features (ARCHIVED — Cascade LLM route retired 2026-07-19) | Archived |
| [cascade-models.md](../../archive/cascade-models.md) | Model tiers (ARCHIVED — daily scrape pipeline dismantled 2026-07-20) | Archived |
| [windsurf_features.md](windsurf_features.md) | All Windsurf IDE features — Tab, Command, Devin, Previews, deploys, etc. | Manual |
| [actively-used-windsurf-extensions.md](actively-used-windsurf-extensions.md) | Currently installed extensions (11) | Yes (daily WSL hook) |

---

## How Fabrik Uses Windsurf

Windsurf is the primary IDE. Three executors read different instruction files:

| Executor | Reads | Instruction file |
|---|---|---|
| **Cascade** (Windsurf AI) | `.windsurfrules` + `.windsurf/rules/**/*.md` + `AGENTS.md` | Glob-triggered rule packs |
| **Kilo CLI** (terminal agent) | `AGENTS-compact.md` via `opencode.json` | Compact instructions |
| **Claude Code** (this tool) | `CLAUDE.md` | Full dev contract |

All three get the same spec contract awareness rules (inline in their respective files).

---

## Configuration

| What | Where |
|---|---|
| Rule packs | `.windsurf/rules/` (35 rule packs across 4 subdirectories (core/, saas/, mobile-app/, chrome-ext/)) |
| Workflows | `.windsurf/workflows/` (11 workflows) |
| MCP servers | `~/.codeium/windsurf/mcp_config.json` |
| Memories | `~/.codeium/windsurf/memories/` (auto-generated, local) |
| Global rules | `~/.codeium/windsurf/memories/global_rules.md` |
| Turbo mode | Enabled — commands auto-execute without prompts |

---

## See Also

- `.windsurf/rules/` — the actual rule packs loaded by Cascade
- `.windsurf/workflows/` — reusable workflow recipes
- `AGENTS.md` — always-on instructions for all executors
