#!/usr/bin/env python3
"""Tier 1 enforcement: every Traefik-enabled service declares the full §7 label set.

Plan §7 (``docs/development/plans/2026-04-18-zero-touch-deployment.md:344``)
acceptance criterion (``:2086``):

    Every emitted ``templates/*/compose.yaml.j2`` declares the full
    Traefik label set explicitly; no reliance on Coolify auto-inject.

Why this matters (GlitchTip incident, 2026-04-18)
-------------------------------------------------
Coolify's runtime Traefik-label auto-injection is non-deterministic across
``PATCH /services/{uuid}`` calls. ``errors.vps1.ocoron.com`` was reachable
without 2FA despite the Authelia policy declaring ``two_factor`` for
``*.vps1.ocoron.com`` — root cause: the service's ``docker_compose_raw``
had zero Traefik labels and Coolify was no longer injecting them on boot.

The only safe posture is: Fabrik-emitted composes declare the FULL label
set explicitly. Every Traefik-enabled service MUST have all five:

    1. ``traefik.http.routers.<R>.rule=...``
    2. ``traefik.http.routers.<R>.entrypoints=...``
    3. ``traefik.http.routers.<R>.tls=true``
    4. ``traefik.http.routers.<R>.tls.certresolver=...``
    5. ``traefik.http.services.<S>.loadbalancer.server.port=...``

Note on ``tls=true``: Traefik infers TLS-on from ``.tls.certresolver=``
being present, BUT the plan explicitly bans relying on inferred behavior
because the whole point of §7 is "no implicit anything" — if the spec
says five labels, we emit five labels, every time, no exceptions.

Check shape
-----------
Per-SERVICE, not per-router. A wordpress-style multi-router template
(apex + www-redirect + xmlrpc-block) passes as long as each label pattern
appears at least once inside the service's ``labels:`` block. Router-
name consistency is NOT policed here — policing it would require
rendering the jinja, which we refuse (see ``check_no_host_ports.py``
module docstring for the invariant).

Exclusions
----------
* Service without ``traefik.enable=true`` — out of scope (not routed).
* Service with ``traefik.enable=false`` — explicit opt-out; honoured.
* ``file-worker``-style non-HTTP services — typically have no ``labels:``
  block at all; pass through unchanged.

Exit codes
----------
0 — all templates compliant
1 — at least one violation (details printed to stdout)

Invocation
----------
    python scripts/enforcement/check_traefik_labels.py
    python scripts/enforcement/check_traefik_labels.py --templates-dir /path

Runs in the lean gate (``scripts/final_gate.py --lean``).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (path, service_name, missing_label_names) — deliberately NOT a dataclass
# to keep this script import-free for the lean gate; dependency minimalism
# matters when the gate runs early on a potentially-broken commit.
Violation = tuple[Path, str, list[str]]

# --------------------------------------------------------------------------- #
# Required label patterns
# --------------------------------------------------------------------------- #
#
# Each entry is (pretty_name, compiled_regex). The regex matches the label
# VALUE as it appears on a single ``- "..."`` line inside a ``labels:``
# block. We match the pattern without anchoring to the whole line so both
# short-form (``- "traefik.x=y"``) and edge cases (trailing comments,
# whitespace variants) are tolerated.
#
# Router/service name placeholder: ``.+?`` (non-greedy any-char).
#
# Simpler patterns like ``[^.]+`` break on jinja router names such as
# ``{{ spec.id }}`` which legitimately contain dots AND whitespace inside
# the ``{{ ... }}`` delimiters. Non-greedy match is safe because each
# pattern is anchored on BOTH sides (``routers.`` prefix + ``.<kw>=``
# suffix), so the regex engine stops at the first valid terminator.
#
# Disambiguation between ``.tls=true`` and ``.tls.certresolver=`` is
# handled by the ``.tls\s*=\s*true\b`` pattern below — the literal
# ``=true`` boundary prevents the cert-resolver line from satisfying the
# ``tls=true`` requirement.

_NAME = r".+?"

REQUIRED_LABELS: list[tuple[str, re.Pattern[str]]] = [
    (
        "traefik.http.routers.<R>.rule=...",
        re.compile(rf"traefik\.http\.routers\.{_NAME}\.rule\s*="),
    ),
    (
        "traefik.http.routers.<R>.entrypoints=...",
        re.compile(rf"traefik\.http\.routers\.{_NAME}\.entrypoints\s*="),
    ),
    (
        "traefik.http.routers.<R>.tls=true",
        # Require the literal ``tls=true``, not just ``.tls.`` — so that
        # ``tls.certresolver=`` alone doesn't satisfy the ``tls=true``
        # requirement. The regex checks for ``.tls=true`` preceded by
        # the router name and not followed by a dot (to exclude
        # ``.tls.certresolver`` matches).
        re.compile(rf"traefik\.http\.routers\.{_NAME}\.tls\s*=\s*true\b"),
    ),
    (
        "traefik.http.routers.<R>.tls.certresolver=...",
        re.compile(rf"traefik\.http\.routers\.{_NAME}\.tls\.certresolver\s*="),
    ),
    (
        "traefik.http.services.<S>.loadbalancer.server.port=...",
        re.compile(rf"traefik\.http\.services\.{_NAME}\.loadbalancer\.server\.port\s*="),
    ),
]

# Detection: does this labels-block line opt the service into Traefik?
#
# ``traefik.enable=true`` — affirmative opt-in
# ``traefik.enable=false`` — explicit opt-out (suppresses enforcement)
_RE_ENABLE_TRUE = re.compile(r"traefik\.enable\s*=\s*true\b")
_RE_ENABLE_FALSE = re.compile(r"traefik\.enable\s*=\s*false\b")

# --------------------------------------------------------------------------- #
# Indent-tracking scanner (same design as check_no_host_ports.py)
# --------------------------------------------------------------------------- #

_SERVICE_INDENT = 2
_BLOCK_KEY_INDENT = 4


def scan_template(path: Path) -> list[Violation]:
    """Scan one ``compose.yaml.j2`` for §7 label-set violations.

    Returns a list of ``Violation`` tuples — one per service that is
    Traefik-enabled but missing at least one required label. Services
    that are opted out (``traefik.enable=false``) or not opted in at all
    produce zero violations.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    # Per-service state.
    #   enabled: None | True | False
    #     None → no ``traefik.enable=*`` seen yet; treat as not-routed (out
    #            of scope) at end of file.
    #     True → require the full label set.
    #     False → explicit opt-out; skip enforcement.
    #   label_hits: which of the REQUIRED_LABELS patterns matched so far.
    service_states: dict[str, dict] = {}
    current_service: str | None = None
    in_services_block = False
    inside_labels_block = False

    for raw_line in text.splitlines():
        stripped = raw_line.lstrip()
        indent = len(raw_line) - len(stripped)

        if not stripped or stripped.startswith("#"):
            continue

        # Top-level boundary.
        if indent == 0:
            in_services_block = stripped.rstrip().rstrip(":").strip() == "services"
            current_service = None
            inside_labels_block = False
            continue

        if not in_services_block:
            continue

        # Service boundary (``  my-service:`` at indent 2).
        if indent == _SERVICE_INDENT and stripped.rstrip().endswith(":"):
            current_service = stripped.rstrip().rstrip(":").strip()
            service_states.setdefault(
                current_service,
                {
                    "enabled": None,
                    "label_hits": {name: False for name, _ in REQUIRED_LABELS},
                },
            )
            inside_labels_block = False
            continue

        if current_service is None:
            continue

        # Service-level sub-key (``    labels:``, ``    ports:``, etc.).
        if indent == _BLOCK_KEY_INDENT and stripped.rstrip().endswith(":"):
            key = stripped.rstrip().rstrip(":").strip()
            inside_labels_block = key == "labels"
            continue

        # Leaving any indent-4 block when we hit a new indent-≤4 line.
        if indent <= _BLOCK_KEY_INDENT:
            inside_labels_block = False

        if inside_labels_block and indent > _BLOCK_KEY_INDENT:
            state = service_states[current_service]
            # Opt-in / opt-out detection. ``false`` takes precedence over
            # ``true`` if both somehow appear — defensive but unreachable
            # in practice.
            if _RE_ENABLE_FALSE.search(stripped):
                state["enabled"] = False
            elif _RE_ENABLE_TRUE.search(stripped) and state["enabled"] is not False:
                state["enabled"] = True
            # Check which required labels this line satisfies.
            for name, pattern in REQUIRED_LABELS:
                if pattern.search(stripped):
                    state["label_hits"][name] = True

    # Emit violations.
    violations: list[Violation] = []
    for service, state in service_states.items():
        if state["enabled"] is not True:
            # Not routed, or explicitly opted out → skip.
            continue
        missing = [name for name, hit in state["label_hits"].items() if not hit]
        if missing:
            violations.append((path, service, missing))
    return violations


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _format_report(violations: list[Violation]) -> str:
    lines = [
        "ERROR: Traefik-enabled service missing one or more §7 required labels.",
        "",
        "Plan §7 (and LESSONS_LEARNT §8.7) require every Traefik-routed",
        "service to declare the FULL label set explicitly — Coolify's",
        "auto-injection is non-deterministic across PATCH calls and has",
        "silently broken admin-dashboard 2FA in production (GlitchTip,",
        "2026-04-18). Add the missing labels listed below.",
        "",
    ]
    for path, service, missing in violations:
        lines.append(f"  {path}  (service: {service})")
        for m in missing:
            lines.append(f"    - missing: {m}")
    lines.append("")
    lines.append("See: docs/development/plans/2026-04-18-zero-touch-deployment.md §7")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce §7 Traefik-label completeness on compose templates."
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "templates",
        help="Directory to scan recursively for compose.yaml.j2 files "
        "(defaults to the repo's templates/ directory).",
    )
    args = parser.parse_args(argv)

    templates_dir: Path = args.templates_dir
    if not templates_dir.is_dir():
        print(
            f"ERROR: --templates-dir {templates_dir} does not exist or is not a directory",
            file=sys.stderr,
        )
        return 2

    all_violations: list[Violation] = []
    for path in sorted(templates_dir.rglob("compose.yaml.j2")):
        all_violations.extend(scan_template(path))

    if all_violations:
        print(_format_report(all_violations))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
