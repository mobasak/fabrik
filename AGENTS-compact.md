# Kilo CLI Agent Rules

## HARD STOPS
- NEVER commit — Traycer commits
- NEVER bare `pip install` — use `/opt/<project>/.venv/bin/pip`
- NEVER Alpine — use `-slim-bookworm`
- NEVER hardcode localhost/secrets — use `os.getenv()`
- NEVER modify files outside task scope

## WORKFLOW
1. **Implement** — code changes for current task only
2. **Self-review** — check hardcoded values, imports, env vars, and only your changes
3. **Lean gate** — `python scripts/final_gate.py --lean` (Tier 1, not completion) and fix all findings
4. **Changelog** — if you touched code/config/infra, add an entry under `## [Unreleased]` in `CHANGELOG.md`
5. **Stage** — `git add -A` (never commit)

If this task closes a milestone or batch, also run `python scripts/final_gate.py` and fix all findings before staging.

**Traycer is the orchestrator. Follow the task, report completion.**
