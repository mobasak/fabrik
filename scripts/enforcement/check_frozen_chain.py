#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_frozen_chain.py | none
"""Frozen-chain drift gate — a consumer's version PIN must not predate its input.

The 2-contract stage is a CHAIN of individually-frozen artifacts (``flows.md`` →
``data-contract.md`` → ``ui-design.md`` [→ ``design-system.md``]), each converged
by its own command to a no-op — and nothing owned the seams between them: a
version bump upstream left every downstream consumer frozen against a version
that no longer exists, with no check saying so (transdoc upstream proposal
2026-08-22 — the drift recurred between two correctly-run commands within hours,
caught by an operator question for the third time in one repo).

WHAT IT CHECKS (per artifact in the registry, present-if-exists):
- **Self-version:** the header's ``**Status:** <S> · **Version:** v<N>`` line
  (first ~5 lines). ``DRAFT`` artifacts are skipped entirely — their authoring
  loop owns them. Absence of the file is silent (headless types have no
  ui-design; pre-flows projects have no flows.md — absence is never a finding).
- **Pins:** within the artifact's HEADER BLOCK only (everything before the first
  ``## `` heading, soft-wrapped lines joined), every mention of another registry
  artifact's filename followed (within a bounded window) by a bold ``**vN**`` is
  a version pin. Header-block-only by construction: the version-HISTORY prose
  every frozen artifact legitimately carries in its body/ledger sections must
  never false-positive.
- **The verdict:** consumer pins B@vX while B's current self-version is vY —
  ``vY > vX`` → the consumer's freeze predates its input: WARN naming the
  consumer's owning re-freeze command. ``vY < vX`` → a pin from the future:
  WARN worded as corruption. Equal → silent.

FAIL DIRECTION — WARN, never ERROR, deliberately: when a freeze command bumps an
input to v5, the tree NECESSARILY holds the consumer's v4 pin for the duration
of that commit; an ERROR would red the gate on the exact commit the workflow
requires (the check_schema_sync reasoning). Exit is ALWAYS 0 (warn_only
contract); the findings are the product.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: artifact (project-relative) → its owning re-freeze command. Present-if-exists.
CHAIN_REGISTRY: dict[str, str] = {
    "docs/flows.md": "/fabrik-flows",
    "docs/data-contract.md": "/fabrik-data-contract",
    "docs/ui-design.md": "/fabrik-ui-design",
    "docs/design-system.md": "/fabrik-ui-design",
}

_STATUS_RE = re.compile(
    r"^>?\s*\*\*Status:\*\*\s*(?P<status>FROZEN|DRAFT|CONVERGED)\b.*?"
    r"\*\*Version:\*\*\s*v(?P<version>\d+)",
    re.I,
)
#: chars after a filename mention within which a bold **vN** counts as its pin
_PIN_WINDOW = 120


def _self_version(text: str) -> tuple[str, int] | None:
    """``(status, version)`` from the first 5 lines, or None (no parseable header)."""
    for line in text.splitlines()[:5]:
        m = _STATUS_RE.search(line)
        if m:
            return m.group("status").upper(), int(m.group("version"))
    return None


def _header_block(text: str) -> str:
    """Everything before the first ``## `` heading, soft-wrapped lines JOINED —
    the pin grammar is line-shape-independent by construction (transdoc's real
    pin soft-wraps across two lines with the filename as a markdown link)."""
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            break
        lines.append(line.strip())
    return " ".join(lines)


def _pins(header: str, own_name: str) -> dict[str, int]:
    """``{registry-basename: pinned version}`` found in the joined header.

    MAX per (consumer, input) pair (transdoc round-trip 2026-08-22): the freeze
    headers' own house style puts per-version HISTORY notes inside the header
    block ("v6 … against `data-contract.md` **v3**"), and a first-match rule
    warned FOREVER after a completed re-freeze — the check's value inverting at
    the exact moment it should go quiet. Every history mention is by
    construction ≤ the binding pin, so max selects the binding pin without
    classifying prose; a genuinely-future pin still exceeds the input's version,
    so the corruption arm still fires."""
    out: dict[str, int] = {}
    for rel in CHAIN_REGISTRY:
        base = Path(rel).name
        if base == own_name:
            continue
        for m in re.finditer(re.escape(base), header):
            window = header[m.end() : m.end() + _PIN_WINDOW]
            vm = re.search(r"\*\*v(\d+)\*\*", window)
            if vm:
                v = int(vm.group(1))
                out[base] = max(out.get(base, v), v)
    return out


def check_chain(root: Path) -> list[str]:
    """All frozen-chain findings for the project at ``root`` (empty = clean)."""
    versions: dict[str, tuple[str, int]] = {}
    headers: dict[str, str] = {}
    for rel in CHAIN_REGISTRY:
        p = root / rel
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # absence is never a finding
        sv = _self_version(text)
        if sv is None:
            continue  # no parseable header — the freeze-header gate owns that
        versions[Path(rel).name] = sv
        headers[Path(rel).name] = _header_block(text)

    findings: list[str] = []
    for rel, cmd in CHAIN_REGISTRY.items():
        name = Path(rel).name
        if name not in versions:
            continue
        status, _own = versions[name]
        if status == "DRAFT":
            continue  # its authoring loop owns it
        for pinned_name, pinned_v in _pins(headers[name], name).items():
            if pinned_name not in versions:
                continue  # pin names a file this project doesn't have
            _pstatus, current_v = versions[pinned_name]
            if current_v > pinned_v:
                findings.append(
                    f"{rel} pins {pinned_name}@v{pinned_v} but it is at v{current_v} — "
                    f"the freeze predates its input; re-freeze via {cmd}"
                )
            elif current_v < pinned_v:
                findings.append(
                    f"{rel} pins {pinned_name}@v{pinned_v} but it is at v{current_v} — "
                    f"a pin from the FUTURE (header corruption or a reverted input); "
                    f"reconcile via {cmd}"
                )
    return findings


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings = check_chain(root)
    for f in findings:
        print(f"WARN: {f}")
    if findings:
        print(
            f"frozen-chain: {len(findings)} stale pin(s) — a consumer is frozen against "
            "a version that no longer exists; run the named re-freeze command(s)."
        )
    return 0  # warn_only contract: findings are the product, never a red exit


if __name__ == "__main__":
    sys.exit(main())
