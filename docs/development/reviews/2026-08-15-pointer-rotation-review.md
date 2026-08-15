# Pointer-rotation delta — review ledger

Operator redesign 2026-08-15 (supersedes the login-once plan's per-project M3 model):
4 per-account fleet dirs + ONE `active` symlink all sessions follow + tick flips by quota
headroom. Load-bearing invariant: a flip moves ZERO credential bytes.

## Round 1 (2026-08-15)

Surface: worktree commit 5b8fa112 (+327 twin ×2, +404 tests; 197/197 re-run by orchestrator,
twins md5 40a15fd8). Finders: pool deepseek+gemini (diff inline) + native opus (worktree
probes: flip atomicity from foreign cwd, selection matrix, dwell/pause loops, invariant
evasion, 2 mutants — both killed, tree restored).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | NO credential-liveness gate on the flip path — presence-only check; a refresh-expired chain with a stale low cached reading is flipped to (probe: rc True, selector picked it) → ONE dead pointer = fleet-wide auth outage; the 2026-08-10 incident class reopened. `_stale_snapshot_reason` exists and the legacy path uses it; fleet path doesn't | opus CONFIRMED HIGH (probe) | **FIX (F-P1)**: liveness gate in _flip_active + selector exclusion + expiry surfaced in --status |
| 2 | Stale cached quota can qualify a candidate whose real state (dead/walled) diverged since the cache | gemini + opus (same probe family) | **FIX (F-P2)**: validate-before-flip — live probe for cached-reading candidates |
| 3 | Both invariant tests evadable: os.link + subprocess-shelled cp create credential copies UNCAUGHT (probes: "EVASION CONFIRMED" ×2) | opus CONFIRMED MEDIUM | **FIX (F-P3)**: trap os.link + subprocess; structural test walks nested code objects |
| 4 | Mid-refresh race: the CLI's read→HTTP→write renewal goes THROUGH the pointer; a flip inside that ~1-2s window writes A's rolled chain into B's dir (B loses its chain locally, one relogin) | deepseek raised / gemini mis-refuted / orchestrator sized | **FIX (F-P4)**: detection net — probe-email vs pinned-identity mismatch warning (no prevention possible from this side; documented residual) |
| 5 | TOCTOU between the liveness check and the symlink replace | opus NIT | **FIX (F-P5)**: docstring note (single-operator threat model) |

Refuted: relative-symlink-resolves-from-CWD (POSIX resolves against the link's own dir —
native probe from a foreign cwd confirmed; gemini's claim was the classic misconception) ·
tie-break "hot-spotting" (deterministic by design, 4 accounts) · reader-with-open-fd during
flip (flip never touches bytes) · dangling-pointer + pause repair loop spam (stderr-only,
ledger writes only on completed flips — probe-confirmed) · manual flip resetting the auto
dwell (intentional, legacy pattern).

Verified clean: atomic dir-symlink replace (pinned), keepalive/pointer double-count fix,
reserved `active` slug, empty-root legacy view byte-unchanged, dwell fail-closed with
advisories still live, both mutants killed by named tests.

Round 1 verdict: NOT CLEAN — F-P1..F-P5 dispatched. Round 2 follows.

## Round 2 (2026-08-15)

Surface: fixup commits 636ee6ed (F-P1..F-P5) + 3e587e92 (F-P6 — the mismatch net made LIVE
after the orchestrator probed the real usage payload and proved it carries no account.email;
hourly stamp-budgeted profile probe, sticky stored verdict). Re-verified first-hand: 207/207,
twins md5 8e046be7. Finders: pool deepseek+gemini (F-P1..F-P6 diff inline) + native opus
(worktree probes + 2 mutants, both killed, tree restored).

Verified fixed: F-P1 (expired-chain flip refused auto+manual, selectors skip via the
_account_flip_dir choke point, ALLOW_STALE escape hatch probed both ways), F-P2
(_validated_pick provably bounded — pool's infinite-loop claim REFUTED on code: return-None
is the loop's first statement, exclude set monotone), F-P3 (evasion probes 3/3 CAUGHT),
F-P5. Missing-expiry fail-closed semantics correctly delegated (capture-suite covered).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 6 | Sticky mismatch verdict gated behind the probe's 8h freshness window — a corrupted dir that idles past 8h has its warning VANISH while the stamp still holds the mismatch (probe: warn → +9h → silent); the idle case is the LIKELY aftermath | opus CONFIRMED HIGH (probe) | **FIX (F-P7)**: reporting unconditional; freshness gates new probes only |
| 7 | Liveness gate ordered before the idempotent no-op check — `--switch <active-slug>` on a since-decayed chain returns failure, breaking the documented no-op contract | opus CONFIRMED moderate (probe) | **FIX (F-P8)**: no-op check first, decay surfaced as a warning |
| 8 | Identity stamp keyed by EMAIL — a fresh pin on a new dir masks a sibling dir's unresolved mismatch; two emails can sanitize identically (pool's collision finding, same root) | opus PLAUSIBLE + both pool | **FIX (F-P9)**: per-SLUG stamps (kebab-validated, collision-free by construction) |
| 9 | _chain_stale_reason double-reads the credentials file | opus NIT | fold into F-P9 commit |

Refuted round 2: _validated_pick infinite loop (deepseek — provably false on the quoted
code) · stamp path traversal (regex collapses non-alnum) · structural one-level walk
(documented limitation; behavioral trap is the net) · gemini's sticky-silences-new-mismatch
(self-refuted: last != email fires on any new pairing).

Round 2 verdict: NOT CLEAN — F-P7..F-P9 dispatched. Round 3 follows.
