# T03 — the command source, its render and the docs rows: per-ticket review ledger

Surface: `commands/_sources/fabrik-task.md` (NEW, 8,804 B), `tests/test_fabrik_task_source.py` (NEW),
`commands/assemble_commands.py` (+1), `docs/CAPABILITIES.md` (+1),
`docs/reference/command-run-protocol.md` (+17/−5). Coder worktree `agent-a297c7a61fd0d2690` at
`88373aae5`, base `010586eac`.

## Orchestrator's independent verification (before the review seats)

| Claim | How it was re-checked | Result |
|---|---|---|
| C2's byte ceiling | `wc -c` on the source vs `fabrik-features.md` | **8,804 B** against **8,847** — 43 B headroom |
| the single include | `command grep -o '{{include:[a-z-]*}}'` | `run-record`, and only it |
| frontmatter | TRIGGER (EN+TR), SKIP, `Stage:` present | all three |
| the corpus check | my own run | rc 0, "all sound across 66 file(s)" |
| the ticket's pytest | my own run | 3 passed |
| `assemble --check` rc 1 | read the whole drift list | the ENTIRE drift is `fabrik-task.md` + its skill MISSING from the installed corpus — structural, since a new source cannot install from a worktree |

**THE LANE RUNS END TO END.** Executed from this source against the MERGED T01a+T01b machinery in a
throwaway repo with a scratch `COMMAND_RUN_DIR`: `start --command fabrik-task --file … --declare …`
printed its `RECORD:` line, `step --phase 2 --design <file>` advanced, and `done --commit <sha>`
closed with `oversized_mini: 0` written to the ledger. That is the first proof the three tickets
COMPOSE rather than each passing alone.

**The fragment defect, routed to the orchestrator by the coder and adjudicated here.** The shared
`commands/_fragments/run-record.md` renders a generic `done … --feedback` line carrying no
`--commit` — which this lane REFUSES, leaving the record `running` and the Stop hook holding the
turn. Verified: the fragment has 0 occurrences of `--commit` and is rendered by **34** sources. NO
fragment edit is made: the lane's own source overrides it in the line IMMEDIATELY after the include
("Neither generic line above is this lane's — `command_run.py` REFUSES a `fabrik-task` `start`
without `--file`/`--declare` and a `done` without `--commit`"), which is the right place and leaves
the other 33 commands untouched.

## Round 1 — acceptance review (2026-09-18)

`dispatch_headroom.py --units 2 --mechanical 0` → **SEATS: 3**, stamped before dispatch, all three
in ONE message on different angles: Opus on the SOURCE's correctness, Sonnet on DOCUMENTATION TRUTH,
Sonnet on the GRADERS and the render predicates.

### Seat B — Sonnet, documentation truth

~18 checkable claims identified, **16 executed**, 14 confirmed accurate. Its highest-value result is
a pass: **`docs/CAPABILITIES.md`'s hand-added row is BYTE-IDENTICAL to what
`generate_capability_index.py` emits live** (the generator run in-process against this tree, `diff -u`
exit 0) — so the row will not silently vanish on the next regeneration. The deliberate rewording that
makes the 160-char truncation land mid-word rather than on a space is confirmed too, which matters
because the armed `trailing-whitespace` hook would strip a trailing space and every regeneration
would re-add it.

| # | Severity | Site | Finding | Disposition |
|---|---|---|---|---|
| B1 | low-med | `command-run-protocol.md:52` | The `declared` dict is written `{files, decision, heavy, mechanism, oneway, tradeoffs, sha, sync_test}`; the code builds `files, sha, sync_test` FIRST, then the five declared answers. All 8 keys are right — the ORDER is not, and curly-brace notation reads as an ordered literal in a codebase whose style is "byte-for-byte, executed". | PENDING |
| B2 | low | `command-run-protocol.md:57-59` | The `blocked`/`handoff` signatures omit `[--commit <sha>]`, which is a real flag on both (`:2531`, `:2563`, `:2580`). The `done` row's prose states the tri-state correctly, so this is asymmetric presentation, not a false claim. | PENDING |
| B3 | low | `command-run-protocol.md:59` | PRE-EXISTING and out of scope: the untouched `handoff` row describes `--resume "<RESUME block>"` as inline text, while the code and the new source both use a PATH. Introduced 2026-08-27 (`9dee3e94`); T03 did not touch that row, but the new source now demonstrates the correct usage beside a row that still describes the wrong shape. | ROUTED |

Confirmed accurate by execution (not read): the count-first `oversized_mini` grammar across three
live closes; `declared` having exactly 8 keys with `sync_test` reading `unavailable`/`ok`; `--file`
accepting a genuinely nonexistent path; `--commit`'s full tri-state including the out-of-lane
refusal; all three `unmeasurable` reasons with their exact strings; `sync (unverified)` appearing
only for an UNREFUTABLE claim while a refutable-and-refuted one is REFUSED at close; `--design`
storing once with a warned no-op on the second call; and the EXCL set matching the doc.

⚠️ **A CLAIM IN MY OWN BRIEF WAS REFUTED, and the record should say so.** I told this seat that T03
"fixed a wrong word T01b had shipped into `docs/reference/command-run-protocol.md`", repeating the
coder's report without checking it. The seat could not substantiate it, and I verified its refutation
myself: T01b touched that file in NONE of its four commits (`01a216fea`, `f0a7b6a08`, `7e7e9e3dc`,
`280ff4c84` — 0 each), and the file carried ZERO `fabrik-task` mentions before T03. The correction
was T03's own, on its own first draft. Passing a coder's claim to a seat as established fact is the
"read it, don't recall it" failure; the brief's instruction to verify independently is what caught it.

### Seat C — Sonnet, the graders and the render predicates

3 of 3 graders examined, **13 mutations** run, each marker-counted before its run and md5-restored
after. It re-verified the coder's independence claim rather than accepting it: a second include at
**8,826 B** (UNDER the cap) reds the includes assertion alone, and an 8,908 B single-include source
reds the size assertion alone — the two are genuinely orthogonal, so neither is doing the other's
work. Extractor denominator confirmed: **4 of 4** fenced lines extracted, the 5th mention correctly
excluded as prose.

| # | Severity | Site | Finding | Disposition |
|---|---|---|---|---|
| C1 | low-mod | test `:158-164` | The parser grader never asserts the extracted lines name THIS lane. Replacing `--command fabrik-task` with `fabrik-spec` on all four lines left **3 passed** — so a typo'd `--command` would silently disable the very `--commit` refusal the test's own docstring calls its purpose. | PENDING |
| C2 | low | test / source | Nothing ties the printed `--phases 5` to `_phase_count(source)`. Mutating it to `--phases 3` (with five real headings) left all 3 green. ⚠️ The sibling `fabrik-deploy-checklist` HAS this cross-check (`tests/test_check_command_corpus.py:880`), so the precedent exists. | PENDING |
| C3 | low | test `:61-90` | The extractor is blind to a `command_run.py` line in a 4-space indented block with no fence — an appended bad line was never extracted and the grader passed. Fire rate today: **0 of 59** `command_run.py` mentions across the corpus use that shape. | ROUTED |
| C4 | low | `assemble_commands.py:74` | Nothing pins the `NEXT["fabrik-task"]` entry's CONTENT. Verified by hand that it renders correctly and that an absent entry falls back to "(no defined successor…)", which would be wrong for this command — but a future edit mis-wording it goes undetected. | ROUTED |

Confirmed correct by mutation, not assertion: the parser grader reds on a syntactically invalid flag;
`_phase_count` returns exactly 5 because the `## SIZE` and `## UPGRADE` headings deliberately miss the
`^#{2,3}\s+PHASE\s+\d` regex; the render grader uses `tempfile.TemporaryDirectory()` exclusively and
never touches `~/.claude/commands`; the parser grader isolates via `COMMAND_RUN_DIR` and passes with
the ambient variable unset; `ruff check` clean with no N802.

**Corpus-checker reach, measured rather than assumed — 8 predicate classes:** 4 actively
examine-and-catch a planted defect in this file (chain-reference existence, script-path existence,
run-record presence, close-`--feedback`), 3 scan it but find no matching content (web-tool names, the
trailer check, claimed-callers), and 1 never applies to command sources at all (agent frontmatter).
A baseline full-corpus audit over a `git archive` export returned only the 19 pre-existing findings
unrelated to this file — **0 attributable to the new source**.

### Seat A — Opus, the command source itself

Denominators: 6 of 6 phases walked as an agent would; **44 sentences** checked for restatement
against `run-record.md`, `close-feedback.md`, four sections of `CLAUDE.md` and
`fabrik-review-scoped.md`; 7 of 7 route-ups cross-checked against both the spec's rule rows AND
`_task_size_gate`'s precedence chain (destinations and ORDER agree in all 7); all 12 of the spec's
cobras read; 72 plan-lock files censused; 43 repos scanned. **19 findings.**

**The one that matters most: a COBRA the spec never named, and it is cheaper than the one it did.**
OVER-declaration. Declare three files, touch one — `oversized_mini: 0` is GUARANTEED, at zero risk
of a refusal, where under-declaring only RISKS a non-zero count. Strictly cheaper and strictly safer
than cobra (1), and the source's own "a path that does not exist yet is accepted on purpose: declare
the grader you are about to write" actively licenses it. The only counter was phase 4's first seat
question — "does the change FIT the declared files?" — which is ONE-DIRECTIONAL: a strict subset
answers yes. The seat checked all twelve of spec § C3 and over-declaration is none of them. So the
lane's headline metric was satisfiable by padding, and the ≤3 cap would have bound only honest
agents.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| A1 | **high** | The source sends the agent to `CLAUDE.md` § Orient step 0 for the lane table — the ONLY definition of the five `--declare` answers — and at T03's own HEAD that file has **0** occurrences of `lane table`, `oneway`, `tradeoffs` or `fabrik-task`. The table is T04a's deliverable. | RECORDED in the spine as a mutual T03↔T04a dependency with a one-way merge order (verified independently: 0 of all four terms) |
| A2 | **high** | The cobra pointer is a repo-RELATIVE path to a hub-only file. **43 repos under /opt with a `.git`, 1 carries it** — so 42 of 43 followed the sentence delegating the entire counter-measure layer to nothing. Both fragments already use the hub-absolute form for this reason. | FIXED (`/opt/fabrik` prefix) |
| A3 | **high** | "in the SAME shell as the commit" — but the fence contained NEITHER the commit nor the push, so the copy-pasteable unit is a separate process on a three-session tree. A sibling's single-parent commit in that window passes all three close-time refusals (not-a-commit, merge, older than `started_at`), so the lane computes `oversized_mini` from someone else's diff and writes it as this run's, silently, rc 0. | FIXED ("the SAME Bash call", with the consequence named) |
| A4 | **high** | The over-declaration cobra above. | FIXED (the question now asks whether the change MATCHES the declaration, and names the padding) |
| A5 | med-high | A FALSE claim about the file it cites: "`handoff` is the fragment's third sanctioned terminal" — the fragment says "EXACTLY ONE of two ways" and contains `handoff` **0** times. | FIXED (cites `AGENT_CLOSED_STATES`) |
| A6 | medium | The sync lane test FAILS OPEN — an unreadable hub filter prints a stderr-only SKIP and the start looks clean — and the source omitted that third outcome entirely. | FIXED |
| A7 | medium | The declaration cannot be amended, and phase 1 (MEASURE) is exactly what changes it: a file SWAP trips no UPGRADE trigger and the close then punishes the agent who measured correctly. | ROUTED |
| A8 | medium | A near-verbatim RESTATEMENT of `CLAUDE.md`'s FIX DIRECTIVE step 1 — the defect the source's own opening sentence forbids, and it dropped the attribution methods. | FIXED (cut; **funded** the rest) |
| A9 | medium | The `UPGRADE:` token set is complete (7 of 7) but not a PARTITION — `seat` overlaps three peers and V4 groups by token. | ROUTED |
| A10 | medium | `UPGRADE:` must BEGIN the value (`startswith`, case-sensitive); the source taught only the token rule, so an agent prefixing its own evidence records NO field at all, silently. | FIXED |
| A11-A19 | low | The `&#124;` rule's placement; "six phases on ONE run record" (phase 4 opens its own); "adds three things" undercounting; phase 2 writing into a directory only phase 5 creates; a hardcoded `2,000`; "gaps print one each" (true of the flag guard; path checks short-circuit); the coldest branch on the surface; the SKIP clause's DRIFTED copy of `/fabrik-spec`'s triggers; unmeasured TRIGGER recall. | A15/A16/A18 FIXED; A17 CUT to fund A2/A6; rest ROUTED |

**What funded the fixes, on an 18 B budget:** A8's restatement (~62 B) and A17's plan-lock fallback
(~170 B). A17's census, re-derived: **72 lock files, 5 without `owned_paths`, 0 of those five
`status: active`**, and both live active locks carry both fields — the coldest branch on the surface.

Its executed probe answered a question I had asked: as the phase-5 capture block was written —
standalone, nothing after it — the `|| exit 1` is **not** load-bearing; it only normalises rc 128 to
1 and does not prevent an empty `commit.sha`. It BECOMES load-bearing in the shape A3 asks for, which
is a second reason to pull the commit into the fence.

## Round 2 — delta (2026-09-18)

One fresh Opus seat over `git diff 88373aae5 054e04fb2`, re-sweeping the three classes round 1
opened (`over-declaration-cobra`, `hub-relative-pointer`, `capture-window`) with the same brief. It is
asked specifically whether either CUT removed something load-bearing, and whether "the SAME Bash
call" is actually the property that makes the capture safe.

**Verdict: 8 CONFIRMED, and TWO of round 1's three HIGH fixes were INOPERATIVE.**

- **The over-declaration counter was POLARITY-INVERTED, and round 1 made it worse.** It sits under
  "a yes to any is that seat's UPGRADE verdict", and round 1 added a second *yes-is-good* clause to
  an already yes-is-good question — so the seat fired an UPGRADE on a correctly-sized change and
  stayed SILENT on the padded one. Executed: declare three files, commit one, `oversized_mini: 0`,
  rc 0, no refusal and no warning. ⚠️ The orchestrator then reproduced the SAME inversion once more
  while fixing it.
- **The `/opt/fabrik` prefix was MALFORMED** — appended to the end of the sentence rather than inside
  the backticks, producing a doubled "of" and leaving the token an agent COPIES repo-relative.
- **"in the SAME Bash call" was not the invariant**, proven by execution: commit → a sibling's commit
  → the prescribed `git rev-parse HEAD`, all inside ONE Bash call, captured the SIBLING's sha, and
  through the real close wrote `oversized_mini: 1 · paths=sibling_only.py` at rc 0.

Also confirmed: the plan-lock cut left the collision guard FAIL-OPEN; the protocol doc still carried
the superseded "same shell" two rows from the table this ticket edited; "it adds three things" was an
undercount; and TWO graders were satisfiable without the outcome — the phase count was a substring
over the WHOLE source (a prose decoy defeated it) and nothing asserted the mandatory verbs EXIST, so
deleting the `done`/`handoff` fences left all four green.

## Round 3 — the fixes, and three more of mine (2026-09-18)

A third fresh seat confirmed the polarity was finally right (all three questions yes-is-bad, audited
one by one) and the path correct inside its backticks, and that the capture race is **narrowed, not
closed** with the prose now matching — it executed the race against the new fence and the source
promises nothing it does not deliver. It then found three more defects of mine:

- ⚠️ **The grader cited D-296, a row that did not exist.** Drafted to scratch, never minted, while
  the cap raise already pointed at it — and `decisions.py --next-id` would have handed 296 to the
  next caller, a collision this repo has already paid for once. Minted first, in its own commit
  (`a2a28f76f`), ahead of the merge that cites it.
- ⚠️ **The `git commit -m "<subject>"` I put in the fence was a HARD STOP handed to the reader.**
  Phase 5 steps 2-3 mandate editing the two canonical SHARED-APPEND files, and phase 3 of this same
  source says those go through the private-index recipe, "never the working file" — so a pasted
  plain pathspec commit ships a sibling's half-finished hunks under your name. And `-m "<subject>"`
  cannot express a trailer block, so every pasted commit lands trailer-less. BEFORE my change the
  fence had no commit and the agent fell through to § EXIT correctly: **my fix created the
  contradiction.** The fence now chains off "your § EXIT commit" — the chaining was the property
  worth teaching; the commit's shape was never mine to prescribe.
- The polarity aside sat INSIDE the italic question span, terminated by the same `?`, so a seat reads
  it as a fourth question — and it answers YES on the honest strict-subset run. And a `yes` on the
  MISS limb routed an UNFINISHED run to the spec chain, where the one-way ratchet strands it.

**Final state (`2958f46c1`):** the source is **8,958 B**, back UNDER the D-296 cap of 8,980 without
touching a correctness fix — funded by cutting three clauses that restated their own sentences.
4 graders pass; `check_command_corpus.py` rc 0 across 66 files; the lane still runs end to end.



