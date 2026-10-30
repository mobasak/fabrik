# Ledger merge driver — stop hand-resolving CHANGELOG/DECISIONS conflicts

**Status:** DRAFT
**Size:** small (≈90 lines, 3 files)
**Profile:** delta — every Intake Inventory IN item maps to code that exists today (`scripts/merge_request.py`'s ledger resolver, `scripts/install_post_commit_hook.sh`'s merge-driver registration, `.gitattributes`); this registers an existing engine with git, it builds no new component.

Work item: W-53360407 (P0). Recommends a DIFFERENT shape from the one the item and D-1381 Part 4 name (per-entry fragment files). The reason is a measurement D-1381's panel did not have (§ Why this exists). The approval gate decides between the two. § Rejected alternatives carries the fragment design in full, so the gate can pick it without a new spec.

## Personas

- **Builder agents** (infra, infra-N, fleet, intel, kaizen windows, each in `.claude/worktrees/<name>`). PRIMARY. When the merge owner refuses a stale branch they run `git merge master`, and today they resolve ledger conflicts by hand.
- **The operator.** Primary persona's pain in their own words, relayed by the coordinator 2026-10-30: *"fed up with merge issues"*. Reads results through the coordinator only (D-943).
- **The coordinator / merge owner.** Lands branches with `python3 scripts/merge_request.py merge` in throwaway worktrees (`scripts/merge_request.py:1163` `_build`). It already auto-resolves ledger insertions in-process (`scripts/merge_request.py:958-1012`) and keeps doing so.
- **git itself** (automated). Invokes the driver on every file-level merge of a ledger path: `git merge`, `rebase`, `cherry-pick`, `merge-tree`. Never `git merge-file`, which has no driver lookup (grounded below).
- **The installer** (automated). `scripts/install_post_commit_hook.sh` runs from `wsl_startup_hook.sh` on every shell. It owns registering the driver and mirroring the attribute lines into `<common>/info/attributes`.
- **The ~46 fleet repos** (automated consumers of the synced `merge_request.py`). They receive the new verb and never call it: no `.gitattributes` line and no `merge.ledger.driver` config exist there (the installer's `ROOT=/opt/fabrik`).

**Primary loop (step budget).** A builder brings master into a refused branch:
1. `git merge master` — the ledgers resolve inside the merge;
2. `git push`;
3. `python3 scripts/merge_request.py request …` (resend).

**Budget: 3 steps.** Today steps 1a–1d also hold: open CHANGELOG.md and docs/DECISIONS.md at the markers, hand-merge them, `git add` both, `git commit`. That makes 7.

## Goal

A `git merge`, `rebase` or `cherry-pick` in any hub worktree resolves concurrent INSERTIONS into the five ledgers (`CHANGELOG.md`, `docs/DECISIONS.md`, `INDEX.md`, `docs/STRATEGIC_BACKLOG.md`, `docs/LESSONS_LEARNT.md`) with the same resolver the merge owner already trusts. No ledger moves, no reader changes, nothing migrates. An EDIT to an already-landed ledger line still conflicts, by design.

## Why this exists (measured 2026-10-30, executed this session)

1. **Builder-side conflicts are the bulk.** Replaying every two-parent merge of the last 14 days with `git merge-tree --write-tree --name-only` (`replay.py` in the run scratch) printed `merges 785 conflicted 419 ledger-touching 411 ledger-only 400`, per file `367 CHANGELOG.md · 202 docs/DECISIONS.md · 34 docs/LESSONS_LEARNT.md · 6 INDEX.md`. Plain git has no driver for these paths: `.gitattributes` maps only `.fabrik/work/W-*.json merge=workitem` (`.gitattributes:3`). Each of the 400 was a hand resolution.
2. **The existing resolver covers them.** `_merge3` (`scripts/merge_request.py:998`) over the same 400 printed `ledger-only conflicted merges 400 driver resolves all files in 397`, refused `{'docs/DECISIONS.md': 2, 'INDEX.md': 1}`, every refusal `a side edits an existing line at a conflict`. That is 99.25%.
3. **The residue is edits of landed lines, which fragments do not fix either.**
   - The 3 refused merges each rewrote rows already on the base (D-1125; D-980 to D-991; an `INDEX.md` row), the shape a botched earlier hand resolution leaves. The diff of merge `6b3e40657`'s branch side shows `-| D-980 …` / `+| D-980 …` pairs.
   - Of the merge owner's 51 refusals in 14 days (`merged 537, refused 51`), 10 are this edits-an-existing-line class (CHANGELOG 7, DECISIONS 2, INDEX 1). The two DECISIONS ones replay to base sections holding landed rows (D-833; D-988 and D-991).
   - A per-entry fragment never prevents an edit to an entry that has already been assembled into the canonical file. A driver removes the hand resolution that produces those rewrites.
4. **D-1381's premise.** D-1381 Part 4 (`docs/DECISIONS.md`, row D-1381) chose fragments on the coordinator's "22 of 51 refusals were conflicts". Of those 22, 6 were `.fabrik/work` (a separate fix, D-1381) and about 6 were code/doc files no ledger design touches. The 400 builder-side resolutions were invisible to it, because refusal records only count the owner's merges.

## What exists today (grounded)

- `_resolve_insertions` (`scripts/merge_request.py:958-995`) keeps both sides of a conflict whose base section is empty: newest D-row first for DECISIONS, ours-then-theirs elsewhere. It refuses a conflict with a non-empty base and re-checks for leftover markers.
- `_merge3` (`scripts/merge_request.py:998-1012`) runs `git merge-file -p --diff3` and calls the resolver only on rc ≠ 0.
- `LEDGERS` (`scripts/merge_request.py:536-544`) names the five paths. `_build` (`scripts/merge_request.py:1163-1210`) resolves them in-process after a conflicted `git merge`, then refuses a duplicate D-id (`_dup_ids`, `scripts/merge_request.py:1216`).
- The work-item driver precedent (`scripts/install_post_commit_hook.sh:69-122`) has three parts: `DRIVER='python3 scripts/work.py merge-item %O %A %B || git merge-file --marker-size %L -L ours -L base -L theirs %A %O %B'` (`:75`); `set_config` writes only on change (`:81-87`); and the `merge=workitem` lines are mirrored into `<common>/info/attributes` (`:93-122`), so a branch cut before `.gitattributes` gained them still gets the driver.
- **Probe (executed, `probe.sh` in run scratch).** In a scratch repo, `CHANGELOG.md merge=ledger` plus `merge.ledger.driver 'python3 scripts/ledger_driver.py %O %A %B %P'` was invoked by `git merge` inside a linked worktree (driver cwd = the worktree top, logged) and by `git merge-tree`. The merged file held both entries above the old one.
  - Caveat: the probe's own no-driver control merged clean as well, so the synthetic edits did not conflict. The conflict evidence is item 1's replay on real history, not the probe.
- **Import cost (executed).** `python3 -c "import merge_request"` took 0.22–0.40 s and about 19 MB across 3 runs. That is the per-file cost of one driver call.

## The delta (invariants + touchpoints)

1. **New verb `merge-ledger`** in `scripts/merge_request.py`. It sits beside the `merge`/`resume`/`retry` parsers (`scripts/merge_request.py:3758-3792`) and takes `<base> <ours> <theirs> <path>` (git's `%O %A %B %P`).
   - It reads the three files as UTF-8.
   - It computes `_merge3(path, ours, base, theirs)`.
   - On success it writes the result to `<ours>` atomically (temp file + rename in the same directory) and exits 0.
   - On `RefusedError`, or any other exception, it writes NOTHING, prints the reason to stderr and exits 1.
   - Invariant: `<ours>` is either untouched or holds a complete, marker-free resolution. Never a partial write.
2. **Driver string** in `scripts/install_post_commit_hook.sh`: `python3 scripts/merge_request.py merge-ledger %O %A %B %P || git merge-file --marker-size %L -L ours -L base -L theirs %A %O %B`.
   - Registered with `set_config merge.ledger.name …` and `merge.ledger.driver …`.
   - The `||` fallback covers a refusal, a tree whose `merge_request.py` predates the verb, a missing `python3`, and a crash. In each case git keeps conflict markers and never picks a side.
   - The tree's OWN copy runs, as with `workitem`. So a branch cut before the verb landed falls back once, on the merge that brings the verb in.
3. **`.gitattributes`** gains one `merge=ledger` line per `LEDGERS` path.
   - The installer's mirror regex (`scripts/install_post_commit_hook.sh:98`) widens from `merge=workitem` to `merge=(workitem|ledger)`.
   - The BEGIN/END marker text stays byte-identical, so no existing block is orphaned.
   - The failure message in `set_config` names the driver it failed on, not always "the work-item merge driver".
4. **Unchanged, deliberately.** The ledger files, every reader (42 scripts and hooks name one of the two files — `readers.txt` census), `SKIP`, `PRETEST_SKIP`, `LEDGERS`, `_dup_ids` and `_build`.
   - Inside `_build`'s throwaway worktree the driver now fires first (the throwaway is a worktree of the same common dir, so it shares the config and `info/attributes`). Its result is byte-identical to the in-process path, because it is the same function.
   - A driver refusal falls back to markers, and `_build`'s in-process `_merge3` then refuses with today's message.
   - `_dup_ids` still runs over the merge result.

**MIRROR — the shapes this changes.**
- A builder who relied on seeing markers in the ledgers to review a sibling's entry now gets them silently merged. That is the intended effect, and the order is the same one the merge owner already lands.
- A merge whose ledger edit was a deliberate rewrite of a landed line still conflicts, as today.
- `git merge -X ours|theirs` reaches no custom driver (git ignores `-X` for drivers, as the installer comment at `:73` already records).
- A clone where the installer never ran behaves as today, which is silent but no worse.

## Contract deltas

None. No data-contract, ui-design, spec `shape:` or CLI surface a project consumes changes. The `merge-ledger` verb is new and internal, and only git calls it.

## Cost

- About 40 lines in `scripts/merge_request.py` (the verb and its parser), about 10 in the installer, and 5 in `.gitattributes`.
- Tests: driver round-trip on a real conflicting pair; refusal leaves `%A` untouched with rc 1; fallback markers when the verb is absent; installer mirror covers both drivers.
- Runtime: 0.2–0.4 s per conflicted ledger file per merge.

## Validation

- **Red-first test:** a two-branch scratch repo whose CHANGELOG and DECISIONS insertions conflict under plain git. It merges clean with the driver registered and is red without it. Guard: the control must CONFLICT, unlike this spec's probe.
- **Refusal test:** an edit of a landed row exits 1, `%A` is byte-identical, and the merge leaves markers.
- **Bootstrap test:** a tree with no `merge-ledger` verb falls back to markers (rc of the driver line ≠ 0, markers present).
- **Replay grader:** re-run `driver_cover.py`'s replay through the real `git merge` path with the driver registered, over the same 14-day window. Expected ≥ 397/400 clean.
- **Tripwire (the judges' shared dissent, named here):**
  - Counter: the edits-an-existing-line refusals in `.git/fabrik-merge/*.json` (`reason` contains `edits an existing line`).
  - Threshold: above 10 per 14 days, today's rate.
  - Check date: 2026-11-13. Owner: the coordinator, as merge owner and records keeper.
  - Reading below the threshold confirms this shape. Reading above it re-opens the fragment design under § Rejected alternatives with its measured residue.

## Decisions taken

- **Recommended:** register the existing resolver as a git merge driver (Approach D). The approval gate decides against D-1381 Part 4's fragments.
  - On approval, a new D-row supersedes D-1381 in part (Part 4 only), naming this measurement. REVERSIBLE: removing five `.gitattributes` lines and two config keys undoes it.
- Defaults chosen without asking:
  - The verb name `merge-ledger`, after `work.py merge-item`.
  - The tree's own copy runs, after the `workitem` precedent.
  - All five `LEDGERS` paths are covered, not only the two the item names, because LESSONS_LEARNT had 34 replay conflicts.

## Rejected alternatives

- **F — per-entry fragments for new entries (`changelog.d/`, `decisions.d/`), assembled at merge (D-1381 Part 4).**
  - Rejected on the measurement. The 400 builder conflicts are insertions, which D resolves at 99.25%. The remaining class is edits of landed lines, which F cannot prevent: an assembled entry is a line of the canonical file again.
  - F costs about 10 code files and 250 lines, two authoring paths kept forever (D-1381 forbids migration), and a fragment-on-master failure mode.
  - Touchpoints if the gate picks it anyway, all censused this run:
    - `SKIP` (`scripts/merge_test_select.py:63`), `PRETEST_SKIP` (`scripts/merge_request.py:1493`) and `LEDGERS` (`scripts/merge_request.py:536`) gain the two directories.
    - Assembly runs inside `_build` (`scripts/merge_request.py:1163`). It is reached by the pretest (`:1606`), the landing (`:1801`) and the queue pretest (`:3135`), so the tested tree equals the landed one. `_dup_ids` runs after assembly.
    - `decisions.py` `_next_id` (`scripts/decisions.py:610`) counts `decisions.d/`.
    - `check_doc_sync.py:462` and `check_changelog.py` accept a staged fragment.
    - `check_decisions_unique.py:51` unions fragments.
    - `final_gate.py:2174` triggers on `decisions.d/`.
    - The exemption lists `command_run.py:5400`, `task_lane.py:105` and `.claude/hooks/final_gate_stop.py:274` gain both directories.
    - Every one is a no-op in a repo without the directories.
- **H — D now, F on a tripwire.** All three judges ranked H first. This spec IS H's first half, and § Validation's tripwire is its second half. "Recommend D" and "H" are the same build.
- **git's built-in `merge=union`.** Rejected: git documents that it "tends to leave the added lines in the resulting file in random order" (gitattributes.adoc:1129-1131). It keeps BOTH sides of an edited landed row, which yields duplicate D-ids. It has no newest-first D-row order.
- **Run the main checkout's copy by absolute path (`/opt/fabrik/scripts/merge_request.py`).** Rejected: it executes a file whose working copy the coordinator may be editing, and it departs from the reviewed `workitem` precedent. The tree's-own-copy cost is one fallback conflict per pre-existing branch.
- **GitLab-style commit trailers instead of a CHANGELOG file.** Rejected: GitLab documents that an entry must sit on a specific commit, and adding one later needs `--amend` or `rebase -i` plus a force-push (https://docs.gitlab.com/development/changelog/). The hub bans both on shared trees (CLAUDE.md HARD STOPS).
- **A per-repo fleet rollout** (register the driver in project repos with coordinator mode). OUT-OF-SCOPE here (Intake I11). The verb ships fleet-wide with the sync, so a later rollout is installer-only.

## External dependencies

| Fact | Source (fetched 2026-10-30) | Tool |
|---|---|---|
| Driver contract: `%O %A %B` temp files, `%L` marker size, `%P` pathname; "leave the result of the merge in the file named with `%A` by overwriting it, and exit with zero status if it managed to merge them cleanly, or non-zero if there were conflicts"; a crash exits > 128 and the merge fails | https://raw.githubusercontent.com/git/git/master/Documentation/gitattributes.adoc lines 1155-1180 | curl (raw, orchestrator) |
| `union`: "This tends to leave the added lines in the resulting file in random order and the user should verify the result." | same file lines 1127-1132 | curl (raw) |
| `merge` attribute applies to `git merge` "and other commands such as `git revert` and `git cherry-pick`"; `git merge-file` calls `xdl_merge` directly and never looks up drivers | https://git-scm.com/docs/gitattributes ; https://raw.githubusercontent.com/git/git/master/builtin/merge-file.c | WebFetch; exa |
| Attributes read from the work tree, then the index; `$GIT_DIR/info/attributes` has the highest precedence | https://git-scm.com/docs/gitattributes | exa |
| towncrier: "Rather than … having one single file which developers all write to and produce merge conflicts, `towncrier` reads 'news fragments'"; fragments `git rm`'d at build | https://towncrier.readthedocs.io/en/stable/index.html ; https://towncrier.readthedocs.io/en/stable/tutorial.html | brave search → exa |
| GitLab: "we'd constantly see merge conflicts in the changelog when multiple merge requests attempted to add an entry" | https://about.gitlab.com/blog/solving-gitlabs-changelog-conflict-crisis/ | exa |
| ADRs: one file per decision, "numbered sequentially and monotonically"; per-number filenames collide across branches | https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions ; https://github.com/adr/madr/issues/28 | brave search → exa |

## fabrik-lib verdict

One line: no fabrik-lib module covers git merge drivers or ledger merging. BUILD (wire an existing hub function), not a fabrik-lib candidate: it is hub-specific, with no second project type.

## Shape/infra implications

One line: no scaffold type, `shape:` flag, port, container or deploy changes. Box-local git config and the hub's `.gitattributes` only.

## Documentation landing sites

- `docs/reference/merge-request.md` gets the driver's paragraph, beside the in-process resolver's description. `grep` it at build: extend, never a second doc.
- `docs/workstation/hooks-index.md` gets the installer's second driver.
- `CHANGELOG.md` and the D-row at approval.
- The script headers' `# AFTER-EDIT:` lines name those docs.

## Constraints Digest

| Quote | Source |
|---|---|
| Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |
| Format: Entry under ## [Unreleased] | `.windsurf/rules/core/40-documentation.md:132` |
The fragment design would have changed how row 1 is satisfied (a fragment, not a CHANGELOG edit). The driver leaves rows 1 and 2 exactly as they are: the entry still lands under `## [Unreleased]`. The other matched pack, `core/10-python.md`, has no row this delta trips. Its exception rules are HTTP-handler rules. The verb's own invariant (§ The delta 1: report and exit 1, never a partial write) stands on git's contract, not on a pack row.

## Lifecycle

- **Adoption.** The installer runs on every WSL shell, so every hub worktree has the driver within one shell start of the merge. A branch cut earlier falls back once.
- **Growth.** The cost is per conflicted ledger file per merge (0.2–0.4 s). At today's ~56 merges/day (785 in 14 d), that is under a minute of driver time a day. Escalation trigger: the § Validation tripwire (edit-class refusals above 10 per 14 days at 2026-11-13) re-opens fragments.
- **Degradation.** Any driver failure falls back to git's markers, which is today's behaviour, never a silent pick. A clone without the installer is today's behaviour.
- **Retirement.** Delete the five `.gitattributes` lines and the two `merge.ledger.*` keys. The verb can stay inert.

## Open / blocking unknowns

- RESOLVED (executed): driver cwd in a linked worktree; driver fires on `git merge-tree`; resolver coverage 397/400; import cost.
- OPEN: whether `git rebase` (merge backend `ort`) invokes the driver on a replayed commit. The docs say only `merge`/`revert`/`cherry-pick`. Resolution step: the plan's bootstrap test runs a real `git rebase` over a conflicting pair and asserts clean.
- OPEN: the 7 CHANGELOG owner refusals could not be replayed exactly (the merge records keep the base name, not its SHA). Resolution: the tripwire counter measures the class after D lands.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "Stop appending to shared files … one entry file per CHANGELOG entry and per DECISIONS row" (W-53360407 title) | IN | § Decisions taken: a merge driver; fragments in § Rejected alternatives F, with the measurement |
| I2 | "rendered into CHANGELOG.md and docs/DECISIONS.md at merge by merge_request.py" | IN | The canonical files are written by git's merge through `merge-ledger`; no render step |
| I3 | "so two branches never touch the same line" | IN | Goal: two branches' insertions never need a hand resolution; edits of landed lines still conflict on purpose |
| I4 | operator: "fed up with merge issues" | IN | § Personas, § Why this exists |
| I5 | coordinator: "NO migration of the existing 31,458 lines" | IN | § The delta 4: nothing migrates |
| I6 | coordinator: "FIRST extend SKIP …, PRETEST_SKIP …, LEDGERS … and _dup_ids …" | OUT-OF-SCOPE under D (no new path exists to add); IN under F | § Rejected alternatives F lists each touchpoint |
| I7 | coordinator: "the .fabrik/work same-item conflicts are a separate item" | OUT-OF-SCOPE | D-1381's separate fix; asked the coordinator to file it (mail 01M676D8JK and the spec-ready report) |
| I8 | coordinator: "merge_request.py is fleet-synced" | IN | § Personas (fleet repos), § The delta 2 |
| I9 | coordinator: "Report in the same turn when the spec is ready" | IN | The run's close (mail to the coordinator) |
| I10 | item next: "the gate checks that read them (check_convergence, decisions.py --reserve-id, the changelog gate)" | IN | § The delta 4 (unchanged under D); § Rejected alternatives F (each reader under F) |
| I11 | fleet repos with coordinator mode hit the same conflicts | OUT-OF-SCOPE | § Rejected alternatives last bullet; the verb ships with the sync, rollout is installer-only |
