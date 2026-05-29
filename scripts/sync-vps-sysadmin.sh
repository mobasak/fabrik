#!/bin/bash
# Sync sysadmin knowledge files from WSL to VPS.
# Run after: editing docs, adding audit prompts, deploying/destroying
# services, changing system prompt, or any config change.
#
# Usage: bash scripts/sync-vps-sysadmin.sh
#
# What gets synced:
# - docs/infrastructure/*.md (inventory, runbooks, audit prompts, plans)
# - docs/operations/fabrik-lifecycle.md + architecture.md
# - scripts/audit/*.sh (diagnostic scripts)
# - scripts/sysadmin/* (bot, proactive check, system prompt)
# - specs/services/*.yaml (deployment specs — so sysadmin knows what's deployed)

set -euo pipefail
cd /opt/fabrik

echo "Syncing sysadmin knowledge to VPS..."

# Ensure dirs exist
ssh vps 'mkdir -p /opt/fabrik/docs/infrastructure/audit-prompts /opt/fabrik/docs/reference /opt/fabrik/scripts/audit /opt/fabrik/scripts/sysadmin /opt/fabrik/specs/services'

# NOTE: Do NOT sync root CLAUDE.md — that's for WSL dev (Claude Code developing fabrik).
# The VPS sysadmin's rules live in scripts/sysadmin/system-prompt.txt which is injected
# via --system-prompt flag per session. No CLAUDE.md on VPS.

# Infrastructure docs (all of them)
rsync -az docs/infrastructure/ vps:/opt/fabrik/docs/infrastructure/

# Reference docs the sysadmin reads
rsync -az docs/operations/fabrik-lifecycle.md docs/reference/architecture.md vps:/opt/fabrik/docs/reference/

# Audit scripts
rsync -az scripts/audit/ vps:/opt/fabrik/scripts/audit/

# Sysadmin bot files
rsync -az scripts/sysadmin/ vps:/opt/fabrik/scripts/sysadmin/

# Deployment specs (so sysadmin knows what's deployed and what shape each service has)
rsync -az specs/services/ vps:/opt/fabrik/specs/services/

# VPS apply limits script
rsync -az scripts/vps_apply_limits.sh vps:/opt/fabrik/scripts/

# Generate fresh inventory on VPS
rsync -az scripts/generate_vps_inventory.py vps:/opt/fabrik/scripts/
ssh vps 'cd /opt/fabrik && python3 scripts/generate_vps_inventory.py --update 2>/dev/null' || true

echo "✅ Sync complete."
echo ""
echo "Files synced:"
echo "  docs/infrastructure/*, docs/reference/{fabrik-lifecycle,architecture}.md"
echo "  scripts/audit/*, scripts/sysadmin/*, specs/services/*"
echo "  scripts/vps_apply_limits.sh, scripts/generate_vps_inventory.py"
