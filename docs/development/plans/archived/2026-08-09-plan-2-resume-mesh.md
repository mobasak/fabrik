# Plan 2 — StopFailure Resume Mesh (2026-08-09)

Status: EXECUTED 2026-08-09 (workstation build; repo artifacts d1199b7f + this commit)
Whole-plan review: docs/development/reviews/2026-08-09-plan-2-resume-mesh-review.md

## Pass Ledger (plan-review convergence)

| Pass | axes | edits | md5 (start → end) |
|-----:|---|---:|---|
| 1 | citations (seams opened this run) · executability (sandbox-HOME pattern pinned — bare tmp HOME hits the decider-MISSING leg; final-failure ring seam pinned to a NO_REVIVE re-fire through the existing pipeline) · wording | 3 | → c58f8482… |
| 2 | full re-read · doc-step explicitness (CHANGELOG named in C5) | 1 | c58f8482… → 8791aaab… |
| 3 | all axes, fresh — **0 edits** | 0 | 8791aaab… ✓ → CONVERGED |
Spec: docs/superpowers/specs/2026-08-09-stopfailure-resume-mesh-design.md (CONVERGED ×2 re-opens,
operator-approved; its Grounded-facts table + Behavior Contract are INHERITED, not re-derived).

## Goal

Build the three-layer mesh: heal-at-death (rotation trigger + `errparked` marker), opt-in revival
(headless `claude -p --resume` + pane self-watch, both connectivity-gated with the revival-storm
guard), ring-and-Telegram only when truly dead. Workstation scope: `~/.claude/bin` + workstation
docs — no fleet-synced surface (spec § Scope; DR-backup already covers `~/.claude/bin/**`).

## Context Ledger

- **Spec inheritance:** all external/binary facts live-verified at spec-review (binary 2.1.219 enum,
  hook-cannot-continue, `claude -p --resume` revival ZEBRA-42, Monitor zero-cost wake, probe
  404@0.11s, CronCreate rejection). Not re-verified here — that is the split working as designed.
- **Implementation seams (opened this run):**
  - `~/.claude/bin/claude-sound.sh:73-103` — the `failure)` branch: err extraction, three case
    families, then `log_line "delegated err=$err"` + setsid-nohup decider spawn. Layer-1 dispatch,
    `errparked` write, and the 2a spawn gate insert AT this delegation point.
  - Lock-dir + sanitize pattern to mirror EXACTLY: `/tmp/claude-sound-locks-$(id -u)` and
    `tr -c 'A-Za-z0-9_-' '_' | head -c 64` (`claude-sound.sh:112` area, compacting-marker precedent;
    decider `_safe()` is the source of the mirror rule).
  - `~/.claude/bin/claude-stop-decider.py:353` `decide(transcript, sid, turn_dead)`; `:505-506`
    env-driven turn_dead; `--self-test` (34 fixtures, green now). The `errparked` CLEAR lands in the
    Stop-path (turn_dead=False) after a verdict; fixtures extended there.
  - Rotation: `python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --next` (usage doc :669;
    detached spawn, same setsid-nohup shape as the decider spawn).
  - Telegram: vendor the `APPRISE_SEND` call pattern from
    `/opt/fabrik/scripts/sysadmin/proactive-check.sh` (spec-named source).
- **ACTIVE packs:** `core/45-testing-strategy.md` (watched-fail-first), `core/90-bootstrap-scripts.md`
  (shell idempotency/quoting — nearest discipline for `~/.claude/bin` shell). Others touch no surface.
- **Out-of-tree note:** `~/.claude/bin/**` writes are the sanctioned workstation exception
  (spec § Scope; sibling precedent: the shipped decider). Repo-side artifacts: this plan, receipt,
  two workstation-doc rows.
- **shape/spec/fabrik-lib:** n/a (workstation tooling; spec audited fabrik-lib: no covering module).

## File Scope (owned paths)

- `~/.claude/bin/claude-sound.sh` (failure-branch extension)
- `~/.claude/bin/claude-stop-decider.py` (errparked clear + fixtures)
- `~/.claude/bin/claude-autoresume.sh` (new)
- `~/.claude/bin/claude-selfwatch.sh` (new)
- `~/.claude/bin/claude-mesh-test.sh` (new — the mesh's fixture harness, PATH-shimmed)
- `docs/workstation/claude-configuration-inventory.md` + `docs/workstation/hooks-index.md` (row updates)

Disjoint from active plans. Workstation files are single-writer by convention (sound-system owner);
the WIP net does not cover `~/.claude` — commit-and-push (repo docs) + DR-backup (bin) are the safety.

## Phase A — Layer 1: heal-at-death + marker plumbing (fixtures red-first)

1. Red-first via `claude-mesh-test.sh` (new harness). **Sandbox pattern (pinned):** copy
   `claude-sound.sh` + `claude-stop-decider.py` into a tmp `HOME/.claude/bin` and run with that
   `HOME` + a PATH shim dir (`claude_rotate.py` shim, later `claude`/`curl`/notify shims) — a bare
   tmp HOME without the decider would flip the script into its decider-MISSING leg (plays instead of
   delegating), testing the wrong flow; lock dir is uid-scoped so the sandbox overrides it via the
   script's env (add `CLAUDE_SOUND_LOCKDIR` override, default unchanged — 1 line, keeps real
   `/tmp/claude-sound-locks-*` out of tests). Fire each of the 10 enum classes through
   `claude-sound.sh failure` →
   assert (a) `errparked` written on EVERY class (content: `<err> <epoch>`), (b) rotation shim
   invoked for `rate_limit|authentication_failed` ONLY, (c) rotation rate-limited (2nd death <10min
   → no second rotation; marker `rotation.last` box-wide), (d) decider still delegated (log line).
   Watch the relevant assertions fail against the CURRENT script first.
2. Implement in the `failure)` branch at the delegation seam: write marker → class-gated detached
   rotation spawn behind the 10-min limiter → (Phase B consumes) `CLAUDE_SOUND_AUTORESUME` gate.
3. Decider: clear `<safe>.errparked` on any Stop-path run (turn_dead=False) for the session;
   `--self-test` fixture for clear-on-stop + keep-on-turn-dead. 34 → 36+ fixtures, all green.
4. **Gate:** `claude-mesh-test.sh` green · `claude-stop-decider.py --self-test` green ·
   `bash -n` both shell files.

## Phase B — Layer 2: the two revivers (shimmed E2E red-first)

1. `claude-autoresume.sh <sid> <err>` (new): per-class backoff → connectivity gate (probe loop 30s,
   30-min ceiling from marker epoch) → 0–45s jitter → K=2 mkdir slot locks (5-min stale) →
   `claude -p --resume "$sid" "continue"` → attempt counter, cap 2 → **final-failure seam
   (pinned):** re-invoke `claude-sound.sh failure` with the ORIGINAL payload +
   `CLAUDE_SOUND_NO_REVIVE=1` (the spawn gate refuses a re-spawn; the reviver's consumed state means
   the decider's waker-consumed logic RINGS via the existing pipeline — no new ring code). Human-only
   classes exit immediately (defense-in-depth; the spawn gate already excludes them).
2. `claude-selfwatch.sh <sid>` (new): poll `<safe>.errparked` (10s); on appear: per-class remedy
   wait → probe gate for `server_error|unknown` (same ceiling; past ceiling exit silent) → jitter →
   print the single RESUME line → exit.
3. Spawn gate in `claude-sound.sh`: `[ "$CLAUDE_SOUND_AUTORESUME" = 1 ]` + revivable class →
   setsid-nohup `claude-autoresume.sh`.
4. Mesh-test additions (shimmed `claude` + shimmed `curl`): probe-DOWN consumes no attempt and
   ceilings to ring; probe flips UP mid-wait → exactly one attempt; 5 parallel revivers → ≤2
   concurrent slots and no two attempt starts share a second; cap 2 then ring path; selfwatch prints exactly one
   line and exits; human-only class exits without resume. Red-first where the behavior is new.
5. **Gate:** full `claude-mesh-test.sh` green (Phases A+B fixtures).

## Phase C — Layer 3 + docs + live regression

1. Ring-path Telegram: in the ring leg (sound actually played for a StopFailure park) with cwd
   under `/opt/`, fire the vendored APPRISE_SEND pattern (rate-limit marker: one per session per
   30 min). Mesh-test: ring+/opt/ → notify shim called once; second ring <30min → suppressed;
   non-/opt cwd → never.
2. Docs: config-inventory row (the two new bin scripts + `errparked`/rotation markers),
   hooks-index sound-row extension (mesh summary — the freshness checker keys on hook FILES, which
   are unchanged; verify `check_hooks_index` green), run-discipline sentence: long autonomous runs
   arm `Monitor(persistent:true, claude-selfwatch.sh <sid>)`.
3. Regression: decider `--self-test` (all fixtures) + the sibling's E2E battery classes re-fired
   through the harness (busy-silent / parked-ring / dup-park / compact marker) — the mesh must not
   change any non-failure verdict.
4. **Live arm (residual confirmation, non-blocking):** arm the self-watch on THIS session as the
   first real long-run consumer; the next genuine StopFailure confirms the extrapolated Monitor-wake
   residual (spec § Residual risks — failure mode is today's ring, no regression).
5. **Gate:** CHANGELOG entry · `final_gate.py --check --json` no NEW failures · whole-diff `/fabrik-review`
   (native, NO-POOL: hooks/workstation shell) · receipt · archive + EXECUTED flip · commit+push
   repo artifacts + DR-backup run (`dr_claude_backup.sh` — bin changed).

## Behavior Contract

- **Given** any of the 10 error classes fired through `claude-sound.sh failure`, **When** the branch runs, **Then** `<safe>.errparked` exists with class+epoch and the decider is still delegated. [A]
- **Given** `rate_limit` then `authentication_failed` within 10 min, **When** both fire, **Then** the rotation shim runs exactly once (box-wide limiter). [A]
- **Given** a Stop-path decider run for a session with a stale `errparked`, **When** it completes, **Then** the marker is cleared; a turn_dead run keeps it. [A]
- **Given** probe DOWN, **When** the reviver waits, **Then** zero attempts are consumed and past the 30-min ceiling the ring path fires. [B]
- **Given** probe flips UP mid-wait, **When** the reviver proceeds, **Then** exactly one attempt is counted and `claude -p --resume <sid> "continue"` is invoked. [B]
- **Given** 5 simultaneous revivers, **When** they pass the gate, **Then** at most 2 hold slots concurrently and attempt starts are jitter-spread. [B]
- **Given** an armed selfwatch and a hand-written `errparked`, **When** the remedy+gate pass, **Then** exactly one RESUME line prints and the process exits. [B]
- **Given** a ringing StopFailure park with cwd under `/opt/`, **When** the ring plays, **Then** the notify shim fires once and is suppressed <30 min. [C]
- **Mocked:** `claude_rotate.py`, `claude`, `curl`, and the notifier via PATH shims; markers/locks real; the decider runs real. Watched-fail-first for every new behavior.

## Subagents & parallelism

A → B → C sequential (each layer consumes the previous seam). Reviews native-only (NO-POOL:
hooks + workstation shell), declared at commit.

## Evidence

**Execution evidence:** Phase A: 13 red → 15 green · Phase B: 25 green (+ mid-build real-sound
incident fixed: sandbox now dead-paths media/Pulse) · Phase C: 28 green · review round: 11 findings
→ 35/35 twice + decider self-test green · deviations: decider clear/keep fixtures live in the
harness (they exercise main()'s side effect, unreachable from the embedded fixture suite); held-slot
storm guard replaced by serialized starts (spec-amended, review-adjudicated). Self-watch armed live
on the build session. Gate: 44/0.

## Self-audit

- (a) Spec build-inventory rows map: sound.sh dispatch → A2 · decider clear → A3 · autoresume → B1 ·
  selfwatch → B2 · rotation limiter → A2 · Telegram → C1 · docs → C2. Nothing orphaned.
- (b) Cross-phase interfaces: the marker format (`<err> <epoch>`, `_safe()` mirror) is defined once
  in A and consumed by B/C; the ring-path hook is defined in B5's failure leg and implemented in C1.

## Residual unknowns

- Monitor-wake into an error-dead pane: extrapolated; confirmed by C4's live arm at the next real
  death (failure mode = today's ring; spec-accepted).
- `claude -p --resume` behavior if the CLI version updates mid-flight: revalidate on version bumps
  (workstation, low risk).
