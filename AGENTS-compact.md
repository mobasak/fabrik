# Kilo CLI Agent Rules

## COMPLETION CONTRACT (Execute in order, every task)

1. **IMPLEMENT** — Changes scoped to current task only. Before finishing, internal audit:
   - All task requirements fully met
   - No hardcoded secrets/localhost (use `os.getenv()`)
   - No logic gaps or silent failure modes
   - Write exactly 1 test file covering the core logic path (skip for documentation-only tasks that change no code)
   - **Adjacent fixes allowed**: You MAY fix directly adjacent, low-risk issues in the same touched files/subsystem if doing so keeps the implementation coherent or prevents obvious breakage

2. **QUALITY GATE** — Run and fix findings until `status: "success"`:
   - **Standard Tasks**: `python scripts/final_gate.py --lean --json`
   - **Milestone / Batch Closer**: `python scripts/final_gate.py --json`
   *(Only run full gate if the task is explicitly labeled as a "Milestone" or "Batch Closer")*

3. **CHANGELOG** — Add one entry under `## [Unreleased]` (Gate enforced)

4. **EXIT 0** — The gate auto-stages your changes. Do not commit, do not stage manually.

---

## CROSS-CUTTING (Every task)

1. **Doc currency** — Update `INDEX.md`, `CHANGELOG.md`, `README.md` when files or features change.
2. **Structured logging** — No `print()` / `console.log()` in production code; use the project's structured logger.
3. **User guide** — If the change is user-facing and `project.yaml` has `has_user_guide: true`, add/update a page in `docs/user-guide/`.
4. **Reusable modules** — Utility code goes in `src/utils/` or `src/lib/` with zero project-specific imports; tag `[reusable]` in `INDEX.md`.

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
