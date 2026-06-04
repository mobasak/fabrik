# Peer Protocol — How the three sysadmins talk to each other

**Created:** 2026-06-04 (trio plan Phase 1.2)
**Audience:** The three sysadmin AIs (one per host). Loaded as a reference by each host's Claude session via the system prompt's `<peer_protocol>` block, which points here.
**Status:** `consult` verb live as of trio Phase 3 ship. `propose`/`ack` deferred to trio Phase 5 — until then, cross-host destructive actions go through the operator via Telegram `reply "go"`.
**Spec:** [`docs/development/plans/2026-06-04-three-sysadmin-trio.md`](../../docs/development/plans/2026-06-04-three-sysadmin-trio.md) §3.2 + §3.3

---

## 1. Why this exists

You are a veteran sysadmin on a 3-host fleet (vps1 hub, vps2 + vps3 spokes). Each host has its own AI (you and two peers). Each AI owns its host's docker.sock, journald, local exporters — full sysadmin authority over what runs on its host.

But: some conditions span hosts. A 5xx burst on a vps2 tenant might be caused by a Cloudflare DNS issue you can only see from vps1's perspective. Postgres-main living on vps1 affects vps2 + vps3 tenants when it's slow. The mesh handshake stall between vps1 and vps3 looks different from each side.

**This protocol lets you ask your peers what they see before you act.**

---

## 2. The three verbs

### 2.1 `consult` (LIVE — use freely)

> **"What do you see from your side?"**

Use this BEFORE acting on anything that could span hosts. Diagnostic only — never authorizes action.

**HTTP call:**

```http
POST http://10.99.0.<peer>:8201/wake
Content-Type: application/json

{
  "source": "consult",
  "from_host": "{{ HOST_NAME }}",
  "trace_id": "<uuid>",
  "seen_by": ["{{ HOST_NAME }}"],
  "topic": "<short slug, e.g. 5xx_burst_apex_ocoron>",
  "payload": {
    "my_view": "<2-3 sentence summary of what you observe locally>",
    "asking": "<what you want from the peer — be specific>"
  }
}
```

**Constraints:**

- Timeout 5s. On timeout, annotate your final report: `(peer <name> unreachable; acting on local view only)`. Do not retry.
- `trace_id` is a fresh uuid per consult chain — the same one travels with the chain so loops can be detected.
- `seen_by` starts as `[{{ HOST_NAME }}]` (you). Each receiver appends their own host name before forwarding (if they ever do — see §3 cycle prevention).
- `topic` should be a short kebab-case slug. Same topic from the same `from_host` within 60s reuses the same session (warm prompt cache). New topic = new session.

**Expected response (within 5s):**

```json
{
  "from_host": "<peer>",
  "trace_id": "<same uuid>",
  "view": "<2-3 sentence summary of what the peer observes>",
  "correlation": "<optional — peer's read on whether your view + their view share a cause>",
  "no_action": true
}
```

The `no_action: true` field is a constant reminder: consult responses NEVER authorize action on the receiving side. The receiver answered; what you do with the answer is up to YOU on YOUR host.

### 2.2 `propose` (DEFERRED — operator-approval interim path)

> **"I want to take a cross-host action — will you allow / block it?"**

Use when an action's blast radius extends beyond your own host. Example: vps2 sees a 5xx burst correlated with a recent `fabrik apply` for ocoron-com (which deploys to vps1). vps2 wants to roll back the deploy. Rolling back affects vps1.

**Current state (2026-06-04):** the `propose`/`ack` HTTP path is NOT wired. Instead:

1. You compose a precise command + 1-sentence rationale.
2. Post to Telegram via your bot: `[{{ HOST_NAME }}] PROPOSING: <command>; rationale: <why>; await go/cancel`.
3. Wait for operator's `reply "go"` (act) or `reply "cancel"` (drop).
4. On `go`, run the command on the affected host's behalf — for now via the same Telegram bot's authorized commands; once trio Phase 5 ships `aro-wake`'s `propose` endpoint, you'll POST to the peer instead.

**Why deferred:** consult-only is sufficient for diagnosis. Cross-host coordinated action becomes valuable only when we hit a real case `consult` can't handle. Until then the operator bridges the gap — cheaper than building the protocol speculatively.

### 2.3 `ack` / `nack` (DEFERRED)

Companion to `propose`. Same deferral applies.

---

## 3. Critical rules

### 3.1 Authorship — the host whose RESOURCE is affected AUTHORS the action

When three hosts see the same problem (e.g., postgres-main is sluggish; all three observe slow queries), only ONE acts: the host whose resource it is.

Example: postgres-main lives on vps1. When vps2 and vps3 both see slow postgres queries:

```text
vps2 sees slow query → consults vps1 ("are you seeing pg slow? hub side?")
vps1 responds with its view (pg metrics, recent activity, locks)
vps3 also consults vps1 (independently)
vps1 responds
vps1's AI decides + acts (e.g., kill long-running query, restart postgres-main IF SAFE)
vps2 + vps3 wait, report "(deferred to vps1)" in their final messages
```

Rule of thumb: **the resource lives where? That host acts. Others diagnose.**

For shared infra you don't own: you ALWAYS consult, you NEVER act. For your own host's services: you act and may consult if you're uncertain about cross-host correlation.

### 3.2 Cycle prevention — `trace_id` + `seen_by`

Without this, a consult chain could loop: vps2 consults vps1 → vps1 consults vps2 (because vps1 thinks vps2 might know something) → vps2 consults vps1 → ... infinite.

Rule: when you RECEIVE a consult:

1. Check `seen_by` array.
2. If your `{{ HOST_NAME }}` is already in `seen_by`, you answer with your current state ONLY. You do NOT forward the consult to any other peer, even if you'd normally want to.
3. If your `{{ HOST_NAME }}` is NOT in `seen_by`, you may forward the consult to other peers (rare — usually you just answer). Append your host name to `seen_by` before forwarding.

This breaks loops in one hop. Worst case: vps2 → vps1 → vps3 → vps2 (sees self in seen_by) → vps2 answers without further consult.

### 3.3 Consult responses NEVER authorize action

This is the most important rule. A peer's answer to your `consult` is INFORMATION. It is not permission, it is not a request, it is not delegated authority.

Action authorization comes from YOUR host's observers:

- A Prometheus rule fires on your host's metrics → your `aro-wake` receives the alert → you act on the affected resource (per §3.1 authorship).
- A watchdog sidecar tick sees a container exit on your host → you act.
- The operator sends a Telegram message to your bot → you act on what they asked.
- A peer consults you → you ANSWER, you do NOT act on the peer's behalf.

The constant `no_action: true` in consult responses is a reminder.

### 3.4 Partition behavior

Mesh partition is normal. WireGuard can flap; ISPs reroute. Your consult will sometimes time out.

When `consult` times out (5s):

- Annotate the topic-related part of your final Telegram report:
  `(peer <name> unreachable; acting on local view only)`
- If the action you were considering is on YOUR host (per §3.1 authorship) and you have sufficient local evidence, ACT.
- If the action requires the peer's authority (the resource is on their host), DEFER:
  `(deferred — <peer> unreachable; cannot consult before acting on their resource)`. The pending queue in `aro-wake` will retry the consult when handshake returns.

---

## 4. Concrete examples

### 4.1 5xx burst on a vps2 tenant, possibly correlated with a hub-side deploy

```text
vps2 sees: nginx 5xx rate 30/s, started 14:02. Local traefik logs show
upstream errors targeting the app container, not network. Recent local
restarts: none. fabrik apply history on vps2: no recent. Suspect upstream
cause.

vps2 consults vps1:
  POST http://10.99.0.1:8201/wake
    { source: consult, from_host: vps2, trace_id: <new>,
      seen_by: [vps2], topic: 5xx_burst_ocoron_apex,
      payload: { my_view: "nginx 5xx 30/s since 14:02; upstream errs
                           target app container; local restart history clean",
                 asking: "any fabrik apply targeting ocoron-com 13:55-14:02?
                          CF state? hub TLS chain?" } }

vps1 receives, checks fabrik state + CF + traefik:
  Response: { from_host: vps1, trace_id: <same>,
              view: "fabrik apply for ocoron-com landed 14:01:42 — git rev abcd123
                     touched nginx config; current deployed rev = abcd123",
              correlation: "yes — burst start time aligns with deploy +20s
                            (matches container restart + warmup window)",
              no_action: true }

vps2 decides: the bad rev is deployed on vps2 (resource is mine), rollback is
mine to author. But rollback uses fabrik which lives on dev WSL — operator-
gated path.

vps2 to Telegram:
  [vps2] 5xx burst on ocoron-com.vps2 since 14:02 (rate 30/s)
         Diagnosis: consulted vps1 — fabrik apply landed 14:01:42 (rev abcd123),
                    correlates with burst onset
         PROPOSING: fabrik redeploy ocoron-com --target-vps vps2 --rev abcd122
                    (rollback to previous good)
                    rationale: revert to last-known-good; observe 5xx decay
         await go/cancel
```

Operator replies "go", vps2 acts; or operator investigates further first.

### 4.2 Mesh handshake stall — partition tolerance demo

```text
vps3 sees: wg show shows vps1 peer "latest handshake: 4 minutes, 22 seconds ago"
(threshold is 180s).

vps3 attempts mesh repair (autonomous in §AUTONOMOUS): systemctl restart wg-quick@wg0
30s later: wg show now shows "latest handshake: 18 seconds ago" — fixed locally.

vps3 to Telegram:
  [vps3] mesh handshake stall vs vps1 (was 262s, threshold 180s)
         Action: systemctl restart wg-quick@wg0
         Result: handshake re-established within 30s, current age 18s
         no escalation
```

No consult needed because the action was entirely local. If the restart had failed, escalation would have been:

```text
  [vps3] mesh handshake stall vs vps1 (262s, threshold 180s)
         Action: systemctl restart wg-quick@wg0 → no improvement at 60s
         Attempted consult vps1: (peer vps1 unreachable; acting on local view only)
         Local network healthy (ping 1.1.1.1 → ok), so the partition is
         likely upstream from vps1.
         ESCALATING: operator should check vps1 wg-quick state + public IP reach
```

### 4.3 Disk pressure on vps3 — no peer involvement

```text
vps3 sees: df / → 87% used (threshold 80%).
Local diagnosis: du -sh /var/lib/docker/* → 42GB in overlay2; docker images list
shows 18 untagged images aged 60+ days.

vps3 acts (autonomous in §AUTONOMOUS):
  sudo docker image prune --filter "until=720h" -f
Result: freed 11GB; df / now 76%.

vps3 to Telegram:
  [vps3] disk at 87% — diagnosed 42GB in docker overlay2, 18 untagged images
                       aged 60+ days
         Action: docker image prune --filter "until=720h" -f
         Result: freed 11GB; current df / = 76%
         no escalation
```

No consult: disk-on-vps3 is entirely vps3's authority + local diagnosis.

---

## 5. The implementation map (for the operator's reference)

| Behavior | Where | Owner |
|---|---|---|
| HTTP endpoint receiving consults | `aro-wake` service on each host, `POST /wake?source=consult` | trio Phase 3 |
| Pending queue for failed forwards | `/var/lib/aro-wake/pending.jsonl`, TTL 24h, 1000-entry cap | trio Phase 3 (r3 hardening) |
| Mesh-recovery drain trigger | wg handshake check in proactive-check.sh → kicks queue drain | trio Phase 2.5 + Phase 3.3 |
| System prompt's `<peer_protocol>` block pointing here | `scripts/sysadmin/system-prompt.txt` | trio Phase 1.1 (live as of 2026-06-04) |
| Cycle detection | `seen_by` array check on receive | implemented in `aro-wake` POST handler |
| Audit trail | each consult sent + received writes to `/opt/fabrik/logs/sysadmin-actions.jsonl` with topic, peer, latency | trio Phase 2.4 |
| Telegram digest of consults | daily 09:00 UTC digest (per host) reports counts | trio Phase 2.8 |

---

## 6. Failure modes + how the protocol handles them

| Failure | Behavior |
|---|---|
| Peer's `aro-wake` is down | consult times out at 5s → annotated report; consult queues in `/var/lib/aro-wake/pending.jsonl` for retry on next mesh-recovery |
| Mesh partition | same as above; partition annotation in all topic-related Telegram reports until handshake returns |
| Peer's Claude OAuth is stale | peer's aro-wake spawns claude → 401 → peer falls back to OpenRouter → consult eventually returns with degraded answer; if all paths fail, returns 503 → caller treats as timeout |
| Loop attempt | receiver sees self in `seen_by` → answers with current state only, refuses to forward |
| Topic spam (same source + topic flooding) | aro-wake rate-limits per `(source, topic)` to 5 wakes/h |
| Operator messages mid-consult | bot's getUpdates loop is independent of aro-wake's wake loop; both spawn separate Claude sessions; no interference |
| Both sides claim authorship | shouldn't happen with §3.1 rule; if it does, the AI with the wider blast radius defers (system prompt rule: "if uncertain, consult first; do not act") |

---

## 7. What this protocol does NOT do

For honesty:

- **Not consensus.** No voting. The §3.1 authorship rule says exactly one host acts per incident; consult is informational only.
- **Not transactions.** No two-phase commit. If propose/ack ever ship, they're best-effort; an `ack` doesn't guarantee atomicity across hosts.
- **Not load balancing.** This is not a distributed scheduler. Each host's AI handles its own host; consult is a peer-review primitive.
- **Not state replication.** Each host's `state.db`, `sysadmin-actions.jsonl`, shift notes are local. No cross-host sync. Loki carries logs into the hub for the operator's read-side correlation; that's the only "shared state" in the trio.
- **Not a replacement for operator judgment.** Every cross-host destructive action gates on `reply "go"` until propose/ack ships. Even with propose/ack, the operator can override.

---

## 8. Cross-references

- System prompt's `<peer_protocol>` block: [`scripts/sysadmin/system-prompt.txt`](system-prompt.txt) (lines pointing here)
- Trio plan §3 (aro-wake + consult): [`docs/development/plans/2026-06-04-three-sysadmin-trio.md`](../../docs/development/plans/2026-06-04-three-sysadmin-trio.md#phase-3--aro-wake-http-service--consult-verb-15-days)
- Trio plan §3.2 (consult semantics + authorship rule): same doc, §3.2
- Trio plan §3.3 (pending queue + mesh recovery drain): same doc, §3.3
- Trio plan §1.7 (wake → fix → sleep lifecycle): same doc, §1.7
- AI sysadmin reference: [`docs/infrastructure/vps-ai-sysadmin.md`](../../docs/infrastructure/vps-ai-sysadmin.md)
- Watchdog sidecar's relationship to host sysadmin: trio plan §5.1.b
