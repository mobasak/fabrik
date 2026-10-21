## RESUME

Item: W-10146d20 (own scrape tool replacing Firecrawl). Plan: docs/development/plans/2026-10-21-plan-3-own-scrape-slice-1a.md
(CONVERGED, D-1101), Phase A of 3. Live runs: /fabrik-execute-plan (phase 1/3) with a nested /fabrik-review (phase 1/5,
round 1 recorded: findings 24, confirmed 13). Receipt: docs/development/reviews/2026-10-21-plan-3-own-scrape-slice-1a-phase-1-review.md
(IN-PROGRESS, rows not yet filled). Pin: /opt/fabrik/.tmp/runs/5ce9d888-9344-466f-b905-652ac93cdf89/fabrik-review-2026-10-21T18-21-51-0300/pins-1.

Pass 1 is complete (wave 1: A-opus, A-sonnet, B-sonnet; wave 2 after the hibernate: A-haiku, B-haiku).

FIXED (committed in 7b5ea84f3, the hibernate wip): A-opus-1 (text-pin tests updated), A-opus-2 (researcher :149
meaning), A-opus-3 (block boundaries: WRAP, fence-aware _mask, _line_of; 20000-text probe 0 mismatches), A-opus-4
(prose spellings), A-opus-5 (_fragments), A-opus-7 (:35 grammar), A-opus-8 (vs./etc., kwarg), A-sonnet-1
(inflections), A-sonnet-6 (docstring names URL false red), B-sonnet-1 = A-sonnet-3 = A-opus-6 = A-haiku-4 = B-haiku-2
(pin on scrape alone), B-sonnet-2 = B-haiku-1 (CHANGELOG count).
REFUTED: A-opus-9 (scrape schema has top-level proxy; crawl has it in scrapeOptions), A-sonnet-4, A-sonnet-5.
RECORDED by design: A-sonnet-2 (other Firecrawl tools out of scope), live-box drift test (red until merge render).

STILL OPEN (confirmed, not yet fixed — do these first):
- A-haiku-1: a `stealth`/`auto` instruction after `;` or ` — ` in the SAME sentence escapes OTHER (OTHER is checked
  over the clause only). Fix: check OTHER (and NEG?) over the clause plus the rest of its sentence/paragraph up to a
  blank line, or end-of-paragraph; add fixtures "pinned; retry with `proxy: "stealth"`" and the em-dash form.
- A-haiku-2: "falling back to the default proxy" passes; add `default` near proxy to OTHER (e.g. `default proxy`).
- A-haiku-3 / B-haiku-3: "Use Firecrawl to read the page with the stealth proxy" is no mention; consider widening
  MENTION to `firecrawl` followed within a clause by read|fetch|scrap|crawl, or record by design (presence scope,
  docstring cobra) — decide with a fire-rate probe on the corpus.

UPDATE 20:10: the three above are FIXED (a2c0564f5; fire rate 0 on the 72-file corpus; 6 of 7 mutants killed, the
equivalent fence-mask alternative deleted). Receipt rows, pass-1 ledger and residuals filed (23e88e0d3); the review
run record is at phase 4 (converge), pass 2 owed after the 21:00 quota reset.

Corpus-test sweep (97 files, 20:10): 4118 passed, 2 skipped, 1 FAILED —
tests/test_vision_reads_work_stores.py::test_assemble_commands_check_reports_no_render_error_and_only_expected_drift.
Cause: its `allowed = ("fabrik-vision", "fabrik-epics-review")` is a hard-coded list from another ticket, so any worktree
that edits another command source reds it until the merge-time render (here: fabrik-spec, fabrik-spec-review,
fabrik-plan-after-chat, the researcher agent). Confirmed candidate for pass 2 — fix at the root: derive the allowed set
from the sources this tree changed against the installed corpus's base (or against `git merge-base HEAD origin/master`),
red-prove on a copy, and add the file to the review surface (`command_run.py surface --add`).

Next steps: fix the sweep failure above (round-zero probe first), re-run the 97-file corpus-test sweep
(scratchpad rv/run_corpus_tests.sh; rebuild it if /tmp was wiped), fill the receipt rows, then pass 2: the round-1
seats re-verify their own slices on a new pin (pins-2). Close the review, then the Phase A commit with the plan marker;
then /fabrik-execute-plan blocks on missing infra for Phases B and C (fabrik-lib W-89c8b88f, W-eadc4d0a).
