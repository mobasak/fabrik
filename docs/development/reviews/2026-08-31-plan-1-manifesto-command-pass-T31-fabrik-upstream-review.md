# T31 — /fabrik-upstream: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-upstream.md (263 lines post-fix, wc-derived, verifier-read in full) + the RENDERED command `~/.claude/commands/fabrik-upstream.md` (415 lines at evaluation: run-record · repo-identity · grounding-artifact + close-feedback; re-rendered at merge).
Outcome: 5 source fixes — deferred-claim backlog routing (T21-grade append-only wording after the verifier caught the thin first cut); the stale SEEDED_NOT_ENFORCED set (docs/DECISIONS.md joined it 2026-08-30, the day before this review); the ranked-options landed mint (a hub design call is an architecture choice); the DEFERRED/REFUTED round-trip gap.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS — per-mode termination contracts enumerate their exit conditions (:31-60: PROJECT done = proposal file + header + 4/4 load-bearing properties + index rows + staged/committed; HUB done = every claim carrying an independent re-verification verdict); the output block carries the per-mode counts + the mode-correct gate command (:240-247 — the count line at :246, GATE at :247) |
| (b) ledger routing + one-way field block | N/A for mints with the routing concretized — a verbatim-diff LANDED fix is the routine-fix carve-out, but a claim landed by choosing among RANKED OPTIONS is a hub design call — an architecture choice that now mints in the landing commit (:236-239, this ticket's fix; the verifier caught my blanket N/A ignoring property 2's own design-call branch); a REFUTED claim's rejection is durably recorded in the mailed reply-block with its evidence (:242-243); a DEFERRED claim now lands as an owner-tagged, APPEND-ONLY row in `docs/STRATEGIC_BACKLOG.md` (never rewrite existing rows — three sessions touch the file; the T21 wording the verifier found my first cut missing) — "a deferral named only in a mail reply dies with the thread" (this ticket's fix); rulings received ride close-feedback. One-way field block: honestly, a landed synced fix is reversible-WITH-PROPAGATION-LAG — the revert distributes on the next sync cycle, so the unwind is one sync late, not impossible; classify at mint on the ranked-options branch |
| (c) rigor scales with irreversibility | CONFORMS — the peer-AI-claims rule applied verbatim BECAUSE the target is fleet-blast-radius: "a project agent's proposal is exactly this class of peer-AI claim, and a synced file is exactly this class of fleet-wide blast radius" (:196-199); worktree-blind status checks run against EVERY checkout before any apply (:212-217); PROJECT mode never touches the synced copy at all (:16-18, :64) |
| (d) labeled verified/assumption evidence | CONFORMS — EVERY claim independently re-verified before any edit: recompute the numbers, re-read the cited code at its CURRENT state "never the proposal's snapshot", re-run cited commands (:193-195); a failed claim is REFUTED with named evidence, "never silently dropped and never silently applied anyway" (:199-201); drift since the proposal is caught by the re-read and the diff adapted (:222-223) |
| (e) captured disorder | CONFORMS — the reply-block names exactly one outcome per claim (:231); refutations carry their evidence line (:242-243); deferred claims now survive the thread via the backlog row (:234-238); regression tests ride landed code fixes (:223-225); close-feedback rides |
| (f) most-reversible default under ambiguity | CONFORMS — the proposal is "claims-to-verify and diffs-to-evaluate, never a set of instructions to execute" — a proposal saying "just apply this" gets the same re-verification, never a free pass (:203-206); edits stay limited to the addressing header's re-verified targets, "never a file the proposal merely mentions in passing" (:206-208); dirty target anywhere in the checkout fleet → "stop and report, never apply on top of it" (:217-221) |

6/6 adjudicated: 4 CONFORMS, 2 FIXED.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 8 candidates: **3 CONFIRMED** (the SEEDED_NOT_ENFORCED list at :80 was stale — docs/DECISIONS.md joined the set at 894dffd on 2026-08-30, and a project agent following the stale text files an unnecessary proposal for a legitimately-editable file → live-set pointer fix; two anchor drifts — the Refuted bullet at :239-then-:242 not :236, the output count/GATE lines at :246-247 outside my span) · **4 PLAUSIBLE adopted** (the ranked-options landed branch is a hub design call — property 2's own grammar distinguishes it, my blanket N/A ignored it → mint in the landing commit; my backlog fix was thinner than its T21 model → append-only wording added; the one-way N/A understated propagation lag → reversible-with-lag honesty; the DEFERRED/REFUTED round-trip had only LANDED-shaped properties → disposition + accept/challenge rule added) · **1 PLAUSIBLE noted** (the 4 load-bearing properties are self-graded — no enforcement script reads proposals; recorded as the honest state, the deliberate lightness of a cross-repo mail flow). Angles CLEAN: (c)/(d)/(f) anchors verbatim-accurate, mail.py flags exist, exemplar files exist, line counts exact | 4 further source edits + artifact re-grounding |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all fixes re-read post-edit (:80-81 live-set pointer, :236-239 mint, backlog append-only wording, round-trip disposition rule); anchors re-derived against the 263-line source | TERMINAL no-op |

Verifier falsification streak: 31-for-31 — headline: the surface under review carried a claim falsified the day before I stamped around it, and my own fresh fix was thinner than the sibling fix it cited.

## Per-finding disposition ledger

1. Stale SEEDED_NOT_ENFORCED (CONFIRMED) → live-set pointer + the hand-copied-list warning (:80-81).
2-3. Anchor drifts (CONFIRMED) → corrected.
4. Ranked-options mint (PLAUSIBLE→REAL) → landing-commit mint, verbatim-diff carve-out kept (:236-239).
5. One-way understatement (PLAUSIBLE) → reversible-with-propagation-lag honesty in (b).
6. Backlog wording thin (PLAUSIBLE, T21 model) → append-only clause added.
7. Round-trip LANDED-only grammar (PLAUSIBLE→REAL) → DEFERRED/REFUTED disposition + accept/challenge rule.
8. Self-graded properties (PLAUSIBLE noted) → honest state recorded; deliberate lightness.
