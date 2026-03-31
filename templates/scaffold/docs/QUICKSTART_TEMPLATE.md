# QUICKSTART: Agent Execution Guide

**Last Updated:** YYYY-MM-DD
**Project Status:** Active
**Operating Manual:** `AGENTS.md`

**Note to Agents:** You are a **Coder**, **Reviewer**, or **Fixer**. You do NOT plan. You do NOT commit.

---

## 0. Mandatory First Output

Before taking ANY action, you must output the following string to confirm compliance:

```
RULES ACTIVE: [ROLE] | [Never commit, Never bare pip, Always final_gate.py]
```

---

## 1. Agent Completion Contract (4 Steps)

Every task follows this sequence. **Authority:** `AGENTS-compact.md`

### Step 1: IMPLEMENT
Implement changes scoped to current task only.

**Environment:**
```bash
# CRITICAL: Use project-specific .venv (PEP 668 compliance)
/opt/<project>/.venv/bin/python -m uvicorn src.<package>.main:app --reload

# Install dependencies (NEVER use bare pip)
/opt/<project>/.venv/bin/pip install <package>
```

**Constraints:**
- ❌ No Alpine base images → Use `python:3.12-slim-bookworm` or `node:22-bookworm-slim`
- ❌ No hardcoded secrets/localhost → Use `os.getenv()` and service names
- ✅ ARM64 compatibility → Add `platform: linux/arm64` in compose.yaml

**Internal Audit (before finishing Step 1):**
- [ ] All task requirements fully met
- [ ] No hardcoded secrets/localhost (use `os.getenv()`)
- [ ] No logic gaps or silent failure modes
- [ ] Write exactly 1 test file covering core logic path
- [ ] Adjacent fixes allowed: MAY fix directly adjacent, low-risk issues in same touched files/subsystem if it keeps implementation coherent or prevents obvious breakage

### Step 2: QUALITY GATE
Run and fix findings until `status: "success"`:

```bash
# Standard Tasks (default)
python scripts/final_gate.py --lean --json

# Milestone / Batch Closer (if explicitly labeled)
python scripts/final_gate.py --json
```

**Auto-runs:**
- Ruff (lint + format)
- mypy (type checking)
- Secrets scan
- Schema sync
- Changelog check (enforced in Tier 1)
- 20+ additional checks

**Fix all failures. Re-run until JSON output shows `"status": "success"`.**

### Step 3: CHANGELOG
Add one entry under `## [Unreleased]` (gate enforces presence).

Format:
```markdown
### Added/Changed/Fixed — Title (YYYY-MM-DD)
- Brief description of change
```

### Step 4: EXIT 0
Gate auto-stages changes. **Do not commit, do not stage manually.**

---

## 2. Optional Tools (Manual / On-Demand Only)

**Not part of default workflow. Use only if explicitly requested:**

### Kilo Review (Optional)
```bash
git add -A
python scripts/kilo_code_review.py staged --plan "task description" --output json
```

### Documentator (Optional)
```bash
python scripts/kilo_docs_enforcer.py --auto-generate --verbose
```

---

## 3. Infrastructure & Services

**Before building custom logic, check if an existing Fabrik service solves the need.**

**Reference:** `docs/reference/prebuilt-app-containers.md`

| Need | Use This |
|------|----------|
| Database | `postgres-main:5432` (shared PostgreSQL) |
| Cache | `redis:6379` (shared Redis) |
| PDF generation | Gotenberg at `pdf.vps1.ocoron.com` |
| Translation | Translator microservice (port 8000) |
| Image generation | Image Broker microservice (port 8010) |
| Email | Email Gateway microservice (port 3000) |
| DNS/domains | DNS Manager microservice (port 8001) |

**Ports:** Register new services in `PORTS.md` (Python: 8000-8099, Frontend: 3000-3099)

---

## 4. Common Commands

| Task | Command |
|------|---------|
| Install dependency | `/opt/<project>/.venv/bin/pip install <package>` |
| Start service | `/opt/<project>/.venv/bin/python -m uvicorn src.<pkg>.main:app --reload` |
| Check health | `curl http://localhost:8000/health` |
| Run tests | `/opt/<project>/.venv/bin/pytest tests/ -v` |
| Check Docker | `python scripts/enforcement/check_docker.py` |
| Check secrets | `python scripts/enforcement/check_secrets.py` |
| Full gate | `python scripts/final_gate.py` |

---

## 5. Completion

Once **Step 2 (Quality Gate)** passes with `"status": "success"`:
1. Report results to Traycer for verification
2. **Do NOT push to GitHub** — Traycer commits, not Coders

---

## 6. Quick Health Check

```bash
# Start service
cd /opt/<project>
source .venv/bin/activate
uvicorn src.<package>.main:app --reload --port 8000

# Test health endpoint (should test DB, not just return 200)
curl http://localhost:8000/health
```

**Expected:**
```json
{
  "service": "project-name",
  "status": "ok",
  "database": "connected",
  "timestamp": "2026-03-24T12:00:00Z"
}
```

---

## 7. Troubleshooting

**Build fails?** Run enforcement scripts individually:
```bash
python scripts/enforcement/check_docker.py
python scripts/enforcement/check_secrets.py
python scripts/enforcement/check_env_contract.py
python scripts/enforcement/check_compose_services.py
```

**See:** `TROUBLESHOOTING.md` for detailed diagnostic steps.

---

**This is an agent-first guide. For user-facing quickstart, see `README.md`.**
