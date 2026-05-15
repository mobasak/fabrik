# 03 — Tier 2: Reconciliation Loop (v3.2)

**Total effort:** ~14 hours across 1-2 focused sessions (was 12 hr in v1; +2 hr for G-F5 + concurrency lock + state-schema flag)
**Risk:** medium — new CLI subcommands and persistent state files
**Goal:** close the spec ↔ live-state loop so drift is detectable, recoverable, and visible

## v2 changes

- **§10 G-F2 reconcile-all** uses a new local-file `flock` helper for WSL-side concurrency (addresses C4 — `drivers/locks.py::run_locked` is for VPS-side bash mutations only and cannot wrap Python orchestration)
- **§13 G-F3 state file** schema adds `data_bearing: bool` flag per resource entry (addresses C3); path notation corrected to `FABRIK_ROOT / ".fabrik" / "state" / "<id>.json"` (addresses C12)
- **§14 G-G4** adds Option B (WSL-side cron) as alternative to systemd-on-VPS (addresses C7)
- **§17 G-J3** alias-watcher write-side specified explicitly: new `_provision_coolify_alias` step + atomic write (addresses C6)
- **NEW §19** G-F5 (`fabrik destroy --partial`) (addresses C14)
- "all 7 deployed shape-having specs" → corrected to "however many specs have shape: blocks" (addresses D row about unsourced 7-figure)

## Why Tier 2

Tier 1 makes the orchestrator capable of acting on the 5 deployed pre-G1 services. Tier 2 makes the orchestrator's actions **observable, auditable, and recoverable** across the whole fleet. After Tier 2:

- One command (`fabrik audit-registrars`) reports all drift across all specs
- One command (`fabrik reconcile-all`) sweeps the fleet to spec-defined state
- Every successful apply persists state to `.fabrik/state/<id>.json` for later destroy/audit
- Pre-commit catches spec contradictions before they reach `fabrik apply`
- Weekly cron alerts on Authelia drift via Alertmanager → Telegram (reuses existing receiver pattern)
- New `fabrik destroy --partial <registrar>` for surgical cleanup

## Order of operations

10-11 are headline features. 12-13 add the persistence layer. 14-16 are pre-commit hardening. 17-18 are operational improvements. 19 is the new partial-destroy. **20 (T2-08) is run BEFORE Tier 2 starts** — see "Pre-flight hot-fix" below.

## Pre-flight hot-fix — T2-08 Part A (15 min, REQUIRED before T2-01)

Before starting Tier 2's foundation work (T2-01 = §10 locks_local + §13 G-F3 state file), execute **T2-08 Part A** (§20 below) against vps1:

```bash
# Surgical Authelia config edit — closes the live security drift for errors.vps1.ocoron.com
ssh vps "sudo cp /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml \
  /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml.backup.t2-08-$(date +%Y%m%d-%H%M%S)"
ssh vps "sudo sed -i '/^    - errors\\.vps1\\.ocoron\\.com\$/d' \
  /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml"
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"
# Verify: curl -sS -o /dev/null -w "%{http_code}\n" https://errors.vps1.ocoron.com/  # expect 302
```

**Why this is the prerequisite for T2-01:**

- T2-01 builds the state file foundation (`/opt/fabrik/.fabrik/state/<id>.json`) that the rest of Tier 2 + 4 depends on. The 15-min hot-fix has no code-level dependency on T2-01, but it leaves the GlitchTip UI publicly reachable while we build foundation. Closing the security drift first is the right operational order.
- T2-08 Parts B + C (Gatus check repair, precedence-aware `add_access_rule`) do NOT need to run before T2-01. They can land any time after.

---

## 10. G-F2 — `fabrik reconcile-all` sweep (CONCURRENCY LOCK ADDED v2)

**Effort:** 2.5 hours (was 2; +0.5 for lock integration)
**File:** `src/fabrik/cli.py` — new subcommand
**Dependency:** Tier 1 G-B1a (so shape-less specs don't no-op)

### Behavior

Walks `specs/services/*.yaml`. For each spec:
1. Skip if no Coolify app exists for that spec id (or `fabrik-<id>` per Tier 1 G-G1 logic).
2. **Acquire per-spec local file lock** via new `src/fabrik/locks_local.py` helper (`with file_lock("reconcile-<id>", timeout_seconds=30)`) to prevent two WSL-side reconcile invocations racing. Note: `drivers/locks.py::run_locked` cannot be reused here — its docstring explicitly says Python-side orchestration of SSH calls cannot hold a remote lock; the only correct use is wrapping a single bash script.
3. Call `redeploy --refresh-infra` (already-existing single-spec command) in dry-run mode.
4. Aggregate the report and print a summary table.
5. With `--yes`, actually apply each.

### Pseudocode

```python
from fabrik.locks_local import file_lock  # NEW v3 — WSL-side local flock helper

@cli.command()
@click.option("--yes", is_flag=True, help="Apply changes (default: dry-run only)")
@click.option("--filter", multiple=True, help="Only reconcile specs matching pattern(s)")
@click.option("--max-concurrent", default=1, help="Max parallel reconciles (default: 1, serial)")
def reconcile_all(yes: bool, filter: tuple, max_concurrent: int):
    """Reconcile every deployed service's registrars to its spec."""
    specs_dir = FABRIK_ROOT / "specs" / "services"
    coolify = CoolifyClient()
    deployed = {a["name"] for a in coolify.list_applications()}

    reports = []
    for spec_path in sorted(specs_dir.glob("*.yaml")):
        try:
            spec = load_spec(spec_path)
        except Exception as e:
            reports.append((spec_path.stem, [], [f"load error: {e}"]))
            continue

        # Tier 1 G-G1 lookup logic
        candidates = [spec.id]
        if not spec.id.startswith("fabrik-"):
            candidates.append(f"fabrik-{spec.id}")
        if not any(c in deployed for c in candidates):
            continue

        if filter and not any(f in spec.id for f in filter):
            continue

        # NEW v2: acquire per-spec lock to prevent concurrent reconcile races
        with file_lock(f"reconcile-{spec.id}", timeout_seconds=30):
            orch = DeploymentOrchestrator()
            ctx = orch.refresh_infrastructure(spec_path=spec_path, dry_run=not yes)
            reports.append((spec.id, ctx.resources, ctx.errors))

    # print summary table
    click.echo(f"\n{'spec':<32} {'registrars':<12} {'errors':<8}")
    for sid, resources, errors in reports:
        click.echo(f"{sid:<32} {len(resources):<12} {len(errors):<8}")
```

### Acceptance criteria

- `fabrik reconcile-all --yes` walks every deployed spec and runs `redeploy --refresh-infra`.
- **Per-spec file lock prevents two operators reconciling the same spec simultaneously**; the second waits up to 30s then fails cleanly.
- Failures in one spec don't abort the others (per-spec error capture).
- `--filter <pattern>` lets the operator scope to one or a few specs.
- Output is a clean summary table.

### Cascading effect

After Tier 1 + this command, a single `fabrik reconcile-all --yes` brings every deployed service into compliance with its spec — fills in all missing Gatus endpoints, Backrest plans, Authelia rules (where shape says yes), etc.

### NEW MODULE: `src/fabrik/locks_local.py` (~30 LoC)

The `file_lock()` helper referenced above is new — `drivers/locks.py` is for VPS-side bash mutations and cannot wrap WSL-side Python orchestration (its own docstring proves it). Sketch:

```python
# src/fabrik/locks_local.py
"""WSL-side local file locking for serializing fabrik subcommands.

This module is the WSL-side counterpart to drivers/locks.py (which is for
VPS-side bash mutations). Use this when you need to prevent two concurrent
fabrik invocations on the operator workstation from racing each other —
e.g., two `fabrik reconcile-all` runs hitting the same spec, or G-F3 state
file writes overlapping with G-F2 reconciles.
"""
from __future__ import annotations
import errno
import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path

LOCK_DIR = Path(os.getenv("FABRIK_LOCK_DIR", "/tmp/fabrik-locks"))


@contextmanager
def file_lock(name: str, timeout_seconds: int = 30, poll_interval: float = 0.5):
    """Acquire an exclusive flock on /tmp/fabrik-locks/<name>.lock.

    Raises TimeoutError if the lock can't be acquired within ``timeout_seconds``.
    The lock is released on context exit (success or exception).
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    # sanitize name → safe filename
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    lock_path = LOCK_DIR / f"{safe}.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if e.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Could not acquire lock {name} within {timeout_seconds}s"
                    )
                time.sleep(poll_interval)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
```

Test: `tests/test_locks_local.py` should cover (a) two threads contending succeed serially, (b) timeout raises `TimeoutError`, (c) exception inside the `with` block still releases the lock.

---

## 11. G-G2 — `fabrik audit-registrars` command

**Effort:** 3 hours (unchanged from v1)
**File:** `src/fabrik/cli.py` — new subcommand + `src/fabrik/audit.py` — new module

### Output format

```
$ fabrik audit-registrars
Loading 65 specs (filtered to N deployed)...
Querying VPS state...

  spec                  | postgres | redis | gatus | backrest | glitchtip | grafana | authelia | meili | prom |
  ----------------------|----------|-------|-------|----------|-----------|---------|----------|-------|------|
  captcha               | n/a      | n/a   | ✗     | n/a      | ✓         | ✓       | n/a      | n/a   | ✗    |
  emailgateway          | n/a      | n/a   | ✗     | n/a      | ✓         | ✓       | n/a      | n/a   | ✗    |
  file-api              | n/a      | n/a   | ✗     | ✗        | ✓         | ✓       | n/a      | n/a   | ✗    |
  image-broker          | n/a      | n/a   | ✗     | n/a      | ✓         | ✓       | ⚠️       | n/a   | ✗    |
  fabrik-proxy          | OVR      | n/a   | ✗     | n/a      | ✓         | ✓       | ⚠️       | n/a   | n/a  |
  site-provisioner      | ✓        | n/a   | ✗     | n/a      | ✓         | ✓       | n/a      | n/a   | n/a  |
  translator            | ⚠️       | n/a   | ✗     | n/a      | ✓         | ✓       | n/a      | n/a   | ✗    |

Legend:
  ✓ = present and matches spec
  ✗ = MISSING (spec says should run, not present on VPS)
  ⚠️ = drift (live state contradicts spec)
  n/a = not applicable per shape
  OVR = explicit infra: <key>: false override
```

### Module structure

```
src/fabrik/audit.py
  ├── audit_postgres(spec) -> AuditResult
  ├── audit_redis(spec) -> AuditResult
  ├── audit_gatus(spec) -> AuditResult
  ├── audit_backrest(spec) -> AuditResult
  ├── audit_glitchtip(spec) -> AuditResult
  ├── audit_grafana(spec) -> AuditResult       (skipped — annotations, like destroyer)
  ├── audit_authelia(spec) -> AuditResult
  ├── audit_meilisearch(spec) -> AuditResult
  ├── audit_prometheus(spec) -> AuditResult
  └── audit_all(spec) -> dict[str, AuditResult]
```

### Acceptance criteria

- `fabrik audit-registrars` runs in <30s against the live VPS.
- Output is the table format above.
- `--json` flag emits machine-readable for automation (used by G-G5 alerting).
- `--spec <path>` scopes to one spec (mirror plan/redeploy).
- Errors querying the VPS are reported, not silently skipped.

---

## 12. G-G3 — `fabrik verify --spec registrars`

**Effort:** 1 hour (unchanged from v1)
**File:** `src/fabrik/verify.py` — add new verifier spec

### Required addition

```python
def verify_registrars(domain: str, spec: Spec) -> VerifyResult:
    """Postcondition: every applicable registrar's side-effect is present."""
    from fabrik.audit import audit_all
    results = audit_all(spec)
    failures = [name for name, r in results.items() if r.status == "missing"]
    if failures:
        return VerifyResult(
            ok=False,
            message=f"Missing registrars for {spec.id}: {', '.join(failures)}"
        )
    return VerifyResult(ok=True, message=f"All applicable registrars present for {spec.id}")
```

### Acceptance

- `fabrik verify proxy.vps1.ocoron.com --spec registrars` returns exit 0 if all good, exit 1 if any missing.

---

## 13. G-F3 — `.fabrik/state/<id>.json` per-deploy state file (SCHEMA + PATH CORRECTED v2)

**Effort:** 2.5 hours (was 2; +0.5 for data_bearing flag + path-handling)
**Files:** `src/fabrik/orchestrator/__init__.py` (DeploymentOrchestrator.deploy + persistence) + new `src/fabrik/state.py` module

### Why

After `fabrik apply` exits, **all in-memory tracking is lost**. There's no record of which Coolify UUID was created, when the deploy succeeded, what git SHA was deployed, or which registrars actually ran.

### Path notation (corrected v2)

State files always live at:

```python
from fabrik.config import FABRIK_ROOT
state_path = FABRIK_ROOT / ".fabrik" / "state" / f"{spec.id}.json"
```

NEVER use a relative path. The orchestrator may be invoked from any cwd (including a project subdirectory during local dev); state writes MUST land in the canonical Fabrik root regardless.

### Schema (v2 — adds `data_bearing` flag per registrar)

```json
{
  "spec_id": "captcha",
  "spec_path": "specs/services/captcha.yaml",
  "spec_sha256": "abc123...",
  "coolify_uuid": "fwgcokk0...",
  "coolify_app_name": "fabrik-captcha",
  "applied_at": "2026-05-09T14:23:11+03:00",
  "git_sha": "4fc36ad5",
  "registrars_applied": [
    {"type": "gatus",     "id": "captcha",      "status": "created", "data_bearing": false},
    {"type": "glitchtip", "id": "captcha",      "status": "exists",  "data_bearing": false},
    {"type": "grafana_annotation_id", "id": "1234", "status": "created", "data_bearing": false}
  ],
  "domain": "captcha.vps1.ocoron.com"
}
```

### Why `data_bearing` matters (addresses C3)

`src/fabrik/orchestrator/rollback.py` `_rollback_postgres` and `_rollback_meilisearch` are **destructive-no-op-by-design** — they refuse to drop DBs/indexes during automated rollback because the data may be the result of hours of ingestion. When G-F4 ships (Tier 4 destroy --use-state), it needs to know which state-file entries are data-bearing to require `--drop-data` opt-in for those specifically. Mark `data_bearing: true` for postgres + meilisearch; `false` for all others.

### Where to write

In `DeploymentOrchestrator.deploy()`, after successful infrastructure provisioning, persist `ctx.resources` + metadata via `state.save(spec_id, resources, ...)`. Also persist on `refresh_infrastructure()` success.

### Concurrency

State writes use the same `locks_local.py` per-spec lock from G-F2 (NEW helper, not `drivers/locks.py`). Atomic write pattern: write to `<id>.json.tmp` then rename.

### Acceptance criteria

- After `fabrik apply specs/services/captcha.yaml --yes`, `.fabrik/state/captcha.json` exists with all fields populated.
- `data_bearing: true` for postgres + meilisearch entries; `false` for the rest.
- After `fabrik destroy specs/services/captcha.yaml --yes`, the state file is moved to `.fabrik/state/_destroyed/<id>.json.<ts>`.
- State files are gitignored (`.fabrik/state/` added to `.gitignore`).
- Concurrent applies are protected by file locking.

---

## 14. G-G4 — Schedule audit_authelia_gates.py (TWO OPTIONS v2)

**Effort:** 30 min (Option A) or 45 min (Option B)
**Why:** The script's docstring says "weekly cron". `systemctl list-timers` confirms no timer exists.

### Option A — VPS-side systemd timer

Refactor `audit_authelia_gates.py` to be standalone-runnable (drop `fabrik.*` imports). Deploy to `/opt/_audit/audit_authelia_gates.py`.

```ini
# /etc/systemd/system/fabrik-audit-authelia.service
[Unit]
Description=Fabrik weekly Authelia gating audit
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/opt/_audit
ExecStart=/usr/bin/python3 /opt/_audit/audit_authelia_gates.py
StandardOutput=journal
StandardError=journal

# /etc/systemd/system/fabrik-audit-authelia.timer
[Unit]
Description=Run Fabrik Authelia audit weekly
Requires=fabrik-audit-authelia.service

[Timer]
OnCalendar=Mon *-*-* 06:00:00
Persistent=true
RandomizedDelaySec=600

[Install]
WantedBy=timers.target
```

**Pros:** runs even if WSL is off. **Cons:** script duplication; updates require copy + deploy.

### Option B — WSL-side cron, runs over SSH (NEW v2)

Keep the script in `/opt/fabrik/scripts/`. Run it from WSL on a schedule; SSH-execute the audit logic remotely.

```bash
# WSL: /etc/cron.d/fabrik-audit-authelia
# Runs every Monday 06:00 Istanbul time
0 6 * * 1 ozgur cd /opt/fabrik && /opt/fabrik/.venv/bin/python scripts/audit_authelia_gates.py >> /var/log/fabrik-audit.log 2>&1
```

OR via systemd --user (if WSL supports it cleanly):

```ini
# ~/.config/systemd/user/fabrik-audit-authelia.timer
[Timer]
OnCalendar=Mon *-*-* 06:00:00 Europe/Istanbul
```

**Pros:** no script duplication; Fabrik logic stays in one repo. **Cons:** doesn't run if WSL is off.

### Recommendation

Option B if WSL is reliably running (typical for daily-use machine). Option A if WSL is intermittent.

### Acceptance (either option)

- `systemctl list-timers fabrik-audit-authelia.timer` (Option A) or `systemctl --user list-timers` / `crontab -l` (Option B) shows next run.
- Manual run produces journal output and exit code 0 if no drift; exit 1 + logged drift on simulated drift.

---

## 15. G-E1 — pre-commit calls `fabrik plan` for changed specs

**Effort:** 30 minutes (unchanged from v1)
**File:** `.pre-commit-config.yaml`

```yaml
- repo: local
  hooks:
    - id: fabrik-plan-specs
      name: Validate changed specs via fabrik plan
      entry: bash -c '
        if [ "$(pwd)" != "/opt/fabrik" ]; then exit 0; fi
        for f in "$@"; do
          /opt/fabrik/.venv/bin/python -m fabrik.cli plan "$f" > /dev/null || {
            echo "fabrik plan failed for $f";
            exit 1;
          }
        done
      ' --
      language: system
      files: '^specs/services/.*\.yaml$'
      pass_filenames: true
```

### Acceptance

- Editing a spec to introduce a contradiction (e.g., `shape.is_admin_dashboard=true` without `domain`) is blocked at commit time, not at deploy time.

---

## 16. G-E2 — `final_gate.py` runs pydantic Spec validation

**Effort:** 30 minutes (unchanged from v1)
**File:** `scripts/final_gate.py:471` (yaml-load location)

When the file matches `specs/services/*.yaml`, additionally validate via pydantic:

```python
if path.match("specs/services/*.yaml"):
    try:
        from fabrik.spec_loader import load_spec
        load_spec(str(path))
    except Exception as e:
        return Issue(
            level="error",
            file=str(path),
            message=f"Spec validation failed: {e}"
        )
```

### Acceptance

- `final_gate.py --check` flags broken specs (missing `id`, `template`, etc.) before commit.

---

## 17. G-J3 — Data-driven `coolify-alias-watcher` (WRITE-SIDE SPECIFIED v2)

**Effort:** 1.5 hours (was 1; +0.5 for orchestrator integration)
**Files on VPS:** `/opt/coolify-alias-watcher/aliases.json` (new) + `/opt/coolify-alias-watcher/watcher.sh` (refactored)
**Files in repo:** `src/fabrik/orchestrator/coolify_alias.py` (new) — addresses C6

### Read side (watcher refactor — same as v1)

```bash
# /opt/coolify-alias-watcher/aliases.json
{
  "bs0wo48k4gwo440gcowscoc8": "meilisearch",
  "e04k4sco44ow04ccc0o0k00k": "gotenberg",
  "vckgs8c00o40o884k48cgow8": "browserless",
  "glitchtip-web": "glitchtip-web"
}

# /opt/coolify-alias-watcher/watcher.sh (refactored)
ALIASES_JSON=/opt/coolify-alias-watcher/aliases.json
declare -A ALIASES
while IFS="=" read -r key val; do
    ALIASES["$key"]="$val"
done < <(jq -r 'to_entries | map("\(.key)=\(.value)") | .[]' "$ALIASES_JSON")
```

### Write side (NEW v2 — orchestrator integration)

When does aliases.json get updated? Only when the orchestrator's deploy step needs a service to be reachable by a custom alias (e.g., a service depends on `gotenberg.coolify.local`).

Add a new orchestrator step `_provision_coolify_alias` invoked from `DeploymentOrchestrator.deploy()` AFTER the Coolify create-app step succeeds:

```python
# src/fabrik/orchestrator/coolify_alias.py (new)
import tempfile
from pathlib import Path
import json, shlex  # json for serialize, shlex for shell-safe quoting
from fabrik.drivers.ssh import ssh  # existing helper, returns stdout str directly

ALIASES_PATH = "/opt/coolify-alias-watcher/aliases.json"

def add_alias(coolify_uuid: str, alias: str) -> None:
    """Atomically add an alias mapping."""
    # 1. Read current
    raw = ssh(f"sudo cat {ALIASES_PATH}")
    aliases = json.loads(raw)

    # 2. No-op if already present and matches
    if aliases.get(coolify_uuid) == alias:
        return

    # 3. Update
    aliases[coolify_uuid] = alias

    # 4. Atomic write: tmp → rename, then signal watcher to reload
    # NOTE: shlex.quote shell-escapes new_content for safe embedding in the heredoc.
    # Add `import shlex, json` at the top of the module if not already imported.
    new_content = json.dumps(aliases, indent=2)
    ssh(f"sudo tee {ALIASES_PATH}.tmp > /dev/null <<< {shlex.quote(new_content)}")
    ssh(f"sudo mv {ALIASES_PATH}.tmp {ALIASES_PATH}")
    ssh("sudo systemctl reload coolify-alias-watcher.service || sudo systemctl restart coolify-alias-watcher.service")
```

### Concurrency note

The `ssh()`-based read+write sequence is NOT atomic across the read-modify-write window. For the volume of deploys today (low), this is acceptable. If concurrent deploys ever become routine, wrap the whole sequence in a per-file `flock` on the VPS:

```bash
# In add_alias, replace the 3 ssh() lines with one combined:
flock /var/lock/aliases.json.lock -c '
    new=$(jq ". + {\"$UUID\": \"$ALIAS\"}" /opt/coolify-alias-watcher/aliases.json)
    echo "$new" > /opt/coolify-alias-watcher/aliases.json.tmp
    mv /opt/coolify-alias-watcher/aliases.json.tmp /opt/coolify-alias-watcher/aliases.json
'
```

### Trigger condition

The orchestrator only calls `add_alias` when the spec's `coolify` block declares a custom alias. Add to spec schema:

```yaml
coolify:
  alias: meilisearch  # optional; if set, _provision_coolify_alias step runs
```

### Acceptance

- Editing aliases.json + restarting the service updates the watch list (manual flow still works).
- `fabrik apply` for a spec with `coolify.alias` set adds an entry to aliases.json automatically.
- Atomic write: no race between watcher reading and orchestrator writing.
- Existing 4 aliases remain functional.

---

## 18. G-J1 — `data/projects.yaml` deploy-aware fields

**Effort:** 1 hour (unchanged from v1)
**File:** `scripts/sync_projects.py`
**Dependency:** G-F3 (state files exist)

### Required additions

```yaml
captcha:
  path: /opt/captcha
  type: python-api
  status: 🔨 Development
  scaffold_status: ✅ Current
  domain: captcha.vps1.ocoron.com
  # NEW (populated from .fabrik/state/captcha.json — created by G-F3):
  spec_path: specs/services/captcha.yaml
  coolify_uuid: fwgcokk0...
  coolify_app_name: fabrik-captcha
  last_apply_at: "2026-05-09T14:23:11+03:00"
  last_apply_sha: 4fc36ad5
  last_apply_status: success
  registrars_applied: [gatus, glitchtip, grafana]
```

### Acceptance

- After `fabrik apply` followed by `fabrik scan`, the project entry includes deploy-aware fields.
- Projects without state files (never deployed) have `last_apply_status: never`.

---

## 19. G-F5 — `fabrik destroy --partial <registrar>` (NEW v2 — addresses C14)

**Effort:** 1.5 hours
**File:** `src/fabrik/cli.py` (extend `destroy`) + `src/fabrik/orchestrator/destroyer.py` (add partial path)
**Why:** today, surgical removal of one registrar's resources (e.g., proxy.vps1 Authelia rule) requires either editing the spec to flip the shape flag (then full destroy) OR manual VPS edits. Both are fragile.

### Behavior

```
$ fabrik destroy specs/services/proxy.yaml --partial authelia
🗑️  Removing only authelia resources for fabrik-proxy:
   - Authelia rule: proxy.vps1.ocoron.com (removed)
✅ Partial destroy complete. Other resources (gatus, glitchtip, etc.) preserved.
   Note: spec.shape.is_admin_dashboard was true; subsequent fabrik redeploy --refresh-infra will re-add the rule.
   To make this permanent, set shape.is_admin_dashboard: false in the spec.
```

### Pseudocode

```python
# IMPORTANT: `destroy` in src/fabrik/cli.py is a single @cli.command() (line 703),
# NOT a click.Group. We extend the existing decorator chain — we do NOT add @destroy.command(...).
# Also: the 8 _destroy_* handlers in orchestrator/destroyer.py have HETEROGENEOUS signatures
# (verified against actual source on 2026-05-09):
#   _destroy_authelia(domain, dry_run)                      # takes domain, NOT name
#   _destroy_postgres(name, drop_data, dry_run)             # takes drop_data
#   _destroy_redis(name, drop_data, dry_run)                # takes drop_data
#   _destroy_meilisearch(name, drop_data, dry_run)          # takes drop_data
#   _destroy_gatus(name, dry_run)
#   _destroy_backrest(name, dry_run)
#   _destroy_glitchtip(name, dry_run)
#   _destroy_prometheus(name, dry_run)
# We dispatch via a per-registrar argument-builder map.

# In src/fabrik/cli.py, ADD --partial and --drop-data to the EXISTING destroy command:
@cli.command()
@click.argument("spec_path")
@click.option("--yes", is_flag=True)
@click.option("--keep-dns", is_flag=True)
@click.option("--drop-data", is_flag=True, help="Required for postgres/redis/meilisearch deletion")
@click.option("--dry-run", is_flag=True, default=False)
@click.option(
    "--partial",
    "partial",
    multiple=True,
    help="Destroy only the named registrar(s). Repeatable. Skips full Coolify+DNS teardown.",
)
def destroy(spec_path, yes, keep_dns, drop_data, dry_run, partial):
    spec = load_spec(spec_path)

    if partial:
        from fabrik.orchestrator import destroyer as _d
        # Per-registrar argument builders matching ACTUAL handler signatures.
        # spec.domain for authelia; spec.id for everything else.
        HANDLER_ARGS = {
            "authelia":    lambda s: (s.domain, dry_run),
            "postgres":    lambda s: (s.id, drop_data, dry_run),
            "redis":       lambda s: (s.id, drop_data, dry_run),
            "meilisearch": lambda s: (s.id, drop_data, dry_run),
            "gatus":       lambda s: (s.id, dry_run),
            "backrest":    lambda s: (s.id, dry_run),
            "glitchtip":   lambda s: (s.id, dry_run),
            "prometheus":  lambda s: (s.id, dry_run),
            # NOTE: grafana intentionally omitted — destroyer.py:469-470 skips it by design.
        }
        for reg_name in partial:
            if reg_name not in HANDLER_ARGS:
                click.echo(f"✗ Unknown or non-destroyable registrar: {reg_name}", err=True)
                click.echo(f"   Valid: {sorted(HANDLER_ARGS)}", err=True)
                continue
            handler = getattr(_d, f"_destroy_{reg_name}", None)
            if handler is None:
                click.echo(f"✗ destroyer module has no _destroy_{reg_name}", err=True)
                continue
            args = HANDLER_ARGS[reg_name](spec)
            result = handler(*args)
            click.echo(f"   - {reg_name}: {result.status}")
        click.echo(
            "⚠️  Partial destroy: spec is unchanged. "
            "Next `fabrik redeploy --refresh-infra` will re-add removed resources "
            "if shape still requires them. Edit spec to make change permanent."
        )
        return

    # else: existing full-destroy path (unchanged from current cli.py:703 destroy body)
    ...
```

### Acceptance criteria

- `fabrik destroy specs/services/proxy.yaml --partial authelia` removes only the Authelia rule.
- Other registrar resources (Gatus endpoint, GlitchTip project, etc.) untouched.
- Warning surfaced: spec drift will cause re-add on next `redeploy --refresh-infra`.
- Multiple `--partial` accepted: `--partial authelia --partial gatus`.

### G-H7 resolution path via G-F5

Once shipped, the G-H7 ⚠️ "remove proxy.vps1 Authelia rule" decision becomes:
```bash
# 1. Edit spec to make it consistent
sed -i 's/is_admin_dashboard: true/is_admin_dashboard: false/' specs/services/proxy.yaml
# 2. Surgically remove the now-orphan rule
fabrik destroy specs/services/proxy.yaml --partial authelia --yes
# 3. No more drift; future redeploy won't re-add.
```

---

## 20. T2-08 — Edge-auth drift cleanup from 2026-05-15 audit (G-H10 + G-G6 + G-H11)

**Total effort:** ~2 hours (~15 min Part A + ~20 min Part B + ~75 min Part C + 10 min verify)
**Risk:** Part A touches live Authelia config (low — same surgical-edit pattern as T1-04 follow-up); Part B is a one-line YAML edit; Part C is a Python registrar change with unit-test coverage.
**Why now:** Surfaced by the 2026-05-15 post-T1-05 wiring audit. Parts A and B are real production drifts (one security-relevant, one false-alarm noise); Part C is the durability fix that prevents Part A from regressing the next time `fabrik redeploy <app> --refresh-infra` runs against an Authelia-gated service. Without Part C, this ticket is groundhog-day.

### Audit evidence

```bash
# Drift A: errors.vps1.ocoron.com publicly reachable despite docs/operations/vps-urls.md
# saying it's Authelia-gated.
curl -sS -o /dev/null -w "%{http_code}\n" https://errors.vps1.ocoron.com/
# Observed: 200 (no redirect to auth.vps1.ocoron.com)
# Expected per vps-urls.md line 59: 302 → https://auth.vps1.ocoron.com/?rd=...

# Root cause: configuration.yml line 29 includes errors.vps1.ocoron.com in the
# multi-domain bulk-bypass block (alongside pdf, browser, search, captcha, proxy,
# translator, files-api, emailgateway, dns) — that block has policy: bypass and
# no resources: filter, so ALL paths bypass. Authelia is first-match-wins; the
# *.vps1.ocoron.com two_factor catchall at line 41 never gets reached.

# Drift B: Gatus check external/monitor-public failing with [STATUS] (401) < 400 = false.
curl -sS https://status.vps1.ocoron.com/api/v1/endpoints/statuses 2>/dev/null \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print([(e["name"], e["results"][-1].get("conditionResults")) for e in d if e["results"] and not e["results"][-1].get("success")])'
# Observed: external/monitor-public expects STATUS < 400, monitor.vps1 returns 401
# because Authelia gates / and Grafana returns 401 to unauthenticated requests.
# This is correct backend behavior; the Gatus check assertion is wrong.
```

### Part A — G-H10: Resolve `errors.vps1.ocoron.com` gating drift

**Decision required** before any edit. Two valid architectures; pick one and align doc + config.

| Option | Behavior | Rationale |
| --- | --- | --- |
| **A1 — Gate with Authelia (RECOMMENDED)** | `errors.vps1.ocoron.com` falls under `*.vps1.ocoron.com two_factor` catchall. User logs in to Authelia first (2FA), then GlitchTip's own auth as second factor inside the gate. | Defense-in-depth: matches `monitor` (Grafana) and `auto` (n8n) admin-UI pattern. Removes any reliance on GlitchTip's own session security. **Aligns with current docs/operations/vps-urls.md line 59.** |
| **A2 — Public, rely on GlitchTip auth only** | Leave in bulk-bypass list. GlitchTip's own login is the only gate. | Simpler for invited error-report viewers (1-click signup, no Authelia account creation). **Requires updating vps-urls.md to say "GlitchTip native auth only".** |

**Recommended: A1.** Reasoning: the audit found this drift because docs say one thing and live says another. A1 restores the documented design and aligns with how every other admin UI on vps1 is gated. A2 is defensible but introduces inconsistency for a marginal UX gain — and GlitchTip's own auth has had CVEs (e.g. CVE-2024-32869 on its upstream Sentry).

**Implementation (A1 path):**

```bash
# 1. Backup current Authelia config
ssh vps 'sudo cp /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml \
        /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml.backup.t2-08-$(date +%Y%m%d-%H%M%S)'

# 2. Remove errors.vps1.ocoron.com from the bulk-bypass list (line ~29).
#    The block currently reads:
#      - domain:
#        - pdf.vps1.ocoron.com
#        - browser.vps1.ocoron.com
#        - search.vps1.ocoron.com
#        - captcha.vps1.ocoron.com
#        - proxy.vps1.ocoron.com
#        - translator.vps1.ocoron.com
#        - files-api.vps1.ocoron.com
#        - emailgateway.vps1.ocoron.com
#        - dns.vps1.ocoron.com
#        - errors.vps1.ocoron.com    ← REMOVE THIS LINE
#        policy: bypass
#    After the edit, errors.vps1 falls through to the *.vps1.ocoron.com two_factor
#    catchall at line 41.

# 3. Restart Authelia (SIGHUP is broken — see CLAUDE.md hard-stops, must docker restart)
ssh vps 'sudo docker restart authelia-hks48k8sg8o4co4co08co00o'

# 4. Wait for healthy
ssh vps 'sudo docker ps --filter "name=authelia" --format "{{.Status}}"'  # expect: Up <N> (healthy)
```

**Acceptance (Part A):**

- `curl -sS -o /dev/null -w "%{http_code}\n" https://errors.vps1.ocoron.com/` → **302** (was 200)
- Redirect Location header points at `https://auth.vps1.ocoron.com/?rd=https%3A%2F%2Ferrors.vps1.ocoron.com%2F&rm=GET`
- After Authelia login (manual browser test), errors.vps1 loads the GlitchTip UI
- Regression: `pdf.vps1.ocoron.com`, `captcha.vps1.ocoron.com`, `translator.vps1.ocoron.com` etc. all still return 200 on `/` (still in bulk-bypass — these are correct API-only services)
- Regression: `monitor.vps1.ocoron.com` still returns 302 (still in two_factor catchall — unchanged)
- `docs/operations/vps-urls.md` line 59 already says "Authelia"; no doc update needed

### Part B — G-G6: Fix Gatus `external/monitor-public` check

**File:** `/opt/gatus/config.yaml` on vps1 (or whichever path the Gatus deploy reads — discover via `docker inspect gatus-v8s4cokcwg0co4w8okkccc0w`).

**Current check (assumed shape):**

```yaml
endpoints:
  - name: monitor-public
    group: external
    url: https://monitor.vps1.ocoron.com/
    interval: 60s
    conditions:
      - "[STATUS] < 400"
      - "[CERTIFICATE_EXPIRATION] > 168h"
```

**Two valid fixes — pick (b):**

| Option | New URL / condition | Rationale |
| --- | --- | --- |
| (a) Accept the auth redirect | URL unchanged; `conditions:` becomes `[STATUS] == 302` and `[BODY] contains "auth.vps1.ocoron.com"` | Verifies Authelia is gating correctly, which is what we want for an external check. |
| (b) Point at Grafana's public health endpoint | URL → `https://monitor.vps1.ocoron.com/api/health` (or `/healthz`, whichever exists); `conditions:` stays `[STATUS] < 400` + `[BODY] contains "ok"` | Verifies the backend service is actually healthy, not just that the auth gate fires. **Stronger signal**: Authelia could be broken and (a) would still pass. |

**Recommended: (b).** Verify Grafana's actual health path first:

```bash
ssh vps "sudo docker exec grafana-loc484owg8gsw04owo0go8kc curl -sS http://localhost:3000/api/health"
# Expect JSON like {"database":"ok","version":"11.5.1","commit":"..."}
```

**Implementation:**

```bash
# 1. Find Gatus config path (compose volume mount)
ssh vps "sudo docker inspect gatus-v8s4cokcwg0co4w8okkccc0w --format '{{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}'"
# Expected something like /opt/gatus/config:/config

# 2. Edit the monitor-public endpoint URL + condition
# 3. Restart Gatus (it autoreloads on file change in recent versions but restart is safer)
ssh vps "sudo docker restart gatus-v8s4cokcwg0co4w8okkccc0w"

# 4. Wait 90s for the check to run, then re-query the status API
sleep 90
curl -fsS https://status.vps1.ocoron.com/api/v1/endpoints/statuses 2>/dev/null \
  | python3 -c 'import sys,json; [print(e["name"], e["results"][-1]["success"]) for e in json.load(sys.stdin) if e["name"]=="monitor-public"]'
```

**Acceptance (Part B):**

- `external/monitor-public` reports `success: True` after the next check interval
- Gatus dashboard at `https://status.vps1.ocoron.com` shows **39/39 healthy** (was 38/39)
- The check's `[STATUS]` condition matches Grafana's real `/api/health` response (200), not a false alarm from the auth gate

### Part C — G-H11: Make `add_access_rule` precedence-aware (durability fix)

**Why this is part of the same ticket:** Without Part C, Part A regresses the next time the Authelia registrar runs for any new admin-dashboard service. The registrar currently appends rules at end-of-file (after the `*.vps1.ocoron.com two_factor` catchall), which makes them dead code. Part A only stays fixed if the registrar respects precedence on every future write.

**File:** `src/fabrik/drivers/authelia.py`

**Current behavior (the bug Lesson 56 documents):**

`add_access_rule(domain, policy, resources, ...)` appends to the `access_control.rules:` list. The two_factor catchall at the bottom matches first for any `*.vps1.ocoron.com` host, so newly-appended specific-path bypasses are dead code.

**Required behavior:**

When inserting a rule with `policy=bypass` (or any non-default policy) for a specific domain that the catchall would also match, **insert it BEFORE the catchall**, not after.

**Implementation sketch:**

```python
# src/fabrik/drivers/authelia.py — extend add_access_rule()

def _insert_rule_at_precedence(rules: list[dict], new_rule: dict) -> list[dict]:
    """Insert new_rule before any rule that would shadow it.

    A rule R shadows new_rule N if R's domain pattern is broader (e.g. wildcard)
    and R has no resources: filter or a less-specific one. The canonical example:
    R = {domain: '*.vps1.ocoron.com', policy: two_factor} shadows
    N = {domain: 'images.vps1.ocoron.com', policy: bypass, resources: [^/api/]}.
    """
    def shadows(broad: dict, narrow: dict) -> bool:
        b_dom = broad.get("domain")
        n_dom = narrow.get("domain")
        # Normalize to lists (Authelia accepts both scalar and list for domain)
        b_doms = b_dom if isinstance(b_dom, list) else [b_dom]
        n_doms = n_dom if isinstance(n_dom, list) else [n_dom]
        # Wildcard match: '*.vps1.ocoron.com' shadows 'images.vps1.ocoron.com'
        for bd in b_doms:
            if not isinstance(bd, str) or "*" not in bd:
                continue
            suffix = bd.replace("*", "")
            for nd in n_doms:
                if isinstance(nd, str) and nd.endswith(suffix):
                    return True
        return False

    # Find insertion point: first shadowing rule, or end of list
    for i, existing in enumerate(rules):
        if shadows(existing, new_rule):
            return rules[:i] + [new_rule] + rules[i:]
    return rules + [new_rule]


def add_access_rule(domain, policy, resources=None, methods=None):
    cfg = _load_config()
    rules = cfg.setdefault("access_control", {}).setdefault("rules", [])

    # Build the rule dict (existing logic)
    new_rule = {"domain": domain, "policy": policy}
    if resources:
        new_rule["resources"] = resources
    if methods:
        new_rule["methods"] = methods

    # Idempotency: if an exact-match rule already exists, no-op
    if any(_rules_equivalent(r, new_rule) for r in rules):
        return

    # Precedence-aware insert (NEW v3 — addresses Lesson 56 follow-up)
    cfg["access_control"]["rules"] = _insert_rule_at_precedence(rules, new_rule)
    _save_config(cfg)
```

**Test coverage (`tests/drivers/test_authelia_rule_order.py`):**

```python
def test_specific_bypass_inserted_before_wildcard_catchall():
    rules = [
        {"domain": "*.vps1.ocoron.com", "policy": "two_factor"},
    ]
    new = {"domain": "images.vps1.ocoron.com", "policy": "bypass",
           "resources": ["^/api/"]}
    result = _insert_rule_at_precedence(rules, new)
    assert result[0]["domain"] == "images.vps1.ocoron.com"
    assert result[1]["domain"] == "*.vps1.ocoron.com"

def test_unrelated_rule_appended():
    rules = [{"domain": "*.vps1.ocoron.com", "policy": "two_factor"}]
    new = {"domain": "ocoron.com", "policy": "bypass"}
    result = _insert_rule_at_precedence(rules, new)
    # ocoron.com is not shadowed by *.vps1.ocoron.com
    assert result[-1]["domain"] == "ocoron.com"

def test_idempotent_no_duplicate():
    existing_rule = {"domain": "images.vps1.ocoron.com", "policy": "bypass",
                     "resources": ["^/api/"]}
    rules = [existing_rule, {"domain": "*.vps1.ocoron.com", "policy": "two_factor"}]
    add_access_rule("images.vps1.ocoron.com", "bypass", ["^/api/"])
    # Verify list length unchanged — would need _load_config mock
```

**Acceptance (Part C):**

- Unit test `test_specific_bypass_inserted_before_wildcard_catchall` passes
- Manual `fabrik redeploy <admin-dashboard-service> --refresh-infra` against a fresh test spec produces rules in correct order (specific bypass before catchall)
- Lesson 56 "Long-term follow-up" paragraph marked resolved in `docs/LESSONS_LEARNT.md`

### Final verification (after all three parts)

```bash
# 1. errors.vps1 now gated (Part A)
curl -sS -o /dev/null -w "errors: %{http_code} → %{redirect_url}\n" https://errors.vps1.ocoron.com/
# Expected: 302 → https://auth.vps1.ocoron.com/?rd=...

# 2. monitor-public Gatus check now green (Part B)
curl -fsS https://status.vps1.ocoron.com/api/v1/endpoints/statuses 2>/dev/null \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print("monitor-public:", [e["results"][-1]["success"] for e in d if e["name"]=="monitor-public"])'
# Expected: monitor-public: [True]

# 3. Add an Authelia rule for a hypothetical admin service, verify ordering (Part C)
python3 -c "
import yaml
from fabrik.drivers.authelia import add_access_rule
# (manual review of the resulting configuration.yml — specific bypass must precede catchall)
"

# 4. Regression: T1-04 image-broker paired-pattern still works
curl -sS -o /dev/null -w "images UI: %{http_code}\n" https://images.vps1.ocoron.com/   # expect 302
curl -sS -o /dev/null -w "images API: %{http_code}\n" -H "X-Internal-Token: $INT_TOKEN" \
  https://images.vps1.ocoron.com/api/v1/health   # expect 200
```

### Rollback procedure

If Part A breaks errors.vps1 access (unlikely — the change only adds an auth gate, doesn't remove access):

```bash
ssh vps "sudo cp /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml.backup.t2-08-* \
        /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml"
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"
```

If Part B breaks the Gatus status board:

```bash
# Git-revert the gatus config edit; restart container.
ssh vps "cd /opt/gatus && git checkout config.yaml && sudo docker restart gatus-v8s4cokcwg0co4w8okkccc0w"
```

If Part C unit tests fail: revert the `add_access_rule` change; the live Authelia config remains correct from Part A's manual edit (no regression until the next refresh-infra call against the wrong service).

### Pre-flight checklist

- [ ] Authelia config backup taken (Part A)
- [ ] `docs/operations/vps-urls.md` line 59 decision aligned with Part A choice
- [ ] Gatus config repo cloned or mount path located (Part B)
- [ ] Grafana `/api/health` confirmed reachable internally (Part B)
- [ ] Lesson 56 read for context (Part C)

### Final Gate Instruction

```bash
python scripts/final_gate.py --lean --json
```

### Lessons Learnt field

If Part A/B execute cleanly: `none`.
If a surprise surfaces: new lesson covering the spec-vs-live drift class.

---

## Tier 2 done — convergence test

After all 10 items:

```bash
# 1. Audit reports zero MISSING (all drift cascade-fixed by Tier 1 + reconcile-all)
fabrik audit-registrars

# 2. State files exist for all deployed services
ls /opt/fabrik/.fabrik/state/*.json | wc -l
# Expect: 7+ files

# 3. State files include data_bearing flag
jq '.registrars_applied[] | {type, data_bearing}' /opt/fabrik/.fabrik/state/captcha.json
# Expect: postgres + meilisearch entries (if any) show data_bearing: true

# 4. data/projects.yaml shows deploy fields
grep -A 3 "last_apply_status" data/projects.yaml | head

# 5. Pre-commit blocks bad specs
echo "id: broken" > /tmp/broken.yaml
cp /tmp/broken.yaml specs/services/broken.yaml
git add specs/services/broken.yaml
git commit -m "test"
# Expect: hook fails, commit blocked
git reset HEAD specs/services/broken.yaml && rm specs/services/broken.yaml

# 6. Authelia audit timer scheduled (Option A or B)
ssh vps 'systemctl list-timers fabrik-audit-authelia.timer 2>/dev/null' || crontab -l | grep audit-authelia
# Expect: next run time within 7 days

# 7. Concurrent reconcile blocks correctly
fabrik reconcile-all --yes &
fabrik reconcile-all --yes
# Expect: second invocation waits up to 30s on per-spec lock, then errors cleanly

# 8. Partial destroy works
fabrik destroy specs/services/proxy.yaml --partial gatus --dry-run
# Expect: only gatus removal listed, other resources untouched
```

If all 8 pass, the reconciliation loop is closed.
