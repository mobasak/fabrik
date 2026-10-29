"""final_gate.py reads git's path lists from STDOUT only, NUL-split (W-5c688a41, fleet 01M4RVW43D).

`run_cmd` returns stdout and stderr merged, which is right for display and wrong for parsing: a git
warning or a `fatal:` line became a "filename" (the sqlfluff leg handed it to `sqlfluff lint`), and a
non `-z` `--name-only` read C-quotes a path holding a tab, a quote or a non-ASCII byte, so the gate
scoped `"t\\tab.py"` — a name no file has — and missed the real one.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import final_gate  # noqa: E402

# five spellings a real tree carries that git C-quotes without -z
ODD = ("t\tab.py", 'quo"te.py', "ünï.py", "sp ace.py", "back\\slash.py")


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    ).stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _git(tmp_path, "init", "-q", "-b", "master", str(repo))
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def test_every_change_set_reader_returns_the_real_names(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    for name in ODD:
        (repo / name).write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "--", *ODD)
    assert final_gate.get_staged_files() == set(ODD)
    assert set(ODD) <= final_gate.get_changed_files()
    assert set(ODD) <= final_gate.get_writable_files()
    _git(repo, "commit", "-q", "-m", "odd")
    for name in ODD:
        (repo / name).write_text("x = 2\n", encoding="utf-8")
    assert set(ODD) <= final_gate.get_changed_files()  # the unstaged read


def test_untracked_sources_are_named_as_they_are(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    (repo / ODD[0]).write_text("x = 1\n", encoding="utf-8")
    msg = final_gate._warn_untracked_sources(emit=False) or ""
    assert ODD[0] in msg and '"t\\tab.py"' not in msg, msg


def test_git_names_reads_stdout_only_and_none_on_failure(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    (repo / "a.sql").write_text("select 1;\n", encoding="utf-8")
    _git(repo, "add", "a.sql")
    assert final_gate._git_names(["ls-files", "--", "*.sql"]) == ["a.sql"]
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", not_a_repo)
    assert final_gate._git_names(["ls-files", "--", "*.sql"]) is None


def test_stderr_at_rc_zero_is_never_a_name_and_any_byte_name_round_trips(tmp_path, monkeypatch):
    """Review A-O4/A-O1: a git that warns on stderr and exits 0 — and a name that is not UTF-8."""
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "git").write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stderr.write('warning: something odd\\n')\n"
        "sys.stdout.buffer.write(b'a.sql\\0caf\\xe9.sql\\0')\n",
        encoding="utf-8",
    )
    (stub / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", tmp_path)
    names = final_gate._git_names(["ls-files", "--", "*.sql"])
    assert names is not None and names[0] == "a.sql" and len(names) == 2, names
    assert not any("warning" in n for n in names), names
    assert os.fsencode(names[1]) == b"caf\xe9.sql"  # surrogateescape: the real bytes, no crash


def test_the_unpublished_and_added_sets_read_odd_names_through_the_log(tmp_path, monkeypatch):
    """Review A-O5: the `git log -z` read in _unpublished_files and the -z name-status read in
    _added_files, reached through a clone whose origin/master is the published ref."""
    origin = _repo(tmp_path)
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    for name in ODD:
        (clone / name).write_text("x = 1\n", encoding="utf-8")
    _git(clone, "add", "--", *ODD)
    _git(clone, "commit", "-q", "-m", "odd, unpushed")
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", clone)
    monkeypatch.chdir(clone)
    assert set(ODD) <= final_gate._unpublished_files()
    assert set(ODD) <= final_gate._added_files()


def test_the_gate_prints_a_non_utf8_name_without_crashing(tmp_path):
    """Review round 2 (A-O4/A-S1): decoding was safe, the PRINT of the surrogate name was not."""
    repo = _repo(tmp_path)
    (repo / os.fsdecode(b"unt\xe9.py")).write_text("x = 1\n", encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "final_gate.py"), "--lean", "--check"],
        cwd=repo,
        env={**os.environ, "PYTHONIOENCODING": "utf-8:strict"},
        capture_output=True,
        timeout=600,
    )
    err = out.stderr.decode("utf-8", "replace")
    assert "UnicodeEncodeError" not in err and "Traceback" not in err, err[-2000:]


def test_a_stream_whose_reconfigure_fails_never_stops_the_gate(monkeypatch):
    """W-f42efcc2 review: a stream whose reconfigure lookup or call raises AttributeError or
    ValueError (as the pre-change `try` swallowed both) is skipped, so main() still reaches parse_args."""
    import io

    class _Inner(io.StringIO):
        def reconfigure(self, **kw):
            return self._absent.reconfigure(**kw)  # AttributeError from INSIDE the method

    class _Refuses(io.StringIO):
        def reconfigure(self, **kw):
            raise ValueError("refused")

    class _LookupRefuses(io.StringIO):
        @property
        def reconfigure(self):
            raise ValueError("refused at lookup")

    class _LookupMissing(io.StringIO):
        @property
        def reconfigure(self):
            raise AttributeError("missing at lookup")

    class _ReachedParseArgsError(Exception):
        pass

    def _stop():
        raise _ReachedParseArgsError

    monkeypatch.setattr(final_gate, "parse_args", _stop)
    for out, err in (
        (_Inner(), _Refuses()),
        (io.StringIO(), _Inner()),
        (_LookupRefuses(), _LookupMissing()),
    ):
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)
        try:
            final_gate.main()
        except _ReachedParseArgsError:
            continue
        raise AssertionError("main() returned before parse_args")


def test_a_git_failure_names_the_sqlfluff_leg_not_run(monkeypatch):
    """Review round 2 (A-O5): `or []` would turn a git failure into a green '(no .sql files)'."""
    real = final_gate._git_names
    monkeypatch.setattr(
        final_gate, "_git_names", lambda args, **kw: None if "*.sql" in args else real(args, **kw)
    )
    monkeypatch.setattr(final_gate, "run_cmd", lambda *a, **kw: (0, ""))
    rows = final_gate.run_static_checks(tier=2, changed_files={"a.sql"})
    sql = [r for r in rows if r[0].startswith("sqlfluff")]
    assert sql == [("sqlfluff-lint (NOT RUN — git ls-files failed)", True, "")], sql
