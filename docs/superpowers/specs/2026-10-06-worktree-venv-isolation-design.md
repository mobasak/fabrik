# Worktree venv isolation — each linked worktree owns its venv

**Status:** CONVERGED
**Size:** small (≈310 lines, 3 code files + 3 config files)
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
  `scripts/merge_request.py:1073-1115` — unchanged code, one new merge-owner step after a dependency change, D6), the governance sync
  (`scripts/sync_enforcement_to_projects.py`, which distributes the settings file and hooks).
- **The operator** in a plain terminal: outside every hook; protected only by the structural fix.

Every mechanism names its holder: the bootstrap and the guard run in the **worktree agent's**
session (hook); the settings change is distributed by the **governance sync**; the migration of
existing symlinked worktrees happens in each **worktree agent's** next session.

## Goal

A linked worktree never writes into the main checkout's `.venv`, and a worktree's tests run the
worktree's own code — in all 48 repos whose synced `.claude/settings.json` carries the block, without changing the
test command agents are told to run.

## Why this exists

`.claude/settings.json` carries `{"worktree": {"baseRef": "head", "symlinkDirectories": [".venv"]}}`
(synced fleet-wide via `scripts/fabrik_synced_manifest.py:272`). The 2026-09-03 multi-agent spec
made the shared venv "safe because D4 makes `uv.lock` identical across an epic's branches"
(`docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md:137`). Measured 2026-10-06 that
precondition does not hold: `uv run --frozen` with an identical lock still re-points the editable
install, and only 4 of those 48 repos track a `uv.lock`. Incidents: trade-intelligence 2026-09-30
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
| Fleet survey (2026-10-06): 51 repos carry `/opt/*/.claude/settings.json` (archived excluded), 48 of them with `symlinkDirectories`; 11 run linked worktrees; 100 worktree `.venv` entries were symlinks when this review began, a count that grows as agents create worktrees — 102 during round 6 (`find /opt -maxdepth 5 -path '*/.claude/worktrees/*/.venv' -type l`; seo's 28 worktrees have none); uv.lock tracked in 4 (fabrik, brand-identiy-creator, candle, job-agent); path-style editable `.pth` in 8, a finder-style editable in 1 (youtube `mt_router`); several requirements.txt-only | Explore seat survey, this run |

Measured in a scratch repo (uv 0.11.31, main + `git worktree add` + `.venv` symlinked to main's;
the editable `.pth` target after each command is the oracle), by me and both critique seats:

| From the worktree | Main venv after |
|---|---|
| `uv run`, `uv run --frozen`, `--locked`, `--with X`, `--active` | editable re-pointed to the worktree |
| `uv sync` (also `--frozen`, `UV_NO_SYNC=1`), `uv add X`, `uv pip install -e .` | re-pointed / packages changed |
| `uv sync --no-install-project` | project editable removed |
| `uv venv --clear`, `rm -rf .venv/`, `rm -rf .venv/*`, `rm -r .venv/lib`, `find .venv/ … -delete` | main venv emptied |
| `uv run --script x.py` (no inline `# /// script` block), `uv -q sync`, `uv --offline run`, `uv version --bump patch`, `uv run --no-sync uv pip install x`, `.venv/bin/python -m ensurepip`, `bash -c "uv sync"` | changed (round-1 Opus seat, executed) |
| `uv venv` without `--clear` (non-TTY) | refused, rc 2 — unchanged |
| `uv run --no-sync`, `--no-project`, `--isolated`, `UV_NO_SYNC=1 uv run`, `uv lock`, `uv sync --check`, `uv sync --dry-run`, `uv add --no-sync`, `uv export`, `uv tree`, `uv build`, `uvx` | unchanged |
| a real (non-symlink) `.venv` in the worktree, then any of the above | unchanged (writes the worktree's own venv) — except with `VIRTUAL_ENV` pointing at the main venv: `uv pip install` and `uv run --active` then write main |

Shell grammar defeats a command parser (executed, Python `shlex` with `punctuation_chars`): a newline
joins two commands into one token list (`echo ok\nuv sync` → `['echo','ok','uv','sync']`), a mid-word
`#` starts a comment (`echo a#b; uv sync` → `['echo','a']`), `bash -c "uv sync"` is one token, and an
unbalanced quote raises. D3 therefore matches words, not grammar.

Per-worktree venv cost, measured: the hub (`uv sync`, pyproject + lock) 15.0 s; web-ecommerce-factory
(requirements.txt, 47 lines: `uv venv` + `uv pip install -r`) 5.4 s, 135 MB by `du` (files are cloned
from uv's cache on the same filesystem, so real disk use is far lower).

## The delta

**D1 — settings.** The synced block becomes `{"worktree": {"baseRef": "head"}}` — `.venv` leaves
`symlinkDirectories` (the key is dropped; nothing else was listed). New worktrees get no venv link.

**D2 — bootstrap (SessionStart).** A new synced hook `.claude/hooks/worktree_venv.py`, registered
for SessionStart, acts ONLY when the session cwd's git toplevel is a LINKED worktree
(`realpath(git-dir)` ≠ `realpath(git-common-dir)`, both resolved against cwd — a plain string
compare misfires in a subdirectory). When that worktree's `.venv` is missing, is a symlink, or the
PENDING marker of step 3 exists:
1. a symlink is removed with `os.unlink` — never a recursive delete (`rm -rf .venv/` through the
   link empties the main venv; measured);
2. it builds the worktree's own venv by MIRRORING the main checkout's (design critiques, Opus + Fable,
   executed: a plain `uv sync` installs no `[project.optional-dependencies]` — where 16 of 27 pyproject
   repos keep pytest, mypy and ruff — picks the newest managed interpreter (3.13 against main's 3.12),
   ignores `requirements*.txt` beside a `[project]` table and writes an untracked `uv.lock`):
   Two values, never interchanged: INTERP = `realpath(<main>/.venv/bin/python)` (the base interpreter)
   and MAINENV = `<main>/.venv/bin/python` unresolved (the venv itself — a freeze through INTERP lists the
   system site-packages; executed).
   - interpreter: `uv venv --python INTERP .venv`;
   - packages: `uv pip freeze --python MAINENV --exclude-editable` installed into the new venv
     with `uv pip install -r` — the worktree starts on exactly the versions main runs, so the I3 drift
     cannot appear and no lock is written;
   - then what the branch itself declares, inexact (installed pins kept): every `requirements*.txt` in
     one `uv pip install -r … -r …`, and `uv pip install -e .` when the project declares a build system;
   - a repo that tracks `uv.lock` (4 today) runs `uv sync --all-extras --python INTERP` instead —
     the lock is the pin (`core/10-python.md:32`);
   - no main venv: `uv sync --all-extras` for a `[project]` table, else `uv venv`; then, in both cases,
     the same inexact requirements install (a `[project]` table beside a `requirements.txt` otherwise
     never gets its requirements; executed), and the banner says so.
   Executed on a scratch project with pytest in a `dev` extra: pytest present, Python equal to main's,
   `1 passed`, no `uv.lock` written.
3. two files in the worktree's own git dir (`git rev-parse --git-path …`, never the working tree): a LOCK
   file `fabrik-venv-bootstrap.lock`, created once and never removed, and a PENDING marker
   `fabrik-venv-bootstrap.pending`. A build takes an exclusive non-blocking `flock` on the lock file (held
   → another build is running, return at once) and, under that lock only, re-checks: `.venv` real and
   no PENDING marker → nothing to do, release and return. Otherwise it writes the marker, builds, and
   removes the marker only when the venv VALIDATES (its python minor equals INTERP's, it imports the
   project when one is installed, and it has pytest when main's venv has it; with no main venv, only
   the import). Every read and write of the marker happens under the lock, and the lock file is never
   unlinked, so two sessions can neither build at once nor rebuild a venv the other just validated. A
   failed or timed-out build leaves the marker with the failing command and its exit code written in
   it; the next banner prints them and the next session or `--bootstrap` rebuilds — the hook writes no
   log file (`core/10-python.md:294`);
4. the build runs DETACHED (a heavy repo — iterative_image_editor's main venv is 2.6 GB with torch —
   cannot finish inside a SessionStart budget): SessionStart starts it with its output discarded,
   prints one banner line naming `python3 <absolute hook path> --bootstrap` as the fix (run in the
   background for a heavy repo), and exits 0 at once (fail-open: a bootstrap
   failure never blocks a session; the PENDING marker carries a failed build to the next session);
5. when `VIRTUAL_ENV` resolves to another checkout's `.venv`, the banner says so (that inherited
   variable makes `uv pip install` and `uv run --active` write the other checkout's venv).
A real `.venv` directory is never touched unless the PENDING marker, read under the lock, says its last
build did not finish. The
main checkout is never touched.

**D3 — guard (PreToolUse, Bash), only while a link remains or no own venv exists yet.** The same file, registered for
PreToolUse with matcher `Bash`, matches WORDS, never shell grammar (the parser failures above). It
denies when BOTH hold:
1. a TARGET is a linked worktree whose `.venv` is still a symlink, OR is missing in a worktree that
   has a `pyproject.toml` or a `requirements*.txt` (subagent `isolation: worktree` checkouts get no
   SessionStart — 92 of the 101 worktree links counted at the start of round 6 were `agent-*` worktrees — so a
   missing venv is the same window; a worktree of a repo with no Python manifest is never a target,
   since nothing could build it) — targets are the payload `cwd` (it
   follows Claude's `cd`) and every token of the command — split on whitespace and on `;&|()<>`, with
   quotes, a leading `NAME=` or `--name=` and a trailing `/` stripped — that resolves (relative to `cwd`, `~` expanded) to an
   existing path inside a linked worktree;
2. the raw command text contains, as a whole word (not preceded or followed by `[A-Za-z0-9_.-]`),
   `uv`, `uvx`, `pip`, `pip3`, `ensurepip`, `virtualenv`, `venv`, `poetry`, `pdm`, `pip-sync`,
   `pip-compile` or `piptools` (`python3 -m venv --clear .venv` empties the main venv through the link;
   executed), or — after removing quote characters — the substring `.venv/`.
The fix itself carries no trigger — `rm .venv` (no slash) and `python3 <absolute hook path>
--bootstrap` match neither list — so it is never denied; the deny prints the ABSOLUTE hook path, so the
fix works from any subdirectory. Over-deny is accepted on purpose:
inside the window even a mention (`grep "uv sync"`) is denied, the deny says why and names the
fix — `rm .venv` (no trailing slash) when it is a link, then `python3 <absolute hook path> --bootstrap`
— and the window closes at the next session start or when that `--bootstrap` runs (a subagent worktree
has no session start; the deny is how it learns the command). Once the worktree has its own venv the guard never
fires there. Writers it cannot see (a script or Makefile that runs uv) are covered only by D1+D2,
the structural part. The deny is JSON on stdout with exit 0; no mode exits 2. Fail-open on any
error.

**D4 — distribution.** `.claude/hooks/worktree_venv.py` joins `AGENT_HOOK_FILES`
(`scripts/fabrik_synced_manifest.py:271`) and therefore `.worktreeinclude`; the settings file and
the hook ship in the same sync; the registration's command also checks the file exists
(`[ -f "$f" ] && python3 "$f" <mode> || exit 0`), because a missing hook file would otherwise fail
every Bash call with exit 2.

**D6 — the merge owner after a dependency change.** Owner tests run a branch's `src` under the MAIN
venv (`scripts/merge_request.py:1073-1115`); with D1 no worktree syncs that venv any more, so after a
merge that changes `pyproject.toml`, `requirements*.txt` or `uv.lock` the merge owner refreshes it
the way it was built — `uv sync --all-extras` where `uv.lock` is tracked; otherwise the inexact
`uv pip install -r` of each requirements file and `uv pip install -e .` — so no untracked `uv.lock`
appears in main — before the next owner test. The operating model
states the step; the refusal text that names it on a `ModuleNotFoundError` is routed to the owner of the
concurrent `merge_request.py` work (mail 01M46NZM).

**D5 — docs.** `docs/reference/multi-agent-operating-model.md` § Environment inside a worktree and
its table row 2 (`:87`, `:95-96`, `:326-332`, `:345-346`) state the new contract (own venv mirrored from main, bootstrap,
guard, the merge owner's D6 step, the old precondition's measured falsity); `docs/workstation/hooks-index.md` lists the hook; the rule packs
are unchanged (`uv run pytest` is correct in an own venv).

## Contract deltas

None to data or UI contracts. The governance surface changes: `.claude/settings.json` (synced, 48
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
- **A shell-grammar guard** (segment splitting with `shlex`, verb at segment head — the first D3 draft):
  round 1 of this review executed spellings that hide a writer from it (a newline, a mid-word `#`,
  `bash -c`, `$(…)`, uv global options such as `uv -q sync`); matching words needs no
  grammar and its only cost, over-deny during a closing window, is visible and self-correcting.
- **B alone — own venvs with no guard.** Leaves every existing symlinked worktree venv (§ What exists today) and pre-D1 subagent
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
  2026-10-06) — the hook would have to re-implement checkout and copies for 48 repos.
- **A read-only main venv:** loud, but main's own `uv sync` then needs a chmod wrapper, and uv's
  cache-cloned files share inodes.
- **Extending `merge_request.py`'s sitecustomize shim to every runner:** fixes which src is imported
  but leaves the shared venv writable from every worktree, and needs every runner to adopt the shim.

## Lifecycle

- **Adoption:** the governance sync distributes D1+D4 to the 48 repos' main checkouts; the
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
  later change when the scan in § Open/blocking unknowns (`-maxdepth 5`), counted over LIVE worktrees,
  reads 0. Dead `agent-*` worktrees never get another session; `scripts/scratch_sweep.py --worktrees`
  removes them (its removal unlinks a `.venv` link and never follows it). `fabrik-lib` is sync-excluded,
  carries no `worktree` block and has 10 linked worktrees with venv links today: it is outside this
  change and is told by mail.

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
- **Resolved — subagent worktrees after D1:** they get no SessionStart, so D3 treats a missing `.venv`
  like a link: a trigger command is denied with the absolute `--bootstrap` line, which builds the mirror.
- **Open — version drift in the 23 pyproject repos that track no `uv.lock`:** the mirror starts a
  worktree on main's versions, but a later `uv run` there resolves fresh. Resolution step: a fleet work
  item to track `uv.lock` in those repos (`core/10-python.md:32` already says the lock is the pin).
- **Open — a non-Claude shell writing through a not-yet-converted symlink:** outside every hook;
  closed only as worktrees convert. Resolution step: the plan's validation counts symlinked
  worktree venvs fleet-wide (`find /opt -maxdepth 5 -path '*/.claude/worktrees/*/.venv' -type l | wc -l`
  — 100 when this review began, 102 during round 6; `-maxdepth 4` reads 0 because the link sits at depth 5) after the sync and
  reports the residue.

## Cost

≈310 lines across 3 code files (the new hook ~280, `scripts/fabrik_synced_manifest.py` +1 entry and a
comment, `scripts/sync_enforcement_to_projects.py` the comment block `:97-101` that cites the worktree symlink)
and 3 config files (`.claude/settings.json` registration + block, `templates/governance/.worktreeinclude`
regenerated, the hub `.worktreeinclude` header comment) plus
tests (~150) and docs. One governance-sync commit after the full `/fabrik-review`.

## Validation

- V1: a scratch repo + linked worktree with a symlinked `.venv`, pytest in a `dev` extra: SessionStart
  replaces the link with an own venv whose interpreter version equals main's and which has pytest; the
  main venv's listing and editable `.pth` are byte-identical before and after; the worktree's python
  imports the worktree's src; no `uv.lock` appears. And once on the hub itself: a throwaway
  `git worktree add` of the hub, bootstrapped, passes `final_gate.py --lean --check --json`.
- V2: a requirements-only scratch repo, and a `[project]` table with no dependencies beside a
  `requirements.txt`, each get an own venv with their requirements installed.
- V3: a real `.venv` directory in a worktree and the main checkout are never modified.
- V4: while a worktree's `.venv` is a symlink, the guard denies every command naming a trigger word
  there — each writer form in the table above, the multi-line, mid-word `#`, `bash -c` and uv
  global-option spellings, and mentions — whether the target is the payload `cwd` or a path token
  (`cd <wt> && uv sync` from main, `uv --directory <wt> sync`); it allows commands with no trigger
  word, the fix (`rm .venv`, `--bootstrap`), every command whose targets are all the main checkout,
  and everything once the venv is real.
- V5: fail-open — a malformed payload, a git failure, a bootstrap timeout: exit 0, banner only; after
  a timeout the PENDING marker makes the next session rebuild the venv.
- V6: the sync manifest lists the hook; `.worktreeinclude` regenerated carries it; a settings file
  without the hook file cannot ship (a test asserts every hook path registered in settings.json is in
  `AGENT_HOOK_FILES`).
Each V is red on HEAD first.

## Decisions taken

- Per-worktree venvs replace the shared symlinked venv fleet-wide (supersedes the 2026-09-03
  design's "`.venv` symlinked" choice and its D4 safety reasoning) — REVERSIBLE (re-adding the key
  restores sharing).
- A guard covers only the window while a link remains or no own venv exists yet; it is not a permanent
  policy layer.
- The worktree venv MIRRORS the main checkout's interpreter and installed set rather than resolving
  fresh (design critiques, both seats; executed), and is built detached under a PENDING marker held by
  `flock`.
- `uv.lock` is not added to the synced ignore block (one critique proposed it): it would fight
  `core/10-python.md:32`, and the lock-tracking work item is the fix for the drift.
- The guard matches trigger WORDS over the raw command and accepts over-denying a mention during the
  window, instead of parsing shell grammar (a parser was measured to miss writers behind a newline,
  a mid-word `#`, `bash -c` and uv's global options).
- One new hook file holds both the bootstrap and the guard (one owner for the venv contract;
  `session_orient.py` stays an orientation printer).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"A `uv run` or `uv sync` inside a worktree finds no uv.lock there … and syncs the SHARED venv to that resolution."* (mail 01M3RYGE) | IN | § Why this exists; D1–D3 |
| I2 | *"the editable install of trade_intelligence re-pointed at agent-3's worktree src, so any process started from main imported another agent's code"* | IN | D1+D2 (own venvs); V1 |
| I3 | *"SQLAlchemy 2.0.52 -> 2.1.1, which red-lit the gate's mypy leg for every agent"* | IN | D1+D2 — a worktree's resolution no longer reaches main |
| I4 | Direction (1): *"worktree setup sets UV_PROJECT_ENVIRONMENT / a uv config so a worktree `uv run` refuses to sync, or gives each worktree its own venv"* | IN | Chosen approach (own venv); the config half rejected (§ Rejected) |
| I5 | Direction (2): *"a PreToolUse hook refuses `uv run|uv sync|pip install` from a linked worktree"* | IN (narrowed) | D3 — only while a link remains or no own venv exists yet |
| I6 | Direction (3): *"the seat-brief and operating-model docs name it as a serialising act"* | IN | D5 (operating model); seat briefs already ban package-manager verbs (D-587) |
| I7 | The hub recurrence 2026-10-06 (`_editable_impl_fabrik.pth` → intel's src) | IN | § Why this exists; restored by hand, prevented by D1+D2 |
| I8 | Critique: a worktree's tests import main's code while sharing (Opus critique 1) | IN | § Goal; V1 |
| I9 | Critique: Makefile wrappers (12 repos) bypass a command guard | IN | structural fix covers them once converted; § Open unknowns |
| I10 | Critique: rule packs order `uv run pytest` | IN | unchanged — correct under own venvs |
| I11 | Critique: `.worktreeinclude` enumerates hooks; missing hook file blocks Bash | IN | D4; V6 |
| I12 | Judge flaw: requirements-only subagent worktree gets no venv | IN | D3.1 (a missing venv is guarded and the deny names `--bootstrap`); § Open/blocking unknowns (resolved) |
| I13 | Judge flaw: non-Claude shells are outside any hook | IN | § Chosen approach (structural part); § Open unknowns |
| I14 | Design critique (Opus, at the approval gate): *"plain `uv sync` does not install the dev tools"*; the interpreter and `requirements*.txt` gaps | IN | D2.2 (mirror main); V1, V2 |
| I15 | Design critique (Fable): *"the lock-copy branch is dead code fleet-wide and the stray-lock complaint is not addressed"* | IN | D2.2 (no lock written); § Open/blocking unknowns (lock-tracking work item) |
| I16 | Design critique (Fable): owner tests run main's venv, which no worktree syncs after D1 | IN | D6 |
| I17 | Design critique (Opus): 92 of 101 links are subagent worktrees with no SessionStart | IN | D3.1 (missing venv); § Lifecycle |

Intake: 17 items — 17 IN, 0 OUT-OF-SCOPE, 0 ASK.
