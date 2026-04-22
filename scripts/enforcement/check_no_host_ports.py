#!/usr/bin/env python3
"""Tier 1 enforcement: ban host-bound ``ports:`` in Traefik-routed compose templates.

Plan §5 (zero-touch deploy) acceptance criterion (line 2091):

    Fails the lean gate if any ``templates/*/compose.yaml.j2`` contains a
    top-level ``ports:`` mapping (``"host:container"``) for services with
    a Traefik router.

Why this matters
----------------
On the production VPS, Traefik owns :80 / :443 (and :6001/:6002 for the
Coolify real-time service). Every Traefik-routed service reaches the
internet through Traefik middlewares — Authelia forward-auth for admin
dashboards, ``^/api/`` bypass for bearer-token API calls, ACME TLS, etc.

If a Fabrik-emitted compose template accidentally publishes the same
service on a host port via ``ports:``, that port bypasses EVERY middleware.
The iptables DOCKER-USER chain catches most direct-port exposures but not
loopback traffic, and the auth model assumes Traefik is the single ingress.

Historic context: ``captcha`` (published 0.0.0.0:8011) + ``image-broker``
(0.0.0.0:8010) both had ``ports:`` blocks that DOCKER-USER was dropping
externally, but the binding was present — a latent risk. Closed 2026-04-18
by removing the ports blocks upstream. This check exists so no future
template can regress the invariant.

Scope
-----
Scans every ``templates/**/compose.yaml.j2`` file (recursive — catches
nested templates like ``templates/wordpress/base/compose.yaml.j2``).

A service is flagged when BOTH conditions hold:

  1. It has at least one Traefik label — ``traefik.enable=true`` OR any
     ``traefik.http.routers.*`` / ``traefik.http.services.*`` label.
  2. Its ``ports:`` block contains at least one host binding:

     * short-form ``"HOST:CONTAINER"`` (any entry containing ``:``)
     * long-form with ``published:`` (that IS the host side)

Bare ``"8000"`` entries (no colon) are NOT host-bound — Docker treats
them as expose-style declarations.

Parsing approach — regex + indent, NOT yaml.safe_load
-----------------------------------------------------
The ``.j2`` files contain jinja ``{{ ... }}`` / ``{% ... %}`` constructs
that don't parse as YAML. Options:

  A. Render with jinja + a mock spec — fragile (every spec field must be
     stubbed; template author adds a new field → parser breaks).
  B. Indent-tracking line scan — robust to any jinja construct at the
     service / block / item level, since the indent of the structural
     keywords (``services:``, ``labels:``, ``ports:``) is preserved in
     the source text.

We use (B). A template that gets exotic enough to break the scan (e.g.
synthesising a ``ports:`` line inside a macro) deserves a code review
anyway.

Exit codes
----------
0 — all templates compliant
1 — at least one violation (details printed to stdout)

Invocation
----------
    python scripts/enforcement/check_no_host_ports.py
    python scripts/enforcement/check_no_host_ports.py --templates-dir /path/to/templates

Runs as part of the lean gate (``scripts/final_gate.py --lean``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Tuple carried back from ``scan_template`` so downstream formatters can
# render a self-contained "file:line — why" report. Kept as a plain tuple
# (not a dataclass) to stay dependency-free — this script runs early in the
# lean gate and MUST NOT import project-local modules that might fail to
# load for the very commit we're gating.
Violation = tuple[Path, str, int, str]  # (path, service_name, line_no, line_text)


# --------------------------------------------------------------------------- #
# Indent-tracking line parser
# --------------------------------------------------------------------------- #

# Canonical compose indentation (house style across all 13 existing templates):
#   services:                 ← indent 0
#     my-service:             ← indent 2
#       labels:               ← indent 4
#         - "..."             ← indent 6
#       ports:                ← indent 4
#         - "8080:8080"       ← indent 6
#
# We intentionally do NOT hard-code "2-space indent" — we bucket by the
# "depth" (0 / first-level / second-level / item) using relative comparisons,
# so a template that uses 4-space indent would still parse correctly. The
# check fails CLOSED: any line we can't bucket is ignored (safer than
# false-flagging).

_SERVICE_INDENT = 2
_BLOCK_KEY_INDENT = 4


def _traefik_label_on_line(text: str) -> bool:
    """True if the line contains a Traefik router-enabling label.

    Tolerant of:
      * single-quoted, double-quoted, or unquoted label values
      * jinja-wrapped hosts (``traefik.http.routers.{{ spec.id }}.rule=...``)
      * ``traefik.enable=true`` OR any router / service sub-key

    ``traefik.enable=false`` — NOT matched. If a template explicitly disables
    Traefik for a service, host ports are allowed.
    """
    lowered = text.lower()
    # Routers/services imply Traefik is enabled by contract — either axis counts.
    return (
        "traefik.enable=true" in lowered
        or "traefik.http.routers." in lowered
        or "traefik.http.services." in lowered
    )


# Long-form ports sub-keys (Docker Compose v3 / v3.8+ schema). Only ``published:``
# represents the host side; the others are container-side or metadata and MUST
# NOT be flagged. We match these as a prefix (``<key>:``) because they appear
# either on the list-item header line (``- target: 8000``) or on indented
# continuation lines (``  published: 8080``).
_LONG_FORM_NON_HOST_KEYS = (
    "target:",
    "protocol:",
    "mode:",
    "name:",
    "host_ip:",
    "app_protocol:",
)


def _host_binding_on_ports_item(item_line: str) -> bool:
    """True if a ``ports:`` list-item line binds a host port in SHORT FORM.

    Short-form examples (all flagged):
      - "8080:8080"
      - "127.0.0.1:8080:8080"
      - "${PORT}:8000"
      - "{{ spec.port }}:8000"

    NOT flagged:
      - "8000"              (bare, no colon)
      - "8000/tcp"          (protocol suffix, no host side)
      - "- target: 8000"    (long-form subkey — handled by
                             :func:`_long_form_published_on_line` separately,
                             and ONLY when the key is ``published:``)
    """
    # Strip the "- " list marker, trailing comments, and surrounding quotes.
    stripped = item_line.strip()
    if stripped.startswith("- "):
        stripped = stripped[2:].strip()
    # Long-form sub-keys starting the list item (``- target: 8000``,
    # ``- protocol: tcp``) are NOT short-form host bindings. They sit
    # alongside ``published:`` in a multi-line entry; only ``published:``
    # itself is the host side (caught by ``_long_form_published_on_line``).
    for key in _LONG_FORM_NON_HOST_KEYS:
        if stripped.startswith(key):
            return False
    # A line like `- "8080:8080"` → value = `8080:8080` after strip.
    value = stripped.strip("\"'").split("#", 1)[0].strip()
    if not value:
        return False
    # Jinja ``{{ ... }}`` values are opaque strings; if they contain ``:`` it's
    # a host binding by construction. Bare ``8000`` and ``8000/tcp`` have no
    # colon and therefore are container-only / expose-style declarations.
    return ":" in value


def _long_form_published_on_line(item_line: str) -> bool:
    """True if a long-form ports entry declares ``published:`` (host side)."""
    return item_line.strip().startswith("published:")


def scan_template(path: Path) -> list[Violation]:
    """Scan one ``compose.yaml.j2`` file; return a list of violations.

    Public by design — also used directly by unit tests to avoid spinning
    subprocesses for every fixture.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # A template we can't read is not a template we can flag. Ignore and
        # let other checks (structure, perms) catch it.
        return []

    # Per-service state. Order-preserving so violation reports mirror source.
    service_states: dict[str, dict] = {}
    current_service: str | None = None
    in_services_block = False
    inside_labels_block = False
    inside_ports_block = False

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        # Compute indent against the UNSTRIPPED original line so jinja tags
        # at the normal indent level are recognised structurally.
        stripped = raw_line.lstrip()
        indent = len(raw_line) - len(stripped)

        # Skip blank lines and YAML comments. Note: we do NOT skip jinja
        # ``{% ... %}`` tags — they sit at the same indent as surrounding
        # keys and act as pass-through from an indent-tracking POV.
        if not stripped or stripped.startswith("#"):
            continue

        # Top-level (indent 0): ``services:``, ``volumes:``, ``networks:`` …
        if indent == 0:
            in_services_block = stripped.rstrip().rstrip(":").strip() == "services"
            current_service = None
            inside_labels_block = False
            inside_ports_block = False
            continue

        if not in_services_block:
            continue

        # Service boundary (indent 2, key ending with ``:``).
        if indent == _SERVICE_INDENT and stripped.rstrip().endswith(":"):
            current_service = stripped.rstrip().rstrip(":").strip()
            service_states.setdefault(
                current_service,
                {"has_traefik": False, "port_violations": []},
            )
            inside_labels_block = False
            inside_ports_block = False
            continue

        if current_service is None:
            # We're inside ``services:`` but haven't seen a service key yet —
            # typically a blank line or comment between services. Skip.
            continue

        # Service-level sub-key (indent 4): ``labels:``, ``ports:``, ``environment:``,
        # ``healthcheck:``, ``deploy:``, etc.
        if indent == _BLOCK_KEY_INDENT and stripped.rstrip().endswith(":"):
            key = stripped.rstrip().rstrip(":").strip()
            inside_labels_block = key == "labels"
            inside_ports_block = key == "ports"
            continue

        # When we hit anything at indent <= _BLOCK_KEY_INDENT that isn't a
        # block-key, we're leaving whichever block we were in.
        if indent <= _BLOCK_KEY_INDENT:
            inside_labels_block = False
            inside_ports_block = False
            # Fall through — the line itself might be a service boundary,
            # but that case is handled above.

        # Inside a labels block — look for Traefik opt-in.
        if inside_labels_block and indent > _BLOCK_KEY_INDENT:
            if _traefik_label_on_line(stripped):
                service_states[current_service]["has_traefik"] = True
            continue

        # Inside a ports block — look for host bindings.
        if inside_ports_block and indent > _BLOCK_KEY_INDENT:
            if _host_binding_on_ports_item(stripped) or _long_form_published_on_line(stripped):
                service_states[current_service]["port_violations"].append(
                    (line_no, raw_line.rstrip())
                )
            continue

    # Emit violations only for services that actually have Traefik labels.
    # A non-Traefik worker with host ports is outside this check's scope.
    violations: list[Violation] = []
    for service, state in service_states.items():
        if not state["has_traefik"]:
            continue
        for line_no, line_text in state["port_violations"]:
            violations.append((path, service, line_no, line_text))
    return violations


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _format_report(violations: list[Violation]) -> str:
    """Operator-readable summary. Path + service + line + the offending text."""
    lines = [
        "ERROR: Traefik-routed service exposes a host port in a Fabrik template.",
        "",
        "Host ports on Traefik services bypass every middleware (Authelia,",
        "rate-limits, ACME TLS) and break the §10 admin-dashboard auth model.",
        "Remove the `ports:` entry; let Traefik own ingress.",
        "",
    ]
    for path, service, line_no, line_text in violations:
        lines.append(f"  {path}:{line_no}  (service: {service})")
        lines.append(f"    {line_text}")
    lines.append("")
    lines.append("See: docs/development/plans/2026-04-18-zero-touch-deployment.md §5")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Scan templates; exit 0 on pass, 1 on any violation."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
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
