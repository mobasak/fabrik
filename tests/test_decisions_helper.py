"""Behaviour tests for `scripts/decisions.py` — the fleet decision-ledger query helper.

WHY (spec docs/superpowers/specs/2026-08-30-decision-ledger-v2-design.md): the operator's
directive — every agent records decisions with why/what/where/who/when and ALWAYS queries them
before answering "where is X / did we decide Y". The helper is the fleet-wide read path (one
command over /opt/*/docs/DECISIONS.md) and carries the design's mechanical integrity checks:
every `supersedes D-NNN` pointer must resolve to an existing row id (the dangling-pointer
failure the tooling literature names for hand-rolled records), and no id may appear on two
rows (the concurrent-mint race — two D-041s, 2026-08-30).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("decisions", REPO / "scripts" / "decisions.py")
assert _spec and _spec.loader
dec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dec)

LEDGER_A = (
    "# Decisions\n\n"
    "Append-at-top. One row per decision; rows are IMMUTABLE.\n\n"
    "| id | when | who | what (the decision) | why | where |\n"
    "|---|---|---|---|---|---|\n"
    "| D-002 | 2026-08-30 | operator+agent | supersedes D-001: retirement reversed | new evidence | abc123 |\n"
    "| D-001 | 2026-08-29 | agent | context7 retired from roster | 45 lifetime calls | 74ad8a06 |\n"
    "| D-000 | 2026-08-01 | operator | decision ledger adopted | struggle class | spec sha |\n"
)
LEDGER_DANGLING = (
    "# Decisions\n\n"
    "| id | when | who | what (the decision) | why | where |\n"
    "|---|---|---|---|---|---|\n"
    "| D-005 | 2026-08-30 | agent | supersedes D-004: flipped | measured | def456 |\n"
    "| D-000 | 2026-08-01 | operator | ledger adopted | seed | spec |\n"
)


def _repo(root: Path, name: str, ledger: str | None) -> Path:
    d = root / name / "docs"
    d.mkdir(parents=True, exist_ok=True)
    if ledger is not None:
        (d / "DECISIONS.md").write_text(ledger, encoding="utf-8")
    return root / name


def test_query_prints_the_matching_row_with_repo_and_fields(tmp_path, capsys):
    _repo(tmp_path, "alpha", LEDGER_A)
    _repo(tmp_path, "beta", LEDGER_A.replace("context7", "meilisearch"))
    rc = dec.main(["context7", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "alpha" in out and "D-001" in out and "74ad8a06" in out, out
    assert "45 lifetime calls" in out, out  # the WHY cell — the field the duty exists for
    assert "beta" not in out, out


def test_check_names_a_dangling_supersede_pointer_and_exits_1(tmp_path, capsys):
    _repo(tmp_path, "gamma", LEDGER_DANGLING)
    rc = dec.main(["--check", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "D-004" in out and "gamma" in out, out


def test_check_passes_when_every_pointer_resolves(tmp_path, capsys):
    _repo(tmp_path, "alpha", LEDGER_A)  # D-002 supersedes D-001, which exists
    rc = dec.main(["--check", "--root", str(tmp_path)])
    assert rc == 0, capsys.readouterr().out


def test_repos_without_a_ledger_are_silently_skipped(tmp_path, capsys):
    _repo(tmp_path, "alpha", LEDGER_A)
    _repo(tmp_path, "no-ledger", None)
    rc = dec.main(["retired", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no-ledger" not in out, out


def test_cli_runs_standalone(tmp_path):
    _repo(tmp_path, "alpha", LEDGER_A)
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "decisions.py"), "context7", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0 and "D-001" in r.stdout, (r.returncode, r.stdout, r.stderr)


def test_check_flags_a_duplicate_row_id_and_exits_1(tmp_path, capsys):
    """Two rows minted with the same D-NNN (concurrent sessions, stale max-id reads —
    live case: two D-041s, 2026-08-30) make every `supersedes D-NNN` ambiguous;
    --check must name the collision and fail."""
    _repo(tmp_path, "hub", (
        "# Decisions\n\n"
        "| id | when | who | what (the decision) | why | where |\n"
        "|---|---|---|---|---|---|\n"
        "| D-002 | 2026-08-30 | a | first | why | here |\n"
        "| D-002 | 2026-08-30 | b | second | why | there |\n"
        "| D-001 | 2026-08-30 | a | base | why | here |\n"
    ))
    rc = dec._check(tmp_path)
    out = capsys.readouterr().out
    assert rc == 1
    assert "DUPLICATE" in out and "D-002" in out


def test_check_resolves_a_lowercase_supersedes_target(tmp_path, capsys):
    """`supersedes d-001` (lowercase, captured case-preserved by the IGNORECASE regex)
    must resolve against the uppercase `| D-001 |` row — not report a false DANGLING."""
    _repo(tmp_path, "hub", (
        "| id | when | who | what (the decision) | why | where |\n"
        "|---|---|---|---|---|---|\n"
        "| D-002 | 2026-08-30 | a | supersedes d-001: flipped | why | here |\n"
        "| D-001 | 2026-08-30 | a | base | why | here |\n"
    ))
    assert dec._check(tmp_path) == 0, capsys.readouterr().out


def test_lowercase_row_ids_are_not_invisible(tmp_path, capsys):
    """A row keyed `| d-003 |` must be seen by the parser (normalized to D-003) —
    an invisible row can carry a duplicate/dangling defect no check can catch."""
    _repo(tmp_path, "hub", (
        "| id | when | who | what (the decision) | why | where |\n"
        "|---|---|---|---|---|---|\n"
        "| d-003 | 2026-08-30 | a | lowercase-minted | why | here |\n"
        "| D-003 | 2026-08-30 | b | uppercase twin | why | there |\n"
    ))
    rc = dec._check(tmp_path)
    out = capsys.readouterr().out
    assert rc == 1 and "DUPLICATE" in out and "D-003" in out


def test_query_output_preserves_unicode(tmp_path, capsys):
    """The ledger is saturated with `·`/`—`/`§`; the query tool must print them, not
    their backslash escapes (live defect: every real row printed `\\xb7` for `·`)."""
    _repo(tmp_path, "alpha", LEDGER_A.replace("context7", "em—dash § row"))
    rc = dec.main(["em—dash", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "·" in out and "em—dash § row" in out, out
    assert "\\xb7" not in out and "\\u2014" not in out, out


def test_piped_output_dies_silently_on_closed_pipe(tmp_path):
    """`decisions.py <term> | head -1` must not traceback — the default Python SIGPIPE
    handling raises BrokenPipeError when head exits early on a big result set."""
    rows = "\n".join(
        f"| D-{i:03d} | 2026-08-30 | a | filler row {i} padded {'x' * 120} | why | here |"
        for i in range(3000)
    )
    _repo(tmp_path, "big", (
        "| id | when | who | what (the decision) | why | where |\n|---|---|---|---|---|---|\n"
        + rows + "\n"
    ))
    r = subprocess.run(
        f"{sys.executable} {REPO / 'scripts' / 'decisions.py'} filler --root {tmp_path} | head -n 1",
        shell=True, capture_output=True, text=True, timeout=60,
    )
    assert "D-" in r.stdout
    assert "BrokenPipeError" not in r.stderr and "Traceback" not in r.stderr, r.stderr[-500:]


def test_say_exits_cleanly_on_broken_pipe_without_signal_guard(monkeypatch, capsys):
    """Library callers (import + main()) get no __main__ SIGPIPE guard — _say itself
    must turn a BrokenPipeError into a clean exit, not a traceback."""
    import builtins

    def _boom(*a, **k):
        raise BrokenPipeError

    monkeypatch.setattr(builtins, "print", _boom)
    try:
        dec._say("row")
    except SystemExit as e:
        assert e.code == 0
    else:
        raise AssertionError("BrokenPipeError escaped _say (or was swallowed silently)")


def test_say_survives_unicode_fallback_hitting_a_closed_pipe(monkeypatch):
    """The compound path: non-UTF-8 stdout makes every row take the UnicodeEncodeError
    fallback, whose own print() can hit the closed pipe — must still exit cleanly."""
    import builtins

    calls = {"n": 0}

    def _flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise UnicodeEncodeError("ascii", "·", 0, 1, "boom")
        raise BrokenPipeError

    monkeypatch.setattr(builtins, "print", _flaky)
    try:
        dec._say("row · with · dots")
    except SystemExit as e:
        assert e.code == 0
    else:
        raise AssertionError("compound Unicode→BrokenPipe path escaped _say")


def test_ledger_check_is_wired_into_pre_commit_and_fails_on_a_duplicate(tmp_path):
    """01M1KDHT (intel, 2026-09-03): `decisions.py --check` detected duplicate ids perfectly and
    NOTHING ran it — two collisions in one day were cleaned by hand. The hook runs on every commit
    touching docs/DECISIONS.md, scoped to THIS repo's ledger (`--root .`), and the check exits 1."""
    cfg = (REPO / ".pre-commit-config.yaml").read_text()
    assert "decisions-ledger-check" in cfg and "decisions.py --root . --check" in cfg
    assert "files: ^docs/DECISIONS\\.md$" in cfg
    repo = tmp_path / "x"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "DECISIONS.md").write_text(
        "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
        "| D-002 | d | w | a | b | c |\n| D-002 | d | w | a | b | c |\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "decisions.py"), "--root", str(repo), "--check"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1 and "DUPLICATE" in (r.stdout + r.stderr)
