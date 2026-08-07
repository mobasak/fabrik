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
| Merge fidelity — merged master content ≡ reviewed worktree HEAD, per ticket (esp. T04 hand-applied assembler) | UNCHECKED | |
| Fail-open vs fail-closed — every new guard/exemption (check_secrets placeholder family; final_gate_stop attribution downgrade) | UNCHECKED | |
| Boundary/sentinel/prefix collisions (substring matching in attribution; regex anchoring in the DSN family) | UNCHECKED | |
| Security — did the checker exemptions open a real-secret hole | UNCHECKED | |
| Logic/null/empty/edge in the two hook/checker diffs | UNCHECKED | |
| Test quality — revert-red, no mock theater, no trivially-green (the 4 new/changed test files) | UNCHECKED | |
| Behavior-without-a-test on the changed surfaces | UNCHECKED | |
| Cross-file contract breaks (assemble_commands hand-edit vs render pipeline; hook contract vs settings timeout) | UNCHECKED | |
| Governance-truth — CHANGELOG/INDEX/receipts/review-doc/Evidence claims vs repo reality | UNCHECKED | |
| 12-Factor axes on the changed surface (III config, XI logs — scripts/hooks) | UNCHECKED | |
| Cost/quota/limit accounting edges (1024 assert; timeout margins) | UNCHECKED | |

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

## Per-finding disposition ledger

(every candidate raised by any finder, terminal FIXED or REFUTED)
