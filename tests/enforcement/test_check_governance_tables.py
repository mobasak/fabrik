#!/usr/bin/env python3
# AFTER-EDIT: scripts/enforcement/check_governance_tables.py
"""Behavior contract for the governance-table guard.

The invariant these tests exist for is NOT "does it find bad rows" — it is the EXIT CODE. The check
is registered `warn_only=True`, and `final_gate.run_optional_check` promotes a non-zero exit from a
warn_only check to a gate FAILURE, so a check that returns 1 on a finding hard-fails the completion
gate in every one of the ~46 repos `scripts/enforcement/` syncs to, on the first sync, blaming the
registration rather than the table. The first draft did exactly that; an author-blind seat measured
47 of 49 `/opt` CLAUDE.md files failing. `test_findings_do_not_fail_the_gate` is that guard.

The rest pin boundaries later seats found by rendering fixtures with markdown_it and by mutating the
check: an indented table (live in CLAUDE.md's own § Orient), a fenced example of a bad row (a false
positive), a header row that itself carries a pipe (GFM renders no table at all and a naive check is
silent — strictly worse than the defect being guarded), both contracts actually being scanned, the
advisory carrying its file:line, `_root()` resolving at all (it had ZERO coverage), the remediation
text not prescribing an escape inside a code span, and an unreadable contract not crashing a
warn_only check into a gate failure.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_CHECK = (
    Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_governance_tables.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("check_governance_tables", _CHECK)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _root(tmp_path: Path, body: str) -> Path:
    (tmp_path / "scripts" / "enforcement").mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text(body, encoding="utf-8")
    return tmp_path


_GOOD = "| Rule | Instead |\n|---|---|\n| do the thing | like this |\n"
_BAD = "| Rule | Instead |\n|---|---|\n| do the thing | run `grep -c '^| I'` here |\n"


def _run(mod, root: Path, argv: list[str], monkeypatch) -> int:
    monkeypatch.setattr(mod, "_root", lambda: root)
    return mod.main(argv)


def test_findings_do_not_fail_the_gate(tmp_path, monkeypatch, capsys):
    """THE load-bearing one: a finding must WARN, never exit non-zero, on the gate's own call."""
    mod = _load()
    rc = _run(mod, _root(tmp_path, _BAD), [], monkeypatch)
    assert rc == 0, "warn_only contract: a finding must not fail the gate in ~46 synced repos"
    assert "ADVISORY" in capsys.readouterr().out


def test_strict_exits_one_on_a_finding(tmp_path, monkeypatch):
    mod = _load()
    assert _run(mod, _root(tmp_path, _BAD), ["--strict"], monkeypatch) == 1


def test_clean_tree_is_silent_both_ways(tmp_path, monkeypatch, capsys):
    mod = _load()
    root = _root(tmp_path, _GOOD)
    assert _run(mod, root, [], monkeypatch) == 0
    assert _run(mod, root, ["--strict"], monkeypatch) == 0
    assert "OK" in capsys.readouterr().out


def test_indented_table_is_still_read(tmp_path, monkeypatch):
    """GFM accepts up to 3 spaces of indent — CLAUDE.md's own § Orient table is indented 3."""
    mod = _load()
    body = "text\n\n   | Stage | Covers |\n   |---|---|\n   | 3-plan | run `grep -c '^| I'` |\n"
    assert _run(mod, _root(tmp_path, body), ["--strict"], monkeypatch) == 1


def test_fenced_example_is_not_a_finding(tmp_path, monkeypatch):
    """A rule about bad table rows attracts a fenced EXAMPLE of one; firing there is wallpaper."""
    mod = _load()
    body = _GOOD + "\n```\n| Rule | Instead |\n|---|---|\n| x | y | z |\n```\n"
    assert _run(mod, _root(tmp_path, body), ["--strict"], monkeypatch) == 0


def test_header_row_carrying_a_pipe_is_reported(tmp_path, monkeypatch, capsys):
    """An inflated header means no body row can exceed it — GFM renders no table and content is lost."""
    mod = _load()
    body = "| Rule | run `grep -c '^| I'` | Instead |\n|---|---|\n| a | b |\n"
    assert _run(mod, _root(tmp_path, body), ["--strict"], monkeypatch) == 1
    assert "HEADER width disagrees" in capsys.readouterr().out


def test_missing_contract_skips_rather_than_passing_silently(tmp_path, monkeypatch, capsys):
    mod = _load()
    (tmp_path / "scripts" / "enforcement").mkdir(parents=True)
    assert _run(mod, tmp_path, ["--strict"], monkeypatch) == 0
    assert "SKIPPED" in capsys.readouterr().out


def test_both_contracts_are_scanned(tmp_path, monkeypatch, capsys):
    """A mutant that drops `templates/governance/CLAUDE.md` from _TARGETS survived every other test.

    The template is the FLEET-SYNCED half — the copy that reaches ~46 repos — so a check that silently
    stops reading it is worse than no check: it reports OK while the distributed contract rots.
    """
    mod = _load()
    root = _root(tmp_path, _GOOD)
    (root / "templates" / "governance").mkdir(parents=True)
    (root / "templates" / "governance" / "CLAUDE.md").write_text(_BAD, encoding="utf-8")
    rc = _run(mod, root, ["--strict"], monkeypatch)
    out = capsys.readouterr().out
    assert rc == 1
    assert "templates/governance/CLAUDE.md" in out, (
        "the template half must be scanned, not just the root contract"
    )


def test_advisory_names_the_file_and_line(tmp_path, monkeypatch, capsys):
    """For a warn_only check the stdout IS the whole product — a message without file:line is unactionable."""
    mod = _load()
    _run(mod, _root(tmp_path, _BAD), [], monkeypatch)
    out = capsys.readouterr().out
    assert "CLAUDE.md:3" in out, (
        "the advisory must name the file and the line, not just that something is wrong"
    )


def test_root_resolves_to_the_repo_that_owns_the_script(monkeypatch):
    """_root() had ZERO coverage: every other test monkeypatches it.

    A wrong root does not fail loudly — it prints SKIPPED and returns 0, i.e. a GREEN advisory row in every
    synced repo, forever. This test is the only thing standing between that and the fleet.
    """
    mod = _load()
    root = mod._root()
    assert (root / "scripts" / "enforcement" / "check_governance_tables.py").is_file()
    assert (root / "CLAUDE.md").is_file()


# A byte-for-byte pin of the shipped remedy. Asserting substrings was the first draft and it is DODGEABLE:
# a reviewer restored the defect in different words ("escape it as `\\|` ANYWHERE it appears, code spans
# included; inside a CODE SPAN rephrase is merely an alternative") and the substring test passed 12/12 while
# the fleet-facing advice was wrong again. A golden pin cannot be reworded by accident — only deliberately,
# in both places, which is the point.
_PINNED_REMEDY = (
    "an unescaped `|` truncates this rule for every rendered reader — escape it as `\\|` in PROSE, "
    "but inside a CODE SPAN rephrase the example so it carries no literal pipe: `\\|` is alternation "
    "in GNU BRE and these contracts are read RAW as well as rendered, so escaping there silently "
    "changes what the example command does."
)


def test_remediation_is_the_pinned_text(tmp_path, monkeypatch, capsys):
    """The advisory ships to ~46 repos, so its ADVICE is fleet-shipping code, not decoration."""
    mod = _load()
    assert mod.REMEDY == _PINNED_REMEDY, (
        "the shipped remedy changed — update the pin ONLY after re-checking that the new advice is "
        "correct on BOTH paths: it must render AND the example must still execute correctly"
    )
    _run(mod, _root(tmp_path, _BAD), [], monkeypatch)
    out = capsys.readouterr().out
    assert _PINNED_REMEDY in out, "the pinned remedy must be what actually reaches the reader"


def test_unreadable_contract_is_reported_not_raised(tmp_path, monkeypatch, capsys):
    """`main()` returns 0 ALWAYS — an OSError was the one door that reached a non-zero exit anyway.

    A warn_only check exiting non-zero is promoted by `run_optional_check` to a gate FAILURE in every
    synced repo, with a message blaming the registration rather than the unreadable file.
    """
    import os

    mod = _load()
    root = _root(tmp_path, _GOOD)
    os.chmod(root / "CLAUDE.md", 0o000)
    try:
        rc_gate = _run(mod, root, [], monkeypatch)  # the GATE's own call — no --strict
        out = capsys.readouterr().out
        rc_strict = _run(mod, root, ["--strict"], monkeypatch)
        capsys.readouterr()
    finally:
        os.chmod(root / "CLAUDE.md", 0o644)
    # `rc in (0, 1)` was the first draft and it is a TAUTOLOGY: every return of main() satisfies it,
    # so restoring `return 1` in the handler passed the test while hard-failing the gate in ~46 repos.
    assert rc_gate == 0, "warn_only contract: an unreadable contract must not exit non-zero"
    assert rc_strict == 1, "--strict must still carry the regression signal"
    assert "could not be read" in out


# --- the code-span rule (W-80ffca68): a pipe spelled to survive a TABLE, inside a code span -------
#
# Inside a table row GFM un-escapes `\|` to `|` but the RAW reader (how a rule pack reaches an agent)
# sees `\|` — invalid Python, JS or URL. Outside a row both readers see `\|`, where GNU BRE alternation
# is legitimate, so the rule is scoped to rows inside a delimiter-confirmed table. Each guard's subject
# is written several LEGITIMATE ways (core/45-testing-strategy § Banned Patterns), never one spelling.

_PACK_REL = ".windsurf/rules/core/10-python.md"
_SPAN_PINNED_REMEDY = (
    "a table-escaped pipe inside a CODE SPAN is `|` to the rendered reader and a literal "
    "backslash-pipe to the RAW reader (invalid Python, JS or URL; alternation in GNU BRE) — rephrase so "
    "the span carries no pipe: move the alternation into prose beside the span, split the span in two, "
    "or lift the example into a fenced block; never an HTML entity (`&#124;` stays literal for BOTH "
    "readers)."
)


def _pack(root: Path, body: str) -> Path:
    p = root / _PACK_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


_TABLE = "| Don't | Do |\n|---|---|\n"


def test_span_pipe_in_a_rule_pack_row_is_reported(tmp_path, monkeypatch, capsys):
    """B1 — five legitimate spellings of the defect, each in its own pack row; file:line and the span named;
    the gate's own call stays rc 0 (warn_only) while --strict carries the signal."""
    mod = _load()
    root = _root(tmp_path, _GOOD)
    rows = [
        "| `Optional[str]` | `str \\| None` |",  # Python union
        "| `process.env.X \\|\\| 'default'` | throw |",  # JS or-fallback, two pipes
        '| `auth.x` | `{reason: "a" \\| "b"}` |',  # schema literal
        "| states | `/login?reason=invalid\\|wrong-browser` |",  # URL alternation
        "| cls | ``f(x) → (a, b) \\| None`` |",  # a double-backtick span
        "| cls | ``a ` b \\| None`` |",  # a double-backtick span holding a single backtick: ONE span
    ]
    # Shapes a review seat found the first walk MISSED, each a real table GFM renders (markdown_it):
    later = (
        "\n```\n~~~\n```\n"
        + _TABLE
        + "| t | `tilde \\| inside` |\n"  # a ~~~ line closes no ``` fence
        "\n    ```\n" + _TABLE + "| i | `indent4 \\| marker` |\n"  # a marker indented 4 is code
        "\n```html\n<!-- opener inside a fence\n```\n" + _TABLE + "| c | `after \\| comment` |\n"
        "\n" + _TABLE + "| e | use \\` and `escaped \\| then` |\n"  # an escaped backtick is text
        "| f | `x | `cell \\| split` |\n"  # cells are split before spans: no span crosses a cell
    )
    _pack(root, "\ufeff" + _TABLE + "\n".join(rows) + "\n" + later)  # a BOM hides nothing
    rc_gate = _run(mod, root, [], monkeypatch)
    out = capsys.readouterr().out
    assert rc_gate == 0, "warn_only contract: a span finding must not fail the gate"
    assert "ADVISORY" in out
    for lineno in (3, 4, 5, 6, 7, 8):
        assert f"{_PACK_REL}:{lineno}:" in out, f"row {lineno} missing from:\n{out}"
    assert out.count(": code span carries a table-escaped pipe") == 11, out
    for span in (
        "`tilde \\| inside`",
        "`indent4 \\| marker`",
        "`after \\| comment`",
        "`escaped \\| then`",
        "`cell \\| split`",
    ):
        assert f"The span: {span}" in out, f"{span} missed:\n{out}"
    assert "The span: `str \\| None`" in out
    assert "The span: ``a ` b \\| None``" in out, "a double-backtick span is ONE span"
    assert _run(mod, root, ["--strict"], monkeypatch) == 1


def test_span_pipe_outside_a_table_row_is_not_reported(tmp_path, monkeypatch, capsys):
    """B2 — outside a row both readers see `\\|`, where GNU BRE alternation is legitimate."""
    mod = _load()
    root = _root(tmp_path, _GOOD)
    _pack(
        root,
        "Use `grep -n 'return\\|raise'` over the function.\n"
        "- a bullet with `a \\| b` in it\n"
        "A paragraph line ending in a pipe `x \\| y` |\n" + _TABLE + "| a | b |\n"
        "Prose right under a table: `grep 'a\\|b'` is BRE, both readers agree.\n",
    )
    assert _run(mod, root, ["--strict"], monkeypatch) == 0
    assert ": code span carries a table-escaped pipe" not in capsys.readouterr().out


def test_span_pipe_in_a_fence_is_not_reported(tmp_path, monkeypatch, capsys):
    """B3 — a fenced example of a bad row (or a fenced BRE command) is not a table."""
    mod = _load()
    root = _root(tmp_path, _GOOD)
    _pack(
        root,
        "```\n" + _TABLE + "| x | `str \\| None` |\n```\n"
        "~~~bash\n" + _TABLE + "| x | `str \\| None` |\n~~~\n"  # a tilde fence is a fence too
        "````\n```\n"
        + _TABLE
        + "| x | `str \\| None` |\n```\n````\n"  # an inner ``` closes no ````
        "\n    | h | h |\n    |---|---|\n    | x | `str \\| None` |\n"  # indent 4 is a code block
        "\n\t| h | h |\n\t|---|---|\n\t| x | `str \\| None` |\n",  # a tab is four columns
    )
    assert _run(mod, root, ["--strict"], monkeypatch) == 0
    assert ": code span carries a table-escaped pipe" not in capsys.readouterr().out


def test_entity_pipe_in_a_row_span_is_reported(tmp_path, monkeypatch, capsys):
    """B4 — the COBRA counter: an HTML pipe entity is the cheapest way to silence a `\\|` finding, and
    GFM leaves it LITERAL inside a code span (measured with markdown_it) — wrong for both readers."""
    mod = _load()
    root = _root(tmp_path, _GOOD)
    rows = [
        "| a | `str &#124; None` |",
        "| b | `str &#0124; None` |",  # leading zeros are valid CommonMark
        "| c | `str &#x7c; None` |",
        "| d | `str &#X7C; None` |",
        "| e | `str &vert; None` |",
        "| f | `str &verbar; None` |",
        "| g | `str &VerticalLine; None` |",
    ]
    _pack(root, _TABLE + "\n".join(rows) + "\n")
    assert _run(mod, root, ["--strict"], monkeypatch) == 1
    assert capsys.readouterr().out.count(": code span carries a table-escaped pipe") == 7


def test_rule_pack_rows_are_width_checked(tmp_path, monkeypatch, capsys):
    """B5 — the width rule now covers the packs too, in EVERY subdirectory of `.windsurf/rules/` (a roster
    narrowed to `core/` survived the first draft of this file: every grader wrote its pack there), and the
    OK line reports the two rosters apart."""
    mod = _load()
    root = _root(tmp_path, _GOOD)
    saas = ".windsurf/rules/saas/60-saas-ui.md"
    _pack(root, _TABLE + "| a | run `grep -c '^| I'` here |\n")
    (root / saas).parent.mkdir(parents=True)
    (root / saas).write_text(_TABLE + "| s | run `grep -c '^| I'` here |\n", encoding="utf-8")
    assert _run(mod, root, ["--strict"], monkeypatch) == 1
    out = capsys.readouterr().out
    assert f"{_PACK_REL}:3: table row renders 3 cells" in out
    assert f"{saas}:3: table row renders 3 cells" in out, (
        "a pack outside core/ must be on the roster"
    )
    _pack(root, _TABLE + "| a | b |\n")
    (root / saas).write_text(_TABLE + "| s | t |\n", encoding="utf-8")
    assert _run(mod, root, [], monkeypatch) == 0
    assert "across 1 contract(s) + 2 pack(s)" in capsys.readouterr().out


def test_span_remediation_is_the_pinned_text(tmp_path, monkeypatch, capsys):
    """B6 — the span advice ships to ~46 repos; it is pinned byte-for-byte like REMEDY and must reach stdout."""
    mod = _load()
    assert mod.SPAN_REMEDY == _SPAN_PINNED_REMEDY, (
        "the shipped span remedy changed — update the pin ONLY after re-checking it against markdown_it "
        "on both readers (rendered row vs raw) and that it still names no entity as a remedy"
    )
    root = _root(tmp_path, _GOOD)
    _pack(root, _TABLE + "| a | `str \\| None` |\n")
    _run(mod, root, [], monkeypatch)
    assert _SPAN_PINNED_REMEDY in capsys.readouterr().out


def test_prose_escape_in_a_row_is_not_a_span_finding(tmp_path, monkeypatch, capsys):
    """B7 — `\\|` in a row OUTSIDE any span is the sanctioned prose escape; and a lone `|…|` line with no
    delimiter row is a paragraph to GFM, not a table, so a span there is left alone."""
    mod = _load()
    root = _root(tmp_path, _GOOD)
    _pack(
        root,
        _TABLE + "| a | either this \\| or that, with `code` beside it |\n"
        "\n| lone | `str \\| None` |\n"
        "\n<!--\n" + _TABLE + "| c | `str \\| None` |\n-->\n"
        "\n"
        + _TABLE
        + "| d | ok |\n```\n```\n| lone2 | `str \\| None` |\n"  # a fence ends the table
        "\n"
        + _TABLE
        + "| e | ok |\n<!--\nx\n-->\n| lone3 | `str \\| None` |\n"  # so does a comment
        "\n" + _TABLE + "| g | \\`not code \\| x\\` |\n",  # escaped backticks make no span
    )
    assert _run(mod, root, ["--strict"], monkeypatch) == 0
    assert ": code span carries a table-escaped pipe" not in capsys.readouterr().out
