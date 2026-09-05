# Sync Enforcement Workflow (Fabrik → Projects)

**Last Updated:** 2026-09-05
**Status:** PRODUCTION
**Script:** `scripts/sync_enforcement_to_projects.py`
**Source of truth (the synced list):** `scripts/fabrik_synced_manifest.py`
**Direction:** Fabrik → Projects

## Overview

Synchronizes Fabrik governance + enforcement files to all `/opt/*` projects, ensuring consistent tooling and agent contracts across the ecosystem. Uses hash comparison and timestamp checks to avoid unnecessary overwrites.

> **⚠️ These files are centrally managed — do not edit them inside a project.**
> A local edit is overwritten on the next sync. The list lives once in
> [`scripts/fabrik_synced_manifest.py`](../../scripts/fabrik_synced_manifest.py) and is consumed by this sync
> script, the `.gitignore` "Fabrik-synced" block emitted by `scaffold.py`, and the
> gate check `scripts/enforcement/check_synced_unmodified.py` (which **fails the
> gate** when a project's copy drifts from the `/opt/fabrik` source). To change a
> synced file: edit the canonical copy in `/opt/fabrik`, re-sync, and **only** if
> the change is correct for ALL projects. Otherwise propose it upstream — never
> fork it locally. (`PORTS.md` is seeded then project-owned, so it is exempt from
> the drift check.)
>
> **When you modify the synced set, edit `fabrik_synced_manifest.py` only** — the
> three consumers derive from it. The tables below mirror those lists.

| **Trigger** | Manual (`fabrik enforce` or direct), or automatic via `watch_enforcement_changes.sh` |
| **Automation** | ✅ Optional: WSL startup hook via `watch_enforcement_changes.sh` (monitors Fabrik governance files) |

---

## What Gets Synced

### Governance Files

| File/Dir | Purpose |
|----------|----------|
| `AGENTS.md` | Agent workflow rules (stub pointing to `agents-fabrik.md`) |
| `agents-fabrik.md` | Canonical infra + codebase map (the real content `AGENTS.md` stubs to) |
| `agents-fabrik-core.md` | High-frequency platform core, @import-ed by every project's synced `CLAUDE.md` |
| `AGENTS-compact.md` | Compact reference |
| `CLAUDE.md` | Per-project Claude agent configuration — sourced from `templates/governance/CLAUDE.md` (`GOVERNANCE_TEMPLATES`), NOT from the hub's own `/opt/fabrik/CLAUDE.md`, which is the hub agents' contract and never distributed |
| `.worktreeinclude` | Worktree-copy manifest for Claude Code linked worktrees — sourced from `templates/governance/.worktreeinclude` (`GOVERNANCE_TEMPLATES`), rendered by `fabrik_synced_manifest.worktreeinclude_text()` from the same `gitignore_dest_paths()` the `.gitignore` block comes from, plus `.env` and `.mcp.json`, minus `.claude/settings.local.json` (plan 2026-09-03-plan-1-multi-agent-per-repo, T01a) |
| `opencode.json` | Kilo CLI configuration |
| `.windsurfrules` | Cascade compact agent contract |
| `.windsurf/rules/` | Cascade rule files (recursive, orphan-pruned) |
| `.windsurf/workflows/` | Cascade workflow files (recursive, orphan-pruned) |
| `docs/reference/kilo/` | Kilo agent-selection + model docs (recursive, orphan-pruned) |
| `docs/reference/MD/` | Shared markdown reference set (recursive, orphan-pruned) |

**Note:** `AFCL.md` is scaffolded as `AFCL_TEMPLATE.md` and customized per project, not synced. `.pre-commit-config.yaml` is tech-stack specific and not synced.

### Reference Documentation

| File | Purpose |
|------|----------|
| `docs/reference/long-command-monitoring.md` | Long command monitoring system documentation |
| `docs/reference/technology-stack-decision-guide.md` | Stack selection guide |
| `PORTS.md` | Port allocations (seed; project-owned thereafter — exempt from drift check) |
| `docs/operations/fabrik-lifecycle.md` | Runtime behavior & data safety |
| `docs/PROJECT_CATALOG.md` → `docs/reference/opt-project-catalog.md` | The `/opt` project inventory ("what exists, so a project can wire to a sibling instead of rebuilding"). Renamed from `BUSINESS_MODEL.md` 2026-07-11 — that path is each project's own *monetization* doc, and the old sync target was clobbering it; now synced to a reference path that never collides. |
| `docs/reference/mobile-responsive-testing-guide.md` | Mobile/responsive testing guide |
| `docs/reference/convergence-prompts.md` | The 3 direct-agent convergence prompts (PLAN/CODE REVIEW/DOCS) — referenced by the synced `CLAUDE.md` HARD-STOP row |

### Core Scripts

| Script | Purpose |
|--------|----------|
| `final_gate.py` | Pre/post Kilo gate checks |
| `kilo_code_review.py` | Kilo CLI review integration |
| `kilo_docs_enforcer.py` | Step 4 DOCUMENTATOR |
| `docs_updater.py` | Documentation maintenance |
| `doc_reconcile.py` | Tier-1 doc-reconcile loop (pool author → verify → converge); agents run it per phase |
| `update_agents_toc.py` | AGENTS.md table of contents |
| `health_checker.py` | HTTP + DB health probes |
| `select_rules.py` | Plan-time: lists applicable `.windsurf/rules` packs |
| `review_rubric.py` | Armed-review rubric extractor — `/fabrik-review` injects its output into finders |

### Run Scripts

Long Command Monitoring System v1.1.0 - see `docs/reference/long-command-monitoring.md`

| Script | Purpose |
|--------|----------|
| `rund` | Run command with timeout monitoring |
| `rundsh` | Run shell script with timeout monitoring |
| `runc` | Read result from last run |
| `runk` | Kill last run |
| `runls` | List active runs |
| `runlast` | Show last run ID |
| `runwait` | Wait for run completion |
| `runtail` | Tail run output |
| `runclean` | Clean up completed runs |
| `sync_cascade_backup.sh` | Check Cascade memory backup freshness (warn if >7d) |
| `sync_extensions.sh` | Sync Windsurf extensions documentation |

### Enforcement Directory

All files in `scripts/enforcement/` are recursively synced (`ENFORCEMENT_DIR`, `fabrik_synced_manifest.py`) — 49 files as of 2026-07-20 (`git ls-files scripts/enforcement/ | wc -l`), a representative sample:

- `check_docker.py` — Dockerfile amd64 compliance
- `check_secrets.py` — Hardcoded secrets detection
- `check_env_contract.py` — .env/.env.example sync
- `check_health.py` — Health endpoint validation
- ... (49 checks total; see [FINAL_GATE_WORKFLOW.md § Enforcement Scripts](FINAL_GATE_WORKFLOW.md) for the full gate-wired inventory)

### Vendored Modules

| Dir | Purpose |
|-----|----------|
| `libs/subagents` | The OpenRouter subagent-pool module (`VENDORED_DIRS`, `fabrik_synced_manifest.py`), vendored into every project. Dev-time tool the `/fabrik-*` commands import as `from libs.subagents import …`; a fix in the hub copy (`/opt/fabrik/libs/subagents`, kept byte-identical to canonical `/opt/fabrik-lib/subagents`) propagates fleet-wide on the next sync. |

### Agent Hook Files

| File | Purpose |
|------|----------|
| `.claude/settings.json` | Claude Code hook configuration |
| `.claude/hooks/final_gate_stop.py` | Claude Code stop-hook enforcing `final_gate` green as the definition of done |
| `.claude/hooks/skill_router.py` | UserPromptSubmit router — suggests the owning `/fabrik-*` skill for bare-prose requests |
| `.claude/hooks/session_orient.py` | SessionStart ORIENT block — binds the synced CLAUDE.md, surfaces MEMORY.md state, names session-recall + the enforcement mesh |
| `.windsurf/hooks.json` | Cascade hook configuration — **DORMANT**: no live runtime consumes it (Cascade retired); synced as a template for a future non-Claude tool, never counted as active enforcement |

Synced verbatim to project root (`AGENT_HOOK_FILES`, `fabrik_synced_manifest.py`) — path/cwd-agnostic: the Claude Code hook resolves its project via `${CLAUDE_PROJECT_DIR}` + stdin cwd, the Cascade hook commands self-locate via `git rev-parse`. This is what makes every project — existing and future — enforce `final_gate` green as the definition of done. Kilo/opencode has no config-level hook surface (strict schema), so Kilo stays instruction-only via `AGENTS-compact.md` (rides the Governance Files sync instead).

---

## CLI Usage

```bash
# Preview what would be synced (safe)
python scripts/sync_enforcement_to_projects.py --dry-run

# Sync with backups before overwriting
python scripts/sync_enforcement_to_projects.py --backup

# Force sync (skip hash comparison)
python scripts/sync_enforcement_to_projects.py --force

# Verbose output (show all file actions)
python scripts/sync_enforcement_to_projects.py -v
```

---

## Sync Logic

### Decision Flow (main checkout only — `sync_single_file`)

This flow governs every file the sync writes into a project's **main checkout**. It does **not**
govern what the sync writes into a project's linked **worktrees** — see
[§ Worktree Re-sync](#worktree-re-sync-multi-agent-per-repo) below, whose decision flow is
deliberately different (and where `--force` means something else entirely).

```text
For each file:
├── Destination doesn't exist? → COPY (new file)
├── --force flag? → COPY (forced overwrite)
├── Hash identical? → SKIP (no change needed)
├── Destination newer? → WARN (don't overwrite local changes)
└── Source newer? → COPY (update)
```

### Safety Features

1. **Hash Comparison** — MD5 hash avoids unnecessary writes
2. **Timestamp Check** — Won't overwrite if destination is newer
3. **Backup Option** — Creates `.backup.YYYYMMDD-HHMMSS` before overwriting
4. **Dry Run** — Preview changes without writing
5. **Permission Check** — Skips projects without write access
6. **Symlink Replacement** — Replaces file and directory symlinks with real copies (workspace isolation)

**The `.gitignore` "Fabrik-synced" block is patched outside the file-by-file loop above** — every
project's tracked `.gitignore` is re-derived from `fabrik_synced_manifest.gitignore_block_text()`
(`patched_gitignore()`), and the marked block is replaced whenever it drifts from that canonical
text (the project's own, non-block rules are left untouched). ⚠️ **This is a one-off ~45-repo
dirty-tree event on first adoption of a new sync-managed path or a `.gitignore` block reword** —
every tracked `.gitignore` in every synced project picks up the new block on its next real run,
which is a real `git status` change the operator will see fleet-wide, not a bug in one project.
Round 7, class 3: a real (non-`--dry-run`) run used to make this write completely silently — no
per-project line, and nothing in the run's own `Results:` summary; only `--dry-run`'s preview
(`Would patch <project>'s .gitignore …`) said anything, and even that line lives among per-project
output the production wrapper's `tail -3` (`scripts/governance_sync_postcommit.sh:82`) discards.
Both paths now print their own line (`Patched …` / `Would patch …`) **and** roll the count into
the final `Results:` line — `gitignore patched: N` (real) or `gitignore would be patched: N`
(`--dry-run`) — the one line that survives truncation.

## Worktree Re-sync (multi-agent-per-repo)

Added across `docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md`'s T01b — hardened
across the T01b acceptance rounds, 2026-09-05 — every sync run also does the following, **per
project**, after the main-checkout legs above. The three steps do NOT share one timing rule — each
is anchored below to where it actually runs (`sync_scripts_to_project`, in call order):

1. **Git-config seeding** (`seed_git_workflow_config`, called first, ~:1599 — BEFORE both steps 2
   and 3) — `push.autoSetupRemote` then `rerere.enabled` (same order and semantics as
   `src/fabrik/scaffold.py`'s `_configure_git_repo`, which seeds fresh repos; this seeds the ~46
   EXISTING ones), local scope, idempotent — a key the project already answered is never
   overwritten. Invoked on every run including `--dry-run` (it just prints `Would set …` and
   writes nothing under `--dry-run` — see the CLI table above).
2. **Shared floor** (`_seed_worktree_secrets_exclude`, called from inside step 3, first thing) —
   seeds `$(git rev-parse --git-common-dir)/info/exclude` with `_WORKTREE_FLOOR_PATTERNS`:
   `.env`, `.mcp.json`, (round 8) `.fabrik/worktree-synced.lock` — the per-worktree ledger step 3
   itself depends on — (round 10) `.fabrik/synced.lock` — the main checkout's lock step 3 copies
   into every worktree — and (round 11) `.fabrik/.ledger-tmp-*` — the reap's own in-flight
   tempfile, which the round-10 age guard deliberately leaves on disk for up to an hour so a
   concurrent writer's still-live tempfile is never deleted out from under it. Each needs this
   exact mechanism for the same reason the secrets do: a linked worktree evaluates its OWN branch's
   tracked `.gitignore`, and one seeded before the pattern's own ignore-fix landed never has it
   (reproduced live for the lock: a
   worktree cut from a branch with no `.gitignore` at all showed `?? .fabrik/`, unignored, after
   receiving it). This is a repo-wide file every worktree shares, so one write protects the main
   checkout AND every worktree present or future, regardless of which branch each has checked out.
   `--dry-run` never writes this — it prints one line per GIT project STILL MISSING a pattern (41 of
   45 on the 2026-09-05 sweep; a non-git `/opt` dir — round 8, class 2's `_is_git_repo` gate — and a
   repo already fully seeded both print nothing), naming the actual pattern list, and not only on a
   repo's first-ever seed: a repo already marker-seeded BEFORE a later pattern existed is missing it
   too, and one more (real or previewed) run appends the gap as a DATED ADDENDUM AT THE END OF THE
   FILE — outside the marker block entirely, after the END line and after any of the repo's own
   rules that already follow it, so it always wins ordering — rather than re-seeding the whole block
   (round 8, class 3 — the marker's mere presence is checked pattern-by-pattern, never treated alone
   as "done forever"). It runs after the lock only incidentally (it lives inside step 3's own
   function, which does — see below); nothing about the shared floor itself depends on the lock's
   content.
3. **Worktree artifact re-copy** (`resync_worktree_artifacts`, called AFTER the main checkout's own
   `.fabrik/synced.lock` is (re)written — this is the one step that actually needs that ordering,
   since it copies the freshly-written lock into every worktree in the same pass) —
   `.worktreeinclude` (see the table above) only fires at Claude Code's own worktree-**creation**
   moment, so a sync landing mid-epic otherwise updates the main checkout alone. This step
   re-copies the same gitignored set `.worktreeinclude` was built from — plus the just-written
   `.fabrik/synced.lock` — into every worktree the project currently has under
   `.claude/worktrees/`.

### Worktree copy decision (per file, per worktree — `_copy_into_worktree_safely`)

**Never the main-checkout flow above, and never mtime.** A worktree's destination file is live,
agent-editable content — `--force` here does **not** mean "overwrite regardless"; it plays no role
in this decision at all. The gate is a hash comparison against **this worktree's own** ledger
(`.fabrik/worktree-synced.lock`, written by this function after its own copy loop — never the
copied `.fabrik/synced.lock`, which lists what the *main checkout* manages, not what *this
worktree* actually received):

```text
For each file, in each worktree:
├── Destination doesn't exist? → COPY (nothing to clobber)
├── destination or source unreadable (OSError — chmod 000, or the path became a
│     directory)? → WARN ("unreadable — left in place")
├── hash(dest) == hash(source)? → SKIP (already in sync; --force changes nothing here either)
├── hash(dest) == the worktree's OWN ledger record for this path?
│     → COPY (provably unmodified since a prior resync wrote it — safe to refresh)
├── no ledger record at all for this path (or a legacy list-shaped ledger's
│     unverified "" sentinel — round 7, class 6)?
│     → WARN ("no ledger record (first sync, or a prior record was lost) — left in
│     place") — a LEDGER GAP, not necessarily an edit (round 5: 5 of 5 hash-sampled
│     live instances of this exact case were stale copies from an older branch, never
│     an agent edit; round 7: this is the ONLY state the first fleet run under this
│     mechanism produces — 101 of 101 live warnings, since no worktree has a ledger
│     yet)
└── a ledger record IS present but its hash matches neither source nor destination
      → WARN ("differs from the ledger record — edit preserved") — a genuine,
      provable drift from what the sync last wrote: the agent's own edit
```

**Bootstrapping a worktree stuck in the ledger-gap state** (the branch above, and the only one the
first-ever resync of any worktree can take — there is no ledger yet to prove anything either way):
this function will never overwrite it on its own — that decision does not change. An operator who
has confirmed the worktree's copy carries no real edit clears the gap by hand: copy the MAIN
CHECKOUT's current file over the worktree's copy at the same relative path
(`cp <project>/<path> <worktree>/<path>`) and run the sync once — that resync's SKIP/COPY branch
(hash now matches the fresh source) records a fresh ledger row, and the file converges normally on
every run after.

Why mtime is excluded entirely (round 4, class 1): a governance commit refreshes the hub file,
`shutil.copy2` propagates that fresh mtime into the project's main checkout when the leg above
re-syncs it, and the production wrapper (`scripts/governance_sync_postcommit.sh`) runs `--force`
immediately after — so an agent's own edit, however recent, is almost always *older* than the
just-refreshed source. Measured live: 106 of 19,256 worktree file pairs were `exists_differ_older`
and 0 were mtime-protected; a probe with an edit stamped 30 minutes old against a hub copy stamped
"now" silently lost the edit, identically with or without `--force`. Mtime is never consulted for
this decision now, on either path.

**Orphan pruning** inside a worktree's directory-shaped patterns removes a file (or a now-empty
directory) only when THIS worktree's own ledger names it **and its CURRENT on-disk hash still
equals that recorded row** **and** it is not tracked by that worktree's own git — never a file
merely absent from the main checkout's current copy, never on the strength of the copied main
lock, and (round 6 correction) never on a ledger row's mere PRESENCE alone: a row surviving from
*before* a genuine edit (rows are merged forward across runs, never dropped just because a run
didn't re-confirm them) is not proof the file is still what the sync wrote — a hash mismatch there
gets the SAME "differs from the ledger record" WARN the copy side gives, never a deletion. A pruned
file is backed up first under `--backup`, but **outside** the worktree
(`<project>/.fabrik/backups/worktrees/<name>/…`), never beside the file inside the live tree.
**Mirror worth stating plainly:** a file the agent deliberately deletes from a synced directory is
recreated on the next resync — there is no ledger entry recording a delete, only ever "last known
good content" — which is the intentional mirror of the copy rule above (governed content always
converges back to the hub's version), not a bug.

The real (or, under `--dry-run`, would-be) per-project file/warning/orphan totals are folded into
the sync's final `Results:` summary line, since the production wrapper truncates everything else
this step prints to its last few lines.

---

## Output Example

```text
Found 38 projects to sync

✓ api-gateway                            OK (5 copied, 20 skipped)
✓ auth-service                           OK (0 copied, 25 skipped)
✓ captcha                                OK (3 copied, 22 skipped)
  WARN (destination newer): final_gate.py
✓ dns-manager                            OK (0 copied, 25 skipped)
✗ legacy-app                             SKIP (no write permission)

Results: 37 projects synced, 1 failed | Files: 8 copied, 917 skipped, 1 warnings
```

---

## When to Run

| Trigger | Command |
|---------|----------|
| After updating scripts | `python sync_enforcement_to_projects.py` |
| Before major releases | `python sync_enforcement_to_projects.py --force` |
| Automatic (optional) | `scripts/watch_enforcement_changes.sh` (WSL startup hook) |

---

## Excluded Directories

The script skips `/opt/fabrik` itself (source) plus the `exclude_folders` set (`sync_enforcement_to_projects.py:748-762`, 11 entries, reconciled 2026-07-20):

- `.factory`, `.ssh` — non-project system dirs
- `web_scraper` (deprecated — use `web-scraper`)
- `containerd` — Docker runtime artifact dir
- `google` — Google Chrome install location
- `logs` — generic logs dir, not a Fabrik project
- `archived` — archived projects, no longer active
- `fabrik-lib`, `fabrik-libs` — reference implementation store (vendor, don't depend)
- `mt-router` — standalone copy, reference already in `fabrik-lib`

---

## Project INDEX.md Updates

Each project's `INDEX.md` contains an auto-generated **Documentation Structure Map** section that is kept in sync with the actual files.

### How to Update Project INDEX.md

```bash
# In any project directory:
cd /opt/<project-name>
python scripts/docs_updater.py

# Or check for issues:
python scripts/docs_updater.py --check

# Dry run to see what would change:
python scripts/docs_updater.py --dry-run
```

### What Gets Updated Automatically

- **Documentation Structure Map** (between `AUTO-GENERATED:STRUCTURE` tags)
- File tree structure of `docs/` directory
- Detects new, moved, or deleted documentation files

### What Remains Manual

- File purposes table (top section)
- "Last Updated" date
- File descriptions and update triggers

---

## Exit Codes

| Code | Meaning |
|------|----------|
| 0      | All projects synced successfully |
| 1      | One or more projects failed       |

---

## Related Workflows

- [Final Gate Workflow](FINAL_GATE_WORKFLOW.md) — The synced enforcement scripts
- [Fabrik Scaffold Workflow](FABRIK_SCAFFOLD_WORKFLOW.md) — Project creation
- [`docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md`](../superpowers/specs/2026-09-03-multi-agent-per-repo-design.md)
  § Lifecycle — the design this doc's [§ Worktree Re-sync](#worktree-re-sync-multi-agent-per-repo)
  section implements
