# T05a — epic containment in check_plan_tickets (both levels)

## Scope
Two enforcement edits, each with a watched-red test. (1) `scripts/enforcement/check_plan_tickets.py`: when the spine carries an `Epic:` header line (T04b's interface), load that epic's frontmatter `owned_paths` — COPY the ~20-line parser from `scripts/epic_order.py:29`, never import it: this check is synced to every project and must stay dependency-free — and enforce **both** links the spec commits to (§ Chain consolidation (e): *"every ticket's Scope ⊆ the spine's File Scope ⊆ the epic's `owned_paths`"*): ERROR any ticket Touches path the epic's paths do not cover, AND ERROR any spine File Scope entry outside them — the first draft implemented only the ticket link, which let a spine widen past its epic and still pass. ⚠️ **Coverage here is GLOB-AWARE, and the existing helper is not.** `_covered_by` (`scripts/enforcement/check_plan_tickets.py:418`) is a plain string-prefix test — proven by execution: `_covered_by("src/a/**", "src/a/x.py")` is **False**, so reusing it would ERROR on every legitimate ticket under a globbed epic, which is every real one (`docs/development/epics/` owns shapes like `libs/**/product_entitlements_bridge/**`). Ticket Touches and File Scope entries are literal by grammar, but an epic's `owned_paths` are GLOBS, so this comparison needs a `/`-AWARE glob match against the epic glob, with `**` in the MIDDLE working and not only trailing. ⚠️ **Not bare `fnmatch`** — it is separator-blind: `fnmatch('src/a/b/deep.py','src/a/*')` returns **True**, so an epic deliberately scoping itself to `src/a/*` would ADMIT a ticket touching `src/a/b/deep.py` and the 'a window cannot plan or build outside its epic' guarantee would silently not hold. Translate explicitly (`**`→`.*`, single `*`→`[^/]*`) or use `PurePath.match` with a `**` pre-pass; a File-Scope directory entry (`docs/x/`) must also match a `**` epic glob. Do NOT widen `_covered_by` itself — it is load-bearing for the literal-vs-literal containment the rest of that file does; add a separate glob-aware predicate beside it. Both sit beside the existing File-Scope containment (`:1067`). A spine with no `Epic:` line behaves exactly as today. **The lock half of this ticket is GONE.** Spec r11 withdrew the relocation (D-117), so `check_plan_lock_release.py:396`'s `lockdir = root / ".fabrik" / "plan-locks"` is correct as it stands and nothing about the lock directory changes anywhere in this plan. SPLIT NOTE: this was T05 until the emit gate measured 267,161 bytes against the 262144 budget; the gate registration is T05b. With the lock half withdrawn at r11 the ticket is smaller again, and its read set shrinks accordingly. DO-NOT: touch `scripts/final_gate.py` (T05b), `scripts/epic_order.py` (T03a), `commands/_sources/` (T04a/T04b), or anything lock-related at all — r11 settled it.

Depends: T04b
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/enforcement/test_plan_tickets_epic_scope.py -q
Docs: CHANGELOG.md · INDEX.md (new tests) — orchestrator-applied

## Touches
- scripts/enforcement/check_plan_tickets.py — PRIMARY PATH
- tests/enforcement/test_plan_tickets_epic_scope.py

## Behavior Contract
- **Given** a fixture spine with `Epic: docs/development/epics/1-x.md` whose `owned_paths` is `["src/a/**"]` and a ticket touching `src/b/x.py`, **When** `check_plan_tickets --plan-dir` runs, **Then** it ERRORs naming the ticket, the path and the epic (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** the same spine with the ticket touching `src/a/x.py`, **When** the check runs, **Then** no epic-containment finding is raised — the glob-aware predicate matches where `_covered_by` returns False (scripts/enforcement/check_plan_tickets.py:418)
- **Given** an epic owning `libs/**/product_entitlements_bridge/**` and a ticket touching `libs/x/product_entitlements_bridge/y.py`, **When** the check runs, **Then** no finding is raised — a `**` in the MIDDLE must match, which is the shape real epics use (scripts/enforcement/check_plan_tickets.py:418)
- **Given** a spine whose File Scope names `src/c/**` while its epic owns only `src/a/**`, **When** the check runs, **Then** it ERRORs on the spine entry, not merely on the tickets (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** a spine with no `Epic:` line, **When** the check runs, **Then** its output is byte-identical to today's (scripts/enforcement/check_plan_tickets.py:1067)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/epic_order.py
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
