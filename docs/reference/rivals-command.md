# `/fabrik-rivals` — competitive evidence before a spec exists

**What this covers:** the `/fabrik-rivals` command, its hub-side driver `scripts/rivals_run.py`, and
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

## Two modes, and why

The engine is vendored-not-imported and needs `deep-research` + `web-tools` + an LLM injected. Putting
that in all ~46 projects would mean vendoring three modules per repo; fabrik-lib's brief asked for a
"thin hub-side driver" instead. The operator's requirement was that the command work in **every**
project, old and new. Both are satisfied by the same two-mode shape `/fabrik-upstream` already uses:

- **PROJECT mode** (repo identity ≠ `/opt/fabrik`) — grounds and files the BRIEF, using local tooling
  only. No hub shell-out, no vendored engine, no keys. The project supplies what only it knows: its
  `project.yaml::type`, its `docs/FEATURES.md`, its market.
- **HUB mode** (repo identity = `/opt/fabrik`) — holds the single vendored copy at
  `libs/competitor_intel` and runs it.

The command reaches every project because the corpus renders to user-level `~/.claude/commands` and
`~/.claude/skills`, not because anything is copied into a project tree.

⚠️ Identity is tested by CONTENT (`scripts/fabrik_synced_manifest.py` at the toplevel), never by a
bare path string — a relocated or DR hub clone is still the hub, and a `/opt/fabrik` worktree IS
hub-repo.

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
| `legs` keys ≠ `firecrawl`/`exa`/`brave` | must match the shipped packs' leg names | checked, with the fix named |
| free leg estimate > 0 | breaks the ceiling arithmetic from the first call | checked |
| empty `job_id` | the double-book guard for resume | checked |

`--preflight-only` runs all of them and exits without spending.

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

Measured 2026-08-26 on a live 12-rival scan of "invoice OCR software": `dossier.to_markdown()`
emitted **404 bytes** — the market line, a spend line, and one BEAT item. It never listed the twelve
rivals it found, never rendered the 12x44 feature matrix, and never showed the pricing models, all of
which were present in `to_dict()`. `rivals_run.py::render_dossier_md()` renders the decision-grade
brief from the structured payload instead (8.9 KB on the same data).

Two details that are easy to get wrong and were checked against the real payload rather than assumed:

- The matrix `cells` dict is keyed `"<row>\u241f<col>"` (U+241F UNIT SEPARATOR), and each value is a
  dict carrying `state`. Guessing `"<row>|<col>"` renders a full grid of `❓` that looks like
  "nothing is known" rather than a lookup bug.
- Every rival carries `verified`. On that run **5 of 12** were `verified: False` with the reason
  "No page text retrieved for this candidate". They are rendered `❓` and named in a callout — an
  unconfirmed name sitting among real ones is how a fabricated competitor reaches a spec.

## Termination — the command is a LOOP

A single engine run is not a dossier. HUB mode is done only when all of these hold:

1. **Discovery is DRY** — two consecutive rounds surface no new competitor and no new MATCH/BEAT item.
   Unknown-size discovery never terminates honestly on a fixed round count.
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
- `scripts/rivals_run.py` — the hub-side driver and its pre-flight
- `scripts/claude_p_cost.py` — what a `claude -p` call actually costs
