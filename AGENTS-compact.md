# Kilo CLI Agent Rules

## HARD STOPS
- NEVER commit — Traycer commits
- NEVER bare `pip install` — use `/opt/<project>/.venv/bin/pip`
- NEVER Alpine — use `-slim-bookworm`
- NEVER hardcode localhost/secrets — use `os.getenv()`
- NEVER modify files outside task scope

## WORKFLOW
1. **Implement** — code changes for current task only
2. **Self-review** — check hardcoded values, imports, env vars, and work you have done
3. **Lean gate** — `python scripts/final_gate.py --lean` (syntax, secrets, schema only) then fix found issues
4. **Stage** — `git add -A` (never commit)

**Traycer is the orchestrator. Follow the task, report completion.**
