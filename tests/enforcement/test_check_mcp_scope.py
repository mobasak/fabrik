"""Graders for scripts/enforcement/check_mcp_scope.py (operator mail 01M4AR32MY, 2026-10-07):
an emitted `.mcp.json` must be a SUBSET of its repo's ruling, the hub included."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HUB = Path(__file__).resolve().parents[2]
SRC = HUB / "scripts" / "enforcement" / "check_mcp_scope.py"

DEFS = {
    name: {"command": f"/usr/bin/{name}", "args": []}
    for name in (
        "session-recall",
        "exa",
        "brave-search",
        "firecrawl",
        "postgres-pro",
        "serena",
        "fabrik-scrape",
        "playwright",
        "chrome-devtools",
        "shadcn",
        "magicui",
        "maestro",
        "mobile-mcp",
        "pubchem",
        "media-engine",
        "grafana",
        "rea",
    )
}


@pytest.fixture(autouse=True)
def _hermetic_git(tmp_path, monkeypatch):
    """The ownership predicate asks git: the box's global or system excludes must not decide these tests. An empty
    `GIT_CONFIG_GLOBAL` still leaves git's DEFAULT excludes file (`$XDG_CONFIG_HOME/git/ignore`, else
    `$HOME/.config/git/ignore`), so `XDG_CONFIG_HOME` points at an empty dir too (W-f7772267 (f))."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    (tmp_path / "empty-xdg").mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-xdg"))


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("check_mcp_scope", SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def repo(root: Path, name: str, rtype: str | None, servers: list[str]) -> Path:
    d = root / name
    (d / ".git").mkdir(parents=True)
    if rtype:
        (d / "project.yaml").write_text(f"name: {name}\ntype: {rtype}\n")
    (d / ".mcp.json").write_text(json.dumps({"mcpServers": {s: DEFS[s] for s in servers}}))
    return d


def test_the_hub_carrying_a_heavy_server_fails_and_names_the_emitter(check, tmp_path):
    repo(tmp_path, "fabrik", None, ["session-recall", "exa", "maestro"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [f["repo"] for f in rep["failures"]] == ["fabrik"]
    assert rep["failures"][0]["extra"] == ["maestro"]
    assert "emit_mcp_project_config.py --repo" in rep["failures"][0]["fix"]


def test_a_subset_passes_and_an_omitted_allowed_server_is_legal(check, tmp_path):
    # no postgres-pro: legal
    repo(tmp_path, "some-api", "python-api", ["session-recall", "exa", "fabrik-scrape", "rea"])
    repo(tmp_path, "app", "mobile-app", ["session-recall", "maestro", "mobile-mcp"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"] == [] and rep["checked"] == 2


def test_a_headless_repo_carrying_a_browser_server_fails(check, tmp_path):
    repo(tmp_path, "some-api", "python-api", ["session-recall", "playwright"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"][0]["extra"] == ["playwright"]


def test_an_unknown_type_and_the_own_agent_hub_class_repo_only_warn(check, tmp_path):
    repo(
        tmp_path, "mystery", "sass-skeleton", ["session-recall", "maestro"]
    )  # a type the roster lacks
    # an UNTYPED repo the emitter owns (its .gitignore keeps .mcp.json out of git) is ruled since D-1246 (the
    # universal set): a server outside it FAILS; one the emitter would refuse to write only warns, since
    # re-emitting cannot clear it
    owned = tmp_path / "untyped"
    owned.mkdir()
    subprocess.run(["git", "init", "-q", str(owned)], check=True)
    (owned / ".gitignore").write_text(".mcp.json\n")
    (owned / ".mcp.json").write_text(
        json.dumps({"mcpServers": {s: DEFS[s] for s in ("rea", "maestro")}})
    )
    vendor = repo(
        tmp_path, "vendor-clone", None, ["session-recall", "maestro"]
    )  # no gitignore line
    (vendor / ".git").rmdir()
    subprocess.run(["git", "init", "-q", str(vendor)], check=True)
    # a repo git cannot answer for (here a bare `.git` dir) FAILS: an unknown answer never demotes to a warning
    repo(tmp_path, "unanswerable", None, ["session-recall", "maestro"])
    # an UNTYPED directory that is no git repo is not graded, as the emitter never sweeps it
    plain = repo(tmp_path, "plain-dir", None, ["session-recall", "maestro"])
    (plain / ".git").rmdir()
    # …but a TYPED one is a ruled project wherever it sits: graded (the liveness canary's fixture shape)
    typed = repo(tmp_path, "typed-no-git", "python-api", ["session-recall", "maestro"])
    (typed / ".git").rmdir()
    # fabrik-lib keeps the FULL roster, maestro included (operator ruling 2026-10-07) — no warning
    lib = repo(tmp_path, "fabrik-lib", None, ["session-recall", "maestro", "playwright"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [(f["repo"], f["extra"]) for f in rep["failures"]] == [
        ("typed-no-git", ["maestro"]),
        ("unanswerable", ["maestro"]),
        ("untyped", ["maestro"]),
    ]
    assert sorted(w["repo"] for w in rep["warnings"]) == ["mystery", "vendor-clone"]
    assert (
        "not ignored by git"
        in next(w for w in rep["warnings"] if w["repo"] == "vendor-clone")["reason"]
    )
    (owned / ".mcp.json").unlink()
    (vendor / ".mcp.json").unlink()
    (tmp_path / "unanswerable" / ".mcp.json").unlink()
    (typed / ".mcp.json").unlink()
    # a server outside the roster in an own-agent repo warns (its agent writes the file), never fails
    (lib / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "session-recall": DEFS["session-recall"],
                    "github": {"command": "/usr/bin/github"},
                }
            }
        )
    )
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"] == []
    lib_warns = [w for w in rep["warnings"] if w["repo"] == "fabrik-lib"]
    assert [w["extra"] for w in lib_warns] == [["github"]], lib_warns


def test_cli_exit_codes(tmp_path):
    repo(tmp_path, "fabrik", None, ["session-recall", "chrome-devtools"])
    r = subprocess.run(
        [sys.executable, str(SRC), "--root", str(tmp_path), "--hub", str(HUB)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1 and "FAIL fabrik" in r.stdout and "chrome-devtools" in r.stdout
    r = subprocess.run(
        [sys.executable, str(SRC), "--root", str(tmp_path / "nowhere"), "--hub", str(HUB)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "SKIP" in r.stdout


def test_projects_skip_without_the_hub_marker(tmp_path):
    fake_hub = tmp_path / "proj"
    fake_hub.mkdir()
    r = subprocess.run(
        [sys.executable, str(SRC), "--root", str(tmp_path), "--hub", str(fake_hub)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "hub-only" in r.stdout


def test_the_hub_without_a_git_dir_is_still_graded(check, tmp_path):
    """Hub-class names are ruled by name, never by type: a hub dir with no `.git` (and no project.yaml) carrying a
    heavy server still FAILS — the untyped-non-git skip never reaches it."""
    hub = repo(tmp_path, "fabrik", None, ["session-recall", "maestro"])
    (hub / ".git").rmdir()
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [(f["repo"], f["extra"]) for f in rep["failures"]] == [("fabrik", ["maestro"])]


def test_an_unreadable_project_yaml_warns_never_crashes(check, tmp_path):
    """A project.yaml the gate cannot read (mode 000) is an unknown type — a warning — never a traceback that
    takes the whole gate down; with or without a `.git`."""
    for name in ("unreadable-repo", "unreadable-dir"):
        d = repo(tmp_path, name, "python-api", ["session-recall", "maestro"])
        if name == "unreadable-dir":
            (d / ".git").rmdir()
        (d / "project.yaml").chmod(0)
    try:
        rep = check.audit(tmp_path, HUB, DEFS)
    finally:
        for name in ("unreadable-repo", "unreadable-dir"):
            (tmp_path / name / "project.yaml").chmod(0o644)
    assert rep["failures"] == []
    assert sorted(w["repo"] for w in rep["warnings"]) == ["unreadable-dir", "unreadable-repo"]


def test_image_generation_is_graded_like_any_repo_of_its_type(check, tmp_path):
    """D-1246 emptied CONDEMNED: image-generation now carries an emitted .mcp.json, graded as python-api."""
    repo(tmp_path, "image-generation", "python-api", ["session-recall", "maestro"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["checked"] == 1
    assert [(f["repo"], f["extra"]) for f in rep["failures"]] == [("image-generation", ["maestro"])]


def test_a_credential_abort_in_the_emitter_is_a_structured_fail(
    tmp_path, monkeypatch, capsys, check
):
    """A-S2 (review 2026-10-07): when the emitter's chain aborts (D-641), the gate prints one
    `check_mcp_scope: FAIL` line and exits 1 — never a bare traceback."""
    repo(tmp_path, "some-api", "python-api", ["session-recall"])

    def boom(root, hub, defs=None):
        raise SystemExit("emit_mcp: credential(s) unresolved — exa.env.EXA_API_KEY")

    monkeypatch.setattr(check, "audit", boom)
    rc = check.main(["--root", str(tmp_path), "--hub", str(HUB)])
    out = capsys.readouterr().out
    assert rc == 1 and "check_mcp_scope: FAIL" in out and "exa.env.EXA_API_KEY" in out


def _tracked(d: Path) -> None:
    """Turn a fixture dir into a real git repo whose `.mcp.json` is TRACKED despite its `.gitignore` rule."""
    (d / ".git").rmdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    (d / ".gitignore").write_text(".mcp.json\n")
    for args in (["add", "-f", ".gitignore", ".mcp.json"], ["commit", "-q", "-m", "t"]):
        subprocess.run(
            ["git", "-C", str(d), "-c", "user.email=t@t", "-c", "user.name=t", *args], check=True
        )


@pytest.mark.parametrize(
    "name, rtype, servers, extra",
    [
        ("tracked-api", "python-api", ["session-recall"], []),
        ("tracked-api", "python-api", ["session-recall", "maestro"], ["maestro"]),
        ("fabrik", None, ["session-recall", "exa", "maestro"], ["maestro"]),
    ],
)
def test_a_typed_repo_whose_file_git_tracks_is_a_warning(
    check, tmp_path, name, rtype, servers, extra
):
    """W-c0d9cea5: the emitter never writes a TYPED or hub repo's `.mcp.json` that git does not ignore, so re-emitting
    cannot clear it: a warning, whose reason no longer says "untyped" and says a tracked copy may still hold
    credentials. Such a repo was always graded before git was asked, so a server outside its ruling is STILL a
    failure (the review's fail-open: the hub's own over-scoped file must never demote to a warning)."""
    _tracked(repo(tmp_path, name, rtype, servers))
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [(f["repo"], f["extra"]) for f in rep["failures"]] == ([(name, extra)] if extra else [])
    # the emitter skips this repo, so a failure's fix must name the untrack step, never a bare re-emit (review pass 2)
    assert all("git rm --cached .mcp.json" in f["fix"] for f in rep["failures"]), rep["failures"]
    (w,) = rep["warnings"]
    assert w["repo"] == name
    assert "untyped" not in w["reason"] and "may still hold credentials" in w["reason"], w["reason"]
    assert "git rm --cached .mcp.json" in w["fix"], w["fix"]


def test_a_symlinked_file_with_an_extra_server_names_the_plain_file_step(check, tmp_path):
    """W-c0d9cea5 review pass 2: the emitter never writes through a symlinked `.mcp.json`, so the failure for a server
    outside the ruling must say to make it a plain file first, never a bare re-emit."""
    d = repo(tmp_path, "linked-api", "python-api", [])
    (d / ".mcp.json").unlink()
    (d / "real.json").write_text(
        json.dumps({"mcpServers": {s: DEFS[s] for s in ("session-recall", "maestro")}})
    )
    (d / ".mcp.json").symlink_to("real.json")
    rep = check.audit(tmp_path, HUB, DEFS)
    (f,) = rep["failures"]
    assert f["repo"] == "linked-api" and f["extra"] == ["maestro"]
    assert f["fix"].startswith("make `.mcp.json` a plain file, then "), f["fix"]


def _not_ignored(d: Path) -> Path:
    """Turn a fixture dir into a real git repo with no rule for `.mcp.json`: the emitter does not own the file."""
    (d / ".git").rmdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    return d


def test_a_not_ignored_repo_of_unknown_type_is_one_warning_and_ok_counts_repos(
    check, tmp_path, capsys
):
    """W-f7772267 (h): a repo whose `.mcp.json` git does not ignore AND whose type the roster lacks is ONE warning
    naming both causes, and the OK line counts warned REPOS — fabrik-lib's not-ignored row plus its unruled-server
    row are still one repo."""
    _not_ignored(repo(tmp_path, "mystery", "sass-skeleton", ["session-recall", "maestro"]))
    lib = _not_ignored(repo(tmp_path, "fabrik-lib", None, ["session-recall"]))
    (lib / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"github": {"command": "/usr/bin/g"}}})
    )
    _not_ignored(repo(tmp_path, "vendor-clone", None, ["session-recall"]))
    rep = check.audit(tmp_path, HUB, DEFS)
    (w,) = [w for w in rep["warnings"] if w["repo"] == "mystery"]
    assert "not ignored by git" in w["reason"] and "no ruling" in w["reason"], w["reason"]
    # every readable file is counted once, the not-ignored untyped one included (review pass 1)
    assert rep["checked"] == 3, rep
    assert check.main(["--root", str(tmp_path), "--hub", str(HUB)]) == 0
    assert (
        "OK — 3 .mcp.json file(s)" in (out := capsys.readouterr().out)
        and "(3 repo(s) warned)" in out
    )


def test_an_unreadable_file_the_emitter_does_not_own_only_warns(check, tmp_path, capsys):
    """W-f7772267 (i): an untyped repo's `.mcp.json` that git does not ignore is never the hub's to fix, so an
    unreadable one warns like a readable one; a typed repo's stays a failure, as it was graded before git was asked."""
    for name, rtype in (("vendor-clone", None), ("typed-api", "python-api")):
        d = _not_ignored(repo(tmp_path, name, rtype, []))
        (d / ".mcp.json").write_text("{not json")
    # a readable file in these repos could only warn — no ruling, an own-agent hub-class file — so an unreadable one
    # warns too, owned or not (review pass 1); the same file with a ruling the hub enforces fails
    for name, rtype, ignored in (
        ("mystery", "sass-skeleton", False),
        ("mystery-owned", "sass-skeleton", True),
        ("fabrik-lib", None, False),
        ("typed-owned", "python-api", True),
    ):
        d = _not_ignored(repo(tmp_path, name, rtype, []))
        if ignored:
            (d / ".gitignore").write_text(".mcp.json\n")
        (d / ".mcp.json").write_text("{not json")
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [(f["repo"], f["reason"]) for f in rep["failures"]] == [
        ("typed-api", "unreadable .mcp.json"),
        ("typed-owned", "unreadable .mcp.json"),
    ]
    vendor = next(w for w in rep["warnings"] if w["repo"] == "vendor-clone")
    assert "not ignored by git" in vendor["reason"] and "unreadable" in vendor["reason"], vendor
    reasons = {w["repo"]: w["reason"] for w in rep["warnings"]}
    assert sorted(reasons) == [
        "fabrik-lib",
        "mystery",
        "mystery-owned",
        "typed-api",
        "vendor-clone",
    ]
    for name in ("mystery", "mystery-owned", "fabrik-lib"):
        assert "unreadable .mcp.json" in reasons[name], reasons[name]
    assert "no ruling" in reasons["mystery"] and "not ignored by git" in reasons["mystery"]
    assert rep["checked"] == 0, rep  # an unreadable file is never counted as checked
    # a row with no servers to name prints no empty `carries` clause (review pass 1)
    assert check.main(["--root", str(tmp_path), "--hub", str(HUB)]) == 1
    out = capsys.readouterr().out
    assert "WARN vendor-clone:" in out and "carries" not in out, out


def test_a_symlinked_not_ignored_file_names_both_steps(check, tmp_path):
    """W-f7772267 (j): the emitter refuses both a not-ignored and a symlinked `.mcp.json`, so the warning's fix names
    the ignore step AND the plain-file step before the re-emit."""
    d = _not_ignored(repo(tmp_path, "linked", None, []))
    (d / ".mcp.json").unlink()
    (d / "real.json").write_text(
        json.dumps({"mcpServers": {"session-recall": DEFS["session-recall"]}})
    )
    (d / ".mcp.json").symlink_to("real.json")
    (w,) = check.audit(tmp_path, HUB, DEFS)["warnings"]
    assert "git rm --cached .mcp.json" in w["fix"], w["fix"]
    assert "then make `.mcp.json` a plain file, then python3 " in w["fix"], w["fix"]


def test_the_hermetic_fixture_blinds_git_to_the_users_global_ignore(check, tmp_path, monkeypatch):
    """W-f7772267 (f): with `GIT_CONFIG_GLOBAL` emptied git still reads its DEFAULT excludes file,
    `$XDG_CONFIG_HOME/git/ignore`, else `$HOME/.config/git/ignore`. A box whose global ignore lists `.mcp.json` would
    make a repo with no rule read as ignored, and decide these tests. The fixture points `XDG_CONFIG_HOME` at an empty
    dir, so a HOME carrying that file changes nothing."""
    # the fixture's own state, so a runner that exports XDG_CONFIG_HOME cannot hide its loss (review pass 1, F1)
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", ""))
    assert xdg.is_relative_to(tmp_path) and xdg.is_dir() and not any(xdg.iterdir()), xdg
    home = tmp_path / "home"
    (home / ".config" / "git").mkdir(parents=True)
    (home / ".config" / "git" / "ignore").write_text(".mcp.json\n")
    monkeypatch.setenv("HOME", str(home))
    d = repo(tmp_path, "vendor-clone", None, ["session-recall"])
    (d / ".git").rmdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [w["repo"] for w in rep["warnings"]] == ["vendor-clone"], rep


def test_an_unreadable_file_failure_names_its_fix(check, tmp_path, capsys):
    """W-f7772267 (k): an unreadable `.mcp.json` the hub enforces fails with the steps that clear it — the emitter
    reads the old file before it writes, so a mode-000 one fails the re-emit and goes first — and the FAIL line
    prints them."""
    d = repo(tmp_path, "typed-api", "python-api", [])
    (d / ".mcp.json").write_text("{not json")
    (f,) = check.audit(tmp_path, HUB, DEFS)["failures"]
    assert f["fix"].startswith("delete the unreadable `.mcp.json`, then python3 "), f
    assert check.main(["--root", str(tmp_path), "--hub", str(HUB)]) == 1
    assert "FAIL typed-api: unreadable .mcp.json — delete the unreadable" in capsys.readouterr().out


@pytest.mark.parametrize(
    "shape, cause, step",
    [
        ("unknown", "the roster rules no `type: sass-skeleton`", "set project.yaml's `type:`"),
        ("unparsed", "a `type:` line the emitter cannot parse", "set project.yaml's `type:`"),
        (
            "mode-000",
            "unreadable project.yaml (Permission denied)",
            "make project.yaml a readable file",
        ),
        (
            "locked-dir",
            "unreadable project.yaml (Permission denied)",
            "make project.yaml a readable file",
        ),
    ],
)
def test_a_no_ruling_warning_names_its_cause_and_a_fix_that_clears_it(
    check, tmp_path, shape, cause, step
):
    """W-f7772267 (k): the emitter SKIPs a repo with no ruling, so a bare re-emit clears nothing — the fix names the
    project.yaml step first — and an unreadable project.yaml is not "a type the roster does not know". A project.yaml
    linking into a mode-000 directory is the same unreadable file, never an uncaught PermissionError (Python 3.12's
    `Path.exists()` raises on EACCES)."""
    d = repo(tmp_path, "mystery", "python-api", ["session-recall", "maestro"])
    py = d / "project.yaml"
    locked = tmp_path / "locked"
    if shape == "unknown":
        py.write_text("type: sass-skeleton\n")
    elif shape == "unparsed":
        py.write_text('type: "python api"\n')
    elif shape == "mode-000":
        py.chmod(0)
    else:
        locked.mkdir()
        py.rename(locked / "project.yaml")
        py.symlink_to(locked / "project.yaml")
        locked.chmod(0)
    try:
        if (
            shape == "mode-000"
            and os.access(py, os.R_OK)
            or shape == "locked-dir"
            and os.access(locked, os.R_OK)
        ):
            pytest.skip("running as a user who can read a mode-000 path")
        rep = check.audit(tmp_path, HUB, DEFS)
    finally:
        if shape == "mode-000":
            py.chmod(0o644)
        if shape == "locked-dir":
            locked.chmod(0o755)
    assert rep["failures"] == [], rep
    # the locked dir sits under the root too, so it is its own unsearchable-dir warning
    assert sorted(w["repo"] for w in rep["warnings"]) == sorted(
        ["mystery"] + (["locked"] if shape == "locked-dir" else [])
    )
    (w,) = [w for w in rep["warnings"] if w["repo"] == "mystery"]
    assert cause in w["reason"] and "roster does not know" not in w["reason"], w["reason"]
    assert w["fix"].startswith(step) and ", then python3 " in w["fix"], w["fix"]


def test_a_not_ignored_repo_with_no_ruling_names_every_step_in_order(check, tmp_path):
    """W-f7772267 (k), review pass 1: the emitter skips a not-ignored file AND a repo with no ruling, so the one warning
    names the ignore step, then the project.yaml step, then the single re-emit that ends it."""
    d = _not_ignored(repo(tmp_path, "mystery", "sass-skeleton", ["maestro"]))
    (w,) = check.audit(tmp_path, HUB, DEFS)["warnings"]
    steps = w["fix"].split(", then ")
    assert (
        steps[0].startswith("make .gitignore ignore `.mcp.json`") and "git rm --cached" in steps[0]
    ), steps
    assert steps[1].startswith("set project.yaml's `type:`"), steps
    assert steps[-1] == f"python3 {HUB / check.EMITTER_REL} --repo {d}" and len(steps) == 3, steps


def test_entries_this_user_cannot_search_never_crash_and_a_locked_link_is_unreadable(
    check, tmp_path, capsys
):
    """W-f7772267 (k), review pass 1: Python 3.12's `is_dir()`/`is_file()` RAISE on EACCES. A root entry linking into a
    dir this user cannot search, and a dir it cannot search, are each one warning naming the dir (any `.mcp.json`
    there is ungraded), never a traceback and never a silent skip; a searchable repo whose `.mcp.json` links into such
    a dir holds a PRESENT, unreadable file, graded like a mode-000 one — a failure whose fix deletes the link, never a
    plain-file step before the delete."""
    locked = tmp_path / "zz-locked"
    locked.mkdir()
    (tmp_path / "linked-root").symlink_to(locked / "repo")
    (locked / "real.json").write_text(json.dumps({"mcpServers": {"maestro": DEFS["maestro"]}}))
    shut = repo(tmp_path, "shut-api", "python-api", ["maestro"])
    d = repo(tmp_path, "typed-api", "python-api", [])
    (d / ".mcp.json").unlink()
    (d / ".mcp.json").symlink_to(locked / "real.json")
    shut.chmod(0)
    locked.chmod(0)
    try:
        if os.access(locked, os.X_OK):
            pytest.skip("running as a user who can search a mode-000 directory")
        rep = check.audit(tmp_path, HUB, DEFS)
        rc = check.main(["--root", str(tmp_path), "--hub", str(HUB)])
    finally:
        locked.chmod(0o755)
        shut.chmod(0o755)
    assert [(f["repo"], f["reason"]) for f in rep["failures"]] == [
        ("typed-api", "unreadable .mcp.json")
    ], rep
    assert rep["failures"][0]["fix"] == (
        f"delete the unreadable `.mcp.json`, then python3 {HUB / check.EMITTER_REL} --repo {d}"
    )
    assert [(w["repo"], w["fix"]) for w in rep["warnings"]] == [
        (name, f"make {tmp_path / name} searchable by this user, or move it out of {tmp_path}")
        for name in ("linked-root", "shut-api", "zz-locked")
    ], rep
    assert rep["checked"] == 0, rep
    out = capsys.readouterr().out
    assert rc == 1 and "FAIL typed-api: unreadable .mcp.json — delete the unreadable" in out, out
    assert "WARN shut-api: this user cannot search it" in out, out


def test_a_deeply_nested_file_is_unreadable_never_a_traceback(check, tmp_path):
    """W-f7772267 (k), review pass 1: `json.loads` raises RecursionError, which is no ValueError, on a deeply nested
    `.mcp.json`; the gate reads it as unreadable, as the emitter does its roster and catalog."""
    d = repo(tmp_path, "deep-api", "python-api", [])
    (d / ".mcp.json").write_text("[" * 100_000)
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [(f["repo"], f["reason"]) for f in rep["failures"]] == [
        ("deep-api", "unreadable .mcp.json")
    ], rep


def test_a_not_ignored_unreadable_file_names_the_same_steps_on_both_rows(check, tmp_path):
    """W-f7772267 (k), review pass 1: a typed repo whose unreadable `.mcp.json` git does not ignore gets a failure and
    a not-ignored warning; both name the ignore step, the delete, then the one re-emit, so neither row's fix stops
    at a re-emit that cannot read the file."""
    d = _not_ignored(repo(tmp_path, "typed-api", "python-api", []))
    (d / ".mcp.json").write_text("{not json")
    rep = check.audit(tmp_path, HUB, DEFS)
    (f,) = rep["failures"]
    (w,) = rep["warnings"]
    steps = f["fix"].split(", then ")
    assert (
        steps[0].startswith("make .gitignore ignore")
        and steps[1] == "delete the unreadable `.mcp.json`"
    ), steps
    assert steps[-1] == f"python3 {HUB / check.EMITTER_REL} --repo {d}" and len(steps) == 3, steps
    assert w["fix"] == f["fix"], (w, f)
