# Design spec — activating check_doc_sprawl (the permanently-green blocking check)

Status: DRAFT (operator approved the activation path 2026-08-14; this spec defines it)
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

And the composition is the real finding — **almost none of it is sprawl**:

1. **12 of the 14 repos red on 1–2 files, and they are the SAME two files everywhere:**
   `docs/reference/ai_agent_prompt_directives.md` and `docs/reference/AI_TAXONOMY.md` — hub
   REFERENCE_DOCS distributed by governance-sync that are **not covered by the generated
   `.gitignore` "Fabrik-synced" block**, so they appear as untracked project files. This is a
   **sync-manifest gap**, not doc sprawl.
2. **`rnfinal`'s 2230 are `node_modules/**/*.md`** (its `.gitignore` does not cover
   `node_modules/`, so `--exclude-standard` does not filter them). The check has **no
   vendor-directory guard** — any JS project with an unignored dependency tree would red on
   thousands of third-party READMEs.
3. Residual genuine candidates after those two classes: a handful, single digits.

## Approach (single — the fear was the only alternative)

Fix the two structural causes FIRST, then activate. Nothing else is needed, and no allowlist
migration is required (the original plan's assumed cost does not exist).

1. **Close the sync gap** — `gitignore_dest_paths()` (`fabrik_synced_manifest.py:147`) must emit
   the REFERENCE_DOCS group so projects ignore what the hub distributes to them. Clears 12 of
   the 14 repos at a stroke, and fixes a real bug independent of this spec: synced files
   showing as untracked project noise.
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
| 2 | Sync gap closed | after re-sync, `git -C /opt/<project> ls-files --others --exclude-standard '*.md'` no longer lists any hub-synced reference doc (checked on ≥3 projects) |
| 3 | Vendor dirs never adjudicated | test: a violating path under `node_modules/` is ignored; the same path outside it is blocked |
| 4 | Grandfathering preserved | test: a tracked .md that violates the allowlist stays green (edits to existing docs are always allowed) |
| 5 | Fleet blast radius measured post-fix | the measurement script re-run, result recorded in the plan's Evidence, expected <10 files total |
| 6 | No silent-green regression | `run_optional_check`'s missing-script GREEN is a separate approved workstream; this spec must not depend on it |

## Out of scope

- Hardening `run_optional_check` (approved separately, same session).
- The sync-excluded-repo governance audit (approved separately).
- Any change to the allowlist policy itself — the rule is not under review, only its execution.

## Risks

- **Sync-gitignore change is fleet-wide** (~46 projects): it only ADDS ignore entries for files
  the hub already owns, so the worst case is a project that had deliberately committed a copy of
  a synced doc — measurable before shipping (`git ls-files` for those paths per repo).
- **Activation surfaces real debt** in whichever repos still red after the fixes; each is a
  genuine unfiled doc, and the remedy (file it in an allowlisted location or track it) is
  actionable in-repo. That is the point of the check.
- `rnfinal`'s missing `node_modules/` ignore is a project defect the vendor guard papers over;
  worth a mailed finding to that repo rather than silent absorption.
