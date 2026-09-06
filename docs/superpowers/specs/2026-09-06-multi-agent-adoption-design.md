# Multi-agent adoption for existing projects — the merge owner and work-item ownership

Status: CONVERGED (2026-09-06 — 4 passes: r1 5 findings (pool ×3 + own), r2 5 (own closing read + 2 pool wording rows), r3 2 (own), r4 edit-free)
Profile: delta
Owner: infra
Date: 2026-09-06

**Profile verdict:** every Intake Inventory item below maps to code that exists today — `scripts/docs_updater.py`
(the `Owner:` parser + the `AUTO-GENERATED:PLANS` block), `scripts/epic_order.py` (`--assign`), the two
session-start hooks, `commands/_sources/fabrik-vision.md`, and the synced `docs/DECISIONS.md` ledger — so the
delta profile holds (D-153 trigger). No new component; three engines and one command gain a small delta each.

## In one line

One declared merge owner per repo, ownership carried by work items (plans, epics, backlog rows) and never by code
areas, an adoption step that stamps what exists today, and two advisories that fire only where more than one
session shares a checkout.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "existing agents must assign one agent as master" | IN | § The delta D1 (the merge-owner row) |
| I2 | "with other agents they must share the repo responsibility already built and will be build according to plans.md strategic_backlog.md and epic files" | IN — CHANGED by the operator-accepted correction: responsibility follows WORK ITEMS, never code areas | § Decisions taken (D-154), § The delta D2 |
| I3 | "do you agree with me? if so, how can we make sure of this? or what do you suggest" | IN | § The delta D2–D5 (the mechanism), § Validation |
| I4 | "i want all agents in the projects be aware of the new way of working" | OUT-OF-SCOPE — already delivered this session: the synced contract § Orient (d) + 46 of 46 relay notices (ids in the session scratch `broadcast_ids.txt`, first `01M1V54XQ8R1A24ZXAQH3PPPH6`) | none further — the adoption step (D2) is what those agents run next |
| I5 | "you had said this now run the commands and see if we need to modify them more or not" | IN | § Machinery report (this run's numbers) — carried to the review's close |
| I6 | gap (1) no surface declares the merge owner without epics — `fabrik-epics-review.md:459` "agent-1 = the first name" of the epics' owner set | IN | § What exists today, § The delta D1 |
| I7 | gap (2) the ownership sweep is a described duty with no mechanism — `docs_updater.py:834` `NO_OWNER = "—"  # … the tail sweep … fills it`; 0 hits for "tail sweep" in `commands/_sources/` | IN | § The delta D2 |
| I8 | gap (3) `/fabrik-vision` EXISTING mode reads neither PLANS.md nor STRATEGIC_BACKLOG.md (0 hits in `fabrik-vision.md`) | IN | § The delta D4 |
| I9 | gap (4) two sessions in one main checkout is undetected | IN — measured: 8 checkouts with 2–3 live sessions each (6 synced project repos + the hub + fabrik-lib), all in the main checkout, none named | § What exists today, § The delta D5 |
| I10 | proposal (c) "a gate WARN … when the repo has linked worktrees" | IN — CHANGED: the worktree trigger is WRONG (measured: 83 linked worktrees in 4 repos, 28 of 29 in seo are `worktree-agent-<hex>` subagent residue); the trigger is live sessions per checkout | § The delta D3, § Rejected alternatives |
| I11 | constraint "single-window repos must see NOTHING new" | IN | § The delta D3/D5 (fire only at ≥2 sessions), D2 (`--adopt` refuses at one session without `--single-window`), § Validation V4 |
| I12 | constraint "the hub itself is excluded from the worktree model" | IN | § The delta D5 (hub identity → advisory suppressed) |
| I13 | constraint "no new command unless the design proves one is needed" | IN — no new command; one script flag + three text deltas | § Chosen approach |
| I14 | "fabrik-lib vendor check per the ladder" | IN | § fabrik-lib verdict |
| I15 | gap (0), found while grounding I7: the `AUTO-GENERATED:PLANS` block exists in 0 of 41 project repos (35 have PLANS.md, none carry the markers; `docs_updater.py:1055` skips a marker-less file) — the ownership surface is dead fleet-wide today | IN | § What exists today, § The delta D2 (the adoption step seeds the markers) |

Intake: 15 items — 14 IN, 1 OUT-OF-SCOPE (I4, named above), 0 ASK.

## Personas

Written in full because the delta introduces a new duty holder and a new automated consumer.

- **The operator** (primary, in their own words: *"existing agents must assign one agent as master"*) — opens the
  windows, reads PLANS.md and the backlog to see who owns what, never fills a column by hand.
- **The merge owner (agent-1)** — the ONLY writer of the base branch; runs the adoption step once; fills untagged
  rows at the tail of every plan; merges branches in phase order. New duty introduced here: the adoption step.
- **Agents 2..N** — read their name in PLANS.md / the epic frontmatter / a backlog tag and work only that item;
  they never run the adoption step.
- **`docs_updater.py --sync/--check`** (automated) — regenerates and validates the PLANS block; gains the
  merge-owner header line and the advisory.
- **`session_orient.py`** (automated, SessionStart) — gains the "N sessions in this checkout" advisory.
- **The governance sync + scaffolder** (automated) — distribute the changed RUN_SCRIPT and hook; the scaffolder seeds
  the PLANS markers so a new repo is born with the surface.

Minimal loop of the primary persona, counted (the frozen STEP BUDGET = 4): (1) open agent-1's window in the main
checkout with `CLAUDE_AGENT=<name>`; (2) say "adopt"; agent-1 runs the adoption step and reports the table; (3) open
agents 2..N per the printed lines; (4) read PLANS.md when asking "who owns what". Four steps; a fifth is a bump.

## Goal

An existing repo with several windows gets, in one turn, a declared merge owner and an owner on every open work
item — and stays that way, because the surfaces that show ownership are regenerated and checked, not hand-kept.

## Why this exists

The operating model shipped ownership for EPIC-BORN work only (`owner:` set by `/fabrik-epics-review`). Existing
repos have no epics, and the measurement this run made is the pain: 21 live sessions on the box, 8 checkouts with 2–3
sessions each (6 of them synced project repos), all in the main checkout, none named — the shared-index way that lost work three times in one day
(D-099 § Why this exists) continues silently in every one of them. And the one surface built to show ownership,
the PLANS block, is present in 0 of 41 project repos because nothing seeds its markers. The chosen delta resolves
exactly this: a declaration that exists without epics, an adoption step that populates the surface, and an
advisory that names the shared-checkout situation the moment it happens.

## What exists today (grounded)

- `scripts/docs_updater.py:832-853` — `_OWNER_LINE_RE`, `NO_OWNER = "—"`, `parse_plan_owner()` (first `Owner:`
  line wins, leading name token only). `:962-1013` `_epic_rows()` reads epic frontmatter `owner`. `:1015-1043`
  `generate_plans_table()` emits `| Epic/Plan | Owner | Status | Phase |`. `:1046-1063` `sync_plans_index()` —
  **opt-in by markers; a marker-less file is skipped**. `:1066-1080` `validate_plans_indexed()` — `--check` finding
  only when the block is stale; missing markers = opted out.
- `src/fabrik/scaffold.py:1436-1452` writes PLANS.md inline with a hand table (`| Plan | Date | Status |`) and **no
  markers** — the reason 0 of 41 projects carry the block.
- `scripts/epic_order.py` — `--assign a,b,c` round-robins `owner:` into epic frontmatter; `--check --owners`
  proves one owner ∈ the set (`:8-10`). Only epics; plans and backlog rows are outside it.
- `commands/_sources/fabrik-epics-review.md:459-466` — agent-1 = the first name of the epics' `owner:` set; the
  only place the merge owner is derived. `fabrik-plan-after-chat.md:637-642` — `**Owner:** <$CLAUDE_AGENT>`,
  `—` when unset.
- `commands/_sources/fabrik-vision.md:17,63` — EXISTING mode reads `project.yaml`, specs, compose, the live
  layout; **not** `docs/development/PLANS.md`, **not** `docs/STRATEGIC_BACKLOG.md` (0 hits).
- `docs/STRATEGIC_BACKLOG.md` in 23 of 41 repos: 619 table rows (`| Effort | Item | Why | Ready when |` — transdoc,
  seo, youtube) + 764 bullet rows; **6** table rows carry a `[name]` tag (re-counted r1 — an earlier pipeline count of
  130 had swallowed `[x]` checkboxes). The tag grammar in use is the HUB's: a legend table `| Tag | Agent | Beat |`
  (`docs/STRATEGIC_BACKLOG.md:19-24`, tags `` `[infra]` `` / `` `[fleet]` `` / `` `[intel]` `` / `` `[operator]` ``), a
  dedicated `Tag` column on table rows, and `**[infra]**` as the leading token of bullet rows.
- `.claude/hooks/session_orient.py` (SessionStart, synced via `AGENT_HOOK_FILES`) prints the ORIENT block; it
  reads `CLAUDE_AGENT` for the "UNNAMED" warning already. No hook counts sessions.
- Live sessions are enumerable box-side with no registry: `readlink /proc/<pid>/cwd` over `pgrep -x claude`
  (measured this run; the kernel's `/proc` doc and `fuser(1)` are the cited ground, § Chosen approach).
- `docs/DECISIONS.md` exists in 41 of 41 git repos (seeded by the sync's SEED_IF_MISSING pair).

## The delta

**D1 — the merge owner is ONE ledger row per repo, printed by the PLANS block header.** Row text is fixed by
grammar so a script can read it: `MERGE OWNER: <name>` as the first words of the `what` cell after leading `*` are stripped (58 of the hub's
155 rows open their `what` with `**`; `decisions.py:82` splits cells on `|`, so the row escapes any pipe as `\|`
like every other row — the D-099 lesson) (`decisions.py` gains a `--merge-owner` read: the LAST row whose stripped
`what` starts with that literal, case-insensitive, wins, so a change is a new row that
supersedes, never an edit — the ledger's own law). `generate_plans_table()` prints a second header comment
`<!-- Merge owner: <name> | source: D-NNN -->` (or `<!-- Merge owner: UNDECLARED — run docs_updater.py --adopt
<name> -->`). No new file, no new field on plans; the ledger every agent already queries first is the declaration.

**D2 — the adoption step: `python scripts/docs_updater.py --adopt <name>[,<name>…]`.** Runs in the main checkout
by agent-1, idempotent, and does exactly four edits (plus the epic half it delegates, below): (a) seeds the `AUTO-GENERATED:PLANS` markers into PLANS.md
when absent (below the existing hand table, which is left as history), then regenerates the block; (b) stamps
`**Owner:** <name>` on every plan unit whose Owner is `—` and whose Status is not terminal, round-robin over the
names given (the first name = the merge owner, mirror of `epic_order.py --assign`); (c) tags every untagged
STRATEGIC_BACKLOG row, round-robin, in the row's own shape: a TABLE row whose header has a `Tag` column (the hub's
`| Effort | Tag | Item | … |`) gets `` `[<name>]` `` in that cell; a table row without one (the projects' `| Effort |
Item | Why | Ready when |`) gets `[<name>] ` prefixed to the Item cell; a BULLET row (`- `, `- [ ] `, `- [x] `) gets
`[<name>] ` after the list marker and any checkbox — skipping rows that already carry a `[tag]` and the legend table
itself; (d) appends the `MERGE OWNER: <first name>` row with the next id from `decisions.py --next-id`
when no such row exists. It prints the same table the operator asked for: `| Item | Owner | Source |` for every
row it touched. `--adopt` is an EXPLICIT act on the operator's word (I11 binds the passive surfaces — `--check`,
SessionStart — which stay silent in a single-session repo; the flag refuses with one line when it counts one live
session and no `--single-window` override, so an over-eager agent cannot adopt a repo nobody shares). Re-running with the same names changes nothing; with a different first name it appends a
superseding row. `epic_order.py --assign` stays the epic half — `--adopt` calls it when an epics dir exists.
The scaffolder's inline PLANS.md gains the markers (`scaffold.py:1436`) so new repos never need (a).

**D3 — the advisory in `docs_updater.py --check`: fires ONLY when ≥2 live sessions share this checkout.** The
check counts `claude` processes whose `/proc/<pid>/cwd` equals the repo root; when the count is ≥2 AND (the merge
owner is undeclared OR any open plan row is `—` OR any backlog row is untagged) it emits ONE advisory line naming
the count and the `--adopt` command. A single-session repo emits nothing — the constraint I11, and the measured
fire rate: 8 shared checkouts on the box today, of which 6 are synced project repos (the other two are the hub and
fabrik-lib, both outside the model) — every one legitimately. The gate already runs `docs_updater.py --check` as an optional
tier-3 check (`final_gate.py:1884`), so no new check file and no new gate row.

**D4 — `/fabrik-vision` EXISTING mode reads the two work stores.** Phase 0's live-project read list gains
`docs/development/PLANS.md` (open rows: Status not terminal) and `docs/STRATEGIC_BACKLOG.md`; each open plan and
each backlog row becomes a candidate line in the Scale Assessment / epic seeds, carried with its owner tag so an
epic cut from a `[beta]` backlog row inherits `owner: beta`. Text delta only, ~12 lines in the source.

**D5 — the session-start advisory.** `session_orient.py` counts sibling `claude` processes with the same cwd at
SessionStart; at ≥2 it prints one line: `⚠️ N sessions share this main checkout — the multi-agent model puts
agents 2..N in worktrees: CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo> (docs: /opt/fabrik/docs/
reference/multi-agent-operating-model.md)`. Suppressed when the repo is the hub (`session_orient.py:139` already computes `is_hub` from
`scripts/fabrik_synced_manifest.py`, I12) and when the session's own cwd is under `/.claude/worktrees/` (a worktree
session is detectable ONLY from its cwd — `CLAUDE_CODE_MESSAGING_SOCKET` is a temp-file path that names nothing,
review r1). One line, no block, no prompt.

**What does not change:** the epic path (`/fabrik-epics-review` still derives agent-1 as the first owner — D1's
row is written by it too, so both paths converge on one declaration); plan-locks; the merge protocol; the tail.

## Chosen approach (and why it is the lean one)

Declare ownership in the ledger and regenerate the surfaces from it, rather than maintain a map. Grounded:

- Pro Git, *Distributed Workflows* § Integration-Manager Workflow — https://git-scm.com/book/en/v2/Distributed-Git-Distributed-Workflows
  (fetched 2026-09-06, HTTP 200, quote matched on the raw page): *"This scenario often includes a canonical
  repository that represents the 'official' project."* — one integrator, everyone else pushes branches; D1 names
  that integrator, D2's first name is that role.
- GitHub *About code owners* — https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
  (fetched 2026-09-06, HTTP 200, quote matched): *"A CODEOWNERS file uses a pattern that follows most of the same
  rules used in gitignore files"* and *"the last matching pattern takes the most precedence"* — ownership BY PATH,
  precedence by order: the exact map shape the operator's correction rejects; cited as the rejected field default.
- git `git-worktree` documentation (raw) — https://raw.githubusercontent.com/git/git/master/Documentation/git-worktree.adoc
  (fetched 2026-09-06, HTTP 200, quote matched): *"The porcelain format has a line per attribute … an empty line
  indicates the end of the record"* — what D3 does NOT use as its trigger, because the worktree list carries
  subagent residue (I10).
- `fuser(1)` — https://man7.org/linux/man-pages/man1/fuser.1.html (fetched 2026-09-06, HTTP 200, quote matched):
  *"fuser displays the PIDs of processes using the specified files or file systems … c current directory"* — the
  cwd-of-a-process signal D3/D5 read directly from `/proc/<pid>/cwd` (same fact, no new dependency).

Four distinct URLs, two tools (pool grounders searching through exa/brave, then the orchestrator's `curl` status
probe + raw-page grep), one real search leg. The operator's rulings (one master; work-item ownership) are grounded
by D-154, not by literature — per D-153.

## Rejected alternatives

- **A static code-area map (`alpha: api/, beta: workers/`)** — decays within weeks (the CODEOWNERS shape above is
  the field's version of it) and fights every plan that cuts across the tree. Rejected by the operator's correction, D-154.
- **A CODEOWNERS file** — path-based, GitHub-side, not read by any agent here; the ledger row is one line and
  already queried first by every agent.
- **A new `/fabrik-adopt` command** — the step is four idempotent file edits; a script flag under the existing
  RUN_SCRIPT ships fleet-wide by the sync with no corpus render, no new run-record shape.
- **"Repo has linked worktrees" as the advisory trigger** — measured false: 28 of 29 seo worktrees are subagent
  isolation residue; would fire on single-session repos that ran a review yesterday.
- **A new field `Merge-owner:` in PLANS.md or project.yaml** — a second source of truth beside the ledger; the
  ledger row plus a generated header line keeps one.
- **Blocking on undeclared ownership** — a block on 6 synced repos today, all mid-work; advisory first, fire rate
  re-measured after a week (D-034 model: measured before anything blocks).

## Contract deltas

- `scripts/docs_updater.py` (RUN_SCRIPT, fleet-synced): new flag `--adopt <names>`; `--check` gains the D3 advisory;
  `generate_plans_table()` gains the merge-owner header comment. The PLANS block bumps to `v2` (the header comment
  is part of the block body, so `--check` sees a v1 block as stale exactly once after the sync).
- `scripts/decisions.py`: `--merge-owner` read (last row whose `what` starts with `MERGE OWNER:`).
- `.claude/hooks/session_orient.py` (AGENT_HOOK_FILES, synced): the D5 line.
- `src/fabrik/scaffold.py:1436`: PLANS.md seeded WITH the markers.
- `commands/_sources/fabrik-vision.md`: D4 read list + seeds (rendered box-wide).
- `commands/_sources/fabrik-epics-review.md`: Step 1.5 also writes the D1 row when absent (one sentence).
- Docs: `docs/reference/multi-agent-operating-model.md` § Ownership surfaces (the adoption step, the row grammar),
  `docs/workstation/hooks-index.md` (the D5 line), CHANGELOG, this spec's D-row. No data-contract, no UI.

## Cost

Zero tokens: every delta is a script or a hook. Runtime: `--adopt` is one pass over plans + backlog (1,383 project backlog rows
fleet-wide today — 619 table + 764 bullet — milliseconds); the session count is one `/proc` scan per SessionStart / per `--check` (21
processes today). Build: ~250 lines of Python across two scripts and one hook, ~30 lines of command text, tests.

## Validation

- V1 `--adopt` on a fixture repo with a marker-less PLANS.md, two `—` plans, three untagged backlog rows and no
  ledger row: after one run — markers present, both plans owned round-robin, three rows tagged, ONE `MERGE OWNER:`
  row; a second run is byte-identical (idempotent). Red-first.
- V1b `--adopt` in a fixture with one injected live session refuses with one line and touches nothing; with
  `--single-window` it proceeds; a bullet-shaped backlog row is tagged after its checkbox, a hub-shaped row in its
  `Tag` cell (parametrized over the three row shapes).
- V2 `--adopt` with a different first name appends a superseding row and rewrites the header comment; the old row
  is untouched (ledger immutability).
- V3 `--check` emits the advisory only when the injected session count is ≥2 AND ownership is incomplete; the
  four other combinations emit nothing (parametrized).
- V4 fire-rate proof over the 45 synced projects before the sync distributes: the advisory would fire in exactly
  the repos with ≥2 live sessions at measurement time (6 of 41 today), never in a single-session repo.
- V5 `session_orient.py` prints the D5 line at ≥2 same-cwd processes, nothing at 1, nothing in the hub.
- V6 the scaffolded PLANS.md carries the markers and `docs_updater.py --sync` regenerates it on a fresh scaffold.
- V7 `/fabrik-vision` EXISTING: a fixture backlog row tagged `[beta]` reaches the epic seeds with `owner: beta`.

## Decisions taken

- **D-154 (this change):** responsibility in a multi-agent repo is split by WORK ITEM — `Owner:` on every plan,
  `owner:` + `owned_paths` on every epic, a `[name]` tag on every backlog row, one migration owner per phase — never
  by code area; one merge owner per repo, declared by a ledger row. Operator's ask + accepted correction, 2026-09-06.
- Inherited: D-099 (the operating model), D-113 (approved), D-117 (locks stay in-repo), D-153 (this spec's profile).

## Lifecycle

Adoption: one `--adopt` per repo by agent-1, on the operator's word per repo (6 synced repos are candidates today).
Growth: rows scale linearly; the advisory's fire rate is re-measured after one week and the block decision is a
new ledger row. Retirement: delete the flag and the two advisories; the ledger rows remain history.

## Constraints digest

| Pack | Row (verbatim) | Applies to |
|---|---|---|
| core/10-python.md:21 | "**`uv`** is the mandated Python package manager. Never use raw `pip`" | no new dependency at all |
| core/10-python.md:219 | "**`datetime.now(UTC)`, never `datetime.utcnow()`**" | the block stamp in `--adopt` |
| core/10-python.md:291 | "**BANNED:** `logging.FileHandler` … any `*.log` file write" | the hook prints to stdout only |
| core/40-documentation.md:458 | "Standalone work (not plan execution) → `Agent-Role: primary`" | every commit of this build |
| core/40-documentation.md:480 | "Every code-shipping ticket must produce exactly one entry" | CHANGELOG per phase |
| core/30-ops.md (FLOOR) | — no row applies: no service, no container, no port | unconstrained |
| core/25-data-postgres.md (FLOOR) | — no row applies: no database | unconstrained |
| core/35-security-auth.md (FLOOR) | "**ZERO secrets/constants in code**" | `/proc` scan reads cwd only, never environ |

## fabrik-lib verdict

| Capability | Verdict | Why |
|---|---|---|
| declare + read the merge owner | BUILD (in `decisions.py`, ~20 lines) | no module covers a decision ledger; Fabrik-specific grammar; not a fabrik-lib candidate (fails (a) generic) |
| stamp owners / tag rows | BUILD (in `docs_updater.py`, ~120 lines) | Fabrik-specific markdown shapes; `file-cache`/`job-queue` locking is data-plane, not tree-plane (D-099's verdict table, unchanged) |
| count sessions per cwd | BUILD (~15 lines, stdlib `/proc`) | nothing to vendor; no dependency |

## Shape / infra implications

None: no scaffold type changes, no `shape:` flag, no deploy. Synced surfaces distribute by the post-commit
governance sync (RUN_SCRIPTS + AGENT_HOOK_FILES); the commands render from the main checkout.

## Documentation landing sites

`docs/reference/multi-agent-operating-model.md` § Ownership surfaces (the adoption step + row grammar, replacing the
"tail sweep" sentence) · `docs/workstation/hooks-index.md` (session_orient's new line) · `templates/governance/
CLAUDE.md` § Orient (d) gains the `--adopt` sentence (synced) · CHANGELOG · D-154 in `docs/DECISIONS.md`.

## Open / blocking unknowns

- **Resolved:** the advisory trigger (worktrees vs sessions) — measured, sessions win.
- **Open (named step):** whether `/proc/<pid>/cwd` is readable for sibling sessions under a different Linux user —
  irrelevant on this single-user box, checked at build by running the count as the same user (V4).
- **Open (named step):** the hub's own three sessions would trip D5 without the hub suppression — V5 proves the
  branch on the hub identity the hook already computes.

## Machinery report (I5 — the first live run of the D-153 changes)

| Measure | This run | brand-identiy-creator 2026-09-05 (the proposal's numbers) |
|---|---|---|
| Brief | ~14 operator lines + my 4 gaps / 5 proposals | 14 lines |
| Grounding wall-clock to Phase 5 | 6 min (11:06→11:12 UTC) | 11m43s to a 471-line draft |
| Pool spend | $0.049 (2 research units) | 13 native dispatches |
| H2 sections at DRAFT | 20 (`grep -c '^## '`): 7 delta sections in full, Personas in full (new duty holder), 12 short mandated sections | 15 |
| Lines at DRAFT | 281 (`wc -l`, this file before the review) | 471 |
| `/fabrik-spec-review` wall-clock | 8 min (11:17→11:25 UTC), 4 passes: 5 → 5 → 2 → 0 findings; pool $0.026 (r1 ×3 finders, one returned empty) + $0.0035 (r2, ran no tools) | ~1h52m, 9 passes, 13 native dispatches |
| Lines at CONVERGED | 297 (+16: three corrected counts, the socket claim, the tag grammar, V1b) | 672 |
| Whole run (spec + review) | 20 min wall-clock, $0.078 pool | 2h47m net |

Friction with the new text: (1) the delta profile still owes `## Personas`, `## Lifecycle` and `## Intake
Inventory` headings for the gate — fine, but the profile text should SAY the three headings are the floor, so an
author does not re-derive it (one sentence, filed at the close if the review agrees); (2) the 1c carve-out worked as
intended — the two rulings cost zero citations; the four URLs ground only the mechanism; (3) the review's ask ↔ spec
table is cheap to produce because the Intake Inventory already carries the operator's words — the two artefacts
share rows, which is the point; (4) the pool's cheapest reader ran no tools in r2 and graded every anchor
'unverifiable' — a reader that cannot read is not a finder; the native closing read caught the three stale counts.
