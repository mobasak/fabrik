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
