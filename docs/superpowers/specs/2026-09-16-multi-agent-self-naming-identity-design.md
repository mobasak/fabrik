# Multi-agent self-naming identity — a live session names itself without a relaunch

**Status:** DRAFT
**Profile:** delta — every IN item maps to code that exists today (`scripts/command_run.py`,
`scripts/check_commit_trailers.py`, `.claude/hooks/session_orient.py`, `.claude/hooks/agent_role.py`).
⚠️ The implementation touches **7 files** (1 new writer + 1 new resolver module + 4 edited readers +
`tests/conftest.py`), which is OVER `Profile: small`'s ≤5-file threshold (D-169). The plan's profile
is therefore decided by `/fabrik-plan-after-chat` on its own count, not asserted here. ⚠️ And
`Profile: small` does **not** skip any pipeline stage: `/fabrik-plan-after-chat` classifies it
INTERNALLY (`:207`) and its `:719` mandates `/fabrik-plan-review` unconditionally — D-220, D-232 and
D-246 are all `Profile: small` plans that went through it. An earlier draft of this spec claimed
otherwise and that claim was false.

## Personas

- **The OPERATOR** runs 1–3 windows per repo and names them in the UI. Duty: say which name is whose.
  They have ruled OUT relaunching a running session, because agents 2 and 3 hold chat histories a
  relaunch destroys (trade-intelligence D-030).
- **The UNNAMED AGENT** — already running when the operator decided it needed a name. It cannot change
  its own environment. Duty: name itself once, then sign its work.
- **The VALIDLY NAMED AGENT** — launched with a well-formed `CLAUDE_AGENT`. Duty: nothing new; this
  spec must not change its behaviour at all. ⚠️ "Validly" is load-bearing: a MALFORMED `CLAUDE_AGENT`
  already resolves to `""` today (`command_run.py:1641`), so falling through to a binding in that case
  changes nothing for anyone who is actually named.
- **The CONSUMER** — the runtime readers of agent identity. Duty: resolve through one order,
  identically, and keep failing silent when identity is genuinely unknown.

## Goal

A session that is already running can bind itself to a name, in-process, with one command; and the
controls that today read `CLAUDE_AGENT` alone resolve that binding instead of failing silent.

## Why this exists

Identity resolves from `CLAUDE_AGENT` — a LAUNCH-TIME variable — and nothing else. A window `/rename`
does not reach it. Executed 2026-09-16 against the operator's three `trade-intelligence` windows,
named `agent-1/2/3` in the UI: **all three report `CLAUDE_AGENT=<UNSET>`**, and **0 of their last 40
commits carry an `Agent-Name` trailer** while 40 of 40 carry `Agent-Role`. Their commits concentrate
on the four shared-append files (CHANGELOG 18 of 40, STRATEGIC_BACKLOG 15, DECISIONS 10, INDEX 8), so
the repo has the highest collision surface on the box and no way to attribute a collision to anyone.

D-267 shipped an advisory that TELLS an unnamed session it is unnamed. It is a SessionStart hook, so
it cannot reach a session already running — the exact population it was written for.

## What exists today (grounded)

**THE ENABLING FACT, executed.** `CLAUDE_CODE_SESSION_ID` is exported into every shell a live session
runs, and **git hooks inherit it**: a scratch repo's `pre-commit` and `commit-msg` both printed
`sid=[dd3c06d1-…]` with `CLAUDE_AGENT` empty in the same run. A `setsid`-detached background shell
inherits it too; only `env -i` (cron) loses it.

⚠️ **BUT THE `claude` PROCESS ITSELF DOES NOT CARRY IT.** Executed on two live sessions
(`/proc/54834/environ`, `/proc/62293/environ`): **0 occurrences** of `CLAUDE_CODE_SESSION_ID`. The
variable exists in the session's *child* shells, not in the session process. This kills the naive
liveness check (see § The delta 1) and is the single most expensive thing to discover late.

⚠️ **A SESSION'S cwd IS NOT STABLE.** `docs/workstation/session-recall.md:43`, measured 2026-09-11:
*"A session that CHANGES cwd is RE-FILED mid-session. `EnterWorktree` (and any `--worktree` launch)
moves the cwd into `<repo>/.claude/worktrees/<name>`."* Live confirmation: pid 62293's cwd is
`/opt/iterative_image_editor/.claude/worktrees/store-content-set`. So cwd is unusable as a key.

**THE CONSUMERS — five, not seven.** `command_feedback_report.py:1204` is an argparse help string and
`commands/assemble_commands.py:54` is a NEXT-map hint; neither reads the environment.

| consumer | site | distributed? | what is actually true today |
|---|---|---|---|
| `scripts/command_run.py` | `_agent_name()`, `:1639-1641` | 49 `/opt` dirs | records `""`, so every run record and `FEEDBACK:` verdict is unattributable — **the largest single win** |
| `scripts/check_commit_trailers.py` | `:561-576` | HUB-ONLY | the mismatch advisory cannot fire; ⚠️ and it is a commit-msg hook, see the carve-out below |
| `.claude/hooks/agent_role.py` | `:52` | synced | no role charter is injected |
| `.claude/hooks/session_orient.py` | `_identity_line`, `:225` | synced | the D-268 advisory fires, but its remedy is a relaunch the operator refuses |
| `scripts/mail.py` | `:1807` | 49 `/opt` dirs | ⚠️ **NOT a consumer to teach.** `:1807` is `list`'s INBOX FILTER, whose namespace is the three hub BEATS — not window names. The `acked-by:` writer is `_append_ack_line` (`:1030`) and writes the REPO name, never an agent; `ack` has no `--agent` flag. Executed: `list --repo fabrik --agent agent-2` returns **0** messages where `list` returns **41**. Teaching it the resolver would EMPTY a bound session's mailbox across 49 dirs. |

⚠️ **THE PLUMBING CARVE-OUT.** Executed with all four commit hooks instrumented: a porcelain
`git commit` fires `pre-commit`, `prepare-commit-msg`, `commit-msg` and `post-commit`, each seeing the
sid; **`git commit-tree` + `git update-ref` fires NONE of them**, and the commit lands with its
trailers because the AGENT wrote them into the message file. That plumbing recipe is what `CLAUDE.md`
MANDATES for the four shared-append files — the same files that motivate this spec. So a commit-msg
hook is structurally absent from the commits that most need attribution.

**THE STATE DIR IS `$HOME`-KEYED.** `command_run.py:84-88` resolves `$COMMAND_RUN_DIR` else
`Path.home() / ".claude" / "state" / …`. `CLAUDE_CONFIG_DIR` is `/home/ozgur/.claude-fleet/active` and
has **no** state dir; `/home/ozgur/.claude/state` holds 54 command-run records. A session pinned to
another config-dir slug therefore shares the store.

**NOTHING PRUNES THAT DIRECTORY BY AGE.** `scratch_sweep.py:59` states it touches
`$HOME/.claude/state/scratch-sweep.lock` and *"reads, writes and deletes nothing else there"*. There
is no janitor to inherit.

## The delta

1. **`scripts/whoami_agent.py --as <name>`** — the writer. It takes the session id from its OWN
   environment, never from an argument.
   ⚠️ **It records the SESSION's pid, not its own.** The writer is a short-lived process that exits
   immediately, so recording `os.getpid()` would make every binding dead on arrival. It walks its own
   `/proc/<ppid>` ancestry for the nearest `comm == claude` and records THAT; if the walk fails it
   records **no pid at all** rather than a wrong one.
   ⚠️ **Name alphabet: `^[a-z0-9-]{1,32}$`** — the STRICTEST of the three live validators. Executed:
   `Agent-2`, `agent_2` and `agent.2` are accepted by `mail._safe_agent` but rejected by both
   `command_run.py:1602` and `agent_role.py::_NAME_RE`, so a name outside this set would bind and then
   be silently dropped by two consumers — one session with two identities and no error anywhere.
   ⚠️ **Re-binding the same sid to a DIFFERENT name requires `--force`**, because a Task subagent
   inherits its parent's `CLAUDE_CODE_SESSION_ID` (verified: a review seat this run carried
   `dd3c06d1-…`, its dispatcher's id) and would otherwise silently re-identify its dispatcher.
2. **The store: `$AGENT_IDENTITY_FILE` else `$HOME/.claude/state/agent-identity.jsonl`.**
   Append-only, one row per binding, last row wins per session id, written with the idiom of
   `command_run.py:1488 _append_ledger_row` — `O_APPEND`, short writes CONTINUED, mode `0600`.
   (Measured: 30 concurrent writers at 140 B / 8 KB / 70 KB rows produced 0 corrupt rows, so this is
   hardening, not a live defect — but the spec names the writer so an implementer does not pick one.)
   ⚠️ **The writer SELF-TRIMS on write** — rows older than 30 days are dropped as it rewrites. There is
   no janitor for `~/.claude/state` and `scratch_sweep.py` is contractually forbidden from that path,
   so an unowned store would grow forever.
   ⚠️ **No repo key, and NOT because a session has one cwd** — it does not (§ What exists today).
   Because the operator names a WINDOW, and a window is one session wherever its cwd wanders.
3. **A resolver, `resolve_agent_name()`**, with ONE order: a **well-formed** `CLAUDE_AGENT` →
   `binding[CLAUDE_CODE_SESSION_ID]` → `""`. A malformed env value falls through to the binding, which
   changes nothing for a validly named agent (today it is `""` either way). The `Agent-Name:` trailer
   is deliberately NOT in the chain: it is what identity PRODUCES, so reading it back is circular.
4. **Four readers taught, in this order** — `mail.py` is explicitly NOT among them:
   (a) `command_run.py` (49 dirs; every run record and FEEDBACK verdict becomes attributable);
   (b) `session_orient.py` (synced; the D-268 advisory stands down for a bound session);
   (c) `agent_role.py` (synced); (d) `check_commit_trailers.py` (hub-only, ranked LAST because of the
   plumbing carve-out — it covers porcelain commits only).
   ⚠️ **Plus one non-reader call site:** the private-index recipe's step-5 message construction, where
   the agent composes trailers by hand. That is the only place the resolver reaches a shared-append
   commit, and it is a shell invocation, not a hook.
   ⚠️ **None of these may import another** — `command_run.py` is distributed while
   `check_commit_trailers.py` is hub-only, so an import either way fails CLOSED fleet-wide. The
   resolver is duplicated, as `command_run.py` / `command_feedback_report.py` duplicate their axis
   list, and pinned by a drift grader.
5. **`tests/conftest.py` gains ONE pin: `AGENT_IDENTITY_FILE`.** ⚠️ The READ side is already safe
   and an earlier draft of this spec got that wrong: `conftest.py:142` DELETES
   `CLAUDE_CODE_SESSION_ID` in the autouse `_isolated_command_run_dir` fixture (`:126`), and that
   fixture's own docstring at `:129` names both spellings — so a grader resolves `""` by default and
   cannot read a live binding. Deletion is stronger than a pin here. What is genuinely missing is
   `AGENT_IDENTITY_FILE` (0 occurrences in `conftest.py`): without it the WRITER graders (V7-V11)
   append to the operator's live `~/.claude/state/agent-identity.jsonl`. This is the class
   `tests/test_conftest_isolation.py` exists to close, and it is one line, not four.

⚠️ **ONE LIMIT, for BOTH SessionStart hooks:** `agent_role.py` and `session_orient.py` both run at
SessionStart only, so a session that names itself mid-flight gains attribution and trailer checking
immediately, but its CHARTER injection and the standing-down of the D-268 advisory take effect at the
NEXT start. An earlier draft flagged this for one hook and implied immediacy for the other.

## Chosen approach

**A box-local, session-keyed binding written by the session itself.** The session id is the only
stable fact a live session can prove about itself and the only one that reaches both a git hook and a
SessionStart hook.

## Rejected alternatives

| Option | Why rejected |
|---|---|
| **Relaunch with `CLAUDE_AGENT` set** | Ruled out by the operator twice; agents 2 and 3 hold chat histories a relaunch destroys. Remains correct for a NEW window. |
| **A tracked `.fabrik/agents.json` roster** | Answers "which agents does this repo have", never "which one am I". Kept as an optional validation source. |
| **Key on the `Agent-Name:` trailer** | Circular, and empty for a session that has not committed. |
| **Key on the window title / `/rename`** | Executed: never reaches the environment or any hook — the defect, not the fix. |
| **A per-repo binding file** | The operator names a window, not a directory; and cwd is not stable enough to key on. |
| **Make it BLOCKING** | ~50% of commits in a multi-agent repo touch a shared-append file, so a gate here sits on the majority path and must fail OPEN. |

## Lifecycle

- **Write:** `python3 scripts/whoami_agent.py --as agent-2`, once per session, any time.
- **Read:** every taught consumer, every invocation, through the one resolver.
- **Collision:** the writer refuses a name currently held by a DIFFERENT live session **in the same
  git toplevel** (`git rev-parse --show-toplevel`), not the same cwd. ⚠️ Executed on the cwd version:
  a plain `cd` into a subdirectory bound the held name at rc 0 with `force:false` — cheaper than
  `--force` and leaving no record. `--force` overrides and the row records `force: true`; ⚠️ the
  reader of that field is `session_orient.py`'s advisory, which names a forced binding — a `--force`
  nobody reads is a promise, not a mechanism.
- **Staleness:** resolution does NOT consult liveness — a binding resolves for the life of its row.
  Rows older than 30 days are trimmed by the writer. (An earlier draft made resolution
  liveness-gated, which made every binding inert at birth.)
- **Degradation:** an unreadable or unwritable store resolves to `""` — today's behaviour exactly.

## Cost

- **Code:** ~150 lines — writer ~55 (the `/proc` ancestry walk and the trim are the new weight),
  resolver ~25 duplicated across the hub-only / distributed boundary (2 copies), four call sites ~10
  each, conftest ~4. Plus graders.
- **Files: 7** — over `Profile: small`'s ≤5. The plan's profile is `/fabrik-plan-after-chat`'s call.
- **Not paid:** no new dependency, no format change, no relaunch, no schema, no change to `mail.py`.

## Validation

| # | Behaviour | How it is proven |
|---|---|---|
| V1 | A live session binds itself and the binding RESOLVES | bind, then resolve from a CHILD process; assert the name — the row must resolve with the writer process long gone |
| V2 | A git hook resolves the binding | a scratch repo whose `commit-msg` prints the resolved name, `CLAUDE_AGENT` unset |
| V3 | A plain SHELL invocation resolves it | the private-index path fires no hook; assert the resolver works from a bare shell under the same sid |
| V4 | A well-formed `CLAUDE_AGENT` WINS | set both to different values; assert the env value |
| V5 | A malformed `CLAUDE_AGENT` falls through | `CLAUDE_AGENT="Agent 2!"` + a binding → the binding resolves; and a VALID env name never falls through |
| V6 | An unbound session is unchanged | no binding, no env → all four consumers behave byte-identically to today |
| V7 | The writer records the SESSION's pid, not its own | assert the recorded pid is alive after the writer exits; mutate it to `os.getpid()` and assert the grader reds |
| V8 | A name held elsewhere in the same TOPLEVEL is refused | two sids, one name; assert refusal — and assert a `cd` into a subdirectory does NOT bypass it |
| V9 | Re-binding one sid to a different name needs `--force` | the subagent case: same sid, new name, no force → refused |
| V10 | A name outside `^[a-z0-9-]{1,32}$` is refused | assert `Agent-2`, `agent_2`, `agent.2` all refuse |
| V11 | Rows older than 30 days are trimmed on write | seed an old row; write; assert it is gone |
| V12 | The resolver copies do not drift | a pin over both copies asserting the order verbatim |
| V13 | Writer graders never touch the live store | assert `conftest` pins `AGENT_IDENTITY_FILE` (the read side is already covered by `:142`'s delenv); mutate the pin out and assert the isolation test reds |
| V14 | An unwritable store degrades to today | chmod the dir; assert `""` and a stderr line, exit 0 |

## Cobra (D-253)

**The cheapest way to satisfy "sessions are named" without the outcome is to bind all three windows to
the SAME name.** The writer's same-toplevel refusal is the ONLY counter-measure, and it is defeatable
by binding first or with `--force`.
⚠️ **The shared-name path is NOT closed, and this spec does not close it.** An earlier draft claimed
`check_commit_trailers.py` would catch it; executed, it does not — that check compares the SIGNED
trailer against THIS session's own resolved name and has no cross-session state, so two sessions on
one name sign consistently and it stays silent. Teaching it to compare against the store's live
holders is the real fix and is **routed to `docs/STRATEGIC_BACKLOG.md`, owner infra**, rather than
claimed here. D-253 permits a stated gap; it does not permit a counter-measure that does not exist.

## Open / blocking unknowns

| # | Unknown | Resolution step |
|---|---|---|
| U1 | Whether the writer should validate the name against a repo roster (`.fabrik/agents.json`) or accept any well-formed name | Named in the approval dialogue; the design works either way |

**U2 is RESOLVED, not open.** An earlier draft asked whether self-naming should rewrite an
already-open run record's agent field. `command_run.py:2485-2487` already settles the identical
question for the analogous `account` field — *"resolved at start, when the env and the marker describe
THIS run — the close may run under a later flip"*. Freeze at start; never rewrite. Deferring a
question the codebase already answers is a defect, not an unknown.

## Decisions taken

To be minted at the implementing commit: the choice of a box-local session-keyed binding over a
relaunch, over a repo roster, and over a trailer-keyed scheme; that `mail.py` is deliberately NOT
taught; and that the shared-name cobra path is stated-and-routed rather than closed.
