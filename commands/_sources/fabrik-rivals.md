---
description: Competitive evidence BEFORE a spec exists — drives fabrik-lib's `competitor-intel` to a match-then-beat dossier at `docs/reference/rivals/<market>.md` that feeds `/fabrik-spec`: finds the rivals, mines their real reviews, builds a feature MATRIX, then a ranked MATCH list (what they have that we lack) and a ranked BEAT list (their review-proven weaknesses = our openings), plus a pricing wedge and white-space. Runs from ANY repo (fleet-synced driver, engine local-first then hub). NOT market-sizing. TRIGGER — EN: "who are our competitors", "what do rivals do better", "how do we beat X"; TR: "rakiplerimiz kim", "onları nasıl geçeriz" — fires bare-prose. SKIP: sizing a market · reviewing a spec (→ /fabrik-spec-review) · our own features (→ /fabrik-features). Stage: 1-design.
argument-hint: "[the market/category to scan] [optional: --us <our product> | --greenfield]"
---

> **POOL OFF (D-181).** Run every fan-out natively with Claude Task subagents (`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose); never write `NO-POOL:`. **Dispatch step (D-191):** run `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <N> [--heavy] [--risky <R>] [--mechanical <M>]` and dispatch exactly the `SEATS:` and mix it prints, all in ONE message, stamped BEFORE they go out with `python3 scripts/command_run.py dispatch --seats <n>` and closed with `python3 scripts/command_run.py round --seats <n> --findings <n> …`.

The engine is fabrik-lib's `competitor-intel` (vendored at `libs/competitor_intel`) driven by `scripts/rivals_run.py`; this command owns the evidence contract, the convergence loop and the hand-off into `/fabrik-spec`.

**Run it from ANY repo — there is no mode to pick and no hand-off.** The driver resolves the engine **local-first, then the hub's single vendored copy**, loads search keys from the env, the nearest `.env`, then `~/.config/fabrik/subagents.env`, and writes every artifact into the CALLING repo.

```
python scripts/rivals_run.py --market "<market>" --product-type <type> [--us-name X | --greenfield]
```

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
{{include:injection}}

## ⚠️ DISCOVERY termination — when the rival SET stops growing

⚠️ This governs the discovery/mining rounds, not the dossier-text loop below (`## ⚠️ Termination contract — READ FIRST`); do not apply its Pass-Ledger format here.

**The run is done when ALL of these hold:**

1. **Discovery is DRY** — a fresh `--rediscover` round surfaces no new competitor AND no new MATCH/BEAT item, twice in a row. ⚠️ **Only a `--rediscover` round can be dry** — without the flag the engine skips discovery entirely, so a plain re-run returns zero new rivals no matter how much of the market is unexplored (Phase 2).
2. **The trust audit returns zero unverifiable claims**, adjudicated per the split below.
3. **`truncated` is False** — the money ceiling never bound the run.
4. **`competitors` is non-empty.** Zero discovered rivals is a FAILED scan, not an empty market.
5. The dossier is written to `docs/reference/rivals/<market>.md` **in this repo**, its `INDEX.md` row exists, and the gate is green THIS run.

### The trust audit — split, because the rails are NOT uniform

- **Feature matrix · pricing wedge · white-space** — **re-groundable**: the verbatim quote must be a real substring of a real fetched source and the `source_url` must come from that source, not the LLM; re-verify by re-fetching, and a failing claim → `❓`, never a guess.
- **BEAT** is **Tier-C** (competitor-intel never held the raw review page): audit the ≥2-distinct-source corroboration gate and the source-weight inputs (`Signal.rating`, the subject domain), and label BEAT Tier-C in the dossier.
- **Adapter signals** — HN comments are unclassified (`neutral`) and do NOT auto-surface as BEAT openings; if you promote one, say who classified it.

{{include:term-edit}}

## Phase 0 — ground the inputs from THIS repo

Never ask the operator for what the repo already answers. Read:

1. `project.yaml::type` → the `product_type`; pass the scaffold type and let `rivals_run.py` alias it to the engine's own vocabulary (`saas mobile-app ecommerce website headless-api docs extension desktop`).
2. `docs/FEATURES.md` → our shipped features, verbatim, for the `us` side. Absent, or every row `Planned`? That is a **greenfield** run (`--greenfield`, `us=None`): rival-vs-rival.
3. `docs/BUSINESS_MODEL.md` (SaaS) → positioning and price points.
4. The market/category — ask only if `docs/` is silent.

## Phase 1 — pre-flight, then run

The engine **never raises** for a money or staging reason, so a wiring mistake yields a plausible empty dossier. Run `--preflight-only` first and read its checklist. The traps:

- **`--budget 0` is REJECTED, not unlimited.** "No ceiling" is a large number.
- **`legs` keys must be exactly `firecrawl`/`exa`/`brave`.**
- **The free leg (`brave`) estimate must be `<= 0`.**
- **`job_id` non-empty** — so a resume re-bills nothing.
- **every required SEARCH key present** — a missing key silently yields an empty dossier with `partial=True`. `--free-legs-only` requires only `BRAVE_API_KEY`.

Run each repo's OWN synced copy from inside that repo: a run from a directory inside some other checkout exits rc 2 with the `WIRING ERROR (nothing was spent)` label before any `.env` is read (`docs/reference/rivals-command.md` § The vacuous-loop trap).

## Phase 2 — converge: dry discovery + the split audit

**Parallelism — per RIVAL.** The engine mines sequentially and is not ours to change, so fan out the convergence rounds: **one native `fabrik-reviewer` seat per RIVAL plus the Opus authoritative seat** audit that rival's dossier section against its cited sources, in a single message. The rival count is the PARTITION; `dispatch_headroom.py --units <rivals> --mechanical 0` prints the seats.

⚠️ **Every convergence round MUST pass `--rediscover`, or the loop is vacuous.** The engine discovers ONCE per `job_id`, so a plain re-run cannot surface a new rival; `--rediscover` re-arms discovery, re-bills no mined review and re-unions the rivals already found.

```
round 1..N-1:  python scripts/rivals_run.py --market "<market>" ... --rediscover
round N:       python scripts/rivals_run.py --market "<market>" ...      # no flag — synthesis round
```

Each round: read the driver's `ROUND:` line (NEW count and running union), diff `competitors` / `match_list` / `beat_list` against the last round, and run the split trust audit over what is new. A round that adds a rival is never the last. Record a Pass Ledger row per round: `found:` / `new:` / `fixed:`.

⚠️ **A `!!` line from `--rediscover` VOIDS the round**: fix the checkpoint (or pass a fresh `--job-id`) and re-run it.

**The final round runs WITHOUT the flag** — the engine restores the full accumulated union and synthesizes the matrix over ALL of it. That round's dossier is the artifact.

**A rival you cannot corroborate is not a finding.** Drop it to `❓`.

## Phase 3 — the artifact, and the hand-off

⚠️ **`--out` must be on the FIRST invocation of the final round.** Without it the driver writes NOTHING and the round must be run again in full:

```bash
python scripts/rivals_run.py --market "<market>" [--us-name "<our product>"] \
  --out docs/reference/rivals/<slug>
```

`--out <slug>` writes BOTH `<slug>.json` and `<slug>.md` — pass the path WITHOUT an extension, and read the dossier from the written file.

Write `docs/reference/rivals/<market>.md` from **`rivals_run.py::render_dossier_md(dossier.to_dict())`**, not `dossier.to_markdown()`, which needs the live TYPED `Dossier` and raises `AttributeError` on the saved dicts; re-rendering an old run from disk takes the same path. Add a header with the **scan DATE** (`scanned_at`), the run's `job_id`, the model, the spend, `partial`/`truncated`, `--free-legs-only` or not, and the Pass Ledger. **Re-read the date before trusting an existing dossier** — an old one is never evidence about today's market.

Carry the renderer's `❓` callout for `verified: False` rivals through. Add the `INDEX.md` and `docs/README.md` rows.

State the hand-off:

- **MATCH** → the features `/fabrik-spec` must build, match or deliberately skip.
- **BEAT** → the problems to solve, and the "how we win" section: rivals' review-proven weaknesses, ranked.
- **pricing wedge + white-space** → positioning. Flag white-space as the weakest evidence (Tier-C search-excerpts).

**Scope, stated plainly in the dossier:** this is competitor and entry-opportunity intel, NOT market-sizing or demand validation. Never let a dossier be read as proof that a market is big enough.

## Guardrails — never

- **Never write a `--rediscover` round's dossier to `docs/reference/rivals/`.**
- **Never count a round the driver flagged `!!` as dry.** Discovery was skipped; it could not find.
- **Never present an unconfirmed rival as a real one.**
- **Never assert a trust rail a stage does not have.**
- **Never ship an UNDATED dossier**, and never read an old one as current.
- **Never prompt the operator for an API key** — a missing one is a provisioning escalation.
- **Never silently fork `libs/competitor_intel`.** File upstream.
- **Never treat `truncated=True` as a footnote.** The scan is partial.

{{include:questionbar}}

## Upstream

A defect in the vendored engine goes upstream through **fabrik-mail**: `python scripts/mail.py send --to fabrik-lib --kind upstream-feedback --ack required` with the symptom + fix + `path:line` evidence. Never append to fabrik-lib's own `UPSTREAM_FEEDBACK.md` yourself — `/opt/fabrik-lib` is another repo, and writing there is the cross-repo HARD STOP. Re-vendor to pick up a fix.

{{include:close-chain}}
