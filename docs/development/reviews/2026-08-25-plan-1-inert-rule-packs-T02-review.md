# Review — T02 (corpus×type layout audit + the two inert packs) · phase-1 of 2026-08-25-plan-1-inert-rule-packs

Status: IN-PROGRESS

Surface: `scripts/enforcement/pack_layout_audit.py` · `tests/enforcement/test_pack_layout_audit.py` ·
`.windsurf/rules/core/75-workers-jobs.md` · `.windsurf/rules/core/app-audit-log.md`.
Commits: `f562b49f` (build) · `d8ac7d31` (review fix).

## Pass Ledger

| Pass | finders | found | fixed | refuted | notes |
|---:|---|---:|---:|---:|---|
| 1 | pool 3 (deepseek-v3.2-exp, gemini-3-flash, qwen3-max) + orchestrator | 9 | 1 | 2 | 7 overreach candidates weighed and accepted with reasons |
| 2 | confirming round — OWED, not yet run | — | — | — | exit NOT claimed |

`Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + qwen3-max×1 — round 1`

⚠️ **Exit NOT claimed.** Round 1 made a fix, so round 2 is owed.

## FIXED

1. **The audit silently dropped legal YAML** (CONFIRMED). `_parse_extra_frontmatter` extracted
   `applies_to` items with a quotes-ONLY regex:
   `applies_to: ["file-worker"]` → `['file-worker']`, but `applies_to: [file-worker]` → `[]`.
   The bare form is valid YAML and is what an author writes naturally; such a pack parsed to an
   empty list, was skipped, and could NEVER produce a Finding. **The check's own fail-silent-green,
   inside the check built to close that exact class.** Fixed in `d8ac7d31`, pinned across six
   frontmatter shapes by `test_applies_to_accepts_bare_yaml_items`.

## REFUTED — against the code, not by argument

2. *"An `activation:` string inside a description collides with the activation lookup"* —
   `_ACTIVATION_RE` is line-anchored under MULTILINE, so a mid-line occurrence cannot collide.
   Verified with a description containing `"Uses activation: manual strategy internally"`; the pack
   still parsed as `('glob', ['file-worker'])`. Pinned by `test_activation_regex_is_line_anchored`
   so a future loosening of the anchor is caught.
3. *"The module is unsafe on the fleet — it needs the hub-only scaffolder but sits on a synced
   path"* — the concern is right, the defect is not present. `_import_create_project()` DEFERS the
   import inside a function with an `/opt/fabrik` fallback, explicitly reasoning that the file "is
   governance-synced to ~46 projects". **Proven by importing the synced copy from `/opt/transdoc`:
   import OK, guard present, `audit_layout` present.** This is precisely the T04 failure mode NOT
   repeated, and it is why this ticket did not break the fleet.

## WEIGHED AND ACCEPTED — the glob-overreach candidates

A finder listed seven added globs as over-broad (`**/auth.py` matching an OAuth client,
`**/webhooks.py` matching a Slack integration, `**/worker.py` matching a test fixture, and so on).
Real, and accepted with reasons rather than dismissed:

- **Measured, not assumed.** Blast radius across 20 repos: **81 files newly matched in 9 repos**,
  ~4 per repo. Largest single glob `**/auth.py` at 29. Not a false-match explosion.
- **Each new glob is the file-shaped twin of one the pack already carried.** `app-audit-log` already
  globbed `**/auth/login*`, `**/auth/password*`, `**/auth/mfa*` — auth code is already its declared
  domain; `auth.py` is that domain in file-per-concern form.
- **The asymmetry of cost decides it.** A false positive costs an agent one extra pack read. The
  false NEGATIVE cost transdoc 19 frontend calls to routes that did not exist, 14 endpoints with no
  caller, an empty beat-loop body, and a retention purge that never ran — with the gate green and
  296 tests passing.
- Directory globs were KEPT alongside the file forms; nothing was replaced.

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| fail-open vs fail-closed | FIXED | finding 1 — the parser failed OPEN (silently examined nothing) for legal YAML |
| cost/quota/limit accounting | REFUTED | no metered call or quota surface; the audit scaffolds into a throwaway tempdir, cached per type |
| boundary/sentinel/prefix collisions | CLEAN | the `activation: manual` sentinel is the load-bearing one; verified excluded, and the line-anchored regex pinned |
| behavior-without-a-test | FIXED | 7 tests; the parser fix and the refuted collision both pinned |
| fleet-sync blast radius | CLEAN | 81 files across 9 repos measured before accepting; corrected packs verified distributed to 48/49 (the 1 is sync-excluded fabrik-lib) |
| synced-module import safety | CLEAN | deferred hub-only import proven by importing the synced copy from a project |

## Evidence

The fix, measured against a real file-per-concern tree (`/opt/transdoc`, 4694 paths):

```
BEFORE — ALL 17 globs across both packs matched ZERO paths, while
         server/src/transdoc/worker.py and billing_routes.py sat right there.

AFTER
core/75-workers-jobs.md  (12 globs)
   **/worker.py               ->   1   e.g. server/src/transdoc/worker.py
   TOTAL AFTER FIX: 1  (was 0)
core/app-audit-log.md  (13 globs)
   **/billing_routes.py       ->   1   e.g. server/src/transdoc/billing_routes.py
   **/webhooks.py             ->   1   e.g. server/src/transdoc/_vendor/payments/webhooks.py
   **/auth.py                 ->   1   e.g. server/src/transdoc/auth.py
   TOTAL AFTER FIX: 3  (was 0)
```

Synced-module import safety, from a project's own copy:

```
$ cd /opt/transdoc && python3 -c "import pack_layout_audit as p; ..."
IMPORT OK on a synced project — deferred scaffolder lookup, no module-scope src.fabrik
  guard present: True
  audit_layout present: True
```

Cross-ticket seam (orchestrator, independent of T99):

```
pack_layout_audit            imports rules_match: True
check_pack_reachability      imports rules_match: True
check_pack_reachability consumes audit_layout: True
packs with activation:glob AND a non-empty applies_to: ['core/75-workers-jobs.md', 'core/app-audit-log.md']
packs the CHECK reports as examined            : ['core/75-workers-jobs.md', 'core/app-audit-log.md']
AGREE: True
```
