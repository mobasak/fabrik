# Spec review — spoke watchdogs alert through a mesh-only Apprise gate (W-5dcafaef)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-23-spoke-watchdog-apprise-mesh-gate-design.md`
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** DRAFT

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice R: approach, facts table, digest, unknowns, validation) + sonnet×1 (slice P: personas → intake, rejected, lifecycle, docs, cost) + sonnet×1 fabrik-researcher (slice F, the cited facts) · all axes; `dispatch_headroom.py` TRIMMED the partition to 3 seats at quota (the authoritative Opus fact seat): the lead covered it by raw-curling `apprise_api/api/views.py` (150,721 bytes, 200) and `utils.py` | found: 24, new: 24, confirmed: 22, fixed: 22, unexecuted: 0, edits: 1 | method: citation — full pass; every candidate re-executed by the lead before folding: `src/fabrik/drivers/ssh.py:207-241` (one `RuntimeError` for every rc), `tests/test_watchdog_spoke_preflight.py:29-113` (the refusal tests and the vps1 test that patches only the driver), vps1 `iptables -S DOCKER-USER` (default-deny, so the spoke drop list protects nothing here), `scripts/sysadmin/ensure-apprise-alerts-config.sh:6-16` (the deployed image answered 204, the `alerts` key exists since 2026-07-12 — the lead's 404 alarm, from master's source, was withdrawn to the coordinator), `configs/gatus/_base.yaml:20` (Gatus pages through Apprise), views.py `_notify_attachments` (keyed notify fetches attachment URLs → the attachment lock). A local probe of the gate (nginx:1.30-trixie, an echo upstream aliased `apprise`) found the raw-URI pass-through and proved the fixed-URI `proxy_pass`, the resolver after an upstream recreate (literal form 502, resolver form 200) and Compose `configs.content` on 2.40.3 (vps1's version, read live). The spec was rewritten in one batch | e57cdd39286a8a0d333f46e4c2812584 → 75061049962966b27eab912d73011553 |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (round-1 owners, resumed) · delta over the pass-1 rewrite | found: 8, new: 8, confirmed: 6, fixed: 6, unexecuted: 0, edits: 6 | method: re-derivation — every pass-1 candidate re-checked FIXED by its owner; the intake split re-counted (19: 14 IN, 5 OUT), the 17+1 callers re-grepped, the preflight script's exit status executed by slice R (`0 'missing /nonexistent.json\npresent /etc/hostname'`); confirmed (own-fix: round 1, all six): the preflight must catch `SshHostError`/`JumpConfigError` (`src/fabrik/drivers/ssh.py:104`, `:121`, both `ValueError`), quote `VPS_CLAUDE_HOME`, the attachment invariant stated ahead of U4, `TestWatchdogSpokeRouting` must patch the preflight, the rollback's orphan spoke sidecar, the step-3 Apprise restart gap; refuted: the Size undercount (D-169 excludes tests), `:560` (`grep -n "target_vps = getattr"` → 560), `/cfg` not revealing (`views.py:1280-1281` "Return stored configuration for ``/get`` and ``/cfg``") | 75061049962966b27eab912d73011553 → fda57e3b00d22c8c022d798f21e5343d |

## Recorded, not confirmed

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| F-6 | 1 | the `proxy_pass` URI with a variable | RECORDED — measured (settled by the lead's probe, Derivations) |
| F-13 | 1 | host port == container port for DOCKER-USER | RECORDED — measured (moot: the spoke drop-list change was removed in pass 1) |
| P-N1 | 2 | Size verdict, the 5-file count | REFUTED — D-169's rule counts code files with tests excluded |
| P-N2 | 2 | `target_vps` at `:560` | REFUTED — `grep -n "target_vps = getattr" src/fabrik/drivers/watchdog.py` → 560 |
| F-a | 2 | the routes row, `/cfg` revealing | REFUTED — `views.py:1280-1281` |
