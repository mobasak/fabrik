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
7-10. As the plan says.

Not this item: the bootstrap template's explicit DOCKER-USER port list (scripts/bootstrap/bootstrap-config.sh
FABRIK_MESH_ONLY_PORTS) lacks 8202 while live vps1's chain is default-DROP (spec :112) — a rebuild-vs-live
drift that belongs to the firewall item W-2ce2df52.
