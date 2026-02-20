# Custom Droids Reference

**Last Updated:** 2026-02-20

Reference documentation for all custom droid definitions available in Factory CLI.

## Overview

Droids are specialized AI agents with predefined roles, capabilities, and constraints. They are invoked via:

```bash
droid exec --droid <name> "prompt"
```

Droid definitions are stored in `~/.factory/droids/` as markdown files with YAML frontmatter.

## Autonomy Levels

| Level | Allowed Actions |
|-------|-----------------|
| **low** | Read-only analysis, reporting, planning — no file modifications |
| **medium** | File creation/modification within scope, test execution |
| **high** | Full autonomy including installs, commits, external requests |

---

## Existing Droids

## Code Reviewer

| Property | Value |
|----------|-------|
| **File** | `~/.factory/droids/code-reviewer.md` |
| **Model** | (inherited) |
| **Autonomy** | low |
| **Description** | Reviews code for quality, security, and maintainability |

**Use Case:** Run security audits, detect secrets, identify injection flaws, ensure production standards.

**Output Format:** Code review comments with severity levels and recommendations.

---

## Service Migrator

| Property | Value |
|----------|-------|
| **File** | `~/.factory/droids/service-migrator.md` |
| **Model** | (inherited) |
| **Autonomy** | medium |
| **Description** | Expert in legacy modernization, refactoring, and architectural migration |

**Use Case:** Upgrade dependencies (e.g., Pydantic v1 → v2), migrate code from State A to State B safely.

**Output Format:** Migration plan with step-by-step changes and rollback instructions.

---

## Worker

| Property | Value |
|----------|-------|
| **File** | `~/.factory/droids/worker.md` |
| **Model** | inherit |
| **Autonomy** | medium |
| **Description** | General-purpose worker for delegating non-trivial tasks |

**Use Case:** Code exploration, Q&A, research, analysis — tasks benefiting from parallel execution.

**Output Format:** Task-dependent; follows prompt instructions.

---

## New Droids (GAP-06)

## Planner

| Property | Value |
|----------|-------|
| **File** | `~/.factory/droids/planner.md` |
| **Model** | claude-sonnet-4-5-20250929 |
| **Autonomy** | low |
| **Description** | Creates detailed execution plans from requirements |

**Use Case:** Transform specs into actionable plans with steps, gates, and verification criteria.

**Output Format:** Execution plan following `templates/docs/EXECUTION_PLAN_TEMPLATE.md`:
- Goal, DONE WHEN criteria, Out of Scope
- Sequential steps with DO/GATE/EVIDENCE

**Constraints:** Does NOT implement code or modify files.

---

## Security Auditor

| Property | Value |
|----------|-------|
| **File** | `~/.factory/droids/security-auditor.md` |
| **Model** | gpt-5.3-codex |
| **Autonomy** | low |
| **Description** | Reviews code for security vulnerabilities |

**Use Case:** OWASP Top 10 audit — detect hardcoded secrets, injection vulnerabilities, auth issues.

**Output Format:** JSON report:
```json
{
  "severity": "critical|high|medium|low|info",
  "findings": [{"file": "...", "line": N, "severity": "...", "description": "..."}],
  "approved": false
}
```

**Constraints:** Does NOT fix issues or modify files — report only.

---

## Test Generator

| Property | Value |
|----------|-------|
| **File** | `~/.factory/droids/test-generator.md` |
| **Model** | swe-1-5 |
| **Autonomy** | medium |
| **Description** | Generates pytest and hypothesis property tests |

**Use Case:** Create unit tests, property-based tests, edge case coverage following existing test patterns.

**Output Format:** Python test code with `def test_*` functions, pytest fixtures, hypothesis decorators.

**Constraints:** Tests placed in `tests/` mirroring `src/` structure.

---

## Documentation Writer

| Property | Value |
|----------|-------|
| **File** | `~/.factory/droids/documentation-writer.md` |
| **Model** | claude-haiku-4-5 |
| **Autonomy** | medium |
| **Description** | Updates documentation following Fabrik conventions |

**Use Case:** Create/update README, guides, API docs, CHANGELOG entries.

**Output Format:** Markdown following `.windsurf/rules/40-documentation.md` conventions.

**Constraints:** Docs in `docs/` subdirectories only; root `.md` limited to allowed list.

---

## See Also

- `config/models.yaml` — Model definitions and stack ranking
- `templates/docs/EXECUTION_PLAN_TEMPLATE.md` — Plan template for Planner droid
- `.windsurf/rules/40-documentation.md` — Documentation conventions
