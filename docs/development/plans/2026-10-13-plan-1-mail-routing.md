# Plan — route hub and fabrik-lib mail to the owning agent (W-931b6837)

Status: DRAFT
Profile: small
**Owner:** infra

Spec: `docs/superpowers/specs/2026-10-13-mail-routing-design.md` (DRAFT at dfc5af664, `Size: small`).
`/fabrik-plan-review` grades its sections together with this plan and flips both.

Decisions: D-815 (seams), D-818 (approach D).

Estimated diff ≈330 lines across 5 code files, tests excluded:
- `scripts/mail.py` ≈200;
- `.claude/hooks/mail_notify.py` ≈10;
- `scripts/sysadmin/mail_escalate.py` ≈60;
- `scripts/enforcement/check_beat_owners.py` ≈60, new;
- `scripts/final_gate.py` ≈8.

The data file `.fabrik/beat-owners.json` is also new.

## What this plan is

Three inline phases the orchestrator codes itself in the main checkout; no coder is dispatched:

- **A — the map, the matcher, the trail and send:** the map, `owner_of`, the validator, the trail, and send-time addressing, advisory and the `map-owner:` header (spec D1, D2, D3, the D7 send path).
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
| I5 | *"D3a, behind a switch until kaizen's pilot"* | IN, CHANGED | the switch is `switches.auto_address` in the map, not an env var (review round 1: senders' environments are not the hub's to set) |

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

- **Apply once, read after (`spec § The delta`, Principle).**
  - `send` computes `owner_of` and writes `map-owner:` into the new message.
  - `list`, `claim`, `mail_notify.py` and `mail_escalate.py` only read that header.
  - No read path imports a matcher or calls `owner_of`; `mail_notify.py` imports nothing new (its docstring's stdlib-only rule stands).
- **No message file is rewritten except by `route()`.** `route()` keeps its inbox-only `os.replace` contract (`scripts/mail.py:1756`). The send path writes `map-owner:` and any `routed:` line into the NEW message before delivery; the tie-break writes only its sidecar.
- **Fail-open everywhere.**
  - A missing, unreadable or invalid map gives `Routing(None, [], "", "")`: `send` writes no header and refuses unaddressed hub mail exactly as today; `list`, `claim` and the hook show nothing extra.
  - `mail_notify.py` stays exit-0 on any exception.
- **Deterministic in fleet-synced files:** `mail.py` and `mail_notify.py` call no model and spawn no process for routing. The only `claude -p` call is in `scripts/sysadmin/mail_escalate.py`, which is hub-only and not in `scripts/fabrik_synced_manifest.py`.
- **Switches live in the map** (`switches.auto_address`, `switches.fabrik_lib_address`, both shipped `false`), never in an environment variable. Every sender's synced `mail.py` reads the one hub map, so turning a switch on is a one-line map commit by the hub, after kaizen's pilot (`spec § Lifecycle`) or the sentinel's agreement (D7). No env var is added, so `.env.example` and `docs/CONFIGURATION.md` are unchanged.
- **Identity and roots come from `mail.py`'s own resolvers.**
  - The caller is `_caller_agent()`, never a raw `$CLAUDE_AGENT`.
  - The hub root and map path are `_opt_root()/fabrik/...` (`scripts/mail.py:317`).
  - The sidecar is under `_mail_root()`.
  - So the existing `env` test fixture (`tests/test_mail_addressing.py:28`, which sets `FABRIK_MAIL_ROOT` and the opt root) isolates every test.
- **Header hygiene:** every value written into a header (`routed:` reason and by, `map-owner:` reason) is one line: CR/LF and `·` removed, whitespace collapsed, capped at 200 characters. The trail is read from raw header lines, because `_parse` keeps only the last of repeated keys.
- **No new dependency** (`core/10-python.md:30`): stdlib `json`, `re`, `subprocess` only. Trail timestamps use `datetime.now(UTC)` (`core/10-python.md:220`). No log file (`core/10-python.md:294`).
- **The tie-break:** one sequential `claude -p --model haiku` per qualifying mail, with a 60 s timeout and at most 10 calls per run. It uses the watchdog's subscription-CLI precedent (`core/60-watchdog.md:198`) and is never a fan-out (`core/62-using-subagents.md:103`) or OpenRouter (`core/62-using-subagents.md:100`).
- **Tests:**
  - watched-fail-first for every behaviour (`core/45-testing-strategy.md:22`);
  - fixtures use the `env` fixture shape, a scratch hub tree under the opt root with its own `.fabrik/beat-owners.json`, and a stubbed `claude` on `PATH` (never called live);
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
| `.windsurf/rules/core/65-rag-search.md`, `core/60-watchdog.md` | `claude -p` is the subscription path for a low-volume classification step | `core/65-rag-search.md:108`, `core/60-watchdog.md:198` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | config via env — not engaged: the switches are data in the map, no secret | `core/35-security-auth.md:267` |
| `.windsurf/rules/core/25-data-postgres.md`, `core/30-ops.md` (FLOOR) | not engaged: no database, no service | `spec § Shape / infra implications` |
| `fabrik-lib` | the module map is read in place, never vendored | `spec § fabrik-lib verdict` |
| D-815, D-818 | the seams; the approach | `docs/DECISIONS.md` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:30` |
| **`datetime.now(UTC)`, never `datetime.utcnow()`** | `.windsurf/rules/core/10-python.md:220` |
| any `*.log` file write, any in-app log rotation/retention/cleanup | `.windsurf/rules/core/10-python.md:294` |
| an operator-facing or batch step (a judge run, a one-off classification), never a per-request path | `.windsurf/rules/core/65-rag-search.md:108` |
| a fan-out of `claude -p` processes from the orchestrator | `.windsurf/rules/core/62-using-subagents.md:103` |
| or a direct OpenRouter HTTP call — a dispatch still spends | `.windsurf/rules/core/62-using-subagents.md:100` |

## Phase A — the map, the matcher, the trail and send

Appetite: 150

**Interfaces — Produces** (`spec § The delta` D1, D2, D3, the D7 send path):
- **`.fabrik/beat-owners.json`**, new, per `spec § The delta` D2.
  - Rules are ordered general → specific: each beat's broad `paths` from kaizen's § A first, then the D-815 seam exceptions, so the specific rule wins (fleet `templates/**` before infra `templates/governance/**`; infra `scripts/**` before intel `scripts/review_loop_ledger.py`).
  - Non-repo entries become `topics`.
  - `switches` are both `false`.
- **In `scripts/mail.py`:**
  - `_glob_re(pattern) -> re.Pattern`: gitignore-style; `*` stops at `/`, `**` crosses it, a pattern without `/` matches a file name anywhere, and a trailing `/` is a directory prefix.
  - `Routing = namedtuple("Routing", "owner owners reason map_version")`.
  - `owner_of(text, mailbox="fabrik") -> Routing`, exactly per `spec § The delta` D2: cited existing FILES under `_opt_root()/fabrik`; owned paths only; last match wins; mixed → `None` plus owners; topic-only → an advisory owner with `reason` starting `topic`; a missing or invalid map → `Routing(None, [], "", "")`.
  - For `mailbox == "fabrik-lib"`, cited modules are matched against `/opt/fabrik-lib/.fabrik/module-owners.json`, per D7.
- **`route(msg_id, to_agent, repo=None, *, reason=None)`.** It appends a sanitised `routed:` line with `by` = `_caller_agent()` and keeps earlier ones; `_routed_lines(text)` reads them from the raw header. **CLI:** `route … [--reason <text>]` (optional).
- **`send(...)`:**
  - It records `explicit = to_agent is not None` before thread inheritance (`scripts/mail.py:1060-1067`).
  - Hub-bound with a map, it writes `map-owner:`.
  - With `switches.auto_address`, it auto-addresses (paths-derived owner only) with a `routed: … · map …` line and the stderr note.
  - An explicit mismatch prints the stderr advisory.
  - To `fabrik-lib` with `switches.fabrik_lib_address`, it addresses an unaddressed single-owner module mail.
  - The refusal prose (`scripts/mail.py:1083-1089`) gains one line naming `.fabrik/beat-owners.json`.
- **`scripts/enforcement/check_beat_owners.py`**, new, per `spec § The delta` D2's validator. It is registered in `scripts/final_gate.py` beside `check_spec_db_match` (`:2240-2247`) as `advisory=False`.

**Consumes:** `HUB_BEATS` (`scripts/mail.py:543`), `_caller_agent()`, `_opt_root()` (`:317`), `_mail_root()` (`:312`).

**Mirror (named):**
- `tests/test_mail_addressing.py`'s refusal tests pass unchanged: the switch ships off.
- `route` library callers (`tests/test_mail_addressing.py:123`, `:198`) and every documented `route` CLI line (`docs/reference/fabrik-mail.md:126`, `docs/reference/agents/kaizen.md:61`) stay valid, because `--reason` is optional.
- `scripts/merge_request.py:662` reads `list_msgs` rows by kind and is unaffected by the new header.

**Steps:**

1. **Write the failing tests first.** Rows A1–A6 go in a new `tests/test_mail_routing.py` on the `env` fixture shape. Run them and confirm each fails on its own assertion.
2. **Write the map.** Run `python3 scripts/enforcement/check_beat_owners.py` → exit 0, and record its unowned-path count with the denominator.
3. **Implement** the matcher, `owner_of`, the trail, the send paths, the validator and its registration.
4. **Green:** `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_mail_routing.py tests/test_mail_addressing.py tests/test_mail.py tests/test_mail_structure.py` → all pass.
5. **Red on revert**, in a throwaway worktree:
   - first-match instead of last → A2 fails;
   - `fnmatch` instead of `_glob_re` → A2's `*`-stops-at-`/` case fails;
   - ignore `switches.auto_address` → A3's off case fails;
   - overwrite instead of append, or drop sanitising → A1 fails;
   - treat an inherited address as explicit → A4 fails;
   - let `owner_of` raise on a bad map → A2's invalid-map case fails;
   - ignore the fabrik-lib switch → A6 fails.
6. **`/fabrik-review-scoped`** on Phase A's surface, run to a closing pass confirming 0. This is BLOCKING before Phase B. Phase A is not committed alone.

### Behavior Contract — Phase A

- **A1** (V1) — **Given** an addressed inbox message, **When** `route` moves it with a reason and again without one, **Then**:
  - two raw `routed:` lines are present in order, the second reading `(no reason)`, with `by` from `_caller_agent()`;
  - a reason holding a newline and `agent: x` is written as one sanitised line;
  - `agent:` is the last target.
- **A2** (V3) — **Given** a scratch map with a broad and a later specific rule and the scratch hub tree, **When** `owner_of` reads each body, **Then**:
  - a path under both → the specific owner, with its reason;
  - two owners' paths → `None` with both owners;
  - a directory, a missing file, and an unowned file → ignored;
  - `scripts/*.py` against `scripts/sysadmin/x.py` → no match;
  - a Subject topic → an advisory owner (reason starts `topic`);
  - no citation → `None`;
  - a missing or invalid map → `map_version` `""`.
- **A3** (V4) — **Given** an unaddressed hub send citing one owner's path, **When** `switches.auto_address` is false and when it is true, **Then**:
  - the first is refused as today;
  - the second is delivered to that owner with a `routed: … · map …` line and the stderr note;
  - a topic-only or mixed body is refused either way.
- **A4** (V4) — **Given** sends citing an infra-owned path, **When** one is `--to-agent intel` and another is a thread reply that inherits intel, **Then**:
  - both deliver to intel;
  - only the explicit one prints the advisory;
  - both carry `map-owner: infra · v<n> · …`;
  - with no map file, there is no header and no advisory.
- **A5** (V2) — **Given** the shipped map and scratch maps holding each defect, **When** `check_beat_owners.py` runs, **Then**:
  - the shipped map exits 0 and prints its unowned count with the denominator;
  - each scratch map exits 1 naming its defect: unknown owner, missing `source`, malformed pattern, dead pattern, a fully shadowed rule, an unknown switch;
  - a repo without the map self-skips at exit 0.
- **A6** (V9) — **Given** a scratch fabrik-lib module map, **When** unaddressed sends to `fabrik-lib` cite one owner's module, two owners' modules, or none, with `switches.fabrik_lib_address` true and then false, **Then**:
  - only the true + single-owner case is addressed, with a `routed:` line;
  - an addressed send is never changed.

## Phase B — read, claim, escalation, report

Appetite: 100

**Interfaces — Produces** (`spec § The delta` D4, D5, D6):
- **`list_msgs(repo, agent=None)`** (`scripts/mail.py:2245`). Each row carries `map_owner`, read from the `map-owner:` header, and a `map_note`:
  - `→ map: <owner>` when the header owner differs from `agent:`;
  - `→ mixed: <a>,<b>` or `→ unmapped` as written;
  - `→ haiku: <owner>` when the tie-break sidecar holds a suggestion;
  - `""` otherwise, including a message with no header.
  - `--agent X` also returns rows whose header owner is X, marked `(map)`.
- **`claim(msg_id, repo)`** (`:1725`). It prints the advisory to stderr when the header names a single owner different from `_caller_agent()`, then claims as today.
- **`.claude/hooks/mail_notify.py`.** `_summaries` (`:97`) appends the same `map_note`, computed from the `map-owner:` key its `_parse_fm` (`:59`) already returns. No new import; the broad `except` blocks (`:146-175`) keep it exit-0.
- **`mail.py route-report --days N`.** It reads inbox and archive messages from the last N days and prints, with numerators and denominators:
  - the share whose `map-owner:` differed from the first addressee;
  - of those, the share re-routed to the map owner, the share re-routed elsewhere, and the share kept;
  - the re-route rate of all hub mail.
- **`scripts/sysadmin/mail_escalate.py`:**
  - The digest line names `map: <owner>` from the header.
  - The tie-break runs per `spec § The delta` D6. It writes the sidecar `_mail_root()/fabrik/.routing/<id>.json`, taking the message id from the file name only.

**Consumes:** the `map-owner:` header and the `routed:` line format, exactly as Phase A writes them (the `Routing` reason text is not re-parsed).

**Mirror (named):**
- `tests/test_mail_notify.py` and `tests/test_mail_escalate.py` pin today's output lines; they are updated with the new markers.
- `list --agent` row expectations in `tests/test_mail_who.py` and `tests/test_mail_items.py` are re-checked.

**Steps:**

1. **Write the failing tests first** (rows B1–B5). The `claude` stub is a script on `PATH` that prints `infra`, prints `banana`, or sleeps past the timeout.
2. **Implement** per the Interfaces.
3. **Green:** `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_mail_routing.py tests/test_mail_notify.py tests/test_mail_escalate.py tests/test_mail_who.py tests/test_mail_items.py tests/test_mail_addressing.py tests/test_mail_structure.py tests/test_mail.py` → all pass.
4. **Measure:** time the hook 20 times on the live inbox; record the median beside the U3 baseline in § Evidence. A median more than 10 ms above the baseline is a stop and a fix before step 5.
5. **Red on revert**, in a throwaway worktree:
   - drop the `--agent` header rows → B1 fails;
   - accept unvalidated tie-break output → B4's `banana` case fails;
   - write the suggestion into the message file → B4's md5 assertion fails;
   - drop the per-run cap → B4's cap case fails.
6. **`/fabrik-review-scoped`** on Phase B's surface, run to a closing pass confirming 0. This is BLOCKING before Phase C.

### Behavior Contract — Phase B

- **B1** (V5) — **Given** an inbox holding an agreeing message, a mis-addressed one, a mixed one, an unmapped one and one with no header, **When** `list` and `list --agent infra` run, **Then**:
  - the notes read `""`, `→ map: infra`, `→ mixed: …`, `→ unmapped` and `""`;
  - infra's list includes the mis-addressed one marked `(map)`.
- **B2** (V5) — **Given** a mis-addressed message, **When** `claim` runs as `intel`, **Then**:
  - stderr carries the advisory and the message is claimed;
  - no inbox file changes bytes before the rename.
- **B3** (V6) — **Given** the hook over the B1 inbox and over a message with a malformed `map-owner:` header, **When** it runs, **Then**:
  - it prints the markers, and prints the banner without a marker for the malformed one;
  - it exits 0;
  - `sys.modules` gains no `mail` module.
- **B4** (V7) — **Given** stale unclaimed `unmapped` messages and the `claude` stub printing `infra`, `banana` and timing out, **When** the escalation tie-break runs, **Then**:
  - the sidecars hold `infra`, `none` and `none`, each with `map_version`;
  - the message files' md5s are unchanged;
  - a second run makes no new call;
  - with 12 qualifying messages, one run makes exactly 10 calls.
- **B5** (V8) — **Given** a fixture archive whose trails and headers hold known re-routes, **When** `route-report --days 30` runs, **Then** it prints each rate with its numerator and denominator.

## Phase C — fabrik-lib request, docs, Finish

Appetite: 90

**Interfaces — Produces** (`spec § The delta` D7, D8, `spec § Documentation landing sites`):
- **A request mail** to `fabrik-lib` (`--to-agent fabrik-lib-sentinel`) carrying:
  - the rule (D-815) and kaizen's numbers (01M4TCHSPX);
  - the `fabrik_lib_address` switch, and that the hub sets it after the sentinel records its agreement;
  - the asks: re-vendor `mail.py`, and validate `--to-agent` against its three-name roster.
- **Docs:**
  - `docs/reference/fabrik-mail.md` § Routing: the map, precedence, the switches, the trail, the `map-owner:` header, markers, the tie-break sidecar, `route-report`, and the measure;
  - `docs/workstation/fabrik-mail.md`: the escalation cron's tie-break step;
  - `docs/workstation/hooks-index.md`: the `mail_notify.py` row;
  - `docs/reference/work-tracking.md`: only if `mail.py`'s AFTER-EDIT coupling shows it stale;
  - `docs/workflows/FINAL_GATE_WORKFLOW.md`: the new check's row (the `final_gate.py` AFTER-EDIT);
  - `INDEX.md`: rows for the map, the validator and the test file;
  - `CHANGELOG.md`.

**Steps:**

1. Write the docs above. Run `python3 scripts/enforcement/check_doc_sync.py` → exit 0, and `python3 scripts/render_doc_script_links.py --check` → exit 0.
2. Send the fabrik-lib request (`mail.py send --to fabrik-lib --to-agent fabrik-lib-sentinel --kind request`).
3. **`/fabrik-review-scoped`** on Phase C's docs, run to a closing pass confirming 0.
4. **Finish — the whole-plan `/fabrik-review`** (the D7 floor: ≥1 Opus authoritative seat plus Sonnet and Haiku finders per slice) over Phases A–C, with its receipt under `docs/development/reviews/`. Run until `Status: CONVERGED`.
5. Gate: `.venv/bin/python scripts/final_gate.py --check --json` → `status: "success"` with the receipt staged.
6. **ONE commit** with explicit pathspecs and trailers, CHANGELOG, and the work items closed. Then push. The post-commit governance sync distributes `mail.py`, `mail_notify.py` and the check.
7. Reply to kaizen with the commit, ask for the pilot rerun against the shipped map (the `auto_address` criterion), and close W-931b6837.

### Behavior Contract — Phase C

- **C1** — **Given** the committed tree after the governance sync, **When** a synced project's `mail.py send` to the hub cites an infra-owned path while addressed to intel, **Then** the message carries `map-owner: infra` and stderr carries the advisory. Checked in one project with `FABRIK_MAIL_ROOT` pointed at scratch, so nothing is delivered for real.

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
- docs/reference/work-tracking.md
- docs/workflows/FINAL_GATE_WORKFLOW.md
- INDEX.md
- CHANGELOG.md
- docs/DECISIONS.md
- docs/superpowers/specs/2026-10-13-mail-routing-design.md
- docs/development/reviews/2026-10-13-plan-1-mail-routing-review.md

## Evidence

**Phase A.** The anchors the delta edits, at 50cc502e0:
```text
scripts/mail.py:312:    return Path(os.environ.get("FABRIK_MAIL_ROOT", "/opt/fabrik-mail"))
scripts/mail.py:543:HUB_BEATS = ("infra", "fleet", "intel", "kaizen")
scripts/mail.py:886:def send(
scripts/mail.py:1079:        if not to_agent and not broadcast and not is_thread_reply:
scripts/mail.py:1756:def route(msg_id: str, to_agent: str, repo: str | None = None) -> Path:
scripts/final_gate.py:2242:                "scripts/enforcement/check_spec_db_match.py",
scripts/merge_request.py:662:        for fm in _mail().list_msgs(ctx.mailbox, None)
```
Stdlib `fnmatch` lets `*` cross `/`, which is why the plan specifies its own segment-aware translator:
```text
$ .venv/bin/python -c "import fnmatch as f; print(f.fnmatch('scripts/sysadmin/dispatch_headroom.py','scripts/*.py'))"
True
```
`route` has no caller outside `scripts/mail.py` and the tests; the documented CLI lines carry no `--reason`, which stays optional:
```text
docs/reference/fabrik-mail.md:126:  **`mail.py route <id> --to-agent <role>`** (empty role clears it). Routing is a FILTER, never a lock:
docs/reference/agents/kaizen.md:61:   workflow or a brief is yours — `python3 scripts/mail.py route <id> --to-agent kaizen`; a mail about
```

**Phase B.** The U3 baseline, measured 2026-10-13 over the live `fabrik` inbox (47 messages): five runs of `.claude/hooks/mail_notify.py` with a UserPromptSubmit payload, wall seconds including interpreter start-up.
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
.claude/hooks/mail_notify.py:59:def _parse_fm(text: str) -> dict | None:
.claude/hooks/mail_notify.py:97:def _summaries(inbox: Path, cap: int = _FLOOD_CAP) -> list[str]:
scripts/sysadmin/mail_escalate.py:2:# AFTER-EDIT: docs/workstation/fabrik-mail.md, docs/reference/fabrik-mail.md | tests/test_mail_escalate.py
```

**Phase C.** fabrik-lib's map, read in place; its modules are top-level directories of the repo:
```text
$ python3 -c "import json;d=json.load(open('/opt/fabrik-lib/.fabrik/module-owners.json'));print(list(d['owners']))"
['fabrik-lib-dev1', 'fabrik-lib-dev2', 'fabrik-lib-sentinel']
```

## Self-audit

- Coverage of the spec's deltas:
  - D1 → A1; D2 → A2, A5; D3a → A3; D3b → A4; D3c (the header) → A4; D7 send path → A6;
  - D4 → B1, B2, B3; D5 → B5; D6 → B4; D7 request → Phase C step 2; D8 → spec and docs.
- Coverage of validation: V1 → A1; V2 → A5; V3 → A2; V4 → A3, A4; V5 → B1, B2; V6 → B3; V7 → B4; V8 → B5; V9 → A6. No gap.
- Signatures: Phase A defines `Routing`, `owner_of`, the `routed:` line format and the `map-owner:` header once. Phase B reads only the two headers, never the `Routing` reason text.
- Round 1 (plan-review) folded 29 confirmed defects; the largest changes are:
  - the header-at-send design, which keeps the notify hook import-free;
  - switches in the map instead of senders' environments;
  - a segment-aware glob matcher;
  - defined path extraction;
  - optional `--reason`.
- Fixed point: not yet — `/fabrik-plan-review` grades it.

## Residual unknowns

- **Resolved — U3:** the hook reads a header it already parses; Phase B step 4 confirms its median stays within 10 ms of the baseline.
- **Open — U1, the pilot result:** it gates `switches.auto_address`. Resolution step: Phase C step 7 asks kaizen for it; turning it on is a one-line map commit.
- **Open — U2, the sentinel's agreement:** it gates `switches.fabrik_lib_address`. Resolution step: Phase C step 2's request; the hub sets the switch after the agreement is recorded.
