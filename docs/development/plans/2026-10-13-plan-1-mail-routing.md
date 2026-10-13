# Plan — route hub and fabrik-lib mail to the owning agent (W-931b6837)

Status: EXECUTED 2026-10-13
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
| I5 | *"D3a, behind a switch until kaizen's pilot"* | IN, CHANGED | the switch is `switches.auto_address` in the map, not an env var (review round 1: senders' environments are not the hub's to set); the pilot runs in the build (design-approval panel) |

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
  - The whole routing step in `send` — extraction, the map read and the matcher — sits in one guard; any exception yields `Routing(None, [], "", "")` and today's behaviour (A3's raise case).
- **Deterministic in fleet-synced files:** `mail.py` and `mail_notify.py` call no model and spawn no process for routing. The only `claude -p` call is in `scripts/sysadmin/mail_escalate.py`, which is hub-only and not in `scripts/fabrik_synced_manifest.py`.
- **Switches live in the map** (`switches.auto_address`, `switches.fabrik_lib_address`, both shipped `false`), never in an environment variable. Every sender's synced `mail.py` reads the one hub map, so turning a switch on is a one-line map commit by the hub, after the in-build pilot (Phase C step 2, `spec § Lifecycle`) or the sentinel's agreement (D7). No env var is added, so `.env.example` and `docs/CONFIGURATION.md` are unchanged.
- **Identity and roots come from `mail.py`'s own resolvers.**
  - The caller is `_caller_agent()`, never a raw `$CLAUDE_AGENT`.
  - The hub root and map path are `_opt_root()/fabrik/...` (`scripts/mail.py:317`).
  - The sidecar is under `_mail_root()`.
  - So the existing `env` test fixture (`tests/test_mail_addressing.py:28`, which sets `FABRIK_MAIL_ROOT` and the opt root) isolates every test.
- **Header hygiene:** every value written into a header (`routed:` reason and by, `map-owner:` reason) is sanitised to one line: every line boundary Python's `str.splitlines()` recognises (CR, LF, VT, FF, the C0 separators 0x1c-0x1e, NEL, U+2028, U+2029) becomes a space and `·` is removed, whitespace is collapsed, and the value is capped at 200 characters — the same boundary set `_parse` and `route()` split on, so a value can never start a header line. The trail is read from raw header lines, because `_parse` keeps only the last of repeated keys.
- **No new dependency** (`core/10-python.md:30`): stdlib `json`, `re`, `subprocess` only. Trail timestamps use `datetime.now(UTC)` (`core/10-python.md:220`). No log file (`core/10-python.md:294`).
- **The tie-break:** one sequential `claude -p --model haiku` per qualifying mail, with a 60 s timeout and at most 10 calls per run. It is the subscription path for a low-volume classification (`core/65-rag-search.md:108`); that rule's `claude_p_chat` adapter lives in fabrik-lib `rag`, which the hub does not vendor, so it calls the CLI directly as the watchdog does (`core/60-watchdog.md:198`) and is never a fan-out (`core/62-using-subagents.md:103`) or OpenRouter (`core/62-using-subagents.md:100`).
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
| an operator-facing or batch step (a judge run, a one-off classification), never a per-request path — is `claude -p` through the module's `claude_p_chat` adapter | `.windsurf/rules/core/65-rag-search.md:108` |
| a fan-out of `claude -p` processes from the orchestrator | `.windsurf/rules/core/62-using-subagents.md:103` |
| or a direct OpenRouter HTTP call — a dispatch still spends | `.windsurf/rules/core/62-using-subagents.md:100` |

## Phase A — the map, the matcher, the trail and send

✅ EXECUTED 2026-10-13 (uncommitted — this plan commits ONCE at Phase C step 7; governance-sync paths)

Appetite: 150

**Interfaces — Produces** (`spec § The delta` D1, D2, D3, the D7 send path):
- **`.fabrik/beat-owners.json`**, new, per `spec § The delta` D2.
  - Rules are ordered general → specific: each beat's broad `paths` from kaizen's § A first, then the D-815 seam exceptions, so the specific rule wins (fleet `templates/**` before infra `templates/governance/**`; infra `scripts/**` before intel `scripts/review_loop_ledger.py`).
  - Non-repo entries become `topics`.
  - `switches` are both `false`.
- **In `scripts/mail.py`:**
  - `_glob_re(pattern) -> re.Pattern`: gitignore-style; `*` stops at `/`, `**` crosses it, a pattern without `/` matches a file name anywhere, and a trailing `/` is a directory prefix.
  - `Routing = namedtuple("Routing", "owner owners reason map_version")`.
  - `owner_of(text, mailbox="fabrik", from_repo="fabrik") -> Routing`, exactly per `spec § The delta` D2, including its non-hub sender rule (own-repo paths count only when absent there or byte-identical to the hub's): cited existing FILES under `_opt_root()/fabrik`; owned paths only; last match wins; mixed → `None` plus owners; topic-only → an advisory owner with `reason` starting `topic`; a missing or invalid map → `Routing(None, [], "", "")`.
  - For `mailbox == "fabrik-lib"`, cited modules are matched against `_opt_root()/fabrik-lib/.fabrik/module-owners.json`, per D7.
- **`route(msg_id, to_agent, repo=None, *, reason=None)`.** It appends a sanitised `routed:` line with `by` = `_caller_agent()` and keeps earlier ones; `_routed_lines(text)` reads them from the raw header. **CLI:** `route … [--reason <text>]` (optional).
- **`send(...)`:**
  - It records `explicit = bool(to_agent)` after the normalisation at `scripts/mail.py:901` and before thread inheritance (`:1060-1067`); `is not None` would be always true there.
  - Hub-bound with a non-empty `map_version`, it writes `map-owner:`; it calls `owner_of(..., from_repo=sending_repo)` with `sending_repo = _current_repo()` (`scripts/mail.py:951`).
  - With `switches.auto_address`, it auto-addresses (paths-derived owner only) with a `routed: … · map …` line and the stderr note.
  - An explicit mismatch prints the stderr advisory.
  - `--to-agent map` (accepted before the `HUB_BEATS` check, `scripts/mail.py:1040`) addresses the paths-derived owner whatever the switch, or is refused naming the owners or `unmapped`; to any non-hub mailbox it is refused.
  - The routing step runs inside one guard (§ Global Constraints, fail-open).
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
   - ignore the fabrik-lib switch → A6 fails;
   - drop the shadowed-rule check, or the unknown-owner check, from the validator → A5 fails;
   - auto-address when the map file is missing → A3's no-map case fails;
   - remove the routing guard → A3's raise case fails;
   - ignore `from_repo` → A2's project-path case fails;
   - record `explicit = to_agent is not None` after `:901` → A4 fails (the inherited one prints the advisory).
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
  - a missing or invalid map → `map_version` `""`;
  - with `from_repo` a scratch project, a cited path present there with different bytes → ignored, and a byte-identical one → counted;
  - an absolute `_opt_root()/fabrik/…` token → counted for both a hub and a project sender.
- **A3** (V4) — **Given** an unaddressed hub send citing one owner's path, **When** `switches.auto_address` is false and when it is true, **Then**:
  - the first is refused as today;
  - the second is delivered to that owner with a `routed: … · map …` line and the stderr note;
  - a topic-only or mixed body is refused either way;
  - with no map file at all, an unaddressed send is refused exactly as today and carries no header;
  - a thread reply is never auto-addressed;
  - with the switch off, `--to-agent map` delivers a paths-placed send to its owner with a `routed: … · map …` line, and is refused for a topic-only, mixed or unmapped one;
  - with `owner_of` patched to raise, an unaddressed send is refused and an addressed one delivered exactly as today, with no header, and `--to-agent map` is refused;
  - `--to-agent map` with `--to fabrik-lib` is refused;
  - a project send with a lane `--from wef1` citing the project's own differing `CLAUDE.md` is not attributed to the hub (`from_repo` is the sending repo, not the lane).
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

✅ EXECUTED 2026-10-13 (uncommitted — one commit at Phase C step 7); the tie-break deferred to W-a28ece0d by step 1

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
  - the re-route rate of all hub mail;
  - who answered: of mail with a reply carrying `from-agent:`, the share whose first reply came from the map owner and the share from the first addressee. Replies are read from every mailbox (`_mail_root()/*/{inbox,archive}`), since a hub agent's reply to a project lands in the project's mailbox (`scripts/mail.py:1111`); the first reply is the earliest whose `re:` names the message.
- **`scripts/sysadmin/mail_escalate.py`:**
  - The digest line names `map: <owner>` from the header.
  - The tie-break runs per `spec § The delta` D6. It writes the sidecar `_mail_root()/fabrik/.routing/<id>.json`, taking the message id from the file name only.

**Consumes:** the `map-owner:` header and the `routed:` line format, exactly as Phase A writes them (the `Routing` reason text is not re-parsed), and in `list` and `mail_escalate.py` only, the D6 sidecar this phase writes.

**Mirror (named):**
- `tests/test_mail_notify.py` and `tests/test_mail_escalate.py` pin today's output lines; they are updated with the new markers.
- `list --agent` row expectations in `tests/test_mail_who.py` and `tests/test_mail_items.py` are re-checked.

**Steps:**

1. **Write the failing tests first** (rows B1–B5). The `claude` stub is a script on `PATH` that prints `infra`, prints `banana`, or sleeps past the timeout.
2. **Implement** per the Interfaces, the tie-break last. The deferral (`spec § The delta` D6) is decided once, at step 1: if Phase A overran its 150-minute appetite, the whole tie-break moves to a follow-up work item — its Interfaces bullet, B4, B1's `→ haiku:` case and step 5's three tie-break mutants — and Phase B is built without it.
3. **Green:** `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_mail_routing.py tests/test_mail_notify.py tests/test_mail_escalate.py tests/test_mail_who.py tests/test_mail_items.py tests/test_mail_addressing.py tests/test_mail_structure.py tests/test_mail.py` → all pass.
4. **Measure:** before Phase B's first edit and again after step 3, time the hook 20 times each on the same live inbox snapshot (copied to scratch) with `time.perf_counter_ns()` around one subprocess run. Record both medians and their spreads in § Evidence. The change adds no I/O, so a median rise above 20 ms between the two 20-run medians is unexpected and is investigated before step 5.
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
  - an unmapped message with a tie-break sidecar holding `infra` shows `→ haiku: infra` in `list`, and the hook shows no haiku marker.
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
- **B5** (V8) — **Given** a fixture archive whose trails, headers and replies hold known re-routes and answerers, **When** `route-report --days 30` runs, **Then** it prints each rate with its numerator and denominator, including the answered-by-map-owner and answered-by-addressee shares.

## Phase C — fabrik-lib request, docs, Finish

✅ EXECUTED 2026-10-13 (the one commit of this plan)

Appetite: 90

**Interfaces — Produces** (`spec § The delta` D7, D8, `spec § Documentation landing sites`):
- **A request mail** to `fabrik-lib` (`--to-agent fabrik-lib-sentinel`) carrying:
  - the rule (D-815) and kaizen's numbers (01M4TCHSPX);
  - the `fabrik_lib_address` switch, and that the hub sets it once the sentinel records its agreement, its only precondition;
  - two follow-ups that never block the switch: re-vendor `mail.py`, and validate `--to-agent` against its three-name roster.
- **Docs:**
  - `docs/reference/fabrik-mail.md` § Routing: the map, precedence, the switches, the trail, the `map-owner:` header, markers, the tie-break sidecar, `route-report`, and the measure;
  - `docs/workstation/fabrik-mail.md`: the escalation cron's tie-break step (deferred with the tie-break to W-a28ece0d by Phase B step 1; the digest's `· map:` field is documented instead);
  - `docs/workstation/hooks-index.md`: the `mail_notify.py` row;
  - `docs/reference/work-tracking.md`: only if `mail.py`'s AFTER-EDIT coupling shows it stale;
  - `docs/workflows/FINAL_GATE_WORKFLOW.md`: the new check's row (the `final_gate.py` AFTER-EDIT);
  - `INDEX.md`: rows for the map, the validator and the test file;
  - `CHANGELOG.md`.

**Steps:**

1. Write the docs above. Run `python3 scripts/enforcement/check_doc_sync.py` → exit 0, and `python3 scripts/render_doc_script_links.py --check` → exit 0.
2. **The pilot, in the build.** Over hub archive mail of the last 30 days that has a reply carrying `from-agent:` from a hub agent (replies read from every mailbox, as `route-report` reads them), compute with the new `owner_of`: the share where the map's paths-derived owner is the replier, and the share where the sender's addressee is, both over the mails the map can place. Record the counts and denominators in § Evidence. The commit ships `switches.auto_address` false either way (the measure is biased toward the sender, `spec § The delta` D5).
3. Send the fabrik-lib request (`mail.py send --to fabrik-lib --to-agent fabrik-lib-sentinel --kind request`).
4. **`/fabrik-review-scoped`** on Phase C's docs, run to a closing pass confirming 0.
5. **Finish — the whole-plan `/fabrik-review`** (the D7 floor: ≥1 Opus authoritative seat plus Sonnet and Haiku finders per slice) over Phases A–C, with its receipt under `docs/development/reviews/`. Run until `Status: CONVERGED`.
6. Gate: `.venv/bin/python scripts/final_gate.py --check --json` → `status: "success"` with the receipt staged.
7. **ONE commit** with explicit pathspecs and trailers, CHANGELOG, and the work items closed. Then push. The post-commit governance sync distributes `mail.py`, `mail_notify.py` and the check.
8. Reply to kaizen with the commit and the pilot's numbers for its review, and close W-931b6837. When the map's share is at least the sender's over at least 50 placeable mails and kaizen's review finds no reason against, the hub sets `switches.auto_address` true in a separate one-line map commit (`spec § Lifecycle` step 2).

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

## Coverage Checklist

Derived from `review_rubric.py` over the paths Phases A and B write, and the review's class ledger; every row adjudicated by the four plan-review passes.

| Class | Source | Where it bites in this plan | Status |
|---|---|---|---|
| secrets, config via env, no hardcoded fallback | core/35-security-auth.md (FLOOR) | the switches are data in the map, not env or secrets; no credential is read | CLEAN |
| data / migrations | core/25-data-postgres.md (FLOOR) | no database; the sidecar is a JSON file in the mail store | CLEAN |
| ops, cron, deploy invariants | core/30-ops.md (FLOOR) | the tie-break rides the existing 6-hourly escalation cron; no new cron, no VPS write | CLEAN |
| 12-Factor (all twelve) | the FLOOR block | stdout/stderr only, config in one repo file, stateless CLI | CLEAN |
| Python discipline (UTC datetimes, no file loggers, deps untouched) | core/10-python.md | `datetime.now(UTC)` in the trail; no dependency added | FIXED (round 1: the Constraints Digest quotes) |
| documentation landing sites | core/40-documentation.md | `docs/reference/fabrik-mail.md` § Routing, hooks-index, INDEX rows | FIXED (round 1: file scope named every doc) |
| one test per behaviour, watched-fail-first | core/45-testing-strategy.md | contract rows A1–A6, B1–B5, each with its red-on-revert mutant | FIXED (rounds 1–2: A3 no-map and A5 validator mutants added) |
| workers / jobs | core/75-workers-jobs.md | the tie-break: sequential, 60 s timeout, at most 10 calls per run | FIXED (round 1: per-run cap and timeout stated) |
| citation | review class ledger | every `path:line` re-derived at HEAD in pass 4 | FIXED (round 1) |
| owner_of semantics, path extraction, glob semantics and order | review class ledger | D2 matcher: last-match-wins, segment globs, defined extraction | FIXED (rounds 1–2) |
| header at send, header sanitising, sidecar readers | review class ledger | D1/D3c/D6: one header written at send, every `splitlines()` boundary, list + cron read the sidecar | FIXED (rounds 1–3) |
| switches, reply exemption, identity resolver | review class ledger | D3a: map switches, thread replies untouched, `_caller_agent()` | FIXED (rounds 1–2) |
| trail, mirrors, file scope, behaviour contract, digest, tie-break | review class ledger | D1, Contract deltas, File Scope, Phase A/B contract rows | FIXED (rounds 1–2) |

The rubric, pasted verbatim:

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment) — `<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

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

### core/10-python.md  (hit: .claude/hooks/mail_notify.py, scripts/enforcement/check_beat_owners.py, scripts/final_gate.py)
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
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### core/40-documentation.md  (hit: docs/reference/fabrik-mail.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_mail_routing.py)
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
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

### core/75-workers-jobs.md  (hit: .fabrik/beat-owners.json)
- Connection string: `postgres-main:5432`, never `localhost`. See `30-ops.md` § Docker DNS.
- If the primary transaction rolls back, the job must never exist. This eliminates dual-write inconsistencies between application state and the queue.
- **Never** use a runtime-generated random UUID as an idempotency key — it changes on every retry, defeating the check entirely.
- The count and the base are env vars (`58-resilience.md` §7a tuning knobs), never literals in SQL or code.
- Poison-pill messages must never loop infinitely. The DLQ is for human inspection — automated agents do not resolve DLQ entries.
- **A dead-lettered job carries WHY, and the why must be honest about transport vs content.** A job that died from an operational cause (hard-timeout/poison, network, proxy, lock contention, worker restart) is an **operational** terminal — record it as `processing_timeout`/transient and present it as "timed out, will retry / re-runnable", and keep it resettable. **Never** stamp it with a *content* verdict (`deleted`, `unavailable`, `no_captions`) — that tells the user the content is gone when only the transport failed, and it's silent unrecoverable loss. A content terminal requires positive content evidence. See `58-resilience.md` § Operational failures are transient.
- I/O-bound handlers run in-process on the asyncio pool (the scaffold's default). Isolate a handler that can take the worker down with it — CPU-bound or memory-heavy — in a **child process** (shelling out is handled in-process by § External Subprocess Lifecycle); the parent monitors and marks a crashed child's job failed. ⚠️ Fork is opt-in under the pinned Python: since 3.14 `multiprocessing`'s POSIX default is `forkserver`, so `fork` must be requested explicitly (`multiprocessing.get_context("fork")`) and never from a process with threads alive (`os.fork()` warns on that since 3.12).
- **This complements the existing drain path, never replaces it.** If the job can finish in time, drain normally.
- **This complements the visibility timeout + orphan sweep, never replaces them.** The sweep is the crash-path backstop — SIGKILL, OOM, segfault, power loss. The fast path only fires on cooperative SIGTERM where the worker is still alive and can execute an `UPDATE`.
- Twelve-factor app processes **must never daemonize or write PID files.** Scale out via the process model (add container replicas), not up via in-process daemons. Docker supervises; Docker Compose restarts.
- 2. **The Adaptive Worker Pool parent** (§ Adaptive Worker Pool) supervises N independent claim loops — asyncio tasks by default, forked children for CPU-bound work — synchronised through the PG queue (`SKIP LOCKED`), not through each other. This is **not** a 12F violation: (a) the parent runs as the foreground CMD — it never daemonizes; (b) children are stateless workers, not daemons; (c) scaling *out* is still done by adding container replicas (`compose.yaml` `deploy.replicas`). The pool scales *within* one container; replicas scale *across* containers.
- 2. **Kill the group, never just the child.** On timeout/early-exit, `os.killpg(os.getpgid(proc.pid), SIGTERM)` then escalate to `SIGKILL` after a grace period. `proc.terminate()` signals only the direct child — grandchildren keep running, keep burning bandwidth/proxy, and keep per-resource locks held.
- 3. **Enforce a per-subprocess hard-timeout wall AND a kill-count poison cap.** The parent watchdog kills a subprocess that exceeds its hard limit, increments a DB `timeout_kill_count`, and after `TIMEOUT_KILL_MAX` (default 3) marks the job terminal. **That terminal is operational** — classify it transient/`processing_timeout` and surface it as "timed out, will retry", **never** as a content verdict like "unavailable" (see Dead-Letter Handling below and `58-resilience.md` § Operational failures are transient).
- 4. **Run an OS-process orphan reaper — distinct from the DB orphan-*job* sweep.** A Beat/cron sweep that SIGKILLs known subprocess names whose **parent is not a live worker** (build a live-worker-PID set; do NOT test `PPID == 1` — orphans reparent to the init system, and on WSL to `/init`, not PID 1) or that exceed the hard-limit age. The DB sweep reconciles queue rows; this reconciles OS processes — you need both.
- Every worker runs an adaptive pool: N independent claim loops scaled between `WORKER_MIN` and `WORKER_MAX` on queue depth. Fixed-concurrency workers waste resources when idle and bottleneck when loaded. The rules below are the pool's PROPERTIES; asyncio tasks are the default implementation, forked children the CPU-bound one — the same properties, not a second pattern. ⚠️ Do not assume the scaffold satisfies this section — verify the emitted worker against the Done When list before building on it.
- The parent is the **orchestrator only** — it never processes jobs. Each claim loop is independent against the PG queue.
- Fall back to process resources (`os.process_cpu_count()` — the affinity-aware count the pinned Python ships since 3.13; never `multiprocessing.cpu_count()`, which reports the HOST — and `os.sysconf`) only when cgroup files are absent or contain `max` (unbounded).
- 3. **Cap:** never exceed `max_workers`.
- 4. **Safety:** only kill workers with `job_id == 0` (idle, not processing). Never kill a worker mid-job.
- 5. **Floor:** never go below `min_workers`.
| Parent process using the shared connection pool | A dedicated short-lived connection per parent loop iteration, never the pool |
- [ ] Per-subprocess hard-timeout wall + kill-count poison cap; poison classified as operational/transient, never a content verdict.
- [ ] Scale-down: requires 3 consecutive idle checks (hysteresis); kills highest slot_id first; only idle workers; never below `min_workers`.

# promote-to-check_*: 100 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `shape.is_admin_dashboard: true` `two_factor` `fabrik apply` `/health` `/metrics` `saas/60-saas-ui.md` `shape.has_bearer_api: true` `two_factor`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `plpgsql` `CLAIMS.yaml` `fleet-postgres-main-no-pgvector` `postgres-main`
```

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

**Phase A — execution evidence (2026-10-13).**
- Tests: `tests/test_mail_routing.py` — the first 30 written red first (27 red before the code; the 3 green ones pin today's refusals); the reviews' regression tests and Phase B bring it to 69 (`pytest --collect-only`, 2026-10-13); the mail suites `test_mail_routing.py test_mail_addressing.py test_mail.py test_mail_structure.py` pass, except `test_kaizen_sends_one_addressed_obligation_per_beat`, red at HEAD before this plan (it greps `kaizen_collect_v2.py` for a loop a90b35a3b rewrote) and boarded as W-d1e6573a.
- Red on revert, in a throwaway worktree: the plan's step-5 mutants 13 of 14 red; the 14th ("auto-address when the map file is missing") is equivalent — with no map `owner_of` returns no owner, so nothing can be auto-addressed; every review fix after that was proven red the same way (12 of 12, then 1 of 1 per later fix).
- The live map: `python3 scripts/enforcement/check_beat_owners.py` → `map OK`, `unowned: 4883 of 5968 tracked` (the unowned mass is `.fabrik/` work items, `docs/` and `tests/`, which kaizen's § A assigns to no beat).
- The scoped review: 7 passes, confirmed 19 → 2 → 2 → 1 → 1 → 1 → 0 (two pass-1 candidates refuted: a topic owner may advise, spec D2).
- **The pilot (Phase C step 2, run here because a backtest of the rule runs before the rule is relied on):** hub mail of the last 30 days, non-reply, with a first reply from a hub agent read from every mailbox: 481. Placeable by cited paths: 49; mixed 11; topic-only 8; unmapped 413. Map owner = first replier: 32 of 49 (65%); sender's addressee = first replier on the same placeable, addressed mails: 45 of 49 (92%). Below the 50-mail floor and below the sender, so `switches.auto_address` stays false. The misses: 8 of 17 are kaizen-owned wording files answered by infra (kaizen joined 2026-10-06, inside the window).
- Appetite: Phase A ran 186 of its 150 minutes, so Phase B step 1's deferral fires: the Haiku tie-break moves to a follow-up work item.

**Phase B — execution evidence (2026-10-13).**
- Step 1: Phase A ran 186 of its 150 minutes, so the tie-break (its Interfaces bullet, B4, B1's `→ haiku:` case and step 5's three tie-break mutants) moved to W-a28ece0d.
- Tests red first (8 new tests red before the code); green: `test_mail_routing.py test_mail_notify.py test_mail_escalate.py test_mail_who.py test_mail_items.py test_mail_addressing.py test_mail_structure.py test_mail.py` — 409 passed, 1 failed, the same pre-existing W-d1e6573a red.
- Step 4, the hook on one 23-message inbox snapshot, 20 runs each, `time.perf_counter_ns()` around one subprocess: before median 31.4 ms (rerun 35.5 ms), after 31.5 ms — no rise.
- Red on revert: 8 of 8 initial mutants, then every review fix (14 of 14 after the fixtures were strengthened, then 1 of 1).
- The scoped review: 3 passes, confirmed 16 → 1 → 0.

**Phase C — execution evidence (2026-10-13).**
- Docs: `docs/reference/fabrik-mail.md` § Routing, `docs/workstation/fabrik-mail.md`, `docs/workstation/hooks-index.md`, `docs/workflows/FINAL_GATE_WORKFLOW.md`, INDEX rows, CHANGELOG; `check_doc_sync.py` exit 0; their scoped review confirmed 11 → 2 → 0 (and fixed two code defects it surfaced: `route-report` now counts only path-derived owners, and a topic is the exact `topic "` prefix).
- The fabrik-lib request: mail 01M4V1N3EJEWAQFN5G17ZA113Y to `fabrik-lib-sentinel` — the switch's one precondition is the sentinel's agreement; re-vendoring and roster validation are follow-ups.
- The pilot: Phase A's evidence above (map 32 of 49, sender 45 of 49, 49 below the 50-mail floor) — `switches.auto_address` ships false.
- The Finish `/fabrik-review`: `docs/development/reviews/2026-10-13-plan-1-mail-routing-review.md`, confirmed 3 → 0 over 2 passes.
- The stale lock `.fabrik/plan-locks/2026-09-06-plan-1-session-history-retention.json` is removed here: fleet reported that plan executed and released `docs/workstation/hooks-index.md` to this plan (2026-10-13).

## Self-audit

- Coverage of the spec's deltas:
  - D1 → A1; D2 → A2, A5; D3a → A3; D3b → A4; D3c (the header) → A4; D7 send path → A6;
  - D4 → B1, B2, B3; D5 → B5; D6 → B4; D7 request → Phase C step 3; D5's pilot → Phase C step 2; D3d, D3e → A3; D8 → spec and docs.
- Coverage of validation: V1 → A1; V2 → A5; V3 → A2; V4 → A3, A4; V5 → B1, B2; V6 → B3; V7 → B4; V8 → B5; V9 → A6. No gap.
- Signatures: Phase A defines `Routing`, `owner_of`, the `routed:` line format and the `map-owner:` header once. Phase B reads only the two headers, never the `Routing` reason text.
- Round 1 (plan-review) folded 29 confirmed defects; the largest changes are:
  - the header-at-send design, which keeps the notify hook import-free;
  - switches in the map instead of senders' environments;
  - a segment-aware glob matcher;
  - defined path extraction;
  - optional `--reason`.
- Fixed point: reached — pass 4 confirmed 0; the design-approval panel's fold was re-reviewed in passes 5 and 6, and pass 6 confirmed 0 over every class in the ledger (§ Pass Ledger).

## Residual unknowns

- **Resolved — U3:** the hook reads a header it already parses and adds no I/O; Phase B step 4 records 20-run before and after medians measured the same way.
- **Open — U1, the pilot result:** it gates `switches.auto_address`. Resolution step: Phase C step 2 measures it in the build; after kaizen's review, a separate one-line map commit sets the switch (step 8).
- **Open — U2, the sentinel's agreement:** it gates `switches.fabrik_lib_address`. Resolution step: Phase C step 3's request; the hub sets the switch after the agreement is recorded.

## Pass Ledger

| Pass | seats · axes | counters | method | md5 plan / spec (end) |
|-----:|---|---|---|---|
| 1 | 4 (slice A: Opus + Haiku on the spec's delta, contract deltas, decisions and the plan's constraints and Phase A · slice B: Sonnet + Haiku on every other section) · claims · gates · interfaces · completeness | found: 29 · confirmed: 29 · refuted 0 | method: re-derivation — each seat re-derived its slice's anchors, counts and quotes from HEAD and ran owner_of mentally against real inbox mail | 56175b66c |
| 2 | 4 (the round-1 seats on their own slices plus one hop) | found: 9 · confirmed: 9 · 5 introduced by pass-1 fixes; 29 of 29 round-1 claims FIXED | method: re-derivation — each seat re-ran its round-1 commands against the pass-2 pin | c02e0d4bb |
| 3 | 4 (the same seats) | found: 3 · confirmed: 2 · refuted 1; both were one-sentence wording fixes (the sidecar's readers, the hook's median threshold) | method: re-verification of the ledger plus one hop | working tree |
| 4 | 2 (slice A Opus, slice B Sonnet; the ledger rows A-O29, A-O30, B-S7) | found: 0 · confirmed: 0 · 3 of 3 ledger rows NOW_FALSE | method: re-derivation — the seats re-verified their rows by execution; the orchestrator re-derived all 42 `path:line` anchors in both documents at HEAD (all resolve; `mail.py:2245` is `def list_msgs`), the 8 cited D-ids (all present in `docs/DECISIONS.md`) and the fabrik-lib owner roster (3 owners: dev1 22, dev2 30, sentinel 21 modules) | 65135ee5 / d77336b1 before this ledger and the Status flips |
| 5 | 2 finders + 2 refuters (slice A Opus, slice B Sonnet) over the design-approval panel's fold: both panel seats returned sound-with-changes (Opus: `--to-agent map`, no re-send, answered-by measure, a non-hub sender path rule, sentinel agreement as the one fabrik-lib precondition; Fable: the pilot in the build, a fail-open guard, a deferrable tie-break) | found: 14 · confirmed: 11 distinct (B-S1, B-S2 duplicate A-O4; B-S3 duplicates A-O8) · all inside the fold: reply scope across mailboxes, switch shipped inside the commit, deferral condition, the `explicit` predicate, the `from_repo` source, `map` off-hub, the measure's bias, kaizen's review step, fail-open wording, the header predicate, absolute paths | method: re-verification of the fold plus one hop, executed against the pinned `scripts/mail.py` | 0c495fdd / ec599610 |
| 6 | 2 (the pass-5 seats on their own ledgers; the scope-growth exit: the fixed set alone) | found: 0 · confirmed: 0 · 14 of 14 ledger rows NOW_FALSE | method: re-derivation — each seat re-ran its pass-5 commands on the pass-6 pin, executing `_safe_agent` on the pinned module for A-O4 and A-O6 | 70f2ad28 / e82c1c4e before this row |

The run record's round 4 was recorded with the wrong class names (`wording,cross-ref` for `sidecar-readers`) and slice A as 1/1 for 2/2; both were corrected in the record by hand, noted in its `swept_correction` field.
