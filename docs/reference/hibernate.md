# Hibernate — pausing every agent for a host sleep

The operator runs `/hibernate` in the hub coordinator's window (W-1e9ae1e5). The command
(`commands/_sources/hibernate.md`) sequences `scripts/sysadmin/hibernate.py`; this page says what the script reads and
decides.

## Who gets the pause

`hibernate.py targets` reads every session record in `~/.claude*/sessions/<pid>.json` and
`~/.claude-fleet/*/sessions/<pid>.json` (de-duplicated by real path). A record is a live session when its pid's start
time in `/proc/<pid>/stat` equals the record's `procStart` and the process is `claude`. An `entrypoint` of `sdk-*`
(`sdk-cli`, `sdk-ts`, `sdk-py`) is a cron-pool worker or a review seat (`claude -p`): counted, never messaged, never a coordinator and
its tree never a `status` row (a live one is an agent's seat or a headless row, below). Every other entrypoint, an unknown or missing one included, is an agent, so a new client fails
toward being checked. Every record says `kind: interactive`, so `kind` cannot tell them apart.

An agent's name is `CLAUDE_AGENT` in its environment, else its newest whoami binding. Agents are grouped by repo
(`/opt/<repo>` from the cwd). A repo's coordinator is its ledger's merge owner (`decisions.py --merge-owner`, D-874);
a repo whose ledger declares none (or has no ledger) and has one live agent has that agent as its coordinator, while a
FAILED lookup names nobody. A repo whose coordinator is not live, or held by two sessions, is messaged session by
session; so is the caller's own repo, which the caller coordinates, and a session outside `/opt`. The caller's own
session is never a target.

## When it is safe

`hibernate.py status` needs the caller's session id (`--self`, default `CLAUDE_CODE_SESSION_ID`) and checks each live
agent's cwd, the caller's own included (its row says `(you)`):

- a run record (`~/.claude/state/command-runs/<sid>.json`, named as `command_run.py` names it) still `running` blocks,
  and so does a running parent frame under it (`stack`), a record that is not readable JSON, and a session record
  with no session id — only the caller's own top-frame `/hibernate` run is running by design;
- uncommitted tracked changes block, and the row names up to five paths, then `+N more`; untracked files are
  listed, never blocking;
- a branch with commits ahead of its upstream blocks; a branch with no upstream blocks unless its HEAD is on some
  remote branch; a detached HEAD, a missing folder, a cwd that is empty or relative, or a git error or timeout blocks.

Six more checks, with T-3 the moment the hard hold arms (`deadline_at` minus 180 s; with no mark or no deadline
every check reads "before T-3"):

1. a live `sdk-*` session whose parent chain (8 hops) reaches no live agent is its own `headless` row: it blocks
   before T-3 and reads `held (headless)`, not blocking, from T-3 (the hold stops its tools; its pool requeues it);
2. an agent with live `sdk-*` seats (processes of their own) blocks before T-3; from T-3 it blocks unless its CLOSED
   record (`blocked`/`handoff`/`done`) names at least as many `abandoned_seats` as are live, and the row lists them;
3. the header (printed above the table, and as `header` in `--json`) names the pause, T-3, T and the time left, and
   whether the hibernate hold stands, whenever a pause is marked and not lifted;
4. with a mark, a non-self agent whose record closed `blocked`/`handoff` with `updated_ts` + 1 >= floor(`paused_at`)
   (`command_run.py` writes whole seconds) and no readable `resume_seed`/`resume_copy` blocks; a `done` close after the
   mark is its own non-blocking `done since the mark - verify` row;
5. an agent whose self-watch lock (`<safe>.selfwatch.lock` in `$CLAUDE_SOUND_LOCKDIR`, else
   `/tmp/claude-sound-locks-<uid>`) is not held by a live process blocks, an agent outside `/opt` and a missing lock
   dir included — the tick wakes armed sessions only (`_armed_sids`);
6. `battery-tick-last` in the state dir older than 180 s, absent or unparsable blocks as `no minute cron`.

`status` reads twice, 5 s apart (the test seam `HIBERNATE_STATUS_GAP_S`, honoured under pytest only), and prints
`SAFE TO HIBERNATE` only when no row blocks on the second read; a first read that blocks answers at once.

No session id, no live session found, or the caller not among
them, is exit 2 — never safe: an empty table is not a safe one.

## The pause marker and its timeline

The marker is `hibernate.json` in the rotation tick's state dir — `$ROTATE_STATE_DIR` when set, else
`<passwd home>/.claude/state` (every verb defaults `--home` to the passwd entry's home, never `$HOME`) — beside the rotate ledger. Its keys: `paused_at`, `words`, `deadline_at` (T, optional),
`lifted_at` (optional) and `lift_path` (`sleep`, `outage`, `cancelled`, `hub` or `migration`). Every writer goes
through `update_marker`, which holds an `flock` on `hibernate.json.lock` across its read-modify-write, so two writers
at once (the tick's lift and the hub's `lift`) both land.

- **The mark (T-0).** `hibernate.py mark --words "…" [--deadline 10m]` writes a fresh marker (no key of an earlier
  pause survives): `paused_at` now and, with `--deadline`, `deadline_at` = T (`10m`, `5m`, `1h`; a bare number is
  minutes). A deadline under 3 minutes (T-3 would fall before the mark), over 24 hours, or too large to represent is
  refused with exit 2 before anything is written. From the mark nothing new is dispatched.
- **T-3.** Three minutes before T the hard hold arms. `brief --deadline` names T-3 and T as clock times in the pause
  text (it refuses with exit 2 when no deadline is marked).
- **T.** The operator closes the lid.
- **The lift.** The hub coordinator, once awake, always runs `hibernate.py lift`, then `targets`, and sends every
  session "RESUME — the hibernate is over". The rotation tick's own lift — after a sleep, after a network outage once
  the API answers again, or 30 minutes past T — arrives with the plan's T06 and is not built yet; until it lands,
  `lift` is the only lift.

`hibernate.py paused` is the launchers' and dispatchers' check: exit 0 while a pause is marked and not lifted, 1
otherwise (no marker file included), and 2 when the marker file exists but cannot be read or parsed (it reads the file
raw, so a corrupt marker never reads as "not paused") or on any other error of its own.

## The manual lift

`hibernate.py lift` finds its caller's session: the nearest live claude session, an agent or an `sdk-*` session alike,
whose pid is an ancestor of the `lift` process, walking the ppid chain to pid 1 with no hop cap. It passes for:

- the hub's merge owner, named by `CLAUDE_AGENT` or the session's identity binding. The owner comes from
  `/opt/fabrik/scripts/decisions.py --merge-owner`; the `FABRIK_DECISIONS_PY` resolver override is honoured only under
  a test (`PYTEST_CURRENT_TEST`);
- the operator's plain shell: the walk reaches pid 1 with no claude session on it AND the real stdin is a terminal
  (`os.isatty(0)`; no environment variable can claim one). Every such lift writes a `hibernate-lift-shell` row to the
  rotate ledger naming its terminal, because this check cannot tell a fresh tmux window from the operator's. A lift
  orphaned under a pseudo-terminal (started with `setsid` from a terminal, or from a session whose record went stale)
  is the same case, and it is audited the same way.

Outside a test, `lift` reads the real `/proc` and home only: a `--proc` other than `/proc`, or a `--home` other than
the passwd home, exits 2 before anything is read, with a `hibernate-lift-refused` row naming the forged root, because a
forged ppid chain or session record would otherwise name any caller. Each is compared only when given: with no
`--home`, every verb (`lift` included) reads the passwd home (never `$HOME`), and with no `--proc` it reads `/proc`. Everything else that fails the check exits 3 with a `hibernate-lift-refused` row in the rotate ledger:
another session, a headless `sdk-*` session (refused before its name is read, since a seat inherits its parent's
`CLAUDE_AGENT`), a process with no terminal (`setsid`, `systemd-run --user`), and a chain that cannot be walked to
pid 1. A row the ledger cannot take goes to the fallback file (`ROTATE_LEDGER_FALLBACK`, else
`<tempdir>/claude-rotate-ledger-fallback-<uid>.jsonl`), with one stderr line.

A pass writes `lifted_at` and `lift_path=hub` and nothing else: it touches no stamp (clearing the `hibernate`
tier is the rotation tick's, T06, not built yet). A second lift leaves `lifted_at` where it was, so a session that already resumed is not told to
resume again. A marker file that cannot be parsed would stand paused (exit 2) forever. A passing lift therefore
replaces it with a well-formed lifted marker (`paused_at` = the file's mtime, `words` = `(unreadable marker replaced
by lift)`), writes a `hibernate-lift-replaced-marker` ledger row and says so. A refused caller changes nothing.

**Threat model.** Every agent runs as the operator's uid, so this check cannot stop a session that sets out to forge
it. It stops an accidental or convention-breaking lift, and every lift path leaves a ledger row. That is why the test
overrides are refused outside tests and the plain-shell residual stays auditable.

## After the wake

`hibernate.py woke` never writes. It answers 0 (RESUME) only when all of these hold:

- the pause was lifted (`lifted_at` at or after the current mark) and not by the marker migration
  (`lift_path=migration`);
- the lift is less than 24 hours old;
- this session has started no run since the lift, in any state, so a daily relaunch never re-runs a finished seed.

Otherwise it exits 1 with `no pending resume`, and with no lift yet it names the lift paths. It exits 2 when it
cannot tell: a marker `paused` would call corrupt (the same rule, every field it validates), or this session's run
record exists but cannot be read or parsed. A `resume-wake` row in
the rotate ledger is the tick's evidence for its lift, never `woke`'s, so an agent is never told to resume while the
hold still stands.

On RESUME it lists the session's seeds (`<command-runs>/seeds/<safe sid>-….json` or `.md`, where `<command-runs>`
is `$COMMAND_RUN_DIR` or `~/.claude/state/command-runs`, as `command_run.py` resolves it) written since the mark,
newest first,
because the parent run closes last. A JSON seed prints its `command_run.py start --command <c> --phases <n>
--resume-from <seed>` line, and a `.md` handoff says to open a fresh start and follow its `## RESUME`. Each seat in a
seed's `abandoned_seats` list (`pid`, `purpose`, `brief`, `output`, optional `procStart`) is shown with its state at
the wake: `still running (pid N)` (with no `procStart`, only when the process on that pid is `claude`), `finished
(output at <path>)` or `exited, no output`. Only the last is ordered
re-run, from its brief, because a frozen seat often finishes after the wake. One `get_chat` line names the session id
and the pause time. The kernel's boot time is no signal on WSL, because every sleep moves it forward, and the self-watch
still words a wake as "the fleet-quota hold LIFTED" (W-b01aa1ec), which is why agents ask `woke` instead of reading the
wake line.

After a lift, `lift` prints rotation offers: every live agent past the rotation line, with the `rotate-session …
--trigger lift` command to run at its next boundary, and every agent it could not read as an `unread` row
(`rotate_session.py due`, W-f975fee0 slice 3). The offer is advice — a fault in it prints one stderr line and `lift`
still exits 0.

## The pause text

`hibernate.py brief --role agent|coordinator --words "…"` prints the text the hub sends. An agent finishes its step,
lets its own subagents and seats finish, commits and pushes on its own worktree branch, closes each live run in the
first form its `command_run.py` accepts (`blocked --paused` · `handoff --resume` · `blocked` with the reason — the
vendored copy in fabrik-lib has no `--paused`), writes its resume point knowing the wake drops its cached prompt, and
replies one `PAUSED — …` line.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/hibernate.py`
<!-- END related-scripts -->
