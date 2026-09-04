# Ticket breadth — the mechanical check that predicts review cost

`scripts/enforcement/check_ticket_breadth.py` · advisory · stdlib-only · fleet-synced

## Why this is a check and not a rule

The operator's question was: *"if tickets are broad, why aren't we narrowing them?"*

The answer is not a new rule. "Keep tickets narrow" is prose, and a rule an agent read
hours ago does not bind it (Lesson 116). The same week this check was written, the kaizen
pass was documented as "binding — weekly" and ran **zero** times, because nothing fired it.
So breadth ships as a check that runs at the moment the plan set is still editable —
`/fabrik-plan-review`'s convergence point and the Tier-2 gate — or it does not ship.

## The measured basis

Source: this repo's own review ledgers, `docs/development/reviews/*.md` — the same corpus
`docs/workstation/kaizen.md` reads for its `Review rounds /plan` column.

- Review rounds per plan average **4.2 (n=14/22)**, with maxima of **16** and **13**.
- The rounds track how many **independent risk classes** a ticket exposes, not its line
  count. The worked pair, 2026-08-15:
  - `T01-disarm-old-world` — thread-safety + alert suppression + clock skew + fail-direction
    + ledger integrity (**5 classes**) → **8 rounds**, 34 fixups.
  - `T02b-fleet-gitignore` — one gitignore line → **1 round**.
- Roughly **1–2 rounds per hand-counted risk class**, each fix opening the next round's
  surface.

## The score

Risk classes are not directly countable from a ticket file, so the check scores three
proxies read from the ticket's own declared fields:

| Component | Read from | Why it is a risk class |
|---|---|---|
| `areas` | distinct top-level dirs in `## Touches` (`scripts/`, `src/`, `.claude/`…), **excluding test surfaces AND doc-sync companions** (`docs/`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `.env.example` — the Matrix mandates they travel with the code that invalidates them; counting them produced peel advice a HARD rule forbids, and following it RAISED the flag count 3→4, measured at wef 01M1DMBS) | each surface reviews on its own axis |
| `behaviors` | `## Behavior Contract` Given/When/Then bullet count | each is a distinct user-observable behaviour |
| `mix` | Touches declares **both** ordinary code **and** a governance/fleet-synced surface | a ~46-repo blast radius mixed into local work |

```
score = areas + behaviors + (1 if mix else 0)
flagged when score >= 5   (BREADTH_THRESHOLD)
```

The governance surface set mirrors the `governance-sync` files-filter in
`.pre-commit-config.yaml` (kept as a literal tuple so the check stays stdlib-only and works
in a project repo with no hub tooling). Fenced blocks are stripped before any count — a
quoted template row is not a behaviour.

The check never prints a bare number: every flagged ticket gets its components, the
predicted round range, and a concrete split naming the surfaces to peel off.

### Test surfaces are NOT a risk class — and never a split target

The first cut counted `tests/` as an independent area. That was wrong, and the advice it
generated was actively harmful: *"keep `scripts/` and peel off `tests/` into separate
tickets."*

**Tests ship WITH the behaviour they prove.** The Behavior Contract requires a test per
behaviour in the *same* ticket, and watched-fail-first requires the test and its code in one
changeset. A ticket whose tests live in another ticket cannot be red-on-revert proven, and
its `Gate:` line would pass while proving nothing. Shipping that suggestion to ~46 repos
would have taught the anti-pattern fleet-wide.

So a companion test surface is excluded from **every** signal — not an area, not the "code"
half of the governance mix, never a peel target. It is still *reported*
(`[+1 test surface(s), not counted]`) so the exclusion is visible rather than silent, and
split suggestions say so explicitly: *"their tests move WITH them — never split a test from
the behaviour it proves."* A test-only ticket scores as one area, never zero.

Recognised as test surfaces: a `tests`/`test`/`spec`/`specs`/`__tests__`/`testing` directory
anywhere in the path, and `test_*.*` / `*_test.*` / `*.test.*` / `*.spec.*` / `conftest.*`
files anywhere.

## Predicted rounds — the measured ratio, not the prose one

The hand-counted class→round ratio is 1–2, but this score is a **proxy** for classes on a
different scale. Retroactively over the 14 tickets with real per-ticket round receipts:

> **rounds ≈ 1.0 × score** (median 1.0, mean 1.00, spread 0.3×–1.6×)

so the printed range is `0.5 × score` to `1.5 × score`. Using 1–2× would over-predict every
ticket by roughly double. **The constants follow the data, not the sentence that motivated
them.**

## Why advisory

Default is warn + **exit 0**, and the gate registration passes no `--strict`.

This is a heuristic over declared fields — and a weak one: score-vs-rounds is Spearman
**ρ = 0.45** (Pearson 0.31, n=14). A hard-fail would block planning on a guess, and
**a blocked plan is worse than a broad one**. `--strict` exists for opt-in author-side use
(exit 1 when anything is flagged).

The warning footer therefore states the check's own accuracy at the point of use:

```
Calibration honesty: in the n=14 retroactive set, 2 of 4 flags with round receipts
matched a ticket that actually ran >=4 rounds (score-vs-rounds Spearman rho=0.45).
Treat a flag as a prompt to LOOK, not a verdict.
```

An advisory that overstates itself gets ignored wholesale, which is worse than not warning —
this box already has a history of advisories nobody reads. Other fail directions, all
deliberate:

- a **parse error** yields a `NOTE` and a zero score — a malformed ticket never reds a gate;
- a repo with **no plan sets** exits clean and **silent** — the fleet-wide inert case, since
  most of the ~46 synced repos have no plans at all;
- a **missing** script is not silently green: `run_optional_check` returns the
  `⚠ check not present, skipping` message that `--json` collects into `warnings`.

## Retroactive calibration — what it would have flagged vs what reviews actually cost

Generated by `python scripts/enforcement/check_ticket_breadth.py --all --table`. Actual
rounds come from the per-ticket review receipts
(`docs/development/reviews/2026-08-15-plan-1-login-once-credentials-T0*-review.md`) and the
per-ticket rounds column of `docs/development/reviews/2026-08-07-plan-1-autotrigger-and-commands-review.md:40-48`.

Scores below are **post-fix** (test surfaces excluded), which lowered every ticket that had a
companion test surface by 1.

| Ticket | Plan set | areas | behaviors | mix | score | flagged (≥5) | ACTUAL rounds | verdict |
|---|---|---:|---:|:--:|---:|:--:|---:|---|
| T01 | 2026-08-15-login-once-credentials | 1 | 4 | no | 5 | **YES** | **8** | ✅ caught — but now EXACTLY on the threshold |
| T02a | 2026-08-15-login-once-credentials | 1 | 6 | no | 7 | **YES** | 3 | ❌ **false positive** |
| T02b | 2026-08-15-login-once-credentials | 1 | 1 | no | 2 | no | 1 | ✅ cleared the cheap one |
| T03 | 2026-08-15-login-once-credentials | 1 | 6 | no | 7 | **YES** | 2 | ❌ **false positive** (highest score, cheapest but one) |
| T04 | 2026-08-15-login-once-credentials | 1 | 1 | no | 2 | no | 1 | ✅ |
| T05 | 2026-08-15-login-once-credentials | 1 | 1 | no | 2 | no | — | orchestrator-run, no receipt |
| T01 | 2026-08-07-autotrigger-and-commands | 1 | 2 | no | 3 | no | 4 | ❌ **missed** (ran ≥4) |
| T02 | 2026-08-07-autotrigger-and-commands | 1 | 2 | no | 3 | no | 3 | ✅ |
| T03 | 2026-08-07-autotrigger-and-commands | 1 | 2 | no | 3 | no | 3 | ✅ |
| T04 | 2026-08-07-autotrigger-and-commands | 1 | 2 | no | 3 | no | 3 | ✅ |
| T05 | 2026-08-07-autotrigger-and-commands | 2 | 3 | no | 5 | **YES** | 4 | ✅ caught |
| T06a | 2026-08-07-autotrigger-and-commands | 1 | 1 | no | 2 | no | 2 | ✅ |
| T06b | 2026-08-07-autotrigger-and-commands | 1 | 1 | no | 2 | no | 3 | ✅ |
| T07 | 2026-08-07-autotrigger-and-commands | 1 | 1 | no | 2 | no | 3 | ✅ |
| T08 | 2026-08-07-autotrigger-and-commands | 1 | 1 | no | 2 | no | 3 | ✅ |
| T99 | 2026-08-07-autotrigger-and-commands | 1 | 1 | no | 2 | no | — | integration ticket, no row |
| T01 | 2026-08-12-catalog-extraction-fabrik-prep | 1 | 8 | no | 9 | **YES** | — | set ABANDONED unexecuted |
| T02 | 2026-08-12-catalog-extraction-fabrik-prep | 1 | 6 | no | 7 | **YES** | — | set ABANDONED unexecuted |
| T03 | 2026-08-12-catalog-extraction-fabrik-prep | 1 | 6 | no | 7 | **YES** | — | set ABANDONED unexecuted |
| T04 | 2026-08-12-catalog-extraction-fabrik-prep | 1 | 5 | no | 6 | **YES** | — | set ABANDONED unexecuted |
| T05 | 2026-08-12-catalog-extraction-fabrik-prep | 1 | 4 | no | 5 | **YES** | — | set ABANDONED unexecuted |

### Re-deriving the threshold from this table

Corpus mean is **3.07 rounds** (median 3), so "genuinely expensive" is taken as **≥ 4
rounds** — three tickets: 2026-08-15 T01 (8), 2026-08-07 T01 (4), 2026-08-07 T05 (4).

| threshold | flags | hits | recall | precision |
|---:|---:|---:|:--|---:|
| 3 | 8 | 3 | 3/3 | 0.38 |
| 4 | 4 | 2 | 2/3 | 0.50 |
| **5** | **4** | **2** | **2/3** | **0.50** |
| 6 | 2 | 0 | 0/3 | 0.00 |
| 7 | 2 | 0 | 0/3 | 0.00 |

**5 survives re-derivation, but for a new reason and with a thinner margin.** It is the
*largest* threshold that still catches the 8-round ticket: at 6 the check catches nothing
expensive at all (recall 0/3) — a cliff, not a gradient. 4 is numerically identical (no
ticket scores exactly 4). Dropping to 3 buys full recall at the cost of flagging 8 of 14
tickets, which is an advisory nobody would read.

### Where the threshold disagrees with reality — stated, not tuned away

- **It now sits on a knife edge.** Before the test-surface fix, 2026-08-15 T01 scored 6 and
  cleared the threshold comfortably. It now scores **exactly 5**. One more correction of this
  kind and the corpus's only genuinely expensive ticket falls below the line.
- **It misses one.** 2026-08-07 T01 scores 3 and ran 4 rounds. Recall **2/3**.
- **It over-flags, and the worst offenders are the top scorers.** 2026-08-15 T02a (score 7)
  cost 3 rounds; T03 (score 7) cost 2. The two highest-scoring tickets with receipts are
  among the cheapest in the corpus. Precision **0.50**.
- **The correlation is weak-to-moderate.** Spearman **ρ = 0.45**, Pearson 0.31 (n=14). The
  score explains some of the variance in review cost, not most of it.
- **Nine flagged tickets prove nothing.** The 2026-08-12 catalog-extraction set was abandoned
  unexecuted (Board entirely ⬜), so those scores were never paid.
- **The validated sample is n=14** of the repo's 21 plan-set tickets.

**Conclusion:** this is a *screen*, not a predictor. It reliably separates "one line" from
"several behaviours", and it is right about half the time on which of those actually cost
review rounds. It is registered advisory for exactly that reason, and the warning says so in
its own footer. Do not read a flag as "this ticket is wrong"; read it as "say out loud why
this is one ticket."

## How kaizen refines it

`BREADTH_THRESHOLD`, `ROUNDS_RATIO_LOW`/`HIGH`, and the footer's honesty constants
(`CALIBRATION_N`, `FLAGS_WITH_RECEIPTS`, `FLAG_HITS`, `SPEARMAN_RHO`) are provisional
constants at the top of the script. The refinement loop is kaizen's weekly
`Review rounds /plan` column (`docs/workstation/kaizen.md`):

1. Each week the pass re-derives the mean from `docs/development/reviews/*.md`.
2. When the mean moves materially, re-run `--all --table` and re-pair the scores against the
   *new* per-ticket receipts — the table above is the template.
3. Re-derive the threshold from the recall/precision sweep, adjust the ratio constants to the
   re-measured median, **update the footer constants so the printed accuracy stays true**, and
   rewrite this section's tables. Never adjust any of them to make a particular plan pass.

Two standing open items:

- **Precision (0.50) needs more per-ticket receipts.** Every plan set that writes per-ticket
  review ledgers with machine-readable round markers adds a data point.
- **The threshold's margin is one point.** If a future correction lowers scores again, check
  whether 2026-08-15 T01 still clears the line before keeping 5 — if it does not, the score's
  components need rework, not the threshold.

⚠️ **Any change to the scoring must re-run this calibration.** Excluding test surfaces moved
every affected score by 1 and turned a comfortable catch into a boundary case; a scoring
change shipped without re-pairing against the receipts is a threshold fitted to nothing.

## Usage

```
python scripts/enforcement/check_ticket_breadth.py --plan-dir docs/development/plans/<set>/
python scripts/enforcement/check_ticket_breadth.py --all --table     # calibration sweep
python scripts/enforcement/check_ticket_breadth.py --range A..B      # plan sets in a range
python scripts/enforcement/check_ticket_breadth.py --strict          # exit 1 when flagged
```

The advisory opens **and closes** with the same headline —
`⚠ TICKET BREADTH — N of M ticket(s) graded score ≥ 5 …` — so a `| tail` of a long run still
carries its own denominator. It used to print the count only at the TOP, above the per-ticket
blocks, which put a bound in the output ORDER: a reviewer read "16 of 24" off a tailed run of the
33-ticket multi-agent-per-repo set when the figure was 20 of 33 (intel,
`01M1PYS0Y7AZ9W2WS8PPYHT0WK`). The headline also never named the population at all — only the
flagged count.

Bare (no args) it discovers plan sets changed in the working tree — which is how
`scripts/final_gate.py` runs it, as the Tier-2 advisory check
`Ticket Breadth (advisory, plan sets)`.

## Fleet blast radius

`scripts/enforcement/` is a governance-sync trigger surface: this check distributes to ~46
repos on the next pre-commit sync. It is correct for a project with **no plans at all** —
that is the majority case, and it exits 0 printing nothing.
