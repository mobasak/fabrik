## RESUME

Item: W-5dcafaef (spoke watchdogs alert through a mesh-only Apprise gate). Plan:
docs/development/plans/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate.md (Status: IN-PROGRESS), next is
Phase C of 3, step 1. Lock: .fabrik/plan-locks/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate.json (active).

Parked 2026-10-23 at the AMBER quota band (weekly, fleet-wide): Phase C step 1 is the heavy whole-plan
`/fabrik-review`, which AMBER forbids starting.

Done:
- Phase A EXECUTED: d25b23f8d, 3b833320d (review fix: preflight after the driver import guard), marker 0c20ec359.
  /fabrik-review-scoped 2 rounds, confirmed 1 → 0.
- Phase B: 63e5cf810 plus the CHANGELOG tense fix; its /fabrik-review-scoped closed on round 2 (see the plan's
  Phase B marker for the commit list).
- PORTS.md: intel released it from plan 3's lock (e6f0a0e31 on worktree-intel, by message 2026-10-23).

PAUSED 2026-10-24 ~15:00 (operator: "pause all agents gracefully, i need quota for web development now.") inside
step 1, the Finish /fabrik-review. Pass 1 DONE: 7 seats (A infra.py+watchdog.py opus/sonnet/haiku · B 3 tests
sonnet/haiku · C compose/gatus/spec/3 docs sonnet/haiku), pin pins-1 at f2637dde1 in
/opt/fabrik/.tmp/runs/efaa87a3-20bc-417a-bfd8-a847b87cd09c/fabrik-review-2026-10-24T12-00-26-0300, ~30 raw, 6
confirmed, all FIXED in the wip(pause) commit (uncommitted-review fixes, to re-verify):
- F1 (A-haiku): `_watchdog_uses_claude` raised AttributeError on a non-mapping `watchdog:` (escaped provision()); now
  defaults. Grader test_a_non_mapping_watchdog_block_never_escapes_the_registrar, red before the fix.
- F2 (B-sonnet/B-haiku): primary openrouter + fallback claude-code untested → test_either_claude_code_lane_runs_the_preflight.
- F3 (B-haiku): duplicate-line preflight output untested → 2 parametrize rows.
- F4 (B-haiku): sidecar env WATCHDOG_APPRISE_URL unasserted → test_watchdog_driver mesh test.
- F5 (B-sonnet, A-opus C7): the remote shell string never executed → test_the_preflight_command_runs_under_sh_and_its_output_parses.
- F6 (C-haiku): 5 doc rows read as live → "pending the W-5dcafaef deploy" (drop at step 9, below).
Mutation battery (throwaway worktree): 8 mutants M1-M8 all red (fallback arm, set compare, gate count, unquoted $f,
unquoted paths, gate braces, non-dict guard, env key); baseline 42 passed.
REFUTED: ctx/spec target disagreement (orchestrator/__init__.py:162, :537 always set ctx.target_vps); "VPS1" case
(spec_loader.py:980 pattern ^vps[1-9][0-9]?$). RECORDED: apprise_url rewrite boundaries (https kept, no-path,
userinfo, other paths) unreachable today — WatchdogConfig is extra="forbid" with no apprise_url; owner = whoever adds
WatchdogConfig.apprise_url (use urlsplit + require the gate URL on a spoke). Gate probe is host-namespace TCP only
(deploy probe 1 from a vps2 container covers the container path). openrouter-only sidecar still mounts the Claude
files (pre-existing driver). Spec text stale on preflight placement and error format (plan :117 records it).
/healthz never touches upstream and limit 503 not 429 (spec design). DOCKER-USER list lacks 8202 → W-2ce2df52.
Gate image tag-only (apprise itself :latest). Gatus mesh-form healthz → plan step 6 probe 4 owns the fallback.
RESUME: re-open /fabrik-execute-plan (phase 3) + /fabrik-review, re-pin to a NEW dir at the wip commit, run the
closing pass = the round-1 seats per slice over the fix hunks + one hop (slice A open: F1; B: F2-F5; C: F6), record
rounds, then fill the receipt docs/development/reviews/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate-review.md.

Next, in order (plan § Phase C):
1. Finish `/fabrik-review` over `0a398d12e..HEAD`, receipt at
   docs/development/reviews/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate-review.md.
2. `/fabrik-docs-review` over the doc surface — add docs/SERVICES.md (edited in Phase B, not in the plan's File
   Scope: the doc-sync matrix required it) and docs/infrastructure/vps-complete-inventory.md (lists vps1's running
   containers; gains the gate only after the deploy).
3-4. Ledgers + `check_doc_sync.py --range`, `final_gate.py --check --json`, `check_convergence.py`; push.
5. The deploy gate: DECISION NEEDED (ground: gate) to the coordinator by SendMessage; close `handoff`.
6. After the go — two additions from Phase B's review (Opus seat), both cheap probes:
   - first `docker compose version` on vps1 must be ≥ 2.23.1 (top-level `configs:` with `content:`), and
     `docker compose config` must render the gate conf with single `$`; else stop (fail-closed);
   - the U4 attachment-lock probe also tries JSON `{"body":"x","attachment":"http://apprise:8000/"}`, JSON
     `attach`, form `attachment=`, and a multipart file part — every one must be non-2xx.
7-10. As the plan says. At step 9, once the acceptance passes, drop the "pending the W-5dcafaef deploy" markers
   (PORTS.md apprise + 8202 rows, docs/infrastructure/vps-urls.md :149/:171/:297, docs/SERVICES.md vps1 row) in the
   deploy-evidence commit (Finish review pass 1, C-H2).

Not this item: the bootstrap template's explicit DOCKER-USER port list (scripts/bootstrap/bootstrap-config.sh
FABRIK_MESH_ONLY_PORTS) lacks 8202 while live vps1's chain is default-DROP (spec :112) — a rebuild-vs-live
drift that belongs to the firewall item W-2ce2df52.
