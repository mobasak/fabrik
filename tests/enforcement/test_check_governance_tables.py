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
