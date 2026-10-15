# Review seats — write isolation in the seat guard (design)

Status: DRAFT
Size: small (≈260 lines across `.claude/hooks/seat_guard.py`, `tests/test_seat_guard.py`, `.claude/settings.json` and `docs/workstation/hooks-index.md`)
Profile: delta
Work item: W-72dfd448 · seed: mail 01M4PHYNXJ (/fabrik-review verdict rows 1791209046, 1791049341, 1791225410) · upgraded from `/fabrik-task` on `tradeoffs` (design seed `/opt/fabrik/.tmp/runs/4e90716e-696b-4ddf-90ab-70e30f51f294/fabrik-task-2026-10-15T22-15-12-0300/design.md`)

## Personas

- **PRIMARY — the operator, whose live checkouts review seats have damaged.** The verdict rows, verbatim: *"the
  review-loop seat brief template could forbid writes under the repo root by construction (cwd = scratch, repo mounted
  read-only) instead of by prose"* (row 1791209046) and *"fabrik-review-loop.js should launch finder and refuter seats with
  cwd set to a fresh scratch directory (or isolation: worktree), never the caller's main checkout"* (row 1791049341). The
  house record behind them: a seat's `git checkout` destroyed a merge owner's uncommitted work, a seat's relative `cp`
  overwrote the hub `Makefile`, and a seat probe removed every session's `~/.claude/skills`.
- **Automated consumers:**
  - the **review seats** — `fabrik-reviewer` finders and refuters, dispatched by the review-loop Workflow
    (`.claude/workflows/fabrik-review-loop.js`) and directly by the Agent tool, which this change constrains: they read
    pins and write only their own scratch;
  - the **lead session / orchestrator** that dispatches them, which must NOT be constrained (it has no `agent_id`);
  - the **PreToolUse seat hook** (`.claude/hooks/seat_guard.py`), which holds the duty to refuse;
  - the **~46 synced repos**, which receive the hook and its registration through the governance sync.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "forbid writes under the repo root by construction (cwd = scratch, repo mounted read-only) instead of by prose" (01M4PHYNXJ row 1791209046) | IN | § The delta — the guard refuses a seat's write outside its scratch, both tool and shell writes |
| I2 | "launch finder and refuter seats with cwd set to a fresh scratch directory (or isolation: worktree), never the caller's main checkout" (01M4PHYNXJ row 1791049341) | IN | § Rejected alternatives — A (worktree) and the cwd option, which does not exist; the guard covers both dispatch paths instead |
| I3 | "hand seats a ready probe script" (01M4PHYNXJ row 1791225410) | OUT-OF-SCOPE | W-f7bf9a54 — a separate change with its own measure (seat turns spent building probes) |

## Goal

A review seat cannot write outside its scratch directory by mistake — not with the Write, Edit or NotebookEdit tools, and
not with a shell command whose destination is a literal path — on BOTH dispatch paths, without changing the seats'
working directory, their briefs, or the lead session.

## What exists today (grounded, read at b2e1069dd)

- `.claude/hooks/seat_guard.py:62` — `SEAT_TYPES = frozenset({"fabrik-reviewer"})`; `decide()` at `:564-584` returns ""
  for any payload without `agent_id` or with another `agent_type`, so the lead and every other agent type are untouched.
- `.claude/hooks/seat_guard.py:283-293` — `_in_scratch()` already defines the scratch roots: the payload's
  `scratchpad_dir`, and `/tmp/` except another session's `/tmp/claude-<uid>/<slug>/<sid>/`; a `$`-bearing or substituted
  path is treated as NOT scratch (fail closed for a write).
- `.claude/hooks/seat_guard.py:504-560` — `_scan()` tokenises quote-aware, follows `cd`/`pushd`/subshell scope, recurses
  into `bash -c` and `$(…)`, and denies kills and git writes outside scratch; an untokenisable command is denied only when
  it names a git write or a kill (`:510-517`).
- `.claude/hooks/seat_guard.py:228-229` — `_simple_commands()` DROPS a redirect's target (`skip_next = True`): today a
  `> path` is invisible to every rule.
- `.claude/hooks/seat_guard.py:611-646` — `main()` returns at once unless `tool_name == "Bash"`, and fails open on any
  exception (the charter: a guard bug never blocks a seat).
- `.claude/settings.json:145-155` — the hook is registered with `"matcher": "Bash"` only.
- `.claude/workflows/fabrik-review-loop.js:139` — Workflow slices default to `agentType: 'fabrik-reviewer'`, so Workflow
  seats already carry the agent type the guard keys on; `:252` and `:266` carry the prose rule this change backs
  ("never write, copy, mkdir or cd-and-create anything outside SCRATCH — your working directory is the LIVE repo").
- `tests/test_seat_guard.py` — 33 tests drive `decide()`/`main()` with synthetic payloads.

## External dependencies (fetched 2026-10-15)

- PreToolUse hooks fire inside subagents and the input carries `agent_id` and `agent_type`; Write and Edit carry an
  absolute `tool_input.file_path`; `permissionDecision: "deny"` blocks the call and shows Claude the reason —
  https://code.claude.com/docs/en/hooks (WebFetch). NotebookEdit is governed by `Edit(...)` rules and carries
  `notebook_path` — https://code.claude.com/docs/en/tools-reference (WebFetch).
- There is no per-subagent cwd or write-path option; a hook keyed on `agent_type` is the documented way to scope a
  subagent — https://code.claude.com/docs/en/sub-agents and https://code.claude.com/docs/en/permissions (WebFetch);
  permissions "isn't a security boundary … Use both for defense-in-depth" (same page).
- Worktree isolation refuses Edit/Write and git aimed at the main checkout, but "a command that writes into the main
  checkout without running git there, such as `cp` or a shell redirect, isn't refused"; a changed worktree is kept until a
  sweep; it starts from committed state — https://code.claude.com/docs/en/worktrees (WebFetch).
- The built-in Bash sandbox is session-wide only ("subagents … use the same sandbox configuration") —
  https://code.claude.com/docs/en/sandboxing (WebFetch).
- Bash-string write detection catches literal paths, not interpreters: a 22-pattern deny list was bypassed by `perl -i` —
  https://github.com/anthropics/claude-code/issues/40408 (exa); OS enforcement is the boundary and hooks are
  defence-in-depth —
  https://developer.nvidia.com/blog/practical-security-guidance-for-sandboxing-agentic-workflows-and-managing-execution-risk/
  (exa).

## Constraints Digest

| Quote | Source |
|---|---|
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |
| silent defaults are the #1 source of | `.windsurf/rules/core/12-node.md:60` |

## The delta — B: widen the seat guard (judge panel 3/3)

1. **Tool writes.** `main()` also handles `Write`, `Edit` and `NotebookEdit`: for a seat payload, the destination
   (`tool_input.file_path`, or `notebook_path`) is resolved with `realpath`; outside `_in_scratch()` the call is denied
   with the reason *"seat guard: a review seat writes only under its scratch dir — <path> is outside it"*. Exact: the path
   is absolute by contract, so this half has no blind spot.
2. **Shell writes with a literal destination.** `_simple_commands()` keeps each output redirect's target (`>`, `>>`,
   `>|`, `&>`, `&>>`) with its command instead of dropping it; `/dev/*` targets and fd duplications (`>&1`, `2>&1`,
   `>&-`) stay allowed. `_scan()` gains a write rule: the destination operands of `tee`, `cp`/`mv`/`install`/`rsync`/`ln`
   (the last operand, or `-t <dir>`), `rm`/`rmdir`/`touch`/`mkdir`/`truncate` (every operand), `sed -i`, `perl -i`,
   `dd of=` and every redirect target are resolved against the tracked `cwd` and must lie in `_in_scratch()`. A copy FROM
   the live tree INTO scratch stays allowed — only destinations are checked.
3. **Unparseable.** The existing fallback (`:510-517`) also denies an untokenisable command that names one of those write
   verbs or an output redirect.
4. **Registration.** `.claude/settings.json`'s seat-guard matcher becomes `Bash|Write|Edit|NotebookEdit`, in the reviewed
   commit only (the main checkout's settings are live for every session).
5. **Docs.** The `docs/workstation/hooks-index.md` row for `seat_guard.py` names the new matcher and the write rule, and
   states the blind spot.

**The blind spot, stated (COBRA, D-253):** the cheapest way past the rule is a write the Bash string does not show — an
interpreter (`python -c "open(p,'w')"`, `shutil.rmtree`), a script file, a variable holding the path (fail-closed only when
the variable is the destination itself). The guard is defence-in-depth against ACCIDENTAL writes, not a boundary against an
adversarial seat; the brief's prose stays as the second layer. **Tripwire:** a confirmed seat write to a live tree through
an interpreter re-opens this design with approach D (below) or a filesystem-level fence.

## Contract deltas

- The seat hook's matcher widens from `Bash` to `Bash|Write|Edit|NotebookEdit` — a synced registration (fleet-wide).
- A seat's Bash command with a literal write destination outside scratch, previously allowed, is now refused. **MIRROR —
  the shapes that now fail:** a seat that writes a report straight into the repo (`> docs/…`), a refuter that "fixes" a
  file in place, a seat whose brief names a repo-relative scratch path (`.tmp/…` under the live tree — the D-836 SCRATCH
  root `<main>/.tmp/runs/<sid>/` is NOT under `/tmp` and is refused unless the build adds it as a scratch root; the build
  adds the session's own `<main>/.tmp/runs/<sid>/` so a brief that uses SCRATCH keeps working).
- Non-seat agents and the lead: no change.

## Lifecycle

- **Adoption:** ships with the next merge of `worktree-intel`; the post-merge sync distributes the hook and matcher to
  every synced repo.
- **Growth, with measured triggers:** a new seat agent type joins `SEAT_TYPES` only when it is read-only by contract; a new
  write verb joins the list when a refused-or-missed seat write names it.
- **Retirement:** the rule retires when Claude Code offers a per-subagent filesystem fence (a sandbox or write-path option
  scoped to a subagent) — then the fence replaces the string rule.

## Cost

One hook file (+≈120 lines), its tests (+≈120 lines), one matcher string, one doc row. No disk, no retention, no brief
change. Hook latency: one more python start per seat Write/Edit (the Bash path already pays it).

## Validation

Each behaviour gets a test in `tests/test_seat_guard.py`, seen red first:

1. A seat `Write`/`Edit`/`NotebookEdit` to a path outside scratch is denied; the same tool inside its scratch is allowed.
2. The lead (no `agent_id`) and a non-seat agent type writing anywhere are allowed.
3. A seat redirect to a live path (`echo x > Makefile` with cwd = the repo) is denied; `> /dev/null`, `2>&1` and a redirect
   into scratch are allowed.
4. A seat `cp <live> <scratch>/` is allowed; `cp <scratch>/x Makefile`, `rm -rf <live dir>`, `sed -i … <live file>`,
   `perl -i … <live file>`, `tee <live file>` and `dd of=<live file>` are denied; `cd <scratch> && touch x` is allowed.
5. An untokenisable command naming a write verb is denied.
6. `main()` with the new tool names emits the deny envelope; a crash inside the new path still fails open.

## Decisions taken

- **B over A and D** (D-913) — the judge panel (three Sonnet seats, 2026-10-15) ranked B first unanimously: it covers both
  dispatch paths, builds on the existing hook, and needs no brief, cwd or retention change; each judge named the
  interpreter blind spot as the strongest point against it, which § The delta states with its tripwire.
- **`perl -i` joins the write list** (a judge's graft): an in-place flag is as literal as `sed -i`. A blanket deny of
  `python -c`/`perl -e` naming a live path is NOT taken — seats read live files that way for probes, and its fire rate on
  legitimate reads is unmeasured.

## Rejected alternatives

- **A — `isolation: 'worktree'` on the review-loop `agent()` calls.** Covers Workflow seats only (the Agent-tool fallback
  stays open); the documentation says `cp` and shell redirects into the main checkout are not refused, which is exactly
  the incident class; ≥7 cwd-relative brief instructions to rewrite; seats see committed state only; `.venv` is absent in
  synced projects; kept worktrees add to the 25 (≈3.5 GB) already on disk.
- **D — both.** All of A's cost for a marginal gain on one path; re-opened only by the tripwire above.
- **C — the built-in Bash sandbox.** Session-wide only, so it would fence the lead too; cut.
- **A per-seat cwd.** The Workflow `agent()` options and the Agent tool take no cwd; not an option.

## fabrik-lib verdict

Build. Nothing in fabrik-lib parses shell destinations or keys a hook on a subagent type; the existing hub hook is the
natural home.

## Documentation landing sites

- `docs/workstation/hooks-index.md` — the `seat_guard.py` row (matcher, write rule, blind spot).
- `CHANGELOG.md` — one `### Changed` entry.
- The module docstring of `.claude/hooks/seat_guard.py` — the rule, its limits and the COBRA line.

## Open / blocking unknowns

None. The one live fact the build must confirm — that a Workflow `agent()` seat's Write payload carries `agent_type:
"fabrik-reviewer"` — is already true of its Bash payloads (the same hook input), so a red-to-green test on synthetic
payloads plus one live seat probe in the build closes it.
