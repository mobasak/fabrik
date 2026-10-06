# Plan — each linked worktree owns its venv (W-46d148b0)

Status: DRAFT
Profile: small
**Owner:** infra

Spec: `docs/superpowers/specs/2026-10-06-worktree-venv-isolation-design.md` (DRAFT at 1cd1a2c97, `Size: small`,
`Profile: delta` — `/fabrik-plan-review` grades its sections together with this plan and flips both). Source:
trade-intelligence mail 01M3RYGETKD5HQZRBTDF3EK3EK (ack: no), the hub recurrence of 2026-10-06, and the UPGRADE
(tradeoffs) of the `/fabrik-task` run on W-46d148b0. Estimated diff: ≈230 code lines in 4 code files, tests excluded —
`.claude/hooks/worktree_venv.py` ≈200 (new), `.claude/settings.json` ≈15, `scripts/fabrik_synced_manifest.py` ≈8 (one
`AGENT_HOOK_FILES` entry and a comment), `templates/governance/.worktreeinclude` +1 regenerated line.

## What this plan is

Two inline phases the orchestrator codes itself in the main checkout; no coder is dispatched:

- **A — the hook**: `.claude/hooks/worktree_venv.py` with its linked-worktree detection, the SessionStart bootstrap
  (spec D2), the PreToolUse Bash guard (spec D3) and the `--bootstrap` CLI form (`spec § Open/blocking unknowns`), and
  its tests (spec V1–V5).
- **B — distribution, docs, Finish**: the settings block and registrations (spec D1), the manifest entry and the
  regenerated `.worktreeinclude` (spec D4), the docs (spec D5), V6, then the whole-plan `/fabrik-review` and ONE commit
  (every surface here is a governance-sync path, so phases A and B land together, after the Finish review).

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I13 (13 items, all IN) | IN | Phases A and B, per the spec rows |
| I2 | *"Plan it as `Profile: small`; its /fabrik-plan-review grades the spec's sections with the plan"* (this run's brief) | IN | this file's header; `/fabrik-plan-review` |
| I3 | *"Governance-sync paths → one commit after the full /fabrik-review at execution"* | IN | Phase B steps 7–9 |
| I4 | *"tests needing uv/network skip with a stated reason, the guard and detection tests need neither"* | IN | Phase A step 1; Behavior Contract A1–A6 |

## What we already agreed (citations, not restatement)

- Goal and personas: `spec § Goal`, `spec § Personas`; why: `spec § Why this exists`.
- Measured behaviour and costs: `spec § What exists today (grounded)`.
- The delta D1–D5: `spec § The delta`; contract deltas: `spec § Contract deltas`.
- Chosen approach C (judge panel 3/3): `spec § Chosen approach`; rejected A, B-alone and six others:
  `spec § Rejected alternatives`.
- Lifecycle: `spec § Lifecycle`; open unknowns and their resolution steps: `spec § Open/blocking unknowns`.
- Validation V1–V6: `spec § Validation`; decisions: `spec § Decisions taken`. The approval row is minted by
  `/fabrik-plan-review` at its gate (a `Size: small` spec is approved there, not here).

## Global Constraints (every phase inherits these)

- **The main checkout's `.venv` is never written** by the hook: no code path in `worktree_venv.py` runs `uv`, `pip`,
  `rm` or `unlink` against a path whose realpath is inside the main checkout's `.venv` (`spec § The delta` D2).
- **A symlink is removed with `os.unlink` only** — never `shutil.rmtree`, never a path with a trailing slash; a real
  `.venv` directory is never removed (`spec § What exists today`, the `rm -rf .venv/` row).
- **Linked-worktree test = realpath compare**: `realpath(git rev-parse --git-dir)` ≠ `realpath(git rev-parse
  --git-common-dir)`, both resolved against the directory under test (a string compare misfires in a subdirectory —
  Fable critique 4).
- **Fail-open everywhere**: any exception, git failure, timeout or unparseable payload → exit 0 with no deny; the
  bootstrap prints at most one banner line on stdout (SessionStart context) naming the command to run by hand.
- **Hook registration guards on the file's existence**: the settings command is
  `f="${CLAUDE_PROJECT_DIR}/.claude/hooks/worktree_venv.py"; [ -f "$f" ] && python3 "$f" <mode> || exit 0`, so a
  settings file that reaches a tree before the hook file can never fail every Bash call with exit 2 (Fable critique
  6b).
- **Guard budget**: the PreToolUse path runs no subprocess unless a segment's head is a writer verb (string test
  first); measured cost per Bash call reported in Evidence.
- **Hub-only experiment never on a synced path**: everything here IS a synced path (`AGENT_HOOK_FILES`,
  `fabrik_synced_manifest.py:271`) — one commit after the Finish review, then the governance sync distributes it.
- No new dependency; `pyproject.toml` and `uv.lock` are not touched (`core/10-python.md:30`). The hook is stdlib-only
  (it runs under the system `python3`, like `quota_stop.py`). No env var is added. No log file
  (`core/10-python.md:294`).
- 12-Factor on this surface: a dev-box hook, not a service — **III** no config added, **XI** no logfile; the rest not
  engaged (no backing service, no process model, no deploy).
- Tests: watched-fail-first for every behaviour this plan adds (`core/45-testing-strategy.md:22`); assertions on files,
  `.pth` targets and hook JSON, never cosmetic (`:21`). Tests build scratch git repos with `git worktree add` in
  `tmp_path` and run git with `GIT_CONFIG_GLOBAL=/dev/null`; tests that need `uv` skip with the reason
  `"uv not on PATH"` when `shutil.which("uv")` is None, and every guard/detection test runs without uv or network.
  Red-on-revert runs in a throwaway worktree (`git worktree add --detach <scratch>/probe HEAD`), never in the shared
  checkout.
- Seats never mutate git state (read-only git only); never read `~/.claude*`; never SSH.
- **Execution discipline (native seats only, D-181):** every phase ends with `/fabrik-review-scoped` on its surface (the
  floor of three native seats on different angles, stamped with `command_run.py dispatch`), not handing on until its
  closing pass confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet
  and a Haiku finder per slice (D-344), the orchestrator executing every refutation. Within a phase the steps are
  sequential (each consumes the previous); the review seats are the parallel fan-out, merged and refuted by the
  orchestrator.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | uv is the package manager; no deps-file edit; no file logging | `core/10-python.md:22`, `:30`, `:294` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | one test per behaviour; watched-fail-first; a guard proven several ways | `45-testing-strategy.md:20-22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | the docs edited stay structured; Doc Sync | `core/40-documentation.md:61` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | config via env only — not engaged: no config, no secret | `core/35-security-auth.md:267` |
| `.windsurf/rules/core/30-ops.md` (FLOOR) | not engaged: no service, compose or deploy change | `spec § Shape/infra implications` |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | not engaged: no database | `spec § Shape/infra implications` |
| `fabrik-lib` | none — hub governance | `spec § fabrik-lib verdict` |
| `agents-fabrik.md` § Development Environment | WSL dev box; the hooks run there | `agents-fabrik.md:130` |
| Claude Code hook contract | PreToolUse deny JSON; `cwd` follows `cd` | `spec § External dependencies` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Verbatim | file:line | Rule |
|---|---|---|
| "**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`." | `.windsurf/rules/core/10-python.md:22` | Package manager |
| "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | `.windsurf/rules/core/10-python.md:30` | Deps |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | `.windsurf/rules/core/45-testing-strategy.md:20` | Behaviour Contract |
| "**Watched-fail-first** (for tests this change adds or modifies" | `.windsurf/rules/core/45-testing-strategy.md:22` | Red first |
| "Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**." | `.windsurf/rules/core/35-security-auth.md:267` | Config (not engaged) |

## Phase A — the hook: detection, bootstrap, guard

Appetite: 120

**Interfaces — Produces** (`.claude/hooks/worktree_venv.py`, new; `spec § The delta` D2, D3):
- `linked_worktree_root(path: Path) -> Path | None` — the toplevel of the linked worktree containing `path`, or `None`
  for a main checkout, a non-repo, or any git failure (realpath compare per Global Constraints).
- `venv_is_link(root: Path) -> bool` — `(root / ".venv").is_symlink()`.
- `bootstrap(root: Path, *, timeout_s: float) -> str | None` — unlinks a symlinked `.venv` (`os.unlink`), then: when
  `root/pyproject.toml` exists runs `uv sync` (cwd=root); else when `requirements*.txt` exist runs `uv venv .venv` then
  `uv pip install --python .venv/bin/python -r <f>` per file (sorted); else nothing. Returns `None` on success or no-op,
  else the one-line banner naming the exact command. Never touches a real `.venv` directory that already exists.
- `writer_segment(command: str, cwd: Path) -> Path | None` — splits `command` on `&&`, `||`, `;`, `|` (quote-aware via
  `shlex` with `punctuation_chars`), tracks a segment-leading `cd X` for later segments, skips leading `NAME=value`
  assignments, `env`, `timeout N`; returns the effective directory of the FIRST segment whose head is a writer per
  `spec § The delta` D3 (honouring `--directory`/`--project`/`UV_PROJECT=` and the safe flags/`UV_NO_SYNC=1`), else
  `None`. An unparseable command returns `None`.
- `main(argv) -> int` — modes: `session-start` (reads the SessionStart payload's `cwd`; bootstraps only in a linked
  worktree with a missing or symlinked `.venv`; prints the banner when one is returned), `pre-tool-use` (reads the
  payload; for `tool_name == "Bash"` computes `writer_segment`; when the effective directory's `linked_worktree_root`
  has `venv_is_link`, prints the deny JSON `{"hookSpecificOutput": {"hookEventName": "PreToolUse",
  "permissionDecision": "deny", "permissionDecisionReason": <reason>}}`), `--bootstrap [PATH]` (the CLI form; bootstraps
  `PATH` or the cwd's linked worktree, prints the outcome, exit 0 even on failure, exit 2 only on a usage error). Every
  mode returns 0 on any exception.
- The deny reason names: why (the main checkout's venv is shared through the link), the fix (`rm .venv` — no trailing
  slash — then `python3 .claude/hooks/worktree_venv.py --bootstrap`), and that the guard stops firing once `.venv` is a
  real directory.

**Consumes:** nothing.

**Mirror (named):** none existing — the file is new; `.claude/hooks/quota_stop.py:645-690` is the deny-shape precedent
(read, not edited).

0. Probe: `uv --version` and `python3 -c "import shlex; print(shlex.shlex('a && b', posix=True, punctuation_chars=True).__class__)"`
   → both print; record the uv version in Evidence.
1. **Write the failing tests first** (rows A1–A6) in `tests/test_worktree_venv.py`, importing the hook by path
   (`importlib.util.spec_from_file_location`, the pattern `tests/test_quota_stop_hook.py` uses for `quota_stop.py`). Fixtures:
   a scratch main repo with a `src/demo` package and a `pyproject.toml` (hatchling), `git worktree add` a linked
   worktree whose `.venv` is a symlink to the main repo's `.venv`; a requirements-only variant. Run them and confirm
   each fails for the right reason (the module does not exist yet → every test errors on the import, which is red; then
   after a stub `main` returning 0, each assertion fails on its own behaviour).
2. Implement the module per the Interfaces.
3. Run green: `.venv/bin/python -m pytest tests/test_worktree_venv.py -q -p no:cacheprovider` → all pass (uv-dependent
   rows pass, not skip, on this box: `uv` is on PATH).
4. Prove red on revert in a throwaway worktree (copy the hook to its exact path, grep a marker to confirm the copy
   landed): replace `os.unlink` with `shutil.rmtree(p, ignore_errors=True)` on the resolved path → A3 fails (the main
   venv is emptied); make `linked_worktree_root` a string compare → A1's subdirectory case fails; drop the `--no-sync`
   exemption → A4's safe-form case fails; make the verb test a substring search → A4's `grep "uv sync"` case fails;
   let an exception escape `main` → A6 fails; remove the worktree.
5. Measure the guard's cost: time 1,000 `pre-tool-use` invocations of a non-writer command (`ls -la`) and of a writer
   in a main checkout; record the per-call median in Evidence.
6. `python scripts/enforcement/check_doc_sync.py` → exit 0.
7. **`/fabrik-review-scoped`** on Phase A's surface (`.claude/hooks/worktree_venv.py`, `tests/test_worktree_venv.py`),
   run to its closing pass confirming 0 — BLOCKING before Phase B. Phase A is NOT committed alone (Global Constraints:
   one commit after Finish).

### Behavior Contract — Phase A

- **Given** a scratch main repo and a linked worktree, **When** `linked_worktree_root` is asked about the worktree root, a subdirectory of it, the main checkout, a subdirectory of the main checkout and a non-repo directory, **Then** it returns the worktree root for the first two and `None` for the other three (A1; spec D2, Fable critique 4)
- **Given** a linked worktree whose `.venv` symlinks the main repo's venv, **When** the `session-start` mode runs with that `cwd`, **Then** the worktree's `.venv` becomes a real directory, `import demo` under it resolves to the worktree's `src`, and the main venv's editable `.pth` is byte-identical before and after (A2; spec V1)
- **Given** a requirements-only main repo and its linked worktree with a symlinked `.venv`, and separately a worktree whose `.venv` is already a real directory and the main checkout itself, **When** `session-start` runs in each, **Then** the first gets an own venv with its requirement installed, and the other two are untouched (directory listing and mtimes unchanged) (A3; spec V2, V3)
- **Given** a linked worktree with a symlinked `.venv`, **When** `pre-tool-use` sees each writer form of the spec's table (`uv run`, `uv run --frozen`, `uv sync`, `uv add x`, `uv pip install -e .`, `uv venv --clear`, `pip install x`, `python3 -m pip install x`, `rm -rf .venv/`), the cross-directory forms from the main checkout (`cd <wt> && uv sync`, `uv run --directory <wt> python`), each safe form (`uv run --no-sync pytest`, `UV_NO_SYNC=1 uv run pytest`, `uv sync --check`, `uv lock`) and two mentions (`grep -rn "uv sync" docs`, `git commit -m "deny pip install"`), **Then** every writer and cross-directory form is denied with the deny JSON and every safe form and mention is allowed (A4; spec V4)
- **Given** the same commands, **When** the worktree's `.venv` is a real directory, or the effective directory is the main checkout, **Then** nothing is denied (A5; spec V4, D3)
- **Given** a malformed payload, a payload with no `cwd`, a git binary that fails, and a bootstrap whose `uv` exceeds the timeout, **When** each mode runs, **Then** it exits 0, prints no deny, and the bootstrap prints exactly one banner line naming the command to run (A6; spec V5)

## Phase B — distribution, docs, Finish

Appetite: 75

**Interfaces — Produces** (`spec § The delta` D1, D4, D5):
- `.claude/settings.json` — the `worktree` block becomes `{"baseRef": "head"}` (`:141-146` today); a SessionStart entry
  (timeout 120, statusMessage "Worktree venv: own venv check...") and a PreToolUse entry with matcher `Bash` (timeout 5)
  register the hook with the existence-guarded command form of the Global Constraints.
- `scripts/fabrik_synced_manifest.py` — `".claude/hooks/worktree_venv.py"` joins `AGENT_HOOK_FILES` (`:271-286`) with a
  one-line comment; the `.venv` gitignore comment (`:457-460`) says the line now matches each worktree's own `.venv`
  directory and any legacy symlink.
- `templates/governance/.worktreeinclude` — regenerated with
  `python3 scripts/fabrik_synced_manifest.py --worktreeinclude > .wti.tmp && mv .wti.tmp templates/governance/.worktreeinclude`
  (gains the hook line).
- `.worktreeinclude` (hub root) — its header comment (`:4`) no longer says `.venv` is a `symlinkDirectories` entry.
- Docs: `docs/reference/multi-agent-operating-model.md` table row 2 (`:87`), the safety bullet (`:95-96`), the
  editable-install paragraph (`:327-333`) and the `.worktreeinclude` sentence (`:345-346`) state the new contract;
  `docs/workstation/hooks-index.md` gains a row for `worktree_venv.py` (SessionStart + PreToolUse); `INDEX.md` lists the
  hook file; `docs/DECISIONS.md` gains the row superseding the 2026-09-03 design's shared-venv choice
  (`spec § Decisions taken`); `CHANGELOG.md` one entry.

**Consumes:** Phase A (the hook's `main` modes and CLI).

**Mirror (named):** `tests/test_review_loop_workflow.py:194` asserts membership in `AGENT_HOOK_FILES` (unchanged);
`tests/test_scaffold_git_config.py:107-121` reads the regenerated `.worktreeinclude` template (must stay green);
`tests/test_governance_template_split.py:63` pins the template pair (unchanged). The scaffold copies the hub's
`.claude/` wholesale (`src/fabrik/scaffold.py:1295-1305`), so new projects get the hook and the block with no scaffold
edit.

1. **Write the failing test first** (B1) in `tests/test_worktree_venv.py`: parse `.claude/settings.json`; assert
   `"symlinkDirectories"` is absent or excludes `.venv`; for every hook command in the file, the hook script path it names
   is in `AGENT_HOOK_FILES` and in `worktreeinclude_text()`; the new hook's two registrations exist with the
   existence-guarded form. Confirm it fails on HEAD.
2. Edit `.claude/settings.json`, the manifest and the hub `.worktreeinclude` per the Interfaces; regenerate the template.
3. Run green: `.venv/bin/python -m pytest tests/test_worktree_venv.py tests/test_review_loop_workflow.py
   tests/test_scaffold_git_config.py tests/test_governance_template_split.py -q -p no:cacheprovider` → all pass; and
   `python3 -c "import json; json.load(open('.claude/settings.json'))"` → no error.
4. Prove the guard-on-existence form: in a scratch dir with a copy of the settings command and no hook file, run the
   command string under `sh -c` with `CLAUDE_PROJECT_DIR` set → exit 0, no output.
5. The doc edits per the Interfaces; `CHANGELOG.md` and `docs/DECISIONS.md` through the shared-append private-index
   recipe (`CLAUDE.md` § Behavior, the shared-repo bullet), the D-id minted with `python3 scripts/decisions.py
   --reserve-id .` inside that shell. Then `python scripts/enforcement/check_doc_sync.py`,
   `python scripts/enforcement/check_doc_index.py` and `python scripts/render_doc_script_links.py --check` → all exit 0.
6. **`/fabrik-review-scoped`** on Phase B's surface (the settings file, the manifest, both `.worktreeinclude` files, the
   two docs), run to its closing pass confirming 0.
7. **Finish — the heavy `/fabrik-review`** over the whole-plan diff (uncommitted vs the plan's base commit): the D7 floor
   — at least one Opus authoritative seat plus one Sonnet and one Haiku seat per independent failure-class group, sized
   by `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <groups>` and stamped with
   `python3 scripts/command_run.py dispatch --seats <n>` before they go out; the receipt at
   `docs/development/reviews/2026-10-06-plan-1-worktree-venv-isolation-review.md` embedding the verbatim
   `final_gate.py --json` success. Then `/fabrik-docs-review` over the two edited docs.
8. The full gate: `python scripts/final_gate.py --check --json` → `"status": "success"` (necessary, not sufficient — the
   Evidence below is the design proof), and `python scripts/enforcement/check_convergence.py` → exit 0.
9. ONE commit (explicit pathspecs + provenance trailers, `Agent-Phase: A,B`), push; the post-commit governance sync
   distributes it — read its summary line (projects synced, 0 failed). Then reply to trade-intelligence (mail
   01M3RYGETKD5HQZRBTDF3EK3EK; ack: no — the reply closes the loop) and close W-46d148b0 with `work.py done`.
10. Validation residue (`spec § Open/blocking unknowns`): count symlinked worktree `.venv` entries fleet-wide —
    `find /opt -maxdepth 4 -path '*/.claude/worktrees/*/.venv' -type l | wc -l` — before the commit and again after the
    hub's own worktree sessions restart; record both numbers in the receipt.

### Behavior Contract — Phase B

- **Given** the hub's `.claude/settings.json`, **When** it is parsed, **Then** `.venv` is not a `symlinkDirectories` entry, every hook script it registers is in `AGENT_HOOK_FILES` and in `worktreeinclude_text()`, and the new hook is registered for SessionStart and for PreToolUse `Bash` with the existence-guarded command (B1; spec V6, D1, D4)
- **Given** the registered command string and a tree without the hook file, **When** it runs under `sh -c`, **Then** it exits 0 with no output (B2; Global Constraints, Fable critique 6b)

## File Scope (owned paths)

- .claude/hooks/worktree_venv.py
- tests/test_worktree_venv.py
- .claude/settings.json
- scripts/fabrik_synced_manifest.py
- templates/governance/.worktreeinclude
- .worktreeinclude
- docs/reference/multi-agent-operating-model.md
- docs/workstation/hooks-index.md
- docs/superpowers/specs/2026-10-06-worktree-venv-isolation-design.md
- docs/development/reviews/2026-10-06-plan-1-worktree-venv-isolation-review.md

## Evidence

**Phase A.** The deny shape and payload reading the new hook follows:
```text
.claude/hooks/quota_stop.py:645: def main() -> int:
.claude/hooks/quota_stop.py:647:         payload = json.load(sys.stdin)
.claude/hooks/quota_stop.py:684:                         "permissionDecision": "deny",
.claude/hooks/quota_stop.py:685:                         "permissionDecisionReason": reason,
```
The defect, measured this session in a scratch repo (main + `git worktree add`, `.venv` symlinked to main's; the
editable `.pth` target is the oracle; uv 0.11.31):
```text
--- uv run                  → .../venvprobe/wt/src     (main's .pth re-pointed)
--- UV_NO_SYNC=1 uv run     → .../venvprobe/main/src   (unchanged)
--- uv sync                 → .../venvprobe/wt/src
--- UV_NO_SYNC=1 uv sync    → .../venvprobe/wt/src
```
The hub instance, restored by hand this session:
```text
== .venv/lib/python3.12/site-packages/_editable_impl_fabrik.pth
/opt/fabrik/.claude/worktrees/intel/src
```
Bootstrap cost: hub `uv sync` 15.03 s (828 MB by `du`); web-ecommerce-factory requirements (47 lines) 5.40 s, 135 MB.

**Phase B.** The block and registrations it changes, and the distribution list:
```text
.claude/settings.json:141:  "worktree": {
.claude/settings.json:142:    "baseRef": "head",
.claude/settings.json:143:    "symlinkDirectories": [
.claude/settings.json:144:      ".venv"
.claude/settings.json:127:    "PreToolUse": [
scripts/fabrik_synced_manifest.py:271: AGENT_HOOK_FILES = [
templates/governance/.worktreeinclude:18: .claude/hooks/quota_stop.py
```
The docs that state the old contract: `docs/reference/multi-agent-operating-model.md:87`, `:95-96`, `:327-333`,
`:345-346`; the hub `.worktreeinclude:4`.

## Self-audit

- Grounding passes: three spec-time seats (Claude Code docs; uv docs + field practice; fleet survey of 36 repos), the
  two design critiques (Opus, Fable) of the `/fabrik-task` design, the three-seat judge panel; every `path:line` above
  re-read this run.
- (a) Coverage: spec D1 → Phase B step 2; D2 → Phase A (A2, A3); D3 → Phase A (A4, A5); D4 → Phase B (B1); D5 → Phase B
  step 5; V1–V5 → A1–A6; V6 → B1; the open unknown's CLI form → Phase A `main --bootstrap`; the residue count → Phase B
  step 10; the reply and the work-item close → Phase B step 9. No gap.
- (b) Signatures: Phase B consumes only `main`'s mode names (`session-start`, `pre-tool-use`, `--bootstrap`) and the
  file path; both are defined once in Phase A's Interfaces and used verbatim in B's settings commands and B1.
- Fixed point: not yet — `/fabrik-plan-review` grades it.

## Residual unknowns

- **Resolved:** `cwd` follows `cd` (documented); `no-sync` is not a uv setting (measured); bootstrap cost (measured);
  the scaffold carries the hook to new projects with no edit (`src/fabrik/scaffold.py:1295-1305`).
- **Open — the guard's per-call cost:** resolution step: Phase A step 5 measures it; a median above 50 ms moves the
  string pre-filter earlier before Phase B.
- **Open — requirements-only subagent worktrees after D1:** resolution step: the `--bootstrap` CLI form (Phase A) and
  its line in the operating model (Phase B step 5).
- **Open — non-Claude shells writing through a not-yet-converted link:** resolution step: Phase B step 10 counts the
  residue; recorded in the receipt.

## Coverage Checklist

| Class | Status |
|---|---|
| Hunt: `.claude/hooks/worktree_venv.py` — every function, its callers in settings.json | UNCHECKED |
| Hunt: `.claude/settings.json` — the block and both registrations | UNCHECKED |
| Hunt: `scripts/fabrik_synced_manifest.py` + both `.worktreeinclude` files | UNCHECKED |
| Hunt: the two docs — every changed claim against the code | UNCHECKED |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | UNCHECKED |
| Recurrence: boundary/sentinel/prefix — a prefix-vs-exact match (verb heads, paths) | UNCHECKED |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | UNCHECKED |
| Recurrence: denominator on every count — bounded searches state their bound | UNCHECKED |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | UNCHECKED |

Rubric invocation (verbatim output — the gate reads the generated header):

```text
$ python scripts/review_rubric.py --changed .claude/hooks/worktree_venv.py tests/test_worktree_venv.py .claude/settings.json scripts/fabrik_synced_manifest.py templates/governance/.worktreeinclude .worktreeinclude docs/reference/multi-agent-operating-model.md docs/workstation/hooks-index.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: .claude/hooks/worktree_venv.py, scripts/fabrik_synced_manifest.py, tests/test_worktree_venv.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: docs/reference/multi-agent-operating-model.md, docs/workstation/hooks-index.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_worktree_venv.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 82 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `postgres:16-alpine` `plpgsql` `postgres-main`
- `postgres-main` `docs/DECISIONS.md`
```
