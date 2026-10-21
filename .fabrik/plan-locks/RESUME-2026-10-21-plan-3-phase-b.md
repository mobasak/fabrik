## RESUME

Item: W-10146d20 (own scrape tool replacing Firecrawl). Plan: docs/development/plans/2026-10-21-plan-3-own-scrape-slice-1a.md
(CONVERGED, D-1101), Phase B of 3. Phase A is EXECUTED and merged (a3fb22070).

Phase B, before merge, is DONE and in merge request 01M5FY5G0D to the coordinator (fabrik-98):
- 30d86d219 vendors fabrik-lib's scrape server (libs/web_scrape_mcp, fabrik-lib main 5e428214), and adds
  scripts/scrape_ledger.py, the systemd unit source, fabrik-scrape in the emitter's universal set, the roster rows and D-1102.
- 87a1e36ec: the full /fabrik-review fixes. Receipt docs/development/reviews/2026-10-21-plan-3-own-scrape-slice-1a-phase-2-review.md
  CONVERGED, confirmed 18, 8, 0, then 0.

Two things are still open in Phase B, both waiting on someone else:
1. The post-merge gate (plan steps 9-10), boarded to the coordinator as a DECISION block (ground: gate) in the same message.
   On approval, infra runs these from /opt/fabrik:
   - `uv venv --python /usr/bin/python3 libs/web_scrape_mcp/.venv`, then the `uv pip install -r requirements`;
   - install and enable `fabrik-scrape-mcp.service`;
   - the probe gate: `scrape_ledger.py --probe http://127.0.0.1:8034/mcp` must list `scrape`;
   - `emit_mcp_project_config.py --check`, then the real run, then `mcp_health.py`.
   After that, intel runs the capability ledger U1-U7. The expected outcomes are U1-U4 and U7 PASS, U6 bot-wall and
   U5 unsupported. Then the scope call: `http://127.0.0.1:8033/` gives `scope`.
2. Step 2: DONE (9df9090ed, merge request 01M5FZEKHW). libs/web_tools.py is re-vendored at fabrik-lib c7ab67e4 and
   guarded by tests/test_web_tools_firecrawl_{proxy,log}.py. web-ecommerce-factory was asked to re-vendor its two copies
   (mail 01M5FYPHA0); that is their work, not a Phase B blocker.

When both are done: mark Phase B EXECUTED in the plan, then start Phase C in a new session. Phase C is:
- the researcher ledger, built from `scrape_ledger.py --harvest`;
- then the switch, behind a flag that defaults to the old path, with Firecrawl as the fallback.
The plan's Phase C section has the steps.
