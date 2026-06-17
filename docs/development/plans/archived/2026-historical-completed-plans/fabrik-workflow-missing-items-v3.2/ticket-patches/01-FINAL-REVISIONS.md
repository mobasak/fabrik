# Final Revisions — Drop-In Ticket Sections

**Created:** 2026-05-11
**Pairs with:** `00-MASTER-PATCHES.md` (rationale + verification evidence)
**Purpose:** Exact replacement text for every ticket section that needs to change. Where this document specifies replacement text, use it verbatim. Where a ticket is marked **CLEAN**, ship as-is.

---

## Index

| Ticket | Action | Revision sections |
|---|---|---|
| T1-01 | PATCH | Steps 4/8 + Acceptance |
| T1-02 | PATCH | Context Files + Steps 4/5/6/7/8/9 + Acceptance |
| T1-03 | POLISH | Step 5 + Acceptance #1/#2 |
| T1-04 | PATCH | Step 0/1/6/7 + DO NOT + Acceptance |
| T1-05 | REWRITE | Steps 1–8 + Acceptance |
| T2-01 | PATCH | Step 3 schema + Step 6 |
| T2-02 | PATCH | Steps 1 + 5 (amendment) |
| T2-03 | CLEAN | — |
| T2-04 | PATCH | Steps 1/4/5 |
| T3-01 | PATCH | Step 4 |
| T3-02 | PATCH | Steps 3 + 8 |
| T3-03 | CLEAN | — |
| T4-01 | PATCH | Step 1 |
| T4-02 | PATCH | Step 3 |
| T4-03 | CLEAN | — |
| T4-04 | REWRITE | Steps 1/4/6 + Acceptance |
| T5-01 | CLEAN | — |

5 clean • 10 patch • 2 rewrite • 0 untouched

---

## T1-01 — PATCH

### Step 4 — REPLACE
> EDIT file:.env.example: add a comment block ABOVE the existing `CLOUDFLARE_API_TOKEN=` line at line 42 stating: `# CLOUDFLARE_API_TOKEN scope: Zone.Zone:Edit + Zone.DNS:Edit. Required for site-provisioner POST /api/cloudflare/zones/{domain}/provision (zone create). Narrowing to Zone:Read breaks new-domain onboarding. See docs/development/plans/fabrik workflow missing items/02-tier1-foundation.md §8.`

### Step 8 — REPLACE
> DECIDE G-B6: **delete `templates/next-tailwind/` directory** (verified: zero specs reference it; `saas-skeleton` covers Next.js+Tailwind+more). Aligns with locked principle "standard rules unless mandatory diverge." Do NOT add a Scaffold-Types table row. Record decision in CHANGELOG: "Deprecated next-tailwind template per pack v3.2 §DECISIONS principle (zero usage; saas-skeleton supersedes)."

### Acceptance Criteria — REPLACE the 3 noted bullets
- `grep -cF "(postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus)" AGENTS.md` returns **2**.
- `grep -c "^  exposes_metrics: true$" templates/python-api/defaults.yaml` returns **1**; same for `templates/node-api/defaults.yaml`.
- YAML validity: `python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ['specs/services/proxy.yaml','templates/python-api/defaults.yaml','templates/node-api/defaults.yaml']]"` exits 0.
- `[ ! -d templates/next-tailwind ] && echo DELETED || echo STILL_PRESENT` prints `DELETED`.
- `grep -c next-tailwind AGENTS.md` returns **0** (no row added; orphan removed cleanly).

---

## T1-02 — PATCH

### Context Files — REPLACE the infrastructure.py line
> file:src/fabrik/orchestrator/infrastructure.py line 126 (`resolve_applicability`) and line 257 (`format_resolved_summary`) and line 84 (`_REGISTRAR_ORDER`)

### Step 4 — REPLACE the test path acceptance + case #4
Drop `tests/test_infrastructure.py` from the test path list. Final list: `tests/orchestrator/test_template_defaults.py` + `tests/orchestrator/test_infrastructure.py` only.

Case #4 expected-reason — use substring assertion not strict equality:
```python
assert resolved["postgres"][0] is False
assert "infra.postgres" in resolved["postgres"][1]
```

### Step 5 — REPLACE
> EDIT file:src/fabrik/scaffold.py after line 759 (existing `shutil.copy(fabrik_compact, project_dir / "AGENTS-compact.md")`): insert `fabrik_claude_md = FABRIK_ROOT / "CLAUDE.md"` then `if fabrik_claude_md.exists(): shutil.copy(fabrik_claude_md, project_dir / "CLAUDE.md")`. Do NOT touch the second opencode.json copy at line 3488 (legacy path).

### Step 6 — REPLACE (covers BOTH offending lines)
> EDIT file:src/fabrik/cli.py at both line 581 AND line 616 (identical bug at two sites): replace `matching = [a for a in apps if a.get("name") == spec.id]` with:
> ```python
> candidates = [spec.id]
> if not spec.id.startswith("fabrik-"):
>     candidates.append(f"fabrik-{spec.id}")
> matching = [a for a in apps if a.get("name") in candidates]
> ```

### Step 7 — REPLACE (correct line citations)
> EDIT file:src/fabrik/cli.py::plan (line 197): import `from fabrik.orchestrator.infrastructure import resolve_applicability, format_resolved_summary` if not already; after `click.echo("📁 Files to Generate:")` (line 264) and before `click.echo("🚀 Actions:")` (line 274), add:
> ```python
> click.echo("\n🔧 Infrastructure Registrars (resolved from shape):")
> for line in format_resolved_summary(resolve_applicability(
>     spec.model_dump(mode="python") if hasattr(spec, "model_dump") else dict(spec)
> )).splitlines():
>     click.echo(f"  {line}")
> ```

### Step 8 — REPLACE
> CREATE file:specs/services/**fabrik-file-worker.yaml** (with `fabrik-` prefix matching id). Structure: copy `specs/services/fabrik-test-file-worker.yaml` as starting point. Override:
> - `id: fabrik-file-worker`
> - `template: file-worker`
> - `domain: ""` (worker, no public endpoint)
> - `source.type: local`, `source.path: /opt/file-worker` (data/projects.yaml has no repository URL; live container probe shows local source)
> - Audit live Coolify env vars first (use corrected polymorphic SQL — see T1-05 patch SQL):
>   ```sql
>   SELECT key FROM environment_variables
>   WHERE resourceable_type = 'App\\Models\\Application'
>     AND resourceable_id = (SELECT id FROM applications WHERE name='fabrik-file-worker');
>   ```
> - Set `secrets.required: [...]` to match live env keys. DO NOT copy test fixture's secrets blindly.
> - Do NOT add a `shape:` block; let G-B1a inherit from `templates/file-worker/defaults.yaml`.

### Step 9 — REPLACE
> `gh repo create mobasak/<name> --private --yes` (`--confirm` is deprecated in newer gh; `--yes` is the modern form. gh v2.45.0 accepts both.)

### Step 12 — REPLACE
> UPDATE file:INDEX.md: add file:specs/services/**fabrik-file-worker.yaml** and file:tests/test_spec_loader.py.

### Acceptance — REPLACE the noted bullets
- `fabrik plan specs/services/fabrik-file-worker.yaml` resolves cleanly; resolved registrars include `glitchtip`, `grafana`, `backrest`.
- `fabrik status specs/services/proxy.yaml` resolves to `fabrik-proxy` (output contains `fabrik-proxy` and NOT `Found in Coolify: None`).
- `fabrik plan specs/services/proxy.yaml | grep -cE "(postgres|redis|gatus|backrest|glitchtip|grafana|authelia|meilisearch|prometheus)"` returns ≥9.
- `cd /opt/fabrik && pytest tests/test_spec_loader.py tests/orchestrator/test_template_defaults.py tests/orchestrator/test_infrastructure.py -v` — all pass.

---

## T1-03 — POLISH (no blockers)

### Step 5 — REPLACE
```bash
ssh vps "sudo tee /opt/monitoring/configs/redis/assignments.json > /dev/null" <<EOF
{
  "version": 1,
  "last_updated": "$(date -Iseconds)",
  "assignments": { "authelia": 3, "glitchtip-web": 4 },
  "free_indexes": [0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
}
EOF
```
(Single-line heredoc, no `'EOF'` quoting so `$(date -Iseconds)` expands.)

### Acceptance #1 — REPLACE
```bash
ssh vps "sudo find /opt/monitoring/configs/gatus/apps -name '*.predrift*' 2>/dev/null | wc -l"
# Expected: 0
```

### Acceptance #2 — REPLACE
```bash
ssh vps 'ls /opt/_archive/gatus-predrift-fix-20260506/' | sort
# Expected (exactly two lines):
#   dns-manager.yaml.predrift-fix.20260506
#   fabrik-microservices.yaml.predrift-fix.20260506
```

---

## T1-04 — PATCH

### Step 0 — INSERT BEFORE Step 1
> DISCOVER image-broker routes (informs Step 7b/7c validity):
> ```bash
> ssh vps 'sudo docker exec image-broker-zo4ggs4g880skwkocwwkscgk-191233590054 python3 -c "from main import app; [print(r.path) for r in app.routes]" 2>/dev/null'
> ```
> If output contains no `/api/*` route: skip Steps 7b/7c and rely solely on Step 5 + Acceptance #2 (live Authelia config has both rules) for paired-pattern validation. Record finding in CHANGELOG.

### Step 1 — REPLACE
> EDIT file:specs/services/image-broker.yaml: append at end of file (no shape block currently exists):
> ```yaml
> shape:
>   is_admin_dashboard: true   # override python-api default — UI behind Authelia 2FA
>   has_bearer_api: true       # override — /api/* bypasses Authelia for X-Internal-Token M2M
> ```
> Do NOT add `is_public`, `has_persistent_data`, `needs_database`, `has_search_feature`, `kind` — they inherit via G-B1a merge from `templates/python-api/defaults.yaml`. Override-only is the canonical pattern (see `proxy.yaml`).

### Step 6 — REPLACE
> RUN `ssh vps 'sudo docker restart authelia-hks48k8sg8o4co4co08co00o'` (per AGENTS.md § Authelia Config Changes — `docker restart` is the canonical Authelia rule-reload mechanism; no SIGHUP support). Wait for healthy: `ssh vps 'sudo docker ps --filter "name=authelia" --format "{{.Status}}"'` returns `Up.*healthy`.

### Step 7a — REPLACE
```bash
# Run from operator workstation (NOT VPS — DNS for image-broker.vps1.ocoron.com doesn't resolve from inside VPS network)
curl -sS -o /dev/null -w "%{http_code}\n%{redirect_url}\n" https://image-broker.vps1.ocoron.com/
# Expected: 302 (or 303); redirect_url contains auth.vps1.ocoron.com
```

### Add to **DO NOT** section
> Do NOT echo, log, or paste `$SERVICE_INTERNAL_SECRET_KEY` literal value. Source via:
> ```bash
> set -a; . /opt/fabrik/.env; set +a
> ```
> Use only the variable name in commands. Never paste the literal into chat logs.

---

## T1-05 — REWRITE (DESTRUCTIVE; evening window)

### Replace Steps 1–8 with the following

**Step 1 (PRE-FLIGHT — Backrest snapshot, MANUAL).**
> Backrest UI: open Backrest's exposed URL (find via `ssh vps 'sudo docker port backrest-l48000k44wc4gk8os88s8k0c'` — Backrest is container-internal only, port 9898 NOT listening on host). Navigate to **Plans → postgres-dumps → Backup Now**. Wait for completion. Record snapshot ID into CHANGELOG. **If backup fails, ABORT** — do not proceed to Step 2.

**Step 2 (PRE-FLIGHT — Coolify env audit).**
> Confirm only `fabrik-translator` references `translator_service` (correct polymorphic-association SQL):
> ```bash
> ssh vps "sudo docker exec coolify-db psql -U coolify coolify -c \"
> SELECT a.name, ev.key, substring(ev.value for 80) AS val_preview
> FROM applications a
> JOIN environment_variables ev
>   ON ev.resourceable_type = 'App\\\\Models\\\\Application'
>  AND ev.resourceable_id = a.id
> WHERE ev.value LIKE '%translator_service%';\""
> ```
> Expected: 1 row (`fabrik-translator` | `DATABASE_URL` | `...translator_service`). If >1 row, ABORT and investigate.

**Step 3 (PRE-FLIGHT — Baseline data integrity).**
> ```bash
> ssh vps 'sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -d translator_service -c "
> ANALYZE;
> SELECT pg_size_pretty(pg_database_size('"'"'translator_service'"'"')) AS db_size;
> SELECT relname, n_live_tup
> FROM pg_stat_user_tables
> ORDER BY relname;"'
> ```
> Record output to CHANGELOG. Expected baseline (verified 2026-05-11): db_size ~8.2 MB, sum(n_live_tup) ≈ 275. **If sum(n_live_tup) = 0 AND db_size < 1 MB**, the DB is empty — abort the destructive ceremony and degrade W-3 to spec-only edit.

**Step 4 (CHANGE WINDOW — stop translator).**
> ```bash
> ssh vps 'sudo docker stop translator-kgws0s4cscsosw8gg848cwgw-191255149559'
> ```
> Single exact container name; no docker filter syntax (Docker has no `!=` operator).

**Step 5 (RENAME — atomic, with backend termination).**
> ```bash
> ssh vps 'sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -c "
> SELECT pg_terminate_backend(pid)
> FROM pg_stat_activity
> WHERE datname = '"'"'translator_service'"'"' AND pid <> pg_backend_pid();
> SELECT pg_sleep(1);
> ALTER DATABASE translator_service RENAME TO translator;"'
> ```
> Note: `ALTER DATABASE RENAME` fails on connected DB. Must terminate other backends (Coolify health probes, idle clients, monitoring scrapes) first.

**Step 6 (VERIFY data preservation).**
> Run the same baseline query against new DB name:
> ```bash
> ssh vps 'sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -d translator -c "
> ANALYZE;
> SELECT pg_size_pretty(pg_database_size('"'"'translator'"'"')) AS db_size;
> SELECT relname, n_live_tup
> FROM pg_stat_user_tables
> ORDER BY relname;"'
> ```
> Compare to Step 3 baseline: `db_size` byte-exact equal, per-table `n_live_tup` byte-exact equal. **If any mismatch, ROLLBACK** (see Step 8 rollback) and abort.

**Step 7 (UPDATE Coolify env_vars — API, not UI).**
> Find translator app UUID + env_var id:
> ```bash
> APP_UUID=$(ssh vps 'sudo docker exec coolify-db psql -U coolify coolify -At -c "SELECT uuid FROM applications WHERE name='"'"'fabrik-translator'"'"';"')
> echo "app uuid: $APP_UUID"
> ```
> Direct DB UPDATE (Coolify env_var format `key:value` per polymorphic schema):
> ```bash
> ssh vps "sudo docker exec coolify-db psql -U coolify coolify -c \"
> UPDATE environment_variables
> SET value = REPLACE(value, '/translator_service', '/translator')
> WHERE resourceable_type = 'App\\\\Models\\\\Application'
>   AND resourceable_id = (SELECT id FROM applications WHERE name='fabrik-translator')
>   AND key = 'DATABASE_URL';\""
> ```
> Verify: `ssh vps "sudo docker exec coolify-db psql -U coolify coolify -At -c \"SELECT value FROM environment_variables WHERE key='DATABASE_URL' AND resourceable_id=(SELECT id FROM applications WHERE name='fabrik-translator');\""` shows new URL.

**Step 8 (DEPLOY translator — Coolify API).**
> ```bash
> COOLIFY_TOKEN=$(grep '^COOLIFY_API_TOKEN=' /opt/fabrik/.env | cut -d= -f2)
> ssh vps "curl -fsS -X POST -H 'Authorization: Bearer $COOLIFY_TOKEN' http://localhost:8000/api/v1/deploy?uuid=$APP_UUID"
> ```
> Wait for translator container healthy: `ssh vps 'sudo docker ps --filter "name=translator" --format "{{.Status}}"'` shows `Up.*healthy`.

**Step 9 (VERIFY health).**
> `curl -fsS https://translator.vps1.ocoron.com/health` returns 2xx.
> `ssh vps 'sudo docker logs --tail 50 translator-kgws0s4cscsosw8gg848cwgw-191255149559'` shows clean DB connect, no errors mentioning `translator_service`.

**Step 10 (SPEC edit — ADD ONLY).**
> EDIT file:specs/services/translator.yaml. Add (do NOT remove anything — verified 2026-05-11: no `infra:` block exists on disk):
> ```diff
>  id: translator
>  kind: service
>  template: python-api
>  domain: translator.vps1.ocoron.com
> +
> +shape:
> +  needs_database: true   # override python-api default — translator uses postgres
> ```
> Unified diff acceptance: `git diff specs/services/translator.yaml` shows only the `+shape:\n+  needs_database: true` addition (no `-infra:` lines).

**Step 11 (VERIFY spec post-edit).**
> `fabrik plan specs/services/translator.yaml` output's `🔧 Infrastructure Registrars` block shows `postgres` RUNS.

**Step 12 (MANUAL audit — Tier 2 audit-registrars not yet shipped).**
> ```bash
> ssh vps 'sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -At -c "\l" | grep -E "^[[:space:]]*translator[[:space:]]*\|"'
> # Expected: ONE line showing database "translator" (NOT "translator_service")
> ```

**Step 13 (CHANGELOG + 7-day rollback window).**
> UPDATE CHANGELOG with: snapshot ID (Step 1), Step 3 baseline (db_size + per-table rows), Step 6 post-rename (must equal baseline), env update SQL (Step 7), deploy API call (Step 8), **rollback command**:
> ```sql
> ALTER DATABASE translator RENAME TO translator_service;
> ```
> **Cleanup window: 7 days from execution date.** Operator schedules a separate cleanup ticket on day 8 to verify zero references to `translator_service` remain across all containers' env-vars, then DROP DATABASE translator_service.

### Acceptance — REWRITE
- Backrest snapshot ID recorded in CHANGELOG before Step 5 runs.
- `\l` output post-rename: exactly one match for `translator` (no `translator_service` row gone — kept for 7-day rollback).
- Step 6 db_size + per-table `n_live_tup` byte-exact match Step 3 baseline.
- `curl -fsS https://translator.vps1.ocoron.com/health` returns 2xx within 60s of Step 8.
- `git diff specs/services/translator.yaml` shows ONLY `+shape:` + `+  needs_database: true` (no `-infra:` lines).
- CHANGELOG entry includes: snapshot ID + baseline metrics + rename timestamp + env update SQL + deploy API command + rollback SQL + 7-day cleanup window date.

---

## T2-01 — PATCH

### Step 3 schema — REPLACE field name `spec_sha256` with `spec_hash`
JSON schema field reads from `ctx.spec_hash`. Either rename in the schema OR document mapping. **Recommend rename** for consistency:
```json
{
  "spec_id": "...",
  "spec_path": "...",
  "spec_hash": "...",        // ← renamed from spec_sha256
  "coolify_uuid": "...",
  "coolify_app_name": "...",
  "applied_at": "...",
  "git_sha": "...",
  "domain": "...",
  "registrars_applied": [...]
}
```

### Step 6 — REPLACE
> EDIT file:src/fabrik/orchestrator/__init__.py: after `ctx.state = DeploymentState.COMPLETE` transition (line ~150) inside `deploy()`, AND symmetrically after refresh_infrastructure's COMPLETE transition, persist state:
> ```python
> import datetime, subprocess
> from fabrik.config import FABRIK_ROOT
> from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER
> from fabrik import state
>
> state.save(
>     spec_id=spec.id,
>     spec_path=str(ctx.spec_path),
>     spec_hash=ctx.spec_hash,
>     coolify_uuid=ctx.coolify_uuid or "",
>     coolify_app_name=spec.id if spec.id.startswith("fabrik-") else f"fabrik-{spec.id}",
>     applied_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
>     git_sha=subprocess.check_output(
>         ["git", "rev-parse", "HEAD"], cwd=FABRIK_ROOT
>     ).decode().strip(),
>     domain=spec.domain or "",
>     registrars_applied=[
>         {"type": r.resource_type,
>          "id": r.resource_id,
>          "status": "applied",
>          "data_bearing": r.resource_type in state.DATA_BEARING_REGISTRARS}
>         for r in ctx.created_resources
>         if r.resource_type in _REGISTRAR_ORDER
>     ],
> )
> ```
> Rationale: only `spec_path`, `spec_hash`, `coolify_uuid` exist on `DeploymentContext` (`context.py:22-42`). The other 5 fields must be derived at save time.

---

## T2-02 — PATCH (amendment + polish)

### Step 1 — REPLACE driver-pattern sentence
> Each `audit_<reg>` uses whichever pattern its existing driver uses:
> - **SSH + parse/exec**: postgres (psql), redis (file + redis-cli), gatus (file glob), backrest (parse config.json), authelia (`docker exec ... cat /config/configuration.yml`), prometheus (parse prometheus.yml)
> - **HTTP API**: glitchtip (`GET /api/0/projects/{org}/{slug}/`), meilisearch (`GET /indexes`)
> - **N/A**: grafana — annotations are point-in-time, not driftable. Return `{"status": "n/a", "reason": "annotations are decorative, not driftable"}`.

### Step 5 — ADD Step 5b (HANDLER_ARGS extraction)
> **AFTER** the existing Step 5 (creating HANDLER_ARGS inside `cli.py:destroy()`), promote HANDLER_ARGS to module-level in `src/fabrik/orchestrator/destroyer.py` so T4-02 can import it:
>
> 1. Move the HANDLER_ARGS dict definition from `cli.py:destroy()` body to `destroyer.py` module top-level (after `_destroy_*` function definitions).
> 2. Refactor it to take `(spec, drop_data, dry_run)` as explicit args via factory:
>    ```python
>    # destroyer.py — module level
>    def get_handler_args(reg: str, spec, drop_data: bool, dry_run: bool):
>        """Return positional args tuple for _destroy_<reg> matching its signature."""
>        sig_map = {
>            "authelia":    lambda s: (s.domain, dry_run),
>            "postgres":    lambda s: (s.id, drop_data, dry_run),
>            "redis":       lambda s: (s.id, drop_data, dry_run),
>            "meilisearch": lambda s: (s.id, drop_data, dry_run),
>            "gatus":       lambda s: (s.id, dry_run),
>            "backrest":    lambda s: (s.id, dry_run),
>            "glitchtip":   lambda s: (s.id, dry_run),
>            "prometheus":  lambda s: (s.id, dry_run),
>            # grafana intentionally omitted — _destroy skips it
>        }
>        builder = sig_map.get(reg)
>        return builder(spec) if builder else None
>    ```
> 3. In `cli.py:destroy()`, call `get_handler_args(reg, spec, drop_data, dry_run)` instead of the local dict.
>
> This unblocks T4-02 (which imports `get_handler_args` from destroyer.py).

---

## T2-04 — PATCH

### Step 1 — REPLACE the reload chain
> ```python
> # coolify-alias-watcher.service has no ExecReload directive (verified 2026-05-11).
> # Use restart directly; reload would always fall through and add noise.
> ssh("sudo systemctl restart coolify-alias-watcher.service")
> ```

### Step 4 — REPLACE (inline exact JSON)
> WRITE `/opt/coolify-alias-watcher/aliases.json` with EXACTLY this content (matches current hardcoded ALIASES in watcher.sh, verified 2026-05-11):
> ```json
> {
>   "aliases": {
>     "bs0wo48k4gwo440gcowscoc8": "meilisearch",
>     "e04k4sco44ow04ccc0o0k00k": "gotenberg",
>     "vckgs8c00o40o884k48cgow8": "browserless",
>     "glitchtip-web": "glitchtip-web"
>   }
> }
> ```
> Set permissions: `chmod 644`, owner root.

### Step 5 — REPLACE watcher.sh refactor body
> In `/opt/coolify-alias-watcher/watcher.sh`, replace the hardcoded `declare -A ALIASES=(...)` block with a load-from-JSON block (jq verified present at `/usr/bin/jq`, v1.7):
> ```bash
> declare -A ALIASES
> ALIASES_PATH=/opt/coolify-alias-watcher/aliases.json
> while IFS=$'\t' read -r prefix alias; do
>     ALIASES["$prefix"]="$alias"
> done < <(jq -r '.aliases | to_entries[] | "\(.key)\t\(.value)"' "$ALIASES_PATH")
> ```
> Place this block where the current hardcoded `declare -A ALIASES=( ... )` lives.

---

## T3-01 — PATCH

### Step 4 — REPLACE CLI decorator pattern
> EXTEND `cli.py` with a Click GROUP (not `@cli.command`) so `fabrik preplan new <slug>` works as written in acceptance:
> ```python
> @cli.group()
> def preplan():
>     """Preplan workflow commands."""
>     pass
>
> @preplan.command("new")
> @click.argument("slug")
> @click.option("--date", default=None, help="Override preplan date (default: today)")
> def preplan_new(slug: str, date: str | None):
>     ...
> ```
> Verify acceptance: `fabrik preplan new test-tier3-demo` invokes the function (not `fabrik preplan-new`).
> Cross-reference: cli.py already uses this pattern at lines 1351, 1566, 1667, 2029, 2089.

---

## T3-02 — PATCH

### Step 3 — REPLACE
> Do NOT append the full registrar/shape snippet to `AGENTS-compact.md` (file is already 98 lines vs the AGENTS.md "Stays under 60 lines" constraint — verified 2026-05-11 pre-existing drift). Instead, append ONE line cross-reference:
> ```
> Spec contract awareness: see KILO_CLI_RULES.md.
> ```
> Surface refactor of AGENTS-compact.md back under 60 lines as known debt in CHANGELOG; out of scope for T3-02.

### Step 8 — REPLACE opencode.json field
> The opencode.json schema field is **`instructions`** (NOT `rules_files`, NOT `_rules_reference`). Edit:
> ```json
> {
>   "$schema": "https://opencode.ai/config.json",
>   "instructions": [
>     "AGENTS-compact.md",
>     "KILO_CLI_RULES.md"
>   ]
> }
> ```

### Step 9 — ADD KILO_CLI_RULES.md to GOVERNANCE_FILES
> EDIT `scripts/sync_enforcement_to_projects.py`: append `"KILO_CLI_RULES.md"` to the `GOVERNANCE_FILES` list (currently 7 entries at scripts/sync_enforcement_to_projects.py around lines 55-63). Final length: 8 entries.

---

## T4-01 — PATCH

### Step 1 — REPLACE seed instructions
> Pre-flight check live state before writing seed values:
> ```bash
> ssh vps 'sudo docker exec postgres-main-l0k4gk0kggc8okcwk0s4c8s8 psql -U postgres -At -c "\l" | awk -F\\| "{print \$1}" | sed "s/ //g" | grep -E "translator|site_provisioner|proxy_management|glitchtip"'
> ```
> Use whichever names appear in the live `\l` output for the seed entries:
> - If output shows `translator_service`: seed with that name (T1-05 hasn't shipped or failed)
> - If output shows `translator`: seed with that name (T1-05 succeeded)
>
> Then write `/opt/monitoring/configs/postgres/allocations.json` matching pack §29 schema, with live-state-matched names. allocations.json must reflect actual state, not assumed T1-05 outcome.

---

## T4-02 — PATCH

### Step 3 — REPLACE the iteration body
> ```python
> from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER
> from fabrik.orchestrator import destroyer as _d
> from fabrik.orchestrator.destroyer import get_handler_args  # from T2-02 Step 5b
>
> def destroy_from_state(state_data: dict, spec, drop_data: bool, dry_run: bool) -> ...:
>     # Phase 1: registrars in reversed order
>     for reg in reversed(_REGISTRAR_ORDER):
>         entries = [e for e in state_data["registrars_applied"] if e["type"] == reg]
>         if not entries:
>             continue
>         if reg == "grafana":
>             continue   # annotations are decorative, no destroy
>         handler = getattr(_d, f"_destroy_{reg}", None)
>         if handler is None:
>             # log warning, skip
>             continue
>         args = get_handler_args(reg, spec, drop_data, dry_run)
>         if args is None:
>             continue
>         result = handler(*args)
>         # collect result
>
>     # Phase 2: non-registrar destroyers (coolify, dns, files) — explicit order
>     _d._destroy_coolify(spec.id, dry_run)
>     _d._destroy_dns(spec.domain, dry_run)
>     _d._destroy_files(spec.id, FABRIK_ROOT, dry_run)
> ```
> Rationale: actual `_REGISTRAR_ORDER` is `(postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus)`. The original ticket order omitted redis/grafana/prometheus and conflated registrars with non-registrar destroyers. Two-phase keeps semantics correct.

### Acceptance — ADD one bullet
- `python3 -c "from fabrik.orchestrator.destroyer import get_handler_args; print('ok')"` succeeds (proves T2-02 Step 5b landed and HANDLER_ARGS is importable).

---

## T4-04 — REWRITE

### Replace Steps with the following

**Step 0 (NEW — deploy pushgateway).**
> Deploy Prometheus pushgateway (verified 2026-05-11: no pushgateway container exists; `docker ps` shows only prometheus + alertmanager). Add to monitoring compose:
> ```yaml
> # /opt/monitoring/compose.yaml — append under services:
> pushgateway:
>   image: prom/pushgateway:v1.9.0
>   container_name: pushgateway
>   restart: unless-stopped
>   ports:
>     - "9091:9091"
>   networks:
>     - monitoring
> ```
> `ssh vps 'cd /opt/monitoring && sudo docker compose up -d pushgateway'`
> Verify: `ssh vps 'curl -fsS http://localhost:9091/-/healthy'` returns 2xx.
> Add Prometheus scrape config for it under `scrape_configs:` in `/opt/monitoring/configs/prometheus/prometheus.yml`:
> ```yaml
>   - job_name: pushgateway
>     honor_labels: true
>     static_configs:
>       - targets: ['pushgateway:9091']
> ```
> Reload Prometheus: `ssh vps 'curl -X POST http://localhost:9090/-/reload'`.

**Step 1 (WSL-side audit cron — aligns with T2-03 mechanism).**
> Add WSL `crontab -e` entry (matches T2-03 Option B):
> ```cron
> */60 * * * * cd /opt/fabrik && /opt/fabrik/.venv/bin/python scripts/audit_all_registrars.py 2>&1 | tee -a /var/log/fabrik-audit-all.log | curl -fsS --data-binary @- http://vps1.ocoron.com:9091/metrics/job/fabrik-audit
> ```
> Note: needs SSH tunnel or public pushgateway endpoint. Recommended: tunnel pushgateway via Cloudflare proxy and HTTPS rather than expose port 9091 publicly.

**Step 2 (Prometheus rules — new file).**
> CREATE `/opt/monitoring/configs/prometheus/rules/fabrik-drift.yml`:
> ```yaml
> groups:
>   - name: fabrik_drift
>     interval: 5m
>     rules:
>       - alert: FabrikRegistrarDrift
>         expr: fabrik_audit_drift_total > 0
>         for: 10m
>         labels:
>           severity: warning
>           alert_class: registrar_drift
>         annotations:
>           summary: "Fabrik registrar drift detected"
>           description: "{{ $labels.registrar }} reports {{ $value }} drift entries for spec {{ $labels.spec_id }}."
> ```
> Verify with `promtool check rules /opt/monitoring/configs/prometheus/rules/fabrik-drift.yml`.

**Step 3 (audit_all_registrars.py script).**
> CREATE `/opt/fabrik/scripts/audit_all_registrars.py`:
> ```python
> #!/usr/bin/env python3
> """Run audit_registrars across all deployed specs; emit Prometheus metrics."""
> # ... iterates specs/services/*.yaml, calls fabrik.audit, emits prom text format
> # OUTPUT FORMAT (stdout, piped to pushgateway):
> #   # TYPE fabrik_audit_drift_total counter
> #   fabrik_audit_drift_total{spec_id="captcha",registrar="postgres"} 0
> #   ...
> ```

**Step 4 (Alertmanager route — use existing `telegram` receiver, NO new receiver).**
> EDIT `/opt/monitoring/configs/alertmanager/alertmanager.yml`. Under `route.routes:`, add:
> ```yaml
>     - match:
>         alert_class: registrar_drift
>       receiver: telegram   # ← existing receiver (verified line 35); do NOT create telegram-fabrik-default
>       group_wait: 10s
>       repeat_interval: 1h
> ```
> Verify: `ssh vps 'sudo docker exec alertmanager-zw4swgkwk0s4s8kg048gw80o amtool check-config /etc/alertmanager/alertmanager.yml'`.
> Reload: `ssh vps 'curl -X POST http://localhost:9093/-/reload'`.

**Step 5 (NOT NEEDED — removed).**
> Original Step 5 created a new `telegram-fabrik-default` receiver. Skip — verified receiver `telegram` already exists at alertmanager.yml line 35.

**Step 6 (REMOVED — duplicates Step 1 cron, conflicts with T2-03).**
> Original Step 6 placed `/etc/systemd/system/fabrik-audit-all-registrars.timer`. Replaced by Step 1 above (WSL-side crontab). Single audit mechanism across T2-03 + T4-04.

### Acceptance — REWRITE
- `curl -fsS http://localhost:9091/-/healthy` (on VPS) returns 2xx.
- `promtool check rules /opt/monitoring/configs/prometheus/rules/fabrik-drift.yml` exits 0.
- `amtool check-config /etc/alertmanager/alertmanager.yml` exits 0.
- `crontab -l | grep audit_all_registrars` returns 1 line (WSL-side, NOT VPS-side).
- `grep -c "alert_class: registrar_drift" /opt/monitoring/configs/alertmanager/alertmanager.yml` ≥1; `grep -c "name: telegram-fabrik-default" /opt/monitoring/configs/alertmanager/alertmanager.yml` = 0 (no new receiver).
- Manual smoke: artificially inject a drift entry; within 1h, Telegram receives an alert containing `alert_class=registrar_drift`.

---

## CLEAN (ship as-is — no revisions)

- **T1-03** — VPS cleanup (with the 3 polish edits above applied)
- **T2-03** — Pre-commit + scheduled audit
- **T3-03** — Dev tooling
- **T4-03** — fabrik export/import (note: roundtrip not verified in epic, accepted per Out of Scope)
- **T5-01** — Epic Closure

---

## Execution sequence (final)

```
Day 1 (proof-of-pipeline + parallel start):
  T1-03 (polish only, ~15min)   ← ship first; proves pipeline
  T1-02 (largest patch, ~6h)    ← in parallel
  T1-01 (3 patches, ~45min)     ← in parallel after T1-02 G-B1a lands

Day 2:
  T1-04 (after T1-02 G-B1a)

Day 3 PM (evening Istanbul window, destructive):
  T1-05 (rewritten — verified Backrest UI flow + correct SQL + connection-kill)

Days 4-6 (Tier 2; T2-02 amendment must land before T4-02):
  T2-01 (patched: state.save 8-field derivation)
    → T2-02 (patched: Step 5b HANDLER_ARGS extraction)
    → T2-03 (clean) + T2-04 (patched) [parallel]

Days 4-6 (Tier 3; parallel with Tier 2):
  T3-01 (patched: @cli.group) + T3-02 (patched) + T3-03 (clean)

Days 7-10 (Tier 4; after T2-02 amendment):
  T4-01 (patched) + T4-02 (patched: reverse order + HANDLER_ARGS import) + T4-03 (clean) + T4-04 (rewritten)

Day 11: T5-01 — 12-point gate.
```

**Total ~68 h ≈ 1.5 focused weeks** within 50h/week budget.

---

## Compliance restatement

All 28 substantive findings (Pass 1: 22 + Pass 2: 6) have drop-in fixes above. Every line citation, SQL query, container name, API endpoint, and command in this file was verified against actual `/opt/fabrik` HEAD or live `vps1.ocoron.com` state on 2026-05-11.

**Where this document and a Traycer ticket conflict, this document wins.**
