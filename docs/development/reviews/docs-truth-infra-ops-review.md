# Docs-truth verification ledger — waves: infrastructure + operations + workstation (Tier A/B)

**Plan:** `docs/development/plans/2026-07-20-plan-1-docs-truth-convergence.md` Phase E · **Date:** 2026-07-20
**Method:** claim-level verification (native verifiers, partitioned per doc-group); every FALSE/STALE fixed in place same-day. Live-fleet-only claims marked UNVERIFIABLE-EXTERNAL by design (dated probes stay dated).

## Coverage & counts

| Slice | Docs | Claims | Non-VERIFIED found |
|---|---|---:|---:|
| glitchtip/grafana ×2/prometheus setup | 4 | 41 | 2 |
| fleet-architecture / hub-rebuild / spoke-rebuild | 3 | ~67 | 2 |
| promtail / bootstrap-plan / residue-policy / urls | 4 | 60 | 4 |
| vps-ai-sysadmin | 1 | 43 | 1 |
| vps-complete-inventory | 1 | ~48 | 7 |
| vps-status (dated journal) | 1 | ~42 | 4 |
| operations (11 docs incl. full live-crontab diff) | 11 | 124 | 1 (+1 pool false-positive refuted: redis volume name is correct) |
| workstation (3 docs) | 3 | 32 | 1 |
| **Total** | **28** | **~457** | **22** |

## Findings → dispositions (all FIXED 2026-07-20)

**The dominant class — the 2026-07-19 pushgateway restore not yet reflected (6 docs):** prometheus-app-metrics-setup (:3,:19,:37 + stale AroWake expr), vps-fleet-architecture (:130,:136), vps-urls (:212 "no pushgateway/spoke jobs" — also internally contradictory), vps-ai-sysadmin (:3,:166), vps-complete-inventory (:433,:841), vps-status (:614). All now state: 17 `job_name`s configured / 16 active; pushgateway restored `b8071f40` 2026-07-19.

**Other fixes:** promtail drop-regex 5-entry → single-entry `^ocoron-com-backup-1$` (incl. the reproducible-setup heredoc that would have resurrected the stale config); spoke-rebuild step table + step_11b/step_11c; residue-policy teardown count 8→9 (destroyer.py order itself verified exact); bootstrap-plan 737→741 lines; inventory: WatchdogConfig default False (×2 — the doc's own header claimed this was already reconciled), sidecar path ×2, gatus apps/ 13 files, Lessons latest=81, microservice spec truth-table (emailgateway/file-api/file-worker specs deleted `a1749dd5`; image-broker regenerated `5caaa23b`); vps-status journal: 4 current-truth notes added without rewriting dated entries; deployment.md "git+local skip validation" → only local (git IS validated, D1); WSL2-DNS-FIX resolv block matched to live file.

**Verified-clean highlights:** hub-rebuild step table exact vs bootstrap-hub.sh (24 steps); wsl-environment crontab diff exact; disaster-recovery 22/22 (incl. `redis_redis-data` volume name — corroborated by 3 sources); gpu-rent 15/15; alert-rule counts (13) exact; sysadmin bot flags/ports/metrics all exact; MCP transports 10/10; wsl-shell-mcp 13/13.

**Queued for completion report (outside plan File Scope):** `scripts/vps_apply_limits.sh` hardcodes the legacy `coolify` network name; 5 enforcement scripts on disk but never gate-wired (check_changelog, check_index_md, check_configuration_md, check_openapi_sync, check_docs); packs `65-rag-search.md`/`ai/30-language.md` still carry Kilo-CLI framing.

**UNRESOLVED rows: 0.**
