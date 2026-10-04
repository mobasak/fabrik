# Prompt audit — intel agent charter (2026-10-04)

**Status:** APPLIED (operator request relayed by fleet, mail 01M3RQ7Y0XRVKCYVK9011SCSS0, work item W-09558696; method: the `/claude-api prompt-audit` skill's audit guide, which ships with the skill, not in this repo). The mail asked for a proposal with its report committed beside the change; the charter is intel's own file, so the loss-checked hunks were applied and the report records them.

## Assumptions

- **Scope:** `docs/reference/agents/intel.md`, the charter `.claude/hooks/agent_role.py` injects into every intel session. It is intel's only live prompt surface. Out of scope: the generated selection tables under `docs/reference/kilo/` (data, not instructions), and the pool-era text in `docs/reference/subagent-pool-contract.md` (frozen and non-binding while the pool is paused, D-343). The hub contract, the project template and the command corpus belong to infra's pass (W-e44ab7d8); the scaffolder's prompts to fleet's (W-2ceb0fc3).
- **Target model:** Claude Opus 5.5 / Fable 5.1 (named in the request).
- **Loss rule:** hub D-330/D-331. No rule is lost and nothing is cut for length; every edit below keeps its rule and its reason.

## Summary

5 findings applied (Group 1: 2 — F1, F2; Group 2: 3 — F3, F4, F5), 3 flagged; the closing review added three in-scope corrections (the stale D-183 uncomment clause, a dropped caution, the header date). The highest-impact one is F3: the charter told every intel session the hub copy of `libs/subagents` is kept byte-identical to canonical by re-vendoring. That has been false since fabrik-lib's hub hook was disabled, and D-547 now freezes the copy. A session trusting it would misjudge the module's state.

## Findings

| # | Location (before) | Evidence | Pattern | Why obsolete | Confidence | Action |
|---|---|---|---|---|---|---|
| F3 | intel.md:31-33 | "kept byte-identical to canonical by re-vendoring" | 2 — volatile specifics | Factually false today: fabrik-lib's hub post-commit hook is disabled and D-547 freezes the copy one fix behind canonical | High (verified against the repo) | rewrite: frozen while paused, re-vendored as restore step 4 (D-547) |
| F5 | intel.md:45-54 | "14 here, 100 in … 6 basenames live in both" | 2 — volatile specifics | Re-measured 2026-10-04: 10 hub scripts and 5 twins (`agent_selector` is gone from the hub). A remembered count rots, and the charter itself warns a reader will re-derive it | High (verified) | rewrite: keep the ownership rule; replace the counts with how to measure the twins |
| F1 | intel.md:14-17 | "⚠️ The mechanism under that question changed on 2026-09-07/08 … no longer a live pool" | 1d — migration-relative phrasing; 1a — emphasis | Written as a diff against an earlier charter the reader never saw; the current rule is that the beat follows the question, not the mechanism | Medium | rewrite as the current state, same meaning |
| F2 | intel.md:26 | "**DORMANT, NOT GONE.**" | 1a — pressure language | Capitals and bold on a fact that a plain sentence carries; the real constraint ("never dispatch a pool fan-out while the ruling stands") stays unchanged | Medium | rewrite at normal volume |
| F4 | intel.md:36-38 | "Learned the expensive way on 2026-09-05 (D-137): a deny was written into the vendored file, force-synced to 46 copies…" | 2 — history narrative | The rule's authority is the behaviour it prescribes; the story is in D-137. The reason (an edit is overwritten and forks 46 copies) is kept | Medium | rewrite to the rule plus its reason, citing D-137 |
| f6 | intel.md:21-25 | "four such findings once sat unworked … ~$16 in 28 hours" | 2 — history narrative | It is the stated reason for routing pool mail to intel, so it is context, not cruft (keep list 1) | Low | flag — kept |
| f7 | intel.md:62-64 | "the last real row is 2026-09-07 22:56 … deletion is an open operator go/no-go" | 2 — volatile specifics | A dated fact that may have moved; not re-measured here | Low | flag — re-check when the flywheel tombstone is next touched |
| f8 | intel.md:84-85 | "this box runs past the ≥2.1.224 floor" | 2 — version pin | A version floor rots, but the hub CLAUDE.md carries the same floor and is the owner | Low | flag — follows the hub contract |

## Loss check

Each rule in the charter before the edit maps to the charter after it:
- **F1:** "the beat did not move with the mechanism" is now "the beat is defined by that question, not by a mechanism".
- **F2:** the dormant-not-gone fact and its D-182 reason are unchanged in substance.
- **F3:** "no edit rights; the module is fabrik-lib's; owning the beat means mail, decisions, spend" is kept verbatim in substance. Only the false re-vendoring claim was replaced.
- **F4:** "a change inside the module is a request to fabrik-lib", its reason (an edit forks 46 copies and is reverted by the next re-vendor) and the caution that this revert is the boundary working, not a defect, kept with D-137.
- **F5:** "the extraction is half done; hub copies are intel's until the hand-off checklist lands; a twin divergence is a finding, not a cross-repo merge", all kept.

Review-found corrections in the same file: the dormant-pool paragraph's "both reverse by an uncomment (D-183)" was stale against D-343 and now reads "an operator ruling first, then a restore"; the header records the 2026-10-04 amendment; the same false byte-identical claim in a comment at `scripts/kilo-benchmarks/rank_task_subagents.py` was corrected too.

No test, script or hook matches the changed text (`command grep` over `tests/`, `scripts/`, `.claude/`). The first line `# Agent charter — intel`, which `agent_role.py` keys on, is unchanged.

## Verification

Step 7's behavioural probe is not applicable as an eval: the charter has no eval suite, and its rules are exercised by sessions, not by a harness. The edits change wording and stale facts only; no instruction was removed.
