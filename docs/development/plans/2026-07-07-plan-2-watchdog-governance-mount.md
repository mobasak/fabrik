# Watchdog governance-mount materialization (hub side) — implementation plan

**Status:** IN-PROGRESS
**Spec:** [docs/superpowers/specs/2026-07-07-watchdog-governance-mount-design.md](../../superpowers/specs/2026-07-07-watchdog-governance-mount-design.md) (CONVERGED)
**Author:** Claude Opus 4.8 (hub) · from chat 2026-07-07

**Pass Ledger (`/fabrik-plan-review` — fixed point, looped solo: ≤4 units, no subagents dispatched):**

| Pass | axes re-grounded (claims · gates · interfaces · completeness) | edits | plan md5 (start → end) |
|-----:|---|---:|---|
| 1 | `_RenderContext` field slot + memory-limits cite + toolchain (pytest 9.0.2/mypy 1.19.1 present) + docs | 4 (resolved File-Scope placeholder → `vps-complete-inventory.md:133`) | `2dc1e2d0…` → `b9f963d3…` |
| 2 | structural pillars — `/fabrik-review` at every phase boundary | 1 (added whole-plan `/fabrik-review` to Phase B) | `b9f963d3…` → `7ceb732b…` |
| 3 | gate hygiene (no `fabrik` gates), final-gate present, placeholders, review coverage | **0** | `7ceb732b…` → `7ceb732b…` ✓ → **CONVERGED** |

Ship the project's governance set to a dedicated per-project VPS path at `fabrik apply` and expose it to the watchdog sidecar as a read-only `/governance` mount + `WATCHDOG_GOVERNANCE_MOUNT` env, so fabrik-lib's `_materialize_conventions` has a reliable source (the current `/opt/<id>:/project:ro` mount is hollow — VPS deploy excludes gitignored `.windsurf/rules/`). **Option B** from the spec (dedicated mount, not push-into-`/opt/<id>`).

## What we already agreed (from the CONVERGED spec + this chat)

- **Approach = Option B** (dedicated `/governance:ro` mount + `WATCHDOG_GOVERNANCE_MOUNT`), rejecting Option A (push into `/opt/<id>` — collides with `git pull` where governance files are tracked, hollow where gitignored; tracking is inconsistent across scaffold vintages) and symlink/git-archive (don't survive scp/bind; git-archive omits gitignored files).
- **Governance contract** (fabrik-lib defines the file list): `CLAUDE.md` + `AGENTS.md` + `.windsurf/rules/**/*.md`, laid out at the mount root as `/governance/{CLAUDE.md,AGENTS.md,.windsurf/rules/**}`.
- **VPS path:** `/var/lib/watchdog-governance/<project_id>/` (dedicated host dir, outside any deploy tree).
- **Source:** the hub's local WSL project tree `/opt/<id>/` (confirmed to carry the set — CLAUDE.md + AGENTS.md + 49 rule files).
- **Gate:** the existing `should_run["watchdog"]` predicate; **no `shape.*` change**.
- **Always-on** (not Tier-D-gated): mount ships for every watchdog deploy; `_materialize_conventions` consumes it only on Tier-D.
- **Non-secret:** governance files are rules/contracts → `chmod 644` / dir `755`; the `core/35-security-auth` chmod-600/backup path does NOT apply.
- **Fail-soft:** missing source → skip the mount+env (never emit a `/governance` volume pointing at a non-existent host dir); fabrik-lib's materialize falls back to `/project` when the env is unset.
- **fabrik-lib coordination** (user's Q2 — see handoff): the hub produces the `/governance` layout above and sets `WATCHDOG_GOVERNANCE_MOUNT=/governance`; fabrik-lib's `_materialize_conventions` reads that env if set, else `/project`, and globs the three paths.

**Branch: RICH** — spec-fed; goal + approach + code targets pinned and grounded.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/30-ops.md` (ACTIVE) | Docker/deploy standards — bind-mount + compose overlay discipline | `select_rules.py` → ACTIVE |
| `.windsurf/rules/core/35-security-auth.md` (ACTIVE) | secret/sensitive-file handling — **governance files are NON-secret**, so the `chmod 600` + backup path does NOT apply; RO mount, world-readable is correct | `35-security-auth.md` (sensitive-file rules scoped to secrets/keys) |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | what to test — highest-risk path first (the fail-soft + conditional mount/env) | ACTIVE |
| `.windsurf/rules/core/50-code-review.md` (ACTIVE) | self-review / gate / reusability discipline for the phase close | ACTIVE |
| `fabrik-lib` `watchdog/` module — `_materialize_conventions` | **VENDOR (coordinate)** — consumer half; reads `WATCHDOG_GOVERNANCE_MOUNT` if set else `/project`, globs `CLAUDE.md`/`AGENTS.md`/`.windsurf/rules/*.md`. Built in parallel by fabrik-lib. | `/opt/fabrik-lib/README.md:63` (`watchdog/`) |
| `fabrik.drivers.ssh` — `scp_to_vps`, `ssh` | **VENDOR (fabrik core)** — the ship + remote-exec primitives; already used by `_build_image` | `src/fabrik/drivers/ssh.py:89` `scp_to_vps(local_path, remote_path, timeout=30, dry_run=False)` |
| `AGENTS.md` — watchdog sidecar topology | the sidecar is a per-project compose overlay on the `fabrik` net; driver = `fabrik.drivers.watchdog`; deploy is hub-owned (trigger-not-execute) | `AGENTS.md` (watchdog driver section) |
| `specs/services/<id>.yaml` `shape.*` | **no flag change** — watchdog-deployer internals, gated on existing `should_run["watchdog"]` | `infrastructure.py:388` (read the predicate; inspection, not `fabrik plan`) |

**fabrik-lib consult:** done — the materialize capability is fabrik-lib's (coordinate, no fork); the ship/render are fabrik-core primitives + seam edits. **No new fabrik-lib candidate** (hub-specific deploy glue bound to Fabrik's VPS layout — fails the generic/≥2-types bar).

## Global Constraints (inherited by the phase)

- **Repo boundary:** edits in `/opt/fabrik` only (fabrik core). The `scp`/`ssh sudo` to the VPS at apply is the same trust boundary the driver already uses.
- **VPS path:** `/var/lib/watchdog-governance/<project_id>/`, mounted `:/governance:ro`; env `WATCHDOG_GOVERNANCE_MOUNT=/governance`.
- **Governance files are non-secret:** `chmod 644` files / `755` dir; RO mount; never the `chmod 600` credential path.
- **Fail-soft, never crash the deploy:** any error shipping governance → log a warning, skip the mount+env for that project (degrades to today's `/project` fallback), never abort `provision()`.
- **Idempotent + refresh-on-apply:** re-shipping overwrites the VPS governance dir wholesale each apply (governance drifts with sync); never merge.
- **Gate:** `should_run["watchdog"]` — same predicate as the WATCHDOG_DB_URL_RO/RW injection; no `shape.*` change.
- **Infra invariants:** `fabrik` external network, per-service `deploy.resources.limits.memory` (unchanged — this touches the existing sidecar service, whose limits are already set at `watchdog.py:724-729`), no host `ports:`.
- **Shared-master:** explicit-path staging, provenance trailers, CHANGELOG atop `[Unreleased]`.

## Phase A — `_push_governance` + conditional mount/env wiring — ✅ EXECUTED 2026-07-07 (13 tests, mypy clean, 156 watchdog tests green, review clean)

**Responsibility:** one cohesive change in the watchdog driver: ship the governance set to the VPS and conditionally add the mount + env to the sidecar compose, fail-soft.

**Files:**
- `src/fabrik/drivers/watchdog.py` (**modify**) —
  - `_RenderContext` (dataclass ~`:330-370`): add field `governance_mount_ready: bool = False`.
  - New method `_push_governance(self, rctx) -> bool` (mirrors `_build_image`'s tar→`ssh mkdir -p`→`scp_to_vps`→`sudo tar -xzf … && rm` pattern, `:633-655`): tar `/opt/<id>/{CLAUDE.md,AGENTS.md,.windsurf/rules}` (skip any member that doesn't exist, arcname-flat at root so the mount presents `/governance/CLAUDE.md` etc.), ship to a `/tmp` staging path, `sudo mkdir -p /var/lib/watchdog-governance/<id>`, `sudo tar -xzf <staging> -C /var/lib/watchdog-governance/<id>`, `sudo chmod -R a+rX` the dir, `rm` staging. Returns `True` on success; on ANY exception logs a warning and returns `False`. If NO governance member exists locally, return `False` without shipping.
  - `provision()` (`:381`): call `rctx.governance_mount_ready = self._push_governance(rctx)` **after** `self._build_image(rctx)` (`:418`) and before `self._push_overlay(rctx)` (`:419`) — the overlay reads the flag.
  - `_push_overlay` volumes list (`:695-714`): append `f"/var/lib/watchdog-governance/{rctx.project_id}:/governance:ro"` **only if** `rctx.governance_mount_ready`.
  - `_render_env` (`:762`): set `env["WATCHDOG_GOVERNANCE_MOUNT"] = "/governance"` **only if** `rctx.governance_mount_ready`.
- `tests/test_watchdog_governance_mount.py` (**create**).

**Interfaces — Produces:** `_push_governance(rctx) -> bool`; `_RenderContext.governance_mount_ready: bool`; compose volume `/var/lib/watchdog-governance/<id>:/governance:ro` (present iff ready); env `WATCHDOG_GOVERNANCE_MOUNT=/governance` (present iff ready). **Consumes:** `scp_to_vps`/`ssh` (`fabrik.drivers.ssh`), `tarfile` (both already imported, `:79,:87`); the fabrik-lib consumer (`_materialize_conventions`) reads the produced env + mount (cross-repo, coordinated).

**Steps (highest-risk test FIRST — the conditional mount/env + fail-soft is the risk):**
1. **Write failing test** `tests/test_watchdog_governance_mount.py` (mock `ssh`, `scp_to_vps`, and the local source tree via `tmp_path` monkeypatching the source root):
   - `_push_governance` with a populated source → returns `True`; asserts the `scp_to_vps` + `sudo tar -xzf … -C /var/lib/watchdog-governance/<id>` + `chmod` calls fired with the right paths; the tar contains `CLAUDE.md`, `AGENTS.md`, `.windsurf/rules/...`.
   - `_push_governance` with an empty/absent source → returns `False`, **no** `scp` call.
   - `_push_governance` where `ssh` raises → returns `False` (fail-soft), no exception propagates.
   - `_push_overlay` with `governance_mount_ready=True` → volumes list contains `/var/lib/watchdog-governance/<id>:/governance:ro`; with `False` → it does NOT.
   - `_render_env` with `ready=True` → `WATCHDOG_GOVERNANCE_MOUNT=/governance` present; with `False` → absent.
   - Run → **RED** (methods/flag don't exist yet).
2. Implement to green (the 5 edits above).
   - Gate: `python -m pytest tests/test_watchdog_governance_mount.py -q` → all pass.
   - Gate: `python -c "import ast; ast.parse(open('src/fabrik/drivers/watchdog.py').read()); print('ok')"` → `ok`.
   - Gate: `python -m mypy src/fabrik/drivers/watchdog.py 2>&1 | tail -3` → no new errors on the changed lines.
   - Gate (inspection, not `fabrik apply`): `python -c "import re,inspect; from fabrik.drivers import watchdog; s=inspect.getsource(watchdog); assert 'WATCHDOG_GOVERNANCE_MOUNT' in s and '/var/lib/watchdog-governance' in s and '_push_governance' in s; print('wiring present')"` → `wiring present`.
3. **Doc-sync (explicit, per Doc Sync Matrix):**
   - `CHANGELOG.md` — entry atop `[Unreleased]`.
   - `docs/CONFIGURATION.md` — document `WATCHDOG_GOVERNANCE_MOUNT` (new env the sidecar consumes) + the `/var/lib/watchdog-governance/<id>` host path.
   - `docs/infrastructure/vps-complete-inventory.md:133` — add the `/governance:ro` mount to the sidecar bind-mount description (the row already lists "project tree RO" etc.).
   - Gate: `python scripts/enforcement/check_doc_sync.py` → green.
4. **Closing sequence (literal steps):**
   1. run the phase gates above → all green;
   2. `python scripts/enforcement/check_doc_sync.py` + the doc updates in step 3;
   3. **`/fabrik-review` on the changed surface** (`watchdog.py` diff + `_push_overlay`/`_render_env`/`provision` callers + the new test) — dispatch independent finder subagents (parallel) for recall → refute false positives → prove-before-fix with a kept regression test → re-run the gate after each fix → **loop to a no-op pass** (zero CONFIRMED/PLAUSIBLE). Risk-gate finders to Opus (this touches deploy + SSH-to-VPS command construction — shell-injection/path-quoting surface);
   4. commit the phase (explicit paths: `src/fabrik/drivers/watchdog.py`, `tests/test_watchdog_governance_mount.py`, `CHANGELOG.md`, `docs/CONFIGURATION.md`, `docs/infrastructure/vps-complete-inventory.md`, `INDEX.md`; provenance trailers `Agent-Role: primary`).

**Non-GUI phase — no Build Verification Loop.**

## Phase B — docs convergence + whole-plan review + full gate (finish)

1. **`/fabrik-docs-review`** across touched docs (`CHANGELOG.md`, `docs/CONFIGURATION.md`, `docs/infrastructure/vps-complete-inventory.md`, `INDEX.md`) → truthful fixed point.
2. **`/fabrik-review` on the WHOLE changed surface** (Phase A's `watchdog.py` diff + the docs) — dispatch independent finder subagents (parallel) → refute → prove-before-fix with kept regression tests → re-run the gate after each fix → **loop to a no-op pass** (zero CONFIRMED/PLAUSIBLE). Catches any doc↔code drift or interaction the per-phase (Phase A) review didn't see; risk-gate finders to Opus (deploy + SSH-command surface).
3. Full gate: `python scripts/final_gate.py --check --json` → `"status":"success"`; `python scripts/enforcement/check_convergence.py` → green. Green is necessary, not sufficient — the real proof is a live `fabrik apply` of a watchdog project showing `/var/lib/watchdog-governance/<id>` populated + the sidecar env set (operator-run; trigger-not-execute).

## File Scope (owned paths)

```
src/fabrik/drivers/watchdog.py                    (modify)
tests/test_watchdog_governance_mount.py           (create)
CHANGELOG.md, docs/CONFIGURATION.md, INDEX.md      (modify)
docs/infrastructure/vps-complete-inventory.md      (modify — sidecar mount list, :133)
```
Disjoint from `2026-07-07-plan-1-sysadmin-claude-rotation.md` (that owns `scripts/sysadmin/*`, `scripts/aro-wake/*`, `alerts.yml`; no overlap). `CHANGELOG.md`/`INDEX.md` are append-only shared points — stage explicit hunks only.

## Evidence

- **Approach + all code targets:** grounded in the CONVERGED spec (Pass Ledger 3-pass, md5-stable).
- **Render/ship seams (read):** `watchdog.py:680` `_push_overlay` (volumes `:695-714`), `:762` `_render_env`, `:553` `_build_image` (tar+scp+extract `:633-655`), `:381` `provision()` (sequence `:418 _build_image → :419 _push_overlay → :420 _bring_up`), `:713` the hollow `/opt/<id>:/project:ro`.
  ```
  # watchdog.py:633-655 — the pattern _push_governance mirrors
  tar.add(str(local_ctx), arcname=rctx.project_id)
  ssh(f"mkdir -p {VPS_BUILD_ROOT}", timeout=15)
  scp_to_vps(str(tar_path), remote_tar)
  ssh(f"sudo tar -xzf {remote_tar} -C {VPS_BUILD_ROOT} && sudo rm {remote_tar}", timeout=60)
  ```
- **Ship primitive (read):** `ssh.py:89` `scp_to_vps(local_path, remote_path, timeout=30, dry_run=False)`; `tarfile` + `scp_to_vps`/`ssh` already imported (`watchdog.py:79,87`).
- **Gate predicate (read):** `infrastructure.py:388 if should_run["watchdog"]:` — the same gate the DB-role injection uses (`:516 if provision_watchdog_roles:`).
- **No teardown to hook (read):** watchdog driver has no de-provision method; `watchdog-state-<id>` volume (`:709,742`) persists un-torn-down → the governance dir is at parity (tiny harmless orphan).
- **Source present (captured):** `tojlo-mail`/`whatsapp-agent`/`calendar-orchestration-engine` each carry `CLAUDE.md` + `AGENTS.md` + 49 `.windsurf/rules/*.md`.
- **Live hollow mount (captured):** `/opt/watchdog-test/` on vps1 = `compose.watchdog.yaml`, `compose.yaml`, `.env` only.

## Self-audit

- **Grounding:** solo (≤4 units, no subagents dispatched → nothing to record for the flywheel). Read every cited `path:line` in `watchdog.py`, `ssh.py`, `infrastructure.py`; confirmed no teardown exists; confirmed imports present.
- **Coverage of "What we agreed":** Option B mount → Phase A `_push_governance` + volume; env → `_render_env`; source `/opt/<id>` → tar source; gate `should_run["watchdog"]` → provision call site; non-secret `chmod` → step-2 `chmod -R a+rX`; fail-soft → `_push_governance` returns bool + conditional mount/env; layout contract → arcname-flat root; docs → step 3; review → closing step 3. ✓
- **Cross-phase signatures:** single implementation phase — `governance_mount_ready` produced in `_push_governance`, consumed in `_push_overlay`/`_render_env` (same file, same rctx). No cross-file signature drift.
- **Not a fixed point** — DRAFT; `/fabrik-plan-review` converges it.

## Residual unknowns

**Resolved (spec + this plan):** approach (B), VPS path, source location + presence, gate predicate, ship pattern, fail-soft design, non-secret handling, no-teardown parity.

**Still open (each with a resolution step):**
1. **The exact `/governance` layout fabrik-lib's `_materialize_conventions` globs** — the plan produces `/governance/{CLAUDE.md,AGENTS.md,.windsurf/rules/**}`. *Resolution:* confirm the glob paths with the fabrik-lib AI before/at their materialize landing (a one-line contract in both READMEs); if they expect a different root layout, adjust the `arcname` in `_push_governance` (a localized change). Non-blocking — both sides building to the same three-path contract.
2. ~~Which `docs/infrastructure/` file lists the sidecar mounts~~ **RESOLVED (plan-review):** `docs/infrastructure/vps-complete-inventory.md:133` (the `watchdog-test-watchdog` row already enumerates the sidecar bind-mounts) — add the `/governance:ro` mount there.

---

**Next:** `/fabrik-plan-review` converges this DRAFT → CONVERGED (runs now, this turn). Then `/fabrik-execute-plan <this file>` is **user-triggered** (mutates fabrik-core deploy code + SSHes to the VPS).
