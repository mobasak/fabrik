# 02 — Tier 1: Foundation Fixes (v3.2)

**Total effort:** ~16 h (covers all 13 Tier 1 items: G-B1a/B1b/B5/B6/D4/G1/F1/J6 + G-H2 redis seed + G-H6/H7 Authelia + G-H8 destructive translator migration + W-3 monitoring window). Was 90 min in v1; expanded as scope grew through v2/v3/v3.1/v3.2 audits.
**Risk:** very low — small file edits + decisions, no live-VPS impact unless `fabrik apply` is run
**Goal:** unlock the cascade so `fabrik redeploy --refresh-infra` can fill in missing registrar state

## v2 changes

- §1 split into **§1a (G-B1a — load_spec merge, code-only)** + **§1b (G-B1b — template default flags, DECIDED 2026-05-09: apply Path B to python-api + node-api)**
- §3 G-G1 fix logic corrected (avoids `fabrik-fabrik-proxy` double-prefix)
- §6 G-H8 Option B rewritten (was a no-op; now uses proxy.yaml pattern correctly)
- §8 G-J5 CF token scope corrected (Zone.Zone:Edit, not Read)
- New §10 (G-D4 — AGENTS.md registrar drift)
- New §11 (G-B5 — scaffold copies CLAUDE.md)
- New §12 (G-B6 — next-tailwind AGENTS.md orphan)
- New §0 (re-verify snapshot before starting — addresses C10)
- All line citations corrected (status() at line 549, NOT 1130; final_gate yaml-load at 471; spec_loader load_spec at 425, return at 457)

## Why Tier 1 first

Of the 47 total gaps, **G-B1a alone** cascade-fixes G-H1, G-H4 (partial), G-H5. Combined with G-H2 (seed redis registry) and the three previously-flagged decisions (G-H6/H7/H8 — all DECIDED 2026-05-09 per 00-README §DECISIONS LOCKED IN), this tier converts the deployed-but-unwired services into deployable-via-fabrik services without editing any of the 5 shape-less specs. **G-B1b** (template default flags) is needed additionally to cascade-fix G-H3 (per-service Prometheus jobs).

## Order of operations

§0 is mandatory before anything else. §1a, §3, §4, §7, §10, §11, §13 are independent code/config edits — parallel-safe. §1b, §2, §5, §6, §8, §9, §12 need decisions resolved or are VPS-side.

---

## 0. Re-verify snapshot (REQUIRED before starting)

**Effort:** 5 minutes
**Why:** This pack was authored 2026-05-09. If more than ~7 days have passed, code line numbers and VPS state can shift. Run the cross-cutting verification scripts from `99-evidence-appendix.md` to confirm.

```bash
# Quick sanity: are the key line numbers still right?
cd /opt/fabrik
grep -n "^def load_spec\|return Spec(" src/fabrik/spec_loader.py | head -3
# Expected: 'def load_spec' at 425, 'return Spec(**raw)' at 457

grep -n "def status(" src/fabrik/cli.py
# Expected: line 549

grep -n "yaml.safe_load" scripts/final_gate.py | head -3
# Expected: line 471

# Are the registrar drivers all still 9?
grep -A 12 "_REGISTRAR_ORDER = (" src/fabrik/orchestrator/infrastructure.py | head -13
# Expected: 9-tuple in order: postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus
```

If any line number drifts, update the affected section in this doc before applying the fix.

---

## 1a. G-B1a — `load_spec()` auto-merges template defaults

**Effort:** 30 min, 1 file
**Risk:** medium — touches the deserialization path used by every Fabrik command
**File:** `src/fabrik/spec_loader.py`
**Function:** `load_spec()` at line 425; `return Spec(**raw)` at line 457

### Current behavior

```python
def load_spec(spec_path: str | Path) -> Spec:    # line 425
    path = Path(spec_path)
    # ... existence/format checks ...
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    # ... emptiness/type checks ...
    return Spec(**raw)                            # line 457
```

### Required change

Between loading `raw` and constructing `Spec(**raw)`, look up `templates/<raw['template']>/defaults.yaml`. If it exists, deep-merge it **under** the spec (so the spec wins on conflicts; missing fields fall through to the template default).

### Pseudocode

```python
from fabrik.config import FABRIK_ROOT

def load_spec(spec_path: str | Path) -> Spec:
    path = Path(spec_path)
    # ... existing checks ...
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    # ... existing checks ...

    # NEW: merge template defaults under the spec
    if isinstance(raw, dict):
        template_name = raw.get("template")
        if template_name:
            defaults_path = FABRIK_ROOT / "templates" / template_name / "defaults.yaml"
            if defaults_path.exists():
                with open(defaults_path, encoding="utf-8") as f:
                    defaults = yaml.safe_load(f) or {}
                if isinstance(defaults, dict):
                    raw = _deep_merge(defaults, raw)  # spec wins on conflicts

    return Spec(**raw)


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Overlay wins on conflicts; nested dicts merge recursively."""
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
```

### Acceptance criteria (5 explicit edge-case tests required — addresses C13)

Add `tests/test_spec_loader.py::test_load_spec_merges_template_defaults` covering:

1. **Happy path:** `load_spec("specs/services/captcha.yaml")` returns Spec with `shape.is_public=True`, `shape.kind="service"` (inherited from `templates/python-api/defaults.yaml`).
2. **Spec wins on conflict:** A spec with explicit `shape.kind: "worker"` keeps that value, NOT the template default.
3. **Nested dict merge:** Spec with `shape: { has_persistent_data: true }` only merges that one flag in; other shape fields come from the template.
4. **Proxy-pattern override survives merge:** Spec carrying the `proxy.yaml` pattern (`infra.postgres: false` AND `shape.needs_database: true` set explicitly in the spec) merged against `templates/python-api/defaults.yaml` (which sets `shape.needs_database: true` but does NOT set `infra.postgres`). The merged result MUST keep both the spec's `infra.postgres: false` (no template clobbers it) AND the spec's `shape.needs_database: true` (template agrees). Then verify downstream `resolve_applicability(merged)` returns `(False, "infra.postgres=false")` for the postgres registrar — i.e. the proxy override pattern continues to gate postgres OFF after the new merge step is in place.
5. **Missing template tolerance:** Spec with `template: "nonexistent-template"` — `load_spec` should NOT crash; it should silently fall through (caller may emit a warning if desired).
6. **Empty/None overlay:** `_deep_merge(defaults, {})` returns defaults unchanged. `_deep_merge(defaults, None)` is rejected before merge.
7. **Existing tests stay green:** `tests/orchestrator/test_template_defaults.py`, `tests/test_infrastructure.py`, `tests/orchestrator/test_infrastructure.py` all still pass.

### Manual verify

```bash
cd /opt/fabrik && PYTHONPATH=src python3 -c "
from fabrik.spec_loader import load_spec
for n in ['captcha', 'emailgateway', 'file-api', 'image-broker', 'translator', 'proxy', 'site-provisioner']:
    s = load_spec(f'specs/services/{n}.yaml')
    print(f'{n:18} shape={getattr(s, \"shape\", None) is not None}')
"
# Expected: all 7 lines 'shape=True'
```

### Cascading effect

After this single change, running `fabrik redeploy --refresh-infra --spec specs/services/<name>.yaml` for each of the 5 deployed pre-G1 services (captcha, emailgateway, file-api, image-broker, translator) auto-creates:

- ✅ Their missing **Gatus endpoints** (G-H4 partial cascade)
- ✅ **Backrest plan** for file-api (G-H5 cascade — file-api template defaults set `has_persistent_data: true`)
- ✅ Refreshed **GlitchTip DSN** if missing
- ❌ **Prometheus scrape jobs** do NOT cascade-fix — see §1b below

---

## 1b. G-B1b — Add `exposes_metrics: true` to template defaults (DECIDED 2026-05-09: APPLY PATH B, scoped to python-api + node-api)

**Effort:** 5 min, 2-3 files (after decision)
**Risk:** changes deploy footprint of EVERY new and existing scaffold
**Files:** `templates/python-api/defaults.yaml`, `templates/node-api/defaults.yaml` (and possibly file-api, saas-skeleton)

### What this unlocks

If applied, post-G-B1a merge for shape-less specs will now resolve `prometheus` registrar to RUN, which auto-creates per-service Prometheus scrape jobs (closes G-H3).

### Decision required

Two paths:

**Path A — opt-in per spec (minimal change):**
Skip G-B1b. For services that should expose metrics, add to their spec:
```yaml
shape:
  exposes_metrics: true
```
Pros: explicit per-service, no surprise change to existing deploys.
Cons: G-H3 stays open for the 5 deployed pre-G1 services until each spec is edited.

**Path B — global default (cascade-fix):**
Edit `templates/python-api/defaults.yaml`:
```yaml
shape:
  kind: service
  is_public: true
  is_admin_dashboard: false
  has_bearer_api: false
  has_persistent_data: false
  needs_database: false
  has_search_feature: false
  exposes_metrics: true   # NEW
```
Same for `templates/node-api/defaults.yaml`. Pros: G-H3 cascade-fixes for all 5 deployed pre-G1 services + every future python/node API. Cons: every new scaffold gets a Prometheus scrape job by default; service code must actually expose `/metrics` or Prometheus will alert on scrape failure.

**Recommendation:** **Path B**, but **scoped to `python-api` and `node-api` templates only** — these auto-emit `metrics.py`/`metrics.ts` per Fabrik convention. Explicitly **excluded**: `saas-skeleton` (Next.js — does not auto-emit Prometheus metrics today) and `static-site` (no runtime, nothing to scrape). The change is exactly two lines: add `exposes_metrics: true` to `templates/python-api/defaults.yaml` and `templates/node-api/defaults.yaml`. Do NOT touch the other 10 template defaults. Use **Path A** only if some `python-api`/`node-api` service genuinely doesn't expose `/metrics` — handle that as a per-spec opt-out.

### Acceptance criteria (Path B)

After editing the template defaults:
```bash
PYTHONPATH=src python3 -c "
import yaml, sys; sys.path.insert(0, 'src')
from fabrik.spec_loader import load_spec
from fabrik.orchestrator.infrastructure import resolve_applicability
s = load_spec('specs/services/captcha.yaml')
res = resolve_applicability(s.model_dump() if hasattr(s, 'model_dump') else dict(s))
print('prometheus runs:', res.get('prometheus', (False,))[0])
"
# Expected: 'prometheus runs: True'
```

---

## 2. G-H2 — Seed Redis assignments.json

**Effort:** 5 minutes
**File on VPS:** `/opt/monitoring/configs/redis/assignments.json`

(unchanged from v1)

```bash
ssh vps 'sudo mkdir -p /opt/monitoring/configs/redis'
ssh vps 'sudo tee /opt/monitoring/configs/redis/assignments.json' <<'EOF'
{
  "version": 1,
  "last_updated": "2026-05-09T11:30:00+03:00",
  "assignments": {
    "authelia": 3,
    "glitchtip-web": 4
  },
  "free_indexes": [0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
}
EOF
ssh vps 'sudo chmod 644 /opt/monitoring/configs/redis/assignments.json'
```

### Acceptance

- File exists at `/opt/monitoring/configs/redis/assignments.json`.
- The next call to `acquire_db_index(<new-service>)` allocates db0 (not db3 or db4).

---

## 3. G-G1 — Fix `fabrik status` Coolify lookup (LOGIC CORRECTED v2)

**Effort:** 5 minutes
**File:** `src/fabrik/cli.py`
**Function:** `status()` at **line 549** (decorator at 547); offending lookup at **line 581**

### Symptom

```
$ PYTHONPATH=src python3 -m fabrik.cli status specs/services/site-provisioner.yaml
🐳 Coolify status:
   ✅ Found in Coolify: None
```

But the app IS deployed under that exact name.

### Root cause

`cli.py:581` does a single-variant lookup: `matching = [a for a in apps if a.get("name") == spec.id]`. Some apps stored as `<id>` (site-provisioner), others as `fabrik-<id>` (fabrik-captcha).

### v2-corrected fix

The v1 proposed `candidates = [spec.id, f"fabrik-{spec.id}"]` would query for `fabrik-fabrik-proxy` if a spec id is already prefixed (e.g. `proxy.yaml` has `id: fabrik-proxy`). Add a guard:

```python
# Replace the single matching = [...] line with:
candidates = [spec.id]
if not spec.id.startswith("fabrik-"):
    candidates.append(f"fabrik-{spec.id}")

matching = [a for a in apps if a.get("name") in candidates]
```

### Acceptance

- `fabrik status specs/services/site-provisioner.yaml` reports actual app status.
- `fabrik status specs/services/captcha.yaml` resolves to `fabrik-captcha`.
- `fabrik status specs/services/proxy.yaml` resolves to `fabrik-proxy` (NOT `fabrik-fabrik-proxy`).

---

## 4. G-F1 — `fabrik plan` prints resolved registrars

**Effort:** 10 minutes
**File:** `src/fabrik/cli.py:197` (`plan()` function)

(unchanged from v1)

After loading the spec, call `resolve_applicability(spec_dict)` and print the result:

```python
from fabrik.orchestrator.infrastructure import resolve_applicability, format_resolved_summary

# ... existing plan() body, after spec loaded ...

click.echo()
click.echo("🔧 Infrastructure Registrars (resolved from shape):")
spec_dict = spec.model_dump(mode="python") if hasattr(spec, "model_dump") else dict(spec)
for line in format_resolved_summary(resolve_applicability(spec_dict)).splitlines():
    click.echo(f"   {line}")
```

### Acceptance

- `fabrik plan specs/services/proxy.yaml` includes the resolved registrar matrix.

---

## 5. G-B3 — Create `fabrik-file-worker` production spec

**Effort:** 10 minutes
**File:** `specs/services/file-worker.yaml` (new)

(unchanged from v1)

```yaml
id: fabrik-file-worker
kind: worker
template: file-worker
domain: ""
# shape inherited from templates/file-worker/defaults.yaml after G-B1a:
#   kind: worker, has_persistent_data: true (others false)
source:
  type: git
  repository: git@github.com:mobasak/file-worker.git  # verify exact URL
  branch: main
coolify:
  project: fabrik-services
  server: localhost
env:
  LOG_LEVEL: INFO
  APP_ENV: production
secrets:
  from_env: []
resources:
  memory: 512M
  cpu: "0.5"
```

### Acceptance

- Resolved registrars after G-B1a: glitchtip + grafana + backrest (because `has_persistent_data: true`).
- `fabrik redeploy fabrik-file-worker --refresh-infra --spec specs/services/file-worker.yaml --dry-run` lists those 3 expected actions.

---

## 6. G-H8 — Translator postgres DB drift (DECIDED 2026-05-09: rename live DB to standard pattern)

**Effort:** ~45 min including ~5 min translator downtime
**Decision:** Standard rules win. translator is a python-api service that uses a database; spec MUST declare `shape.needs_database: true`; live DB MUST be named per the registrar's standard convention (`<id_with_underscores>` = `translator`).
**Risk:** destructive operation on live VPS data. Schedule outside business hours; take a Backrest snapshot of the postgres-main volume immediately before.

### Current state

| Side | DB name | Status |
|---|---|---|
| Live VPS (postgres-main) | `translator_service` | Active, used by deployed translator container |
| `templates/python-api/defaults.yaml` | n/a — `shape.needs_database: false` (default) | Means post-G-B1a, registrar SKIPS unless spec overrides |
| `specs/services/translator.yaml` | n/a — needs `shape.needs_database: true` set explicitly | Today: spec uses `infra.postgres: false` override (legacy escape hatch); after this fix: explicit shape opt-in |
| Target post-fix (live + spec aligned) | `translator` (registrar-standard) | Spec says yes; registrar would create/manage |

### Why this matters

Today's state has translator running in a "registrar-blind" hole: the live DB exists with a non-standard name, the spec uses `infra.postgres: false` to keep the registrar from touching it, and any new operator looking at the spec has no way to tell the service uses a database. After the fix, translator looks like every other DB-using service in the fleet; the registrar can manage its lifecycle on future redeploys.

### Migration plan (run 2026-05-09 or later, ~5 min translator downtime window)

**Pre-flight (do before the change window):**
```bash
# 1. Take a fresh Backrest snapshot of postgres-main volume so we can roll back
ssh vps 'curl -s -X POST http://localhost:9898/api/v1/backup -H "Content-Type: application/json" \
    -d "{\"plan\":\"postgres-dumps\"}"'
# 2. Confirm no other service references translator_service
ssh vps 'sudo docker exec coolify-db psql -U coolify coolify -At -c \
    "SELECT name, environment_variables_preview FROM applications;" \
  | grep -i translator_service'
# Expected: only the translator app's DATABASE_URL — no third-party refs

# 3. Confirm row count baseline so we can verify post-rename
ssh vps 'sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -At -d translator_service -c \
    "SELECT count(*) FROM pg_stat_user_tables;"'
```

**Migration (downtime starts):**
```bash
# 4. Stop translator container in Coolify (5-min window begins)
ssh vps 'sudo docker stop $(sudo docker ps -q --filter "name=translator" --filter "name!=postgres-main")'

# 5. Rename the database on postgres-main (translator_service → translator)
ssh vps "sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -c \
    \"ALTER DATABASE translator_service RENAME TO translator;\""

# 6. Verify rename succeeded and row counts match
ssh vps "sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -At -d translator -c \
    \"SELECT count(*) FROM pg_stat_user_tables;\""
# Expected: same count as step 3

# 7. Update Coolify env var DATABASE_URL: change `/translator_service` → `/translator`
# (use Coolify UI, or coolify-db UPDATE applications SET ... WHERE name='fabrik-translator')

# 8. Restart translator via Coolify
# (Coolify UI Deploy button, or wait for next webhook)

# 9. Verify health
curl -fsS https://translator.vps1.ocoron.com/health
ssh vps 'sudo docker logs --tail 50 $(sudo docker ps -q --filter "name=translator")'
# Expected: clean DB connect, no errors
```

**Spec-side changes (commit AFTER live state stable):**
```yaml
# specs/services/translator.yaml — edits:
shape:
  needs_database: true        # ← NEW: explicit opt-in (overrides python-api default of false)

# REMOVE the `infra:` block entirely (currently has `postgres: false` override).
# Do NOT replace it with `infra: postgres: true` — that's redundant noise.
# When shape.needs_database=true and no infra override, the postgres registrar
# runs by default and creates DB `translator` per the standard naming convention.
```

**What the diff should look like:**
```diff
 id: translator
 template: python-api
 domain: translator.vps1.ocoron.com
+
+shape:
+  needs_database: true
-
-infra:
-  postgres: false
```

**Cleanup (after 7+ days of stability — keep old DB temporarily as rollback):**
```bash
# Final cleanup: ensure no app references it, then drop
ssh vps "sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -At -c \
    \"SELECT datname FROM pg_database WHERE datname='translator_service';\""
# If empty (already renamed), nothing to drop. If somehow re-created (manual error), DROP DATABASE.
```

### Acceptance criteria

- `ssh vps "...psql ... -c \\"\\\\l\\""` shows DB named `translator` (not `translator_service`).
- `specs/services/translator.yaml` has `shape.needs_database: true` and no `infra.postgres: false` override.
- `fabrik audit-registrars --spec specs/services/translator.yaml` (Tier 2) reports zero drift for postgres registrar.
- translator service responds 2xx on `GET /health`.
- Backrest snapshot taken in step 1 is retained for 30 days.

### Rollback procedure

If step 4-9 reveals a problem:
```bash
# Reverse the rename
ssh vps "sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -c \
    \"ALTER DATABASE translator RENAME TO translator_service;\""
# Revert DATABASE_URL env var, restart translator
```
If postgres data is corrupted, restore from the Backrest snapshot taken in step 1.

---

## 7. G-J6 — Archive Gatus predrift-fix files

**Effort:** 2 minutes

```bash
ssh vps "sudo mkdir -p /opt/_archive/gatus-predrift-fix-20260506"
ssh vps "sudo find /opt/monitoring/configs/gatus -name '*.predrift-fix.20260506' -exec mv {} /opt/_archive/gatus-predrift-fix-20260506/ \\;"
ssh vps "ls /opt/_archive/gatus-predrift-fix-20260506/"
```

---

## 8. G-J5 — Narrow Cloudflare token scope (CORRECTED v2)

**Effort:** 15 minutes (Cloudflare UI)
**DECIDED 2026-05-09:** keep Zone:Edit + DNS:Edit (preserves site-provisioner's zone-create capability).

### Current scope

Token `cfut_nNprCT...` has Workers Scripts:Edit + Account Settings:Read + Read User. Overly broad.

### Why v1 narrowing was incorrect

v1 said `Zone.DNS:Edit + Zone.Zone:Read`. But site-provisioner exposes `POST /api/cloudflare/zones/{domain}/provision` for CREATING new zones (per `/opt/site-provisioner/README.md`). Zone:Read forbids zone creation; would break new-domain onboarding.

### Corrected scope (Path A — preserve zone provisioning)

1. Cloudflare dashboard → My Profile → API Tokens → Edit `cfut_nNprCT...`
2. Permissions:
   - Zone → Zone → **Edit** (covers Read + create)
   - Zone → DNS → **Edit**
3. Zone Resources: Include → All zones from account (or specific zones if site-provisioner is constrained)
4. Save and verify both work:
   - `POST /api/cloudflare/zones/test.example.com/provision` succeeds (zone create)
   - DNS record creation for existing zone succeeds (e.g., subdomain.ocoron.com A record)

### Alternative (Path B — narrower, breaks zone provisioning)

If you decide to manage zone creation manually via the Cloudflare dashboard going forward:

- Zone → Zone → **Read**
- Zone → DNS → **Edit**

Document this decision in `docs/infrastructure/security-tokens.md`: "Zone creation is operator-only via dashboard; site-provisioner POST /api/cloudflare/zones/.../provision is disabled."

### Acceptance

- Token scope matches the chosen Path.
- All existing operations continue to work (DNS record creation, optionally zone provisioning).

---

## 9. G-H6 + G-H7 — Authelia decisions (DECIDED 2026-05-09: both treated as admin dashboards)

**Operating principle:** standard rules apply to all deployments; non-public services get Authelia gates.

### G-H6 — image-broker (DECIDED: pair `is_admin_dashboard: true` + `has_bearer_api: true`)

**M2M risk discovered v3.1 (V3-N1):** image-broker is called from internal Fabrik services (captcha, translator, emailgateway, file-api, file-worker, etc.) via `httpx.get("https://image-broker.vps1.ocoron.com/...", headers={"X-Internal-Token": "..."})`. Locking `is_admin_dashboard: true` alone would route those internal calls to Authelia 2FA login → break every internal caller.

**Standard Fabrik pattern (per Coolify, Grafana):** admin dashboard + bearer API both flagged. Authelia rule gates the UI on `/` but bypasses `/api/*` for valid bearer-token requests. Aligns with Özgür's "standard rules unless mandatory diverge" principle — this IS the standard rule for internally-consumed services with admin UIs.

```yaml
# specs/services/image-broker.yaml — edit:
shape:
  is_admin_dashboard: true   # ← UI behind Authelia 2FA
  has_bearer_api: true       # ← /api/* paths bypass Authelia for bearer-token requests
```

Then:
```bash
fabrik redeploy --refresh-infra --spec specs/services/image-broker.yaml --yes
# Authelia registrar adds:
#   - 2FA rule for image-broker.vps1.ocoron.com (UI paths)
#   - bearer-bypass rule for image-broker.vps1.ocoron.com/api/* (API paths)
```

**Document the M2M contract in spec comments:**
```yaml
# specs/services/image-broker.yaml top-of-file comment:
# image-broker is consumed by internal Fabrik services (captcha, translator, file-api, etc.)
# via X-Internal-Token bearer auth on /api/* paths. UI paths require Authelia 2FA.
# DO NOT remove has_bearer_api: true without first auditing all internal callers
# and migrating them to OAuth/Authelia headers.
```

**Acceptance:**
- `ssh vps 'sudo grep -F image-broker /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml'` returns ≥2 rules (UI gate + API bypass).
- Browsing `https://image-broker.vps1.ocoron.com/` redirects to Authelia 2FA login.
- `curl -fsS -H "X-Internal-Token: $TOKEN" https://image-broker.vps1.ocoron.com/api/health` returns 2xx (NOT redirected to Authelia).
- `curl -fsS https://image-broker.vps1.ocoron.com/api/health` (no token) returns 401 from image-broker (NOT 302 from Authelia) — proves bearer-bypass forwarded the request and the app's own auth rejected it.

### G-H7 — fabrik-proxy (DECIDED: update spec to match live state)

Live state already has the Authelia rule. Spec is the source of drift. Reconcile by editing the spec, NOT the live state:

```yaml
# specs/services/proxy.yaml — edit line 16:
shape:
  is_admin_dashboard: true   # ← was false. Proxy serves Coolify admin UI; admin-dashboard is correct.
```

No live VPS change needed. Just `git commit specs/services/proxy.yaml` after edit.

**Acceptance:**
- `git diff specs/services/proxy.yaml` shows only the `is_admin_dashboard: false → true` change.
- `fabrik audit-registrars --spec specs/services/proxy.yaml` (Tier 2) reports zero drift for authelia registrar.

---

## 10. G-D4 — Fix AGENTS.md registrar list drift (NEW v2)

**Effort:** 2 minutes, 1 file
**Risk:** zero — pure doc edit
**File:** `/opt/fabrik/AGENTS.md` lines 459 + 479

### Current state

Both lines list registrars as: `(postgres / gatus / backrest / glitchtip / grafana / authelia / meilisearch)` — **7 registrars**.

Code's `_REGISTRAR_ORDER` tuple at `src/fabrik/orchestrator/infrastructure.py:86-94` has **9**: postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus.

### Required edit

In both places, replace the parenthetical with:

```
(postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus)
```

### Why this matters

Traycer auto-loads AGENTS.md on every interaction. The drift means Traycer plans against a 7-registrar reality while code runs 9. After this 2-minute edit, Traycer's mental model matches the orchestrator.

### Acceptance

- `grep -c "redis\|prometheus" AGENTS.md` increases by ≥2 in the registrar-list context.
- The Scaffold Types table at line ~461 still references the same 9 (no broader edit needed).

---

## 11. G-B5 — `fabrik scaffold` copies CLAUDE.md (NEW v2)

**Effort:** 5 minutes, 1 file
**File:** `src/fabrik/scaffold.py` around line 666 (where AGENTS.md is copied)

### Current state

`scaffold.py` copies AGENTS.md (line 666), AGENTS-compact.md (line 671), .windsurfrules (line 650). **CLAUDE.md is NOT copied.** It only arrives later via the `governance-sync` pre-commit hook on first qualifying commit (`scripts/sync_enforcement_to_projects.py:GOVERNANCE_FILES`).

This means Claude Code in fresh scaffolds runs without its rule file for the first commit cycle.

### Required change

Add a fourth copy line near line 666:

```python
# After the existing AGENTS-compact.md copy at line 671:
fabrik_claude_md = FABRIK_ROOT / "CLAUDE.md"
if fabrik_claude_md.exists():
    shutil.copy(fabrik_claude_md, project_dir / "CLAUDE.md")
```

(`AFCL.md` is already copied at scaffold.py:679; `opencode.json` is already copied at scaffold.py:717. CLAUDE.md is the only governance file scaffold currently misses.)

### Acceptance

- `fabrik scaffold test-tier1-demo --type python-api` produces `/opt/test-tier1-demo/CLAUDE.md` immediately (before any commit).
- `cmp /opt/fabrik/CLAUDE.md /opt/test-tier1-demo/CLAUDE.md` returns no diff.

---

## 12. G-B6 — Decide fate of next-tailwind template (NEW v2)

**Effort:** 5 min (deprecate) or 15 min (document)
**Risk:** zero — config decision
**Files:** `templates/next-tailwind/` and/or `AGENTS.md`

### Current state

`templates/next-tailwind/defaults.yaml` exists with a valid shape block. **But** `grep -c "next-tailwind" AGENTS.md` returns 0 — it's missing from the Scaffold Types table at AGENTS.md line ~461.

### Decision

**Path A — deprecate:**
```bash
# If next-tailwind isn't actively used:
git mv templates/next-tailwind /tmp/  # outside repo
git commit -m "Remove unused next-tailwind template (G-B6)"
```

**Path B — document:**
Add a row to AGENTS.md Scaffold Types table:
```markdown
| next-tailwind | templates/next-tailwind/ | Next.js + Tailwind | service | is_public |
```
And to the Project Type → Default Packs table.

### Acceptance

- Either: `templates/next-tailwind/` no longer exists, OR `grep -c "next-tailwind" AGENTS.md` ≥ 2.

---

## 13. G-B1a + G-D4 + G-B5 propagation step (addresses C5)

**Effort:** 1 minute
**Why:** After editing AGENTS.md (G-D4) and scaffold.py (G-B5), the existing `governance-sync` pre-commit hook only fires on staged commits including those files. Initial bulk propagation to all 42 projects requires:

```bash
cd /opt/fabrik
python3 scripts/sync_enforcement_to_projects.py --force
# Watch for "synced X files to Y projects"
```

### Acceptance

- All 42 `/opt/<project>/` clones have the updated AGENTS.md (with corrected 9-registrar list).
- All 42 have CLAUDE.md — verify explicitly:
  ```bash
  for p in /opt/*/CLAUDE.md; do [ -f "$p" ] || echo "MISSING: $p"; done
  # Expected: empty output. Any "MISSING:" lines mean the propagator hasn't run since CLAUDE.md was added to GOVERNANCE_FILES; run `python3 scripts/sync_enforcement_to_projects.py --force` to fix.
  ```

---

## Tier 1 done — verification

After all 13 items:

```bash
# 0. Snapshot still current
cd /opt/fabrik && grep -n "def status(" src/fabrik/cli.py    # 549

# 1a. Spec merge works
PYTHONPATH=src python3 -c "
from fabrik.spec_loader import load_spec
for n in ['captcha', 'emailgateway', 'file-api', 'image-broker', 'translator', 'file-worker', 'proxy', 'site-provisioner']:
    s = load_spec(f'specs/services/{n}.yaml')
    print(f'{n:18} shape={getattr(s, \"shape\", None) is not None}')
"
# Expect: 8 lines all 'shape=True'

# 1b. (if Path B applied) prometheus runs for shape-less specs
PYTHONPATH=src python3 -c "
import sys; sys.path.insert(0, 'src')
from fabrik.spec_loader import load_spec
from fabrik.orchestrator.infrastructure import resolve_applicability
s = load_spec('specs/services/captcha.yaml')
res = resolve_applicability(s.model_dump() if hasattr(s, 'model_dump') else dict(s))
print('prometheus runs:', res.get('prometheus', (False,))[0])
"
# Expect (Path B): True; (Path A): False

# 3. fabrik status fixed
PYTHONPATH=src python3 -m fabrik.cli status specs/services/site-provisioner.yaml
# Expect: actual Coolify status, not "None"
PYTHONPATH=src python3 -m fabrik.cli status specs/services/proxy.yaml
# Expect: resolves correctly without 'fabrik-fabrik-proxy' lookup

# 4. fabrik plan shows registrars
PYTHONPATH=src python3 -m fabrik.cli plan specs/services/proxy.yaml | grep "RUNS\|skipped"
# Expect: gatus RUNS, glitchtip RUNS, grafana RUNS, others skipped

# 2. Redis registry seeded
ssh vps 'cat /opt/monitoring/configs/redis/assignments.json | python3 -m json.tool'
# Expect: clean JSON with authelia=3, glitchtip-web=4

# 7. predrift-fix files archived
ssh vps 'ls /opt/monitoring/configs/gatus/apps/*.predrift* 2>&1'
# Expect: ls: cannot access ... No such file

# 10. AGENTS.md drift fixed
grep -c "redis\|prometheus" AGENTS.md
# Expect: ≥ baseline + 2

# 11. CLAUDE.md scaffold copy
fabrik scaffold _tier1_test --type python-api -d "test"
ls /opt/_tier1_test/CLAUDE.md
# Expect: file exists; cleanup with: rm -rf /opt/_tier1_test
```

Once these pass, Tier 2 becomes safe to start.
