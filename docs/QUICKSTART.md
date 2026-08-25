# Quick Start

**Last Updated:** 2026-08-25

Get Fabrik running in 5 minutes. Full reference: [DEPLOYMENT_ARCHITECTURE.md](DEPLOYMENT_ARCHITECTURE.md).

## Prerequisites

Before starting, ensure you have:

- [ ] VPS with SSH access configured
- [ ] SSH key pair (public key on VPS)
- [ ] Cloudflare account with API access (default DNS driver; Namecheap is optional, only needed if running the namecheap service locally)
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
# VPS (SSH key-based; fabrik SSHes here to deploy)
VPS_HOST=your-vps-ip
VPS_USER=ozgur
# Configure a `vps` alias in ~/.ssh/config (or set FABRIK_VPS_SSH_HOST)

# DNS — Cloudflare driver (current/primary)
CLOUDFLARE_API_TOKEN=your-token
CLOUDFLARE_ZONE_ID=your-zone-id

# DNS Manager service — RETIRED (not deployed; dns.vps1.ocoron.com returns NXDOMAIN)
# DNS_MANAGER_URL=https://dns.vps1.ocoron.com

# Backblaze B2 (backups)
B2_KEY_ID=your-key-id
B2_APPLICATION_KEY=your-app-key
B2_BUCKET_NAME=your-bucket
```

## First Deployment

```bash
# (Optional but recommended — Stage 1 of the lifecycle, T3-01) Capture intent
# in a preplan markdown BEFORE scaffolding. Edit the 9 sections, then hand off
# to scaffold via --from-preplan.
fabrik preplan new hello-api
# edit docs/preplans/<today>-hello-api.md — fill in Idea / Shape / Deps / Domain / Success criteria
# Then scaffold ingests the preplan and layers a `Preplan:` reference into all 4 AI guardrail files
# (AGENTS.md / CLAUDE.md / AGENTS-compact.md / .windsurfrules) so every downstream agent
# reads the same intent without re-deriving it.
fabrik scaffold hello-api --from-preplan docs/preplans/$(date -u +%F)-hello-api.md

# OR scaffold directly without a preplan — spec auto-generated with `shape:` defaults from the template.
# Emits per-project CLAUDE.md (Claude Code bootstrap) + AGENTS-compact.md (Kilo CLI's bootstrap;
# Kilo CLI itself RETIRED 2026-07-19 — file still synced for now) alongside the existing
# .windsurfrules (Windsurf Cascade's bootstrap; Cascade itself RETIRED 2026-07-19 — file still
# synced for now). Ends with a Traycer next-step hint.
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
cd /opt/hello-api && fabrik apply   # resolves spec from project.yaml
```

**Secret precedence:** `-s KEY=VALUE` flag > `/opt/<project>/.env` > `/opt/fabrik/.env` > process env.

## Verify

```bash
# Deployment status (needs a spec path). Reads live container state via SSH
# and the local .fabrik/state/<id>.json file written by `fabrik apply`.
fabrik status /opt/fabrik/specs/services/hello-api.yaml

# Preview the plan (post-T1-02: now also prints a "🔧 Infrastructure Registrars"
# section showing which of the 9 registrars will RUN/skip with shape-based reason).
fabrik plan /opt/fabrik/specs/services/hello-api.yaml

# Tail logs (Loki for centralized, or `docker logs` over SSH for live container).
fabrik logs /opt/fabrik/specs/services/hello-api.yaml

# `fabrik app-logs` was REMOVED 2026-08-25 (it called the retired Coolify API). Use
# `fabrik logs` above, or `docker logs <app>` over SSH.

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
# No DNS removal, no compose-stack teardown, no file cleanup.
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --partial gatus --dry-run
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --partial gatus --partial backrest -y

# Local dev loop (T3-03) — code in WSL, watch, bundle for review.
cd /opt/<project>
fabrik dev -d                                    # start compose.dev.yaml stack
fabrik logs --local -f                           # tail dev stack logs
fabrik logs --local --service api -f             # one service only
fabrik review                                    # bundle diff+spec+preplan to .fabrik/review/<ts>.md
fabrik review --since HEAD~3 --out /tmp/r.md     # custom diff range + output

# State-driven destroy (T4-02) — replay what was actually deployed, not what the spec says now.
# Use when the spec has drifted between apply and destroy (e.g. shape.has_search_feature flipped).
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state --dry-run
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state -y                # safe path
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state --drop-data -y    # required when state has postgres/redis/meilisearch
# After success: state file moves to /opt/fabrik/.fabrik/state/_destroyed/<id>.json.<UTC-ts>

# Cross-VPS portability bundle (T4-03) — capture this VPS's full apply-state for rebuild on vps2.
fabrik export --out /tmp/vps1-base.tar.gz                          # default skips remote-config probes
fabrik export --out /tmp/vps1-full.tar.gz --include-data           # reserved: postgres/meili snapshots
fabrik import /tmp/vps1-base.tar.gz                                # dry-run plan (default; import is shipped UNTESTED)
fabrik import /tmp/vps1-base.tar.gz --apply                        # stubbed real run; real roundtrip deferred to vps2
# Bundle has NO secret values — operator re-populates .env on the target per secrets-redacted.json.

# Hit the endpoint
curl https://hello-api.vps1.ocoron.com/health
```

Expected wall time for a first deploy: **~60–90s** (published-image templates) or **2–5 min** (build-from-source). See [DEPLOYMENT_ARCHITECTURE.md](DEPLOYMENT_ARCHITECTURE.md) §9.6 for the validated maximal-shape E2E test.

## Scan Project Health

```bash
# Check scaffold health across all projects
python scripts/health_summary.py

# JSON output for automation
python scripts/health_summary.py --json
```

See `docs/workflows/HEALTH_SUMMARY_WORKFLOW.md` for details.

## Next Steps

- [DEPLOYMENT_ARCHITECTURE.md](DEPLOYMENT_ARCHITECTURE.md) — **canonical deploy reference**, read this next
- [CONFIGURATION.md](CONFIGURATION.md) — every env var explained
- [reference/architecture.md](reference/architecture.md) — how the pieces fit together
- [reference/fabrik-cli-reference.md](reference/fabrik-cli-reference.md) — all 22 CLI commands
- [reference/modules/templates.md](reference/modules/templates.md) — deploy templates for the scaffold types (`wordpress` is a recognised deploy/shape type with no template — redirects to the legacy `/opt/wpf` CLI; `next-tailwind` is planned-but-unimplemented — template files exist but there is no scaffolder function, `spec_generator.py:53`)
- [reference/modules/deployment-orchestrator.md](reference/modules/deployment-orchestrator.md) + [reference/modules/drivers.md](reference/modules/drivers.md)
- [LESSONS_LEARNT.md](LESSONS_LEARNT.md) — every live-incident invariant (read before deep changes)
- [infrastructure/vps-status.md](infrastructure/vps-status.md) — VPS inventory
