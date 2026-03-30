# Kilo CLI Agent Rules

## HARD STOPS
- NEVER commit — Traycer commits
- NEVER bare `pip install` — use `.venv/bin/pip`
- NEVER Alpine — use `-slim-bookworm`
- NEVER hardcode localhost/secrets — use `os.getenv()`
- NEVER modify files outside task scope

## ONE-PASS WORKFLOW

### Tasks Before Milestone Task: Rolling Green (Implement → Test → Clean → Gate)
1. **Implement** — logic changes for current task only
2. **Test** — add 1 test that validates the change (required)
3. **Auto-clean** — `make gate-lean` (runs ruff + mypy)
4. **Lean gate** — `python scripts/final_gate.py --lean --json` and fix all findings
5. **Changelog** — if you touched code/config/infra, add entry under `## [Unreleased]`
6. **Stage** — `git add -A` (never commit)

### Milestone Task: Full Gate
1. **Implement** — final changes
2. **Test** — add 1 test
3. **Auto-clean** — `make gate-lean` (runs ruff + mypy)
4. **Full gate** — `python scripts/final_gate.py --json` (all checks) and fix all findings
5. **Changelog** — update
6. **Stage** — `git add -A` (never commit)

## GATE OUTPUT
- JSON mode returns: `{"status": "success|failure", "tier": 1|2, "passed": N, "failed": N, "failures": [...]}`
- Exit code 0 = success, 1 = failure
- Parse JSON to determine next action

**Traycer is the orchestrator. Follow the task, report completion.**
