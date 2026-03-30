# Kilo CLI Agent Rules

## DEFAULT COMPLETION CONTRACT
1. **Implement** — Logic changes for the current task only + 1 test.
2. **Run Quality Gate** — Execute and fix findings until success:
   - **Tasks 1-9**: `python scripts/final_gate.py --lean --json`.
   - **Task 10**: `python scripts/final_gate.py --json`.
3. **Changelog** — Add entry under `## [Unreleased]`.
4. **Exit** — If the gate passes, it will auto-stage your changes. Simply exit with code 0.

## HARD STOPS
- NEVER commit — Traycer commits.
- NEVER bare `pip install` — use `.venv/bin/pip`.
- NEVER modify files outside task scope.
