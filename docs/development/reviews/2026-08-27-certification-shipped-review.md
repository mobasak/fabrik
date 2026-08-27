# Review — the shipped certification surface

Status: CLOSED — coverage-adjudicated exit, final round `found: 0, fixed: 0`

**Surface:** `b94e9ce8 · d612b5fd · 690e9c6f` — `check_certification_coverage.py`, its tests,
`check_doc_sprawl.py`, `CLAUDE.md`, both command sources, the reference doc.

**No agents** — finders native per the operator's standing instruction; every finding reproduced by
execution.

## The finding, and it is one class six times over

**Declared, documented, asserted-by-tests — and never consumed.** Which is precisely the defect this
whole plan exists to remove, committed inside the code that removes it.

| Constant | State as shipped |
|---|---|
| `REGISTRY_BY_TYPE` | DEAD — the per-type registry table was read by nothing |
| `DECLARATION_KEY` | DEAD — **nothing ever opened `project.yaml`** |
| `RETIRED_TYPES` | DEAD — asserted by a test, consulted by no code |
| `TERMINAL` | DEAD |
| `CERT_LOCK_DIR` | DEAD |
| `check_doc_sprawl.CERT_BOARD_RE` | **DEFINED AND NEVER ADDED TO `ALLOWED_PATTERNS`** |

The last one is severe and was shippable-breaking. Proven, not argued:

```
$ python scripts/enforcement/check_doc_sprawl.py --strict
  BLOCKED: docs/development/certifications/2026-08-27-cert-probe/2026-08-27-cert-probe.md
  BLOCKED: docs/development/certifications/2026-08-27-cert-probe/TC01-probe.md
  BLOCKED: docs/development/certifications/2026-08-27-cert-probe/ledger.md
  exit=1
```

**The first project to run the new certification contract would have had its board rejected by the
gate.** The `CLAUDE.md` allowlist row I committed was prose with dead code behind it.

The Phase-B declaration contract was equally inert: the plan says the denominator is declared in
`project.yaml::certification_registry`, the reference doc explains the precedent, a test asserts the
key's value — and no code path opened the file. `resolve_registry()` now does, and reports
`declared` / `fallback:<type>` / `retired:<type>` / unknown, so an undeclared fallback is as
auditable as a declared source.

## Why the tests did not catch it

They asserted the constants' **contents**, not their **effect**:
`test_the_registry_table_covers_every_live_scaffold_type` checked the table was total;
`test_the_declaration_key_follows_the_shipped_precedent` checked the key's name. Both pass whether or
not anything reads them. A constant being *correct* says nothing about it being *consulted*.

Added: `test_a_declared_registry_is_actually_read`, `test_no_module_constant_is_dead` (a mechanical
sweep for defined-but-unreferenced module constants), and an end-to-end assertion that a real
`TC##` path is permitted by `ALLOWED_PATTERNS` while a `T##` path on a cert board is not.

## Two of my own mutations were wrong before they were right

- Commenting out `# CERT_BOARD_RE,` left the test GREEN — a substring check passes on a
  commented-out line. Same blindness as matching prose that quotes the thing it forbids. The
  assertion now requires an ACTIVE, uncommented entry and proves it end-to-end.
- The dead-constant mutation (renaming the consuming function) did not create a dead constant at
  all. Re-run by injecting a genuinely unreferenced constant; then RED.

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | **declared-but-never-consumed** | FIXED (6) | mechanical sweep: 0 dead constants remain |
| 2 | **inert allowlist** | FIXED (1) | cert board permitted; `T##` on a cert board still blocked |
| 3 | **test asserts contents not effect** | FIXED (1) | effect-asserting tests added |
| 4 | **fail-open vs fail-closed** | CLEAN | exit-0 contract intact on every path |
| 5 | **behavior-without-a-test** | CLEAN | 53 tests |

## Pass Ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| Pass 1 (WIDE) | native, 6 classes | 6 | 6 | 6 |
| **Pass 2 (terminal)** | native, same 6 re-swept | **0** | **0** | **0** |

## Verification

```
$ python -m pytest tests/enforcement/test_certification_coverage.py -q
53 passed

$ python scripts/final_gate.py --check --json
"status": "success"  (50 passed / 0 failed)
```

---

# Second pass — re-invoked on the fixed surface (34d7fab6)

Status: CLOSED — `found: 0, fixed: 0` on the confirming round.

Two more, both invisible to the first pass because it hunted the CODE and these live in what the code
change *removed* and what it *inferred*.

**1 — the Phase-C rewrite silently deleted a real constraint from BOTH commands.** The old Phase-1
text carried: *"every `features[]` row maps to the scenario IDs that exercise it — and a feature with
zero mapped scenarios cannot be reported as working."* My replacement sliced from the `Output:` line
to the next heading and did not carry that clause forward. The new block covers the open-row half
(`UNVISITED` blocks the close) and dropped the traceability half.

That is the **same class as the earlier "cross-check declared and never graded" finding**: the plan
demotes `docs/FEATURES.md` to a cross-check and insists its bidirectional-reconciliation value is
kept — then the rewrite deleted the one clause that made it real. **Demoting is not discarding.**
Restored in both sources and re-rendered; pinned by a test that reads both files.

**2 — the resolver produced a FALSE DECLARATION.** `resolve_registry` had a fallback branch reading a
bare `source:` key as the declaration whenever the file mentioned `certification_registry` anywhere.
Reproduced:

```
project.yaml:  type: saas-skeleton
               # certification_registry is planned      <- a COMMENT
               external_systems:
                 source: stripe                          <- unrelated key
resolved:      how="declared"  source="stripe"           <- ⚠ FALSE
```

A denominator inferred from an unrelated key is worse than an honest fallback, because `declared` is
the one state that means *a human chose this*. The branch also re-read the whole file per line.
Removed; only the declaration key counts now. Verified the four real projects on the box still
resolve (`transdoc`/`tryton-crm` → `fallback:saas-skeleton`, `job-agent` →
`fallback:chrome-extension`, `whatsapp-agent` → `fallback:python-api`).

**Watched-fail-first, by accident and worth recording:** the removal edit did not apply on its first
attempt (ruff had reformatted the target), so the new test ran RED against the unfixed code before
the fix landed — the strongest evidence a test discriminates, obtained because the edit failed.

## Pass Ledger (second pass)

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| Pass 1 | native, 6 classes | 2 | 2 | 2 |
| **Pass 2 (terminal)** | native, same 6 re-swept | **0** | **0** | **0** |

55 tests · gate green · corpus re-rendered, `--check` reports installed == rendered.
