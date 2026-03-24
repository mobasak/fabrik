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

## 1. The 8-Step Execution Workflow

Every task must follow this exact sequence. **Skipping a step = workflow failure.**

### Step 1: Plan (Traycer Only)
Traycer provides functional spec. Coders execute, never plan.

### Step 2: Implementation
Implement changes for the current phase or ticket only.

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

### Step 2.5: Self-Review (MANDATORY)
**Before requesting Kilo Review:**
- [ ] All imports exist
- [ ] `.env.example` updated with new variables
- [ ] Docker health checks test real dependencies (not just 200 OK)
- [ ] Port registered in `PORTS.md`

### Step 3: Kilo Review & Fix
```bash
git add <intended_files>
python scripts/kilo_code_review.py staged --plan "Task description" --output json
```

**Fixer Role:** Address ALL BLOCKER, MAJOR, and MINOR findings. Max 5 iterations.

### Step 4: Documentator (Auto-Generate)
```bash
python scripts/kilo_docs_enforcer.py --auto-generate --verbose
git add CHANGELOG.md docs/reference/*.md
python scripts/kilo_docs_enforcer.py --enforce
```

**Required:**
- [ ] Entry in `CHANGELOG.md`
- [ ] API docs for new functions/endpoints
- [ ] `.env.example` documented

### Step 5: Final Gate (ALL CHECKS MUST PASS)
```bash
python scripts/final_gate.py
```

**This script automatically runs:**
- `check_docker.py` — Verifies ARM64 platform, no Alpine, HEALTHCHECK present
- `check_secrets.py` — Scans for hardcoded keys/tokens
- `check_env_contract.py` — Syncs `.env.example` with compose.yaml
- 24 additional enforcement checks

**Exit code 0 = PASS. Anything else = STOP and fix.**

### Step 6: Verify (Traycer Only)
Traycer confirms spec compliance.

### Step 7: Commit (Traycer Only)
Traycer commits. **Coders never commit.**

---

## 2. Infrastructure & Services

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

## 3. Common Commands

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

## 4. Completion

Once **Step 5 (Final Gate)** passes with exit code 0:
1. Report results to Traycer for verification
2. **Do NOT push to GitHub** — Traycer commits, not Coders

---

## 5. Quick Health Check

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

## 6. Troubleshooting

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
