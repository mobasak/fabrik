"""The Phase E review's routed findings that still held at HEAD (W-fe6e0ed3).

Each grader is keyed on the defect as the routing named it: a hub whose registry cannot be
imported read as ALL_TYPES parity; a `--dry-run` named every file it would NOT touch and none it
would; `scratch_sweep` stripped git's C-quoting without unescaping it, so a path git quotes
resolved wrong.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_an_unimportable_registry_in_the_hub_is_not_parity(tmp_path: Path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))
    cs = _load("check_structure_w_fe6", ROOT / "scripts" / "enforcement" / "check_structure.py")
    scaffold = tmp_path / "src" / "fabrik" / "scaffold.py"
    scaffold.parent.mkdir(parents=True)
    scaffold.write_text('SCAFFOLD_TYPES = frozenset({"python-api"})\n', encoding="utf-8")
    monkeypatch.setattr(cs, "_doc_registry", None)
    out = cs._scaffold_registry_drift(tmp_path)
    assert len(out) == 1 and "NOT checked" in out[0] and "_doc_registry" in out[0], out


def test_a_dry_run_names_every_file_it_would_write(tmp_path: Path) -> None:
    se = _load("sync_enforcement_w_fe6", ROOT / "scripts" / "sync_enforcement_to_projects.py")
    files = [
        se.SyncResult("COPY", tmp_path / "a", tmp_path / "copied.py", "new"),
        se.SyncResult("BACKUP", tmp_path / "b", tmp_path / "backed.py", "differs"),
        se.SyncResult("SKIP", tmp_path / "c", tmp_path / "same.py"),
        se.SyncResult(
            "DELETE", tmp_path / "d", tmp_path / "retired.py", "retired core script pruned"
        ),
    ]
    dry = "\n".join(se._file_lines(files, verbose=False, dry_run=True))
    assert all(n in dry for n in ("copied.py", "backed.py", "same.py", "retired.py")), dry
    # a real run stays as terse as before
    real = "\n".join(se._file_lines(files, verbose=False, dry_run=False))
    assert "copied.py" not in real and "retired.py" not in real and "same.py" in real, real


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_status_entries_are_the_real_paths_git_would_quote(tmp_path: Path) -> None:
    ss = _load("scratch_sweep_w_fe6", ROOT / "scripts" / "scratch_sweep.py")
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(
        repo,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "0",
    )
    (repo / "old.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", "old.txt")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "1")
    _git(repo, "mv", "old.txt", "new.txt")
    names = ["tab\tname.md", "ü-review.md", 'q"uote.md']
    for n in names:
        (repo / n).write_text("x", encoding="utf-8")
    rc, entries = ss._status_z(repo)
    assert rc == 0
    got = {p for _, p in entries}
    assert set(names) <= got, entries
    # a rename's source is consumed, never parsed as an entry of its own
    assert "new.txt" in got and "old.txt" not in got, entries
    assert len(entries) == len(names) + 1, entries
    for _, p in entries:
        assert (repo / p).is_file(), (p, entries)  # every entry resolves to the file on disk


def test_a_failed_registry_import_is_not_checked_never_a_name_error(
    tmp_path: Path, monkeypatch
) -> None:
    """The module-level import failing must leave `_doc_registry` BOUND (to None): an unbound name
    turned the NOT-checked line into a NameError crash of the whole structure check."""
    sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))
    monkeypatch.setitem(sys.modules, "_doc_registry", None)  # `import _doc_registry` now raises
    cs = _load(
        "check_structure_w_fe6_noreg", ROOT / "scripts" / "enforcement" / "check_structure.py"
    )
    assert cs._doc_registry is None
    scaffold = tmp_path / "src" / "fabrik" / "scaffold.py"
    scaffold.parent.mkdir(parents=True)
    scaffold.write_text('SCAFFOLD_TYPES = frozenset({"python-api"})\n', encoding="utf-8")
    out = cs._scaffold_registry_drift(tmp_path)
    assert len(out) == 1 and "NOT checked" in out[0], out


def test_an_unreadable_worktree_status_keeps_the_worktree(tmp_path: Path, monkeypatch) -> None:
    """A failed `git status` is not a clean tree: the verdict feeds a removal, so it keeps the work."""
    ss = _load("scratch_sweep_w_fe6_rc", ROOT / "scripts" / "scratch_sweep.py")
    monkeypatch.setattr(ss, "_status_z", lambda repo, *extra: (128, []))
    verdict, reason, _ = ss._worktree_chain(tmp_path, {}, tmp_path, "master", "b", set(), False, {})
    assert verdict == "wt-dirty" and "unreadable" in reason, (verdict, reason)
