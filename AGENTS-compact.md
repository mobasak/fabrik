# Kilo CLI Agent Rules

## DEFAULT COMPLETION CONTRACT

1. **Implement** — Logic changes for the current task only + 1 test. Critically audit your implementation against the initial task and production-grade best practices, specifically identifying logic gaps, security risks, and silent failure modes while verifying all requirements are fully met.
2. **Run Quality Gate** — Execute and fix findings until success:
   - **Standard Tasks**: `python scripts/final_gate.py --lean --json`.
   - **Milestone / Batch Closer Tasks**: If the task description explicitly identifies this as a "Milestone" or "Batch Closer," run `python scripts/final_gate.py --json`.
3. **Changelog** — Add entry under `## [Unreleased]`.
4. **Exit** — If the gate passes, it will auto-stage your changes. Simply exit with code 0.

## HARD STOPS
- NEVER commit — Traycer commits.
- NEVER bare `pip install` — use `.venv/bin/pip`.
- NEVER Alpine — use `-slim-bookworm`.
- NEVER hardcode localhost/secrets — use `os.getenv()`.
- NEVER modify files outside task scope.
