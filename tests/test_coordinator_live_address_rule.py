"""W-9bf5a363 — a builder addresses its coordinator by a LIVE name, never one kept in its notes.

WHY. The hub coordinator runs in the code-server extension (D-1092); each of its rotations starts a process with a
new auto-generated peer name, so a name a builder wrote in its notes goes dead — infra-3's `rotate` request to
`fabrik-ec` sat 14 h. D-1337 made a builder's prompt block print `work: coordinator (<role>) → SendMessage to=<name>`,
but that line is fail-open and absent for a window `_builder` drops (the feedback owner among them), so the rule names
a resolver order, and every live name, since a stale one cannot be told apart. Each sentence is pinned WHOLE
(whitespace collapsed): a clause-pinned grader lets a force-changing rewording through. The code tokens the sentences
quote are pinned too, so the text cannot outlive the code. infra-2.md and infra-3.md are symlinks to infra.md, so the
charter check counts per RESOLVED file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACTS = {"CLAUDE.md": "D-1337", "templates/governance/CLAUDE.md": "hub D-1337"}
CHARTERS = REPO / "docs" / "reference" / "agents"
BUILDER_FILES = {"fleet.md", "infra.md", "intel.md", "kaizen.md"}
ESCALATION = "goes to the coordinator by `SendMessage`, naming"

CONTRACT_SENTENCE = (
    "messages its coordinator `rotate <name>` and waits for the keys, sending it by `SendMessage` to every `to=` name "
    "the latest `work: coordinator (<role>)` line of its prompt block prints (one may be stale when several are "
    "listed), else, or when that line says `… and <n> more`, to every name `python3 scripts/mail.py who <role>` "
    "prints (`<role>` is the role that line names: the `distributor` in `.fabrik/work/config.json`, else the name "
    "`python3 /opt/fabrik/scripts/decisions.py --merge-owner .` prints), and only when neither names a live session "
    "by `python3 scripts/mail.py send --to <this repo> --kind request --ack required --to-agent <role>` with the ask "
    "as its body on stdin — never to a session name kept in its notes, since the coordinator's session name changes "
    "when it rotates ({cite}); the coordinator — for whom the ask is not a work item —"
)
CHARTER_SENTENCE = (
    "the coordinator decides what it can and boards the rest. Send each one by `SendMessage` to every `to=` name the "
    "latest `work: coordinator (coordinator)` line of your prompt block prints (one may be stale when several are "
    "listed), else, or when that line says `… and <n> more`, to every name `python3 scripts/mail.py who "
    "coordinator` prints, and only when neither names a live session by `python3 scripts/mail.py send --to fabrik "
    "--kind request --ack required --to-agent coordinator` with the message as its body on stdin — never to a "
    "session name kept in your notes, since the coordinator's session name changes when it rotates (D-1337). A "
    "permission prompt you hit"
)


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


@pytest.mark.parametrize("rel", sorted(CONTRACTS))
def test_both_contracts_carry_the_address_order(rel: str) -> None:
    text = _flat(REPO / rel)
    sentence = CONTRACT_SENTENCE.format(cite=CONTRACTS[rel])
    assert text.count(sentence) == 1, f"{rel}: the coordinator address-order sentence is missing, reworded or doubled"


def test_every_routing_charter_carries_the_address_order() -> None:
    routed = {p.resolve().name for p in CHARTERS.glob("*.md") if ESCALATION in _flat(p)}
    assert routed == BUILDER_FILES, f"the charter files routing questions to the coordinator changed: {sorted(routed)}"
    for name in sorted(BUILDER_FILES):
        count = _flat(CHARTERS / name).count(CHARTER_SENTENCE)
        assert count == 1, f"{name}: the address-order sentence appears {count} times, want exactly 1"


def test_the_named_resolvers_exist() -> None:
    work = (REPO / "scripts" / "work.py").read_text(encoding="utf-8")
    assert 'head = f"work: coordinator ({role}) → SendMessage "' in work
    assert 'role = str(_read_config(main).get("distributor") or "").strip()' in work
    assert '"who", agent],' in work
    assert 'rest = f" … and {len(names) - shown} more" if shown < len(names) else ""' in work
    assert '"--merge-owner"' in (REPO / "scripts" / "decisions.py").read_text(encoding="utf-8")
    mail = (REPO / "scripts" / "mail.py").read_text(encoding="utf-8")
    assert 'add_parser(\n        "who", help="read-only: the live session name(s) of an agent in THIS repo' in mail
    assert '"request"' in mail.split("KINDS = frozenset(", 1)[1].split(")", 1)[0]
