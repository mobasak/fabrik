# Kilo CLI Agent Rules

## HARD STOPS
- NEVER commit — Traycer commits
- NEVER bare `pip install` — use `.venv/bin/pip`
- NEVER Alpine — use `-slim-bookworm`
- NEVER hardcode localhost/secrets — use `os.getenv()`
- NEVER modify files outside task scope

## DEFAULT COMPLETION CONTRACT

1. **Implement** — Logic changes for current task only + 1 test.
2. **Auto-Clean** — Run `.venv/bin/ruff check . --fix && .venv/bin/ruff format .` to auto-fix linting.
3. **Run Quality Gate** — Address all failures reported in the JSON output:
   - **Normal Task (1-9)**: Run `python scripts/final_gate.py --lean --json`.
   - **Milestone Task (10)**: Run `python scripts/final_gate.py --json`.
4. **Changelog** — Add entry under `## [Unreleased]` if code/config/infra changed.
5. **Stage** — `git add -A` (never commit).

## GATE OUTPUT
- JSON mode returns: `{"status": "success|failure", "tier": 1|2, "passed": N, "failed": N, "failures": [...]}`
- Exit code 0 = success, 1 = failure
- Fix all findings until `"status": "success"` appears

**Traycer is the orchestrator. Follow the task, report completion.**
