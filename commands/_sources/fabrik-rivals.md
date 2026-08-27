---
description: Competitive evidence BEFORE a spec exists — drives fabrik-lib's `competitor-intel` to a match-then-beat dossier at `docs/reference/rivals/<market>.md` that feeds `/fabrik-spec`: finds the rivals, mines their real reviews, builds a feature MATRIX, then a ranked MATCH list (what they have that we lack) and a ranked BEAT list (their review-proven weaknesses = our openings), plus a pricing wedge and white-space. Runs from ANY repo (fleet-synced driver, engine local-first then hub). NOT market-sizing. TRIGGER — EN: "who are our competitors", "what do rivals do better", "how do we beat X"; TR: "rakiplerimiz kim", "onları nasıl geçeriz" — fires bare-prose. SKIP: sizing a market · reviewing a spec (→ /fabrik-spec-review) · our own features (→ /fabrik-features). Stage: 1-design.
argument-hint: "[the market/category to scan] [optional: --us <our product> | --greenfield]"
---

Produce the competitive evidence a product should be spec'd on, so the ANGLE, the FEATURES and the
PROBLEMS-TO-SOLVE come from real rivals and real reviews instead of vibes. The engine is fabrik-lib's
`competitor-intel` (vendored at `libs/competitor_intel`; the driver resolves it local-first, then
the hub's copy) driven by
`scripts/rivals_run.py`; this command owns the brief, the evidence contract, the convergence loop and
the hand-off into `/fabrik-spec`.

**Run it from ANY repo — there is no mode to pick and no hand-off.** `scripts/rivals_run.py` is
fleet-synced, so every project already has it, and it resolves the engine **local-first, then the
hub's single vendored copy**. The search keys already reach every project through the synced
`libs/subagents` autoloader. Every artifact it writes lands in the CALLING repo.

```
python scripts/rivals_run.py --market "<market>" --product-type <type> [--us-name X | --greenfield]
```

⚠️ **An earlier version of this command split the work across two repos** — a project filed a brief by
mail and the operator opened a hub session to run it. That was built on a misreading of the
cross-repo hard stop, which governs *"create/edit/**commit** files in a repo OTHER than the one you
were launched in"* — **writes**, not reads. Importing the hub's vendored engine and writing only into
your own tree breaks nothing, and the two-hop version turned a one-rival scan into a cross-repo
errand. If the engine is in neither place the driver says so and names the fix; it never degrades to
a hand-off.

{{include:run-record}}
{{include:injection}}

## ⚠️ DISCOVERY termination — when the rival SET stops growing

⚠️ Distinct from the dossier-text convergence loop below (`## ⚠️ Termination contract — READ FIRST`),
which converges the WRITTEN dossier to an md5-verified no-op with its own Pass Ledger. This one
governs the discovery/mining rounds — whether the set of rivals is complete. Two loops, two
mechanisms: do not apply the Pass-Ledger format to these rounds (youtube, 2026-08-27, lost real time
to the two sections sharing a header).

**The run is done when ALL of these hold** — this is a LOOP, not a single shot:

1. **Discovery is DRY** — a fresh `--rediscover` round surfaces no new competitor AND no new
   MATCH/BEAT item. Two consecutive dry rounds, not one: unknown-size discovery never terminates
   honestly on a fixed round count, and the tail is where the non-obvious rival lives. ⚠️ **Only a
   `--rediscover` round can be dry** — without the flag the engine skips discovery entirely, so a
   plain re-run returns zero new rivals no matter how much of the market is unexplored (Phase 2).
2. **The trust audit returns zero unverifiable claims**, adjudicated per the split below.
3. **`truncated` is False.** `truncated=True` means the money ceiling BOUND the run — partial by
   budget, and with the standing no-ceiling policy it should never fire. If it does, that is a LOUD
   finding, never a footnote.
4. **`competitors` is non-empty.** Zero discovered rivals is a FAILED scan, not an empty market.
5. The dossier is written to `docs/reference/rivals/<market>.md` **in this repo**, its `INDEX.md` row
   exists, and the gate is green THIS run.

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

## Phase 0 — ground the inputs from THIS repo

Never ask the operator for what the repo already answers. Read, in this order:

1. `project.yaml::type` → the `product_type`. The engine's vocabulary is its OWN
   (`saas mobile-app ecommerce website headless-api docs extension desktop`), NOT the fabrik
   `SCAFFOLD_TYPES` strings — `rivals_run.py` maps them, so pass the scaffold type and let it alias.
2. `docs/FEATURES.md` → our shipped features, verbatim, for the `us` side of the matrix. Absent, or
   every row `Planned`? That is a **greenfield** run (`--greenfield`, `us=None`) and the matrix
   becomes rival-vs-rival — the headline use case, not a degraded one.
3. `docs/BUSINESS_MODEL.md` (SaaS) → positioning and price points, for the pricing wedge.
4. The market/category — the ONE thing the repo often cannot answer, and the question worth asking
   if `docs/` does not state it.

## Phase 1 — pre-flight, then run

`rivals_run.py` pre-flights every wiring trap BEFORE spending, because the engine **never raises**
for a money or staging reason — so a wiring mistake yields a dossier that looks like a completed run.
Run `--preflight-only` first and read its checklist; it reports which engine copy it resolved
(`local` or `hub`).

The traps, all of which produce a plausible-looking empty dossier rather than an error:

- **`--budget 0` is REJECTED, not treated as unlimited.** The engine documents `0`/absent as "run NO
  research" while still returning a `Dossier`. "No ceiling" is spelled as a large number.
- **`legs` keys must be exactly `firecrawl`/`exa`/`brave`** — they must match the shipped packs' leg
  names, or the engine raises a wiring `ValueError` at entry.
- **The free leg (`brave`) estimate must be `<= 0`** — a positive estimate silently breaks the
  ceiling arithmetic from the first call.
- **`job_id` non-empty** — the double-book guard, so a resume re-bills nothing.
- **every required SEARCH key present** — a missing key raises nowhere: the leg fails, the engine
  degrades, and you get an empty dossier with `partial=True`. The pre-flight names the missing key,
  because the engine cannot. `--free-legs-only` requires only `BRAVE_API_KEY`.

## Phase 2 — converge: dry discovery + the split audit

⚠️ **Every convergence round MUST pass `--rediscover`, or the loop is vacuous.** The engine discovers
ONCE per `job_id` (`orchestrator.py:566` guards it on a persisted `discovery_done`), and the driver
derives `job_id` deterministically from the market — so a plain re-run cannot surface a new rival **by
construction**, and condition 1 above would auto-satisfy at round 2. That is not a dry market; it is
the question never being asked. `--rediscover` re-arms the discovery leg while re-billing no mined
review, and re-unions the rivals already found (the engine REPLACES the competitor list rather than
merging it, so without the union a thinner round silently drops rivals).

```
round 1..N-1:  python scripts/rivals_run.py --market "<market>" ... --rediscover
round N:       python scripts/rivals_run.py --market "<market>" ...      # no flag — synthesis round
```

Loop. Each round: re-run discovery with `--rediscover`, read the driver's `ROUND:` line (it prints the
NEW count and the running union — a dry round is a MEASURED fact, never an assumption), diff the new
`competitors` / `match_list` / `beat_list` against the last round, and run the split trust audit over
whatever is new. A round that adds a rival is never the last round. Record a Pass Ledger row per round
with `found:` / `new:` / `fixed:`, exactly as the review commands do.

⚠️ **A `!!` line from `--rediscover` VOIDS the round.** If the driver reports that the checkpoint could
not be rewritten, discovery was SKIPPED — that round's zero-new result is not a dry round and must not
be counted toward the two. Fix the checkpoint (or pass a fresh `--job-id`) and re-run it.

**The final round runs WITHOUT the flag** — the engine then restores the full accumulated union as its
competitor set, mines any still-unmined reviews, and synthesizes the matrix over ALL of them. That
round's dossier is the artifact; a `--rediscover` round's dossier covers only that round's fresh
discoveries and must never be written to `docs/reference/rivals/`.

**A rival you cannot corroborate is not a finding.** Drop it to `❓` and say so. The failure mode here
is a confident, well-formatted, fabricated competitor — which is why the audit re-fetches rather than
re-reads.

## Phase 3 — the artifact, and the hand-off

Write `docs/reference/rivals/<market>.md` from **`rivals_run.py::render_dossier_md(dossier.to_dict())`**
— not from `dossier.to_markdown()`. ⚠️ **The reason is a SHAPE mismatch, not a quality gap** (corrected
2026-08-27): `to_markdown()` requires the live TYPED `Dossier` (`m.universal`, `b.weight` — it raises
`AttributeError` on plain dicts), while the driver writes the JSON payload BEFORE rendering, because
the money is already spent and a formatting bug must never destroy a paid run. There is no
`Dossier.from_dict()`, so the saved payload can only be rendered from dicts. Re-rendering an old run
from disk needs the same path.

The earlier justification — that `to_markdown()` emitted only 404 bytes — was measured against the
PRE-`e818249` engine and is now FALSE: upstream rebuilt it, and it emits all six sections
(COMPETITORS · FEATURE MATRIX · MATCH · BEAT · PRICING · WHITE SPACE) with its own render-safety
suite. Do not repeat the retired claim. Add a header carrying the **scan DATE** (the driver stamps `scanned_at`; a dossier with no date
reads as current forever, and competitive intel is perishable — rival pricing, features and review
sentiment all move), the run's `job_id`, the model, the spend, `partial`/`truncated`, whether it
ran `--free-legs-only`, and the Pass Ledger. **Re-read the date before trusting an existing
dossier** — an old one is a starting point for a fresh scan, never evidence about today's market.

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

## Guardrails — never

Scope lives in the phases above; these are the actions that make a RUN defective.

- **Never write a `--rediscover` round's dossier to `docs/reference/rivals/`.** It covers that round's
  fresh discoveries only; the artifact is the final no-flag round's synthesis over the full union.
- **Never count a round the driver flagged `!!` as dry.** Discovery was skipped; it could not find.
- **Never present an unconfirmed rival as a real one.** `verified: False` renders `❓` and is named in
  the callout — carry that through; a fabricated competitor reaching a spec starts here.
- **Never assert a trust rail a stage does not have.** BEAT is Tier-C and cannot be re-grounded like
  the matrix; say so rather than implying uniform provenance.
- **Never ship an UNDATED dossier**, and never read an old one as current.
- **Never prompt the operator for an API key** — a missing one is a provisioning escalation.
- **Never silently fork `libs/competitor_intel`.** A vendored copy cannot fix itself; file upstream.
- **Never treat `truncated=True` as a footnote.** The money ceiling bound the run; the scan is partial.

{{include:questionbar}}

## Upstream

The engine is vendored, so a copy cannot fix itself. A defect belongs upstream: append a dated note to
`/opt/fabrik-lib/competitor-intel/UPSTREAM_FEEDBACK.md` (symptom + fix) — or mail fabrik-lib — and
never silently fork `libs/competitor_intel`. Re-vendor to pick up a fix.
