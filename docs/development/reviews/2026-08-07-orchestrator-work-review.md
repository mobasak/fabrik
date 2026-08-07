# Review — orchestrator-authored surface of the autotrigger dispatcher session (2026-08-07)

Surface: 0ab74259762b5e637dd2c434201c62a39e89de2e + dirty-md5 62140ac6afbd94901e49ca83e84a16a7
Scope: the DISPATCHING session's own authored work (the ticket coders' diffs each had 2-4 native-Opus
rounds; this reviews what did NOT get an independent pass): `scripts/enforcement/check_secrets.py`
(+tests) `804662d2` · `.claude/hooks/final_gate_stop.py` (+tests) `8136457b` · the hand-applied T04
assembler delta + all squash-apply merge mechanics (fidelity of merged master vs reviewed worktree
HEADs) · `commands/_sources/fabrik-decommission.md` deferred fixup `3bffff89` · governance edits
(Board flips, CHANGELOG entries, INDEX rows, spine Evidence table, receipts, whole-plan review doc,
lock) · Lesson 104.

Rubric: `python scripts/review_rubric.py --changed <the 9 scope paths>` — verbatim output captured in
the session transcript at dispatch (FLOOR: core/35-security-auth + core/25-data-postgres + core/30-ops
+ all twelve 12-Factor axes; matched packs incl. 45-testing-strategy; "50 injected mandates look
deterministically greppable" tail).

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| Merge fidelity — merged master content ≡ reviewed worktree HEAD, per ticket (esp. T04 hand-applied assembler) | CLEAN | 14-file byte-identity battery (all OK); AST union check: NEXT=24 keys, PARAMS=20 keys, zero dupes; decommission delta = T99 fixup only; Opus class-4 independent verify ("No drops, no duplicates, render sane 24/24") |
| Fail-open vs fail-closed — every new guard/exemption | FIXED(8) | Attribution v2: per-check outputs (Opus#4), path-token match (#1,#6), indeterminate-blocks for path-less (#2), count-independent (#3), session_floor (#5), mypy (#8), governance-self indeterminate (r2); direction table probed executed (r3-r5 re-checks clean) |
| Boundary/sentinel/prefix collisions | FIXED(3) | Substring ban (t==rel / abs-suffix / basename triple; probes: data_app.py no-match, abs-path match); token normalization; 1000-char extraction bound (r2); r3-r5 re-swept clean |
| Security — checker exemptions vs real secrets | FIXED(3) | Family narrowed (example/sample/dummy/todo/tbd dropped — Opus#9 table re-verified red); greedy-to-last-@ full-line capture (#10 probe green); DSN-pattern-only scoping (#11 suppression test) |
| Logic/null/empty/edge in the hook/checker diffs | FIXED(2) | `f.get("output") or ""`; two-empty-outputs test; remaining candidates REFUTED with quoted lines (call sites 3-tuple; session_floor or-chain includes ts=0) |
| Test quality — revert-red, no theater | FIXED(2)+proof | Mutation red-on-revert executed (reverted→1 failed / restored→16 passed); DRAFT-fixture class from T08 not repeated; 12 new tests each tied to a specific guard |
| Behavior-without-a-test | FIXED | Every new behavior carries a test: 7 attribution edges + govself + pre-session floor + 4 secrets shapes (51 total green) |
| Cross-file contract breaks | CLEAN | _run_gate 3-tuple at both call sites; render 24/24 + corpus --check OK post-merge; hook timeout 15 > HAIKU 8 margin re-verified in T05's review |
| Governance-truth | FIXED(9) | Spine md5-vs-commit citation reworded + Board legend (worktree tips → master squash commits); review-doc D7 verdict AMENDED (finder-floor gap disclosed, 3 in-range fixes named, sibling seo failure disclosed); receipts 48/48; Lesson 104 (9 worktrees, attribution-v2); lock resolutions; worktrees pruned branches-kept |
| 12-Factor axes on the changed surface | CLEAN | Scripts/hooks: stdout-only (XI), no config-in-code introduced (III); swept by 4 finder rounds, zero candidates raised |
| Cost/quota/limit accounting edges | CLEAN | 1024 _emit_skill assert verified tripping (T02 r3); 1000-char DSN bound (hostile-line probe 0.00s); HAIKU_TIMEOUT at frozen 8 with measured rationale |

## Pass Ledger

Pass 1 — COMPLETE — finders: pool fanout×4 (deepseek-v3.2-exp, gemini-3-flash-preview, qwen3-max, deepseek-v4-flash; recorded + scored 2/4/3/3) + native Opus fabrik-reviewer (running) + dispatcher mechanical battery (merge-fidelity: 14 files byte-identical vs reviewed worktree HEADs; accumulated assembler = exact T03∪T04 union; decommission delta = T99 fixup only; assembler parses).
Interim triage of pool candidates (live probes): CONFIRMED — substring false-attribution in final_gate_stop (`rel in failure_text`: authored `app.py` matches sibling `data_app.py` → false block; probe output in transcript). REFUTED with evidence — anchored-regex substring claim (`MyPassword123` no-match), `_PLACEHOLDER_VALUES` missing-family claim (line 73 has it), abs-vs-rel wave-through (`src/main.py` substring-matches abs path), stale 2-tuple call sites (both sites 3-tuple), trivially-green test claim (mutation red-on-revert: reverted→1 failed, restored→16 passed). PENDING adjudication: empty-output fail-closed edge (U2-3), `f.get("output") or ""` nit (U3-2), non-DSN URL exemption class (U3-6), pre-existing extraction-regex candidates (U0-4/5).
Native Opus authoritative pass (executed probes, throwaway harness): 21 findings. Merged round-1 totals: found: 39 raised (21 Opus + 18 pool candidates incl. overlaps) → 20 FIXED-class items in one batch + 19 REFUTED/pre-existing. → not done (changed code) — Round 2 owed.

Pass 1 fix batch (all landed this round):
- final_gate_stop attribution REWORKED (Opus #1-#8 + pool U1-1/U2-3/U3-2): per-check outputs from _run_gate; path-TOKEN matching with substring ban (exact / abs-suffix / basename); scoped to NEW failures only (baseline contamination killed); _ROUTINE_GOVERNANCE exclusion (the CHANGELOG.md incident — the v1 fix never fired in its own motivating case); session_floor filter (pre-session transcript edits don't attribute); path-less output = INDETERMINATE → block up to cap (the fail-open hole closed); mypy annotation fixed + `re` import. 31 hook tests (7 new red-on-revert).
- check_secrets exemption HARDENED (Opus #9-11, #12): family narrowed (example/sample/dummy/todo/tbd DROPPED — real shipped weak creds like the canonical `POSTGRES_PASSWORD: example` stay flagged); greedy-to-last-@ credential capture on the full line (prefix-placeholder truncation bypass killed); exemption scoped to the two DSN patterns only (whole-match suppression killed). 19 enforcement tests (4 new: real-world-weak, @-truncation, suppression, second family token).
- Governance corrected (Opus #13,#14,#16-19,#21): spine citation re-worded (b44bf3250438 = plan-review md5, not a commit) + Board legend mapping worktree tips → on-master squash commits; whole-plan review doc verdict AMENDED (D7 finder floor not met disclosed; 3 in-range corrective commits named; sibling seo gate failure disclosed); receipts 44/44 → 48/48; Lesson 104: 9 worktrees + attribution-v2 description; lock deferred_fixups got resolution fields.
- Hygiene (Opus #20): 9 merged coder worktrees removed, branches kept (Board tips stay alive).

REFUTED with quoted/executed evidence (no code change): anchored-regex substring claim (probe: MyPassword123 no-match) · _PLACEHOLDER_VALUES missing-family (line 73) · abs-path wave-through (probe: substring matches) · stale 2-tuple call sites (both 3-tuple) · trivially-green test (mutation red-on-revert: 1 failed reverted / 16 passed restored) · U2-4 non-edit-tool transcripts (covered by existing _session_files tests) · U3-3 own_uncommitted-after-downgrade (correct by design — EXIT law is orthogonal) · U3-6 non-DSN URL exemption (now impossible: exemption scoped to DSN patterns) · Opus-#7 no-transcript fail-closed (RULING: deliberate — attribution without authored-set knowledge is indeterminate; CAP bounds it; documented in the docstring).
Pre-existing, out of scope (residual (a)): U0-3 literal `secret` password token (in the original family pre-change) · U0-4/5 extraction-regex shapes predating this diff · Opus gate-crash silent fail-open (documented _run_gate philosophy, unchanged) · Opus #17 embedded-JSON-abridged (kept: the embed is verbatim-labeled for its run point; superseding run disclosed in prose).

Pass 2 — finders: pool×3 (deepseek-v3.2-exp, gemini-3-flash, qwen3-max; scored 3/3/3) over the round-1 fix diff | found: 12 | fixed: 2 (governance-self indeterminate branch; 1000-char DSN extraction bound) | 10 REFUTED (session_floor or-chain misread ×2; charset excludes '(' and ':' from tokens ×2; multi-DSN greedy fails closed; docs-example FP = deliberate security ruling; docs/CHANGELOG.md not a convention; FAKE_FAIL_OUTPUTS is a test fixture; combinatorial case already covered; noise-token attribution needs a matching authored filename) | → not done (changed code)
Pass 3 — finders: pool×2 (deepseek-v3.2-exp scored 2, gemini-3-flash scored 3) over the round-2 diff | found: 3 | fixed: 0 | 3 REFUTED (mixed governance+unauthored-cite has no realistic failing-check shape and lands on the never-trap default; 1000-char truncation of an over-long placeholder line fails CLOSED; abs-path governance cite same class) | → not quiet, next round owed
Pass 4 — finders: pool×2 (deepseek-v3.2-exp scored 2, gemini-3-flash scored 4) + dispatcher confirming re-checks (51 tests, mypy×2 clean, lean gate: session classes green) | found: 2 (both deepseek, self-refuted: extensionless-token indeterminate = by-design; session-floor staleness = factually wrong, baseline rewrites per SessionStart) | fixed: 0 | → not quiet, next round owed
Pass 5 — finders: pool×2 (deepseek-v3.2-exp, gemini-3-flash; scored 3/3), adjudicated design decisions fenced | found: 0 | fixed: 0 | → EXIT (checklist fully adjudicated; last code change was Pass 2, re-swept by Passes 3-5)

## Per-finding disposition ledger

Totals: 56 candidates raised across 5 passes = 22 FIXED + 34 REFUTED (sums; zero parked).

FIXED (22) — commits `aafc9b20` (r1 batch: attribution v2 ×8, secrets ×3, governance ×9 incl. worktree prune) and `665233ff` (r2: governance-self indeterminate, DSN bound) — every code fix carries a red-on-revert test; governance fixes carry corrected artifacts.
REFUTED (34) — each with quoted/executed proof recorded in the Pass Ledger rows above and the round transcripts: 19 in Pass 1 (incl. mutation red-on-revert proof, anchored-regex probes, _PLACEHOLDER_VALUES:73 quote, 3-tuple call-site grep, U3-3 by-design EXIT-law orthogonality, Opus#7 deliberate fail-closed ruling documented in the docstring), 10 in Pass 2, 3 in Pass 3, 2 in Pass 4.

Residual risks (pre-existing only, per the contract): U0-3 literal `secret` token was in the ORIGINAL family (pre-change); U0-4/5 extraction-regex shapes predate this diff; the gate-crash silent fail-open is `_run_gate`'s documented philosophy (unchanged). Sibling-owned (escalated, not mine): the live seo spec↔project DB-name drift (`specs/services/seo.yaml` staged by a concurrent session) — reported here and disclosed in the whole-plan review doc; the reworked hook attributes it as inherited (live-verified this session).

## Exit

Both exit proofs hold: the checklist above is fully adjudicated (no UNCHECKED) and Pass 5 is a genuine
quiet round (found: 0, fixed: 0) following two all-refuted rounds after the last code change (Pass 2).
Mechanical gates: suites 51/51, mypy clean ×2, corpus --check OK; the lean/full gate carries exactly one
failure, owned by a concurrent sibling session's staged files (disclosed above, not this session's to fix).
