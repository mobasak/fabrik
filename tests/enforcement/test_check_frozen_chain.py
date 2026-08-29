"""check_frozen_chain — a consumer's version pin must not predate its input.

Regression guard for the transdoc upstream proposal (2026-08-22): ui-design v9
pinned data-contract **v4** in a binding header claim while the contract was at
v5, between two correctly-run commands, caught only by an operator question.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_frozen_chain as c  # noqa: E402


def _write(root: Path, rel: str, status: str, version: int, header_extra: str = "") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"> **Status:** {status}  ·  **Version:** v{version}  ·  **Date:** 2026-08-22\n"
        f"{header_extra}\n"
        "\n## Body\n\nVersion history prose: v1 pinned data-contract.md **v1** long ago.\n",
        encoding="utf-8",
    )


def test_stale_pin_is_exactly_one_finding(tmp_path: Path) -> None:
    """The transdoc shape: consumer pins v4, input is at v5 — one finding naming
    the consumer's owning re-freeze command."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(
        tmp_path,
        "docs/ui-design.md",
        "FROZEN",
        9,
        "> Binding inputs: the FROZEN [`data-contract.md`](data-contract.md) **v4** "
        "(every field below is one of its columns)",
    )
    findings = c.check_chain(tmp_path)
    assert len(findings) == 1, findings
    assert "pins data-contract.md@v4" in findings[0]
    assert "v5" in findings[0]
    assert "/fabrik-ui-design" in findings[0]


def test_soft_wrapped_pin_is_seen(tmp_path: Path) -> None:
    """Today's real shape: the filename as a markdown link with the bold vN on
    the NEXT header line — joined before matching."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(
        tmp_path,
        "docs/ui-design.md",
        "FROZEN",
        9,
        "> Binding inputs: the FROZEN [`data-contract.md`](data-contract.md)\n> **v4** (every field)",
    )
    findings = c.check_chain(tmp_path)
    assert len(findings) == 1, findings


def test_equal_pin_is_silent(tmp_path: Path) -> None:
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(tmp_path, "docs/ui-design.md", "FROZEN", 9, "> inputs: data-contract.md **v5**")
    assert c.check_chain(tmp_path) == []


def test_draft_consumer_is_skipped(tmp_path: Path) -> None:
    """A DRAFT artifact's authoring loop owns it — never a chain finding."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(tmp_path, "docs/ui-design.md", "DRAFT", 9, "> inputs: data-contract.md **v4**")
    assert c.check_chain(tmp_path) == []


def test_absence_is_silent(tmp_path: Path) -> None:
    """Headless types have no ui-design; pre-flows projects no flows.md."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    assert c.check_chain(tmp_path) == []
    assert c.check_chain(tmp_path / "empty") == []


def test_future_pin_is_worded_as_corruption(tmp_path: Path) -> None:
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 3)
    _write(tmp_path, "docs/ui-design.md", "FROZEN", 9, "> inputs: data-contract.md **v4**")
    findings = c.check_chain(tmp_path)
    assert len(findings) == 1
    assert "FUTURE" in findings[0]


def test_body_version_history_never_false_positives(tmp_path: Path) -> None:
    """The version-HISTORY prose every frozen artifact carries (the _write body
    mentions data-contract.md **v1**) is outside the header block — no finding."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(tmp_path, "docs/ui-design.md", "FROZEN", 9, "> no pins in this header")
    assert c.check_chain(tmp_path) == []


def test_warn_only_exit_is_always_zero(tmp_path: Path, capsys, monkeypatch) -> None:
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(tmp_path, "docs/ui-design.md", "FROZEN", 9, "> inputs: data-contract.md **v4**")
    monkeypatch.setattr(sys, "argv", ["check_frozen_chain.py", str(tmp_path)])
    assert c.main() == 0
    out = capsys.readouterr().out
    assert "WARN:" in out and "re-freeze" in out


def test_history_notes_never_outvote_the_binding_pin(tmp_path: Path) -> None:
    """Round-trip (transdoc 2026-08-22): the freeze headers' own house style puts
    per-version HISTORY notes inside the header block — a v3 history mention
    beside a v5 binding pin must compare as v5 (max per (consumer, input)), so a
    completed re-freeze goes QUIET instead of warning forever."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(
        tmp_path,
        "docs/ui-design.md",
        "FROZEN",
        10,
        "> v6 note: designed against `data-contract.md` **v3** back then\n"
        "> Binding inputs: the FROZEN [`data-contract.md`](data-contract.md) **v5** "
        "(every field below is one of its columns)",
    )
    assert c.check_chain(tmp_path) == [], "the completed re-freeze must be silent"


def test_max_pin_still_fires_when_genuinely_stale(tmp_path: Path) -> None:
    """Same shape with the input ahead of the max pin: exactly one finding,
    citing the BINDING pin (@v5), never the history note."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 6)
    _write(
        tmp_path,
        "docs/ui-design.md",
        "FROZEN",
        10,
        "> v6 note: against `data-contract.md` **v3** ·\n"
        "> Binding inputs: [`data-contract.md`](data-contract.md) **v5**",
    )
    findings = c.check_chain(tmp_path)
    assert len(findings) == 1, findings
    assert "@v5" in findings[0], "cite the binding pin, never the history note"


# --- transdoc 1.8: a stale pin in BODY prose was structurally unreachable -----


def test_body_prose_pin_that_contradicts_the_header_is_warned(tmp_path):
    """transdoc 1.8: this gate is header-block-only BY DESIGN, which is right for the
    BINDING pin — but it made a version reference in the artifact's BODY unreachable.
    Their damage was real: docs/ui-design.md carried "Banned: any field not in
    data-contract.md **v4**" from v7 through v12 while the header pin moved v4 → v5 →
    v6. TWO re-freezes explicitly re-pinned the header and missed it, and that line is
    THE RULE an agent consults to decide whether a field is legal — it would have
    authorised v5/v6 fields against a v4 contract. Found by a human-style read; no
    check could see it."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "data-contract.md").write_text(
        "**Status:** FROZEN · **Version:** v6\n\n## Fields\n", encoding="utf-8"
    )
    (d / "ui-design.md").write_text(
        "**Status:** FROZEN · **Version:** v12 · frozen against `data-contract.md` **v6**\n"
        "\n## Rules\n\nBanned: any field not in data-contract.md **v4**\n",
        encoding="utf-8",
    )
    body = [f for f in c.check_chain(tmp_path) if "BODY prose" in f]
    assert len(body) == 1, c.check_chain(tmp_path)
    assert "v4" in body[0] and "v6" in body[0]


def test_body_prose_agreeing_with_the_header_is_silent(tmp_path):
    """The inverse must hold or the sweep is noise: a body that cites the SAME version
    the header pins is correct prose, not drift."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "data-contract.md").write_text(
        "**Status:** FROZEN · **Version:** v6\n\n## Fields\n", encoding="utf-8"
    )
    (d / "ui-design.md").write_text(
        "**Status:** FROZEN · **Version:** v12 · frozen against `data-contract.md` **v6**\n"
        "\n## Rules\n\nBanned: any field not in data-contract.md **v6**\n",
        encoding="utf-8",
    )
    assert [f for f in c.check_chain(tmp_path) if "BODY prose" in f] == []


# --- transdoc 01M14VM1RT: the WARN had the line number and dropped it ----------


def test_body_prose_warn_names_the_line_number(tmp_path):
    """The advisory says "confirm before editing", but named only the file and the two
    versions — so a reviewer had to grep every occurrence and judge each with no way to
    check off what they had covered. transdoc judged four and missed two; four-judged
    and six-judged read IDENTICALLY. The two survivors were present-tense NORMATIVE
    rules ("Banned: any field not in data-contract.md v6"), i.e. the line an agent
    consults to decide whether a field is legal. The checker had the offsets all along."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "data-contract.md").write_text(
        "**Status:** FROZEN · **Version:** v10\n\n## Fields\n", encoding="utf-8"
    )
    (d / "ui-design.md").write_text(
        "**Status:** FROZEN · **Version:** v12 · frozen against `data-contract.md` **v10**\n"
        "\n## Rules\n\n"
        "padding line\n"
        "Banned: any field not in data-contract.md **v6**\n"
        "more padding\n"
        "Required: every field is a data-contract.md **v4** column\n",
        encoding="utf-8",
    )
    body = [f for f in c.check_chain(tmp_path) if "BODY prose" in f]
    assert len(body) == 2, body
    # Each finding must carry ITS OWN line number, so two occurrences are distinguishable.
    assert any("ui-design.md:6" in f for f in body), body
    assert any("ui-design.md:8" in f for f in body), body
    # …and the line numbers must be DIFFERENT — one shared number would defeat the point.
    import re as _re
    nums = {_re.search(r"ui-design\.md:(\d+)", f).group(1) for f in body}
    assert len(nums) == 2, nums


# --- attestation staleness: "reviewed at v6" on a contract now at v11 ---------
# /fabrik-flows-review and /fabrik-ui-design-review write
# `Independently reviewed: v<N> — <cmd> no-op <date>` into the contract, and NOTHING
# read it: `rg "Independently reviewed" scripts/` returned zero hits. So nothing noticed
# a contract moving past its last independent review.
#
# ⚠️ The rule is NOT "attestation == current version". Real contracts carry a HISTORY
# (tryton-crm: v6 · v4 · v2 on a v11 contract), which is correct — those rounds happened.
# The signal is the NEWEST attestation vs the current version: everything after it is
# unreviewed. Measured across 29 real contracts: 7 carry an attestation and 6 are stale
# by 1-5 versions.


def test_attestation_older_than_the_contract_version_is_warned(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "ui-design.md").write_text(
        "**Status:** FROZEN · **Version:** v11\n\n## Rules\n\n"
        "> **Independently reviewed:** v6 — `/fabrik-ui-design-review` no-op 2026-08-11\n",
        encoding="utf-8",
    )
    out = [f for f in c.check_chain(tmp_path) if "independent review attests" in f]
    assert len(out) == 1, c.check_chain(tmp_path)
    assert "v6" in out[0] and "v11" in out[0]


def test_attestation_history_uses_the_newest_entry(tmp_path):
    """A history is correct, not drift — grade the newest entry, never the oldest."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "ui-design.md").write_text(
        "**Status:** FROZEN · **Version:** v11\n\n## Rules\n\n"
        "> **Independently reviewed:** **v6 — no-op 2026-08-11** · **v4 — no-op 2026-08-01** · v2 no-op\n",
        encoding="utf-8",
    )
    out = [f for f in c.check_chain(tmp_path) if "independent review attests" in f]
    assert len(out) == 1 and "v6" in out[0], out


def test_attestation_current_with_the_contract_is_silent(tmp_path):
    """The counter-direction: a contract reviewed AT its current version is not drift."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "ui-design.md").write_text(
        "**Status:** FROZEN · **Version:** v6\n\n## Rules\n\n"
        "> **Independently reviewed:** v6 — no-op 2026-08-11\n",
        encoding="utf-8",
    )
    assert [f for f in c.check_chain(tmp_path) if "independent review attests" in f] == []


def test_a_contract_with_no_attestation_is_silent(tmp_path):
    """Absence is never a finding — most contracts have no review twin run yet, and a
    check that demanded one would fire on 22 of 29 real contracts."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "ui-design.md").write_text(
        "**Status:** FROZEN · **Version:** v11\n\n## Rules\n\nno attestation here\n",
        encoding="utf-8",
    )
    assert [f for f in c.check_chain(tmp_path) if "independent review attests" in f] == []


# --- transdoc 01M17S1B: the universal-declarative rule shape was invisible ----


def test_universal_declarative_body_pin_is_warned(tmp_path):
    """transdoc missed the SAME two lines twice (v20 and v21): 'Every field named below
    is a `data-contract.md` **v10** column' binds a reader at least as hard as a modal
    and carried none of the prescriptive vocabulary — invisible to the filter that
    decides what gets line-named. Measured before widening (2026-08-30): +6 newly
    eligible lines fleet-wide, all in the reporting repo's own chain files."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "data-contract.md").write_text(
        "**Status:** FROZEN · **Version:** v11\n\n## Fields\n", encoding="utf-8"
    )
    (d / "ui-design.md").write_text(
        "**Status:** FROZEN · **Version:** v22 · frozen against `data-contract.md` **v11**\n"
        "\n## Rules\n\nEvery field named below is a `data-contract.md` **v10** column.\n",
        encoding="utf-8",
    )
    body = [f for f in c.check_chain(tmp_path) if "BODY prose" in f]
    assert len(body) == 1, c.check_chain(tmp_path)
    assert "v10" in body[0] and "v11" in body[0]
