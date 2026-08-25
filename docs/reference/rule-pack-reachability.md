# Rule-pack reachability

An advisory gate that catches a `.windsurf/rules` pack claiming it governs a scaffold
type its `globs:` cannot actually reach — a silently-inert governance surface that a
green `select_rules.py` output cannot detect on its own.

- **Engine:** `scripts/enforcement/pack_layout_audit.py::audit_layout(root, types)`.
- **Gate wrapper:** `scripts/enforcement/check_pack_reachability.py` — wired into
  `scripts/final_gate.py` as an ADVISORY (`warn_only=True`) row, "Rule-pack reachability".
- **Tests:** `tests/enforcement/test_pack_reachability.py` (this wrapper),
  `tests/enforcement/test_pack_layout_audit.py` (the shared engine).

## The class of bug this closes

Fabrik's rule packs (`.windsurf/rules/**/*.md`) were largely authored assuming a
**directory-per-concern** layout: `workers/`, `jobs/`, `auth/` as real directories a
glob like `**/workers/**` can match. The actual fabrik scaffolds emit a
**file-per-concern** layout instead: `worker.py`, `billing_routes.py`, `auth.py` — single
files, not directories. A pack written for the first shape and glob-matched against the
second can match **zero paths** in every real project it is meant to govern, and nothing
in the existing pipeline notices: the pack still renders, still gets read when its glob
*does* happen to fire on an unrelated path, and the operator has no signal that its
actual subject matter (worker discipline, audit-log discipline) was silently never
applied. Measured live against `/opt/transdoc` (2026-08-25): `core/75-workers-jobs.md`
and `core/app-audit-log.md` matched zero real paths, while
`transdoc/server/src/transdoc/worker.py` and `billing_routes.py` — exactly what those
packs are meant to govern — sat right there on disk. The result: 19 dead frontend calls,
14 orphan endpoints, and an empty beat loop, with the gate green throughout.

## Why the obvious check is circular

The obvious design is "assert every pack `select_rules.py` marks ACTIVE matches at least
one real path." That check can **never fire**, because `select_rules.py` derives its
ACTIVE/AVAILABLE split from the very same globs under test:

```python
if any(rules_match.any_path_matches(root, g, empty_matches_all=False) for g in globs):
    active.append(entry)
else:
    available.append(entry)
```

A pack with broken globs doesn't end up "ACTIVE but matching nothing" — it just drops to
AVAILABLE, indistinguishable from a pack that is correctly irrelevant to this project.
The search space "ACTIVE and matches zero paths" is empty by construction. This was
directly confirmed live for both known-inert packs: `core/75-workers-jobs.md` and
`core/app-audit-log.md` sat in AVAILABLE, not ACTIVE, exactly because their globs never
matched anything.

Reachability therefore needs a signal **independent** of the globs under test — a
declared expectation the check can cross-reference against, rather than a
self-referential derivation.

## `applies_to:` — the declared expectation

Each pack's frontmatter can carry an `applies_to:` list naming the scaffold type(s) (from
`src/fabrik/scaffold.py::SCAFFOLD_TYPES`) it is meant to govern, alongside its existing
`globs:`:

```yaml
---
activation: glob
globs: ["**/workers/**", "**/worker/**", "**/worker.py", "**/jobs/**", ...]
applies_to: ["file-worker"]
description: Workers & jobs discipline — PG queue, retry/backoff, dead-letter, ...
trigger: glob
---
```

Chosen over a central registry (e.g. a `types -> packs` table maintained separately)
because a registry drifts from the pack silently — exactly the same failure class this
subsystem exists to close, just moved one layer up. Keeping the declaration in the pack's
own frontmatter, beside the globs it cross-checks, means the two can never disagree about
which pack they describe.

Two packs already carry it (the two the live transdoc finding named):
`.windsurf/rules/core/75-workers-jobs.md` (`applies_to: ["file-worker"]`) and
`.windsurf/rules/core/app-audit-log.md` (`applies_to: ["saas-skeleton"]`).

### Adding `applies_to` to a pack

1. Identify which `SCAFFOLD_TYPES` (see `src/fabrik/scaffold.py`) the pack is actually
   meant to govern — read the pack's own "Applicability" / "When to Use" section.
2. Add `applies_to: ["type-one", "type-two"]` to the frontmatter, next to `globs:`.
3. Run `python scripts/enforcement/check_pack_reachability.py` (or
   `pack_layout_audit.py` directly) to confirm the pack's globs actually reach something
   a fresh scaffold of that type emits. If they don't, the globs need fixing — not the
   `applies_to` declaration.
4. `activation: manual` packs (the four `00-domain-*` packs — loaded by path, not by
   glob) are excluded entirely from this check by design; adding `applies_to` to one has
   no effect and is not required.

A pack with **no** `applies_to:` field is not flagged either way — see below.

## Behavior contract

1. **A pack whose `applies_to` names a scaffold type it cannot match is REPORTED.**
   Applicability comes from `applies_to`, never from whether the pack's globs happen to
   match anything — that would be the same circularity described above, just moved into
   this check instead of `select_rules.py`.
2. **A pack with no `applies_to` field passes silently.** This lets the field land
   incrementally across the ~56-pack corpus without turning the fleet gate red on day
   one for packs nobody has annotated yet.
3. **The check reports the count of packs it actually examined** — i.e. glob-activated
   (non-`manual`) packs whose `applies_to` names at least one of the scaffold types being
   checked. Row 2's silence makes "0 findings" the default outcome for an unannotated
   corpus; row 3 is what stops that silence from being misread as "everything checked
   out." A corpus where nobody has declared `applies_to` prints `Examined 0 pack(s)` and
   an explicit "NOTHING TO CHECK" line — never an unqualified `OK`.

## Non-circularity, proven directly

`tests/enforcement/test_pack_reachability.py::test_row1_non_circularity_check_reports_select_rules_calls_it_available`
builds a fixture pack whose globs match nothing in a synthetic project tree AND whose
`applies_to` claims a scaffold type. It asserts BOTH:

- `select_rules.collect()` places that pack in `available`, never `active` (the real,
  unpatched ACTIVE/AVAILABLE split its glob-matching produces).
- `check_pack_reachability` still examines and reports it as unreachable.

That contrast — one signal says "not my concern" while the other still asks the
question — is the concrete demonstration that reachability here is driven by the
declared `applies_to`, not derived from `select_rules`' ACTIVE set.

## Running it

```bash
python scripts/enforcement/check_pack_reachability.py            # human-readable
python scripts/enforcement/check_pack_reachability.py --json      # machine-readable
python scripts/enforcement/check_pack_reachability.py --types file-worker saas-skeleton
```

Exit code is always `0` on a completed run (advisory contract) — a non-zero exit means
the check itself failed to run (e.g. the live `SCAFFOLD_TYPES` registry could not be
resolved), never that a pack was found unreachable. Findings and the examined count are
Findings and the examined count are printed to stdout on every run that COMPLETES. The one non-completing path — the hub scaffolder being unreachable — prints its explanation instead and still exits 0; it does not print a findings list or a count, because it has neither. (An earlier version of this sentence said "regardless of exit status", which was false in precisely the case where it would have mattered.)

## Cross-ticket seam proof (T02 x T03 x T04 agree)

Three tickets independently touch the same "does this pack's glob reach this scaffold
type's output" question — `pack_layout_audit.audit_layout()` (T02), the gate wrapper
`check_pack_reachability.py` that reuses it (T03), and the shared path/glob matcher
`rules_match.packs_for_paths()` (T04), which answers the same question through a
*different* call path (`pack_matches_path` + `_prefixes` vs. `audit_layout`'s direct
`_tail_matches` loop over pre-fetched emitted paths). An executable check run against
the live corpus for both packs that currently declare `applies_to:` — including a
negative control asking each pack about a scaffold type it does *not* claim — confirms
all three agree, with no disagreement papered over:

```
$ /opt/fabrik/.venv/bin/python /tmp/.../seam_proof.py
{
  "fixtures": [
    {
      "pack": "core/75-workers-jobs.md",
      "claimed_type": "file-worker",
      "emitted_path_count": 254,
      "positive": {
        "T02_audit_layout_reachable": true,
        "T03_examined_pack": true,
        "T03_reachable": true,
        "T04_packs_for_paths_reachable": true,
        "AGREE": true
      },
      "negative_control": {
        "unclaimed_type": "saas-skeleton",
        "T02_is_finding (must be False)": false,
        "T03_examined (must be False)": false,
        "AGREE": true
      },
      "AGREE": true
    },
    {
      "pack": "core/app-audit-log.md",
      "claimed_type": "saas-skeleton",
      "emitted_path_count": 359,
      "positive": {
        "T02_audit_layout_reachable": true,
        "T03_examined_pack": true,
        "T03_reachable": true,
        "T04_packs_for_paths_reachable": true,
        "AGREE": true
      },
      "negative_control": {
        "unclaimed_type": "file-worker",
        "T02_is_finding (must be False)": false,
        "T03_examined (must be False)": false,
        "AGREE": true
      },
      "AGREE": true
    }
  ],
  "OVERALL_AGREE": true
}
```
(exit code 0 — the script asserts `OVERALL_AGREE` and fails the process on any
disagreement; it is a throwaway integration-ticket receipt, not a shipped script.)

## Promotion to blocking

This check is **advisory only** (`warn_only=True` in `scripts/final_gate.py`) by design.
Landing it as a blocking gate on day one — with most of the ~56-pack corpus carrying no
`applies_to` declaration yet, and the two known-inert packs not yet the only offenders —
would fail every one of the ~46 synced repos in one commit and train operators to ignore
the gate. Promoting this row from advisory to blocking is a deliberate **operator**
decision, made once the corpus has been swept and `applies_to` coverage is judged
sufficient — never something a future edit to this script decides unilaterally.
