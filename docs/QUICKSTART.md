# Quick Start

**Last Updated:** 2026-04-22

Get Fabrik running in 5 minutes. Full reference: [DEPLOYMENT.md](DEPLOYMENT.md).

## Prerequisites

Before starting, ensure you have:

- [ ] VPS with SSH access configured
- [ ] SSH key pair (public key on VPS)
- [ ] Namecheap account with API access
- [ ] Backblaze B2 account
- [ ] A domain you control

## Installation

```bash
# Clone/navigate to project
cd /opt/fabrik

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

## Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

Required variables:

```bash
# VPS
VPS_HOST=your-vps-ip
VPS_USER=deploy

# Coolify
COOLIFY_API_URL=https://coolify.yourdomain.com
COOLIFY_API_TOKEN=your-token

# DNS Manager
DNS_MANAGER_URL=https://dns.vps1.ocoron.com

# Or use Cloudflare (optional)
# CLOUDFLARE_API_TOKEN=your-token
# CLOUDFLARE_ZONE_ID=your-zone-id

# Backblaze B2 (backups)
B2_KEY_ID=your-key-id
B2_APPLICATION_KEY=your-app-key
B2_BUCKET_NAME=your-bucket
```

## First Deployment

```bash
# Scaffold a new project — spec auto-generated with `shape:` defaults from the template.
# Emits per-project CLAUDE.md (Claude Code bootstrap) + AGENTS-compact.md (Kilo CLI)
# alongside the existing .windsurfrules (Cascade). Ends with a Traycer next-step hint.
fabrik scaffold hello-api --type python-api

# Optionally also create a private GitHub repo (mobasak/<name>) at the same time:
fabrik scaffold hello-api --type python-api --github-create

# (Optional) Tune the spec
nano /opt/fabrik/specs/services/hello-api.yaml   # shape: / domain: / env: / health:

# Put secrets in the project .env
cat > /opt/hello-api/.env <<'EOF'
API_KEY=your_api_key
DATABASE_PASSWORD=your_password
EOF

# Dry-run first (always uses the orchestrator)
fabrik apply /opt/fabrik/specs/services/hello-api.yaml --dry-run

# Deploy
fabrik apply /opt/fabrik/specs/services/hello-api.yaml

# Or: project-based deploy (reads /opt/hello-api/project.yaml)
fabrik deploy --project /opt/hello-api
```

**Secret precedence:** `-s KEY=VALUE` flag > `/opt/<project>/.env` > `/opt/fabrik/.env` > process env.

## Verify

```bash
# Deployment status (needs a spec path). Resolves the spec.id against Coolify,
# trying both the bare id AND the `fabrik-<id>` prefix so it works for
# Coolify-prefixed apps (fabrik-proxy, fabrik-file-worker, etc.) transparently.
fabrik status /opt/fabrik/specs/services/hello-api.yaml

# Preview the plan (post-T1-02: now also prints a "🔧 Infrastructure Registrars"
# section showing which of the 9 registrars will RUN/skip with shape-based reason).
fabrik plan /opt/fabrik/specs/services/hello-api.yaml

# Tail logs (Loki or Coolify) — same `fabrik-<id>` candidate-list lookup as status.
fabrik logs /opt/fabrik/specs/services/hello-api.yaml
fabrik app-logs /opt/fabrik/specs/services/hello-api.yaml -n 50

# Audit live VPS state against what shape says SHOULD be registered (T2-02).
# Pivot table of all 9 registrars × all deployed specs.
fabrik audit-registrars
fabrik audit-registrars --spec /opt/fabrik/specs/services/hello-api.yaml --json

# Sweep the fleet — re-run InfrastructureProvisioner per spec (T2-02 G-F2).
fabrik reconcile-all --filter hello-api          # dry-run, scoped
fabrik reconcile-all --yes                       # apply across fleet

# Postcondition check: every shape-applicable registrar is live.
fabrik verify hello-api.vps1.ocoron.com --spec registrars

# Surgical un-registration of a single registrar (T2-02 G-F5).
# No DNS removal, no Coolify app delete, no file cleanup.
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --partial gatus --dry-run
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --partial gatus --partial backrest -y

# Hit the endpoint
curl https://hello-api.vps1.ocoron.com/health
```

Expected wall time for a first deploy: **~60–90s** (published-image templates) or **2–5 min** (build-from-source). See [DEPLOYMENT.md](DEPLOYMENT.md) §9.6 for the validated maximal-shape E2E test.

## Scan Project Health

```bash
# Check scaffold health across all projects
python scripts/health_summary.py

# JSON output for automation
python scripts/health_summary.py --json
```

See `docs/workflows/HEALTH_SUMMARY_WORKFLOW.md` for details.

## Next Steps

- [DEPLOYMENT.md](DEPLOYMENT.md) — **canonical deploy reference**, read this next
- [CONFIGURATION.md](CONFIGURATION.md) — every env var explained
- [reference/architecture.md](reference/architecture.md) — how the pieces fit together
- [reference/fabrik-cli-reference.md](reference/fabrik-cli-reference.md) — all 22 CLI commands
- [reference/templates.md](reference/templates.md) — 12 deploy templates (11 scaffold types + `next-tailwind` deploy-only)
- [reference/orchestrator.md](reference/orchestrator.md) + [reference/drivers.md](reference/drivers.md)
- [LESSONS_LEARNT.md](LESSONS_LEARNT.md) — every live-incident invariant (read before deep changes)
- [operations/vps-status.md](operations/vps-status.md) — VPS inventory
