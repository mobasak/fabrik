# Whole-plan review — 2026-08-25-plan-1-inert-rule-packs

Status: IN-PROGRESS

Cumulative surface: `git diff 4a9731ca..HEAD` across `scripts/`, `commands/`, `tests/`,
`.windsurf/rules/`, `docs/reference/`. Five Board units (T01, T02, T03, T04, T99), fifteen commits.

## Pass Ledger

| Pass | finders | found | fixed | refuted | notes |
|---:|---|---:|---:|---:|---|
| 1 | per-ticket rounds (pool 4 + native Opus ×2, T01/T04) | 22 | 6 | 6 | incl. a LIVE 48-repo fleet break |
| 2 | per-ticket round (pool 3, T02) | 9 | 1 | 2 | 7 overreach candidates weighed |
| 3 | orchestrator acceptance (T03) + T99 integration | 1 | 1 | — | T99 found a BLOCKING INDEX drift no ticket review could see |
| 4 | D7 whole-plan: pool 5 axes + native Opus authoritative | 12 | 12 | 0 | the heaviest round — incl. an advisory check REWRITING tracked hub files |
| 5 | D7 confirming (4 axes) | 3 | 3 | 0 | finding 13 + the TWO defects its own first two fixes introduced |
| 6 | D7 confirming (4 axes) | 3 | 3 | 0 | ⚠️ first dispatch returned 4 EMPTY units — recorded as FAILED, not clean, and re-run |
| 7 | D7 confirming (4 axes) | 2 | 2 | 4 | an uncaught ValueError a round-6 finder had explicitly DISMISSED on a false premise |
| 8 | D7 confirming (4 axes) | 2 | 2 | 0 | 5th false claim: pack-count vs pair-count |
| 9 | D7 confirming (4 axes) | 1 | 1 | 1 | applies_to dropped a 3rd legal YAML form |
| 10 | D7 confirming (4 axes) | 2 | 2 | 0 | BOTH were defects in rounds 4 and 8's own fixes |
| 11 | D7 confirming (4 axes) | 2 | 2 | 0 | exception types patched 4x one at a time → catch the CLASS |
| 12 | D7 confirming (4 axes) | 1 | 1 | 1 | ⚠️ one axis errored (idle-stuck) — round recorded INCOMPLETE |
| 13 | D7 confirming (4 axes) | 2 | 2 | 0 | `--types X X`: content and count disagreed |
| 14 | D7 confirming (4 axes) | 2 | 2 | 1 | six live globs cannot reach what they were written for |
| 15 | D7 confirming (4 axes) | 1 | 1 | 0 | ⚠️ one axis 404'd — INCOMPLETE; LOCATE guard narrower than RUN guard |
| 16 | D7 confirming (4 axes) | 3 | 3 | 1 | the check emitted a FALSE accusation of its own |
| 17 | D7 confirming (4 axes) | 2 | 2 | 0 | a typo'd applies_to was indistinguishable from opting out |
| 18 | D7 confirming (4 axes) | 5 | 0 | 5 | **zero edits** — every candidate refuted by execution |
| 19 | D7 confirming (4 axes) | 2 | 1 | 1 | round 8's "fixed" double-parse was actually three, then four |
| 20 | D7 confirming (4 axes) | 0 | **0** | 0 | **4/4 axes ran · 0 confirmed · 0 edits → QUIET** |

`Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + qwen3-max×1 + deepseek-v4-flash×1 — round 1`
`Finders: native opus×2 — round 1`
`Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + qwen3-max×1 — round 2`
`Finders: pool ×5 + native opus×1 — round 4`

✅ **EXIT CLAIMED at round 20** — 4/4 axes ran, 0 confirmed findings, 0 edits, and the full Tier-2
gate green in the same turn (`status: success`, 0 failures). Round 18 was already edit-free (5
candidates, all refuted) but round 19 then confirmed one, which is exactly why a single quiet round
is not the standard: the artifact must be unchanged AND unchallenged.

**37 findings across 17 rounds.** The distribution is the lesson:
* **9 were false or imprecise CLAIMS** — sentences asserting behavior nobody had executed. Not one
  was caught by a test, a gate, or the suite; every one was found by reading the claim against the
  code. A claim costs nothing to write and nothing to check.
* **At least 8 were introduced by the FIX for an earlier finding** — the wildcard docstring, the
  `()`-vs-`None` sentinel, the false OK, the over-counted denominator, the false UNKNOWN TYPE, the
  flagged empty-list, the tripled corpus parse. Fixes are the least-reviewed code in any loop.
* **4 were the same defect patched one instance at a time** — the applies_to parser (4 YAML forms),
  the scaffolder guard (4 exception types), the corpus parse (4 call sites), the LOCATE/RUN guard
  asymmetry. Each time, fixing the reported instance left its siblings.
* **3 rounds FAILED rather than passed** (4 empty units, an idle-stuck axis, a provider 404). None
  was counted as clean — an errored unit is not a quiet unit, which is the same discipline the
  check itself enforces on packs.

**Round 4's twelve, for the record** — the severity is the point, not the count:
1. The ADVISORY, contractually read-only check REWROTE three tracked hub files (`PORTS.md`,
   `data/projects.yaml`, `docs/PROJECT_CATALOG.md`) on every run, via `create_project`'s
   `_post_scaffold_sync`. On a shared tree with three sessions, and synced to ~46 repos where a
   project's gate run would have reached into `/opt/fabrik` — the files-outside-project-tree HARD
   STOP, executed by machinery. I had SEEN ` M PORTS.md` earlier and filtered it out as a sibling's.
2. `wordpress` is in `SCAFFOLD_TYPES` but raises `NotImplementedError` → uncaught → non-zero exit →
   `warn_only` turns an advisory row into a HARD gate failure in ~46 repos.
3-4. Two more fail-silent-green instances: block-sequence YAML silently dropped; a typo'd scaffold
   type reading as a confident pass while printing "no pack declares applies_to yet".
5. The examined-count — the line that EXISTS to defeat silent-green — asserted packs were
   "reachable" while printing them as UNREACHABLE directly beneath.
6-9. A FOURTH false claim (wildcard-only globs), hiding a real T02↔T04 disagreement the seam proof
   could not observe; plus a false doc claim and a docstring truncated mid-clause.
10. The denominator is contaminated BOTH ways — copied hub boilerplate over-states reachability
   (`core/62-using-subagents.md` satisfies its own claim with its own copied file); `_EXCLUDE`
   under-states it. Unfixable without a scaffolder manifest; made VISIBLE instead.
11-12. Two tests that could not fail, and fixtures that mirrored the implementation's own blind
   spots — which is precisely why 6 and 10 survived the suite.


## What the plan closed, proven end-to-end

The class: rule-pack `globs:` were written for a **directory-per-concern** layout (`workers/`,
`auth/`) while the fabrik scaffolds emit **file-per-concern** (`worker.py`, `billing_routes.py`), so
a pack can be silently inert in every project it governs and nothing detects it. In transdoc that
cost 19 frontend calls to routes that did not exist, 14 endpoints with no caller, an empty beat-loop
body and a retention purge never run — while `final_gate` was green and 296 tests passed.

**The shipped check catches the original defect.** Replaying transdoc's exact pre-fix condition —
the directory-only globs still claiming `file-worker`:

```
=== the ORIGINAL defect, replayed: pre-fix globs + a file-worker claim ===
  FINDING: pack='core/75-workers-jobs.md' type='file-worker'
  -> caught: True
=== and the FIXED globs on the same claim -> no finding ===
  findings: 0
```

It flags the historical bug and goes quiet on the fix. That is the proof no individual ticket could
give.

## Requirements coverage (Finish step 3)

Every `## File Scope` path shipped with a commit; every `Interfaces.Produces` symbol exists:

```
✓ scripts/rules_match.py                     d388c9ef   ✓ rules_match.pack_matches_path
✓ scripts/enforcement/pack_layout_audit.py   d8ac7d31   ✓ rules_match.any_path_matches
✓ scripts/enforcement/check_pack_reachability.py d8aa4749  ✓ rules_match.packs_for_paths
✓ scripts/select_rules.py                    fec39417   ✓ pack_layout_audit.audit_layout
✓ scripts/review_rubric.py                   b589a1b8
✓ scripts/final_gate.py                      d8aa4749
✓ commands/_sources/fabrik-execute-plan.md   b589a1b8
✓ .windsurf/rules/core/75-workers-jobs.md    f562b49f
✓ .windsurf/rules/core/app-audit-log.md      f562b49f
✓ tests/… (4 files)                          d8aa4749 / d8ac7d31 / d4d3bafc
✓ docs/reference/rule-pack-reachability.md   d8aa4749
```

## Cross-ticket seam — proven in BOTH directions

One matcher, not three: `pack_layout_audit` and `check_pack_reachability` both import
`rules_match`; the check consumes `audit_layout`. Positive and negative control, per pack:

```
core/75-workers-jobs.md  claims ['file-worker']   · asked 'saas-skeleton' -> findings: 0
core/app-audit-log.md    claims ['saas-skeleton'] · asked 'file-worker'   -> findings: 0
positive: T02 reachable / T03 examined+reachable / T04 reachable -> AGREE
OVERALL_AGREE: true
```

The negative control matters: a positive-only proof cannot distinguish "the three agree" from "all
three say yes to everything". T99 added it; the orchestrator re-ran it independently.

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| fail-open vs fail-closed | FIXED | two instances: the audit's parser failed OPEN on legal YAML (`d8ac7d31`); the check's silent-on-absent row is made honest by printing its examined count |
| cost/quota/limit accounting | REFUTED | no metered call, no LLM dispatch, no quota surface anywhere in the plan |
| boundary/sentinel/prefix collisions | FIXED | the empty-pattern sentinel (deliberate True/False divergence + the inherited `/**` asymmetry, both pinned) and the `activation: manual` sentinel |
| behavior-without-a-test | FIXED | 31 tests across four suites, green together on the integrated tree; two dishonest tests found and strengthened |
| fleet-sync blast radius | FIXED | a 48-repo import break shipped and healed (`3f7b8bd2`); pack globs measured at 81 files/9 repos before accepting; corrected packs verified distributed to 48/49 |
| claims vs behavior | FIXED | FOUR false docstring/doc claims found and corrected — each a property nobody had executed. The recurring defect of this plan was never a logic bug; it was assertions that could not fail |
| doc truthfulness | FIXED | T99 verified every checkable claim by running it, but D7 then found one it had missed — "printed regardless of exit status", false on the one non-completing path. Corrected |
| requirements coverage | CLEAN | every File Scope path and every produced symbol accounted for above |

## Residual, reported not fixed

1. **`/opt/fabrik-lib` is broken by this change and the fix cannot reach it.** It re-vendored the new
   `select_rules.py` at 2026-08-25 20:37 without `rules_match.py`; it is sync-EXCLUDED by design
   (`sync_enforcement_to_projects.py:795`), so the force-sync that healed the other 48 structurally
   cannot touch it. Reported via fabrik-mail with the one-line fix. **Cross-repo edits are a HARD
   STOP** — not fixed here.
2. **The class has no enforcement.** A synced/vendored script's IMPORTS are part of its surface.
   Nothing cross-checks a module-scope import against `fabrik_synced_manifest.py`, and fabrik-lib's
   own `check_vendored_drift.py` compares files it already vendors — it structurally cannot see a NEW
   file it should now be vendoring. This class has now fired twice in one day.
3. **`select_rules.py --changed` returns before the Kaizen M1 sensor block**, so that invocation
   emits no `rule_activation` event. Behavioral, possibly intended, undocumented.




## Phase-gate evidence — the code, green

Captured in THIS turn immediately BEFORE the `Status: EXECUTED` flip, i.e. with every line of
this plan's code and tests in the tree and only the status line still saying IN-PROGRESS:

```
$ python scripts/final_gate.py --json
{
  "status": "success",
  "blocking": 38,
  "failures": [],
  "warnings": ["Coverage Checklist (reviews)", "Vendored Drift (sync-excluded repos)"]
}
```

Stated plainly because the ordering matters: after the flip the gate goes RED on exactly one
check — `check_convergence`, complaining that THIS file lacked an embedded success. That is
self-referential by construction (the flip cannot be proven green until the proof is written,
and the proof cannot be written until the flip). The block above is the honest resolution: a
real run, from this turn, proving the CODE is green, with the flip as the only delta. Both
warnings are pre-existing and belong to siblings — see the attribution note below.

## Phase T01 — D7 live-request — ✅ PASS

Prose pin watched RED then GREEN in my own turn; proven non-vacuous by per-signal mutation
(stripping `live request` alone → False; stripping `## Evidence` alone → False).
`check_command_corpus` green across 44 corpus files. `commands/_sources/fabrik-execute-plan.md:520`.

## Phase T04 — shared matcher — ✅ PASS

Purity byte-identical for BOTH callers (`review_rubric --changed`, `select_rules --json`) in the
tree the baseline was taken. Three call sites rewired incl. `globs_fired`; `_GLOBS` untouched;
the empty-pattern divergence pinned as inherited against `b589a1b8~1`. `scripts/rules_match.py:143`.

## Phase T02 — corpus audit + pack fixes — ✅ PASS

Both packs reproduced at 0 matches BEFORE and ≥1 AFTER; blast radius measured before accepting
each glob; `activation: manual` packs excluded — the defect that would have violated
`.windsurf/rules/saas/00-domain-saas.md:6`'s explicit warning.

## Phase T03 — non-circular check — ✅ PASS

Non-circularity proven by contrast: a fixture pack the check REPORTS while `select_rules.collect()`
puts it in AVAILABLE. Advisory via `warn_only=True` (`scripts/final_gate.py:221`); denominator
printed; exits 0 on every failure path (RuntimeError / ImportError / ValueError /
NotImplementedError / FileNotFoundError all verified live).

## Phase T99 — integration — ✅ PASS

Seam proven both directions with a negative control; `check_doc_sync --range` and
`check_doc_stubs --range` exit 0; all four ticket suites green together on the integrated tree.
`docs/reference/rule-pack-reachability.md:1`.

## Exit round

Pass 20: found: 0, fixed: 0 — 4 of 4 axes ran (no empty, stuck, or errored units), zero
candidates survived adjudication, zero edits to the artifact. Round 18 was already edit-free,
but round 19 then confirmed a real defect, which is why one quiet round is not the bar: the
artifact must be BOTH unchanged and unchallenged. Round 20 is the first round meeting both.
