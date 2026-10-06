# Worktree venv isolation — each linked worktree owns its venv

**Status:** DRAFT
**Size:** small (≈230 lines, 4 files)
**Profile:** delta
**Owner:** infra
**Work item:** W-46d148b0 · trade-intelligence mail 01M3RYGETKD5HQZRBTDF3EK3EK · UPGRADE: tradeoffs from `/fabrik-task` (2026-10-06)

## Personas

- **Primary — the worktree agent** (infra/fleet/intel in the hub, agent-2..N in a project): an
  automated Claude Code session working in `.claude/worktrees/<name>`. In the reporter's words:
  *"`uv run` is the natural test command for an agent."* Its loop today (measured): open the
  worktree (1) → edit code (2) → `uv run pytest` (3) → the shared venv's editable install is
  re-pointed at its src and its packages re-synced (side effect on every other window) → gate (4)
  → commit + push (5). **Step budget: 5 steps, 0 hidden side effects.** This design keeps the 5
  steps and removes the side effect; the first session in a worktree pays one bootstrap (~5–15 s,
  measured) inside SessionStart, not a step.
- **The merge owner / main-checkout agent** (infra in the hub; agent-1 in a project): runs tools
  from the main `.venv`; today its imports silently follow whichever worktree synced last
  (the hub, 2026-10-06: `_editable_impl_fabrik.pth` → `.claude/worktrees/intel/src`).
- **Subagent worktree checkouts** (`isolation: "worktree"` — coders, review seats): get no
  SessionStart; they hold no duty here but must not damage the main venv.
- **Automated consumers:** `scripts/final_gate.py` (runs `<cwd>/.venv/bin/python`,
  `scripts/final_gate.py:70-80`), the Stop hook (`.claude/hooks/final_gate_stop.py:229-234`),
  `scripts/merge_request.py`'s owner tests (MAIN venv + sitecustomize shim,
  `scripts/merge_request.py:1073-1115` — unaffected), the governance sync
  (`scripts/sync_enforcement_to_projects.py`, which distributes the settings file and hooks).
- **The operator** in a plain terminal: outside every hook; protected only by the structural fix.

Every mechanism names its holder: the bootstrap and the guard run in the **worktree agent's**
session (hook); the settings change is distributed by the **governance sync**; the migration of
existing symlinked worktrees happens in each **worktree agent's** next session.

## Goal

A linked worktree never writes into the main checkout's `.venv`, and a worktree's tests run the
worktree's own code — in all 36 repos that sync `.claude/settings.json`, without changing the
test command agents are told to run.

## Why this exists

`.claude/settings.json` carries `{"worktree": {"baseRef": "head", "symlinkDirectories": [".venv"]}}`
(synced fleet-wide via `scripts/fabrik_synced_manifest.py:272`). The 2026-09-03 multi-agent spec
made the shared venv "safe because D4 makes `uv.lock` identical across an epic's branches"
(`docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md:137`). Measured 2026-10-06 that
precondition does not hold: `uv run --frozen` with an identical lock still re-points the editable
install, and only 4 of the 36 repos track a `uv.lock`. Incidents: trade-intelligence 2026-09-30
twice (SQLAlchemy 2.0.52 → 2.1.1 red-lit every agent's mypy; the editable install re-pointed at
agent-3's src); the hub 2026-10-06 (every hub tool outside a conftest imported intel's branch;
restored by hand). And while shared, a worktree's own tests import the MAIN checkout's src
(path-style `.pth` in 8 repos), so they test the wrong code. Each worktree owning its venv removes
the shared mutable state, so both failures stop at the root.

## What exists today (grounded)

| Fact | Anchor |
|---|---|
| The synced block symlinks `.venv` into every new worktree | `.claude/settings.json` (`worktree` block); `scripts/fabrik_synced_manifest.py:272` |
| Worktrees receive hooks by `.worktreeinclude`, which enumerates each hook file | `templates/governance/.worktreeinclude:14-20`; `scripts/fabrik_synced_manifest.py:478-490` |
| SessionStart hooks exist, with per-hook timeouts | `.claude/settings.json:46-77` |
| One PreToolUse hook today (quota hold), deny via `hookSpecificOutput.permissionDecision` | `.claude/hooks/quota_stop.py:645-690` |
| The gate and Stop hook run `<cwd>/.venv/bin/python`, falling back to `sys.executable` | `scripts/final_gate.py:70-80`; `.claude/hooks/final_gate_stop.py:229-234` |
| Owner tests run under the MAIN venv with a shim putting the worktree's src first | `scripts/merge_request.py:1073-1115` |
| The operating model states the shared venv's (false) safety condition | `docs/reference/multi-agent-operating-model.md:95-96` |
| Rule packs order `uv run pytest` / `uv sync` | `.windsurf/rules/core/10-python.md:25-27`; `.windsurf/rules/core/45-testing-strategy.md:48` |
| Fleet survey (2026-10-06): 36 repos sync the block; 11 run linked worktrees (~140 worktrees, most `.venv` symlinked; seo 28 with none); uv.lock tracked in 4 (fabrik, brand-identiy-creator, candle, job-agent); path-style editable `.pth` in 8, a finder-style editable in 1 (youtube `mt_router`); several requirements.txt-only | Explore seat survey, this run |

Measured in a scratch repo (uv 0.11.31, main + `git worktree add` + `.venv` symlinked to main's;
the editable `.pth` target after each command is the oracle), by me and both critique seats:

| From the worktree | Main venv after |
|---|---|
| `uv run`, `uv run --frozen`, `--locked`, `--with X`, `--active` | editable re-pointed to the worktree |
| `uv sync` (also `--frozen`, `UV_NO_SYNC=1`), `uv add X`, `uv pip install -e .` | re-pointed / packages changed |
| `uv sync --no-install-project` | project editable removed |
| `uv venv --clear`, `rm -rf .venv/`, `rm -rf .venv/*` | main venv emptied |
| `uv run --no-sync`, `--no-project`, `--isolated`, `UV_NO_SYNC=1 uv run`, `uv lock`, `uv sync --check`, `uv sync --dry-run`, `uv add --no-sync` | unchanged |
| a real (non-symlink) `.venv` in the worktree, then any of the above | unchanged (writes the worktree's own venv) |

Per-worktree venv cost, measured: the hub (`uv sync`, pyproject + lock) 15.0 s; web-ecommerce-factory
(requirements.txt, 47 lines: `uv venv` + `uv pip install -r`) 5.4 s, 135 MB by `du` (files are cloned
from uv's cache on the same filesystem, so real disk use is far lower).

## The delta

**D1 — settings.** The synced block becomes `{"worktree": {"baseRef": "head"}}` — `.venv` leaves
`symlinkDirectories` (the key is dropped; nothing else was listed). New worktrees get no venv link.

**D2 — bootstrap (SessionStart).** A new synced hook `.claude/hooks/worktree_venv.py`, registered
for SessionStart, acts ONLY when the session cwd's git toplevel is a LINKED worktree
(`realpath(git-dir)` ≠ `realpath(git-common-dir)`, both resolved against cwd — a plain string
compare misfires in a subdirectory). When that worktree's `.venv` is missing or is a symlink:
1. a symlink is removed with `os.unlink` — never a recursive delete (`rm -rf .venv/` through the
   link empties the main venv; measured);
2. it builds the worktree's own venv: `uv sync` when `pyproject.toml` exists; else `uv venv` and
   `uv pip install -r` for each `requirements*.txt` present; else nothing;
3. bounded by a timeout inside the hook's own budget; on timeout or failure it prints one banner
   line naming the exact command to run by hand and exits 0 (fail-open: a bootstrap failure never
   blocks a session).
A real `.venv` directory is never touched. The main checkout is never touched.

**D3 — guard (PreToolUse, Bash), only while a link remains.** The same file, registered for
PreToolUse with matcher `Bash`, denies a command when, for any `&&`/`||`/`;`/`|` segment, the
effective directory (payload `cwd` — it follows Claude's `cd` — plus a leading `cd X`, and uv's
`--directory`/`--project`/`UV_PROJECT=`) is a linked worktree whose `.venv` is STILL a symlink, and
the segment's command (shlex-split; leading `NAME=value` assignments, `env`, `timeout N` skipped) is
a venv writer: `uv run` without `--no-sync`/`--no-project`/`--isolated`/`--script` and without a
`UV_NO_SYNC=1` prefix; `uv sync` without `--check`/`--dry-run`; `uv add`/`uv remove` without
`--no-sync`; `uv pip install|uninstall|sync`; `uv venv`; `pip`/`pip3`/`python[3] -m pip`/
`.venv/bin/pip` `install|uninstall`; `rm` naming `.venv/` or `.venv/*`. The reason names the fix:
`rm .venv` (no trailing slash) then the D2 build command. Text that merely mentions a verb (a grep
pattern, a commit message) is not a command head and is allowed. Once the worktree has its own
venv the guard never fires there. Fail-open on any parse or git error.

**D4 — distribution.** `.claude/hooks/worktree_venv.py` joins `AGENT_HOOK_FILES`
(`scripts/fabrik_synced_manifest.py:271`) and therefore `.worktreeinclude`; the settings file and
the hook ship in the same sync, so no repo carries a registration without its file (a missing
hook file would fail every Bash call with exit 2).

**D5 — docs.** `docs/reference/multi-agent-operating-model.md` § Environment inside a worktree and
its table row 2 (`:87`, `:95-96`) state the new contract (own venv, bootstrap, guard, the old
precondition's measured falsity); `docs/workstation/hooks-index.md` lists the hook; the rule packs
are unchanged (`uv run pytest` is correct in an own venv).

## Contract deltas

None to data or UI contracts. The governance surface changes: `.claude/settings.json` (synced, 36
repos) and one new synced hook.

## Chosen approach

**C — one venv per worktree, plus a guard while a symlink remains** (D1–D4). Judge panel (three
Sonnet seats, approaches unranked and alphabetical, no recommendation shown): **3 of 3 ranked C
first**; all three scored A (guard the shared venv) as failing "complex where simple exists" and
"build where consume exists". C consumes uv's own per-project venv model, which the field practice
recommends — *"Keep `node_modules/` local; share the package-manager store or cache instead"* and
*"For Python `.venv/`, reuse may be reasonable when dependency inputs, interpreter, platform, and
tool behavior match. Still, preserve existing local environments and stop sharing when inputs
drift."* (https://dev.to/jamesjf7/share-env-not-dependency-drift-across-git-worktrees-4d3o, fetched
2026-10-06 via WebSearch + fetch); a per-worktree uv venv workflow
(https://fbruzzesi.github.io/blog/2025/07/20/stop-context-switching-how-git-worktree--uv-revolutionized-my-python-workflow/,
fetched 2026-10-06); uv clones from its cache when it shares the filesystem — *"It is important for
performance for the cache directory to be located on the same file system as the Python
environment uv is operating on"* (https://docs.astral.sh/uv/concepts/cache/, fetched 2026-10-06 via
exa). The structural part (D1+D2) protects against every writer, including a plain terminal; the
guard (D3) only covers Claude's Bash tool during the migration window and for subagent worktrees
created before D1 lands.

## Rejected alternatives

- **A — guard the shared venv permanently.** A shell-parsing denylist that must track uv's verb
  surface, misses Makefile wrappers (12 repos) and every non-Claude shell, and still leaves a
  worktree's tests importing main's code unless every run carries `PYTHONPATH=src uv run --no-sync`
  (which the rule packs would then have to teach). Panel: 0 of 3.
- **B alone — own venvs with no guard.** Leaves ~140 existing symlinked worktrees and pre-D1 subagent
  checkouts writing through the link until their next SessionStart, silently. C adds the guard for
  that window. Panel: ranked below C by all three.
- **`UV_NO_SYNC=1` in settings `env`.** Neutralises every `uv run` form, but `env` applies to the
  main checkout too (main's `uv run` stops syncing after a pyproject edit), and it does not cover
  `uv sync`/`pip install`/`uv venv --clear` (measured).
- **PreToolUse `updatedInput` rewrite** (`uv run` → `uv run --no-sync`, documented since v2.0.10 at
  code.claude.com/docs/en/hooks, fetched 2026-10-06): silent rewriting keeps the shared venv and its
  wrong-code imports; a deny that names the fix is visible.
- **`UV_PROJECT_ENVIRONMENT` per worktree:** uv documents it for single-project CI/Docker only
  (*"This setting is only recommended for use for a single project in CI or Docker images"*,
  https://docs.astral.sh/uv/concepts/projects/config/, fetched 2026-10-06), and settings `env`
  cannot carry a per-worktree value.
- **`no-sync` in `uv.toml` / `[tool.uv]`:** not a setting — `uv.toml` with `no-sync = true` fails to
  parse; `[tool.uv]` ignores it (measured by the Fable critique seat).
- **A `WorktreeCreate` hook building the venv:** the hook *"replace[s] the default `git worktree`
  logic entirely"* and skips `.worktreeinclude` (code.claude.com/docs/en/worktrees, fetched
  2026-10-06) — the hook would have to re-implement checkout and copies for 36 repos.
- **A read-only main venv:** loud, but main's own `uv sync` then needs a chmod wrapper, and uv's
  cache-cloned files share inodes.
- **Extending `merge_request.py`'s sitecustomize shim to every runner:** fixes which src is imported
  but leaves the shared venv writable from every worktree, and needs every runner to adopt the shim.

## Lifecycle

- **Adoption:** the governance sync distributes D1+D4 to the 36 repos' main checkouts; the
  worktree re-copy loop refreshes existing worktrees. Each existing symlinked worktree converts on
  its next session (D2); until then D3 denies its writers.
- **Growth:** one venv per live worktree. Disk is cache-cloned; the count is bounded by live
  worktrees (scratch_sweep removes dead ones). Trigger to revisit: a repo whose bootstrap exceeds
  the hook budget on 3 consecutive sessions (the banner says so) → raise that repo's budget or
  pre-build.
- **Degradation:** bootstrap failure → banner + fail-open; the gate then falls back to
  `sys.executable` and reports missing tools/deps loudly (`scripts/final_gate.py:80`). Guard parse
  error → allow.
- **Retirement:** D3 goes inert once no worktree has a symlinked `.venv`; it can be removed by a
  later change when a fleet scan finds zero symlinked worktree venvs.

## External dependencies

| Dependency | Grounded fact | Source (fetched 2026-10-06) |
|---|---|---|
| Claude Code `worktree.symlinkDirectories` | *"Symlink directories from the main repository into each worktree so you don't duplicate large directories on disk."* | https://code.claude.com/docs/en/settings-reference |
| Claude Code PreToolUse payload | *"`cwd` follows Claude: the `cwd` field in the hook's input JSON is the worktree root, and it moves again when Claude runs `cd`."* | https://code.claude.com/docs/en/worktrees |
| Claude Code PreToolUse deny | `hookSpecificOutput.permissionDecision: "deny"` blocks the tool, even under bypassPermissions | https://code.claude.com/docs/en/hooks |
| uv sync semantics | *"`uv sync` performs 'exact' syncing by default, which means it will remove any packages that are not present in the lockfile."* | https://docs.astral.sh/uv/concepts/projects/sync/ |
| uv `--no-sync` | *"Avoid syncing the virtual environment [env: UV_NO_SYNC=]"* | https://docs.astral.sh/uv/reference/cli/ |
| uv editable install | *"By default, the project will be installed in editable mode"* | https://docs.astral.sh/uv/concepts/projects/config/ |

## fabrik-lib verdict

One line: no module covers Claude Code hooks or venv layout → BUILD, hub-only (a hook is not a
fabrik-lib candidate: it is governance, distributed by the sync).

## Shape/infra implications

None — no deployed service, no `shape:` flag. Hub governance only.

## Documentation landing sites

`docs/reference/multi-agent-operating-model.md` § Environment inside a worktree (the contract);
`docs/workstation/hooks-index.md` (the hook row); `CHANGELOG.md`; a `docs/DECISIONS.md` row
superseding the shared-venv clause of the 2026-09-03 design (R5 / D4 reasoning); `INDEX.md` for the
new hook file.

## Constraints

| Rule | Quote | Source |
|---|---|---|
| uv is the package manager | **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | .windsurf/rules/core/10-python.md:22 |
| test runner | uv run pytest                   # Run via uv | .windsurf/rules/core/10-python.md:27 |
| deps files | Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | .windsurf/rules/core/10-python.md:30 |
| lock is the pin | **Pinning policy:** `uv.lock` IS the pin — `pyproject.toml` uses `>=` floors, no routine upper | .windsurf/rules/core/10-python.md:32 |
| run tests | - **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has | .windsurf/rules/core/45-testing-strategy.md:48 |
| behaviour tests | - **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and | .windsurf/rules/core/45-testing-strategy.md:20 |
| red first | - **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a | .windsurf/rules/core/45-testing-strategy.md:22 |
| config | => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. | .windsurf/rules/core/35-security-auth.md:267 |

Applied: D2 installs with `uv` for pyproject repos and `uv pip install -r` for requirements-only
repos (no raw pip); no deps file is edited; the rule packs' `uv run pytest` stays correct. The
1b-bis hard constraints (LLM gateway, vector DB, billing, Alpine, ports) do not apply (no service).

## Open/blocking unknowns

- **Resolved:** whether `cwd` follows `cd` (yes, documented); whether `no-sync` is a uv setting (no);
  bootstrap cost (5.4–15 s, measured).
- **Open — requirements-only repo + subagent worktree after D1:** no SessionStart, no `.venv`; the
  gate falls back to `sys.executable` and fails loudly on missing deps. Resolution step: the plan
  adds a `python3 .claude/hooks/worktree_venv.py --bootstrap` CLI form and names it in the gate's
  missing-venv message (one line), so a subagent can self-serve.
- **Open — a non-Claude shell writing through a not-yet-converted symlink:** outside every hook;
  closed only as worktrees convert. Resolution step: the plan's validation counts symlinked
  worktree venvs fleet-wide after the sync and reports the residue.

## Cost

≈230 code lines in 4 code files (the new hook ~200, `.claude/settings.json` registration + block,
`scripts/fabrik_synced_manifest.py` +1, `templates/governance/.worktreeinclude` regenerated) plus
tests (~150) and docs. One governance-sync commit after the full `/fabrik-review`.

## Validation

- V1: a scratch repo + linked worktree with a symlinked `.venv`: SessionStart (hook invoked with a
  SessionStart payload) replaces the link with an own venv; the main venv's editable `.pth` is
  byte-identical before and after; a `uv run` in the worktree imports the worktree's src.
- V2: a requirements-only scratch repo gets an own venv with its requirements installed.
- V3: a real `.venv` directory in a worktree and the main checkout are never modified.
- V4: the guard denies each writer form in the table above from a symlinked-venv worktree (including
  `cd <wt> && uv sync` from main and `uv run --directory <wt>`), allows the safe forms and verb
  mentions (`grep "uv sync"`, `git commit -m "… pip install …"`), and allows everything once the
  venv is real.
- V5: fail-open — a malformed payload, a git failure, a bootstrap timeout: exit 0, banner only.
- V6: the sync manifest lists the hook; `.worktreeinclude` regenerated carries it; a settings file
  without the hook file cannot ship (a test asserts every hook path registered in settings.json is in
  `AGENT_HOOK_FILES`).
Each V is red on HEAD first.

## Decisions taken

- Per-worktree venvs replace the shared symlinked venv fleet-wide (supersedes the 2026-09-03
  design's "`.venv` symlinked" choice and its D4 safety reasoning) — REVERSIBLE (re-adding the key
  restores sharing).
- A guard covers only the window while a symlink remains; it is not a permanent policy layer.
- One new hook file holds both the bootstrap and the guard (one owner for the venv contract;
  `session_orient.py` stays an orientation printer).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"A `uv run` or `uv sync` inside a worktree finds no uv.lock there … and syncs the SHARED venv to that resolution."* (mail 01M3RYGE) | IN | § Why this exists; D1–D3 |
| I2 | *"the editable install of trade_intelligence re-pointed at agent-3's worktree src, so any process started from main imported another agent's code"* | IN | D1+D2 (own venvs); V1 |
| I3 | *"SQLAlchemy 2.0.52 -> 2.1.1, which red-lit the gate's mypy leg for every agent"* | IN | D1+D2 — a worktree's resolution no longer reaches main |
| I4 | Direction (1): *"worktree setup sets UV_PROJECT_ENVIRONMENT / a uv config so a worktree `uv run` refuses to sync, or gives each worktree its own venv"* | IN | Chosen approach (own venv); the config half rejected (§ Rejected) |
| I5 | Direction (2): *"a PreToolUse hook refuses `uv run|uv sync|pip install` from a linked worktree"* | IN (narrowed) | D3 — only while a link remains |
| I6 | Direction (3): *"the seat-brief and operating-model docs name it as a serialising act"* | IN | D5 (operating model); seat briefs already ban package-manager verbs (D-587) |
| I7 | The hub recurrence 2026-10-06 (`_editable_impl_fabrik.pth` → intel's src) | IN | § Why this exists; restored by hand, prevented by D1+D2 |
| I8 | Critique: a worktree's tests import main's code while sharing (Opus critique 1) | IN | § Goal; V1 |
| I9 | Critique: Makefile wrappers (12 repos) bypass a command guard | IN | structural fix covers them once converted; § Open unknowns |
| I10 | Critique: rule packs order `uv run pytest` | IN | unchanged — correct under own venvs |
| I11 | Critique: `.worktreeinclude` enumerates hooks; missing hook file blocks Bash | IN | D4; V6 |
| I12 | Judge flaw: requirements-only subagent worktree gets no venv | IN | § Open unknowns (CLI bootstrap form) |
| I13 | Judge flaw: non-Claude shells are outside any hook | IN | § Chosen approach (structural part); § Open unknowns |

Intake: 13 items — 13 IN, 0 OUT-OF-SCOPE, 0 ASK.
