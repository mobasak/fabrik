# Review — auto-continuation (resume-mesh) full implementation · 2026-08-09

Scope: the complete auto-continuation stack the operator asked to verify as "100% functional and
correctly designed": `~/.claude/bin/{claude-sound.sh, claude-stop-decider.py, claude-autoresume.sh,
claude-selfwatch.sh, claude-mesh-test.sh}` + fleet-synced `.claude/hooks/session_orient.py` (arm
order, commit 50675991) + `tests/test_session_orient_hook.py` + `~/.claude/settings.json` StopFailure
wiring + `docs/workstation/{hooks-index.md, claude-configuration-inventory.md}`. Anchored on the
prior reviews `2026-08-09-plan-2-resume-mesh-review.md` and `2026-08-09-session-work-review.md`
(surface CHANGED since: waker-loss bridge, rotation opt-in-OFF, mesh-notify .env fix, ORIENT arm
order, first live production firing this evening).

Surface (pre-fix): 506759916f637371104841bdec0f291de0fa71f0 + working-tree d41d8cd98f00b204e9800998ecf8427e
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

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Marker lifecycle / state machine | FIXED(6): F1 F2 F3 F4 F13 F14 | every marker's writer/reader/clearer walked by N1 + adjudicator; lifecycle table now in hooks-index |
| 2 | Fail-open vs fail-closed on every gate/guard | FIXED(2): F14 F17 · CLEAN elsewhere | N1.17: every OSError gate biases to ring, matching the documented philosophy |
| 3 | Concurrency & races | FIXED(3): F5 F6 F8 · REFUTED(4): mkdir-atomic, RMW-post-F5, dup-sleeper, B7 | N1 §2-3, N2 §11 |
| 4 | Cost/quota/limit accounting | FIXED(2): F15 (+F5 counter integrity) · quota-wall trace CONFIRMED-as-designed pending health-aware build (N2.3 — 2 attempts ~150s then ring; reset-clock revival is the operator-confirmed next-session design, recorded in memory) | N2 full trace |
| 5 | Boundary/sentinel/prefix collisions | FIXED(2): F9 F18 · REFUTED: /opt/ prefix correct, _safe≡tr equivalence verified (N1.18) | |
| 6 | Error-matrix completeness (11 classes × 7 decision points) | FIXED(3): F11 F12 F16 · rest of the matrix verified correct (N2 CLEAN list: spawn gate exact, human-only exact, backoffs mirrored) | N2 matrix |
| 7 | Behavior-without-a-test | FIXED(5): F19 F20 + harness W/D2/D4/D5/B10/B11 fixtures (42→57) | red run: 10 reds each naming a finding |
| 8 | Test quality | FIXED(1): F21 (4 strengthened asserts were red-first) · REFUTED: N3.12/18/20 above | |
| 9 | Injection/quoting safety | FIXED(2): F9 F23 · REFUTED: threat-model set | |
| 10 | 12-Factor applicable axes (III, XI, V, IX) | FIXED(2): F17 (XI observability) F24 · REFUTED: N2.9/10/13/14 above | |
| 11 | Doc truth | FIXED(1): F22 (5 surfaces) | check_hooks_index green |
| 12 | Fleet blast radius of the synced surface | FIXED(3): F7 F8 F10 — arm order now correct for headless, compact, non-dict payloads, meshless boxes (existing test) | |
| 13 | N/A rows (DB/compose/RLS/sticky/SQLite) | N/A | no such code in surface |

## Pass Ledger

```
Pass 1 — finders: pool×4 (sound / selfwatch+autoresume / decider / orient+tests) +
         native×3 (lifecycle+races / error-matrix+quota / test-quality+doc-truth) +
         adjudicator live-log trace
         | found: ~100 raised → 24 confirmed fix-classes, ~45 refuted, rest merged dups
         | fixed: 24 | → not done (changed code)
VERIFY — red-first witness: 10 harness reds + 4 orient-test reds against pre-fix code;
         post-fix: harness 57/57, self-test 41 green, orient 14/14 (recorded below)
Pass 2 — (fresh independent round on the fixed surface — REQUIRED, in flight)
```

## Round-1 fix verification (this run)

- Harness: `mesh-test: 57 ok, 0 fail` (post-fix full run)
- Decider: `--self-test` all green (41 checks incl. the new 12b/12c/18 fixtures)
- Orient: `14 passed`
- Ruff: repo files clean; decider carries 6 pre-existing style rows (deliberate breadcrumb + old fixture style) — not introduced by this pass
- DR: `dr-claude: 20260809T185350Z` committed + pushed (mesh scripts versioned off-box)
- Post-fix md5: sound=aaf1980cc1f04894ecea50e255931bfb · decider=b4a270be1e0a6e5672b72b5682e6f05e ·
  autoresume=5dc51df1b61b8a94d7602bcf0aa823f3 · selfwatch=722ba4dd47900f97006d25315bddd30c ·
  harness=5248ad9c5af40d4749fea9851f86ada3
