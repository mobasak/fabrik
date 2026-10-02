# T03 — merge_request.py merge and resume: the one data-safe merge path

## Scope
Implements spec § The delta 5 and the § Data-safety invariants, plus residuals O35, O36 and the `git commit -a` warning (spec § U4, W-8a6a5644; the invariant-(3) wording is a spec text fix, T06's). In `scripts/merge_request.py`: `merge [<id>]` holds an exclusive flock on `<git common dir>/fabrik-merge.lock` for its whole run and writes `<git common dir>/fabrik-merge/<id>.json` per claimed request (claimer session, the run's OWN pid and its `/proc/<pid>/stat` start time — O36 — phase reached, merge SHA); a second run that cannot take the lock exits at once, claiming and writing nothing; resumes a stranded record (short of `replied`, and its pid dead OR alive with a different start time) first, then takes the oldest `merge-request` whose `agent:` EQUALS the owner (resolved by T02's resolver — the hub's absolute `decisions.py --merge-owner`) with `ack: required` — `list_msgs` (`scripts/mail.py:1703`) also returns every UNADDRESSED message, so the exact `agent:` filter is the script's — and claims it with `mail.py claim <id>` (`scripts/mail.py:1225`) before building, which moves it out of the inbox; steps (a) preflight — fetch, refuse if origin is ahead (a START condition only), build in a throwaway detached worktree with the message `merge(<agent>): <branch> — request <id>, item <item>`, snapshot every merged path and refuse on an untracked collision, a dirty non-ledger path, a dirty path the merge deletes or renames, a staged-only difference, or a conflicting 3-way ledger carry computed with `git merge-file -p`; (b) auto-resolve only pure-insertion conflicts on the five ledgers, newest first for DECISIONS, then a line-anchored marker check; any other conflict refuses with "rebase on <base> and resend"; (c) the owner's tests — `.fabrik/merge-tests` read with `git show <base>:` else pytest over touched `tests/` files — with the worktree's `src` first on `PYTHONPATH` and, when the main checkout's parent holds a `fabrik-lib` directory (what the repo's tests reach as `../fabrik-lib`), a symlink to it beside the throwaway worktree; (d) re-hash against the snapshot, then `git update-ref <base> <new> <old>`, rebuilding (a)-(c) in full up to 3 times on a change or a moved ref; (e) re-hash, carry, `git reset -q <new> -- <carried paths>`, a raced path keeping the owner's edit with its index at the merge and a `git commit -a` warning in the reply; (f) fast-forward push, a rejection finished by `resume` through a catch-up merge of origin's base EXEMPT from (a)'s origin-ahead refusal (O35); (g) the governance sync in the hub when the re-derived files match the filter; (h) reply to requester and coordinator, then `mail.py ack` done with `--merge-sha` or blocked with `--reason` naming the refused step; the throwaway worktree (and its link) is removed and pruned on every exit, success or refusal. The merge commit message carries `item <item>` so `work.py done <item> --evidence <sha>` accepts it (`scripts/work.py:2859` `_evidence_commit`: a commit whose message names the item id). TEST SEAM: a module-level `on_phase(name)` no-op, called at `after-build`, `before-cas`, `before-carry` and `before-push`, which the tests replace in-process to move a ref or edit a path at that exact point — never an environment variable, so production has no injection path. `resume <id>` continues from the recorded phase, and skips to (e)-(h) with the existing merge commit (found by the request id) when `head` is already in base.

Depends: T02
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_merge_request_merge.py -q
Docs: none (the model doc is T06's)

## Touches
- scripts/merge_request.py — PRIMARY PATH
- tests/test_merge_request_merge.py

## Behavior Contract
- **Given** a fixture repo whose main checkout has dirty `CHANGELOG.md` and `docs/DECISIONS.md` WIP and a worktree branch adding a CHANGELOG entry and a D-row, **When** `merge_request.py merge` runs, **Then** base advances by one merge commit, the sibling WIP survives byte-for-byte, the requester and coordinator each get a reply, and `git worktree list` equals its start with no throwaway directory or link left — as it does after a refusal (spec § Validation V4; § The delta 5 (h))
- **Given** in turn an untracked collision, a dirty non-ledger merged path, a dirty path the merge deletes, a staged-only difference, a ledger conflict where a side edits an existing line, and a red owner test, **When** `merge` runs, **Then** each refuses and origin, the local base and the main checkout are byte-identical to before (spec § Validation V5)
- **Given** origin ahead of local base at start, **When** `merge` runs, **Then** it refuses; **Given** the local base moved during the build, **Then** it rebuilds with a fresh snapshot and tests and refuses after 3 (spec § Validation V6)
- **Given** a push rejected because origin moved and a main checkout with unstaged WIP, **When** `resume <id>` runs, **Then** it finishes by a catch-up merge — no rebase, no stash, the WIP intact, the request's merge commit still an ancestor of the pushed base (spec § Validation V7d; W-8a6a5644 O35)
- **Given** a coordinator copy and an UNADDRESSED `merge-request` in the inbox beside the owner's request, **When** `merge` picks, **Then** it takes only the owner's and claims it before building, so it leaves the inbox; **Given** a record short of `replied` whose recorded pid is dead, or alive with a different start time (a reused pid), **Then** it is resumed first; whose recorded pid and start time are the live run's own, **Then** it is not stranded; **Given** a run holding the merge lock, **When** a second `merge` or `resume` starts, **Then** it exits without claiming, building or writing a record (spec § Validation V7, invariant 6; W-8a6a5644 O36)
- **Given** a merged path edited between the CAS and the carry (`on_phase('before-carry')`), **When** the carry runs, **Then** its working copy keeps the edit, its index entry equals the merge, and the reply lists the path with a warning that a later `git commit -a` would revert the merge there (spec § The delta 5 (e); W-8a6a5644)
- **Given** a request whose `head` is already an ancestor of base, **When** `resume <id>` runs, **Then** no second merge is made and the reply names the existing merge commit (spec § Validation V7)
- **Given** a merged path edited after the snapshot and before the CAS, **When** `merge` runs, **Then** it returns to the preflight instead of writing it; **Given** a `.fabrik/merge-tests` edited on the branch, **Then** the base's copy is the one run (spec § Validation V7c, V7d)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/10-python.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- scripts/merge_request.py
- scripts/mail.py
- scripts/decisions.py
- scripts/governance_sync_postcommit.sh
- .pre-commit-config.yaml
- tests/test_merge_sync.py
