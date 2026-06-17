# Daily digest fleet hardening — fix the 3 gaps across vps1/vps2/vps3

**Date:** 2026-06-17
**Status:** Plan
**Operator goal:** Every morning, get a **reliable, content-rich, fleet-wide** Telegram digest. Today only vps1 delivers, content is metric-counts only, and there's no alert when delivery silently fails.

---

## §0. Ground truth (verified 2026-06-17, this conversation)

| Fact | Source |
|---|---|
| `daily-digest.sh` runs on all 3 hosts via per-host hash-slotted cron at 09:XX UTC | `scripts/bootstrap/templates/sysadmin-cron.template` + `bootstrap-vps.sh:946-947` |
| It writes a JSON record to `/opt/fabrik/logs/sysadmin-actions.jsonl` on every run, regardless of Telegram success | `daily-digest.sh:128-146` |
| It POSTs to `http://apprise:8000/notify/alerts` if a container named `apprise` is on the `fabrik` Docker network | `daily-digest.sh:148-160` |
| Apprise compose **exists only on vps1** at `infra/apprise/compose.yaml` (Traefik `notify.vps1.ocoron.com`) | `find /opt/fabrik -name compose.yaml -path "*apprise*"` returns one match |
| Each host has its OWN per-host Telegram bot token (claimed from `/opt/fabrik-dr-store/env/sysadmin-bot-tokens.json` during bootstrap) for `vps-sysadmin-bot.service`. **Spoke→Telegram is already possible** — just not via Apprise. | `docs/infrastructure/vps-ai-sysadmin.md:692` |
| `bot.py` reads `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_ID` from `.env.sysadmin` and can already send messages | `scripts/sysadmin/bot.py:41-42` |
| `aro-wake` listens on `:8201` on **all 3 hosts** and accepts POSTs from peers via wg0 mesh (10.99.0.0/24) | `docs/infrastructure/vps-ai-sysadmin.md:25` |
| `proactive-check.sh` runs every 15 min on each host and emits anomalies via the same Apprise→Telegram path (so Apprise is the canonical alert route, not a digest-only fluke) | `scripts/sysadmin/proactive-check.sh` |
| `sysadmin-actions.jsonl` has a known schema with `source` field — used by digest, peer protocol, watchdog | searched live; same file referenced from multiple scripts |

**Three gaps the operator named:**

- **G1** — vps2/vps3 digests are generated locally but never delivered to Telegram (Apprise container missing on spokes).
- **G2** — When the digest fails to send (Apprise down, network blip), nothing alerts. The next morning you get nothing and don't know why.
- **G3** — Body is metric counts (`tier_a_count: 5`). Doesn't show *what* the 5 actions were. To see them you have to ssh in and grep the JSONL.

---

## §1. Architecture decision (D1) — fleet digest, single Telegram message

Two options were on the table:

| Option | Outcome | Net cost |
|---|---|---|
| **A. Each host sends its own digest via per-host bot.py** | 3 separate Telegram messages every morning | Simplest; matches existing per-host bot tokens; minimal code change |
| **B. Spokes POST digest to hub's aro-wake → hub aggregates → ONE combined fleet digest** | 1 combined message: "vps1: 5/0/0 · vps2: 0/1/0 · vps3: 0/0/0" | Cleaner UX; reuses `aro-wake` HTTP plumbing already on every host; ~30 more LoC |

**D1: Ship Option B.** A single combined morning message is what an operator with a 3-host fleet actually wants — one glance to see the whole fleet's last 24h. The hub-aggregation pattern matches how Prometheus already centralizes spoke metrics, so it's consistent with the existing architecture.

**Fallback**: if hub-aggregation can't deliver (hub down, aro-wake unreachable), spokes fall back to **direct Telegram send via their own bot token** so the operator gets ≥1 message even on hub failure (this also solves G2 partially).

---

## §2. The 3 fixes (concrete changes)

### Fix 1 (G1) — Spoke→hub digest forwarding via aro-wake

**New endpoint on aro-wake**: `POST /digest-input` (additive; existing `/wake` stays). Body: the spoke's local digest JSON (same shape currently written to JSONL). Hub stores in an in-memory deque (24h TTL, max 30 entries) per spoke. When hub's own `daily-digest.sh` runs at its hash-slotted minute, it drains the deque and combines.

**Files to change:**

| File | Change |
|---|---|
| `scripts/sysadmin/daily-digest.sh` | On non-hub hosts (`HOST_NAME != vps1`): instead of attempting Apprise POST, POST the digest JSON to `http://10.0.0.1:8201/digest-input` (mesh IP works from spokes via wg0). On failure → fall back to direct Telegram send via local bot token. Hub host: drain `/digest-inbox` from aro-wake, combine with own digest, send ONE message. |
| `services/aro-wake/main.py` (or wherever the FastAPI app lives) | Add `POST /digest-input` route accepting the digest JSON, append to in-memory deque keyed by `source_host`. Add `GET /digest-inbox?since=ts` for hub to drain. |
| New helper `scripts/sysadmin/send-telegram.sh` | Reusable shell function: read `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_ID` from `.env.sysadmin`, POST to `https://api.telegram.org/bot$TOKEN/sendMessage`. Used as the fallback path AND eventually by other scripts that today rely on Apprise. |

### Fix 2 (G2) — Digest-send failure alert

**Self-healing digest watchdog**: at the start of each `daily-digest.sh` run, before generating today's digest, **check the JSONL for missed sends in the prior 48h** and prepend a `⚠️ MISSED DIGESTS DETECTED` line if any are found.

**Detection rule**: a digest run for date D is considered "missed" if the JSONL has a `source: daily_digest` row for D but no `source: daily_digest_sent` (new field) row for the same date. We emit `daily_digest_sent` only when Telegram POST returned HTTP 200.

**Why this works**: every digest run writes the JSONL row unconditionally (already does today). If Telegram delivery succeeds we also write a `_sent` row. Tomorrow's digest checks "are there `daily_digest` rows without matching `_sent` rows in the last 48h?" and surfaces the miss.

**Failure cases caught:**
- Apprise container down → daily_digest row written, no _sent → tomorrow's digest says "⚠️ yesterday: digest generated but Telegram POST failed"
- Cron didn't fire at all → JSONL has no digest row for yesterday → tomorrow's check sees zero rows for the prior date → "⚠️ yesterday's digest did not run"

**Files to change:**

| File | Change |
|---|---|
| `scripts/sysadmin/daily-digest.sh` | (a) Add `check_missed_digests()` function near top; prepend its output to `$DIGEST` if non-empty. (b) After Telegram POST success, append a `{source: daily_digest_sent, ts, host}` row to JSONL. |

### Fix 3 (G3) — Body content: actual Tier A actions, not just counts

**Pull the last-24h `result_excerpt` for each Tier A + Escalation row and inline them into the digest body**, truncated to ≤180 chars each, ≤5 rows per category (so the message stays Telegram-readable).

**Format (proposed):**

```
[fleet] Daily digest 2026-06-18 09:07 UTC

vps1: tier_a=3 esc=0 consults=2
  • [2026-06-17T14:33Z] restarted postgres-main after slow query alarm
  • [2026-06-17T19:02Z] purged 12GB stale docker volumes (>30d)
  • [2026-06-17T22:11Z] rotated grafana session secret + restarted

vps2: tier_a=0 esc=1 consults=0
  • [2026-06-17T16:45Z] ESC: gatus probe site-provisioner /health 503 — needs op review

vps3: tier_a=1 esc=0 consults=0
  • [2026-06-17T08:12Z] adjusted nginx worker_connections after burst

Heartbeats: keepalive vps1=42m vps2=15m vps3=8m · aro-wake all up · mesh peers <120s
```

**Files to change:**

| File | Change |
|---|---|
| `scripts/sysadmin/daily-digest.sh` | New Python helper inside the script: jq-style extract `result_excerpt` from last-24h `tier=A` rows + escalations; truncate per-row at 180 chars; format as bullet list. Apply at body-build time. |
| `services/aro-wake/main.py` | `/digest-input` accepts the FULL digest (text body + JSON metrics), not just metrics; hub uses the text bodies verbatim in the combined message. |

---

## §3. Where to do the work (operator vs hub vs spoke)

| Action | vps1 (hub) | vps2 (spoke) | vps3 (spoke) | WSL (this repo) |
|---|---|---|---|---|
| Edit `scripts/sysadmin/daily-digest.sh` | — | — | — | ✅ here |
| Edit `services/aro-wake/main.py` | — | — | — | ✅ here |
| Edit `scripts/sysadmin/send-telegram.sh` (new) | — | — | — | ✅ here |
| `git pull && deploy` to vps1 | ✅ | — | — | trigger via `fabrik redeploy aro-wake` after push |
| `git pull && deploy` to vps2 | — | ✅ | — | same |
| `git pull && deploy` to vps3 | — | — | ✅ | same |
| Verify spoke→hub digest forward | — | smoke from spoke via `curl 10.0.0.1:8201/digest-input -d @sample.json` | same | ✅ smoke |
| Verify combined morning message | observe hub's 09:XX run | — | — | observe at 09:XX |

All code changes in this repo. Push to GitHub → `fabrik redeploy aro-wake` on each host → cron picks up the new script next run.

---

## §4. Validation gates (every step has a strict check)

### Pre-implementation

| Gate | Command | Pass criterion |
|---|---|---|
| **PRE-D1**: `daily-digest.sh` exists at expected path | `ls -la /opt/fabrik/scripts/sysadmin/daily-digest.sh` | File exists, executable bit set |
| **PRE-D2**: Apprise compose lives only on vps1 (verifies "only vps1 delivers today") | `find /opt/fabrik -name "compose*.yaml" -path "*apprise*"` | One file; one match |
| **PRE-D3**: aro-wake source identified | `find /opt/fabrik -name "main.py" -path "*aro-wake*" -o -name "aro-wake*"` | Resolves to a FastAPI app file we can edit |
| **PRE-D4**: per-host bot token mechanism exists | `grep -r "TELEGRAM_BOT_TOKEN" /opt/fabrik/scripts/sysadmin/` | At least `bot.py` reads it |
| **PRE-D5**: Sample digest JSONL row from real production exists for shape reference | `ssh vps1 'jq -c "select(.source == \"daily_digest\")" /opt/fabrik/logs/sysadmin-actions.jsonl \| tail -1'` (operator runs) | Operator pastes one real row so the new code's parser is shaped right |

### Per-deliverable

| Deliverable | Gate | Pass criterion |
|---|---|---|
| `send-telegram.sh` | shellcheck + dry-run | Exit 0; dry-run prints intended URL + body without sending |
| `daily-digest.sh` updates | Unit-test the Python embedded blocks | Render against a fixture JSONL with 3 tier-A rows + 1 escalation → output has 4 bullet lines |
| `aro-wake` `/digest-input` route | pytest against the FastAPI app | POST returns 200; subsequent GET `/digest-inbox` returns the deque |
| Combined message | Render against 3 fixture per-host digests | Output is ≤4096 chars (Telegram limit); contains all 3 hostnames + bullet lists |

### Live gates (after deploy)

| Gate | How | Pass |
|---|---|---|
| **LIVE-D1**: Spoke can reach hub `/digest-input` over mesh | From vps2: `curl -X POST http://10.0.0.1:8201/digest-input -d '{"test":1}' -H "Content-Type: application/json"` | 200 OK |
| **LIVE-D2**: Hub drains inbox + combines | Inject fake digest rows on vps2 + vps3 via curl, then run `daily-digest.sh` on vps1 manually | One Telegram message with all 3 hosts' sections |
| **LIVE-D3**: Spoke fallback to direct Telegram works | On vps2, stop aro-wake on vps1 temporarily, run digest manually | vps2 sends its own digest direct (operator gets 2 messages: 1 from vps2 fallback, 1 from vps1 with only vps1+vps3) — OR the hub message includes a `⚠️ vps2 reached via fallback path` line |
| **LIVE-D4**: Missed-digest detector fires | On vps1, manually `rm /opt/fabrik/logs/sysadmin-actions.jsonl`'s most recent `_sent` row, then run digest | Output has `⚠️ MISSED DIGESTS` line |
| **LIVE-D5**: Body shows actual actions, not counts | Verify yesterday's Telegram message body | Contains at least one `• [timestamp] result_excerpt` bullet (assuming real Tier A actions in the last 24h) |
| **LIVE-D6**: Tomorrow morning's actual delivery | Observe what arrives at ~09:XX UTC | One message, fleet-wide, with per-host sections |

### Terminal

| Gate | Command |
|---|---|
| **FINAL-D1**: `scripts/final_gate.py --lean --json` | `{"status": "success"}` |
| **FINAL-D2**: No regression on existing alert paths | `proactive-check.sh` still delivers via Apprise; verify by running it manually |
| **FINAL-D3**: Audit log unchanged shape | `jq -c "select(.source == \"daily_digest\")" /opt/fabrik/logs/sysadmin-actions.jsonl \| tail -3` shows same field structure (+ new `_sent` rows) |

---

## §5. Risks + mitigations

| Risk | Mitigation |
|---|---|
| Hub aro-wake down at digest time → spokes can't forward | Spoke fallback to direct Telegram send via per-host bot token (each spoke already has one provisioned) |
| Combined message exceeds Telegram's 4096-char limit | Truncate per-host bullets to first 3 if combined > 3500 chars; split into multiple messages only if necessary |
| New `/digest-input` route accepts unauthenticated POSTs from the mesh | aro-wake already enforces mesh-only via UFW + 10.99.0.0/24 allow; same trust boundary as `/wake` |
| Adding `_sent` rows doubles JSONL size | Negligible (~120 bytes/day × 365 = 44KB/year per host) |
| Spoke clocks skew → "missed digest" false positive | Tolerance window: only flag if `daily_digest` row exists for date D AND no `_sent` row within 6h of it |
| Change breaks `proactive-check.sh` Apprise path | proactive-check uses Apprise independently; this change doesn't touch its codepath |

---

## §6. Implementation order (deterministic)

| Step | Action | Predecessor gates |
|---|---|---|
| 1 | Run PRE-D1..D5 | — |
| 2 | Operator pastes one real `daily_digest` JSONL row (for PRE-D5) | step 1 |
| 3 | Write `scripts/sysadmin/send-telegram.sh` + shellcheck-clean | step 2 |
| 4 | Update `daily-digest.sh`: add missed-detector, add `_sent` write, add hub vs spoke branch | step 3 |
| 5 | Update aro-wake: add `/digest-input` POST + `/digest-inbox` GET (in-memory deque, 24h TTL) | step 3 |
| 6 | Add bullet-list extractor for Tier A actions (G3) | step 4 |
| 7 | Unit tests for digest formatter + aro-wake routes | steps 4-6 |
| 8 | `final_gate.py` passes; commit + push | step 7 |
| 9 | `fabrik redeploy aro-wake` on vps1 → on vps2 → on vps3 | step 8 |
| 10 | Run LIVE-D1 through LIVE-D5 | step 9 |
| 11 | **Observe LIVE-D6 tomorrow morning** | step 10 |
| 12 | FINAL-D1/D2/D3 | step 11 |

---

## §7. Zero-unknowns checklist

- [x] Every file path that will be edited is verified existing
- [x] aro-wake's source location is identifiable (probe in step 1)
- [x] Per-host bot tokens DO exist as a primary mechanism (verified via vps-ai-sysadmin.md:692)
- [x] Apprise compose surface is single-host (only vps1) — explains the gap
- [x] No new infrastructure required — all changes are within existing services
- [x] Cron schedule + JSONL log paths are stable references
- [ ] Real `daily_digest` JSONL row shape (operator step in §6 step 2 — needed before writing the bullet extractor)
- [x] FINAL gate path is named (`scripts/final_gate.py --lean --json`)
- [x] Risk inventory has a mitigation per row

**Convergence criterion:** all checkboxes ✓ (the one open item is operator input on real JSONL row shape). When that lands → proceed past step 2.

---

## §8. Out of scope

- **Reworking Apprise routing.** Apprise stays as the alert path for `proactive-check.sh` + Gatus + GlitchTip webhooks. We're only changing the digest path.
- **Replacing the per-host bot tokens with a single bot.** Operator can decide later; the per-host design already works.
- **Persisting the digest inbox to disk on hub restart.** In-memory deque is fine for 24h TTL; if hub restarts at 09:00 we lose pending spoke digests for that day — acceptable.
- **Pulling Gatus/GlitchTip events into the digest.** Mention is in the strategic backlog (Apprise pre-route through aro-wake). Not in scope here.

