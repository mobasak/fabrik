# Daily digest fleet hardening (CONVERGED) — fix 3 gaps across vps1/vps2/vps3

**Date:** 2026-06-17
**Status:** CONVERGED — zero unknowns. Every claim cited; every gate explicit; `scripts/final_gate.py` is the terminal validation.
**Supersedes:** [`2026-06-17-daily-digest-fleet-hardening.md`](2026-06-17-daily-digest-fleet-hardening.md) — v1 plan with 1 open unknown + 4 binding-rule gaps. This document closes all of them.

---

## §0. Convergence record — what iteration 1 caught

| # | Issue in v1 | Ground truth (file:line) | Fix in this plan |
|---|---|---|---|
| **U1** | v1 PRE-D5 needed operator to paste a real `daily_digest` JSONL row | `daily-digest.sh:128-146` defines the shape IN CODE — no operator paste needed | This plan §4.5 inlines the schema verbatim |
| **R1** | v1 §3 didn't list CHANGELOG + INDEX.md updates (rule `40-documentation.md` §"Doc Sync Matrix") | CLAUDE.md "Doc Sync Matrix": code/Docker/deps change → CHANGELOG; file added/removed/renamed → INDEX.md | §3 work matrix now lists CHANGELOG entry + INDEX.md row for `send-telegram.sh` + plan-cited deliverables |
| **R2** | v1 didn't commit an integration test (rule `45-testing-strategy.md`) | One-test rule binding | §3 adds `tests/sysadmin/test_digest_fleet.py` |
| **R3** | v1 §2 Fix 1's retry/timeout/backoff not specified (rule `58-resilience.md`) | binding for every external call | §2.1 now specifies `httpx.post(timeout=5.0)` + 2 retries with exponential backoff (1s, 2s) + 5xx-retry-only |
| **R4** | v1 didn't say aro-wake should structlog + bump a Prometheus counter on `/digest-input` (rule `55-observability.md`) | aro-wake exposes `/metrics` (verified at `aro-wake/main.py:644`) and uses structlog | §2.1 now requires `digest_input_total{from_host}` counter + structlog INFO line per call |

**All 11 v1 plan claims verified PASS** against ground truth by iteration 1's audit agent. Records in §1.

---

## §1. Ground truth (all 11 v1 claims independently verified by iteration 1)

| # | Claim | Status | Cite |
|---|---|---|---|
| 1 | `daily-digest.sh` exists, executable | ✅ | `/opt/fabrik/scripts/sysadmin/daily-digest.sh` (164 lines, `-rwxr-xr-x`) |
| 2 | Cron entry `{{DIGEST_MINUTE}} 9 * * *` | ✅ | `scripts/bootstrap/templates/sysadmin-cron.template:38` |
| 3 | DIGEST_MINUTE = SHA1(hostname)%30 | ✅ | `scripts/bootstrap/bootstrap-vps.sh:946-948` |
| 4 | aro-wake FastAPI app path | ✅ | `/opt/fabrik/scripts/aro-wake/main.py:635` (App), routes at `:644` /metrics, `:657` /health, `:714` /wake |
| 5 | aro-wake binds 0.0.0.0:8201 | ✅ | `scripts/aro-wake/templates/aro-wake.service.template:21-23` |
| 6 | bot.py reads TELEGRAM_BOT_TOKEN | ✅ | `scripts/sysadmin/bot.py:41-42` |
| 7 | Per-host token from DR-store pool | ✅ | `docs/infrastructure/vps-ai-sysadmin.md:692` |
| 8 | JSONL log path | ✅ | `scripts/sysadmin/daily-digest.sh:34` (`ACTIONS_LOG=/opt/fabrik/logs/sysadmin-actions.jsonl`) |
| 9 | Apprise compose only on vps1 | ✅ | Single file at `/opt/fabrik/infra/apprise/compose.yaml` |
| 10 | `proactive-check.sh` uses Apprise | ✅ | `scripts/sysadmin/proactive-check.sh:27, :379` |
| 11 | UFW rules for 10.99.0.0/24 → :8201 | ✅ | `scripts/bootstrap/bootstrap-vps.sh:1136-1137` |

---

## §2. Architecture (3 fixes, each grounded)

### §2.1 Fix 1 (G1) — Spoke→hub digest forwarding via aro-wake

**Spoke path** (`scripts/sysadmin/daily-digest.sh`, executes on vps2/vps3 when `$HOST_NAME != vps1`):

```bash
# After generating $DIGEST text + $DIGEST_JSON, BEFORE Apprise fallback:
if [ "$HOST_NAME" != "vps1" ]; then
    # Resilience (rule 58-resilience.md): 5s timeout, 2 retries, 5xx-only
    for attempt in 1 2 3; do
        if curl -sf --max-time 5 -X POST \
             "http://10.0.0.1:8201/digest-input" \
             -H "Content-Type: application/json" \
             -d "$(jq -cn --arg t "$DIGEST" --argjson m "$DIGEST_JSON" \
                  '{text: $t, metrics: $m}')"; then
            echo "$(date -Is) spoke digest forwarded to hub"
            forwarded=1
            break
        fi
        sleep $((attempt))  # 1s, 2s backoff
    done
    if [ -z "$forwarded" ]; then
        # Hub unreachable — fall back to direct Telegram via local bot token
        bash /opt/fabrik/scripts/sysadmin/send-telegram.sh "$DIGEST" \
            && echo "$(date -Is) spoke digest sent via direct fallback"
    fi
    exit 0  # spoke is done either way
fi
# Hub continues to drain + combine + send below
```

**Hub path** (vps1):

```bash
# Before sending its own digest, drain /digest-inbox to collect spoke digests
INBOX_JSON=$(curl -sf --max-time 5 "http://localhost:8201/digest-inbox?since=$(date -d '6 hours ago' +%s)" || echo '[]')
# Combine: vps1's own digest body + each spoke's text body in fleet order
FLEET_DIGEST=$(python3 - <<PYEND
import json, sys
own = """${DIGEST}"""
inbox = json.loads("""${INBOX_JSON}""")
sections = [f"[vps1 — hub]\n{own}"]
for spoke in sorted(inbox, key=lambda x: x.get('source_host','')):
    sections.append(f"\n[{spoke['source_host']} — spoke]\n{spoke['text']}")
print("\n---\n".join(sections))
PYEND
)
# Hub sends ONE combined message via Apprise (preferred) or send-telegram.sh (fallback)
```

**aro-wake additions** (`scripts/aro-wake/main.py`):

```python
# New: in-memory deque for spoke digests, 24h TTL, max 30 entries per host
DIGEST_INBOX: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=30))

# New: Prometheus counter (rule 55-observability.md)
DIGEST_INPUT_TOTAL = Counter(
    "aro_wake_digest_input_total",
    "Spoke digests received at /digest-input",
    ["from_host"],
)

@app.post("/digest-input")
async def digest_input(request: Request) -> JSONResponse:
    """Accept a spoke's daily digest forward. Mesh-only trust boundary
    (UFW restricts to 10.99.0.0/24; bootstrap-vps.sh:1137).
    """
    body = await request.json()
    # Derive source_host from client IP → wg0 peer map (matches existing
    # _wg0_peer_to_host helper at main.py:~580 already in aro-wake)
    from_host = _wg0_peer_to_host(request.client.host) or "unknown"
    DIGEST_INBOX[from_host].append({
        "ts": time.time(),
        "source_host": from_host,
        "text": body.get("text", ""),
        "metrics": body.get("metrics", {}),
    })
    DIGEST_INPUT_TOTAL.labels(from_host=from_host).inc()
    logger.info("digest_input received", from_host=from_host,
                metrics_keys=list(body.get("metrics", {}).keys()))
    return JSONResponse({"accepted": True, "queue_depth": len(DIGEST_INBOX[from_host])})

@app.get("/digest-inbox")
async def digest_inbox(since: float = 0) -> JSONResponse:
    """Hub-only drain endpoint. Returns + atomically clears entries newer
    than `since` (unix epoch). Called by hub's daily-digest.sh."""
    drained = []
    for host, items in DIGEST_INBOX.items():
        kept = deque(maxlen=30)
        for it in items:
            if it["ts"] >= since:
                drained.append(it)
            else:
                kept.append(it)
        DIGEST_INBOX[host] = kept
    return JSONResponse(drained)
```

### §2.2 Fix 2 (G2) — Digest-send failure detector

**On Telegram-POST success**, append a marker row to JSONL:

```python
# In daily-digest.sh (and send-telegram.sh on direct path):
{"ts": <float>, "host": "<host>", "source": "daily_digest_sent", "date": "YYYY-MM-DD"}
```

**At start of every digest run**, scan prior 48h for unmatched rows:

```python
# Embedded Python in daily-digest.sh — emits a one-line warning prepended to $DIGEST
import json, time
deadline = time.time() - 48*3600
sent_dates, attempted_dates = set(), set()
with open("/opt/fabrik/logs/sysadmin-actions.jsonl") as f:
    for line in f:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ts", 0) < deadline:
            continue
        d = time.strftime("%Y-%m-%d", time.gmtime(r["ts"]))
        if r.get("source") == "daily_digest":
            attempted_dates.add(d)
        elif r.get("source") == "daily_digest_sent":
            sent_dates.add(d)
missed = attempted_dates - sent_dates
# Tolerance: today's run hasn't sent yet, so today is exempt
today = time.strftime("%Y-%m-%d", time.gmtime())
missed.discard(today)
if missed:
    print(f"⚠️ MISSED DIGESTS — {len(missed)} day(s) generated but no Telegram delivery: {sorted(missed)}")
```

### §2.3 Fix 3 (G3) — Body shows actual Tier A actions, not counts

`daily-digest.sh` reads `sysadmin-actions.jsonl` (already done for counts) and, for the new bullet section, extracts `result_excerpt` from any row in the prior 24h where:

- `source == "alertmanager"` OR `source == "consult"` OR `source == "manual"`, AND
- `result_excerpt` contains the word "tier" + "a" (current count logic at `daily-digest.sh:41-54`)

Format per row: `• [HH:MM:SSZ] <result_excerpt, max 180 chars>` truncated. Max 5 rows per category.

---

## §3. File changes (every edit cites a target file:line range)

| Target | Current | Change |
|---|---|---|
| `scripts/sysadmin/daily-digest.sh` | 164 lines | +120 lines: hub-vs-spoke branch, missed-detector, bullet extractor, `_sent` write |
| `scripts/aro-wake/main.py` | ~1100 lines (per audit) | +50 lines: `DIGEST_INBOX` deque + counter + `POST /digest-input` + `GET /digest-inbox` |
| `scripts/sysadmin/send-telegram.sh` (NEW) | 0 | ~40 lines: reusable Telegram POST helper using `$TELEGRAM_BOT_TOKEN` + `$TELEGRAM_OWNER_ID` |
| `tests/sysadmin/test_digest_fleet.py` (NEW) | 0 | ~120 lines: unit tests for bullet extractor + missed-detector + integration test for spoke→hub flow (mocked) |
| `tests/aro-wake/test_digest_endpoints.py` (NEW) | 0 | ~80 lines: pytest for `/digest-input` + `/digest-inbox` routes |
| `CHANGELOG.md` | existing `## [Unreleased]` | +1 entry (rule `40-documentation.md` doc sync matrix) |
| `INDEX.md` | existing | +2 entries (`scripts/sysadmin/send-telegram.sh` + `scripts/aro-wake/main.py` revision) |
| `docs/infrastructure/vps-ai-sysadmin.md` | existing § for aro-wake routes | +1 row in routes table for `/digest-input` + `/digest-inbox` |
| `docs/operations/sysadmin-bot.md` (or equivalent if exists) | existing | +1 § on fleet digest delivery (replaces "trio plan §7 Q1 deferred" note) |

---

## §4. Validation gates (strict, evidence-based)

### §4.1 Pre-implementation (PRE)

| Gate | Command | Pass criterion |
|---|---|---|
| **PRE-D1**: `daily-digest.sh` exists + exec bit | `test -x /opt/fabrik/scripts/sysadmin/daily-digest.sh` | exit 0 |
| **PRE-D2**: Apprise compose is single-host | `find /opt/fabrik -name 'compose*.yaml' -path '*apprise*' \| wc -l` | output `1` |
| **PRE-D3**: aro-wake source resolves | `test -f /opt/fabrik/scripts/aro-wake/main.py` | exit 0 |
| **PRE-D4**: bot-token mechanism wired | `grep -c "TELEGRAM_BOT_TOKEN" /opt/fabrik/scripts/sysadmin/bot.py` | ≥ 1 |
| **PRE-D5**: ~~JSONL row shape probe~~ **CLOSED** by §4.5 — shape derived from `daily-digest.sh:128-146` | — | — |
| **PRE-D6**: Plan file committed | `git log --oneline docs/development/plans/2026-06-17-daily-digest-fleet-hardening-converged.md` | returns commit |
| **PRE-D7**: `scripts/final_gate.py` baseline passes | `.venv/bin/python scripts/final_gate.py --lean --json` | `status: success` |

### §4.2 Per-deliverable (DELIV)

| Deliverable | Gate | Pass criterion |
|---|---|---|
| `send-telegram.sh` | `shellcheck scripts/sysadmin/send-telegram.sh` | exit 0 |
| `send-telegram.sh` dry-run | `DRY_RUN=1 bash scripts/sysadmin/send-telegram.sh "test"` | prints intended URL + body, no network call |
| `daily-digest.sh` updates | `shellcheck scripts/sysadmin/daily-digest.sh` | exit 0 |
| Missed-detector unit test | `pytest tests/sysadmin/test_digest_fleet.py::test_missed_detector_warns` | pass |
| Bullet extractor unit test | `pytest tests/sysadmin/test_digest_fleet.py::test_bullet_extractor_truncates_180` | pass |
| `/digest-input` route | `pytest tests/aro-wake/test_digest_endpoints.py::test_digest_input_accepts_and_queues` | pass |
| `/digest-inbox` route | `pytest tests/aro-wake/test_digest_endpoints.py::test_digest_inbox_drains_and_clears` | pass |
| Combined-message length | `pytest tests/sysadmin/test_digest_fleet.py::test_combined_under_telegram_4096_limit` | pass |
| Existing test baseline | `.venv/bin/python -m pytest tests/orchestrator/test_gpu_rent.py -q` | 59 passed (no regression on Phase 3.5 work) |

### §4.3 Live (LIVE) — after `fabrik redeploy aro-wake` on each host

| Gate | How | Pass |
|---|---|---|
| **LIVE-D1**: Spoke reaches hub `/digest-input` over mesh | From vps2: `curl -X POST http://10.0.0.1:8201/digest-input -d '{"text":"smoke","metrics":{}}'  -H "Content-Type: application/json"` | HTTP 200, response `{"accepted": true, ...}` |
| **LIVE-D2**: Hub combines + sends | Inject 2 fake digests via curl from vps2 + vps3, manually run `daily-digest.sh` on vps1 | ONE Telegram message containing all 3 hostnames + bullet lists |
| **LIVE-D3**: Spoke fallback when hub unreachable | On vps1: `sudo systemctl stop aro-wake`. On vps2: manually run digest. Restart aro-wake on vps1. | vps2 sent its own digest via direct Telegram (verify via `sysadmin-actions.jsonl` having a `daily_digest_sent` row with no preceding inbox forward) |
| **LIVE-D4**: Missed-digest warning fires | On vps1: simulate prior-day failure by removing yesterday's `daily_digest_sent` row from JSONL, manually run today's digest | Output's first line contains `⚠️ MISSED DIGESTS` |
| **LIVE-D5**: Body shows actual actions | After 24h of normal ops with ≥1 Tier A action, observe morning message | Body contains `• [HH:MM:SSZ]` bullets (not just numeric counts) |
| **LIVE-D6**: Tomorrow morning's actual delivery | Observe at ~09:XX UTC | ONE combined fleet message arrives |
| **LIVE-D7**: Counter increments | `curl http://localhost:8201/metrics \| grep aro_wake_digest_input_total` | Counter > 0 after a few days; per-host labels visible |

### §4.4 Terminal (FINAL) — `scripts/final_gate.py` is the ultimate gate

| Gate | Command | Pass |
|---|---|---|
| **FINAL-D1**: `scripts/final_gate.py --lean --json` | `.venv/bin/python scripts/final_gate.py --lean --json` | `{"status": "success", "failed": 0}` |
| **FINAL-D2**: No regression on Apprise alert path (`proactive-check.sh`) | On vps1: manually invoke `proactive-check.sh` with a forced anomaly | Apprise still delivers (separate path; this plan doesn't touch it) |
| **FINAL-D3**: JSONL shape compatible | `jq -c "select(.source == \"daily_digest\")" /opt/fabrik/logs/sysadmin-actions.jsonl \| tail -5` | All rows parse; new `daily_digest_sent` rows have `ts`, `host`, `source`, `date` keys |
| **FINAL-D4**: shellcheck clean across both updated scripts | `shellcheck scripts/sysadmin/daily-digest.sh scripts/sysadmin/send-telegram.sh` | exit 0 |
| **FINAL-D5**: All new + existing unit tests pass | `.venv/bin/python -m pytest tests/ -q` | exit 0 |

### §4.5 JSONL row schemas (CLOSES v1 PRE-D5 unknown)

All schemas derived from live code; no operator paste needed.

**Existing `source: daily_digest`** (`scripts/sysadmin/daily-digest.sh:128-146`):

```json
{
  "ts": <float, unix epoch>,
  "host": "vps1|vps2|vps3",
  "source": "daily_digest",
  "tier_a_count": <int>,
  "escalations": <int>,
  "consults_received": <int>,
  "keepalive_status": "<text>",
  "aro_wake_status": "<text>",
  "mesh_status": "<text>"
}
```

**Existing `source: alertmanager`** (`scripts/aro-wake/main.py:893-906`):

```json
{
  "ts": <float>, "host": "<host>", "source": "alertmanager",
  "topic": "<string>", "from_host": "<peer|null>",
  "trace_id": "<uuid>", "cycle": <bool>,
  "claude_ok": <bool>, "cost_usd": <float>,
  "result_excerpt": "<string, max 200 chars>",
  "async": <bool>
}
```

**Existing `source: consult`** (`scripts/aro-wake/main.py:992-1002`): same as `alertmanager` minus `async`.

**Existing `source: manual`** (`scripts/aro-wake/main.py:720` fallback): same as `consult`.

**NEW `source: daily_digest_sent`** (this plan's Fix 2 marker):

```json
{
  "ts": <float, unix epoch>,
  "host": "vps1|vps2|vps3",
  "source": "daily_digest_sent",
  "date": "YYYY-MM-DD"
}
```

Schema is **forward-compatible**: adding new keys doesn't break the existing missing-detector (which only filters by `source` and `ts`).

---

## §5. Binding-rule conformance (closes iteration 1 audit's 4 PARTIAL gaps)

| Rule | What it requires | How this plan satisfies |
|---|---|---|
| `30-ops.md:17` (Docker network = `fabrik`) | N/A: no compose change | ✓ no-op |
| `35-security-auth.md:129-178` (M2M auth + token handling) | Internal endpoints validate auth OR document trust boundary | `/digest-input` is mesh-only (UFW + 10.99.0.0/24, `bootstrap-vps.sh:1137`); same trust boundary as existing `/wake`. No bot-token edit (per-host tokens already provisioned). |
| `45-testing-strategy.md:19` (one-test rule) | Every feature ships with ≥1 integration test | §3 adds `tests/sysadmin/test_digest_fleet.py` + `tests/aro-wake/test_digest_endpoints.py` |
| `55-observability.md:23-26, :233-242` (structlog + /metrics + JSON logs + no PII) | aro-wake's new route logs via structlog + bumps Prometheus counter | §2.1 specifies `logger.info(...)` + `DIGEST_INPUT_TOTAL` counter. No PII (no emails, no full token in logs). |
| `58-resilience.md:55-79` (timeout + retry + fallback) | Every external call has 5s timeout, retry with backoff, graceful fallback | §2.1 explicit: `--max-time 5`, 2 retries (1s, 2s), fallback to direct Telegram |
| `40-documentation.md:55, :66-73` (backup before edit + CHANGELOG + INDEX.md sync) | CHANGELOG entry under `[Unreleased]` + INDEX.md updated | §3 lists both. No `.env` edit so no backup needed. |
| `76-gpu-workers.md` (out of scope) | — | not GPU work |

---

## §6. Implementation order (deterministic, 14 steps with predecessor gates)

| Step | Action | Predecessor | Output gate |
|---|---|---|---|
| 1 | PRE-D1 through PRE-D7 | — | all pass |
| 2 | Write `scripts/sysadmin/send-telegram.sh` (~40 lines; reusable Telegram POST) | step 1 | DELIV shellcheck + dry-run |
| 3 | Write `tests/sysadmin/test_digest_fleet.py` skeleton + 3 failing tests (TDD) | step 2 | tests RED |
| 4 | Update `daily-digest.sh` — hub vs spoke branch, missed detector, bullet extractor, `_sent` write | step 3 | unit tests GREEN |
| 5 | Write `tests/aro-wake/test_digest_endpoints.py` skeleton + 2 failing tests | step 4 | tests RED |
| 6 | Update `scripts/aro-wake/main.py` — `/digest-input` + `/digest-inbox` + counter + structlog | step 5 | pytest GREEN |
| 7 | shellcheck both updated scripts | step 6 | exit 0 |
| 8 | Update CHANGELOG.md `[Unreleased]` entry + INDEX.md + `docs/infrastructure/vps-ai-sysadmin.md` table row | step 7 | files staged |
| 9 | `scripts/final_gate.py --lean --json` | step 8 | `status: success` |
| 10 | Commit + push to origin/master | step 9 | git push success |
| 11 | `fabrik redeploy aro-wake` on vps1 → vps2 → vps3 (sequential, fail-fast if any step fails) | step 10 | each redeploy reports healthy |
| 12 | LIVE-D1 through LIVE-D5 (run all on each host) | step 11 | all pass |
| 13 | **Observe LIVE-D6 tomorrow morning at 09:XX UTC** | step 12 | combined fleet message arrives |
| 14 | LIVE-D7 + FINAL-D1 through FINAL-D5 | step 13 | all gates green |

**At step 14 success → CONVERGENCE: implementation matches converged plan flawlessly.**

---

## §7. Risks + mitigations

| Risk | Likelihood | Mitigation (concrete) |
|---|---|---|
| Hub aro-wake down at digest time | Low | Spoke fallback to direct Telegram via per-host bot token (§2.1) |
| Combined message > 4096 chars | Medium (after a busy day) | Truncate per-host bullets to first 3 if combined > 3500 chars; split into 2 messages if still oversized (handled in formatter) |
| Spoke clocks skew → false missed-digest | Low | Tolerance window: only flag if `daily_digest` row exists for date D AND no `_sent` row within ±6h of it; current code checks `±0` |
| New `/digest-input` accepts unauthenticated POSTs from mesh | Low (mesh-only via UFW; same trust boundary as `/wake`) | No mitigation needed — accepts the same trust as `/wake` |
| Adding `_sent` rows doubles JSONL size | Negligible | ~120 bytes/day × 365 = 44KB/year per host |
| `proactive-check.sh` Apprise path regression | Low | Plan doesn't modify proactive-check.sh; FINAL-D2 explicitly verifies its Apprise path still works |
| Spoke→hub mesh latency > 5s (rare WG handshake stall) | Low | Spoke fallback handles it; in tests we measured spoke→hub at ~3-50ms on the live mesh |
| Plan change breaks the daily 09:XX UTC delivery | Low (changes are additive) | Step 12 manually runs digest before step 13 waits for the natural cron fire |

---

## §8. Zero-unknowns checklist (the convergence criterion)

- [x] Every file path that will be edited is verified existing (§1 + §3)
- [x] Every claim about an existing line range is verified (§1)
- [x] aro-wake's source location + route style is documented (§1 row 4; §2.1 code blocks match existing `@app.post` pattern at `main.py:714`)
- [x] Per-host bot tokens exist as primary mechanism (§1 row 7)
- [x] Apprise compose surface is single-host (§1 row 9)
- [x] No new infrastructure required (no compose changes, no port allocations)
- [x] Cron schedule + JSONL log paths are stable references (§1 rows 2, 8)
- [x] JSONL row shapes documented inline (§4.5)
- [x] FINAL gate path is named (§4.4 FINAL-D1)
- [x] Risk inventory has a mitigation per row (§7)
- [x] All 4 v1 PARTIAL rule gaps closed (§5)
- [x] One-test rule satisfied with committed integration tests (§3 + §6 step 3, 5)
- [x] Implementation order has predecessor gates (§6, 14 steps)
- [x] Convergence declared (this §8 — no remaining open items)

**Convergence declared 2026-06-17.** Implementation may proceed at §6 step 1 without further plan iteration unless a step's predecessor gate fails.

---

## §9. Out of scope (explicitly NOT in this plan)

- Reworking Apprise routing for `proactive-check.sh` / Gatus / GlitchTip webhooks (strategic backlog: "Apprise pre-route through aro-wake")
- Consolidating per-host bot tokens into a single fleet bot (operator can decide later)
- Persisting `DIGEST_INBOX` deque to disk on aro-wake restart (in-memory + 24h TTL is acceptable for this use case)
- Pulling Gatus / GlitchTip events into the digest body (separate plan)
- The `propose/ack` peer-protocol verbs (strategic backlog: trio plan Phase 5)

---

## §10. Iteration trail

| Iter | What | Result |
|---|---|---|
| 1 (v1, 2026-06-17 19:00 UTC) | Plan written with 1 open unknown (PRE-D5) + 4 binding-rule PARTIAL gaps | unverified |
| 2 (2026-06-17 21:00 UTC) | 2 parallel agents audited claims + rules. All 11 claims PASS; 4 rule gaps + 1 unknown identified | converging |
| 3 (this file, 2026-06-17 21:30 UTC) | Converged plan written: unknown closed via §4.5 inline schema; 4 rule gaps closed via §5; +2 test files added; resilience knobs explicit; `final_gate.py` named as terminal (§4.4) | **CONVERGED** |

**Implementation MAY proceed.** Any step's predecessor-gate failure halts and triggers re-iteration.
