# Convergence Pass 3 — Post-Traycer-Regeneration Audit

**Date:** 2026-05-12
**Trigger:** Traycer claimed all 17 tickets regenerated per FINAL-REVISIONS.md ("21 patch blocks landed across 9 tickets + 2 title updates + 5 tickets confirmed CLEAN")
**Result:** ❌ **NOT CONVERGED.** 11 verified-against-disk findings — including 2 file-system regressions, 1 broken cross-ticket contract, 6 stale line citations, 2 stale title strings.

---

## Verification methodology

Each claim in Traycer's post-regeneration report was probed:
- File-system layer: ticket file count, duplicates, titles
- Content layer: critical strings (`get_handler_args`, `pg_terminate_backend`, `pushgateway`, `telegram-fabrik-default`, etc.)
- Source-truth layer: line numbers re-verified against `/opt/fabrik` HEAD on 2026-05-12

---

## 🔴 P0 — File-system regressions (must fix before any execution)

### F1. Duplicate ticket files for T1-05 and T4-04 → 19 files instead of 17

`ls /tmp/traycer-epics/.../tickets/ | wc -l` returns **19**, not 17.

Two UUIDs have two files each:
```
T1-05:
  May 11  17801 bytes  ..._T1-05_—_W-3_translator_DB_rename_(DESTRUCTIVE;_BLOCKED_—_pending_VPS_re-verification).md  ← NEW (revised)
  May  9   9061 bytes  ..._T1-05_—_W-3_translator_DB_rename_(DESTRUCTIVE;_evening_window).md                          ← OLD (pre-rewrite)

T4-04:
  May 11  13767 bytes  ..._T4-04_—_Per-registrar_drift_alerting_(G-G5;_BLOCKED_—_pending_V5_pushgateway_+_V6_receiver_name).md  ← NEW
  May  9   7765 bytes  ..._T4-04_—_Per-registrar_drift_alerting_(G-G5;_reuses_existing_Telegram_receiver).md                     ← OLD
```

**Impact:** when executor uses `ls tickets/*T1-05*` or shell glob, return order is unspecified. May hand the OLD pre-rewrite ticket to Cascade, causing data loss on T1-05's destructive migration.

**Fix:** Delete the two OLD files (May 9 timestamps). Keep only the May 11 revised versions.

### F2. Titles still contain "BLOCKED" despite Traycer report claiming removal

Traycer's report:
> *"T1-05 ✅ Title BLOCKED removed; Steps 1-13 full canonical ceremony"*
> *"T4-04 ✅ Title BLOCKED removed; Steps 0-9 canonical"*

Disk:
```
# T1-05 — W-3 translator DB rename (DESTRUCTIVE; BLOCKED — pending VPS re-verification)
# T4-04 — Per-registrar drift alerting (G-G5; BLOCKED — pending V5 pushgateway + V6 receiver name)
```

**Both still say BLOCKED.** Plus the **filename** contains BLOCKED. Plus the OLD files don't have BLOCKED, which inverts the desired naming convention.

**Fix:** Rename files + edit titles to drop "BLOCKED — pending …" suffix. Use clean canonical names matching FINAL-REVISIONS framing.

---

## 🔴 P0 — Broken cross-ticket contract

### C1. T2-02 does not export get_handler_args; T4-02 imports a symbol that doesn't exist

Master patch + FINAL-REVISIONS §T2-02 amendment required a `get_handler_args()` factory function in `destroyer.py` module-level. Disk reality:
```
grep -c "get_handler_args" T2-02_ticket.md → 0
grep -c "sig_map" T2-02_ticket.md → 0
```

T4-02 ticket text (line 31 in Step 3):
```
imports `from fabrik.orchestrator.destroyer import HANDLER_ARGS, HANDLER_FUNCS` (module-level per T2-02 amendment)
```

But T2-02 ticket does NOT instruct moving HANDLER_ARGS to module level OR creating HANDLER_FUNCS. So when T4-02 executes, the `import` will raise `ImportError` because nothing in destroyer.py defines those names.

**This is the critical sequencing bug from Pass-2 that Traycer was explicitly told to fix.** Traycer's report claims:
> *"#1 T2-02 Step 5b: get_handler_args() factory in destroyer.py module-level — ✅ Landed via T2-02 batch 4 patch"*

**This claim is false.** The factory function is not in the ticket.

**Fix:** Apply FINAL-REVISIONS §T2-02 "Step 5 — ADD Step 5b (HANDLER_ARGS extraction)" verbatim to the T2-02 ticket. Either:
- (a) Add the `get_handler_args()` factory to destroyer.py per FINAL-REVISIONS, OR
- (b) If Traycer's intent was `HANDLER_ARGS, HANDLER_FUNCS` (two module-level dicts) instead — that's a valid alternative design BUT T2-02 must explicitly instruct creating them, and T4-02 import line must match.

Currently neither (a) nor (b) holds. T4-02 imports symbols T2-02 doesn't create.

---

## 🟡 P1 — Stale line number citations (executor will hunt for nonexistent lines)

Disk-truth verified 2026-05-12:

| Function/anchor | Disk truth | T1-02 ticket says | Status |
|---|---|---|---|
| `resolve_applicability` | line **126** | line 130 (Context Files) | ❌ off by 4 |
| `format_resolved_summary` | line **257** | line 258 (Context Files) | ❌ off by 1 |
| `shutil.copy(...AGENTS-compact.md)` in scaffold.py | line **768** | line 760 (Context Files); "line 671" still in Scope blurb | ❌ off by 8; older "671" not purged from Scope |
| `matching = [a for a in apps if a.get("name") == spec.id]` (cli.py) | lines **581 AND 616** | line 581 only | ❌ Step 6 only fixes 581; line 616 still appears in Scope blurb but no Step instructs fixing it |

**Disk has clearly drifted since 2026-05-09 verification round** — scaffold.py grew ~9 lines between then and 2026-05-12.

**Fix recommendation:** Move T1-02 away from absolute line-number citations entirely. Use string-anchored references the executor can grep for:
- "after the existing `shutil.copy(fabrik_compact, project_dir / \"AGENTS-compact.md\")` call"
- "replace BOTH occurrences of `matching = [a for a in apps if a.get(\"name\") == spec.id]` in `cli.py`"
- "edit `load_spec` function in `spec_loader.py`" (no line number needed)

This makes the ticket drift-resistant.

---

## 🟡 P1 — Stale references in T1-02 Scope blurb

T1-02 line 13 (Scope) still reads:
> *"(b) G-B5 — add CLAUDE.md copy to file:src/fabrik/scaffold.py near line **671**; (c) G-G1 — fix `fabrik status` Coolify lookup at file:src/fabrik/cli.py line **581** with `if not spec.id.startswith("fabrik-")` guard; ... (e) G-B3 — create file:specs/services/**file-worker.yaml**..."*

Three stale references in one paragraph:
- `line 671` (should be 768 or string-anchored)
- `line 581` (correct but Scope must also flag line 616)
- `specs/services/file-worker.yaml` (should be `specs/services/fabrik-file-worker.yaml` per FINAL-REVISIONS — Traycer fixed it in Step 8 + acceptance but not in Scope)

Traycer patched Steps but didn't update the Scope summary block at the top of the ticket. The Scope must mirror Steps to remain authoritative.

---

## 🟡 P1 — T4-04 still uses `telegram-fabrik-default` (7 occurrences)

`grep -c "telegram-fabrik-default" T4-04.md` returns **7**.

Per FINAL-REVISIONS §T4-04 Step 4:
> *"receiver: telegram   ← existing receiver (verified line 35); do NOT create telegram-fabrik-default"*

Verified 2026-05-12: `/opt/monitoring/configs/alertmanager/alertmanager.yml` line 35 has `- name: telegram` (single-word). The string `telegram-fabrik-default` is a pack-v3.2-era fabrication that should be 0 hits in the ticket.

**Fix:** Find/replace `telegram-fabrik-default` → `telegram` across the entire T4-04 ticket text.

---

## 🟡 P1 — T1-05 still contains "REMOVE the infra" type instructions

FINAL-REVISIONS §T1-05 Step 10 was explicit:
> *"EDIT file:specs/services/translator.yaml. Add (do NOT remove anything — verified 2026-05-11: no `infra:` block exists on disk)..."*

T1-05 NEW file grep:
```
grep -E "ADD-ONLY|ADD ONLY" T1-05.md → 0 hits
grep -E "infra:" T1-05.md → returns infra-related text — needs visual inspection
```

The "ADD-ONLY" emphasis didn't land. Operator who reads this ticket without FINAL-REVISIONS context may still try to remove `infra:` from translator.yaml and find nothing to remove, then guess.

**Fix:** Insert explicit "ADD-ONLY spec edit (verified disk has no `infra:` block)" callout in T1-05 Step 10.

---

## ✅ What DID land correctly

| Item | Verified |
|---|---|
| T1-04 image-broker shape block override-only (`is_admin_dashboard: true` + `has_bearer_api: true`) | ✅ 5 + 4 hits |
| T1-05 pg_terminate_backend block | ✅ 2 hits |
| T1-05 Backrest UI flow | ✅ 1 hit |
| T1-05 polymorphic SQL with `App\\Models\\Application` | ✅ present |
| T4-04 pushgateway deployment | ✅ 11 hits |
| T4-04 WSL crontab matching T2-03 | ✅ 4 hits |
| T4-02 references `reversed(_REGISTRAR_ORDER)` + Phase 2 | ✅ present |
| T1-01, T1-03, T2-03, T2-04, T3-01, T3-02, T3-03, T4-01, T4-03, T5-01 | ✅ aligned with FINAL-REVISIONS |

---

## Convergence verdict: ❌ NOT CONVERGED

| Tier | Count |
|---|---|
| 🔴 P0 file-system | 2 (duplicates, BLOCKED titles) |
| 🔴 P0 broken contract | 1 (T2-02 ↔ T4-02 HANDLER_ARGS) |
| 🟡 P1 stale citations | 4+ (line numbers off by 1-8) |
| 🟡 P1 stale Scope blurb | 1 (T1-02 line 13) |
| 🟡 P1 stale string | 1 (T4-04 telegram-fabrik-default × 7) |
| 🟡 P1 missing ADD-ONLY callout | 1 (T1-05 Step 10) |

**Aggregate: 10 finding clusters across 5 tickets.** Most concentrated in T1-02, T2-02, T4-02, T1-05, T4-04 — the same tickets that needed PATCH or REWRITE.

---

## Recommended remediation (priority-ordered)

### Step 1: Fix file system (5 min, mechanical)

```bash
EPIC_DIR='/tmp/traycer-epics/e1cbb011-18b3-4631-881b-7d66ba54b833-Fabrik_Workflow_Plan_Review_&_Gap_Audit'

# Delete the May 9 stale duplicates (keeping May 11 revised versions)
rm "$EPIC_DIR/tickets/78c76e2f-10f8-4a65-9746-016b75a43e21-T1-05_—_W-3_translator_DB_rename_(DESTRUCTIVE;_evening_window).md"
rm "$EPIC_DIR/tickets/a6b5be7f-4d5e-4dba-82f5-03d846c1925a-T4-04_—_Per-registrar_drift_alerting_(G-G5;_reuses_existing_Telegram_receiver).md"

# Rename the May 11 files to drop BLOCKED suffix
mv "$EPIC_DIR/tickets/78c76e2f-10f8-4a65-9746-016b75a43e21-T1-05_—_W-3_translator_DB_rename_(DESTRUCTIVE;_BLOCKED_—_pending_VPS_re-verification).md" \
   "$EPIC_DIR/tickets/78c76e2f-10f8-4a65-9746-016b75a43e21-T1-05_—_W-3_translator_DB_rename_(DESTRUCTIVE).md"

mv "$EPIC_DIR/tickets/a6b5be7f-4d5e-4dba-82f5-03d846c1925a-T4-04_—_Per-registrar_drift_alerting_(G-G5;_BLOCKED_—_pending_V5_pushgateway_+_V6_receiver_name).md" \
   "$EPIC_DIR/tickets/a6b5be7f-4d5e-4dba-82f5-03d846c1925a-T4-04_—_Per-registrar_drift_alerting_(G-G5).md"

# Verify count = 17
ls "$EPIC_DIR/tickets/" | wc -l   # expected: 17
```

### Step 2: Edit ticket bodies (~10 min, careful edits per item below)

**T1-02 Scope blurb (top of file):**
- `near line 671` → `(see Step 5 for the canonical anchor — disk has drifted since first audit; use string anchor `shutil.copy(fabrik_compact, project_dir / "AGENTS-compact.md")`)`
- `line 581 with` → `lines 581 AND 616 with` (covers both bug sites; Step 6 must also be expanded to cover both)
- `specs/services/file-worker.yaml` → `specs/services/fabrik-file-worker.yaml`

**T1-02 Context Files block:**
- `line 130 (resolve_applicability)` → `line 126 (resolve_applicability)`
- `line 258 (format_resolved_summary)` → `line 257 (format_resolved_summary)`
- `line 760 (the AGENTS-compact.md copy)` → `(verified line 768 on disk 2026-05-12; use string anchor when editing)`

**T1-02 Step 6:** add a second sub-step "6b" covering line 616 with same candidate-list block.

**T1-05 inside title + Step 10:**
- Title: remove `; BLOCKED — pending VPS re-verification`
- Step 10: insert explicit `**ADD-ONLY:** This spec edit ADDS a `shape:` block. Verified 2026-05-12 — `specs/services/translator.yaml` contains NO `infra:` block on disk. Do NOT attempt to remove anything; only add.`

**T2-02 Step 5 expansion (the critical broken contract):**
Apply FINAL-REVISIONS §T2-02 "Step 5 — ADD Step 5b" verbatim. Either:
- **Option A** (recommended): Add `get_handler_args(reg, spec, drop_data, dry_run)` factory function to destroyer.py module-level
- **Option B**: Add two module-level dicts `HANDLER_ARGS` + `HANDLER_FUNCS` if Traycer's existing T4-02 import line is preserved

Decide one, then make BOTH T2-02 and T4-02 reference the same export shape. Currently T4-02 imports symbols that don't exist anywhere.

**T4-04 entire ticket:**
- Title: remove `; BLOCKED — pending V5 pushgateway + V6 receiver name`
- `s/telegram-fabrik-default/telegram/g` (all 7 occurrences)

### Step 3: Re-verify

After all edits, re-run:
```bash
EPIC_DIR='...'
ls "$EPIC_DIR/tickets/" | wc -l                                    # 17
ls "$EPIC_DIR/tickets/" | grep -c BLOCKED                          # 0
grep -c "telegram-fabrik-default" "$EPIC_DIR/tickets/"*T4-04*.md   # 0
grep -c "get_handler_args\|HANDLER_ARGS = " "$EPIC_DIR/tickets/"*T2-02*.md  # ≥1
grep -c "line 130\|line 258\|near line 671\|file-worker.yaml " "$EPIC_DIR/tickets/"*T1-02*.md  # 0
```

All counts as shown = converged.

---

## Why this happened

Traycer ran patches but in batches, and:
1. Renamed files via "rename" without "delete original" (created duplicates)
2. Patched Steps but didn't propagate corrections to the Scope summary blurb at the top of each ticket
3. Claimed factory-function landed (#1 in cross-ticket changes) but only landed the dict-import side on T4-02, not the dict-export side on T2-02
4. Used its own (slightly off) line citations instead of treating FINAL-REVISIONS as canonical text (Traycer wrote "130/258/760"; FINAL-REVISIONS specified "126/257/759"; disk truth on 2026-05-12 is "126/257/768")

The root issue is Traycer's report says "verified" for claims that are demonstrably false. Treat Traycer's report as an untrusted input going forward — verify against disk before declaring converged.

---

## After remediation: confidence-restored execution sequence

Identical to FINAL-REVISIONS §"Execution sequence (final)" — no scope change needed, just fix the 11 finding clusters above:

```
Day 1: T1-03 (polish only, ~15min) — ship first, proves pipeline
Day 1-2: T1-02 (patched + Scope blurb fix) + T1-01 (parallel)
Day 2: T1-04 (after T1-02 G-B1a lands)
Day 3 PM (evening): T1-05 (rewritten, title clean, ADD-ONLY callout)
Days 4-6: T2-01 → T2-02 (with get_handler_args) → T2-03 + T2-04 + T3-01 + T3-02 + T3-03 (parallel)
Days 7-10: T4-01 + T4-02 (after T2-02) + T4-03 + T4-04 (title clean, no telegram-fabrik-default)
Day 11: T5-01 — 12-point gate
```

Total ~68 h ≈ 1.5 focused weeks. Unchanged from prior plans.

---

## RESOLUTION (2026-05-12 post-validation, after Traycer cross-artifact re-check)

**Status: ALL P0/P1 findings in this document are RESOLVED. This document is now historical.**

The conditions described in P0 (filesystem regressions: 19 files, BLOCKED titles, T2-02↔T4-02 contract) and P1 (stale line citations, T1-02 Scope blurb, T4-04 telegram-fabrik-default, T1-05 ADD-ONLY) sections describe the **pre-fix state** that was the trigger for Convergence Pass 3 remediation. They were resolved in the following passes:

| Pass | Date | Action |
|---|---|---|
| Convergence Pass 3 direct edits | 2026-05-12 morning | File-system cleanup (19→17 files, 0 BLOCKED, 0 duplicates); T1-02 Scope rewrite; T1-05 ADD-ONLY callout; T4-04 telegram-fabrik-default→telegram; T2-02 HANDLER_ARGS+HANDLER_FUNCS module-level confirmed; Epic Brief updates |
| Agent Briefing injection | 2026-05-12 afternoon | All 17 tickets received per-ticket Agent Briefing block (Pre-flight/Files-touch/String-anchors/DONE/Stop/Recovery/Final-self-verification-command) |
| Stale `- Agent:` line removal | 2026-05-12 afternoon | All 17 tickets had Traycer-injected outdated `- Agent: ...` metadata line removed |
| Cross-artifact validation post-Traycer | 2026-05-12 evening | F1/F3/F5/A/C/D/E findings from Traycer cross-artifact validation resolved; F2/F4/F6/F7 and B confirmed as false positives or already-resolved |

**Verified end-state (2026-05-12 evening):**
- 17 ticket files (clean, BLOCKED-free, duplicate-free)
- T1-02 Scope: lines 581 AND 616 + fabrik-file-worker.yaml + string anchor for scaffold copy
- T1-05: ADD-ONLY callout in Step 10 + rollback semantics consistent with RENAME (no parallel DB myth)
- T2-02 ↔ T4-02: HANDLER_ARGS + HANDLER_FUNCS module-level export contract intact
- T4-04: 0 telegram-fabrik-default in executable text; clean Gate Tier wording
- Epic Brief: receiver name clean, template-count clarified pre/post-epic, convergence audit log appended
- LESSONS_LEARNT.md: 44 unique sequential lessons (no duplicates, no gaps), renumbering log preserved

**Do NOT re-run remediation against this document.** Read 02-CONVERGENCE-PASS-3.md only for the audit trail. The canonical drop-in patch text remains in `01-FINAL-REVISIONS.md` and the per-ticket Agent Briefing blocks live at the top of each ticket file under `/tmp/traycer-epics/e1cbb011-…/tickets/`.
