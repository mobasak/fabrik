"""Behavior-Contract tests — fleet-dir scaffolder (T02a of plan 2026-08-15-plan-1).

The login-once credential architecture gives every long-lived Claude window its own
``CLAUDE_CONFIG_DIR``, so its OAuth refresh chain has exactly one owner. This module covers
``--new-dir`` (seeding contract, refusal, carrier merge), ``--sync-mcp`` / ``--sync-shared``
(the de-fork helpers), the carrier-presence + occupancy WARNs on ``--status``, and the
symlink WRITE-THROUGH probe that decided how ``settings.json`` is seeded.

Everything is tmp_path-isolated — ``CLAUDE_FLEET_ROOT``, ``ROTATE_STATE_DIR``, the canonical
``~/.claude`` dir and ``~/.claude.json``. No network, no real credentials, no real fleet dir.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "claude_rotate_fleet", REPO / "scripts" / "sysadmin" / "claude_rotate.py"
)
cr = importlib.util.module_from_spec(spec)
sys.modules["claude_rotate_fleet"] = cr
spec.loader.exec_module(cr)

SENTINEL = "SENTINEL-ACCESS-TOKEN"


def _canonical(tmp_path, monkeypatch):
    """A fake ~/.claude + ~/.claude.json + an empty fleet root. Returns (fleet, cdir, home)."""
    home = tmp_path / "home"
    cdir = home / ".claude"
    for sub in ("agents", "commands", "skills", "projects"):
        (cdir / sub).mkdir(parents=True)
    (cdir / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": []}}))
    # The shared chain. Nothing under a fleet dir may ever contain these bytes.
    (cdir / ".credentials.json").write_text(
        json.dumps({"claudeAiOauth": {"accessToken": SENTINEL}})
    )
    (home / ".claude.json").write_text(
        json.dumps(
            {
                "mcpServers": {"serena": {"command": "serena"}},
                "oauthAccount": {"emailAddress": "ob@ocoron.com"},
                "projects": {"/opt/seo": {"hasTrustDialogAccepted": True}},
            }
        )
    )
    monkeypatch.setattr(cr, "CLAUDE_DIR", cdir)
    monkeypatch.setattr(cr, "USER_CLAUDE_JSON", home / ".claude.json")
    monkeypatch.setattr(cr, "ACTIVE_CREDS", cdir / ".credentials.json")
    fleet = tmp_path / "fleet"
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(fleet))
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    return fleet, cdir, home


def _repo(tmp_path, name="seo"):
    r = tmp_path / "opt" / name
    r.mkdir(parents=True)
    return r


# ── B1: --new-dir delivers the whole seeding contract ─────────────────────────────────────────


def test_new_dir_seeds_the_full_contract(tmp_path, monkeypatch):
    fleet, cdir, _home = _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)

    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com", "--project", str(repo)]) == 0

    d = fleet / "seo"
    assert d.is_dir()
    assert oct(d.stat().st_mode & 0o777) == "0o700"

    seeded = json.loads((d / ".claude.json").read_text())
    assert seeded["mcpServers"] == {"serena": {"command": "serena"}}
    assert seeded["projects"] == {"/opt/seo": {"hasTrustDialogAccepted": True}}

    for name in ("agents", "commands", "skills", "projects"):
        link = d / name
        assert link.is_symlink(), f"{name}/ must be a symlink to the canonical dir"
        assert link.resolve() == (cdir / name).resolve()

    # settings.json is a COPY, not a symlink — see the write-through probe below.
    settings = d / "settings.json"
    assert settings.is_file() and not settings.is_symlink()
    assert json.loads(settings.read_text()) == json.loads((cdir / "settings.json").read_text())

    row = json.loads((fleet / "assignments.json").read_text())["seo"]
    assert row["account"] == "sarp@ocoron.com"
    assert row["identity"] == "pending-login"
    assert row["created"]
    assert row["project"] == str(repo.resolve())

    carrier = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert carrier["env"]["CLAUDE_CONFIG_DIR"] == str(d)
    assert carrier["env"]["CLAUDE_QUOTA_HOME"] == str(d)

    # Zero credential bytes: the dir is created EMPTY of credentials, filled by one /login.
    assert not (d / ".credentials.json").exists()
    for f in d.iterdir():
        if f.is_file() and not f.is_symlink():
            assert SENTINEL not in f.read_text()


def test_new_dir_without_a_project_writes_no_carrier(tmp_path, monkeypatch):
    """Hub role dirs carry the env on the launch line, not in a repo file."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "fabrik-infra", "ob@ocoron.com"]) == 0
    assert (fleet / "fabrik-infra").is_dir()
    assert "project" not in json.loads((fleet / "assignments.json").read_text())["fabrik-infra"]


def test_new_dir_skips_absent_canonical_entries_with_a_note(tmp_path, monkeypatch, capsys):
    fleet, cdir, _home = _canonical(tmp_path, monkeypatch)
    shutil.rmtree(cdir / "skills")
    (cdir / "settings.json").unlink()
    capsys.readouterr()

    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0

    out = capsys.readouterr().out
    assert not (fleet / "seo" / "skills").exists()
    assert not (fleet / "seo" / "settings.json").exists()
    assert "skills" in out and "settings.json" in out
    assert (fleet / "seo" / "agents").is_symlink()


@pytest.mark.parametrize(
    "slug", ["../escape", "Seo", "a b", "seo/sub", "-seo", "", "..", ".", ".hidden"]
)
def test_new_dir_refuses_a_bad_slug(tmp_path, monkeypatch, slug):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", slug, "a@b.com"]) != 0
    assert not fleet.exists()


# ── B2: a LIVE chain is never re-seeded; an unfinished scaffold RESUMES ───────────────────────


def test_new_dir_refuses_a_dir_holding_a_live_chain(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    (fleet / "seo").mkdir(parents=True)
    (fleet / "seo" / ".credentials.json").write_text("LIVE-CHAIN")

    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) != 0

    assert (fleet / "seo" / ".credentials.json").read_text() == "LIVE-CHAIN"
    assert not (fleet / "assignments.json").exists()


def test_new_dir_resumes_an_unfinished_scaffold(tmp_path, monkeypatch, capsys):
    """A dir with no credentials is an unfinished scaffold, not a live chain: re-running COMPLETES
    it. This is what turns every partial-failure state into "fix the cause, re-run"."""
    fleet, cdir, _home = _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    half = fleet / "seo"
    half.mkdir(parents=True)
    (half / "agents").symlink_to(cdir / "agents", target_is_directory=True)  # only piece present
    capsys.readouterr()

    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(repo)]) == 0

    out = capsys.readouterr().out
    assert "resumed" in out
    assert (half / ".claude.json").is_file()
    assert (half / "settings.json").is_file()
    for name in ("agents", "commands", "skills", "projects"):
        assert (half / name).is_symlink()
    assert json.loads((repo / ".claude" / "settings.local.json").read_text())["env"][
        "CLAUDE_CONFIG_DIR"
    ] == str(half)
    assert json.loads((fleet / "assignments.json").read_text())["seo"]["account"] == "a@b.com"


def test_resume_preserves_the_original_created_stamp_and_pinned_identity(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    table = json.loads((fleet / "assignments.json").read_text())
    table["seo"]["created"] = "2020-01-01T00:00:00+00:00"
    table["seo"]["identity"] = "a@b.com"  # pinned by the login that already happened
    (fleet / "assignments.json").write_text(json.dumps(table))

    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0

    row = json.loads((fleet / "assignments.json").read_text())["seo"]
    assert row["created"] == "2020-01-01T00:00:00+00:00"
    assert row["identity"] == "a@b.com", "a resume must not reset a pinned identity to pending"


def test_new_dir_refuses_to_rebind_a_slug_to_another_project(tmp_path, monkeypatch):
    """Silently re-pointing leaves the OLD repo's carrier live: two repos on one chain, and
    --status blind to the first (it only checks the row's current project)."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    proj_a = _repo(tmp_path, "projA")
    proj_b = _repo(tmp_path, "projB")
    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(proj_a)]) == 0

    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(proj_b)]) == 1

    assert not (proj_b / ".claude").exists(), "the double-carrier state must be unreachable"
    assert json.loads((fleet / "assignments.json").read_text())["seo"]["project"] == str(proj_a)
    assert (proj_a / ".claude" / "settings.local.json").is_file()


def test_new_dir_names_the_existing_binding_when_it_refuses(tmp_path, monkeypatch, capsys):
    _canonical(tmp_path, monkeypatch)
    proj_a = _repo(tmp_path, "projA")
    proj_b = _repo(tmp_path, "projB")
    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(proj_a)]) == 0
    capsys.readouterr()

    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(proj_b)]) == 1

    err = capsys.readouterr().err
    assert str(proj_a) in err, "the operator must be told which project holds the binding"
    assert str(cr._carrier_path(proj_a)) in err, "…and where the carrier to remove lives"


def test_resume_without_project_completes_the_binding_from_the_row(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(repo)]) == 0
    carrier = repo / ".claude" / "settings.local.json"
    carrier.unlink()  # the worktree/hand-edit case the monitor warns about

    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0  # no --project: the row is truth

    assert json.loads(carrier.read_text())["env"]["CLAUDE_CONFIG_DIR"] == str(fleet / "seo")


def test_new_dir_refuses_a_row_with_no_usable_account(tmp_path, monkeypatch):
    """assignments.json is hand-editable: a nulled account is CORRUPT, never unclaimed."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    table = json.loads((fleet / "assignments.json").read_text())
    table["seo"]["account"] = None
    raw = json.dumps(table)
    (fleet / "assignments.json").write_text(raw)

    assert cr.main(["--new-dir", "seo", "takeover@evil.com"]) == 1

    assert (fleet / "assignments.json").read_text() == raw, "a corrupt row is never rewritten"


def test_new_dir_refuses_a_slug_assigned_to_another_account(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0

    assert cr.main(["--new-dir", "seo", "other@b.com"]) != 0

    assert json.loads((fleet / "assignments.json").read_text())["seo"]["account"] == "a@b.com"


def test_new_dir_seeding_is_idempotent_and_never_reseeds(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    seeded = fleet / "seo" / ".claude.json"
    blob = json.loads(seeded.read_text())
    blob["oauthAccount"] = {"emailAddress": "seo@ocoron.com"}  # the dir's own login state
    seeded.write_text(json.dumps(blob))

    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0

    assert json.loads(seeded.read_text())["oauthAccount"] == {"emailAddress": "seo@ocoron.com"}


# ── F37: a mid-scaffold failure is one clean line + a retryable slug ──────────────────────────


def test_mid_scaffold_failure_removes_the_partial_dir(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)

    def boom(dest, notes, source):
        (dest / ".claude.json").write_text("{}")  # a partial scaffold, then failure
        raise OSError("disk full")

    monkeypatch.setattr(cr, "_scaffold_dir", boom)

    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 1  # clean rc, not a traceback

    assert not (fleet / "seo").exists(), "the slug must be retryable, not permanently wedged"
    table = fleet / "assignments.json"
    assert not table.exists() or "seo" not in json.loads(table.read_text()), "no orphan row"


def test_mid_scaffold_failure_never_removes_a_dir_holding_a_chain(tmp_path, monkeypatch):
    """A login could land between the mkdir and the failure — cleanup must never eat a chain."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)

    def boom(dest, notes, source):
        (dest / ".credentials.json").write_text("CHAIN")
        raise OSError("disk full")

    monkeypatch.setattr(cr, "_scaffold_dir", boom)

    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 1

    assert (fleet / "seo" / ".credentials.json").read_text() == "CHAIN"


def test_resumed_dir_is_never_removed_on_failure(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    (fleet / "seo").mkdir(parents=True)
    (fleet / "seo" / "keepme").write_text("prior work")

    def boom(dest, notes, source):
        raise OSError("disk full")

    monkeypatch.setattr(cr, "_scaffold_dir", boom)

    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 1

    assert (fleet / "seo" / "keepme").read_text() == "prior work"


# ── F39: the routing table survives concurrent writers ────────────────────────────────────────


def test_concurrent_new_dirs_keep_both_rows(tmp_path, monkeypatch):
    """Unlocked read-modify-write loses a row: both readers see {}, both write their own table."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    barrier = threading.Barrier(2)
    real_load = cr._load_assignments

    def racing_load(strict):
        table = real_load(strict=strict)
        try:
            barrier.wait(timeout=5)  # force both to sit in the RMW window together
        except threading.BrokenBarrierError:
            pass
        return table

    monkeypatch.setattr(cr, "_load_assignments", racing_load)
    results = []
    threads = [
        threading.Thread(target=lambda s=s: results.append(cr.main(["--new-dir", s, "a@b.com"])))
        for s in ("seo", "youtube")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert results == [0, 0] or sorted(results) == [0, 0]
    table = json.loads((fleet / "assignments.json").read_text())
    assert set(table) == {"seo", "youtube"}, f"a row was lost: {sorted(table)}"


# ── F47: the routing table is never silently replaced ─────────────────────────────────────────


def test_new_dir_refuses_a_corrupt_assignments_table(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    fleet.mkdir(parents=True)
    raw = '{"youtube": {"account": "c@d.com"'  # truncated
    (fleet / "assignments.json").write_text(raw)

    assert cr.main(["--new-dir", "seo", "a@b.com"]) != 0

    assert (fleet / "assignments.json").read_text() == raw, "never replace what you cannot parse"
    assert not (fleet / "seo").exists()


# ── F45: the hub gets no carrier ──────────────────────────────────────────────────────────────


def test_new_dir_refuses_a_carrier_for_the_hub(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    hub = _repo(tmp_path, "fabrik")
    monkeypatch.setattr(cr, "HUB_REPO", hub)

    assert cr.main(["--new-dir", "fabrik-infra", "a@b.com", "--project", str(hub)]) == 1

    assert not (hub / ".claude").exists(), "a hub carrier collapses all 3 windows onto one chain"
    assert not (fleet / "fabrik-infra").exists()


def test_hub_role_dirs_are_fine_without_a_project(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    hub = _repo(tmp_path, "fabrik")
    monkeypatch.setattr(cr, "HUB_REPO", hub)

    assert cr.main(["--new-dir", "fabrik-infra", "a@b.com"]) == 0

    assert (fleet / "fabrik-infra").is_dir()


# ── B3: carrier merge — 3 live projects already hold permissions state here ───────────────────


def test_new_dir_merges_into_an_existing_carrier(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    existing = {"permissions": {"allow": ["Bash(ls:*)"], "deny": []}, "env": {"FOO": "1"}}
    (repo / ".claude" / "settings.local.json").write_text(json.dumps(existing))

    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(repo)]) == 0

    got = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert got["permissions"] == existing["permissions"], "permissions state must survive"
    assert got["env"]["FOO"] == "1"
    assert got["env"]["CLAUDE_CONFIG_DIR"] == str(fleet / "seo")
    assert got["env"]["CLAUDE_QUOTA_HOME"] == str(fleet / "seo")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the mode bits this test relies on")
def test_new_dir_reports_a_carrier_write_failure_without_a_traceback(tmp_path, monkeypatch):
    """A write failure after the dir exists is a non-zero exit, never a traceback: the half-state
    announces itself through the carrier WARN on every --status until the operator re-runs."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    repo.chmod(0o500)  # readable + traversable, not writable
    try:
        rc = cr.main(["--new-dir", "seo", "a@b.com", "--project", str(repo)])
    finally:
        repo.chmod(0o700)

    assert rc == 1
    assert (fleet / "seo").is_dir()
    assert not (repo / ".claude").exists()


def test_carrier_merge_preserves_an_existing_files_mode(tmp_path, monkeypatch):
    """Merging into someone's carrier must not silently widen its permissions."""
    _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    carrier = repo / ".claude" / "settings.local.json"
    carrier.write_text(json.dumps({"permissions": {"allow": []}}))
    carrier.chmod(0o600)

    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(repo)]) == 0

    assert oct(carrier.stat().st_mode & 0o777) == "0o600"


def test_the_seeded_settings_copy_is_0644_not_0600(tmp_path, monkeypatch):
    """Shared config, not a secret — and it must not inherit the writer's 0600 default."""
    fleet, cdir, _home = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0

    assert oct((fleet / "seo" / "settings.json").stat().st_mode & 0o777) == "0o644"

    (cdir / "settings.json").write_text(json.dumps({"hooks": {}}))
    assert cr.main(["--sync-shared", "--from", "seo"]) == 0
    assert oct((fleet / "seo" / "settings.json").stat().st_mode & 0o777) == "0o644"


def test_the_seeded_claude_json_stays_0600(tmp_path, monkeypatch):
    """The counterpart: .claude.json carries account identity, so it is NOT widened."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0

    assert oct((fleet / "seo" / ".claude.json").stat().st_mode & 0o777) == "0o600"


def test_a_newly_created_carrier_is_0644(tmp_path, monkeypatch):
    _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)

    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(repo)]) == 0

    carrier = repo / ".claude" / "settings.local.json"
    assert oct(carrier.stat().st_mode & 0o777) == "0o644"


def test_new_dir_refuses_a_corrupt_carrier_without_touching_it(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    (repo / ".claude").mkdir()
    raw = '{"permissions": {"allow": ["Bash(ls:*)"'  # truncated — unparseable
    (repo / ".claude" / "settings.local.json").write_text(raw)

    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(repo)]) != 0

    assert (repo / ".claude" / "settings.local.json").read_text() == raw
    assert not (fleet / "seo").exists(), "refusal must precede every mutation"


# ── B4: --sync-mcp re-pushes the roster, never the OAuth section ──────────────────────────────


def test_sync_mcp_updates_every_dir_and_preserves_oauth(tmp_path, monkeypatch):
    fleet, _cdir, home = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    assert cr.main(["--new-dir", "youtube", "c@d.com"]) == 0

    # Each dir's own login state diverges from the canonical copy after its /login.
    for slug in ("seo", "youtube"):
        p = fleet / slug / ".claude.json"
        blob = json.loads(p.read_text())
        blob["oauthAccount"] = {"emailAddress": f"{slug}@ocoron.com"}
        p.write_text(json.dumps(blob))

    roster = {"serena": {"command": "serena"}, "grafana": {"command": "grafana"}}
    (home / ".claude.json").write_text(
        json.dumps({"mcpServers": roster, "oauthAccount": {"emailAddress": "ob@ocoron.com"}})
    )

    assert cr.main(["--sync-mcp"]) == 0

    for slug in ("seo", "youtube"):
        blob = json.loads((fleet / slug / ".claude.json").read_text())
        assert blob["mcpServers"] == roster
        assert blob["oauthAccount"] == {"emailAddress": f"{slug}@ocoron.com"}
        assert blob["projects"] == {"/opt/seo": {"hasTrustDialogAccepted": True}}


def test_sync_warns_when_defaulting_to_the_shared_source(tmp_path, monkeypatch, capsys):
    """Post-migration ~/.claude.json is the ad-hoc leftover — syncing from it REVERTS every dir."""
    _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    capsys.readouterr()

    assert cr.main(["--sync-mcp"]) == 0

    err = capsys.readouterr().err
    assert "WARNING" in err and "--from" in err


def test_sync_from_a_migrated_dir_is_the_roster_source(tmp_path, monkeypatch, capsys):
    fleet, _cdir, home = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    assert cr.main(["--new-dir", "youtube", "c@d.com"]) == 0
    live = {"serena": {"command": "serena"}, "playwright": {"command": "pw"}}
    src = fleet / "seo" / ".claude.json"
    blob = json.loads(src.read_text())
    blob["mcpServers"] = live
    src.write_text(json.dumps(blob))
    # the stale ad-hoc file that the DEFAULT source would have pushed
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"old": {"command": "old"}}}))
    capsys.readouterr()

    assert cr.main(["--sync-mcp", "--from", "seo"]) == 0

    assert json.loads((fleet / "youtube" / ".claude.json").read_text())["mcpServers"] == live
    assert "WARNING" not in capsys.readouterr().err


def test_sync_settings_replaces_a_symlink_instead_of_writing_through_it(tmp_path, monkeypatch):
    """A truncate-in-place write would follow the link and corrupt the CANONICAL settings.json,
    re-forking the seeding decision this module pinned. tmp+rename replaces the LINK."""
    fleet, cdir, _home = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    seeded = fleet / "seo" / "settings.json"
    seeded.unlink()
    seeded.symlink_to(cdir / "settings.json")  # the hazard state
    canonical_before = (cdir / "settings.json").read_text()
    (cdir / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": ["new"]}}))

    assert cr.main(["--sync-shared", "--from", "seo"]) == 0

    assert not seeded.is_symlink(), "the link must be replaced, not written through"
    assert json.loads(seeded.read_text()) == {"hooks": {"SessionStart": ["new"]}}
    assert canonical_before != (cdir / "settings.json").read_text()  # only OUR edit changed it


def test_sync_skips_a_dir_a_live_session_is_writing(tmp_path, monkeypatch, capsys):
    """A /login completing mid-sync must not be discarded by our stale in-memory copy."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    target = fleet / "seo" / ".claude.json"
    real_stat = Path.stat
    bumps = {"n": 0}

    class _Bumped:
        """A stat result whose mtime advances on every read — a live writer, always."""

        def __init__(self, st, ns):
            self._st = st
            self.st_mtime_ns = ns

        def __getattr__(self, name):
            return getattr(self._st, name)

    def racing_stat(self, *a, **k):
        st = real_stat(self, *a, **k)
        if Path(self) == target:
            bumps["n"] += 1
            return _Bumped(st, st.st_mtime_ns + bumps["n"])
        return st

    monkeypatch.setattr(Path, "stat", racing_stat)
    capsys.readouterr()

    rc = cr.main(["--sync-mcp", "--from", "seo"])

    assert rc == 1
    assert "changed under us" in capsys.readouterr().err


def test_sync_mcp_never_overwrites_an_unparseable_dir(tmp_path, monkeypatch):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    broken = fleet / "seo" / ".claude.json"
    broken.write_text('{"mcpServers": ')

    assert cr.main(["--sync-mcp"]) != 0
    assert broken.read_text() == '{"mcpServers": '


def test_sync_shared_also_repushes_the_settings_copy(tmp_path, monkeypatch):
    fleet, cdir, _home = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    (cdir / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": ["new"]}}))

    # --sync-mcp is roster-only: the settings copy is left where it was.
    assert cr.main(["--sync-mcp"]) == 0
    assert json.loads((fleet / "seo" / "settings.json").read_text()) == {
        "hooks": {"SessionStart": []}
    }

    assert cr.main(["--sync-shared"]) == 0
    assert json.loads((fleet / "seo" / "settings.json").read_text()) == {
        "hooks": {"SessionStart": ["new"]}
    }


# ── B5: the WRITE-THROUGH probe that decided the settings.json seeding mode ───────────────────


def test_writethrough_rename_replaces_a_file_symlink(tmp_path):
    """The one unproven mechanism (ticket T02a §Scope 4).

    The CLI writes config with tmp+rename. POSIX ``rename(2)`` operates on the LINK, not its
    target, so a rename onto a FILE symlink REPLACES the link with a regular file — forking that
    dir off the canonical copy. Observed outcome: FORK. Therefore ``settings.json`` is seeded as
    a COPY and re-pushed by ``--sync-shared``; only DIRECTORIES stay symlinked (next test).
    """
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "settings.json").write_text('{"canonical": true}')
    d = tmp_path / "dir"
    d.mkdir()
    link = d / "settings.json"
    link.symlink_to(canonical / "settings.json")
    assert link.is_symlink()

    tmpf = d / "settings.json.tmp.4242.beef"
    tmpf.write_text('{"written": "by-cli"}')
    os.replace(tmpf, link)

    assert not link.is_symlink(), "POSIX changed — re-decide the settings.json seeding mode"
    assert json.loads((canonical / "settings.json").read_text()) == {"canonical": True}
    assert json.loads(link.read_text()) == {"written": "by-cli"}

    # …and the scaffolder implements exactly that branch.
    assert "settings.json" in cr._SHARED_FILE_COPIES
    assert "settings.json" not in cr._SHARED_DIR_LINKS


def test_writethrough_survives_a_directory_symlink(tmp_path):
    """A rename INSIDE a symlinked dir resolves through the link and lands on the canonical
    inode — which is why agents/, commands/, skills/ and projects/ stay symlinks."""
    canonical = tmp_path / "canonical" / "projects"
    canonical.mkdir(parents=True)
    d = tmp_path / "dir"
    d.mkdir()
    (d / "projects").symlink_to(canonical, target_is_directory=True)

    tmpf = d / "projects" / "session.jsonl.tmp"
    tmpf.write_text("row")
    os.replace(tmpf, d / "projects" / "session.jsonl")

    assert (d / "projects").is_symlink()
    assert (canonical / "session.jsonl").read_text() == "row"
    assert set(cr._SHARED_DIR_LINKS) == {"agents", "commands", "skills", "projects"}


# ── B6: carrier-presence + occupancy WARNs on --status ────────────────────────────────────────


def _status_out(monkeypatch, capsys, occupancy=0):
    monkeypatch.setattr(cr, "_collect_statuses", lambda: ([], None))
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: occupancy)
    capsys.readouterr()
    assert cr._cmd_status(as_json=False) == 0
    return capsys.readouterr().out


def test_status_warns_when_a_mapped_carrier_is_missing(tmp_path, monkeypatch, capsys):
    _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com", "--project", str(repo)]) == 0
    (repo / ".claude" / "settings.local.json").unlink()

    out = _status_out(monkeypatch, capsys)

    assert "seo" in out
    assert "carrier MISSING" in out
    assert str(repo) in out


def test_status_warns_when_a_carrier_lacks_an_env_key(tmp_path, monkeypatch, capsys):
    _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com", "--project", str(repo)]) == 0
    carrier = repo / ".claude" / "settings.local.json"
    blob = json.loads(carrier.read_text())
    del blob["env"]["CLAUDE_QUOTA_HOME"]
    carrier.write_text(json.dumps(blob))

    out = _status_out(monkeypatch, capsys)

    assert "seo" in out and "CLAUDE_QUOTA_HOME" in out


def test_status_is_quiet_when_every_carrier_is_present(tmp_path, monkeypatch, capsys):
    _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com", "--project", str(repo)]) == 0

    out = _status_out(monkeypatch, capsys)

    assert "carrier" not in out and "occupancy" not in out


def test_status_warns_on_credentials_occupancy(tmp_path, monkeypatch, capsys):
    _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0  # a fleet exists → occupancy is meaningful
    monkeypatch.setenv("CLAUDE_FLEET_OCCUPANCY_MAX", "4")

    out = _status_out(monkeypatch, capsys, occupancy=9)

    assert "occupancy" in out
    assert "9" in out
    assert ".credentials.json" in out


def test_no_occupancy_warn_before_the_fleet_exists(tmp_path, monkeypatch, capsys):
    """Pre-migration every process is legitimately on the shared chain — a WARN there would fire
    on normal operation every run, and a monitor that cries wolf is not read when it is right."""
    _canonical(tmp_path, monkeypatch)

    out = _status_out(monkeypatch, capsys, occupancy=99)

    assert "occupancy" not in out


def test_status_payload_carries_the_warnings(tmp_path, monkeypatch):
    _canonical(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    assert cr.main(["--new-dir", "seo", "a@b.com", "--project", str(repo)]) == 0
    (repo / ".claude" / "settings.local.json").unlink()
    monkeypatch.setattr(cr, "_collect_statuses", lambda: ([], None))
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)

    pay = cr._status_payload()

    assert any("carrier MISSING" in w for w in pay["fleet_warnings"])


@pytest.mark.parametrize(
    ("count", "warns"), [(3, False), (4, True)]
)  # cap default 3: boundary must not fire, cap+1 must
def test_occupancy_warn_boundary(tmp_path, monkeypatch, capsys, count, warns):
    _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "a@b.com"]) == 0
    monkeypatch.delenv("CLAUDE_FLEET_OCCUPANCY_MAX", raising=False)

    out = _status_out(monkeypatch, capsys, occupancy=count)

    assert ("occupancy" in out) is warns


def test_status_survives_a_missing_fleet_root(tmp_path, monkeypatch, capsys):
    _canonical(tmp_path, monkeypatch)  # fleet root never created
    assert _status_out(monkeypatch, capsys) is not None


# ── the shared-binding probe itself ───────────────────────────────────────────────────────────


def _fake_proc(tmp_path, monkeypatch, procs):
    """Build a /proc fixture. procs = [(argv, env)]; env None = environ unreadable."""
    root = tmp_path / "proc"
    root.mkdir()
    for pid, (argv, env) in enumerate(procs, start=100):
        d = root / str(pid)
        d.mkdir()
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        if env is not None:
            (d / "environ").write_bytes(
                b"".join(f"{k}={v}".encode() + b"\0" for k, v in env.items())
            )
    (root / "self").mkdir()  # a non-numeric entry must be ignored, not crash
    monkeypatch.setattr(cr, "PROC_DIR", root)
    return root


def test_shared_bound_counts_only_sessions_without_config_dir(tmp_path, monkeypatch):
    _fake_proc(
        tmp_path,
        monkeypatch,
        [
            (["/usr/bin/claude", "--print"], {"HOME": "/home/o"}),  # shared
            (["claude"], {"HOME": "/home/o"}),  # shared
            (["claude", "-p"], {"CLAUDE_CONFIG_DIR": "/h/.claude-fleet/seo"}),  # migrated
            (["node", "claude"], {"HOME": "/home/o"}),  # shared (launcher form)
        ],
    )
    assert cr._shared_bound_sessions() == 3


def test_shared_bound_ignores_processes_that_merely_mention_claude(tmp_path, monkeypatch):
    """Measured on this box: a substring match hit 42 processes, only 14 of them the real CLI."""
    _fake_proc(
        tmp_path,
        monkeypatch,
        [
            (["bash", "-c", "claude -p ping"], {"HOME": "/home/o"}),
            (["python3", "/home/o/.claude/bin/claude-stop-decider.py"], {"HOME": "/home/o"}),
            (["node", "/opt/claude-proxy/proxy.js"], {"HOME": "/home/o"}),
            (["uvicorn", "--app-dir", "/opt/claude-thing"], {"HOME": "/home/o"}),
        ],
    )
    assert cr._shared_bound_sessions() == 0


def test_shared_bound_counts_an_empty_config_dir_as_shared(tmp_path, monkeypatch):
    """`CLAUDE_CONFIG_DIR=` (exported empty) makes the CLI fall back to ~/.claude — counting the
    bare NAME as isolated would UNDERCOUNT: the monitor going quiet exactly when it should fire."""
    _fake_proc(
        tmp_path,
        monkeypatch,
        [
            (["claude"], {"CLAUDE_CONFIG_DIR": ""}),
            (["claude", "-p"], {"CLAUDE_CONFIG_DIR": "   "}),
            (["claude"], {"CLAUDE_CONFIG_DIR": "/h/.claude-fleet/seo"}),
        ],
    )
    assert cr._shared_bound_sessions() == 2


def test_shared_bound_is_unknown_when_no_session_can_be_inspected(tmp_path, monkeypatch):
    """Sessions found but none readable → unknown. A false 0 all-clear is worse than no signal."""
    _fake_proc(tmp_path, monkeypatch, [(["claude"], None), (["claude", "-p"], None)])
    assert cr._shared_bound_sessions() is None


def test_shared_bound_is_zero_when_no_claude_runs(tmp_path, monkeypatch):
    _fake_proc(tmp_path, monkeypatch, [(["bash", "-lc", "sleep 1"], {"HOME": "/home/o"})])
    assert cr._shared_bound_sessions() == 0


def test_shared_bound_fails_soft_without_proc(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "PROC_DIR", tmp_path / "no-such-proc")
    assert cr._shared_bound_sessions() is None


# ── the atomic writers' fd ownership ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("writer", "payload"),
    [("_write_json_atomic", {"a": 1}), ("_replace_file", b"bytes")],
)
def test_writer_closes_the_fd_when_fdopen_raises(tmp_path, monkeypatch, writer, payload):
    """fdopen ADOPTS the fd, so the manual close belongs only on the path where it never adopted.
    Closing an adopted-then-closed fd could shut a sibling thread's reused fd number."""
    seen = {}
    real_fdopen = os.fdopen

    def failing_fdopen(fd, *a, **k):
        seen["fd"] = fd
        raise OSError("no memory for a stream")

    monkeypatch.setattr(os, "fdopen", failing_fdopen)
    with pytest.raises(OSError):
        getattr(cr, writer)(tmp_path / "target.json", payload)

    monkeypatch.setattr(os, "fdopen", real_fdopen)
    with pytest.raises(OSError):  # EBADF — the fd we were handed is closed, not leaked
        os.fstat(seen["fd"])
    assert not list(tmp_path.glob(".*tmp*")), "no .tmp. litter left behind"


@pytest.mark.parametrize(
    ("writer", "payload"),
    [("_write_json_atomic", object()), ("_replace_file", "not-bytes")],
)
def test_writer_never_closes_an_fd_fdopen_adopted(tmp_path, monkeypatch, writer, payload):
    """The real defect path: the BODY raises inside the with-block, which closes the adopted fd —
    and then a handler calls os.close on that same number. An EBADF guard does not make that safe:
    a sibling thread (aro-wake runs this under asyncio.to_thread) can be handed the freed number in
    between, and the "harmless" close would shut someone else's file."""
    adopted = {}
    real_fdopen, real_close = os.fdopen, os.close

    def recording_fdopen(fd, *a, **k):
        adopted["fd"] = fd
        return real_fdopen(fd, *a, **k)

    closed = []

    def recording_close(fd):
        closed.append(fd)
        return real_close(fd)

    monkeypatch.setattr(os, "fdopen", recording_fdopen)
    monkeypatch.setattr(os, "close", recording_close)
    with pytest.raises(TypeError):
        getattr(cr, writer)(tmp_path / "target.json", payload)

    assert adopted["fd"] not in closed, "os.close hit a descriptor fdopen already owned"
    assert not list(tmp_path.glob(".*tmp*")), "no .tmp. litter left behind"


# ── _fleet_root itself ────────────────────────────────────────────────────────────────────────


def test_fleet_root_honors_env_and_never_creates(tmp_path, monkeypatch):
    root = tmp_path / "nope"
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(root))
    assert cr._fleet_root() == root
    assert not root.exists(), "reading the fleet root must never conjure one"

    monkeypatch.delenv("CLAUDE_FLEET_ROOT")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "h"))
    assert cr._fleet_root() == tmp_path / "h" / ".claude-fleet"


# ── the byte-identical twin ───────────────────────────────────────────────────────────────────


def test_twin_copies_are_byte_identical():
    a = (REPO / "scripts" / "sysadmin" / "claude_rotate.py").read_bytes()
    b = (REPO / "scripts" / "aro-wake" / "claude_rotate.py").read_bytes()
    assert a == b, "the two vendored copies must stay byte-identical (cp after every edit)"


# ── T03: fleet-mode --status / tick + --keepalive ─────────────────────────────────────────────
# Feature-detected: ≥1 scaffolded fleet dir flips --status/--tick into the per-ACCOUNT view; an
# empty fleet root keeps the legacy manager-accounts machinery byte-unchanged. All tmp_path
# fleet roots, all probes faked — no network, no real credentials, no real crontab.

FLEET_NOW = 1_800_000_000.0


def _pin(fleet, slug, email):
    """Simulate an ALREADY-pinned identity (a prior successful post-login profile probe)."""
    path = fleet / "assignments.json"
    table = json.loads(path.read_text())
    table[slug]["identity"] = email
    path.write_text(json.dumps(table))


def _fleet_creds(fleet, slug, token, age_s=0.0, refresh_expires_s=30 * 86400.0):
    """Plant a FAKE but LIVE credential chain in a tmp fleet dir (tests only) and backdate its
    mtime. LIVE means it passes the F-P1 flip liveness gate (_chain_stale_reason): a refresh
    token with a future expiry, relative to FLEET_NOW. Pass refresh_expires_s <= 0 to plant an
    EXPIRED chain (a dead flip target)."""
    creds = fleet / slug / ".credentials.json"
    creds.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": token,
                    "refreshToken": f"R-{token}",
                    "expiresAt": int((FLEET_NOW + 3600) * 1000),
                    "refreshTokenExpiresAt": int((FLEET_NOW + refresh_expires_s) * 1000),
                }
            }
        )
    )
    ts = FLEET_NOW - age_s
    os.utime(creds, (ts, ts))
    return creds


def _fake_oauth(monkeypatch, profiles=None, usages=None):
    """Fake the api/oauth endpoint, keyed by token. Returns the recorded (path, token) calls."""
    calls = []

    def fake(path, token, timeout_s=15.0):
        calls.append((path, token))
        return {"profile": profiles or {}, "usage": usages or {}}.get(path, {}).get(token)

    monkeypatch.setattr(cr, "_oauth_get", fake)
    return calls


def _usage_blob(session=42.0, weekly=31.0):
    return {
        "five_hour": {"utilization": session, "resets_at": "2027-01-20T00:00:00+00:00"},
        "seven_day": {"utilization": weekly, "resets_at": "2027-01-22T00:00:00+00:00"},
    }


def _fleet_two_accounts(tmp_path, monkeypatch):
    """Three dirs on two accounts, identities already pinned. Returns the fleet root."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    for slug, email in (
        ("seo", "sarp@ocoron.com"),
        ("youtube", "sarp@ocoron.com"),
        ("intel", "ob@ocoron.com"),
    ):
        assert cr.main(["--new-dir", slug, email]) == 0
        _pin(fleet, slug, email)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    return fleet


# ── B7: fleet --status groups by account, live quota from the freshest token ──────────────────


def test_fleet_status_groups_by_account_with_live_quota(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=3600.0)
    _fleet_creds(fleet, "youtube", "tok-yt", age_s=600.0)  # freshest sarp dir
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    calls = _fake_oauth(
        monkeypatch,
        usages={"tok-yt": _usage_blob(42.0, 31.0), "tok-intel": _usage_blob(7.0, 9.0)},
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out

    assert "sarp@ocoron.com" in out and "ob@ocoron.com" in out
    assert "42%" in out and "7%" in out
    assert "parked — quota unknown" not in out
    # usage is queried ONCE per account, with the FRESHEST dir's token — never per dir
    assert sorted(t for p, t in calls if p == "usage") == ["tok-intel", "tok-yt"]
    sarp_line = next(line for line in out.splitlines() if "sarp@ocoron.com" in line)
    assert "seo" in sarp_line and "youtube" in sarp_line, "dirs must group under their account"


def test_fleet_status_stale_account_falls_back_to_the_cached_row_with_age(
    tmp_path, monkeypatch, capsys
):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    _pin(fleet, "seo", "sarp@ocoron.com")
    _fleet_creds(fleet, "seo", "tok-seo", age_s=10 * 3600.0)  # no token <8h old
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-usage-cache.json").write_text(
        json.dumps(
            {
                "sarp@ocoron.com": {
                    "ts": FLEET_NOW - 9 * 3600.0,
                    "five_hour": {"utilization": 66.0, "resets_at_epoch": FLEET_NOW + 3600},
                    "seven_day": {"utilization": 12.0, "resets_at_epoch": FLEET_NOW + 86400},
                }
            }
        )
    )
    calls = _fake_oauth(monkeypatch)
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out

    assert [c for c in calls if c[0] == "usage"] == [], "a stale account must not be probed"
    assert "66%" in out and "STALE" in out and "9h" in out
    assert "parked — quota unknown" not in out


def test_fleet_status_without_any_reading_never_prints_the_legacy_parked_line(
    tmp_path, monkeypatch, capsys
):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    _pin(fleet, "seo", "sarp@ocoron.com")
    _fleet_creds(fleet, "seo", "tok-seo", age_s=10 * 3600.0)  # idle >8h, and no cache exists
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    _fake_oauth(monkeypatch)
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out

    assert "sarp@ocoron.com" in out
    assert "parked — quota unknown" not in out


# ── B8: identity pinning — ONE probe, written back, never re-probed ───────────────────────────


def test_pending_login_is_pinned_once_and_never_reprobed(tmp_path, monkeypatch, capsys):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0  # identity: pending-login
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    calls = _fake_oauth(
        monkeypatch,
        profiles={"tok-seo": {"account": {"email": "sarp@ocoron.com"}}},
        usages={"tok-seo": _usage_blob()},
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    row = json.loads((fleet / "assignments.json").read_text())["seo"]
    assert row["identity"] == "sarp@ocoron.com", "the verified email must be written back"
    assert [c for c in calls if c[0] == "profile"] == [("profile", "tok-seo")]

    calls.clear()
    assert cr.main(["--status"]) == 0  # second run: the pin holds — ZERO profile probes
    assert [c for c in calls if c[0] == "profile"] == []
    assert json.loads((fleet / "assignments.json").read_text())["seo"]["identity"] == (
        "sarp@ocoron.com"
    )


def test_pending_login_probe_failure_stays_pending_and_excluded_from_grouping(
    tmp_path, monkeypatch, capsys
):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    _fake_oauth(monkeypatch)  # profile answers None — probe failure
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out

    assert "pending-login" in out
    assert "sarp@ocoron.com — " not in out, "an unpinned dir must not be grouped as an account"
    row = json.loads((fleet / "assignments.json").read_text())["seo"]
    assert row["identity"] == "pending-login"


# ── B9: empty fleet root → the legacy view, byte-unchanged ────────────────────────────────────


def test_empty_fleet_root_keeps_the_legacy_view_and_one_dir_flips_it(tmp_path, monkeypatch, capsys):
    _canonical(tmp_path, monkeypatch)  # fleet root never created
    reset = FLEET_NOW
    row = {
        "name": "sarp-ocoron-com-s-organization",
        "email": "sarp@ocoron.com",
        "valid": True,
        "five_hour": {"utilization": 42.0, "resets_at_epoch": reset},
        "seven_day": {"utilization": 31.0, "resets_at_epoch": reset},
    }
    monkeypatch.setattr(cr, "_collect_statuses", lambda: ([row], row["name"]))
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    capsys.readouterr()

    assert cr._cmd_status(as_json=False) == 0
    out = capsys.readouterr().out

    from datetime import datetime

    rs = datetime.fromtimestamp(reset).strftime("%a %H:%M")
    session = f"42% (resets {rs})"
    expected = f"* {row['email']:32} session {session:24} weekly 31% (resets {rs})\n"
    assert out == expected, "empty fleet root must render the legacy view BYTE-unchanged"

    # …and ONE scaffolded dir must flip the same call into the fleet view (the dispatch seam)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    capsys.readouterr()
    assert cr._cmd_status(as_json=False) == 0
    assert "fleet" in capsys.readouterr().out


# ── B10: --keepalive — mtime-gated, one in-place ping per stale dir ───────────────────────────


def test_keepalive_pings_exactly_the_stale_dirs_with_their_own_env(tmp_path, monkeypatch, capsys):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    for slug in ("old", "fresh", "empty"):
        assert cr.main(["--new-dir", slug, "sarp@ocoron.com"]) == 0
    _fleet_creds(fleet, "old", "tok-old", age_s=8 * 86400.0)  # 8 days idle → ping
    _fleet_creds(fleet, "fresh", "tok-fresh", age_s=1 * 86400.0)  # 1 day → skip
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    runs = []

    def fake_run(argv, **kw):
        runs.append((list(argv), dict(kw.get("env") or {})))
        return subprocess.CompletedProcess(argv, 0, "pong", "")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    capsys.readouterr()

    assert cr.main(["--keepalive"]) == 0
    out = capsys.readouterr().out

    assert len(runs) == 1, "exactly ONE ping — the stale dir only"
    argv, env = runs[0]
    assert argv == ["claude", "-p", "ping"]
    # in-place sole-owner refresh: BOTH carrier variables point at the dir ITSELF, no temp copy
    assert env["CLAUDE_CONFIG_DIR"] == str(fleet / "old")
    assert env["CLAUDE_QUOTA_HOME"] == str(fleet / "old")
    for line in out.splitlines():
        assert line.startswith("keepalive:"), f"cron-log lines must be single-line: {line!r}"


def test_keepalive_failed_ping_alerts_via_mesh_notify_and_exits_nonzero(
    tmp_path, monkeypatch, capsys
):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "old", "sarp@ocoron.com"]) == 0
    _fleet_creds(fleet, "old", "tok-old", age_s=8 * 86400.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)

    def fake_run(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, "", "boom")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    alerts = []
    # _tick_telegram IS the ci_health_probe mesh-notify invocation
    # (bash ~/.claude/bin/claude-sound.sh mesh-notify <sid> /opt/fabrik "<msg>")
    monkeypatch.setattr(cr, "_tick_telegram", lambda msg: alerts.append(msg))
    capsys.readouterr()

    assert cr.main(["--keepalive"]) == 1, "a failed ping must be visible to cron (rc 1)"
    assert alerts and "old" in alerts[0]


def test_keepalive_never_reads_credential_bytes(tmp_path, monkeypatch):
    """The staleness gate is MTIME-only: a keepalive pass must never open the credential file."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "old", "sarp@ocoron.com"]) == 0
    creds = _fleet_creds(fleet, "old", "tok-old", age_s=8 * 86400.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(
        cr.subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", "")
    )
    real_read_bytes, real_read_text = Path.read_bytes, Path.read_text

    def guarded_bytes(self, *a, **k):
        assert self.name != ".credentials.json", "keepalive read credential BYTES"
        return real_read_bytes(self, *a, **k)

    def guarded_text(self, *a, **k):
        assert self.name != ".credentials.json", "keepalive read credential BYTES"
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_bytes", guarded_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_text)

    assert cr.main(["--keepalive"]) == 0
    assert creds.read_text  # fixture intact


# ── B11: the fleet tick — per-account advisory; legacy install machinery never touched ────────


def _fleet_tick_spies(monkeypatch):
    actions = {"switched": [], "picked": [], "telegrams": [], "mails": []}
    monkeypatch.setattr(cr, "_tick_switch", lambda name: actions["switched"].append(name) or True)
    monkeypatch.setattr(cr, "_pick_successor", lambda *a, **k: actions["picked"].append(a) or None)
    monkeypatch.setattr(cr, "_tick_telegram", lambda msg: actions["telegrams"].append(msg))
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, msg: actions["mails"].extend(repos))
    return actions


def test_fleet_tick_no_advisory_while_a_sibling_has_headroom(tmp_path, monkeypatch, capsys):
    """The active account at 96% is a NON-event while any sibling has headroom: the flip leg
    re-points to it and every agent keeps working, so NO advisory fires (operator directive
    2026-08-26 + trade-intelligence 01M0YAB2 — the old per-account 96% advisory was spam AND a
    false alarm). The tick still installs nothing (credential-free flip)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik", "seo"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert actions["switched"] == [] and actions["picked"] == [], "fleet tick installs NOTHING"
    assert actions["telegrams"] == [], (
        "a walled account with a headroom sibling fires NO advisory — the flip relieves it"
    )
    assert actions["mails"] == [], "no drain mail while the fleet has headroom"


def test_fleet_exhaustion_advisory_broadcasts_to_all_mailbox_repos(
    tmp_path, monkeypatch, capsys
):
    """When the ONLY account is walled (no sibling to flip to), the fleet-wide wall advisory
    fires and BROADCASTS to every mailbox repo — the wall concerns every project equally."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "ob", "ob@ocoron.com"]) == 0
    _pin(fleet, "ob", "ob@ocoron.com")
    _fleet_creds(fleet, "ob", "tok-ob", age_s=60.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    _fake_oauth(monkeypatch, usages={"tok-ob": _usage_blob(96.0, 96.0)})
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik", "seo", "youtube"])
    _point(fleet, "ob")
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")

    assert cr._cmd_tick() == 0

    assert len(actions["telegrams"]) == 1, "the active account is walled with no relief → 1 advisory"
    assert "ob@ocoron.com" in actions["telegrams"][0]
    assert sorted(actions["mails"]) == ["fabrik", "seo", "youtube"]


def test_fleet_exhaustion_advisory_fires_once_then_rearms_on_relief(tmp_path, monkeypatch):
    """Fire ONCE on entry to the walled state, suppress while it persists (the latch), and
    re-arm the instant relief arrives — a headroom sibling returning clears the latch so the
    NEXT genuine wall speaks fresh. This is the epoch-free replacement for the churny per-
    account band|cycle dedup that spammed 8x at a steady 95% (trade-intelligence 01M0YAB2)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    usages = {"tok-seo": _usage_blob(96.0, 96.0), "tok-intel": _usage_blob(100.0, 100.0)}
    _fake_oauth(monkeypatch, usages=usages)
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")

    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 1, "entry to the walled state fires ONE advisory"

    # Still walled next tick → the latch suppresses the repeat (this is the anti-spam fix).
    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 1, "a persisting wall must NOT re-fire (latch holds)"

    # A sibling regains headroom → the flip relieves the active account → latch re-arms, silent.
    usages["tok-intel"] = _usage_blob(10.0, 10.0)
    _fake_oauth(monkeypatch, usages=usages)
    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 1, "relief (a flip to headroom) fires nothing and re-arms"

    # A fresh total wall AFTER relief speaks again — the latch was cleared, so it is a new fact.
    usages["tok-seo"] = _usage_blob(97.0, 97.0)
    usages["tok-intel"] = _usage_blob(100.0, 100.0)
    _fake_oauth(monkeypatch, usages=usages)
    _point(fleet, "seo")
    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 2, "a new wall episode after relief is a new fact — fires"


def test_fleet_wall_advisory_future_dated_latch_is_invalid_and_still_fires(tmp_path, monkeypatch):
    """A latch whose mtime sits in the FUTURE (WSL suspend/resume, NTP — the clock-skew class,
    F54) is INVALID: it must NOT silence a live wall until the wall clock catches up in N days,
    which is exactly when the operator most needs the warning. Treat future-dated as expired and
    speak now. (The fresh-latch suppression path is covered by the fires_once test below.)"""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "ob", "ob@ocoron.com"]) == 0
    _pin(fleet, "ob", "ob@ocoron.com")
    _fleet_creds(fleet, "ob", "tok-ob", age_s=60.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    _fake_oauth(monkeypatch, usages={"tok-ob": _usage_blob(96.0, 96.0)})
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "ob")
    stamp = cr._fleet_exhaustion_stamp()
    stamp.write_text("1")  # a latch is present, but its mtime is in the future → invalid
    future = FLEET_NOW + 5 * 86400
    os.utime(stamp, (future, future))

    assert cr._cmd_tick() == 0

    assert len(actions["telegrams"]) == 1, "a future-dated (invalid) latch must not silence a live wall"


def test_fleet_wall_advisory_silent_when_a_headroom_sibling_relieves_the_wall(
    tmp_path, monkeypatch, capsys
):
    """A walled active WITH a headroom sibling is NOT exhaustion, so no wall advisory fires.
    Originally this state was "flip held by the 30-min dwell, relief minutes away"; since D-104
    (2026-09-03) trip flips are dwell-exempt, so the second tick FLIPS to the sibling — the class
    under test (no false alarm while the fleet has headroom) is unchanged, only the mechanism of
    relief moved from "wait out the dwell" to "flip now"."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    usages = {"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)}
    _fake_oauth(monkeypatch, usages=usages)
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")

    # tick 1: flips seo(96%) -> intel(headroom), ledgers a flip at FLEET_NOW; the flip relieved it
    assert cr._cmd_tick() == 0
    assert os.readlink(fleet / "active") == "intel"
    assert actions["telegrams"] == [], "the flip relieved the wall — no advisory"

    # tick 2 (same instant): intel walls to 96%, seo now has headroom → the flip is NOT held
    # (D-104), the pointer moves to seo, and the relieved wall fires nothing.
    usages["tok-intel"] = _usage_blob(96.0, 96.0)
    usages["tok-seo"] = _usage_blob(10.0, 10.0)
    _fake_oauth(monkeypatch, usages=usages)
    assert cr._cmd_tick() == 0
    assert os.readlink(fleet / "active") == "seo", "a trip flip is never held by the dwell (D-104)"
    assert actions["telegrams"] == [], "a wall relieved by a flip fires NO advisory"
    assert actions["mails"] == []


def test_fleet_wall_advisory_rearms_after_a_week_of_unbroken_exhaustion(tmp_path, monkeypatch):
    """The latch is not forever: a WEEK of unbroken total exhaustion re-reminds the operator
    (restores the old 'week without a word' re-arm; a presence-only latch would otherwise go
    silent for good if the walled active never dips below threshold across a reset)."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "ob", "ob@ocoron.com"]) == 0
    _pin(fleet, "ob", "ob@ocoron.com")
    _fleet_creds(fleet, "ob", "tok-ob", age_s=60.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    _fake_oauth(monkeypatch, usages={"tok-ob": _usage_blob(96.0, 96.0)})
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "ob")

    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 1, "entry to the walled state fires once"

    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 1, "a fresh latch suppresses the immediate repeat"

    # 8 days later, still walled, still no successor → the latch has expired → re-fire
    stamp = cr._fleet_exhaustion_stamp()
    old = FLEET_NOW - 8 * 86400
    os.utime(stamp, (old, old))
    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 2, "a week of unbroken exhaustion re-reminds"


def test_keepalive_future_skewed_credentials_mtime_counts_as_due(tmp_path, monkeypatch, capsys):
    """F55: a credentials mtime AHEAD of now beyond the skew tolerance must be pinged — a
    spurious ping is harmless, a silently skipped one risks the ~30-day idle lapse."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "skewed", "sarp@ocoron.com"]) == 0
    _fleet_creds(fleet, "skewed", "tok-skewed", age_s=-5 * 86400.0)  # mtime 5 days in the FUTURE
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    runs = []

    def fake_run(argv, **kw):
        runs.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "pong", "")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    capsys.readouterr()

    assert cr.main(["--keepalive"]) == 0
    out = capsys.readouterr().out

    assert len(runs) == 1, "a future-skewed mtime must be treated as DUE, never as fresh"
    for line in out.splitlines():
        assert line.startswith("keepalive:"), f"cron-log lines must be single-line: {line!r}"


def test_fleet_flip_path_structurally_writes_no_credentials(tmp_path, monkeypatch):
    """REPLACES test_fleet_tick_branch_has_structurally_no_successor_logic: fleet-mode successor
    selection now exists BY DESIGN (the pointer flip — operator redesign 2026-08-15). The
    load-bearing invariant is restated as what it always protected: the flip path performs NO
    credential-file writes — it renames a symlink, never touches the legacy install machinery
    (its behavioral twin is test_fleet_flip_tick_moves_zero_credential_bytes)."""
    forbidden = {
        "_activate_snapshot",
        "_tick_switch",
        "_rotate_active_account",
        "_cmd_capture_current",
        "_file_refreshed_credentials",
        "_secure_write",
        "_replace_file",
        "_cmd_next",
        "_pick_successor",
        "_tick_inner",
    }

    def _names(code):
        """co_names of *code* PLUS its one-level nested code objects (lambdas / inner defs /
        comprehensions), so a nested function cannot smuggle a forbidden name past the assert.
        KNOWN LIMITATION: a fresh module-level helper with a novel name still evades a name
        check by construction — the behavioral trap
        (test_fleet_flip_tick_moves_zero_credential_bytes) is the real net, which is why it
        must stay tight (writes, links, symlinks, AND subprocess argv are all trapped there)."""
        names = set(code.co_names)
        for const in code.co_consts:
            if hasattr(const, "co_names"):
                names |= set(const.co_names)
        return names

    for fn_name in (
        "_flip_active",
        "_resolve_active",
        "_chain_stale_reason",
        "_refresh_expiry_epoch",
        "_pick_flip_target",
        "_validated_pick",
        "_account_flip_dir",
        "_freshest_credentialed_slug",
        "_cmd_fleet_switch",
        "_fleet_flip_leg",
        "_fleet_row_warnings",
        "_identity_probe_stamp",
        "_identity_probe_due",
        "_identity_probe_record",
        "_identity_probe_result",
        "_fleet_tick_inner",
        "_fleet_account_rows",
        "_cmd_fleet_status",
        "_cmd_keepalive",
    ):
        fn = getattr(cr, fn_name)
        overlap = _names(fn.__code__) & forbidden
        assert not overlap, f"{fn_name} references credential-install machinery: {overlap}"

    # …and the dispatch never reaches the single-live-account tick in fleet mode
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    monkeypatch.setattr(
        cr, "_tick_inner", lambda: (_ for _ in ()).throw(AssertionError("legacy tick reached"))
    )
    monkeypatch.setattr(cr, "_fleet_tick_inner", lambda dirs: 0)
    assert cr._cmd_tick() == 0


# ── B12: the active POINTER — flip rotation, zero credential bytes ────────────────────────────
# Operator redesign 2026-08-15: per-ACCOUNT fleet dirs (each logged in once, chains never move)
# + ONE `active` symlink every session follows; the tick FLIPS the pointer by quota headroom.


def _point(fleet, slug):
    """Pre-set the active pointer WITHOUT ledgering (simulates a flip from a past dwell window,
    so the tick under test is not held by its own fixture's dwell clock)."""
    ptr = fleet / "active"
    if ptr.is_symlink():
        ptr.unlink()
    ptr.symlink_to(slug, target_is_directory=True)


def test_rename_replaces_a_directory_symlink(tmp_path):
    """The probe _flip_active's atomicity rests on (2026-08-15, the DIR twin of T02a's
    file-symlink write-through probe): os.replace onto a symlink-to-DIRECTORY replaces the LINK
    itself — rename(2) follows neither argument — so the pointer swap has no missing window.
    If a platform ever changes this, this goes red and the flip design is re-taken."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    ptr = tmp_path / "active"
    ptr.symlink_to("a", target_is_directory=True)
    tmp = tmp_path / ".active.tmp"
    tmp.symlink_to("b", target_is_directory=True)
    os.replace(tmp, ptr)
    assert ptr.is_symlink(), "the pointer must remain a symlink, never become a real dir"
    assert os.readlink(ptr) == "b", "os.replace must swap the LINK, not write through it"
    assert not tmp.exists() and not tmp.is_symlink(), "the temp link is consumed by the rename"


def test_new_dir_refuses_the_reserved_active_slug(tmp_path, monkeypatch, capsys):
    _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "active", "sarp@ocoron.com"]) == 2
    assert "reserved" in capsys.readouterr().err


def test_fleet_dirs_and_keepalive_ignore_the_active_pointer(tmp_path, monkeypatch, capsys):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    for slug in ("ob", "sarp"):
        assert cr.main(["--new-dir", slug, f"{slug}@ocoron.com"]) == 0
    _fleet_creds(fleet, "ob", "tok-ob", age_s=8 * 86400.0)  # stale → exactly one ping
    _fleet_creds(fleet, "sarp", "tok-sarp", age_s=86400.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    assert cr._flip_active("ob", manual=True)
    assert [d.name for d in cr._fleet_dirs()] == ["ob", "sarp"], (
        "the active symlink must never be counted as a fleet dir"
    )
    runs = []

    def fake_run(argv, **kw):
        runs.append(dict(kw.get("env") or {})["CLAUDE_CONFIG_DIR"])
        return subprocess.CompletedProcess(argv, 0, "pong", "")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    capsys.readouterr()
    assert cr.main(["--keepalive"]) == 0
    assert runs == [str(fleet / "ob")], (
        "one ping for the stale dir only — never a double ping through the pointer"
    )


def test_flip_active_repoints_atomically_and_idempotently(tmp_path, monkeypatch):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo")
    _fleet_creds(fleet, "intel", "tok-intel")
    assert cr._flip_active("seo", manual=True)
    ptr = fleet / "active"
    assert ptr.is_symlink() and os.readlink(ptr) == "seo", (
        "a RELATIVE link — the fleet root stays relocatable"
    )
    assert cr._resolve_active() == "seo"
    assert cr._flip_active("seo", manual=True), "re-flipping to the active slug is a no-op success"
    assert cr._flip_active("intel", manual=True)
    assert os.readlink(ptr) == "intel"
    lines = (tmp_path / "state" / "rotate-ledger.jsonl").read_text().splitlines()
    flips = [e for e in map(json.loads, lines) if e.get("event") == "flip"]
    assert [(f["from"], f["to"]) for f in flips] == [(None, "seo"), ("seo", "intel")], (
        "every real flip is ledgered; the idempotent no-op is not"
    )


def test_flip_active_refuses_a_dir_without_credentials(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo")
    assert cr._flip_active("seo", manual=True)
    capsys.readouterr()
    assert not cr._flip_active("youtube", manual=True), "an empty chain is never pointed at"
    assert not cr._flip_active("ghost", manual=True), "nor an absent dir"
    assert not cr._flip_active("active", manual=True), "nor the pointer itself (no self-loop)"
    assert "credentialed" in capsys.readouterr().err
    assert os.readlink(fleet / "active") == "seo", "a refused flip leaves the pointer untouched"


def test_flip_active_pause_holds_and_manual_overrides(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo")
    _fleet_creds(fleet, "intel", "tok-intel")
    _point(fleet, "seo")
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "switch-paused").touch()
    capsys.readouterr()
    assert not cr._flip_active("intel"), "the pause marker holds every automated flip"
    err = capsys.readouterr().err
    assert "PAUSED" in err and "--resume-switch" in err, "the refusal must name the override"
    assert os.readlink(fleet / "active") == "seo"
    assert cr._flip_active("intel", manual=True), "--switch stays the deliberate escape hatch"
    assert os.readlink(fleet / "active") == "intel"


def test_flip_active_dwell_blocks_then_allows_and_fails_closed(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo")
    _fleet_creds(fleet, "intel", "tok-intel")
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    ledger = state / "rotate-ledger.jsonl"
    ledger.write_text(json.dumps({"event": "flip", "ts": FLEET_NOW - 10 * 60, "to": "seo"}) + "\n")
    capsys.readouterr()
    assert not cr._flip_active("intel"), "10 min after a flip is inside the 30-min dwell"
    assert "within dwell" in capsys.readouterr().err
    ledger.write_text(json.dumps({"event": "flip", "ts": FLEET_NOW - 31 * 60, "to": "seo"}) + "\n")
    assert cr._flip_active("intel"), "31 min after a flip is outside the dwell"
    assert os.readlink(fleet / "active") == "intel"
    # unusable ledger ts → the dwell guard fails CLOSED (the _last_switch_ts contract, flip event)
    ledger.write_text(json.dumps({"event": "flip", "ts": "soon", "to": "seo"}) + "\n")
    capsys.readouterr()
    assert not cr._flip_active("seo"), "an unusable ledger must hold the flip, never allow it"
    assert "fail-closed" in capsys.readouterr().err


def test_fleet_tick_flips_at_threshold_to_the_headroom_account(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    usages = {"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)}
    _fake_oauth(monkeypatch, usages=usages)
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out

    assert os.readlink(fleet / "active") == "intel", "the tick must FLIP the pointer"
    assert "flipped active sarp@ocoron.com -> ob@ocoron.com (intel) at 96%" in out
    assert actions["switched"] == [] and actions["picked"] == [], "legacy install never touched"
    lines = (tmp_path / "state" / "rotate-ledger.jsonl").read_text().splitlines()
    flip = next(e for e in map(json.loads, lines) if e.get("event") == "flip")
    assert (flip["from"], flip["to"], flip["at_pct"]) == ("seo", "intel", 96.0)

    # …and a second over-threshold tick moments later FLIPS AGAIN. Until 2026-09-03 this tick
    # was held by the 30-min dwell; D-104 made every trip flip dwell-exempt (a trip is a wall,
    # never churn — the session wall stops every running agent at once), and churn is prevented
    # where it belongs: the candidate predicate never targets a sibling at/over the threshold or
    # without 5h budget. seo at 10% IS such a target, so the pointer moves back to it.
    usages["tok-intel"] = _usage_blob(96.0, 96.0)
    usages["tok-seo"] = _usage_blob(10.0, 10.0)
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out
    assert "withheld" not in out, out
    assert os.readlink(fleet / "active") == "seo", "a trip flip is never held by the dwell (D-104)"


def test_fleet_tick_below_threshold_never_flips(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(94.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert "below 95%, no flip" in capsys.readouterr().out
    assert os.readlink(fleet / "active") == "seo"


def test_fleet_tick_repairs_a_missing_or_dangling_pointer(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(42.0, 31.0), "tok-intel": _usage_blob(7.0, 9.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    # a recent ledger flip must NOT hold the repair — a dangling pointer is an outage, not
    # hysteresis territory
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "rotate-ledger.jsonl").write_text(
        json.dumps({"event": "flip", "ts": FLEET_NOW - 60, "to": "seo"}) + "\n"
    )
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out

    assert "repaired" in out
    assert os.readlink(fleet / "active") == "intel", "no pointer → flip to most weekly headroom"

    ptr = fleet / "active"
    ptr.unlink()
    ptr.symlink_to("ghost", target_is_directory=True)  # dangling
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    assert "repaired" in capsys.readouterr().out
    assert os.readlink(fleet / "active") == "intel", "a dangling pointer reads as no active"


def test_fleet_tick_without_headroom_flips_nothing_and_advises(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(100.0, 100.0)},
    )
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out

    assert os.readlink(fleet / "active") == "seo", "a walled sibling is never a flip target"
    assert "NO successor has headroom" in out
    assert any("sarp@ocoron.com" in t for t in actions["telegrams"]), (
        "the ≥85% drain advisory is the recourse when nothing can flip"
    )


def test_fleet_tick_pause_holds_the_flip_but_never_the_advisory(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "switch-paused").touch()
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    err = capsys.readouterr().err

    assert os.readlink(fleet / "active") == "seo", "the pause marker holds the tick's flip"
    assert "PAUSED" in err
    assert any("sarp@ocoron.com" in t for t in actions["telegrams"]), (
        "pause holds flips, NEVER telemetry/advisories (T01 semantics)"
    )


def test_switch_in_fleet_mode_is_a_manual_pause_exempt_flip(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo")
    _fleet_creds(fleet, "intel", "tok-intel")
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "switch-paused").touch()
    capsys.readouterr()

    assert cr.main(["--switch", "intel"]) == 0, "--switch flips even while paused (escape hatch)"
    assert "pointer flip" in capsys.readouterr().out
    assert os.readlink(fleet / "active") == "intel"
    assert cr.main(["--switch", "nope"]) == 1, "an unknown slug is refused, pointer untouched"
    assert os.readlink(fleet / "active") == "intel"


def test_fleet_status_shows_the_active_account(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fake_oauth(monkeypatch, usages={"tok-seo": _usage_blob(42.0, 31.0)})
    capsys.readouterr()

    assert cr.main(["--status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["active"] is None, "no pointer → active: null"

    assert cr._flip_active("seo", manual=True)
    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out
    assert "active: seo" in out
    sarp_line = next(line for line in out.splitlines() if "sarp@ocoron.com" in line)
    assert sarp_line.startswith("*"), "the active account's row carries the * mark"

    assert cr.main(["--status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["active"] == "seo"


def test_fleet_flip_tick_moves_zero_credential_bytes(tmp_path, monkeypatch):
    """THE invariant that distinguishes the flip from the retired file-swap rotation: a
    flip-inducing tick performs no write of any kind against a *.credentials.json path —
    every write primitive is trapped for the duration, and the bytes are compared after."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    before = {slug: (fleet / slug / ".credentials.json").read_bytes() for slug in ("seo", "intel")}

    def _no_cred(target):
        assert ".credentials.json" not in str(target), f"credential write during a flip: {target}"

    real_write_bytes, real_write_text, real_open_p = Path.write_bytes, Path.write_text, Path.open
    real_os_open, real_replace, real_rename = os.open, os.replace, os.rename
    real_copy, real_copy2, real_copyfile, real_move = (
        shutil.copy,
        shutil.copy2,
        shutil.copyfile,
        shutil.move,
    )
    monkeypatch.setattr(
        Path, "write_bytes", lambda self, *a, **k: _no_cred(self) or real_write_bytes(self, *a, **k)
    )
    monkeypatch.setattr(
        Path, "write_text", lambda self, *a, **k: _no_cred(self) or real_write_text(self, *a, **k)
    )

    def guarded_open(self, mode="r", *a, **k):
        if any(c in mode for c in "wax+"):
            _no_cred(self)
        return real_open_p(self, mode, *a, **k)

    monkeypatch.setattr(Path, "open", guarded_open)

    def guarded_os_open(path, flags, *a, **k):
        if flags & (os.O_WRONLY | os.O_RDWR):
            _no_cred(path)
        return real_os_open(path, flags, *a, **k)

    monkeypatch.setattr(os, "open", guarded_os_open)
    monkeypatch.setattr(
        os, "replace", lambda src, dst, **k: _no_cred(dst) or real_replace(src, dst, **k)
    )
    monkeypatch.setattr(
        os, "rename", lambda src, dst, **k: _no_cred(dst) or real_rename(src, dst, **k)
    )
    monkeypatch.setattr(
        shutil, "copy", lambda src, dst, **k: _no_cred(dst) or real_copy(src, dst, **k)
    )
    monkeypatch.setattr(
        shutil, "copy2", lambda src, dst, **k: _no_cred(dst) or real_copy2(src, dst, **k)
    )
    monkeypatch.setattr(
        shutil, "copyfile", lambda src, dst, **k: _no_cred(dst) or real_copyfile(src, dst, **k)
    )
    monkeypatch.setattr(
        shutil, "move", lambda src, dst, **k: _no_cred(dst) or real_move(src, dst, **k)
    )
    # F-P3 evasion probes closed: hardlinks, credential-path symlinks, and shelling out
    # (cp/mv/install/dd — ANY argv naming a credential path) are trapped too.
    real_link, real_symlink = os.link, os.symlink

    def guarded_link(src, dst, **k):
        _no_cred(src)
        _no_cred(dst)
        return real_link(src, dst, **k)

    def guarded_symlink(src, dst, **k):
        _no_cred(src)
        _no_cred(dst)
        return real_symlink(src, dst, **k)

    monkeypatch.setattr(os, "link", guarded_link)
    monkeypatch.setattr(os, "symlink", guarded_symlink)

    def _no_cred_argv(argv):
        if isinstance(argv, (list, tuple)):
            for a in argv:
                _no_cred(a)
        else:
            _no_cred(argv)

    for sub_name in ("run", "check_call", "check_output", "Popen", "call"):
        real_sub = getattr(subprocess, sub_name)
        monkeypatch.setattr(
            subprocess,
            sub_name,
            lambda argv, *a, __real=real_sub, **k: _no_cred_argv(argv) or __real(argv, *a, **k),
        )

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "intel", "the flip must actually have happened"
    for slug, blob in before.items():
        assert (fleet / slug / ".credentials.json").read_bytes() == blob, (
            f"{slug}'s credential bytes changed across a flip"
        )


# ── B13: flip-path liveness (F-P1), validate-before-flip (F-P2), identity net (F-P4) ──────────


def test_flip_refuses_an_expired_chain_auto_and_manual(tmp_path, monkeypatch, capsys):
    """F-P1: file presence is not usability — a chain whose refresh token is expired must never
    become the fleet's pointer, MANUAL included (one dead pointer = fleet-wide auth outage)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo")
    _fleet_creds(fleet, "intel", "tok-intel", refresh_expires_s=-3 * 3600.0)  # expired 3h ago
    _point(fleet, "seo")
    capsys.readouterr()

    assert not cr._flip_active("intel", manual=True), "a manual flip to a dead chain is refused"
    err = capsys.readouterr().err
    assert "refresh token expired" in err, "the refusal must carry the module's own stale reason"
    assert "/login" in err, "the refusal must name the revival path"
    assert not cr._flip_active("intel"), "the auto path refuses the same chain"
    assert os.readlink(fleet / "active") == "seo", "the pointer never moved"
    assert cr.main(["--switch", "intel"]) == 1, "fleet --switch inherits the liveness gate"
    assert os.readlink(fleet / "active") == "seo"


def test_selector_skips_an_expired_chain_that_ranks_best_on_quota(tmp_path, monkeypatch, capsys):
    """F-P1: the auto-selector must exclude a dead chain even when its (cached or live) quota
    reading makes it the most attractive successor — quota headroom on a chain that cannot
    authenticate is not headroom."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    # ob@'s chain is EXPIRED but its reading (10/10) ranks far ahead of sarp's (96/50)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0, refresh_expires_s=-3 * 3600.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "seo", "a dead chain is never chosen, however rosy"
    assert "NO successor has headroom" in capsys.readouterr().out


def test_status_warns_when_a_chain_nears_expiry(tmp_path, monkeypatch, capsys):
    """F-P1: a dying chain must be visible on --status BEFORE it silently drops out of flip
    candidacy — under 5d to expiry (the keepalive's 7d cadence has already missed it)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0, refresh_expires_s=3 * 86400.0)  # 3d left
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)  # 30d left → silent
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(42.0, 31.0), "tok-intel": _usage_blob(7.0, 9.0)},
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out
    assert "sarp@ocoron.com: refresh chain expires in 3.0d" in out
    assert "ob@ocoron.com: refresh chain expires" not in out, "a healthy chain warns nothing"

    assert cr.main(["--status", "--json"]) == 0
    rows = {r["email"]: r for r in json.loads(capsys.readouterr().out)["accounts"]}
    assert rows["sarp@ocoron.com"]["refresh_expires_epoch"] == FLEET_NOW + 3 * 86400.0

    # …and the tick prints the same warning (the cron log is where an operator will see it)
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    assert "refresh chain expires in 3.0d" in capsys.readouterr().out


@pytest.mark.parametrize("live_probe", [None, "walled"])
def test_flip_validates_a_cached_candidate_before_flipping(
    tmp_path, monkeypatch, capsys, live_probe
):
    """F-P2: a candidate ranked off a CACHED reading gets ONE live usage probe before the fleet
    is pointed at it. Probe failure (None) or a walled live reading → excluded, next-best
    chosen. Cached-and-unverifiable must never become the fleet's sole pointer."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    for slug, email in (("a", "a@ocoron.com"), ("b", "b@ocoron.com"), ("c", "c@ocoron.com")):
        assert cr.main(["--new-dir", slug, email]) == 0
        _pin(fleet, slug, email)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    _fleet_creds(fleet, "a", "tok-a", age_s=60.0)  # active, over threshold (live)
    _fleet_creds(fleet, "b", "tok-b", age_s=10 * 3600.0)  # idle >8h → CACHED reading used
    _fleet_creds(fleet, "c", "tok-c", age_s=60.0)  # live, modest headroom
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-usage-cache.json").write_text(
        json.dumps(
            {
                "b@ocoron.com": {  # rosy STALE cache — ranks b@ best on quota
                    "ts": FLEET_NOW - 9 * 3600.0,
                    "five_hour": {"utilization": 5.0, "resets_at_epoch": FLEET_NOW + 3600},
                    "seven_day": {"utilization": 5.0, "resets_at_epoch": FLEET_NOW + 86400},
                }
            }
        )
    )
    usages = {"tok-a": _usage_blob(96.0, 50.0), "tok-c": _usage_blob(20.0, 20.0)}
    if live_probe == "walled":
        usages["tok-b"] = _usage_blob(100.0, 100.0)  # the rosy cache hid a wall
    calls = _fake_oauth(monkeypatch, usages=usages)  # live_probe=None: tok-b probe returns None
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "a")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "c", "the unverifiable/walled cache loses to c@"
    assert ("usage", "tok-b") in calls, "the cached candidate got exactly its ONE live probe"
    assert calls.count(("usage", "tok-b")) == 1


def test_identity_mismatch_probe_email_warns_loudly(tmp_path, monkeypatch, capsys):
    """F-P4: the mid-refresh-race / wrong-dir-login NET, zero-cost usage-payload leg — a dir
    whose already-made probe answers as a DIFFERENT account than its pinned identity gets a
    LOUD warning naming the dir, both emails, and the /login recovery; a matching probe stays
    silent. NB: probed live 2026-08-15 the real usage payload carries NO account.email, so this
    leg is dormant on today's API shape — the LIVE leg is the hourly profile probe (F-P6,
    test_identity_net_live_leg_fires_via_hourly_profile_probe); this test pins the wiring that
    upgrades for free if the field ever appears."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    for slug, email in (("seo", "sarp@ocoron.com"), ("intel", "ob@ocoron.com")):
        assert cr.main(["--new-dir", slug, email]) == 0
        _pin(fleet, slug, email)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={
            # seo is pinned to sarp@ but its token answers as ob@ — the crossed-chain signature
            "tok-seo": {**_usage_blob(42.0, 31.0), "account": {"email": "ob@ocoron.com"}},
            # intel matches its pin — must stay silent
            "tok-intel": {**_usage_blob(7.0, 9.0), "account": {"email": "ob@ocoron.com"}},
        },
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out
    warn_lines = [line for line in out.splitlines() if "IDENTITY MISMATCH" in line]
    assert len(warn_lines) == 1, "exactly the mismatched dir warns; the matching one is silent"
    warn = warn_lines[0]
    assert "seo" in warn and "sarp@ocoron.com" in warn and "ob@ocoron.com" in warn
    assert "/login" in warn and "do NOT copy" in warn

    # the tick prints the same net (the 5-min cron log is the operator's surface)
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    assert "IDENTITY MISMATCH" in capsys.readouterr().out


# ── B14: F-P6 — the identity net's LIVE leg: one bounded profile probe per account per hour ───
# Probed live 2026-08-15: /api/oauth/usage payloads carry NO account.email, so the usage-payload
# leg above is dormant on today's API shape. These pin the leg that actually fires.


def _identity_fleet(tmp_path, monkeypatch, profiles=None):
    """One pinned account (seo → sarp@) with a fresh token and a REALISTIC usage payload (no
    account.email). Returns (fleet, calls)."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    _pin(fleet, "seo", "sarp@ocoron.com")
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    calls = _fake_oauth(
        monkeypatch, usages={"tok-seo": _usage_blob(42.0, 31.0)}, profiles=profiles or {}
    )
    return fleet, calls


def test_identity_net_live_leg_fires_via_hourly_profile_probe(tmp_path, monkeypatch, capsys):
    """F-P6: the hourly profile probe IS the net's live leg — a wrong-account answer warns
    loudly even though the usage payload (realistically) carries no email; and the verdict is
    STICKY: the very next pass still warns without a second probe."""
    _fleet, calls = _identity_fleet(
        tmp_path, monkeypatch, profiles={"tok-seo": {"account": {"email": "ob@ocoron.com"}}}
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out
    warn_lines = [line for line in out.splitlines() if "IDENTITY MISMATCH" in line]
    assert len(warn_lines) == 1, "the profile leg must fire the warning on its own"
    assert "seo" in warn_lines[0] and "sarp@ocoron.com" in warn_lines[0]
    assert "ob@ocoron.com" in warn_lines[0] and "/login" in warn_lines[0]

    assert cr.main(["--status"]) == 0
    out2 = capsys.readouterr().out
    assert "IDENTITY MISMATCH" in out2, "the recorded verdict must be sticky between probes"
    assert [c for c in calls if c[0] == "profile"] == [("profile", "tok-seo")], (
        "stickiness comes from the recorded verdict, never a second probe inside the hour"
    )


def test_identity_probe_budget_is_one_per_account_per_hour(tmp_path, monkeypatch, capsys):
    """F-P6: two passes inside the hour → exactly ONE profile probe; stamp aged past the hour
    → the next pass probes again."""
    fleet, calls = _identity_fleet(
        tmp_path, monkeypatch, profiles={"tok-seo": {"account": {"email": "sarp@ocoron.com"}}}
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    assert cr.main(["--status"]) == 0
    assert [c for c in calls if c[0] == "profile"] == [("profile", "tok-seo")], (
        "two passes inside the hour must spend exactly ONE profile probe"
    )
    assert "IDENTITY MISMATCH" not in capsys.readouterr().out, "a matching answer is silent"

    stamp = cr._identity_probe_stamp("seo")
    aged = FLEET_NOW - 3700.0
    os.utime(stamp, (aged, aged))
    assert cr.main(["--status"]) == 0
    assert [c for c in calls if c[0] == "profile"] == [
        ("profile", "tok-seo"),
        ("profile", "tok-seo"),
    ], "a stamp older than an hour re-arms the probe"


def test_identity_probe_failure_retries_and_stays_silent(tmp_path, monkeypatch, capsys):
    """F-P6: a transport failure neither warns (a blip is not a mismatch) nor stamps (the next
    tick retries — a blip must not silence the net for an hour)."""
    fleet, calls = _identity_fleet(tmp_path, monkeypatch)  # profiles absent → probe fails
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out

    assert "IDENTITY MISMATCH" not in out
    assert not cr._identity_probe_stamp("seo").exists(), (
        "a failed probe must not consume the hourly budget"
    )
    assert [c for c in calls if c[0] == "profile"] == [
        ("profile", "tok-seo"),
        ("profile", "tok-seo"),
    ], "both passes must RETRY the failed probe"


def test_identity_probe_future_skewed_stamp_reads_due(tmp_path, monkeypatch, capsys):
    """F-P6: a stamp mtime AHEAD of now beyond the skew tolerance is INVALID and reads DUE
    (the advisory-stamp convention) — and the probe rewrites it at now."""
    fleet, calls = _identity_fleet(
        tmp_path, monkeypatch, profiles={"tok-seo": {"account": {"email": "sarp@ocoron.com"}}}
    )
    stamp = cr._identity_probe_stamp("seo")
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("sarp@ocoron.com\n")
    future = FLEET_NOW + 5 * 86400
    os.utime(stamp, (future, future))
    capsys.readouterr()

    assert cr.main(["--status"]) == 0

    assert [c for c in calls if c[0] == "profile"] == [("profile", "tok-seo")], (
        "a future-dated stamp must not silence the probe"
    )
    assert stamp.stat().st_mtime == FLEET_NOW, "the invalid stamp must be rewritten at now"


# ── B15: round-3 — unconditional verdict reporting, self-flip no-op, per-dir stamps ───────────


def test_identity_mismatch_warning_survives_dir_idling(tmp_path, monkeypatch, capsys):
    """F-P7 (the coordinator's probe scenario): warn → the corrupted dir idles past the 8h
    freshness window → STILL warns — the freshness gate governs NEW probes only, and the
    LIKELY aftermath of a corrupted dir is that it goes idle. Recovery (/login = fresh file +
    matching probe) clears it."""
    profiles = {"tok-seo": {"account": {"email": "ob@ocoron.com"}}}
    fleet, calls = _identity_fleet(tmp_path, monkeypatch, profiles=profiles)
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    assert "IDENTITY MISMATCH" in capsys.readouterr().out

    creds = fleet / "seo" / ".credentials.json"
    aged = FLEET_NOW - 9 * 3600.0
    os.utime(creds, (aged, aged))  # +9h: the dir has idled past _FLEET_TOKEN_FRESH_S
    assert cr.main(["--status"]) == 0
    assert "IDENTITY MISMATCH" in capsys.readouterr().out, (
        "an idle dir's recorded mismatch must keep warning, not vanish at the 8h mark"
    )
    assert [c for c in calls if c[0] == "profile"] == [("profile", "tok-seo")], (
        "no new probe on a stale token — the warning must come from the stored verdict"
    )

    # recovery: ONE /login re-mints the chain (fresh file, new token); once the hourly budget
    # re-arms, the probe re-verifies THAT dir and the warning clears
    _fleet_creds(fleet, "seo", "tok-seo2", age_s=60.0)
    profiles["tok-seo2"] = {"account": {"email": "sarp@ocoron.com"}}
    stamp = cr._identity_probe_stamp("seo")
    old = FLEET_NOW - 3700.0
    os.utime(stamp, (old, old))
    assert cr.main(["--status"]) == 0
    assert "IDENTITY MISMATCH" not in capsys.readouterr().out, "re-verification must clear it"
    assert ("profile", "tok-seo2") in calls


def test_self_flip_on_a_decayed_active_chain_is_a_noop_success(tmp_path, monkeypatch, capsys):
    """F-P8: --switch <already-active-slug> keeps the documented no-op-success contract even
    when the active chain has decayed IN PLACE — the pointer does not move, so there is
    nothing to gate; the decay is SURFACED as a stderr warning, never a failure (a flip to a
    DIFFERENT dead dir stays refused — test_flip_refuses_an_expired_chain_auto_and_manual)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", refresh_expires_s=-3 * 3600.0)  # decayed in place
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr.main(["--switch", "seo"]) == 0, "self-flip is a no-op success, decay or not"
    captured = capsys.readouterr()
    assert "pointer flip" in captured.out
    assert "WARNING" in captured.err
    assert "refresh token expired" in captured.err and "/login" in captured.err
    assert os.readlink(fleet / "active") == "seo"
    assert cr._flip_active("seo", manual=True), "direct manual self-flip: same contract"
    assert cr._flip_active("seo"), "auto self-flip: same contract (nothing moves)"


def test_sibling_dir_mismatch_survives_a_fresh_pin(tmp_path, monkeypatch, capsys):
    """F-P9: verdict stamps are keyed by SLUG, so a fresh pin on a NEW dir of the same account
    can never overwrite a sibling dir's unresolved mismatch. (The email-keyed collision class
    — two emails sanitizing identically sharing one stamp — is moot by construction: slugs are
    _SLUG_RE-validated kebab, on which the sanitize regex is the identity function, and two
    distinct dirs are two distinct slugs.)"""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    _pin(fleet, "seo", "sarp@ocoron.com")
    assert cr.main(["--new-dir", "youtube", "sarp@ocoron.com"]) == 0  # pending → will pin now
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    monkeypatch.setattr(cr, "_shared_bound_sessions", lambda *a, **k: 0)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=10 * 3600.0)  # the corrupted dir went idle
    _fleet_creds(fleet, "youtube", "tok-yt", age_s=60.0)  # the new dir, freshly logged in
    stamp = cr._identity_probe_stamp("seo")  # seo carries an unresolved mismatch verdict
    stamp.write_text("ob@ocoron.com\n")
    old = FLEET_NOW - 2 * 3600.0
    os.utime(stamp, (old, old))
    _fake_oauth(
        monkeypatch,
        profiles={"tok-yt": {"account": {"email": "sarp@ocoron.com"}}},
        usages={"tok-yt": _usage_blob(10.0, 10.0)},
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out
    warn_lines = [line for line in out.splitlines() if "IDENTITY MISMATCH" in line]
    assert len(warn_lines) == 1, "exactly seo warns; the freshly-pinned youtube is silent"
    assert "seo" in warn_lines[0] and "ob@ocoron.com" in warn_lines[0], (
        "the pin on youtube must not mask seo's unresolved mismatch"
    )


# ── B16: F-P10 — fleet mode structurally retires the LEGACY credential installer ──────────────
# Rollout analysis: the pause marker was the ONLY barrier between run_claude's 401-retry (and
# --next) and _rotate_active_account's file-swap install into ~/.claude — and the rollout
# removes the marker. The guard is structural (fleet dirs exist → refuse, BEFORE the pause
# check), while the empty-fleet box keeps legacy behavior byte-unchanged (the capture-suite
# sandbox pins that, now hermetically).


def test_fleet_mode_structurally_retires_the_legacy_installer(tmp_path, monkeypatch, capsys):
    fleet, cdir, _home = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "ob", "ob@ocoron.com"]) == 0
    _fleet_creds(fleet, "ob", "tok-ob")
    # a legacy snapshot pool that WOULD be installable pre-fleet (2 live snapshots)
    stores = tmp_path / "manager-accounts"
    for name in ("ob-ocoron-com", "sarp-ocoron-com"):
        d = stores / name
        d.mkdir(parents=True)
        (d / ".credentials.json").write_text(
            json.dumps(
                {
                    "claudeAiOauth": {
                        "accessToken": f"TOK-{name}",
                        "refreshToken": f"R-{name}",
                        "expiresAt": int((FLEET_NOW + 3600) * 1000),
                        "refreshTokenExpiresAt": int((FLEET_NOW + 30 * 86400) * 1000),
                    }
                }
            )
        )
    monkeypatch.setattr(cr, "ACCOUNTS_DIR", stores)
    monkeypatch.setattr(cr, "ACTIVE_MARKER", tmp_path / ".active-account")
    monkeypatch.setattr(cr, "ALERT_STATE", tmp_path / "last-401-alert")
    alerts = []
    monkeypatch.setattr(cr, "_notify_telegram", lambda text: alerts.append(text) or True)
    installs = []
    monkeypatch.setattr(cr, "_activate_snapshot", lambda *a, **k: installs.append(a) or "x")

    def fake_run(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, "401 authentication failed", "")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    capsys.readouterr()

    # (1) run_claude's 401-retry path: rotation refused structurally, no install, no retry
    result = cr.run_claude(["claude", "-p", "hi"], timeout=5, cwd="/", env={})
    err = capsys.readouterr().err
    assert installs == [], "fleet mode must never install a credential file into ~/.claude"
    assert result.returncode == 1
    assert "fleet mode is live" in err and "pointer flip" in err
    assert alerts and "fleet mode" in alerts[0], (
        "the 401 alert stays ARMED (unlike the pause marker) and names the fleet-mode cause"
    )

    # (2) the guard is FIRST-STATEMENT-CLASS: with the pause marker PRESENT the refusal is
    # still the structural one, not the marker (removing the marker changes nothing)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "switch-paused").touch()
    capsys.readouterr()
    assert cr._rotate_active_account() is None
    err = capsys.readouterr().err
    assert "fleet mode is live" in err and "PAUSED" not in err
    assert getattr(cr._TLS, "withheld_reason", None) == cr._WITHHELD_FLEET
    (state / "switch-paused").unlink()

    # (3) --next inherits the guard: rc 1, no misleading "need ≥2 snapshots" hint
    capsys.readouterr()
    assert cr._cmd_next() == 1
    err = capsys.readouterr().err
    assert "fleet mode is live" in err and "need ≥2 snapshots" not in err

    # (4) the LEGACY --switch form (manager-accounts snapshot name) is unreachable in fleet
    # mode — the dispatch resolves against fleet dirs only, and no install can happen
    capsys.readouterr()
    assert cr.main(["--switch", "sarp-ocoron-com"]) == 1
    assert "no unique fleet dir" in capsys.readouterr().err
    assert installs == []
    assert cr.main(["--switch", "ob"]) == 0, "the fleet flip form stays the live lever"
    assert os.readlink(fleet / "active") == "ob"

    # (5) structural: the guard exists at the choke point
    assert "_fleet_dirs" in cr._rotate_active_account.__code__.co_names


# ── B16: per-account weekly caps — caps.json reserves quota for operator browser use ──────────
# Operator contract (2026-08-15): "do not consume ob@'s weekly quota more than 90% — I also use
# it in the claude.ai browser regularly." <fleet_root>/caps.json = {"email": cap%}; at/over the
# cap an account is flipped away from and excluded from automated selection; manual --switch,
# keepalive and the identity/liveness nets ignore caps.


def _caps(fleet, table):
    (fleet / "caps.json").write_text(json.dumps(table))


def test_account_caps_loader_clamps_skips_and_fails_soft(tmp_path, monkeypatch, capsys):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    fleet.mkdir(parents=True, exist_ok=True)
    assert cr._account_caps() == {}, "no caps.json → no caps (regression: today's behavior)"
    _caps(
        fleet,
        {"ob@ocoron.com": 90, "hi@x.com": 150, "lo@x.com": -5, "bad@x.com": "ninety"},
    )
    capsys.readouterr()
    caps = cr._account_caps()
    err = capsys.readouterr().err
    assert caps == {"ob@ocoron.com": 90, "hi@x.com": 100, "lo@x.com": 1}, (
        "values clamp to 1..100; non-numeric entries are skipped"
    )
    assert "bad@x.com" in err and "caps.json" in err, "a skipped entry warns, naming the file"
    # unparseable file: loud warning naming the file, and rotation proceeds UNCAPPED
    (fleet / "caps.json").write_text("{not json")
    capsys.readouterr()
    assert cr._account_caps() == {}
    assert "caps.json" in capsys.readouterr().err, "a broken caps file must never be silent"
    # wrong shape (a list) is the same contract
    (fleet / "caps.json").write_text("[90]")
    capsys.readouterr()
    assert cr._account_caps() == {}
    assert "caps.json" in capsys.readouterr().err


def test_cap_walled_candidate_is_excluded_even_when_best_by_weekly(tmp_path, monkeypatch, capsys):
    """ob ranks BEST by weekly headroom but sits at/over its cap → the flip must pick the
    worse-by-weekly uncapped account instead (cap-walled = walled, same choke point)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "mob", "mob@ocoron.com"]) == 0
    _pin(fleet, "mob", "mob@ocoron.com")
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fleet_creds(fleet, "mob", "tok-mob", age_s=60.0)
    _caps(fleet, {"ob@ocoron.com": 15})
    _fake_oauth(
        monkeypatch,
        usages={
            "tok-seo": _usage_blob(96.0, 50.0),  # active, over threshold
            "tok-intel": _usage_blob(10.0, 20.0),  # ob: best weekly, but 20 ≥ cap 15
            "tok-mob": _usage_blob(10.0, 60.0),  # worse weekly, uncapped
        },
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "mob", (
        "a cap-walled account is never an automated flip target, however good its weekly"
    )


def test_active_flips_away_at_weekly_cap_with_session_low(tmp_path, monkeypatch, capsys):
    """The flip-away leg: weekly ≥ cap trips the flip even though BOTH windows sit below
    ROTATE_THRESHOLD — the remainder is the operator's browser reserve."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(fleet, {"sarp@ocoron.com": 90})
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(50.0, 91.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out

    assert os.readlink(fleet / "active") == "intel", "weekly ≥ cap must flip the pointer away"
    assert "cap 90" in out, "the flip line must name the cap that tripped it"


def test_active_below_cap_and_threshold_never_flips(tmp_path, monkeypatch, capsys):
    """Session threshold is UNCHANGED by a cap: weekly under cap + session under threshold →
    no flip (the cap only tightens the WEEKLY leg)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(fleet, {"sarp@ocoron.com": 90})
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(50.0, 89.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "seo", "under cap AND under threshold → no flip"


def test_near_threshold_candidate_is_excluded_from_selection(tmp_path, monkeypatch, capsys):
    """Adjacent churn fix: a candidate already ≥ ROTATE_THRESHOLD on EITHER window is never
    picked — flipping to a 99%-session account just trips the flip-away next tick."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(99.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out

    assert os.readlink(fleet / "active") == "seo", (
        "a 99%-session sibling is pointless churn, never a flip target"
    )
    assert "NO successor has headroom" in out


def test_corrupt_caps_json_warns_and_rotation_proceeds_uncapped(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    (fleet / "caps.json").write_text("{broken")
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(96.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    captured = capsys.readouterr()

    assert os.readlink(fleet / "active") == "intel", (
        "a broken caps file must never HALT rotation — it proceeds uncapped"
    )
    assert "caps.json" in captured.err, "…but it must never be silent either"


def test_status_shows_the_cap_and_the_cap_walled_marker(tmp_path, monkeypatch, capsys):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(fleet, {"sarp@ocoron.com": 90})
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(50.0, 91.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out

    sarp_line = next(line for line in out.splitlines() if "sarp@ocoron.com" in line)
    assert "(cap 90)" in sarp_line, "a capped account's row must show its cap"
    assert "cap-walled" in out and "reserved for operator use until weekly reset" in out

    assert cr.main(["--status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_email = {r["email"]: r for r in payload["accounts"]}
    assert by_email["sarp@ocoron.com"]["weekly_cap"] == 90
    assert by_email["sarp@ocoron.com"]["cap_walled"] is True
    assert by_email["ob@ocoron.com"]["weekly_cap"] is None
    assert by_email["ob@ocoron.com"]["cap_walled"] is False


def test_manual_switch_to_a_capped_account_succeeds_with_a_warning(tmp_path, monkeypatch, capsys):
    """The cap NEVER binds the operator: --switch to a capped account is honored — with one
    line naming the cap (their deliberate act, same escape-hatch contract as pause)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(fleet, {"ob@ocoron.com": 90})
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr.main(["--switch", "intel"]) == 0, "a cap must never refuse a manual switch"
    out = capsys.readouterr().out

    assert os.readlink(fleet / "active") == "intel"
    assert "pointer flip" in out
    assert "cap" in out and "90" in out, "the override prints one line naming the cap"


def test_all_capped_or_walled_fires_the_drain_advisory(tmp_path, monkeypatch, capsys):
    """Cap-walled counts as unavailable exactly like walled: with every sibling capped-or-walled
    nothing flips and the ≥85% drain advisory fires, exactly as today."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(fleet, {"ob@ocoron.com": 40})
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(96.0, 96.0), "tok-intel": _usage_blob(10.0, 50.0)},
    )
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out

    assert os.readlink(fleet / "active") == "seo", "a cap-walled sibling is never a flip target"
    assert "NO successor has headroom" in out
    assert any("sarp@ocoron.com" in t for t in actions["telegrams"]), (
        "the drain advisory stays the recourse when everything is capped-or-walled"
    )


# ── B17: round-2 — shared exclusion predicate, case-normalized caps, trip attribution ─────────


def test_live_reverify_applies_the_same_churn_exclusion_as_the_selector(
    tmp_path, monkeypatch, capsys
):
    """F-C1: a stale-cached candidate (cached weekly 50) that live-verifies to a 97% session —
    under 100, under its cap, but ≥ ROTATE_THRESHOLD — must be excluded and the next-best
    chosen; returning it re-trips the flip-away next tick (the exact churn the selector's
    exclusion exists to prevent). One shared predicate covers both sites so they cannot drift."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "mob", "mob@ocoron.com"]) == 0
    _pin(fleet, "mob", "mob@ocoron.com")
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=10 * 3600.0)  # stale → cached row
    _fleet_creds(fleet, "mob", "tok-mob", age_s=10 * 3600.0)  # stale → cached row
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-usage-cache.json").write_text(
        json.dumps(
            {
                "ob@ocoron.com": {  # best by cached weekly — the rosy cache
                    "ts": FLEET_NOW - 3600.0,
                    "five_hour": {"utilization": 10.0, "resets_at_epoch": None},
                    "seven_day": {"utilization": 20.0, "resets_at_epoch": None},
                },
                "mob@ocoron.com": {
                    "ts": FLEET_NOW - 3600.0,
                    "five_hour": {"utilization": 10.0, "resets_at_epoch": None},
                    "seven_day": {"utilization": 60.0, "resets_at_epoch": None},
                },
            }
        )
    )
    _fake_oauth(
        monkeypatch,
        usages={
            "tok-seo": _usage_blob(96.0, 50.0),  # active, over threshold
            "tok-intel": _usage_blob(97.0, 50.0),  # live truth: session 97 ≥ threshold
            "tok-mob": _usage_blob(10.0, 60.0),  # live truth: clean
        },
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "mob", (
        "a cached-rosy candidate whose LIVE reading is ≥ threshold is churn, never the pick"
    )


def test_caps_keys_match_account_emails_case_insensitively(tmp_path, monkeypatch, capsys):
    """F-C2: {"SARP@ocoron.com": 90} must cap sarp@ocoron.com — keys and comparison emails
    normalize to lowercase at the loader boundary; a silent case mismatch violates the
    loader's own never-silent contract."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(fleet, {"SARP@ocoron.com": 90})
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(50.0, 91.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    capsys.readouterr()

    assert cr.main(["--status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_email = {r["email"]: r for r in payload["accounts"]}

    assert by_email["sarp@ocoron.com"]["weekly_cap"] == 90, "case must not defeat the cap"
    assert by_email["sarp@ocoron.com"]["cap_walled"] is True


def test_caps_key_matching_no_account_warns_cap_inactive(tmp_path, monkeypatch, capsys):
    """F-C2: a caps.json key that matches NO known account email (pinned identities +
    assignments accounts) is a typo doing nothing — it must warn, never sit silent."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _caps(fleet, {"ghost@nowhere.com": 50})
    _fake_oauth(monkeypatch, usages={"tok-seo": _usage_blob(42.0, 31.0)})
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out

    assert "ghost@nowhere.com" in out and "matches no account" in out and "cap inactive" in out
    # a key that DOES match (any case) must not false-fire the warning
    _caps(fleet, {"OB@ocoron.com": 90})
    capsys.readouterr()
    assert cr.main(["--status"]) == 0
    assert "matches no account" not in capsys.readouterr().out


def test_cap_trip_ledger_records_the_weekly_value_that_tripped(tmp_path, monkeypatch, capsys):
    """F-C3: session 93 / weekly 91 / cap 90 → the flip line says weekly ≥ cap, so the
    ledger's at_pct must record 91 (the tripping weekly), not hot=93 — misattributing the
    trigger poisons the audit trail."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(fleet, {"sarp@ocoron.com": 90})
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(93.0, 91.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "intel"
    lines = (tmp_path / "state" / "rotate-ledger.jsonl").read_text().splitlines()
    flip = next(e for e in map(json.loads, lines) if e.get("event") == "flip")
    assert flip["at_pct"] == 91.0, "at_pct must be the value that actually tripped (weekly)"


def test_selector_excludes_a_candidate_at_exactly_its_cap(tmp_path, monkeypatch, capsys):
    """F-C4 boundary: weekly == cap EXACTLY is cap-walled (≥, not >) at the SELECTOR layer —
    kills the >= → > mutant that the flip-away tests alone cannot see."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "mob", "mob@ocoron.com"]) == 0
    _pin(fleet, "mob", "mob@ocoron.com")
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fleet_creds(fleet, "mob", "tok-mob", age_s=60.0)
    _caps(fleet, {"ob@ocoron.com": 15})
    _fake_oauth(
        monkeypatch,
        usages={
            "tok-seo": _usage_blob(96.0, 50.0),  # active, over threshold
            "tok-intel": _usage_blob(10.0, 15.0),  # ob: weekly 15 == cap 15 exactly
            "tok-mob": _usage_blob(10.0, 60.0),  # worse weekly, uncapped
        },
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "mob", "weekly == cap exactly is already walled"


def test_active_flips_away_at_exactly_its_cap(tmp_path, monkeypatch, capsys):
    """F-C4 boundary: the flip-away leg trips at weekly == cap EXACTLY (90 == 90)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(fleet, {"sarp@ocoron.com": 90})
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(50.0, 90.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    assert os.readlink(fleet / "active") == "intel", "weekly == cap exactly must flip away"


# ── cron-PATH resolution for the `claude` ping (regression: 2026-08-22) ──
# A cron job runs with PATH=/usr/bin:/bin, which excludes ~/.local/bin where the
# CLI installs. Under cron the tick's `claude -p ping` raised FileNotFoundError
# and refresh/keepalive pings failed silently — every idle cred mtime stayed
# frozen and the dashboard caches aged past 85h. The env each ping builds must
# carry ~/.local/bin so `claude` resolves under cron exactly as in a login shell.
def test_with_claude_on_path_adds_local_bin_under_cron(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    out = cr._with_claude_on_path({"PATH": "/usr/bin:/bin"})
    local_bin = str(tmp_path / ".local" / "bin")
    parts = out["PATH"].split(os.pathsep)
    assert local_bin in parts, "cron PATH must gain ~/.local/bin so `claude` resolves"
    assert parts[0] == local_bin, "prepended so it wins binary resolution"


def test_with_claude_on_path_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    local_bin = str(tmp_path / ".local" / "bin")
    out = cr._with_claude_on_path({"PATH": f"{local_bin}{os.pathsep}/usr/bin"})
    assert out["PATH"].split(os.pathsep).count(local_bin) == 1, "no duplicate when already present"


def test_with_claude_on_path_handles_empty_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    out = cr._with_claude_on_path({})
    assert out["PATH"] == str(tmp_path / ".local" / "bin")


# ── _oauth_get bounded transient retry (regression: 2026-08-22 dashboard 60s timeout) ──
class _FakeResp:
    def __init__(self, body):
        self._b = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._b


def test_oauth_get_retries_transient_then_succeeds(monkeypatch):
    import urllib.request

    calls = {"n": 0}

    def fake(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("blip")
        return _FakeResp(b'{"ok": 1}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = cr._oauth_get("usage", "tok", attempts=2, backoff_s=0)
    assert out == {"ok": 1}
    assert calls["n"] == 2, "a transient blip must be retried, not surfaced as failure"


def test_oauth_get_does_not_retry_4xx(monkeypatch):
    import urllib.error
    import urllib.request

    calls = {"n": 0}

    def fake(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 401, "unauth", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = cr._oauth_get("usage", "tok", attempts=3, backoff_s=0)
    assert out is None
    assert calls["n"] == 1, "401 is definitive auth — never retried (burns the budget)"


def test_oauth_get_gives_up_after_attempts(monkeypatch):
    import urllib.request

    calls = {"n": 0}

    def fake(req, timeout=None):
        calls["n"] += 1
        raise TimeoutError("down")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = cr._oauth_get("usage", "tok", attempts=2, backoff_s=0)
    assert out is None
    assert calls["n"] == 2, "bounded — exactly `attempts` tries, then give up (fail-soft)"


# ── per-model weekly limits from the `limits` array (2026-08-22: Fable-5 visibility) ──
def test_usage_windows_captures_scoped_model_limits_from_limits_array():
    usage = {
        "five_hour": {"utilization": 10, "resets_at": None},
        "seven_day": {"utilization": 40, "resets_at": None},
        "limits": [
            {"kind": "session", "percent": 10, "scope": None},
            {"kind": "weekly_all", "percent": 40, "scope": None},  # == seven_day, NOT a model
            {
                "kind": "weekly_scoped",
                "percent": 6,
                "resets_at": None,
                "scope": {"model": {"id": None, "display_name": "Fable"}},
            },
        ],
    }
    out = cr._usage_windows(usage)
    mw = out["model_windows"]
    assert mw["Fable"]["utilization"] == 6.0, "Fable's weekly limit is read from limits[]"
    assert "weekly_all" not in mw and len(mw) == 1, (
        "unscoped weekly is the general one, not a model"
    )


def test_usage_windows_no_model_windows_key_when_no_scoped_limits():
    usage = {
        "five_hour": {"utilization": 1},
        "seven_day": {"utilization": 2},
        "limits": [{"kind": "weekly_all", "percent": 2, "scope": None}],
    }
    out = cr._usage_windows(usage)
    assert "model_windows" not in out, "no model-scoped limit → no key"


def test_usage_windows_still_fail_closed_on_bad_required_window():
    # a malformed required window still nulls the whole read — model limits never rescue it
    assert (
        cr._usage_windows(
            {
                "five_hour": {"utilization": "x"},
                "seven_day": {"utilization": 3},
                "limits": [
                    {
                        "kind": "weekly_scoped",
                        "percent": 9,
                        "scope": {"model": {"display_name": "Fable"}},
                    }
                ],
            }
        )
        is None
    )


# ── fabrik-lib's advisory-volume report (01M0DQ…, 2026-08-19): one FACT, one message ──


def test_no_advisory_churn_from_reset_jitter_while_a_sibling_has_headroom(tmp_path, monkeypatch):
    """The root cause of trade-intelligence 01M0YAB2 (mob@ 8x at a steady 95% on 2026-08-25):
    the per-account dedup keyed its cycle on a reset epoch that JITTERS/SLIDES tick-to-tick
    (the weekly reset crossing :59<->:00, the 5h reset sliding forward), so int(epoch) churned
    and the advisory re-fired every 5 minutes. The redesign removes the per-account advisory
    entirely — while ANY sibling has headroom the account crossing 95% is a non-event (the flip
    relieves it), so NO amount of reset jitter on the hot account can produce a single mail.
    Epoch-free by construction."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)

    def blob(weekly_reset_iso):
        # weekly reset jitters across the minute boundary — the exact 51181918 defect input.
        return {
            "five_hour": {"utilization": 95.0, "resets_at": "2027-01-20T00:00:00+00:00"},
            "seven_day": {"utilization": 95.0, "resets_at": weekly_reset_iso},
        }

    usages = {"tok-seo": blob("2027-01-22T20:59:59+00:00"), "tok-intel": _usage_blob(10.0, 10.0)}
    _fake_oauth(monkeypatch, usages=usages)
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik", "seo"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")

    # Tick repeatedly with the weekly reset flipping :59<->:00 — the old churn trigger.
    for reset_iso in (
        "2027-01-22T21:00:00+00:00",
        "2027-01-22T20:59:59+00:00",
        "2027-01-22T21:00:01+00:00",
    ):
        usages["tok-seo"] = blob(reset_iso)
        _fake_oauth(monkeypatch, usages=usages)
        assert cr._cmd_tick() == 0

    assert actions["telegrams"] == [], "reset jitter must produce ZERO advisories while headroom exists"
    assert actions["mails"] == [], "and zero mail — the spam class is structurally gone"


# ── operator rule 2026-09-03: "when we see 90% session limit reached and if no account is
# available we must send an URGENT mail to repos: stop your work asap gracefully and hook
# yourself to start 1 minute after next account session resets" ──────────────────────────────


def _row(email, session, weekly, cap=None, s_reset=None, w_reset=None, slug=None):
    return {
        "email": email,
        "slugs": [slug or email.split("@")[0]],
        "source": "live",
        "weekly_cap": cap,
        "five_hour": {"utilization": session, "resets_at_epoch": s_reset},
        "seven_day": {"utilization": weekly, "resets_at_epoch": w_reset},
    }


def test_next_session_relief_prefers_the_soonest_session_reset_of_a_weekly_ok_sibling():
    now = FLEET_NOW
    rows = [
        _row("act@x", 91.0, 40.0, cap=99, s_reset=now + 4000),  # the active — never its own relief
        _row("late@x", 97.0, 30.0, cap=90, s_reset=now + 9000, w_reset=now + 86400),
        _row("soon@x", 98.0, 27.0, cap=90, s_reset=now + 3000, w_reset=now + 90000),
        _row("wk@x", 0.0, 100.0, cap=99, s_reset=None, w_reset=now + 1000),  # weekly-walled
    ]
    assert cr._next_session_relief(rows, "act@x", now) == (now + 3000, "soon@x", "session")


def test_next_session_relief_falls_back_to_the_soonest_weekly_reset_when_every_sibling_is_weekly_blocked():
    now = FLEET_NOW
    rows = [
        _row("act@x", 91.0, 40.0, cap=99),
        _row("a@x", 5.0, 100.0, cap=99, s_reset=now + 100, w_reset=now + 5000),
        _row("b@x", 5.0, 96.0, cap=90, s_reset=now + 100, w_reset=now + 2000),  # cap-walled
    ]
    assert cr._next_session_relief(rows, "act@x", now) == (now + 2000, "b@x", "weekly")


def test_next_session_relief_skips_stale_past_resets_and_returns_none_when_nothing_is_known():
    now = FLEET_NOW
    assert cr._next_session_relief([_row("act@x", 91.0, 40.0), _row("a@x", 97.0, 10.0, s_reset=now - 5)], "act@x", now) is None
    assert cr._next_session_relief([_row("act@x", 91.0, 40.0)], "act@x", now) is None


def test_urgent_drain_message_carries_the_operator_wording_and_the_resume_instant():
    now = 1_800_000_000
    msg = cr._urgent_drain_message("act@x", 91.0, (float(now), "soon@x", "session"))
    assert "URGENT" in msg and "STOP YOUR WORK ASAP" in msg and "GRACEFULLY" in msg
    assert "1 MINUTE AFTER soon@x's session window resets" in msg
    assert f"epoch {now + 60}" in msg  # resume = reset + 60 s, stated as a number the agent can sleep on
    assert f"sleep $(( {now + 60} - $(date +%s) ))" in msg
    none = cr._urgent_drain_message("act@x", 91.0, None)
    assert "STOP YOUR WORK ASAP" in none and "no resume time can be given" in none


def test_urgent_tier_fires_at_ninety_with_no_successor_and_names_the_resume_time(tmp_path, monkeypatch):
    """The operator's rule end to end through the advisory: active at 91 session, every sibling
    unusable, → ONE telegram + ONE broadcast mail carrying the next session reset + 60 s; the
    latch then holds for the episode."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    now = FLEET_NOW
    rows = [
        _row("act@x", 91.0, 40.0, cap=99, slug="act"),
        _row("full@x", 97.0, 30.0, cap=90, s_reset=now + 1800, w_reset=now + 86400, slug="full"),
        _row("wall@x", 0.0, 100.0, cap=99, w_reset=now + 5000, slug="wall"),
    ]
    monkeypatch.setattr(cr, "_resolve_active", lambda: "act")
    monkeypatch.setattr(cr, "_switch_paused", lambda: False)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: None)
    tg, mails, ledger = [], [], []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m: tg.append(m))
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, m: mails.append((list(repos), m)))
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik", "seo"])
    monkeypatch.setattr(cr, "_ledger_append", lambda e: ledger.append(e))
    cr._fleet_active_wall_advisory(rows, now, threshold=95.0)
    assert len(tg) == 1 and len(mails) == 1, (tg, mails)
    assert mails[0][0] == ["fabrik", "seo"]
    assert "URGENT" in mails[0][1] and f"epoch {int(now + 1800) + 60}" in mails[0][1]
    assert ledger[-1]["tier"] == "urgent-90" and ledger[-1]["resume_epoch"] == int(now + 1800) + 60
    cr._fleet_active_wall_advisory(rows, now + 60, threshold=95.0)
    assert len(tg) == 1, "latched: one message per episode"


def test_urgent_tier_is_silent_below_ninety_and_while_a_successor_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    now = FLEET_NOW
    monkeypatch.setattr(cr, "_resolve_active", lambda: "act")
    monkeypatch.setattr(cr, "_switch_paused", lambda: False)
    tg = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m: tg.append(m))
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, m: tg.append(m))
    monkeypatch.setattr(cr, "_ledger_append", lambda e: None)
    # 89: below the urgent line even with nobody available
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: None)
    cr._fleet_active_wall_advisory([_row("act@x", 89.0, 40.0, cap=99, slug="act")], now, threshold=95.0)
    assert tg == []
    # 93 but a successor exists: the flip leg is the remedy, not the mail
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: ("fresh", "fresh@x"))
    cr._fleet_active_wall_advisory([_row("act@x", 93.0, 40.0, cap=99, slug="act"), _row("fresh@x", 5.0, 5.0, slug="fresh")], now, threshold=95.0)
    assert tg == []
