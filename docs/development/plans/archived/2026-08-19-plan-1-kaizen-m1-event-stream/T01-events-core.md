# T01 — events-core: schema + emitter library + exposure resolver

Depends: —
Parallel: ⚡ (first; everything else consumes it)
Complexity: native
## Scope
The emitter library every other ticket consumes. Vocabulary + fail-open law per the spec (docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:54-74); the honesty `Signal` pattern mirrored from scripts/sysadmin/kaizen_shrink_audit.py:66. Account exposure resolves the `~/.claude-fleet/active` symlink target name directly (readlink — three lines; claude_rotate.py deliberately NOT in the read set, it is 10× this ticket's budget).

## Touches
- scripts/sysadmin/kaizen_events.py
- tests/test_kaizen_events.py
- docs/workstation/kaizen-event-stream.md

## Context Files
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- scripts/sysadmin/kaizen_shrink_audit.py
- docs/workstation/kaizen-shrink-audit.md



## Interfaces

Consumes: nothing (root ticket).
Produces:
- `kaizen_events.emit(event: str, sid: str | None = None, **fields) -> bool` — ONE JSON line
  appended to `$KAIZEN_EVENTS_DIR/<safe-sid>.jsonl` (default `~/.claude/state/events/`);
  fail-open: returns False on ANY error, never raises, never blocks. Line carries
  `schema` (int, start at 1), `ts` (ISO), `sid`, `event`, `exposure` (below), + the caller's fields.
- `kaizen_events.exposure() -> dict` — hub commit (git HEAD of the repo cwd resolves into, else
  `unknown`), account (the `~/.claude-fleet/active` symlink target name, else `unknown`), model
  (env `CLAUDE_MODEL`/`ANTHROPIC_MODEL` if present, else `unknown` — the collector backfills from
  transcripts), project (cwd-derived `/opt/<name>`), headless flag (`CLAUDE_MESH_HEADLESS` env or
  no TTY), plan_era (the newest `IN-PROGRESS` plan stem under `docs/development/plans/`, else `—`).
  The concurrency flag is COLLECTOR-side (overlapping session windows), not emit-side.
- `kaizen_events.resolve_sid(explicit: str | None) -> str` — explicit → `$CLAUDE_SESSION_ID` →
  the literal `unknown` (NEVER a shared bucket name; `unknown` events are the collector's
  unclassified-rate input).
- The schema section of `docs/workstation/kaizen-event-stream.md` — one row per event type with
  its required fields (the vocabulary from spec :57-63).

## Steps

1. TDD first (watched-fail-first): `tests/test_kaizen_events.py` —
   fail-open (monkeypatch open to raise → emit returns False, no exception), per-sid file naming
   (two sids → two files), single-line JSON parseability, unknown-sid fallback, line length
   asserted < 4096 (PIPE_BUF margin; oversize FIELD VALUES are truncated BEFORE serialization
   with a `truncated: true` marker — the emitted line is ALWAYS valid JSON; a test parses the
   truncated line back).
   RUN RED, then implement to green.
2. Implement `kaizen_events.py` (stdlib only; `# AFTER-EDIT:` header listing the consumer tickets'
   files). O_APPEND single `write()` per event. Exposure resolver with every field defaulting to
   `unknown`/`—`, never raising — every subprocess/git/filesystem probe inside its own
   try/except (CalledProcessError, OSError, ValueError all included; a non-repo cwd yields
   `unknown`, tested).
3. `--selftest` duplex canary (M0 discipline): emits into a temp dir and asserts both ways
   (good emit lands + parses; injected failure returns False and leaves no partial line).
4. Author `docs/workstation/kaizen-event-stream.md`: the schema table, the fail-open law, the
   per-session-file rationale (PIPE_BUF), the honesty semantics of `unknown`.
5. Gate: `uv run pytest tests/test_kaizen_events.py -q` green;
   `python3 scripts/sysadmin/kaizen_events.py --selftest` green.

## Behavior Contract

- **Given** a session whose emitter raises anywhere (disk full, bad field, missing dir), **When**
  any instrumented surface runs, **Then** the session proceeds unharmed and the emitter returns
  False — fail-open is proven by a test that injects the failure
  (scripts/sysadmin/kaizen_events.py).
- **Given** two concurrent sessions emitting simultaneously, **When** their events land, **Then**
  each writes only its own per-session file and no line tears (one file per sid; O_APPEND
  single-line writes ≤ PIPE_BUF asserted in-test).
- **Given** an event emitted from a context with no resolvable session id, **When** it lands,
  **Then** `sid` is the literal `unknown` and the collector counts it in the unclassified-rate —
  never silently merged into another session's stream.

Docs: docs/workstation/kaizen-event-stream.md (new — INDEX row rides T09's docs pass).
Gate: `uv run pytest tests/test_kaizen_events.py -q` && `python3 scripts/sysadmin/kaizen_events.py --selftest`
