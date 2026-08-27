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
| `sid_source` | str | `explicit` \| `env` (`$CLAUDE_SESSION_ID`) \| `none` \| `join`. `none` makes the `nosession` collision measurable even where it is not yet solvable; `join` marks an id a sensor **reconstructed** from this stream (`command_run.py --adopt-sid`) — an inferred id must never be indistinguishable from one the session actually carried. |
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
| `commit` | `git rev-parse HEAD` in the session's cwd (`git -C` when the caller pins one) | `unknown` (non-repo cwd, no `git` binary) |
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
instrument overhead: a session that emits dozens of events pays it once. The hooks resolve it
**lazily, on their first emit**, so a Stop that emits nothing pays nothing at all.

## Event vocabulary (schema 1)

Required fields are beyond the envelope. Producers are the M1 tickets that wire each sensor.
Every `scripts/command_run.py` row additionally carries `command` + `seq` + `persisted` + `cwd`
(the paragraph below the table), not just `run_open`.

| Event | Required fields | Producer |
|---|---|---|
| `session_start` | `cwd`, `project` | `.claude/hooks/session_orient.py` — only where a Stop hook also runs (payload cwd has `scripts/final_gate.py`) and only on `source=startup` |
| `stop_pass` | `outcome` (`clean`\|`warned_through`), `warned` | `.claude/hooks/final_gate_stop.py` — the Stop pass-through, i.e. it did NOT block |
| `session_end` | `closed_by` (`coroner`\|`ttl`) | `scripts/sysadmin/kaizen_coroner.py` — the genuinely session-scoped, post-hoc close; a TTL-expired run record's close emits one too (`closed_by: ttl`) |
| `run_open` | `command`, `phases`, `terminal`, `nested` | `scripts/command_run.py start` |
| `phase` | `n`, `title` | `scripts/command_run.py step` |
| `round` | `n`, `findings`, `classes_swept`, `classes_new`, `classes_open` | `scripts/command_run.py round` |
| `run_close` | `verdict` (`done`\|`blocked`), `evidence_hash`, `closed_by`, `rounds`, `resumed`, `resumed_phase`, `resumed_rounds`, **`feedback`** (`filed`\|`none`\|`unstated`), **`feedback_to`** (subset of `infra`/`fleet`/`intel`), **`feedback_hash`** | `scripts/command_run.py done`/`blocked` |
| `gate_run` | `tier`, `mode`, `status`, `checks: [{name, outcome}]` (every EXECUTED check, advisory rows labelled) | `scripts/final_gate.py` |
| `rule_activation` | `packs: [{pack, globs_fired}]` — labelled *invocation-time* activation | `scripts/select_rules.py`, `scripts/review_rubric.py` (`rubric_injection`) |
| `stop_block` | `cause` (`gate-red`\|`uncommitted`\|`unpushed`\|`promise-stall`\|`run-record`), `outcome` (`blocked`\|`warned_through`) | `.claude/hooks/final_gate_stop.py` |
| `final_block_emitted` | — | `.claude/hooks/final_gate_stop.py` — emitted on the NON-BLOCKING exit only |
| `death` | `class`, `reconstructed: true` | `scripts/sysadmin/kaizen_coroner.py` (post-hoc; hooks go silent exactly when things get interesting) |
| `revival` | `class`, `reconstructed: true` | `scripts/sysadmin/kaizen_coroner.py` |
| `operator_override` | `marker`, `kind` (`human-gate`\|`blocked-escalation`), `stalls` (count of waived stalls this turn), `kinds` (every waived kind, in order) | `.claude/hooks/final_gate_stop.py` — turns sanctioned skips from noise into labelled data; ONE event per turn carries the whole waiver ledger |
| `fleet_health` | `project`, `swept`, `cell`, `reason`, `checks` (`{check: verdict}`), `duration_s` | `scripts/sysadmin/kaizen_outcomes.py --sweep` — one per swept project (T07's nightly outcome tier) |
| `instrument_alarm` | `reason`, `mismatches` (first 10) | `scripts/sysadmin/kaizen_collect_v2.py` — golden-corpus refusal or a delta darkening; instrument health is metric zero |

An event outside this list is still written (losing data is worse than a typo) but warns on stderr,
so a misspelled sensor is visible the day it ships.

**The Stop hook fires once per TURN, not once per session.** So its pass-through is `stop_pass`,
and **session liveliness derives from a session's LAST `stop_pass` timestamp** — the hole in the
data is a session that produced **no `stop_pass` ever**, not a missing "session end". `session_end`
is reserved for the coroner's post-hoc close of a session that is already gone.

**`stop_block.outcome` separates enforcement that HELD from enforcement that gave up.** After `CAP`
consecutive blocked stops each cause warns through and lets the turn end; that give-up used to be
indistinguishable from a clean pass, so a cause the agent simply outlasted counted as enforcement
working. A warned-through turn emits `stop_block` with `outcome: warned_through` **and** carries the
cause in its `stop_pass.warned`.

**`operator_override` requires a cause that was actually WAIVED**, not merely a message containing
the marker vocabulary. The promise-guard records `(kind, marker)` whenever a stall MATCHES and is
then exempted by a sanctioned-skip marker; only that ledger produces the event. Matching the marker
alone fired on the mandated `NEXT: operator decision: …` footer of nearly every operator-gated task
end — the normal way a fabrik turn finishes, not an override.

**Message-shaped events are emitted only at the exit that ends the turn.** A blocked stop is
RETRIED, and the same final message is re-read on every retry — emitting `final_block_emitted` at
the hook's entry point counted one task terminator up to `CAP+1` times.

Every `command_run.py` event additionally carries `cwd`, `persisted` (did the record's `save()`
succeed), and the ordering pair **`command` + `seq`**. `seq` comes from the record's `event_seq`
counter, incremented under the same flock that serializes the mutation, so it is dense and gap-free
even when twenty subagents share one session id. **Order a run's stream by `(command, seq)`, never by
`ts`** — timestamps are millisecond-quantized and concurrent events collide inside one millisecond.
Details: `docs/reference/command-run-protocol.md` § Events.

## Consumers — the derived-facts store and the metric registry

The daily collector (`scripts/sysadmin/kaizen_collect_v2.py --daily`, T06) parses each session's
event file ONCE into a one-row JSONL store (`~/.claude/state/kaizen/derived-facts.jsonl`,
append-only, keyed `(sid, facts_version, day)`), publishes per-day deltas into versioned series
files (`series/<metric>@v<N>.jsonl` — a definition change writes a NEW file, never rewrites), and
refuses to publish anything unless the hand-labelled golden corpus
(`tests/fixtures/kaizen-golden/`) derives to its expected counts first. T08's backfill
(`scripts/sysadmin/kaizen_backfill.py`) shares the SAME store with `era: "transcript"` rows —
every event-only field an honest `—` string, and their `facts_version` (row + skip key) is the
backfill's own `TRANSCRIPT_FACTS_VERSION`, independent of the event schema's `FACTS_VERSION`,
so an event-schema bump never re-appends the corpus — and writes the noise-floor report
(`noise-floor@v1.md` beside the store). The collector's metric inputs are **event-era only**
(`daily()` filters `era != "event"` rows out of its day/week selection and delta baselines — the
T09 era filter; `read_rows` itself stays era-blind because T08's report needs both eras).

Every metric is registered with a version, a definition hash, and a **reciprocal counter pair**
(an unpaired definition refuses to load — a schema constraint). The full M1 registry
(`kaizen_outcomes.registry()` = T06's ten + T07's six):

| Metric | Counter pair | Level | Source |
|---|---|---|---|
| `rules_compliance` | `terminator_spam` | run_close events | T06 collector |

### `feedback` — why `unstated` is a third value, not a synonym for `none`

Added 2026-08-27 with the close-out feedback duty (`commands/_fragments/close-feedback.md`,
auto-appended to all 31 commands). The agent running a command is the only witness to how the
machinery behaved on that run, and `--feedback` is how that verdict reaches the stream.

- `filed` — a beat was named; something was routed. `feedback_to` says which.
- `none` — the agent looked and had nothing to file. **A real answer.**
- `unstated` — no `--feedback` was passed at all.

Collapsing `unstated` into `none` would report perfect diligence for a corpus nobody ever looked at —
the fail-silent-green shape reproduced inside the telemetry built to measure it. The prose never
enters the store; only a `blake2s` hash, on the same contract `evidence_hash` already keeps.

**Consumer status:** the stream now CARRIES the signal; the kaizen log's `Filed (spec/mail)` cell is
still the analyst's to type. Wiring it to the measured count belongs in `kaizen_outcomes` alongside
the other windowed metrics (its day-scoped delta rows and the 20% attribution floor), and
`_merge_cells` must first be changed so a computed value can never overwrite an analyst's prose — its
current rule lets a real new value win. Both are open; neither is bodged in here.
| `terminator_spam` | `rules_compliance` | final_block_emitted / closures | T06 collector |
| `premature_stop_rate` | `first_attempt_gate_pass` | EVENT-level stop verdicts | T06 collector |
| `first_attempt_gate_pass` | `premature_stop_rate` | sessions, first gate_run | T06 collector |
| `gate_failure_taxonomy` | `rule_activation` | per-check fail distribution (non-check runs) | T06 collector |
| `rule_activation` | `gate_failure_taxonomy` | run-closing sessions | T06 collector |
| `unclassified_rate` | `hole_count` | instrument health (metric zero) | T06 collector |
| `hole_count` | `unclassified_rate` | coroner holes | T06 collector |
| `death_occurrences` | `death_classes` | day's death events (coroner-evidence-gated) | T06 collector |
| `death_classes` | `death_occurrences` | day's NEW class distribution (delta suffix) | T06 collector |
| `rework_rate` | `review_rounds` | git-mined commits, `/opt/*` | T07 `--rework` |
| `review_rounds` | `rework_rate` | round-carrying sessions | T07 (from store rows) |
| `fleet_health` | `sweep_coverage` | swept projects, all checks green | T07 `--sweep` |
| `sweep_coverage` | `fleet_health` | swept / configured pilot set | T07 `--sweep` |
| `premature_stop` | `stop_block_causes` | SESSION-level premature stops | T07 `--stops` |
| `stop_block_causes` | `premature_stop` | full cause histogram (events) | T07 `--stops` |

Truncated lines (`truncated`/`fields_dropped`) derive **envelope-only**: the event name, window
and exposure count, the partial payload never feeds a distribution — the line rides the
unclassified rate as reason `truncated`. **The root law (delta seam):** a delta field is only
computable against a baseline that MEASURED the same field — a field the predecessor row never
carried (a `FACTS_VERSION` bump day) is `None` in the delta row, and every consumer excludes
that row from numerator AND denominator, counting a stated **bump-day gap**; `runs_noncheck >
runs` violates non-check ⊆ all and is warned + unmeasured. Metrics whose numerator event family
sits mostly in the `unknown` stream are guarded by the **20% attribution floor** over the same
window of rows they compute from (`rules_compliance`, `terminator_spam`, `rule_activation`,
`gate_failure_taxonomy`): below it the metric renders `—` with the reason — an attributed sliver
is not the population. `gate_failure_taxonomy`'s guard operand is the attributed **NON-check**
occurrence count (the population the value is computed over — check-run mass cannot vouch for a
non-check sliver), and it counts NON-check runs only (`mode.check` false — the Stop hook's
automatic `--lean --check` self-review is diagnostic, never taxonomy population; the same
rationale as `first_attempt_gate_pass`). The WINDOWED store metrics (`review_rounds`,
`premature_stop`, `stop_block_causes`) use the **windowed attribution guard**, and since W5-1
BOTH of its operands — and the value population — come from the SAME source with the SAME
semantics: day-scoped DELTA rows for the caller's day stamps (`window_delta_rows`; every sid's
in-window store rows delta'd against its nearest earlier row, so a lifetime session
contributes only its in-window growth). The CLI's on-demand view is the trailing window — the
last `KAIZEN_OUTCOMES_WINDOW_DAYS` LOCAL calendar days including today — while the daily
publish passes `days=[the published day]` so every PUBLISHED day point is DAY-scoped (W7-1: a
trailing-window value published as a day point made the weekly cell sum overlapping windows).
Attributed-side bootstrap symmetry (W6-2, mass tightened W12-1): a first-ever attributed
delta row carrying the metric's own POPULATION mass (stop verdicts for the stops pair,
round growth for review_rounds) whose `first_ts` predates the window is
bootstrap-unmeasurable — excluded from
both operands and counted; a kept row whose baseline (`delta_of`) skips at least one calendar
day before the ROW'S OWN day smears the skipped days' growth into it — deliberate and
annotated in the detail (W7-5, per-row since W9-1: the immediately-preceding day is the
normal consecutive baseline, never a smear). The weekly log cells run no guard of their own
(the rounds carve-out runs the guard function at week scope and prints its detail — W9-2):
they AGGREGATE the published day
series (the single-source law, W6-1; split weeks are annotated PER HALF for paired metrics —
W8-3 — and one-sided death weeks dash on the pair contract), EXCEPT the rounds cell, which
recomputes latest-per-sid over the week's delta rows under the day publish's guard (W8-1 —
point-in-time per-session quantities cannot be deduplicated from anonymous day points; see
`docs/workstation/kaizen.md` § The kaizen-log row). The unattributed operand is the
`unknown` accumulator's per-day delta mass over the same window days; the same 20% floor applies.
The guard publishes (share stated) when healthy, dashes when the unknown stream holds the
window's mass, and HEALS when attribution improves. An unknowable unknown mass dashes with its
TRUE cause (W5-2): accumulator **shrank**; **pre-v3 rows in window** (no `events_unattributed`
field — absent ≠ 0, the root law); **bump-day gap** (measured with no same-field baseline); or
**bootstrap window** — the accumulator's first derivation carries pre-window backlog, so the
first window after store bootstrap is expected unmeasurable (family-scoped: a bootstrap row with
zero family mass is a knowable 0). A window with NO derived delta rows at all is a derivation
gap — "no derivation in window" naming the measured cause (empty store · transcript-era only ·
rows out of window · every in-window delta shrink-suppressed, W7-4), never a knowable 0. Never a lifetime ratio (fails open on a bad
week) and never a lifetime-knowability rule (ratchets permanently dead once any unknown mass
ever existed). `hole_count` dashes when the
coroner is BLIND (missing/unreadable transcripts dir → `holes()` returns None, mapped to `—`
reason "transcripts unreadable"); an empty-but-readable dir stays a measured 0 — and a CRASHED
coroner sweep reports `holes_today: null` (unmeasured), never a measured-looking 0. `premature_stop_rate` (T06, event-level) and
`premature_stop` (T07, session-level) share the `PREMATURE_CAUSES` vocabulary and cross-reference
each other in their definitions — read them together. The cross-reference rides a non-hashed `cross_reference` field, so the published
definition hashes are unchanged (the versioned-definitions law). The loop doc — cadence, cron
lines, runbooks, the M1→M2 gate — is `docs/workstation/kaizen.md`; noise-floor method and
variance live in `noise-floor@v1.md` (regenerate: `kaizen_backfill.py --report`).

## API

```python
import kaizen_events                                   # scripts/sysadmin on sys.path

kaizen_events.emit("phase", sid=session_id, n=2, title="collector")   # -> bool, never raises
kaizen_events.resolve_sid(explicit)                    # explicit -> $CLAUDE_SESSION_ID -> "unknown"
kaizen_events.resolve_sid_with_source(explicit)        # -> (sid, "explicit" | "env" | "none")
kaizen_events.exposure()                               # memoized dict; exposure(refresh=True) re-probes
kaizen_events.exposure(cwd=payload_cwd, probe_timeout_s=2.0)   # pinned + hot-path bounded
```

`exposure()` takes two optional parameters beyond `refresh`:

- **`cwd`** pins the three cwd-derived probes (`commit`, `project`, `plan_era`) to a directory the
  caller names, via `git -C`. A sensor running in a **subprocess** — every hook — has no guarantee
  its own process cwd is the session's project; unpinned, it stamps project A's events with project
  B's commit, silently and unfixably after the fact. Hooks pass the payload's `cwd`. The result is
  **not** memoized (a caller-specific answer must never poison the shared cache); `cwd=None` keeps
  the historical process-cwd behaviour and its cache. A repeat `cwd=None` call served from the
  cache runs NO probes at all, so its `probe_timeout_s` is moot.
- **`probe_timeout_s`** (default `10.0`) bounds each git probe. A caller on an interactive hot path
  passes something small — the hooks use `2.0`, because SessionStart's whole budget is 10 s. A
  non-positive or non-finite value falls back to the default.

Two further keyword-only parameters on `emit()`:

- **`sid_source`** — provenance-restricted, validated against `SID_SOURCES`
  (`explicit`/`env`/`none`/`join`). A sensor that RECONSTRUCTED the id passes `"join"`; an unvetted
  value warns and keeps the resolved source, since a stray label would silently open a new bucket in
  every collector query. `None` resolves exactly as before.
- **`probe_timeout_s`** — forwarded to `exposure()` for a caller on a hot path (`None` keeps
  the 10s default). `command_run.py`'s post-save flush passes **2.0**: the mutation is already
  durable, so waiting buys nothing and `unknown` beats latency in front of an agent.

Both are parameters, not caller fields, so neither can reach the payload or be `f_`-re-keyed.

`emit()` takes one more keyword-only parameter, **`exposure_override` — producer-restricted**: a post-hoc
producer (only the coroner today, reconstructing a `death` from a session that is already gone)
passes the exposure it joined from that dead session's own last trusted events, and it **replaces**
the resolved exposure instead of stamping the coroner's own process — merged over an all-`unknown`
`EXPOSURE_KEYS` baseline, so a partial override still ships every schema key (missing ones the
literal `unknown`, never absent). It is a parameter, not a caller field, so it is never
`f_`-re-keyed; a non-dict value is ignored in favour of the live exposure. No live sensor should
pass it — stamping your own process is what `exposure()` is for.

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
