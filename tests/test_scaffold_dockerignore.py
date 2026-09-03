"""Every Dockerfile-bearing scaffold type ships a `.dockerignore` at the build context root.

Mail 01M1M9CYEHA55DQP03081X09HS (infra, pass 61): the scaffolder wrote one by hand for 3 of the ~10
Dockerfile-bearing types and skipped 7, while every one of those Dockerfiles does `COPY . .`. The
VPS deploys by `git pull` into a LONG-LIVED working tree, so a gitignored `.env`, `node_modules/`
or `dist/` surviving a pull is baked into the image — "what git does not track never deploys" holds
for the repo and not for the build context.
"""

from __future__ import annotations

from pathlib import Path

from fabrik.scaffold import TEMPLATE_DIR, _ensure_dockerignore


def test_a_project_with_a_dockerfile_gets_the_ignore_file_at_the_context_root(tmp_path: Path):
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "Dockerfile").write_text("FROM python:3.13-slim\nCOPY . .\n")
    written = _ensure_dockerignore(tmp_path)
    # the CONTEXT root, not the Dockerfile's directory: compose builds with `context: .`
    assert written == tmp_path / ".dockerignore"
    body = written.read_text()
    assert ".env" in body, "the ignore file must exclude secrets — that is the point"
    assert not (tmp_path / "server" / ".dockerignore").exists()


def test_a_bespoke_ignore_file_is_never_overwritten(tmp_path: Path):
    """chrome-extension and mobile-app ship one that excludes the RN client and ships server/
    only; the generic template must never clobber it."""
    (tmp_path / "Dockerfile").write_text("FROM node:24-slim\nCOPY . .\n")
    (tmp_path / ".dockerignore").write_text("# bespoke\nclient/\n")
    assert _ensure_dockerignore(tmp_path) is None
    assert (tmp_path / ".dockerignore").read_text() == "# bespoke\nclient/\n"


def test_a_project_with_no_dockerfile_gets_nothing(tmp_path: Path):
    """static-site and other Dockerfile-less types must not gain a stray file."""
    (tmp_path / "README.md").write_text("# no docker here\n")
    assert _ensure_dockerignore(tmp_path) is None
    assert not (tmp_path / ".dockerignore").exists()


def test_it_never_raises_when_the_template_is_missing_or_the_dir_is_unwritable(tmp_path: Path):
    """A scaffold that otherwise succeeded must not fail on this."""
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    ro = tmp_path / "ro"
    ro.mkdir()
    (ro / "Dockerfile").write_text("FROM scratch\n")
    ro.chmod(0o555)
    try:
        assert _ensure_dockerignore(ro) is None  # unwritable → None, no raise
    finally:
        ro.chmod(0o755)


def test_the_template_the_sweep_copies_actually_exists():
    """The helper degrades to None when the template is absent, so its absence would be silent."""
    assert (TEMPLATE_DIR / "docker" / "dockerignore.template").is_file()
