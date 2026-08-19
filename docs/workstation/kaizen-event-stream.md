# Kaizen event stream (M1) — the typed record agents write about themselves

Box-local. Emitter: `scripts/sysadmin/kaizen_events.py`. Tests: `tests/test_kaizen_events.py`.
Store: one JSONL file per session under `$KAIZEN_EVENTS_DIR` (default `~/.claude/state/events/`).

The v1 meter read prose — transcripts and ledger tables — and its first run produced two instrument
bugs (a 100% failure rate from a wrong status vocabulary, a 1440-round ledger from a naive table
regex). Both are parsing artifacts of treating prose as data. M1 moves measurement to the source:
the hooks, the run-record machinery and the gate each append one typed line at the moment the thing
happens, and the collector reads events instead of inferring them
(`docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:54-74`). Transcripts become
forensics.

## The three laws

**1 — Fail-open.** `emit()` never raises and never blocks. Any failure (missing dir, full disk,
unserializable field, absent `git`) returns `False`, warns once on stderr, and writes nothing —
never half a line. A caller puts `kaizen_events.emit(...)` on its hot path with no `try/except` and
behaves identically when the entire stream is broken. Event files are a **data store, not a log**:
this module's own diagnostics go to stderr only, never into an event file.

A short write is the one failure that cannot be undone — every byte past ours already belongs to a
concurrent appender, so truncating back would eat *their* events. The emitter instead appends a
newline to terminate the fragment and returns `False`: the damage stays one unclassified line
instead of a fragment the next event is glued onto (which would cost two events, not one).

**2 — One file per session, one atomic append per event.** Each session owns `<sid>.jsonl`, and
every event is a **single `O_APPEND` `write()` of the whole line**. That is what makes it atomic:
on Linux, an append-mode write to a *regular file* takes the inode lock, so it cannot interleave
with a concurrent writer's — the guarantee is the kernel's file locking, **not** the `PIPE_BUF`
rule (which governs pipes). `MAX_LINE_BYTES` (4096) is a **defensive bound**: it caps the blast
radius if the guarantee ever fails, matches `PIPE_BUF` for free, and keeps lines cheap for the
collector to stream. ⚠️ The atomicity is **not guaranteed on NFS** (or any network filesystem) —
the events dir must stay local. Oversize **field values** are clipped *before* serialization (never
the serialized line), so the line that lands is always valid JSON; the clipped line carries
`truncated: true`. Clipping runs in progressive passes (512 chars / 200 items → 128/50 → 32/10);
an event that still cannot fit keeps its envelope and adds `fields_dropped: true`.

Verified live: 6 OS processes × 40 events into ONE file → 240 lines, every one parsing, max line
3154 bytes, no interleaving (`test_concurrent_processes_append_to_one_file_without_tearing`). The
session file is also opened `O_NOFOLLOW` — a symlink planted at that path would redirect appends
anywhere the process can write, so it fails open instead.

**3 — Honesty over guessing.** An unresolvable session id is the literal `unknown` and lands in
`unknown.jsonl` — never a shared bucket merged into a neighbour's stream, because `unknown` events
are the collector's unclassified-rate input. `$CLAUDE_SESSION_ID=unknown` is the *absence* of an
id, so it resolves with `sid_source: none`, never `env`. An unmeasurable exposure field is the
literal `unknown` (or `—` for `plan_era`), never a fabricated value and never an exception. An
empty universe and a clean result must stay distinguishable.

## The envelope — on every line

| Field | Type | Meaning |
|---|---|---|
| `schema` | int | Schema version (currently **1**). Bump on any breaking envelope change; the collector keys off it. |
| `ts` | str | UTC ISO-8601, millisecond precision. |
| `sid` | str | Session id, sanitized to `[A-Za-z0-9_-]` — identical to the file stem, so value and file can never diverge. Sanitization is **injective**: if it changed or truncated the raw id, an 8-hex digest of the raw value is appended (`a/b` and `a.b` must never merge into one stream). A clean id passes through untouched. |
| `sid_source` | str | `explicit` \| `env` (`$CLAUDE_SESSION_ID`) \| `none`. `none` makes the `nosession` collision measurable even where it is not yet solvable. |
| `event` | str | One of the vocabulary below. |
| `exposure` | obj | Stratification metadata (next section). |
| `truncated` | bool | Present only when a value was clipped. |
| `fields_dropped` | bool | Present only when the payload could not be made to fit at all. |

Caller fields are merged in at the top level. A field whose name collides with **any** envelope key
— `truncated` and `fields_dropped` included, even though the emitter adds those last — is re-keyed
with an `f_` prefix (`schema=99` → `f_schema: 99`), and the prefix **loops** (`f_f_…`) until the
name is free, so a caller sending both `schema` and `f_schema` loses neither. A sensor can never
forge the fields the collector trusts, nor claim `truncated: false` on a line the emitter clipped.

## Exposure — stamped on every event, resolved once per process

Three accounts rotate every ~2 days, so the model mix changes intrinsically through the week;
unstamped, that drift is attributed to whatever merged that day (spec `:97-104`). Every probe sits
in its own `try/except` (`CalledProcessError`, `TimeoutExpired`, `OSError`, `ValueError`) and
degrades to `unknown` alone.

| Field | Source | When unmeasurable |
|---|---|---|
| `commit` | `git rev-parse HEAD` in the session's cwd | `unknown` (non-repo cwd, no `git` binary) |
| `account` | the `~/.claude-fleet/active` symlink target's name | `unknown` |
| `model` | `$CLAUDE_MODEL` → `$ANTHROPIC_MODEL` | `unknown` — the collector backfills from transcripts |
| `project` | cwd-derived `/opt/<name>` (worktrees resolve to the same project) | `unknown` |
| `headless` | `$CLAUDE_MESH_HEADLESS` present ⇒ `true`; absent ⇒ `false` | never — a bool |
| `plan_era` | newest (max stem) plan with `Status: IN-PROGRESS` **or** `**Status:** IN-PROGRESS` under `docs/development/plans/` — plain plans + plan-set SPINES (`<dir>/<same-stem>.md`), never `T##` ticket files, never `archived/` | `—` |

**`headless` is env-driven only — there is deliberately no `isatty()` fallback.** Hooks, cron jobs
and every subprocess sensor read a pipe, so stdin is never a TTY there and an isatty-based flag
would be constant-true, pooling the very two distributions this field exists to separate. The mesh
contract is the honest signal: every headless dispatch exports the variable, so its absence means
human.

The **concurrency flag is collector-side** (overlapping session windows on the same project), not
emit-side — a session cannot know its own overlaps.

**Cost.** Resolving exposure is a cold-path cost paid once per process: **~4.6 ms median** (7 runs,
range 3.8–5.2 ms) — two `git rev-parse` subprocesses plus one bounded 4 KiB read per candidate plan
(never a full file, however large the plan). Cached lookups after that are ~0.01 ms. Accepted as
instrument overhead: a session that emits dozens of events pays it once.

## Event vocabulary (schema 1)

Required fields are beyond the envelope. Producers are the M1 tickets that wire each sensor.

| Event | Required fields | Producer |
|---|---|---|
| `session_start` | `cwd`, `project` | `.claude/hooks/session_orient.py` |
| `session_end` | — | `.claude/hooks/final_gate_stop.py` (Stop pass-through, i.e. it did NOT block) |
| `run_open` | `command`, `phases`, `terminal` | `scripts/command_run.py start` |
| `phase` | `n`, `title` | `scripts/command_run.py step` |
| `round` | `findings`, `classes_swept`, `classes_new` | `scripts/command_run.py round` |
| `run_close` | `verdict` (`done`\|`blocked`), `evidence_hash` | `scripts/command_run.py done`/`blocked` |
| `gate_run` | `tier`, `mode`, `status`, `checks: [{name, outcome}]` (every EXECUTED check, advisory rows labelled) | `scripts/final_gate.py` |
| `rule_activation` | `packs: [{pack, globs_fired}]` — labelled *invocation-time* activation | `scripts/select_rules.py`, `scripts/review_rubric.py` (`rubric_injection`) |
| `stop_block` | `cause` (`gate-red`\|`uncommitted`\|`unpushed`\|`promise-stall`\|`run-record`) | `.claude/hooks/final_gate_stop.py` |
| `final_block_emitted` | — | `.claude/hooks/final_gate_stop.py` |
| `death` | `class`, `reconstructed: true` | `scripts/sysadmin/kaizen_coroner.py` (post-hoc; hooks go silent exactly when things get interesting) |
| `revival` | `class`, `reconstructed: true` | `scripts/sysadmin/kaizen_coroner.py` |
| `operator_override` | `marker` | `.claude/hooks/final_gate_stop.py` — turns sanctioned skips from noise into labelled data |

An event outside this list is still written (losing data is worse than a typo) but warns on stderr,
so a misspelled sensor is visible the day it ships.

## API

```python
import kaizen_events                                   # scripts/sysadmin on sys.path

kaizen_events.emit("phase", sid=session_id, n=2, title="collector")   # -> bool, never raises
kaizen_events.resolve_sid(explicit)                    # explicit -> $CLAUDE_SESSION_ID -> "unknown"
kaizen_events.resolve_sid_with_source(explicit)        # -> (sid, "explicit" | "env" | "none")
kaizen_events.exposure()                               # memoized dict; exposure(refresh=True) re-probes
```

`emit()` takes one more keyword-only parameter, **`exposure_override` — producer-restricted**: a post-hoc
producer (only the coroner today, reconstructing a `death` from a session that is already gone)
passes the exposure it joined from that dead session's own last trusted events, and it **replaces**
the resolved exposure verbatim instead of stamping the coroner's own process. It is a parameter,
not a caller field, so it is never `f_`-re-keyed; a non-dict value is ignored in favour of the live
exposure. No live sensor should pass it — stamping your own process is what `exposure()` is for.

```python
kaizen_events.emit("death", sid=dead_sid, exposure_override=joined, reconstructed=True)
```

Consumers import defensively — an additive, idempotent `sys.path` append plus
`try: import kaizen_events / except Exception: kaizen_events = None`, and every call site guarded
with `if kaizen_events:` — so a project that has not yet received the module behaves exactly as
before.

## Config and CLI

| Env | Default | Effect |
|---|---|---|
| `KAIZEN_EVENTS_DIR` | `~/.claude/state/events/` | Where session files land (tests and fixtures point it at a temp dir). |
| `CLAUDE_SESSION_ID` | — | The session id when none is passed explicitly. Bash-tool shells carry it EMPTY → `unknown`; the literal `unknown` also resolves as `sid_source: none`. |
| `CLAUDE_MODEL` / `ANTHROPIC_MODEL` | — | `exposure.model`. |
| `CLAUDE_MESH_HEADLESS` | — | Present (any value) ⇒ `exposure.headless: true`; absent ⇒ `false`. |

```bash
python3 scripts/sysadmin/kaizen_events.py --selftest    # duplex canary
python3 scripts/sysadmin/kaizen_events.py --exposure    # print resolved exposure
```

`--selftest` is **duplex** by design: it asserts good events land, parse and stay within the line
bound, *and* that an injected write failure returns `False` leaving the file byte-identical, that a
symlinked event file is refused, and that an unresolvable sid lands in its own `unknown.jsonl` —
a one-way check cannot tell a working emitter from one that silently writes nothing. It restores
every environment variable it touches, so importing and running it cannot re-attribute later emits
in the same process. Every guard in the emitter has additionally been proven red-on-revert (neuter
the guard, watch its test fail, restore): truncation, fail-open, envelope shadowing, the looping
`f_` rescue, sid sanitization and injectivity, exposure honesty, the env-driven `headless` split,
the `plan_era` spine/status parsing, the torn-line terminator, and `O_NOFOLLOW`.
