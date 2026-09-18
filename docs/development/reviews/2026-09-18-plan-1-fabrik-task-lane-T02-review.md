# T02 — `command_feedback_report.py --queue fabrik-task`: per-ticket review ledger

Surface: `scripts/command_feedback_report.py` (+57/−0) and `tests/test_command_feedback_report.py`
(+241/−0), coder worktree `agent-aadd823bb3377f764` at `55b282fa1`, base `010586eac`. Pure inserts.

## Orchestrator's independent verification (before the review seats)

The coder's report is a claim. Each line below was re-executed here.

| Claim | How it was re-checked | Result |
|---|---|---|
| the gate passes | `pytest tests/test_command_feedback_report.py -q` in the coder's worktree | **135 passed** |
| scope respected | `git show --numstat` on the coder's commit | exactly the two files |
| pure inserts | `git diff --numstat 010586eac` | `57 0` / `241 0` |
| the `upgrade: sync` exclusion is load-bearing | mutation: dropped ` and str(r.get("upgrade") or "") != "sync"` | **KILLED** |
| the `fabrik-task` guard is load-bearing | mutation: widened `command == "fabrik-task"` to `True` | **KILLED** |
| other commands' headers unchanged | 40-row synthetic ledger over 6 commands, pre-script vs post-script, `cmp` per command | **0 of 5 differ** |
| the feature is not inert | same probe, `--queue fabrik-task` | differs by exactly the new `series:` line |

A note on the third-file phantom: `git diff` against master also listed the T01b receipt, because the
coder's worktree branched before that commit landed. The coder's own commit touches exactly two
files — checked, not assumed.

## A seam neither ticket could have known

T01b merged AFTER T02's ticket was written, and it introduced a THIRD value into the `upgrade` field:
**`sync (unverified)`**, set whenever the close could not actually refute the sync claim (no commit,
the measurement raised, or the sync filter was unreadable). T02's exclusion tests `!= "sync"` by
equality, so a `sync (unverified)` row STAYS in the `oversized_mini` denominator.

The orchestrator's reading is that this is CORRECT — the exemption exists because a genuine
sync upgrade-in-place necessarily counts its own sync path ("the ratchet working, not evasion"), and
a claim nothing verified has not earned that exemption. But it is ACCIDENTAL: nothing in the code or
a comment records the decision, and the next reader would have to re-derive it. It was put to the
authoritative seat as an explicit ruling rather than settled quietly here.

## Round 1 — acceptance review (2026-09-18)

Units-sized surface, `dispatch_headroom.py --units 1 --mechanical 0` → **SEATS: 3** (1 Opus + 2
Sonnet, the D-188 floor for a surface with fewer than three units), stamped `dispatch --seats 3`
before dispatch, all three in ONE message, on DIFFERENT angles:

- **Opus — the arithmetic:** the four numbers, their denominators, the `for_it` vs `rows` split, the
  `—/0` window, and a ruling on the `sync (unverified)` seam above.
- **Sonnet — the nesting rule:** the `/`-boundary in both directions (`/opt/fabrik` must never pair
  with `/opt/fabrik-lib`), the window's inclusivity, self-nesting, and the empty-`repo` collapse.
- **Sonnet — header integrity and the graders:** whether each of the five new graders would catch a
  defect in the behaviour it names, and the byte-identical claim re-executed independently.

Ground truth handed to the nesting seat so it need not read the live ledger (which no seat may):
291 rows, 16 distinct `sid`s, **3** spanning more than one `repo` — two of them a worktree under its
main checkout (which must nest) and one a `/tmp` scratchpad path (which must not) — and **0 of 291**
rows carrying an empty `repo`, so that guard is defensive rather than observed.

### Seat B — Sonnet, the nesting rule

Denominators: **33 isolated `_task_series_nested` calls** (25 boundary cases + 6 multi-candidate and
shuffle cases + self-nest + an epoch-scale float case), plus **5 end-to-end `--queue fabrik-task`
runs** against synthetic ledgers. 0 of them read the live ledger. Four whole classes examined and
CLEAN: the `/`-boundary in both directions, window inclusivity, multi-candidate order-independence,
and all three reconstructed live shapes.

| # | Severity | Site | Defect | Disposition |
|---|---|---|---|---|
| N1 | medium | `:1116-1120` | An empty or missing `sid` on BOTH sides collapses the session guard — `"" == ""` reads as the same session — exactly as an empty `repo` would collapse the repo guard the ticket calls load-bearing. The function's docstring claims fail-closed parity for a malformed `ts`/`wall_s` and does not extend it to `sid`. Reproduced end-to-end: the header printed `adoption 1/1` where the correct value is `1/2`. | PENDING |
| N2 | low-med | `:1106-1131` | "some OTHER command's row" is enforced only by the caller's filter, never by the predicate. Called with an `others` list containing `r` itself, every row nests trivially — a row's own `[ts − wall_s, ts]` window always contains its own `ts`. Latent: the sole call site excludes correctly. | PENDING |
| N3 | — | `:1106` | A non-dict row raises `AttributeError`. Unreachable: `load()` filters to `isinstance(r, dict)` before any row reaches `rows`. | NOT A DEFECT |

**Reachability of N1, verified by the orchestrator rather than taken from the seat:**
`scripts/command_run.py::_session_id` (`:91-108`) is an `or` chain ending in `_nosession_key()`,
which is repo-scoped — so the sole live writer can never emit an empty `sid`, and the seat said so
itself rather than overselling the finding. It remains reachable through a hand-edited row, a future
writer, or a truncated append, which this file's own `_num` docstring names as a real hazard for this
exact ledger.

### Seat C — Sonnet, header integrity and the graders

Denominators: 5 of 5 graders examined, **14 mutations executed** (each marker-verified on disk, each
restored and md5-re-checked against the pristine blob), 7 commands compared byte-for-byte between
pre and post.

**The claims that matter HOLD, verified independently rather than accepted:**
- Byte-identity: **7 of 7** non-`fabrik-task` commands `cmp`-identical between `010586eac` and
  `55b282fa1` — including a deliberately planted "leak-risk" row that hand-carries
  `oversized_mini`/`upgrade` keys on ANOTHER command, proving those keys cannot leak into a
  different command's header, and a command with zero rows.
- `fabrik-task` differs by **exactly one inserted line**, with no reordering and no existing byte
  changed.
- `--json` carries the line correctly, and `--mark-answered` cannot desync: it resolves handles from
  the raw ledger (`:351`), never by parsing printed text.
- The formatting nit the coder disclosed is genuinely PRE-EXISTING — present identically at both
  SHAs, at `:1661`, unrelated to the new code at `:2320+`.

**But the coder's "all five watched red via mutation" does NOT fully hold. 3 of 14 mutations produced
a FALSE GREEN:**

| # | Severity | Site | The uncovered sub-condition | Evidence |
|---|---|---|---|---|
| H1 | medium | `:1112-1119` | The `/`-BOUNDARY rule — the thing the ticket itself calls load-bearing ("a bare `startswith` pairs `/opt/fabrik` with `/opt/fabrik-lib`"). No fixture holds two repos sharing a bare prefix without a `/` boundary. | replaced both guarded `startswith`es with bare ones → **5 passed** |
| H2 | medium | `:1109` | The `sid`-EQUALITY check. No fixture places a same-repo, different-`sid` pair inside a matching window, so a regression letting cross-session rows nest ships silently. | dropped the `sid` comparison → **5 passed** |
| H3 | medium | test, the empty-repo grader | It needs BOTH non-empty guards removed to fail; dropping EITHER alone leaves it green — contradicting its own docstring, which says "the guard" in the singular where there are two independent early exits. | drop `r_repo` guard alone → **1 passed**; drop `o_repo` guard alone → **1 passed**; drop both → red |

H3 is the sharpest of the three: a future refactor merging those two conditions would ship the exact
defect the grader is NAMED for, and the grader would stay green.

Everything else grades correctly, measured not asserted: the sync exclusion, the unmeasurable share,
the upgrade rate, the adoption numerator AND denominator, the window inequality, the dash-denominator
branch, the command gate (caught even when widened to `if True`), an extra space in the shared header
string (so it checks exact bytes, not a substring), and the seam grader's row-count-before-indexing
discipline — re-confirmed against a live `command_run.py` close.

### Seat A — Opus, the arithmetic

Denominators: ~18 checkable claims, **284 ledger states** built, ~293 reader invocations, 12 of 12
cases isolated, a full Unicode sweep (0x0–0x10FFFF). **6 confirmed, 2 plausible.** Live ledger never
read.

**Its RULING on the `sync (unverified)` seam is better-reasoned than mine and is the one adopted.**
I argued "an unverified claim has not earned the exemption" — a moral reading. The seat gave the
mechanical one: a VERIFIED `upgrade: sync` row is forced to a count >= 1 BY CONSTRUCTION, because set
B is populated only when the filter is readable and the close is REFUSED when a sync claim yields no
hit. Its `1` is structural and says nothing about oversizing — that is what the exemption removes. A
`sync (unverified)` row reaches a numeric value ONLY when the filter was unreadable, so set B was
never populated and the count is the pure membership measurement, with none of that inflation. It
stays in, and `startswith("sync")` would silently delete real measurements.

| # | Severity | Site | Defect | Disposition |
|---|---|---|---|---|
| A1 | **high** | `:1144`, `:1147` | The `upgrade: sync` exclusion was SILENT where spec § V4 requires those rows "reported beside the rate". Two materially different ledgers printed a byte-identical line, and V4's own scaling term needs the missing count. Contradicts this function's own discipline 60 lines up — "an exclusion you cannot see is a denominator you cannot check". | FIXED |
| A2 | med-high | `:1321-1327` | `--queue X --command X` was PERMITTED and collapsed adoption to `t/t` — a vacuous 100%, rc 0, flattering. One redundant flag was the cheapest cobra path on this metric. | FIXED, with a message DISTINCT from the pre-existing "different commands" refusal, which keeps its own contract and grader |
| A3 | medium | `:1151-1154` | The adoption share ignored `state`, wrong on BOTH sides and flattering: a `handoff` fabrik-task row is a run that LEFT the lane, which is the spec's own sentence inverted. | FIXED (DONE-only, both sides) |
| A4 | medium | `:1145` | An unguarded `int()` crashed the ENTIRE reader on 128 of the 808 codepoints `isdigit()` accepts, and on >4,300 digits — reintroducing the class `_num` and `_rows` were rewritten to close. | FIXED |
| A5 | low-med | `:1148-1150` | `total = len(for_it)` counts rows that structurally cannot contribute, diluting both shares. | ROUTED |
| A6 | low | `:1143` | Truthiness where the file insists on presence: a JSON integer `0` vanishes — and `0` is what a clean run writes. | FIXED |
| A7 | low | `:1153` | O(n²) standalone scan: 500 rows 0.04 s, 5,000 0.25 s, 20,000 3.89 s. | ROUTED |
| A8 | low | `:1144` | The equality is load-bearing for `sync (unverified)` and nothing recorded it — 0 of 2,560 test lines mentioned `unverified`. | FIXED (comment + grader) |

## Round 2 — delta (2026-09-18)

One fresh Opus seat over `git diff 55b282fa1 18feeb734`. **2 confirmed, both inside round 1's own
fixes.**

- **The `int()` guard traded a crash for an UNDISCLOSED UNDERCOUNT.** `.isascii()` rejects 670
  codepoints `int()` parses fine and the length bound rejects 19–4300 digits — so it silently drops
  rows, three lines above the disclosure cell added in the SAME hunk for exactly that reason. FIXED
  as `[+N unreadable]`. ⚠️ The first cut of that disclosure counted `unmeasurable=…` rows as
  unreadable, double-reporting a legitimate outcome that has its own cell; two existing graders
  caught it immediately, which is what they are for.
- **The `o is r` branch was unreachable and ungraded** — deleting all six lines left the suite green,
  and it only PARTIALLY did what its comment claimed: a future caller passing the full row set would
  still have every OTHER same-session row nest `r`. DELETED. The second unreachable guard of mine on
  this ticket, after `not r_sid`.

Everything else it checked came back CLEAN, stated because a silent pass is not information: the
`sync (unverified)` mechanism (all 7 return points of `_task_measure` enumerated; no counter-example
constructible), the DONE-only baseline with no pre-`state` row vintage existing, no consumer parsing
the queue output by offset or regex, 13 of 13 targeted mutations killed, byte-identity reproducing,
and mypy showing the same pre-existing 5 errors outside the delta. Its **400-ledger differential
fuzz** found exactly four behaviour-change classes and no unexpected one — including that **27 of
400** random ledgers crashed the OLD reader, which is the rate the `int()` guard removes.

## Round 3 — delta (2026-09-18)

One fresh Opus seat over `git diff 18feeb734 e8a2faa96`, re-sweeping the three classes round 1
opened (`silent-exclusion`, `flag-collapse`, `state-baseline`) with the same brief rather than a
re-scope.

**Verdict: 5 CONFIRMED, 4 of them new to round 2's own fixes.** The headline: the two readers of
`oversized_mini` keyed on DIFFERENT STRINGS — the exclusion tested the whitespace-STRIPPED first
token, the `unmeasurable` cell tested the RAW value — so any value with a leading whitespace
codepoint was in NEITHER bucket. 29 of the 29 codepoints `str.split()` honours produce it, NBSP
among them. The comment added in that same hunk asserting "`unmeasurable=…` has its own cell" was
FALSE for exactly those values. Fixed with one `_is_unmeasurable()` predicate serving both readers.
Also: the `unreadable` count OVERSTATED the damage (the readability guard ran before the sync check,
so a sync row was billed as lost measurement); the `val and` guard, the suffix ORDER, and the
`unmeasurable` exclusion were all ungraded — the last defended only incidentally, by two graders
that happen to pin an exact prefix, while the docstring claiming it sat on a fixture that could not
reach it.

## Round 4 — delta (2026-09-18)

**Verdict: 3 CONFIRMED, all three inside round 3's fixes, plus one recorded no-op.**

⚠️ **The invisible row came back in its MIRROR form.** Hoisting the `upgrade: sync` test above the
readability guard made it claim EVERY sync row rather than the ones that would otherwise have
counted — 32 of 32 value shapes against the spec's 6 — so a row that is both `sync` and
`unmeasurable` landed in TWO buckets. And the printed numbers still SUM to the total: a reader
checking the denominator concludes every row is accounted for while one is double-counted and
another is hidden. Reconciling numbers are a worse failure than short ones. Closed by
`and not _is_unmeasurable(raw)`, which restores the spec's intersection and gives every row exactly
one bucket.

⚠️ **The reorder shipped with no grader** — reverting it left 152 of 152 green. That is the third
unguarded behaviour change of mine on this ticket, so the replacement grader asserts the WHOLE
partition on one ledger rather than the branch I happened to touch. I then re-derived the invariant
exhaustively myself: **72 combinations** of 18 value shapes x 4 upgrade states, every one in exactly
one bucket except the empty/`None`/whitespace values, which are the deliberately-uncounted
population a round-3 grader already blesses.

**Recorded, not claimed as a fix:** half of round 3's "one predicate for both readers" was a
behavioural NO-OP — the seat brute-forced all 1,114,112 codepoints and found the two spellings
disagree zero times, so only the second reader changed. Legitimate drift-proofing; the commit should
not have read as two corrections.

The seat's independent re-derivations came back clean: `_is_unmeasurable` correct at its edges across
96 value-state combinations; the parametrization NOT redundant (each of bare/space/tab/NBSP
discriminates a different path, proven by three separate mutations); byte-identity across 440
substantive comparisons with 0 differing outside `--queue fabrik-task`; the DONE-only baseline and
the `sync (unverified)` equality both holding; and no consumer parsing this output by offset or
regex.

⚠️ **THE D-278 EXIT DECLARED AT ROUND 3 DID NOT HOLD.** Round 4 found three defects inside the exit
commit itself. A scope-growth stop bounds the LOOP; it does not certify the last diff, and the round-3
commit should not have been written as though it did. Round 4 is the honest exit: the named set is
fixed, the partition is verified exhaustively rather than asserted, and the residue stays routed —
the pre-lane dilution, the O(n²) scan, and the spec § C3 self-contradiction, none of which this
ticket introduced or worsened.

**Final state (`3b71592f7`):** `scripts/command_feedback_report.py` +148/−6 and
`tests/test_command_feedback_report.py` +527/−1 against master. **153 graders pass.** `ruff check`
and `ruff format --check` clean on both.




