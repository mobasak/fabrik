# ⚠️ MANDATORY FIRST OUTPUT
Before taking ANY action, output: `RULES ACTIVE: [CODER|FIXER|REVIEWER] | [Never commit, Never bare pip, Always final_gate.py] | final_gate.py required`
**If you skip this, the task is non-compliant.**

## HARD STOPS
- NEVER commit — Traycer commits, not coding agents
- NEVER run bare `pip install` — always use `/opt/<project>/.venv/bin/pip install`
- NEVER use Alpine base images — use `-slim-bookworm` only
- NEVER hardcode localhost, secrets, or credentials — always use `os.getenv()`
- NEVER modify files outside task scope — stay within assigned phase/ticket
- ALWAYS run `python scripts/final_gate.py` before reporting complete
- ALWAYS self-review before running gates (Step 2.5 mandatory)

## MANDATORY STEPS
1. **Implement** — code changes for current phase/ticket only
2. **Self-review** — check hardcoded values, imports, env vars, db/schema.sql updates
3. **Final gate** — `python scripts/final_gate.py` → all PASS required
4. **Kilo review** — `python scripts/kilo_code_review.py staged --plan "..." --output json`

## FULL RULES
- **AGENTS.md** — your role section + `[ALL AGENTS]`
- **Coding patterns** — `.windsurf/rules/*.md`
