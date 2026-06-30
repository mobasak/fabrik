# Plan — Watchdog `error_webhook` → `:8889` ingest (build the missing sidecar consumer)

**Status:** PLANNED (ready to implement) — 2026-06-30
**Owner:** operator (single-host WSL dev)
**Repo:** `/opt/fabrik-lib/watchdog` (sidecar) + a small guard in `/opt/fabrik` (orchestrator)
**Origin:** Residual-risks #1/#2 from the Phase 7 adversarial review. Grounding 2026-06-30 found the `:8889` ingest is **entirely unbuilt**, so the apply reminder + docs are now gated to PENDING (commit on master). This plan builds the real consumer so `error_webhook` works end-to-end.

## Problem (grounded)

The fabrik side is complete: `drivers/watchdog.py` sets `WATCHDOG_TRIGGER_SOURCES` (`watchdog.py:709-710`), the spec model allows `error_webhook` (`spec_loader.py:623`), the GlitchTip payload is captured (`docs/reference/fixtures/glitchtip-webhook.json`), and apply surfaces the manual step (`cli._emit_glitchtip_webhook_reminder`). **But the sidecar never consumes any of it:**

- `/opt/fabrik-lib/watchdog/sidecar/agent.py:46` binds `HEALTH_PORT = 8888` only; `_HealthHandler`/`_start_health_server` (`agent.py:156-192`) is the sole HTTP surface.
- `grep -r '8889|WATCHDOG_TRIGGER_SOURCES|error_webhook'` over `/opt/fabrik-lib/watchdog` → **0 hits**. The sidecar never reads `WATCHDOG_TRIGGER_SOURCES`.
- Error detection is `gather_snapshot` → `detect_anomalies` (`agent.py:198-279`): container-state + `docker logs` regex, on `CHECK_INTERVAL_SECONDS`. Output is an `incident` dict: `{"source", "name", "severity", "details"}`.

So a GlitchTip webhook → `http://<id>-watchdog:8889/` POSTs into a dead port today.

## Goal

Make `error_webhook` a real, tested trigger source: a `:8889` ingest server that parses GlitchTip's Slack-compatible envelope into the existing `incident` shape and feeds it to the agent loop — additive to log-polling, opt-in via `WATCHDOG_TRIGGER_SOURCES`.

## One-Test Rule

Per CLAUDE.md ("1 test for the highest-risk path"), this plan's highest-risk path is the `:8889` ingest mapping the GlitchTip envelope into the agent's `incident` shape — a wrong mapping silently drops or mis-pages production errors.

- **Given** the captured `docs/reference/fixtures/glitchtip-webhook.json` (byte-identical to GlitchTip's real POST per its `_provenance`),
- **When** `_IngestHandler` parses that body,
- **Then** it enqueues exactly one incident `{source:"error_webhook", name:"ZeroDivisionError: division by zero", details.issue_url endswith "/issues/999999"}`, AND a wrong/missing `WATCHDOG_INGEST_TOKEN` or a malformed body is rejected (401/400) without crashing the server (`tests/test_ingest.py`).

## Phase 1 — Sidecar ingest server (`/opt/fabrik-lib/watchdog/sidecar/agent.py`)

1. Module-level thread-safe `queue.Queue` (`_ingest_q`) for webhook-sourced incidents.
2. `_IngestHandler(BaseHTTPRequestHandler)` — mirror `_HealthHandler`. On `POST`: optional bearer check against `WATCHDOG_INGEST_TOKEN` (401 if set + mismatch); `json.loads` the body; map GlitchTip envelope → incident:
   - `name` = `body.attachments[0].title`
   - `details` = `{"issue_url": .title_link, "color": .color, "fields": {f.title: f.value}}`
   - `severity` = `"urgent"` (GlitchTip only fires on new issues; keep it simple, refine later)
   - `source = "error_webhook"`
   Enqueue to `_ingest_q`; return `202`. Malformed body → `400`, never crash the server.
3. `_start_ingest_server()` — bind `("0.0.0.0", 8889)` in a daemon thread, **only if** `"error_webhook" in os.environ.get("WATCHDOG_TRIGGER_SOURCES", "").split(",")`.
4. Main loop: each iteration, drain `_ingest_q` (non-blocking) and process those incidents alongside `detect_anomalies(snap)`.

**Test (closes #1):** `tests/test_ingest.py` feeds `docs/reference/fixtures/glitchtip-webhook.json` (vendor a copy into the watchdog repo, or read via a shared path) to `_IngestHandler`'s parse path; assert the incident dict; assert `WATCHDOG_INGEST_TOKEN` enforced. The parser is now tested **where it lives**, against the same fixture fabrik's `test_watchdog_ingest_payload.py` pins.

## Phase 2 — Cross-host fail-closed guard (closes #2, `/opt/fabrik`)

GlitchTip is pinned to vps1; the `fabrik` net is a per-host bridge, so `<id>-watchdog:8889` only resolves same-host. In `orchestrator/__init__.py` right after `ctx.target_vps` is resolved (`:128`), fail closed: if the spec's `watchdog.trigger_sources` contains `error_webhook` and `ctx.target_vps != "vps1"`, raise a clear error (*"error_webhook ingest must be co-located with GlitchTip (vps1) — deploy on vps1 or drop error_webhook"*). Unit-test both branches.

## Phase 3 — Un-gate fabrik

Flip `glitchtip.webhook_registration_reminder` back to the actionable `ACTION REQUIRED: register …` text; drop the PENDING banner in `docs/operations/deployment.md`; update the reminder tests. (Revert of the 2026-06-30 gating commit, conditioned on Phases 1-2 shipping.)

## Validation gate

- fabrik-lib: `pytest tests/test_ingest.py` green; live: deploy a watchdog+error_webhook app on vps1, register the webhook, trigger a test issue, confirm a `logs/` cron/incident row appears.
- fabrik: `python scripts/final_gate.py --json` → success.

## Residual / risks

- Live watchdog: the ingest server is additive (new thread/port) — default path (no `error_webhook`) is byte-identical.
- `severity` mapping is coarse (always urgent); refine via `color` once real traffic is observed.
- Auth: `WATCHDOG_INGEST_TOKEN` is optional; document that an unauthenticated `:8889` is acceptable only because it's on the internal `fabrik` net with no Traefik route.
