# Ledger write integrity — the append writer, id reservation, and the ratcheted gate

**Status:** CONVERGED
**Profile:** delta — every Intake Inventory IN item maps to code that exists today
(`scripts/decisions.py`, `scripts/enforcement/check_decisions_unique.py`); this is a change to an
existing engine, not a new component.

## Personas

Written in full, not collapsed: the delta creates a new automated consumer path (agents invoking a
writer where they previously hand-authored markdown), and the § Behavior rule that "a duty with no
named holder lands on nobody" bites hardest on a shared ledger 49 repos append to.

- **PRIMARY — the agent recording a decision**, in the operator's own words:
  *"you must prevent it happening again"*. Today this persona hand-assembles a six-cell pipe-delimited
  markdown row whose content is prose full of pipes, backticks and code spans, and hand-picks an id
  from `--next-id`.
  **Minimal loop today, counted — this is the frozen STEP BUDGET:**
  1. run `decisions.py --next-id .`
  2. read the ledger to find where newest-first ordering puts the row
  3. compose six cells by hand, escaping nothing
  4. paste the row into `docs/DECISIONS.md`
  5. commit it in the same change
  **5 steps. The delta must not exceed it** — a writer that costs more than hand-pasting will not be
  used, which is this spec's own adoption risk (AF-17, habit: the hand-paste is the incumbent).
- **The agent READING the ledger** — the persona CLAUDE.md serves with *"grep `docs/DECISIONS.md`
  first … the row's what+why+where is the full answer"*. Holds no duty here; is the one harmed when a
  row is malformed, because the tool answers blank and sends them into the wider hunt.
- **The operator** — holds the ruling on id FORMAT (rejected alternative A below) because it is
  governance-visible across 49 ledgers. Holds no duty in the normal path.
- **AUTOMATED — the completion gate** (`check_decisions_unique.py`, run by `final_gate.py`): holds the
  DETECTION duty. It must not hold a blocking duty on day one (79 pre-existing malformed rows).
- **AUTOMATED — `docs_updater.py`** (`:1176`, merge-owner reader): a downstream consumer of the same
  row shape; holds no new duty but constrains the parse (it must keep reading `cells[3]`).
- **Every feature traced:** the writer → primary persona. The reservation → primary persona (the
  collision is theirs). The gate → the automated gate persona. The merge-base read → primary
  persona (it is their id that goes stale on an old branch). The `--renumber` helper a reader might
  expect is traced to NO persona and is therefore NOT built (see Rejected alternatives).

## Goal

Make a malformed or id-colliding ledger row impossible to write through the sanctioned path, and
visible when written through any other, without changing the id format or renumbering any row.

## Why this exists

**The measured pain, re-derived at this revision:** 79 of 953 rows across 49 ledgers (8.3%) are
malformed — 64 carry fewer
cells than the header, 15 more. Their `why` and `where` are unreadable by the tool the contract makes
the FIRST stop for "where is X / did we decide Y". Concentration: fabrik-lib 61, fabrik 6,
iterative_image_editor 5, web-ecommerce-factory 5, trade-intelligence 2.

**And the id race:** `--next-id` reads the maximum and returns max+1 without reserving it. Two
incidents in iterative_image_editor alone (2026-09-03, three agents, two minted D-006; 2026-09-15,
lanes A and C both minted D-037/D-038), plus the hub's own, recorded in `decisions.py`'s comment
(*"two D-041s, 2026-08-30"*) and CLAUDE.md (*"two collisions here in one day, 2026-09-03"*).

**The root cause is one thing:** there is no write path. `decisions.py` exposes `--check`,
`--merge-owner`, `--next-id`, `--root` — every row in all 49 ledgers was hand-assembled, and every id
hand-picked. The reader was the only thing that could notice a defect, and until `051d0859` it
silently padded instead.

**How the chosen approach resolves exactly that:** the writer removes the hand-assembly (it emits the
row, escaping what must be escaped); the reservation removes the hand-picked id; the gate makes any
row that bypassed both visible. Each closes one half of the same cause.

## What exists today (grounded)

| Fact | Evidence |
|---|---|
| No write path exists | `scripts/decisions.py` — subcommands are exactly `--check`, `--merge-owner`, `--next-id`, `--root` |
| `--next-id` does not reserve | `scripts/decisions.py:204` `_next_id`, an inline `re.findall(r"^\|\s*D-(\d+)\s*\|", text, re.M)` then max+1 |
| The gate checks ids, not shape | `scripts/enforcement/check_decisions_unique.py:96` `main()` — duplicate ids and rows outside the table; no cell-count assertion |
| Nothing requires contiguous ids | no `contiguous`/`sequential` requirement in either script — so reservation holes are legal |
| Cross-session box-local state is proven | 15 distinct session ids already append to `~/.claude/state/command-feedback.jsonl` |
| The flock idiom already ships here | `scripts/command_run.py:161-190` — *"Exclusive flock held across the whole READ-MODIFY-WRITE of a mutating subcommand"* |
| `decisions.py` is hub-only | absent from every list in `scripts/fabrik_synced_manifest.py`; not in the governance-sync trigger regex — one landing site serves all 49 ledgers |
| Row shape is locked | 6 columns `\| id \| when \| who \| what (the decision) \| why \| where \|`; ids `D-NNN`, 3-digit zero-padded, 266 rows on the hub (high-water D-265; the extra row is the `D-000` legend at `docs/DECISIONS.md:229`) |

## The delta

Four additions to `scripts/decisions.py` plus one to the existing gate. No new file, no new
dependency, no format change.

1. **`--append`** — takes the five AUTHORED fields (`when`, `who`, `what`, `why`, `where`); it
   ALLOCATES the id itself and returns it, so no caller hand-picks one. ⚠️ **Allocation and the row
   write happen inside ONE flock critical section** — the same lock `--next-id` takes. Two concurrent
   `--append` calls that each computed `max(ledger ∪ reserved)+1` outside a lock would produce exactly
   the duplicate this spec exists to prevent, through the sanctioned path. It emits the row atop the
   table (newest first), escaping **code-span-aware, exactly as the reader decodes**: outside a code span `\` becomes `\\`
   then `|` becomes `\|`; INSIDE a code span only `|` is escaped and a backslash is left alone,
   because a code span decodes nothing else. An unconditional `\`→`\\` doubles every backslash in the
   rendered ledger (executed on a real wef regex row) and breaks both round-trip halves. The writer also
   refuses a field containing a newline. **Code-span detection is ONE shared helper called by both
   halves** — the CommonMark §6.1 backtick-string rule (a run of N backticks opens a span that only a
   run of exactly N closes; an unclosed run is literal text). Encoder and decoder must agree
   byte-for-byte or `read(append(x)) != x`, so they call the same function rather than each
   implementing the rule. **The contract is a round trip in
   both directions:** `read(append(x)) == x` AND `render(append(x)) == x`, the second checked against
   GitHub's renderer, because a row that round-trips through our own tool while diverging from the
   rendered ledger is the mirror this spec must not create.
   ⚠️ **One consumer reads the ledger BOTTOM-up.** `docs_updater.py::read_merge_owner` takes the LAST
   matching row in FILE order (`docs_updater.py:1190`; its docstring: *"A LATER row always wins"*), and
   the hub ledger is not cleanly newest-first today — its last merge-owner match is D-155 at line 244.
   A MERGE OWNER row written atop the table by `--append` would therefore lose to an older one below
   it, so `--append` is not the path for a merge-owner row until that consumer is reconciled (backlog,
   with the parser mirror named in delta §4).
2. **Reservation, box-local.** `--next-id` gains a reservation write under
   `~/.claude/state/decision-ids/<repo>.jsonl`, taken under the `command_run.py` flock idiom.
   **`<repo>` is `basename(dirname(git rev-parse --path-format=absolute --git-common-dir))`** — never
   `Path(arg).name`, which returns `''` for the contract-mandated `--next-id .` (`CLAUDE.md:124`) and
   would put all 49 repos in one file, and returns `DECISIONS.md` for every repo when a file path is
   passed; `git rev-parse` runs against the `--next-id` argument, never the cwd.
   ⚠️ **The ledger's own path must NOT enter the key — the SEED separates the ledgers instead.**
   Adding it looks right: `/opt/fabrik-lib`, `-account` and `-review` are registered worktrees of one
   repo carrying **three separate ledgers** (237, 1 and 1 rows — executed), so one shared key pushes a
   1-row ledger's next id past D-268. But `/opt/fabrik` has **18 registered worktrees of its own**
   whose `docs/DECISIONS.md` is the SAME ledger at an older commit (`agent-ae398d23a2b677726`: 156
   rows, high-water D-155 — executed), and a path-keyed reservation hands that worktree its own file:
   it then mints **D-156, an id already in use on master**. Both cases present identically — one
   common-dir, the repo-relative path `docs/DECISIONS.md` — so no path-based key separates the first
   while unifying the second. **The key is the common-dir ALONE, and the high-water mark is seeded
   from the LEDGER BEING WRITTEN: `max(that ledger's rows ∪ that key's reservations) + 1`.** A hub
   worktree is then seeded from master's own reservations and cannot re-issue; `-account`'s second row
   gets an id above fabrik-lib's high-water rather than D-002, which is a GAP, and gaps are normal and
   correct (§ External dependencies). 78 worktree-resident `DECISIONS.md` exist across 5 repos today.
   ⚠️ **Allocation is a MONOTONIC HIGH-WATER MARK: `max(ledger ∪ reserved) + 1`, never a first-free
   scan.** A first-free scan backfills gaps — executed, it returns `D-011` in fabrik-lib (31 gaps) and
   `D-003` in web-ecommerce-factory (3) — re-issuing retired numbers so every `supersedes D-011`
   resolves to the wrong row. That is the harm this spec's own source names, and the high-water mark
   is what makes a pruned or unused reservation permanently safe rather than merely tidy.
   ⚠️ **The flock leg fails CLOSED.** On timeout `--next-id` exits non-zero and prints NO id. The
   earlier draft let it fall open to `max+1`; executed, agent B then minted the exact id agent A held
   — a silent collision generator in precisely the two-agent condition the mechanism exists for. A
   refused allocation costs a retry; a colliding one costs the duplicate. (The unwritable-state-dir
   leg DOES fail open: nobody can reserve, so degradation is uniform and no id is stolen.)
3. **`--next-id` reads the MERGE-BASE, not HEAD**, when the repo is a git worktree — so an agent on a
   three-day-old branch picks the id it would get on a fresh branch. Duty holder: the PRIMARY persona
   (it is their id that would otherwise be stale). Note the cited sources' own caveat: a merge-base
   "next free" can shift across rebases, which the high-water mark absorbs.
4. **`_rows` gains code-span awareness (the DECODER half).** Punctuation escapes decode outside a code
   span; inside one only `\|` decodes. This is the correction the external gate forced (§ External
   dependencies) and it changes the reader every ledger query depends on, so it is a delta point
   rather than a footnote. ⚠️ **And it opens a parser MIRROR.** `docs_updater.py` does NOT import
   `decisions.py` (executed: zero import sites) — it reimplements the scan with a plain
   `stripped.strip("|").split("|")` at `docs_updater.py:1190` and its own `MERGE_OWNER_RE` /
   `_DECISION_ROW_ID_RE` at `:938-939`, deliberately (`:936`, *"no import — see the Interfaces
   seam"*). After this change the two disagree on cell boundaries for any row carrying an escaped
   pipe. The mirror is named here; its repair — one shared helper, or the same rule in both — is OUT
   of this delta and routed to the backlog.
5. **The gate gains a row-integrity assertion**, ADVISORY and RATCHETED. A row is MALFORMED when its
   cell count differs from the header **or** its `why`/`where` cell is empty — content, not shape
   alone, because padding a short row to six empty cells is cheaper than repairing it and produces
   exactly the blank the reader cannot use. The baseline in `.fabrik/decision-shape-baseline.json`
   records **the set of malformed row IDs**, not a count: every id in the baseline must appear in the
   after-state with a non-empty `why` and `where`, so the set may only shrink by REPAIR. An aggregate
   count cannot express that and is defeated by three separate moves (below). First run seeds the set
   and blocks nothing; empty locks permanently — the `render_doc_script_links.py --coverage`
   mechanism, with identity instead of arithmetic.
   ⚠️ **`check_decisions_unique.py` has been BLOCKING since 2026-09-04** (its own docstring; wired at
   `final_gate.py:1733`), so the ADVISORY leg must never reach its exit code: the row-integrity
   assertion prints a WARN line and contributes nothing to the `return 1 if (dups or stray) else 0` at
   `check_decisions_unique.py:125`. Promotion to blocking follows the same WARN-first sequencing that
   check itself documents for D-057 — re-measured at the moment it would decide something, never
   assumed — and is out of this delta.
   ⚠️ `.fabrik/` is TRACKED, not ignored (74 tracked files; `git check-ignore` rc=1), so the baseline
   is a shared-append file three hub sessions can race on — it is written with the private-index
   recipe like any other, never by a working-file hash.

## Chosen approach

**Box-local reservation + writer + ratcheted gate**, as one mechanism in one file.

The reporter ranked reservation SECOND and discounted it: *"a worktree's reservation still has to
reach the other agent — so this narrows the window without closing it unless the reservation lands on
a shared branch."* That is true of a reservation living in the repo. **It does not live in the repo.**
Every agent that writes one of the **49 `/opt` ledgers** runs on this box, and 15 sessions already
coordinate through `~/.claude/state/`. A reservation there is visible to every worktree and every
repo the instant it is written, with no merge — which converts "narrows the window" into "closes
it". ⚠️ **The claim is box-SCOPED, not universal**: a second workstation runs Claude with its own
`~/.claude/` and its own ledger (`docs/workstation/volkan-mac.md:52`, `~/dev/cryptnshare/`
D-001..D-005). That ledger is out of scope here and the mechanism must never be described as
fleet-universal — `CLAUDE_CONFIG_DIR` does NOT move the state dir (`command_run.py:84-88` derives it
from `Path.home()`; `_CARRIER_ENV_KEYS` carries no `HOME`), and no cron job touches a ledger, so
every writer of the 49 IS on this box — but the boundary is the box, and the spec says so.

## Rejected alternatives

| Option | Why rejected |
|---|---|
| **A — collision-free id format** (`D-041a`, `D-2026.09.15-iie1-1`); the reporter's rank 1 | A governance-visible format change to a file 49 ledgers carry and every CLAUDE.md references by shape, against 266 hub rows alone. The number is load-bearing in supersession pointers. Operator's call, not a spec's — and unnecessary once the race is closed. |
| **B1 — renumber a MERGED row** (the reporter's `--renumber` helper) | Rejected on the cited sources: *"renumbering is the most expensive operation you can do to an ADR directory and it buys nothing… Every link breaks."* Both of their incidents renumbered merged rows, and that is what left lane C's D-035 citing a D-032 that no longer exists. |
| **B2 — bump the UNMERGED row at merge/CI** (detect-at-merge) | **NOT rejected on the sources — they all implement it**, and an earlier draft of this spec wrongly conflated it with B1. `whychose.com/seo/adr-github-action` ships a literal number-collision job; the Binclusive commit's fix was a combined-tree gate, not a reservation. Rejected here on a DIFFERENT and narrower ground: it detects at the merge boundary, and hub agents do not merge through PRs with CI (verified: no `.github/workflows/`, and **all 200 of the last 200 commits direct to `master`** — zero merge commits in that window; the most recent is `5a5184a2`, 2026-07-19, at `rev-list` position 2,930. `git log -200 --merges \| wc -l` reads 6 because `-N` bounds the OUTPUT of the filter, not the window — the eighth shape of `denominator-honesty`); 14 of 45 `/opt` repos DO have PR workflows, which is why B2 stays the right answer there — they commit to one shared `master` on one box, where a reservation acts BEFORE the write instead of after it. B2 remains the correct answer for a PR-based fleet, and the ratchet in delta §5 is its detection half, kept. |
| **C — a reservation row written INTO the ledger** (a placeholder `\| D-042 \| RESERVED \|`) | Leaves a stale placeholder when unused, and is exactly the in-repo reservation whose merge window the reporter correctly criticised. |
| **D — SQLite or a JSONL ledger instead of markdown** | The ledger is read by `grep` by every agent and rendered on GitHub; the contract's first-stop instruction is a grep. Changing the storage format to fix a writer is a far larger blast radius than the defect. (Adjudicated here because "why not db, or jsonl?" is the question a spec must answer before it is asked.) |
| **E — Redis semaphore via fabrik-lib `concurrency-throttle`** | It is a cluster-wide Redis slot semaphore; this is a local-file mutation and Redis is not in every repo's context. The hub's own `flock` idiom fits at the first rung of the ladder. |
| **F — a blocking shape gate on day one** | Fires on 79 of 953 rows (8.3%) across 5 repos immediately — wallpaper by lunchtime, and it would red five repos for pre-existing rows they did not write. Ratchet instead. |
| **G — a monotonic high-water mark with NO reservation file** | The leanest option: one line, no state dir, no flock, no prune. Rejected because it does not close the race at all — two agents reading the same `max` still get the same id; it only removes the gap-backfill hazard, which the chosen approach also removes. Kept as the FALLBACK the fail-open leg degrades to when the state dir is unwritable. |
| **H — a lock file inside the repo's `.fabrik/`** | This is the in-repo reservation whose merge window the reporter correctly criticised, plus a tracked file three sessions race on. Box-local state has neither problem. |
| **I — per-repo vs ONE shared id space across all 49 ledgers** | A single space would make ids globally unique and collision-proof across repos, but every existing citation (`supersedes D-041`) is repo-scoped, and 953 rows would need re-reading against a new namespace. Per-repo, keyed by git common-dir, matches what exists. |
| **J — a collision-only suffix** (`D-041` stays `D-041`; `D-041a` appears only when a collision actually lands) | A strictly narrower form of A whose blast radius is near zero — the format is unchanged for all 953 existing rows. NOT rejected on merit: it is the natural REPAIR when a collision does land despite the reservation, and the spec adopts it as such in place of renumbering. Only the *wholesale* format change (A) is rejected. |

## Lifecycle

- **Adoption / first run.** The writer is opt-in by availability: the contract's § decision ledger
  bullet gains one clause naming `--append` as the way to write a row. The gate's first run seeds the
  baseline and blocks nothing.
- **As it GROWS.** The reservation file is one JSONL line per minted id per repo. At the hub's
  observed rate (266 rows in ~5 months) a repo writes well under 100 lines/year; all 49 together are
  below 5,000 lines/year at ~80 B/line — under 400 KB/year. ⚠️ **Pruning is for SIZE ONLY and never
  frees an id**: under the high-water mark a pruned reservation is permanently burned, so a long run
  cannot have its id re-issued underneath it. An earlier draft pruned at 7 days AND let the id return —
  executed, a reservation held by a still-running session 8 days old was handed to another agent, and
  this session alone has run over 24 h while `~/.claude/state/command-runs/` holds records spanning 25
  days. The box's own staleness precedent is 12 h and it fails OPEN (`.claude/hooks/final_gate_stop.py:493`,
  `_STALE_H_DEFAULT = 12.0`). **Escalation trigger, measured not vibed:** if
  any repo's reservation file exceeds 1 MB (a chosen bound, not an inherited one),
  the prune window is wrong and the mechanism is re-examined — not enlarged.
- **Degradation / failure — the two legs fail in OPPOSITE directions, deliberately.** Unwritable state
  directory ⇒ fails OPEN to alternative G (high-water mark, no reservation) and says so on stderr:
  nobody can reserve, so degradation is uniform and no id is stolen. Flock timeout (5 s PROPOSED — U3, measured at implementation) ⇒ fails
  CLOSED, non-zero, NO id printed: someone else holds the lock, so falling open would mint exactly
  their id. The writer likewise refuses rather than emit a malformed row. The rule is one sentence: a
  refused allocation costs a retry, a colliding one costs the duplicate this spec exists to prevent.
- **Supersession / retirement.** If option A (a collision-free id format) is ever ruled, the
  reservation becomes unnecessary and is deleted; the writer and gate survive unchanged, because
  neither depends on ids being sequential.

## External dependencies

| Fact | Source | Fetched |
|---|---|---|
| In a GFM table cell, **plain text decodes every ASCII-punctuation backslash escape** (ordinary CommonMark inline rules); **inside a code span nothing decodes EXCEPT `\|`**, which the table extension decodes specially so a pipe can appear in code. Verified against GitHub's own renderer (`POST api.github.com/markdown`, `mode=gfm`): `plain: a\_b and cost \$5` renders `a_b … $5`, while `` code: `a\_b` and `C:\\srv` `` renders `a\_b` and `C:\\srv` unchanged | `https://github.github.com/gfm/` §4.10 + §6.1; `https://docs.rs/markdown/latest/src/markdown/construct/gfm_table.rs.html` 86-93, 132-133; GitHub renderer API | 2026-09-16 |
| Sequential-id practice: **allocate against the merge-base, not HEAD**; **gaps are normal and correct**; **never renumber** — the number is part of the supersession pointer and renumbering breaks every link | `https://whychose.com/seo/adr-numbering-scheme`; `https://whychose.com/seo/adr-github-action` | 2026-09-16 |
| A real-world combined-tree duplicate gate for exactly this failure | `https://github.com/Binclusive/a11y/commit/9be9d7b5886984739ecf8df4e55eb4f7f4742dc0` | 2026-09-16 |

⚠️ **This gate found a live defect in shipped code — and corrected the first diagnosis of it.**
`scripts/decisions.py`'s `_ESCAPABLE` consumes all 32 ASCII punctuation marks everywhere. Measured
over 49 ledgers: of the 15 non-pipe punctuation escapes, **12 sit inside code spans (over-consumed —
the real defect) and 3 sit in plain text (correctly consumed)**. An earlier draft of this spec
prescribed narrowing `_ESCAPABLE` to the pipe alone; that would have FIXED the 12 and BROKEN the 3,
making the tool disagree with the rendered ledger — the very harm § Why this exists cites. The
implementation therefore gains **code-span awareness**: punctuation escapes decode outside a code
span, only `\|` decodes inside one.

## fabrik-lib verdict table

| Capability | Verdict | Module / why |
|---|---|---|
| Cross-process mutual exclusion on a local file | **build (reuse the in-repo idiom)** | No fabrik-lib module fits. `concurrency-throttle` is a cluster-wide Redis slot semaphore — wrong tool, wrong dependency. `scripts/command_run.py:161-190` already implements the exact flock READ-MODIFY-WRITE this needs, against a file 15 sessions share. |
| Markdown table row emission | **build** | No module; ~35 lines once the code-span-aware escaping above is included. |
| Id allocation | **build** | No module. |

## Shape / infra implications

**The two halves differ and an earlier draft said 'None' for both.** `decisions.py` is hub-only
(absent from `fabrik_synced_manifest.py`, not in the trigger regex), so the writer and reservation land
once and serve all 49 ledgers — the contract already has every agent invoke it by absolute path. **The
GATE half is fleet-synced**: `check_decisions_unique.py` sits under `ENFORCEMENT_DIR =
"scripts/enforcement"`, matched by `^scripts/enforcement/` in the governance-sync trigger, so delta §5
distributes to ~46 repos on the post-commit hook AND seeds a new TRACKED
`.fabrik/decision-shape-baseline.json` in each. No `shape:` flag, no env var, no dependency.

## Documentation landing sites

| What | Where | Why |
|---|---|---|
| The writer's interface + the escaping rule | `docs/reference/decision-ledger.md` (exists; `decisions.py`'s `# AFTER-EDIT:` header already couples it) | the subsystem's own reference doc |
| The one-clause instruction to use `--append` | `CLAUDE.md` § Behavior decision-ledger bullet + `templates/governance/CLAUDE.md` twin | it teaches the ACT; splitting it from the read is the two-sources-of-truth defect |
| The ratchet baseline's meaning | `docs/workflows/FINAL_GATE_WORKFLOW.md` | where every other gate check is documented |
| The decision itself | `docs/DECISIONS.md` — written with `--append`, as its own first customer | dogfooding is the adoption proof |
| CHANGELOG + INDEX rows | `CHANGELOG.md`, `INDEX.md` | Doc Sync Matrix |

## Constraints (digest — every row verbatim, with `file:line`)

| # | Rule | Verbatim | Source |
|---|---|---|---|
| C1 | Durable state is not temp | *"Anything that must SURVIVE a restart is not temp: it goes on a **named volume** … never in `.tmp` and never in `/tmp`."* | `core/10-python.md:152-153` |
| C2 | UTC only | *"**`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive"* | `core/10-python.md:219` |
| C3 | Behaviour contract | *"every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**"* | `core/45-testing-strategy.md:19` |
| C4 | Watched-fail-first | *"a non-trivial behavior's test proves something only if it has been SEEN RED … A green test never seen red is unverified"* | `core/45-testing-strategy.md:21` |
| C5 | Some domains need exhaustive permutation, not one test each | *"exhaustive permutation testing is required"* — the named list (`:40` is its payments bullet, *"test edge cases, race conditions, idempotent retries"*); this spec's id race is adopted into that standard by analogy, not as a listed row | `core/45-testing-strategy.md:38,:40` |
| C6 | Rows immutable | *"rows immutable; a changed decision is a NEW row `supersedes D-NNN`"* | `CLAUDE.md:122-123` |
| C7 | Cross-repo is a HARD STOP | *"create/edit/**commit** files in a repo OTHER than the one you were launched in … HALT"* | `CLAUDE.md:260` |
| C8 | Cobra in the same change | *"the cheapest way to satisfy it without producing the outcome is written down IN THE SAME CHANGE"* | `CLAUDE.md:222-223` |

C1 is why the reservation lives in `~/.claude/state/`, not `/tmp`. C7 is why this spec repairs the
hub's 6 malformed rows only and routes the other 73 by mail. C8 is answered under Validation.

## Contract deltas

No `docs/data-contract.md` or `docs/ui-design.md` exists for the hub; no version bump applies. The
governance contract gains one clause in both `CLAUDE.md` twins (byte-identical), which is a
fleet-synced change distributed by the post-commit governance sync.

## Cost

- **Code:** ~125 lines in `scripts/decisions.py` (writer ~35 incl. code-span-aware escaping, the
  `_rows` decoder ~15, reservation ~35, merge-base ~20, `<repo>` key ~20), ~25 in
  `check_decisions_unique.py`, plus graders. That fits the `Profile: small` ceiling the implementation
  PLAN will carry (D-169); this spec's own `Profile: delta` describes the SPEC, not the plan.
- **Governance weight:** one clause in each CLAUDE.md twin — the surface that grew 4,649 B across TWO commits today (`3b1f8f23` +4,091 and `7e24fa0c` +558), so
  the clause is one sentence and cites the tool rather than restating its interface.
- **Runtime:** one flock + one small JSONL read per `--next-id`; `command_run.py` pays the same on
  every close.
- **Fleet cost, which an earlier draft missed:** the GATE half syncs to ~46 repos and seeds a tracked
  baseline file in each; the writer and reservation do not (hub-only).
- **Not paid:** no new dependency, no Redis, no format change, no renumbering.

## Validation

Every behaviour gets one grader, each proven red-on-revert per C4; the race domain (C5) gets
permutation coverage rather than one case.

| # | Behaviour | How it is proven |
|---|---|---|
| V1 | `--append` emits a six-cell row for content containing `\|`, backticks and a code span | round-trip: append, then `_rows` + `_six` return the six fields byte-identical |
| V2 | Escaping is CODE-SPAN-CONDITIONAL, both directions | outside a code span `\_` decodes (GitHub renders `a_b`); inside one it does not (`` `a\_b` `` stays); and the writer never doubles a backslash inside a code span |
| V3 | `--append` refuses a newline in a field | non-zero exit, nothing written |
| V4 | Two concurrent `--next-id` calls never return the same id | N parallel processes; assert the returned set has no duplicate — the C5 permutation case |
| V5 | A reservation is VISIBLE across worktrees of one repo | reserve in worktree A's cwd; assert worktree B's `--next-id` skips it, and that two different repos (different common-dirs) never share a file — the case a path-keyed file defeats, where a hub worktree stopping at D-155 would mint the live D-156 |
| V15 | The high-water seed is the LEDGER BEING WRITTEN | in a hub worktree whose ledger stops at D-155, assert `--next-id` returns above master's high-water; in `/opt/fabrik-lib-account` (1 row, same common-dir as fabrik-lib) assert it returns above fabrik-lib's, never D-002 |
| V6 | A pruned reservation's id is NEVER re-issued | prune an 8-day-old unconsumed reservation, then assert `--next-id` returns a value strictly greater than it — the hole is permanent, which is what makes pruning safe |
| V7 | State dir unwritable ⇒ behaves exactly as today | chmod the dir; assert max+1 and a stderr line, exit 0 |
| V8 | `--next-id` reads the merge-base in a worktree | fixture repo with a branch behind master |
| V9 | The gate ratchets a SET of ids, not a count | a repaired row leaves the set; a DELETED one is refused; a row padded to six empty cells is refused |
| V10 | The gate is advisory on day one | on a fixture seeded with pre-existing malformed rows, `final_gate.py` stays green — 79 is the FLEET total; a hub gate run faces 6 of them and wef's faces 5 |
| V11 | The flock leg fails CLOSED | hold the lock in another process; assert `--next-id` exits non-zero and prints NO id — the leg whose earlier fail-open minted the held id |
| V12 | `--append` allocates and writes under ONE lock | N concurrent `--append` calls; assert no duplicate id lands in the ledger |
| V13 | `render(append(x)) == x` | round-trip a regex field carrying backslashes through GitHub's renderer, not only through `_rows` — the half that catches an over-escaping writer |
| V14 | `_rows` decodes code-span-aware | on a FIXTURE ledger, never the live fleet (whose 12-in-code-span / 3-plain split today moves with every appended row): each in-code-span sequence keeps its backslash, each plain-text one decodes |

**Cobra (C8), written here because the mechanism's docstring will carry it too.** An aggregate
malformed COUNT is defeated by three moves, and the cheapest is not the obvious one — all three were
built and executed against a baseline of malformed=1 / total=4:

| move | against a COUNT ratchet | against the SET ratchet shipped |
|---|---|---|
| delete the malformed row | refused (total also fell) | refused — the id is absent, not repaired |
| delete it AND add one well-formed row (i.e. record any decision) | **PASSES** | refused |
| **pad the row to six empty cells** — cheapest: an edit, no deletion, total never moves | **PASSES** | refused — `why`/`where` are empty |
| repair it properly (the wanted outcome) | passes | passes |

The padding move is the cheapest satisfying move and is therefore the one FIX DIRECTIVE 5 requires be
written down; an earlier draft wrote down the second-cheapest. The per-row-identity set is the
counter-measure, and it is why the baseline stores ids rather than a number.

## Pass Ledger

Closed on the **D-252 scope-growth stop**, not on a quiet round — stated plainly because the
distinction is the whole point of that stop.

| Pass | md5 in | Findings | CONFIRMED | Of which inside the PREVIOUS pass's own fix |
|---|---|---|---|---|
| 1 | `faec2083…` | 14 | 14 | — (first pass) |
| 2 | `cf706490…` | 17 | 13 | 5 |
| 3 | `10e7cbba…` | 17 | 7 | **7 of 7** |

Pass 3's seat was fresh and non-authoring, and every finding it CONFIRMED lay inside pass 2's own
patch — the D-252 condition. One of the seven (the `<repo>` key) was a live behaviour defect rather
than residue, so it was corrected here together with the six textual ones and the ten RECORDED items;
the loop then ENDS rather than taking a fourth review round. Two residues are carried into the spec
itself as named backlog work (the `docs_updater.py` parser mirror in delta §4) and as U4, rather than
patched. The honest disposition: this artifact's final edit pass was not itself reviewed by a fresh
seat, and the implementation plan's own review is where that is caught.

## Decisions taken

To be minted at the implementing commit with `decisions.py --append`, as the mechanism's own first
customer: the choice of box-local
reservation over id-format change and over renumbering, with the reporter's ranking and the reason
each rejection rests on. It supersedes nothing.

## Open / blocking unknowns

| # | Unknown | Resolution step |
|---|---|---|
| U1 | Whether the operator wants id format A ruled instead — it is theirs, and it would retire the reservation | Named in the approval dialogue; the spec is written so A remains possible later without rework |
| U2 | Whether fabrik-lib (61 of 79 malformed rows) wants the repair done by their agent or a hub-generated patch they apply | Mail, after approval — C7 forbids me editing their tree |
| U3 | Exact flock timeout (5 s proposed) | Measured at implementation against `command_run.py`'s observed hold times |
| U4 | WHO seeds `.fabrik/decision-shape-baseline.json` in the ~46 synced repos, and what `final_gate.py --check` (documented *"no fixes, no sync"*) does when the baseline is ABSENT — a check that seeds nothing under `--check` leaves every `--check`-only repo permanently unseeded | Read `final_gate.py`'s `--check` path and `render_doc_script_links.py:104`'s `_GATE_MODE` precedent at implementation; the duty holder is named in delta §5 before the sync runs |

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"the writer + --next-id reservation + the ratcheted check, as one item"* | IN | The delta (all five points) |
| I2 | *"you must prevent it happening again"* | IN | Chosen approach; Validation V4/V5 |
| I3 | *"should all agents or you fix this"* | OUT-OF-SCOPE | Operations, not mechanism: hub's 6 rows are mine, the other 73 route by mail (U2) |
| I4 | `decisions.py:94` pads a short row | OUT-OF-SCOPE | Shipped at `051d0859` |
| I5 | `decisions.py:83` naive split | OUT-OF-SCOPE | Shipped at `051d0859` |
| I6 | *"returns max+1 without reserving it"* | IN | The delta §2 |
| I7 | *"the window is not seconds: it is until MERGE"* | IN | Chosen approach — box-local, so no merge is involved |
| I8 | *"rows are IMMUTABLE, so a citation … cannot be corrected"* | IN | Rejected alternative B |
| I9 | *"No gate catches it: the duplicate check is within-file"* | IN | The delta §5 |
| I10 | The reporter's three ranked directions | IN | Rejected alternatives A/B, Chosen approach |
| I11 | 79 malformed of 953 across 49 ledgers (re-derived; the total moves daily) | IN (as the ratchet baseline) | The delta §5; Why this exists |
| I12 | No write path exists | IN | Why this exists — the root cause |
| I13 | Gate checks ids, not cell count | IN | The delta §5 |
| I14 | Reconstruction residue (4 sub-items) | OUT-OF-SCOPE | `docs/STRATEGIC_BACKLOG.md` row filed 2026-09-16 |
| I15 | *"RELATED, SAME SWEEP, ALSO YOURS: `check_governance_tables.py:19-23` scopes itself to governance contracts … `docs/DECISIONS.md` and `INDEX.md` … have no cell-width check at all"* (+ the `INDEX.md` `-` bullet dropping 13 rows) | OUT-OF-SCOPE | A different checker with a deliberate wallpaper trade-off in its own docstring; this spec's gate covers `DECISIONS.md` only. `docs/STRATEGIC_BACKLOG.md` row written 2026-09-16 |

**Intake: 15 items — 10 IN, 5 OUT-OF-SCOPE (each named above), 0 ASK.**
