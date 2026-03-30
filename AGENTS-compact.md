# Kilo CLI Agent Rules

## COMPLETION CONTRACT (Execute in order, every task)

1. **IMPLEMENT** — Changes scoped to current task only. Before finishing, internal audit:
   - All task requirements fully met
   - No hardcoded secrets/localhost (use `os.getenv()`)
   - No logic gaps or silent failure modes
   - Write exactly 1 test file covering the core logic path

2. **QUALITY GATE** — Run and fix findings until `status: "success"`:
   - **Standard Tasks**: `python scripts/final_gate.py --lean --json` 
   - **Milestone / Batch Closer**: `python scripts/final_gate.py --json` 
   *(Only run full gate if the task is explicitly labeled as a "Milestone" or "Batch Closer")*

3. **CHANGELOG** — Add one entry under `## [Unreleased]` (Gate enforced) 

4. **EXIT 0** — The gate auto-stages your changes. Do not commit, do not stage manually.

---

## HARD STOPS — NEVER do these

| Rule | Instead |
| :--- | :--- |
| `git commit` | Traycer commits |
| `git add` | `final_gate.py` handles auto-staging |
| bare `pip install` | `/opt/<project>/.venv/bin/pip install` |
| Alpine base image | `python:3.12-slim-bookworm` or `node:22-bookworm-slim` |
| edit files outside task scope | stay strictly within the assigned task boundaries |
| modify `pyproject.toml` / `requirements.txt` | only if the task explicitly requires dependency changes |
| create files outside project tree | use local project paths only |
