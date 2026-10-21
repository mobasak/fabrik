## RESUME

Paused for the operator's /hibernate (2026-10-21 18:36). Item: W-10146d20 (own scrape tool replacing Firecrawl).
Plan: docs/development/plans/2026-10-21-plan-3-own-scrape-slice-1a.md (CONVERGED, D-1101), Phase A of 3.

Where: /fabrik-execute-plan Phase A, inside its /fabrik-review pass 1 (receipt
docs/development/reviews/2026-10-21-plan-3-own-scrape-slice-1a-phase-1-review.md, IN-PROGRESS).

Done in pass 1 (all three seats returned; slice A opus+sonnet, slice B sonnet; the two Haiku seats were TRIMMED by
dispatch_headroom and are still owed as a wave-2 full pass over slices A and B before any delta pass):
- CONFIRMED and fixed: A-opus-1 (4 text-pin tests asserted the old wording: tests/test_agent_definitions.py,
  tests/test_spec_plan_lane_text.py updated), A-opus-2 (researcher :149 cached-arm meaning), A-opus-3 (clause crossed
  block boundaries: WRAP regex, fence-aware _mask, _line_of rewritten; 20000-text reference probe 0 mismatches),
  A-opus-4 (prose spellings, case-insensitive MENTION), A-opus-5 (_fragments scanned), A-opus-8 (vs./etc., kwarg
  form), A-sonnet-1 (inflected negations), B-sonnet-2 (CHANGELOG count dropped), B-sonnet-1/A-sonnet-3/A-opus-6
  (pin on scrape alone in search/scrape pairs; no new crawl claim), A-opus-7 (researcher :35 grammar).
- REFUTED: A-opus-9 (firecrawl_scrape schema has top-level proxy enum basic|stealth|enhanced|auto; crawl takes it in
  scrapeOptions — read via ToolSearch this session), A-sonnet-4, A-sonnet-5 (superseded by A-opus-2's fix).
- RECORDED by design: A-sonnet-2 (extract/agent/interact/map out of scope: plan pins scrape/crawl), A-sonnet-6
  (URL-dot false red, now named in the docstring), test_the_live_box_matches_the_repo_sources (red until the
  merge-time render, by design).
- Tests: the four files pass except the live-box test (103 passed, 1 by-design fail). The 97-file corpus-test sweep
  (scratchpad run_corpus_tests.sh) was STOPPED by the pause — re-run it first.

Next steps on wake:
1. `python3 /opt/fabrik/scripts/sysadmin/hibernate.py woke`.
2. Re-open both runs from their seeds (parent /fabrik-execute-plan first, then /fabrik-review).
3. Re-run the 97-file corpus-test sweep; record round 1 (`round --findings 20 --confirmed 12 …`, recount from the
   ledger above); fill the receipt rows.
4. Wave 2: the two Haiku seats over slices A and B (full pass), then pin pass 2 for the round-1 seats.
5. Close the review, then Phase A commit (plan marker), then the execute-plan run blocks on missing infra for B/C.
