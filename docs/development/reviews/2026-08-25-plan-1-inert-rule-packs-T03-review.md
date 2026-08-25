# Review — T03 (the non-circular reachability check) · phase-1 of 2026-08-25-plan-1-inert-rule-packs

Status: IN-PROGRESS

Surface: `scripts/enforcement/check_pack_reachability.py` · `scripts/final_gate.py` (one
`run_optional_check`) · `tests/enforcement/test_pack_reachability.py` ·
`docs/reference/rule-pack-reachability.md`. Commit: `d8aa4749`.

## Pass Ledger

| Pass | finders | found | fixed | refuted | notes |
|---:|---|---:|---:|---:|---|
| 1 | orchestrator acceptance verification (independent re-execution of all three BC rows) | 0 | 0 | — | coder's own red-on-revert accepted after re-proving its claims |
| 2 | pool + native round — OWED, not yet run | — | — | — | exit NOT claimed |

`Finders: orchestrator opus×1 (acceptance) — round 1`

⚠️ **Exit NOT claimed.** This ticket has had acceptance verification but no adversarial finder
round; round 2 is owed before it may go ✅.

## What the orchestrator re-proved rather than accepted on report

The coder reported DONE with a red-on-revert receipt (neutered `_examined_packs`, watched 4 tests
fail, restored to 7 green). A DONE is a claim. Each Behavior-Contract row was re-executed here:

1. **Non-circularity (row 1).** Built a fixture pack with a non-matching glob and
   `applies_to: ["file-worker"]`:

   ```
   select_rules.collect():  ACTIVE = False   AVAILABLE = True
     -> the circular check ('ACTIVE and matches-zero') sees: NOTHING
   this check reads the INDEPENDENT declaration: activation='glob' applies_to=['file-worker']
     -> examined regardless of the ACTIVE/AVAILABLE split: True
   ```

   This is the ticket's entire reason to exist, and it holds. transdoc's proposed check would have
   seen nothing; this one examines the pack anyway.

2. **Silent-on-absent (row 2)** — a pack with no `applies_to` passes silently, so the field lands
   incrementally across 56 packs without turning ~46 repos red on day one.

3. **The denominator (row 3)** — against the real corpus:

   ```
   Examined 2 pack(s) with a reachable applies_to claim (of 12 scaffold type(s) checked).
   OK — every examined pack's applies_to claim reaches at least one emitted path.
   ```

   Exactly 2 — the packs T02 seeded. **Row 3 is what stops row 2 from being a defect.** Without the
   count, a corpus where nobody has declared anything reads identically to a corpus that is healthy —
   which is the "reports SUCCESS when it cannot ask its question" class this check exists to catch.
   A check that shipped rows 1+2 without row 3 would have BEEN an instance of its own target.

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| fail-open vs fail-closed | CLEAN | `warn_only=True` is a deliberate fail-soft on LANDING (56 packs × ~46 repos must not go red day one), but the row still FAILS the gate if the check itself breaks — per `run_optional_check`'s own contract. Promotion to blocking is a named operator decision recorded in the reference doc |
| cost/quota/limit accounting | REFUTED | no metered call, no LLM dispatch; it reuses T02's cached scaffold walk |
| boundary/sentinel/prefix collisions | CLEAN | the `activation: manual` exclusion and the absent-`applies_to` sentinel both inherited from the shared engine and re-verified here |
| behavior-without-a-test | CLEAN | all three BC rows tested; the coder's red-on-revert neutered the examined-count path and watched 4 tests fail before restoring |
| circularity (ticket-specific) | CLEAN | proven by executable contrast, not asserted — the fixture is in AVAILABLE and still examined |
| synced-surface import safety | CLEAN | coder reported `SYNC-IMPORTS: none` unprompted — stdlib plus a sibling already on the synced path. This was written into its brief as a standing constraint after the same class broke 48 repos earlier today |

## Evidence

Gate row, non-blocking (advisory):

```
{'check': 'Rule-pack reachability',
 'output': "Examined 2 pack(s) with a reachable applies_to claim (of 12 scaffold type(s) checked).\n
            OK — every examined pack's applies_to claim reaches at least one emitted path."}
```

Whole-plan receipts over the plan range, run by the orchestrator:

```
$ python scripts/enforcement/check_doc_sync.py  --range 4a9731ca..HEAD   -> exit 0
$ python scripts/enforcement/check_doc_stubs.py --range 4a9731ca..HEAD   -> exit 0
$ python scripts/enforcement/check_convergence.py                        -> exit 0
$ python -m pytest tests/test_execute_plan_d7.py tests/test_rules_match.py \
      tests/enforcement/test_pack_layout_audit.py tests/enforcement/test_pack_reachability.py -q
31 passed in 1.63s
```
