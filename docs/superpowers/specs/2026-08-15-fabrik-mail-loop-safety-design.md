# fabrik-mail auto-reply loop-safety — design spec

Status: CONVERGED
Date: 2026-08-15
Author: fleet (hub session) — **build owner: infra** (fabrik-mail is infra's beat)
Feeds: `/fabrik-plan-after-chat` → infra executes; this spec is the **deliverable**, not an implementation.
Grounds: `scripts/mail.py` · `docs/reference/fabrik-mail.md` · `docs/superpowers/specs/2026-08-11-fabrik-mail-design.md` (the parent, CONVERGED)

---

## Goal

Make it **safe for an agent to auto-reply to an inbox message without creating an infinite A→B→A messaging
loop.** This is the *buildable half* of the operator's ask "a message auto-wakes the recipient to reply,
without an infinite loop." The **wake half is explicitly deferred** (see § Out of scope) — this spec adds only
the loop-safety guard rails, which are valuable **now** (two actively-running repos' agents can already
ping-pong) and **required** the day native auto-wake (Layer 2) lands.

Success criteria:

1. An unattended auto-reply that would extend a runaway chain is **refused at `mail.py send`** (structurally
   impossible, not merely discouraged) — while a **human-driven** `--re` reply is **never** blocked.
2. The trivial `reply → reply → reply` loop cannot form at all (terminal kinds).
3. A legitimate `request ↔ request` back-and-forth is **bounded** (hop budget) and a flood is **circuit-broken**
   (per-sender rate limit), then surfaced to the operator.
4. Zero new always-on infrastructure; no new state store; fully backward-compatible with existing messages.

## Context (inherited — do NOT re-decide)

fabrik-mail exists and is live fleet-wide. Locked facts read from `scripts/mail.py`:

- **Frontmatter** is `id / from / to / ts / re / kind / ack` (`_frontmatter`, mail.py:209-223). `_parse`
  (mail.py:402-421) reads **arbitrary** keys and only requires `id` + `kind` non-empty → **adding a `hops` key
  is backward-compatible**; a legacy message with no `hops` is read as `hops=0`.
- **`ACK_BY_KIND`** (mail.py:44-50) already encodes the split this design keys on:
  `request`/`upstream-feedback` → `ack: required`; `finding`/`relay`/`reply` → `ack: no`.
- **Claim/ack = atomic rename** (mail.py `claim`/`ack`, 274-377); the ULID gives idempotency; `digest`
  (438-477) already **walks every mailbox** reading frontmatter → a rate count can reuse that pattern with
  **no new store**.
- **Star topology, secret-refusal, 64 KB cap, quarantine** are unchanged and orthogonal to this delta.

## Chosen approach — four layered guards, enforced via a `--auto` send flag

An agent that composes an **unattended** reply passes a new `--auto` flag. `send`, when `--auto` is set, applies
`should_auto_reply(parent)` to the message being replied to (`--re <id>`, resolved in the sender's own mailbox)
and **REFUSES (`MailRefusedError`, exit 2, nothing written)** if any guard trips. Without `--auto`, `send`
behaves exactly as today — **a human is never gated.** The same predicate is exposed read-only as
`mail.py should-reply <id>` so an agent (or the surfacing hook) can pre-check before it even drafts a reply.

Two edge rules make `--auto` well-defined (every parent-based guard needs a resolved parent):

- **`--auto` requires `--re`.** `send --auto` with no `--re` is a **usage error** (`MailRefusedError`) — an
  auto-reply that references no parent has nothing to guard against and would silently bypass guards 1/2/4.
- **Unresolvable `--re` under `--auto` → fail-soft ALLOW.** If `--re` dangles (no such id in inbox+archive —
  `read_msg` raises), the guards have no parent to evaluate; consistent with guard fail-softness (below) the
  send is **ALLOWed** with `hops=0` and a stderr note. A dangling `re:` is already documented as harmless
  (`fabrik-mail.md`), and a wedged channel is worse than a rare un-bounded reply.

**Enforcement is opt-in — and honestly so.** The guard only fires when the agent sets `--auto`; an agent that
omits it on an unattended reply bypasses enforcement. This is inherent to any opt-in guard and is why the
mechanism is **belt-and-suspenders**: the enforced `--auto` refusal is the strong line, and the advisory
`should-reply` verb (+ the optional hook annotation, § Open unknowns) are the pre-checks. The convention doc
MUST instruct agents to **always pass `--auto` on an unattended reply** — the loop-safety is only as strong as
that discipline plus the enforced refusal that backs it.

The four guards (evaluated against the **parent** message being replied to):

1. **Terminal kinds (the primary breaker).** Auto-reply only when `parent.ack == "required"` (i.e. `parent.kind`
   ∈ {`request`, `upstream-feedback`}). A `reply` / `finding` / `relay` is **terminal** — never auto-replied.
   → the trivial `A→B→A` reply loop is *structurally impossible*: a `reply` (ack:no) can never beget a reply.
2. **Hop budget.** New frontmatter field **`hops`**: a human-initiated send = `0`; every `--re` send sets
   `hops = parent.hops + 1` (auto-derived by `send` from the resolved parent — the agent does no arithmetic). If
   `parent.hops >= HOP_CAP` (default **3**), refuse the auto-reply and surface to the operator. → bounds even a
   *legitimate* `request ↔ request` chain. (`hops` increments on **every** `--re`, human or agent — it measures
   thread depth; only the `--auto` guard consumes it, so humans continuing a deep thread are unaffected.)
3. **Per-pair rate limit (circuit breaker).** Count messages from `parent.from` in **this repo's own
   inbox + archive** whose `ts` is within `RATE_WINDOW` (default **3600 s**). If `>= RATE_CAP` (default **5**),
   refuse and hold+escalate. **State is the mailbox itself** — derived per call by the same frontmatter walk
   `digest` uses; no counter store, no Redis (preserves zero-infra + 12-Factor VI statelessness).
4. **Dedup + self-guard.** The ULID + claim-once rename **already** give idempotency (a message resolves once);
   this design adds only the **self-guard**: refuse when `parent.from == <this repo>` (never auto-reply to your
   own message).

Guard order in `should_auto_reply`: **self → terminal-kind → hop-cap → rate-cap → ALLOW**. First trip wins and
names the reason. The predicate is **fail-soft**: if the rate count can't be computed (unreadable mailbox), it
does **not** block — it ALLOWs and logs to stderr (a loop is lower-risk than a wedged channel; mirrors the
hook's fail-open contract).

### The delta (what infra builds)

- **`scripts/mail.py`** (fleet-synced `CORE_SCRIPTS`):
  - Add `hops` to `_frontmatter` (new param) and to `send()` — auto-derive `hops = parent.hops + 1` when `--re`
    resolves to a real parent (via the existing `read_msg` inbox+archive lookup), else `0`.
  - Add constants `HOP_CAP = 3`, `RATE_CAP = 5`, `RATE_WINDOW = 3600` (module-level, near the other caps).
  - Add `should_auto_reply(parent_fm, self_repo, *, now, root) -> tuple[bool, str]` (verdict + reason) and a
    `_recent_from_count(repo, sender, window, now)` helper (mailbox-derived; tolerate `FileNotFoundError`).
  - Add a `send(..., auto: bool = False)` branch: when `auto`, require `--re` (else `MailRefusedError` usage
    error), resolve the parent (fail-soft ALLOW on an unresolvable id), run the predicate, `raise
    MailRefusedError(reason)` on a HOLD verdict — **before** the message is minted/published.
  - Add the `--auto` flag to the `send` subparser and a `should-reply <id> [--repo]` subcommand (prints
    `ALLOW`/`HOLD: <reason>`, exit 0/3).
- **`tests/test_mail.py`**: the guard truth table (self / terminal-kind / hop-cap / rate-cap / allow), the
  `--re` hops-increment property, `--auto` refusal vs un-flagged human send passes through, `--auto`-without-
  `--re` usage refusal, and `--auto` with an unresolvable `--re` fail-soft ALLOWs. Watched-fail-first (red-on-
  revert) on the risky ones: the hop-cap boundary (`==` vs `>=`), the rate-window edge, the self-guard, and
  fail-soft-on-unreadable.
- **`docs/reference/fabrik-mail.md`**: a new "**Loop-safety / auto-reply**" section — the `hops` field in the
  frontmatter table, the 4 guards, the `--auto` enforcement contract **including the always-pass-`--auto`
  discipline on unattended replies**, the `should-reply` verb, the defaults.
- **`docs/workstation/fabrik-mail.md`**: an operator-facing note (what a HOLD looks like, how to override — a
  human `--re` without `--auto`, or bump the cap for a genuine long thread).
- **`CHANGELOG.md`**: one `### Added` entry.

## Rejected alternatives

1. **Always-on mail-responder worker** (a headless `claude -p` per repo watching the inbox and auto-replying) —
   **REJECTED.** Violates fabrik-mail's stated *zero always-on infrastructure* principle
   (fabrik-mail.md:5), adds a supervised process per repo, and duplicates what Layer 2 gives natively. It would
   also make loops *worse* (a tireless responder), not better.
2. **Redis / state-file rate-limit counters** — **REJECTED.** Adds a state store to a deliberately stateless
   file channel; 12-Factor VI would then push that state to `redis-main` (more infra for a hub tool that has
   none). The mailbox already **is** the record — deriving the count per call is O(recent-messages) and needs
   nothing new.
3. **Advisory-only prose (document the guards in `fabrik-mail.md`, no enforcement)** — **REJECTED as the sole
   mechanism.** An LLM agent's judgment is not a guarantee; a single bad turn re-opens the loop. The `--auto`
   enforced refusal makes a runaway *structurally impossible* for unattended replies. (The advisory
   `should-reply` verb is **kept** as a companion pre-check, not the only line of defense.)
4. **Hard-refusing all deep-hop `--re` replies at `send` (no `--auto` distinction)** — **REJECTED.** `send`
   cannot tell a human-driven reply from an auto one; a blanket refusal would block a human continuing a
   legitimate long thread. The `--auto` flag is exactly what separates "unattended, guard me" from "a human is
   driving, don't."

## Out of scope — DEFERRED live auto-wake (Layer 2)

The **wake** half — a message *automatically waking* the recipient to reply — is **not designed here**:

- Native Claude Code **cross-session messaging (Layer 2)** provides auto-wake (socket delivery into a running
  session) **and** its own loop-throttling (per-sender rate limit + dedup + unread cap) for same-machine
  session-to-session. It is **flag-gated OFF** on these accounts today (`/list-agents` returns "Unknown
  command"; `CLAUDE_CODE_MESSAGING_SOCKET` empty — memory `project_intra_repo_session_comms_layer2`), an
  Anthropic-side rollout wait with no local toggle. **adopt-not-build applies when the flag lands.**
- For a *running-idle* session, a self-armed inbox `Monitor` could wake it — noted as an **option**, not
  specced. A **closed** interactive window fundamentally cannot be externally woken without an always-on
  responder (rejected above).
- **Composition when Layer 2 lands:** socket = the live doorbell; file = the durable truth; **these guards** =
  the loop-safety on the file side. They compose — the guards do not depend on Layer 2, and Layer 2 does not
  replace them (it covers session-to-session same-machine; the mailbox covers durable cross-repo).

## External dependencies

**None — N/A.** This is internal `mail.py` logic over the local filesystem. No 3rd-party API, SDK, pricing, or
rate limit is touched, so the live-research gate (1a) has nothing to ground. The one external *fact* the design
leans on — Layer 2's flag state — is already grounded in memory + `CLAUDE.md` and re-confirmed this session by
the operator's `/list-agents` probe.

## fabrik-lib verdict

| Capability | Verdict | Why |
|---|---|---|
| loop-safety guard predicate | **BUILD (in `mail.py`)** | Not a generic capability — it is specific to fabrik-mail's kinds/frontmatter/mailbox layout. No fabrik-lib module models a mail protocol; a guard bolted onto this protocol has no reuse surface. **No `🆕 fabrik-lib candidate`** — it fails the generic + ≥2-types bar (it is hub mail-tooling, not a portable primitive). |

No module is vendored or enhanced; the digest already vendors `libs.alerting` and is untouched by this delta.

## Shape / infra implications

**None.** No scaffold type, no `shape:` flag, no Docker service, no DB, no new port. `mail.py` stays a
stdlib-only CLI; the guard is stateless computation over existing files. No data-contract change (no DB/user
fields — the store is markdown files).

## Constraints digest (design-shaping rows this delta must honor)

| Rule | Source | Implication here |
|---|---|---|
| Zero always-on infrastructure | `docs/reference/fabrik-mail.md:5` | rate-limit state is **mailbox-derived**, never a daemon/store |
| 12-Factor VI — stateless processes | `agents-fabrik.md` § Architectural Mandates | the guard holds **no** cross-call state; recomputed from files each call |
| 12-Factor XI — logs to stdout, no logfiles | `mail.py:22` (already) | HOLD/skip diagnostics go to **stderr**, never a logfile |
| Fail-soft for optional components | memory `feedback_failclosed_vs_failsilent` + hook contract | an unreadable-mailbox rate check **ALLOWs** (never wedges the channel) |
| Shared-tree / fleet blast radius | `CLAUDE.md` § Sync-consciousness | `mail.py` is `CORE_SCRIPTS` (synced) — the change is **additive + backward-compatible**, correct for all ~46 repos |

Everything else the design touches is **unconstrained** (no pack cuts an approach).

## Open / blocking unknowns

- **Cap values** (`HOP_CAP=3`, `RATE_CAP=5`, `RATE_WINDOW=3600 s`) — **RESOLVED to sensible defaults**, operator-
  overridable via env at build time if wanted; none is a blocking unknown (a wrong default is a one-line change,
  not a design flaw). infra may tune during build if the dogfood traffic suggests it.
- **`should-reply` consumed by the hook too?** — **OPEN (non-blocking), infra's call at build.** Annotating each
  surfaced message with its verdict (`[auto-reply: HOLD — hop cap]`) is a nice-to-have; it adds logic to the
  fail-open hook. Default: ship the `should-reply` verb as the SSOT; add the hook annotation only if it stays
  trivially fail-open. Not required for the guard to work.

No Phase-1 BLOCKING unknown (no external fact to verify), no unanswered Phase-2 question.

## Sync-consciousness

`scripts/mail.py` **IS a governance-sync trigger** — `mail` is named in the `governance-sync` files-filter
(`.pre-commit-config.yaml:64`, `^scripts/(final_gate|…|mail)\.py$`), so the commit that edits it **fires the
sync itself** and distributes `mail.py` **fleet-wide to ~46 repos at that commit** (not "rides the next
unrelated sync"). infra must therefore treat the mail.py commit as a fleet-distribution event: the change must
be correct for **all** repos at commit time. It is — **additive and backward-compatible**: the new optional
`hops` key is parsed as `0` when absent, the `--auto` flag defaults off (existing sends unchanged), and the
`should-reply` subcommand is inert until called; every repo's mail.py gains the identical guard.
`docs/reference/fabrik-mail.md` is **not** in the trigger filter → it is a manifest-synced reference doc that
rides the next trigger-caused sync; `docs/workstation/fabrik-mail.md` and `tests/test_mail.py` are hub-local
(not synced). No **other** trigger surface changes (no `.windsurf/rules`, `scripts/enforcement`, hook, or
settings) — the mail.py edit is the one and only fleet-distribution trigger in this build.
