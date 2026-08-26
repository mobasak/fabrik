#!/usr/bin/env python3
# AFTER-EDIT: commands/_sources/fabrik-rivals.md | docs/reference/rivals-command.md | INDEX.md
"""Hub-side driver for the vendored `competitor-intel` engine — the executable half of `/fabrik-rivals`.

`competitor-intel` is a fabrik-lib module: vendored-not-imported, and it INJECTS its engine rather
than importing it. All this script does is wire ONE `Deps(...)` correctly and hand the result back as
JSON + markdown. That wiring is the entire job, because the module's own contract is that `run()`
**never raises** for a money or staging reason — a failed leg degrades the dossier to `partial`, and
money exhaustion sets `truncated`. The ONLY exception it raises is a `ValueError` at ENTRY, for a
caller wiring bug.

That contract has a sharp edge, and it is why `_preflight()` below exists: every wiring mistake that
does NOT raise produces a dossier that looks like a completed run. Four of them are reachable from a
plausible command line, and all four are checked BEFORE a cent is spent:

1. **`total_budget_usd=0`** — the README is explicit that `0`/absent means *no research runs*, while
   still returning a `Dossier`. An operator who reads "no ceiling" as "pass 0 for unlimited" gets an
   empty dossier that reads as a finished scan. This is the fail-silent-green shape, so `0` is
   REJECTED rather than treated as unlimited. "No ceiling" is spelled as a large number.
2. **`legs` keys must be exactly `firecrawl`/`exa`/`brave`** — they must match the shipped packs' leg
   names. A typo'd key raises at entry (good), but only if we hand the module a mismatch; we check
   first so the error names the fix instead of a stack trace.
3. **The free leg's estimate must be `<= 0`** — `brave` is the free leg. A positive estimate for it
   silently disables the ceiling arithmetic the module relies on.
4. **`job_id` must be non-empty** — it is the double-book guard for checkpoint resume.

The LLM is `claude -p` — SUBSCRIPTION-billed, never a metered API and never a pool/subagent
dispatch. The only metered spend left is the SEARCH legs (Exa/Firecrawl); `brave` is free, so
`--free-legs-only` runs the whole scan at zero marginal cost with thinner discovery.

Search keys are read from the environment ONLY, via `libs.subagents.load_env` (the fleet's curated
autoload already carries `EXA_API_KEY`, `BRAVE_API_KEY`, `FIRECRAWL_API_KEY`). Never prompt for a
key, never hardcode one.

Usage (see `/fabrik-rivals` for the surrounding contract):

    python scripts/rivals_run.py --market "project management" --product-type saas \\
        --us-name Acme --us-feature timers --us-feature reports --out .tmp/rivals/pm

    python scripts/rivals_run.py --market "invoice ocr" --greenfield --preflight-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
# The vendored modules use ABSOLUTE internal imports (`from deep_research.engine import ...`), so
# they must be importable as TOP-LEVEL packages. Rewriting their imports would fork a vendored
# module, which fabrik-lib's own contract forbids — putting `libs/` on the path is the honest fix.
sys.path.insert(0, str(REPO / "libs"))
sys.path.insert(0, str(REPO))

# The module's own product-type vocabulary is NOT the fabrik SCAFFOLD_TYPES strings. It aliases the
# common ones itself and degrades an unknown type to Tier-C with a warning rather than erroring, but
# we map explicitly so `/fabrik-rivals` can read `project.yaml::type` straight off a project.
SCAFFOLD_TO_PRODUCT_TYPE = {
    "saas-skeleton": "saas",
    "chrome-extension": "extension",
    "desktop-app": "desktop",
    "mobile-app": "mobile-app",
    "python-api": "headless-api",
    "python-api-gpu": "headless-api",
    "node-api": "headless-api",
    "file-api": "headless-api",
    "file-worker": "headless-api",
    "static-site": "website",
    "docusaurus": "docs",
}
PRODUCT_TYPES = (
    "saas",
    "mobile-app",
    "ecommerce",
    "website",
    "headless-api",
    "docs",
    "extension",
    "desktop",
)
FREE_LEG = "brave"
REQUIRED_LEGS = ("firecrawl", "exa", "brave")
# "No ceiling" (operator, 2026-08-26) is spelled as a large number, never as 0 — see the module
# docstring above for why 0 is the fail-silent-green trap rather than the unlimited sentinel.
DEFAULT_BUDGET_USD = "1000"


class PreflightError(RuntimeError):
    """A wiring bug we caught BEFORE spending, with the fix named in the message."""


def _preflight(
    *,
    budget: Decimal,
    legs: dict[str, Any],
    leg_estimates: dict[str, Decimal],
    job_id: str,
    checkpoint_dir: Path,
    product_type: str,
) -> list[str]:
    """Every wiring trap that would otherwise yield a plausible-looking empty dossier.

    Returns the list of checks that PASSED (so `--preflight-only` can show its work); raises
    `PreflightError` naming the fix on the first failure. This runs before any network call.
    """
    ok: list[str] = []

    if budget <= 0:
        raise PreflightError(
            f"total_budget_usd={budget} — the module treats 0/absent as 'run NO research' and still "
            f"returns a Dossier, so this would hand you an EMPTY dossier that reads as a completed "
            f"scan. For an effectively-unlimited run pass a large number (default "
            f"{DEFAULT_BUDGET_USD}), never 0."
        )
    ok.append(f"budget is a real ceiling (${budget}), not the 0 no-research sentinel")

    missing = [k for k in REQUIRED_LEGS if k not in legs]
    if missing:
        raise PreflightError(
            f"legs is missing {missing} — the keys must match the shipped packs' leg names exactly "
            f"({', '.join(REQUIRED_LEGS)}), or run() raises a wiring ValueError at entry."
        )
    ok.append(f"legs keys match the packs' leg names ({', '.join(REQUIRED_LEGS)})")

    est_missing = [k for k in legs if k not in leg_estimates]
    if est_missing:
        raise PreflightError(
            f"leg_estimates is missing {est_missing} — a missing estimate silently disables the "
            f"money ceiling for that leg."
        )
    ok.append("every wired leg carries a cost estimate")

    if leg_estimates[FREE_LEG] > 0:
        raise PreflightError(
            f"leg_estimates[{FREE_LEG!r}]={leg_estimates[FREE_LEG]} — {FREE_LEG} is the FREE leg and "
            f"its estimate MUST be <= 0, or the ceiling arithmetic is wrong from the first call."
        )
    ok.append(f"the free leg ({FREE_LEG}) is estimated at <= 0")

    if not job_id.strip():
        raise PreflightError("job_id is empty — it is the double-book guard for checkpoint resume.")
    ok.append(f"job_id is set ({job_id})")

    # The module's constraint is `.tmp`, not `/tmp` — a repo-local scratch dir, so a resumed run
    # finds its checkpoints and a tmpfs reboot does not silently re-bill a completed leg.
    if checkpoint_dir.is_absolute() and not str(checkpoint_dir).startswith(str(REPO)):
        raise PreflightError(
            f"checkpoint_dir={checkpoint_dir} is outside the repo — the module's constraint is a "
            f"repo-local `.tmp` path, never /tmp."
        )
    ok.append(f"checkpoint_dir is repo-local ({checkpoint_dir})")

    if product_type not in PRODUCT_TYPES:
        raise PreflightError(
            f"product_type={product_type!r} is not one of {PRODUCT_TYPES}. Pass a scaffold type and "
            f"it is aliased for you ({', '.join(sorted(SCAFFOLD_TO_PRODUCT_TYPE))})."
        )
    ok.append(f"product_type is in the module's vocabulary ({product_type})")

    return ok


def _resolve_product_type(raw: str) -> str:
    """Accept EITHER the module's vocabulary or a fabrik scaffold type."""
    return SCAFFOLD_TO_PRODUCT_TYPE.get(raw, raw)


def _make_llm(model: str):
    """An async VARIADIC-positional LLM routed through OpenRouter.

    ⚠️ The arity here is load-bearing and is NOT what competitor-intel's README documents. The two
    consumers of the injected `llm` call it differently:

      * `competitor_intel/synth.py:53`  -> `self.llm(prompt)`            — ONE positional
      * `deep_research/engine.py:257`   -> `deps.llm(prompt, payload)`   — TWO positionals
        (also `:337` and `:401`; the second arg is a JSON payload)

    The README's snippet is `async def my_llm(prompt: str, **kwargs) -> str`, which satisfies only
    the first and raises `TypeError` on every deep-research call. Both call sites sit behind
    never-raise boundaries (`_safe_research` at orchestrator.py:198, the synth guard at synth.py:54),
    so the failure is SILENT: every research leg degrades and the run returns an empty dossier with
    `partial=True` that otherwise looks like a completed scan. Measured live on 2026-08-26 — a
    verbatim copy of the README snippet produced `competitors=0` and no error anyone could see.
    Accepting `*parts` satisfies both consumers; filed upstream to fabrik-lib.

    ⚠️ The LLM is `claude -p` — the SUBSCRIPTION-billed Claude Code CLI — never a metered API and
    never a pool/subagent dispatch (operator, 2026-08-26: "why do we spend money while we have
    claude -p … I reject using any agents for this purpose"). `ANTHROPIC_API_KEY` is reserved for
    `fabrik ai generate` and must never reach an operational path like this one.

    Two things that are load-bearing rather than cosmetic:

    * **`cwd` is a NEUTRAL directory.** `claude -p` loads the CLAUDE.md of whatever tree it runs in,
      so running it from `/opt/fabrik` prepends ~34k tokens of hub governance to EVERY synthesis
      call — measured 33,953 cache-creation tokens from the repo vs 11,611 from an empty dir. It is
      also wrong on the merits: the hub's agent contract is not context for "summarise these review
      excerpts", and letting it leak in invites the model to follow instructions meant for an agent.
    * **A concurrency cap.** Each call is a process, and the engine fans out across competitors.

    `claude -p` is subscription-billed, NOT free — the binding constraint is the weekly quota, not
    dollars. The `total_cost_usd` the CLI reports is the API-EQUIVALENT lens, not real spend; see
    `scripts/claude_p_cost.py`. The module meters synthesis by `synth_call_estimate` regardless.
    """
    sem = asyncio.Semaphore(int(os.getenv("RIVALS_LLM_CONCURRENCY", "4")))
    neutral = REPO / ".tmp" / "rivals" / "_neutral_cwd"
    neutral.mkdir(parents=True, exist_ok=True)

    async def llm(*parts: str, **_: Any) -> str:
        prompt = "\n\n".join(str(p) for p in parts if p)
        last = ""
        async with sem:
            for attempt in range(3):
                proc = await asyncio.create_subprocess_exec(
                    "claude",
                    "-p",
                    prompt,
                    "--model",
                    model,
                    "--output-format",
                    "json",
                    cwd=str(neutral),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                out, err = await proc.communicate()
                if proc.returncode == 0:
                    try:
                        doc = json.loads(out.decode("utf-8", "replace"))
                    except json.JSONDecodeError:
                        last = f"unparseable JSON from claude -p: {out[:200]!r}"
                    else:
                        if not doc.get("is_error"):
                            return str(doc.get("result") or "")
                        last = f"claude -p is_error: {str(doc.get('result'))[:200]}"
                else:
                    last = f"claude -p rc={proc.returncode}: {err.decode('utf-8', 'replace')[:200]}"
                await asyncio.sleep(2 * (attempt + 1))
        # Raise rather than return "": both consumers sit behind never-raise boundaries that
        # DEGRADE on an exception, and a degraded stage is honest. An empty string would be taken
        # as a real (empty) answer and silently poison the synthesis.
        raise RuntimeError(f"claude -p failed after 3 attempts — {last}")

    return llm


# The `claude -p` model vocabulary (`scripts/claude_p_cost.py`), NOT an API model id.
CLAUDE_P_MODELS = ("fable", "opus", "sonnet", "haiku")


def _default_model() -> str:
    """Subscription models only. `sonnet` is the default: the synthesis tail does structured
    extraction and ranking over fetched text, where haiku measurably under-performs and opus is
    quota the job does not need."""
    return os.getenv("RIVALS_LLM_MODEL", "sonnet")


def render_dossier_md(d: dict[str, Any]) -> str:
    """Render the DECISION-GRADE brief from `to_dict()`, not `to_markdown()`.

    Measured 2026-08-26 on a real 12-rival scan: the engine's own `to_markdown()` emitted **404
    bytes** — the market line, a spend line, and one BEAT item. It never listed the twelve
    competitors it found, never rendered the 12-column feature matrix, and never showed the pricing
    models. All of that IS in `to_dict()`. The engine's markdown is a summary; this command's
    artifact is what a spec gets decided on, so it renders from the structured payload.

    `verified` is surfaced per rival and never silently dropped: on that same run, 5 of 12
    candidates carried `verified: False` with the reason "No page text retrieved for this candidate"
    — an unconfirmed name sitting in a list of real ones is exactly how a fabricated competitor
    reaches a spec.
    """

    def _s(v: Any) -> str:
        return str(v).replace("|", "\\|").strip()

    out: list[str] = []
    out.append(f"# Rivals dossier — {d.get('market', '?')}")
    out.append("")
    verified = [c for c in (d.get("competitors") or []) if str(c.get("verified")) == "True"]
    unconfirmed = [c for c in (d.get("competitors") or []) if str(c.get("verified")) != "True"]
    out.append(
        f"**product_type:** `{d.get('product_type')}` · **rivals:** {len(d.get('competitors') or [])} "
        f"({len(verified)} verified, {len(unconfirmed)} unconfirmed) · "
        f"**review signals:** {len(d.get('review_signal') or [])} · "
        f"**spend:** ${d.get('spend_usd')} · **partial:** {d.get('partial')} · "
        f"**truncated:** {d.get('truncated')}"
    )
    out.append("")
    if d.get("truncated"):
        out.append(
            "> ⚠️ **truncated** — the money ceiling BOUND this run. Partial by budget, not complete."
        )
        out.append("")
    if not d.get("competitors"):
        out.append(
            "> ⚠️ **ZERO rivals discovered — treat this as a FAILED scan, not an empty market.**"
        )
        out.append("")

    out.append("## Rivals")
    out.append("")
    out.append("| Rival | Verified | Positioning | Source |")
    out.append("|---|---|---|---|")
    for c in d.get("competitors") or []:
        ok = "✅" if str(c.get("verified")) == "True" else "❓"
        out.append(
            f"| [{_s(c.get('name'))}]({c.get('url')}) | {ok} | {_s(c.get('positioning'))[:120]} "
            f"| {c.get('url')} |"
        )
    if unconfirmed:
        out.append("")
        out.append(
            f"> ❓ **{len(unconfirmed)} unconfirmed** — the engine could not retrieve page text to "
            f"verify these. Do NOT let an unconfirmed name reach a spec as a real competitor: "
            + ", ".join(_s(c.get("name")) for c in unconfirmed)
        )
    out.append("")

    fm = d.get("feature_matrix") or {}
    cols, rows, cells = fm.get("columns") or [], fm.get("rows") or [], fm.get("cells") or {}
    if cols and rows:
        out.append("## Feature matrix")
        out.append("")
        out.append("| Feature | " + " | ".join(_s(c) for c in cols) + " |")
        out.append("|---" * (len(cols) + 1) + "|")
        for r in rows:
            line = [_s(r)]
            for c in cols:
                # The engine keys cells "<row>\u241f<col>" (U+241F UNIT SEPARATOR) and each value is
                # a dict carrying `state` (✅/❌/⚠️/❓). Guessing "<row>|<col>" rendered a 44x12 grid
                # of ❓ that looked like "nothing known" rather than a lookup bug — checked against
                # the real payload rather than assumed.
                cell = cells.get(f"{r}\u241f{c}") if isinstance(cells, dict) else None
                state = cell.get("state") if isinstance(cell, dict) else cell
                line.append(_s(state) if state else "❓")
            out.append("| " + " | ".join(line) + " |")
        out.append("")

    match = d.get("match_list") or []
    out.append("## MATCH — what rivals have that we lack")
    out.append("")
    if match:
        for m in match:
            star = "★ " if m.get("universal") else ""
            out.append(f"- {star}**{_s(m.get('feature'))}** — {_s(m.get('detail') or '')}")
    else:
        out.append(
            "_Empty. In a **greenfield** run (`us=None`) this is EXPECTED — there is no `us` side to "
            "lack anything, and the matrix is rival-vs-rival. Re-run with `--us-name`/`--us-feature` "
            "once features exist to get a real MATCH list._"
        )
    out.append("")

    beat = d.get("beat_list") or []
    out.append("## BEAT — rivals' corroborated weaknesses (our openings)")
    out.append("")
    out.append(
        "> **Tier-C.** These are deep-research's review cards; the engine never held the raw review "
        "page, so BEAT is corroboration-gated (≥2 distinct sources) and source-weighted, NOT "
        "quote-re-grounded like the matrix and pricing below."
    )
    out.append("")
    for b in beat:
        out.append(
            f"- **{_s(b.get('theme') or b.get('weakness'))}** "
            f"(weight {b.get('weight')}, {b.get('n_sources') or b.get('sources')} sources)"
        )
        for q in (b.get("quotes") or [])[:3]:
            out.append(f'  - "{_s(q)[:220]}"')
    if not beat:
        out.append(
            "_None cleared the ≥2-distinct-source gate. Thin BEAT is the gate working, not a bug._"
        )
    out.append("")

    pricing = (d.get("pricing") or {}).get("models") or []
    if pricing:
        out.append("## Pricing wedge")
        out.append("")
        out.append("| Rival | Model | Free tier | Evidence | Source |")
        out.append("|---|---|---|---|---|")
        for m in pricing:
            out.append(
                f"| {_s(m.get('competitor'))} | {_s(m.get('model'))} | {_s(m.get('free_tier'))} "
                f"| {_s(m.get('evidence'))[:140]} | {m.get('source_url') or '—'} |"
            )
        out.append("")

    needs = (d.get("white_space") or {}).get("needs") or []
    out.append("## White-space — unmet demand")
    out.append("")
    out.append(
        "> Weakest evidence in this dossier: **incumbent/discourse-anchored**, never blue-ocean, and "
        "for four of five product types it degrades entirely to Tier-C search-excerpts."
    )
    out.append("")
    for n in needs:
        out.append(f"- **{_s(n.get('need'))}** — {_s(n.get('detail') or '')}")
    if not needs:
        out.append("_None corroborated._")
    out.append("")
    out.append("---")
    out.append(
        "**Scope:** competitor and entry-opportunity intel. This is **NOT market-sizing or demand "
        "validation** — a spec still needs that separately, and this dossier is never evidence that "
        "a market is big enough."
    )
    return "\n".join(out) + "\n"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the vendored competitor-intel engine (hub-side).")
    p.add_argument("--market", required=True, help="the market / category to scan")
    p.add_argument(
        "--product-type",
        default="saas",
        help=f"{'|'.join(PRODUCT_TYPES)} — or a fabrik scaffold type, which is aliased",
    )
    p.add_argument(
        "--us-name", help="our product's name; omit (or --greenfield) for a landscape run"
    )
    p.add_argument("--us-category", help="our product's category")
    p.add_argument(
        "--us-feature", action="append", default=[], help="repeatable; our shipped features"
    )
    p.add_argument(
        "--greenfield", action="store_true", help="force us=None (pre-spec landscape mode)"
    )
    p.add_argument("--budget", default=DEFAULT_BUDGET_USD, help="total_budget_usd — NEVER 0")
    p.add_argument(
        "--job-id", default="", help="checkpoint/double-book guard; defaults from market"
    )
    p.add_argument("--out", default="", help="write <out>.json and <out>.md")
    p.add_argument(
        "--free-legs-only",
        action="store_true",
        help="wire ONLY the free brave leg — zero marginal cost, thinner discovery",
    )
    p.add_argument("--no-pricing", action="store_true", help="disable the price-wedge stage")
    p.add_argument("--no-white-space", action="store_true", help="disable the white-space stage")
    p.add_argument(
        "--llm-model",
        default="",
        choices=("", *CLAUDE_P_MODELS),
        help="claude -p model for synthesis (default sonnet) — subscription, never a metered API",
    )
    p.add_argument(
        "--preflight-only",
        action="store_true",
        help="run every wiring check and exit WITHOUT spending — the offline proof",
    )
    return p.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    import httpx
    from competitor_intel import Deps, Us, run
    from deep_research import load_pack, run_research
    from web_tools import (
        WebToolsConfig,
        a_brave_search,
        a_exa_search,
        a_firecrawl_scrape,
        a_firecrawl_search,
    )

    product_type = _resolve_product_type(args.product_type)
    job_id = args.job_id or "rivals-" + "".join(
        ch if ch.isalnum() else "-" for ch in args.market.lower()
    )[:40].strip("-")
    checkpoint_dir = REPO / ".tmp" / "rivals" / job_id
    budget = Decimal(str(args.budget))

    legs = {"firecrawl": a_firecrawl_search, "exa": a_exa_search, "brave": a_brave_search}
    leg_estimates = {
        "firecrawl": Decimal("0.05"),
        "exa": Decimal("0.01"),
        FREE_LEG: Decimal("0"),
    }
    if args.free_legs_only:
        # The paid legs stay WIRED but are estimated above the ceiling so the engine forecloses
        # them, rather than being removed from `legs` — the pack names all three, and a missing
        # key is the exact wiring ValueError the pre-flight exists to prevent.
        leg_estimates["firecrawl"] = budget * 10
        leg_estimates["exa"] = budget * 10

    passed = _preflight(
        budget=budget,
        legs=legs,
        leg_estimates=leg_estimates,
        job_id=job_id,
        checkpoint_dir=checkpoint_dir,
        product_type=product_type,
    )
    print("PRE-FLIGHT — every wiring trap checked before a cent is spent:")
    for line in passed:
        print(f"  ok  {line}")

    if args.preflight_only:
        print("\n--preflight-only: wiring is sound; exiting without spending.")
        return 0

    model = args.llm_model or _default_model()
    print(
        f"  ok  synthesis LLM is subscription `claude -p --model {model}` (no metered API, no agents)"
    )

    us = None
    if not args.greenfield and args.us_name:
        us = Us(
            name=args.us_name,
            category=args.us_category or args.market,
            features=tuple(args.us_feature),
        )
    mode = "greenfield landscape (us=None)" if us is None else f"us={args.us_name}"
    print(f"\nRunning: market={args.market!r} · product_type={product_type} · {mode}")

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    cfg = WebToolsConfig(
        exa_api_key=os.getenv("EXA_API_KEY", ""),
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""),
    )
    async with httpx.AsyncClient(timeout=180) as client:
        deps = Deps(
            research_fn=run_research,
            load_pack=load_pack,
            llm=_make_llm(model),
            legs=legs,
            scrape=a_firecrawl_scrape,
            leg_estimates=leg_estimates,
            scrape_estimate=Decimal("0.05"),
            config=cfg,
            client=client,
            total_budget_usd=budget,
            ceiling_factor=Decimal("1.5"),
            checkpoint_dir=checkpoint_dir,
            job_id=job_id,
        )
        dossier = await run(
            us,
            args.market,
            product_type=product_type,
            deps=deps,
            enable_pricing=not args.no_pricing,
            enable_white_space=not args.no_white_space,
        )

    data = dossier.to_dict()
    md = render_dossier_md(data)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        out.with_suffix(".md").write_text(md, encoding="utf-8")
        print(f"\nwrote {out.with_suffix('.json')} and {out.with_suffix('.md')}")
    else:
        print("\n" + md)

    # An honest close-out. `truncated` means the ceiling bound the run; with the large default it
    # should never fire, so if it does it is a LOUD signal (a runaway discovery), not a footnote.
    n_comp = len(data.get("competitors") or [])
    print(
        f"\nSUMMARY: competitors={n_comp} "
        f"match={len(data.get('match_list') or [])} beat={len(data.get('beat_list') or [])} "
        f"signals={len(data.get('review_signal') or [])} "
        f"partial={data.get('partial')} truncated={data.get('truncated')}"
    )
    if data.get("truncated"):
        print(
            "  ⚠ truncated=True — the money ceiling BOUND this run. The dossier is partial by "
            "budget, not complete. Raise --budget and resume (the checkpoint re-bills nothing)."
        )
    if n_comp == 0:
        print("  ⚠ ZERO competitors discovered — treat as a FAILED scan, not an empty market.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        from libs.subagents import load_env

        load_env(str(REPO))
    except Exception:  # pragma: no cover - the autoload is a convenience, never a hard dep
        pass
    try:
        return asyncio.run(_run(args))
    except PreflightError as exc:
        print(f"WIRING ERROR (nothing was spent): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
