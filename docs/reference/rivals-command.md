# `/fabrik-rivals` — competitive evidence before a spec exists

**What this covers:** the `/fabrik-rivals` command, its fleet-synced driver `scripts/rivals_run.py`, and
the wiring contract between them and the vendored `competitor-intel` engine. The engine itself is a
fabrik-lib module and is documented there (`/opt/fabrik-lib/competitor-intel/README.md`); this doc is
about the *fabrik* half — where the command sits, what it costs, and the traps that make a broken run
look like a successful one.

---

## Why it exists, and where it sits

A product spec decides an ANGLE, a FEATURE set, and a set of PROBLEMS-TO-SOLVE. Those three decisions
are worth more when they come from what rivals actually ship and what their users actually complain
about. `/fabrik-rivals` produces that evidence and hands it to `/fabrik-spec`:

| Dossier output | What it seeds in the spec |
|---|---|
| **MATCH** — features rivals have that we lack (★ = universal gap) | the features to build, match, or deliberately skip |
| **BEAT** — rivals' corroborated review weaknesses | the problems to solve, and "how we win" |
| **pricing wedge** + **white-space** | positioning |

It sits at stage `1-design`, **before** `/fabrik-spec` — which is why the engine's `us` parameter is
optional. A greenfield run (`us=None`) produces a rival-vs-rival landscape, and that is the headline
use case, not a degraded one.

**Out of scope, stated so a dossier is never read as more than it is:** this is competitor and
entry-opportunity intel, **not market-sizing or demand validation**. A spec still needs that
separately. White-space is incumbent/discourse-anchored — it surfaces needs people are already
voicing, never a blue ocean nobody has mentioned.

## One mode: every repo runs its own scan

**There is no mode to pick and no hand-off.** Any repo — hub or project, old or new — runs the scan
itself and writes every artifact into its own tree.

Two things make that work. `scripts/rivals_run.py` is a **`CORE_SCRIPT`**
(`scripts/fabrik_synced_manifest.py:41`), so it is fleet-synced into every project and scaffolded into
every new one. And it resolves the engine **local-first, then the hub's single vendored copy**
(`rivals_run.py::_resolve_engine`) — a project imports `/opt/fabrik/libs/competitor_intel` rather than
vendoring `deep-research` + `web-tools` + `competitor-intel` into all ~46 repos. Search keys reach
every project through the synced `libs/subagents` autoloader. If the engine is in neither place the
driver says so and names the fix; it never degrades to a hand-off.

⚠️ **An earlier version of this command split the work across two repos** — a project filed a brief by
mail and the operator opened a hub session to run it. That was built on a **misreading of the
cross-repo HARD STOP**, which governs *"create/edit/**commit** files in a repo OTHER than the one you
were launched in"* — **writes**, not reads. Importing the hub's vendored engine while writing only
into your own tree breaks nothing, and the two-hop version turned a one-rival scan into a cross-repo
errand (which is exactly how a project agent got stuck, 2026-08-27). The split is gone; do not
reintroduce it.

## What it costs

**The LLM is `claude -p` — subscription-billed — and the command dispatches NO agents.** No pool
`fanout`, no Task subagents, no metered LLM API (operator directive, 2026-08-26). `ANTHROPIC_API_KEY`
is reserved for `fabrik ai generate` and must never reach this path. The binding constraint is the
weekly **quota**, not dollars; the `total_cost_usd` the CLI reports is an API-equivalent lens rather
than real spend (see `scripts/claude_p_cost.py`).

`claude -p` is invoked from a **neutral cwd** on purpose. It loads the CLAUDE.md of whatever tree it
runs in, so running it from the hub prepends the entire hub governance contract to every synthesis
call — measured **33,953** cache-creation tokens from `/opt/fabrik` versus **11,611** from an empty
directory. It is also wrong on the merits: an agent contract is not context for "summarise these
review excerpts", and leaking it invites the model to follow instructions aimed at an agent.

The only metered spend left is the **search legs** — Exa and Firecrawl. `brave` is the free leg, so
`--free-legs-only` runs an entire scan at zero marginal cost with thinner discovery. The dossier
should say which mode produced it.

**Budget policy: no ceiling** (operator, 2026-08-26) — spelled as a large number, never `0`.

## The traps — why a broken run looks like a good one

The engine's contract is that `run()` **never raises** for a money or staging reason: a failed leg
degrades to `partial`, exhausted money sets `truncated`. Its only exception is a wiring `ValueError`
at entry. The consequence is that **every wiring mistake yields a dossier that looks complete**, so
`scripts/rivals_run.py::_preflight` checks each one before spending:

| Trap | Why it is silent | Guard |
|---|---|---|
| `total_budget_usd=0` | documented as "run NO research" — still returns a `Dossier` | REJECTED, never treated as unlimited |
| a negative budget | the same unasked question with a different sign | REJECTED (`<= 0`, not `== 0`) |
| `legs` keys ≠ `firecrawl`/`exa`/`brave` | must match the shipped packs' leg names | checked, with the fix named |
| a wired leg with no estimate | disables the ceiling for that leg | checked |
| free leg estimate > 0 | breaks the ceiling arithmetic from the first call | checked |
| empty `job_id` | the double-book guard for resume | checked |
| `checkpoint_dir` outside the repo | a tmpfs reboot drops the checkpoints that make a resume free | checked |
| **a missing search key** | the leg fails, the engine degrades, and you get an EMPTY dossier with `partial=True` — and the engine cannot tell you WHICH key | checked, naming the key; `--free-legs-only` requires only `BRAVE_API_KEY` |
| an unknown `product_type` | degrades to Tier-C with no venue hints rather than erroring | checked, with the scaffold aliases listed |

`--preflight-only` runs all of them and exits without spending. **Never prompt the operator for a
key** — a missing one is a provisioning escalation, and the guard says so in its own message.

### The vacuous-loop trap: discovery runs ONCE per `job_id`

Found by audit 2026-08-27, and the most dangerous of the set because it defeated the very phase that
exists to stop a fabricated rival reaching a spec.

The engine guards discovery with `if not discovery_done:` (`orchestrator.py:566`) and persists that
flag in the progress checkpoint. The driver derives `job_id` **deterministically from the market**
(`rivals_run.py::main`), into a persistent `.tmp/rivals/<job_id>/`. So a second round could not
surface a new rival **by construction** — and the command's terminal condition #1, "two consecutive
dry rounds", auto-satisfied at round 2. The loop reported DRY without ever re-asking the question:
fail-silent-green, in the convergence loop itself.

Clearing the flag alone would have been **worse**. `discovered` is REPLACED at `orchestrator.py:572`,
not merged — so a round-2 discovery returning 9 of 12 rivals would silently drop 3, while their
`reviews_done` entries survived, meaning no later round would re-mine them either.

`--rediscover` is therefore two halves, both driver-side (never a fork of the vendored engine):

1. **Re-arm** — clear `discovery_done`, preserving `reviews_done` (no mined review is re-billed),
   `spent_usd` (the ceiling's only memory across a resume) and the degrade flags.
2. **Re-union** — after the run, union the prior competitor set back over the round's fresh
   discoveries, prior cards first and winning collisions (a surviving card may already carry mined
   data).

The re-arm reports one of three outcomes, and the distinction is load-bearing: `rearmed` (the next run
genuinely re-discovers), `ROUND 1` (no checkpoint yet — discovery would have run regardless), and a
loud `!!` **failed** (the checkpoint could not be rewritten, so discovery is SKIPPED and that round
**cannot** discover anything). Collapsing the last two — which an earlier revision did, by returning a
bare empty list for both — reintroduces the exact fail-silent-green defect this flag exists to remove,
inside its own error path: a voided round reads as a dry one.

**The loop shape this implies:** every round but the last runs `--rediscover`; the **final round runs
without it**, so the engine restores the full union as `discovered`, mines any still-unmined reviews,
and synthesizes the matrix over the complete set. The driver prints the per-round `NEW`/`union` counts
so a dry round is a measured fact rather than an assumption.

The progress file is located by **glob**, not by rebuilding the engine's private
`_slug(job_id)-_hash(job_id)-progress.json` naming — `checkpoint_dir` is already per-`job_id`, so it
holds exactly one, and replicating a vendored module's private naming is a fork that drifts silently
on the next re-vendor. Every path verifies `job_id` first (the engine discards a foreign progress
file, and mutating one would corrupt an unrelated scan) and fails **soft** — a checkpoint problem must
never cost a paid run.

The key autoload itself stays **fail-open but never silent**: if `libs.subagents.load_env` is
unavailable the driver prints a `note:` and relies on the ambient environment, rather than swallowing
the failure. Swallowing it would be the same diagnosability gap this command filed upstream against
the engine's `_safe_research`, which logs a stage label and not the cause.

### The LLM arity trap (found live, filed upstream)

The two consumers of the injected `llm` call it with **different arities**:

- `competitor_intel/synth.py:53` → `self.llm(prompt)` — ONE positional
- `deep_research/engine.py:257` (also `:337`, `:401`) → `deps.llm(prompt, payload)` — TWO positionals

competitor-intel's README documents `async def my_llm(prompt: str, **kwargs) -> str`, which satisfies
only the first. A verbatim copy of that snippet raises `TypeError` on **every** deep-research call —
and because both call sites sit behind never-raise boundaries (`orchestrator.py:198`, `synth.py:54`),
the failure is entirely silent: every leg degrades and the run returns an empty dossier with
`partial=True`. Measured 2026-08-26: `competitors=0`, no error visible anywhere.

The driver therefore accepts `*parts` and joins them. Two upstream items were filed with fabrik-lib:
the README signature, and the fact that `_safe_research` logs only the stage label and not the
exception, which is what made the failure undiagnosable from outside.

## The artifact is rendered from `to_dict()`, not `to_markdown()`

⚠️ **Corrected 2026-08-27 — the original justification has EXPIRED.** It read: measured 2026-08-26 on
a live 12-rival scan, `dossier.to_markdown()` emitted **404 bytes** while `to_dict()` held all twelve
rivals, a 12x44 matrix and the pricing models. That was true of the engine as it then stood. Upstream
then rebuilt the renderer (`e818249`, "render safety", re-vendored here at `bdb73670`), and
`to_markdown()` now emits all six sections — COMPETITORS · FEATURE MATRIX · MATCH · BEAT · PRICING ·
WHITE SPACE — with a 12-test render-safety suite of its own. **The quality gap is gone.**

The reason the driver still renders is now a **SHAPE mismatch**, and it is narrower: `to_markdown()`
consumes the live TYPED `Dossier` (`m.universal`, `b.weight`; it raises `AttributeError` on plain
dicts), while `render_dossier_md()` consumes `to_dict()`. That matters because the driver writes the
JSON **before** rendering — the money is already spent, so a formatting bug must cost the pretty view
and never the data — and because re-rendering a past run from disk has only the dict path. There is
no `Dossier.from_dict()`.

**Standing debt:** `render_dossier_md` is therefore ~600 lines running PARALLEL to a renderer upstream
now maintains, with its own duplicate injection hardening. `Dossier.from_dict()` (or a
`render_from_dict()`) would let the driver drop nearly all of it; requested from fabrik-lib
2026-08-27. Until that lands, keep the driver's renderer and keep it honest about WHY it exists.

Two details that are easy to get wrong and were checked against the real payload rather than assumed:

- The matrix `cells` dict is keyed `"<row>\u241f<col>"` (U+241F UNIT SEPARATOR), and each value is a
  dict carrying `state`. Guessing `"<row>|<col>"` renders a full grid of `❓` that looks like
  "nothing is known" rather than a lookup bug.
- Every rival carries `verified`. On that run **5 of 12** were `verified: False` with the reason
  "No page text retrieved for this candidate". They are rendered `❓` and named in a callout — an
  unconfirmed name sitting among real ones is how a fabricated competitor reaches a spec.

## The dossier is DATED, and the date is load-bearing

Competitive intel is perishable in a way most artifacts are not — rival pricing, feature sets and
review sentiment all move — and this artifact is what a product spec gets decided on. The driver
stamps `scanned_at` (UTC) into the payload before either artifact is written, and the renderer leads
the header with it. A payload with no date renders `⚠️ UNDATED — provenance unknown, do not treat as
current` rather than going quiet: an undated dossier that LOOKS complete is the same fail-silent-green
shape this command exists to avoid. `check_rivals_dossier.py` grades its presence.

Added 2026-08-27 by auditing the command against `docs/reference/command-evaluation-checklist.md`
item 28 (external claims carry a cited URL + fetch date). The original 14-aspect audit missed it
entirely — which is the case for having the checklist.

## Termination — the command is a LOOP

A single engine run is not a dossier. The run is done only when all of these hold:

1. **Discovery is DRY** — two consecutive `--rediscover` rounds surface no new competitor and no new
   MATCH/BEAT item. Unknown-size discovery never terminates honestly on a fixed round count. ⚠️ A
   round run **without** `--rediscover` cannot discover anything (see the vacuous-loop trap above) —
   it is the closing synthesis round, never a dry round.
2. **The trust audit is clean** — see the split below.
3. **`truncated` is False** — with the no-ceiling policy it should never fire; if it does, that is a
   loud finding (runaway discovery), not a footnote.
4. **`competitors` is non-empty** — zero rivals is a FAILED scan, never an empty market.
5. The dossier is written to `docs/reference/rivals/<market>.md` with its `INDEX.md` and
   `docs/README.md` rows, and the gate is green.

### The trust audit is SPLIT, because the rails are not uniform

Claiming one rail for every stage is an overclaim the engine's own review had to scope out of its
README. Audit by what the engine actually guarantees:

- **Feature matrix · pricing wedge · white-space** — competitor-intel holds the fetched source text,
  so these are **re-groundable**: the verbatim quote must be a real substring of a real source, and
  the `source_url` must come from that source rather than the LLM. Re-verify by re-fetching.
- **BEAT** — these are deep-research's review cards; the engine never held the raw page, so BEAT is
  **Tier-C** and cannot be re-grounded the same way. Audit what exists: the ≥2-distinct-source
  corroboration gate and the source-weight inputs. Label it Tier-C in the dossier.
- **Adapter signals** — HN comments are unclassified (`neutral`); they enrich the signal but do not
  auto-surface as BEAT openings. An unclassified mention is not a proven weakness.

## Upstream

`libs/competitor_intel` is **vendored** — a copy cannot fix itself. A defect goes upstream: append a
dated note to `/opt/fabrik-lib/competitor-intel/UPSTREAM_FEEDBACK.md`, or mail fabrik-lib. Never
silently fork the vendored copy; re-vendor to pick up a fix.

## See also

- `/opt/fabrik-lib/competitor-intel/README.md` — the engine, its `Deps` table, and its gotchas
- `commands/_sources/fabrik-rivals.md` — the command source (rendered box-wide)
- `scripts/rivals_run.py` — the fleet-synced driver, its pre-flight and `--rediscover`
- `scripts/claude_p_cost.py` — what a `claude -p` call actually costs

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/rivals_run.py`
<!-- END related-scripts -->
