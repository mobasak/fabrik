# Coordinator proactive assignment — the build

Status: DRAFT
Profile: small
**Owner:** infra
Spec: docs/superpowers/specs/2026-10-02-coordinator-assignment-design.md (DRAFT, `Size: small` — this plan's `/fabrik-plan-review` grades the spec's sections with the plan and holds the design-approval gate)
Work item: W-83021827 · Decision: D-512

## What this plan is

The build of spec § The delta D1–D7: two `work.py` verbs and a floor constant (Phase A), the Stop hook's eighth cause and the extension of its seventh (Phase B), the rule text in the docs and both contracts plus the hub's first triage run (Phase C). Three phases, inline execution by the orchestrator in the main checkout (`Profile: small`, D-169).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § The delta D1 (`work.py queue`) | IN | Phase A |
| I2 | spec § The delta D2 (`work.py triage`) | IN | Phase A |
| I3 | spec § The delta D3 (worker Stop cause) | IN | Phase B |
| I4 | spec § The delta D4 (coordinator Stop cause) | IN | Phase B |
| I5 | spec § The delta D5 (assignment notice line) | IN | Phase A (printed by `triage --apply`) |
| I6 | spec § The delta D6 (`QUEUE_FLOOR`, `queue_floor`) | IN | Phase A |
| I7 | spec § The delta D7 (docs and both contracts) | IN | Phase C |
| I8 | spec § Validation V1–V5 | IN | Behavior Contracts of Phases A and B |
| I9 | spec § Validation V6 (a week of hub data) | OUT-OF-SCOPE | measured after the build; W-83021827 stays open for it with its `next` naming the week-1 read |
| I10 | spec § Lifecycle — the hub's first `triage --apply` (dedup, route, surface plans) | IN | Phase C step 6 |

## What we already agreed (citations, not restatement)

- The approach — owned queues topped up by the coordinator, pull at the worker: spec § Decisions taken, § Rejected alternatives (judge panel B, 3 of 3).
- Enforcement by Stop refusal on both sides: spec § Decisions taken.
- The worker reads owned-then-unowned (`ready --mine`): spec § The delta D3; `scripts/work.py:725-727`.
- `K = 3`, per-repo override: spec § The delta D6.
- Quota band and DECISION exemptions; GREEN only starts new work: spec § The delta D3, § Decisions taken.
- External facts (no idle field in `ListAgents`; `notify_when_idle` limits): spec § External dependencies; `docs/reference/research/2026-10-02-coordinator-assignment-ledger.md`.
- The design-approval row is minted by `/fabrik-plan-review` at its gate, not here (`Size: small`, spec § Phase 5 D10 of the fabrik-spec command).

## Global Constraints (every phase inherits these)

- Hub tooling only: no service, no compose, no port, no `shape:` flag (spec § Shape/infra implications).
- `datetime.now(UTC)`, never `datetime.utcnow()` (`.windsurf/rules/core/10-python.md:220`) — the stale-age computation in `triage`.
- Every new `--json` output is ONE line (compact `json.dumps`, no indent): the Stop hook's `_resolve_line` reads only the first stdout line (`.claude/hooks/final_gate_stop.py:1620-1636`).
- The Stop hook FAILS OPEN on every new read: a missing store, an unreadable band, a resolver timeout (`_RESOLVER_TIMEOUT_S = 5.0`, `:1552`) or a non-zero exit means no block.
- The roster of workers is the repo's linked worktrees under `<main>/.claude/worktrees/<name>` whose `<name>` matches `work.py`'s `NAME_RULE` and is NOT a harness isolation worktree (`agent-` followed by hex, e.g. `agent-a5dabb83737b0534f` in this repo today). No worker worktree ⇒ a one-window repo.
- 12-Factor: logs to stdout/stderr only (XI); no daemon (VIII); config through files the repo commits and env (III). Nothing else of the twelve is touched (no service, no migration, no backing service).
- Shared tree: explicit pathspecs; the kaizen logs and untracked work items of siblings are never staged; `.fabrik/work/` item files this plan's run creates are committed with the phase that created them.
- A commit that touches a governance-sync path (read the `governance-sync` files filter in `.pre-commit-config.yaml` at execution — `.claude/hooks/` and `templates/governance/` are on it) lands ONCE per phase, after that phase's FULL `/fabrik-review`.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | timezone-aware datetimes; no logfiles | `:220`; `:292` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED: docs + template) | no skipped heading levels; fenced code only | `:241`; `:243` |
| `scripts/work.py` | verb registration `sub.add_parser(...).set_defaults(fn=...)`; distributor idiom; `_ready_from`; `_new_item`/`_create_item`; `_drop_duplicate` | `:3877-3972`; `:2684-2686`; `:708-727`; `:643-677`; `:2976-3043` |
| `.claude/hooks/final_gate_stop.py` | `decide_stall`; counter slots; `_merge_owner_duty`; `_run_record`; accepted-DECISION signal | `:1756-1767`; `:468-486`; `:1663-1753`; `:526-562`; `:3360` |
| `scripts/sysadmin/quota_posture_hook.py` | the band reader | `_load_posture` `:179`; `_band_for_session` `:477` |
| fabrik-lib | none — BUILD (spec § fabrik-lib verdict) | — |
| `agents-fabrik.md` infra invariants | none touched (no service) | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Pack:line | Verbatim | Applies to |
|---|---|---|
| `.windsurf/rules/core/10-python.md:220` | "**`datetime.now(UTC)`, never `datetime.utcnow()`**" | Phase A `triage` stale ages |
| `.windsurf/rules/core/10-python.md:292` | "**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`" | Phases A, B (stdout/stderr only) |
| `.windsurf/rules/core/40-documentation.md:241` | "**No skipped heading levels**" | Phase C docs |
| `.windsurf/rules/core/40-documentation.md:243` | "**Fenced code blocks only**" | Phase C docs |

## Phase A — the work store: `queue`, `triage`, the floor

Appetite: 90

**Interfaces — Produces:** `work.py queue [--json]` → one line of JSON `{"floor": K, "workers": [{"name", "owned_ready", "claim"}], "one_window": bool}`; `work.py triage [--apply] [--json]` → the report (dedups, routed, ambiguous, surfaced, stale, top-up plan) and, with `--apply`, the assigns plus one `SendMessage to=<worker>: assigned <ids> — <titles>` line per worker; `QUEUE_FLOOR = 3`; `_queue_floor(repo) -> int` (config `queue_floor`, else the constant; a non-integer or < 1 falls back). **Consumes:** nothing from later phases.

1. **Test first (the risky path is the roster and the floor).** Create `tests/test_work_coordinator.py` on the `tests/test_work.py` helpers (`_env`, `_repo`, `_init`, `_add`, `_edit`, `run`): a repo with two linked worker worktrees (`git worktree add .claude/worktrees/w1`, `…/w2`) and one `agent-0123abcd` harness worktree; owned items for `w1` only. Write the V-rows below as tests; run `python -m pytest -q tests/test_work_coordinator.py` and confirm they FAIL with `invalid choice: 'queue'` (the verb does not exist).
2. Add `QUEUE_FLOOR = 3` beside `DEFAULT_LEASE_S` (`scripts/work.py:87`) and `_queue_floor(repo)` reading `_read_config(repo).get("queue_floor")`.
3. Add `_workers(repo) -> list[str]` — `git worktree list --porcelain` from the common dir's main checkout; keep paths `<main>/.claude/worktrees/<name>` whose name passes `NAME_RULE` and does not match `^agent-[0-9a-f]+$`; sorted. Empty ⇒ one-window.
4. Add `cmd_queue` — per worker, `len(_ready_items(repo, mine=False, agent=None))` filtered to `owner == worker` (reuse `_ready_from`, never a second readiness rule), plus the worker's live claim from `_live_claims`; `--json` prints the one-line shape above. Register `sub.add_parser("queue", …)` beside `ready` (`:3877-3961`).
5. Add `cmd_triage` (distributor idiom `:2684-2686`): (a) dedup — group open `awaiting-operator` items by `block_digest`, else normalised `question`; for each group call `_drop_duplicate` on the copies keeping the oldest, `--why "triage: same question"`; (b) route — an unowned open item whose `tags`, `links` or title names exactly one worker's name (or one charter in `docs/reference/agents/<name>.md` when present) gets that owner via the `cmd_assign` write path; more than one match ⇒ listed as ambiguous; (c) surface — each live plan (spine, never a `T##` ticket, never `archived/`) whose first `Status:` line reads CONVERGED, and each CONVERGED spec with no plan linking it, gets ONE `task` item via `_new_item`/`_create_item` with `links.plan`/`links.spec` set — skipped when an item already links that path; (d) stale — open items older than 14 days (`datetime.now(UTC)`) with no claim are LISTED, never changed; (e) top-up plan — for each worker below `_queue_floor`, the next unowned items by `(priority, created, id)`. Without `--apply` nothing is written; with `--apply`, (a)–(c) and the top-up assigns run and the per-worker `SendMessage to=…` lines print last. `--json` is one line.
6. Run `python -m pytest -q tests/test_work_coordinator.py tests/test_work.py tests/test_work_claims.py tests/test_work_doc_verbs.py` → all pass; `ruff check scripts/work.py tests/test_work_coordinator.py` and `ruff format --check` → clean.
7. `python scripts/enforcement/check_doc_sync.py` and the phase's doc step: `docs/reference/work-tracking.md` gains the two verbs in its verb table (so `tests/test_work_doc_verbs.py` stays green) — reconciled + native-verified.
8. **`/fabrik-review-scoped` on this phase's changed surface** to a confirmed-zero closing pass (`Profile: small`; if `scripts/work.py` is on the `governance-sync` filter at execution, the FULL `/fabrik-review` instead, before the commit).
9. Commit the phase (explicit paths, provenance trailers, `Agent-Phase: A`).

**Behavior Contract**
- **Given** a repo with workers `w1`, `w2` and a harness worktree `agent-0123abcd`, **When** `work.py queue --json` runs, **Then** it prints one line naming `w1` and `w2` only, with `owned_ready` counts that equal what `ready --mine` would list for each.
- **Given** a repo with no linked worktrees, **When** `work.py queue --json` runs, **Then** `one_window` is true and `workers` is empty.
- **Given** `queue_floor: 5` in config, **When** `queue` runs, **Then** the floor reads 5; **Given** `queue_floor: "x"` or `0`, **Then** it reads 3.
- **Given** three awaiting-operator items with the same `block_digest`, **When** `triage --apply` runs, **Then** two are dropped as duplicates of the oldest and a second run drops nothing.
- **Given** an unowned item tagged `w1`, **When** `triage --apply` runs, **Then** its owner is `w1`; **Given** one naming both workers, **Then** it is listed ambiguous and stays unowned.
- **Given** one live CONVERGED plan spine and one EXECUTED plan, **When** `triage --apply` runs twice, **Then** exactly one `task` item links the CONVERGED plan.
- **Given** `w1` owns 1 ready item and 4 unowned items exist, **When** `triage --apply` runs, **Then** `w1` owns 3, and one `SendMessage to=w1: assigned …` line prints.
- **Given** a caller who is not the distributor, **When** `triage --apply` runs, **Then** it refuses like `assign` and writes nothing; **When** `triage` runs without `--apply`, **Then** nothing is written whoever calls it.

## Phase B — the Stop hook: the worker cause and the coordinator cause

Appetite: 90

**Interfaces — Consumes:** `work.py queue --json` and `work.py triage --json` (Phase A), one line each. **Produces:** `_work_idle_reason(root, sid, band, decision_ground) -> str | None` (D3) and `_under_supplied_reason(root) -> str | None` (D4, folded into `_merge_owner_duty`'s reason when no merge request waits); `_COUNTER_SLOTS = 8`; `_session_band(transcript_path) -> str | None` (GREEN/AMBER/RED/WALL or None).

1. **Test first.** Create `tests/test_stop_hook_coordinator.py` on the `tests/test_stop_hook_merge_requests.py` pattern (`_load`, `_repo`, `_drive`, `_slots`), stubbing the band and the two `work.py` resolvers. Write the V-rows below; run it and confirm RED (no eighth cause exists).
2. `_session_band`: import `scripts/sysadmin/quota_posture_hook.py` by absolute hub path (`/opt/fabrik/scripts/sysadmin/quota_posture_hook.py`, the path every repo on this box can read) and return `_band_for_session(_load_posture(now)[0], transcript_path)[0]`; any exception or a missing posture ⇒ `None`.
3. `_work_idle_reason`: in a repo with a `.fabrik/work/` store; no live claim for `sid`; `ready --mine` non-empty (via `_resolve_line` on `work.py next`, one line); the session is not the merge owner of a repo whose `queue --json` says `one_window: false`; `(_run_record(sid) or {}).get("state") != "running"`; band `== "GREEN"`; `decision_ground is None` ⇒ the reason *"WORK IS WAITING: claim `<id> — <title>` (`python3 scripts/work.py claim <id>`) and start it, or say why it cannot start."*; anything else ⇒ `None`.
4. Wire it into `_stall_gate` after the merge-owner cause (`:3542-3589`) with its own counter slot: bump `_COUNTER_SLOTS` to 8 and extend `_read_counters`' pad-on-read (`:471-486`) so a 7-slot file reads slot 8 as 0; block with `"WORK IS WAITING (attempt {n}/{CAP}). " + reason`, warn through at CAP like the others.
5. `_under_supplied_reason`: only when `queue --json` says `one_window: false`; for each worker with `owned_ready < floor`, when `triage --json`'s top-up plan has items for it ⇒ *"<w> has <n> of <K> items queued and <m> assignable items wait: run `python3 scripts/work.py triage --apply`, then send the assignment line it prints."* `_merge_owner_duty` returns this when no merge request waits (it already resolves the caller as the merge owner, `:1714-1724`), under the same quota and DECISION exemptions as step 3.
6. Run `python -m pytest -q tests/test_stop_hook_coordinator.py tests/test_stop_hook_merge_requests.py tests/test_final_gate_stop_hook.py tests/test_final_gate_stop_deferral.py` → all pass; ruff clean.
7. `python scripts/enforcement/check_doc_sync.py`; `docs/workstation/hooks-index.md`'s Stop row: "SEVEN blocking causes" → "EIGHT", the counter count `(7)` → `(8)`, and the new cause appended as a ` · `-joined clause in the row's own format — reconciled + native-verified.
8. **The FULL `/fabrik-review`** on this phase's surface (`.claude/hooks/` is a governance-sync path) to a confirmed-zero closing pass, BEFORE the commit.
9. Commit the phase once (explicit paths, trailers, `Agent-Phase: B`); the post-commit sync distributes the hook.

**Behavior Contract**
- **Given** a worker session with no live claim and one owned ready item, band GREEN, **When** it stops, **Then** it is blocked naming that item, and the CAP+1th stop warns through.
- **Given** the same session holding a live claim, or with `ready --mine` empty, **When** it stops, **Then** it is not blocked by the eighth cause.
- **Given** the same session at band AMBER, RED or WALL, or with a `running` run record, or ending on an accepted DECISION block, **When** it stops, **Then** it is not blocked by the eighth cause.
- **Given** an unreadable posture or a `work.py` resolver that times out, **When** the session stops, **Then** it is not blocked (fail-open).
- **Given** the merge owner of a repo with worker `w1` holding 1 of 3 items and assignable items waiting, **When** it stops, **Then** it is blocked with the triage instruction; once `queue` shows `w1` at 3, **Then** it is not.
- **Given** a one-window repo, **When** its only agent stops with no claim and ready work, **Then** the eighth cause blocks it and the coordinator extension never fires.
- **Given** a 7-slot counter file from before this change, **When** the hook reads it, **Then** slot 8 reads 0 and no other slot moves.

## Phase C — the rule text, the contracts, the hub's first triage, Finish

Appetite: 60

**Interfaces — Consumes:** Phases A and B as committed. **Produces:** the rewritten rule in the two reference docs and both contracts; the hub store after one `triage --apply`.

1. `docs/reference/work-tracking.md` § Ownership and the distributor (`:130-141`): replace the "Assigning is not the default…" sentences with the D-512 rule (the coordinator triages and keeps every worker at `K` owned items; a worker claims its next item rather than ending idle; claiming unowned items stays the fallback), citing D-512; re-read `:206-211` (the § Serialising acts cross-reference) and correct it to the new rule.
2. `docs/reference/multi-agent-operating-model.md` § Claim or assign (`:216-224`): same rewrite, keeping the serialising-act and untriaged-queue cases as reasons to ASSIGN rather than as exceptions to self-service.
3. Hub `CLAUDE.md:48`: after "…and it alone runs `work.py assign`." add one sentence per duty (coordinator: triage and keep every worker at the floor, refused at Stop otherwise; worker: claim the next item, refused at Stop otherwise). `templates/governance/CLAUDE.md`: find the merge-owner/coordinator statement by grep (`D-471`, `merge owner`) and add the same two sentences there; if the template carries no coordinator sentence, add the two beside its merge-owner rule. Run `python -m pytest -q tests/test_governance_template_split.py tests/test_work_contract_rule.py tests/test_mail_structure.py` → green.
4. `python scripts/enforcement/check_doc_sync.py`; `CHANGELOG.md` atop `[Unreleased]`; the build's D-row via `decisions.py --append` (the build lands; supersedes the self-service clause of D-442).
5. **`/fabrik-docs-review`** over the four docs this plan changed, to a truthful fixed point.
6. **The hub's first run:** `python3 scripts/work.py triage` (report), read it, then `python3 scripts/work.py triage --apply`; send each printed `SendMessage to=…` line; commit the item files it wrote.
7. **Finish — the ONE heavy round:** the `/fabrik-execute-plan` D7 floor over the whole-plan diff (`dispatch_headroom.py --units <groups>`, stamped first), one receipt under `docs/development/reviews/`.
8. `python scripts/final_gate.py --check --json` → `"status": "success"` and `python scripts/enforcement/check_convergence.py` → green. A green gate is necessary, not sufficient: the Evidence below is the proof.
9. Commit (explicit paths, trailers, `Agent-Phase: C`), push; close W-83021827's build half with `work.py` evidence and set its `next` to the V6 week-1 read.

**Behavior Contract**
- **Given** the rewritten docs, **When** `tests/test_work_doc_verbs.py` runs, **Then** every verb the doc names exists in `work.py`, `queue` and `triage` included.
- **Given** both contracts after the edit, **When** `tests/test_governance_template_split.py` runs, **Then** it passes and each contract states both duties once.

## File Scope (owned paths)

- scripts/work.py
- tests/test_work_coordinator.py
- .claude/hooks/final_gate_stop.py
- tests/test_stop_hook_coordinator.py
- docs/reference/work-tracking.md
- docs/reference/multi-agent-operating-model.md
- docs/workstation/hooks-index.md
- CLAUDE.md
- templates/governance/CLAUDE.md
- .fabrik/work/
- docs/development/reviews/2026-10-02-plan-3-coordinator-assignment-review.md
- docs/superpowers/specs/2026-10-02-coordinator-assignment-design.md

## Evidence

**Phase A** — `scripts/work.py:708-727` (`_ready_from`), `:2669-2701` (`cmd_assign`), `:2976-3043` (`_drop_duplicate`), `:643-677` (`_new_item`/`_create_item`):

```text
$ grep -n "def _ready_from\|def cmd_assign\|def _drop_duplicate\|def _new_item\|def _create_item\|^QUEUE_FLOOR\|def _agent_name\|def _read_config" scripts/work.py
347:def _agent_name(*, session: str = "") -> str:
502:def _read_config(repo: Path) -> dict:
643:def _new_item(
668:def _create_item(repo: Path, item: dict, *, attempts: int = 8) -> Path:
708:def _ready_from(
2669:def cmd_assign(repo: Path, args: argparse.Namespace) -> int:
2976:def _drop_duplicate(repo: Path, args: argparse.Namespace, keep_id: str, why: str) -> int:
$ git worktree list | sed "s/ .*//"
/opt/fabrik
/opt/fabrik/.claude/worktrees/agent-a5dabb83737b0534f
/opt/fabrik/.claude/worktrees/agent-ac9bf02c69b237079
/opt/fabrik/.claude/worktrees/fleet
/opt/fabrik/.claude/worktrees/intel
```

**Phase B** — `.claude/hooks/final_gate_stop.py:468` (`_COUNTER_SLOTS`), `:1552` (`_RESOLVER_TIMEOUT_S`), `:1663-1753` (`_merge_owner_duty`); `scripts/sysadmin/quota_posture_hook.py:477` (`_band_for_session`):

```text
$ grep -n "_COUNTER_SLOTS = \|^CAP = \|_RESOLVER_TIMEOUT_S = " .claude/hooks/final_gate_stop.py
46:CAP = 3  # consecutive blocked stops before letting it stop anyway (anti-trap)
468:_COUNTER_SLOTS = 7
1552:_RESOLVER_TIMEOUT_S = 5.0
$ grep -n "def _band_for_session\|def _load_posture" scripts/sysadmin/quota_posture_hook.py
179:def _load_posture(now: float) -> tuple[dict | None, str]:
477:def _band_for_session(posture: dict, transcript_path: object) -> tuple[str | None, bool]:
```

**Phase C** — `docs/reference/work-tracking.md:130-141`, `docs/reference/multi-agent-operating-model.md:216-224`, `CLAUDE.md:48`:

```text
$ wc -l -c scripts/work.py .claude/hooks/final_gate_stop.py
  3980 178210 scripts/work.py
  3821 198388 .claude/hooks/final_gate_stop.py
  7801 376598 total
```

## Self-audit

- **Grounding passes:** three native seats (work store, Stop hook, docs/template) returned anchors; each anchor this plan cites was re-read by the orchestrator in the evidence block above or in the seat's quoted line. Two plan-shaping facts came from them: the hook keeps only the first stdout line of a resolver (hence one-line JSON), and the quota band lives outside the hook (hence `_session_band`).
- **(a) coverage:** every row of "What we already agreed" maps to a phase — approach (A, B), Stop refusal on both sides (B steps 3–5), owned-then-unowned (B step 3), `K` (A step 2), exemptions (B steps 3, 5), external facts (no code; spec), approval row (plan-review). V6 is the one OUT-OF-SCOPE item, with its destination.
- **(b) cross-phase signatures:** `queue --json` keys `floor`, `workers[].name`, `workers[].owned_ready`, `workers[].claim`, `one_window` are produced in A step 4 and consumed in B steps 3 and 5 by those names; `triage --json`'s top-up plan is produced in A step 5(e) and consumed in B step 5.
- Fixed point: not claimed — `/fabrik-plan-review` converges it.

## Residual unknowns

- **Resolved:** where the quota band lives (`quota_posture_hook.py:477`); how the hook calls a script (`_resolve_line`, first line only); the roster source (linked worktrees, harness worktrees excluded); the dedup key (`block_digest`, `_drop_duplicate` requirements `:2989-3008`).
- **Open — U1:** whether `scripts/work.py` is on the `governance-sync` files filter — resolution: Phase A step 8 reads the filter at execution and picks the scoped or full review accordingly.
- **Open — U2:** the template may carry no coordinator sentence (the docs seat found D-471's sentence only in the hub `CLAUDE.md:48`) — resolution: Phase C step 3 greps and adds both sentences beside the template's merge-owner rule either way.
- **Open — U3:** `K = 3` is a planning figure — resolution: spec V6, the week-1 read.

## Coverage Checklist

| Class | Verdict |
|---|---|
| Roster correctness (linked worktrees vs harness `agent-<hex>` worktrees) | UNCHECKED |
| Fail-open on every new hook read (band, store, resolver timeout, non-zero exit) | UNCHECKED |
| Counter-slot upgrade (7-slot files read cleanly as 8) | UNCHECKED |
| Exemption precedence (quota band, running record, accepted DECISION, merge owner vs one-window) | UNCHECKED |
| Triage idempotence and the distributor gate | UNCHECKED |
| Doc and contract truth (two docs, two contracts, hooks-index) | UNCHECKED |
| fail-open | UNCHECKED |
| cost/quota accounting | UNCHECKED |
| boundary/sentinel | UNCHECKED |
| behavior-without-a-test | UNCHECKED |

The rubric this plan's review injects into every seat brief, run on the plan's own changed paths:

```bash
python3 scripts/review_rubric.py --changed scripts/work.py tests/test_work_coordinator.py .claude/hooks/final_gate_stop.py tests/test_stop_hook_coordinator.py docs/reference/work-tracking.md docs/reference/multi-agent-operating-model.md docs/workstation/hooks-index.md CLAUDE.md templates/governance/CLAUDE.md
```

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
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
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

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

### core/40-documentation.md  (hit: CLAUDE.md, docs/reference/multi-agent-operating-model.md, docs/reference/work-tracking.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_stop_hook_coordinator.py, tests/test_work_coordinator.py)
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

# promote-to-check_*: 34 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `uv` `pip` `pip install` `poetry` `pipenv`
- `pyproject.toml` `uv.lock`
- `async def` `.query().all()` `25-data-postgres.md`
- `engine` `async_session` `get_db` `src/database.py` `25-data-postgres.md`
- `DATABASE_URL` `postgresql+asyncpg://user:pass@host:port/db` `REDIS_URL` `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `localhost` `postgres-main`
- `30-ops.md` `.tmp` `/tmp`
- `except Exception` `logger.exception()` `55-observability.md`
- `from {package}.logger import get_logger` `55-observability.md` `structlog.get_logger()` `logging.getLogger(__name__)`
- `asyncio.create_task()` `asyncio.TaskGroup`
- `datetime.now(UTC)` `datetime.utcnow()`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `30-ops.md`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
- `scripts/enforcement/_doc_registry.py::PROJECT_DOCS` `/fabrik-plan-after-chat` `Docs:`
- `Agent-Role: primary` `Co-Authored-By` `Co-Authored-By:` `Agent-Role:`
```
