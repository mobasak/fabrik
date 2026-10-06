# Plan — an account that refuses inference is never the next account (W-f8bfe7eb)

Status: DRAFT
Profile: small
**Owner:** —
**Surface:** `git rev-parse HEAD` = 99b111443 at authoring; `scripts/sysadmin/claude_rotate.py` 7560 lines, byte-identical to `scripts/aro-wake/claude_rotate.py`

Spec: `docs/superpowers/specs/2026-10-06-rotation-capability-probe-design.md` (DRAFT at 99b111443, `Size: small`,
`Profile: delta` — `/fabrik-plan-review` grades its sections together with this plan and flips both). Decision: D-614.
Source: fleet mail 01M3QG6GG5NQNVG5MZE6SAME1G; work item W-f8bfe7eb. Estimated diff: ≈250 code lines in ONE source
file, copied byte-identical to its twin (2 code files), tests excluded — `_capability_probe` + `_capability_verdict` ≈60
(replacing `_keepalive_ping`'s 30), the parked lock + `_parked_update` + `_auto_park` ≈60, the probe cache and its two
windows ≈35, `_validated_pick` split and docstring ≈20, the D6 branch in `_fleet_flip_leg` ≈45, the D4 call site ≈8,
the D4b hook in `run_claude` ≈25 (sum 253). Tests ≈330 lines in one new file plus two repointed tests.

## What this plan is

Three inline phases the orchestrator codes itself in the worktree; no coder is dispatched:

- **A — the primitives**: the classifying probe that replaces `_keepalive_ping` (spec D1, D4), the locked `parked.json`
  update (D5) and the auto-park (D3), with their tests.
- **B — the wiring**: probe on promote inside `_validated_pick` (D2), active re-validation in the flip leg (D6), and the
  wrapper's classification (D4b), with their tests.
- **C — docs and Finish**: the rotation doc, the whole-plan `/fabrik-review`, the gate.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I8 (6 IN, 2 OUT-OF-SCOPE) | IN as dispositioned there | Phases A and B, per the spec rows |
| I2 | *"Plan it as Profile: small"* (this run's brief) | IN | this header |
| I3 | *"D1 classifying probe … D6 active-account re-validation per trust window"* (the brief's six deltas) | IN | A: D1, D3, D4, D5 · B: D2, D4b, D6 |
| I4 | *"both copies … byte-identical"* | IN | Global Constraints; every phase's commit step |
| I5 | *"The plan-review flips spec+plan to CONVERGED and holds the approval gate (open question … ≤6 h detection window)"* | IN | `/fabrik-plan-review` at Phase 5; Residual unknowns R4 |
| I6 | Grounding finding (this run): on a fleet host `run_claude` never moves the pointer — its rotate is withheld (`scripts/sysadmin/claude_rotate.py:541-548`), so spec D4b's "and rotates" cannot hold as written | IN — D4b re-scoped to park only; the next tick flips away | Phase B step 4; the spec's D4b, D4, D1, Validation and U1 amended in this plan's `/fabrik-plan-review` |

## What we already agreed (citations, not restatement)

- Goal, personas, lifecycle: `spec § Goal`, `spec § Personas`, `spec § Lifecycle`; why: `spec § Why this exists`.
- Measured behaviour: `spec § What exists today (grounded)`; external facts G1–G6: `spec § External dependencies`.
- The delta D1–D6: `spec § The delta`; cost ceiling: `spec § Cost`; validation: `spec § Validation`.
- Chosen approach (probe on promote, judge split 2–1): `spec § Chosen approach`; rejected four: `spec § Rejected
  alternatives`; decision row D-614: `spec § Decisions taken`. The approval row is minted by `/fabrik-plan-review` at
  its gate (a `Size: small` spec is approved there, not here).
- Open unknowns U1–U3: `spec § Open unknowns` — U1 is resolved by this run's probe (Evidence, Phase A).

## Global Constraints (every phase inherits these)

- **Byte-identical twin**: every edit lands in `scripts/sysadmin/claude_rotate.py` and is copied with
  `cp scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py` before each commit; `cmp` of the two prints
  nothing (`scripts/sysadmin/claude_rotate.py:3-4`; pinned by `tests/test_mail_addressing.py:228`).
- **Stdlib only**, no new import beyond the module's existing ones (`fcntl`, `json`, `subprocess` are already imported,
  `scripts/sysadmin/claude_rotate.py:31-41`); no dependency file is touched (`core/10-python.md:30`).
- **Credential bytes are never read, copied, written or logged** by the probe (module docstring `:19-26`); the probe
  binds `CLAUDE_CONFIG_DIR` and `CLAUDE_QUOTA_HOME` to the dir itself, exactly like the function it replaces (`:7134-7140`).
- **Inconclusive changes nothing**: a timeout, an `OSError`, a non-zero exit with no parseable result, or an `is_error`
  result for any cause other than the refusal is `inconclusive`; the pick, the ping's `ping_failed` and the wrapper's
  result proceed exactly as today (`spec § Lifecycle`, failure clause).
- **`refused` needs `is_error: true` in the result JSON** — never a bare text match over stdout, so a conversation that
  merely quotes the code (the class `run_claude`'s own comment admits at `:796-798`) can never park an account.
- **The probe's `result` text is never logged, stored or alerted** — a healthy result echoes the account's private
  session context (Evidence, Phase A); the ledger row carries the verdict, the source and `api_error_status` only.
- **Never key on `subtype`** — measured this run: a failed call reports `"is_error":true,"subtype":"success"` (Evidence,
  Phase A).
- **Stdout is never written** from the auto-park or the wrapper path: the CLI passthrough mirrors stdout to its callers
  (`:522-523`); the auto-park reports on stderr, the ledger and Telegram only.
- **The operator owns un-parking** (D-443, `docs/DECISIONS.md:158`); nothing in this plan removes an email from
  `parked.json` except `--unpark`. A manual `--switch` never probes (`_cmd_fleet_switch` → `_flip_active(…, manual=True)`
  at `:3643`, which never calls `_validated_pick`).
- **12-Factor on this surface**: a box-local cron script, not a service — **III** one optional env knob
  (`ROTATE_PROBE_TRUST_S`), read with `os.environ.get` and a default; **XI** no log file (stderr + the existing ledger);
  the rest not engaged (no backing service, port, process model or deploy).
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md`, the Behavior Contract and
  Watched-fail-first rows); assertions on `parked.json`, ledger rows, the pointer and verdict strings, never on prose.
  The `claude` binary is a PATH stub script or a monkeypatched `cr.subprocess.run` (the patterns at
  `tests/test_claude_fleet.py:1767-1779` and `:1412-1416`). Red-on-revert runs in a throwaway worktree
  (`git worktree add --detach <scratch>/probe HEAD`), never in the shared checkout.
- Seats never mutate git state (read-only git only); never read `~/.claude*`; never run `uv` or `pip`; a seat runs
  Python as `.venv/bin/python …` with `PYTHONPATH=<worktree>/src`.
- **Execution discipline (native seats only, D-181):** every phase ends with `/fabrik-review-scoped` on its surface (the
  floor of three native seats on different angles, stamped with `command_run.py dispatch`), not handing on until its
  closing pass confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet
  and a Haiku finder per slice (D-344), the orchestrator executing every refutation. Within a phase the steps are
  sequential (each consumes the previous); the review seats are the parallel fan-out, merged and refuted by the
  orchestrator.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | no deps-file edit; timeouts owned by the resilience pack | `core/10-python.md:30`, `:218` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | one test per behaviour; watched-fail-first; a guard proven five ways | `core/45-testing-strategy.md` Behavior Contract, Watched-fail-first and BANNED rows |
| `.windsurf/rules/core/40-documentation.md` (MATCHED — the rotation doc) | structured docs; Doc Sync in the same change | `core/40-documentation.md:240` |
| `.windsurf/rules/core/58-resilience.md` (AVAILABLE, matches the work) | every external call bounded; graceful fallback | `core/58-resilience.md:88` |
| `docs/DECISIONS.md` D-443 | parked = never picked; operator un-parks; broken state parks nothing | `docs/DECISIONS.md:158` |
| `fabrik-lib` | none covers Claude subscription rotation — BUILD in place | `spec § fabrik-lib verdict` |
| `agents-fabrik.md` § Development Environment | WSL dev box; the tick runs from cron there | `agents-fabrik.md:130` |
| `specs/services/*.yaml` `shape:` | not engaged: no service | `spec § Shape / infra implications` |
| Claude Code `-p` result JSON | `is_error`, `api_error_status`, `result`; refusal code `oauth_org_not_allowed` | `spec § External dependencies` G1, G3, G4 |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source | Rule |
|---|---|---|
| "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | .windsurf/rules/core/10-python.md:30 | Deps (no new import, no deps edit) |
| "Timeouts/retries on every outbound call are owned by" | .windsurf/rules/core/10-python.md:218 | The probe keeps a bounded timeout |
| "every external call has timeout + retry with backoff. Circuit-breaker for repeated failures. Graceful fallback when dependencies are down." | .windsurf/rules/core/58-resilience.md:88 | Inconclusive falls back to today's pick |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | .windsurf/rules/core/45-testing-strategy.md:20 | Behaviour Contract |
| "**Watched-fail-first** (for tests this change adds or modifies" | .windsurf/rules/core/45-testing-strategy.md:22 | Red first |
| "**No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes." | .windsurf/rules/core/45-testing-strategy.md:21 | Assert state, not prose |
| "**No skipped heading levels** — `##` to `###`, never `##` to `####`" | .windsurf/rules/core/40-documentation.md:240 | Docs (the § Parking paragraph stays under its `###`; no new heading) |

## Phase A — the primitives: the classifying probe, the parked lock, the auto-park

Appetite: 90

**Interfaces — Produces** (all in `scripts/sysadmin/claude_rotate.py`; `spec § The delta` D1, D3, D4, D5):
- `_capability_verdict(rc: int | None, stdout: str) -> str` — pure. The result object is `json.loads(stdout)` when the
  whole stdout parses as a JSON object (a pretty-printed result), else the LAST line of `stdout` that parses as a JSON
  object with `"type": "result"` (a result after a warning line). Returns `"refused"` when that object has `is_error`
  true AND its whole serialisation (`json.dumps(obj)` — so `result`, `error` or `errors` alike) contains
  `oauth_org_not_allowed` or `disabled claude subscription access`, compared lower-cased — `api_error_status` is read
  for the ledger only, never required (spec U2). Returns `"ok"` when `rc == 0` and no result object has `is_error` true
  (a non-JSON stdout at rc 0 is `ok`, keeping `tests/test_claude_fleet.py:1767`'s semantics). Everything else, `rc is
  None` and a refusal printed only on stderr before the run starts included, is `"inconclusive"` (G1 covers in-run
  failures only; a pre-run failure fails open). The `result` text is never logged or stored — a healthy result echoes
  the account's private session context (Evidence, Phase A).
- `_capability_probe(cfg_dir: Path) -> str` — replaces `_keepalive_ping` (`:7129-7157`), same env, same
  `KEEPALIVE_TIMEOUT` (default 150) and `errors="replace"`; argv `["claude", "-p", "ok", "--output-format", "json",
  "--max-turns", "1", "--tools", ""]`; returns `_capability_verdict(p.returncode, p.stdout)`, and `"inconclusive"` on
  `OSError`/`SubprocessError`. `_keepalive_ping` is deleted; its one caller (`:4055`) and its two tests move to the new
  name.
- `_parked_lock_fd() -> int` — `<fleet_root>/parked.lock`, `O_CREAT|O_RDWR|O_NOFOLLOW`, `0o600`; the mirror of
  `_assignments_lock_fd` (`:1628-1638`).
- `_parked_update(email: str, park: bool, *, repair: bool) -> bool | None` — under `fcntl.LOCK_EX` on that fd, re-reads
  `<fleet_root>/parked.json` STRICTLY: missing → empty; unreadable or not a JSON list → with `repair=False` return
  `None` and write nothing (an automated park never overwrites the operator's list — spec § Constraints digest, "broken
  parked.json parks nothing"); with `repair=True` (the operator's `--park`/`--unpark`) proceed from empty, exactly as
  `_cmd_park` does today (`:3885`). Return `False` when nothing changes, else `_write_json_atomic(path, sorted(...),
  mode=0o644)` and return `True`; `None` on `OSError` (write failed). A lock fd that cannot open
  (`_STATE_DIR_ERRORS`, `:450`) returns `None` with one stderr line and writes nothing — the assignments site's rule
  (`:3692-3694`: "cannot lock → apply in memory only; never risk clobbering the table"). Unlock and close each in their
  own `try` (`:3712-3716`).
- `_auto_park(email: str, *, source: str, status: object = None, row: dict | None = None) -> bool` — `source` ∈
  `promote` · `active` · `ping` · `wrapper`. Normalises `email = email.strip().lower()` first (as `_cmd_park` does,
  `:3877`), then refuses (stderr, returns `False`) an email not in `_known_account_emails()` (`:3861-3870`), so a `pending-login` identity (`:3699`) is never written. Calls `_parked_update(email, True,
  repair=False)`; on `True` appends
  `{"event": "auto-park", "email", "cause": "oauth_org_not_allowed", "source", "api_error_status": status, "ts": _now()}`
  via `_ledger_append` and sends `_tick_telegram(<msg>, key=f"capability-{email}")` naming the account, the cause and
  the one-step fix `claude_rotate.py --unpark <email>`; when `row` is given sets `row["weekly_cap"] = 0` and
  `row["capability_refused"] = True`, so every later reader of this tick walls it through the cap path it already has
  (`_flip_candidate_verdict`, `:3509-3510`) — the row is walled even when the write returned `None`, so a broken or
  unlockable `parked.json` still excludes the account for this tick. Writes nothing to stdout. Returns `True` when the
  account is parked after the call (newly or already).
- `_cmd_park` (`:3873-3900`) keeps its CLI output and return codes and calls `_parked_update(…, repair=True)` for the
  write.

**Consumes:** nothing from later phases.

Steps:
1. **Test first (the highest-risk behaviour, A1)**: create `tests/test_claude_rotate_capability_probe.py`, importing the
   fleet harness helpers (`_canonical`, `_fleet_creds`, `_pin`, `_point`, `_fake_oauth`, `_usage_blob`) from
   `tests.test_claude_fleet` (`tests/__init__.py` exists). Write A1–A4 against `_capability_verdict`. A1's five
   legitimate spellings of the refusal, all `refused` (5/5 or it is a finding): the code in `result`; the incident's
   human text "Your organization has disabled Claude subscription access for Claude Code" in `result` with no code;
   the code in an `error` field rather than `result`; the result pretty-printed across several lines; the code in mixed
   case. Two framing cases beside them, also `refused`: the one-line result preceded by a non-JSON warning line, and
   `api_error_status: null` instead of `403`. The verbatim not-logged-in result captured this run (Evidence) is
   `inconclusive`; the verbatim healthy result's keys (`is_error: false`, `terminal_reason: "completed"`) at rc 0 are
   `ok`; an `is_error: false` result whose `result` text quotes `oauth_org_not_allowed` is `ok`; empty stdout with
   the refusal on stderr only is `inconclusive`. Run
   `.venv/bin/python -m pytest tests/test_claude_rotate_capability_probe.py -q` → expect a collection/attribute
   failure naming `_capability_verdict` (red for the right reason).
2. Implement `_capability_verdict` and `_capability_probe`; delete `_keepalive_ping`; change the call site at `:4055` to
   `verdict = _capability_probe(with_creds[0]["dir"])`: `ok` → today's re-read of the token and usage; `refused` →
   `_auto_park(email, source="ping", row=row)` and NOT `ping_failed` (the chain is alive, only the capability is gone —
   D4); `inconclusive` → `row["ping_failed"] = True` as today. Repoint `tests/test_claude_fleet.py:1400-1440` (argv
   expectation becomes the JSON argv; `is True` becomes `== "ok"`) and `:1767-1779` (`== "ok"`). Re-run step 1 → green.
3. Write A5–A8, then implement `_parked_lock_fd`, `_parked_update`, `_auto_park` and the `_cmd_park` refactor:
   - A5: `_auto_park` on a known email → `parked.json` lists it, one `auto-park` ledger row carrying the email and
     `source`, one `_tick_telegram` call with `key="capability-<email>"`, `capsys` stdout empty.
   - A6: two writers racing — a monkeypatched `_write_json_atomic` that sleeps between the read and the write, two
     threads parking two different emails → both emails in `parked.json` (red without the lock: the second write
     drops the first).
   - A7: the stale-reading ping returning the refusal → the row carries `capability_refused` and NOT `ping_failed`,
     and the account is parked; the ping returning a timeout → `ping_failed` true and nothing parked.
   - A8: a `parked.json` holding invalid JSON → `_auto_park` leaves its bytes unchanged, returns `False`, and still
     walls the row it was given; `cr.main(["--park", <email>])` on the same file still repairs it (today's operator
     behaviour). An unknown email and `pending-login` → nothing written.
   Run `.venv/bin/python -m pytest tests/test_claude_rotate_capability_probe.py tests/test_claude_fleet.py -q -k
   "capability or keepalive or park"` → all pass.
4. `cp scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py && cmp scripts/sysadmin/claude_rotate.py
   scripts/aro-wake/claude_rotate.py` → no output, rc 0.
5. **Phase gate**: `.venv/bin/python -m pytest tests/test_claude_rotate_capability_probe.py tests/test_claude_fleet.py
   tests/test_claude_rotate_v2.py tests/test_mail_addressing.py -q` → every test passes (the fleet, v2 and twin suites
   unchanged except the two repointed keepalive tests); `.venv/bin/python -m mypy scripts/sysadmin/claude_rotate.py
   --ignore-missing-imports` → no new error against the pre-phase count. Red-on-revert for A1, A5 and A6 in a
   throwaway worktree (neuter the refusal branch; drop the lock; drop the ledger append) → each named test red, then
   the worktree removed.
6. `python scripts/enforcement/check_doc_sync.py` → no finding for this phase (no doc trigger yet; the CHANGELOG entry
   lands with the commit).
7. **`/fabrik-review-scoped`** on Phase A's changed surface (`scripts/sysadmin/claude_rotate.py` hunks, the new test
   file, the two repointed tests) — BLOCKING, run to its closing pass confirming zero defects; fix and re-run the gate
   after each fix.
8. Commit Phase A (explicit pathspecs: both `claude_rotate.py` copies, the new test file, `tests/test_claude_fleet.py`,
   the `CHANGELOG.md` hunk via the private-index recipe; trailers `Agent-Role: primary`, `Agent-Phase: A`), push.

**Behavior Contract (Phase A):**
- **Given** a `claude -p` result with `is_error` true naming `oauth_org_not_allowed` (or the incident's "disabled Claude subscription access" text) anywhere in the result object, **When** it is classified, **Then** the verdict is `refused` for all five spellings and both framings (spec § The delta D1)
- **Given** a result at exit 0 with `is_error` false, or a non-JSON stdout at exit 0, **When** it is classified, **Then** the verdict is `ok` (spec § The delta D1)
- **Given** a timeout, an `OSError`, or an `is_error` result for another cause such as "Not logged in", **When** it is classified, **Then** the verdict is `inconclusive` (spec § Lifecycle)
- **Given** an `is_error: false` result whose text quotes `oauth_org_not_allowed`, **When** it is classified, **Then** the verdict is `ok`, never `refused` (Global Constraints, the quoted-code class)
- **Given** a refused account, **When** `_auto_park` runs, **Then** `parked.json` lists it, the ledger has one `auto-park` row, one Telegram alert names the `--unpark` fix, and stdout is empty (spec § The delta D3)
- **Given** two park writers racing, **When** both complete, **Then** both emails are in `parked.json` (spec § The delta D5)
- **Given** the stale-reading ping returns the refusal, **When** the tick builds its rows, **Then** the account is parked and its row is not marked `ping_failed` (spec § The delta D4)
- **Given** a broken `parked.json` or an unknown identity, **When** an automated park runs, **Then** the file is left untouched and only the in-tick row is walled, while the operator's `--park` still repairs the file (spec § Constraints digest)

## Phase B — the wiring: probe on promote, active re-validation, the wrapper

Appetite: 120

**Interfaces — Consumes** (Phase A): `_capability_probe(cfg_dir) -> str`, `_capability_verdict(rc, stdout) -> str`,
`_auto_park(email, *, source, status=None, row=None) -> bool`.

**Interfaces — Produces** (`spec § The delta` D2, D4b, D6):
- `_probe_trust_s() -> float` — `ROTATE_PROBE_TRUST_S` (default 21600), non-finite or ≤0 → the default (the
  `_env_float` refusal pattern).
- `_probe_cache_path() -> Path` — `_rotate_state_dir() / "capability-probe.json"` (`:2225-2231`); content
  `{email: {"verdict": "ok" | "inconclusive", "ts": <epoch>}}`. A `refused` verdict is never cached (the account is
  parked instead). An unreadable file reads as empty (the next probe runs, bounded by the windows below).
- `_PROBE_RETRY_S = 1800` — a module constant: an `inconclusive` verdict is not re-probed by D2 or D6 for 30 minutes,
  so a probe outage costs those two paths at most two calls per account per hour, never one per tick. The D4
  stale-reading ping keeps its own budget (`_ping_slots`, `:5561`; at most `ROTATE_REFRESH_MAX_PER_RUN` accounts a
  tick, each only when its reading is older than `ROTATE_READING_MAX_AGE_S`) — it is today's call, unchanged in count —
  and it writes its verdict into the same cache through `_record_probe`, so D6 never re-probes an account the ping
  just probed. The flip leg's own flips are dwell-exempt
  (`ignore_dwell=True` at `:5722`, `:5740`, `:5843`, `:5894`), so the dwell bounds nothing here — these two windows
  are the only bound.
- `_probe_account(email: str, slug: str) -> str` — returns the cached verdict without a call while it is younger than
  its window (`ok`: `_probe_trust_s()`; `inconclusive`: `_PROBE_RETRY_S`); otherwise runs
  `_capability_probe(_fleet_root() / slug)`, stores the verdict with `_record_probe`, and returns it.
- `_record_probe(email: str, verdict: str) -> None` — writes an `ok` or `inconclusive` verdict with `ts = _now()`
  atomically into the cache (a `refused` is never written); called by `_probe_account` and by the D4 ping call site
  (`:4055`), which Phase B step 2 amends to call it after `_capability_probe`.
- `_validated_pick(accounts, exclude, *, verbose=False, probe=False)` — the existing body (`:3559-3625`) moves
  unchanged into `_validated_pick_reading(accounts, exclude, *, verbose)`; the wrapper loops: take the reading-validated
  pick; `probe` false or `None` → return it; `_probe_account` → `ok` → return the pick; `inconclusive` → return the
  pick and print one stdout tick line `tick: <email> capability probe inconclusive — picked anyway` (every caller that
  probes; the tick's stdout is its log); `refused` → `_auto_park(email, source="promote", row=<its row>)`, add the
  email to its own exclude set, loop. The four flip-leg callers (`:5717`, `:5737`, `:5832`, `:5878`) pass
  `probe=True`; the advisory caller (`:6683`) does not. The docstring (`:3562-3567`) gains one sentence naming the
  probe, its two windows and the auto-park (spec § Documentation landing sites).
- In `_fleet_flip_leg` (`:5706`), right after the active row resolves (`:5727-5730`) and BEFORE the dead-chain branch
  (`:5736`): when the active account is not already parked (`_is_parked(row.get("weekly_cap"))`, `:6110-6115`, is
  false) and `_probe_account(row["email"], active_slug)` returns `refused`, call `_auto_park(row["email"],
  source="active", row=row)`. Then, when the active account is parked — this tick's refusal or any earlier park, the
  operator's included (D-443: "an ACTIVE parked account is flipped away from on the next tick") — run
  `pick = _validated_pick(accounts, {row["email"]}, probe=True)`. A pick → `_flip_active(slug, ignore_dwell=True,
  kind="refused" if row.get("capability_refused") else "parked")`; on `True` one stdout tick line and one
  `_tick_telegram` naming both accounts; on `False` one stdout line `flip to <slug> withheld (see stderr)` and no
  alert claiming a flip (the dead-chain branch's shape, `:5740-5747`). No pick → one stdout line naming the exclusion
  reasons (`_flip_exclusion_reasons`, `:5752`). Either way `return`. A parked active account is never re-probed (its
  `weekly_cap` reads 0 every tick), and the branch does not depend on a quota reading (the `no quota reading` early
  return at `:5767-5769` would otherwise strand a parked active account that has none).
- In `run_claude` (`:735`): BEFORE each `subprocess.run` (`:765`, `:826`), snapshot the account the call is bound
  to — `cfg = env.get("CLAUDE_CONFIG_DIR")` (`env` is a required parameter, `:736`); when it is set and
  `Path(cfg).resolve()` lies directly inside `_fleet_root().resolve()`, the slug is that directory's name (a session
  bound to `<root>/active` resolves to the pointer's target AT CALL TIME, `:3022-3028`). Resolving after the call
  would name whatever the pointer reached meanwhile — a tick that parks the refused account and flips to a healthy
  one during a long call would get the healthy one parked too. After the result and BEFORE the usage-limit/401
  classification (`:801-804`): when `_capability_verdict(result.returncode, result.stdout or "") == "refused"`, park
  the SNAPSHOT slug's account — its email is the slug's `identity` in `_load_assignments(strict=False)`; then
  `_auto_park(email, source="wrapper")` (which refuses an unknown or `pending-login` identity). Any other case — no
  `CLAUDE_CONFIG_DIR`, the shared `~/.claude`, a dir outside the fleet root, a host with no fleet (the VPS callers,
  `scripts/aro-wake/main.py:543`) — writes one stderr line `capability refused outside the fleet — nothing parked` and
  parks nothing. Then `break`. The result is returned to the caller unchanged.

Steps:
1. **Test first (the highest-risk behaviour, B5)**: write B5 — a fleet of two accounts (`_canonical`, `_pin`,
  `_fleet_creds`, `_point`), the ACTIVE account's probe returning the refusal with no cached verdict → after one
  `_fleet_tick_inner` the pointer names the other account, `parked.json` lists the refused one, the ledger carries one
  `auto-park` row with `source: "active"` and one flip row with `kind: "refused"`. Run it → red (no D6 branch).
2. FIRST add a module-level autouse fixture to `tests/test_claude_fleet.py` that replaces `cr._capability_probe` with a
  stub returning `"ok"` and counting its calls, so none of the file's existing tick tests (92 `_cmd_tick()` /
  `_fleet_tick_inner(` calls) can launch the real `claude` binary once the flip leg probes; the new test file sets its
  own stub per test. Then implement `_probe_trust_s`, `_PROBE_RETRY_S`, `_probe_cache_path`, `_probe_account`,
  `_record_probe` (and its call at the D4 ping site, `:4055`) and the `_fleet_flip_leg` branch. Re-run B5 → green. Add its mirrors: the same fleet with an `ok` cached 1 h ago → zero probe calls on that
  tick; an operator-parked active account with NO quota reading → flipped away with kind `parked` and zero probe
  calls; `_flip_active` withheld (pause marker set) → no Telegram call and the `withheld` tick line.
3. Write B1–B4, then implement the `_validated_pick` split and the four `probe=True` call sites:
   - B1: the top candidate refused, the second healthy → the pick is the second, the first is parked with
     `source: "promote"`, and the row of the first reads `weekly_cap == 0`.
   - B2: an `ok` verdict younger than `ROTATE_PROBE_TRUST_S` → no `claude` call; older → one call.
   - B3: the probe times out → the top candidate is returned and nothing is parked.
   - B4: `_fleet_active_wall_advisory`'s pick and `cr.main(["--switch", <refused slug>])` make zero probe calls, and the
     manual switch still flips (D-443's escape hatch).
4. Write B6, then implement the `run_claude` hook: `env["CLAUDE_CONFIG_DIR"]` naming fleet dir `b` while the pointer
   names `a`, stdout carrying the refusal result → `b`'s identity is parked with `source: "wrapper"` and `a`'s is not,
   the function returns the result unchanged and `capsys` stdout is empty; the same result with `CLAUDE_CONFIG_DIR`
   unset → nothing parked and the stderr line printed; an `is_error: false` result that quotes the code → nothing
   parked. (A no-retry assertion is not used as the red signal: `is_usage_limit` and `is_auth_401` are both already
   false on the refusal text, so the loop breaks without the hook — executed this review.)
   Add the race case: the stubbed `subprocess.run` repoints `<root>/active` from `a` to `b` before returning the
   refusal, with `env["CLAUDE_CONFIG_DIR"] = <root>/active` → `a` is parked and `b` is not.
4a. Add B7, the cache windows: a probe returning `inconclusive` → a second `_probe_account` call within
   `_PROBE_RETRY_S` makes no `claude` call; past it, one. A D4 ping that returned `ok` this tick → D6 makes no probe
   call for that account on the same tick.
5. `cp scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py && cmp scripts/sysadmin/claude_rotate.py
   scripts/aro-wake/claude_rotate.py` → no output, rc 0.
6. **Phase gate**: `.venv/bin/python -m pytest tests/test_claude_rotate_capability_probe.py tests/test_claude_fleet.py
   tests/test_claude_rotate_v2.py tests/test_claude_rotate_capture.py tests/test_mail_addressing.py -q` → every test
   passes; `.venv/bin/python -m mypy scripts/sysadmin/claude_rotate.py --ignore-missing-imports` → no new error.
   Red-on-revert for B1, B5 and B6 in a throwaway worktree (drop `probe=True` at `:5878`; drop the D6 branch; drop the
   wrapper hook) → each named test red, then the worktree removed.
7. `python scripts/enforcement/check_doc_sync.py` → no finding beyond Phase C's declared docs.
8. **`/fabrik-review-scoped`** on Phase B's changed surface — BLOCKING, run to its closing pass confirming zero
   defects; fix and re-run the gate after each fix.
9. Commit Phase B (explicit pathspecs, trailers `Agent-Phase: B`), push.

**Behavior Contract (Phase B):**
- **Given** the ACTIVE account is refused and holds no fresh `ok` verdict, **When** the tick runs, **Then** it is parked and the pointer is flipped away on that same tick with flip kind `refused` (spec § The delta D6)
- **Given** the ACTIVE account holds an `ok` verdict younger than the trust window, **When** the tick runs, **Then** no probe call is made (spec § Cost)
- **Given** the top flip candidate is refused and the next is healthy, **When** the flip leg picks, **Then** the next is picked and the first is parked and walled for the rest of the tick (spec § The delta D2)
- **Given** a candidate's `ok` verdict is younger than `ROTATE_PROBE_TRUST_S`, **When** it is picked, **Then** no probe call is made, and an older verdict makes exactly one (spec § The delta D2)
- **Given** the probe times out, **When** the flip leg picks, **Then** the candidate is picked as today and nothing is parked (spec § Lifecycle)
- **Given** the relief advisory or a manual `--switch`, **When** either runs, **Then** no probe call is made and the manual switch still flips (spec § The delta D2)
- **Given** a session call through `run_claude` bound to a fleet dir returns the refusal result, **When** the wrapper classifies it, **Then** the account of THAT dir is parked (never the pointer's, when they differ), the result is returned unchanged and stdout carries nothing extra (spec § The delta D4b)
- **Given** the refusal reaches `run_claude` with no fleet `CLAUDE_CONFIG_DIR`, **When** the wrapper classifies it, **Then** nothing is parked and one stderr line says so (spec § The delta D4b)
- **Given** an active account already parked — by the operator or an earlier refusal — with no quota reading, **When** the tick runs, **Then** it is flipped away with kind `parked` and is not probed (spec § The delta D6; D-443)
- **Given** the flip away from a parked active account is withheld, **When** the tick runs, **Then** no alert claims a flip and the tick line says `withheld` (spec § The delta D6)
- **Given** a probe returned `inconclusive`, **When** the same account is probed again within `_PROBE_RETRY_S`, **Then** no `claude` call is made (spec § Cost)
- **Given** the pointer moves from `a` to `b` while a wrapper call bound to `<root>/active` is running, **When** that call returns the refusal, **Then** `a` is parked and `b` is not (spec § The delta D4b)
- **Given** the D4 ping probed an account this tick, **When** D6 considers that account, **Then** no second probe call is made (spec § Cost)

## Phase C — docs and Finish

Appetite: 60

**Interfaces — Consumes:** the verdict names, the `auto-park` ledger row and the `refused` flip kind from Phases A and B.

Steps:
1. `docs/workstation/claude-account-rotation.md` § Parking (`:189-202`): one paragraph on the auto-park — when it fires
   (a definitive `oauth_org_not_allowed` refusal on promote, on the active re-check, on the stale-reading ping, or in a
   session call), what it writes (`parked.json`, the `auto-park` ledger row, one Telegram alert), the
   `ROTATE_PROBE_TRUST_S` window, and that only `--unpark` restores it. The `--status` section's flip-kind list
   (`trip / perishable / repair / dead-chain / switch`, `:213`) gains `refused` and `parked`; one sentence says an ACTIVE
   parked account is now flipped away even with no quota reading.
2. `python3 scripts/render_doc_script_links.py --check` and `python3 scripts/enforcement/check_doc_sync.py` → green.
3. **Finish — the heavy `/fabrik-review`** over the whole-plan diff (the plan's commits vs its base commit): the D7 floor
   — file partition, a Sonnet and a Haiku finder per slice (D-344), the orchestrator executing every refutation,
   stamped with `command_run.py dispatch` first — to its closing pass confirming zero defects; receipt
   `docs/development/reviews/2026-10-06-plan-2-rotation-capability-probe-review.md` embedding the verbatim
   `final_gate.py --json` success. Then `/fabrik-docs-review` over the edited doc.
4. The full gate: `python scripts/final_gate.py --check --json` → `"status": "success"` (necessary, not sufficient —
   the Evidence below is the design proof), and `python scripts/enforcement/check_convergence.py` → exit 0.
5. Commit Phase C (explicit pathspecs; `CHANGELOG.md`, `docs/STRATEGIC_BACKLOG.md` (spec U3's backlog row) via the
   private-index recipe; trailers `Agent-Phase: C`), push; `merge_request.py request --review <receipt> --item
   W-f8bfe7eb` and the `SendMessage` lines it prints.

**Behavior Contract (Phase C):**
- **Given** an operator reading the rotation doc after an auto-park, **When** they look up the alert's account, **Then** § Parking states what parked it and that `--unpark <email>` restores it (spec § Personas, the 3-step loop)

## File Scope (owned paths)

- scripts/sysadmin/claude_rotate.py
- scripts/aro-wake/claude_rotate.py
- tests/test_claude_rotate_capability_probe.py
- tests/test_claude_fleet.py
- docs/workstation/claude-account-rotation.md
- docs/development/reviews/2026-10-06-plan-2-rotation-capability-probe-review.md

## Evidence

**Phase A.** The failure shape of `claude -p --output-format json`, captured this run with the exact probe argv against
an EMPTY config dir (no account, so no inference and no quota spent; Claude Code 2.1.280):
```text
$ CLAUDE_CONFIG_DIR=<scratch>/probe-cfg … claude -p ok --output-format json --max-turns 1 --tools "" < /dev/null
{… "terminal_reason":"api_error", … "is_error":true,"num_turns":1,"subtype":"success","api_error_status":null,"result":"Not logged in · Please run /login","type":"result", …}
rc=1
```
So the flags parse (the CLI returned a result object, not an argument error, before any API call), a failure exits
non-zero with `is_error: true`, and `subtype` reads `success` on a failure (spec U1 resolved: never key on it). The
healthy shape, captured during this plan's review with ONE real call (a one-word turn, no tools, on the session's own
account — the `result` text omitted here because it echoes private session context, which is also why D1 never logs
it):
```text
$ claude -p ok --output-format json --max-turns 1 --tools "" < /dev/null | <keys only>
{'type': 'result', 'is_error': False, 'subtype': 'success', 'api_error_status': None, 'terminal_reason': 'completed', 'num_turns': 1, 'result': <omitted>}
rc=0
```
So `--max-turns 1 --tools ""` completes a healthy turn and D1 reads it `ok`: the D4 ping keeps today's `ok` path on a
healthy account. The function being replaced and its one caller:
```text
scripts/sysadmin/claude_rotate.py:4055:                if _keepalive_ping(with_creds[0]["dir"]):
scripts/sysadmin/claude_rotate.py:4060:                    row["ping_failed"] = True
scripts/sysadmin/claude_rotate.py:7129:def _keepalive_ping(cfg_dir: Path) -> bool:
scripts/sysadmin/claude_rotate.py:1628:def _assignments_lock_fd() -> int:
scripts/sysadmin/claude_rotate.py:3873:def _cmd_park(email: str, park: bool) -> int:
```
`_cmd_park` reads (`:3885`) and writes (`:3891`) `parked.json` with no lock; it is the only writer of the file in
`scripts/` (`command grep -rn "parked.json" scripts/` → `:3838`, `:3884`, the `:4317` label, and the twin).

**Phase B.** The seams the wiring lands in:
```text
scripts/sysadmin/claude_rotate.py:3559:def _validated_pick(
scripts/sysadmin/claude_rotate.py:5717:        pick = _validated_pick(accounts, set())
scripts/sysadmin/claude_rotate.py:5737:        pick = _validated_pick(accounts, {row["email"]})
scripts/sysadmin/claude_rotate.py:5832:                    cand = _validated_pick(accounts, excluded, verbose=True)
scripts/sysadmin/claude_rotate.py:5878:    pick = _validated_pick(accounts, {row["email"]}, verbose=True)
scripts/sysadmin/claude_rotate.py:6683:    if not _switch_paused() and _validated_pick(accounts, {row["email"]}) is not None:
scripts/sysadmin/claude_rotate.py:5790:    cap_trip = cap is not None and weekly_trip
scripts/sysadmin/claude_rotate.py:6836:    accounts, pending = _fleet_account_rows(dirs, allow_pings=True)
scripts/sysadmin/claude_rotate.py:6837:    _fleet_flip_leg(dirs, accounts, threshold)
scripts/sysadmin/claude_rotate.py:542:        _TLS.withheld_reason = _WITHHELD_FLEET
scripts/sysadmin/claude_rotate.py:802:        is_401 = is_auth_401(combined)
```
`_fleet_flip_leg` returns with no decision when the active row has no quota reading (`:5767-5769`), which is why D6 is
its own branch ahead of the trip arithmetic rather than a forced `weekly_cap`. The picker reads parked state from the
row's `weekly_cap` (`_is_parked`, `:6110-6115`; used at `:3509`), set when the rows are built — why `_auto_park` also
walls the in-memory row.

**Phase C.** The doc section edited: `docs/workstation/claude-account-rotation.md:189` (`### Parking — taking an
account out of service`); the twin pin: `tests/test_mail_addressing.py:228`.

## Self-audit

- Grounding passes: the spec's research and three-judge panel; this run's three native seats (Opus: the `run_claude`
  wrapper; Sonnet: the pick and tick seams; Sonnet: parking, ledger, Telegram and the test harnesses), every claim
  they returned re-read by the orchestrator at 99b111443 (two drifted anchors corrected: `cap_trip` is `:5790`, the
  seat said `:5778`); the probe argv executed live (Evidence, Phase A).
- Findings that changed the design: (1) `run_claude` cannot rotate on a fleet host, so D4b parks and leaves the flip to
  the tick (I6; the spec was amended in this plan's review); (2) the wrapper's existing text classifier would park on a quoted code,
  so `refused` requires `is_error` true; (3) a mid-tick park must also wall the in-memory row; (4) the D6 flip must not
  sit behind the no-reading early return; (5) `_keepalive_ping`'s two pinning tests are a named mirror cost (Phase A
  step 2).
- (a) Coverage: D1 → A1–A4; D3 → A5 and A8; D4 → A7; D5 → A6; D2 → B1–B4 and B7 (the cache windows); D6 → B5 and
  its three mirrors (cached `ok`, parked with no reading, withheld flip); D4b → B6; Validation's twin row → every phase's `cp`/`cmp` step and `tests/test_mail_addressing.py:228`;
  the documentation landing sites → Phase C step 1 (the rotation doc), Phase B's `_validated_pick` Interface (its
  docstring), each phase's commit (`CHANGELOG.md`) and D-614 plus the approval row (the D-rows); U3's backlog row →
  Phase C step 5. No gap.
- (b) Signatures: Phase B consumes `_capability_probe`, `_capability_verdict` and `_auto_park` with the exact
  parameters Phase A's Interfaces name; `source` values used in B (`promote`, `active`, `wrapper`) and A (`ping`) are the
  four the Interface lists; the flip kinds `refused` and `parked` are named once in B and documented in C;
  `_parked_update`'s `repair` keyword is passed by both of its callers (`_auto_park` False, `_cmd_park` True);
  `_record_probe` is the one cache writer, called by `_probe_account` and the D4 ping site.
- Fixed point: not yet — `/fabrik-plan-review` grades it.

## Residual unknowns

- **Resolved — U1** (`subtype` spellings): measured this run; D1 never reads it.
- **Resolved — the probe's flags and healthy shape**: `--max-turns` and `--tools ""` are absent from `claude --help`
  (2.1.280) but parse — the empty-dir run returned a result object, not an argument error — and a real healthy call
  returned `is_error: false`, `terminal_reason: "completed"` at rc 0 (Evidence, Phase A).
- **Open — U2** (does every refusal carry `api_error_status: 403`?): resolution: D1 does not require it; A1's framing
  cases include `null`; the ledger records the observed status so the first real refusal settles it.
- **Open — R4, the approval question** carried from the judge split: is a ≤6 h detection window for a refusal that first
  appears on the ACTIVE account acceptable? Resolution: `/fabrik-plan-review`'s approval gate puts it to the panel
  standing in for the operator (D-613). D4b narrows the window only for calls that pass through `run_claude` bound to a
  fleet dir — the script's own CLI passthrough; interactive Claude Code sessions on the box never pass through it, and
  the VPS callers have no fleet — so for interactive work the window is the full trust window.
- **Open — U3** (other credentials-not-capability probes on the box): resolution: the `docs/STRATEGIC_BACKLOG.md` row
  in Phase C step 5.
- **Open — real-refusal end-to-end**: no account is refusing today, so the refused path is exercised against the
  documented shape (G1, G3) and the incident's text, never a live 403. Resolution: the ledger's `auto-park` row and the
  Telegram alert are the live proof on the first real refusal; the operator un-parks after confirming.

## Pass Ledger

Joint loop over this plan and its `Size: small` spec (md5 pairs: plan · spec).

| Pass | seats · axes re-checked | counters | method | md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (plan § Global Constraints, Phase A, Phase B; spec § The delta, § Validation, § Constraints digest) + sonnet×1 (every other section of both) · all axes; the monolith and spec flip gates run on flipped copies in a throwaway worktree | found: 15, new: 15, confirmed: 14, fixed: 14, unexecuted: 0, edits: 32 | method: citation — full pass; every candidate executed by the orchestrator (the four `ignore_dwell=True` flips, the assignments lock site `:3692-3694`, `is_usage_limit`/`is_auth_401` on the refusal text, `_is_parked` at `:6110-6115`, one real healthy probe call); confirmed: D4b parked the pointer's account not the answering one, the dwell bounded nothing and an inconclusive probe re-ran every tick, the unlocked-write citation said the opposite, an automated park overwrote a broken `parked.json`, an already-parked active account was re-probed and its withheld flip unspecified, three of five spellings, the "reached the API" contradiction and the uncaptured healthy shape, B6's vacuous no-retry assertion, D2's logging mismatch, R4 overstating D4b's reach, the `_validated_pick` docstring landing site, the spec/plan size mismatch, the `_is_parked` range, the digest missing `core/40-documentation.md` (flip gate) | plan 2957ecae · spec df9aaf05 → plan 67dcaa0b · spec be9ad375 |
| Pass 2 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-1 fix hunks + one hop | found: 8, new: 8, confirmed: 5, fixed: 5, unexecuted: 0, edits: 10 | method: re-derivation — A 14/17 and B 12/15 re-executed (the 92 tick calls in `tests/test_claude_fleet.py`, `_known_account_emails` at `:3861-3870`, the two `subprocess.run` sites `:765`/`:826`, `ROTATE_REFRESH_MAX_PER_RUN` `:5564`, the pin-minus-ledger hash, D-613 on `origin/master`); confirmed, all in round-1 hunks (own-fix: round 1): the existing fleet tick tests would launch the real `claude` once the flip leg probes, the wrapper resolved the answering account after the call so a mid-call flip could park the healthy successor, the D4 ping was outside the cache and the cost sentence, `_auto_park` did not lower-case its email, the `_known_account_emails` span | plan d06380af · spec be9ad375 → plan 39c89b8e · spec dd0a5661 |

## Residual

| Id | Verdict |
|---|---|
| A5 | RECORDED — measured (the pointer-repair fallback `_freshest_credentialed_slug`, `:5718`, can name a just-parked account when every candidate is parked; a missing pointer and a pointer on a refused account both fail every session, and each auto-park has already alerted the operator, so the fallback changes no outcome) |
| B2-1 | REFUTED (the Pass 1 end hash is the plan with its own ledger sections deleted, per the in-plan-ledger anti-cheat rule: `awk` deleting `## Pass Ledger`…`## Coverage Checklist` from the pass-2 pin hashes to `67dcaa0b94727298f888bd9b72db5e61`) |
| B2-2 | REFUTED (`git show origin/master:docs/DECISIONS.md` carries `| D-613 | 2026-10-06 | operator ruling 2026-10-06 …` — the design-approval panel ruling; this branch predates its merge) |
| A2-1b | RECORDED — measured (one hop out: the three round-0 `probe=True` callers share the test-isolation gap; closed by the same autouse fixture in Phase B step 2) |

## Coverage Checklist

| Class | Status |
|---|---|
| Hunt: `scripts/sysadmin/claude_rotate.py` + its twin — every changed function, its callers | UNCHECKED |
| Hunt: `tests/test_claude_rotate_capability_probe.py`, `tests/test_claude_fleet.py` — every new or repointed test | UNCHECKED |
| Hunt: `docs/workstation/claude-account-rotation.md` — every changed claim against the code | UNCHECKED |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | UNCHECKED |
| Recurrence: boundary/sentinel/prefix — a prefix-vs-exact match | UNCHECKED |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | UNCHECKED |
| Recurrence: denominator on every count — bounded searches state their bound | UNCHECKED |
| Recurrence: cost/quota accounting — pool units scored, native seats counted, a limit at its edges | UNCHECKED |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | UNCHECKED |

Rubric invocation (verbatim output — the gate reads the generated header):

```text
$ python scripts/review_rubric.py --changed scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py tests/test_claude_rotate_capability_probe.py tests/test_claude_fleet.py docs/workstation/claude-account-rotation.md
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
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
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

### core/40-documentation.md  (hit: docs/workstation/claude-account-rotation.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_claude_fleet.py, tests/test_claude_rotate_capability_probe.py)
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

# promote-to-check_*: 35 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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
- `.` `scripts/` `mypy --explicit-package-bases worker` `server/` `mypy src` `server/`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `30-ops.md`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
- `scripts/enforcement/_doc_registry.py::PROJECT_DOCS` `/fabrik-plan-after-chat` `Docs:`
```
