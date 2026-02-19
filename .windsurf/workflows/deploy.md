---
auto_execution_mode: 0
description: Deploy application to VPS via Coolify
---

# Deploy Workflow

Deploy application to production VPS via Coolify auto-deploy.

## Prerequisites

- [ ] All tests passing locally
- [ ] `CHANGELOG.md` updated with release notes
- [ ] Clean working tree (`git status` shows no uncommitted changes)
- [ ] Feature branch merged to `main` (or ready to push `main` directly)

## Steps

// turbo
1. **Pre-flight checks** — Run verification gates:
```bash
pytest tests/ -x --tb=short
ruff check .
mypy .
```

2. **Docker build verification** — Build and test locally:
```bash
docker compose build
docker compose up -d --wait
curl -f http://localhost:8000/health
docker compose down
```

3. **Push to production** — Coolify auto-deploys on push to `main`:
```bash
git push origin main
```

// turbo
4. **Verify health on VPS** — Confirm deployment succeeded:
```bash
curl -f https://$PROJECT.vps1.ocoron.com/health
```

## Verification

- [ ] Pre-flight gates passed (tests, lint, types)
- [ ] Local Docker build succeeded
- [ ] Health endpoint responds 200 on VPS
- [ ] No error logs in Coolify dashboard
