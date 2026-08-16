# Command Run-Record Protocol

**What it is:** one json per Claude session recording which `/fabrik-*` command is in flight — its
phase, its convergence rounds, its class ledger, and its terminal condition. It exists to fix three
operator complaints at once:

| Complaint (verbatim) | The mechanism |
|---|---|
| "reviews are still taking 30 rounds" | the persistent **class ledger** + the **non-convergence detector** |
| "i want to see each commands status pinned in each agents reply, as like total steps, and current step" | the pinned **`RUN:` line** |
| "agents are still stopping without reaching a no ops pass or fully executing the commands for no valid reason" | the Stop hook's **fifth cause** |

Owner: `scripts/command_run.py` (stdlib only, fleet-synced via `CORE_SCRIPTS`).
Enforcement: `.claude/hooks/final_gate_stop.py`.
Contract text: `CLAUDE.md` § COMMAND RUN-RECORD (hub) and `templates/governance/CLAUDE.md` (projects).

## State

One file per session: `$COMMAND_RUN_DIR/<session_id>.json`, default
`~/.claude/state/command-runs/<session_id>.json`. The session id comes from `CLAUDE_SESSION_ID` or
`--session`. Writes are atomic (tmp + `os.replace`).

```json
{
  "command": "fabrik-review", "phases": 5, "phase": 4, "phase_title": "Converge",
  "terminal": "found:0 no-op round", "state": "running",
  "rounds": [{"n": 1, "findings": 5, "swept": ["auth"], "new": ["concurrency"]}],
  "classes": {"auth": "clean", "concurrency": "open"},
  "updated_ts": 1755300000, "stack": []
}
```

`state` ∈ `running` · `done` · `blocked`. `stack` parks a **caller's** record when a command nests
(`/fabrik-execute-plan` → `/fabrik-review` at a phase boundary) so the nested `done` restores the parent
instead of erasing it — a green phase gate must never read as "the plan is finished".

## CLI

| Command | Effect |
|---|---|
| `start --command <name> --phases <N> [--terminal "<cond>"]` | begin a run at phase 1 (a running record is pushed onto `stack`) |
| `step --phase <N> [--title "<t>"]` | advance |
| `round [--findings <N>] [--classes-swept a,b] [--classes-new c,d]` | record one convergence pass; merge the class ledger |
| `done --command <name> --evidence "<proof>"` | terminal — the contract IS met |
| `blocked --command <name> --reason "<sanctioned case>"` | terminal — a real halt |
| `line` | the pinned status line; **silent + rc 0 when no run is active** |
| `status --json` | the record (`{}` when there is none) |

Every **mutating** subcommand (`start` · `step` · `round` · `done` · `blocked`) holds an exclusive
`fcntl.flock` over the record across its whole read-modify-write. Subagents routinely inherit the
parent's `CLAUDE_SESSION_ID`, and unlocked, 20 concurrent `round` calls lost 14 of 20 class-opens
(measured) — a dropped class means a review reads CLEAN on a class that was never swept, destroying
exactly the integrity the ledger provides. `line` and `status` stay lock-free readers: `line` runs on
every reply and must never wait behind a writer.

### Closing a run requires naming it

`done` and `blocked` take a **required `--command`**, and a name that is not the live run's is
**REFUSED (rc 1)** — the record is not touched. Closing "whatever is live" reintroduces the exact
defect this protocol exists to prevent: after a nested `/fabrik-review` pops back to
`/fabrik-execute-plan`, a retried or duplicated `done` would close the PLAN at phase 2/5, silence the
pinned line, and disarm the Stop hook for every remaining phase. Closing an **already-closed** record
is a warned no-op (rc 0) — a retry is not an error, and a resumed parent is never mutated by one.

### Session-id filenames never collide

Flattening a raw session id to `[A-Za-z0-9_-]` alone mapped `abc.xyz` and `abc xyz` onto one
`abc_xyz.json`, letting an innocent session inherit — and be blocked by — another's run. `_safe_sid`
appends a short blake2s tag of the RAW id whenever flattening changed anything; uuid-shaped ids pass
through unchanged, so no existing record is renamed. The hook carries a byte-identical copy (it must
not import the script), pinned by `test_hook_and_script_agree_on_every_record_filename`. The hook's
own `_counter_path` / `_baseline_path` use the same helper: unsanitized, a `/`-containing id escaped
the tmp dir and the resulting `OSError` hit the outermost `except`, failing the WHOLE hook open and
silently disabling all five causes.

### The pinned line

```
RUN: /<command> · phase <c>/<t> (<title>) · round <r> · terminal: <condition>
```

Segments whose data does not exist yet are **omitted, not filled with placeholders**: `· round` before
the first round, `(title)` before a `step` names one, `· terminal:` when the command declared none. When
no run is active the command prints **nothing** — it runs on every reply, so idle must be silent and
cheap, never `RUN: none`.

## Convergence: re-sweep a fixed ledger, never re-scope

A **class** is a named failure/claim category (a Coverage-Checklist row, a doc, a subsystem). The ledger
persists across rounds:

- `--classes-new` opens a class (`open`).
- `--classes-swept` retires one (`clean`) — **only a round that swept it clean retires it.** Sweeps apply
  before opens, so a class both swept and re-found in the same round stays `open`.
- A round that leaves **every known class clean with `--findings 0`** prints the **TERMINAL verdict**:
  that is the no-op round the corpus already demands, and the agent then calls `done`.
- An empty ledger can never be terminal — a round that declared no classes swept nothing.

### The non-convergence detector

A converging review trends **down**: `5 → 3 → 0` (a real pointer-rotation review, 4 rounds). A
pathological one **oscillates**: `43 → 11 → 30 → 13 → 22` (a real peer run, ten passes, never
converging) — because each round *re-scopes*, inventing a fresh brief, instead of *re-sweeping* the
persisted ledger with the same one.

From round 5, when the last 3 findings counts are not non-increasing, `round` prints a loud warning
naming the sequence and that diagnosis. It is **advisory only and never blocks** — the operator must not
be trapped by a heuristic, and a legitimately widening review (a fix that opens a new surface) must be
able to say so and continue.

## Coverage — which commands open a record

**All 27.** Until 2026-08-16 it was three (`/fabrik-review`, `/fabrik-execute-plan`,
`/fabrik-docs-review`), so for the other 24 every mechanism on this page — the pinned `RUN:` line,
the class ledger, the non-convergence detector, the Stop hook's fifth cause — was inert. The
protocol was sound and simply not wired in, which is indistinguishable from not having it.

Coverage is now structural rather than remembered:

- `commands/_fragments/run-record.md` is the shared block; a command includes it with
  `{{include:run-record}}`, placed as the first thing after its frontmatter.
- `assemble_commands.py` fills the fragment's `{{COMMAND}}` and `{{PHASES}}` **at render time**
  from the source itself (`_phase_count`), so a new command or a new phase needs no bookkeeping.
- `scripts/enforcement/check_command_corpus.py` FAILS the gate on any command source that carries
  neither the fragment nor its own `command_run.py start` block — the three bespoke commands keep
  their richer, round-aware blocks and satisfy it that way.

See `docs/reference/command-corpus-check.md` § Predicate 5.

## Enforcement — the Stop hook's fifth cause

`.claude/hooks/final_gate_stop.py` had four causes (gate red · own uncommitted · own unpushed ·
promise/permission stall) and no concept of an in-flight command. The fifth: **a record that says
`running` BLOCKS the stop**, naming the command, phase `c/t`, round, the terminal condition, any still-open
classes, and the two legitimate exits (`done --command <name> --evidence …` /
`blocked --command <name> --reason …`, with the live command's name filled in for you).

It uses the same counter/reset/warn-through idiom as every other cause: its own slot in the per-session
counter file (now 5 slots, tolerating older 3/4-slot files), reset the moment the cause is false, and
warn-through after `CAP` (3) blocked stops so a genuinely stuck agent still escapes.

### The fail direction is deliberately asymmetric

Blocking a stop is a strong act, so **freshness must be POSITIVELY PROVEN** — every shape that cannot
prove it fails open. Anything less inverts the design: a record whose timestamp is merely *unusual*
would block forever, indistinguishable from a legitimate block.

| State | Verdict |
|---|---|
| record says `running`, `updated_ts` finite and within the bound | **BLOCK** |
| no record · corrupt / unreadable / not a dict | allow |
| `state` is `done` / `blocked` | allow |
| `updated_ts` missing · `null` · a string · a bool | allow — freshness unprovable |
| `updated_ts` is `NaN` / `±Infinity` (`json.loads` accepts these literals) | allow — freshness unprovable |
| `updated_ts` older than the bound (`COMMAND_RUN_STALE_H`, default **12h**) | allow — abandoned record from a dead session |
| `updated_ts` further in the FUTURE than `_CLOCK_SKEW_TOLERANCE_S` (60s) | allow — a broken clock is not evidence of freshness |
| `COMMAND_RUN_STALE_H` ≤ 0, `nan` or `inf` | allow — the operator disabled the trap; that can never mean "block forever" |

A *small* forward skew (inside the 60s tolerance) still blocks — otherwise the escape hatch would be
"set your clock one second ahead". Everything else **fails OPEN**: broken state must never trap an
agent, and that is worth more than the blocks a corrupt record would otherwise catch.

The hook duplicates the ~10-line path resolver rather than importing `scripts/command_run.py`: a hook
must not acquire an import that can fail (missing mid-sync, absent in a project that has not synced yet,
a syntax error) — an `ImportError` there would degrade **every** cause, not just this one.

### The three sanctioned BLOCKED reasons

`blocked --reason` takes one of exactly these (`CLAUDE.md` § Behavior):

1. **3 consecutive same-test failures**
2. **missing infra**
3. **an unresolvable spec contradiction**

Format the reason as `BLOCKED: <what> — searched: <sources> — missing: <need>`. Anything short of those
three is not a halt — it is the run continuing.

## Why a hook and not just prose

Lesson 116: an agent reads its contract once at session start and then acts for hours from that snapshot
— a documentation fix is invisible to every session already running (200/200 commits carried a trailer
block, 10 parsed; the corrected example still produced 0/50). A governance rule with a mechanically
checkable output has to be checked **at the moment the output is still editable**. For "did you finish
the command?", that moment is the Stop hook.

## Configuration

| Env var | Default | Effect |
|---|---|---|
| `COMMAND_RUN_DIR` | `~/.claude/state/command-runs` | where records live (read by both the script and the hook) |
| `CLAUDE_SESSION_ID` | `nosession` | record filename (`--session` overrides) |
| `COMMAND_RUN_STALE_H` | `12` | hours after which the hook treats a record as abandoned; **≤0 / non-finite disables the block entirely** (never "block forever") |

## Tests

`tests/test_command_run.py` — line format · idle/corrupt/unwritable silence · ledger persistence ·
terminal verdict (including 0 findings with a class still open) · the detector on `43,11,30,13,22` vs
`5,3,0` · nested pop/restore · duplicate-`done` refusal · double-close no-op · 20 real concurrent
`round` processes losing nothing · session-id collision · hook↔script filename agreement.

`tests/test_final_gate_stop_hook.py` — the fifth cause (running blocks · done/blocked/corrupt/missing/
stale allow · the anti-trap cap · the 5-slot counter) and the freshness matrix (missing/null/string/
bool/NaN/±Infinity/far-future timestamps and `COMMAND_RUN_STALE_H` ∈ {0, -1, nan, inf} all fail open;
a sub-tolerance skew still blocks) plus the tmp-path sanitization guards.
