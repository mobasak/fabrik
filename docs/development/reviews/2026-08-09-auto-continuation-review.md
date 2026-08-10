# Review — auto-continuation (resume-mesh) full implementation · 2026-08-09

Scope: the complete auto-continuation stack the operator asked to verify as "100% functional and
correctly designed": `~/.claude/bin/{claude-sound.sh, claude-stop-decider.py, claude-autoresume.sh,
claude-selfwatch.sh, claude-mesh-test.sh}` + fleet-synced `.claude/hooks/session_orient.py` (arm
order, commit 50675991) + `tests/test_session_orient_hook.py` + `~/.claude/settings.json` StopFailure
wiring + `docs/workstation/{hooks-index.md, claude-configuration-inventory.md}`. Anchored on the
prior reviews `2026-08-09-plan-2-resume-mesh-review.md` and `2026-08-09-session-work-review.md`
(surface CHANGED since: waker-loss bridge, rotation opt-in-OFF, mesh-notify .env fix, ORIENT arm
order, first live production firing this evening).

Surface: 506759916f637371104841bdec0f291de0fa71f0 + working-tree d41d8cd98f00b204e9800998ecf8427e (pre-fix anchor)
Out-of-repo pre-fix md5: sound=3cfdd39f12b34568f80e30f9dca3f6f6 ·
decider=349db1b80ca8d18baf77caa27f3b7e0c · autoresume=c82d4a42175459fbecfa664c3efdd69e ·
selfwatch=498fa949d0b9e0623629b4e84199ca30 · harness=51539039542c8f4a2ab9203cf9ead233
(post-fix hashes recorded at the end of the run.)

## Rubric

`review_rubric.py --changed .claude/hooks/session_orient.py tests/test_session_orient_hook.py
docs/workstation/hooks-index.md scripts/wip_backup.sh` — run verbatim at review start (floor:
core/35-security-auth · core/25-data-postgres · core/30-ops · all twelve 12-Factor axes). The
surface is workstation shell/python hooks: applicable floor rows are III config-as-env, XI bounded
logs, fail-open-vs-fail-closed, injection safety; server-only rows (compose/Traefik/Alembic/RLS/
sticky-sessions/SQLite-backing) map to no code in this surface → checklist row 13 N/A.

## Finder manifest (Round 1)

- Pool (fanout "review", read_only, content inlined; auto-recorded + scored via set_quality):
  deepseek/deepseek-v3.2-exp (sound.sh) · google/gemini-3-flash-preview (selfwatch+autoresume) ·
  qwen/qwen3-max (decider) · deepseek/deepseek-v4-flash (orient+tests). $0.042 total.
- Native fabrik-reviewer ×3 (session model, exceeds the Opus floor): N1 lifecycle/races/fail-open/
  sentinels · N2 error-matrix/quota/accounting/12F · N3 test-quality/behavior-without-a-test/doc-truth.
- Adjudicator (this session): refute/merge/decide + the live-log trace (sound-debug.log timeline of
  tonight's real firing) — source of the two heaviest findings no finder raised.

## Round-1 confirmed findings → ALL FIXED (fix commit + regression fixture per row)

| # | Finding (finder) | Fix | Regression guard |
|---|---|---|---|
| F1 | Persistent Monitor counted as a pending waker → park chime suppressed up to 60min per arm (live log 18:21:31, 21:16:15) AND its "expiry" mimics waker-loss → false `waker_lost` ring + 💀 Telegram + spurious wake ~62min after every armed park (adjudicator, from live log) | `_scan_tasks` excludes `persistent:true` Monitors — standing watches, never wakers | self-test 12b `persistent Monitor parks` |
| F2 | Recheck sleeper wrote `waker_lost` without proof-of-loss — any busy→parked flip (incl. expired-by-design watches) forged a death record (adjudicator + N2.6 class leak) | `waker_provably_lost()`: waker identity travels via `CLAUDE_RECHECK_WAKER`; record written only for dispatched-never-completed | self-test 12c ×4 · harness D (sWL still green = true loss still detected) |
| F3 | Self-watch never consumes its marker → spurious RESUME on every re-arm; ORIENT arms at turn START while clears happen at turn END, maximizing the window (adjudicator C1 = pool-U1.1 = N1.1/N1.9 = N3.6) | consume-at-arm (pre-arm marker is history; the arming session is alive by construction) + consume-at-fire (one wake per record) | harness W1 (consume-on-fire) + W2 (stale-at-arm silent) |
| F4 | `errparked` written on EVERY StopFailure incl. non-terminal ones (a live waker exists) → armed watch fires into the self-revived session (N1.2) | decider clears the record on a busy turn-death verdict; recheck re-parks with its own record if the waker is later lost | harness D2 |
| F5 | Reviver's `claude -p` child lacked `NO_REVIVE` → the resumed turn's own death spawns a second writer, racing `.attempts` (N1.3) | child env `CLAUDE_SOUND_NO_REVIVE=1` | harness B8b |
| F6 | F8 marker-abort checked once, never re-checked after backoff/gate/spacing sleeps → reviver barges into an already-alive session (N1.4 = N2.1) | `survived()` re-checked before EVERY attempt + last-look before the counter write | harness B10 |
| F7 | Headless `claude -p` sessions also receive the ORIENT arm order — no pane to wake, duplicate watchers (pool-U3.2, N3-adjacent) | reviver child exports `CLAUDE_MESH_HEADLESS=1`; orient skips the arm order when set | orient test `test_headless_run_gets_no_arm_order` + harness B8b |
| F8 | `source=compact` re-prints the arm order though the armed Monitor SURVIVES compaction (proven live tonight) → duplicate watchers (N3.7, N1.9) | orient skips arm on `source=compact`; resume (new process) still arms | orient test `test_compact_source_gets_no_arm_order` |
| F9 | sid interpolated raw into the Monitor command instruction (pool-U3.3 = N3.10) | allowlist `[A-Za-z0-9_-]` (+64 cap) in orient — same class every mesh script sanitizes to | orient test `test_arm_order_sanitizes_a_garbage_sid` |
| F10 | Non-dict JSON payload (`[]`) escaped to the outer swallow → whole ORIENT block silently lost (pool-U3.5/U3.13) | `isinstance(data, dict)` guard | orient tests `test_non_dict_payload_still_orients` + strengthened garbage-stdin assert |
| F11 | Selfwatch network-gated only server_error/unknown while autoresume gates every attempt — a rate_limit/overloaded wake fires into a dead network (N2.4; N3.8 same for waker_lost) | selfwatch gates ALL classes (instant probe when up) | harness W3 |
| F12 | waker-loss Telegram reported the ORIGINAL death's class (stale `CLAUDE_SOUND_PARK_ERR` env) — live-witnessed in the red run: "died on rate_limit" for a lost waker (N2.6) | recheck env pops PARK_*; notify arg forced to `waker_lost`; error-family wav set on the proven-loss ring | harness D4 |
| F13 | Two distinct deaths at the same transcript byte size: dup-park guard swallowed the second ring (N3.5) | turn_dead rung value scoped `size:death-epoch` | harness D5 |
| F14 | `.recheck` dedup marker written BEFORE Popen — a failed spawn silently disabled the bridge for the whole window (N1.8) | marker written after successful spawn | code order + breadcrumb stderr kept |
| F15 | Capped reviver still slept the full backoff before ringing (N2.2 tail) | cap short-circuit before the backoff sleep | harness B11 (with AR backoff-passthrough fix) |
| F16 | `model_not_found` rang the transient-system voice though every gate treats it human-only (N2.5) | moved to the human-action wav family | family case arm + comment |
| F17 | mesh-notify entirely fail-silent — no log on no-keys/curl-fail/suppress (N2.8 = N3.3 = pool-U0.17) | log_line on every outcome: sent/sent(cmd)/FAILED(cmd)/FAILED(curl)/NO-KEYS/suppressed | code (observability; sandboxed C-section covers the shim path) |
| F18 | Empty/sentinel sid collided every anonymous payload on one marker set (N1.6/N1.7, pool-U0.7) | sid guard: mesh actions skipped for `""`/`"-"` sid, logged `mesh-skipped(no sid)` | code guard |
| F19 | Spawn gate (`AUTORESUME=1` path through sound.sh) had zero test coverage (N3.1) | — (behavior existed; coverage added) | harness B8 + B9 |
| F20 | `blocking_hooks_alive` dark to every test layer (N3.4) + exact-string cwd match misses symlinked forms (N1.13) | realpath both sides; detection fixture | self-test 18 ×2 |
| F21 | Vacuous/weak test asserts: bounded-memory test proved nothing about the bound; digit-substring count asserts; arm-order test didn't pin `persistent: true` (N3.9/N3.11/N3.21, pool-U3.16-18) | exact `(N entries)` asserts, `(16384+ entries)` bound proof, Monitor-shape pin | strengthened tests (4 were RED against the pre-fix hook) |
| F22 | Doc drift: hooks-index "long autonomous runs arm" vs ORIENT-orders-every-session; config-inventory "per long run"+"28 fixtures"+retired K-slot design; harness header missing Section D; decider docstring "four states" vs 7 verdicts; sound.sh `.env.sysadmin` comment (N3.13-17, adjudicator C3) | all five surfaces rewritten to shipped behavior | `check_hooks_index.py` remains green |
| F23 | `rm -f {marker}` unquoted in the sleeper script — latent quoting anti-pattern (pool-U2.2) | quoted | code |
| F24 | `powershell.exe` fallback unbounded (N2.15 tail) | `timeout 15` | code |

## Round-1 REFUTED (proof per row — the mirror obligation)

- Ring-plainly on decider-missing; attention rings on malformed payload — documented deliberate
  fail-open directions (sound.sh comments; "ring rather than lose the signal").
- `model_not_found` unhandled (pool-U0.4) — factually wrong: catch-all handled it; family now fixed (F16).
- Marker write race two-failures-one-session (pool-U0.6) — one turn one death; last-writer-wins identical semantics.
- Corrupt `rotation.last`/`.notified` fail-open (pool-U0.8/15) — bounded: worst case one extra action in the alert-beats-silence direction; rotation default-OFF.
- `MESH_ROTATE_CMD` word-splitting (pool-U0.9) — intentional (command-with-args env); operator-owned box.
- `.reviving` stale deadlock (pool-U0.10/11, U1.9) — decider bounds it: fresh <2100s else fall-through-and-ring (decider `busy-reviving` branch); success clears via the revived session's next normal Stop.
- Env-var injection into decider/ffplay/powershell paths (pool-U0.12, U2.9) — single-operator threat model (recorded memory): same-user env is same-user code execution already.
- `/opt/*` Telegram gate too narrow (pool-U0.13) — fleet projects live in `/opt` by contract.
- Telegram body/JSON injection (pool-U0.16/20) — factually wrong: `--data-urlencode` values, no eval, no hand-built JSON.
- Token quoting → curl fail (pool-U0.18/19) — self-healing direction (no stamp → retry next window).
- Compact-marker race (pool-U0.21/22) — bounded by COMPACT_STALE_S; PostCompact wiring live-verified tonight (21:13:41).
- mkdir mutex both-win race (pool-U1.2) — impossible: mkdir is atomic; the 60s steal only fires on a >60s holder, which defaults (spacing 15s) prevent. Spacing>60s misconfiguration noted in N1.10 — accepted (degrades to two close starts, not corruption).
- `.attempts` never cleared on distant success (pool-U1.4) — wrong: the revived session's next normal Stop clears it (decider clear set); consecutive-death accumulation IS the cap's design.
- locks-dir-missing infinite loop (pool-U1.5) — bounded by the `.reviving` 35-min fall-through ring; `/tmp` full breaks the box anyway.
- `invalid_request` spin-loop (pool-U1.6) — cap 2 bounds it; immediate resume is the designed matrix (context-overflow resumes trigger compaction).
- Captive-portal false-up (pool-U1.7 = N1.11) — documented deliberate any-HTTP-is-up choice; failure is bounded (attempts→ring).
- Corrupt marker timestamp extends ceiling (pool-U1.8) — self-written format; benign direction.
- Payload re-serialization mutation (pool-U2.1) — JSON object round-trip is semantically stable.
- transcript_path arbitrary read / unbounded stdin (pool-U2.3/10, U3.14) — trusted harness payloads; threat model.
- rungsize size-collision via hand-edited transcript (pool-U2.5) — append-only in practice; turn_dead scoping (F13) covers the real variant.
- Forged `<task-notification>` completions (pool-U2.6) — harness-controlled channel (type=user STRING); assistant/tool_result echoes already excluded; single operator.
- `/opt_mine` prefix bypass (pool-U2.13) — self-refuted by finder: `startswith("/opt/")` includes the slash.
- ORIENT claims mesh/session-recall on boxes without them (pool-U3.1/10) — the hook ships only via the sync that also ships the mesh wiring; VPS clones run no interactive sessions in /opt trees; cosmetic at worst.
- `read(N)` chars-not-bytes (pool-U3.6) — bound holds within 4× on pathological multi-byte; purpose (no multi-MB spike) preserved.
- `+` at exact cap (pool-U3.7) — "at least N" is true at exact-cap.
- `is_file()` EACCES → no arm (pool-U3.8) — the hook's binding contract is fail-open, never block a session.
- Unreadable MEMORY.md reported as absent (pool-U3.9) — deliberate fail-soft.
- Hub-marker spoofing / key-transform collisions (pool-U3.11/12) — content-based detection is the established discipline; the key transform deliberately mirrors the harness's own encoder (fidelity is the requirement, proven by the dots test).
- `reconfigure` failure + exotic stdout (pool-U3.15) — the real risk (C locale) is tested; residual is a hypothetical embedder.
- `.reviving` 2100s vs unbounded `claude -p` (N1.5) — bias-to-ring on a >35-min resumed turn that dies again is correct escalation; a timeout on the child would kill legitimate long turns.
- `_arm_stale_recheck` unlocked check-then-write dup sleepers (N1.15) — bounded and harmless (dup re-eval → dup-park guard); marker-after-Popen (F14) keeps the fail direction correct.
- ring() hand-built JSON escaping (N1.16 = pool-U1.3) — inputs are harness-controlled real paths; degradation lands on the still-ringing unknown-class path; bounded.
- Marker TTLs absent (N1.12) — every marker now has an explicit clearer (F1-F4 table in hooks-index) plus the prune sweep; anonymous-sid buckets eliminated by F18.
- waker_lost gets no 2a auto-revival (N2.7) — designed: the pane self-watch IS waker-loss's reviver; headless expansion rides the health-aware design if wanted.
- log_verdict unbounded (N2.9) — the shared log is trimmed on every sound.sh hook event box-wide; decider-only growth between events is ~100B/verdict.
- log-trim TOCTOU (N2.10) — best-effort debug log; bounded loss accepted.
- `.attempts` RMW race (N2.11) — post-F5 a second reviver per session no longer spawns; serialize_start spaces the residual.
- Token in curl argv (N2.13) — single-operator box (recorded threat-model memory).
- Hardcoded `/opt/fabrik/.env` (N2.14) — MESH_NOTIFY_CMD is the override seam; the path is this box's canonical creds source.
- Hook timeout 10 vs ffplay 15 (N2.15) — async hooks detach; the sync attention path's play is precondition-gated; powershell now bounded (F24).
- Rotation excludes billing/oauth/model (N2.16) — intentional; health-aware rotation revisits.
- Ring asserts prove log-reach not audio (N3.12) — accepted headless limitation, documented in the harness header; playback is environment, the decision point is the log site.
- attention-case untested (N3.18) — pre-existing sound layer outside the mesh scope, live-verified daily.
- `invalid_grant` dead arm (N3.19) — documented defensive legacy alias.
- B7 two-writer timing (N3.20) — both writers produce the asserted line; presence-grep is timing-tolerant.
- B5/B2/rotation-limiter fixtures (N3 CLEAN list) — recorded as genuinely mutation-sensitive.

Count: 24 FIXED classes (F1-F24, spanning ~55 raised candidates after cross-finder merge) +
~45 REFUTED candidates above. Every raised candidate appears in exactly one bucket; no
noted/to-watch parking lot exists.

## Coverage Checklist (final adjudication — spans all four rounds)

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Marker lifecycle / state machine | FIXED(11): F1-F4 F13 F14 G1 G4 G5 H2 H5 | every marker's writer/reader/clearer walked in R1 (N1) and re-walked in R3 (native contract-5 audit); lifecycle documented in hooks-index |
| 2 | Fail-open vs fail-closed on every gate/guard | FIXED(4): F14 F17 G7 H7 · CLEAN elsewhere | R1 N1.17 + R3 contract-1: every OSError gate biases to ring; both stat-failure shapes now fall toward ringing |
| 3 | Concurrency & races | FIXED(6): F5 F6 F8 G2 G3 H4 · REFUTED: mkdir-atomic, doorbell lock protocol, both-layers ms-window (config: 2a is for paneless contexts) | R1 N1 §2-3 · R2 break-the-fixes §2-4 · R3 native §3 · R4 pool §2 |
| 4 | Cost/quota/limit accounting | FIXED(3): F15 G8→(H6 full-identity) · quota-wall trace CONFIRMED-as-designed pending the health-aware build (2 attempts ~150s then ring; reset-clock revival is the operator-confirmed next-session design, in memory) | R1 N2 full trace; R2 G8; R3 H6 |
| 5 | Boundary/sentinel/prefix collisions | FIXED(5): F9 F18 G6 H2 H3 | _safe≡tr equivalence verified twice (R1 N1.18, R2 break-the-fixes #9 incl. the end-to-end sid trace); anonymous policy now uniform across BOTH scripts |
| 6 | Error-matrix completeness (11 classes × 8 decision points incl. the selfwatch filter) | FIXED(5): F11 F12 F16 G9 H1 · rest verified correct (R1 N2 CLEAN list; R3 contract-6/7) | R1 N2 matrix + R3 native contracts |
| 7 | Behavior-without-a-test | FIXED(9): F19 F20 + fixtures 42→66 (W1-W5, B8-B12, D2, D4-D7, self-test 12a2/12b/12c/18) | red-first witnessed: 10 R1 reds + W4 red in an independent finder run + D6's empirical repro |
| 8 | Test quality | FIXED(2): F21 + the D5/D6b vacuous-fixture corrections (async-decider pollution; transcript shape) · R3 native's revert-audit: no vacuous fixture in the B8-D7 set | |
| 9 | Injection/quoting safety | FIXED(3): F9 F23 G1(quoted rm) · REFUTED: threat-model set (single-operator box, recorded memory) | |
| 10 | 12-Factor applicable axes (III, XI, V, IX) | FIXED(2): F17 F24 · REFUTED: N2.9/10/13/14 (bounded/best-effort log + env-seam arguments) | |
| 11 | Doc truth | FIXED(2): F22 (5 surfaces) + counts re-trued each round (57→63→66) | check_hooks_index green |
| 12 | Fleet blast radius of the synced surface | FIXED(4): F7 F8 F10 H8 — arm order correct for headless, compact-resume, non-dict payloads, meshless boxes; consumed watches order their own re-arm | orient 14/14; fleet-synced via commit 7d987d70 |
| 13 | Rubric floor rows with no code in this surface (DB/compose/RLS/sticky/SQLite) | CLEAN | scope-verified: the surface is workstation shell/python hooks — zero DB, compose, or server-process code to which these floor rows could apply |

## Round 2 — fresh independent finders on the FIXED surface

Finder manifest: pool×3 (decider / three shell scripts / orient+tests — fresh model draw, all
scored) + native fabrik-reviewer ×2 (one briefed to BREAK THE FIXES with empirical repro
authority; one FRESH-EYES full sweep with no Round-1 knowledge) + adjudicator's own trace.

### Round-2 confirmed → FIXED (all in the same run)

| # | Finding (finder) | Fix | Guard |
|---|---|---|---|
| G1 | Recheck rings never epoch-scoped (env pop forces turn_dead=False) + dup-park guard evaluated BEFORE waker_lost + the recheck run's entry-clear emptied the death record behind a dup-park early-return → a SECOND independently-lost waker on a frozen transcript silently swallowed. **Empirically reproduced by the break-the-fixes native** (repro artifact in session scratchpad: run1 rang, run2 `dup-park → silent`, errparked left EMPTY) | recheck runs skip the entry-clear; waker_lost computed before the dup guard; waker-loss rungs identity-scoped (`size:wl:<ids>`) | harness D6 (2 lost wakers → 2 rings + record intact) |
| G2 | Self-watch reads the marker once and never re-checks during backoff/gate/jitter — decider's busy-clear mid-wait → false RESUME into a live session AND the consumed one-shot watch is gone (adjudicator + fresh-eyes native, live-reproduced: staged W4 ran red `57 ok, 1 fail` in the finder's independent run) | loop restructure: post-wait `[ -f marker ] || continue` — no fire on heal, watch KEEPS WATCHING (also shrinks the two-watcher double-fire window to ms) | harness W4 |
| G3 | Zero-backoff reviver classes can outrun the decider's busy-clear (settle ~2s) → duplicate resume into a session ruled non-terminal (break-the-fixes native #4) | `MESH_INITIAL_GRACE` 5s before the first survival check | AR/FIRE grace=0 keeps fixtures fast; code default 5 |
| G4 | busy-compacting has NO waker identity → a crashed compaction (PostCompact never fired) degrades to a clean tada ~17min later, no record, no Telegram (break-the-fixes native #5) | `compact` waker sentinel; proof = the stale `.compacting` marker PostCompact never removed | harness D7 |
| G5 | 1-hour lock-dir prune undercuts the 62-min busy-task recheck marker → any session's Stop could prune it 2min before its sleeper fired (break-the-fixes native #6, numeric) | prune cutoff 7200s | comment pins the invariant |
| G6 | Anonymous ("-"/empty) sessions collide on decider-side marker files (`-.rungsize`, `-.recheck`, `-.notified`) — sound.sh was guarded in R1, the decider wasn't (break-the-fixes #8 + fresh-eyes #6) | anonymous guard: no rung dedup/write, no recheck arming, no mesh-notify; bias to ringing | code guards |
| G7 | `s0=-1`/`s1=-2` distinct failure sentinels guarantee `continued → silent` forever on a persistently-unreadable transcript — hole in "bounded failure returns to RINGING" (fresh-eyes #5) | same sentinel both sides → falls through toward the ring path | code + comment |
| G8 | Waker identity tracked only `detail.split(",")[0]` — first-sorted id completed + second lost = loss never proven, silent tada (fresh-eyes #2) | full identity list travels; ANY member provably lost = proof | harness D6b (completed-first list still classifies) + self-test 12c |
| G9 | `invalid_grant` legacy arm never exercised by the sweep (fresh-eyes #11) | added to the ALL error-class sweep | harness A-loop (11 classes) |

Red-first witness for Round 2: W4 ran RED in the fresh-eyes finder's independent live run
("57 ok, 1 fail" quoted in its report); D6's pre-fix red is the break-the-fixes native's
empirical repro (dup-park swallow + emptied record, documented with the repro artifact);
D7's pre-fix red is proven by the pre-fix line itself (`waker = ... if busy-task else ""` —
compacting unconditionally yielded no identity → `waker_provably_lost("")` is `False` by its
first guard).

### Round-2 REFUTED (proof per row)

- Pool U0 (decider, 14): lock-supersede + missing-lock ambiguity = the documented doorbell
  protocol (release_lock docstring: "worst race outcome is one extra or one stale chime");
  empty-transcript parks ring-bias; waker staleness "false positive" is the proof's point
  (expired + never-completed = lost); payload re-serialization stable; prune-nonempty-dir —
  start.lock dirs are empty by construction; UTF-8 replace preserves ASCII ids; orphan sleepers
  bounded by depth cap + one-shot; deleted-transcript races all OSError-guarded.
- Pool U1 (shell, 7): ".attempts never cleared" factually wrong (decider clear set, normal-Stop
  path); "$0" resolution — settings wire the absolute path; ring() payload "context loss" — the
  consumer needs exactly the four fields it re-reads; marker non-atomicity bounded (≤30-min
  ceiling extension once, tmpfs small-write); selfwatch process leak — persistent Monitor
  lifecycle is harness-owned (TaskStop/session end); mutex triple-race degrades to two close
  starts only under >60s spacing misconfiguration.
- Pool U2 (orient): finder self-refuted every candidate on walkthrough (sid allowlist holds,
  no traversal, hub detection grounded); the "compact ⇒ already armed" assumption — the arm
  order is a mandated FIRST action at source=startup, which always precedes compact in the same
  process; non-compliance is an agent-discipline defect, not a hook hole.
- Break-the-fixes #3 (consume-at-arm eats a racing waker_lost record) — REFUTED by liveness
  logic: ANY marker present at arm predates the arming session's proof-of-life (an agent inside
  a running turn armed it); a fresh waker_lost consumed at resume-arm describes a strand the
  resume itself just healed; the audible ring already fired independently.
- Break-the-fixes #7 (per-session recheck dedup starves the subagent bridge) — bounded: the
  armed bridge's re-run re-decides fully and re-arms for the then-current verdict; the residual
  collapse-to-one-ring still RINGS (identity classification loss only, operator still alerted).
- Break-the-fixes #12 ("self-test covers none of the stateful paths") — partially factually
  wrong: the stateful paths are covered at the HARNESS layer (D2 busy-clear, D4 class
  propagation, D5 epoch rung, D6/D7 added this round); the finder's read set did not include
  the harness. The REAL hole it found via repro (G1) is fixed above.
- Fresh-eyes #4 (still_owner ambiguity) — doorbell protocol as above; #7 ("+" at exact cap) —
  "at least N" semantics true at the boundary; #8 (ring() JSON escaping) — degradation lands on
  the still-ringing malformed-payload path, inputs are real paths (R1 disposition upheld);
  #9 (two concurrent self-watches) — G2's post-wait check shrinks the double-fire window to
  milliseconds and a duplicate RESUME line is idempotent; #10 (doc "57 fixtures" while red) —
  the red WAS the staged W4 red-first fixture mid-review-cycle, by design; final count updated.

## Round 3 — closing sweep on the twice-fixed surface

Finder manifest: pool×2 (decider / shell scripts+harness, fresh draw, scored) + native
fabrik-reviewer ×1 (closing sweep briefed on all 8 contracts, ran the three gates live and
mentally reverted every R1/R2 fixture — none vacuous) + adjudicator.

### Round-3 confirmed → FIXED

| # | Finding (finder) | Fix | Guard |
|---|---|---|---|
| H1 | Self-watch fires "the cause has been healed" for human-only classes (auth/billing/org/model) — false by construction with rotation off; the reviver excludes them, the watch didn't (pool R3-U1) | human-only classes consume the record silently and keep watching (the death already rang + Telegramed in its own voice) | harness W5 |
| H2 | `.compacting` writer lacks the anonymous-sid guard every other marker has → two anonymous sessions collide on `-.compacting` = 15-min cross-session false silence (native #1) | compact-start/end skip sid-less payloads, logged | code guard |
| H3 | `.pid` lock: anonymous sessions collide on `-.pid`; a superseded anonymous verdict silently early-returns with NO log — a dropped ring with zero trace (native #2) | anonymous sessions run LOCKLESS (acquire/release/still_owner short-circuit; worst case an extra chime = the ring-bias direction) | code |
| H4 | 2a spawn gate never checks `.reviving` freshness → a second StopFailure mid-reviver-window spawns a concurrent second writer (native #3) | spawn gate skips when `.reviving` is fresh (<2100s, the decider's own interlock bound) | harness B12 |
| H5 | The recheck sleeper's trailing `rm` races an inner re-arm and deletes the freshly-armed dedup marker (native #4) | the recheck RUN unlinks its own marker at entry; the bash script carries no trailing cleanup | code + comment |
| H6 | `decide()`'s `[:3]` detail truncation makes a 4th+ concurrent waker unprovable at recheck time — silent park despite a genuinely lost waker (native #5) | full identity list travels (log display clips separately) | self-test 12a2 |
| H7 | Asymmetric stat failure (`s0` ok, `s1` OSError) still classified "continued" → eternal silence on a transcript that vanishes mid-grace (native #6) | `s1 = s0` on failure — every unreadable-after case falls toward ringing | code + comment |
| H8 | A fired (consumed) watch never tells the woken agent to re-arm — rest-of-session deaths lose the pane wake (native #7) | the RESUME line itself orders the re-arm with the concrete sid | wording in the fire line |

### Round-3 REFUTED (proof per row)

- Pool R3-U0 (decider contract walk, 7): the `s0==s1==-1` fall-through-to-ring is the FIX's
  intended direction, not a defect; waker_lost-write OSError → ring-without-record is fail-open
  toward ring with Telegram intact; parked turn_dead KEEPING the record is the self-watch's feed;
  compact-proof "race" needs a 15-min-stuck compaction completing in the same instant, outcome one
  benign wake; empty `CLAUDE_RECHECK_WAKER` cannot reach the `:wl:` suffix (waker_lost requires a
  proven non-empty identity); the anonymous errparked-write concern is unreachable (anonymous
  sessions never get a recheck armed); malformed-payload ring is the documented deliberate default.
- Pool R3-U1: anonymous skip of `.errparked` = the designed anonymous policy (decider unlink is
  missing_ok; anonymous-in-/opt is pathological); `.attempts` RMW double-spawn — H4 closes the
  spawn-side, serialize_start spaces the residual, cap bounds it; "infinite auth loop" — factually
  wrong (the watch is one-shot; second death rings), and H1 removes even the single spurious wake;
  "mesh-notify fork-bomb" — notify spawns are ring-gated and rings are dup-park-bounded, each
  spawn a 15s-capped curl; NO_REVIVE/identity confusion — misreading (CLAUDE_RECHECK_WAKER is
  decider-internal).
- Native #7 adjudicated as product note → FIXED as H8 rather than refuted.

```
Pass 1 — pool×4 + native×3 + live-log trace | found: ~100 → 24 fix-classes + ~45 refuted | fixed: 24 | → not done
VERIFY — red-first: 10 harness + 4 orient reds pre-fix; post-fix 57/57 · self-test · 14/14
Pass 2 — pool×3 + native×2 (break-the-fixes, fresh-eyes) | found: 9 (G1-G9) + ~30 refuted | fixed: 9 | → not done
VERIFY — W4 red witnessed independently; D6 red = empirical repro; post-fix 63/63 · self-test · 14/14
Pass 3 — pool×2 + native×1 (closing, contracts + fixture-revert audit) | found: 8 (H1-H8) + ~14 refuted | fixed: 8 | → not done
VERIFY — post-fix: `mesh-test: 66 ok, 0 fail` · self-test all green (incl. 12a2) · orient 14/14
Pass 4 — pool×2 (fresh draw) + native×1 (quiet-round audit w/ live-repro authority)
         | found: 5 (I1-I5, below) + ~10 refuted | fixed: 5 | → not done (changed code)
Pass 5 — pool×2 (fresh draw; both units self-refuted or refuted-with-cites: the "NO_REVIVE skips
         the death record" claim factually wrong per sound.sh:114 vs :140; double-spawn needs two
         deaths of one turn; sanitizer idempotence proven twice) + native×1 (final audit w/ live-
         repro authority)
         | found: 2 (J1 CONFIRMED live-reproduced: the blocking-hook-wait retry at the second
         decide() dropped `or recheck_run` — dead-tail semantics lost exactly when a sibling
         session's Stop hook is alive at recheck fire time, permanent-silence reopened in that
         branch; J2 minor: "recheck-armed" logged even when the dedup-marker write failed)
         + refuted: the live-but-silent-foreground ring-bias residual (accepted: proof gate
         prevents a false death record, only a premature done-chime remains) and the byte-vs-char
         64-boundary truncation (unreachable for ASCII UUID sids)
         | fixed: 2 | → not done (changed code)
VERIFY — J-batch: retry decide carries `turn_dead or recheck_run`; honest `no-dedup` log tag;
         harness D10 (fake blocking-hook process forces the wait+retry during a recheck →
         waker_lost record MUST land + elapsed-time witness that the wait engaged)
Pass 6 — pool×2 (fresh draw; unit 0 validated both J-changes on its own trace, unit 1's three
         candidates factually refuted: the human-class "CPU spin" misreads the loop whose
         `continue` re-enters the SLEEPING inner wait; "no-dedup poisoning" confuses the dedup
         marker with the death record; both-layers race = the upheld config adjudication)
         + native×1 (authoritative final audit: both J-changes CLEAN with citations, D10 proven
         load-bearing for the retry call site, all four cross-round interaction seams traced
         CLEAN, live runs verbatim `mesh-test: 71 ok, 0 fail` + `SELF-TEST: all green`)
         | found: 0 | fixed: 0 | → EXIT (quiet round + fully-adjudicated checklist)
```

Two observational notes recorded by the final native (explicitly non-candidates): the `,no-dedup`
guard is broader than strictly needed (harmless), and D10's hook-alive timing margin (~1-1.5s) is
tight under hypothetical heavy box load — test-fixture risk only, currently deterministic.

## Exit state

- Six rounds, 17 finder dispatches (11 pool units — every one scored into the flywheel — + 5
  native fabrik-reviewer audits + the adjudicator's own live-log tracing and isolations).
- 48 confirmed defects fixed (24 + 9 + 8 + 5 + 2), every one either watched RED first, empirically
  reproduced by a finder, or proven-red-by-construction of the pre-fix line — and re-guarded:
  harness 42 → 71 fixtures, decider self-test 34 → 43 checks, orient tests 10 → 14.
- ~105 raised candidates REFUTED with proof, each in the disposition ledgers above; zero parked in
  any "noted/to-watch" bucket.
- Every fix generation DR-versioned (5 snapshots) and the repo surface fleet-synced.
- Residuals (accepted, documented): ring-bias extra chimes for anonymous/edge states; the
  both-revival-layers ms-window if an operator ever co-deploys 2a against a pane (config-refuted);
  D10 timing margin; single-operator threat-model refutations.

## Post-close addendum (2026-08-10 ~05:50) — the review's observability fix caught a live incident

The 23:22 daily-quota deaths attempted their Layer-3 Telegram escalations and FAILED — visible
ONLY because of F17 (mesh-notify outcome logging; pre-review this was silent). Diagnosis: Telegram
404 — `/opt/fabrik/.env` splits the credential (`TELEGRAM_BOT_TOKEN` holds the SECRET HALF only;
the complete `id:secret` is `TELEGRAM_FULL_BOT_TOKEN`), so every escalation ever sent from this
box had 404'd silently. Fixed in `claude-sound.sh` (reads the FULL key, composes ID+secret as
fallback, colon-shape enforced), live-verified `notify-sent` at 05:51, DR `…T025212Z`. The
1:10 AM quota reset itself resumed nothing — correct per current design: reset-clock revival is
the operator-confirmed NEXT-SESSION build, and tonight is its live justification.

Self-audit: the exit conditions of the termination contract all hold — final round raised
nothing (Pass 6: found 0, fixed 0, two independent finder layers + the authoritative native);
every checklist row terminates CLEAN/FIXED/REFUTED with evidence; the last code-changing pass
(J-batch) was re-checked by a full fresh round (Pass 6), not a spot-verify; mechanical gates
green this turn (`mesh-test: 71 ok, 0 fail` · self-test · orient 14/14 · final_gate below);
ledger rows name their finders throughout.

## Round 4 — the audit that was meant to be quiet found five more

### Round-4 confirmed → FIXED

| # | Finding | Fix | Guard |
|---|---|---|---|
| I1 | `.recheck` dedup marker is CLASS-BLIND (native, live-reproduced: one sleeper, second class's arm silently dropped): busy-task's 62-min window swallows a later busy-subagent arm; when the old sleeper fires, the dead subagent has stale-aged out and the frozen assistant-mid tail reads busy-input → no re-arm, no ring, permanent silence — the bridge's own target shape | class-scoped markers (`.recheck-<verdict>`), `CLAUDE_RECHECK_CLASS` travels for the self-consume, legacy name also cleared | harness D8 (two classes → two sleepers + both markers) |
| I2 | Recheck runs evaluated frozen tails as LIVE (`busy-input` for a corpse assistant-mid) — the second half of I1's silence | dead-tail semantics: `decide(…, turn_dead or recheck_run)` — real wakers still silence, corpses park + prove | harness D9 (lost subagent end-to-end → waker_lost) |
| I3 | `_arm_stale_recheck` Popen failure fully silent (stderr is devnull'd) — an unarmed safety net with zero trace (native #3) | `recheck-arm-FAIL` log_verdict row + kept breadcrumb | log line |
| I4 | `:wl:` rung suffix `[:48]` truncation — two long waker lists sharing a 48-char head collide → second distinct loss dup-park-swallowed (native #4) | md5-hash suffix (16 hex), fixed-length, collision-proof at scale | code |
| I5 | RESUME re-arm line embedded the RAW `$sid` while the marker path uses `$safe` (native #5) + harness W4/W5 `kill $!` killed only the job-wrapper subshell, orphaning the timeout/selfwatch tree (native #2, reproduced with a process-tree dump) | `$safe` in the printed instruction; fixtures bound by the watch's own `timeout` + plain `wait` | code + fixtures |

### Round-4 REFUTED (proof per row)

- Pool U0: anonymous duplicate rings = the documented ring-bias tradeoff; crash-between-unlink-and-rearm = general
  mid-process-kill class, out of the doorbell's crash-consistency contract (exception paths ring via run_hook);
  commas-in-task-ids unreachable (harness ids alphanumeric); `tur.get("persistent")` falsy misread — `persistent:false`
  does NOT skip (the finder inverted the branch); duplicate of #2.
- Pool U1: "stale `.reviving` black hole" factually wrong — the decider's 2100s staleness bound falls through and rings
  (the finder lacked the decider file); both-layers ms-window — 2a is opt-in for paneless contexts, not co-deployed
  (residual recorded); jq-spawn latency — payloads are small by hook schema; log-trim TOCTOU — upheld R1 disposition
  (bounded loss, best-effort debug log); ffplay-with-live-socket failure — precondition-gated with beep fallback, pre-existing.
- Native attack-items 1, 2, 4(log-clip/env-size), 7 — CLEAN with cited lines (lockless mode gates verified writer-by-writer;
  spawn-gate fallthrough intact; A-sweep 11-class math + rotation-limiter asserts hold).

## Round-1 fix verification (this run)

- Harness: `mesh-test: 57 ok, 0 fail` (post-fix full run)
- Decider: `--self-test` all green (41 checks incl. the new 12b/12c/18 fixtures)
- Orient: `14 passed`
- Ruff: repo files clean; decider carries 6 pre-existing style rows (deliberate breadcrumb + old fixture style) — not introduced by this pass
- DR: `dr-claude: 20260809T185350Z` (post-R1) · `…T192045Z` (post-R2) · `…T193816Z` (post-R3) ·
  `…T195909Z` (post-R4/I-batch) — every fix generation versioned off-box
- FINAL post-fix md5 (exit state, after the R5/J-batch): sound=5d92e335c57b4e639a6d9aee4c0c3979 ·
  decider=99ad48dce4d31e6d1a85f5a1f80acf94 · autoresume=e576d9c2fdb2aa1418f64b26dad4fdb5 ·
  selfwatch=d53fe852aa91595dd444b4fe51f4fc7d · harness=86a3683a8e1c131ec37c150a3f1d5d7a
- Exit verification: `mesh-test: 71 ok, 0 fail` · self-test all green · orient 14/14 — each also
  re-run INDEPENDENTLY by the final native audit (verbatim in its report) · DR snapshots
  `…T185350Z / …T192045Z / …T193816Z / …T195909Z / …T201343Z`
