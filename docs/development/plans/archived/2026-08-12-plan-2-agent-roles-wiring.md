# Plan — Hub agent-roles wiring (charters · role hook · catalog ownership · mail beat · flywheel)

Status: EXECUTED 2026-08-12 (final commit 25645c73 + Finish; gate success 46/0 fresh in the
finishing turn. Whole-plan review: docs/development/reviews/2026-08-12-plan-2-agent-roles-wiring-review.md
— 13 rounds, closing round found: 0, fixed: 0)
Date: 2026-08-12
Owner: infra session (operator-approved: spec r2 CONVERGED 13d86c55; "can you proceed to
/fabrik-plan-after-chat now?" = the go)

## What we already agreed

- **Spec (source of truth, INHERITED):** `docs/superpowers/specs/2026-08-12-hub-agent-roles-design.md`
  (r2 CONVERGED, md5 cdd71e2e). Roles infra/fleet/intel; soft beats + hard addresses; kaizen binding
  for infra+fleet with intel as non-author auditor; mail on infra's beat; fleet owns scaffolding
  (`templates/governance/` carve-out); intel = kilo-benchmarks beat until the `/opt/ai-model-catalog`
  extraction completes + persistent reviewer/floater; `Agent-Name` trailer (never new `Agent-Role`
  values); charters/kaizen logs in allowlisted `docs/reference/agents/`; NO fabrik-mail
  sub-addressing (Layer-2 native messaging is the intra-repo channel — feature-flag still off
  server-side as of today, so charters cite the shared inbox as fallback until the probe passes).
- **Operator decisions this conversation (verbatim-anchored):** "fix the 3 defects first then
  resuggest agent distinction" → DONE pre-plan (258e8086); flywheel stays, intel-owned ("if we use
  it, intel might be responsible of it"); scored-rate leak: auto-0 + metric + WARN-first ("what
  should we do about this?" → my 3-layer answer, unopposed); kaizen cadence = Monday after the
  weekly cron batch (suggested-unopposed); intel dispatcher lane = DEFERRED until a real epic queue
  exists (recorded, not built).
- **Queued findings this plan lands (all claimed or claim-on-execute):** mail digest sys.path
  (fleet's 01KZTMZ193HTV6P3SGNKB8NVJW — accepted by infra in-thread); mail.py re-fork
  (fabrik-lib's 01KZTKMFQN6EH5X4JECQTPQZX1); claim verb (fabrik-lib's 01KZTGCCZHDPF2VY3GGPJ4KJYY).
- **Intel's flywheel analysis (operator-relayed, VERIFIED by query this session):** the 30% is
  three problems — a dead 07-18 bulk block (2,727 rows, 0%, one project one day; excluded ⇒ real
  rate 52.2%), the done-row back-fill asymmetry (2,413 @ 40.9% — the real leak), and the ~274
  mechanically-failed rows (the auto-0 target). Adopted: honest scoping (C4), the structural
  round-close + gate escalation (C4b), data-side work split to intel.
- **Rejected:** hard permission walls; `fabrik/<role>` mail sub-addressing; a 4th "review" seat;
  gate-enforced beats; per-call budget caps on the pool.

## CONSTRAINTS DIGEST (rule-grounding gate)

| rule | pack:line | implication here |
|---|---|---|
| pool-default for gradeable fan-out; `fanout` auto-records; `set_quality` back-fill owed; never hand-roll `run_agents`+`record_run` (silently no-ops) | core/62-using-subagents.md § Dispatch policy | Phase C's flywheel change must keep `record_agent_run` the only write wrapper; review/test fan-outs in every phase name pool-default |
| watched-fail-first for every non-trivial behavior; test-per-behavior, lean | core/45-testing-strategy.md § Behavior Contract | every new verb/field/hook behavior below carries a red-first test |
| no hardcoded hosts/secrets; `os.getenv` | core/10-python.md | role hook reads `CLAUDE_AGENT` via env only |
| stdout-only output from hooks; no logfiles | core/55-observability.md | `agent_role.py` prints context to stdout, writes nothing |
| Doc Sync Matrix rows are gate-enforced | core/40-documentation.md + CLAUDE.md § Doc Sync Matrix | INDEX rows for every new file; CHANGELOG entry; charters ARE docs |
| `.claude/hooks/` + both hook configs are governance-sync TRIGGERS; `scripts/mail.py` + `.claude/settings.json` ride the synced manifest | CLAUDE.md § Sync-consciousness + `scripts/fabrik_synced_manifest.py:106` | the role hook + settings edit distribute fleet-wide AT COMMIT — unset-env no-op is a fleet invariant, not a nicety; mail.py edits must be correct for all ~46 repos |
| vendored-module fixes are upstreamed, never cross-repo-written | CLAUDE.md HARD STOPS + /fabrik-plan-after-chat § fabrik-lib | the `libs/subagents` auto-0 edit sends upstream-feedback BY MAIL to fabrik-lib |
| 12-Factor: no logfiles (XI) · no startup migrations (XII) · same backing services (X) · no daemons/PID (VIII) | plan-after-chat § Global Constraints | trivially satisfied: docs + small script edits; no services, no containers, no DB schema |
| unconstrained by: chrome-ext/gpu/node/workers/postgres/api-contracts/bootstrap packs | — | no glob match on any touched path (docs, hooks, scripts, libs) |

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| spec r2 (CONVERGED) | roles/beats/addresses/kaizen architecture — this plan implements, never re-designs | `docs/superpowers/specs/2026-08-12-hub-agent-roles-design.md` (13d86c55) |
| `scripts/fabrik_synced_manifest.py` | `.claude/settings.json` (:106) + `mail.py` (:38) + `mail_notify.py` (:110) are fleet-synced | manifest lines read 2026-08-12 |
| `scripts/mail.py` | `_ACK_LINE` :84 (SSOT-derived), requeue strip :295, ack-guard :368, digest lazy `from libs.alerting import send_alert` :418, `main` :425 | read this session |
| `libs/subagents/pg_ledger.py` | `record_agent_run(spec, result, *, quality_score=None, …)` :211 — the ONLY sanctioned write wrapper | read this session |
| `scripts/generate_capability_index.py` | 9-kind enumerators, `_rec()` schema (8 keys), `_ENUMERATORS` map :410-ish; owner field extends `_rec` | authored/extended this session (258e8086) |
| `capabilities.json` | 565 entries / 9 kinds / 0 broken — the ownership base | probed this session (fenced below) |
| `CLAUDE.md:132` | `Agent-Role` value enum is pinned — `Agent-Name` is a NEW row in the same table | read this session |
| `.claude/hooks/session_orient.py` | the SessionStart-hook shape `agent_role.py` mirrors (fail-open, stdout, exit 0) | exists; registered in `.claude/settings.json` SessionStart |
| fabrik-lib verdicts (spec §) | role hook = build in-repo · claim verb = enhance hub `mail.py` · fan-outs = vendored `subagents` | spec table, consulted 2026-08-12 |
| `pyproject.toml:55-61` + `final_gate.py:352-362` | hub ruff line-length 100 vs project default 88; formatter is diff-scoped by design — the re-fork fix is gitignore-block repair, never format chasing | read this session |
| `fabrik_synced_manifest.py:146-186` + `sync_enforcement_to_projects.py:118` | `gitignore_block_text()` already lists `scripts/mail.py`; `patched_gitignore` is THE single repair path | probed this session (fenced below) |
| Layer-2 probe result | native cross-session messaging OFF server-side today (empty `/run/user/1000/cc-socks/`, no ListAgents tool, kill-switch envs clean, CC 2.1.228) | probed this session |

## Global Constraints

- `.claude/hooks/` + `.claude/settings.json` edits distribute fleet-wide at commit (governance-sync
  trigger + manifest). The role hook MUST: exit 0 always, print nothing when `CLAUDE_AGENT` is unset
  or names no charter file, never read outside the repo, stdout only.
- `scripts/mail.py` is manifest-synced: every edit must be correct for all ~46 repos. Project
  copies are protected from local reformatting by the generated `.gitignore` synced block
  (diff-scoped formatters never see gitignored files) — C1 repairs the stale blocks; never chase
  format fixpoints across differing ruff configs (hub 100 vs default 88, probed).
- The five shared-append governance surfaces (CHANGELOG/INDEX/docs README/FEATURES/LESSONS_LEARNT)
  are edited per the shared-tree rules, never listed in File Scope.
- No new deps; no `pyproject.toml`/`requirements.txt` edits. No services, containers, ports, or DB
  schema — 12-Factor rows II/V/VI/VII/VIII/IX/X/XI/XII are structurally untouchable here.
- Commits: explicit pathspecs + provenance trailers (this plan's commits add `Agent-Name: infra`).
- Charters are overlays; CLAUDE.md is never forked (one added table row + one § Pipeline-adjacent
  pointer line ONLY).

## Phase A — Identity: charters, kaizen logs, role hook, trailer row — ✅ EXECUTED 2026-08-12 (e8b24ea1 + 95f96a4d, f4fef9c0, e7461a24; review: 3 rounds to QUIET)

Interfaces — Produces: `docs/reference/agents/{infra,fleet,intel}.md` (charter format: H1, Mandate,
Beat table, Kaizen §, Escalation, mail-is-data rule — ~40 lines each);
`docs/reference/agents/kaizen-log-{infra,fleet}.md` (one metric table header + row-0);
`.claude/hooks/agent_role.py` (reads `CLAUDE_AGENT`, prints `## AGENT ROLE: <name>` + the charter
body inside a delimiter, exit 0 always); `.claude/settings.json` SessionStart entry;
`CLAUDE.md` `Agent-Name` trailer row. Consumes: spec r2 role table verbatim.

1. Write the three charters from the spec's role table + conversation decisions (intel's includes:
   flywheel ownership — `subagent_runs` + `rank_task_subagents.py` + selection docs — the
   scored-rate metric `scored/total trailing-14d`, and the extraction hand-off note). Kaizen
   cadence line: "Monday, after the weekly cron batch." Each charter carries the Layer-2 status
   line: "native messaging pending the server-side flag — until the ListAgents probe passes, the
   shared claim-once inbox is the intra-repo queue."
2. Kaizen-log stubs: the 5-metric table header (infra/fleet variants per spec § kaizen) + a row-0
   dated 2026-08-12 with baseline values marked `—` (first real pass fills them).
3. **Red-first:** `tests/test_agent_role_hook.py` — behaviors: (a) `CLAUDE_AGENT=infra` → stdout
   contains `AGENT ROLE: infra` + charter text; (b) unset → EMPTY stdout, exit 0; (c) bogus value
   (`CLAUDE_AGENT=xyz`) → empty stdout, exit 0 (fleet-safety — projects have no charters);
   (d) charter file missing → empty stdout, exit 0. Watch all four RED (hook not yet written) →
   write `.claude/hooks/agent_role.py` (mirror `session_orient.py`'s fail-open shape; resolve the
   charter at `docs/reference/agents/<name>.md` RELATIVE to `CLAUDE_PROJECT_DIR`) → green.
4. Register in `.claude/settings.json` SessionStart (after `session_orient.py`, before
   `mail_notify.py`); 10s timeout, statusMessage "Loading agent role charter...".
5. `CLAUDE.md`: add `| Agent-Name | infra · fleet · intel | hub sessions once the operator sets CLAUDE_AGENT |`
   to the provenance table (:132 region).
6. Docs: INDEX.md rows for the 6 new files; CHANGELOG entry (plan-scoped, appended at Phase C).
7. Gate: `python -m pytest tests/test_agent_role_hook.py -q` → all green; then
   `python scripts/enforcement/check_doc_sync.py` quiet for this phase's triggers.
8. `/fabrik-review` on Phase A's changed surface — BLOCKING, run to its coverage-adjudicated exit
   (pool finders + a native non-author closer; every class CLEAN/FIXED/REFUTED; the pass that fixed
   anything is never the last look).
9. Commit Phase A (explicit paths + trailers incl. `Agent-Name: infra`). Sync-consciousness: THIS
   commit fires governance-sync (hooks + settings touched) — verify post-commit that one project
   copy carries the hook and behaves as no-op (probe: `CLAUDE_AGENT= python3
   /opt/tryton-crm/.claude/hooks/agent_role.py` → empty, exit 0).

## Phase B — Catalog ownership: the `owner:` field — ✅ EXECUTED 2026-08-12 (c56bc175 + 495039f6, bc90dc1c, 5acb1850; review: pool + 4 native rounds to QUIET; census infra 290 · intel 105 · fleet 105 · external 66 · unassigned 0)

Interfaces — Consumes: Phase A charters (the mapping mirrors their beat tables). Produces:
`owner` key in every `capabilities.json` entry + an Owner column in `docs/CAPABILITIES.md`;
`_OWNER_RULES` mapping in `generate_capability_index.py` (kind+path-prefix → role, first match
wins, fallback `"unassigned"`).

1. **Red-first:** extend `tests/test_generate_capability_index.py` — behaviors: (a) every entry
   carries `owner` ∈ {infra, fleet, intel, external:fabrik-lib, unassigned}; (b) spot-anchors:
   `mail_notify.py` hook → infra; `fabrik scaffold --type python-api` → fleet;
   `scripts/kilo-benchmarks/…` script → intel; a `lib-module` → `external:fabrik-lib`;
   (c) an entry matching no rule → `unassigned` (fixture with a synthetic kind);
   (d) `docs/CAPABILITIES.md` renders the owner column. Watch RED → implement `_OWNER_RULES` per
   spec Wiring 5 (kind-level defaults + path-prefix overrides for scripts:
   enforcement/sysadmin/utils/probes/aro-wake/bootstrap/audit → infra · kilo-benchmarks → intel ·
   remainder scripts → infra default with named fleet exceptions e.g. deploy-facing) → green.
2. Regenerate artifacts; assert `unassigned` count in the fresh run is REPORTED (stdout line
   `owners: … unassigned: N`) — N>0 is expected initially and is intel's kaizen WARN signal, not a
   gate failure.
3. Docs: INDEX.md capability rows gain "owner-attributed"; `docs/CAPABILITIES.md` auto-regen.
4. Gate: `python -m pytest tests/test_generate_capability_index.py -q` green +
   `python scripts/generate_capability_index.py --check` exit 0.
5. `/fabrik-review` on Phase B's changed surface — BLOCKING, coverage-adjudicated exit (same shape
   as Phase A step 8).
6. Commit Phase B (explicit paths + trailers).

## Phase C — Mail beat + flywheel record layer — ✅ EXECUTED 2026-08-12 (33c3dad7, e1027a00, ed9a712f, 6ab199ef, 394e96a2, 86223d3d; review: pool + 5 native rounds to QUIET — the resolve converged to unified per-process rename-locked windows)

Interfaces — Consumes: `_ACK_LINE`/DISPOSITIONS SSOT (`mail.py:56-84`), `record_agent_run`
(`pg_ledger.py:211`). Produces: `mail.py claim <id>` verb (rename-only inbox→archive lock, NO
acked-by line; `ack` keeps append semantics; `requeue` continues stripping); digest that actually
alerts; repaired project gitignore blocks (the re-fork cure); auto-0 quality for
mechanically-failed pool runs.

1. **mail.py re-fork adjudication (root cause PROBED at plan time, decision recorded):** the
   format-fixpoint idea is DISPROVEN — hub ruff is line-length 100 (`pyproject.toml:57`),
   fabrik-lib runs default 88, and one file cannot be format-stable under both. The REAL
   mechanism: `run_formatting_fixes` is diff-scoped by design (`final_gate.py:352-362` — correct,
   untouched), and `fabrik_synced_manifest.gitignore_block_text()` ALREADY lists
   `scripts/mail.py` — but fabrik-lib's `.gitignore` block is STALE (0 hits for even
   `scripts/final_gate.py`), so synced scripts enter their diffs and get project-config-formatted.
   Fix = repair, not code: (a) probe why the block is stale on affected nodes (sync target set /
   last `patched_gitignore` run — self-service); (b) run
   `python scripts/sync_enforcement_to_projects.py --force` (the CLAUDE.md-sanctioned
   distribute-NOW path — `patched_gitignore` is THE single repair code path,
   `sync_enforcement_to_projects.py:118`), which also restores canonical `mail.py` bytes over
   their reflow; (c) verify probe: `grep -c "scripts/mail.py" /opt/fabrik-lib/.gitignore` → ≥1
   (same for one more project); (d) IF probing reveals a code defect in the sync's gitignore
   repair path, fix it red-first in `sync_enforcement_to_projects.py` (already fleet-synced
   surface — in File Scope). Reply the disposition to fabrik-lib's 01KZTKMFQN… by mail.
2. **Red-first — claim verb:** tests: (a) `claim <id>` moves inbox→archive WITHOUT an acked-by
   line; (b) second `claim` of the same id fails loudly (file gone — the rename IS the lock);
   (c) `ack` on a claimed (archived) id appends the disposition line in place; (d) `requeue` of a
   claimed-then-requeued message carries no stale marker (existing `_ACK_LINE` strip covers it —
   regression row). Watch RED → implement (reuse the ack rename path minus the line-append; SSOT
   untouched) → green.
3. **Red-first — digest alert leg:** test: run `python scripts/mail.py digest` with cwd=repo-root
   and `PYTHONPATH` UNSET, monkeypatched `libs.alerting.send_alert` import — assert the import
   resolves (repo-root inserted on `sys.path` before the lazy import at :418) instead of
   `ModuleNotFoundError`. Watch RED → insert the two-line root-insert guard → green. Reply
   disposition to fleet's 01KZTMZ19… by mail.
4. **Red-first — flywheel auto-0 (honestly scoped per intel's verified analysis):** targets
   error(157)+capped(117)+empty-output rows ≈ 274 all-time — correct and cheap, NOT the headline
   fix. Test in a new `tests/test_pg_ledger_auto0.py` (hub-side, no DSN needed — assert via the
   JSONL outbox path): a result whose `status` is errored/capped OR whose `text` is
   empty/whitespace records `quality_score=0.0` when the caller passed `None`; a healthy result
   with `quality_score=None` stays `None` (unscored ≠ bad). Watch RED → implement in
   `record_agent_run` (the wrapper — never the raw `record_run`) → green. **Upstream-feedback by
   mail to fabrik-lib** (`--kind upstream-feedback`): the auto-0 diff + the fanout scorer-handle
   proposal (fanout returns a handle the merge step must consume — the module-side half of the
   asymmetry fix; canonical module is theirs, never write into `/opt/fabrik-lib`).
4b. **Red-first — the STRUCTURAL fix (the real leak: done-rows never back-filled — dispatch is
   guaranteed, scoring is best-effort; verified: done=2,413 @ 40.9%):** two machinery edits on
   infra's beat: (i) `commands/_sources/fabrik-review.md` — the round-close contract gains a
   REQUIRED step: "back-fill `set_quality` for every pool row this round dispatched — a round
   with unscored pool rows is NOT closed" (same rank as the refute step); re-render the corpus
   from merged master post-commit (§ Merge-time render — never from a worktree). (ii)
   `scripts/enforcement/check_subagent_flywheel.py` — escalate WARN → session-scoped ERROR: the
   CURRENT session's ledger rows unscored and older than 30 min red the gate (fleet-synced
   surface; red-first test in the check's existing test file or a new
   `tests/test_check_subagent_flywheel.py`; intel's own two leaks today are the evidence the WARN
   doesn't bite). Historical data work is explicitly NOT this plan's: the 07-18 dead block
   (2,727 rows, one project, one day — verified) adjudication + intel's own 21-row back-fill are
   INTEL's, on the analytics DB (their beat); the plan's trailing-14d metric is immune to the
   block by construction.
5. Docs: CHANGELOG entry (whole plan, one entry); `docs/reference/fabrik-mail.md` § verbs gains
   `claim`; INDEX row for the new test file; intel charter already carries scored-rate (Phase A).
6. Gate: `python -m pytest tests/test_mail.py tests/test_mail_notify.py
   tests/test_pg_ledger_auto0.py tests/test_check_subagent_flywheel.py -q` green.
7. `/fabrik-review` on Phase C's changed surface — BLOCKING, coverage-adjudicated exit (same shape
   as Phase A step 8).
8. **Final whole-plan step:** `python scripts/final_gate.py --check --json` → `"status":"success"`
   + `python scripts/enforcement/check_convergence.py` green + `/fabrik-docs-review` scoped to the
   plan's doc delta. A green gate is necessary, not sufficient — the Evidence below is the proof.
9. Commit Phase C; push; whole-plan review artifact
   `docs/development/reviews/2026-08-12-plan-2-agent-roles-wiring-review.md`; flip EXECUTED citing
   it; release the plan lock.

## Execution notes (subagents + parallelism)

Pool-default for the gradeable work in every phase: test-authoring and doc-reconcile units via
`fanout("code"/"docs", …)` (auto-records; `set_quality` back-fill owed per unit), finders in every
`/fabrik-review` via the pool + ONE native non-author closer (the review floor). Native (this
session) owns: charter prose (design-heavy governance voice), the settings/CLAUDE.md edits (synced
surfaces), decide/refute/merge. Phases are SEQUENTIAL (A→B→C: B's mapping mirrors A's charters;
C replies to findings A's charters cite); INSIDE each phase the test-units and doc-units fan out in
parallel (disjoint files). Merge/dedupe happens in this session at each phase's step-before-review.

## File Scope (owned paths)

- docs/development/plans/2026-08-12-plan-2-agent-roles-wiring.md
- docs/development/reviews/2026-08-12-plan-2-agent-roles-wiring-review.md
- docs/reference/agents/infra.md
- docs/reference/agents/fleet.md
- docs/reference/agents/intel.md
- docs/reference/agents/kaizen-log-infra.md
- docs/reference/agents/kaizen-log-fleet.md
- .claude/hooks/agent_role.py
- .claude/settings.json
- CLAUDE.md
- scripts/generate_capability_index.py
- tests/test_generate_capability_index.py
- tests/test_agent_role_hook.py
- scripts/mail.py
- scripts/sync_enforcement_to_projects.py
- commands/_sources/fabrik-review.md
- scripts/enforcement/check_subagent_flywheel.py
- tests/test_check_subagent_flywheel.py
- tests/test_mail.py
- libs/subagents/pg_ledger.py
- tests/test_pg_ledger_auto0.py
- docs/reference/fabrik-mail.md
- docs/CAPABILITIES.md
- capabilities.json

## Evidence

Phase-A grounding (all read this session, 2026-08-12):
- `.claude/settings.json` SessionStart chain (final_gate_stop --baseline → session_orient →
  mail_notify) — the role hook slots third; `scripts/fabrik_synced_manifest.py:106` lists
  `.claude/settings.json` (fleet distribution is a FACT, not a risk guess).
- `CLAUDE.md:132` — `| Agent-Role | primary · orchestrator · subagent · review-fix | every AI commit |`
  (the pinned enum the new row must not touch).

Phase-B grounding:
```
$ python3 -c "import json,collections; d=json.load(open('capabilities.json')); \
  print(len(d['capabilities']), dict(collections.Counter(c['kind'] for c in d['capabilities'])))"
565 {'cli': 55, 'driver': 27, 'registrar': 10, 'script': 309, 'lib-module': 66,
     'scaffold': 11, 'rules-pack': 56, 'hook': 4, 'command': 27}
```
- `generate_capability_index.py` `_rec()` 8-key schema + `_ENUMERATORS` map — the owner key is a
  9th `_rec` field, one mapping table, no enumerator changes.

Phase-C grounding:
- `scripts/mail.py:84` `_ACK_LINE` (SSOT-derived), `:295` requeue strip, `:368` ack-guard, `:418`
  lazy `from libs.alerting import send_alert` (the exact ModuleNotFoundError site fleet reported),
  `:425` `main` (argparse verbs — `claim` joins send/list/read/ack/requeue/digest).
- `libs/subagents/pg_ledger.py:211` `record_agent_run(spec, result, *, quality_score=None, …)` —
  the wrapper docstring itself warns raw `record_run` silently no-ops; auto-0 lands in the wrapper.
- Flywheel leak measurement (drives the auto-0 + metric):
```
$ SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics … SELECT count(*) FROM subagent_runs …
rows/min/max: (6282, 2026-07-06, 2026-08-12) · scored: 1857 · last 14d: 880
```
- Flywheel decomposition (drives C4/C4b — intel's numbers verified):
```
$ SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics … GROUP BY status …
(empty) 2727 0.0% · done 2413 40.9% · scored 860 100% · error 157 1.9% · capped 117 3.4%
empty-status block: (2727, 2026-07-18, 2026-07-18, 1 project) · last 7d: 0 · excl-rate: 52.2%
```
- Re-fork root cause (drives C1):
```
$ .venv/bin/ruff format --check --isolated scripts/mail.py   → Would reformat (default 88)
$ .venv/bin/ruff format --check scripts/mail.py              → already formatted (hub 100)
$ python3 -c "…gitignore_block_text()…"                     → 'scripts/mail.py' in block: True
$ grep -c 'scripts/final_gate.py' /opt/fabrik-lib/.gitignore → 0   (stale block = the leak)
```
- Layer-2 probe (drives the charters' fallback line):
```
$ ls -la /run/user/1000/cc-socks/   → empty (no session bound an inbox socket)
$ echo "${CLAUDE_CODE_MESSAGING_SOCKET:-EMPTY}"  → EMPTY   (CC 2.1.228; kill-switch envs unset)
```

## Self-audit

- (a) Coverage vs "What we already agreed": charters+stubs → A1-2; role hook+settings → A3-4;
  trailer row → A5; owner field → B; claim verb → C2; digest fix → C3; re-fork adjudication → C1;
  auto-0 + scored-rate → C4 + A1(intel charter); Layer-2 fallback → A1 charter line + probe
  evidence; cadence + dispatcher-lane defaults → recorded in charters/Residuals. No gap found.
- (b) Cross-phase signatures: `_OWNER_RULES` (B) mirrors the charter beat tables (A) — names match
  the spec role table verbatim; `claim` (C2) reuses the ack rename path (grounded :368 region);
  no phase consumes a symbol another phase renames.
- Grounding passes: manifest/sync surfaces read; mail.py verb internals read; pg_ledger wrapper
  read; catalog schema authored this session; Layer-2 probed live; flywheel DB queried live.
- Not yet a fixed point — `/fabrik-plan-review` owns convergence.

## Residual unknowns

- RESOLVED: all three queued findings have named landing steps (C1/C2/C3); sync blast radius is a
  grounded fact with a fleet no-op probe (A9); kaizen cadence + dispatcher lane defaulted by
  operator-unopposed suggestion (charters record both; overridable one-line).
- OPEN (self-service): the exact `unassigned` count after B2 — the run reports it; intel's first
  kaizen pass consumes it (no operator stop needed).
- OPEN (external, non-blocking): the Layer-2 server-side flag — charters carry the fallback; the
  ListAgents probe is re-run at each session start until it passes (no plan step blocks on it).
- OPEN (spec-r3 refinements, recorded per the Phase B review adjudication): P4 — `cli → fleet`
  blankets 55 verbs including `fabrik dev`/`fabrik review`/`fabrik ai usage`, which the charters
  place nearer infra's beat (per-verb attribution when it matters). P6 — `docs/CAPABILITIES.md`
  renders `(owner: …)` only for `status == "ok"`, so the 189 broken/retired/manual entries — the
  defect-triage set where ownership matters most — carry no owner in the human-facing catalog
  (the JSON is complete; a triage-doc owner column rides `audit_capability_docs`). H6 — a
  `_OWNER_PATH_PREFIXES` tier for un-catalogued beat surfaces (`templates/`, `docs/*.md` beats).
