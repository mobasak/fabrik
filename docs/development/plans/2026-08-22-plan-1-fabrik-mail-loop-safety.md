# Plan — fabrik-mail auto-reply loop-safety (the four guards + `--auto`)

Status: CONVERGED
Date: 2026-08-22
Owner: infra (build) — spec by fleet (`docs/superpowers/specs/2026-08-15-fabrik-mail-loop-safety-design.md`,
CONVERGED b886ce5b; build assigned via mail `01M02SV4498PHFBG3SM8KN1TR9`, acked)
Executor entry: `/fabrik-execute-plan docs/development/plans/2026-08-22-plan-1-fabrik-mail-loop-safety.md`

Pass Ledger (/fabrik-plan-review, 2026-08-22):
| Pass | axes re-checked | raised | new: | edits | plan md5 (start → end) |
|-----:|---|---:|---:|---:|---|
| 1 | all (wide: every claim re-grounded on current mail.py) | 4 | 4 | 3 | f9f0e385… → 71a8db18… |
| 2 | scoped: pass-1 edits' new line refs | 1 | 1 | 1 | 71a8db18… → c5a5dbda… |
| 3 | all (closing wide: mechanical 15-ref sweep + spec-delta coverage) | 0 | 0 | **0** | c5a5dbda… → c5a5dbda… ✓ → **CONVERGED** |
(The status flip below is the sanctioned post-convergence write, exempt per the term-edit contract.)

## What we already agreed (from the spec — do not re-decide)

- **Goal:** an unattended auto-reply that would extend a runaway chain is REFUSED at `mail.py send`
  (structurally impossible), while a human `--re` reply is NEVER gated. Operator (2026-08-22): "go".
- **Mechanism:** a `--auto` send flag gating `should_auto_reply(parent)`; guard order
  self → terminal-kind → hop-cap → rate-cap → ALLOW; first trip wins, names the reason; fail-soft
  (unreadable mailbox / unresolvable parent → ALLOW + stderr note). `--auto` requires `--re`.
- **The four guards:** (1) terminal kinds — auto-reply only when `parent.ack == "required"`;
  (2) hop budget — new backward-compatible `hops` frontmatter (missing = 0), `send --re` sets
  `hops = parent.hops + 1` always (human or auto; only the `--auto` guard consumes it), cap 3;
  (3) per-sender rate limit — mailbox-derived count (digest-style walk), window 3600 s, cap 5,
  ZERO new state; (4) self-guard — `parent.from == self` never auto-replied.
- **Rejected (spec § Rejected):** always-on responder · Redis/state-file counters · advisory-only prose ·
  blanket deep-hop refusal without `--auto`.
- **Out of scope:** Layer-2 live auto-wake (flag-gated OFF upstream; adopt-not-build) and the mail
  DISPATCHER (its own `/fabrik-spec` next — operator-sanctioned separately).
- **OPEN items settled here (spec § Open, infra's call):**
  - **Cap tuning:** ship the spec defaults as module constants overridable via env —
    `FABRIK_MAIL_HOP_CAP` (3) · `FABRIK_MAIL_RATE_CAP` (5) · `FABRIK_MAIL_RATE_WINDOW_S` (3600) —
    the `_env_int`-style guard (positive int else default). A wrong default is a one-line env fix.
  - **Hook annotation of `should-reply`:** **DECLINED this build.** The surfacing hook's value is its
    trivial fail-openness; the `should-reply` verb is the SSOT and agents can call it pre-draft.
    Recorded as a residual option, not owed work.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/10-python.md` (ACTIVE) | typing, env handling for the new constants | pack; `scripts/mail.py` is stdlib-only and stays so |
| `core/45-testing-strategy.md` (ACTIVE) | watched-fail-first on the risky guards (hop boundary, rate edge, self, fail-soft) | pack § regression rules |
| `core/55-observability.md` (ACTIVE) | diagnostics to stderr, never a logfile | `scripts/mail.py:22` already prints to std streams |
| fabrik-lib | **BUILD in `mail.py`** — protocol-specific, no reuse surface, no 🆕 candidate | spec § fabrik-lib verdict (inherited) |
| `agents-fabrik.md` § mandates | 12-Factor VI statelessness — rate state is the mailbox itself | spec § constraints digest |
| Sync-consciousness | `scripts/mail.py` IS a governance-sync trigger (`.pre-commit-config.yaml` files-filter `mail`) — the commit distributes fleet-wide (~46 repos); change must be additive + backward-compatible | spec § Sync-consciousness |
| `specs/services/*` shape | N/A — no service, no shape flag, no infra | spec § Shape |
| Frozen contracts | N/A — no DB fields, no GUI | spec § Shape |

**Grounded API (re-read THIS run, current master):** `ACK_BY_KIND` `scripts/mail.py:44` ·
`MailRefusedError` `:101` · `_frontmatter` `:209` · `send()` `:226` (raises `MailRefusedError`,
"nothing written") · `claim` `:274` / `ack` `:301` (atomic renames) · `_parse` `:402` (arbitrary keys,
requires `id`+`kind` → `hops` additive-safe) · `digest` `:438` (the mailbox-walk pattern to reuse) ·
`read_msg` `:495` (inbox+archive lookup; raises **FileNotFoundError** `:502` on a missing id — the
fail-soft ALLOW catches exactly that, never `MailRefusedError`) · `_age_seconds` `:424` (EXISTING
fail-soft ts arithmetic — unparseable ts → `inf`; the rate window reuses it, no new date parsing) ·
`_mail_root` `:107` (`FABRIK_MAIL_ROOT` env — the existing test-isolation seam `tests/test_mail.py:38-44`
uses; all new tests isolate the same way) · send subparser `:547` · CLI `MailRefusedError`→exit 2 /
`FileNotFoundError`→exit 1 handler `:598` (the `should-reply` HOLD exit 3 collides with neither). `tests/test_mail.py` exists (extend, don't fork).

## Phase A — the guards in `mail.py` (red-first)

1. **Tests first** (extend `tests/test_mail.py`; each RED before its code lands — run and quote the
   failure): the guard truth table (self / terminal-kind / hop-cap / rate-cap / ALLOW) ·
   `--re` hops-increment property (parent 0 → child 1; missing `hops` parses 0) · hop boundary
   `parent.hops >= cap` (the `==` case REFUSES) · rate-window edge (message at `now - window` exactly
   is OUT of the window; `now - window + 1` is IN) · `--auto` without `--re` → usage `MailRefusedError` ·
   `--auto` with dangling `--re` → fail-soft ALLOW, `hops=0`, stderr note · un-flagged human send with
   deep hops passes untouched · unreadable-mailbox rate count → ALLOW + stderr · env overrides honored ·
   `should-reply <id>` prints `ALLOW`/`HOLD: <reason>` with exit 0/3.
2. **Code** (`scripts/mail.py`, one commit with the tests):
   - constants + env guards near `ACK_BY_KIND` (`:44`); `hops` param in `_frontmatter` (`:209`, default 0,
     emitted only as a plain int — legacy readers ignore unknown keys per `_parse:402`);
   - `send()` (`:226`): resolve the parent once via the `read_msg` lookup when `re` is set (tolerate
     failure → parent None); `hops = parent.hops + 1` when resolved else 0; the `auto` branch — require
     `re`, run `should_auto_reply`, `raise MailRefusedError(reason)` BEFORE minting; parent resolution
     catches `FileNotFoundError` (+`OSError`) → parent None → fail-soft ALLOW with the stderr note;
   - `should_auto_reply(parent_fm, self_repo, *, now, root) -> tuple[bool, str]` + `_recent_from_count`
     (the `digest:438` walk pattern but **READ-ONLY** — `digest` QUARANTINES malformed files as a side
     effect (`_quarantine:432`); the rate count must SKIP malformed, never move them — plus
     `FileNotFoundError`-tolerant, window ages via the existing `_age_seconds:424`);
   - CLI: `--auto` on the send subparser (`:547`); `should-reply <id> [--repo]` subcommand (exit 0 ALLOW /
     3 HOLD — distinct from the `:598` refusal exit 2).
3. **Gate:** `pytest tests/test_mail.py -q` green · `ruff` + `ruff format` · `mypy scripts/mail.py` ·
   `python scripts/final_gate.py --lean --json` success. **`/fabrik-review` at the phase boundary**
   (changed surface: `scripts/mail.py` + `tests/test_mail.py`) — loop to found:0.

## Phase B — docs + the fleet-distribution commit

1. `docs/reference/fabrik-mail.md`: "Loop-safety / auto-reply" section — `hops` row in the frontmatter
   table, the four guards, the **always-pass-`--auto`-on-unattended-replies discipline** (the guard is
   only as strong as this rule + the enforced refusal), the `should-reply` verb, the defaults + env
   overrides. (Manifest-synced reference doc — rides the same commit's sync since mail.py triggers it.)
2. `docs/workstation/fabrik-mail.md`: operator note — what a HOLD looks like; the overrides (a human
   `--re` without `--auto`; env-bump for a genuine long thread).
3. `CHANGELOG.md` `### Added` entry; `docs/README.md`/INDEX rows only if a NEW doc file is created
   (both docs exist — verify, else Doc Sync Matrix applies). **The three env vars land in
   `.env.example` + `docs/CONFIGURATION.md`** (the gate-enforced New-env-var row — E3).
   **The mixed-fleet rollout note (E4)** goes in the fabrik-mail.md section: until every repo
   syncs the new mail.py, a not-yet-synced peer emits hops-less replies read as 0 — the hop
   cap is weak across mixed versions and the RATE cap is the backstop; also document that
   `--auto` resolves the parent in `--from`'s OWN mailbox (a wrong --from degrades to the
   fail-soft ALLOW — wrappers must pass the correct identity).
4. **Commit** (explicit pathspecs + trailers): sync-conscious — this IS the fleet-distribution event;
   verify post-commit that a sample project's `scripts/mail.py` carries the guard (the transdoc check,
   as done for check_schema_sync). **Gate:** full `python scripts/final_gate.py --json` success ·
   distribution verified · push per § EXIT.

## Phase C — close-out

1. Reply to fleet (`--re 01M02SV4498PHFBG3SM8KN1TR9` thread): built, commit sha, the two OPEN items'
   dispositions (caps → env-overridable defaults; hook annotation → declined, residual option).
2. `docs/LESSONS_LEARNT.md`: only if execution surfaces one (else `none`).
3. Handoff line: **NEXT → `/fabrik-spec` for the mail dispatcher** (Layer-1.5 auto-processing:
   cron/stamp-checked headless runs, beat-routed infra/fleet/intel — operator sanctioned "go" 2026-08-22;
   these guards are its prerequisite, now met).

## Subagents & parallelism

Small single-file delta: **no pool fan-out for the build itself** (one coder surface, no gradeable
partition — a NO-POOL declaration rides the commit). The phase-boundary `/fabrik-review` runs its
normal finder pattern (pool breadth + native authority) per that command's own contract.

## Self-audit

- Every step grounded in a re-read `path:line` (see Context Ledger — grounded THIS run, not the spec's
  snapshot; all its refs re-verified current).
- No 12-Factor violation stepped (no logfile, no state store, no daemon; stderr only).
- The one fleet-distribution event is named with its verification step (Phase B.4).
- No `[OPEN → resolve at execution]` residuals: both spec OPEN items are settled above; no execution-
  blocking question remains.
- Behavior Contract: every user-observable behavior in the delta has a named test in Phase A.1,
  risk-ordered, red-first on the four risky edges.

## Residuals (documented, not owed)

- Hook annotation of `should-reply` verdicts — declined this build; revisit only if agents demonstrably
  skip the pre-check.
- Layer 2 adopt-not-build when Anthropic's flag lands; the dispatcher spec is the named next command.
