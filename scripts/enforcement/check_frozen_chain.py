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

# The attestation /fabrik-flows-review and /fabrik-ui-design-review write into a contract.
# Tolerant on purpose — the real corpus writes all of these:
#   "**Independently reviewed:** v2 — …"      (transdoc/flows.md, in a blockquote)
#   "**Independently reviewed:** **v6 — …**"  (tryton-crm/ui-design.md, bold value)
#   "> **Independently reviewed: v2 — …**"    (tojlo-mail/ui-design.md)
# A narrower pattern is what made an earlier count report 2 attestations and 0 stale when
# the truth was 7 and 6 — the measurement that wrongly justified deferring this check.
_ATTEST_RE = re.compile(r"Independently\s+reviewed:?\*{0,2}\s*:?\s*\*{0,2}v(\d+)", re.I)


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


# A version reference in BODY prose: "<file>.md ... v<N>" within a short window, which
# is how the real drift was written ("any field not in data-contract.md **v4**").
_BODY_PIN_RE = re.compile(r"(?P<name>[a-z0-9-]+\.md)[^\n]{0,40}?\*{0,2}v(?P<v>\d+)\*{0,2}", re.I)


# Prose that BINDS a future reader, as opposed to prose that recounts history. Only a
# binding sentence can authorise a wrong-version field, which is the damage 1.8 names.
# Second alternative (transdoc 01M17S1B): a UNIVERSAL DECLARATIVE — "Every field named
# below is a <doc> vN column" — binds at least as hard as a modal and carried none of
# them; the same two lines went invisible through TWO converged re-freezes. Measured
# before widening (2026-08-30, all /opt chain files): +6 newly eligible lines, all in
# the reporting repo — no wallpaper risk at this vocabulary.
_PRESCRIPTIVE_RE = re.compile(
    r"\b(?:banned|forbidden|must|must not|never|only|required|not in|conform|comply)\b"
    r"|\b(?:every|each|all)\b[^\n]{0,60}?\b(?:is|are)\b",
    re.I,
)


def check_chain(root: Path) -> list[str]:
    """All frozen-chain findings for the project at ``root`` (empty = clean)."""
    versions: dict[str, tuple[str, int]] = {}
    headers: dict[str, str] = {}
    bodies: dict[str, str] = {}
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
        bodies[Path(rel).name] = text

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

    # transdoc finding 1.8 (2026-08-23): this gate is header-block-only BY DESIGN — and
    # that is correct for the BINDING pin. But it makes a version reference in the
    # artifact's BODY structurally unreachable, and their damage was real:
    # docs/ui-design.md carried "Banned: any field not in data-contract.md **v4**" from
    # v7 through v12 while the header pin moved v4 -> v5 -> v6. TWO re-freezes explicitly
    # re-pinned the header and missed it. That line is THE RULE an agent consults to
    # decide whether a field is legal — it would have authorised v5/v6 fields against a
    # v4 contract. Found by a human-style read; no check could see it.
    # WARN, never block: body prose legitimately contains historical references
    # ("superseded v3", a changelog line), so this can only ever be a prompt to look.
    for rel in CHAIN_REGISTRY:
        name = Path(rel).name
        if name not in versions or versions[name][0] == "DRAFT":
            continue
        header_pins = _pins(headers[name], name)

        # ── attestation staleness ────────────────────────────────────────────────
        # The review twins write `Independently reviewed: v<N>` into the contract and
        # NOTHING read it (`rg "Independently reviewed" scripts/` → 0 hits), so a
        # contract could move past its last independent review unnoticed. Measured
        # across 29 real contracts: 7 carry an attestation, 6 were stale by 1-5
        # versions.
        #
        # NOT "attestation == current version": a contract legitimately carries a
        # HISTORY of rounds (tryton-crm: v6 · v4 · v2 at v11) and those rounds really
        # happened. The signal is the NEWEST attestation vs the current version —
        # everything after it is unreviewed. Absence of any attestation is SILENT:
        # most contracts have never had a twin run, and demanding one would fire on
        # 22 of 29.
        _attests = [int(v) for v in _ATTEST_RE.findall(bodies[name])]
        if _attests:
            _newest = max(_attests)
            _cur = versions[name][1]
            if _newest < _cur:
                findings.append(
                    f"{rel}: newest independent review attests v{_newest} but the "
                    f"contract is at v{_cur} — {_cur - _newest} version(s) have had no "
                    f"author-blind pass; re-run the review twin or drop the claim"
                )

        # everything from the first `## ` heading on — _header_block returns a JOINED
        # string, so slicing the original by its length addresses nothing.
        _txt = bodies[name]
        _i = _txt.find("\n## ")
        body_only = _txt[_i:] if _i != -1 else ""
        for other, (_st, _cur) in versions.items():
            if other == name:
                continue
            pinned = header_pins.get(other)
            if pinned is None:
                continue
            for m in _BODY_PIN_RE.finditer(body_only):
                if m.group("name") not in other:
                    continue
                # PRESCRIPTIVE prose only. The first cut flagged every body mention and
                # lit up 5 of 6 existing fixtures — body prose legitimately cites history
                # ("superseded v3", a changelog line), so an undiscriminating sweep is
                # pure noise and a noisy advisory gets ignored, which is worse than none.
                # The damage case reads like a RULE: "Banned: any field not in
                # data-contract.md **v4**". Require that shape.
                line_start = body_only.rfind("\n", 0, m.start()) + 1
                line_end = body_only.find("\n", m.end())
                line = body_only[line_start : line_end if line_end != -1 else len(body_only)]
                if not _PRESCRIPTIVE_RE.search(line):
                    # transdoc's filter-disclosure alternative ("N reported; M filtered")
                    # was BUILT and REJECTED here after measurement (2026-08-30): with
                    # the widened regex above, what remains filtered is history prose
                    # ("v1 pinned … long ago"), and the disclosure fired on the standard
                    # noise-budget fixture — a counter of benign lines is wallpaper.
                    continue
                if int(m.group("v")) != pinned:
                    # NAME THE LINE. The advisory asks the reviewer to "confirm before
                    # editing", but naming only the file and the two versions meant they
                    # had to grep every occurrence and judge each with nothing to check
                    # off — transdoc judged four and missed two, and "four judged" read
                    # identically to "six judged" (01M14VM1RT). The survivors were
                    # present-tense NORMATIVE rules, the line an agent consults to decide
                    # whether a field is legal. The offsets were here all along.
                    # `body_only` starts at `_i` in `_txt`, so the absolute offset is
                    # `_i + m.start()`.
                    lineno = _txt.count("\n", 0, _i + m.start()) + 1
                    # Excerpt is BOUNDED: final_gate truncates advisory output at 500
                    # chars with no ellipsis, and an unbounded quote is how a remedy line
                    # gets cut mid-word (checklist anti-pattern 95).
                    excerpt = " ".join(line.split())[:70]
                    # Only what VARIES goes per-finding. The advisory boilerplate is
                    # identical on every one and was repeating N times into final_gate's
                    # 500-char no-ellipsis budget (measured 1166 chars on a real 3-finding
                    # run — checklist anti-pattern 95, which loses the REMEDY line). It is
                    # now charged ONCE, in main().
                    findings.append(
                        f"{rel}:{lineno} BODY prose pins {other}@v{m.group('v')}, "
                        f"header says v{pinned} — {excerpt!r}"
                    )
    return findings


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings = check_chain(root)
    # Charge the shared advisory ONCE rather than per finding (see the note at the
    # append site): N findings x ~130 chars of identical boilerplate is how a capped
    # advisory loses its own remedy line.
    if any("BODY prose pins" in f for f in findings):
        print(
            "NOTE: BODY-prose pin drift below is ADVISORY — prose may legitimately cite "
            "history. Judge each LINE; a present-tense rule ('Banned: …', 'Every field "
            "is …') pinning a stale version is the damaging case."
        )
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
