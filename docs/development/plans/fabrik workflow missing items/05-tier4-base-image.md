# 05 — Tier 4: Base-Image Architectural Items (v3.2)

**Total effort:** ~28 h; in scope for the single Fabrik Workflow Convergence epic; depends on Tier 2 G-F3 state file (was 3 days in v1; +0.5 day for G-J2 secrets ergonomics)
**Risk:** higher — touches portability, persistence semantics, alerting infrastructure
**Goal:** make this VPS portable as a base image for "upcoming systems" (Özgür's stated long-term vision: sequential company launches, eventually a holding company structure)

## v2 changes

- §28 G-J2 effort revised from 1 day → 1.5 days; explicit note that secrets-bundle re-population for ~40 services is a real ergonomics cost; secrets tooling (1Password CLI / age / sops) deferred to a future Tier 4+ item — addresses C9
- §31 G-G5 reuses existing Alertmanager telegram receiver pattern instead of adding a new receiver — addresses C8
- All "41 projects" → "42 projects" (where referenced)

## Why Tier 4 separate from Tier 1-3

Tier 1-3 close the day-to-day operational loop. Tier 4 closes the **multi-VPS / portability / disaster-recovery** loop. These are bigger bets:

- `fabrik export` / `fabrik import` enables cloning vps1 as base for vps2/vps3
- `fabrik destroy --use-state` removes the spec-edit-between-apply-and-destroy drift risk
- Per-registrar drift alerting (Alertmanager → Telegram) extends the audit_authelia model to all 9 registrars
- Postgres allocation registry mirrors the redis pattern for symmetric scale safety

These items are NOT blockers for the current single-VPS workflow. Defer until:
- You're standing up vps2 (then G-J2 is critical), OR
- Tier 1-3 has been live long enough that drift between apply and destroy starts biting (then G-F4 is critical), OR
- An incident exposes that multi-registrar drift was silent (then G-G5 is critical)

## Order of operations

28-29 are the portability story. 30 is destroy hardening. 31 is the alerting story (corrected).

---

## 28. G-J2 — `fabrik export` / `fabrik import` for cross-VPS portability (EFFORT REVISED v2)

**Effort:** 1.5 days (was 1 day; +0.5 day for secrets ergonomics — addresses C9)
**Files:** `src/fabrik/cli.py` (two new subcommands) + `src/fabrik/portability.py` (new module)

### Why

Cloning vps1 as base for vps2 today requires manual: recreating each Coolify Application, re-binding domain → app, re-injecting secrets per app, re-creating Authelia rules per domain, re-importing Backrest plans, etc.

A `fabrik export` should produce a portable bundle; `fabrik import` should rebuild on the new VPS.

### Export bundle structure

```
fabrik-export-<vps>-<YYYY-MM-DD>.tar.gz
├── manifest.json                     # version, source vps, timestamp, list of contents
├── specs/                            # all specs (already in repo, included for self-contained bundle)
│   └── services/*.yaml
├── state/                            # .fabrik/state/<id>.json from G-F3 — coolify_uuid omitted (regenerated)
│   └── *.json
├── secrets-redacted.json             # WSL /opt/fabrik/.env keys (values redacted)
├── coolify/
│   ├── applications.json             # Coolify app config exports (env vars, source, healthcheck) sans UUIDs
│   ├── services.json                 # Infrastructure service config
│   └── projects.json                 # Coolify project structure
├── monitoring/
│   ├── prometheus.yml
│   ├── alertmanager.yml
│   ├── gatus/                        # All endpoints
│   ├── grafana/dashboards/           # All Fabrik dashboards
│   └── redis-assignments.json
├── authelia/
│   └── configuration.yml             # Access rules
├── backrest/
│   └── config.json                   # All plans + repo definitions
└── README.md                         # restore instructions
```

### Secrets ergonomics (NEW v2 — addresses C9)

The bundle's `secrets-redacted.json` lists key NAMES (e.g., `CLOUDFLARE_API_TOKEN`, `GITHUB_TOKEN`, `STRIPE_SECRET_KEY`) but NEVER values. Operator must re-populate on the target VPS manually.

For ~40 services with multiple secrets each, this is a real ergonomics cost. The 1.5-day estimate accounts for:
- 1 day: export/import pipeline (tarball + Coolify API rehydration)
- 0.5 day: docs + manual secrets re-population walkthrough on the target

### Future deferred enhancement (Tier 4+ or later)

Wire a secrets manager (1Password CLI / age / sops) so `fabrik import --secrets-from <vault>` re-populates automatically. Out of scope for this version — operator handles secrets manually, with the bundle's redacted list as a checklist.

### `fabrik export` behavior

```python
@cli.command()
@click.option("--output", default=None, help="Output path")
@click.option("--include-data", is_flag=True, help="Include postgres dumps and meili snapshots")
def export(output: str | None, include_data: bool):
    """Export the current VPS state as a portable bundle for cloning."""
    # 1. Collect specs/, .fabrik/state/, monitoring configs (via SSH/scp)
    # 2. Pull Coolify Applications + Services + Projects via Coolify API
    # 3. Pull Authelia config from /var/lib/docker/volumes/<authelia-vol>
    # 4. Pull Backrest config
    # 5. Optionally: pg_dump all postgres-main DBs, meili snapshots
    # 6. Tar + gzip
    # 7. Print restore instructions
```

### `fabrik import` behavior

Run on a fresh VPS that has Coolify + the Fabrik base infrastructure (postgres-main, redis-main, etc.) bootstrapped. Reverses export:

1. Recreate Coolify Projects → Services → Applications via API.
2. Re-inject env vars (operator must re-populate secrets).
3. Re-create Authelia rules.
4. Re-create Backrest plans (repo definitions need re-auth).
5. Re-create Prometheus/Gatus configs.
6. Re-create Grafana dashboards.
7. Restore postgres dumps if `--include-data` was used at export.
8. Run `fabrik audit-registrars` to verify post-import state.

### Acceptance criteria

- `fabrik export --output ./vps1-base.tar.gz` produces a complete bundle.
- Bundle README documents prerequisites for the target VPS.
- Manual test: spin up an Ubuntu VM, install Coolify + Fabrik base infra, run `fabrik import vps1-base.tar.gz`, end up with all Coolify Applications visible.
- Operator re-populates `.env` secrets manually (~0.5 day for ~40 services).
- `fabrik audit-registrars` on the imported VPS reports no MISSING.

### Note on scope

Edge cases (LetsEncrypt cert transfer, DNS provider re-binding, OAuth providers like GitHub apps) are out of scope — operator handles those manually with the bundle as reference.

---

## 29. G-J4 — Postgres allocation registry

**Effort:** 2 hours (unchanged from v1)
**File on VPS:** `/opt/monitoring/configs/postgres/allocations.json` (new) + `src/fabrik/drivers/postgres.py` (extend)

### Schema

```json
{
  "version": 1,
  "last_updated": "2026-05-09T...",
  "allocations": {
    "site_provisioner": {
      "owner": "fabrik",
      "spec_id": "site-provisioner",
      "user": "site_provisioner",
      "created_at": "2026-04-22T...",
      "notes": ""
    },
    "proxy_management": {
      "owner": "manual",
      "spec_id": "fabrik-proxy",
      "user": "ozgur",
      "created_at": "2025-10-29T...",
      "notes": "infra.postgres: false override"
    },
    "translator_service": {
      "owner": "manual",
      "spec_id": "translator",
      "user": "postgres",
      "notes": "post-Tier-1 G-H8 decision: kept as-is with infra.postgres: false override"
    },
    "glitchtip": {
      "owner": "infrastructure",
      "spec_id": null,
      "user": "postgres",
      "notes": "GlitchTip Coolify Service, not a Fabrik Application"
    }
  }
}
```

### Driver extension

`drivers/postgres.py::create_database()` writes an entry on success. `drop_database()` removes it. A new `list_allocations()` reads and reports.

### Acceptance criteria

- File exists at `/opt/monitoring/configs/postgres/allocations.json`.
- `fabrik audit-registrars` (Tier 2) reports drift between `allocations.json` and live `pg_database`.
- New service deploys add entries; `fabrik destroy --drop-data` removes them.

---

## 30. G-F4 — `fabrik destroy --use-state`

**Effort:** 1 day (unchanged from v1)
**Files:** `src/fabrik/cli.py` (extend `destroy`) + `src/fabrik/orchestrator/destroyer.py` (add state-driven path)
**Dependency:** Tier 2 G-F3 (state file must exist) AND data_bearing flag (added in v2 — addresses C3)

### Why

Current destroy is shape-driven (`destroyer.py:433`). Risk: spec is edited between apply and destroy → destroy uses NEW shape, misses resources created under OLD shape.

Example: deploy with `shape.has_search_feature: true` → meilisearch index created. Edit spec to `false`. Destroy sees `false` → meilisearch index leaks.

### Required behavior

```
$ fabrik destroy specs/services/captcha.yaml --use-state
📋 Reading .fabrik/state/captcha.json:
   Tracked resources: 4 (gatus, glitchtip, grafana_annotation, dns)
   Coolify UUID: fwgcokk0...
🗑️  Tearing down per state file (NOT per current spec):
   ...
✅ Destroyed. State file moved to .fabrik/state/_destroyed/captcha.json.<timestamp>
```

### Pseudocode

```python
@cli.command()
@click.option("--use-state", is_flag=True, help="Tear down based on .fabrik/state/<id>.json")
@click.option("--drop-data", is_flag=True, help="Required to destroy data-bearing resources")
def destroy(spec_path: str, use_state: bool, drop_data: bool, ...):
    if use_state:
        state_file = FABRIK_ROOT / ".fabrik" / "state" / f"{spec.id}.json"
        if not state_file.exists():
            click.echo("✗ No state file — fall back to spec-driven destroy?", err=True)
            raise SystemExit(1)
        state = json.loads(state_file.read_text())

        # NEW v2: enforce --drop-data for data-bearing resources
        data_bearing = [r for r in state["registrars_applied"] if r.get("data_bearing")]
        if data_bearing and not drop_data:
            click.echo(f"✗ {len(data_bearing)} data-bearing resources detected (postgres/meilisearch).")
            click.echo(f"   Re-run with --drop-data to confirm destruction, or omit --use-state.")
            raise SystemExit(1)

        report = destroy_from_state(state, drop_data=drop_data, dry_run=dry_run)
    else:
        # existing shape-driven path
        report = destroy_deployment(spec, ...)
```

### Acceptance criteria

- `fabrik destroy --use-state` reverses every resource recorded in the state file, including ones the current spec wouldn't trigger.
- `--use-state` without `--drop-data` BLOCKS destruction of data-bearing resources (postgres + meilisearch entries with `data_bearing: true`).
- `fabrik destroy` (no flag) keeps existing shape-driven behavior for back-compat.
- After `--use-state` destroy, state file is moved to `.fabrik/state/_destroyed/<id>.json.<ts>`.
- Test: deploy with shape A → edit spec to shape B → `destroy --use-state` reverses A's resources, not B's.

---

## 31. G-G5 — Per-registrar drift alerting (CORRECTED v2 — reuse existing Alertmanager pattern)

**Effort:** 1 day (unchanged from v1)
**Files:** `scripts/audit_<registrar>.py` × 8 (or one combined `fabrik audit-registrars --json` consumer) + 1 systemd timer + Alertmanager **route** (NOT new receiver)
**Dependency:** Tier 2 G-G4 (audit_authelia timer exists; mirror its pattern) AND Tier 2 G-G2 (`fabrik audit-registrars --json`)

### Why

Today only authelia has a drift detector. The other 8 registrars (postgres, redis, gatus, backrest, glitchtip, grafana, meilisearch, prometheus) have no equivalent. If a manual VPS edit drifts from spec, the operator finds out on the next deploy attempt — possibly weeks later.

### Reuse existing Alertmanager pattern (NEW v2 — addresses C8)

**v1 mistake:** v1 proposed adding a NEW receiver `telegram-fabrik-drift` to Alertmanager.

**Corrected v2:** the existing `/opt/monitoring/configs/alertmanager/alertmanager.yml` (on VPS) already has telegram receivers wired for Fabrik infrastructure alerts. Reuse them.

The full chain has THREE pieces and must be built bottom-up:

**Piece 1 — Pushgateway metric** (NEW): the audit job pushes one gauge per (registrar, service) drift detection:
```
fabrik_registrar_drift{registrar="postgres",service="captcha"} 1
```
Cleared (set to 0 or deleted) when the drift is resolved.

**Piece 2 — Prometheus alert rule** (NEW, MUST land BEFORE the Alertmanager route): create `/opt/monitoring/configs/prometheus/rules/fabrik-drift.yml` (the `rules/` subdirectory already exists per `ssh vps 'ls /opt/monitoring/configs/prometheus/'`). Reference it from `prometheus.yml`'s `rule_files:` block. The rule:
```yaml
# /opt/monitoring/configs/prometheus/rules/fabrik-drift.yml
groups:
  - name: fabrik-registrar-drift
    interval: 1m
    rules:
      - alert: FabrikRegistrarDrift
        expr: fabrik_registrar_drift > 0
        for: 5m
        labels:
          severity: warning
          alert_class: registrar_drift   # ← THIS is what Alertmanager routes on
        annotations:
          summary: "Drift in {{ $labels.registrar }} for {{ $labels.service }}"
          detail: "Live state diverges from spec. Run: fabrik audit-registrars --spec specs/services/{{ $labels.service }}.yaml"
```
Without this rule, no alert ever fires with `alert_class: registrar_drift`, and the Alertmanager route below has nothing to match.

**Piece 3 — Alertmanager route** (extends existing config): adds a new ROUTE that matches `alert_class: registrar_drift` and routes to the existing telegram receiver with appropriate templating:

```yaml
# /opt/monitoring/configs/alertmanager/alertmanager.yml (extension)
route:
  receiver: telegram-fabrik-default  # existing
  routes:
    # NEW v2: dedicated route for registrar drift, REUSING existing receiver
    - match:
        alert_class: registrar_drift
      receiver: telegram-fabrik-default   # SAME receiver — just different template
      group_by: [registrar, service]
      group_wait: 30s
      group_interval: 5m
      repeat_interval: 12h
      continue: false
```

If the existing receiver's `message:` template needs adjustment for drift events, add a conditional clause inside the existing template instead of creating a parallel receiver:

```yaml
# In the existing telegram_configs[].message:
message: |
  {{ if eq .CommonLabels.alert_class "registrar_drift" }}
  🚨 Fabrik registrar drift: {{ .Labels.registrar }}
  Service: {{ .Labels.service }}
  Detail: {{ .Annotations.detail }}
  {{ else }}
  ... existing templates ...
  {{ end }}
```

### Trigger

Simpler approach: one combined `fabrik-audit-all-registrars.timer` runs `fabrik audit-registrars --json`, parses output, pushes a `fabrik_registrar_drift{registrar="X",service="Y"}` metric to Prometheus pushgateway → existing alert rule fires → matches the new route → existing Telegram receiver delivers.

### Acceptance criteria

- Drift in any of 8 registrars → Telegram alert within 1 hour.
- Alert includes which registrar, which service, what the drift is.
- **No new Alertmanager receiver added** — reuses existing telegram-fabrik-default receiver via new route.
- Manual repair confirmed: fix → next audit cycle clears the alert.

---

## Tier 4 done — convergence test

After all 4 items:

```bash
# 1. Export bundle
fabrik export --output /tmp/vps1-base.tar.gz
tar -tzf /tmp/vps1-base.tar.gz | head        # contents listed
ls -lh /tmp/vps1-base.tar.gz                 # size sane

# 2. Postgres registry
ssh vps 'cat /opt/monitoring/configs/postgres/allocations.json | python3 -m json.tool'
# Expect: 4-5 entries (all current DBs)

# 3. Destroy with state — data-bearing protection works
fabrik apply specs/services/test-tier4-demo.yaml --yes
ls .fabrik/state/test-tier4-demo.json        # exists
# Try without --drop-data when data-bearing resources exist:
fabrik destroy specs/services/test-tier4-demo.yaml --use-state --yes
# Expect: blocks if data_bearing entries present
fabrik destroy specs/services/test-tier4-demo.yaml --use-state --drop-data --yes
ls .fabrik/state/_destroyed/test-tier4-demo.json.* # archived

# 4. Drift alerting — reuses existing receiver
ssh vps "sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -c 'CREATE DATABASE drift_test;'"
ssh vps 'sudo systemctl start fabrik-audit-all-registrars.service'
# Within ~1 minute: Telegram alert via EXISTING telegram-fabrik-default receiver
ssh vps "sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -c 'DROP DATABASE drift_test;'"
# Confirm no parallel receivers were added:
ssh vps 'sudo grep -c "telegram-fabrik-drift" /opt/monitoring/configs/alertmanager/alertmanager.yml'
# Expect: 0 (the v1 mistake, NOT applied)
```

If all 4 pass, vps1 is ready to be the base image for vps2/vps3.

---

## Trade-offs and deferral notes

These items are explicitly marked Tier 4 because:

- **G-J2 (`export/import`)** — only matters when you're spinning up a second VPS. If the current VPS stays the only one for 6+ months, this is wasted effort. Even when you do pull the trigger, plan for ~0.5 day of manual secrets re-population on the target unless you've also added a secrets manager.

- **G-F4 (`destroy --use-state`)** — only bites if you regularly edit specs between apply and destroy. For greenfield projects, the spec is usually stable from first apply through eventual destroy. Risk window is small. The data-bearing protection added in v2 means even if you DO trigger this, postgres/meilisearch data is shielded behind `--drop-data`.

- **G-G5 (drift alerting)** — Tier 2 G-G2 (`fabrik audit-registrars`) gives you on-demand drift visibility. The alert layer is "make it automatic"; if you run audit weekly by habit, the alert layer is overkill.

- **G-J4 (postgres allocation registry)** — at 4-5 DBs, `pg_database` is fine as the de facto registry. At 50+ DBs (the long-term goal), the JSON registry pays off.

In other words: Tier 4 is for when scale or team size makes manual operational discipline insufficient. Solo operator with single VPS — Tier 1+2+3 is enough.
