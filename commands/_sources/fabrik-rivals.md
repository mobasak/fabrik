---
description: Competitive evidence BEFORE a spec exists — drives fabrik-lib's `competitor-intel` to a match-then-beat dossier at `docs/reference/rivals/<market>.md` that feeds `/fabrik-spec`: finds the rivals, mines their real reviews, builds a feature MATRIX, then a ranked MATCH list (what they have that we lack) and a ranked BEAT list (their review-proven weaknesses = our openings), plus a pricing wedge and white-space. Two modes by repo identity — PROJECT briefs, HUB runs. NOT market-sizing. TRIGGER — EN: "who are our competitors", "what do rivals do better", "how do we beat X"; TR: "rakiplerimiz kim", "onları nasıl geçeriz" — fires bare-prose. SKIP: sizing a market · reviewing a spec (→ /fabrik-spec-review) · our own features (→ /fabrik-features). Stage: 1-design.
argument-hint: "[the market/category to scan] [optional: --us <our product> | --greenfield] [HUB mode: the brief path]"
---

Produce the competitive evidence a product should be spec'd on, so the ANGLE, the FEATURES and the
PROBLEMS-TO-SOLVE come from real rivals and real reviews instead of vibes. The engine is fabrik-lib's
`competitor-intel` (vendored at `libs/competitor_intel`, hub-side) driven by
`scripts/rivals_run.py`; this command owns the brief, the evidence contract, the convergence loop and
the hand-off into `/fabrik-spec`.

**This command is two commands wearing one name** — pick the mode by repo identity (never a bare cwd
string, and never by asking):

- **PROJECT mode** (repo identity ≠ `/opt/fabrik`) — grounds and files the BRIEF. **Where this runs:**
  any project, with local project tooling only — no hub shell-out, no vendored engine, no API keys.
  The project owns what only the project knows (what we ship, who we think we compete with, which
  market); the hub owns execution.
- **HUB mode** (repo identity = `/opt/fabrik`, given a brief) — wires the engine and runs it, then
  replies with the dossier. **Where this runs:** hub-side only — the hub holds the single vendored
  copy and the fleet's curated keys. Identity is tested by CONTENT, never a bare path string:
  `scripts/fabrik_synced_manifest.py` present at the toplevel = HUB (a relocated or DR hub clone is
  still the hub); a `/opt/fabrik` **worktree** IS hub-repo — run it there, never file a brief to
  yourself.

{{include:run-record}}
{{include:repo-identity}}
{{include:injection}}

## ⚠️ Termination contract

Two contracts, one per mode. Never let one mode's "done" stand in for the other's.

**PROJECT mode is done when:** the brief exists, every claim in it is grounded in this repo (not
recalled), it has been sent to the hub with `--to fabrik --to-agent infra`, and the send is verified
**on disk** — `mail.py send` echoes your body back inside an argparse error if the flags are wrong,
so a tail of its output looks identical whether it sent or failed. Confirm the message file exists
before claiming it was filed.

**HUB mode is done when ALL of these hold** — this is a LOOP, not a single shot:

1. **Discovery is DRY** — a fresh round surfaces no new competitor AND no new MATCH/BEAT item.
   Unknown-size discovery never terminates honestly on a fixed round count; the tail is where the
   non-obvious rival lives. Two consecutive dry rounds, not one.
2. **The trust audit returns zero unverifiable claims**, adjudicated per the split below.
3. **`truncated` is False.** `truncated=True` means the money ceiling BOUND the run — the dossier is
   partial-by-budget, and with the standing no-ceiling policy it should never fire. If it does, that
   is a LOUD finding (a runaway discovery), never a footnote: report it and raise the budget.
4. **`competitors` is non-empty.** Zero discovered rivals is a FAILED scan, not an empty market.
5. The dossier is written to `docs/reference/rivals/<market>.md`, its `INDEX.md` and
   `docs/README.md` rows exist, and the gate is green THIS run.

### The trust audit — split, because the rails are NOT uniform

The engine's guarantees differ by stage, and claiming one rail for all of them is an overclaim the
module's own review already had to scope out of its README. Audit accordingly:

- **Feature matrix · pricing wedge · white-space** — competitor-intel HOLDS the fetched source text
  for these, so each claim is **re-groundable**: the verbatim quote must be a real substring of a
  real fetched source, and the `source_url` must come from that source rather than from the LLM.
  Re-verify by re-fetching, not by re-reading the dossier. Any claim that fails → `❓`, never a guess.
- **BEAT** — these are deep-research's review cards; competitor-intel never held the raw review page,
  so BEAT is **Tier-C** and cannot be re-grounded the same way. Audit what actually exists: the
  ≥2-distinct-source corroboration gate, and the source-weight inputs (`Signal.rating`, the
  subject domain). Label BEAT Tier-C in the dossier. Do not assert a rail this stage does not have.
- **Adapter signals** — HN comments are unclassified (`neutral`): they enrich the signal and feature
  extraction but do NOT auto-surface as BEAT openings. An unclassified mention is not a proven
  weakness; if you promote one, say who classified it.

{{include:term-edit}}

## Phase 0 — PROJECT mode: ground the brief

Never ask the operator for what the repo already answers. Read, in this order:

1. `project.yaml::type` → the `product_type`. The engine's vocabulary is its OWN
   (`saas mobile-app ecommerce website headless-api docs extension desktop`), NOT the fabrik
   `SCAFFOLD_TYPES` strings — `scripts/rivals_run.py` maps them, so pass the scaffold type and let it
   alias. An unknown type degrades to Tier-C with no venue hints; it never errors.
2. `docs/FEATURES.md` → our shipped features, verbatim, for the `us` side of the matrix. If the file
   is absent or every row is `Planned`, this is a **greenfield** run (`--greenfield`, `us=None`) and
   the matrix becomes rival-vs-rival. That is the headline use case, not a degraded one.
3. `docs/BUSINESS_MODEL.md` (SaaS) → positioning and price points, for the pricing wedge.
4. The market/category. This is the ONE thing the repo often cannot answer — it is the question worth
   asking if `docs/` does not state it.

The brief names: the market, the product type, `us` (name + category + the feature list, verbatim
from FEATURES.md) or greenfield, any rivals we already believe we have, and what decision the dossier
is meant to inform. Send it, then verify the file on disk.

## Phase 1 — HUB mode: pre-flight, then run

`scripts/rivals_run.py` pre-flights every wiring trap BEFORE spending, because the module's contract
is that `run()` **never raises** for a money or staging reason — so a wiring mistake yields a dossier
that looks like a completed run. Run `--preflight-only` first and read its checklist:

```
python scripts/rivals_run.py --market "<market>" --product-type <type> --greenfield --preflight-only
```

The traps, all of which produce a plausible-looking empty dossier rather than an error:

- **`--budget 0` is REJECTED, not treated as unlimited.** The module documents `0`/absent as "run NO
  research" while still returning a `Dossier`. "No ceiling" is spelled as a large number (the default
  is `1000`); `0` is the fail-silent-green sentinel.
- **`legs` keys must be exactly `firecrawl`/`exa`/`brave`** — they must match the shipped packs' leg
  names, or `run()` raises a wiring `ValueError` at entry.
- **The free leg (`brave`) estimate must be `<= 0`** — a positive estimate silently breaks the ceiling
  arithmetic from the first call.
- **`job_id` non-empty** — it is the double-book guard, so a resume re-bills nothing.

### What this costs, and what it must never cost

**The LLM is `claude -p` — subscription-billed — and this command dispatches NO agents.** No pool
`fanout`, no Task subagents, no metered LLM API. `ANTHROPIC_API_KEY` is reserved for
`fabrik ai generate` and must never reach this path. The binding constraint on `claude -p` is the
weekly QUOTA, not dollars, and the `total_cost_usd` the CLI reports is an API-equivalent lens rather
than real spend (`scripts/claude_p_cost.py`).

`claude -p` runs from a NEUTRAL cwd on purpose: it loads the CLAUDE.md of whatever tree it runs in,
so running it from the hub prepends ~34k tokens of governance to every synthesis call (measured
33,953 cache-creation tokens from the repo vs 11,611 from an empty dir) — wasteful, and wrong on the
merits, since an agent contract is not context for "summarise these review excerpts".

The ONLY metered spend left is the **search legs**: Exa and Firecrawl. `brave` is free, so
`--free-legs-only` runs the entire scan at zero marginal cost with thinner discovery — say which mode
you ran in the dossier. Search keys come from `libs.subagents.load_env` (the fleet's curated autoload
carries `EXA_API_KEY`, `BRAVE_API_KEY`, `FIRECRAWL_API_KEY`). **Never prompt the operator for a key
and never hardcode one** — a missing key is a provisioning escalation.

Then run it for real, writing both artifacts, and read the SUMMARY line honestly: `partial=True` means
a leg failed, `truncated=True` means the ceiling bound the run.

## Phase 2 — converge: dry discovery + the split audit

Loop. Each round: re-run discovery (the checkpoint re-bills nothing for completed work), diff the new
`competitors` / `match_list` / `beat_list` against the last round, and run the split trust audit over
whatever is new. A round that adds a rival is never the last round. Record a Pass Ledger row per round
with `found:` / `new:` / `fixed:`, exactly as the review commands do.

**A rival you cannot corroborate is not a finding.** Drop it to `❓` and say so. The failure mode here
is a confident, well-formatted, fabricated competitor — which is why the audit re-fetches rather than
re-reads.

## Phase 3 — the artifact, and the hand-off

Write `docs/reference/rivals/<market>.md` from **`rivals_run.py::render_dossier_md(dossier.to_dict())`**
— NOT from `dossier.to_markdown()`. Measured on a real 12-rival scan: the engine's own markdown emitted
**404 bytes** (market line, spend, one BEAT item) while the structured payload held all twelve rivals,
a 12x44 feature matrix and the pricing models. The engine's markdown is a summary; this artifact is
what a spec gets decided on. Add a header carrying the run's `job_id`, the model, the spend,
`partial`/`truncated`, whether it ran `--free-legs-only`, and the Pass Ledger.

**Never let an unconfirmed rival read as a real one.** The engine sets `verified` per competitor; on
that same run **5 of 12** were `verified: False` ("No page text retrieved"). The renderer marks them
`❓` and names them in a callout — carry that through, because an unconfirmed name sitting in a list
of real ones is exactly how a fabricated competitor reaches a spec. `docs/reference/**/*.md` is already inside the gate-enforced `.md` allowlist, so this
needs no governance change. Add the `INDEX.md` and `docs/README.md` rows — the ordinary Doc Sync
Matrix obligation for a new file under `docs/reference/`, not an exemption.

Then state the hand-off explicitly, because it is the whole point of running before a spec:

- **MATCH** → the features `/fabrik-spec` must decide to build, match or deliberately skip.
- **BEAT** → the problems to solve, and the "how we win" section. This is the ranked list of rivals'
  review-proven weaknesses — the openings.
- **pricing wedge + white-space** → positioning. Flag white-space as the weakest evidence: it is
  incumbent/discourse-anchored, it surfaces needs people are already voicing, and for four of five
  product types it degrades entirely to Tier-C search-excerpts.

**Scope, stated plainly in the dossier:** this is competitor and entry-opportunity intel, NOT
market-sizing or demand validation. A spec still needs that separately. Never let a dossier be read as
proof that a market is big enough.

{{include:questionbar}}

## Upstream

The engine is vendored, so a copy cannot fix itself. A defect belongs upstream: append a dated note to
`/opt/fabrik-lib/competitor-intel/UPSTREAM_FEEDBACK.md` (symptom + fix) — or mail fabrik-lib — and
never silently fork `libs/competitor_intel`. Re-vendor to pick up a fix.
