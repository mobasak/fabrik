"""The github-wire flow must make a scaffolded project deploy-ready.

Regression for the "not fully ready" bug: the old `--github-create` only ran
`gh repo create` (an orphan repo) and left the spec at source.type=template, so
`fabrik apply` couldn't ship the build context. The wire flow must ALSO link the
remote, push, and regenerate the spec so it resolves to source.type=git.
"""

from __future__ import annotations

import subprocess

from fabrik import cli


def test_wire_flow_creates_links_pushes_and_regenerates_spec(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **_kw):
        calls.append(list(cmd))

        class R:
            returncode = 0
            stdout = "main" if "symbolic-ref" in cmd else ""
            stderr = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    regen: list[tuple] = []
    monkeypatch.setattr(
        cli,
        "generate_and_save_spec",
        lambda *a, **k: regen.append((a, k)) or (tmp_path / "spec.yaml"),
    )
    monkeypatch.setattr(cli, "_detect_secrets", lambda _p: ([], {}))

    cli._create_and_wire_github_repo("transdoc", tmp_path, "saas-skeleton", db=True)

    joined = [" ".join(c) for c in calls]
    assert any("repo create mobasak/transdoc" in j for j in joined), "repo not created"
    assert any("remote add origin" in j for j in joined), "remote not linked"
    assert any("push -u origin main" in j for j in joined), "initial commit not pushed"
    # The load-bearing assertion: the spec is regenerated so detect_git_source can
    # flip source.type template -> git. Without this, the project isn't deployable.
    assert regen, "spec not regenerated — source.type would stay template (the bug)"
    assert regen[0][1]["use_database"] is True, "--db flag must propagate into regen"


def test_wire_flow_tolerates_existing_repo(tmp_path, monkeypatch):
    """An already-existing repo is not an error — still links/pushes/regenerates."""

    def fake_run(cmd, **_kw):
        is_create = "create" in cmd

        class R:
            returncode = 1 if is_create else 0
            stdout = "main" if "symbolic-ref" in cmd else ""
            stderr = "GraphQL: Name already exists on this account" if is_create else ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    regen: list[tuple] = []
    monkeypatch.setattr(cli, "generate_and_save_spec", lambda *a, **k: regen.append(1))
    monkeypatch.setattr(cli, "_detect_secrets", lambda _p: ([], {}))

    cli._create_and_wire_github_repo("transdoc", tmp_path, "saas-skeleton", db=False)
    assert regen, "existing repo should still proceed to push + regenerate the spec"
