# Strategic Backlog

**Last Updated:** 2026-08-25 — every item now carries an owner tag (see § Ownership).
Current split of the 16 open items: **infra 3 · fleet 11 · intel 1 · operator 1** (5 infra rows closed 2026-08-25).

> **Purpose:** Track work that's been deliberately deferred from active development — not because it's unimportant, but because it's not yet ready for a focus window, blocked on operator action, or correctly waiting for a triggering incident.

Generated from the end-of-day plan-state on 2026-06-07 after the trio Phase 5.1.a ship. Each item below is something we explicitly DIDN'T do this session and explicitly DIDN'T commit to today — and why.

---

- **[intel] `/fabrik-rivals` guard debt left after the 2026-09-14 key-autoload review** — four low-severity grader gaps a 25-mutant battery found and the run deliberately did not close, each one line: the unreadable-`.env` fail-open path (`chmod 000`) is claimed by a docstring and pinned by no test; the `expanduser()` on `$SUBAGENTS_ENV_FILE` is documented as a deliberate divergence from `libs/alerting/_dotenv.py` and nothing pins it, so the next re-port reverts it; `main()`'s `load_env(str(REPO))` argument is ungraded, and swapping it for `os.getcwd()` — the historical wrong-repo bug — passes every test; and the `note:` the docs make a contract is not asserted. Plus one behaviour item: running the HUB's copy of the driver from another repo binds `REPO` to the hub, so it reads the hub's `.env` and writes its checkpoint under `/opt/fabrik/.tmp` while preflight calls it repo-local (reproduced; the doc now states the precondition, but no check enforces it). None is a live defect in the shipped path — the closing reader's verdict was SAFE for 48 repos.

### The rotate-ledger's retention window, and the weekly urgent-drain leg that is still unbuilt (2026-09-16)

- **D-201 states the 1 MB `_ledger_rotate` cap holds "roughly three weeks of history"**, derived
  from ~288 ticks/day at ~150 B. Neither input matches this ledger, so the figure needs a NEW
  decision row (rows are immutable) — but ⚠️ do NOT re-derive it from the ledger's whole span: the
  fleet tick wrote ZERO tick rows on every date before 2026-09-08 (D-201 is what turned the series
  on), so a whole-span average is a bounded population wearing a denominator's clothes. Use a
  recent window, and state which. Owner: infra.
- **`_ledger_rotate` keeps only the NEWEST HALF on crossing the cap**, so retained history
  sawtooths between half and full — the GUARANTEED floor is half the apparent window, and a rotate
  can land mid-sample. Any plan that schedules work against "N weeks of accumulated rows" must use
  the floor, not the ceiling. Owner: infra.
- **One ledger row carries `ts=1.0` (1970-01-01)**, which poisons any `min()`/`max()` span over
  `rotate-ledger.jsonl` — it produced a 20,712-day span before range-filtering. Latent: nothing
  reads the span today. Owner: infra.
- **The weekly urgent-drain leg itself is NOT built.** `_urgent_drain_pct` remains session-gated,
  so an account that is weekly-hot and session-cold is RED by the bands contract with no mail. The
  tick now records `weekly_pct`; the threshold stays unset until that band has been observed —
  subject to the sampling bound above, which means the high band accumulates slowly by design.
  Owner: infra.

### Kaizen loop — the residue of the D-252 stop (2026-09-15)

- **`decisions.py` reconstruction residue** (owner: **infra**) — routed by the scope-growth stop
  rather than patched a fourth time: (a) the both-ends read anchors on the last two cells, which is
  wrong when the shatter happens INSIDE the `why` — fabrik-lib D-177 gets a prose fragment as its
  `where` where HEAD had an honest blank (1 of 947 rows); a `where` plausibility test would close
  it; (b) the short-branch marker is ungraded for columns 0-3, so a 3-cell row could regain a
  silent blank in `what` (0 live rows today); (c) `tests/test_decisions_table_shape.py` strips code
  spans before counting pipes, so 10 of 947 rows pass its shape check while the parser splits them
  long — the guard is lenient exactly where the parser is strict; (d) `.strip("|")` still eats a
  trailing escaped pipe (0 live rows, unchanged from HEAD).
- **`--next-id` collides when two agents mint correctly** (owner: **infra**; SPEC work) —
  `decisions.py --next-id` reads max+1 without reserving, and in a linked worktree the window is
  until MERGE, not seconds. Two incidents in iterative_image_editor alone (2026-09-03 three agents
  minted D-006 twice; 2026-09-15 lanes A and C both minted D-037/D-038). Rows are immutable, so the
  repair renumbers rows and BREAKS citations written before the merge. Reported with a proposal at
  01M2KA20BJ02GF1GG3TQ8YA6VB; needs a mechanism (reservation, or worktree-scoped ids), not a patch.

- **The quota-band contract's routed residue** (owner: **infra**; D-264) — four items the
  scope-growth stop routed rather than patched a fourth time: (a) the bands overlap at exactly 90
  and the RED band's mail keys on the SESSION window while the band keys on the HOTTEST, an 8-point
  gap where an agent is RED with no mail coming — both are in the operator's own directive text and
  are raised on its ack, not rewritten by its implementer; (b)
  `docs/workstation/claude-account-rotation.md:30` says the carrier binding is "a no-op" without
  both env vars while `claude_rotate.py:1386` says it fails OPEN onto the wrong chain — the doc
  overstates; (c) the legacy tick writer records `pct` as `max(five_hour, seven_day)` while the
  fleet writer records `five_hour` alone, so one file holds two incompatible series under one key;
  (d) stale comments in `claude_rotate.py` — `:4257` names caps "sarp 90, ob 80" against a live
  `caps.json` of 95/99, and `:4908` says the threshold defaults to 95 when it returns 98.
- **`check_corpus_weight.py` exits rc 0 while printing its growth warning** (owner: **infra**) — a
  caller gating on the exit code alone sees green, and the warning names a D-row obligation the
  script never verifies. Both halves surfaced by review seats on 2026-09-16.

- **`mail.py ack()` cannot distinguish "handled and answered" from "handled and silent"**
  (owner: **infra**; SPEC work, not a patch) — `ack()` takes a `disposition` from a fixed set and
  appends an `acked-by:` line; it has no notion of whether a reply was ever sent, so a message can
  leave the inbox with the sender never hearing anything and nothing downstream can see it.
  Measured on the HUB's own archive (1,254 messages, reply-threading resolved across the whole
  `/opt/fabrik-mail` store): **342 of 669 findings, 62 of 171 requests and 15 of 27 relays carry no
  reply anywhere** — worse than the fabrik-lib number that prompted the question (187 of 350).
  Reported by fabrik-lib-dev1 (01M2K5ZAAS41EHGQ52HDW6QFDM), who asked BEFORE building because
  `scripts/mail.py` is hub-vendored. It is: the fix changes the mail contract's grammar on a file
  distributed to ~46 repos, so it opens at /fabrik-spec — a `reply-sent` fact the ack can read, or
  a disposition that names silence honestly, plus whatever the digest should do with it.

- **The denominator rule never warns that a SEARCH ROOT can contain whole duplicate trees**
  (owner: **infra**) — it names `.claude/worktrees` only inside its `*.py` population example, so a
  compliant census rooted at a repo root over-counts: fabrik-lib measured `LlmMeter(` at 43 hits of
  which 35 were stale worktree copies, an AST pass returned 10. Two independent reports (fabrik-lib
  01M2JWEMFRFN3H item 3; a hub review seat the same day).
- **The mutation rule and a read-only finder brief contradict each other** (owner: **infra**) —
  CLAUDE.md mandates `repo_lock.py acquire` before a mutation sweep; a finder brief forbids mutating
  the shared tree at all. They reconcile only if "mutate a COPY under your own scratchpad" is named
  as the sanctioned finder path, which neither document says. A seat took the right route and
  reported worrying it was non-compliant (fabrik-lib 01M2JWEMFRFN3H item 4).
- **Nothing catches a malformed `docs/DECISIONS.md` row** (owner: **infra**) — `decisions.py:97` pads
  a short row with `[""] * (6 - len(cells))` and `check_decisions_unique.py` exits rc 0, so a
  column-shifted row answers the ledger query the contract says to run FIRST with a blank `where`.
  Two rows shipped that way this session (D-262, D-263) and were repaired by hand; a one-line
  cell-count assertion closes the class for all 264 rows. Separately, 8 rows carry MORE cells than
  the header from a literal `|` in prose (D-178, D-099, D-092, D-090, D-087, D-084, D-075, D-055).

- **The Pass-row FINDERS cell: checker, command text, error string and generator all disagree** (owner:
  **infra**; D-262) — `check_review_coverage.py:753` reads `cells[1]`; `commands/_fragments/term-coverage.md`
  documents "METHOD FIRST … finders after"; the checker's sibling error string and `review_receipt.py:180`
  both emit finders SECOND. A row written as documented is REFUSED. Three patches were tried and withdrawn
  (fail-open twice, then 9 retro-red receipts across 3 repos). Size: /fabrik-spec — it is a fleet-synced
  grammar with 847 receipts constraining it. Reported by site-provisioner 01M2K19AEKKAXG5NB211C2WFCM.
- **`check_citations_resolve` cannot grade a bare-filename citation, by design** (owner: **infra**; D-262) —
  `check_text:72-77` skips every path without a `/` because a bare name is ambiguous across repos (measured:
  11 of 30 hits at review of 66aa32a5). So `.env.example:N`, `Makefile:N` and CLAUDE.md's own `.gitignore:199`
  are ungraded and a wrong line number there is invisible. A fix must engage that measurement — root-anchored
  dotfiles are safe (measured: 43 repos, 156 resolve, 0 red) while `Makefile`/`Dockerfile` are not (5 false
  reds in the hub alone). Reported by trade-intelligence 01M2JT7N2RKZ7DABFMRDXE6KJ1.

- **`commands/assemble_commands.py::PARAMS` holds per-command TEXT that `--mark-answered` refuses**
  (owner: **infra**) — `_is_corpus_path('commands/assemble_commands.py')` is False, so a verdict about a
  per-command slot can be edited but never marked answered; the run dies mid-PHASE-5 and the queue never
  falls. Executed in a throwaway repo: `REFUSED — nothing marked: … touches no corpus path`.
- **The lock-status filter is narrower than the writer's own partition** (owner: **infra**) —
  `/fabrik-command-improve` and its readers filter `status == "active"`, while
  `scripts/enforcement/check_plan_lock_release.py:59` defines `NON_TERMINAL = {active, paused, blocked}`.
  No paused/blocked lock exists today (0 of 70), so this is a latent fail-open, not a live one.
- **A foreign `{{include:}}` on its own line renders GREEN and silently inlines** (owner: **infra**) —
  `assemble_commands.py:1170` substitutes `[\w-]+` while the leftover guard at `:1171` matches only
  `[A-Za-z_-]+`, so a digit-bearing directive passes both. A round-3 seat rendered a copied corpus with a
  foreign fragment inserted: rc 0, `rendered 37 commands`, the file 3.5 KB larger. Only the mid-line shape
  errors — the corpus warning about this is therefore true only for that shape.
- **`COMMAND_RUN_DIR` does not scope kaizen events** (owner: **infra**) — a review seat's scratch-scoped
  `command_run.py` probe still wrote a fabricated session into the shared fleet stream
  (`~/.claude/state/events/probe-seat-r3.jsonl`, removed). `kaizen_events.py` keys only on
  `KAIZEN_EVENTS_DIR`; every probe brief that scopes `COMMAND_RUN_DIR` must set both, or the scoping lies.

- **`^def test_` reaches 75% of Python graders** (owner: **infra**) — round 3 measured 310,030 of
  413,590 declaration lines across 79,354 files (`rg --no-ignore --hidden`): the pattern misses every
  class-method and `async def test_` grader. Rule (4) now hedges with "whichever pattern the suite's
  language uses" rather than prescribing; the pattern engineering is deferred, not done. Routed here by
  the D-252 scope-growth stop on `/fabrik-command-improve` 2026-09-15 (rounds 2 and 3 both confirmed
  only defects inside round 1's own fix).
- **No check greps the command corpus for BRE-invalid regex literals** (owner: **infra**) — rule (4)
  shipped `^\s*(test|it)\(`, which exits 2 under default BRE and reads as a clean `0` through a pipe:
  the exact trap CLAUDE.md § denominator-honesty names in prose. The corpus now warns in-line; nothing
  enforces it. Found by the round-3 seat's MACHINERY note.
- **`_MAIL_TRIAGE_FRAGMENT_SENTENCES` is named for a plan that no longer owns it** (owner: **infra**) —
  it is now the general fragment-phrase registry (adjudicated COSMETIC by the round-2 seat: the rows
  carry their own provenance comments, and a second dict would re-create the third-parallel-reader
  defect this run removed). Rename when something else touches the file.

`/fabrik-review` over `9802bd43..11b75eac` closed on the D-252 scope-growth stop after three
rounds (confirmed 28 / 21 / 9; own-fix 1 / 21 / 9). Every confirmed defect of rounds 2 and 3 lay
inside a fix the review itself had written, which is the stop's own definition. These four were
RECORDED rather than fixed, each with its destination.

| Residue | Why it was not fixed in-run | Destination |
|---|---|---|
| `tests/test_command_feedback_report.py::test_a_partial_write_is_not_reported_as_success` is a pure tautology — it re-implements `main()`'s rc branch inside the test body and never drives the CLI (mutating `main()` to `return 0` leaves it green) | One hop out: it landed at `84b62eb7`, the left endpoint of round 3's range, so the D-230 bar makes it RECORDED. The CLASS is covered — `test_cli_return_codes_separate_refusal_from_an_idempotent_no_op` reds under the same mutation — so the guard is a decoy, not a hole | **infra** — drive `main()` via `_cli(...)` with a forced PARTIAL and assert `returncode == 1` |
| `test_every_live_ledger_row_that_reads_as_a_none_still_closes` has three narrownesses: it `pytest.skip`s when the ledger is absent (CI, a fresh clone) so it asserts nothing there; its filter strips an ASCII hyphen that `_is_none_head` does not, so a row whose first token is `none-` would be selected and falsely reported; and it hard-codes `("none","nothing","n/a")` instead of reading `cr._NONE_WORDS` | Not vacuous — it selects 5 of 186 live rows and 4 of those 5 catch the regression it guards — so the value is real and the narrowing is a hardening, not a fix | **infra** — same file |
| `test_the_writer_never_blocks_on_a_non_regular_index` catches its regression by HANGING (rc 124), not failing | A genuine catch, but in a repo with the pytest leg armed it would wedge the completion gate with no diagnostic instead of printing a failure | **infra** — wrap in `signal.alarm` / `faulthandler.dump_traceback_later` |
| `command_feedback_report.py::_axis_of` buckets `<legal axis>: <anything bracketed>` as `placeholder`, so `change: lean: <cut the rubric block>` never counts toward its axis | Pre-dates this diff (`eca8da1d`), and 0 of 186 live rows are affected. Either `_axis_of` mirrors `_is_placeholder`'s keyed rule, or the sweep's `unkeyable` definition excludes a keyed bracket — today they contradict | **infra** — `_axis_of`, or the grader's definition |

**Not blocking.** Every fix from all three rounds is committed, pushed and fleet-synced; the gate is
green; the loop is proven end to end at `<scratchpad>/kzrev/probes/loop-closes-end-to-end.md`.
Receipt: `docs/development/reviews/2026-09-15-kaizen-loop-gap-closure-review.md`.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/rules_currency_watch.py`
<!-- END related-scripts -->
