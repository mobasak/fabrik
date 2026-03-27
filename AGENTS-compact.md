# Kilo CLI Agent Rules

## HARD STOPS
- NEVER commit — Traycer commits
- NEVER bare `pip install` — use `/opt/<project>/.venv/bin/pip`
- NEVER Alpine — use `-slim-bookworm`
- NEVER hardcode localhost/secrets — use `os.getenv()`
- NEVER modify files outside task scope

## WORKFLOW
1. **Implement** — code changes for current phase/ticket only
2. **Self-review** — check hardcoded values, imports, env vars

## END OF PHASE ONLY (Traycer decides when)
- Kilo review: `git add -A && python scripts/kilo_code_review.py staged`
- Documentator: `python scripts/kilo_docs_enforcer.py --auto-generate`
- Final gate: `python scripts/final_gate.py`

**Traycer is the orchestrator. Follow the task, report completion.**
