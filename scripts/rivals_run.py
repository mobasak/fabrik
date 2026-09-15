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

Search keys are read from the environment ONLY, by this script's own vendored `load_env`: the real
env wins, then the calling repo's nearest `.env`, then the fleet file
`~/.config/fabrik/subagents.env` (`$SUBAGENTS_ENV_FILE` / `$XDG_CONFIG_HOME` override it), which is
where `EXA_API_KEY`, `BRAVE_API_KEY` and `FIRECRAWL_API_KEY` normally live. Never prompt for a key,
never hardcode one.

Usage (see `/fabrik-rivals` for the surrounding contract):

    python scripts/rivals_run.py --market "project management" --product-type saas \\
        --us-name Acme --us-feature timers --us-feature reports --out .tmp/rivals/pm

    python scripts/rivals_run.py --market "invoice ocr" --greenfield --preflight-only
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent

# ── KEY AUTOLOAD, VENDORED (fabrik-lib 01M25GEXPY, measured 2026-09-14) ─────────────────────────
# This used to `from libs.subagents import load_env`. That module is being DELETED fleet-wide, and
# this script is synced to every repo — so in a repo that finished the delete the import failed,
# the caller printed one stdout note, and `/fabrik-rivals` ran with THREE OF FOUR search providers
# holding no credential. Reproduced in /opt/web-ecommerce-factory on 2026-09-14: both import paths
# raise ModuleNotFoundError and every key is unset in the process env. The curated list below is
# what THIS script needs — the three search legs plus Context7; `OPENROUTER_API_KEY` is deliberately
# NOT here, because the LLM is `claude -p` (subscription) and no code path in this file reads it.
#
# The keys themselves are NOT going away — `~/.config/fabrik/subagents.env` is fleet infrastructure
# and the documented home for a key a project should not duplicate. So this vendors the resolution
# RULE, byte-for-byte in behaviour, and drops the dependency: real env wins, then the project's own
# `.env` (nearest, walking up), then the fleet file. Fail-open, never raises, curated keys only —
# a rivals scan must never pull a project's DB URL or Stripe key into the process env.
# The three search legs, plus CONTEXT7 — which no rivals leg reads today (`docs_lookup` is never
# wired into `Deps`), carried because the shared `web_tools` surface declares it and a curated
# list that drifts from that surface is how a key goes missing the next time a leg is added.
_ENV_KEYS = ("EXA_API_KEY", "BRAVE_API_KEY", "FIRECRAWL_API_KEY", "CONTEXT7_API_KEY")


def _env_file_values(path: Path) -> dict:
    """Parse `KEY=VALUE` lines — a faithful port of `libs/subagents/_dotenv.py::_parse_env_text`, not a
    re-implementation. A first pass here was hand-rolled and diverged from the canonical rule in 12 of
    33 cases an author-blind reviewer drove; three of them corrupted credentials SILENTLY, which is
    worse than the missing-module bug this vendoring exists to fix:
      · `KEY=sk-abc # rotate monthly` shipped the comment as part of the key — and `_preflight`'s
        truthiness check then reported that key PRESENT, so the only symptom was a 401;
      · a UTF-8 BOM from a Windows editor glued itself to the first key, which then matched no curated
        name and was dropped in silence (`utf-8-sig` is why the canonical reader uses it);
      · an unterminated quote left a literal `"` on the front of the secret.
    Keep this and the canonical function byte-identical in behaviour; if one changes, change both.
    A malformed line is skipped, never raised."""
    out: dict = {}
    try:
        # utf-8-sig exactly as the canonical reader: strips a leading BOM instead of gluing it to the
        # first key. An undecodable file is dropped WHOLE rather than half-read — a half-read
        # credential file is the shape that yields a plausible-but-wrong key.
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, val = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key.isidentifier():  # guards against `A B=1` and other junk
            continue
        val = val.strip()
        if val[:1] in ("'", '"'):
            # quoted: content up to the matching close quote, so an inline comment AFTER the close is
            # discarded while a `#` INSIDE the quotes survives (a valid secret character).
            # Unterminated → best-effort drop the opening quote.
            close = val.find(val[0], 1)
            val = val[1:close] if close != -1 else val[1:]
        elif val.startswith("#"):
            # the value is ENTIRELY a comment (`KEY= # placeholder`) — the user commented it out.
            # Treat as empty so the truthiness guard skips it, rather than sending a bogus
            # `Authorization: Bearer # placeholder`.
            val = ""
        else:
            # unquoted: strip a trailing inline comment only when whitespace precedes the `#`, so a
            # `#` mid-value (a DSN query, a password) stays intact.
            m = re.search(r"\s#", val)
            if m:
                val = val[: m.start()]
            val = val.rstrip()
        out[key] = val
    return out


def _shared_env_path() -> Path | None:
    """`$SUBAGENTS_ENV_FILE`, else `$XDG_CONFIG_HOME/fabrik/subagents.env`, else the default under
    `~/.config` — the rule the retired module used, so a key set once keeps serving every repo.
    The override is `expanduser()`-ed, GUARDED, so `SUBAGENTS_ENV_FILE=~/.config/…` resolves instead
    of silently missing a file whose path begins with a literal `~`. The guard matters because
    `expanduser()` raises the same RuntimeError as `Path.home()` on an unresolvable home, and this
    branch runs BEFORE the try below (01M2GSRM4T1Y).
    ⚠️ This is NO LONGER a divergence from fabrik-lib: they closed SB-003 on 2026-09-15 (`88d061f8`)
    and all 21 canonical `_dotenv` loaders now carry the same guarded expansion — verified at
    `/opt/fabrik-lib/alerting/_dotenv.py:110-125` (NOT `libs/alerting/…`, a path that does not
    exist; the old docstring named it unchecked).
    ⚠️ ONE REAL DIVERGENCE REMAINS, and it is ours: on an unresolvable home fabrik-lib falls back to
    the literal `Path(override)` while we return None, because a bare `~/...` path is RELATIVE and
    the caller's `.is_file()` resolves it against the CWD — a cwd-relative credential read. Theirs
    is the more permissive shape; do not "align" by copying it back."""
    override = os.getenv("SUBAGENTS_ENV_FILE")
    if override:
        try:
            return Path(override).expanduser()
        except (KeyError, RuntimeError, OSError):
            # `expanduser()` resolves the home directory by the SAME mechanism as `Path.home()`
            # below and raises the SAME RuntimeError — and this branch runs BEFORE that guard, so
            # the guard never covered it (fabrik-lib-sentinel, 01M2GSRM4T1Y).
            # ⚠️ Degrade to None, NOT to the unexpanded path. A bare `Path("~/.config/...")` is
            # RELATIVE, and the caller does `shared.is_file()`, which resolves it against the CWD —
            # so a stray directory named `~` in the repo root turns the fallback into a silent read
            # of an ATTACKER-PLACED credential file. Executed: `load_env` applied `EXA_API_KEY` and
            # `BRAVE_API_KEY` from `<cwd>/~/.config/fabrik/subagents.env` (review round 1). Missing
            # the file is the honest outcome when home cannot be resolved; reading a different one
            # is not. `OSError` is in the tuple because `pwd` may fail from a broken NSS/sssd
            # backend, which `posixpath.expanduser` does not swallow (only ImportError/KeyError).
            p = Path(override)
            return p if p.is_absolute() else None
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "fabrik" / "subagents.env"
    try:
        # `Path.home()` raises RuntimeError — NOT an OSError — when the home directory cannot be
        # resolved (no HOME, no passwd entry: a container, a systemd unit, a cron with a stripped
        # env). Unguarded it escaped `load_env`'s "Never raises" contract AND, because the call sits
        # before the apply loop, took the project's own `.env` down with it: a repo holding all three
        # keys locally got NONE of them. The canonical module guards the same call for the same reason.
        return Path.home() / ".config" / "fabrik" / "subagents.env"
    except (KeyError, RuntimeError):
        return None


def load_env(repo: str) -> list:
    """Populate `os.environ` for `_ENV_KEYS` and return the keys this call set. Precedence: a value
    already in the real env ALWAYS wins; then the project's nearest `.env` walking up from `repo`;
    then the fleet-wide shared file. Never raises."""
    loaded: list = []
    sources = []
    # ⚠️ An EMPTY or non-existent `repo` must never fall back to the CWD: `Path("").resolve()` is the
    # current directory, so the walk would climb out of whatever tree the process happens to sit in
    # and load a DIFFERENT repo's `.env` — silently, with preflight reporting keys present. That is
    # the same wrong-keys-no-warning failure the retired module's cwd autoload caused here, and the
    # reason it warns rather than guesses. Caught by this script's own grader, not in review.
    start = None
    if repo:
        try:
            candidate = Path(repo)
            # ABSOLUTE only. `Path(".").resolve()` IS the current directory and IS a directory, so a
            # guard that merely checks `is_dir()` passes ".", ".." and any relative name — each of
            # which walks up from wherever the process happens to sit and loads a DIFFERENT repo's
            # `.env`. That is the same silent wrong-keys failure in a different spelling (measured on
            # a copy: `load_env(".")` from a victim tree loaded its EXA key). The one caller passes
            # `str(REPO)`, always absolute; this keeps a future one honest.
            if candidate.is_absolute():
                resolved = candidate.resolve()
                if resolved.is_dir():
                    start = resolved
        except (OSError, ValueError):
            start = None
    if start is None:
        print(
            f"note: no project .env read — {repo!r} is not a directory; "
            "search keys come from the environment or the fleet file only"
        )
    if start is not None:
        for parent in (start, *start.parents):
            candidate = parent / ".env"
            try:
                if candidate.is_file():
                    sources.append(candidate)
                    break
            except OSError:
                break
    shared = _shared_env_path()
    try:
        if shared is not None and shared.is_file():
            sources.append(shared)
    except OSError:
        pass
    for src in sources:  # project .env first — it WINS over the fleet file
        values = _env_file_values(src)
        for key in _ENV_KEYS:
            # `not in os.environ`, NEVER `not os.getenv(...)`: an explicitly EXPORTED EMPTY value is a
            # decision ("disable this leg") and a falsy test would silently overwrite it from a file.
            # The truthiness guard on the parsed value is the other half — an empty `.env` value must
            # not land in the environment either, or the key gets set twice from two sources and the
            # returned list carries it twice.
            if key not in os.environ and values.get(key):
                os.environ[key] = values[key]
                loaded.append(key)
    return loaded


# The vendored modules use ABSOLUTE internal imports (`from deep_research.engine import ...`), so
# they must be importable as TOP-LEVEL packages. Rewriting their imports would fork a vendored
# module, which fabrik-lib's own contract forbids — putting `libs/` on the path is the honest fix.
sys.path.insert(0, str(REPO / "libs"))
sys.path.insert(0, str(REPO))

# ── ENGINE RESOLUTION: local first, then the hub ────────────────────────────────────────────────
# This script is FLEET-SYNCED, so it runs in ~46 repos that do not vendor the engine. It resolves
# `competitor_intel` / `deep_research` / `web_tools` from this repo if present, else from the hub's
# single vendored copy.
#
# ⚠️ Reading the hub is NOT the cross-repo hard stop. That rule governs "create/edit/COMMIT files in
# a repo OTHER than the one you were launched in" — writes. This only ever READS and IMPORTS; every
# artifact it produces is written into the CALLING repo. An earlier design mistook the rule for a
# ban on reads and built a two-hop mail workflow around a restriction that did not exist, which made
# a one-rival scan into a cross-repo errand for the operator. Keys need no such hop either: this
# script's own vendored `load_env` resolves EXA/FIRECRAWL/BRAVE in every project, from the repo's
# `.env` or the fleet file, with no module to import and none to retire.
HUB_LIBS = Path("/opt/fabrik/libs")


# Where a repo may keep the engine. `libs/` is the vendored fleet layout; `competitor-intel/`
# is fabrik-lib's CANONICAL source-of-truth layout (it is the module's home, so it has no
# `libs/` copy of itself). Checking only the first made a fabrik-lib run resolve to `hub` and
# silently build its dossier from the hub's VENDORED copy rather than the canonical engine —
# reported by fabrik-lib (01M14SG0RQ) after running the command from there. A silent
# wrong-source is worse than a hard failure: the run succeeds and nothing says which code ran.
_LOCAL_ENGINE_DIRS = (
    Path("libs") / "competitor_intel",
    Path("competitor-intel") / "competitor_intel",
)


def _resolve_engine() -> str:
    """Put the engine on sys.path. Returns 'local' or 'hub'; raises PreflightError if neither."""
    for rel in _LOCAL_ENGINE_DIRS:
        if (REPO / rel).is_dir():
            # The parent is what goes on sys.path — `competitor_intel` is the package.
            parent = str((REPO / rel).parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            return "local"
    if (HUB_LIBS / "competitor_intel").is_dir():
        # APPEND and guard, mirroring the local branch above and `main()`'s key-loader. An
        # unguarded `insert(0)` here undid that append twenty lines later: the hub landed at
        # sys.path[0] AND was duplicated, so a project's own `libs/deep_research` /
        # `libs/web_tools.py` were shadowed by the hub's again (round 8d — latent, 2 of 43 repos
        # own such a copy today and they differ from the hub only by one pack file). The hub is a
        # FALLBACK: it must be searched last, whichever branch puts it there.
        if str(HUB_LIBS) not in sys.path:
            sys.path.append(str(HUB_LIBS))
        return "hub"
    raise PreflightError(
        f"the competitor-intel engine is in neither {REPO / 'libs'} nor {HUB_LIBS}. Vendor it "
        f"(`cp -r /opt/fabrik-lib/competitor-intel/competitor_intel libs/`) or repair the hub copy."
    )


# The module's own product-type vocabulary is NOT the fabrik SCAFFOLD_TYPES strings. It aliases the
# common ones itself and degrades an unknown type to Tier-C with a warning rather than erroring, but
# we map explicitly so `/fabrik-rivals` can read `project.yaml::type` straight off a project.
SCAFFOLD_TO_PRODUCT_TYPE = {
    "saas-skeleton": "saas",
    "chrome-extension": "extension",
    "office-extension": "extension",  # an Office add-in is an extension-class product (found by the registry-coverage test)
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
# Wall-clock bound per `claude -p` call. The engine has a MONEY ceiling and checkpoints, but
# nothing bounds a wedged subprocess — `communicate()` takes no timeout and blocks forever.
_LLM_TIMEOUT_S = float(os.getenv("RIVALS_LLM_TIMEOUT_S", "300"))


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
    required_keys: tuple[str, ...] = (),
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

    # A missing search key does not raise anywhere: the leg fails, the engine degrades, and the run
    # returns an empty dossier with partial=True. That is the same fail-silent-green shape as
    # budget-0, so it is caught HERE with the key named — the engine cannot tell you which one.
    missing_keys = [k for k in required_keys if not os.getenv(k)]
    if missing_keys:
        raise PreflightError(
            f"{', '.join(missing_keys)} not set — the leg(s) using them would fail silently and the "
            f"run would return an EMPTY dossier with partial=True. They are autoloaded from this repo's "
            f".env or the fleet file ~/.config/fabrik/subagents.env (override with "
            f"$SUBAGENTS_ENV_FILE): provision them in either. NEVER prompt for a key and never "
            f"hardcode one."
        )
    if required_keys:
        # Only claim the check when it actually ran: "search keys present ()" is a green line for a
        # question nobody asked, which is the whole failure class this pre-flight exists to prevent.
        ok.append(f"search keys present ({', '.join(required_keys)})")

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
                    # T13.5: a full-turn `claude -p` whose output is parsed as JSON — any hook
                    # banner on that stream is both unread and a parse hazard. The two advisory
                    # hooks stand down on this. (The LARGER fix the mail names — routing this
                    # spawn through llm-dispatch with its bounded flags — is intel's rivals beat
                    # and is filed there, not done here.)
                    env={**os.environ, "FABRIK_HEADLESS": "1"},
                )
                try:
                    out, err = await asyncio.wait_for(proc.communicate(), timeout=_LLM_TIMEOUT_S)
                except TimeoutError:
                    # A wedged `claude` is bounded by NOTHING otherwise: the retry loop never
                    # reaches its next attempt, and the money ceiling bounds SPEND, not wall-clock,
                    # so an unattended run hangs forever. Proven with a stub that never exits.
                    proc.kill()
                    await proc.wait()
                    last = f"claude -p exceeded {_LLM_TIMEOUT_S}s and was killed"
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
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


# Every character Python's `str.splitlines()` treats as a line boundary. CommonMark only breaks on
# `\n`, so the exotic ones do not open a heading in a *renderer* — but every line-oriented CONSUMER
# (this module's own checks, the gate's doc scanners, anything calling `.splitlines()`) disagrees
# with a sanitiser that guards only `\r\n`. A guard whose definition of "a line" differs from its
# readers' is a guard with a hole, so the whole class is collapsed to a space.
_LINE_BOUNDARIES = tuple(ch for ch in map(chr, range(0x110000)) if len(f"a{ch}b".splitlines()) > 1)
_FLATTEN = {ord(ch): " " for ch in _LINE_BOUNDARIES}


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    """Normalise an LLM-shaped list into a list of dicts, keeping non-dict entries visible.

    A bare string in `competitors` used to raise `AttributeError` deep in the renderer. Dropping
    such entries silently would be worse than raising — the count would quietly disagree with the
    engine's own census — so a non-dict is wrapped as `{"name": <repr>}` and renders as an
    unconfirmed row the reader can see and question.
    """
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        out.append(item if isinstance(item, dict) else {"name": str(item), "verified": "False"})
    return out


def _as_map(value: Any) -> dict[str, Any]:
    """`value` if it is a mapping, else an empty mapping — never raise on a surprising shape."""
    return value if isinstance(value, dict) else {}


# ── re-discovery: making `/fabrik-rivals` Phase 2's convergence loop actually loop ────────────────
# The engine discovers ONCE per job_id — `if not discovery_done:` (orchestrator.py:566), with the
# flag persisted in the progress checkpoint — and this driver derives `job_id` deterministically
# from the market. So a second round found no new rival BY CONSTRUCTION, and the command's "two
# consecutive dry rounds" terminal condition auto-satisfied at round 2: a loop that reported DRY
# without ever re-asking. Clearing the flag alone is NOT enough, and is in fact worse: the engine
# REPLACES `discovered` (orchestrator.py:572) rather than merging, so a round-2 discovery returning
# 9 of 12 rivals would silently drop 3 — while their `reviews_done` entries survived, so no later
# round would re-mine them either. Re-discovery is therefore two halves: re-arm the flag while
# preserving everything already paid for, and re-union the prior set back in afterwards.
#
# We locate the progress file by GLOB rather than by rebuilding the engine's private
# `_slug(job_id)-_hash(job_id)-progress.json` naming: `checkpoint_dir` is already per-job_id, so it
# holds exactly one, and replicating a vendored module's private naming is a fork that drifts
# silently on the next re-vendor. Every path here fails SOFT — a checkpoint problem must never cost
# a paid run — and every path verifies `job_id` first, because the engine discards a foreign
# progress file and mutating one would corrupt an unrelated scan.


def _progress_file_for(checkpoint_dir: Path, job_id: str) -> tuple[Path, dict[str, Any]] | None:
    """This job's progress file + its parsed body, or None (absent, unreadable, or another job's)."""
    try:
        candidates = sorted(checkpoint_dir.glob("*-progress.json"))
    except OSError:
        return None
    for path in candidates:
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(body, dict) and body.get("job_id") == job_id:
            return path, body
    return None


def _write_progress(path: Path, body: dict[str, Any]) -> bool:
    """Atomic rewrite — a torn progress file loses the cumulative-spend record, so never write in
    place. Returns False on any failure; the caller degrades to "discovery runs anyway"."""
    try:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(body, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False


def _rediscover_reset(checkpoint_dir: Path, job_id: str) -> tuple[str, list[dict[str, Any]]]:
    """Re-arm discovery for the next round. Returns `(status, prior competitors)`.

    Everything already paid for is preserved — `reviews_done` (so no review is re-mined),
    `spent_usd` (the ceiling's only memory across a resume), and the degrade flags. The prior set is
    stashed to the durable sidecar BEFORE the engine can overwrite it (see `_union_sidecar`).

    ⚠️ The STATUS is load-bearing, not decoration. An earlier revision returned a bare list, so
    "no checkpoint yet" (genuinely round 1) and "the re-arm WRITE FAILED" were indistinguishable —
    and in the second case `discovery_done` is still True, so the round is silently vacuous while
    the driver cheerfully reports "discovery re-armed". That is the exact fail-silent-green class
    `--rediscover` exists to remove, rebuilt inside its own error path.

    - `"no-checkpoint"` — round 1; discovery would have run regardless.
    - `"rearmed"` — the flag is cleared; the next run genuinely re-discovers.
    - `"failed"` — the checkpoint could NOT be rewritten; discovery will be SKIPPED. Not a dry round.
    """
    found = _progress_file_for(checkpoint_dir, job_id)
    if found is None:
        return "no-checkpoint", []
    path, body = found
    # Union with anything a previous round already stashed. A round that CRASHED after the engine
    # overwrote `competitors` leaves the progress file THINNER than the sidecar, and reading the
    # progress file alone would then discard exactly what the sidecar exists to protect.
    prior = _dedup_cards(
        [*_durable_prior(checkpoint_dir, job_id), *(body.get("competitors") or [])]
    )
    body["discovery_done"] = False
    if not _write_progress(path, body):
        # Carry `prior` even on failure. The round's ROUND: line computes `added = total - len(prior)`,
        # so returning [] here would count every ALREADY-KNOWN rival as NEW and print a growth
        # number for a round that discovered nothing — the same lie in a different field.
        return "failed", prior
    _stash_prior(checkpoint_dir, job_id, prior)
    return "rearmed", prior


def _comp_slug(value: str) -> str:
    """Filename-safe slug for the sidecar. Local on purpose — the engine's `_slug` is private to a
    vendored module, and replicating a private helper is a fork that drifts on the next re-vendor."""
    out = "".join(ch if ch.isalnum() else "-" for ch in value.strip().lower()).strip("-")
    return out[:80] or "job"


def _union_sidecar(checkpoint_dir: Path, job_id: str) -> Path:
    """Where the accumulated union is stashed DURABLY, outside the progress file.

    It cannot live IN the progress file: `orchestrator.py::_persist` rewrites that from a LITERAL
    dict, so any key the driver adds is silently dropped on the engine's next save. And it cannot
    live only in a local variable: the engine overwrites `competitors` with the fresh discovery at
    `orchestrator.py:585` — immediately after discovery — so if the run then raises, or the operator
    Ctrl-Cs a long scan, the post-run merge never executes and every rival accumulated in prior
    rounds is gone from work that was already PAID for.
    """
    return checkpoint_dir / f"{_comp_slug(job_id)}-union.json"


def _durable_prior(checkpoint_dir: Path, job_id: str) -> list[dict[str, Any]]:
    """The stashed union, or []. Fails soft — a missing or corrupt sidecar degrades to "no prior
    rivals known", never to a traceback on a paid run."""
    try:
        body = json.loads(_union_sidecar(checkpoint_dir, job_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(body, dict) or body.get("job_id") != job_id:
        return []
    return [c for c in (body.get("competitors") or []) if isinstance(c, dict)]


def _stash_prior(checkpoint_dir: Path, job_id: str, cards: list[dict[str, Any]]) -> None:
    """Write the union sidecar atomically. Best-effort: a failure here costs the safety NET, not the
    run, so it is never allowed to raise."""
    path = _union_sidecar(checkpoint_dir, job_id)
    try:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"job_id": job_id, "competitors": cards}, indent=2), encoding="utf-8"
        )
        tmp.replace(path)
    except OSError:
        pass


def _dedup_cards(cards: list[Any]) -> list[dict[str, Any]]:
    """Order-preserving dedup by `_comp_key`; first occurrence wins (an earlier round's card may
    already carry mined data). A card with NEITHER name nor url has no key — it is KEPT, once,
    rather than dropped: `_as_dicts` already ruled on this class for the renderer ("dropping such
    entries silently would be worse than raising — the count would quietly disagree with the
    engine's own census"), and the union must not contradict that ruling one layer down."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    keyless = 0
    for card in cards:
        if not isinstance(card, dict):
            # A bare string has no fields to merge on. Dropping it here matches the ENGINE exactly:
            # `orchestrator.py:526` filters non-dicts out of `competitors` on every resume, so a
            # string kept in the union would be discarded the moment the final round restored it.
            continue
        key = _comp_key(card)
        if key is None:
            keyless += 1
            if keyless == 1:  # keep ONE, so the census disagreement is visible, not multiplied
                out.append(card)
            continue
        if key not in seen:
            seen.add(key)
            out.append(card)
    return out


def _comp_key(card: Any) -> str | None:
    """Dedup key for the competitor union. Deliberately NOT the engine's `_ck` — that keys
    `reviews_done` and must stay exactly as the engine writes it; this one only has to recognise the
    same rival re-discovered with different casing or stray whitespace."""
    if not isinstance(card, dict):
        return None
    name = str(card.get("name") or "").strip().lower()
    url = str(card.get("url") or "").strip().lower().rstrip("/")
    if not name and not url:
        return None
    return f"{name}|{url}"


def _merge_competitors_into_progress(
    checkpoint_dir: Path, job_id: str, prior: list[dict[str, Any]]
) -> int:
    """Union `prior` back over the round's fresh discoveries; return the union size (0 = not written).

    Prior cards come FIRST and win a collision: a card that survived an earlier round may already
    carry mined data, and the fresh card is at best equivalent. The union lands in the checkpoint so
    the FINAL round — run WITHOUT `--rediscover` — restores all of them as `discovered`, mines any
    still-unmined reviews, and synthesizes the matrix over the complete set.
    """
    found = _progress_file_for(checkpoint_dir, job_id)
    if found is None:
        return 0
    path, body = found
    # `prior` is the caller's in-memory copy; the SIDECAR is the durable one. Union both, so a
    # resumed process that never held `prior` still recovers everything earlier rounds paid for.
    union = _dedup_cards(
        [*prior, *_durable_prior(checkpoint_dir, job_id), *(body.get("competitors") or [])]
    )
    body["competitors"] = union
    if not _write_progress(path, body):
        return 0
    _stash_prior(checkpoint_dir, job_id, union)  # keep the safety net current for the next round
    return len(union)


def render_dossier_md(d: dict[str, Any]) -> str:
    """Render the DECISION-GRADE brief from `to_dict()`, not `to_markdown()`.

    ⚠️ The reason is a SHAPE mismatch, not a quality gap (corrected 2026-08-27). The original
    justification — `to_markdown()` emitting only 404 bytes on a 12-rival scan — was measured
    against the pre-`e818249` engine and no longer holds: upstream rebuilt the renderer and it now
    emits all six sections with its own render-safety suite.

    What remains: `to_markdown()` requires the live TYPED `Dossier` (`m.universal`, `b.weight`; it
    raises `AttributeError` on plain dicts), while this renders `to_dict()`. The driver writes the
    JSON BEFORE rendering — the money is already spent, so a formatting bug must cost the pretty
    view and never the data — and re-rendering a past run from disk has only the dict path. There is
    no `Dossier.from_dict()`; one has been requested upstream, and it would retire most of this.

    `verified` is surfaced per rival and never silently dropped: on that same run, 5 of 12
    candidates carried `verified: False` with the reason "No page text retrieved for this candidate"
    — an unconfirmed name sitting in a list of real ones is exactly how a fabricated competitor
    reaches a spec.
    """

    def _url(v: Any) -> str:
        """Link-target-safe. The rival URL is LLM- and web-sourced and went RAW into
        `[name](url)`, so a value like `http://e)vil](javascript:alert(1))` closed the link early
        and injected a `javascript:` target into a document the operator is invited to click.
        Only http/https survive; parens are percent-encoded so the link cannot be closed early.
        """
        raw = str(v or "").strip()
        if not raw.lower().startswith(("http://", "https://")):
            return ""
        # Percent-encode EVERY character that can terminate or restructure a markdown link target.
        # `.strip()` only trims the ENDS: an embedded newline still broke the link open, and the
        # sink test missed it because the following space was encoded to %20, so the assertion's
        # literal needle never matched. Encode the whitespace class, not just the space.
        raw = raw.translate(_FLATTEN)  # any line boundary -> space, then encode it
        for ch, enc in (
            (" ", "%20"),
            ("\t", "%09"),
            ("(", "%28"),
            (")", "%29"),
            ("<", "%3C"),
            (">", "%3E"),
            ('"', "%22"),
        ):
            raw = raw.replace(ch, enc)
        return raw

    def _s(v: Any) -> str:
        """Table-cell-safe. Escapes `|` AND collapses newlines.

        Escaping only the pipe let a value containing `\\n## FAKE HEADING` break out of the table
        and inject a heading into a document a spec gets decided on — and this content is
        LLM- and web-sourced, i.e. precisely the untrusted input this command warns about.
        """
        if v is None:
            return ""  # a missing field rendered the literal string "None" in the dossier
        return str(v).replace("\\", "\\\\").replace("|", "\\|").translate(_FLATTEN).strip()

    out: list[str] = []
    # `market` reaches an H1. It arrives from the CLI or from a project-authored brief, so a
    # newline in it injected a heading — same class as the table break-out, different sink.
    out.append(f"# Rivals dossier — {_s(d.get('market')) or '?'}")
    out.append("")
    # Every collection below is normalised to "list of dicts" first. The payload is LLM-shaped:
    # a competitor can arrive as a bare string, and `white_space` as something other than a mapping.
    # Both raised AttributeError before this, AFTER the money was spent.
    comps = _as_dicts(d.get("competitors"))
    verified = [c for c in comps if str(c.get("verified")) == "True"]
    unconfirmed = [c for c in comps if str(c.get("verified")) != "True"]
    # ⚠️ The SCAN DATE leads the header, because competitive intel is PERISHABLE in a way the rest
    # of this payload is not: rival pricing, feature sets and review sentiment all move, and this
    # artifact is what a product spec gets decided on. An undated dossier reads as current forever.
    # Absence is spelled LOUDLY — a missing date must be visible, not silent, which is the whole
    # failure shape this command exists to avoid. (Found by auditing /fabrik-rivals against
    # docs/reference/command-evaluation-checklist.md item 28; the first audit missed it.)
    scanned = _s(d.get("scanned_at")).strip()
    out.append(
        f"**scanned:** {scanned or '⚠️ UNDATED — provenance unknown, do not treat as current'} · "
        f"**product_type:** `{_s(d.get('product_type'))}` · **rivals:** {len(comps)} "
        f"({len(verified)} verified, {len(unconfirmed)} unconfirmed) · "
        f"**review signals:** {len(d.get('review_signal') or []) if isinstance(d.get('review_signal'), list) else 0} · "
        f"**spend:** ${_s(d.get('spend_usd'))} · **partial:** {_s(d.get('partial'))} · "
        f"**truncated:** {_s(d.get('truncated'))}"
    )
    out.append("")
    if d.get("truncated"):
        out.append(
            "> ⚠️ **truncated** — the money ceiling BOUND this run. Partial by budget, not complete."
        )
        out.append("")
    if not comps:
        out.append(
            "> ⚠️ **ZERO rivals discovered — treat this as a FAILED scan, not an empty market.**"
        )
        out.append("")

    out.append("## Rivals")
    out.append("")
    out.append("| Rival | Verified | Positioning | Source |")
    out.append("|---|---|---|---|")
    for c in comps:
        ok = "✅" if str(c.get("verified")) == "True" else "❓"
        href = _url(c.get("url"))
        name = _s(c.get("name")) or "(unnamed)"
        cell = f"[{name}]({href})" if href else f"{name} ⚠️"
        out.append(f"| {cell} | {ok} | {_s(c.get('positioning'))[:120]} | {_s(href) or '—'} |")
    if unconfirmed:
        out.append("")
        out.append(
            f"> ❓ **{len(unconfirmed)} unconfirmed** — the engine could not retrieve page text to "
            f"verify these. Do NOT let an unconfirmed name reach a spec as a real competitor: "
            + ", ".join(_s(c.get("name")) for c in unconfirmed)
        )
    out.append("")

    fm = _as_map(d.get("feature_matrix"))
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

    match = _as_dicts(d.get("match_list"))
    out.append("## MATCH — what rivals have that we lack")
    out.append("")
    if not d.get("us_name"):
        # Greenfield: MATCH is populated from RIVALS' features, so it is non-empty whenever they
        # have any — the `us` column then reads ❌ everywhere while nothing was evaluated. A
        # downstream spec read that as a determination (youtube 01M1J16A, 4 claims refuted).
        out.append(
            "_⚠ The `us` column was NOT EVALUATED — no `--us-name`/`--us-feature` was supplied "
            "(greenfield run): ❌ here means UNKNOWN, never absent. Re-run with our features "
            "to get a real MATCH list._"
        )
        out.append("")
    if match:
        for m in match:
            # `detail` is not emitted by the module; MATCH items carry `rivals_having` (+
            # `universal`). Reading a field that does not exist rendered an empty tail.
            star = "★ " if m.get("universal") else ""
            having = m.get("rivals_having") or []
            # The count and the list come from the SAME field, so they must agree: a bare
            # [:6] truncation printed "9 rival(s):" over 6 names (trade-intelligence live
            # run, via fabrik-lib). Say the truncation out loud instead.
            if len(having) > 6:
                who = (
                    f"{len(having)} rival(s) (top 6 shown): {', '.join(_s(x) for x in having[:6])}"
                )
            elif having:
                who = f"{len(having)} rival(s): {', '.join(_s(x) for x in having)}"
            else:
                who = ""
            out.append(f"- {star}**{_s(m.get('feature'))}** — {who}")
    else:
        out.append(
            "_Empty. In a **greenfield** run (`us=None`) this is EXPECTED — there is no `us` side to "
            "lack anything, and the matrix is rival-vs-rival. Re-run with `--us-name`/`--us-feature` "
            "once features exist to get a real MATCH list._"
        )
    out.append("")

    beat = _as_dicts(d.get("beat_list"))
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
            # The beat item carries `source_urls`; `n_sources`/`sources` do not exist, so this
            # printed "None sources" on every BEAT row. Verified against the real payload —
            # beat keys are quotes/source_urls/theme/weight. (fabrik-lib, 2026-08-27)
            f"(weight {_s(b.get('weight'))}, {len(b.get('source_urls') or [])} sources)"
        )
        for q in (b.get("quotes") or [])[:3]:
            out.append(f'  - "{_s(q)[:220]}"')
    if not beat:
        out.append(
            "_None cleared the ≥2-distinct-source gate. Thin BEAT is the gate working, not a bug._"
        )
    out.append("")

    pricing = _as_dicts(_as_map(d.get("pricing")).get("models"))
    if pricing:
        out.append("## Pricing wedge")
        out.append("")
        out.append("| Rival | Model | Free tier | Evidence | Source |")
        out.append("|---|---|---|---|---|")
        for m in pricing:
            out.append(
                f"| {_s(m.get('competitor'))} | {_s(m.get('model'))} | {_s(m.get('free_tier'))} "
                f"| {_s(m.get('evidence'))[:140]} | {_s(_url(m.get('source_url'))) or '—'} |"
            )
        out.append("")

    # NIT 2: the per-rival models table was rendered but `pricing.wedge` — the ranked list of
    # pricing OPENINGS, i.e. the actual output the stage exists to produce — was dropped entirely.
    wedge = _as_dicts(_as_map(d.get("pricing")).get("wedge"))
    if wedge:
        out.append("### Pricing wedge — the openings")
        out.append("")
        rendered_any = False
        for w in wedge:
            # An item whose name fields are ALL empty rendered "- **** " (bold-wrapped
            # nothing) — the empty-openings artifact from trade-intelligence's live run.
            # Skip nameless items; an all-nameless list gets the same _None_ line the
            # white-space section uses.
            # `name` FIRST: `PricingBlock.wedge` is a `list[str]` (competitor_intel/stages.py:36)
            # and `_as_dicts` normalises a bare string to {"name": ...}. Reading only the dict-shaped
            # keys meant every REAL wedge was skipped and the section printed the same
            # "_None corroborated._" as genuinely empty data — a grounded finding rendered as no
            # finding (youtube 2026-08-28; routed by fabrik-lib with the type as evidence). The
            # other keys stay for a future stage that emits richer entries.
            name = _s(w.get("name") or w.get("wedge") or w.get("opening") or w.get("theme"))
            if not name.strip():
                continue
            detail = _s(w.get("rationale") or w.get("evidence") or "")
            out.append(f"- **{name}** {detail}"[:400])
            rendered_any = True
        if not rendered_any:
            out.append("_None corroborated._")
        out.append("")

    needs = _as_dicts(_as_map(d.get("white_space")).get("needs"))
    out.append("## White-space — unmet demand")
    out.append("")
    out.append(
        "> Weakest evidence in this dossier: **incumbent/discourse-anchored**, never blue-ocean, and "
        "for four of five product types it degrades entirely to Tier-C search-excerpts."
    )
    out.append("")
    for n in needs:
        # white-space needs carry weight + quotes + source_urls, not `detail`.
        q = (n.get("quotes") or [None])[0]
        srcs = len(n.get("source_urls") or [])
        out.append(
            f"- **{_s(n.get('need'))}** (weight {_s(n.get('weight'))}, {srcs} sources)"
            + (f' — "{_s(q)[:160]}"' if q else "")
        )
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
        "--rediscover",
        action="store_true",
        help=(
            "re-arm discovery for a CONVERGENCE round: re-runs the discovery leg (which the "
            "checkpoint otherwise skips forever) and unions the result with the rivals already "
            "found, while re-billing NO mined review. Use it for every round but the LAST — the "
            "final round runs WITHOUT it, so the engine synthesizes over the full union."
        ),
    )
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


def _web_tools_config():
    """Build the engine's web-tools config from the environment — EVERY key the legs need.

    Extracted so it can be graded. `brave_api_key` was missing from the inline version, and nothing
    could see it: `WebToolsConfig` reads no environment of its own by design, so the free Brave leg
    got `None` and returned `error="BRAVE_API_KEY not set"` on every run, while `_preflight` — which
    REQUIRES that key — printed it as present. Under `--free-legs-only` the paid legs are foreclosed
    by estimate, so Brave is the only live leg and every such scan ended in "⚠ ZERO competitors
    discovered" with the key sitting in the environment throughout. Found 2026-09-14 by an
    author-blind seat; it is the same class as the autoload defect this file's vendored loader fixes
    — a provider unauthenticated while every report says otherwise.
    """
    # imported here, not at module scope: the engine only becomes importable after
    # `_resolve_engine()` puts the right `libs/` on sys.path (local-first, then the hub).
    from web_tools import WebToolsConfig

    return WebToolsConfig(
        exa_api_key=os.getenv("EXA_API_KEY", ""),
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""),
        brave_api_key=os.getenv("BRAVE_API_KEY", ""),
    )


async def _run(args: argparse.Namespace) -> int:
    where = _resolve_engine()
    import httpx
    from competitor_intel import Deps, Us, run
    from deep_research import load_pack, run_research
    from web_tools import (
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

    # `--free-legs-only` forecloses the paid legs, so only the free leg's key is required then.
    required_keys = (
        ("BRAVE_API_KEY",)
        if args.free_legs_only
        else (
            "BRAVE_API_KEY",
            "EXA_API_KEY",
            "FIRECRAWL_API_KEY",
        )
    )
    passed = _preflight(
        required_keys=required_keys,
        budget=budget,
        legs=legs,
        leg_estimates=leg_estimates,
        job_id=job_id,
        checkpoint_dir=checkpoint_dir,
        product_type=product_type,
    )
    print(f"PRE-FLIGHT (engine: {where}) — every wiring trap checked before a cent is spent:")
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
    # A CONVERGENCE round, not a resume. Must happen AFTER the `--preflight-only` return above — a
    # wiring check has no business mutating a checkpoint.
    prior_competitors: list[dict[str, Any]] = []
    if args.rediscover:
        status, prior_competitors = _rediscover_reset(checkpoint_dir, job_id)
        if status == "rearmed":
            print(
                f"  ok  --rediscover: discovery re-armed, carrying {len(prior_competitors)} known "
                f"rival(s) forward; mined reviews are NOT re-billed"
            )
        elif status == "no-checkpoint":
            print(
                "  ok  --rediscover: no prior checkpoint for this job_id - this is ROUND 1 and "
                "discovery would have run anyway"
            )
        else:  # "failed" - never let this read as a dry round
            print(
                "  !!  --rediscover: the checkpoint could NOT be rewritten, so discovery will be "
                "SKIPPED and this round CANNOT discover anything. Its zero-new result is NOT a dry "
                "round. Fix the checkpoint (or pass a fresh --job-id) before trusting convergence."
            )
    cfg = _web_tools_config()
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
    # Stamp the scan date HERE, on the driver side, before either artifact is written. The engine's
    # payload carries no date, and a dossier without one reads as current no matter how old it is.
    # UTC, so a dossier is comparable across machines.
    data.setdefault("scanned_at", _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d"))
    if args.rediscover:
        # Re-union BEFORE anything else touches the checkpoint: the engine has just overwritten
        # `competitors` with this round's discoveries only (orchestrator.py:572), so without this
        # the rivals the fresh round happened not to re-surface are gone from every later round.
        fresh = len(data.get("competitors") or [])
        total = _merge_competitors_into_progress(checkpoint_dir, job_id, prior_competitors)
        added = total - len(prior_competitors)
        print(
            f"\nROUND: discovery re-ran and returned {fresh} rival(s); "
            f"{added} NEW, union now {total}."
        )
        print(
            "  → This round's dossier covers the fresh discoveries only. "
            + (
                "A round that adds a rival is never the last round — run another --rediscover round."
                if added > 0
                else "DRY round. Two consecutive dry rounds, then a FINAL run WITHOUT "
                "--rediscover to synthesize over the full union."
            )
        )
    # ⚠️ ORDER IS LOAD-BEARING. The JSON is the paid artifact — the money is already spent by this
    # line — so it lands on disk BEFORE anything that can raise. Rendering used to run first, and
    # `render_dossier_md` reads keys off an LLM-shaped dict: an `AttributeError` on a competitor
    # that arrived as a bare string destroyed BOTH artifacts and left the operator a traceback for
    # a scan they had already paid for. The renderer is now defensive too, but the ordering is the
    # guarantee: a rendering bug can cost you the pretty view, never the data.
    # The dossier records whether an `us` side existed — the renderer keys its NOT-EVALUATED caveat on
    # it, and the JSON artifact must carry it too (set BEFORE the paid artifact is written).
    data["us_name"] = us.name if us is not None else None
    out = Path(args.out) if args.out else None
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"\nwrote {out.with_suffix('.json')}")
    try:
        md = render_dossier_md(data)
    except Exception as exc:  # noqa: BLE001 — never lose a paid run to a formatting bug
        md = (
            f"# Rivals dossier — {str(data.get('market') or '?').replace(chr(10), ' ')}\n\n"
            f"> ⚠️ The dossier could not be rendered ({type(exc).__name__}). The full payload IS "
            f"saved as JSON alongside this file — nothing was lost. Please report this shape.\n"
        )
        print(f"  ⚠ render failed ({type(exc).__name__}) — JSON is intact; wrote a stub markdown")
    if out is not None:
        out.with_suffix(".md").write_text(md, encoding="utf-8")
        print(f"wrote {out.with_suffix('.md')}")
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
        # No `subagents` sys.path search happens here any more. That loop existed ONLY so the
        # deleted `from libs.subagents import load_env` could resolve across three layouts, and
        # with the loader vendored it stat-ed three paths and mutated `sys.path` for a lookup
        # nothing consumes — while still able to put a directory at `sys.path[0]` and shadow the
        # project's own vendored engine, the hazard its own comment described. Deleting it removes
        # that hazard rather than guarding it. Engine resolution is unaffected: `_resolve_engine`
        # does its own local-first-then-hub search, and the `REPO/"libs"` insert at the top of the
        # file serves the engine, not the retired module.
        # The loader is VENDORED above, so there is no import to fail and no cwd autoload to
        # suppress. The bug that dance existed for cannot recur by construction: the retired
        # module autoloaded `load_env(os.getcwd())` at IMPORT, which in a hub-driven run for
        # project P silently loaded the HUB's search keys while preflight reported keys present.
        # `load_env` here reads nothing until called, and it is called with REPO — the calling
        # repo — exactly once.
        load_env(str(REPO))
    except Exception as exc:  # pragma: no cover - the autoload is a convenience, never a hard dep
        # Stays fail-open (a missing autoload must not block a run whose keys are already exported)
        # but SAYS SO. Swallowing it silently is the same diagnosability gap this command filed
        # upstream against the engine's `_safe_research`, which logs a label and not the cause.
        # T12.19 (01M21TGTR, 01M25GEXP, 01M28K3N8): naming the EXCEPTION answers "why did the
        # loader stop", which nobody asked. The question an operator has at this line is "is my
        # run degraded?", and that is answered by which expected keys the environment does NOT
        # carry — the loader failing is harmless when the keys are already exported, and fatal to
        # the run's coverage when they are not. So: name the cause AND the consequence.
        _absent = [k for k in _ENV_KEYS if not os.environ.get(k)]
        _state = (
            f"{len(_absent)} of {len(_ENV_KEYS)} expected key(s) absent: {', '.join(_absent)}"
            if _absent
            else f"all {len(_ENV_KEYS)} expected keys are already in the environment — no impact"
        )
        print(
            f"note: key autoload unavailable ({type(exc).__name__}: {exc}); "
            f"relying on the environment — {_state}"
        )
    try:
        return asyncio.run(_run(args))
    except PreflightError as exc:
        print(f"WIRING ERROR (nothing was spent): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
