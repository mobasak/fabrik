# T24 — /fabrik-rivals: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-rivals.md (221 lines, wc-derived, read in full; grep-derived anchors — no source edits this ticket) + the RENDERED command `~/.claude/commands/fabrik-rivals.md` (375 lines: run-record :30-65 · injection · term-edit :106-131 · questionbar :269-272 · close-feedback :282-375 — all spans verifier-confirmed). Side artifact: docs/DECISIONS.md D-050 minted (the 2026-08-26 rivals-budget ruling pair, previously living only in code comments — the T20 unminted-standing-policy class).
Outcome: zero source fixes (the source conforms) + 1 ledger mint + artifact re-adjudication of (a)/(b).

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors) |
|---|---|
| (a) checkable gates | CONFORMS (honestly split) — PER-ROUND measurement is MECHANICAL: the driver's ROUND: line prints the new count + running union (rivals_run.py:1013-1015, verifier-confirmed), a `!!` line voids the round (:131-133), only `--rediscover` rounds CAN be dry — a plain re-run returns zero by construction (:43-47, :111-118). The TWO-CONSECUTIVE-DRY count is SELF-GRADED across invocations — `check_rivals_dossier.py:19` says itself it "cannot tell a genuinely dry discovery round from one that never re-ran"; the round ledger is the graded trace. `truncated=False`, non-empty `competitors`, gate green THIS run are enumerated exits (:49-54); the two loops explicitly distinguished (:33-39) |
| (b) ledger routing + one-way field block | N/A for in-run mints, with the provenance gap CLOSED at the ledger: the "standing no-ceiling policy" the source cites (:49-51, :98-99) and the claude-p/agents rejection were UNMINTED operator rulings living in rivals_run.py code comments — D-050 now records both with their 2026-08-26 date and verbatim quote (the T20 class, this time closable because the in-code provenance is strong). Spend is NOT "bounded" — the honest statement: the no-ceiling design is a RECORDED ruling (D-050) that overrides the manifesto's default budget-cap invariant exactly the way the manifesto wants — by a findable decision, with `truncated` as the after-the-fact tripwire, never a cap. The dossier feeds /fabrik-spec, whose approval mints (the T18→T28 chain) |
| (c) rigor scales with irreversibility | CONFORMS — the trust audit is SPLIT because "the rails are NOT uniform": matrix/pricing/white-space re-groundable against held source text; BEAT is Tier-C, "do not assert a rail this stage does not have" (:56-71); white-space flagged weakest with per-type degradation stated (:188-190); perishability dating mandatory (:170-174) |
| (d) labeled verified/assumption evidence | CONFORMS — re-verification by RE-FETCHING, never re-reading (:63-64); failed claims → ❓, "never a guess" (:64); `verified: False` rivals render ❓ and are NAMED (:176-179, :203-204); the retired 404-byte claim corrected in-source with "Do not repeat the retired claim" (:167-170); "grep, don't trust a line number" (:156); unclassified signals never auto-promote — "say who classified it" (:69-71) |
| (e) captured disorder | CONFORMS — `truncated=True` is "a LOUD finding, never a footnote" (:49-51, :210); the NOT-market-sizing disclaimer lives IN the dossier (:192-194); the header carries date/job_id/model/spend/partial/mode + Pass Ledger (:170-173); both youtube live losses recorded in-source (verifier confirmed the CHANGELOG citations real); close-feedback rides |
| (f) most-reversible default under ambiguity | CONFORMS — uncorroborated rival → ❓ "and say so" (:140-142); missing API key → provisioning escalation, never a prompt (:208); vendored engine never silently forked — the mail route, which the verifier's probe strengthens (competitor-intel has NO UPSTREAM_FEEDBACK.md file, so mail is the ONLY channel, exactly as written) (:209, :214-221); `--budget 0` REJECTED rather than reinterpreted (:98-99); greenfield is "the headline use case, not a degraded one" (:82-84) |

6/6 adjudicated: 5 CONFORMS (two honestly re-split), 1 N/A-with-ledger-mint. Source unmodified — the first zero-source-fix ticket of the pass; the fixes landed in the LEDGER and in this artifact's honesty.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 6 candidates: **1 CONFIRMED** (my Surface line claimed 222 lines; wc/awk agree on 221 — the phantom-trailing-newline line, the denominator class again) · **1 PLAUSIBLE-strong ADOPTED** (the no-ceiling + claude-p-rejection rulings had ZERO ledger rows despite verbatim in-code provenance — D-050 minted, decisions.py --check exit-0) · **2 PLAUSIBLE adopted as artifact honesty** ((b)'s "bounded by preflight" conflated wiring checks with a financial cap — rewritten: no-ceiling is a RECORDED ruling overriding the manifesto's default cap-invariant by findable decision; (a)'s "MEASURED not felt" overclaimed — the per-round line is mechanical, the two-round count is self-graded, check_rivals_dossier admits it) · **2 weak adjudicated** (UPSTREAM_FEEDBACK.md nonexistence STRENGTHENS the mail-only route — noted; the docs/README per-file-row prescription matches the Doc Sync Matrix verbatim — existing docs' missing rows are pre-existing debt, REFUTED as this command's defect). Angles CLEAN: every executable claim verified against driver+engine (preflight, rediscover, ROUND:, !!, render_dossier_md, discovery_done guard, min_sources=2, fleet-sync manifest), all fragment spans exact, youtube citations real | 1 ledger mint + artifact re-grounding; no source edits |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — D-050 verified in-ledger (checker exit-0), all cited anchors re-grepped against the 221-line source | TERMINAL no-op |

Verifier falsification streak: 24-for-24 — this round's substance was OUTSIDE the source: an unminted operator ruling pair and my own conflation of wiring-preflight with a spend bound.

## Per-finding disposition ledger

1. 222-vs-221 denominator (CONFIRMED) → fixed; wc-derived.
2. Unminted 2026-08-26 ruling pair (PLAUSIBLE-strong) → D-050 minted with in-code provenance; checker exit-0.
3. "Bounded by preflight" conflation (PLAUSIBLE) → (b) rewritten: recorded-ruling override + truncated-as-tripwire.
4. Two-round count self-graded (PLAUSIBLE) → (a) honestly split; check_rivals_dossier's own admission cited.
5. UPSTREAM_FEEDBACK.md nonexistence (weak) → noted: strengthens the mail-only route as written.
6. docs/README row prescription (weak) → REFUTED as a defect: the source matches the Doc Sync Matrix; missing rows on older docs are pre-existing debt.
