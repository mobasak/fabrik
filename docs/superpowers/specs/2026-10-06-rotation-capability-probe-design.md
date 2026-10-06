# Rotation capability probe — an account that refuses inference is never the next account

Status: DRAFT
Profile: delta
Size: small (≈170 lines, 2 files — `claude_rotate.py` and its byte-identical `scripts/aro-wake/` twin)
Work item: W-f8bfe7eb · Evidence: fleet mail 01M3QG6GG5NQNVG5MZE6SAME1G · Detection half: W-ffd390d2 (done)

## Personas

- **The operator** (primary). Their own words, D-443: *"make it unusable untill i say it is avaiable again"* and *"enabling it must be easy. even put a button in the gui so i can enable disable them manually too"*. Their loop when an account's billing lapses is **3 steps** (the frozen step budget): (1) read the alert naming the account and the cause; (2) fix the billing or the org setting outside the box; (3) re-enable the account with one action (`--unpark <email>` or the dashboard's enable button). Today it is 5+: notice sessions failing, diagnose the refusal text, find the account, `--switch` away by hand, `--park` it by hand (mail 01M3QG6G § WHEN).
- **Every Claude Code session on the box** (automated consumer). It follows the `active` pointer. It holds no duty here, but it is the one trapped when the pointer names a refusing account ("Typing 'proceed' does not help, because every retry hits the same account" — mail 01M3QG6G § WHEN).
- **The rotation tick** (`claude_rotate.py --tick`, cron every 5 min; automated). It holds the new duty: probe a candidate before promoting it, and auto-park on a definitive refusal.
- **The quota dashboard and `--status`** (automated readers of `parked.json` and the ledger). They hold no new duty but must render an auto-parked account the same way as an operator-parked one (D-443: listed, never capacity).

## Lifecycle

Adoption: it lands in the tick with no flag and no new file; the first refusing candidate it meets is parked and alerted. Growth: one probe per automated promotion, bounded by the 30-minute dwell (`ROTATE_DWELL_MIN`) and an OK-verdict cache (6 h), so at most ~4 probes per account per day with 4-5 accounts. Revisit if the fleet passes ~10 accounts or a probe's p95 latency exceeds 60 s. Failure: an inconclusive probe (timeout, network, any error that is not the definitive refusal) changes nothing. The pick proceeds as today and the result is logged, so a probe outage can never take accounts out of service (D-443's fail-open-on-broken-state stance). Retirement: if Anthropic ships a documented capability or entitlement read for subscription OAuth, the probe is replaced by that read.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "Spec the prevention half" (W-f8bfe7eb title) | IN | § The delta |
| I2 | "probe-on-flip vs per-tick" | IN | § Chosen approach, § Rejected alternatives |
| I3 | "claude -p (full CLI, fires hooks) vs a minimal OAuth messages call (undocumented contract — ground it first)" | IN — the OAuth call is cut by grounding | § External dependencies G2, § Rejected alternatives |
| I4 | "the quota cost" | IN | § Cost |
| I5 | "auto-park on the refusal" | IN | § The delta D3 |
| I6 | "W-ffd390d2 (alert hook) is the detection half" | OUT-OF-SCOPE — already built; this spec only reuses its alert path | W-ffd390d2 (done) |
| I7 | "SYSTEMIC: every health probe that checks credentials rather than the capability actually used has this blind spot" (mail 01M3QG6G) | OUT-OF-SCOPE — other probes on the box are not this item | recorded in § Open unknowns U3 |
| I8 | "fires hooks" (the CLI probe runs session hooks) | IN | § The delta D1 (headless env) |

Intake: 8 items — 6 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.

## Goal

When the tick is about to promote an account to `active`, it first proves the account can actually serve a Claude Code call. An account refused with `oauth_org_not_allowed` is parked, alerted and skipped, so the pointer never lands on it. The operator's 3-step re-enable loop is unchanged.

## Why this exists

On 2026-09-29/30, mob and then ob were refused on every Claude Code call: "Your organization has disabled Claude subscription access for Claude Code". The tick kept ob as successor and then active, and every session on the box was trapped until the operator switched by hand at 00:07 (mail 01M3QG6G). The picker's checks are a usage reading and refresh-chain liveness (`scripts/sysadmin/claude_rotate.py:3559-3625`, `_chain_stale_reason` `:3044`), and neither exercises inference. The one inference call the tick does make, the refresh ping (`:4040-4060`), runs only when a reading is stale, so a healthy reading hid the refusal.

## What exists today (grounded)

- `_validated_pick` (`claude_rotate.py:3559-3625`) returns the first candidate whose reading is live, or whose cached reading passes a live usage probe; it never runs inference.
- `_flip_active` (`:3139`) is the only place the pointer moves; its gates are credentials, chain liveness, pause and dwell (`:3157-3167`).
- `_keepalive_ping` (`:7129-7158`) runs `claude -p ping` bound to one fleet dir with `CLAUDE_MESH_HEADLESS=1` and `CLAUDE_SOUND_NO_REVIVE=1`, and returns only `returncode == 0`. Its caller marks any failure `ping_failed` (`:4060`), the dead-chain flip trigger.
- Parking (D-443): `_cmd_park` (`:3873-3900`) read-modify-writes `<fleet_root>/parked.json` with no lock; `_parked_accounts` (`:3827-3850`) reads it and a broken file parks nothing; `_account_caps` reads a parked account as cap 0, so every reader that handles a cap wall already handles a park.
- The file is vendored byte-identical into `scripts/aro-wake/claude_rotate.py` (header `:1-4`).

## External dependencies

| # | Fact | Source (fetched 2026-10-06) |
|---|---|---|
| G1 | `claude -p --output-format json` reports an in-run failure on stdout as the result JSON with `is_error` and `api_error_status`, and exits non-zero: "When a failure happens inside the run, such as missing authentication, Claude Code prints the failure as the result on stdout." | https://code.claude.com/docs/en/headless |
| G2 | Subscription OAuth "is intended exclusively for purchasers of Claude Free, Pro, Max, Team, and Enterprise subscription plans and is designed to support ordinary use of Claude Code and other native Anthropic applications"; no OAuth Messages endpoint is documented. | https://code.claude.com/docs/en/legal-and-compliance · https://platform.claude.com/docs/en/api/beta-headers |
| G3 | The refusal "is a server-side organization setting, so it can't be overridden from local settings, environment variables, or CLI flags. The Agent SDK and `-p` non-interactive mode surface this as the `oauth_org_not_allowed` error code." | https://code.claude.com/docs/en/errors |
| G4 | `--max-turns`: "Limit the number of agentic turns (print mode only)"; `--tools ""` disables all tools. | https://code.claude.com/docs/en/cli-reference |
| G5 | Approach: a check of a dependency belongs on the gate that admits traffic (readiness), not on the reflexive one — "the readiness probe additionally checks that each required back-end service is available. This helps you avoid directing traffic to Pods that can only respond with error messages." | https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/ |
| G6 | Approach: re-admit a target only after a trial of the real operation — "a circuit breaker can periodically ping the remote service or resource to determine whether it's available. This ping can either attempt to invoke a previously failed operation or use a special health-check operation". Dependency checks acted on automatically need thresholding (AWS Builders' Library, quoted via siddharthsarda.com; the canonical page did not render). | https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker · https://www.siddharthsarda.com/p/service-health-and-health-checks |

## Constraints digest

| Rule | Quote | Source | Applies |
|---|---|---|---|
| every external call bounded | "every external call has timeout + retry with backoff. Circuit-breaker for repeated failures. Graceful fallback when dependencies are down." | .windsurf/rules/core/58-resilience.md:88 | the probe has a timeout and falls back to today's pick when inconclusive |
| timeouts owned by resilience | "Timeouts/retries on every outbound call are owned by `58-resilience.md`." | .windsurf/rules/core/10-python.md:218 | the probe reuses `_keepalive_ping`'s bounded subprocess timeout |
| parked means never picked | "A parked account stays listed, pinned and logged in, but is never an automated flip target" | docs/DECISIONS.md:158 | auto-park writes the same `parked.json`, so every reader handles it already |
| broken park state fails open | "A broken `parked.json` parks NOTHING and warns loudly" | docs/DECISIONS.md:158 | an auto-park write failure is logged and the candidate is still excluded for this tick only |

Stdlib-only, byte-identical vendoring (`claude_rotate.py:1-4`) rules out new imports; the FastAPI-only rules of `core/10-python.md` (structlog, `HTTPException`) do not apply to this script.

## The delta

- **D1 — a classifying probe.** `_capability_probe(cfg_dir) -> "ok" | "refused" | "inconclusive"` runs `claude -p ok --output-format json --max-turns 1 --tools ""` with `_keepalive_ping`'s headless environment and timeout. It returns `refused` only when the stdout JSON has `is_error` true AND either `api_error_status == 403` with `oauth_org_not_allowed` in the result text, or the text names `oauth_org_not_allowed` (G1, G3). It returns `ok` on exit 0 with `is_error` false. Anything else is `inconclusive`. It never keys on `subtype`, whose enum spellings were not fetched raw (§ Open unknowns U1). The headless env vars keep the box's session hooks from treating the probe as a session (I8).
- **D2 — probe on promote.** Before `_validated_pick` returns an automated flip target, it runs D1 bound to that candidate's config dir. It skips the probe when the candidate holds an `ok` verdict younger than 6 h (`<state>/capability-probe.json`, keyed by email; `ROTATE_PROBE_TRUST_S`, default 21600). On `refused` it applies D3, excludes the candidate and considers the next one, exactly as the loop's existing exclude-and-continue does for a walled live reading (`:3612-3615`). On `inconclusive` it returns the pick as today and logs one line. On `ok` it records the verdict and returns. A manual `--switch` never runs the probe (D-443's escape hatch).
- **D3 — auto-park.** A `refused` verdict parks the account through the same writer as `--park`, under a lock (D5), appends a `{"event": "auto-park", "email", "cause": "oauth_org_not_allowed", "ts"}` row to `rotate-ledger.jsonl`, and sends one alert through the existing Telegram path naming the account, the cause and the one-step fix (`--unpark <email>` after the org or billing is fixed). The operator owns un-parking (D-443); nothing auto-unparks.
- **D4 — the existing ping classifies too.** `_keepalive_ping` returns the D1 verdict instead of a bool. `refused` auto-parks (D3) instead of marking `ping_failed`, since the chain is alive and only the capability is gone. `inconclusive` keeps today's `ping_failed`.
- **D4b — the CLI wrapper classifies too.** The wrapper that already rotates on a usage limit or a `401` (module docstring `:11-17`) recognises the `oauth_org_not_allowed` refusal the same way: it auto-parks (D3) and rotates. This adds no new call.
- **D6 — the active account is re-validated.** A refusal can first appear on the account that is ALREADY active, mid-session. D2 never sees that case, and with healthy readings the staleness-gated ping (`:4040`) never fires either (judge 2's split, § Chosen approach). So the tick also runs D1 against the ACTIVE account whenever that account's `ok` verdict is older than the D2 trust window. That is one probe per 6 h, about 4 per day, never every tick. `refused` → D3, and the parked active account is flipped away from on the same tick, like any cap-walled one (D-443). `inconclusive` → nothing changes.
- **D5 — one lock for `parked.json`.** `_cmd_park` and the auto-park take the same `fcntl` lock (the assignments lock pattern, `:3692-3716`) around the read-modify-write, so a dashboard click and a tick park cannot lose one another's write.

## Cost

One probe is one Claude Code turn with no tools on a one-word prompt, drawn from the probed account's subscription quota. With D2's cache (an `ok` verdict is trusted for 6 h) and the 30-minute dwell, the ceiling is ~4 promote probes per account per day plus ~4 active re-validations (D6); at 4-5 accounts that is ≤24 small calls per day across the fleet. A refused account costs one probe, then none, because it is parked.

## Validation

- A fixture `claude` stub on PATH prints the documented refusal JSON (`is_error: true`, `api_error_status: 403`, text with `oauth_org_not_allowed`) for one fleet dir. `_validated_pick` must skip it, `parked.json` must list it, and the ledger must carry the `auto-park` row; red before the change.
- The same stub timing out yields `inconclusive`: the pick proceeds and nothing is parked.
- A manual `--switch` to the refused dir is never probed and still flips (D-443's escape hatch).
- Two concurrent `_cmd_park` calls each land their email (D5).
- The ACTIVE account's dir returning the refusal, with an expired `ok` verdict, is parked and flipped away from on that tick (D6). With a fresh `ok` verdict it is not probed.
- The wrapper running a session call that returns the refusal parks the account and rotates (D4b).
- The vendored twin is byte-identical (`cmp`).

## Chosen approach

**Probe on promote** (D1-D5). The real operation is tried once, at the moment an account is about to receive the fleet's traffic: the readiness and circuit-breaker shape (G5, G6). A definitive refusal quarantines the account through D-443's existing park, and the operator re-admits it. The judge panel was three independent Sonnet seats, given the approaches unlabeled and in alphabetical order. Two ranked probe-on-promote first. **The split:** judge 2 ranked passive classification first, because neither promote-time nor stale-ping probing can see a refusal that first appears on the already-active account mid-session. That gap is real, and the design closes it rather than recording it: D4b adds the wrapper's zero-cost classification, and D6 re-validates the active account once per trust window. The split is carried to the approval gate as an open question: is a ≤6 h detection window for an active-account refusal acceptable, or should the trust window be shorter?

## Rejected alternatives

- **Passive classification only.** This reads the refusal from the existing ping and from failed sessions, and adds no new call. It is kept as D4, a free part of the chosen approach, but rejected as the whole answer. The ping fires only on a stale reading (`:4040`), so on 2026-09-29 it would never have run before promotion, and the box would still have been trapped once.
- **Probe every standby every tick.** Killed. It spends a call per standby every 5 minutes on accounts nobody is about to promote, and the cited practice warns that deep checks acted on automatically every tick produce correlated false positives (G6).
- **A raw Messages API call with the subscription OAuth token.** Cut by grounding: it is outside "ordinary use of Claude Code", and no endpoint for it is documented (G2).
- **Auto-unpark after a timer, or on a later successful probe.** Cut by D-443: the operator owns re-enabling.

## Decisions taken

D-614 records the placement decision, minted in this spec's commit. It covers probe on promote, auto-park on the definitive refusal, and un-parking owned by the operator.

## fabrik-lib verdict

One line: no fabrik-lib module covers Claude subscription rotation; this is a delta inside the hub's own `claude_rotate.py` (BUILD, in place).

## Shape / infra implications

None: a box-local cron script, no service, no `shape:` flags.

## Documentation landing sites

`docs/workstation/claude-account-rotation.md` § Parking (an auto-park and its alert), the module docstring of `_validated_pick`, `CHANGELOG.md`, and the D-row.

## Open unknowns

- U1 — the exact `subtype` enum spellings of the result JSON were not fetched raw. Resolution: D1 does not key on `subtype`; the plan's red test pins the fields D1 does read.
- U2 — whether a `refused` result always carries `api_error_status == 403`. Resolution: D1 also accepts the documented `oauth_org_not_allowed` code in the text alone.
- U3 — other box probes may share the credentials-not-capability blind spot (mail 01M3QG6G § SYSTEMIC). Resolution: out of scope here; filed as a backlog row with the plan.
