# Design spec — activating check_doc_sprawl (the permanently-green blocking check)

Status: EXECUTED 2026-08-15 — activation landed (see below); the orphan disposition was answered
DELETE by intel, who removed 74 copies fleet-wide; final fleet state at activation: 2 blocking
files in ONE repo, already red on check_structure for the identical files.
Prior: CONVERGED (2026-08-14 — /fabrik-spec-review: 3-pass loop. Pass 1 OVERTURNED this spec's
own central claim: the two flagged docs are NOT fabrik-synced (no script mentions them, absent
from synced.lock, hub copies untracked, gitignore_dest_paths already emits a reference-docs
group) — they are orphaned bulk copies, so "close the sync gap" became "disposition the orphans",
a named BLOCKING decision for intel + the operator. Pass 2: two coherence edits. Closing pass:
raised 0, edits 0, md5 1cf714bd053376058ae8647ade1fd074 stable, numeric claims re-verified live
(44 / 30 repos). AWAITING the orphan disposition + operator approval to plan.)
Date: 2026-08-14 · Owner: infra

## The problem

`scripts/enforcement/check_doc_sprawl.py` has been **inert in both call paths** since at least
2026-08-04 (its own in-file comment says so):

- `final_gate.py:1064` executes it as a script — it has no `__main__`, so it always exits 0.
- `validate_conventions.py:117-119` imports `check_file`, which feeds a RELATIVE path into
  `relative_to(abs)` → `ValueError` → `[]`.

It was left inert deliberately, on the belief that "activating it is a fleet-behavior change
(every project with stray .md files would newly red)". fabrik-lib then wired it BLOCKING in
their own gate and read `OK Doc Sprawl` for months while it checked nothing (mail 01M00TWS91) —
a known defect rediscovered by a consumer is the trigger for this spec.

## Grounded facts (measured this session, 2026-08-14)

**The blocking fear is FALSE.** The rule is default-deny for **NEW (untracked)** `.md` files
only — tracked docs are grandfathered (`is_tracked()` short-circuits). Measured across all 43
git repos under `/opt`, applying the check's own `ALLOWED_NEW_ROOT_DOCS` / `ALLOWED_NEW_DOCS_SCAFFOLD`
/ `ALLOWED_PATTERNS`:

| Result | Count |
|---|---|
| repos scanned | 43 |
| repos that would newly RED | **14** |
| total blocking files | 2272 |
| …of which `rnfinal` alone | 2230 |

And the composition is the real finding — **none of it is the sprawl the check was written for**
(new project docs invented ad hoc); it is two mechanical classes plus a handful of real cases:

1. **12 of the 14 repos red on 1–2 files, and they are the SAME two files everywhere:**
   `docs/reference/ai_agent_prompt_directives.md` and `docs/reference/AI_TAXONOMY.md`. Re-probed
   at review time, and the first framing of this spec was WRONG — they are **not fabrik-synced
   at all**:
   - no hub script mentions either filename (`grep` over `scripts/`, `src/fabrik/`, `commands/`,
     `.claude/`: zero matches);
   - they are absent from a project's `.fabrik/synced.lock` (204 entries in `/opt/meb`);
   - `gitignore_dest_paths()` (`fabrik_synced_manifest.py:147-172`) DOES already emit a
     `"Reference docs (synced from fabrik)"` group — so there is no missing-group bug;
   - the **hub's own copies are untracked too** (`git ls-files` returns nothing for either);
   - they exist in **44 repos** (prompt_directives) / **30 repos** (AI_TAXONOMY), byte-identical
     (`md5 77385e0a…` across repos) with a **single shared mtime** each (2026-05-30 17:40 and
     2026-06-25 13:08).
   Verdict: these are **orphaned bulk-copied artifacts** — a one-off fleet-wide copy that was
   never adopted into the sync manifest and never tracked anywhere. A third class, distinct from
   both "sprawl" and "synced", and the check is RIGHT to flag them: they are unfiled by
   definition.
2. **`rnfinal`'s 2230 are `node_modules/**/*.md`** (its `.gitignore` does not cover
   `node_modules/`, so `--exclude-standard` does not filter them). The check has **no
   vendor-directory guard** — any JS project with an unignored dependency tree would red on
   thousands of third-party READMEs.
3. Residual genuine candidates after those two classes: a handful, single digits.

## Approach (single — the fear was the only alternative)

Settle the orphan disposition and fix the two code causes FIRST, then activate. No allowlist
migration is required (that assumed cost does not exist), and the three steps are independent —
only step 1 needs an owner's answer.

1. **Disposition the orphaned bulk copies** (BLOCKING decision, not a code fix — clears 12 of
   the 14 repos whichever way it goes). Three legitimate answers, and the owner picks:
   (a) **adopt** — add both to `REFERENCE_DOCS` in the manifest, commit the hub copies, re-sync:
   they become properly owned, ignored in projects, and updatable from one place;
   (b) **delete fleet-wide** — if they are stale one-off output nobody reads;
   (c) **track per-repo** — if each project legitimately owns its own copy.
   ⚠️ Ownership note: `AI_TAXONOMY.md` is AI-model documentation, which is **intel's beat**, and
   its 2026-06-25 timestamp coincides with intel's AI-taxonomy work. This decision is routed to
   intel + the operator BEFORE the activation lands, not assumed by infra.
2. **Add a vendor guard to the check** — skip `node_modules/`, `vendor/`, `.venv/`, `dist/`,
   `build/`, `site-packages/`. A default-deny doc policy must never adjudicate third-party
   files. Clears `rnfinal` + `rn-kit-sandbox`.
3. **Give the script a `__main__`** (repo-scan mode, exit 1 on violations) so the `final_gate`
   invocation is real, and **fix the `relative_to` ValueError** in the `check_file` path so
   `validate_conventions` works too. Both paths must be non-vacuous — a check wired BLOCKING
   must have a non-zero exit path (fabrik-lib's corollary, adopted).
4. **Activate**, then re-measure: the expected post-fix number is single-digit blocking files
   fleet-wide, each a genuine unfiled doc.

## Requirements → acceptance

| # | Requirement | Acceptance |
|---|---|---|
| 1 | Both call paths non-vacuous | red-first test: a violating untracked .md makes `python scripts/enforcement/check_doc_sprawl.py` exit 1 AND `validate_conventions` return a finding |
| 2 | Orphans dispositioned | after the owner's choice lands (adopt/delete/track), `git -C /opt/<project> ls-files --others --exclude-standard '*.md'` no longer lists `ai_agent_prompt_directives.md` or `AI_TAXONOMY.md` on ≥3 sample repos |
| 3 | Vendor dirs never adjudicated | test: a violating path under `node_modules/` is ignored; the same path outside it is blocked |
| 4 | Grandfathering preserved | test: a tracked .md that violates the allowlist stays green (edits to existing docs are always allowed) |
| 5 | Fleet blast radius measured post-fix | the measurement script re-run, result recorded in the plan's Evidence, expected <10 files total |
| 6 | No silent-green regression | `run_optional_check`'s missing-script GREEN is a separate approved workstream; this spec must not depend on it |

## Named BLOCKING unknown

The orphan disposition (approach step 1) must be answered by intel + the operator before
activation, because activating first would red 12 repos on files nobody has decided about. It is
NOT a research gap — the facts are measured above; it is an ownership decision with three valid
answers. Everything else in this spec (vendor guard, `__main__`, `relative_to` fix) is
independent and can be built while the decision is pending.

## Out of scope

- Hardening `run_optional_check` (approved separately, same session).
- The sync-excluded-repo governance audit (approved separately).
- Any change to the allowlist policy itself — the rule is not under review, only its execution.

## Risks

- **The orphan disposition is fleet-wide** (44 repos hold at least one copy): "adopt" adds them
  to the sync surface and to every project's ignore block; "delete" removes a file 44 repos have
  had since May/June. Either is reversible (git history on adopt; the byte-identical copies make
  restore trivial on delete), but it is a fleet action and belongs to the owner, not to this
  spec's executor.
- **Activation surfaces real debt** in whichever repos still red after the fixes; each is a
  genuine unfiled doc, and the remedy (file it in an allowlisted location or track it) is
  actionable in-repo. That is the point of the check.
- `rnfinal`'s missing `node_modules/` ignore is a project defect the vendor guard papers over;
  worth a mailed finding to that repo rather than silent absorption.
