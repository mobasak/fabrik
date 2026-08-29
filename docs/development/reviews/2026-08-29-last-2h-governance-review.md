# Review — the session's last 2 hours of governance work (2026-08-29, infra)

**Status:** CONVERGED
**Surface:** `bbe82bfa` + `git diff HEAD` md5 `06771f7fcf41e4cd7f50c336ae9e8d9a` at pass 1 (the one
in-run fix, F1, changed CLAUDE.md — re-swept in passes 2–3) · fabrik-lib `4f7dd414`
(operator-approved cross-repo)
**Scope:** my authored commits `c3e171e8` (ai-consult third lane) · `03e517bb` (review-machinery
fragments) · `e58a8890` (cmd 31) · `58ca7ab0` (researcher tool grant) · `097fdc38` (cmd 30 rivals) ·
`bbe82bfa` (three-constitution reconciliation) · fabrik-lib `4f7dd414`. Sibling commits interleaved
in the window (quota-governance plan, Mistral keys) are NOT this surface.
**Anchor:** newest prior reports (cmd-27/cmd-25 audit reviews) carry commit-list `Surface:` lines —
not comparable hashes, no match by construction → full WIDE pass 1 (stated, not silently degraded).
**Rubric:** `python scripts/review_rubric.py --changed <the 10 changed files>` ran at pass 1 (150
lines armed — FLOOR + prompt-authoring + doc-integrity classes).
**Finder mechanism:** NO-POOL standing operator directive — solo native passes, declared; zero
flywheel rows is the directive's cost, not an omission. The closing pass applied the term-edit
FACTUAL-pass law this very surface shipped: re-derive every claim from source, don't re-verify cites.

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| C1 | fail-open/fail-closed | CLEAN | No new code guard in the surface; the one code-adjacent edit (`assemble_commands.py` recipe string) is rendered prose. The credits rule's failure direction is stated in-rule (short balance → ask, never spend the tail). Hunted: all 7 diffs. |
| C2 | cost/quota accounting | CLEAN | Credits endpoint fields (`total_credits`/`total_usage`) were live-verified before the rule shipped; negative-remaining collapses into "cannot cover → ask". The $3.65 figure is time-stamped as at-write-time, not asserted as current. |
| C3 | boundary/sentinel/prefix | CLEAN | Anchor phrases added verbatim-stable (`A bounded search returns "not found in N"` identical in all three files — byte-grep proven); no anchor reworded in place (procedure text edited AROUND the anchors only). |
| C4 | behavior-without-a-test | CLEAN | Deliberate ruling, named: the surface is governance PROSE consumed by LLMs — its graders are the corpus gate (54 files green), render parity (`--check` OK), the 7×3 anchor matrix, and fabrik-lib's drift checker (exit 0), all run this pass; a per-sentence prose grader would be wallpaper per the measure-first rule. |
| C5 | quantifier/denominator (anchor #7 applied to its own authors) | CLEAN | Every universal/negative claim in the 2h diffs re-derived with its denominator: "7 seats, 6 families, zero Anthropic" re-counted from `roster.py` (7/6/False) · hub § UNIVERSAL bullets counted 7 · template's anchor list counted 7 · "five-vs-six" pre-edit claim was verified against the pre-edit file during the reconciliation. |
| C6 | factual re-derivation | FIXED(1) | F1: the hub § UNIVERSAL parenthetical attributed the drift-checker's parse behavior to ruling `01KZXM0XA6`; fabrik-lib's own file separates the ruling (hub-owns-list) from the later parse-hardening (post proxy-by-mail). Reworded precisely. All other re-derivations pass: rivals grep-recipes return hits (1 · 6), the spec silence-guard renders (`FAILED grounding` in the installed command), fragment citations point at real ids/incidents (the close-feedback bullet deliberately cites NO mail id — the absence of mail IS its incident). |
| C7 | anchor integrity | CLEAN | 7×3 matrix GREEN, fresh at pass 1 AND the closing pass; `check_governance_drift.py` exit 0 against the edited hub file, fresh both passes. |
| C8 | render parity | CLEAN | `assemble_commands.py --check` OK (installed == rendered) fresh this run; corpus gate green across 54 files. |
| C9 | cross-file consistency | CLEAN | Hub/template/lib agree on all seven anchors and the reconciled rules; the one known asymmetry — lib's § UNIVERSAL prose still lists six bullets — is sanctioned by lib's OWN design (":353: the checker parses the hub's index... without anyone editing this file first") and their sessions hold the heads-up mail (01M178N7); not a defect by their contract. |
| C10 | prompt-authoring quality | CLEAN | The factual-pass sentence renders into both review twins (grep: 1 hit each in installed plan-review + spec-review); it complements rather than contradicts the probe duty (probes re-run, citations not re-verified — different objects). |
| C11 | script coupling | REFUTED(1) | F2: `assemble_commands.py` carries no `# AFTER-EDIT:` header — but the rule's scope is `scripts/**/*.py` (check_script_headers globs scripts/ only); the file is under `commands/`. Out of the rule's population — the denominator law applied to the rule itself. |

## Pass Ledger

- Pass 1 (WIDE) — all 11 classes, solo native (NO-POOL declared); probes: anchor matrix, render parity, roster re-count, bullet counts, rubric armed: found: 2, new: 2, fixed: 1
- Pass 2 (SCOPED) — F1's hunk + drift checker re-run (exit 0): found: 0, new: 0, fixed: 0
- Pass 3 (WIDE, closing — FACTUAL method: re-derive from source, non-author-fresh read) — anchor matrix GREEN, corpus 54 green, fragment/citation/recipe re-derivations all pass: found: 0, new: 0, fixed: 0

## Gate

Verbatim `python3 scripts/final_gate.py --json` top-level, run after the F1 fix + this report:

```json
{"status": "success", "tier": 2, "passed": 55, "failed": 0, "failures": []}
```
