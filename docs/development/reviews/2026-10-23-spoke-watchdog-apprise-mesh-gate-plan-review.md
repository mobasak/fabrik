# Plan review — spoke watchdog apprise mesh gate (W-5dcafaef)

**Command:** /fabrik-plan-review
**Surface:** `docs/development/plans/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate.md` (monolith, `Profile: small`)
**Spec:** `docs/superpowers/specs/2026-10-23-spoke-watchdog-apprise-mesh-gate-design.md` (CONVERGED, D-1166; no `Size: small` line, so no joint loop and no panel)
**Seats:** agent-tool (the hub never calls the Workflow tool, D-961); round-1 slices `opus-rule` (header, Global Constraints, Context Ledger, Constraints Digest, File Scope, Coverage Checklist, Evidence, Self-audit, Pass Ledger, Residuals) and `sonnet-phases` (What we already agreed, Intake, Phases A-C)

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
PASS_ROWS

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
