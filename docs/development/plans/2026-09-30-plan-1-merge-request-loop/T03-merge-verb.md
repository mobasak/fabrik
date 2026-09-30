# T03 — merge_request.py merge and resume: the one data-safe merge path

## Scope
Implements spec § The delta 5 and the § Data-safety invariants, plus residuals O35, O36, the invariant-(3) wording and the `git commit -a` warning (spec § U4, W-8a6a5644). In `scripts/merge_request.py`: `merge [<id>]` holds an exclusive flock on `<git common dir>/fabrik-merge.lock` for its whole run and writes `<git common dir>/fabrik-merge/<id>.json` per claimed request (the run's OWN pid and its `/proc` start time — O36 — plus phase and merge SHA); resumes a stranded record (short of `replied`, its process gone) first, then takes the oldest unclaimed `merge-request` addressed to the owner with `ack: required` (the mailbox read of `scripts/mail.py:1703` `list_msgs`); steps (a) preflight — fetch, refuse if origin is ahead (a START condition only), build in a throwaway detached worktree with the message `merge(<agent>): <branch> — request <id>, item <item>`, snapshot every merged path and refuse on an untracked collision, a dirty non-ledger path, a dirty path the merge deletes or renames, a staged-only difference, or a conflicting 3-way ledger carry computed with `git merge-file -p`; (b) auto-resolve only pure-insertion conflicts on the five ledgers, newest first for DECISIONS, then a line-anchored marker check; (c) the owner's tests — `.fabrik/merge-tests` read with `git show <base>:` else pytest over touched `tests/` files — with the worktree's `src` first on `PYTHONPATH` and a `fabrik-lib` sibling link when vendored; (d) re-hash against the snapshot, then `git update-ref <base> <new> <old>`, rebuilding (a)-(c) in full up to 3 times on a change or a moved ref; (e) re-hash, carry, `git reset -q <new> -- <carried paths>`, a raced path keeping the owner's edit with its index at the merge and a `git commit -a` warning in the reply; (f) fast-forward push, a rejection finished by `resume` through a catch-up merge of origin's base EXEMPT from (a)'s origin-ahead refusal (O35); (g) the governance sync in the hub when the re-derived files match the filter; (h) reply to requester and coordinator, then `mail.py ack` done with `--merge-sha` or blocked with `--reason`. `resume <id>` continues from the recorded phase, and skips to (e)-(h) with the existing merge commit (found by the request id) when `head` is already in base.

Depends: T02
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_merge_request_merge.py -q
Docs: none (the model doc is T06's)

## Touches
- scripts/merge_request.py — PRIMARY PATH
- tests/test_merge_request_merge.py

## Behavior Contract
- **Given** a fixture repo whose main checkout has dirty `CHANGELOG.md` and `docs/DECISIONS.md` WIP and a worktree branch adding a CHANGELOG entry and a D-row, **When** `merge_request.py merge` runs, **Then** base advances by one merge commit, the sibling WIP survives byte-for-byte, and the requester and coordinator each get a reply (spec § Validation V4)
- **Given** in turn an untracked collision, a dirty non-ledger merged path, a dirty path the merge deletes, a staged-only difference, a ledger conflict where a side edits an existing line, and a red owner test, **When** `merge` runs, **Then** each refuses and origin, the local base and the main checkout are byte-identical to before (spec § Validation V5)
- **Given** origin ahead of local base at start, **When** `merge` runs, **Then** it refuses; **Given** the local base moved during the build, **Then** it rebuilds with a fresh snapshot and tests and refuses after 3 (spec § Validation V6)
- **Given** a push rejected because origin moved and a main checkout with unstaged WIP, **When** `resume <id>` runs, **Then** it finishes by a catch-up merge — no rebase, no stash, the WIP intact, the request's merge commit still an ancestor of the pushed base (spec § Validation V7d; W-8a6a5644 O35)
- **Given** a coordinator copy in the inbox beside the owner's request, **When** `merge` picks, **Then** it takes the owner's; **Given** a record short of `replied` whose recorded pid is dead, **Then** it is resumed first; whose recorded pid is the live run's own, **Then** it is not stranded (spec § Validation V7; W-8a6a5644 O36)
- **Given** a request whose `head` is already an ancestor of base, **When** `resume <id>` runs, **Then** no second merge is made and the reply names the existing merge commit (spec § Validation V7)
- **Given** a merged path edited after the snapshot and before the CAS, **When** `merge` runs, **Then** it returns to the preflight instead of writing it; **Given** a `.fabrik/merge-tests` edited on the branch, **Then** the base's copy is the one run (spec § Validation V7c, V7d)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/10-python.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- scripts/mail.py
- scripts/governance_sync_postcommit.sh
- tests/test_merge_sync.py
