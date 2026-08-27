"""Behaviour tests for `scripts/enforcement/check_trigger_routing.py`.

Every `/fabrik-*` command advertises `TRIGGER — EN: "..."` phrases. Nothing checked the router
agreed. Measured on the live corpus 2026-08-28: of 71 advertised EN phrases, **5 resolved to a
DIFFERENT command** — and each landed on a command whose own description disclaims the phrase
("review this UI" and "review the epic or ticket breakdown" both fell to `fabrik-review`, whose
SKIP clause names `/design-review` and `/fabrik-workflow-review` for exactly those).

The check grades ONLY mis-routes. A phrase routing NOWHERE is safe and is reported as a
denominator, never a finding — the router's documented failure mode is over-firing, and a check
that pressured someone to close 42 gaps with loose patterns would cause the damage it prevents.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_trigger_routing", REPO / "scripts" / "enforcement" / "check_trigger_routing.py"
)
assert _spec and _spec.loader
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


class _R:
    """Wires phrase -> target through the two-call shape the real router has."""

    def __init__(self, routes):
        self.routes = routes
        self._cur = None

    def first_regex_match(self, phrase):
        self._cur = self.routes.get(phrase, "__absent__")
        return None if self._cur == "__absent__" else "stem"

    def resolve_target(self, stem, roster, ptype, exists):  # noqa: ANN001, ARG002
        return self._cur


def _sources(tmp: Path, entries: dict[str, list[str]]) -> Path:
    d = tmp / "_sources"
    d.mkdir()
    for cmd, phrases in entries.items():
        quoted = ", ".join(f'"{p}"' for p in phrases)
        (d / f"{cmd}.md").write_text(
            f"---\ndescription: does a thing. TRIGGER — EN: {quoted}; TR: \"x\" — fires. "
            f"Stage: gate.\n---\nbody\n",
            encoding="utf-8",
        )
    return d


# ── fleet safety: warn_only means a non-zero exit reddens ~46 repos ─────────────────────────────


@pytest.mark.parametrize("argv", [["--bogus"], ["--sources"], ["-x"], ["stray"], ["--help"]])
def test_malformed_argv_never_exits_nonzero(argv):
    try:
        rc = chk.main(argv)
    except SystemExit as exc:  # argparse's exit is a BaseException — `except Exception` misses it
        raise AssertionError(f"argv={argv} raised SystemExit({exc.code})")
    assert rc == 0


def test_a_project_without_command_sources_is_silent(tmp_path, capsys):
    """`commands/_sources/` is hub-only; a synced project must see nothing."""
    assert chk.main(["--sources", str(tmp_path / "absent")]) == 0
    assert capsys.readouterr().out == ""


def test_a_file_where_the_sources_dir_should_be_is_silent(tmp_path):
    f = tmp_path / "notadir"
    f.write_text("x", encoding="utf-8")
    assert chk.main(["--sources", str(f)]) == 0


# ── extraction ──────────────────────────────────────────────────────────────────────────────────


def test_advertised_phrases_are_pulled_from_the_en_clause_only(tmp_path):
    d = _sources(tmp_path, {"fabrik-a": ["run the thing", "do the thing"]})
    got = chk.advertised(d)
    assert got == [("fabrik-a", "run the thing"), ("fabrik-a", "do the thing")]


def test_a_command_with_no_trigger_clause_contributes_nothing(tmp_path):
    d = tmp_path / "_sources"
    d.mkdir()
    (d / "fabrik-b.md").write_text("---\ndescription: no trigger here.\n---\n", encoding="utf-8")
    assert chk.advertised(d) == []


# ── the finding ─────────────────────────────────────────────────────────────────────────────────


def test_a_phrase_reaching_a_different_command_is_the_finding(tmp_path, capsys):
    d = _sources(tmp_path, {"fabrik-a": ["review this UI"]})
    router = _R({"review this UI": "fabrik-review"})
    mis, correct, nowhere, broken = chk.grade(d, router, {"fabrik-review"})
    assert mis == [("fabrik-a", "review this UI", "fabrik-review")]
    assert (correct, nowhere) == (0, 0)


def test_a_phrase_reaching_its_own_command_is_correct(tmp_path):
    d = _sources(tmp_path, {"fabrik-a": ["do a thing"]})
    mis, correct, nowhere, broken = chk.grade(d, _R({"do a thing": "fabrik-a"}), {"fabrik-a"})
    assert not mis and (correct, nowhere) == (1, 0)


def test_a_phrase_routing_nowhere_is_counted_but_never_a_finding(tmp_path):
    """The deliberate non-finding. 42 of 71 live phrases route nowhere; grading them would push
    someone to add loose stems, and over-firing is the router's actual failure mode."""
    d = _sources(tmp_path, {"fabrik-a": ["some unrouted phrase"]})
    mis, correct, nowhere, broken = chk.grade(d, _R({}), {"fabrik-a"})
    assert not mis and (correct, nowhere) == (0, 1)


def test_the_service_test_command_is_graded_against_a_type_it_actually_serves():
    """Its stem resolves DYNAMICALLY by project type. Grading it as a UI-bearing type reports a
    mis-route that does not exist — reproduced while writing this check."""
    assert chk._HEADLESS_GRADE["fabrik-service-test"] == "python-api"
    assert chk._DEFAULT_GRADE == "saas-skeleton"


# ── output discipline ───────────────────────────────────────────────────────────────────────────


def test_a_clean_corpus_states_its_denominator(tmp_path, capsys, monkeypatch):
    """`assert out == "" or "mis-routed" in out` was the first version of this — it passes on BOTH
    branches, so it asserted nothing. A success line must state how many phrases it examined."""
    monkeypatch.setattr(chk, "_load_router", lambda: _R({"x": "fabrik-a", "y": "fabrik-b"}))
    d = _sources(tmp_path, {"fabrik-a": ["x"], "fabrik-b": ["y"]})
    skills = tmp_path / "skills"
    for n in ("fabrik-a", "fabrik-b"):
        (skills / n).mkdir(parents=True)
    chk.main(["--sources", str(d), "--skills", str(skills)])
    out = capsys.readouterr().out
    assert "2 advertised phrase(s)" in out, out
    assert "0 mis-routed" in out, out
    assert chk.SCOPE_NOTE in out, "a clean run must still say what it cannot grade"


def test_output_fits_the_advisory_budget_and_is_ascii(tmp_path, capsys, monkeypatch):
    mis = [(f"fabrik-a-long-command-name-{i:02d}", "a" * 60, "fabrik-review") for i in range(30)]
    monkeypatch.setattr(chk, "grade", lambda *a, **k: (mis, 3, 40, []))
    monkeypatch.setattr(chk, "_load_router", lambda: object())
    d = _sources(tmp_path, {"fabrik-a": ["x"]})
    skills = tmp_path / "skills"
    (skills / "fabrik-a").mkdir(parents=True)
    chk.main(["--sources", str(d), "--skills", str(skills)])
    out = capsys.readouterr().out
    assert len(out) <= chk.ADVISORY_BUDGET, f"{len(out)} chars exceeds the advisory budget"
    out.encode("ascii")
    assert chk.REMEDY[-20:] in out, "the remedy must survive truncation"
    assert "more" in out, "a truncated list must say how many were dropped"


def test_a_broken_router_does_not_wedge_the_check(monkeypatch, tmp_path):
    """The router is a synced file another agent may be mid-edit on. An unimportable router means
    'cannot ask the question' — which must be silence, never a fleet-wide red."""
    monkeypatch.setattr(chk, "_load_router", lambda: None)
    assert chk.main(["--sources", str(_sources(tmp_path, {"fabrik-a": ["x"]}))]) == 0


def test_the_check_states_what_it_cannot_grade():
    assert chk.SCOPE_NOTE and "cannot" in chk.SCOPE_NOTE.lower()
    assert "nowhere" in chk.SCOPE_NOTE.lower()


def test_no_module_constant_is_dead():
    src = (REPO / "scripts" / "enforcement" / "check_trigger_routing.py").read_text(encoding="utf-8")
    for name in [n for n in dir(chk) if n.isupper() and not n.startswith("_")]:
        assert src.count(name) > 1, f"{name} is defined and never used"


# ── the bare-prose PROMISE is a routing claim, and a broken one is a finding ─────────────────────


def _promising(tmp: Path, cmd: str, phrases: list[str]) -> Path:
    d = tmp / "_sources"
    d.mkdir()
    quoted = ", ".join(f'"{p}"' for p in phrases)
    (d / f"{cmd}.md").write_text(
        f'---\ndescription: does a thing. TRIGGER — EN: {quoted}; TR: "x" — fires bare-prose, '
        f"no slash command needed. Stage: utility.\n---\nbody\n",
        encoding="utf-8",
    )
    return d


def test_a_command_promising_bare_prose_with_no_reaching_phrase_is_a_finding(tmp_path):
    """Checklist item 6's exact line: an unrouted TRIGGER is defensible, a PROMISE of bare-prose
    routing that no stem backs is not. /fabrik-rivals promised it and reached nothing on all 3."""
    d = _promising(tmp_path, "fabrik-rivals", ["who are our competitors"])
    _mis, _c, _n, broken = chk.grade(d, _R({}), {"fabrik-rivals"})
    assert broken == ["fabrik-rivals"], broken


def test_one_reaching_phrase_is_enough_to_keep_the_promise(tmp_path):
    """The promise is 'an operator can reach me by typing', not 'every phrase routes'. Demanding
    all of them would push loose patterns into a router whose failure mode is over-firing."""
    d = _promising(tmp_path, "fabrik-rivals", ["who are our competitors", "unrouted phrase"])
    _mis, _c, _n, broken = chk.grade(d, _R({"who are our competitors": "fabrik-rivals"}), set())
    assert broken == [], broken


def test_a_command_that_never_promised_bare_prose_is_not_graded_on_it(tmp_path):
    """41 of 71 phrases route nowhere by design. Only the PROMISE turns that into a defect."""
    d = _sources(tmp_path, {"fabrik-flows": ["map the journeys/flows"]})
    _mis, _c, _n, broken = chk.grade(d, _R({}), {"fabrik-flows"})
    assert broken == [], broken
