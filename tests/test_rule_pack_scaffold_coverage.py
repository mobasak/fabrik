"""The rule corpus must stay consistent with the live scaffold registry and with itself.

Two classes of defect this catches, both found live on 2026-08-28 while grounding the
provider-death resilience standard:

1. `58-resilience.md`'s Per-Scaffold Applicability matrix carried 11 rows against a 12-entry
   `SCAFFOLD_TYPES` registry. The missing one was `python-api-gpu` — the single scaffold type
   whose entire purpose is model inference, and therefore the type most exposed to a provider
   death. An agent scaffolding one and looking up its resilience obligations found no row at all.
   Nothing compared the matrix to the registry, so the gap was invisible for as long as it existed.

2. `76-gpu-workers.md`'s § Provider Failover worked example caught only `httpx.TimeoutException`
   and `httpx.ConnectError` — two TRANSPORT exceptions. An `http_402` (what a billing-gated free
   tier returns) therefore did not advance the fallback chain in either branch of the snippet's
   undefined `call_provider`: raised, it is an `HTTPStatusError` this `except` does not catch, so
   it propagates and the remaining rungs are never tried; unraised, the 402 body is returned as if
   it were a completion. The pack was teaching the exact pattern that stalled youtube's backfill
   for 8 hours.

Both assertions read the REAL rule-pack files and the REAL registry via import. There is no
fixture and no stub: a test that parsed a copy of the matrix would assert nothing about the file
that actually ships to ~46 repos via the governance sync.

⚠️ SCOPE. This enforces the CORPUS's internal consistency. It enforces nothing about whether any
project complies with the provider-death standard — that is prose-enforced at the planning phase
(docs/superpowers/specs/2026-08-28-provider-death-resilience-design.md § Enforcement). Conflating
the two would be a rule naming enforcement that does not exist.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RULES = REPO / ".windsurf" / "rules" / "core"
sys.path.insert(0, str(REPO / "src"))

from fabrik.scaffold import SCAFFOLD_TYPES  # noqa: E402

# A matrix row opens with a backticked scaffold-type name in the first cell.
_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`", re.M)


def _matrix_types() -> set[str]:
    """Scaffold types named in 58-resilience's Per-Scaffold Applicability matrix."""
    text = (RULES / "58-resilience.md").read_text(encoding="utf-8")
    start = text.find("## Per-Scaffold Applicability")
    assert start != -1, "58-resilience.md lost its Per-Scaffold Applicability heading"
    nxt = text.find("\n## ", start + 1)
    section = text[start : (nxt if nxt != -1 else len(text))]
    return set(_ROW.findall(section))


def test_every_scaffold_type_has_a_resilience_row() -> None:
    """The matrix is the lookup an agent uses to learn what resilience its scaffold owes.
    A type absent from it has no obligations at all, which is silently weaker than having
    lenient ones."""
    registry = set(SCAFFOLD_TYPES)
    matrix = _matrix_types()
    assert matrix == registry, (
        f"58-resilience Per-Scaffold matrix is out of sync with scaffold.py::SCAFFOLD_TYPES.\n"
        f"  missing from the matrix: {sorted(registry - matrix)}\n"
        f"  in the matrix but not the registry: {sorted(matrix - registry)}"
    )


def test_provider_failover_example_handles_http_status_errors() -> None:
    """The worked example is the artifact projects copy. An `except` that names only transport
    exceptions does not fail over on 402/403/429 — the billing-gate and quota classes that kill a
    free tier — so the documented failover silently does not fail over."""
    text = (RULES / "76-gpu-workers.md").read_text(encoding="utf-8")
    start = text.find("### Provider Failover")
    assert start != -1, "76-gpu-workers.md lost its § Provider Failover heading"
    nxt = text.find("\n### ", start + 1)
    section = text[start : (nxt if nxt != -1 else len(text))]

    # Grade EVERY except clause in the section, parenthesized tuple or bare single exception.
    # A parens-only pattern is a false negative on correct code: the fix that added
    # `except httpx.HTTPStatusError as e:` is unparenthesized, and a narrower regex reported
    # the section as still-broken while reading only the transport tuple beside it.
    excepts = re.findall(r"except\s+([^\n:]+?)(?:\s+as\s+\w+)?\s*:", section)
    assert excepts, "§ Provider Failover has no except clause to grade"
    joined = " ".join(excepts)
    assert "HTTPStatusError" in joined, (
        "§ Provider Failover's failover except catches only transport errors "
        f"({joined!r}) — an http_402/403/429 would not advance the chain. "
        "Add httpx.HTTPStatusError."
    )


def test_provider_failover_breaker_granularity_is_per_model() -> None:
    """A per-PROVIDER breaker is the wrong resolution for a model-specific death: youtube's
    primary model went ReadTimeout-down while other models of the SAME provider stayed up.
    Writing off the whole provider discards live capacity and hides the real failure."""
    text = (RULES / "76-gpu-workers.md").read_text(encoding="utf-8")
    assert not re.search(
        r"Circuit-breaker per provider \(not per model\)", text
    ), (
        "76-gpu-workers.md still mandates a per-provider (not per-model) circuit breaker — "
        "the granularity that made youtube's model-specific provider death invisible."
    )
