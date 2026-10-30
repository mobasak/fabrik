# Ledger merge driver — stop hand-resolving CHANGELOG/DECISIONS conflicts

**Status:** DRAFT
**Size:** small (≈100 lines, 3 files)
**Profile:** delta — every Intake Inventory IN item, in the driver shape the coordinator accepted (I1–I3), maps to code that exists today (`scripts/merge_request.py`'s ledger resolver, `scripts/install_post_commit_hook.sh`'s merge-driver registration, `.gitattributes`); this registers an existing engine with git, it builds no new component.

Work item: W-53360407 (P0). Recommends a DIFFERENT shape from the one the item and D-1381 Part 4 name (per-entry fragment files). The reason is a measurement D-1381's panel did not have (§ Why this exists). The coordinator accepted the driver-first shape on 2026-10-30, in its answer to mail 01M677712S: *"accepted — the spec's driver-first shape amends D-1381 Part 4 on your measurement"*. The design approval belongs to `/fabrik-spec-review`'s panel. § Rejected alternatives carries the fragment design in full.

## Personas

- **Builder agents** (infra, infra-N, fleet, intel, kaizen windows, each in `.claude/worktrees/<name>`). PRIMARY. When the merge owner refuses a stale branch they run `git merge master` (or rebase). Today they resolve ledger conflicts by hand. The builder who executes this spec's plan runs § Validation's replay grader.
- **The operator.** Primary persona's pain in their own words, relayed by the coordinator 2026-10-30: *"fed up with merge issues"*. Reads results through the coordinator only (D-943).
- **The coordinator / merge owner.** Lands branches with `python3 scripts/merge_request.py merge` in throwaway worktrees (`scripts/merge_request.py:1163` `_build`). It already auto-resolves ledger insertions in-process (`scripts/merge_request.py:958-1012`) and keeps doing so. It owns § Validation's tripwire check.
- **git itself** (automated). Invokes the driver for a ledger path whenever both sides changed that file, conflicting or not: `git merge`, `rebase`, `cherry-pick`, `merge-tree`. Never `git merge-file`, which has no driver lookup (grounded below).
- **The installer** (automated). `scripts/install_post_commit_hook.sh` runs from `wsl_startup_hook.sh` on every shell. It registers the driver and mirrors the attribute lines into `<common>/info/attributes`. A failed `set_config` prints to that shell's stderr and the next shell retries (`scripts/install_post_commit_hook.sh:81-85`). The session that opened the shell is the one that sees it. `git config merge.ledger.driver` is the check any session can run.
- **The ~46 fleet repos** (automated consumers of the synced `merge_request.py`). They receive the new verb and never call it: no `.gitattributes` line and no `merge.ledger.driver` config exist there (the installer's `ROOT=/opt/fabrik`, `scripts/install_post_commit_hook.sh:14`). A rollout there is W-480cdb61.

**Primary loop (step budget).** A builder brings master into a refused branch, with no conflict outside the ledgers:
1. `git merge master` — the ledgers resolve inside the merge;
2. `git push`;
3. `python3 scripts/merge_request.py request …` (resend).

**Budget: 3 steps.** Today the loop is 7 steps, because four more sit between `git merge master` and `git push`: open each conflicted ledger at its markers, hand-merge it, `git add` it, and `git commit` the merge.

## Goal

A `git merge` in any hub worktree (and the `rebase` or `cherry-pick` a local, unpushed branch may still do; a pushed branch is never rebased, `scripts/merge_request.py:101-108`) resolves concurrent INSERTIONS into the five ledgers (`CHANGELOG.md`, `docs/DECISIONS.md`, `INDEX.md`, `docs/STRATEGIC_BACKLOG.md`, `docs/LESSONS_LEARNT.md`) with the same resolver the merge owner already trusts. No ledger moves, no reader changes, nothing migrates. An EDIT to an already-landed ledger line still conflicts, by design.

## Why this exists (measured 2026-10-30, executed this session — § Derivations)

1. **Builders hand-resolve ledger conflicts; the owner already does not.** § Derivations D1 replays every two-parent merge of the last 14 days on every ref with `git merge-tree --write-tree`, split by merge subject.
   - **Owner merges.** 557 owner builds (`merge(coordinator): …`, `pretest …`, `queue pretest …`). 331 conflict under plain git, all ledger-only, all cleared by the existing resolver. `_build` already applies that resolver in-process, so these cost nobody anything.
   - **Builder merges.** 229 builder merges (master into a branch, branch merges). 89 conflict, 70 of them only on ledgers. Plain git has no driver for these paths: `.gitattributes` maps only `.fabrik/work/W-*.json merge=workitem` (`.gitattributes:3`). Each of the 70 was a hand resolution, about 5 a day.
2. **The driver clears most of them, measured with a real `git merge`.** § Derivations D5 replays each builder merge with the driver registered: of the 67 ledger-only merges in the window, it clears 58 (87%) with no duplicated line, and 9 still conflict. Three of the 9 are edits of landed lines (below). The other 6 are merges with two merge bases, where git first merges the bases with the driver and the outer merge then sees an edit; they fall back to markers, today's behaviour, and are follow-up W-6614b62e. D1's single-base replica (`_merge3` in-process) counts 67 of 70 and overstates exactly those 6; it stays as the discriminator between the two kinds of residue (§ Derivations D3).
3. **The residue is edits of landed lines, which fragments do not fix either.**
   - The 3 refused merges each rewrote rows already on the base (D-1125; D-980 to D-991; an `INDEX.md` row), the shape a botched earlier hand resolution leaves. The branch side of merge `6b3e40657` diffs as `-| D-980 …` / `+| D-980 …` pairs.
   - Of the merge owner's 51 refusals in 14 days (`merged 537, refused 51`, record `reason` text), 10 are this edits-an-existing-line class (CHANGELOG 7, DECISIONS 2, INDEX 1). The two DECISIONS ones replay to base sections holding landed rows (D-833; D-988 and D-991).
   - A per-entry fragment never prevents an edit to an entry that has already been assembled into the canonical file. A driver removes the hand resolution that produces those rewrites.
4. **The item's premise.** The item's title measured "22 of 51 refusals in 14 d were conflicts", and D-1381 Part 4 (row D-1381 in `docs/DECISIONS.md` on master) chose fragments on it. In the records' `reason` text, the 22 that say `conflict` are 5 `.fabrik/work` conflicts, the 10 edit-class refusals above, and 7 code/doc files no ledger design touches. A sixth `.fabrik/work` refusal (`merge-item: both sides changed …`) does not say `conflict`, and D-1381 counts 7 work-item refusals in all; the separate fix is W-7a1411b3. The 70 builder-side hand resolutions never appear in refusal records, which count only the owner's merges.

## What exists today (grounded)

- `_resolve_insertions` (`scripts/merge_request.py:958-995`) keeps both sides of a conflict whose base section is empty: newest D-row first for DECISIONS, ours-then-theirs elsewhere. It refuses a conflict with a non-empty base and re-checks for leftover markers.
- `_merge3` (`scripts/merge_request.py:998-1012`) runs `git merge-file -p --diff3` and calls the resolver only on rc ≠ 0. `_build` reads and writes the blobs as bytes through `_decode`/`_encode` (UTF-8 with `surrogateescape`, `scripts/merge_request.py:728-733`).
- `LEDGERS` (`scripts/merge_request.py:536-544`) names the five paths. `_build` (`scripts/merge_request.py:1163-1210`) resolves them in-process after a conflicted `git merge`, then refuses a duplicate D-id (`_dup_ids`, `scripts/merge_request.py:1216`).
- The work-item driver precedent (`scripts/install_post_commit_hook.sh:69-122`) has three parts:
  - `DRIVER='python3 scripts/work.py merge-item %O %A %B || git merge-file --marker-size %L -L ours -L base -L theirs %A %O %B'` (`:75`);
  - `set_config` (`:81-85`) writes only on change and is called at `:86-87`;
  - the `merge=workitem` lines are mirrored into `<common>/info/attributes` (`:93-122`), so a branch cut before `.gitattributes` gained them still gets the driver.
- **Probes (executed in scratch repos, this run and its review).**
  - A `.gitattributes` merge driver is invoked by `git merge` inside a linked worktree (driver cwd = the worktree top, logged), by `git merge-tree`, and by `git rebase`: the driver logged one call, the rebase finished clean, and the same pair conflicts with no driver.
  - A driver that kills itself, with no fallback, FAILS the merge (`error: failed to execute internal merge`, rc 2, no stages). With the `||` fallback the same case yields an ordinary conflict with stages and markers. So does a missing script, and so does a pre-verb `merge_request.py` (argparse `invalid choice: 'merge-ledger'`, exit 2).
  - When the driver resolves everything, `git merge --no-ff --no-edit -m <msg>` exits 0 and writes today's two-parent commit with `<msg>`. `_build` skips its conflict block and still runs `_dup_ids` (`scripts/merge_request.py:1203-1208`).
- **Call cost (executed).** `python3 -c "import merge_request"` took 0.22–0.40 s and about 19 MB across 3 runs. A full driver call on the real 41,715-line `CHANGELOG.md` (import, `git merge-file`, the resolver, the write) took 0.67–0.79 s in one 3-run batch and 0.37–0.38 s in another; the spread is box load.

## The delta (invariants + touchpoints)

1. **New verb `merge-ledger`** in `scripts/merge_request.py`. It sits beside the `merge`/`resume`/`retry` parsers (`scripts/merge_request.py:3758-3792`) and takes `<base> <ours> <theirs> <path>` (git's `%O %A %B %P`).
   - It reads the three files as bytes through `_decode`, exactly as `_build` does.
   - It computes `_merge3(path, ours, base, theirs)`.
   - For `docs/DECISIONS.md` it then refuses, naming the ids, when the result holds a D-id twice that neither side held twice alone: the duplicate-id check `_build` applies at landing (`scripts/merge_request.py:1203-1208`), moved to the first merge that can see the clash, so a builder sees both rows at its own merge instead of a refusal one round trip later. (Panel, Fable concern 1.)
   - It writes the `_encode`d result to `<ours>` atomically (temp file + rename in the same directory). Nothing after the rename can fail: the verb is dispatched before `main()`'s `try`/`finally` sync drain, as `sync-runner` is (`scripts/merge_request.py:3779-3790`).
   - On `RefusedError`, or any other exception, it leaves `<ours>` untouched and no temp file behind, prints the reason to stderr and exits 1.
   - Invariant: `<ours>` is either untouched with a non-zero exit, or holds a complete, marker-free resolution with exit 0. Never a write followed by a non-zero exit, which the `||` fallback would re-merge into a misleading conflict.
2. **Driver string** in `scripts/install_post_commit_hook.sh`: `python3 scripts/merge_request.py merge-ledger %O %A %B %P || git merge-file --marker-size %L -L ours -L base -L theirs %A %O %B`.
   - Registered with `set_config merge.ledger.name …` and `merge.ledger.driver …`.
   - The `||` fallback turns every failure into an ordinary conflict with markers, never a picked side: a refusal (exit 1), a tree whose `merge_request.py` predates the verb (exit 2), a missing `python3` (exit 127), and a crash (exit > 128).
   - The tree's OWN copy runs, as with `workitem`. So a branch cut before the verb landed falls back once, on the merge that brings the verb in.
3. **`.gitattributes`** gains one `merge=ledger` line per `LEDGERS` path, each anchored to the repo root (`/CHANGELOG.md`, `/INDEX.md`, `/docs/DECISIONS.md`, …). An unanchored `CHANGELOG.md` matches that name at any depth and would widen the auto-resolve past `LEDGERS`.
   - The installer's mirror regex (`scripts/install_post_commit_hook.sh:98`) widens from `merge=workitem` to `merge=(workitem|ledger)`.
   - The BEGIN/END marker text stays byte-identical, so no existing block is orphaned.
   - The failure message in `set_config` names the driver it failed on, not always "the work-item merge driver".
4. **Unchanged, deliberately.** The ledger files, `SKIP`, `PRETEST_SKIP`, `LEDGERS`, `_dup_ids`, `_build`, and every reader of the two ledgers. § Derivations D2 counts 47 Python files outside `tests/` naming `CHANGELOG.md` or `DECISIONS.md` under `scripts/`, `.claude/hooks/` and `src/`.
   - Inside `_build`'s throwaway worktree the driver now fires first: the throwaway is a worktree of the same common dir, so it shares the config and `info/attributes`. For a path git's own merge would conflict on, its text is the in-process path's, because it calls the same function with the same sides (ours = the base branch there). For a path git would have merged cleanly, the text now comes from `git merge-file` instead of git's internal merge; § Derivations D4 measures that difference. (Panel, Opus concern 1.)
   - A driver refusal falls back to markers, and `_build`'s in-process `_merge3` then refuses with today's message.
   - `_dup_ids` still runs over the merge result.

**MIRROR — the shapes this changes.**
- A builder who relied on seeing markers in the ledgers to review a sibling's entry now gets them merged. That is the intended effect.
- **Order.** In DECISIONS the conflict hunk holding the higher D-number goes first (`_max_d`, `scripts/merge_request.py:980`); rows inside one hunk keep their side's order, so two rows on one side can interleave with the other side's. In the other four files the resolver keeps ours first. (Panel, Fable concern 3.) A builder's `git merge master` therefore places the branch's own new entry above master's new entries, while the owner's landing places master's first. Content is identical either way, and only the order of entries that landed in the same window differs. Rebase reverses ours and theirs again. No reader checked here depends on that order. The plan's tests pin the content, never the order.
- A merge whose ledger edit was a deliberate rewrite of a landed line still conflicts, as today.
- **Empty base.** When both sides CREATE a ledger (git passes an empty `%O`), the resolver keeps both whole files, headers included, as `_build` already does with `orig = ""` (`scripts/merge_request.py:1189`). Pre-existing on the owner path, new on the builder path. (Panel, Fable concern 6.)
- `git merge -X ours|theirs` reaches no custom driver (git ignores `-X` for drivers, as the installer comment at `:73` already records).
- A clone where the installer never ran behaves as today, which is silent but no worse.

## Contract deltas

None. No data-contract, ui-design, spec `shape:` or CLI surface a project consumes changes. The `merge-ledger` verb is new and internal, and only git calls it.

## Cost

- **Code.** About 40 lines in `scripts/merge_request.py` (the verb and its parser), about 10 in the installer, and 5 in `.gitattributes`.
- **Tests.** Listed in § Validation.
- **Runtime.** git calls the driver once per ledger file changed on BOTH sides of a merge, conflicting or not, at up to 0.8 s each (§ What exists today, call cost). So the cost per merge build is at most 5 × 0.8 s = 4 s.
  - On the owner side, every build pays it: the pretest (`scripts/merge_request.py:1606`), the landing (`:1801`), the queue pretest (`:3135`), and each rebuild up to `MAX_REBUILDS` (`:546`).
  - At D1's 557 owner builds and 229 builder merges in 14 days (about 56 a day), the bound is under 4 minutes a day, against owner builds that run for minutes each.

## Validation

- **Red-first test.** A two-branch scratch repo whose CHANGELOG and DECISIONS insertions conflict under plain git.
  - The control (no driver) must CONFLICT: the test asserts it first.
  - With the driver registered, the same merge is clean and holds both entries.
  - A third leg runs `git rebase` over the same pair and asserts clean.
  - The DECISIONS leg inserts `D-1391` on one side and `D-1390` on the other and asserts `D-1391` precedes `D-1390` whichever side is ours: the one assertion that proves `%P` reached the verb. (Panel, Fable concern 2.)
- **Duplicate-id test.** Both sides insert a `| D-1390 |` row: the verb exits 1 with `%A` byte-identical, and the merge leaves markers showing both rows. (Panel, Fable concern 1.)
- **No-regression test.** A ledger merge that `git merge` resolves cleanly with no driver still exits 0 with no markers with the driver registered, and `_build` raises no `ConflictError` on it. (Panel, Opus concern 3.)
- **Refusal test.** An edit of a landed row: the verb, run directly, exits exactly 1 with `%A` byte-identical. Through git, the merge leaves markers.
- **Bootstrap test.** A tree whose `merge_request.py` has no `merge-ledger` verb.
  - The driver's stderr carries `invalid choice: 'merge-ledger'`, which proves the driver ran.
  - The merge leaves markers.
  - Plain git without the driver would leave markers too, so the stderr line is what makes this test red-able.
- **Replay grader.** § Derivations D5 (a real `git merge` per merge, the driver registered, on a scratch clone at the plan's tip) over the same window, both sides: builder and owner. Expected: at least 58 builder merges cleared with no duplicated line, and every owner ledger-only merge cleared (the first real-driver run, 2026-10-31, over "14 days ago": 392 of 392 owner merges cleared). (Panel, Opus concern 4.) The builder who executes the plan runs it, and the plan records its output.
- **Tripwire (the judges' shared dissent, named here).**
  - What it watches: insertions the driver failed to clear, which per-entry fragments would have cleared. That is a builder merge D5 leaves conflicted on a ledger while D3's single-base replica clears it (an edit of a landed line fails in both, and fragments cannot fix it either).
  - Counter: D5's still-conflicted builder SHAs minus D3's. Window: the 14 days after the driver lands, by commit date (`--since=<landing> --until=<landing + 14 days>`, both scripts take them), never by merge-record fields, which carry no wall-clock time.
  - Threshold: more than 6, today's two-base residue (D5's 9 minus D3's 3), unless W-6614b62e has landed, when it is more than 0.
  - Edit-class residue is reported beside the counter and never re-opens fragments, which cannot prevent it (§ Why this exists 3).
  - Check date: 14 days after the driver lands. Owner: the coordinator, as merge owner.
  - Reading 0 confirms this shape. Any other reading re-opens the fragment design under § Rejected alternatives, with the merge SHAs named.
  - Counter B (a driver regression, independent of fragments): merges in the window that are clean with no `merge.ledger.*` and conflict on a ledger with it. Threshold: any; a non-zero reading blocks and is fixed in the driver. (Panel, Opus concern 2.)
  - A rebased branch leaves no merge commit, so neither counter sees it; the owner's refusal records stay the rebase-side signal and are read beside them.

## Decisions taken

- **Recommended:** register the existing resolver as a git merge driver (Approach D), accepted by the coordinator over D-1381 Part 4's fragments (answer to mail 01M677712S). This review's panel gives the design approval.
  - On approval, a new D-row supersedes D-1381 in part (Part 4 only), naming this measurement.
  - REVERSIBLE. Undo means deleting the `merge.ledger.*` registration lines from `scripts/install_post_commit_hook.sh` and the five `merge=ledger` lines from `.gitattributes`. Then `git config --unset` the two `merge.ledger.*` keys, and the next installer run rebuilds the `info/attributes` block without the ledger lines. Removing only the keys does not undo it: `set_config` re-writes a missing key on the next shell.
- Defaults chosen without asking:
  - The verb name `merge-ledger`, after `work.py merge-item`.
  - The tree's own copy runs, after the `workitem` precedent.
  - All five `LEDGERS` paths are covered, not only the two the item names, because LESSONS_LEARNT and INDEX conflict in the replay too.

## Rejected alternatives

- **F — per-entry fragments for new entries (`changelog.d/`, `decisions.d/`), assembled at merge (D-1381 Part 4).**
  - Rejected on the measurement. Of the 67 builder ledger-only merges (D5), D clears 58. F would also clear the 6 two-base merges (64), but not the 3 edits of landed lines, which F cannot prevent: an assembled entry is a line of the canonical file again. Six merges in 14 days do not pay for F's cost below, while the driver's own follow-up (W-6614b62e) targets them and § Validation's tripwire re-opens F if they grow.
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
- **H — D now, F on a tripwire.** All three judges ranked H first. This spec IS H's first half, and § Validation's tripwire is its second half, so "Recommend D" and "H" are the same build.
- **`merge.ledger.recursive=binary`** (git's knob for the internal merge of two merge bases). Rejected on execution: it clears the 6 two-base merges, but by adding lines beyond ours + theirs − base, i.e. duplicated CHANGELOG entries and DECISIONS rows (up to 28 extra lines in one file). The default (unset: the driver merges the bases too) is kept; its residue falls back to markers.
- **git's built-in `merge=union`.** Rejected. git documents that it "tends to leave the added lines in the resulting file in random order" (gitattributes.adoc:1129-1131). It keeps BOTH sides of an edited landed row, which yields duplicate D-ids, and it has no D-number order.
- **Run the main checkout's copy by absolute path (`/opt/fabrik/scripts/merge_request.py`).** Rejected. It executes a file whose working copy the coordinator may be editing, and it departs from the reviewed `workitem` precedent. The tree's-own-copy cost is one fallback conflict per pre-existing branch.
- **GitLab-style commit trailers instead of a CHANGELOG file.** Rejected. GitLab's changelog guide tells authors to put the `Changelog` trailer on the first commit and, to add one later, to amend the commit or use `git rebase -i`, then force-push if the commits were already pushed (https://docs.gitlab.com/development/changelog/). The hub bans `--amend` and force pushes on shared trees (CLAUDE.md HARD STOPS).
- **A per-repo fleet rollout** (register the driver in project repos with coordinator mode). OUT-OF-SCOPE here (Intake I11, W-480cdb61). The verb ships fleet-wide with the sync, so a later rollout is installer-only.

## External dependencies

| Fact | Source (fetched 2026-10-30) | Tool |
|---|---|---|
| Driver contract: `%O %A %B` temp files, `%L` marker size, `%P` pathname; "leave the result of the merge in the file named with `%A` by overwriting it, and exit with zero status if it managed to merge them cleanly, or non-zero if there were conflicts"; a crash exits > 128 and the merge fails | https://raw.githubusercontent.com/git/git/master/Documentation/gitattributes.adoc lines 1155-1180 | curl (raw, orchestrator) |
| `union`: "This tends to leave the added lines in the resulting file in random order and the user should verify the result." | same file lines 1127-1132 | curl (raw) |
| `merge` attribute applies to `git merge` "and other commands such as `git revert` and `git cherry-pick`"; `git merge-file` calls `xdl_merge` directly and never looks up drivers | https://git-scm.com/docs/gitattributes ; https://raw.githubusercontent.com/git/git/master/builtin/merge-file.c | WebFetch; exa |
| `$GIT_DIR/info/attributes` has the highest precedence; the index copy of `.gitattributes` is a fallback only when the work tree lacks the file | https://git-scm.com/docs/gitattributes | exa |
| towncrier: "Rather than reading the Git history, or having one single file which developers all write to and produce merge conflicts, towncrier reads “news fragments”"; fragments `git rm`'d at build | https://towncrier.readthedocs.io/en/stable/index.html ; https://towncrier.readthedocs.io/en/stable/tutorial.html | brave search → exa; curl (raw, orchestrator) |
| GitLab: "we'd constantly see merge conflicts in the changelog when multiple merge requests attempted to add an entry" | https://about.gitlab.com/blog/solving-gitlabs-changelog-conflict-crisis/ | exa |
| ADRs: one file per decision, "numbered sequentially and monotonically"; per-number filenames collide across branches | https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions ; https://github.com/adr/madr/issues/28 | brave search → exa |

## fabrik-lib verdict

One line: no fabrik-lib module covers git merge drivers or ledger merging. BUILD (wire an existing hub function), not a fabrik-lib candidate: it is hub-specific, with no second project type.

## Shape/infra implications

One line: no scaffold type, `shape:` flag, port, container or deploy changes. Box-local git config and the hub's `.gitattributes` only.

## Documentation landing sites

- `docs/reference/multi-agent-operating-model.md` § Ledgers and ids across branches (`:162-166`, which already describes the in-process resolver) gets the driver's paragraph, and its sentence that two branches prepending a row "always conflict at merge" is corrected: in a hub worktree with the driver they no longer do. It is the doc `scripts/merge_request.py:2`'s `# AFTER-EDIT:` header names, so the header needs no change.
- `docs/workstation/hooks-index.md` gets the installer's second driver, in the installer's row beside the work-item driver. `scripts/install_post_commit_hook.sh:2` already names that doc.
- `CHANGELOG.md`, and the D-row at approval.

## Constraints Digest

| Quote | Source |
|---|---|
| Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |
| Format: Entry under ## [Unreleased] | `.windsurf/rules/core/40-documentation.md:132` |

The fragment design would have changed how row 1 is satisfied (a fragment, not a CHANGELOG edit). The driver leaves rows 1 and 2 exactly as they are: the entry still lands under `## [Unreleased]`. The other matched pack, `core/10-python.md`, has no row this delta trips; its exception rules are HTTP-handler rules. The verb's own invariant (§ The delta 1: report and exit 1, never a partial write) stands on git's contract, not on a pack row.

## Lifecycle

- **Adoption.** The installer runs on every WSL shell, so every hub worktree has the driver within one shell start of the merge. A branch cut earlier falls back once.
- **Growth.** The cost is bounded per merge build (§ Cost: ≤ 4 s) and grows linearly with merges. Escalation trigger: § Validation's tripwire, which re-opens fragments only on insertion conflicts the driver failed to clear.
- **Degradation.** Any driver failure falls back to git's markers, which is today's behaviour, never a silent pick. A clone without the installer is today's behaviour.
- **Retirement.** The undo in § Decisions taken: installer lines, `.gitattributes` lines, then the two keys. The verb can stay inert.

## Open / blocking unknowns

- RESOLVED (executed):
  - driver cwd in a linked worktree;
  - driver fires on `git merge-tree` and `git rebase`;
  - the crash, missing-script and pre-verb fallbacks;
  - the clean-merge commit shape in `_build`;
  - the real driver's coverage of the builder-side population (58/67, D5) and of the owner side (392/392);
  - import cost.
- OPEN: the two-base residue (6 of 67 builder merges, D5). Resolution: W-6614b62e; until then those merges fall back to markers, today's behaviour.
- OPEN: the 7 CHANGELOG owner refusals could not be replayed exactly, because the merge records keep the base branch name, not its SHA. Resolution: the tripwire counts builder-side residue after landing, and the owner's refusal reasons stay readable in the records.

## Derivations

**D1 — the replay, split by merge subject** (run from the hub worktree root at `51716046f`; ~10 minutes):

```python
import subprocess, collections, re, sys
sys.path.insert(0, "scripts")
import merge_request as mr
def g(*a, text=True): return subprocess.run(["git", *a], capture_output=True, text=text)
def blob(c, p):
    r = g("show", f"{c}:{p}", text=False)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
L = {"CHANGELOG.md", "docs/DECISIONS.md", "INDEX.md", "docs/STRATEGIC_BACKLOG.md", "docs/LESSONS_LEARNT.md"}
c = collections.Counter()
for line in g("log", "--all", "--merges", "--since=14 days ago", "--format=%H %P\t%s").stdout.splitlines():
    head, subj = line.split("\t", 1); parts = head.split()
    if len(parts) != 3: continue
    kind = "owner" if re.match(r"(merge\(coordinator\)|pretest |queue pretest )", subj) else "builder"
    c[kind, "merges"] += 1
    _, p1, p2 = parts
    res = g("merge-tree", "--write-tree", "--name-only", "--no-messages", p1, p2)
    if res.returncode == 0: continue
    files = set(res.stdout.split("\n")[1:]) - {""}
    c[kind, "conflicted"] += 1
    if files and files <= L:
        c[kind, "ledger-only"] += 1
        base = g("merge-base", p1, p2).stdout.split()[0]
        ok = True
        for f in files:
            try: mr._merge3(f, blob(p1, f), blob(base, f), blob(p2, f))
            except mr.RefusedError: ok = False
        c[kind, "resolver-clears"] += ok
for k in sorted(c): print(k, c[k])
```

Output on 2026-10-30:

```text
('builder', 'conflicted') 89
('builder', 'ledger-only') 70
('builder', 'merges') 229
('builder', 'resolver-clears') 67
('owner', 'conflicted') 331
('owner', 'ledger-only') 331
('owner', 'merges') 557
('owner', 'resolver-clears') 331
```

**D3 — the builder residue with its reasons** (D1's builder ledger-only merges, each `_merge3` refusal printed; the tripwire's counter is the number of distinct merge SHAs whose reason is not `a side edits an existing line`). Run from the hub worktree root as `python3 d3.py <since> <until>` (git date strings). (Panel, Fable concern 4.)

```python
import subprocess, re, sys
sys.path.insert(0, "scripts")
import merge_request as mr
def g(*a, text=True): return subprocess.run(["git", *a], capture_output=True, text=text)
def blob(c, p):
    r = g("show", f"{c}:{p}", text=False)
    return mr._decode(r.stdout) if r.returncode == 0 else ""
L = {"CHANGELOG.md", "docs/DECISIONS.md", "INDEX.md", "docs/STRATEGIC_BACKLOG.md", "docs/LESSONS_LEARNT.md"}
since, until = sys.argv[1:3]  # the tripwire window: --since=<landing> --until=<landing + 14 days>
for line in g("log", "--all", "--merges", f"--since={since}", f"--until={until}", "--format=%H %P\t%s").stdout.splitlines():
    head, subj = line.split("\t", 1); p = head.split()
    if len(p) != 3 or re.match(r"(merge\(coordinator\)|pretest |queue pretest )", subj): continue
    r = g("merge-tree", "--write-tree", "--name-only", "--no-messages", p[1], p[2])
    if r.returncode == 0: continue
    files = set(r.stdout.split("\n")[1:]) - {""}
    if not (files and files <= L): continue
    b = g("merge-base", p[1], p[2]).stdout.split()[0]
    for f in files:
        try: mr._merge3(f, blob(p[1], f), blob(b, f), blob(p[2], f))
        except mr.RefusedError as e: print(p[0][:9], f, str(e).split(": ", 1)[1])
```

Output on 2026-10-30, run as `python3 d3.py "14 days ago" now` (3 distinct merges, = D1's 70 − 67):

```text
fdf514616 docs/DECISIONS.md a side edits an existing line at a conflict
6f6cd85ec INDEX.md a side edits an existing line at a conflict
6b3e40657 docs/DECISIONS.md a side edits an existing line at a conflict
```

**D4 — merges that are clean today: does the driver break or change them?** (Panel, Opus concern 1.) Every merge whose `merge-tree` is clean, each ledger file both sides changed, run through `_merge3` and compared with git's own merge result:

```python
import subprocess, re, sys, collections
sys.path.insert(0, "scripts")
import merge_request as mr
def g(*a, text=True): return subprocess.run(["git", *a], capture_output=True, text=text)
def blob(c, p):
    r = g("show", f"{c}:{p}", text=False)
    return mr._decode(r.stdout) if r.returncode == 0 else None
L = ["CHANGELOG.md", "docs/DECISIONS.md", "INDEX.md", "docs/STRATEGIC_BACKLOG.md", "docs/LESSONS_LEARNT.md"]
c = collections.Counter(); bad = []
for line in g("log", "--all", "--merges", "--since=14 days ago", "--format=%H %P\t%s").stdout.splitlines():
    head, subj = line.split("\t", 1); p = head.split()
    if len(p) != 3: continue
    kind = "owner" if re.match(r"(merge\(coordinator\)|pretest |queue pretest )", subj) else "builder"
    r = g("merge-tree", "--write-tree", "--no-messages", p[1], p[2])
    if r.returncode != 0: continue
    tree = r.stdout.split()[0]
    b = g("merge-base", p[1], p[2]).stdout.split()[0]
    for f in L:
        o, a, t = blob(b, f), blob(p[1], f), blob(p[2], f)
        if o is None or a is None or t is None or a == o or t == o or a == t: continue
        c[kind, "both-sides-changed"] += 1
        want = blob(tree, f)
        try:
            got = mr._merge3(f, a, o, t)
            if got == want: c[kind, "identical"] += 1
            else: c[kind, "differs"] += 1; bad.append((kind, p[0][:9], f, "differs"))
        except mr.RefusedError as e:
            c[kind, "REFUSED"] += 1; bad.append((kind, p[0][:9], f, str(e).split(": ", 1)[1][:40]))
for k in sorted(c): print(k, c[k])
for x in bad[:20]: print(x)
```

Output on 2026-10-30:

```text
('builder', 'both-sides-changed') 32
('builder', 'differs') 3
('builder', 'identical') 29
('owner', 'both-sides-changed') 113
('owner', 'differs') 1
('owner', 'identical') 112
('builder', 'e84651224', 'CHANGELOG.md', 'differs')
('builder', 'e84651224', 'docs/DECISIONS.md', 'differs')
('builder', 'e84651224', 'docs/LESSONS_LEARNT.md', 'differs')
('owner', 'd42930d43', 'CHANGELOG.md', 'differs')
```

No clean merge is refused (0 of 145 files). The 4 differences are both merges with two merge bases, where this replica's single `merge-base` is not the virtual base git hands a driver. A real `git merge --no-commit` of `e84651224` in a scratch clone with the driver registered reproduces every committed ledger blob, and a driver set to `false` also merges clean there: git never calls the driver on those files, because against the virtual base one side is unchanged.

**D5 — the real driver, one `git merge` per builder merge** (Panel, Opus concern 1). Run as `python3 d5.py <clone> <baseline checkout> <since> <until>`: `<clone>` is a scratch `git clone --shared` of the hub with the five `merge=ledger` lines in its `.git/info/attributes`, `merge.ledger.driver` registered, and the work-item driver too; `<baseline checkout>` is a checkout with no ledger attribute, which gives the plain-git verdict:

```python
import subprocess, re, sys, collections
R, BASE = sys.argv[1:3]; since, until = sys.argv[3:5]
def g(*a): return subprocess.run(["git", *a], capture_output=True, text=True, cwd=R)
L = {"CHANGELOG.md", "docs/DECISIONS.md", "INDEX.md", "docs/STRATEGIC_BACKLOG.md", "docs/LESSONS_LEARNT.md"}
def lines(rev, f):
    r = g("show", f"{rev}:{f}"); return collections.Counter(r.stdout.splitlines()) if r.returncode == 0 else collections.Counter()
c = collections.Counter(); left = []
for line in g("log", "--all", "--merges", f"--since={since}", f"--until={until}", "--format=%H %P\t%s").stdout.splitlines():
    head, subj = line.split("\t", 1); p = head.split()
    if len(p) != 3: continue
    kind = "owner" if re.match(r"(merge\(coordinator\)|pretest |queue pretest )", subj) else "builder"
    if kind != "builder": continue
    # the no-driver baseline: BASE is a checkout with no merge=ledger attribute (the repo before the driver)
    nod = subprocess.run(["git", "-C", BASE, "merge-tree", "--write-tree", "--name-only", "--no-messages", p[1], p[2]], capture_output=True, text=True)
    files = set(nod.stdout.split("\n")[1:]) - {""}
    if nod.returncode == 0 or not (files and files <= L): continue  # ledger-only under plain git
    c["ledger-only"] += 1
    g("checkout", "-q", "--detach", "-f", p[1])
    m = g("merge", "-q", "--no-commit", "--no-ff", p[2])
    if m.returncode == 0:
        c["driver-clears"] += 1
        for f in L:
            try: res = collections.Counter(open(f"{R}/{f}", encoding="utf-8", errors="replace").read().splitlines())
            except FileNotFoundError: continue
            mb = g("merge-base", p[1], p[2]).stdout.split()[0]
            dup = sum((res - ((lines(p[1], f) + lines(p[2], f)) - lines(mb, f))).values())  # beyond ours + theirs - base
            if dup: c["clears-with-duplicated-lines"] += 1; left.append((p[0][:9], f, "dup", dup))
    else:
        c["still-conflicted"] += 1
        left.append((p[0][:9], [x for x in g("diff", "--name-only", "--diff-filter=U").stdout.split() if x], (m.stderr.strip().splitlines() or [""])[-1][:70]))
    g("merge", "--abort"); g("reset", "-q", "--hard")
for k in sorted(c): print(k, c[k])
for x in left: print(x)
```

Output for `"2026-10-17 00:00" "2026-10-31 00:00"` (summary lines; the 12 still-conflicted SHAs print below them):

```text
driver-clears 58
ledger-only 70
still-conflicted 12
```

Of the 12, 3 conflict only on a `.fabrik/work` item, because those trees' `work.py` predates `merge-item`; they are not ledger residue, which leaves 58 of 67. The other 9 refuse `a side edits an existing line at a conflict`: 3 are D3's edits of landed lines (`fdf514616`, `6f6cd85ec`, `6b3e40657`), and 6 are two-base CHANGELOG merges (`29c6d1da4`, `ce79b4775`, `db42471cb`, `7ec2b85dd`, `669274a87`, `2e9c1758d`). No cleared merge holds a line beyond ours + theirs − base.

**D2 — the reader census:**

```text
command grep -rlE "DECISIONS\.md|CHANGELOG\.md" --include=*.py scripts .claude/hooks src tests   → 119 files
… of them outside tests/ → 47 (of which 4 under scripts/.archive or scripts/archived)
```

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "Stop appending to shared files … one entry file per CHANGELOG entry and per DECISIONS row" (W-53360407 title) | IN | Changed shape, accepted by the coordinator (answer to 01M677712S): § Decisions taken (a merge driver); fragments kept in full in § Rejected alternatives F |
| I2 | "rendered into CHANGELOG.md and docs/DECISIONS.md at merge by merge_request.py" | IN | Changed shape: git's merge writes the canonical files through `merge-ledger` (§ The delta 1-2); no render step |
| I3 | "so two branches never touch the same line" | IN | Changed shape: § Goal (concurrent insertions never need a hand resolution; edits of landed lines still conflict on purpose) |
| I4 | operator: "fed up with merge issues" | IN | § Personas, § Why this exists |
| I5 | coordinator: "NO migration of the existing 31,458 lines" (their figure; `CHANGELOG.md` is 41,715 lines at `51716046f`) | IN | § The delta 4: nothing migrates |
| I6 | coordinator: "FIRST extend SKIP …, PRETEST_SKIP …, LEDGERS … and _dup_ids …" | OUT-OF-SCOPE | Under the driver no new path exists to add (§ The delta 4); each touchpoint is listed for the fragment design in § Rejected alternatives F |
| I7 | coordinator: "the .fabrik/work same-item conflicts are a separate item" | OUT-OF-SCOPE | W-7a1411b3 (filed 2026-10-30, linked to D-1381) |
| I8 | coordinator: "merge_request.py is fleet-synced" | IN | § Personas (fleet repos), § The delta 2 |
| I9 | coordinator: "Report in the same turn when the spec is ready" / "when the review closes" | IN | The review's close (mail to the coordinator) |
| I10 | item next: "the gate checks that read them (check_convergence, decisions.py --reserve-id, the changelog gate)" | IN | § The delta 4 (unchanged under the driver); § Rejected alternatives F (each reader under fragments) |
| I11 | fleet repos with coordinator mode hit the same conflicts | OUT-OF-SCOPE | W-480cdb61 (filed 2026-10-30) |
