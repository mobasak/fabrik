# 99 — Evidence Appendix (v3.2)

**Purpose:** every claim in this pack is independently verifiable. Each subsection below pairs a gap ID with the exact command(s) used during the audit. Run any of them to spot-check.

**v2 changes:**
- B11 corrected: status() function at line 549, NOT 1130
- C1 addressed: added the full-sweep script that proves "5 deployed pre-G1 specs" is exhaustive (not a sampling)
- Counts corrected throughout: 12 templates, 22 rule files, 7 governance files, 42 projects, 65 spec files
- Cascade evidence updated: G-H3 (prom) does NOT cascade-fix; only G-H1 + G-H4 + G-H5

**Conventions:**
- Commands prefixed `$` are for the WSL-side `/opt/fabrik` repo
- Commands prefixed `vps$` are run via `ssh vps '...'` against the VPS
- `PYTHONPATH=src` is required for any Python that imports `fabrik.*` from the repo

---

## Phase A — Preplan

### G-A1, G-A2, G-A3, G-A4, G-A5

```bash
# G-A1: no preplan template
$ find /opt/fabrik -name "*preplan*" -not -path "*/.git/*" -not -path "*/.venv/*" -not -path "*/docs/development/plans/*"
# Expected: 0 hits (only the new docs we'd create in Tier 3)

# G-A2: no preplan location
$ ls /opt/fabrik/docs/preplans /opt/fabrik/preplans /opt/fabrik/.fabrik/preplans 2>&1
# Expected: 'No such file or directory' for all three

# G-A3: no preplan CLI command
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli --help | grep -i preplan
# Expected: empty

# G-A4: scaffold doesn't accept --from-preplan
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli scaffold --help | grep -i preplan
# Expected: empty

# G-A5: workflow doc has no preplan handoff section
$ grep -n "preplan\|pre.plan" /opt/fabrik/docs/traycer/fabrik-workflow.md
# Expected: 0 hits
```

---

## Phase B — Scaffold

### G-B1a — load_spec doesn't merge template defaults

```bash
$ sed -n '425,460p' /opt/fabrik/src/fabrik/spec_loader.py
# Expected: function at line 425, return Spec(**raw) at line 457; no template merge

$ cd /opt/fabrik && PYTHONPATH=src python3 -c "
from fabrik.spec_loader import load_spec
s = load_spec('specs/services/captcha.yaml')
print('shape attr:', getattr(s, 'shape', None))
"
# Expected: 'shape attr: None' (proves no merge)
```

### G-B1b — Templates don't set exposes_metrics or needs_cache

```bash
$ for t in python-api node-api; do
    echo "--- templates/$t/defaults.yaml ---"
    grep -E "exposes_metrics|needs_cache" /opt/fabrik/templates/$t/defaults.yaml || echo "(neither set)"
done
# Expected: "(neither set)" for both

# Resolved applicability for shape-less spec post-G-B1a merge:
$ cd /opt/fabrik && PYTHONPATH=src python3 << 'PY'
import yaml, sys; sys.path.insert(0, 'src')
from fabrik.orchestrator.infrastructure import resolve_applicability
with open('templates/python-api/defaults.yaml') as f:
    defaults = yaml.safe_load(f)
spec = dict(defaults); spec['id']='captcha'; spec['template']='python-api'; spec['domain']='captcha.vps1.ocoron.com'
for k, (runs, reason) in resolve_applicability(spec).items():
    print(f"{'RUNS' if runs else 'skip'} {k:12} — {reason}")
PY
# Expected: only gatus + glitchtip + grafana RUNS; prometheus + redis SKIP
```

### G-B3 — fabrik-file-worker has no production spec

```bash
$ grep -rln "id:.*fabrik-file-worker\|^id: file-worker" /opt/fabrik/specs/services/
# Expected: only test-file-worker.yaml and fabrik-test-file-worker.yaml (test fixtures)

$ ssh vps 'sudo docker exec coolify-db psql -U coolify coolify -At -c "SELECT name FROM applications WHERE name = '"'"'fabrik-file-worker'"'"';"'
# Expected: 'fabrik-file-worker' (proves it's deployed without a spec)
```

### G-B5 — scaffold does NOT copy CLAUDE.md

```bash
$ grep -nE "shutil\.copy.*CLAUDE\.md|copy.*claude" /opt/fabrik/src/fabrik/scaffold.py
# Expected: empty (CLAUDE.md NOT in scaffold copy list)

$ grep -n "shutil.copy" /opt/fabrik/src/fabrik/scaffold.py | head
# Expected: lines 650 (windsurfrules), 666 (AGENTS.md), 671 (AGENTS-compact.md), 3440 (windsurfrules in second path)
# NO CLAUDE.md line
```

### G-B6 — next-tailwind orphan

```bash
$ ls -d /opt/fabrik/templates/next-tailwind/  # exists
$ grep -c "^shape:" /opt/fabrik/templates/next-tailwind/defaults.yaml  # = 1 (has shape)
$ grep -c "next-tailwind" /opt/fabrik/AGENTS.md  # = 0 (orphan from Scaffold Types table)
```

---

## Phase C — Traycer

### G-C1 — fabrik-workflow.md has zero deploy references

```bash
$ grep -cE "fabrik apply|fabrik deploy|fabrik destroy|fabrik redeploy|registrar" \
    /opt/fabrik/docs/traycer/fabrik-workflow.md
# Expected: 0
```

### G-C2 — no registrar-audit workflow

```bash
$ ls /opt/fabrik/.windsurf/workflows/registrar-audit.md 2>&1
# Expected: 'No such file or directory'

$ ls /opt/fabrik/.windsurf/workflows/ | wc -l
# Expected: 10 (bug-fix, deploy, kilo, kilo-review, local-coder, local-docs,
#               local-fixer, local-review, new-feature, review)
```

---

## Phase D — Coding rule files

### G-D1 — 5 executor rule files have zero shape/registrar awareness (CORRECTED v2)

```bash
$ for f in /opt/fabrik/AGENTS.md /opt/fabrik/AGENTS-compact.md \
           /opt/fabrik/CLAUDE.md /opt/fabrik/.windsurfrules \
           /opt/fabrik/AFCL.md /opt/fabrik/opencode.json; do
    echo "$f: $(grep -cE 'shape|registrar|fabrik apply|InfrastructureProvisioner' "$f" 2>/dev/null || echo 0)"
done
# Expected:
#   AGENTS.md: 6-7
#   AGENTS-compact.md: 0
#   CLAUDE.md: 0
#   .windsurfrules: 0
#   AFCL.md: 0
#   opencode.json: 0
```

### G-D2 — 21 .windsurf/rules/ files (CORRECTED v3, post-CCR-dissolution 2026-05-14)

```bash
$ ls /opt/fabrik/.windsurf/rules/ | wc -l
# Expected: 21 (20 numbered + ocoron-design-system.md).
# CROSS_CUTTING_REQUIREMENTS.md was dissolved on 2026-05-14; its content was redistributed
# to topic packs (30-ops, 35-security-auth, 50-code-review, 55-observability) and the
# three bootstrap files (CLAUDE.md, .windsurfrules, AGENTS-compact.md).

$ grep -lE "shape|registrar|InfrastructureProvisioner" /opt/fabrik/.windsurf/rules/*.md
# Expected: empty (no files match — all 21 lack shape/registrar awareness)
```

### G-D4 — AGENTS.md registrar list drift (NEW v2)

```bash
# Code's authoritative 9-tuple:
$ grep -A 12 "_REGISTRAR_ORDER = (" /opt/fabrik/src/fabrik/orchestrator/infrastructure.py | head -13
# Expected: 9 entries — postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus

# AGENTS.md drift:
$ grep -n "postgres / gatus" /opt/fabrik/AGENTS.md
# Expected: 2 hits (line 459 + 479) — both list 7 registrars, missing redis + prometheus
```

---

## Phase E — Commit

### G-E1 — pre-commit doesn't run fabrik plan for specs

```bash
$ grep -E "fabrik plan|fabrik validate" /opt/fabrik/.pre-commit-config.yaml
# Expected: empty
```

### G-E2 — final_gate.py only does YAML-loadability

```bash
$ grep -nE "yaml.safe_load|load_spec|Spec\(" /opt/fabrik/scripts/final_gate.py | head
# Expected: line 471 has yaml.safe_load(); no load_spec or Spec(...) imports
```

---

## Phase F — Deploy

### G-F1 — fabrik plan doesn't surface registrars

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli plan specs/services/proxy.yaml
# Expected output: lists Generate files, Create DNS, Deploy to Coolify, Add Gatus monitor.
# Does NOT include "Resolved registrars: ..." block.

$ grep -nE "resolve_applicability|format_resolved_summary" /opt/fabrik/src/fabrik/cli.py | head
# Expected: only references in redeploy() function (~line 877), NOT in plan() (line 197)
```

### G-F2 — no reconcile-all command

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli --help | grep -iE "reconcile"
# Expected: empty
```

### G-F3 — no .fabrik/state/ directory

```bash
$ ls /opt/fabrik/.fabrik/state/ 2>&1
# Expected: 'No such file or directory'

$ grep -nE "add_resource|state_file|persist|save_state" \
    /opt/fabrik/src/fabrik/orchestrator/__init__.py | head -10
# Expected: only ctx.add_resource() calls; no persist/save_state functions
```

### G-F4 — destroy is shape-driven, intentional

```bash
$ sed -n '15,30p' /opt/fabrik/src/fabrik/orchestrator/destroyer.py
# Expected: docstring at line 23 says "Derived from the spec, not from live state"

$ grep -n "resolve_applicability" /opt/fabrik/src/fabrik/orchestrator/destroyer.py
# Expected: line 433 calls resolve_applicability(spec_dict)
```

### G-F5 — no fabrik destroy --partial (NEW v2)

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli destroy --help | grep -i partial
# Expected: empty
```

### Rollback policy — postgres + meilisearch are destructive-no-op-by-design

```bash
$ grep -B 1 -A 4 "def _rollback_postgres\|def _rollback_meilisearch" /opt/fabrik/src/fabrik/orchestrator/rollback.py | head -20
# Expected: both have docstring "Destructive-no-op by design"
# This is why G-F3 schema needs data_bearing flag (Tier 2 §13)
```

---

## Phase G — Verify / audit

### G-G1 — fabrik status broken for site-provisioner (LINE CORRECTED v2)

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli status specs/services/site-provisioner.yaml
# Expected output snippet:
#   🐳 Coolify status:
#      ✅ Found in Coolify: None

# Confirm app IS deployed:
$ ssh vps 'sudo docker exec coolify-db psql -U coolify coolify -At -c "SELECT name FROM applications WHERE name='"'"'site-provisioner'"'"';"'
# Expected: 'site-provisioner'

# Confirm function location (corrected from v1's "line 1130" to actual 549):
$ grep -n "def status(" /opt/fabrik/src/fabrik/cli.py
# Expected: line 549

# Confirm offending lookup at line 581:
$ sed -n '578,585p' /opt/fabrik/src/fabrik/cli.py | head
# Expected: matching = [a for a in apps if a.get("name") == spec.id]  (single-variant)
```

### G-G2 — no fabrik audit-registrars

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli --help | grep -iE "audit"
# Expected: empty
```

### G-G3 — no registrars verifier spec

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli verify --help | grep -A 2 "spec"
# Expected: 'Verification spec to use (deploy, dns)' — only those two
```

### G-G4 — audit_authelia_gates.py not scheduled

```bash
$ ssh vps 'sudo systemctl list-timers --all | grep -iE "fabrik|authelia|audit"'
# Expected: empty (no fabrik audit timer)

$ head -20 /opt/fabrik/scripts/audit_authelia_gates.py | grep cron
# Expected: docstring mentions "weekly cron" (intent only, not configured)
```

---

## Phase H — Live VPS state

### G-H1 — 5 deployed specs lack shape (proven exhaustive via full sweep — addresses C1)

The v1 pack named 5 specs without proving the count. The v2 full-sweep script confirms it's exhaustive against all 65 spec files:

```bash
# C1 full sweep — addresses Traycer's exhaustiveness concern
$ cd /opt/fabrik && bash << 'EOF'
DEPLOYED=$(ssh vps 'sudo docker exec coolify-db psql -U coolify coolify -At -c "SELECT name FROM applications;" 2>/dev/null')

echo "Total spec files: $(ls specs/services/*.yaml | wc -l)"
echo ""
echo "DEPLOYED but NO SHAPE block:"
for f in specs/services/*.yaml; do
    sid=$(grep -m1 "^id:" "$f" | sed 's/id: //; s/[ \r]//g')
    has_shape=$(grep -c "^shape:" "$f")
    deployed=""
    for cand in "$sid" "fabrik-$sid"; do
        if echo "$DEPLOYED" | grep -qFx "$cand"; then deployed="$cand"; break; fi
    done
    if [ -n "$deployed" ] && [ "$has_shape" -eq 0 ]; then
        echo "  $(basename $f) — id=$sid, deployed as $deployed"
    fi
done
EOF
# Expected output:
#   Total spec files: 65
#   DEPLOYED but NO SHAPE block:
#     captcha.yaml — id=captcha, deployed as fabrik-captcha
#     emailgateway.yaml — id=emailgateway, deployed as fabrik-emailgateway
#     file-api.yaml — id=file-api, deployed as fabrik-file-api
#     image-broker.yaml — id=image-broker, deployed as fabrik-image-broker
#     translator.yaml — id=translator, deployed as fabrik-translator
# Exactly 5 of 65 — exhaustiveness proven.
```

### G-H2 — Redis assignments.json missing

```bash
$ ssh vps 'sudo cat /opt/monitoring/configs/redis/assignments.json' 2>&1
# Expected: 'No such file or directory'

$ ssh vps 'sudo docker exec redis-main redis-cli INFO keyspace 2>/dev/null | grep "^db"'
# Expected: db3:keys=39, db4:keys=14
```

### G-H3 — Zero per-service Prometheus jobs (does NOT cascade-fix from G-B1a)

```bash
$ ssh vps 'sudo grep "^- job_name:" /opt/monitoring/configs/prometheus/prometheus.yml'
# Expected: 13 lines, all infra-level. Zero match deployed Fabrik service ids.

# Why G-B1a alone doesn't fix this — templates lack exposes_metrics:
$ grep -E "exposes_metrics" /opt/fabrik/templates/python-api/defaults.yaml
# Expected: empty (G-B1b decision required to add this default)
```

### G-H4 — Zero per-service Gatus endpoints (cascade-fixed by G-B1a partially)

```bash
$ ssh vps 'sudo find /opt/monitoring/configs/gatus -name "*.yaml" -not -name "*.predrift*" -exec grep -hE "^  - name: " {} \; | sort -u'
# Expected: 21 endpoints, all infra-level. Zero match deployed Fabrik service ids.
# Cascade: 4 of 5 specs have is_public=true (templates default) + domain set → Gatus runs after G-B1a
```

### G-H5 — file-api missing Backrest plan (cascade-fixed by G-B1a)

```bash
$ ssh vps 'sudo cat /opt/backrest/config/config.json' | python3 -c "
import json, sys
d = json.load(sys.stdin)
plans = [p['id'] for p in d.get('plans', [])]
print('plans:', plans)
print('file-api-data present:', 'file-api-data' in plans)
"
# Expected: ['docker-volumes', 'opt-configs', 'postgres-dumps', 'fabrik-e2e-test-data']
# 'file-api-data present: False'
# Cascade: file-api template defaults set has_persistent_data: true → Backrest runs after G-B1a
```

### G-H6 — image-broker no Authelia rule (DECIDED: ADD rule)

```bash
$ ssh vps 'sudo grep -c "image-broker" /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml'
# Expected: 0
```

### G-H7 — fabrik-proxy authelia drift (DECIDED: update spec to match live)

```bash
$ ssh vps 'sudo grep -A 3 "proxy.vps1" /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml'
# Expected: matched rule (live state)

$ grep -A 5 "^shape:" /opt/fabrik/specs/services/proxy.yaml
# Expected: 'is_admin_dashboard: false' at line 16 (spec disagrees with live state)
```

### G-H8 — translator postgres DB drift (DECIDED: rename live DB)

```bash
$ ssh vps 'sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -At -c "SELECT datname FROM pg_database WHERE datname LIKE '"'"'%translator%'"'"';"'
# Expected: 'translator_service'

# Post-G-B1a, what would orchestrator do? Verify resolve_applicability:
$ cd /opt/fabrik && PYTHONPATH=src python3 << 'PY'
import yaml, sys; sys.path.insert(0, 'src')
from fabrik.orchestrator.infrastructure import resolve_applicability
with open('templates/python-api/defaults.yaml') as f:
    d = yaml.safe_load(f)
with open('specs/services/translator.yaml') as f:
    s = yaml.safe_load(f)
def merge(b, o):
    out = dict(b)
    for k, v in (o or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = v
    return out
m = merge(d, s)
res = resolve_applicability(m)
print("postgres:", res['postgres'])
PY
# Expected: postgres: (False, 'not applicable: shape.needs_database=false')
# This is why v1 Option B was a no-op — postgres registrar is already gated off.
```

### G-H9 — fabrik-file-worker deployed without spec

Same evidence as G-B3 above.

---

## Phase I — Local dev

### G-I1, G-I2

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli --help | grep -iE "^  dev|local"
# Expected: empty (no fabrik dev, no fabrik logs --local)

$ grep -n "compose.dev" /opt/fabrik/src/fabrik/scaffold.py | head -3
# Expected: 3 references — proves compose.dev.yaml is created, just no CLI to start it
```

---

## Phase J — Operational

### G-J1 — projects.yaml lacks deploy fields (42 projects total)

```bash
$ head -3 /opt/fabrik/data/projects.yaml
# Expected: version: 2, total_projects: 42

$ grep -E "coolify_uuid|spec_path|last_apply" /opt/fabrik/data/projects.yaml | head -5
# Expected: empty
```

### G-J2 — no fabrik export/import

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 -m fabrik.cli --help | grep -iE "^  export|^  import"
# Expected: empty
```

### G-J3 — coolify-alias-watcher hardcoded

```bash
$ ssh vps 'sudo cat /opt/coolify-alias-watcher/watcher.sh' | grep -A 6 "declare -A ALIASES"
# Expected: 4 hardcoded entries (meilisearch, gotenberg, browserless, glitchtip-web)
```

### G-J4 — no postgres allocation registry

```bash
$ ssh vps 'sudo cat /opt/monitoring/configs/postgres/allocations.json' 2>&1
# Expected: 'No such file or directory'
```

### G-J5 — Cloudflare token (manual UI check; site-provisioner needs Zone:Edit not Read)

```bash
$ grep "CLOUDFLARE_API_TOKEN" /opt/fabrik/.env | sed 's/=.*/=***MASKED***/'
# Expected: token starts with 'cfut_nNprCT'

# Why narrowing to Zone:Read is wrong — site-provisioner exposes zone create:
$ grep -E "POST.*zones.*provision" /opt/site-provisioner/README.md | head -3
# Expected: POST /api/cloudflare/zones/{domain}/provision documented
# This needs Zone:Edit (create), not just Zone:Read
```

### G-J6 — predrift-fix files leftover

```bash
$ ssh vps 'sudo find /opt/monitoring/configs/gatus -name "*.predrift-fix.20260506" 2>/dev/null'
# Expected: 2 files
```

---

## Cross-cutting verification scripts

### Verify line numbers (Step 0 sanity check before Tier 1)

```bash
$ cd /opt/fabrik && {
    echo "load_spec at:    $(grep -n '^def load_spec' src/fabrik/spec_loader.py)"
    echo "return Spec at:  $(grep -n 'return Spec(' src/fabrik/spec_loader.py | head -1)"
    echo "status() at:     $(grep -n 'def status(' src/fabrik/cli.py | head -1)"
    echo "yaml.safe_load:  $(grep -n 'yaml.safe_load' scripts/final_gate.py | head -1)"
    echo "destroyer doc:   $(sed -n 23p src/fabrik/orchestrator/destroyer.py)"
    echo ""
    echo "_REGISTRAR_ORDER:"
    grep -A 12 '_REGISTRAR_ORDER = (' src/fabrik/orchestrator/infrastructure.py | head -13
}
# Expected against 2026-05-09 snapshot:
#   load_spec at:    425:def load_spec(spec_path: str | Path) -> Spec:
#   return Spec at:  457:    return Spec(**raw)
#   status() at:     549:def status(spec_path: str):
#   yaml.safe_load:  471: ...yaml.safe_load(...)
#   destroyer doc:   docstring mentioning "Derived from the spec, not from live state"
#   9-tuple postgres redis gatus backrest glitchtip grafana authelia meilisearch prometheus
```

### Per-deployed-service registrar reality check

```bash
$ cd /opt/fabrik && PYTHONPATH=src python3 << 'EOF'
import yaml, sys, subprocess
sys.path.insert(0, 'src')
from fabrik.orchestrator.infrastructure import resolve_applicability
from pathlib import Path

def ssh_run(cmd):
    return subprocess.run(['ssh', 'vps', cmd], capture_output=True, text=True, timeout=30).stdout.strip()

PG = set(ssh_run("sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -At -c \"SELECT datname FROM pg_database WHERE datname NOT IN ('template0','template1');\"").splitlines())
GATUS = set()
for line in ssh_run("sudo find /opt/monitoring/configs/gatus -name '*.yaml' -not -name '*.predrift*' -exec grep -hE '^  - name:' {} \\;").splitlines():
    GATUS.add(line.replace('  - name:', '').strip().strip('"').strip("'"))
PROM_RAW = ssh_run("sudo cat /opt/monitoring/configs/prometheus/prometheus.yml")
PROM_JOBS = {l.split('job_name:', 1)[1].strip() for l in PROM_RAW.splitlines() if 'job_name:' in l}
COOLIFY = set(ssh_run('sudo docker exec coolify-db psql -U coolify coolify -At -c "SELECT name FROM applications;"').splitlines())

for f in sorted(Path('specs/services').glob('*.yaml')):
    with open(f) as fh:
        try: spec = yaml.safe_load(fh)
        except: continue
    if not isinstance(spec, dict): continue
    sid = spec.get('id', '?')
    deployed = sid in COOLIFY or f"fabrik-{sid}" in COOLIFY
    if not deployed: continue
    has_shape = 'shape' in spec
    print(f"\n>>> {sid} (has_shape={has_shape})")
    if has_shape:
        runs = [k for k, v in resolve_applicability(spec).items() if v[0]]
        print(f"    SHOULD run: {runs}")
    db_name = sid.replace('-', '_')
    print(f"    pg DB '{db_name}': {'✓' if db_name in PG else '✗'}")
    print(f"    gatus '{sid}': {'✓' if sid in GATUS else '✗'}")
    prom_job = f"fabrik-{sid}"
    print(f"    prom '{prom_job}': {'✓' if prom_job in PROM_JOBS else '✗'}")
EOF
```

---

## Source-of-truth file paths

| Topic | Path |
|---|---|
| Orchestrator pipeline | `src/fabrik/orchestrator/__init__.py` (DeploymentOrchestrator) |
| Registrar dispatch | `src/fabrik/orchestrator/infrastructure.py` |
| Applicability resolver | `src/fabrik/orchestrator/infrastructure.py` (`resolve_applicability`) |
| Per-registrar provision methods | `src/fabrik/orchestrator/infrastructure.py:318-342` (9 dispatch lines) |
| Registrar order tuple | `src/fabrik/orchestrator/infrastructure.py:86-94` (canonical 9 list) |
| Destroy logic | `src/fabrik/orchestrator/destroyer.py` (resolve_applicability at line 433) |
| Rollback handlers | `src/fabrik/orchestrator/rollback.py` (postgres + meilisearch destructive-no-op) |
| Driver implementations | `src/fabrik/drivers/{postgres,redis,gatus,backrest,glitchtip,grafana,authelia,meilisearch,prometheus}.py` |
| Driver locks (for G-F2/G-F3 concurrency) | `src/fabrik/drivers/locks.py` |
| Spec loader | `src/fabrik/spec_loader.py:425` (`load_spec`); return Spec at line 457 |
| CLI entry | `src/fabrik/cli.py` |
| Status command | `src/fabrik/cli.py:549` (NOT 1130) |
| Plan command | `src/fabrik/cli.py:197` |
| Redeploy --refresh-infra | `src/fabrik/cli.py:850-889` |
| Spec generator | `src/fabrik/spec_generator.py:507` |
| Scaffold | `src/fabrik/scaffold.py` (copies at lines 650, 666, 671) |
| Template defaults | `templates/<type>/defaults.yaml` (12 templates total, all with shape) |
| Pre-commit config | `.pre-commit-config.yaml` |
| Final gate | `scripts/final_gate.py:471` (yaml-load only) |
| Authelia drift script | `scripts/audit_authelia_gates.py` |
| Governance file list | `scripts/sync_enforcement_to_projects.py` (`GOVERNANCE_FILES` = 7 items) |
| Project registry | `data/projects.yaml` (total_projects: 42) |
| Port registry | `data/ports.yaml` |
| Spec files | `specs/services/*.yaml` (65 total; 35 with shape blocks; only 2 of those are DEPLOYED + non-test: proxy + site-provisioner) |
| Live Coolify state | `vps1.ocoron.com:coolify-db` (Postgres) |
| Live registrar configs | `vps1.ocoron.com:/opt/monitoring/configs/{prometheus,gatus,redis,postgres}/` |
| Authelia rules | `vps1.ocoron.com:/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml` |
| Backrest config | `vps1.ocoron.com:/opt/backrest/config/config.json` |
| Alertmanager config | `vps1.ocoron.com:/opt/monitoring/configs/alertmanager/alertmanager.yml` |

If anything in this pack stops being true, run the relevant script above and update the truth table accordingly.
