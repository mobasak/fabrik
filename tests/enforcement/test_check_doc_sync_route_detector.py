# AFTER-EDIT: scripts/enforcement/check_doc_sync.py
"""The route detector must grade the CHANGE, not the file's contents.

Mail 01M1H61P4CKFPX47CZGYKNM1EP: `_has_route_change` regex-scanned whole file TEXT, so
`src/fabrik/scaffold.py` — which embeds route templates for every scaffold type — raised
"API route changed but docs/QUICKSTART.md not updated" on a one-line `SCRIPT_FILES` append.
QUICKSTART documents the `fabrik` CLI, which had not changed, and the warning was then
misattributed to sibling commits because the receipt reasoned by PATH and the detector by
CONTENT. A warning whose only correct response is to ignore it teaches scroll-past.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/opt/fabrik/scripts/enforcement")
import check_doc_sync as ds  # noqa: E402

ROUTE_SRC = '@app.get("/health")\ndef health():\n    return {"ok": True}\n'


def _repo(tmp_path: Path) -> Path:
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def _commit(repo: Path, msg: str = "c") -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True, capture_output=True)


def test_touching_a_file_that_merely_contains_routes_is_not_a_route_change(tmp_path, monkeypatch):
    """The reported shape: a scaffolder holding route TEMPLATES, edited elsewhere."""
    repo = _repo(tmp_path)
    f = repo / "scaffold.py"
    f.write_text(f'TEMPLATE = """\n{ROUTE_SRC}"""\nSCRIPT_FILES = ["a.py"]\n')
    _commit(repo)
    f.write_text(f'TEMPLATE = """\n{ROUTE_SRC}"""\nSCRIPT_FILES = ["a.py", "b.py"]\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    monkeypatch.chdir(repo)
    assert ds._has_route_change(["scaffold.py"], ["diff", "--cached"]) is False
    # and the old whole-file behaviour, which is what fired the false positive
    assert ds._has_route_change(["scaffold.py"]) is True


def test_actually_adding_a_route_is_still_detected(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    f = repo / "api.py"
    f.write_text("x = 1\n")
    _commit(repo)
    f.write_text("x = 1\n" + ROUTE_SRC)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    monkeypatch.chdir(repo)
    assert ds._has_route_change(["api.py"], ["diff", "--cached"]) is True


def test_removing_a_route_is_still_detected(tmp_path, monkeypatch):
    """A deleted endpoint changes the documented API just as much as an added one."""
    repo = _repo(tmp_path)
    f = repo / "api.py"
    f.write_text("x = 1\n" + ROUTE_SRC)
    _commit(repo)
    f.write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    monkeypatch.chdir(repo)
    assert ds._has_route_change(["api.py"], ["diff", "--cached"]) is True


def test_a_path_named_like_a_route_in_the_diff_header_does_not_trip_it(tmp_path, monkeypatch):
    """The `+++ b/<path>` headers must not be fed to the route regexes."""
    repo = _repo(tmp_path)
    d = repo / "app"
    d.mkdir()
    f = d / "get.py"
    f.write_text("x = 1\n")
    _commit(repo)
    f.write_text("x = 2\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    monkeypatch.chdir(repo)
    assert ds._has_route_change(["app/get.py"], ["diff", "--cached"]) is False


def test_no_diff_scope_keeps_the_old_broader_behaviour(tmp_path, monkeypatch):
    """A caller with no diff (a test, a future programmatic use) must not silently detect
    nothing — it falls back to reading file text.

    Uses a repo-relative path on purpose: `_skip` matches SKIP_PATTERNS as substrings anywhere
    in the path, and pytest's own tmp dir is named `test_*`, so an absolute tmp path is skipped
    before the detector ever reads it — which would make this assertion pass for the wrong
    reason if it were inverted."""
    repo = _repo(tmp_path)
    f = repo / "api.py"
    f.write_text(ROUTE_SRC)
    monkeypatch.chdir(repo)
    assert ds._skip("api.py") is False, "guard: the fixture path must not be skip-filtered"
    assert ds._has_route_change(["api.py"]) is True
