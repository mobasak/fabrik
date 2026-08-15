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
