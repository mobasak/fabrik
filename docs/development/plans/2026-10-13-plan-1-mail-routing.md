# Plan — route hub and fabrik-lib mail to the owning agent (W-931b6837)

Status: DRAFT
Profile: small
**Owner:** infra

Spec: `docs/superpowers/specs/2026-10-13-mail-routing-design.md` (DRAFT at dfc5af664, `Size: small`).
`/fabrik-plan-review` grades its sections together with this plan and flips both.

Decisions: D-815 (seams), D-818 (approach D).

Estimated diff ≈330 lines across 4 code files, tests excluded:
- `scripts/mail.py` ≈170;
- `.claude/hooks/mail_notify.py` ≈25;
- `scripts/sysadmin/mail_escalate.py` ≈70;
- `scripts/enforcement/check_beat_owners.py` ≈65, new.

The data file `.fabrik/beat-owners.json` is also new.

## What this plan is

Three inline phases the orchestrator codes itself in the main checkout; no coder is dispatched:

- **A — the map and the send path:** the map, the loader, the validator, the trail and send-time addressing and advisory (spec D1, D2, D3).
- **B — read, claim, escalation:** markers in `list`, `claim` and the notify hook; the escalation cron's owner naming and Haiku tie-break; `route-report` (spec D4, D5, D6).
- **C — fabrik-lib request, docs, Finish:** the request to the fabrik-lib sentinel (spec D7) and the docs (spec D8 and § Documentation landing sites). Then the Finish review: the whole-plan `/fabrik-review` and ONE commit. `mail.py` and `mail_notify.py` are governance-sync paths, so everything lands together after it.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the `/fabrik-execute-plan` D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I17 (18 rows: 16 IN, 2 OUT-OF-SCOPE with destinations) | IN | Phases A–C, per the spec rows |
| I2 | *"Plan it as `Profile: small`; its /fabrik-plan-review grades the spec's sections with the plan"* (this run's brief) | IN | this header; `/fabrik-plan-review` |
| I3 | *"Governance-sync paths (mail.py, mail_notify.py) → one commit after the full /fabrik-review at execution"* | IN | Phase C steps 5–7 |
| I4 | *"Measure U3 (mail_notify latency) during planning"* | IN | § Evidence (Phase B); spec U3 resolved |
| I5 | *"D3a, behind a switch until kaizen's pilot"* | IN | Phase A Interfaces (`FABRIK_MAIL_AUTO_ADDRESS`) |

## What we already agreed (citations, not restatement)

- Goal and personas: `spec § Goal`, `spec § Personas`; why: `spec § Why this exists`.
- What exists: `spec § What exists today (grounded)`.
- The delta D1–D8: `spec § The delta`; contract deltas and their mirrors: `spec § Contract deltas`.
- Approach D (judge panel 3–0, round 2; D-818): `spec § Chosen approach`; rejected A, B, C and seven others: `spec § Rejected alternatives`.
- Seams: D-815.
- Lifecycle: `spec § Lifecycle`; open unknowns: `spec § Open unknowns`.
- Validation V1–V9: `spec § Validation`; decisions: `spec § Decisions taken`.
- The approval row is minted by `/fabrik-plan-review` at its gate: a `Size: small` spec is approved there, not here.

## Global Constraints (every phase inherits these)

- **No message file is rewritten except by `route()`**, and `route()` keeps its inbox-only, `os.replace` contract (`scripts/mail.py:1756`). The send path writes the `routed:` line into the NEW message before delivery. The tie-break writes only its sidecar.
- **Fail-open on every read surface.**
  - A missing, unreadable or invalid `.fabrik/beat-owners.json` makes `owner_of` return `None`.
  - `list`, `claim` and the hook then behave exactly as today, and `send` refuses unaddressed hub mail as today.
  - `mail_notify.py` stays exit-0 on any exception, and its map lookup stops at a 50 ms budget measured with `time.monotonic()`.
- **Deterministic in fleet-synced files.**
  - `mail.py` and `mail_notify.py` call no model and spawn no process for routing.
  - The only `claude -p` call is in `scripts/sysadmin/mail_escalate.py`, which is hub-only and not in `scripts/fabrik_synced_manifest.py`.
- **D3a is switched, D3b is not.**
  - Automatic addressing of an unaddressed hub send runs only when `FABRIK_MAIL_AUTO_ADDRESS=1` (default off). It is off until kaizen's pilot meets the spec's adoption bar (`spec § Lifecycle`).
  - The advisory and every read marker are on from day one.
  - The new env var is documented in `.env.example` and `docs/CONFIGURATION.md` (Doc Sync Matrix).
- **The fabrik-lib leg is off in this plan.** `send` gains the code path behind `FABRIK_MAIL_LIB_ADDRESS=1` (default off). The hub never edits fabrik-lib; Phase C sends the request.
- **No new dependency** (`core/10-python.md:30`): stdlib `json`, `fnmatch`, `subprocess` only. Trail timestamps use `datetime.now(UTC)` (`core/10-python.md:220`). No log file (`core/10-python.md:294`).
- **The tie-break** is one sequential `claude -p` per qualifying mail, with a 60 s timeout and a per-run cap of 10 calls. It is never a fan-out (`core/62-using-subagents.md:103`) and never OpenRouter (`core/62-using-subagents.md:100`).
- **Tests:**
  - watched-fail-first for every behaviour (`core/45-testing-strategy.md:22`);
  - fixtures build a scratch mail root (`FABRIK_MAIL_ROOT` as `tests/test_mail_addressing.py` does) and a scratch map;
  - `claude` is stubbed with a fake on `PATH`, never called live;
  - red-on-revert runs in a throwaway worktree (`git worktree add --detach <scratch>/probe HEAD`), never in the shared checkout.
- **Seats:** they never mutate git state, never read `~/.claude*`, and never write under `/opt`.
- **Execution discipline (native seats only, D-181):**
  - Every phase ends with `/fabrik-review-scoped` on its surface (the floor of three native seats on different angles, stamped with `command_run.py dispatch`), and does not hand on until its closing pass confirms zero defects.
  - The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku finder per slice (D-344), plus the D7 Opus floor once. The orchestrator executes every refutation.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | no deps-file edit; UTC-aware datetimes; no file logging | `core/10-python.md:30`, `:220`, `:294` |
| `.windsurf/rules/core/45-testing-strategy.md` | one test per behaviour; watched-fail-first | `core/45-testing-strategy.md:20-22` |
| `.windsurf/rules/core/62-using-subagents.md` | no `claude -p` fan-out; no OpenRouter | `core/62-using-subagents.md:100`, `:103` |
| `.windsurf/rules/core/65-rag-search.md` | `claude -p` for a low-volume classification step | `core/65-rag-search.md:108` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | config via env: the two switches are env vars with defaults | `core/35-security-auth.md:267` |
| `.windsurf/rules/core/25-data-postgres.md`, `core/30-ops.md` (FLOOR) | not engaged: no database, no service | `spec § Shape / infra implications` |
| `fabrik-lib` | the module map is read in place, never vendored | `spec § fabrik-lib verdict` |
| D-815, D-818 | the seams; the approach | `docs/DECISIONS.md` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Dependencies live in pyproject.toml + uv.lock. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:30` |
| datetime.now(UTC), never datetime.utcnow() | `.windsurf/rules/core/10-python.md:220` |
| any in-app log rotation/retention/cleanup | `.windsurf/rules/core/10-python.md:294` |
| an operator-facing or batch step (a judge run, a one-off classification), never a per-request path | `.windsurf/rules/core/65-rag-search.md:108` |
| a fan-out of claude -p processes from the orchestrator | `.windsurf/rules/core/62-using-subagents.md:103` |
| a direct OpenRouter HTTP call — a dispatch still spends | `.windsurf/rules/core/62-using-subagents.md:100` |

## Phase A — the map and the send path

Appetite: 150

**Interfaces — Produces** (spec D1, D2, D3):
- **`.fabrik/beat-owners.json`**, new.
  - Shape: `{"version": 1, "rules": [{"paths": [...], "topics": [...], "owner": "<beat>", "source": "<D-id or charter line>"}], "floater": "intel"}`.
  - Contents: D-815's seams (1)–(5) and kaizen's § A path lists (01M4TCHD5Y), in that order, the broad `scripts/**` → infra rule first so later specific rules win (last match wins).
- **`owner_of(text: str, mailbox: str = "fabrik") -> tuple[str | None, list[str], str]`** in `scripts/mail.py`. It returns `(owner, owners_seen, map_version)`.
  - Cited paths are backticked tokens and `path:line` tokens (the `:line` stripped) that exist under the mailbox's repo root (`/opt/fabrik` for `fabrik`).
  - Each cited path is matched with `fnmatch` against every rule; the LAST matching rule wins for that path.
  - `owner` is set when every cited path maps to one owner. Otherwise it is `None` with `owners_seen` listing them.
  - No path: topic lines match case-insensitively as whole words, and exactly one owner must match.
  - A missing or invalid map returns `(None, [], "")`.
  - For `mailbox == "fabrik-lib"`, the map is `/opt/fabrik-lib/.fabrik/module-owners.json`, and cited module names are matched against its `owners` lists.
- **`route(msg_id, to_agent, repo=None, *, by=None, reason=None)`.** It appends `routed: <UTC ISO> · <by or $CLAUDE_AGENT or -> · <old or -> → <new or -> · <reason or (no reason)>` after the existing headers and keeps every earlier `routed:` line. The `agent:` line is still replaced.
- **CLI `mail.py route <id> --to-agent X --reason "<text>"`.** `--reason` is required when the message already has an `agent:` header (CLI-level only, so library callers and the existing tests keep working).
- **`send(...)`, hub-bound:**
  - **(D3a, `FABRIK_MAIL_AUTO_ADDRESS=1`):** no `--to-agent`, no `--broadcast`, no inherited thread address, and `owner_of` returns one owner → `agent: <owner>`. The message carries `routed: … · map · - → <owner> · ownership map (<rule source>)`, and stderr shows `addressed to <owner> by the ownership map`. Otherwise, today's refusal at `scripts/mail.py:1079-1090`, its beat list generated from the map's owners.
  - **(D3b):** an explicit `--to-agent` that differs from a single map owner prints `advisory: the ownership map names <owner> for <path> (<source>); delivered to <to-agent> as addressed` to stderr.
  - **(fabrik-lib, `FABRIK_MAIL_LIB_ADDRESS=1`):** an unaddressed send to `fabrik-lib` whose cited modules have one owner gets that owner's `agent:` and a `routed:` line.
- **`scripts/enforcement/check_beat_owners.py`**, new, registered in `scripts/final_gate.py` beside `check_spec_db_match` (`:2240-2247`).
  - Exit 1 on: an owner outside `mail.HUB_BEATS`, a rule missing `owner`/`source`, or a `paths` pattern matching no tracked file (`git ls-files`).
  - Advisory line: tracked paths no rule owns, with the count and its denominator.
  - Self-skips outside the hub (no map file).

**Consumes:** `HUB_BEATS` (`scripts/mail.py:543`).

**Mirror (named):**
- `tests/test_mail_addressing.py`'s refusal tests (unaddressed hub send) still pass with the switch off.
- `route` callers: only `scripts/mail.py` itself and the tests. `mail_escalate.py:322` prints the CLI line in prose, which is updated to include `--reason`.

**Steps:**

1. **Write the failing tests first.** Add rows A1–A5 to a new `tests/test_mail_routing.py`, reusing the `env` fixture shape from `tests/test_mail_addressing.py`. Run them and confirm each fails on its own assertion.
2. **Write `.fabrik/beat-owners.json`.** Run `python3 scripts/enforcement/check_beat_owners.py` → exit 0, and record the unowned-path count.
3. **Implement** `owner_of`, the trail, the CLI `--reason`, the send paths, the generated refusal list and the validator, plus its final_gate registration.
4. **Green:** `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_mail_routing.py tests/test_mail_addressing.py tests/test_mail.py tests/test_mail_structure.py` → all pass.
5. **Red on revert**, in a throwaway worktree:
   - drop last-match-wins (first match) → A2 fails;
   - drop the switch check → A3's off case fails;
   - drop the trail append (overwrite) → A1 fails;
   - let `owner_of` raise on a bad map → A2's invalid-map case fails;
   - drop the advisory → A4 fails.
6. **`/fabrik-review-scoped`** on Phase A's surface, run to a closing pass confirming 0. This is BLOCKING before Phase B. Phase A is not committed alone.

### Behavior Contract — Phase A

- **A1** — **Given** an addressed inbox message, **When** `route` moves it twice with reasons, **Then** both `routed:` lines are present in order, `agent:` is the last target, and the CLI refuses a third move without `--reason`.
- **A2** — **Given** a scratch map with a broad and a later specific rule, **When** `owner_of` reads a body citing a path under both, a body citing two owners' paths, a body citing nothing, and a body under a missing or invalid map, **Then** it returns the specific owner, `None` with both owners, `None`, and `(None, [], "")` respectively.
- **A3** — **Given** an unaddressed hub send citing one owner's path, **When** `FABRIK_MAIL_AUTO_ADDRESS` is unset and when it is `1`, **Then** the first is refused with the generated beat list, and the second is delivered to that owner with the `routed: … map` line and the stderr note. A body the map cannot place is refused either way.
- **A4** — **Given** a send to `--to-agent intel` citing an infra-owned path, **When** it runs, **Then** it is delivered to intel and stderr carries the advisory naming infra.
- **A5** — **Given** the shipped map and a scratch map with an unknown owner and a dead pattern, **When** `check_beat_owners.py` runs, **Then** the shipped map exits 0 with its unowned count, and the scratch map exits 1 naming both defects.

## Phase B — read, claim, escalation, report

Appetite: 120

**Interfaces — Produces** (spec D4, D5, D6):
- **`list_msgs(repo, agent=None)`** (`scripts/mail.py:2245`). Each row gains `map_owner` and `map_note` (`→ map: <owner>`, `→ unmapped`, or `""` when the map agrees). The tie-break sidecar's suggestion appears as `→ haiku: <owner>` when present. `--agent X` also returns rows whose `map_owner` is X, marked `(map)`.
- **`claim(msg_id, repo)`** (`:1725`). Before the rename, when `owner_of` names a single owner different from `$CLAUDE_AGENT`, it prints the advisory to stderr. The rename, its return and its lock are unchanged.
- **`.claude/hooks/mail_notify.py`.** Each summary line gains the `→ map:` marker.
  - The lookup imports `owner_of` only for the `fabrik` mailbox, and only when `/opt/fabrik/.fabrik/beat-owners.json` exists.
  - It stops once 50 ms have elapsed (`time.monotonic()`), printing the remaining lines unmarked.
  - It sits under the hook's existing broad `except` (`:146-175`).
- **`mail.py route-report --days N`.** It reads the inbox and archive `routed:` trails and prints, with denominators:
  - the share of messages whose map owner differed from the first addressee;
  - of those, the share re-routed to the map owner, the share re-routed elsewhere, and the share kept;
  - the sender-address re-route rate.
- **`scripts/sysadmin/mail_escalate.py`:**
  - The digest line names `map: <owner>` beside the addressee.
  - For unclaimed `fabrik` inbox mail older than the escalation threshold with `owner_of` → no cited mapped path and no sidecar yet, it makes one `claude -p --model haiku` call. The prompt is the map JSON plus the message body and asks for one word.
  - Output is validated against `HUB_BEATS ∪ {none}`, and anything else reads `none`.
  - The result goes to `/opt/fabrik-mail/fabrik/.routing/<id>.json` as `{"suggested", "by": "haiku", "map_version", "at"}`, at most 10 calls per run, each with a 60 s timeout.
  - The message id comes from the file name only.

**Consumes:** `owner_of`, the map, and the trail line format from Phase A.

**Mirror (named):**
- `tests/test_mail_notify.py` and `tests/test_mail_escalate.py` pin the current output lines; they are updated in this phase with the new markers.
- `list --agent` row counts in `tests/test_mail_who.py` and `tests/test_mail_items.py` are re-checked.

**Steps:**

1. Write the failing tests first (rows B1–B5): the `claude` stub is a script on `PATH` printing a fixed word (`infra`, `banana`, or sleeping past the timeout).
2. Implement per the Interfaces.
3. **Green:** `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_mail_routing.py tests/test_mail_notify.py tests/test_mail_escalate.py tests/test_mail_who.py tests/test_mail_items.py tests/test_mail.py` → all pass.
4. **Measure:** time the hook 20 times on the live inbox with the map present; record the median beside the U3 baseline in § Evidence. A median above baseline + 50 ms is a stop and a fix before step 5.
5. **Red on revert**, in a throwaway worktree:
   - drop the time cap → B3's slow-map case fails;
   - accept unvalidated tie-break output → B4's `banana` case fails;
   - write the suggestion into the message file → B4's md5 assertion fails;
   - drop the `--agent` map rows → B1 fails.
6. **`/fabrik-review-scoped`** on Phase B's surface, run to a closing pass confirming 0. This is BLOCKING before Phase C.

### Behavior Contract — Phase B

- **B1** — **Given** an inbox with one agreeing, one mis-addressed and one path-less message, **When** `list` and `list --agent infra` run, **Then** the markers read `""`, `→ map: infra` and `→ unmapped`, and infra's list includes the mis-addressed one marked `(map)`.
- **B2** — **Given** a mis-addressed message, **When** `claim` runs with `CLAUDE_AGENT=intel`, **Then** stderr carries the advisory, the message is claimed, and no inbox file changes bytes before the rename.
- **B3** — **Given** the hook run under the `fabrik` mailbox, **When** the map exists, is invalid, or its lookup is made to sleep past 50 ms, **Then** it prints markers, prints none, or prints the banner unmarked, and exits 0 in every case.
- **B4** — **Given** a stale path-less unclaimed message and stubbed `claude` outputs `infra`, `banana` and a timeout, **When** the escalation tie-break runs, **Then** the sidecar holds `infra`, `none` and `none`, each with `map_version`; the message file's md5 is unchanged; a second run makes no new call; and at most 10 calls happen in one run.
- **B5** — **Given** a fixture archive whose trails hold known re-routes, **When** `route-report --days 30` runs, **Then** it prints each rate with its numerator and denominator.

## Phase C — fabrik-lib request, docs, Finish

Appetite: 90

**Interfaces — Produces** (spec D7, D8, § Documentation landing sites):
- **A request mail** to `fabrik-lib` (`--to-agent fabrik-lib-sentinel`) carrying:
  - the rule (D-815);
  - kaizen's numbers (01M4TCHSPX);
  - the two switches and what the hub turns on after the sentinel records its agreement;
  - the asks: re-vendor `mail.py`, and validate `--to-agent` against its three-name roster.
- **Docs:**
  - `docs/reference/fabrik-mail.md` § Routing: the map, precedence, automatic addressing and its switch, the trail, markers, the tie-break sidecar, `route-report`, and the measure;
  - `docs/workstation/hooks-index.md`: the `mail_notify.py` row;
  - `docs/workstation/fabrik-mail.md`: the escalation cron's tie-break step (the script's `AFTER-EDIT` names it);
  - `.env.example` and `docs/CONFIGURATION.md`: `FABRIK_MAIL_AUTO_ADDRESS` and `FABRIK_MAIL_LIB_ADDRESS`;
  - `INDEX.md`: rows for the map, the validator and the test file;
  - `CHANGELOG.md`.

**Steps:**

1. Write the docs above. Run `python3 scripts/enforcement/check_doc_sync.py` → exit 0, and `python3 scripts/render_doc_script_links.py --check` → exit 0.
2. Send the fabrik-lib request (`mail.py send --to fabrik-lib --to-agent fabrik-lib-sentinel --kind request`).
3. **`/fabrik-review-scoped`** on Phase C's docs, run to a closing pass confirming 0.
4. **Finish — the whole-plan `/fabrik-review`** (the D7 floor: ≥1 Opus authoritative seat plus Sonnet and Haiku finders per slice) over Phases A–C, with its receipt under `docs/development/reviews/`. Run until `Status: CONVERGED`.
5. Gate: `.venv/bin/python scripts/final_gate.py --check --json` → `status: "success"` with the review receipt staged.
6. **ONE commit** with explicit pathspecs and trailers, CHANGELOG, and the work items closed. Then push. The post-commit governance sync distributes `mail.py` and `mail_notify.py`.
7. Reply to kaizen with the commit, ask for the pilot rerun against the shipped map (the D3a switch criterion), and close W-931b6837.

### Behavior Contract — Phase C

- **C1** — **Given** the committed tree, **When** the governance sync runs, **Then** a synced project's `mail.py send` to the hub with an infra-owned citation addressed to intel prints the advisory. Checked in one project after the sync, read-only.

## File Scope (owned paths)

- scripts/mail.py
- .claude/hooks/mail_notify.py
- scripts/sysadmin/mail_escalate.py
- scripts/enforcement/check_beat_owners.py
- scripts/final_gate.py
- .fabrik/beat-owners.json
- tests/test_mail_routing.py
- tests/test_mail_notify.py
- tests/test_mail_escalate.py
- tests/test_mail_who.py
- tests/test_mail_items.py
- docs/reference/fabrik-mail.md
- docs/workstation/fabrik-mail.md
- docs/workstation/hooks-index.md
- docs/CONFIGURATION.md
- .env.example
- docs/superpowers/specs/2026-10-13-mail-routing-design.md
- docs/development/reviews/2026-10-13-plan-1-mail-routing-review.md

## Evidence

**Phase A.** The anchors the delta edits, at dfc5af664:
```text
scripts/mail.py:543:HUB_BEATS = ("infra", "fleet", "intel", "kaizen")
scripts/mail.py:886:def send(
scripts/mail.py:1079:        if not to_agent and not broadcast and not is_thread_reply:
scripts/mail.py:1756:def route(msg_id: str, to_agent: str, repo: str | None = None) -> Path:
scripts/final_gate.py:2242:                "scripts/enforcement/check_spec_db_match.py",
```
`route` has no caller outside `scripts/mail.py` and the tests:
```text
$ grep -rn "mail.py route\|mail\.route(\| route(" scripts/*.py scripts/sysadmin/*.py .claude/hooks/*.py commands/_sources/*.md | grep -v '^scripts/mail.py'
scripts/sysadmin/claude_broker.py:38:    def route(self, kind: str, *, caller: str | None = None) -> str: ...
scripts/sysadmin/mail_escalate.py:322:        "owner, or `mail.py route <id> --repo <repo> --to-agent infra|fleet|intel`. Never sweep.\n"
scripts/sysadmin/quota_governor.py:141:    def route(self, kind: str, *, caller: str | None = None) -> str:
```
(`claude_broker` and `quota_governor` define an unrelated `route` method; `mail_escalate.py:322` is prose.)

**Phase B.** U3 baseline, measured 2026-10-13 over the live `fabrik` inbox (47 messages): five runs of `.claude/hooks/mail_notify.py` with a UserPromptSubmit payload, wall seconds including interpreter start-up.
```text
0.08
0.03
0.04
0.04
0.04
```
The anchors:
```text
scripts/mail.py:1725:def claim(msg_id: str, repo: str) -> Path:
scripts/mail.py:2245:def list_msgs(repo: str, agent: str | None = None) -> list[dict]:
scripts/sysadmin/mail_escalate.py:2:# AFTER-EDIT: docs/workstation/fabrik-mail.md, docs/reference/fabrik-mail.md | tests/test_mail_escalate.py
.claude/hooks/mail_notify.py:29:_FLOOD_CAP = 10  # inject at most this many summaries
```

**Phase C.** fabrik-lib's map, read in place:
```text
$ python3 -c "import json;d=json.load(open('/opt/fabrik-lib/.fabrik/module-owners.json'));print(list(d['owners']))"
['fabrik-lib-dev1', 'fabrik-lib-dev2', 'fabrik-lib-sentinel']
```

## Self-audit

- Coverage of the spec's deltas:
  - D1 → A1; D2 → A2, A5; D3a → A3; D3b → A4; the fabrik-lib send path → Phase A Interfaces (switched off);
  - D4 → B1, B2, B3; D5 → B5; D6 → B4; D7 → Phase C step 2; D8 → spec and docs.
- Coverage of validation:
  - V1 → A1; V2 → A5; V3 → A2; V4 → A3, A4; V5 → B1, B2; V6 → B3; V7 → B4; V8 → B5;
  - V9 → deferred to the sentinel's agreement (the switch stays off). Named, not silent: it is spec U2.
- Signatures: Phase B consumes `owner_of`'s three-tuple and the `routed:` line format exactly as Phase A defines them.
- Fixed point: not yet — `/fabrik-plan-review` grades it.

## Residual unknowns

- **Resolved — U3:** the hook's baseline is 30–80 ms per run; Phase B step 4 measures the added cost against it.
- **Open — U1, the pilot result:** it gates `FABRIK_MAIL_AUTO_ADDRESS=1`. Resolution step: Phase C step 7 asks kaizen for it; the switch is an env change, not a code change.
- **Open — U2, the sentinel's agreement:** it gates `FABRIK_MAIL_LIB_ADDRESS=1` and V9. Resolution step: Phase C step 2's request; the hub turns the switch on after the agreement is recorded.
