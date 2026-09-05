# Review — 3833fb16: four peer-reported defects in synced machinery

Status: IN-PROGRESS — pass 1 in flight.

Surface: commit `3833fb16` (parent `76c86221`), `git show --format= 3833fb16 -- <9 paths>` = 588 diff lines. Anchor: NO MATCH for this scope (the nearest report, `2026-08-31-mail-fixes-review.md`, covers a different commit set).

## Scope

| path | change |
|---|---|
| `scripts/final_gate.py` | armed-pytest leg: the sentinel runs the suite on any change; the prefix gate stays for the CI-text fallback |
| `scripts/enforcement/check_doc_sync.py` | `_is_orm_model` content probe gates the `models.py` filename trigger |
| `scripts/mail.py` | D-035 headers accept a spaced em/en dash as the separator |
| `commands/_sources/fabrik-review.md` + `scripts/enforcement/check_review_coverage.py` | rotation rule past 200 KB; `*-archive.md` skipped |
| four test files | graders, each red on revert; three ruff-reflowed |

Blast radius: all nine paths are governance-sync trigger surfaces (45 repos).

## Rubric (`review_rubric.py --changed <9 paths>`, 162 lines)

FLOOR: core/35 · core/25 · core/30 · 12-FACTOR. MATCHED: core/10-python (three scripts), core/40-documentation (the command source), core/45-testing-strategy (four tests).

## Coverage Checklist

| # | class | verdict | evidence |
|---|---|---|---|
| C1 | fail-open / fail-silent (final_gate armed leg; doc_sync unreadable/deleted paths) | FIXED(1) | deleted/unreadable `models.py` keeps the demand (fail closed); the staged-blob read (`_staged_text`) closes the working-tree-vs-index gap gemini found — a Pydantic file staged then edited to ORM unstaged no longer flips the verdict; `_blob` was CHANGELOG-only by construction and my first draft called it — the grader caught it |
| C2 | false positive / false deny (doc_sync markers; mail dash; coverage archive skip) | FIXED(3) | doc_sync false negatives closed: SQLAlchemy registry-mapped (`__table__`/`registry(`/`.mapped` — own pass, executed), Pony `db.Entity` (pool p1); false positives named, not held: marker words in comments/docstrings and a Pydantic-local `Column(` helper fail toward the demand (the old verdict); mail: a `WHY —` line inside another section IS a header by contract (any_header keys on line start — refuted) |
| C3 | boundary / sentinel / prefix (the `_armed` clause vs the three prefixes; `-archive.md` suffix; `[^:\n`]` qualifier) | FIXED(1) | `models.PY` bypassed the probe on suffix case (regex is IGNORECASE; suffix was not) — `.lower()`; the `_armed` clause still ANDs `tests/`; `[^:\\n`]{0,120}` bound is pre-existing (named) |
| C4 | behaviour without a test / vacuous grader (four graders; the seeded tracked schema dump) | FIXED(1) | the mirror test re-implemented the prefix check and pinned two lines — the whole 12-line condition is now pinned; proven: final_gate at its parent reds the pin. The doc_sync grader seeds a TRACKED dump because the old trigger exempted repos without one (the first draft was vacuous — caught by red-on-revert). Reflow: parent-formatted vs committed differ only by my additions (37/0, 28/5 = the rewritten 01M1J0KY test, 43/0) |
| C5 | cost / quota accounting (armed repos now run the suite on docs-only diffs) | CLEAN | measured: 5 of 43 /opt repos are armed and ALL 5 have .py outside the three prefixes (site-provisioner 66, transdoc 92, youtube 275, trade-intelligence 40, brand-identiy-creator 29) — they now run their suite on every change; direction fail-open → fail-closed, cost named in the CHANGELOG |
| C6 | staged blob vs working tree (doc_sync reads the working-tree file) | FIXED(1) | see C1: the probe grades `git show :path`, working tree only as the intent-to-add fallback (grader: stage Pydantic, edit to ORM unstaged → no demand) |
| C7 | doc / prose consistency (rotation rule executable as written; CHANGELOG claims) | CLEAN | the rotation rule names what moves (per-round finding tables older than the last three passes, by position) and what stays; pool p3 read it as executable |
| C8 | sibling readers of the same surface (check_convergence's own `_changed_md`; the md allowlist) | FIXED(1) | executed: an untracked archive is skipped by check_convergence as an in-flight draft, a staged (intent-to-add) archive draws 0 mentions from check_convergence and check_doc_sprawl; the new-.md allowlist regex is `docs/development/reviews/.+-review\\.md$` — a `…-review-archive.md` does NOT match it (`-archive.md` ≠ `-review.md`) — FIXED in pass 2 (see below) |
| C9 | blast radius per fix across 45 repos (direction of each verdict flip) | CLEAN | per fix: armed repos (5) fail-open → fail-closed; `models.py` files: 40 on the box, 1 ORM-marked, 39 Pydantic-shaped (fabrik-lib copies) — the false positive was the majority case, direction blocking → passing; mail authors using dashes: false-missing → credited; long reviews: rotation is opt-by-size |
| C10 | reflow safety (three test files re-formatted) | CLEAN | see C4: reflow proven additive-only |

## Pass Ledger

| Pass | method | found | new | fixed | finders |
|---|---|---|---|---|---|
| Pass 1 | method: citation | found: 7 | new: 7 | fixed: 7 | finders: pool MF1 (5 partitions, dispatched 5, returned 5, $0.032, all scored: p0 mirror pin (real), p1 staged-vs-working-tree + suffix case + Pony (real ×3; comments/deletion named), p2 mail (2 refuted, 1 named), p3 CLEAN, p4 (1 named)) + orchestrator by execution (registry-mapped ORM false negative; archive file vs check_convergence/doc_sprawl when untracked AND staged; the allowlist regex `.+-review\\.md$` rejecting `…-review-archive.md` — a Pydantic/ORM census of 40 models.py; armed-repo census 5 of 43; reflow proof). All 7 fixed with graders red on revert; the first draft of the staged read called the CHANGELOG-only `_blob` and its own grader caught it |

## Per-phase verdicts

(one `### Phase N — <path>` per changed script at the close)

## Gate

(re-measured at the close, never inherited)
