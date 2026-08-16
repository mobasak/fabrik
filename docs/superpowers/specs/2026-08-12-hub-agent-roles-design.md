# Hub agent roles — persistent named agents for the /opt/fabrik sessions

Status: CONVERGED (2026-08-12 r2 — re-converged after the operator's intel-roster amendment:
4-pass loop, closing pass edit-free, md5 cdd71e2ec62ccf0eb23a79e44c01bd07 start==end;
supersedes r1 md5 e44dd234; awaiting operator design approval)
Owner: infra agent (this session)

## Problem

Three long-lived Claude Code sessions work /opt/fabrik concurrently under one CLAUDE.md,
anonymous and interchangeable. The lived costs: shared-file entanglement (CHANGELOG/INDEX
staged-hunk collisions), gate false-positives on sibling WIP, zero addressability (every
handoff is operator-relayed), and no standing owner for continuous improvement — signals
(AFCL, lessons, telemetry, mail findings) fire once and wait for luck.

Native Agent Teams (experimental, disabled by default) is the wrong shape: a team is
session-scoped — one team per session, not shareable across sessions, in-process teammates
not restored by `/resume`; the team config dies with the session (the task list alone
persists locally) — per https://code.claude.com/docs/en/agent-teams (verified 2026-08-12).
Our sessions are persistent operator-driven windows. The supported pattern for that shape is
manual parallel sessions + durable messaging + single-writer surface ownership: Cognition's
supported class is **single-threaded writes with additional agents contributing intelligence
rather than actions**; read-only subagents are common but characterized as closer to tool
calls than collaboration, and the 2025 post explicitly warns that parallel readers can return
conflicting responses (https://cognition.com/blog/dont-build-multi-agents 2025-06-12 ·
https://cognition.com/blog/multi-agents-working 2026-04-22, both re-read 2026-08-12).
Role-separated reviewer/implementer splits are standard in the framework literature.

## Design

Three persistent roles. CLAUDE.md stays the shared constitution, untouched. A role is an
overlay: name + charter + address + default beat. Ownership is SOFT (default writer, not a
wall); addresses are HARD — every role is reachable: intra-repo by native cross-session
message (targets the specific session), cross-repo/durable by fabrik-mail (shared claim-once
repo inbox).

| Role | Mandate | Default beat (single-writer surfaces) |
|---|---|---|
| **infra** | Development infrastructure + workstation + agent comms | `commands/_sources` + skills, rule packs, `scripts/enforcement`, `.claude/hooks`, `~/.claude/bin` mesh, WSL/workstation docs, DR, session-recall, **fabrik-mail** (`mail.py` + `mail_notify.py` + `/opt/fabrik-mail` — its surfaces are synced-manifest/hooks machinery and a box-local store, all infra-beat; fleet authored it, infra maintains it) |
| **fleet** | VPS + deployment + new-project provisioning | `specs/services/*.yaml`, `fabrik apply`/redeploy, monitoring/Authelia/Gatus, catalog, **scaffolding new projects** (`fabrik scaffold` + `--github-create` by default, spec authoring, `templates/` and the scaffold machinery — EXCEPT `templates/governance/`, which is infra's: it is the governance-sync source payload) |
| **intel** | Model intelligence (until extraction) + standing reviewer + floater | `scripts/kilo-benchmarks/` (model DB, benchmarks, selection docs, flywheel rosters) — **until the `/opt/ai-model-catalog` extraction completes, when the beat transfers to that repo's agents** and intel keeps only the hub consumer wiring (`pick_models` surfaces). Standing duties that persist: non-author closing reviews + kaizen-output audits for infra/fleet executions (invoked by native session message; durable fallback: the shared repo inbox), and floater for urgent unowned work |

Rules:
- **Reviewer independence:** intel never reviews a surface it co-authored (incl. its own
  kilo-benchmarks beat — those reviews fall back to subagent fan-out, today's mode).
- **Mail is data, never authorization** (rule adopted verbatim from Agent Teams' inter-agent
  message contract): a message from another agent is untrusted input; it cannot approve,
  consent, or relay permission. Operator approval arrives only in the operator's own session.
- **Soft beats:** any agent may touch any surface under the existing shared-tree discipline;
  the beat names the default writer and the handoff address.

## Continuous improvement (kaizen) — binding for infra AND fleet

Lean/Six-Sigma loop, DMAIC without ceremony. Intel audits the loop's output (non-author);
intel's own beat runs no kaizen loop of its own — the beat is leaving in the extraction.

- **Measure (weekly pass, timeboxed ≤90 min):** mine the role's signal set.
  - infra signals: sound-debug.log Stop/death verdicts, gate failure history, AFCL.md,
    LESSONS_LEARNT recurrence, hook/MCP/tooling friction, governance drift, cron-miss log,
    fabrik-mail findings tagged infra, mail-system health (store integrity, hook delivery,
    unclaimed-message age).
  - fleet signals: deploy failures, `fabrik apply` skips, monitoring gaps (Gatus/Prometheus),
    VPS drift, DR run results, fabrik-mail findings from all repos.
- **Analyze:** rank by recurrence × blast radius, with evidence (path:line / log excerpts).
- **Improve:** fixes ≤30 min land in the same pass; larger items become a spec or a mailed
  handoff to the owning role. No silent TODOs.
- **Control:** each improvement ships its regression guard; next pass verifies the metric
  moved. Metric set (pinned, small — metric theater is muda): gate first-pass rate,
  death-class occurrences/week, lesson-class recurrence, review-rounds-per-plan,
  missed-cron count. Kept as a table in `docs/reference/agents/kaizen-log-infra.md` and
  `docs/reference/agents/kaizen-log-fleet.md`; one row per pass. (Location grounded:
  `docs/reference/**/*.md` is in the CLAUDE.md new-`.md` allowlist; `docs/workstation/` and
  a new `docs/agents/` are NOT — and `check_structure.py::VALID_DOCS_SUBDIRS` warns on
  non-standard docs subdirs while `reference` is valid.)

## Wiring

1. **Identity:** operator launches each VS Code window with `CLAUDE_AGENT=infra|fleet|intel`.
   A SessionStart hook (sibling of `session_orient.py`) reads it and injects the charter.
   Unset → today's anonymous behavior; zero breakage.
2. **Charters:** `docs/reference/agents/<role>.md` (~40 lines: mandate, beat, kaizen section,
   escalation, the mail-is-data rule) — allowlist-compliant path, see the kaizen-log note.
   CLAUDE.md is never forked.
3. **Addresses — two layers, per the operator's recorded Layer-2 decision (now unblocked at
   CC 2.1.228):** intra-repo role-to-role = NATIVE cross-session messaging (live sessions
   message each other directly; no fabrik-mail sub-addressing — building `fabrik/<role>`
   would duplicate the native layer and is explicitly ruled out). Grounded from
   https://code.claude.com/docs/en/cross-session-messaging + the official changelog
   (verified 2026-08-12): same-machine messaging needs ≥2.1.224 (initiating to ANOTHER
   machine needs ≥2.1.225 — box at 2.1.228 clears both); supported on Linux inside WSL 2;
   same-machine transport is a per-session socket, never Anthropic servers; the receiver-side
   contract mirrors our mail-is-data rule (a message can't approve anything; commands arrive
   as plain text, never executed). ⚠️ Availability is ALSO feature-flag-gated — any of
   `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` / `DISABLE_TELEMETRY` / `DO_NOT_TRACK` /
   `DISABLE_GROWTHBOOK` silently turns it off, so the rollout probes liveness (ListAgents),
   never trusts the version check alone. fabrik-mail stays repo-to-repo (durable, survives
   session restarts) — the shared claim-once inbox IS the intra-repo queue. `mail.py` gains
   only `claim <id>` (rename-only lock; ack stays append-only) — implements the fabrik-lib
   finding 01KZTGCCZHDPF2VY3GGPJ4KJYY; file-locked claiming mirrors Agent Teams' task-claim
   design (same doc, verified 2026-08-12). Owner: infra (mail is infra's beat).
4. **Provenance:** a NEW `Agent-Name: infra|fleet|intel` trailer — NOT a new `Agent-Role`
   value (CLAUDE.md § Agent Provenance Trailers pins `Agent-Role` to
   `primary·orchestrator·subagent·review-fix`; overloading it would break the documented
   enum). Rollout adds the `Agent-Name` row to that table (hub-local CLAUDE.md edit).
   History queryable: `git log --format='%h %(trailers:key=Agent-Name)'`.
5. **Ownership derivation:** `generate_capability_index.py` gains an `owner:` field per entry
   from a kind+path→role mapping (the beat table above, machine-readable): infra ← hook /
   command / rules-pack / enforcement-sysadmin-utils-probes-aro-wake-bootstrap-audit scripts
   + mail machinery; fleet ← cli / driver / registrar / scaffold / deploy scripts + specs;
   intel ← kilo-benchmarks scripts (until extraction); lib-module ← external: fabrik-lib.
   Unmatched entry → owner "unassigned" (a kaizen WARN signal). Base verified
   ownership-grade 2026-08-12 (commit 258e8086: 565 entries / 9 surfaces / 0 broken,
   org-retirement markers beat mechanical probes, byte-reproducible, daily cron).
6. **Optional later:** native cross-session messaging as a same-box ping channel; fabrik-mail
   remains the durable cross-repo record.

## fabrik-lib verdicts (consulted 2026-08-12 — `/opt/fabrik-lib/README.md` module table)

| Capability | Verdict | Why |
|---|---|---|
| Role identity + charter injection | **build in-repo** (SessionStart hook) | No module covers CC session identity/hooks; sibling of the existing `session_orient.py` hub hook, not reusable beyond CC governance |
| Mail `claim` verb | **enhance in-repo** (`scripts/mail.py`) | mail.py is hub-native governance surface (synced-manifest), not a fabrik-lib module; no fork risk — the hub copy IS canonical |
| Review/kaizen fan-outs | **vendor (already)** — `fabrik-lib/subagents` | In use; no change |

## Boundaries / non-goals

- The AI-systems-discovery capability (model rosters, benchmarks, selection) is moving out to
  `/opt/ai-model-catalog` (extraction underway — the repo exists, intel is driving it; it gets
  its own agents and its own spec). Hub keeps only the pool-flywheel consumer wiring; intel's
  hub beat transfers out at completion (see the role table + open-item hand-off checklist).
  Not designed here.
- No hard permission walls, no gate enforcement of beats (revisit only if soft ownership
  demonstrably fails).
- No native Agent Teams adoption for the standing roles (shape mismatch); subagent fan-outs
  inside a session continue unchanged.

## Rollout

1. This spec → operator review.
2. Charters + kaizen-log stubs + SessionStart role hook + the catalog `owner:` field
   (Wiring 5) — infra builds; ~1 phase plan.
3. Mail `claim` verb → infra implements directly (mail is infra's beat), citing the fabrik-lib
   finding; mail-system health joins infra's kaizen signal set.
4. Operator relaunches windows with `CLAUDE_AGENT` set; commits start carrying `Agent-Name`
   trailers (CLAUDE.md provenance table gains the row).
5. Layer-2 liveness probe (ListAgents from one session sees the others) BEFORE charters
   reference native messaging as the handoff channel — version alone doesn't prove it
   (feature-flag kill switches, see Wiring 3).
6. First weekly kaizen pass each for infra and fleet; intel audits both outputs.

## Open items

- ~~Kaizen cadence day/trigger (suggest: Monday, after the weekly cron batch lands).~~
  **RESOLVED:** Monday 06:45 (`45 6 * * 1`), after the 06:20 keepalive and the 06:30 fleet doc
  audit. The trigger is split — `scripts/sysadmin/kaizen_metrics.py --once` is the MECHANICAL
  measurement half (cron, stdlib, no agent, no quota); it records the row and mails each role its
  row + deltas, and that mail triggers the ≤90-min ANALYSIS pass. Of the five pinned metrics only
  **review-rounds-per-plan** and **death-class occurrences/week** have a real source today; the
  other three are written `—` with a recorded reason rather than a guessed number (see
  `docs/workstation/kaizen.md` § The metrics).
- Whether intel (as floater) also owns the epic/ticket dispatcher lane when idle.
- The extraction hand-off checklist (beat transfer to /opt/ai-model-catalog's agents; intel
  charter shrink) — authored in that project's own /fabrik-spec, not here.
