# Watchdog governance-mount materialization (hub side) — design spec

**Status:** CONVERGED
**Author:** Claude Opus 4.8 (hub) · from chat 2026-07-07
**Sequence:** watchdog spec-shape/deployer work — lands **before** the fabrik-lib GOLDEN.jsonl generator.

**Pass Ledger (`/fabrik-spec-review` — fixed point, looped solo: ≤4 deps, no subagents dispatched):**

| Pass | axes re-grounded (facts · vendor · approach · completeness) | edits | spec md5 (start → end) |
|-----:|---|---:|---|
| 1 | all — cited line numbers + fabrik-lib README | 1 (RO-bind cite: `:711` is docker.sock RW, not `:ro`) | `39d2ff3d…` → `5facb933…` |
| 2 | all — `should_run["watchdog"]` gate + Option-A-rejection crux | 2 (git-tracking is *inconsistent* across scaffold vintages — reframed 2 absolutes; strengthens B) | `5facb933…` → `34200e8d…` |
| 3 | all — consistency scan for lingering absolutes | **0** | `34200e8d…` → `34200e8d…` ✓ → **CONVERGED** |

---

## Goal

Make the per-project watchdog sidecar actually **see the project's governance** (rule packs + agent contracts) on the live VPS, so its Tier-D autonomous fixes conform to project conventions instead of being written blind.

Today the sidecar bind-mounts the deployed project tree read-only (`/opt/<id>:/project:ro`, `watchdog.py:713`) and fabrik-lib's `_materialize_conventions` copies `CLAUDE.md + AGENTS.md + .windsurf/rules/*.md` from that mount into the Tier-D fix clone. **But the mount cannot be RELIED UPON to contain the governance set.** VPS deployment excludes gitignored files, and `.windsurf/rules/` is gitignored in current-scaffold projects (verified: `whatsapp-agent`), so it never reaches the VPS tree there. Tracking is inconsistent across scaffold vintages — the older `tojlo-mail` *does* track `.windsurf/rules/` — which is precisely why a git-status-dependent mount is fragile. Live proof of the hollow end-state: `/opt/watchdog-test/` on vps1 contains only `compose*.yaml` + `.env` (no `.windsurf/rules`, no `CLAUDE.md`, no `docs`). Where the mount is hollow, `_materialize_conventions` copies nothing and the watchdog is blind to the very rules it must obey.

**This spec covers the HUB half:** at `fabrik apply`, ship the project's governance set to a dedicated VPS path and expose it to the sidecar as a read-only mount + an env var. fabrik-lib ships the matching consumer half (a governance-source-flexible `_materialize_conventions` that reads `WATCHDOG_GOVERNANCE_MOUNT` if set, else `/project`) — already agreed, being built in parallel.

## Chosen approach — Option B: dedicated `/governance:ro` mount

At watchdog `provision()`, add a `_push_governance(rctx)` step (between `_build_image` and `_push_overlay`) that:

1. **Reads** the project's governance set from the hub's local WSL tree `/opt/<id>/` — confirmed to reliably carry `CLAUDE.md`, `AGENTS.md`, and `.windsurf/rules/**/*.md` (49 files) for every scaffolded project. Tars the set preserving the `.windsurf/rules/` subtree.
2. **Ships** it via the existing `scp_to_vps(local_tar, remote_tmp)` primitive (`ssh.py:89`) and extracts (over SSH `sudo`) into a dedicated **host** path on the VPS: **`/var/lib/watchdog-governance/<project_id>/`** — outside any project deploy tree. Files are non-secret (rules/contracts), `chmod 644`, dir `chmod 755`, so the sidecar (UID 1000) reads them through the RO mount regardless of owner.
3. **Mounts** it into the sidecar: add `f"/var/lib/watchdog-governance/{rctx.project_id}:/governance:ro"` to the `_push_overlay` volumes list (`watchdog.py:695-714`).
4. **Advertises** it: `_render_env` (`watchdog.py:762`) sets `WATCHDOG_GOVERNANCE_MOUNT=/governance` so fabrik-lib's materialize reads from the dedicated mount rather than the hollow `/project`.

**Layout at the mount root** (the fabrik-lib contract — coordination point): `/governance/CLAUDE.md`, `/governance/AGENTS.md`, `/governance/.windsurf/rules/**/*.md`. `_materialize_conventions` globs these three off `WATCHDOG_GOVERNANCE_MOUNT`.

**Always-on, not Tier-D-gated:** the mount ships for every watchdog deploy (gated on the existing `should_run["watchdog"]` predicate, same as the DB-role injection). The mount is cheap and non-sensitive, and the sidecar reads the rules for *diagnosis* across all tiers, not just Tier-D fix-authoring; `_materialize_conventions` merely *consumes* it on Tier-D. Refreshed on every apply (governance drifts with each sync), matching the idempotent-re-run contract of `provision()`.

**Fail-soft:** if a project's WSL tree is missing a governance file (e.g. no `AGENTS.md`), ship what exists and log a warning; if the whole source is absent, skip the mount + env (do NOT emit a `/governance` volume pointing at a non-existent host dir — that would make compose fail). fabrik-lib's materialize already falls back to `/project` when `WATCHDOG_GOVERNANCE_MOUNT` is unset, so a skip degrades to today's behavior, not a crash.

## Rejected alternatives

- **Option A — push governance into `/opt/<id>` directly (reuse the existing `/project:ro` mount, zero fabrik-lib change).** Rejected: `/opt/<id>` on the VPS is a **git working tree** (`fabrik redeploy` runs `git pull` against it), and governance-file tracking is **inconsistent across scaffold vintages** (verified: `tojlo-mail` tracks `CLAUDE.md` + `AGENTS.md` + `.windsurf/rules/`; `whatsapp-agent` gitignores `.windsurf/rules/`). Option A therefore behaves differently per project: where a governance file is **tracked**, writing a hub copy over it collides with `git pull` on redeploy (`"local changes would be overwritten"`, a redeploy-breaker); where it's **gitignored**, the tree is hollow anyway. A dedicated mount (B) is robust to both — it never touches the git working tree and doesn't depend on any project's tracking status. Option B keeps the deploy tree a pure artifact. (fabrik-lib recommended A for "one mount contract"; the per-project git-collision-vs-hollow split is the deciding factor A missed.)
- **Symlink / git-archive of the rules into the mount.** Rejected: symlinks don't survive the `scp`/bind boundary into a container cleanly, and `git archive` omits the gitignored `.windsurf/rules/` — the exact files we need. A plain tar of the working-tree set is simplest and correct.

## External dependencies

| Dependency | Grounded fact | Source · date |
|---|---|---|
| Docker Compose RO bind mount | `host_path:container_path:ro` — standard, long-stable Compose `volumes` short syntax; the driver already uses RO binds for OAuth + `/project` (`watchdog.py:698,707,713`) and a RW bind for docker.sock (`:711`) | Compose spec (in-repo precedent, read 2026-07-07) — no vendor API, no live-research gate |
| fabrik-lib `_materialize_conventions` governance-source-flexible variant | **Coordination contract (not external API):** consumer reads `WATCHDOG_GOVERNANCE_MOUNT` if set, else `/project`; globs `CLAUDE.md`, `AGENTS.md`, `.windsurf/rules/*.md` off that root. Being built in parallel by fabrik-lib; agreed 2026-07-07 | fabrik-lib AI, this chat — **named coordination point** below |

No 3rd-party API / pricing / rate-limit surface → the Phase-1a live-research gate is N/A (nothing external to ground). The one cross-repo contract (mount layout the consumer globs) is recorded as a coordination point, not a blocking unknown — fabrik-lib owns and matches it.

## fabrik-lib vendor→enhance→build verdict

| Capability | Verdict | Module / why |
|---|---|---|
| Materialize governance into the Tier-D fix clone | **VENDOR (coordinate)** | fabrik-lib `subagents`/watchdog `_materialize_conventions` already owns this; the hub only feeds it. Consumer being made source-flexible upstream (their deliverable), so no fork. |
| Ship files hub→VPS | **VENDOR (fabrik core)** | `scp_to_vps` + `ssh` (`fabrik.drivers.ssh`) — the exact primitives `_build_image` already uses. No new code class. |
| Render mount + env into the sidecar compose | **ENHANCE (fabrik core)** | Extend `_push_overlay` volumes + `_render_env` in `watchdog.py` — the same seams the DB-role injection used. In-repo, hub-owned; not a fork of a vendored module. |

**No new fabrik-lib candidate.** This is hub-specific deploy glue (project→VPS governance shipping), not a generic reusable module: it's bound to Fabrik's watchdog driver + VPS layout, fails the "reused by ≥2 project types / clean generic interface" bar.

## Shape / infra implications

- **No `shape.*` flag change.** This is watchdog-deployer internals, gated on the **existing** watchdog-applicable predicate (`should_run["watchdog"]`, `infrastructure.py`) — the same gate the WATCHDOG_DB_URL_RO/RW injection uses. A project that already gets a watchdog sidecar gets the governance mount; nothing new in `specs/services/<id>.yaml`.
- **Scaffold type:** none — this is fabrik core (`src/fabrik/drivers/watchdog.py`), not a scaffolded project.
- **Precedent:** mirrors the WATCHDOG_DB_URL_RO/RW pattern I shipped (mint/derive a per-project resource → inject at apply, gated on the watchdog predicate). Governance mount is the file-plane analogue of that credential-plane work.
- **VPS footprint:** a new host dir `/var/lib/watchdog-governance/<id>/` per watchdog project (~49 small `.md` files + 2 root files; KBs). Cleaned when the project is de-provisioned (add to the watchdog teardown path, symmetric with `watchdog-state-<id>`).

## Constraints

- Governance files are **non-secret** (rules/contracts/docs) → world-readable is fine; do NOT reuse the `chmod 600` OAuth path. This is the opposite of the credential mounts.
- **RO mount only** — the sidecar must never mutate governance (it reads to conform). `:ro` enforced at the bind.
- Hub reads governance from the **project's** WSL tree `/opt/<id>/`, NOT the hub's `/opt/fabrik/` — `CLAUDE.md`/`AGENTS.md` are project-specific; `.windsurf/rules/` is sync-identical but still read from the project copy for a single source path.
- Idempotent + refresh-on-apply — re-shipping overwrites the VPS governance dir wholesale each apply (governance drifts with sync); never merge.
- Stays in `/opt/fabrik` (hub core). The only out-of-tree writes are the `scp` + `ssh sudo` to the operator's own VPS at apply — the same trust boundary the driver already uses.

## Open / blocking unknowns

**Resolved (this chat):**
- Root cause — VPS deploy excludes gitignored `.windsurf/rules/`; mount hollow (verified live on `/opt/watchdog-test`).
- Approach — Option B (dedicated mount) over A (git-tree collision) over symlink/archive.
- Governance source reliably present on the hub's WSL project trees (CLAUDE.md + AGENTS.md + 49 rule files, confirmed across 3 projects).
- Ship primitive (`scp_to_vps`), render seams (`_push_overlay` volumes, `_render_env`), insertion point (`provision()` after `_build_image`), gate (`should_run["watchdog"]`).

**Open (each with a resolution step):**
1. **Mount-root layout the consumer globs** — the hub must lay out `/governance/{CLAUDE.md,AGENTS.md,.windsurf/rules/**}` exactly as fabrik-lib's `_materialize_conventions` expects. *Resolution:* confirm the glob paths with the fabrik-lib AI when their source-flexible materialize lands; a one-line contract in both repos' READMEs. Non-blocking (agreed in principle; both sides building to the same three-path contract).
2. **De-provision cleanup** — the teardown that drops `watchdog-state-<id>` must also `rm -rf /var/lib/watchdog-governance/<id>`. *Resolution:* locate the watchdog teardown path during planning and add the symmetric cleanup step (an owned line, not a new mechanism).

## Grounded code references

- `src/fabrik/drivers/watchdog.py:680` `_push_overlay` — writes `compose.watchdog.yaml`; volumes list `:695-714` (add `/governance:ro`).
- `src/fabrik/drivers/watchdog.py:762` `_render_env` — sidecar `environment:` dict (add `WATCHDOG_GOVERNANCE_MOUNT`).
- `src/fabrik/drivers/watchdog.py:381` `provision()` → `:418 _build_image` → `:419 _push_overlay` → `:420 _bring_up` (insert `_push_governance` after `_build_image`).
- `src/fabrik/drivers/watchdog.py:553` `_build_image` — the tar + `scp_to_vps` + remote `docker build` pattern to mirror for shipping governance.
- `src/fabrik/drivers/watchdog.py:713` — the existing hollow `/opt/<id>:/project:ro` mount this supplements.
- `src/fabrik/drivers/ssh.py:89` `scp_to_vps(local_path, remote_path, timeout=30, dry_run=False)`.
- `src/fabrik/orchestrator/infrastructure.py` (WATCHDOG_DB_URL_RO/RW injection, gated on `should_run["watchdog"]`) — the precedent this mirrors.
- Live evidence: `/opt/watchdog-test` on vps1 = `compose.watchdog.yaml`, `compose.yaml`, `.env` only (hollow mount, confirmed 2026-07-07).

---

**Next (per `/fabrik-spec` pipeline):** `/fabrik-spec-review` converges this DRAFT → CONVERGED (re-verify refs + vendor verdict), then user approval → `/fabrik-plan-after-chat` (no data-contract/UI-design freeze needed — no persistence/GUI surface). The fabrik-lib consumer half proceeds in parallel via their own plan.
