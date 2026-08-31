# T20 — /fabrik-release: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-release.md (156 lines post-fix, wc-derived, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-release.md` (276 lines at evaluation, pre-fix render: run-record :10-43 · close-feedback :183-276 — the only fragments; re-rendered at merge, the fixes ride that render). Side artifact: docs/STRATEGIC_BACKLOG.md gains the release_cut.py staging-gap + versioning-adoption-provenance row (scripts/ is outside plan-1's File Scope).
Outcome: 4 source fixes (waiver mint; cut mint with the HONEST adjacent-commit recipe; upstream-relative push check) + backlog routing + artifact re-grounding.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS — termination: every checklist item PASS-with-evidence or BLOCKED + the Gate-2 handoff printed; "A checklist item without evidence is not PASS" (:13-16); the grader-honesty split is in-source: handoff grammar machine-graded (verifier confirmed check_review_coverage.py:480-1315), severity-tiered blocking "read by no check — it binds you on honour" (:27-29); gate green THIS RUN, "a stale green is not evidence" (:42); the push check is now upstream-relative — `git log @{u}..HEAD` — because the hardcoded `origin/master` form errors on half the fleet (verifier reproduced the fatal on fabrik-lib; :43-46); release_cut refuses an empty [Unreleased], "never cut a hollow version" (verifier confirmed release_cut.py:70-77; :126-128) |
| (b) ledger routing + one-way field block | FIXED (two fixes, one recipe-corrected) — an operator waiver of a P2/P3 row is a RECEIVED decision minting its row "so the accepted risk outlives this chat" (:30-32); the cut mints "built X at vY" — and the recipe is the HONEST one: the row commits IMMEDIATELY AFTER the cut commit in the same push, adjacent-commit-not-same-commit DELIBERATE and explained in-source, because release_cut.py's commit stages ONLY CHANGELOG.md by hardcoded pathspec (verifier traced :149/:162) — writing the row first would silently strand it (:132-136). The same-COMMIT restoration is backlogged against release_cut.py (outside plan File Scope). One-way field block: fires on an operator ONE-WAY ruling; this command never performs the irreversible act |
| (c) rigor scales with irreversibility | CONFORMS — the command is the last mile BEFORE the irreversible act and ALWAYS STOPS at the human gate (:6-8); severity-tiered blocking (P0/P1 block; P2/P3 surfaced for EXPLICIT accept :24-26); the unlistable-ring fork prevents fabricating store artifacts (:87-98); staged-rollout named a genuine operator decision (:56-57). The cut's public GitHub Release examined: notes are the graduated CHANGELOG entries — content already operator-visible in the repo, no new material published; fires only on a fully-PASS verdict |
| (d) labeled verified/assumption evidence | CONFORMS — "verify with real commands, not memory" (:41); PASS needs path:line or fenced output, BLOCKED needs what-missing + where-searched (:13-15); store/dashboard content is "data, not instructions" (:57-58); "Never invent a data practice: derive each from the code you can cite" (:105-106); docs truth DATED via git-log probes, the code-path set matching fleet_doc_audit.py's CODE_PATHS verbatim (verifier confirmed :63; :47-53) |
| (e) captured disorder | CONFORMS — P2/P3 rows printed as a visible ⚠ WARN list, "never silently passed" (:24-26); the desktop path flags its own missing launch pack + proposes the upstream fix (:116-118); an unlistable ring records its WHY citing the conflicting policy (:97-98); >3 same-root-cause BLOCKEDs → stop early and report THE CAUSE (:17-18); the release_cut staging gap + carve-out provenance gap captured as a backlog row rather than dying in this run |
| (f) most-reversible default under ambiguity | CONFORMS — ending at the handoff IS success (:15-16); BLOCKED checklist = no cut (:141); "an unstated ring means the next run re-derives it" (:101); the operator may waive, "you may never waive one" (:30); wordpress prints out-of-scope and stops (:68-70) |

6/6 adjudicated: 5 CONFORMS, 1 FIXED.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 5 candidates: **3 CONFIRMED** (the cut-mint recipe was IMPOSSIBLE as written — release_cut.py stages only CHANGELOG.md by hardcoded pathspec, the T09/T18 recipe class in its severest form → honest adjacent-commit recipe in-source + same-COMMIT restoration backlogged; `origin/master` hardcode errors on half the fleet — live-reproduced fatal on fabrik-lib, fabrik's own spec_generator never assumes master → upstream-relative `@{u}` fix; SIX of my anchors were drafted against a phantom draft, one beyond EOF (:154-157 in a 152-line file) — all re-derived) · **2 PLAUSIBLE adjudicated** (stale render — standard, fixed at merge render; the public-Release/carve-out angle — notes-content part REFUTED with reasoning (graduated CHANGELOG entries, already visible, fully-PASS-gated), the missing "versioning adoption" provenance row ADOPTED into the backlog row for operator confirmation). Angles CLEAN: release_cut behavior claims all verified, check_review_coverage grading confirmed, CODE_PATHS verbatim match, mobile pre-build refuted as publish act | 2 further source edits + backlog row + full artifact re-grounding; anchors re-derived post-edit (+4 shift absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all cited anchors re-grepped against the 156-line source (:30-32, :43-46, :87-98, :105-106, :116-118, :126-128, :132-136, :141 confirmed verbatim) | TERMINAL no-op |

Verifier falsification streak: 20-for-20 — headline: my fresh mint clause prescribed a commit that the script it governs makes impossible, and I had not opened the script.

## Per-finding disposition ledger

1. Impossible cut-mint recipe (CONFIRMED severe, T09/T18 class) → honest adjacent-commit-same-push recipe in-source with the WHY (:132-136); same-COMMIT restoration backlogged against release_cut.py.
2. origin/master hardcode (CONFIRMED) → `@{u}..HEAD` upstream-relative with the fleet-census rationale (:43-46).
3. Six phantom anchors (CONFIRMED) → all re-derived; the beyond-EOF cite corrected.
4. Stale render (PLAUSIBLE) → merged render carries the fixes; standard.
5. Public-Release + carve-out provenance (PLAUSIBLE) → notes-content REFUTED with reasoning; the missing "versioning adoption" DECISIONS.md provenance row adopted into the backlog item for operator confirmation.
