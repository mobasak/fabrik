# Plan review — spoke watchdog apprise mesh gate (W-5dcafaef)

**Command:** /fabrik-plan-review
**Surface:** `docs/development/plans/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate.md` (monolith, `Profile: small`)
**Spec:** `docs/superpowers/specs/2026-10-23-spoke-watchdog-apprise-mesh-gate-design.md` (CONVERGED, D-1166; no `Size: small` line, so no joint loop and no panel)
**Decision row:** D-1169 (the CONVERGED flip)
**Seats:** agent-tool (the hub never calls the Workflow tool, D-961); round-1 slices `opus-rule` (header, Global Constraints, Context Ledger, Constraints Digest, File Scope, Coverage Checklist, Evidence, Self-audit, Pass Ledger, Residuals) and `sonnet-phases` (What we already agreed, Intake, Phases A-C)

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (header, Global Constraints, Context Ledger, Constraints Digest, File Scope, Coverage Checklist, Evidence, Self-audit, Pass Ledger, Residuals) + sonnet×1 (What we agreed, Intake, Phases A-C) · all axes · shape: agent-tool (D-961) | found: 21, new: 21, confirmed: 20, fixed: 20, unexecuted: 0, edits: 26 | method: citation — full pass; every candidate executed by the orchestrator (the parse fail-opens re-run as rules2.py, 14 cases; `check_doc_sync.py:393-405` staged mode read; `work.py:6485-6499`; `mail.py:2966-2995`; the missing test path `ls`-ed; the curl image tag probed 200); 1 RECORDED — measured (wording; changes no behaviour: the provider read is the registrar's form of `watchdog.py:521`); flip gates at pass 1 on a flipped copy in a throwaway worktree: `check_convergence` graded it (red only on UNCHECKED rows and no re-derivation row), `check_rule_grounding` 5 CONVERGED in-window plans, 0 findings, `check_plan_quality` 0 findings and red on an Appetite-less mutant | 2a7f0ac3… → 6d251bd2… |
| Pass 2 | the round-1 slice owners (opus×1 + sonnet×1) · their own claims over the pass-1 fix diff + one hop · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — opus slice 8/8 claims re-verified, the v2 probe re-run from the pin (23 of 23 lines identical); sonnet slice 11/12 verified, S9 residue confirmed (own-fix: round 1 — C step 7's kaizen mail cited a merge sha before the merge); RECORDED — measured: probe 3 proves little since the gate binds only 10.99.0.1 (spec `:379` wording, W-2ce2df52); the step-6 Gatus follow-up commit lands after the `--range` doc-sync (trivial); nobody named to resume at step 8 (pre-existing); the probe's vps1-gate-line case keeps the vps2 label (the Phase A test passes `target="vps1"`); the ledger row cannot hold its own file's md5 (by construction) | 95e84baf… → 434d24fe… |
| Pass 3 | sonnet×1 (round-1 owner of the only slice holding an open claim; opus-rule stands at 8/8 from pass 2) · the two pass-2 hunks + one hop · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — S9 re-executed against `merge_request.py:283-292` (the request records the pushed tip); the pins-2 → pins-3 diff is exactly the two hunks (7 lines); the Intake counts (23 · 14 IN · 9 OUT) and Phase C's ten steps re-derived from the pin; standing clean since pass 2: every other class | 2681694c… → 2681694c… ✓ |

## What the review changed

- The preflight parse rule (v2, probed over 14 cases): a missing file no longer hides the gate result, and
  contradictory, duplicated or misplaced lines read as "unexpected output" instead of a pass (fail-open closed).
- The preflight and the driver call both run inside `_host_env(target)`, so a spec-only `target_vps` is probed and
  provisioned on one host.
- Phase C follows the spec's adoption order: the gate is live and probed before the merge request; every deploy probe
  is an exact command with its expected code; a rollback step exists; the U4 stop routes to it.
- Red-on-revert runs on a probe worktree carrying the uncommitted phase; doc-sync runs in staged mode after staging,
  and over the whole plan range at Finish; `work.py done` carries `--evidence`.
- Citation repairs: `30-ops.md:150`, `60-watchdog.md:27`, `watchdog.py:566`/`:568-571`, a `core/40-documentation`
  ledger row, the fleet charter path.

## Recorded, not counted

- Probe 3 (public connect to 8202) proves little, since the gate binds only `10.99.0.1` — the spec's own wording
  (`:379`); W-2ce2df52 owns the firewall scope.
- The step-6 Gatus follow-up commit lands after the Finish `--range` doc-sync — trivial.
- Nobody is named to resume Phase C at step 8 after the merge — the coordinator's relay covers it (pre-existing).
- The probe's "gate line on vps1" case keeps the vps2 label; the Phase A test passes `target="vps1"`.
- The registrar's provider read `(ctx.spec or {}).get("watchdog", {})` is its own form of `watchdog.py:521` (wording).
- One citation reads "ambiguous" to `check_citations_resolve.py` (advisory; every graded citation lands).
