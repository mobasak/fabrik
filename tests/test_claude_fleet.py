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

import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "claude_rotate_fleet", REPO / "scripts" / "sysadmin" / "claude_rotate.py"
)
cr = importlib.util.module_from_spec(spec)
sys.modules["claude_rotate_fleet"] = cr
spec.loader.exec_module(cr)

# A session reading that TRIPS the flip line, whatever the line currently is. Derived, never
# typed: these fixtures were written with a literal 96.0 when the threshold was 95, and every one
# of them silently became a BELOW-the-line reading when the operator moved it to 98 (D-201) —
# ten tests failed for a stale fixture rather than a real defect. `+ 1.0` keeps the reading
# strictly over the line without reaching 100, which is a different branch (the wall).
OVER_LINE = cr._rotate_threshold() + 1.0

SENTINEL = "SENTINEL-ACCESS-TOKEN"


def _canonical(tmp_path, monkeypatch):
    """A fake ~/.claude + ~/.claude.json + an empty fleet root. Returns (fleet, cdir, home)."""
    home = tmp_path / "home"
    cdir = home / ".claude"
    for sub in ("agents", "commands", "skills", "projects", "sessions"):
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

    for name in ("agents", "commands", "skills", "projects", "sessions"):
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


def test_the_peer_registry_is_one_dir_across_every_account(tmp_path, monkeypatch):
    """The CLI lists peers from `<config dir>/sessions/<pid>.json`, resolved through the `active`
    pointer as it stands NOW, while each session wrote its record under the dir the pointer named
    when it STARTED — so a per-account `sessions/` emptied the whole box's peer list on every flip
    (2026-09-17: 18 sessions under one slug, one under another, one peer listed anywhere; D-287).
    A record written under any slug's dir must be the same file under every other slug's."""
    fleet, cdir, _home = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    assert cr.main(["--new-dir", "intel", "ob@ocoron.com"]) == 0
    (fleet / "seo" / "sessions" / "4242.json").write_text('{"pid": 4242, "name": "seo-1a"}')
    assert (
        fleet / "intel" / "sessions" / "4242.json"
    ).read_text() == '{"pid": 4242, "name": "seo-1a"}'
    assert (cdir / "sessions" / "4242.json").is_file()  # the one canonical inode, like projects/


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
    inode — which is why agents/, commands/, skills/, projects/ and sessions/ stay symlinks."""
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
    assert set(cr._SHARED_DIR_LINKS) == {"agents", "commands", "skills", "projects", "sessions"}


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


def _usage_blob(
    session=42.0,
    weekly=31.0,
    fable=None,
    session_reset="2027-01-20T00:00:00+00:00",
    weekly_reset="2027-01-22T00:00:00+00:00",
):
    """The usage endpoint's shape. ``fable`` adds the Fable weekly-scoped limit exactly as
    ``_usage_windows`` parses it (``limits[].kind == "weekly_scoped"``, ``scope.model.display_name``)."""
    blob = {
        "five_hour": {"utilization": session, "resets_at": session_reset},
        "seven_day": {"utilization": weekly, "resets_at": weekly_reset},
    }
    if fable is not None:
        blob["limits"] = [
            {
                "kind": "weekly_scoped",
                "scope": {"model": {"display_name": "Fable"}},
                "percent": fable,
                "resets_at": "2027-01-23T00:00:00+00:00",
            }
        ]
    return blob


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
    # round 2 seat C: the legacy view's guard had no grader — a revert to the bare conversion
    # survived the whole suite. Drive `--status` itself with the row the docstring narrates.
    row["seven_day"] = {"utilization": int("1" + "0" * 400), "resets_at_epoch": 1e300}
    assert cr._cmd_status(as_json=False) == 0
    assert capsys.readouterr().out == f"* {row['email']:32} session {session:24} weekly -\n"

    # …and ONE scaffolded dir must flip the same call into the fleet view (the dispatch seam)
    assert cr.main(["--new-dir", "seo", "sarp@ocoron.com"]) == 0
    capsys.readouterr()
    assert cr._cmd_status(as_json=False) == 0
    assert "fleet" in capsys.readouterr().out


# ── B10: --keepalive — RETIRED 2026-09-12: a ping never extends a chain; the flag is a no-op that says why ───────────────────────────


def test_keepalive_ping_runs_claude_in_place_and_never_reads_credential_bytes(
    tmp_path, monkeypatch
):
    """`_keepalive_ping` is KEPT for the tick's stale-reading refresh and it is the in-place
    SOLE-OWNER shape: `claude -p ping` with CLAUDE_CONFIG_DIR == CLAUDE_QUOTA_HOME == the dir
    itself, no temp-dir copy (a copy's refresh consumes the single-use refresh token — mob@
    2026-09-12), and not one credential byte read by this script."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "old", "sarp@ocoron.com"]) == 0
    creds = _fleet_creds(fleet, "old", "tok-old", age_s=8 * 86400.0)
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"], seen["env"] = list(argv), dict(kw["env"])
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)

    def no_copy(*a, **k):
        raise AssertionError("the in-place ping made a temp-dir copy")

    monkeypatch.setattr(cr.tempfile, "mkdtemp", no_copy)
    real_read_bytes, real_read_text = Path.read_bytes, Path.read_text

    def guarded_bytes(self, *a, **k):
        assert self.name != ".credentials.json", "ping read credential BYTES"
        return real_read_bytes(self, *a, **k)

    def guarded_text(self, *a, **k):
        assert self.name != ".credentials.json", "ping read credential BYTES"
        return real_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_bytes", guarded_bytes)
    monkeypatch.setattr(Path, "read_text", guarded_text)

    assert cr._keepalive_ping(fleet / "old") is True
    assert seen["argv"] == ["claude", "-p", "ping"]
    env = seen["env"]
    assert env["CLAUDE_CONFIG_DIR"] == env["CLAUDE_QUOTA_HOME"] == str(fleet / "old")
    assert env["CLAUDE_MESH_HEADLESS"] == "1" and env["CLAUDE_SOUND_NO_REVIVE"] == "1"
    assert real_read_text(creds)  # fixture intact, never opened by the ping


def test_keepalive_is_retired_spawns_nothing_and_says_why(tmp_path, monkeypatch, capsys):
    """2026-09-12: a `claude -p ping` never moves refreshTokenExpiresAt (measured on mob@), and
    the old mtime idle gate never fired anyway — so --keepalive pings NOTHING, exits 0 (the cron
    line keeps working) and prints the one line that says what replaced it."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "old", "sarp@ocoron.com"]) == 0
    _fleet_creds(fleet, "old", "tok-old", age_s=40 * 86400.0)  # 40 days idle: the old gate's DUE
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)

    def forbidden_run(argv, **kw):
        raise AssertionError(f"the retired keepalive spawned a process: {argv!r}")

    monkeypatch.setattr(cr.subprocess, "run", forbidden_run)

    def no_scan():
        raise AssertionError("the retired keepalive scanned the fleet dirs")

    monkeypatch.setattr(cr, "_fleet_dirs", no_scan)
    capsys.readouterr()

    assert cr.main(["--keepalive"]) == 0
    out = capsys.readouterr().out
    assert "RETIRED" in out and "/login" in out and "nothing pinged" in out
    assert len(out.splitlines()) == 1, "one cron-log line, nothing per dir"


def test_tick_never_calls_the_retired_keepalive_sweep(tmp_path, monkeypatch, capsys):
    """The tick used to fold the sweep in every 5 minutes; with the mechanism retired the tick
    must not spend a call on it (structural: the sweep symbol is not reached from the tick)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(10.0, 10.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    calls = []
    monkeypatch.setattr(cr, "_keepalive_sweep", lambda *a, **k: calls.append(a) or (0, 0))
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    assert calls == [], "the tick must not call the retired sweep"


# ── B11: the fleet tick — per-account advisory; legacy install machinery never touched ────────


def _fleet_tick_spies(monkeypatch):
    actions = {"switched": [], "picked": [], "telegrams": [], "mails": []}
    monkeypatch.setattr(cr, "_tick_switch", lambda name: actions["switched"].append(name) or True)
    monkeypatch.setattr(cr, "_pick_successor", lambda *a, **k: actions["picked"].append(a) or None)
    monkeypatch.setattr(
        cr, "_tick_telegram", lambda msg, **kw: actions["telegrams"].append(msg) or True
    )
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, msg: actions["mails"].extend(repos))
    return actions


def test_fleet_tick_pushes_once_per_chain_inside_three_days(tmp_path, monkeypatch, capsys):
    """A chain inside 3 d of its expiry (or past it) is pushed to the operator ONCE — the tick log
    is not read, and an unnoticed lapse becomes a fleet hold (2026-09-12). The stamp keys on the
    chain's expiry epoch: the same chain never pushes twice, a re-minted chain re-arms."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0, refresh_expires_s=4 * 86400.0)  # 4 d left
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)  # 30 d → silent
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(10.0, 10.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    capsys.readouterr()

    # 4 d: inside the 5 d WARNING, outside the 3 d PUSH — warned on stdout, nothing pushed
    assert cr._cmd_tick() == 0
    assert "sarp@ocoron.com: refresh chain expires in 4.0d" in capsys.readouterr().out
    assert [m for m in actions["telegrams"] if "refresh chain" in m] == []
    # exactly 3 d: the push window is strict (`exp - now >= _CHAIN_PUSH_S` → not yet)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0, refresh_expires_s=cr._CHAIN_PUSH_S)
    assert cr._cmd_tick() == 0
    assert [m for m in actions["telegrams"] if "refresh chain" in m] == []
    # 2 d: pushed, once
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0, refresh_expires_s=2 * 86400.0)
    assert cr._cmd_tick() == 0
    pushes = [m for m in actions["telegrams"] if "refresh chain" in m]
    assert len(pushes) == 1, "one push for the one chain inside 3 d"
    assert "sarp@ocoron.com" in pushes[0] and "/login as sarp@ocoron.com" in pushes[0]
    assert "ob@ocoron.com" not in pushes[0]

    assert cr._cmd_tick() == 0
    assert len([m for m in actions["telegrams"] if "refresh chain" in m]) == 1, (
        "the same chain never pushes twice"
    )

    # re-minted (a /login happened): a new expiry re-arms, and a fresh 30 d chain pushes nothing
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0, refresh_expires_s=30 * 86400.0)
    assert cr._cmd_tick() == 0
    assert len([m for m in actions["telegrams"] if "refresh chain" in m]) == 1
    # …and a NEW short chain (different expiry) pushes again, once
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0, refresh_expires_s=1 * 86400.0)
    assert cr._cmd_tick() == 0
    assert len([m for m in actions["telegrams"] if "refresh chain" in m]) == 2


def test_status_and_push_name_an_expired_chain_with_the_login_block(tmp_path, monkeypatch, capsys):
    """An ALREADY-expired chain gets the same remedy as a dying one: the EXPIRED warning carries
    the re-login block and says a claude turn does NOT extend it (the text used to omit that
    clause on this branch), and the push says EXPIRED."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0, refresh_expires_s=-3600.0)  # lapsed 1 h ago
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(10.0, 10.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out
    assert "sarp@ocoron.com: refresh chain EXPIRED 0.0d ago" in out
    assert "does NOT extend it" in out and "/login as sarp@ocoron.com" in out
    assert 'CLAUDE_CONFIG_DIR="$HOME/.claude-fleet/seo"' in out

    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: sent.append(m) or True)
    rows, _pending = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    assert cr._chain_expiry_push(rows, FLEET_NOW) == 1
    assert "EXPIRED" in sent[0] and "does NOT extend it" in sent[0]
    assert "/login as sarp@ocoron.com" in sent[0]


def test_chain_warning_and_push_name_the_dir_whose_chain_lapses_soonest(
    tmp_path, monkeypatch, capsys
):
    """An account pinned in several dirs: the block names the dir carrying the SOONEST expiry
    (`refresh_expires_slug`), not the alphabetically first member — a /login in the wrong dir
    leaves the warning firing and the push already stamped on the unchanged expiry."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)  # sarp@ is pinned in seo AND youtube
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)  # 30 d
    _fleet_creds(fleet, "youtube", "tok-yt", age_s=120.0, refresh_expires_s=2 * 86400.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={
            "tok-seo": _usage_blob(10.0, 10.0),
            "tok-yt": _usage_blob(10.0, 10.0),
            "tok-intel": _usage_blob(10.0, 10.0),
        },
    )
    capsys.readouterr()

    assert cr.main(["--status"]) == 0
    out = capsys.readouterr().out
    warn = [ln for ln in out.splitlines() if "refresh chain expires in 2.0d" in ln]
    assert len(warn) == 1 and "/.claude-fleet/youtube" in warn[0]
    assert '/.claude-fleet/seo"' not in warn[0]

    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    assert cr._cmd_tick() == 0
    pushes = [m for m in actions["telegrams"] if "refresh chain" in m]
    assert len(pushes) == 1 and "/.claude-fleet/youtube" in pushes[0]


def test_chain_push_stamps_only_a_delivered_notify(tmp_path, monkeypatch, capsys):
    """The stamp is written ONLY when the notifier reported delivery: a missing or failing
    `claude-sound.sh` used to be stamped as "pushed" and the chain was never retried — the
    2026-09-12 lapse with the new mechanism reporting success."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    row = {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400}
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)  # no notifier → the reason says so
    capsys.readouterr()
    assert cr._chain_expiry_push([row], FLEET_NOW) == 0
    assert cr._chain_expiry_push([row], FLEET_NOW) == 0, "unconfirmed → retried, never stamped"
    out = capsys.readouterr().out
    assert out.count("push UNCONFIRMED") == 2 and "unavailable" in out
    assert not cr._chain_push_stamp("sarp@ocoron.com").exists()

    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: sent.append(m) or True)
    assert cr._chain_expiry_push([row], FLEET_NOW) == 1
    assert cr._chain_expiry_push([row], FLEET_NOW) == 0 and len(sent) == 1


def test_tick_telegram_reports_delivery_from_the_notifier_artifact(tmp_path, monkeypatch):
    """`claude-sound.sh mesh-notify` exits 0 on EVERY outcome (suppressed, curl failure, no keys —
    0 non-zero exits in 325 lines) and writes `<lockdir>/<safe key>.notified` ONLY on a delivered
    send. So the verdict is the artifact: no script → False; a script that exits 0 without touching
    the artifact (the suppressed shape) → False; one that stamps it → True; a stale artifact from
    an earlier send does not count; and the key names the artifact, so the chain push's own key
    is never eaten by a rotation notification's window."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    locks = tmp_path / "locks"
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    assert cr._tick_telegram("x") is False, "no notifier at all"
    script = tmp_path / ".claude" / "bin" / "claude-sound.sh"
    # the autouse pin points CLAUDE_SOUND_SH at a path that does not exist; a test that
    # wants a real notifier names its own, which is what the pin's composability is for
    monkeypatch.setenv("CLAUDE_SOUND_SH", str(script))
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/bash\nexit 0\n")
    assert cr._tick_telegram("x") is False, "exit 0 without the artifact is NOT delivery"
    script.write_text(
        '#!/bin/bash\nmkdir -p "$CLAUDE_SOUND_LOCKDIR"\n'
        'printf "%s" "$(date +%s)" > "$CLAUDE_SOUND_LOCKDIR/$2.notified"\nexit 0\n'
    )
    assert cr._tick_telegram("x", key="k1") is True
    assert (locks / "k1.notified").is_file() and not (locks / "quota-rotation.notified").exists()
    script.write_text("#!/bin/bash\nexit 0\n")
    assert cr._tick_telegram("x", key="k1") is False, "the old artifact did not advance"
    assert cr._tick_telegram("x", key="k2") is False


def test_tick_telegram_reads_both_artifact_epochs_against_one_clock(tmp_path, monkeypatch):
    """Both artifact readings are judged against the ONE clock value taken before the call. Read
    against two clocks, an artifact just past the tolerance (stale after a backward clock step,
    or planted) reads 0 before the call and as itself after it — with NOTHING written — and a
    send that never happened is confirmed and its chain push stamped (review round 14,
    executed). A real write inside the tolerance still confirms against that same value."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    locks = tmp_path / "locks"
    locks.mkdir()
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    script = tmp_path / ".claude" / "bin" / "claude-sound.sh"
    # the autouse pin points CLAUDE_SOUND_SH at a path that does not exist; a test that
    # wants a real notifier names its own, which is what the pin's composability is for
    monkeypatch.setenv("CLAUDE_SOUND_SH", str(script))
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/bash\nexit 0\n")
    clock = iter([FLEET_NOW] + [FLEET_NOW + 10.0] * 8)
    monkeypatch.setattr(cr, "_now", lambda: next(clock))
    (locks / "k.notified").write_text(str(int(FLEET_NOW + cr._CLOCK_SKEW_TOLERANCE_S + 1)))
    assert cr._tick_telegram("x", key="k") is False, "nothing written — a moving limit confirmed"
    clock = iter([FLEET_NOW] + [FLEET_NOW + 10.0] * 8)
    monkeypatch.setattr(cr, "_now", lambda: next(clock))
    (locks / "k.notified").unlink()
    script.write_text(
        '#!/bin/bash\nprintf "%s" "'
        + str(int(FLEET_NOW + 5))
        + '" > "$CLAUDE_SOUND_LOCKDIR/$2.notified"\nexit 0\n'
    )
    assert cr._tick_telegram("x", key="k") is True


def test_tick_telegram_never_raises_on_an_unencodable_message(tmp_path, monkeypatch):
    """A lone surrogate in the message (JSON-parsed ledger text can carry one) made
    `subprocess.run` raise `UnicodeEncodeError` before the spawn (review round 15); catching it
    turned the push into a permanent silent miss (round 16). The message is escaped at the sink
    instead: the notifier runs, receives `\\ud800` in place of the surrogate, and the send is
    confirmed."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    locks = tmp_path / "locks"
    locks.mkdir()
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    script = tmp_path / ".claude" / "bin" / "claude-sound.sh"
    # the autouse pin points CLAUDE_SOUND_SH at a path that does not exist; a test that
    # wants a real notifier names its own, which is what the pin's composability is for
    monkeypatch.setenv("CLAUDE_SOUND_SH", str(script))
    script.parent.mkdir(parents=True)
    script.write_text(
        '#!/bin/bash\nprintf "%s" "$4" > "$CLAUDE_SOUND_LOCKDIR/seen.txt"\n'
        'printf "%s" "$(date +%s)" > "$CLAUDE_SOUND_LOCKDIR/$2.notified"\nexit 0\n'
    )
    assert cr._tick_telegram("push for \ud800bad", key="k") is True
    seen = (locks / "seen.txt").read_bytes().decode("utf-8")
    assert seen == "push for \\ud800bad", seen


@pytest.mark.skipif(not Path("/opt/fabrik/scripts/mail.py").is_file(), reason="no mail.py here")
def test_drain_mail_never_raises_on_an_unencodable_message(monkeypatch):
    """The drain writes the message into each send's TEXT pipe. A lone surrogate raised
    `UnicodeEncodeError` out of the tick (round 15); catching it per repo left EVERY spawned child
    on a never-closed pipe, each sending an EMPTY broadcast at the tick's death (round 16). Now the
    message is escaped once, every child receives it, and the write end is closed on every exit
    — a broken pipe included."""
    procs: list = []

    class FakeStdin:
        """A strict-UTF-8 text pipe end: `write` encodes as the real one does, `close` records."""

        def __init__(self, broken: bool = False):
            self.buf, self.closed, self.broken = b"", False, broken

        def write(self, text: str) -> int:
            if self.broken:
                raise BrokenPipeError
            self.buf += text.encode("utf-8")  # strict — a lone surrogate raises here
            return len(text)

        def close(self) -> None:
            self.closed = True
            if self.broken:
                raise BrokenPipeError  # the flush on close of a dead child's pipe

    class FakeProc:
        broken = False

        def __init__(self, *a, **k):
            self.stdin = FakeStdin(self.broken)
            procs.append(self)

    class BrokenProc(FakeProc):
        broken = True

    monkeypatch.setattr(cr.subprocess, "Popen", FakeProc)
    # `_drain_mail` resolves its SENDER through `_opt_dir()` now, not a hardcoded
    # /opt/fabrik/scripts/mail.py, so that one pin closes delivery as well as enumeration. A test
    # that wants the send attempted builds the sender inside its own pinned opt dir.
    sender = Path(str(cr._opt_dir())) / "fabrik" / "scripts" / "mail.py"
    sender.parent.mkdir(parents=True, exist_ok=True)
    sender.write_text("", encoding="utf-8")
    cr._drain_mail(["repo-a", "repo-b"], "fleet \ud800 exhausted")
    assert len(procs) == 2, "every repo attempted"
    for proc in procs:
        assert proc.stdin.closed, "the write end is released"
        assert proc.stdin.buf == b"fleet \\ud800 exhausted"
    procs.clear()
    monkeypatch.setattr(cr.subprocess, "Popen", BrokenProc)
    cr._drain_mail(["repo-a", "repo-b"], "fleet exhausted")
    assert len(procs) == 2 and all(p.stdin.closed for p in procs), "closed on a broken pipe too"


def test_keepalive_ping_survives_undecodable_output(tmp_path, monkeypatch):
    """`_keepalive_ping` captures the ping's text; a single invalid UTF-8 byte from `claude` raised
    `UnicodeDecodeError` past `(OSError, SubprocessError)` mid-liveness-pass (round 16, executed).
    The text is never read — only the status — so it is decoded with `errors="replace"`."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "claude").write_text("#!/bin/bash\nprintf '\\xff\\xfe bad\\n'\nexit 0\n")
    (fake_bin / "claude").chmod(0o755)
    monkeypatch.setattr(
        cr, "_with_claude_on_path", lambda env: env.__setitem__("PATH", str(fake_bin))
    )
    monkeypatch.setenv("KEEPALIVE_TIMEOUT", "20")
    assert cr._keepalive_ping(tmp_path) is True


def test_argv_safe_spells_out_what_argv_refuses():
    """`_argv_safe` exists for the two JSON-legal code points argv refuses — a lone surrogate
    (`UnicodeEncodeError`) and a NUL (`ValueError: embedded null byte`), neither an `OSError` — and
    spells a surrogateescape byte out the same way rather than restoring the raw byte (round 17,
    executed). Ordinary text, an em-dash and an emoji included, is returned byte-identical."""
    assert cr._argv_safe("push for \ud800bad") == "push for \\ud800bad"
    assert cr._argv_safe("a\x00b") == "a\\x00b"
    assert cr._argv_safe(b"dir\xff".decode("utf-8", "surrogateescape")) == "dir\\udcff"
    plain = "quota — rotation ✅ ünïcode 日本 back\\slash"
    assert cr._argv_safe(plain) == plain


def test_chain_push_uses_its_own_notify_key_per_account(tmp_path, monkeypatch):
    """Every rotation notification shares the notifier's 30-minute window under `quota-rotation`;
    the chain push passes its OWN per-account key so a flip or wall advisory in the same tick can
    never suppress it — and two accounts pushed in one tick never suppress each other."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(tmp_path / "locks"))
    keys = []
    monkeypatch.setattr(
        cr, "_tick_telegram", lambda m, key="quota-rotation": keys.append(key) or True
    )
    rows = [
        {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400},
        {"email": "ob@ocoron.com", "slugs": ["intel"], "refresh_expires_epoch": FLEET_NOW + 3600},
    ]
    assert cr._chain_expiry_push(rows, FLEET_NOW) == 2
    assert len(keys) == 2 and len(set(keys)) == 2
    assert all(k.startswith("quota-rotation-chain-") and k != "quota-rotation" for k in keys)


def test_chain_push_survives_a_garbage_stamp(tmp_path, monkeypatch):
    """A torn or non-UTF-8 stamp reads as ABSENT: the push proceeds and rewrites it — it used
    to raise UnicodeDecodeError out of `_chain_expiry_push` ("Never raises") and abort the rest of
    the tick every five minutes until someone deleted the file."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    row = {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400}
    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: sent.append(m) or True)
    stamp = cr._chain_push_stamp("sarp@ocoron.com")
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_bytes(b"\xff\xfe garbage")
    assert cr._chain_expiry_push([row], FLEET_NOW) == 1
    assert stamp.read_text() == str(int(FLEET_NOW + 86400))
    assert cr._chain_expiry_push([row], FLEET_NOW) == 0 and len(sent) == 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory modes")
def test_chain_push_says_so_and_repeats_when_the_state_dir_refuses_the_stamp(
    tmp_path, monkeypatch, capsys
):
    """There is ONE stamp home, the state dir; when it refuses the write (an existing read-only
    dir passes `mkdir(exist_ok=True)`) the push still goes out, the tick says the stamp is
    unwritable, and — with nothing to remember it by — the next tick pushes again, bounded in
    practice by the notifier's own 30-minute window per key. The documented repeat, never a
    silent one, and never a fallback home of its own (three review rounds showed each fallback
    dir adds a class of defect)."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    row = {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400}
    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: sent.append(m) or True)
    state.chmod(0o500)
    capsys.readouterr()
    try:
        assert cr._chain_expiry_push([row], FLEET_NOW) == 1
        assert cr._chain_expiry_push([row], FLEET_NOW) == 1, "nothing remembered it → pushed again"
        out = capsys.readouterr().out
        assert out.count("stamp unwritable") == 2 and "bounded by the notifier's window" in out
        assert len(sent) == 2
    finally:
        state.chmod(0o700)


def test_chain_push_degrades_when_the_state_dir_cannot_be_made(tmp_path, monkeypatch, capsys):
    """`_rotate_state_dir()` raising (a FILE sits where the dir should be) is the other refusal:
    the push goes out, the stamp is reported unwritable, nothing raises."""
    blocker = tmp_path / "state"
    blocker.write_text("not a dir")
    monkeypatch.setenv("ROTATE_STATE_DIR", str(blocker))
    row = {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400}
    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: sent.append(m) or True)
    capsys.readouterr()
    assert cr._chain_expiry_push([row], FLEET_NOW) == 1 and len(sent) == 1
    assert "stamp unwritable" in capsys.readouterr().out


def test_chain_push_refuses_a_planted_symlink_stamp(tmp_path, monkeypatch, capsys):
    """A symlink planted at the stamp's path is neither read as a stamp (fail toward notifying)
    nor written through (O_NOFOLLOW) — the write is refused, the link target keeps its bytes."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    victim = tmp_path / "victim"
    victim.write_text("ORIGINAL")
    key = str(int(FLEET_NOW + 86400))
    stamp = cr._chain_push_stamp("sarp@ocoron.com")
    stamp.symlink_to(victim)
    victim.write_text(key)  # a link "holding the key" must still not count as a stamp
    assert not cr._stamp_holds(stamp, key)
    with pytest.raises(OSError):
        cr._write_stamp(stamp, "1")
    assert victim.read_text() == key, "never written through the link"
    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: sent.append(m) or True)
    row = {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400}
    capsys.readouterr()
    assert cr._chain_expiry_push([row], FLEET_NOW) == 1, "a planted link never reads as stamped"
    assert victim.read_text() == key, "nor does the push path write through it"
    assert "stamp unwritable" in capsys.readouterr().out


def test_chain_push_names_the_notifier_verdict_it_can_know(tmp_path, monkeypatch, capsys):
    """The UNCONFIRMED line says the notifier is absent when it is, and otherwise that the send
    could not be confirmed, with every possible cause — some of them a send that DID go out (the
    notifier delivered but could not write its artifact), which is why the line never says
    "NOT delivered" — and the tick's `now` plays no part."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    locks = tmp_path / "locks"
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    row = {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400}
    capsys.readouterr()
    assert cr._chain_expiry_push([row], FLEET_NOW) == 0
    assert "unavailable" in capsys.readouterr().out
    script = tmp_path / ".claude" / "bin" / "claude-sound.sh"
    # the autouse pin points CLAUDE_SOUND_SH at a path that does not exist; a test that
    # wants a real notifier names its own, which is what the pin's composability is for
    monkeypatch.setenv("CLAUDE_SOUND_SH", str(script))
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/bash\nexit 0\n")  # runs, delivers nothing
    assert cr._chain_expiry_push([row], FLEET_NOW) == 0
    out = capsys.readouterr().out
    assert (
        "push UNCONFIRMED" in out and "could not be confirmed" in out and "retried next tick" in out
    )
    assert "NOT delivered" not in out, "the tick never asserts non-delivery it cannot know"


def test_write_stamp_enforces_0600_on_an_existing_stamp(tmp_path):
    """`os.open`'s mode applies only to a file it creates: a stamp left at 0644 by an older writer
    would keep 0644 across every re-mint — so the mode is enforced with fchmod."""
    stamp = tmp_path / "fleet-chain-push-x"
    stamp.write_text("old")
    stamp.chmod(0o644)
    cr._write_stamp(stamp, "123")
    assert stamp.read_text() == "123"
    assert oct(stamp.stat().st_mode & 0o777) == "0o600"


def test_stamp_epoch_rejects_garbage_and_future_values(tmp_path):
    """An all-digits garbage artifact (or a value past now by more than the clock-skew tolerance)
    must read as 0, not as "the
    future": otherwise no later send could ever advance it and the chain warning could never be
    delivered again under that key. Negative, non-numeric, symlinked → 0 too."""
    p = tmp_path / "k.notified"
    p.write_text("1" * 40)
    assert cr._stamp_epoch(p, FLEET_NOW) == 0
    p.write_text(str(int(FLEET_NOW + 2 * 86400)))
    assert cr._stamp_epoch(p, FLEET_NOW) == 0
    assert cr._CLOCK_SKEW_TOLERANCE_S == 60.0, "seconds of skew, never a day of it"
    edge = int(FLEET_NOW + cr._CLOCK_SKEW_TOLERANCE_S)  # the file's one future tolerance
    p.write_text(str(edge))
    assert cr._stamp_epoch(p, FLEET_NOW) == edge, "exactly at the tolerance is still a reading"
    p.write_text(str(edge + 1))
    assert cr._stamp_epoch(p, FLEET_NOW) == 0
    p.write_text(str(int(FLEET_NOW - 60)))
    assert cr._stamp_epoch(p, FLEET_NOW) == int(FLEET_NOW - 60)
    p.write_text("-5")
    assert cr._stamp_epoch(p, FLEET_NOW) == 0
    p.write_text("12.5")
    assert cr._stamp_epoch(p, FLEET_NOW) == 0
    link = tmp_path / "link.notified"
    link.symlink_to(p)
    p.write_text(str(int(FLEET_NOW - 60)))
    assert cr._stamp_epoch(link, FLEET_NOW) == 0


def test_chain_push_skips_a_non_finite_expiry_and_never_raises(tmp_path, monkeypatch):
    """A hand-built row with NaN / ±inf must not raise out of a "never raises" function
    (`int(nan)` is a ValueError, `int(-inf)` an OverflowError): non-finite is skipped."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(tmp_path / "locks"))
    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: sent.append(m) or True)
    rows = [
        {"email": "a@x.com", "slugs": ["a"], "refresh_expires_epoch": float("nan")},
        {"email": "b@x.com", "slugs": ["b"], "refresh_expires_epoch": float("-inf")},
        {"email": "c@x.com", "slugs": ["c"], "refresh_expires_epoch": float("inf")},
    ]
    assert cr._chain_expiry_push(rows, FLEET_NOW) == 0 and sent == []
    assert [w for w in cr._fleet_row_warnings(rows) if "refresh chain" in w] == [], (
        "the warning leg skips a non-finite expiry the same way — one field, two guards"
    )
    # and the producer: a corrupt giant refreshTokenExpiresAt reads as None, never an OverflowError
    creds = tmp_path / ".credentials.json"
    creds.write_text(json.dumps({"claudeAiOauth": {"refreshTokenExpiresAt": 10**400}}))
    assert cr._refresh_expiry_epoch(creds) is None


def test_chain_push_key_and_stamp_share_one_digest():
    """The notify key and the stamp name derive from ONE function, so they can never drift."""
    d = cr._chain_push_digest("Sarp@Ocoron.com")
    assert d == cr._chain_push_digest("sarp@ocoron.com") and len(d) == 8
    assert d == hashlib.sha1(b"sarp@ocoron.com").hexdigest()[:8], "the LOWERCASED email"
    assert cr._chain_push_stamp("sarp@ocoron.com").name.endswith(f"-{d}")


def test_rotate_state_dir_never_mutates_an_existing_dirs_mode(tmp_path, monkeypatch):
    """`--status` is a read every agent runs, so the accessor must not chmod: a state dir the
    operator made wider (0775) keeps its mode; only a dir this tool CREATES is 0700."""
    state = tmp_path / "state"
    state.mkdir()
    state.chmod(0o775)  # plain group/other bits: portable to mounts that strip setgid
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    assert cr._rotate_state_dir() == state
    assert oct(state.stat().st_mode & 0o777) == "0o775", "an existing dir is the operator's"
    fresh = tmp_path / "fresh" / "state"
    monkeypatch.setenv("ROTATE_STATE_DIR", str(fresh))
    assert cr._rotate_state_dir() == fresh
    assert oct(fresh.stat().st_mode & 0o777) == "0o700", "a dir this tool creates is 0700"


def test_write_stamp_refuses_a_fifo_and_never_blocks_on_it(tmp_path):
    """O_NOFOLLOW refuses a symlink but not a FIFO: a readerless FIFO at the stamp's path would
    park the 5-minute tick forever inside `os.open` (O_NONBLOCK → ENXIO), and a FIFO WITH a reader
    would let the write "succeed" into something `_stamp_holds` never reads (the S_ISREG check).
    The grader carries its own alarm so a regression fails in seconds instead of hanging pytest."""
    fifo = tmp_path / "fleet-chain-push-x"
    os.mkfifo(fifo)

    def _hung(signum, frame):
        raise AssertionError("_write_stamp blocked on a readerless FIFO")

    old = signal.signal(signal.SIGALRM, _hung)
    signal.alarm(5)
    try:
        with pytest.raises(OSError):
            cr._write_stamp(fifo, "1")
        reader = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        try:
            with pytest.raises(OSError, match="not a regular file"):
                cr._write_stamp(fifo, "1")
        finally:
            os.close(reader)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def test_notify_failure_reason_names_every_cause_it_cannot_tell_apart(tmp_path, monkeypatch):
    """This side can only know that the notifier is absent, or that the send is unconfirmed
    — and the latter has causes it cannot separate honestly, some of them a send that went out
    (a guessed "suppressed" or "FAILED" was wrong under a stale tick clock and under a backward
    clock step, review rounds 4–6; and on the timeout path the artifact is not even re-read, so
    the line may not claim it "did not advance"). The property under test is INVARIANCE: the line
    names every cause and does not vary with what the artifact holds — the four contents are the
    input domain."""
    locks = tmp_path / "locks"
    locks.mkdir()
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    key = "quota-rotation-chain-abcdef12"
    assert "unavailable" in cr._notify_failure_reason()
    script = tmp_path / ".claude" / "bin" / "claude-sound.sh"
    # the autouse pin points CLAUDE_SOUND_SH at a path that does not exist; a test that
    # wants a real notifier names its own, which is what the pin's composability is for
    monkeypatch.setenv("CLAUDE_SOUND_SH", str(script))
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/bash\nexit 0\n")
    for content in (str(int(FLEET_NOW - 600)), str(int(FLEET_NOW + 600)), "garbage", ""):
        (locks / f"{key}.notified").write_text(content)
        line = cr._notify_failure_reason()
        assert "suppressed" in line and "failed" in line and "unreadable" in line, content
        assert "did not finish" in line and "failed exec" in line, content
        assert "abort" not in line, content
        assert "delivered but could not write" in line and "clock-implausible" in line, content
        assert "MESH_NOTIFY_CMD" in line and "never attempted" in line, content
        assert "no custom notifier" in line and "torn short" not in line, content
        assert "plausible epoch above the previous reading" in line, content
        assert "a symlink, a non-file, an unreadable or non-numeric file, or a" in line, content
        assert "clock-implausible value reads as nothing" in line, content
        assert "at or below it" in line and "torn to empty" not in line, content
        assert "unavailable" not in line
    (locks / f"{key}.notified").unlink()
    assert "could not be confirmed" in cr._notify_failure_reason()


def test_chain_push_names_the_state_dir_refusal(tmp_path, monkeypatch, capsys):
    """When the state dir cannot be made the printed line carries the real exception — its path
    and its errno text — not a function name."""
    blocker = tmp_path / "state"
    blocker.write_text("not a dir")
    monkeypatch.setenv("ROTATE_STATE_DIR", str(blocker))
    row = {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400}
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: True)
    capsys.readouterr()
    assert cr._chain_expiry_push([row], FLEET_NOW) == 1
    out = capsys.readouterr().out
    assert "stamp unwritable (state dir unavailable: FileExistsError: " in out
    assert str(blocker) in out and "File exists" in out


def test_stamp_holds_trusts_the_dir_not_the_mode(tmp_path, monkeypatch):
    """The contract after D-251: the state dir is the trust boundary, so a stamp in it holds
    whatever its mode (a legacy 0644 stamp, a hand-chmodded 0666 one) — a path-based owner/mode
    check here was removed because it defended against no principal this box has and mis-fired
    on mounts that cannot hold a mode. This grader pins the contract, not the absence of a guard."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    key = str(int(FLEET_NOW + 86400))
    stamp = cr._chain_push_stamp("sarp@ocoron.com")
    for mode in (0o644, 0o666):
        stamp.write_text(key)
        stamp.chmod(mode)
        assert cr._stamp_holds(stamp, key), oct(mode)
    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m, **kw: sent.append(m) or True)
    row = {"email": "sarp@ocoron.com", "slugs": ["seo"], "refresh_expires_epoch": FLEET_NOW + 86400}
    assert cr._chain_expiry_push([row], FLEET_NOW) == 0 and sent == []


def test_chain_push_stamps_do_not_collide_across_lookalike_emails(tmp_path, monkeypatch):
    """`a.b@x.com` and `a-b@x.com` sanitise to the same a-z0-9 slug; the hash suffix keeps their
    stamps apart (two chains alternating on one file would re-push each other every tick)."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(tmp_path / "locks"))
    one = cr._chain_push_stamp("a.b@x.com").name
    two = cr._chain_push_stamp("a-b@x.com").name
    assert one != two and one.startswith("fleet-chain-push-a-b-x-com-")
    assert cr._chain_push_stamp("Sarp@Ocoron.com") == cr._chain_push_stamp("sarp@ocoron.com")


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


def test_fleet_exhaustion_advisory_broadcasts_to_all_mailbox_repos(tmp_path, monkeypatch, capsys):
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

    assert len(actions["telegrams"]) == 1, (
        "the active account is walled with no relief → 1 advisory"
    )
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
    usages = {"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)}
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
    usages["tok-seo"] = _usage_blob(OVER_LINE + 1.0, 97.0)
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

    assert len(actions["telegrams"]) == 1, (
        "a future-dated (invalid) latch must not silence a live wall"
    )


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
    usages = {"tok-seo": _usage_blob(OVER_LINE, 50.0), "tok-intel": _usage_blob(10.0, 10.0)}
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
    usages["tok-intel"] = _usage_blob(OVER_LINE, 96.0)
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


def test_fleet_dirs_ignore_the_active_pointer(tmp_path, monkeypatch, capsys):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    for slug in ("ob", "sarp"):
        assert cr.main(["--new-dir", slug, f"{slug}@ocoron.com"]) == 0
    _fleet_creds(fleet, "ob", "tok-ob", age_s=8 * 86400.0)
    _fleet_creds(fleet, "sarp", "tok-sarp", age_s=86400.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    assert cr._flip_active("ob", manual=True)
    assert [d.name for d in cr._fleet_dirs()] == ["ob", "sarp"], (
        "the active symlink must never be counted as a fleet dir"
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
    usages = {"tok-seo": _usage_blob(OVER_LINE, 50.0), "tok-intel": _usage_blob(10.0, 10.0)}
    _fake_oauth(monkeypatch, usages=usages)
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out

    assert os.readlink(fleet / "active") == "intel", "the tick must FLIP the pointer"
    assert f"flipped active sarp@ocoron.com -> ob@ocoron.com (intel) at {OVER_LINE:.0f}%" in out
    assert actions["switched"] == [] and actions["picked"] == [], "legacy install never touched"
    lines = (tmp_path / "state" / "rotate-ledger.jsonl").read_text().splitlines()
    flip = next(e for e in map(json.loads, lines) if e.get("event") == "flip")
    assert (flip["from"], flip["to"], flip["at_pct"]) == ("seo", "intel", OVER_LINE)

    # …and a second over-threshold tick moments later FLIPS AGAIN. Until 2026-09-03 this tick
    # was held by the 30-min dwell; D-104 made every trip flip dwell-exempt (a trip is a wall,
    # never churn — the session wall stops every running agent at once), and churn is prevented
    # where it belongs: the candidate predicate never targets a sibling at/over the threshold or
    # without 5h budget. seo at 10% IS such a target, so the pointer moves back to it.
    usages["tok-intel"] = _usage_blob(OVER_LINE, 96.0)
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
        # 84, not 94: at/over the drain band (85) with a fresh sibling the tick now RELIEF-flips
        # (D-171, 2026-09-06); the trip rule this test guards is exercised below the band
        usages={"tok-seo": _usage_blob(84.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    capsys.readouterr()

    assert cr._cmd_tick() == 0

    # derived: the tick prints the LIVE threshold, so a literal here fails on every future
    # move of the line rather than on a real defect (D-201 moved it 95 -> 98)
    assert f"below {cr._rotate_threshold():.0f}%, no flip" in capsys.readouterr().out
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
        usages={"tok-seo": _usage_blob(OVER_LINE, 50.0), "tok-intel": _usage_blob(100.0, 100.0)},
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
        usages={"tok-seo": _usage_blob(OVER_LINE, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
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
        usages={"tok-seo": _usage_blob(OVER_LINE, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
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
    candidacy — under 5d to expiry (the tick's once-per-chain push follows inside 3 d)."""
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
    # the remedy is the ONE thing that works — a /login in that dir, as a copy/paste line —
    # never "run a claude turn", which does not move refreshTokenExpiresAt (measured 2026-09-12)
    assert (
        'CLAUDE_CONFIG_DIR="$HOME/.claude-fleet/seo" CLAUDE_QUOTA_HOME="$HOME/.claude-fleet/seo" claude'
        in out
    )
    assert "/login as sarp@ocoron.com" in out and "does NOT extend it" in out
    assert "run one claude turn" not in out and "keepalive cadence" not in out

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
        # weekly 84, not 89: 89 is in the drain band and a 10/10 sibling makes it a relief flip
        # (D-171); the cap-vs-threshold rule this test guards is exercised below the band
        usages={"tok-seo": _usage_blob(50.0, 84.0), "tok-intel": _usage_blob(10.0, 10.0)},
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
        usages={"tok-seo": _usage_blob(OVER_LINE, 50.0), "tok-intel": _usage_blob(99.0, 10.0)},
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
        usages={"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(10.0, 50.0)},
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
    # `attempts` is PER HOST — the bound is hosts x attempts. Derived from the constant, never
    # hardcoded: this assertion read `== 2` from 2026-08-22 until the second probe host landed on
    # 2026-08-30 and doubled the real bound, leaving the test red and unnoticed until fleet ran
    # the full suite (01M1MG98SC90HB863AW18XJKQ6). A literal here goes stale on the next host.
    assert calls["n"] == len(cr._OAUTH_HOSTS) * 2, (
        "bounded — exactly `attempts` tries PER HOST, then give up (fail-soft)"
    )


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

    assert actions["telegrams"] == [], (
        "reset jitter must produce ZERO advisories while headroom exists"
    )
    assert actions["mails"] == [], "and zero mail — the spam class is structurally gone"


# ── operator rule 2026-09-03: "when we see 90% session limit reached and if no account is
# available we must send an URGENT mail to repos: stop your work asap gracefully and hook
# yourself to start 1 minute after next account session resets" ──────────────────────────────


def _row(email, session, weekly, cap=None, s_reset=None, w_reset=None, slug=None, source="live"):
    return {
        "email": email,
        "slugs": [slug or email.split("@")[0]],
        "source": source,
        "weekly_cap": cap,
        "five_hour": {"utilization": session, "resets_at_epoch": s_reset},
        "seven_day": {"utilization": weekly, "resets_at_epoch": w_reset},
    }


def test_a_giant_int_in_the_usage_cache_does_not_raise_out_of_the_relief_writer_or_the_window_reader():
    """Delta 22 seat A, A3: `float()` of a giant JSON int `resets_at_epoch` raised out of
    `_next_session_relief` — and `math.isfinite` of one out of `_window_reading` — killing the
    tick on every run until the cache file was hand-edited; the same class Delta 17 closed for
    the ledger readers, one function away on the same path."""
    giant = int("1" + "0" * 400)
    now = FLEET_NOW
    rows = [
        _row("act@x", 91.0, 40.0, cap=99, s_reset=now + 4000),
        _row("g@x", 98.0, 27.0, cap=90, s_reset=giant, w_reset=now + 90000),
    ]
    relief = cr._next_session_relief(
        rows, "act@x", now
    )  # returns, and an unusable reset is no relief
    assert relief is None or relief[1] != "g@x", relief
    assert cr._window_reading({"utilization": 0.5, "resets_at_epoch": giant}) == (0.5, None)
    assert cr._window_reading({"utilization": giant, "resets_at_epoch": now}) == (None, now)
    picture = cr._fleet_picture(rows, "act", now)  # the picture composer read the same field bare
    assert isinstance(picture, dict)
    # and the CACHE-sourced row with the giant in BOTH fields: `_fleet_picture` calls
    # `_flip_candidate_verdict` before its own validated reads, and that function converted bare —
    # the first cut of this grader pinned `source: "live"` and could not reach it (Delta 23 seat)
    cached = _row("c@x", giant, giant, cap=90, s_reset=giant, w_reset=giant, source="cache")
    verdict = cr._flip_candidate_verdict(cached, 98.0)
    assert verdict[1] == {"five_hour": None, "seven_day": None}, verdict
    assert isinstance(cr._fleet_picture(rows + [cached], "act", now), dict)
    target = cr._pick_flip_target(rows + [cached])  # (slug, email) | None — never a bare email
    assert target is None or target[1] != "c@x", target


def test_a_candidate_row_with_a_giant_weekly_reset_does_not_raise_out_of_the_picker(
    tmp_path, monkeypatch
):
    """The quota-posture review's Delta 24 seat recorded it: a CANDIDATE row (normal utilizations, a
    live-chained credentialed dir) whose WEEKLY reset alone carries a giant JSON int reached the
    picker's own bare `float(reset)` after every other reset read had been routed through
    `_usable_ts` — OverflowError out of `_pick_flip_target` and `_fleet_picture`. A row without a
    credentialed dir never gets that far (the verdict skips it first), which is why the first cut
    of this grader could not reach the line."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=600.0)
    giant = int("1" + "0" * 400)
    now = FLEET_NOW
    for src in ("cache", "live"):
        hot = _row(
            "sarp@ocoron.com",
            10.0,
            20.0,
            cap=90,
            s_reset=now + 3600,
            w_reset=giant,
            slug="seo",
            source=src,
        )
        assert cr._flip_candidate_verdict(hot, 98.0)[2] is None, (
            src
        )  # a CANDIDATE, so the line is reached
        picked = cr._pick_flip_target([hot])
        assert picked == ("seo", "sarp@ocoron.com"), (
            src,
            picked,
        )  # returns; the giant reset reads as no reset
        assert isinstance(cr._fleet_picture([hot], "intel", now), dict), src
    # and the ORDERING the fix chose: an undated candidate sorts LAST (`far`), so a dated sibling
    # wins — a mutant writing `0.0` for the undated row inverted perishable-first fleet-wide and
    # the single-candidate arm above stayed green (round 1 seat A)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=600.0)
    # the dated row carries the WORSE weekly reading on purpose: with every candidate undated the
    # tie-break (lowest weekly) would pick it anyway, so only perishable-first explains the pick
    dated = _row(
        "ob@ocoron.com", 10.0, 30.0, cap=90, s_reset=now + 3600, w_reset=now + 7200, slug="intel"
    )
    assert cr._pick_flip_target([hot, dated]) == ("intel", "ob@ocoron.com")
    # a PAST reset is not perishability either (closing review R3): a stale cached row whose weekly
    # reset has passed sorts LAST like an undated one, never ahead of a live future reset — and a
    # reset exactly at `now` is on the past side of the strict `>` (mutants M4 and M2 survived)
    for stale_reset in (now - 100, now):
        stale = _row(
            "sarp@ocoron.com",
            10.0,
            20.0,
            cap=90,
            s_reset=now + 3600,
            w_reset=stale_reset,
            slug="seo",
        )
        assert cr._pick_flip_target([stale, dated]) == ("intel", "ob@ocoron.com"), stale_reset


def test_a_giant_int_on_the_active_row_does_not_raise_out_of_the_tick_burn_projection():
    """`_tick_burn` runs on the ACTIVE row before the picker on every tick and converted the cache
    fields bare — a giant JSON int there killed the tick, the posture write and the advisory
    (scoped review, round 1 seat A). Its docstring says 'never raises'; now it does not."""
    giant = int("1" + "0" * 400)
    row = {
        "email": "a@x",
        "five_hour": {"utilization": 40.0, "resets_at_epoch": FLEET_NOW + 3600},
        "seven_day": {"utilization": 31.0, "resets_at_epoch": giant},
    }
    assert cr._tick_burn("a@x", row, FLEET_NOW) == {"five_hour": 0.0, "seven_day": 0.0}
    row2 = {**row, "five_hour": {"utilization": giant, "resets_at_epoch": FLEET_NOW + 3600}}
    assert cr._tick_burn("a@x", row2, FLEET_NOW) == {"five_hour": 0.0, "seven_day": 0.0}


def test_status_renders_a_reset_the_platform_cannot_date_as_unknown():
    """Text `--status` died on `datetime.fromtimestamp` for a reset past `time_t` — and a finite
    `1e300` passes every type validator and still raises, so the guard is on the conversion
    (round 1 seat A)."""
    for bad in (1e300, int("1" + "0" * 400), float("nan"), -1e300, "x"):
        assert (
            cr._fmt_quota_window({"utilization": 31.0, "resets_at_epoch": bad}) == "31% (resets ?)"
        ), bad
    assert cr._fmt_quota_window({"utilization": 31.0, "resets_at_epoch": None}) == "31% (resets ?)"
    assert cr._fmt_reset_clock(0) == "?" and cr._fmt_reset_clock(None, "unknown") == "unknown"
    # round 2 seat A: the utilization half of the SAME row raised one token later (F2); a bool
    # or a negative reset rendered a 1970 clock the picker reads as undated (F5)
    for bad in (int("1" + "0" * 400), float("nan"), float("inf"), True, "31"):
        assert cr._fmt_quota_window({"utilization": bad, "resets_at_epoch": FLEET_NOW}) == "-", bad
    assert cr._fmt_reset_clock(True) == "?" and cr._fmt_reset_clock(-100) == "?"
    assert cr._fmt_quota_window({"utilization": 31.0, "resets_at_epoch": FLEET_NOW}).startswith(
        "31% (resets "
    )


def test_every_reader_of_a_cache_utilization_survives_the_value_the_validator_refuses(monkeypatch):
    """Round zero of the routed-up review swept the CLASS — a value that passes `isinstance` and
    raises on conversion (`float()`, `math.isfinite`, an f-string) — at every mirror site the
    two scoped rounds had not reached: both probe parsers, the cap-walled warning, the band and
    posture-line readers, the forecast renderer, the drain reason, the advisory's hot/session
    reads and `--probe-current`. Each reads the giant as NO reading, none raises."""
    giant = int("1" + "0" * 400)
    w = {"utilization": giant, "resets_at_epoch": FLEET_NOW + 60}
    row = {
        "email": "a@x",
        "valid": True,
        "weekly_cap": 90,
        "cap_walled": True,
        "slugs": ["a"],
        "source": "live",
        "five_hour": w,
        "seven_day": w,
    }
    assert (
        cr._usage_windows(
            {
                "five_hour": {"utilization": giant, "resets_at": None},
                "seven_day": {"utilization": 3, "resets_at": None},
            }
        )
        is None
    )
    assert any("cap-walled — weekly ? ≥ cap 90" in s for s in cr._fleet_row_warnings([row]))
    # the capless twin prints nothing — the guard had no grader (confirming seat G, F2)
    assert cr._fleet_row_warnings([{**row, "weekly_cap": None, "cap_walled": False}]) == []
    assert (
        cr._fmt_forecast({"utilization": 5.0, "verdict": "reset_first", "minutes_to_reset": giant})
        == "no burn"
    )
    assert (
        cr._drain_trigger_reason(row, None, True) == "it is walled with no readable weekly figure"
    )
    assert cr._row_utils(row) == {"five_hour": None, "seven_day": None}
    assert (
        cr._fleet_band(
            {"five_hour": w, "seven_day": w}, "GREEN", False, 85.0, 90.0, fable=False, measured=1
        )
        == "RED"
    )
    line = cr._posture_status_line(
        {
            "ts": FLEET_NOW,
            "active": {"slug": "a", "windows": {"five_hour": w}},
            "fleet": {"five_hour": {**w, "slug": "a"}},
        },
        FLEET_NOW,
    )
    assert "5h —" in line, (
        line
    )  # the primary 5h field, not the `burn 5h` field (round 1 seat 2, F3)
    monkeypatch.setattr(cr, "_tick_telegram", lambda m: None)
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, m: None)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "_ledger_append", lambda e: None)
    monkeypatch.setattr(cr, "_resolve_active", lambda: "a")
    cr._fleet_active_wall_advisory([row], FLEET_NOW, threshold=95.0)


def test_the_legacy_successor_picker_reads_a_reset_the_validator_refuses_as_none(monkeypatch):
    """`_pick_successor`'s sort key took the raw cache value: a string reset raised TypeError in
    the tuple compare, a JSON `true` sorted as a 1970 reset and won perishable-first (round 2
    seat C). Both read as no reset now; the dated sibling wins."""
    monkeypatch.setattr(cr, "_walled", lambda r: False)
    rows = [
        {"name": "bad", "valid": True, "seven_day": {"utilization": 10.0, "resets_at_epoch": "x"}},
        {
            "name": "bool",
            "valid": True,
            "seven_day": {"utilization": 10.0, "resets_at_epoch": True},
        },
        {
            "name": "dated",
            "valid": True,
            "seven_day": {"utilization": 50.0, "resets_at_epoch": FLEET_NOW + 60},
        },
        # a NEGATIVE epoch passed the validator and, truthy, beat `or far` to win perishable-first
        # — the flip picker's `reset > _now()` mirror was missing here (round 1 seat 2, F5)
        {
            "name": "negative",
            "valid": True,
            "seven_day": {"utilization": 10.0, "resets_at_epoch": -50.0},
        },
    ]
    assert cr._pick_successor(rows, None, FLEET_NOW) == "dated"


def test_a_giant_int_utilization_on_the_active_row_does_not_kill_the_flip_leg(monkeypatch, capsys):
    """`_tick_burn` was made non-raising on the giant int and its ONLY caller read the same row
    bare one line later — the tick died at the projection sum, so no flip, no posture, no
    advisory, and cron saw rc 0 (round 2 seat A, F1). The giant window reads as no reading; the
    other window still decides."""
    monkeypatch.setattr(cr, "_resolve_active", lambda: "intel")
    giant = int("1" + "0" * 400)
    row = {
        "email": "a@x",
        "slugs": ["intel"],
        "source": "live",
        "valid": True,
        "five_hour": {"utilization": giant, "resets_at_epoch": FLEET_NOW + 3600},
        "seven_day": {"utilization": 31.0, "resets_at_epoch": FLEET_NOW + 7200},
    }
    cr._fleet_flip_leg([], [row], 98.0)  # red on HEAD: OverflowError at the projection sum
    out = capsys.readouterr().out
    assert "at 31%" in out and "no flip" in out, out  # the surviving weekly reading decided
    # the mirror: giant in the WEEKLY window, the session reading decides (round 1 seat 2, F2)
    row["five_hour"], row["seven_day"] = row["seven_day"], row["five_hour"]
    cr._fleet_flip_leg([], [row], 98.0)
    out = capsys.readouterr().out
    assert "at 31%" in out and "no flip" in out, out


def test_the_drain_broadcast_soonest_reset_skips_a_reset_the_validator_refuses():
    """`min()` over raw cache values raised TypeError on a string reset one line ABOVE the
    guarded renderer — the drain mail and telegram were lost to `_cmd_tick`'s blanket except
    (round 2 seat A, F4). The valid reset still wins; an invalid row contributes nothing."""
    rows = [
        {
            "valid": True,
            "five_hour": {"resets_at_epoch": FLEET_NOW + 50},
            "seven_day": {"resets_at_epoch": "x"},
        },
        {
            "valid": True,
            "five_hour": {"resets_at_epoch": True},
            "seven_day": {"resets_at_epoch": FLEET_NOW + 20},
        },
        {"valid": False, "five_hour": {"resets_at_epoch": FLEET_NOW + 1}, "seven_day": None},
    ]
    assert cr._soonest_reset(rows, FLEET_NOW) == FLEET_NOW + 20
    assert (
        cr._soonest_reset(
            [{"valid": True, "five_hour": {"resets_at_epoch": int("1" + "0" * 400)}}], FLEET_NOW
        )
        is None
    )


def test_the_urgent_drain_message_survives_a_relief_epoch_the_platform_cannot_date():
    """`_usable_ts` admits any finite float, so a 1e300 relief reached four bare conversions
    BEFORE the telegram, the mail and the fleet-exhausted stamp — no WALL for quota_stop.py
    (round 2 seat A, F3). Such a relief is no relief: the no-resume-time text goes out."""
    msg = cr._urgent_drain_message("a@x", "session exhausted", (1e300, "b@x", "session"))
    assert "no resume time can be given" in msg and "RESUME AT" not in msg

    # each exception the platform can raise from the conversion, not only the one 1e300 raises —
    # a mutant narrowing the tuple to OverflowError survived the whole battery (round 1 seat 2, F1)
    def _refusing(exc):
        class _DT:
            @staticmethod
            def fromtimestamp(*a, **k):
                raise exc("platform refused")

        return _DT

    for exc in (OverflowError, OSError, ValueError):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cr, "datetime", _refusing(exc))
            out = cr._urgent_drain_message("a@x", "r", (FLEET_NOW + 60, "b@x", "session"))
        assert "no resume time can be given" in out, exc


def test_a_nan_weekly_figure_reads_as_cap_walled_and_weekly_blocked_not_as_headroom():
    """`json.loads` admits NaN and a cached row is used as-is; the comparison-only sites never
    raised on it but read it as NOT walled — fail-open on the one value the whole class is about
    (round 1 seat 3, F7). An unreadable figure blocks; an absent one is still no reading."""
    now = FLEET_NOW
    nan_row = _row("nan@x", 97.0, float("nan"), cap=90, s_reset=now + 3000, w_reset=now + 86400)
    ok_row = _row("ok@x", 97.0, 30.0, cap=90, s_reset=now + 3000, w_reset=now + 86400)
    # the relief writer: a NaN weekly is BLOCKED, so the account waits on its weekly reset —
    # on HEAD it read as headroom and the session reset was promised
    act = _row("act@x", 91.0, 40.0, cap=99)
    assert cr._next_session_relief([act, nan_row], "act@x", now) == (now + 86400, "nan@x", "weekly")
    assert cr._next_session_relief([act, ok_row], "act@x", now) == (now + 3000, "ok@x", "session")


def test_an_unreadable_weekly_figure_is_one_reading_in_the_verdict_the_board_and_the_flag(
    tmp_path, monkeypatch
):
    """The flag, the warning and the relief writer read an unreadable weekly as walled; the
    verdict read it as no reading and named the row ELIGIBLE, and the board then gave that
    eligible row a `returns_at` a day out, called a session-exhausted row weekly-exhausted, and
    could never reach `cap-walled` for the case the warning names (heavy review round 3 seat C,
    F1–F3). One reading now: not a target; `cap-walled` under a cap, `weekly-unreadable` without;
    `returns_at` follows the state."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=600.0)
    now = FLEET_NOW
    capped = _row(
        "sarp@ocoron.com",
        10.0,
        float("nan"),
        cap=90,
        s_reset=now + 3600,
        w_reset=now + 86400,
        slug="seo",
    )
    # the verdict does NOT refuse it (round 4 seat E: refusing here overrode the rolled-over
    # rescue and took the fleet band RED on one garbage cell); a pickable row carries no return
    assert cr._flip_candidate_verdict(capped, 98.0)[2] is None
    board = cr._fleet_picture([capped], None, now)["accounts"][0]
    assert (board["state"], board["returns_at"]) == ("eligible", None), board
    capless = _row(
        "sarp@ocoron.com",
        10.0,
        float("nan"),
        cap=None,
        s_reset=now + 3600,
        w_reset=now + 86400,
        slug="seo",
    )
    assert cr._flip_candidate_verdict(capless, 98.0)[2] is None
    board = cr._fleet_picture([capless], None, now)["accounts"][0]
    assert (board["state"], board["returns_at"]) == ("eligible", None), board
    spent = _row(
        "sarp@ocoron.com",
        90.0,
        float("nan"),
        cap=None,
        s_reset=now + 3600,
        w_reset=now + 86400,
        slug="seo",
    )
    board = cr._fleet_picture([spent], None, now)["accounts"][
        0
    ]  # named for what it is, not "exhausted"
    assert (board["state"], board["returns_at"]) == ("weekly-unreadable", now + 86400), board
    readable = _row(
        "sarp@ocoron.com", 10.0, 20.0, cap=90, s_reset=now + 3600, w_reset=now + 86400, slug="seo"
    )
    board = cr._fleet_picture([readable], None, now)["accounts"][0]
    assert (board["state"], board["returns_at"]) == ("eligible", None), board


def test_the_active_account_keeps_its_return_instant_on_the_board(tmp_path, monkeypatch):
    """Keying `returns_at` on the state dropped the ACTIVE account's return in every walled or
    spent shape — the one fact an agent needs at the wall (round 4 seat E, F1)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=600.0)
    now = FLEET_NOW
    walled = _row(
        "sarp@ocoron.com", 10.0, 100.0, cap=99, s_reset=now + 3600, w_reset=now + 86400, slug="seo"
    )
    board = cr._fleet_picture([walled], "seo", now)["accounts"][0]
    assert (board["state"], board["returns_at"]) == ("active", now + 86400), board
    spent = _row(
        "sarp@ocoron.com", 99.0, 20.0, cap=99, s_reset=now + 3600, w_reset=now + 86400, slug="seo"
    )
    board = cr._fleet_picture([spent], "seo", now)["accounts"][0]
    assert (board["state"], board["returns_at"]) == ("active", now + 3600), board
    # and a HEALTHY active row with an unreadable weekly carries no return — the arm fired on the
    # relief writer's conservative reading and promised a day out (remainder seat F, F1)
    healthy = _row(
        "sarp@ocoron.com",
        3.0,
        float("nan"),
        cap=90,
        s_reset=now + 3600,
        w_reset=now + 86400,
        slug="seo",
    )
    board = cr._fleet_picture([healthy], "seo", now)["accounts"][0]
    assert (board["state"], board["returns_at"]) == ("active", None), board


def test_an_unreadable_cached_weekly_never_costs_the_fleet_its_session_reading(
    tmp_path, monkeypatch
):
    """Refusing an unreadable-weekly row in the verdict moved it out of `_SERVING_STATES`, so its
    cool session reading left the fleet picture and the band went GREEN → RED on one garbage
    cache cell (round 4 seat E, F3); and the rolled-over cached row stayed refused while its 100%
    twin was rescued (F2). The verdict leaves such a row pickable; the board serves it."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=600.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=600.0)
    now = FLEET_NOW
    active = _row(
        "ob@ocoron.com", 96.0, 40.0, cap=99, s_reset=now + 3600, w_reset=now + 86400, slug="intel"
    )
    standby = _row(
        "sarp@ocoron.com",
        3.0,
        float("nan"),
        cap=90,
        s_reset=now + 3600,
        w_reset=now + 86400,
        slug="seo",
    )
    pic = cr._fleet_picture([active, standby], "intel", now)
    states = {a["email"]: a["state"] for a in pic["accounts"]}
    assert states["sarp@ocoron.com"] == "eligible", states
    assert cr._fleet_readings([active, standby], pic)["five_hour"]["slug"] == "seo"
    rolled = _row(
        "sarp@ocoron.com",
        3.0,
        float("nan"),
        cap=90,
        s_reset=now + 3600,
        w_reset=now - 60,
        slug="seo",
        source="cache",
    )
    assert cr._flip_candidate_verdict(rolled, 98.0)[2] is None


def test_the_legacy_picker_survives_a_parked_row_whose_window_is_not_a_dict():
    """A parked row skips `_walled`, so the sort key's window reads reached a non-dict window
    bare and raised AttributeError out of the legacy picker (round 3 seat C, F4)."""
    rows = [
        {
            "name": "p",
            "valid": True,
            "telemetry": "unknown-parked",
            "seven_day": "?",
            "five_hour": {"utilization": 1.0},
        },
        {
            "name": "g",
            "valid": True,
            "five_hour": {"utilization": 1.0},
            "seven_day": {"utilization": 1.0},
        },
    ]
    assert cr._pick_successor(rows, None, FLEET_NOW) == "g"


def test_the_legacy_picker_prefers_a_just_reset_zero_over_a_nearly_spent_sibling():
    """`_usable_ts(...) or 100.0` read a genuine 0.0 as fully spent, so with no reset epochs the
    tick installed the 97%/84% account over the 0%/0% one (delta round seat A, F1)."""
    rows = [
        {
            "name": "spent",
            "valid": True,
            "five_hour": {"utilization": 84.0},
            "seven_day": {"utilization": 97.0},
        },
        {
            "name": "fresh",
            "valid": True,
            "five_hour": {"utilization": 0.0},
            "seven_day": {"utilization": 0.0},
        },
    ]
    assert cr._pick_successor(rows, None, FLEET_NOW) == "fresh"
    rows[1]["seven_day"]["utilization"] = 84.0  # weekly tie broken by the session element too
    rows[0]["seven_day"]["utilization"] = 84.0
    assert cr._pick_successor(rows, None, FLEET_NOW) == "fresh"
    assert (
        cr._walled({"five_hour": "87%", "seven_day": {"utilization": 1.0}}) is True
    )  # non-dict window (F5)


def test_cap_walled_is_set_from_a_cached_row_whose_weekly_figure_is_unreadable(
    tmp_path, monkeypatch
):
    """`cap_walled` is computed in `_fleet_account_rows` from the cached row AS-IS; a NaN there
    (which `json.loads` admits) read as headroom, and no grader reached the flag (delta round
    seat B, m9). A capped account with an unreadable weekly is cap-walled; a capless one is not
    cap-walled but is still refused by the successor filter."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _caps(fleet, {"sarp@ocoron.com": 90})
    _fleet_creds(fleet, "seo", "tok-seo", age_s=10 * 3600.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=10 * 3600.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-usage-cache.json").write_text(
        json.dumps(
            {
                "sarp@ocoron.com": {
                    "ts": FLEET_NOW - 9 * 3600.0,
                    "five_hour": {"utilization": 10.0, "resets_at_epoch": FLEET_NOW + 3600},
                    "seven_day": {
                        "utilization": float("nan"),
                        "resets_at_epoch": FLEET_NOW + 86400,
                    },
                },
                "ob@ocoron.com": {
                    "ts": FLEET_NOW - 9 * 3600.0,
                    "five_hour": {"utilization": 10.0, "resets_at_epoch": FLEET_NOW + 3600},
                    "seven_day": {
                        "utilization": float("nan"),
                        "resets_at_epoch": FLEET_NOW + 86400,
                    },
                },
            }
        )
    )
    _fake_oauth(monkeypatch)
    rows, _pending = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    by = {r["email"]: r for r in rows}
    # round 4: the flag follows the VERDICT — an unreadable figure is no reading, never a cap wall
    # (round 3 fused the two and the fleet band went RED on one garbage cell); the relief writer
    # alone refuses to promise from it, and the legacy successor filter stays conservative
    assert (
        by["sarp@ocoron.com"]["source"] == "cache" and by["sarp@ocoron.com"]["cap_walled"] is False
    ), by["sarp@ocoron.com"]
    assert cr._weekly_blocked(by["sarp@ocoron.com"]["seven_day"], 90) is True
    # the warning is driven by that reading, through the real writer, not by a hand-set flag
    # (remainder seat F, F2/F3): the operator still sees the "reserved" line for the garbage cell
    assert any(
        "sarp@ocoron.com: cap-walled — weekly ? ≥ cap 90" in s
        and "does NOT exclude it" in s
        and "automated flips exclude it" not in s  # the pick takes this row (seat G, F1)
        for s in cr._fleet_row_warnings(rows)
    ), rows
    assert by["ob@ocoron.com"]["cap_walled"] is False and cr._walled(by["ob@ocoron.com"]) is True


def test_the_board_the_relief_writer_and_the_cap_flag_share_one_weekly_walled_reading():
    """Three sites carried three readings of "weekly walled" and disagreed on exactly the
    garbage value: the board read an unreadable figure as headroom while the relief writer
    blocked it, so one `--status` payload promised two resume times (delta round seat A, F3);
    and a capless account's unreadable figure read as no wall at all (F4)."""
    for garbage in ("97", True, float("nan"), int("1" + "0" * 400)):
        assert cr._weekly_blocked({"utilization": garbage}, None) is True, garbage
        assert cr._weekly_blocked({"utilization": garbage}, 90) is True, garbage
    assert (
        cr._weekly_blocked({"utilization": None}, 90) is False
        and cr._weekly_blocked(None, 90) is False
    )
    assert (
        cr._weekly_blocked({"utilization": 95.0}, 90) is True
        and cr._weekly_blocked({"utilization": 95.0}, None) is False
    )
    assert cr._weekly_blocked({"utilization": 100.0}, None) is True
    now = FLEET_NOW
    row = _row("g@x", 97.0, 30.0, cap=90, s_reset=now + 3000, w_reset=now + 7200, slug="g")
    row["seven_day"]["utilization"] = "97"
    board = cr._fleet_picture([row], None, now)["accounts"][0]
    assert board["state"] != "eligible" and board["returns_at"] == now + 7200, (
        board
    )  # the weekly reset, not the session one
    assert cr._next_session_relief([_row("act@x", 91.0, 40.0, cap=99), row], "act@x", now) == (
        now + 7200,
        "g@x",
        "weekly",
    )


def test_tick_burn_pairs_only_two_windows_that_both_lack_a_reset(tmp_path, monkeypatch):
    """The second `same_window` arm compared a RAW previous reset with a VALIDATED current one,
    so an unreadable current reset paired with an absent previous one and burned across two
    windows (delta round seat A, F7)."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path))
    p = tmp_path / "tick-last-reading.json"
    p.write_text(
        json.dumps(
            {
                "email": "a@x",
                "ts": FLEET_NOW - 60,
                "five_hour": 40.0,
                "five_hour_reset": FLEET_NOW + 3600,
                "seven_day": 30.0,
                "seven_day_reset": None,
            }
        )
    )
    row = {
        "email": "a@x",
        "five_hour": {"utilization": 45.0, "resets_at_epoch": FLEET_NOW + 3600},
        "seven_day": {"utilization": 37.0, "resets_at_epoch": int("1" + "0" * 400)},
    }
    assert cr._tick_burn("a@x", row, FLEET_NOW) == {"five_hour": 5.0, "seven_day": 0.0}


def test_tick_burn_survives_and_rewrites_a_poisoned_memory_file(tmp_path, monkeypatch):
    """The previous reading is `json.loads` of the memory file and was compared bare: a giant
    int there raised BEFORE the rewrite, so the poisoned file wedged every later tick until a
    human deleted it (heavy review round 1 seat 1, F1). Now the burn falls back to zero AND the
    file is rewritten with the finite current reading."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path))
    giant = int("9" * 400)
    p = tmp_path / "tick-last-reading.json"
    p.write_text(
        json.dumps(
            {
                "email": "a@x",
                "ts": FLEET_NOW - 60,
                "five_hour": giant,
                "five_hour_reset": giant,
                "seven_day": 30.0,
                "seven_day_reset": FLEET_NOW + 7200,
            }
        )
    )
    row = {
        "email": "a@x",
        "five_hour": {"utilization": 45.0, "resets_at_epoch": FLEET_NOW + 3600},
        "seven_day": {"utilization": 31.0, "resets_at_epoch": FLEET_NOW + 7200},
    }
    assert cr._tick_burn("a@x", row, FLEET_NOW) == {"five_hour": 0.0, "seven_day": 1.0}
    assert json.loads(p.read_text())["five_hour_reset"] == FLEET_NOW + 3600
    # the VALUE alone poisoned, the reset matching — `same_window` is True and the subtraction is
    # reached: a bare `float(pu)` there survived the battery (delta round seat B, m1)
    p.write_text(
        json.dumps(
            {
                "email": "a@x",
                "ts": FLEET_NOW - 60,
                "five_hour": giant,
                "five_hour_reset": FLEET_NOW + 3600,
                "seven_day": 30.0,
                "seven_day_reset": FLEET_NOW + 7200,
            }
        )
    )
    assert cr._tick_burn("a@x", row, FLEET_NOW) == {"five_hour": 0.0, "seven_day": 1.0}
    # a memory file that is not JSON at all is rewritten too, never left to wedge the next tick (m2)
    p.write_text("not json")
    assert cr._tick_burn("a@x", row, FLEET_NOW) == {"five_hour": 0.0, "seven_day": 0.0}
    assert json.loads(p.read_text())["email"] == "a@x"


def test_the_soonest_reset_ignores_a_zero_or_past_epoch_instead_of_letting_it_win():
    """A `0.0` reset passed the validator and won the `min()`, so a known revive rendered as
    "unknown" (heavy review round 1 seat 1, F2); a reset three days PAST won it too and the drain
    broadcast named an instant long gone — the floor is `now`, like every sibling bar (delta
    round seat A, F2)."""
    rows = [
        {
            "valid": True,
            "five_hour": {"resets_at_epoch": 0.0},
            "seven_day": {"resets_at_epoch": FLEET_NOW + 3600},
        }
    ]
    assert cr._soonest_reset(rows, FLEET_NOW) == FLEET_NOW + 3600
    rows[0]["five_hour"] = {"resets_at_epoch": FLEET_NOW - 3 * 86400}
    assert cr._soonest_reset(rows, FLEET_NOW) == FLEET_NOW + 3600
    # a reset AT now is "now", the relief writer's `>=` bar (round 3 seat C, F5)
    rows[0]["five_hour"] = {"resets_at_epoch": FLEET_NOW}
    assert cr._soonest_reset(rows, FLEET_NOW) == FLEET_NOW
    assert (
        cr._soonest_reset([{"valid": True, "five_hour": {"resets_at_epoch": -0.0}}], FLEET_NOW)
        is None
    )


def test_an_undateable_relief_epoch_is_refused_at_the_source_not_only_in_the_message():
    """A finite 1e300 passed `_usable_ts`, so the relief tuple carried it to the wall stamp and
    the ledger while only the message fell back — `_promised_resume` could never reach that
    instant and the re-arm slept for a week (heavy review round 1 seat 1, F3)."""
    now = FLEET_NOW
    rows = [
        _row("act@x", 91.0, 40.0, cap=99, s_reset=None),
        _row("far@x", 97.0, 30.0, cap=90, s_reset=1e300, w_reset=now + 86400),
    ]
    assert cr._next_session_relief(rows, "act@x", now) is None
    rows[1] = _row("far@x", 97.0, 30.0, cap=90, s_reset=now + 3000, w_reset=now + 86400)
    assert cr._next_session_relief(rows, "act@x", now) == (now + 3000, "far@x", "session")
    assert cr._dateable_ts(1e300) is None and cr._dateable_ts(now) == now
    # the mirror site: a weekly-blocked sibling whose WEEKLY reset is undateable (delta seat B, m5)
    rows[1] = _row("far@x", 97.0, 100.0, cap=90, s_reset=now + 3000, w_reset=1e300)
    assert cr._next_session_relief(rows, "act@x", now) is None


def test_the_legacy_picker_reads_an_unreadable_utilization_as_walled_and_sorts_it_last(monkeypatch):
    """`_walled` and the two utilization sort elements were the last bare reads one line from the
    guarded reset element (heavy review round 1 seat 1, F4): a string raised TypeError; now it
    reads as walled, and a bool utilization sorts as no reading."""
    assert (
        cr._walled({"five_hour": {"utilization": "x"}, "seven_day": {"utilization": 1.0}}) is True
    )
    rows = [
        {
            "name": "bool",
            "valid": True,
            "five_hour": {"utilization": 1.0},
            "seven_day": {"utilization": True, "resets_at_epoch": FLEET_NOW + 60},
        },
        {
            "name": "real",
            "valid": True,
            "five_hour": {"utilization": 1.0},
            "seven_day": {"utilization": 50.0, "resets_at_epoch": FLEET_NOW + 60},
        },
    ]
    assert cr._pick_successor(rows, None, FLEET_NOW) == "real"


def test_next_session_relief_prefers_the_soonest_session_reset_of_a_weekly_ok_sibling():
    now = FLEET_NOW
    rows = [
        _row("act@x", 91.0, 40.0, cap=99, s_reset=now + 4000),  # the active — never its own relief
        _row("late@x", 97.0, 30.0, cap=90, s_reset=now + 9000, w_reset=now + 86400),
        _row("soon@x", 98.0, 27.0, cap=90, s_reset=now + 3000, w_reset=now + 90000),
        # weekly-walled, resetting LATER than soon@x — D1 (2026-09-06): the soonest epoch across
        # both buckets wins, so an earlier weekly reset would (correctly) be the relief
        _row("wk@x", 0.0, 100.0, cap=99, s_reset=None, w_reset=now + 90000),
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
    assert (
        cr._next_session_relief(
            [_row("act@x", 91.0, 40.0), _row("a@x", 97.0, 10.0, s_reset=now - 5)], "act@x", now
        )
        is None
    )
    assert cr._next_session_relief([_row("act@x", 91.0, 40.0)], "act@x", now) is None


def test_urgent_drain_message_carries_the_operator_wording_and_the_resume_instant():
    """The operator's wording and the concrete resume instant. UPDATED 2026-09-05: the signature now
    takes the TRIGGER REASON rather than a bare percentage, because the message used to hardcode
    "5-hour session window" and print whatever number it was handed — so a weekly wall reported the
    session figure. The invariants pinned here are unchanged; only the caller's contract moved."""
    now = 1_800_000_000
    reason = "its 5-hour session window is 91% CONSUMED"
    # a relief IN THE FUTURE — a reset at/before `now` is a stale row the renderer no longer promises
    msg = cr._urgent_drain_message("act@x", reason, (float(now + 3000), "soon@x", "session"))
    assert "URGENT" in msg and "STOP YOUR WORK ASAP" in msg and "GRACEFULLY" in msg
    assert reason in msg, "the notice must say WHICH window triggered it, in its own words"
    # wording since e8f0473d (2026-09-05): "NEXT ACCOUNT AVAILABLE: <email> — its 5-hour window resets at …"
    assert "soon@x" in msg and "resets at" in msg, msg
    resume = int(now + 3000) + cr._drain_resume_lead_s()  # reset + lead, an integer epoch
    assert f"epoch {resume}" in msg, msg
    assert f"sleep $(( {resume} - $(date +%s) ))" in msg
    none = cr._urgent_drain_message("act@x", reason, None)
    assert "STOP YOUR WORK ASAP" in none and "no resume time can be given" in none


def test_urgent_tier_fires_at_ninety_with_no_successor_and_names_the_resume_time(
    tmp_path, monkeypatch
):
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
    assert (
        "URGENT" in mails[0][1]
        and f"epoch {int(now + 1800) + cr._drain_resume_lead_s()}" in mails[0][1]
    )
    assert (
        ledger[-1]["tier"] == "urgent-90"
        and ledger[-1]["resume_epoch"] == int(now + 1800) + cr._drain_resume_lead_s()
    )
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
    cr._fleet_active_wall_advisory(
        [_row("act@x", 89.0, 40.0, cap=99, slug="act")], now, threshold=95.0
    )
    assert tg == []
    # 93 but a successor exists: the flip leg is the remedy, not the mail
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: ("fresh", "fresh@x"))
    cr._fleet_active_wall_advisory(
        [_row("act@x", 93.0, 40.0, cap=99, slug="act"), _row("fresh@x", 5.0, 5.0, slug="fresh")],
        now,
        threshold=95.0,
    )
    assert tg == []


# ── BQ11: the refresh-ping budget must be spent on the STALEST reading, never by alphabet ────


def _starving_fleet(tmp_path, monkeypatch, ages):
    """Four accounts, every token too old to probe live, every cached reading past the 1h line.

    *ages* maps email -> cache age in seconds. Returns (fleet, pinged-slug recorder).
    """
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    slugs = {}
    for i, email in enumerate(sorted(ages)):
        slug = f"d{i}"
        slugs[email] = slug
        assert cr.main(["--new-dir", slug, email]) == 0
        _pin(fleet, slug, email)
        _fleet_creds(fleet, slug, f"tok-{slug}", age_s=10 * 3600.0)  # > 8h → no live probe
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-usage-cache.json").write_text(
        json.dumps(
            {
                email: {
                    "ts": FLEET_NOW - age,
                    "five_hour": {"utilization": 10.0, "resets_at_epoch": FLEET_NOW + 3600},
                    "seven_day": {"utilization": 10.0, "resets_at_epoch": FLEET_NOW + 86400},
                }
                for email, age in ages.items()
            }
        )
    )
    _fake_oauth(monkeypatch)  # the post-ping re-probe answers None → the cache row rides
    pinged = []

    def fake_run(argv, **kw):
        pinged.append(Path(dict(kw.get("env") or {})["CLAUDE_CONFIG_DIR"]).name)
        return subprocess.CompletedProcess(argv, 0, "pong", "")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    return slugs, pinged


def test_the_ping_budget_serves_the_stalest_reading_not_the_first_in_the_alphabet(
    tmp_path, monkeypatch
):
    """The 2026-09-04 fleet freeze, in one assertion.

    `_fleet_account_rows` spends ROTATE_REFRESH_MAX_PER_RUN pings inside a
    `for email in sorted(groups)` pass. With MORE stale accounts than budget, whichever account
    sorts LAST is skipped — deterministically, every run, for ever. Measured that day: four
    accounts, budget 3, and sarp@ (last in sort) reached a 405-minute-old reading while the
    other three were re-pinged each tick. `_validated_pick` refuses any cache past
    ROTATE_CACHE_TRUST_S (60m), so the one account that HAD headroom (30% on its first live reading after the operator
    switched to it by hand, 10h41m after the urgent mail) was invisible to the picker, and the
    tick printed "NO successor has headroom" 47 times (the whole tail run of that line; 87 is the log-wide count, all accounts, all time).
    """
    ages = {
        "a@ocoron.com": 2 * 3600.0,
        "b@ocoron.com": 3 * 3600.0,
        "c@ocoron.com": 4 * 3600.0,
        "z@ocoron.com": 9 * 3600.0,  # the STALEST — and last in the alphabet
    }
    slugs, pinged = _starving_fleet(tmp_path, monkeypatch, ages)

    cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=True)

    assert len(pinged) == 3, f"the per-run budget must still hold: {pinged}"
    assert slugs["z@ocoron.com"] in pinged, (
        "the STALEST reading must get a ping; serving the alphabet starves the last account "
        f"for ever (pinged {pinged}, z is {slugs['z@ocoron.com']})"
    )
    assert slugs["a@ocoron.com"] not in pinged, (
        "the FRESHEST of the stale set is the one to drop when the budget binds"
    )


def test_a_skipped_account_is_served_on_the_next_run_so_starvation_cannot_persist(
    tmp_path, monkeypatch
):
    """Staleness ordering is self-correcting: the account dropped this run is the stalest next
    run, so it outranks the three just served. That is the property a fixed order lacks."""
    ages = {
        "a@ocoron.com": 5 * 3600.0,
        "b@ocoron.com": 4 * 3600.0,
        "c@ocoron.com": 3 * 3600.0,
        "z@ocoron.com": 2 * 3600.0,  # freshest → dropped this run
    }
    slugs, pinged = _starving_fleet(tmp_path, monkeypatch, ages)
    cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=True)
    assert slugs["z@ocoron.com"] not in pinged, f"freshest is dropped first: {pinged}"

    # …an hour passes; the three served accounts refreshed their cache, z did not.
    state = tmp_path / "state"
    later = FLEET_NOW + 3600.0
    monkeypatch.setattr(cr, "_now", lambda: later)
    (state / "fleet-usage-cache.json").write_text(
        json.dumps(
            {
                email: {
                    "ts": (FLEET_NOW if email != "z@ocoron.com" else FLEET_NOW - 2 * 3600.0),
                    "five_hour": {"utilization": 10.0, "resets_at_epoch": later + 3600},
                    "seven_day": {"utilization": 10.0, "resets_at_epoch": later + 86400},
                }
                for email in ages
            }
        )
    )
    for stamp in state.glob("fleet-refresh-*"):  # the per-account stamp budget has elapsed
        os.utime(stamp, (FLEET_NOW - 7200.0, FLEET_NOW - 7200.0))
    pinged.clear()

    cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=True)

    assert slugs["z@ocoron.com"] in pinged, (
        f"the account skipped last run must be served this run — else it starves: {pinged}"
    )


# ── BQ12: the wall latch re-arms when the resume instant it PROMISED comes due ────────────────


def _walled_fleet_advisory(monkeypatch, tmp_path, relief_epoch, now):
    """One walled active account, no successor, and a sibling whose session resets at
    *relief_epoch*. Returns the list every message lands in."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    (tmp_path / "state").mkdir(exist_ok=True)
    monkeypatch.setattr(cr, "_resolve_active", lambda: "act")
    monkeypatch.setattr(cr, "_switch_paused", lambda: False)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: None)
    monkeypatch.setattr(cr, "_ledger_append", lambda e: None)
    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m: sent.append(m))
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, m: None)
    rows = [
        _row("act@x", 100.0, 40.0, cap=99, slug="act"),
        _row("sib@x", 100.0, 40.0, cap=99, slug="sib", s_reset=relief_epoch),
    ]
    return rows, sent


def test_the_latch_refires_once_the_promised_resume_instant_has_passed(tmp_path, monkeypatch):
    """2026-09-04: the 20:55 message named 21:31, nothing switched, and the fleet then sat
    walled and SILENT for 10h41m (47 no-successor ticks of that exact line) because the latch only re-arms on
    relief or after a week. A promise that comes due unmet is new information."""
    now = FLEET_NOW
    relief = now + 1800.0
    rows, sent = _walled_fleet_advisory(monkeypatch, tmp_path, relief, now)

    cr._fleet_active_wall_advisory(rows, now, threshold=95.0)
    assert len(sent) == 1, "the wall fires once on entry"
    assert f"epoch {int(relief) + cr._drain_resume_lead_s()}" in sent[0]

    # still walled five minutes later, well before the promise comes due → silent
    cr._fleet_active_wall_advisory(rows, now + 300.0, threshold=95.0)
    assert len(sent) == 1, "latched while the promise still stands"

    # the promised instant passes with the wall UNBROKEN → speak again, with the next time
    later = relief + 120.0
    rows[1]["five_hour"]["resets_at_epoch"] = later + 3600.0  # the window rolled, still walled
    cr._fleet_active_wall_advisory(rows, later, threshold=95.0)
    assert len(sent) == 2, "a broken promise must re-arm the latch, not extend the silence"
    assert f"epoch {int(later + 3600.0) + cr._drain_resume_lead_s()}" in sent[1], (
        "the new message carries the NEXT time"
    )


def test_a_stamp_written_before_the_promise_field_existed_does_not_refire_every_tick(
    tmp_path, monkeypatch
):
    """Migration: the old stamp held its own write time. Read naively that is always 'due',
    which would turn the latch into a per-tick spammer — the exact class the latch exists for."""
    now = FLEET_NOW
    rows, sent = _walled_fleet_advisory(monkeypatch, tmp_path, now + 1800.0, now)
    stamp = cr._fleet_exhaustion_stamp()
    stamp.write_text(str(int(now - 600.0)), encoding="utf-8")  # legacy content == its write time
    os.utime(stamp, (now - 600.0, now - 600.0))

    cr._fleet_active_wall_advisory(rows, now, threshold=95.0)

    assert sent == [], "a legacy stamp falls through to the week-long re-arm, not to every tick"
    assert cr._promised_resume(stamp) is None


def test_no_relief_time_means_no_promise_to_break(tmp_path, monkeypatch):
    """When no sibling reports a reset the message gives no time; the stamp must then hold no
    promise, or the latch would re-arm on the very next tick."""
    now = FLEET_NOW
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    (tmp_path / "state").mkdir(exist_ok=True)
    monkeypatch.setattr(cr, "_resolve_active", lambda: "act")
    monkeypatch.setattr(cr, "_switch_paused", lambda: False)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: None)
    monkeypatch.setattr(cr, "_ledger_append", lambda e: None)
    sent = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda m: sent.append(m))
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, m: None)
    rows = [_row("act@x", 100.0, 40.0, cap=99, slug="act")]  # nobody else at all

    cr._fleet_active_wall_advisory(rows, now, threshold=95.0)
    cr._fleet_active_wall_advisory(rows, now + 300.0, threshold=95.0)

    assert len(sent) == 1, "no promise → the plain latch still holds"
    assert "no resume time can be given" in sent[0]
    assert cr._promised_resume(cr._fleet_exhaustion_stamp()) is None


def test_the_urgent_message_does_not_promise_a_switch_it_cannot_guarantee(tmp_path, monkeypatch):
    """The wording that shipped said "the rotation will have switched to that account by the
    time you wake". It had not, 10h later. A message that asserts a future state the machinery
    does not control is a false claim broadcast to every repo."""
    msg = cr._urgent_drain_message(
        "act@x",
        "its 5-hour session window is 90% CONSUMED",
        (FLEET_NOW + 1800.0, "sib@x", "session"),
    )
    assert "will have switched" not in msg
    assert "EXPECTED, not promised" in msg
    assert "another message like this one will arrive" in msg, (
        "the relay must still be named — it is the actual wake mechanism (01M1P86NZ2)"
    )


def test_a_fresh_token_whose_live_probe_fails_still_earns_its_refresh_ping(tmp_path, monkeypatch):
    """Review finding on my own `_ping_slots`: the first cut skipped any account whose token was
    fresh enough to probe live, reasoning that the probe would refresh it "for free". But the
    account only BECOMES a ping candidate when its cached reading is already an hour old, and a
    fresh token that keeps a reading stale means the probe is FAILING — exactly the account that
    needs the ping. Skipping it also silently narrowed the dead-chain detector: `ping_failed` is
    set only in this branch, and it is what makes a dead ACTIVE chain a flip trigger (the
    2026-08-17 21:00 outage sat undetected for 9h because quota was the only trigger)."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", "d0", "a@ocoron.com"]) == 0
    _pin(fleet, "d0", "a@ocoron.com")
    _fleet_creds(fleet, "d0", "tok-d0", age_s=600.0)  # FRESH token → the live probe is attempted
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-usage-cache.json").write_text(
        json.dumps(
            {
                "a@ocoron.com": {
                    "ts": FLEET_NOW - 5 * 3600.0,  # stale despite the fresh token → probe failing
                    "five_hour": {"utilization": 10.0, "resets_at_epoch": FLEET_NOW + 3600},
                    "seven_day": {"utilization": 10.0, "resets_at_epoch": FLEET_NOW + 86400},
                }
            }
        )
    )
    _fake_oauth(monkeypatch)  # every probe answers None — the failing-probe condition
    pinged = []

    def fake_run(argv, **kw):
        pinged.append(Path(dict(kw.get("env") or {})["CLAUDE_CONFIG_DIR"]).name)
        return subprocess.CompletedProcess(argv, 1, "", "boom")  # the ping fails too

    monkeypatch.setattr(cr.subprocess, "run", fake_run)

    accounts, _pending = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=True)

    assert pinged == ["d0"], f"a fresh token with a stale reading must still be pinged: {pinged}"
    assert accounts[0]["ping_failed"] is True, (
        "and a failed ping must still mark the chain DEAD — that flag is the dead-chain flip "
        "trigger, and skipping the ping would silently retire it"
    )


def test_ping_slots_and_promised_resume_hold_at_their_edges(tmp_path, monkeypatch):
    """The two guards that have no natural caller: a budget an operator can set to zero, and a
    stamp whose content is not a number. Both must fail SAFE — no pings, and no promise."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    (tmp_path / "state").mkdir(exist_ok=True)
    groups = {"a@x": [{"slug": "d0", "dir": tmp_path / "d0", "mtime": FLEET_NOW - 10 * 3600.0}]}
    cache = {"a@x": {"ts": FLEET_NOW - 9 * 3600.0}}

    monkeypatch.setenv("ROTATE_REFRESH_MAX_PER_RUN", "0")
    assert cr._ping_slots(groups, cache, FLEET_NOW) == set(), "a zero budget spends nothing"
    monkeypatch.setenv("ROTATE_REFRESH_MAX_PER_RUN", "3")
    assert cr._ping_slots(groups, cache, FLEET_NOW) == {"a@x"}, "guard: it would fire otherwise"
    # an account with no credentialed dir has no chain to ping
    assert (
        cr._ping_slots({"b@x": [{"slug": "d1", "dir": tmp_path, "mtime": None}]}, {}, FLEET_NOW)
        == set()
    )

    stamp = tmp_path / "state" / "probe-stamp"
    for content in ("", "not-a-number", "0"):
        stamp.write_text(content)
        assert cr._promised_resume(stamp) is None, f"{content!r} is not a promise"
    assert cr._promised_resume(tmp_path / "state" / "absent") is None


# ── The drain notice must name the window that actually TRIGGERED it ──────────────────────────
#
# fabrik-lib finding 01M1P86NZ2DEDGKJ62CS3K346A, and a second defect found while reading it. The
# notice sent 2026-09-04T12:59Z said the active account was "at 10% of its 5-hour session window"
# and ordered an immediate graceful stop — a number that argues against its own instruction. Cause:
# the message hardcodes "5-hour session window" and is handed `session_pct` no matter which tier
# fired, so a WEEKLY wall reports the SESSION number. The unit was ambiguous too ("at 90%" one day,
# "at 10%" the next, both ordering a stop).


def test_a_weekly_wall_names_the_weekly_window_not_the_session():
    """The reported defect: walled on weekly, but the notice talked about the 5-hour window."""
    row = {
        "email": "ob@ocoron.com",
        "five_hour": {"utilization": 10.0},
        "seven_day": {"utilization": 100.0},
        "weekly_cap": None,
    }
    reason = cr._drain_trigger_reason(row, session_pct=10.0, walled=True)
    msg = cr._urgent_drain_message("ob@ocoron.com", reason, None)

    assert "weekly" in msg.lower()
    assert "10%" not in msg, "the SESSION number must not be quoted when the WEEKLY window walled"
    assert "100%" in msg


def test_an_operator_cap_says_so_rather_than_claiming_the_window_is_full():
    """ob@ sat at weekly 80% against a caps.json cap of 80 — walled by OUR reserve, not by Anthropic.
    Reporting that as a full window would send agents hunting a limit that is not there."""
    row = {
        "email": "ob@ocoron.com",
        "five_hour": {"utilization": 12.0},
        "seven_day": {"utilization": 81.0},
        "weekly_cap": 80,
    }
    reason = cr._drain_trigger_reason(row, session_pct=12.0, walled=True)

    assert "cap" in reason.lower() and "81%" in reason
    assert "caps.json" in reason


def test_a_session_drain_names_the_session_window_and_its_unit():
    row = {
        "email": "ob@ocoron.com",
        "five_hour": {"utilization": 94.0},
        "seven_day": {"utilization": 40.0},
        "weekly_cap": None,
    }
    reason = cr._drain_trigger_reason(row, session_pct=94.0, walled=False)
    msg = cr._urgent_drain_message("ob@ocoron.com", reason, None)

    assert "5-hour session" in msg and "94%" in msg
    assert "CONSUMED" in msg, (
        "name the unit — '90%' and '10%' both ordered a stop on consecutive days"
    )


def test_the_self_scheduled_sleep_is_a_courtesy_and_the_relay_is_the_mechanism():
    """fabrik-lib followed the old wording exactly, armed the sleep, and resumed 15.5h LATE — only
    when the next notice arrived. A background `sleep` is session-scoped: it dies with the very stop
    it is timing. An agent that reads self-scheduling as coverage believes it is protected while
    nothing is running."""
    relief = (1788530459.0, "can@ocoron.com", "session")
    msg = cr._urgent_drain_message(
        "ob@ocoron.com", "its 5-hour session window is 94% CONSUMED", relief
    )

    low = msg.lower()
    assert "follow-up notice" in low, "the relay must be named as the mechanism"
    relay_at, sleep_at = low.index("follow-up notice"), low.index("sleep")
    assert relay_at < sleep_at, "the relay must LEAD; the timer is secondary"
    assert "courtesy" in low
    assert "session-scoped" in low or "dies with" in low, "say WHY the timer cannot be relied on"
    assert str(1788530459 + cr._drain_resume_lead_s()) in msg, (
        "the concrete resume epoch (reset + lead) must still be there"
    )


# ── drain-band relief flip (operator directive 2026-09-06; incident 23:01-23:17 +03) ───────────
def _drain_relief_fleet(tmp_path, monkeypatch, active, successor, cap=99):
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    (fleet / "caps.json").write_text(json.dumps({"sarp@ocoron.com": cap}))
    _fake_oauth(
        monkeypatch, usages={"tok-seo": _usage_blob(*active), "tok-intel": _usage_blob(*successor)}
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    return fleet


def test_relief_on_a_sibling_flips_the_pointer_off_an_active_in_the_drain_band(
    tmp_path, monkeypatch, capsys
):
    """The incident: mob@ at session 93 / weekly 97 (cap 99) is not TRIPPED, so the flip leg said
    "no flip" for sixteen minutes while ozgurbasak@ sat at 0 / 19 — every session released by the
    hold resumed on the drained account. Relief on a sibling IS a flip when the active is in the
    drain band and the successor is below it on both windows."""
    fleet = _drain_relief_fleet(tmp_path, monkeypatch, active=(93.0, 97.0), successor=(0.0, 19.0))
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out
    assert os.readlink(fleet / "active") == "intel", out
    assert "drain-band relief" in out and "flipped -> ob@ocoron.com (intel)" in out, out
    lines = (tmp_path / "state" / "rotate-ledger.jsonl").read_text().splitlines()
    flip = next(e for e in map(json.loads, lines) if e.get("event") == "flip")
    assert (flip["from"], flip["to"]) == ("seo", "intel")
    # …and the NEXT tick does not bounce back: the fresh active (0/19) is below the band, and the
    # drained account is refused as a target (session 93 > the picker's 85 bar) — no ping-pong
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    out2 = capsys.readouterr().out
    assert os.readlink(fleet / "active") == "intel", out2
    assert "drain-band relief" not in out2 and "flipped" not in out2, out2


def test_relief_flip_needs_a_successor_below_the_drain_threshold_on_both_windows(
    tmp_path, monkeypatch, capsys
):
    """Hysteresis: a successor at weekly 87 is itself in the band — flipping to it would flip
    back next tick. No drain-band flip; the ordinary trip rule still governs."""
    fleet = _drain_relief_fleet(tmp_path, monkeypatch, active=(93.0, 97.0), successor=(30.0, 87.0))
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out
    assert os.readlink(fleet / "active") == "seo", out
    assert "drain-band relief" not in out


def test_an_active_below_the_drain_band_never_relief_flips(tmp_path, monkeypatch, capsys):
    fleet = _drain_relief_fleet(tmp_path, monkeypatch, active=(60.0, 50.0), successor=(0.0, 19.0))
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    assert os.readlink(fleet / "active") == "seo"


def test_an_active_in_the_drain_band_with_no_eligible_sibling_stays_put(
    tmp_path, monkeypatch, capsys
):
    """Scoped review F8: the moved fixtures left "in the band, nobody to flip to" untested. The
    sibling is itself in the band on its weekly, so it is not below-drain on both windows."""
    fleet = _drain_relief_fleet(tmp_path, monkeypatch, active=(93.0, 97.0), successor=(20.0, 88.0))
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out
    assert os.readlink(fleet / "active") == "seo", out
    assert "drain-band relief" not in out and "no flip" in out, out


def test_relief_flips_even_within_the_dwell_of_the_last_flip(tmp_path, monkeypatch, capsys):
    """Native reader R2 (HIGH), end to end: a flip five minutes ago used to hold the relief while the
    advisory leg lifted the hold — every released session landed on the drained account for up to
    30 min. Relief is dwell-exempt; the ledger row is `kind: relief`."""
    fleet = _drain_relief_fleet(tmp_path, monkeypatch, active=(93.0, 97.0), successor=(0.0, 19.0))
    ledger = tmp_path / "state" / "rotate-ledger.jsonl"
    ledger.parent.mkdir(exist_ok=True)
    ledger.write_text(
        json.dumps(
            {
                "event": "flip",
                "ts": time.time() - 300,
                "from": "intel",
                "to": "seo",
                "at_pct": 96.0,
                "via": "tick",
            }
        )
        + "\n"
    )
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    out = capsys.readouterr().out
    assert os.readlink(fleet / "active") == "intel", out
    rows = [json.loads(ln) for ln in ledger.read_text().splitlines()]
    # by EVENT, not by position: the fleet tick also appends its own `tick` row now (D-201, the
    # burst sample), so "the last row" is no longer "the flip". Both production readers already
    # filtered by event name — `_last_event_ts` and the picture's last-flip scan — which is why
    # this was a test-only assumption and not a defect.
    flips = [r for r in rows if r.get("event") == "flip"]
    assert flips and flips[-1]["kind"] == "relief", rows[-3:]
    assert (flips[-1]["from"], flips[-1]["to"]) == ("seo", "intel"), flips[-1]


# ── relief wake (plan 2026-09-07-plan-1-relief-wake, Phase A.4) ──────────────────────────────


def _armed_watch(tmp_path, monkeypatch, sid="pane1"):
    """A tmp lock dir with ONE armed self-watch (an exclusive flock held for the test's life —
    `claude-selfwatch.sh:30-34`'s shape). Returns (locks, fd)."""
    import fcntl
    import os

    locks = tmp_path / "locks"
    locks.mkdir(exist_ok=True)
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    fd = os.open(str(locks / f"{sid}.selfwatch.lock"), os.O_WRONLY | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return locks, fd


def _lifted_rows():
    return [
        json.loads(line)
        for line in (cr._rotate_state_dir() / "rotate-ledger.jsonl").read_text().splitlines()
        if '"hold-lifted"' in line
    ]


def test_relief_wakes_the_armed_watch_once_and_only_on_the_transition(tmp_path, monkeypatch):
    """A.4(a): the wall sets the stamp; a sibling regaining headroom relieves it → the ONE armed
    pane gets `<sid>.holdlifted` with the tick's epoch and a `reason="relief"` row; the next
    tick (no stamp) writes nothing more — dedup by the exists→unlink transition."""
    import os

    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    locks, fd = _armed_watch(tmp_path, monkeypatch)
    try:
        _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
        _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
        usages = {"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)}
        _fake_oauth(monkeypatch, usages=usages)
        _fleet_tick_spies(monkeypatch)
        monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
        monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
        _point(fleet, "seo")
        assert cr._cmd_tick() == 0  # the wall: stamp set
        assert cr._fleet_exhaustion_stamp().exists()
        assert not (locks / "pane1.holdlifted").exists()
        usages["tok-intel"] = _usage_blob(10.0, 10.0)  # headroom returns
        _fake_oauth(monkeypatch, usages=usages)
        assert cr._cmd_tick() == 0  # relief: stamp unlinked + the wake
        assert not cr._fleet_exhaustion_stamp().exists()
        assert (locks / "pane1.holdlifted").read_text() == f"{int(FLEET_NOW)}\n"
        rows = _lifted_rows()
        assert len(rows) == 1 and rows[0]["reason"] == "relief" and rows[0]["woken"] == 1
        assert rows[0]["armed"] == 1 and rows[0]["dead"] == 0
        (locks / "pane1.holdlifted").unlink()
        assert cr._cmd_tick() == 0  # still relieved, no stamp → nothing to lift
        assert not (locks / "pane1.holdlifted").exists()
        assert len(_lifted_rows()) == 1
    finally:
        os.close(fd)


def test_a_transient_dwell_unlink_wakes_with_reason_dwell(tmp_path, monkeypatch):
    """A.4(b): the stamp stands, the active is still walled, but a validated successor exists and
    rotation is not paused — the dwell site (`:4764-4766` shipped; `:4605` at plan time) unlinks and the wake fires with `reason="dwell"`."""
    import os

    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    locks, fd = _armed_watch(tmp_path, monkeypatch)
    try:
        _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
        _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
        usages = {"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)}
        _fake_oauth(monkeypatch, usages=usages)
        _fleet_tick_spies(monkeypatch)
        monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
        monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
        _point(fleet, "seo")
        assert cr._cmd_tick() == 0
        assert cr._fleet_exhaustion_stamp().exists()
        monkeypatch.setattr(cr, "_validated_pick", lambda *a, **k: ("intel", "ob@ocoron.com"))
        monkeypatch.setattr(cr, "_switch_paused", lambda: False)
        assert cr._cmd_tick() == 0
        assert not cr._fleet_exhaustion_stamp().exists()
        rows = _lifted_rows()
        assert rows and rows[-1]["reason"] == "dwell" and rows[-1]["woken"] == 1
        assert (locks / "pane1.holdlifted").exists()
    finally:
        os.close(fd)


def test_a_probe_blackout_keeps_the_hold_and_wakes_nobody(tmp_path, monkeypatch):
    """Phase A.4(c) as refined by D-180 (the heavy review, R4): a wall episode is latched and the
    tick's next reading is a PROBE BLACKOUT (every window `None`) — the stamp is KEPT (a blackout is
    not relief; unlinking it consumed the wake's only transition), NO lift file is written, and no
    `hold-lifted` row is appended (no transition happened). Before D-180 this test pinned the lossy
    behaviour: unlink without waking.
    """
    import os

    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    locks, fd = _armed_watch(tmp_path, monkeypatch)
    try:
        _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
        _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
        _fake_oauth(
            monkeypatch,
            usages={"tok-seo": _usage_blob(None, None), "tok-intel": _usage_blob(None, None)},
        )
        _fleet_tick_spies(monkeypatch)
        monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
        monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
        _point(fleet, "seo")
        stamp = cr._fleet_exhaustion_stamp()
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text("0")  # a wall episode is latched from an earlier tick
        assert cr._cmd_tick() == 0
        assert stamp.exists(), "D-180: no reading → the stamp is KEPT (a blackout is not relief)"
        assert not (locks / "pane1.holdlifted").exists(), "a blackout never wakes the fleet"
        ledger = cr._rotate_state_dir() / "rotate-ledger.jsonl"
        rows = (
            _lifted_rows() if ledger.exists() else []
        )  # D-180: no transition → maybe no ledger at all
        assert not [r for r in rows if r.get("event") == "hold-lifted"], (
            rows
        )  # no transition → no row
    finally:
        os.close(fd)


def test_an_unusable_lock_dir_never_aborts_the_tick(tmp_path, monkeypatch):
    """A.4(d): the lock dir is a FILE → the relief tick still returns 0 and the row carries
    `errors >= 1` (fail-open on the mesh, visible in the ledger)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    bogus = tmp_path / "locks-as-a-file"
    bogus.write_text("not a dir")
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(bogus))
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    usages = {"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)}
    _fake_oauth(monkeypatch, usages=usages)
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    _point(fleet, "seo")
    assert cr._cmd_tick() == 0
    usages["tok-intel"] = _usage_blob(10.0, 10.0)
    _fake_oauth(monkeypatch, usages=usages)
    assert cr._cmd_tick() == 0
    rows = _lifted_rows()
    assert rows and rows[-1]["errors"] >= 1 and rows[-1]["woken"] == 0


def test_the_fleet_tick_ledgers_the_active_session_reading(tmp_path, monkeypatch, capsys):
    """D-201: without this row the threshold cannot be tuned again, only guessed.

    The legacy tick wrote `{"event": "tick", "verdict": "ok", "pct": …}` every pass; the FLEET
    tick never did. So the burst distribution behind the 95-vs-98 argument stops dead on
    2026-08-15 — the day this box moved to fleet mode — and `_rotate_threshold`'s own docstring
    had to say the numbers it quotes cannot be refreshed. One row per tick, ACTIVE account only.
    """
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(42.0, 50.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    rows: list[dict] = []
    monkeypatch.setattr(cr, "_ledger_append", rows.append)
    assert cr._cmd_tick() == 0

    ticks = [r for r in rows if r.get("event") == "tick"]
    assert len(ticks) == 1, f"exactly one row per tick, for the ACTIVE account only: {ticks}"
    t = ticks[0]
    # WHICH account is active is the fixture's business, not this grader's — assert the row is
    # self-consistent instead of hardcoding it, which is how the first draft of this test failed.
    sessions = {"seo": 42.0, "intel": 10.0}
    slug = "seo" if "sarp" in str(t["account"]) else "intel"
    assert t["pct"] == sessions[slug], t  # the SESSION window, never the max of both windows
    assert t["pct"] != 50.0, "50 is seo's WEEKLY — the flip line governs the session window"
    assert t["verdict"] == "ok" and t["account"] and "source" in t, t


def test_the_fleet_tick_ledgers_the_weekly_reading_beside_the_session_one(tmp_path, monkeypatch):
    """The bands contract keys RED on the account's HOTTEST window; the tick recorded only the
    SESSION one, so a weekly urgent line could never be tuned — only argued. Measured 2026-09-16:
    a scan of all 2,498 rotate-ledger rows found NO weekly-ish key on any row, while three of five
    live accounts sat weekly-hot and session-cold (mob 98/0, ob 100/0, sarp 97/0) — exactly the
    band `_urgent_drain_pct` (session-gated, read in `_fleet_active_wall_advisory`) cannot see.

    Same row, one added field: the write CONDITION is deliberately unchanged, so no row starts or
    stops existing and every reader's population is byte-for-byte what it was (the mirror).
    """
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(42.0, 50.0), "tok-intel": _usage_blob(10.0, 20.0)},
    )
    rows: list[dict] = []
    monkeypatch.setattr(cr, "_ledger_append", rows.append)
    assert cr._cmd_tick() == 0

    ticks = [r for r in rows if r.get("event") == "tick"]
    assert len(ticks) == 1, f"one row per tick, ACTIVE account only: {ticks}"
    t = ticks[0]
    slug = "seo" if "sarp" in str(t["account"]) else "intel"
    sessions, weeklies = {"seo": 42.0, "intel": 10.0}, {"seo": 50.0, "intel": 20.0}
    assert t.get("weekly_pct") == weeklies[slug], (
        f"the SEVEN_DAY window belongs on the row beside pct: {t}"
    )
    # ⚠️ BOTH fixture accounts carry weekly != session on purpose. The first cut gave intel
    # 10/10 and guarded this assert with `if slug == "seo"`, so on the intel branch a code path
    # that wrote `pct` into `weekly_pct` would have passed — the grader would prove nothing
    # exactly where it is the only witness. Unconditional now, whichever account the fixture
    # elects as active.
    assert t["weekly_pct"] != t["pct"], (
        f"session and weekly must be distinguishable on the row, not coincidentally equal: {t}"
    )
    assert t["pct"] == sessions[slug], f"pct stays the SESSION window, unmoved by this change: {t}"


@pytest.mark.parametrize("weekly", [0.0, 99.0])
def test_the_weekly_reading_is_recorded_at_both_ends_of_its_range(tmp_path, monkeypatch, weekly):
    """Two mutations survived the first graders, and both live at the ends of the range.

    `if _wk:` (a truthiness guard, the likeliest simplification of that line) DROPS a weekly
    reading of exactly 0.0 — which is what an account reads right after its weekly reset — and the
    absent-window grader then reads that omission as "no reading". `_wk < 99.0` drops the HIGH
    band, which is the RED case the field exists to observe. Both passed every earlier test.
    """
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(42.0, 50.0), "tok-intel": _usage_blob(10.0, 20.0)},
    )
    monkeypatch.setattr(
        cr,
        "_active_account_walled",
        lambda accounts, threshold: (
            False,
            {
                "email": "edge@ocoron.com",
                "source": "live",
                "five_hour": {"utilization": 42.0},
                "seven_day": {"utilization": weekly},
            },
        ),
    )
    rows: list[dict] = []
    monkeypatch.setattr(cr, "_ledger_append", rows.append)
    assert cr._cmd_tick() == 0

    t = next(r for r in rows if r.get("event") == "tick")
    assert "weekly_pct" in t, f"a {weekly} reading is a READING, not an absence: {t}"
    assert t["weekly_pct"] == weekly, t


def test_the_tick_row_still_writes_when_the_weekly_window_is_absent(tmp_path, monkeypatch):
    """The MIRROR half of the weekly field, and the half prose alone was asserting.

    The change's whole safety claim is "the write CONDITION is unchanged, so no row starts or stops
    existing". Nothing held that: a mutation making the weekly key unconditional
    (`_row["weekly_pct"] = float(_wk or 0)`) passed the entire suite, and so would one that moved
    the weekly read ABOVE the session gate and dropped the row when `seven_day` is missing. Here the
    account has NO seven_day window at all: the row must still be written, still carry the session
    `pct`, and simply omit `weekly_pct`.
    """
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(42.0, 50.0), "tok-intel": _usage_blob(10.0, 20.0)},
    )
    # ⚠️ Injected HERE, not by deleting `seven_day` from the usage blob: `_usage_windows` is
    # all-or-nothing (None when EITHER window is malformed), so a blob without `seven_day` yields
    # no reading at all and therefore no row — which grades nothing. That is also why this branch
    # is DEFENSIVE: no producer on this box can currently emit session-without-weekly.
    monkeypatch.setattr(
        cr,
        "_active_account_walled",
        lambda accounts, threshold: (
            False,
            {
                "email": "weekly-less@ocoron.com",
                "source": "live",
                "five_hour": {"utilization": 42.0},
            },
        ),
    )
    rows: list[dict] = []
    monkeypatch.setattr(cr, "_ledger_append", rows.append)
    assert cr._cmd_tick() == 0

    ticks = [r for r in rows if r.get("event") == "tick"]
    assert len(ticks) == 1, f"the row must still be written without a weekly window: {ticks}"
    t = ticks[0]
    assert "weekly_pct" not in t, f"an absent window omits the key, never invents a 0.0: {t}"
    assert t.get("pct") == 42.0, f"the session reading is unaffected by the weekly guard: {t}"


# ── D-269: the quota posture — the tick writes it, --status shows it ─────────────────────────────


def _posture_path(tmp_path):
    return tmp_path / "state" / "quota-posture.json"


def _posture_fixture(tmp_path, monkeypatch, seo=(42.0, 50.0), intel=(10.0, 20.0), **blob_kw):
    """Two live accounts, both freshly probed on every tick (a <8h token re-probes). Returns
    (fleet, rows_captured_by_ledger_append)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={
            "tok-seo": _usage_blob(*seo, **blob_kw),
            "tok-intel": _usage_blob(*intel, **blob_kw),
        },
    )
    rows: list[dict] = []
    monkeypatch.setattr(cr, "_ledger_append", rows.append)
    return fleet, rows


def _tick_row(rows):
    ticks = [r for r in rows if r.get("event") == "tick"]
    assert len(ticks) == 1, ticks
    return ticks[0]


def test_the_fleet_tick_writes_the_quota_posture_file_atomically(tmp_path, monkeypatch):
    """B1 — one file per tick, atomic, describing the ACTIVE account the ledger row names."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    # the test's NAME claims atomic, so record the mechanism rather than only the absence of
    # litter: a direct `p.write_text(...)` regression leaves the file present and no .tmp
    # behind, and would pass every assertion below (review round 1, seat 3)
    replaced: list[tuple[str, str]] = []
    _real_replace = os.replace

    def _spy(src, dst, *a, **kw):
        replaced.append((str(src), str(dst)))
        return _real_replace(src, dst, *a, **kw)

    monkeypatch.setattr(cr.os, "replace", _spy)
    assert cr._cmd_tick() == 0
    p = _posture_path(tmp_path)
    assert p.exists() and not p.with_name(p.name + ".tmp").exists()
    posture_writes = [(s, d) for s, d in replaced if Path(d) == p]
    assert posture_writes, f"the posture was written without os.replace: {replaced}"
    src, dst = posture_writes[-1]
    assert Path(src).parent == p.parent, (src, dst)
    posture = json.loads(p.read_text())
    t = _tick_row(rows)
    assert posture["schema"] == 1 and abs(posture["ts"] - FLEET_NOW) <= 5.0
    assert posture["active"]["email"] == t["account"]
    assert posture["active"]["windows"]["five_hour"]["utilization"] == t["pct"]
    assert posture["active"]["windows"]["seven_day"]["utilization"] == t["weekly_pct"]
    assert posture["fleet"]["thresholds"] == {"trip": 98.0, "drain_band": 85.0, "urgent": 90.0}


def test_posture_burn_is_null_on_the_first_sample_and_positive_on_the_second(tmp_path, monkeypatch):
    """B2 — the smoothed burn needs two samples of the same window 300 s apart; the second file
    forecasts the wall from it."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    assert cr._cmd_tick() == 0
    first = json.loads(_posture_path(tmp_path).read_text())
    assert first["active"]["windows"]["five_hour"]["burn_per_min"] is None
    active = first["active"]["email"]
    tok = "tok-seo" if "sarp" in active else "tok-intel"
    other = "tok-intel" if tok == "tok-seo" else "tok-seo"
    base_s, base_w = (
        first["active"]["windows"]["five_hour"]["utilization"],
        first["active"]["windows"]["seven_day"]["utilization"],
    )
    _fake_oauth(
        monkeypatch,
        usages={tok: _usage_blob(base_s + 3.0, base_w), other: _usage_blob(10.0, 20.0)},
    )
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW + 300.0)
    assert cr._cmd_tick() == 0
    second = json.loads(_posture_path(tmp_path).read_text())
    fh, wk = second["active"]["windows"]["five_hour"], second["active"]["windows"]["seven_day"]
    assert second["active"]["email"] == active
    assert abs(fh["burn_per_min"] - 0.6) < 1e-9, fh
    assert abs(fh["minutes_to_wall"] - (100.0 - (base_s + 3.0)) / 0.6) < 1e-6, fh
    assert fh["verdict"] == "wall_first", fh  # the fixture's reset is months away
    assert (
        wk["burn_per_min"] == 0.0
        and wk["minutes_to_wall"] is None
        and wk["verdict"] == "reset_first"
    ), wk


def test_posture_burn_restarts_when_the_window_reset_epoch_moves(tmp_path, monkeypatch):
    """B3 — a moved reset epoch is a NEW window: no burn until it has two samples of its own."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    assert cr._cmd_tick() == 0
    first = json.loads(_posture_path(tmp_path).read_text())
    active = first["active"]["email"]
    tok = "tok-seo" if "sarp" in active else "tok-intel"
    other = "tok-intel" if tok == "tok-seo" else "tok-seo"
    _fake_oauth(
        monkeypatch,
        usages={
            tok: _usage_blob(60.0, 50.0, session_reset="2027-01-21T00:00:00+00:00"),
            other: _usage_blob(10.0, 20.0),
        },
    )
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW + 300.0)
    assert cr._cmd_tick() == 0
    second = json.loads(_posture_path(tmp_path).read_text())
    assert second["active"]["windows"]["five_hour"]["burn_per_min"] is None


def test_posture_samples_ring_is_bounded_and_per_email(tmp_path, monkeypatch):
    """B4 — at most 8 kept samples (the 35-minute window at the 5-minute cadence); a new active
    email starts with one sample and no burn."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    for i in range(12):
        monkeypatch.setattr(cr, "_now", lambda i=i: FLEET_NOW + 300.0 * i)
        assert cr._cmd_tick() == 0
    posture = json.loads(_posture_path(tmp_path).read_text())
    active = posture["active"]["email"]
    assert list(posture["samples"]) == [active]
    assert 2 <= len(posture["samples"][active]) <= cr._RING_LEN == 8
    # a flip: the same prev ring, a picture whose active is the OTHER account
    rows_now, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    other_row = next(r for r in rows_now if r["email"] != active)
    pic = cr._fleet_picture(rows_now, other_row["slugs"][0], FLEET_NOW + 300.0 * 12)
    flipped = cr._quota_posture(rows_now, pic, FLEET_NOW + 300.0 * 12, posture, hold=False)
    assert list(flipped["samples"]) == [other_row["email"]]
    assert len(flipped["samples"][other_row["email"]]) == 1
    assert flipped["active"]["windows"]["five_hour"]["burn_per_min"] is None


def test_posture_ring_length_is_derived_from_the_window_and_cadence():
    """B13 — one constant moves on a cadence change, and the identity is graded."""
    assert cr._RING_LEN == int(cr._RING_WINDOW_S // cr._TICK_PERIOD_S) + 1 == 8


@pytest.mark.parametrize(
    ("session", "weekly", "expect"),
    [
        (84.9, 10.0, "GREEN"),
        (85.0, 10.0, "AMBER"),
        (10.0, 89.9, "AMBER"),
        (10.0, 90.0, "RED"),
        (0.0, 0.0, "GREEN"),
    ],
)
def test_posture_band_follows_the_hottest_window_and_the_hold(
    tmp_path, monkeypatch, session, weekly, expect
):
    """B5 — the raw D-265 line on the hottest of the two windows; WALL on the hold; null on no reading."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    assert cr._cmd_tick() == 0
    rows_now, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    active = json.loads(_posture_path(tmp_path).read_text())["active"]["email"]
    row = next(r for r in rows_now if r["email"] == active)
    row["five_hour"]["utilization"], row["seven_day"]["utilization"] = session, weekly
    pic = cr._fleet_picture(rows_now, row["slugs"][0], FLEET_NOW)
    got = cr._quota_posture(rows_now, pic, FLEET_NOW, None, hold=False)
    assert (
        got["active"]["band_account"] == expect and got["active"]["band_account_fable"] == expect
    ), got["active"]
    assert cr._quota_posture(rows_now, pic, FLEET_NOW, None, hold=True)["active"]["band"] == "WALL"
    row["five_hour"], row["seven_day"] = None, None
    # the sibling is made HOT on weekly so the fleet's band is AMBER — a hardcoded GREEN would pass
    # against a cool sibling (Delta 8 seat A #3); the expectation below is derived, not typed
    other_row = next(r for r in rows_now if r["email"] != row["email"])
    other_row["seven_day"]["utilization"] = 88.0
    pic2 = cr._fleet_picture(rows_now, row["slugs"][0], FLEET_NOW)
    blank = cr._quota_posture(rows_now, pic2, FLEET_NOW, None, hold=False)
    # the ACCOUNT's band is null with no reading; the FLEET's band is not, because the other
    # account still serves — which is exactly the per-window design (operator ruling 2026-09-17)
    assert blank["active"]["band_account"] is None and blank["active"]["hottest"] is None
    # the fleet's reading survives a blank active row — and it is the OTHER account's, by name and
    # value, not merely a GREEN label a hardcoded band would also print (closing seat 5)
    other = next(r for r in rows_now if r["email"] != active)
    assert blank["fleet"]["windows"]["seven_day"] == {
        "utilization": other["seven_day"]["utilization"],
        "slug": other["slugs"][0],
    }
    assert blank["active"]["band"] == cr._band_of(
        max(other["five_hour"]["utilization"], other["seven_day"]["utilization"]), False, 85.0, 90.0
    )
    assert blank["active"]["windows"]["five_hour"]["utilization"] is None


def test_posture_is_still_written_when_the_active_account_has_no_reading(tmp_path, monkeypatch):
    """B5 (the file half) — no reading ⇒ band null, and the file exists anyway (the hook then
    prints `band ?`, never nothing)."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(monkeypatch, usages={})  # the endpoint answers nothing for every token
    assert cr._cmd_tick() == 0
    posture = json.loads(_posture_path(tmp_path).read_text())
    assert posture["schema"] == 1 and posture["active"]["band"] is None


def test_posture_carries_the_fable_window_and_keys_band_fable_on_it(tmp_path, monkeypatch):
    """B6 — the Fable weekly-scoped window rides the posture; band_fable includes it, band does not."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch, fable=32.0)
    assert cr._cmd_tick() == 0
    p = json.loads(_posture_path(tmp_path).read_text())["active"]
    assert p["windows"]["fable"]["utilization"] == 32.0 and "Fable" in p["windows"]["models"]
    assert p["band"] == "GREEN" and p["band_fable"] == "GREEN"
    rows_now, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    row = next(r for r in rows_now if r["email"] == p["email"])
    row["model_windows"]["Fable"]["utilization"] = 91.0
    pic = cr._fleet_picture(rows_now, row["slugs"][0], FLEET_NOW)
    hot = cr._quota_posture(rows_now, pic, FLEET_NOW, None, hold=False)["active"]
    assert (
        hot["band_account"] == "GREEN"
        and hot["band_account_fable"] == "RED"
        and hot["hottest_fable"] == "fable"
    ), hot
    row.pop("model_windows", None)
    pic = cr._fleet_picture(rows_now, row["slugs"][0], FLEET_NOW)
    none = cr._quota_posture(rows_now, pic, FLEET_NOW, None, hold=False)["active"]
    assert none["windows"]["fable"] is None and none["band_account_fable"] == none["band_account"]


def test_the_fleet_tick_ledgers_the_fable_reading_beside_the_weekly_one(tmp_path, monkeypatch):
    """B11 — `fable_pct` on the tick row, same guard and write condition as `weekly_pct`."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch, fable=32.0)
    assert cr._cmd_tick() == 0
    assert _tick_row(rows)["fable_pct"] == 32.0
    _fleet2, rows2 = _posture_fixture(tmp_path / "b", monkeypatch)
    assert cr._cmd_tick() == 0
    t = _tick_row(rows2)
    assert "fable_pct" not in t and "weekly_pct" in t


def test_posture_weekly_wall_is_the_caps_json_cap(tmp_path, monkeypatch):
    """B7 — the weekly wall is the operator's cap when one exists."""
    fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    _caps(fleet, {"sarp@ocoron.com": 95, "ob@ocoron.com": 95})
    assert cr._cmd_tick() == 0
    p = json.loads(_posture_path(tmp_path).read_text())["active"]
    assert p["weekly_cap"] == 95.0 and p["windows"]["seven_day"]["wall_pct"] == 95.0
    assert p["windows"]["five_hour"]["wall_pct"] == 100.0


def test_posture_forecast_reaches_the_wall_at_the_weekly_cap(tmp_path, monkeypatch, capsys):
    """B12 — both accounts cap-walled (no successor, so the flip leg leaves the pointer): the
    posture names the capped account, the ACCOUNT band stays the raw line (GREEN at 80) while the
    FLEET band is RED and the line says which windows nobody serves, the forecast says the wall is
    reached; the NEXT tick reads WALL because the advisory stamped."""
    fleet, rows = _posture_fixture(tmp_path, monkeypatch, seo=(10.0, 80.0), intel=(10.0, 80.0))
    _caps(fleet, {"sarp@ocoron.com": 80, "ob@ocoron.com": 80})
    assert cr._cmd_tick() == 0
    p = json.loads(_posture_path(tmp_path).read_text())["active"]
    wk = p["windows"]["seven_day"]
    # the account sits AT its cap, so `_fleet_readings` walls it and nobody serves either window:
    # the FLEET band is RED (D-275, Delta 8 seat A) while the account's own raw reading stays GREEN
    # on the 85/90 line — the two bands are the point, not a contradiction
    assert p["band_account"] == "GREEN" and p["band"] == "RED" and wk["wall_pct"] == 80.0, p
    # both accounts measured, neither serving: the worst case rendered NO fleet section at all
    # (Delta 9 seat A, F2) — the map is empty either way, `measured` tells them apart
    full = json.loads(_posture_path(tmp_path).read_text())
    assert full["fleet"]["measured"] == 2 and full["fleet"]["windows"] == {}, full["fleet"]
    line = cr._posture_status_line(full, FLEET_NOW)
    assert "fleet 5h — (nobody serves it) weekly — (nobody serves it)" in line, line
    assert (
        wk["minutes_to_wall"] == 0.0
        and wk["verdict"] == "wall_first"
        and wk["burn_per_min"] is None
    )
    assert cr._fmt_forecast(wk) == "wall in ~0m at —%/m"
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW + 300.0)
    assert cr._cmd_tick() == 0
    second = json.loads(_posture_path(tmp_path).read_text())["active"]
    assert second["band"] == "WALL", second


def test_posture_successor_is_the_first_eligible_after_the_active(tmp_path, monkeypatch):
    """The successor is the first ELIGIBLE row after the active in the picker's queue; a row with
    no slug is skipped (skip-and-continue); none ⇒ null."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    assert cr._cmd_tick() == 0
    posture = json.loads(_posture_path(tmp_path).read_text())
    active = posture["active"]["email"]
    rows_now, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    other = next(r for r in rows_now if r["email"] != active)
    assert posture["fleet"]["successor"] == {"email": other["email"], "slug": other["slugs"][0]}
    # two eligible siblings, the first with no slug → the second is the successor
    ghost = json.loads(json.dumps(other))
    ghost["email"], ghost["slugs"] = "ghost@ocoron.com", []
    rows_plus = rows_now + [ghost]
    active_row = next(r for r in rows_now if r["email"] == active)
    pic = cr._fleet_picture(rows_plus, active_row["slugs"][0], FLEET_NOW)
    queue = pic["queue"]
    assert active in queue and "ghost@ocoron.com" in queue
    got = cr._quota_posture(rows_plus, pic, FLEET_NOW, None, hold=False)["fleet"]["successor"]
    assert got is not None and got["email"] != "ghost@ocoron.com" and got["slug"], got
    # the only eligible sibling has no slug → null
    lone = [active_row, ghost]
    pic2 = cr._fleet_picture(lone, active_row["slugs"][0], FLEET_NOW)
    assert cr._quota_posture(lone, pic2, FLEET_NOW, None, hold=False)["fleet"]["successor"] is None
    # no eligible sibling at all → null
    pic3 = cr._fleet_picture([active_row], active_row["slugs"][0], FLEET_NOW)
    assert (
        cr._quota_posture([active_row], pic3, FLEET_NOW, None, hold=False)["fleet"]["successor"]
        is None
    )


def test_posture_write_failure_never_takes_the_tick_down(tmp_path, monkeypatch, capsys):
    """B8 — the ledger's own tolerance: an unwritable state dir costs a file, never the tick."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    state.chmod(0o500)
    try:
        assert cr._cmd_tick() == 0
    finally:
        state.chmod(0o700)
    assert "Traceback" not in capsys.readouterr().out
    assert not _posture_path(tmp_path).exists()


def test_status_json_carries_the_posture_and_status_text_prints_one_posture_line(
    tmp_path, monkeypatch, capsys
):
    """B9 — `--status --json` carries the file; the text board prints ONE `posture:` line."""
    _fleet, rows = _posture_fixture(tmp_path, monkeypatch)
    capsys.readouterr()
    assert cr.main(["--status"]) == 0
    before = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("posture:")]
    assert before == ["posture: none written yet"], before
    assert cr._cmd_tick() == 0
    capsys.readouterr()
    assert cr.main(["--status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["posture"]["schema"] == 1
    assert cr.main(["--status"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("posture:")]
    assert len(lines) == 1 and " · 5h " in lines[0] and "written 0m ago" in lines[0], lines


# --- review round 1: the guards seat 1's confirmed findings owe (Phase B, D-269) ----------------


def test_posture_staging_file_is_per_process(tmp_path, monkeypatch):
    """B14 — the staging path carries the pid, so two overlapping ticks cannot tear each other.

    `os.replace` makes the PUBLISH atomic and says nothing about the STAGING: with one shared
    `<file>.tmp` the seat measured 3,471 of 4,000 concurrent reads unparseable. A real fork race is
    flaky as a grader, so this asserts the PROPERTY that makes the race impossible — the name the
    writer actually stages through — which a revert to `p.name + ".tmp"` fails immediately.
    """
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    _real = os.replace

    def _spy(src, dst, *a, **kw):
        staged.append(str(src))
        return _real(src, dst, *a, **kw)

    monkeypatch.setattr(cr.os, "replace", _spy)
    cr._write_quota_posture({"schema": 1, "ts": FLEET_NOW})
    assert staged, "the posture was published without os.replace"
    assert str(os.getpid()) in Path(staged[-1]).name, staged
    assert not list((tmp_path / "state").glob("*.tmp")), "the staging file outlived the publish"


def test_posture_write_failure_is_raised_not_swallowed(tmp_path, monkeypatch):
    """B15 — a failing write raises, so the tick's own handler prints one line.

    The inner `except: pass` froze the posture silently until some reader's staleness bound
    noticed, contradicting the call site's own "never silent, never fatal" comment.
    """
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "nope"))

    def _boom(*_a, **_k):
        raise OSError("read-only state dir")

    monkeypatch.setattr(Path, "write_text", _boom)
    with pytest.raises(OSError):
        cr._write_quota_posture({"schema": 1, "ts": FLEET_NOW})


def test_posture_a_past_reset_never_wins_the_forecast(monkeypatch):
    """B16 — a reset epoch already in the past is stale data, not a reset that "came first".

    Clamped to 0.0 it won every tie, so an account burning 5%/min ten minutes from its wall was
    told `reset in 0:00` — the calmest possible line at the hottest possible moment.
    """
    now = FLEET_NOW
    past = cr._forecast(50.0, now - 3600.0, 100.0, 5.0, now)
    assert past["verdict"] == "wall_first" and past["minutes_to_wall"] == 10.0
    assert past["minutes_to_reset"] == 0.0  # still clamped for DISPLAY
    future = cr._forecast(50.0, now + 300.0, 100.0, 5.0, now)
    assert future["verdict"] == "reset_first" and future["minutes_to_reset"] == 5.0
    # the exact tie still goes to the reset, which is the calmer and the correct reading
    tie = cr._forecast(50.0, now + 600.0, 100.0, 5.0, now)
    assert tie["verdict"] == "reset_first"


def test_posture_a_non_finite_file_reads_as_absent(tmp_path, monkeypatch):
    """B18 — a posture file holding a bare NaN is ABSENT, not a reading.

    `_window_reading` drops non-finite at the ROW, and Python's `json` re-admitted it at the FILE:
    `json.loads` accepts a bare `NaN`, `int(nan)` then raised out of `_fmt_forecast`, and
    `_cmd_status` calls that renderer unguarded — so one poisoned file took down the command the
    contract names as the authority. A NaN carried forward in the sample ring was worse than a
    crash: `max(0.0, nan)` is `0.0`, so the burn read "no burn" at the hottest possible moment.
    """
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path))
    cr._posture_path().write_text('{"schema": 1, "ts": NaN}', encoding="utf-8")
    assert cr._read_quota_posture() is None, "a non-finite posture must read as absent"
    cr._posture_path().write_text(
        '{"schema": 1, "ts": 1.0, "active": {"windows": {"five_hour": {"utilization": Infinity}}}}',
        encoding="utf-8",
    )
    assert cr._read_quota_posture() is None
    # and the renderer the status path calls is reached with None, which it handles
    assert (
        cr._posture_status_line(cr._read_quota_posture(), FLEET_NOW) == "posture: none written yet"
    )


def test_posture_a_non_finite_reading_is_no_reading(monkeypatch):
    """B17 — NaN and infinity are dropped at the reader, so no band and no renderer ever sees one.

    NaN compares False against every threshold, so it banded GREEN — the hottest possible reading
    presented as the safest — and `int(nan)` crashed `--status`, the contract's named authority.
    """
    for bad in (float("nan"), float("inf"), float("-inf")):
        u, r = cr._window_reading({"utilization": bad, "resets_at_epoch": bad})
        assert u is None and r is None, bad
        assert cr._band_of(u, False, 85.0, 90.0) is None
    # ⚠️ and the RENDERER survives a window that already holds one, which is the crash that took
    # `--status` down: `int(nan)` raised out of `_fmt_forecast`. A window built from None returns
    # "—" with or without the fix, so asserting THAT proved nothing (review round 1, seat 1).
    poisoned = {
        "utilization": float("nan"),
        "verdict": "wall_first",
        "minutes_to_wall": float("nan"),
        "burn_per_min": float("nan"),
    }
    assert cr._fmt_forecast(poisoned) == "no burn"


def test_a_flip_invalidates_the_posture_so_no_reader_names_the_previous_account(
    tmp_path, monkeypatch
):
    """B19 — a FRESH posture naming the OLD account is the one wrong state no reader can detect.

    Measured live 2026-09-17: `--switch ozgurbasak` repointed `active`, and the injected line still
    read `QUOTA: ob · weekly 31%` while the account actually in use sat at weekly 85% — under-
    reporting the binding constraint by 54 points, with every staleness guard silent because the
    file was three minutes old. Timestamps cannot catch this; only the flip can.
    """
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    posture = cr._posture_path()
    posture.parent.mkdir(parents=True, exist_ok=True)
    posture.write_text(
        json.dumps({"ts": time.time(), "active": {"slug": "ob", "band": "GREEN"}}),
        encoding="utf-8",
    )
    assert posture.exists(), "fixture must start from a posture on disk"

    cr._invalidate_quota_posture("ozgurbasak")

    assert not posture.exists(), (
        "after a flip the posture still names the previous account; a reader would inject that "
        "account's band and percentages for the account now in use"
    )
    # and it must never turn a landed flip into a reported failure
    cr._invalidate_quota_posture("ozgurbasak")


def test_a_real_flip_invalidates_the_posture_through_the_wiring(tmp_path, monkeypatch):
    """B19a — closing seat 1 neutered the `_invalidate_quota_posture(slug)` call inside
    `_flip_active` and 222 of 223 graders stayed green: B19 called the helper directly and never
    drove a flip. This one flips for real and reads the file."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _point(fleet, "seo")
    posture = cr._posture_path()
    posture.parent.mkdir(parents=True, exist_ok=True)
    posture.write_text(json.dumps({"ts": time.time(), "active": {"slug": "seo", "band": "GREEN"}}))
    assert cr._flip_active("intel", manual=True), "fixture: the manual flip must land"
    assert not posture.exists(), "the flip landed and the posture still names the previous account"


def _probe_row(email, slug, fh, wk, fable=None):
    row = {
        "email": email,
        "slugs": [slug],
        "five_hour": {"utilization": fh, "resets_at_epoch": FLEET_NOW + 3600},
        "seven_day": {"utilization": wk, "resets_at_epoch": FLEET_NOW + 86400},
    }
    if fable is not None:
        row["model_windows"] = {
            "Fable 5.1": {"utilization": fable, "resets_at_epoch": FLEET_NOW + 86400}
        }
    return row


def _pic_rows(*states):
    return {"accounts": [{"email": e, "state": st, "weekly_cap": cap} for e, st, cap in states]}


def test_fleet_readings_take_the_coolest_serving_account_per_window():
    """B20 — capacity is per WINDOW across the fleet, and the live 2026-09-17 shape proves why:
    `ob` session-exhausted at weekly 31% still holds the fleet's weekly; `can` fresh at weekly 85%
    holds the fleet's session; the active account at 87% weekly is nobody's constraint."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    accounts = [
        _probe_row("oz@x", "ozgurbasak", 11.0, 87.0, fable=62.0),
        _probe_row("can@x", "can", 0.0, 85.0, fable=20.0),
        _probe_row("ob@x", "ob", 88.0, 31.0, fable=18.0),
        _probe_row("mob@x", "mob", 0.0, 100.0, fable=0.0),
    ]
    pic = _pic_rows(
        ("oz@x", "active", 99),
        ("can@x", "eligible", 99),
        ("ob@x", "session-exhausted", 95),
        ("mob@x", "weekly-exhausted", 99),
    )
    fw = cr._fleet_readings(accounts, pic)
    assert fw["seven_day"] == {"utilization": 31.0, "slug": "ob"}, (
        "a spent session still holds its weekly"
    )
    assert fw["five_hour"] == {"utilization": 0.0, "slug": "can"}, (
        "a spent session cannot serve 5h now"
    )
    assert fw["fable"] == {"utilization": 18.0, "slug": "ob"}, (
        "Fable is weekly-scoped: a spent session still holds it (seat 1 F7), so ob's 18 beats can's 20"
    )
    assert "mob" not in {w["slug"] for w in fw.values()}, (
        "a weekly-exhausted account serves nothing"
    )
    # and the band that follows: fleet hottest is 31 -> GREEN, while the account's own is 87 -> AMBER
    assert (
        cr._fleet_band(
            fw, "AMBER", False, 85.0, 90.0, fable=False, measured=cr._fleet_measured(accounts, pic)
        )
        == "GREEN"
    )
    assert (
        cr._fleet_band(
            fw, "AMBER", False, 85.0, 90.0, fable=True, measured=cr._fleet_measured(accounts, pic)
        )
        == "GREEN"
    )


def test_fleet_band_is_amber_or_red_only_when_every_serving_account_is():
    """B20a — the fleet is constrained on a window only when EVERY serving account is hot on it."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    accounts = [_probe_row("a@x", "a", 5.0, 91.0), _probe_row("b@x", "b", 0.0, 90.0)]
    pic = _pic_rows(("a@x", "active", 99), ("b@x", "eligible", 99))
    fw = cr._fleet_readings(accounts, pic)
    assert fw["seven_day"]["utilization"] == 90.0
    assert (
        cr._fleet_band(
            fw, "RED", False, 85.0, 90.0, fable=False, measured=cr._fleet_measured(accounts, pic)
        )
        == "RED"
    ), "every account >= 90 weekly: the fleet's wall"
    accounts[1]["seven_day"]["utilization"] = 86.0
    fw = cr._fleet_readings(accounts, pic)
    assert (
        cr._fleet_band(
            fw, "RED", False, 85.0, 90.0, fable=False, measured=cr._fleet_measured(accounts, pic)
        )
        == "AMBER"
    )


def test_fleet_band_ignores_fable_unless_asked_and_a_cap_is_a_wall():
    """B20b — Fable is folded in ONLY for `band_fable` (operator: relevant solely where the running
    agent is Fable), and a weekly at its cap serves nothing whatever the state string says."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    accounts = [
        _probe_row("a@x", "a", 5.0, 10.0, fable=95.0),
        _probe_row("c@x", "c", 0.0, 99.0, fable=0.0),
    ]
    pic = _pic_rows(("a@x", "active", 99), ("c@x", "eligible", 99))
    fw = cr._fleet_readings(accounts, pic)
    assert "c" not in {w["slug"] for w in fw.values()}, "weekly 99 >= cap 99 serves nothing"
    assert (
        cr._fleet_band(
            fw, "GREEN", False, 85.0, 90.0, fable=False, measured=cr._fleet_measured(accounts, pic)
        )
        == "GREEN"
    )
    assert (
        cr._fleet_band(
            fw, "GREEN", False, 85.0, 90.0, fable=True, measured=cr._fleet_measured(accounts, pic)
        )
        == "RED"
    )


def test_the_wall_is_never_softened_and_a_window_nobody_serves_is_red():
    """B20c — `hold` means every account is spent; the stamp owns it. And a REQUIRED window with NO
    serving account is RED — maximal scarcity, never "no constraint" and never the account's own
    raw band: closing seat 1 drove a capped active beside a session-exhausted sibling and the
    posture read GREEN from the one surviving key; Delta 8 seat A then showed the first fix's
    fallback (`return account_band`) reading GREEN for an account walled by a cap of 80 at weekly
    81. Only an outright missing reading stays unknown."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    only_weekly = {"seven_day": {"utilization": 60.0, "slug": "b"}}
    assert (
        cr._fleet_band(only_weekly, "GREEN", False, 85.0, 90.0, fable=False, measured=1) == "RED"
    ), "nobody can serve 5h: RED, whatever the walled account's raw percentage says"
    only_5h = {"five_hour": {"utilization": 0.0, "slug": "c"}}
    assert cr._fleet_band(only_5h, "AMBER", False, 85.0, 90.0, fable=False, measured=1) == "RED"
    both = {
        "five_hour": {"utilization": 0.0, "slug": "c"},
        "seven_day": {"utilization": 60.0, "slug": "b"},
    }
    assert cr._fleet_band(both, "RED", False, 85.0, 90.0, fable=False, measured=2) == "GREEN"
    assert cr._fleet_band(both, "WALL", True, 85.0, 90.0, fable=False, measured=2) == "WALL"
    assert cr._fleet_band(both, "RED", True, 85.0, 90.0, fable=False, measured=2) == "RED", (
        "a hold must not be downgraded"
    )
    assert cr._fleet_band({}, "AMBER", False, 85.0, 90.0, fable=False, measured=1) == "RED"
    assert cr._fleet_band({}, "WALL", False, 85.0, 90.0, fable=False, measured=1) == "WALL"
    assert cr._fleet_band({}, None, False, 85.0, 90.0, fable=False, measured=0) is None, (
        "no reading at all (nobody measured) stays unknown"
    )
    junk = {"five_hour": {"slug": "a"}, "seven_day": {"utilization": None}}
    assert cr._fleet_band(junk, "GREEN", False, 85.0, 90.0, fable=False, measured=1) == "RED"


def test_the_wall_advisory_cannot_storm_when_the_stamp_cannot_be_written(tmp_path, monkeypatch):
    """B21 — the 2026-09-16 storm, reproduced: with the fleet-exhausted stamp UNWRITABLE, the
    presence latch never engages and every tick re-broadcasts (460 copies in one hour across 49
    mailboxes — 01M2P19KP9GE9S). The ledger row the advisory writes is now the second latch, so a
    dead stamp bounds the repeat at ONE per episode instead of one per tick."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    usages = {"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)}
    _fake_oauth(monkeypatch, usages=usages)
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    # the stamp's parent does not exist and cannot be created: every write raises OSError
    dead = tmp_path / "no-such-dir" / "fleet-exhausted"
    monkeypatch.setattr(cr, "_fleet_exhaustion_stamp", lambda: dead)
    _point(fleet, "seo")

    for _ in range(3):
        assert cr._cmd_tick() == 0
    assert not dead.exists(), "fixture: the stamp must really be unwritable"
    assert len(actions["telegrams"]) == 1, (
        f"{len(actions['telegrams'])} advisories in 3 ticks with a dead stamp — the storm shape"
    )


def test_the_ledger_latch_ends_with_relief_and_honours_the_floor_and_the_promise(
    tmp_path, monkeypatch
):
    """B21a — the ledger latch mirrors the stamp's rules: a relief or flip row ENDS the episode
    (so a fresh wall after relief speaks again), the 30-minute floor holds unconditionally, and
    beyond it the promised resume instant is what re-arms."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    led = state / "rotate-ledger.jsonl"
    now = FLEET_NOW
    row = {
        "event": "fleet-active-wall",
        "ts": now - 60,
        "account": "a@x",
        "resume_epoch": now + 3600,
    }
    led.write_text(json.dumps(row) + "\n")
    assert cr._advisory_ledger_latch("a@x", now) is True, "inside the floor: latched"
    assert cr._advisory_ledger_latch("b@x", now) is False, "another account: not this episode"
    # beyond the floor, the promise still stands -> latched; once due -> re-armed
    old = dict(row, ts=now - 2 * cr._ADVISORY_MIN_GAP_S)
    led.write_text(json.dumps(old) + "\n")
    assert cr._advisory_ledger_latch("a@x", now) is True
    assert cr._advisory_ledger_latch("a@x", now + 3600) is False, "promise came due: speak"
    # a relief row after the wall row ends the episode
    led.write_text(
        json.dumps(row) + "\n" + json.dumps({"event": cr._WAKE_EVENT, "ts": now - 30}) + "\n"
    )
    assert cr._advisory_ledger_latch("a@x", now) is False, "relief ended the episode"
    led.write_text(json.dumps(row) + "\n" + json.dumps({"event": "flip", "ts": now - 30}) + "\n")
    assert cr._advisory_ledger_latch("a@x", now) is False, "a flip ended the episode"
    # the week-long re-arm, and an unreadable ledger fails OPEN (the stamp latch still stands)
    led.write_text(json.dumps(dict(row, ts=now - cr._FLEET_WALL_REARM_S - 1)) + "\n")
    assert cr._advisory_ledger_latch("a@x", now) is False
    led.write_text("{not json\n")
    assert cr._advisory_ledger_latch("a@x", now) is False


def test_fleet_readings_wall_a_capless_weekly_at_100_and_treat_a_nan_cap_as_no_cap():
    """B20d — seat 1 F2: `_fleet_picture` walls a weekly at >=100 with no cap, or at its cap; the
    first `_fleet_readings` walled ONLY on a cap, so a capless ACTIVE account at weekly 100 kept
    serving the 5h window (its state string is always `active`, so nothing else drops it), and a
    NaN cap disarmed the guard entirely."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    accounts = [_probe_row("a@x", "a", 0.0, 100.0), _probe_row("b@x", "b", 5.0, 20.0)]
    fw = cr._fleet_readings(accounts, _pic_rows(("a@x", "active", None), ("b@x", "eligible", None)))
    assert fw["five_hour"]["slug"] == "b", "a capless weekly at 100 serves nothing"
    fw = cr._fleet_readings(
        accounts, _pic_rows(("a@x", "active", float("nan")), ("b@x", "eligible", None))
    )
    assert fw["five_hour"]["slug"] == "b", "a NaN cap is no cap: the wall is 100"


def test_fable_follows_the_weekly_rule_so_a_spent_session_still_holds_it():
    """B20e — seat 1 F7: Fable is weekly-scoped, so a session-exhausted account's cool Fable reading
    is fleet capacity exactly as its weekly is; the first cut scored Fable on the 5h rule."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    accounts = [
        _probe_row("a@x", "a", 5.0, 30.0, fable=95.0),
        _probe_row("b@x", "b", 99.0, 20.0, fable=2.0),
    ]
    fw = cr._fleet_readings(
        accounts, _pic_rows(("a@x", "active", 99), ("b@x", "session-exhausted", 99))
    )
    assert fw["fable"] == {"utilization": 2.0, "slug": "b"}
    assert "five_hour" in fw and fw["five_hour"]["slug"] == "a", "the 5h rule still excludes b"


def test_the_posture_is_not_green_in_the_tick_that_stamps_the_wall(tmp_path, monkeypatch):
    """B20f — seat 1 F1 end to end: the active account walled on weekly (5h 0%), the only sibling
    session-exhausted (5h 95 / weekly 60). Nobody can serve 5h. The first cut wrote `band: GREEN`
    from the one surviving window in the very tick that stamped the fleet-exhaustion marker, and
    the hook holds nothing at GREEN. (Seat 1 walled the active on a cap; this fixture walls it at
    weekly 100 with no cap — the F2 predicate — because the picture reads caps from a file, not
    from a monkeypatch. Both are the same shape: an active that serves nothing.)"""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(0.0, 100.0), "tok-intel": _usage_blob(95.0, 60.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    _point(fleet, "seo")
    assert cr._cmd_tick() == 0
    doc = json.loads(_posture_path(tmp_path).read_text())
    fw = doc["fleet"]["windows"]
    assert "five_hour" not in fw, f"fixture: nobody must be able to serve 5h — {fw}"
    assert doc["active"]["band"] != "GREEN", doc["active"]


def _ledger_events(tmp_path):
    led = Path(os.environ["ROTATE_STATE_DIR"]) / "rotate-ledger.jsonl"
    if not led.exists():
        return []
    out = []
    for ln in led.read_text().splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def test_relief_with_an_absent_stamp_closes_the_ledger_episode_so_the_next_wall_speaks(
    tmp_path, monkeypatch
):
    """B21b — seat 2 #1, the worse direction: with the stamp unwritable, wall -> relief -> wall gave
    ONE advisory; relief cleared no stamp and wrote no end row, so the ledger latch called the second
    wall "the same episode" for the whole promised window. Relief now closes the episode in the
    ledger when there is no stamp to clear. ⚠️ The relief here is a RESET on the same account, not a
    sibling regaining headroom: that would FLIP, and a `flip` row already closes the episode — the
    first cut of this grader used a flip and stayed green with the episode-close removed."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    usages = {"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)}
    _fake_oauth(monkeypatch, usages=usages)
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    monkeypatch.setattr(
        cr, "_fleet_exhaustion_stamp", lambda: tmp_path / "no-such-dir" / "fleet-exhausted"
    )
    _point(fleet, "seo")
    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 1
    usages["tok-seo"] = _usage_blob(10.0, 10.0)  # relief WITHOUT a flip: the active's own reset
    _fake_oauth(monkeypatch, usages=usages)
    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 1
    assert "flip" not in [e.get("event") for e in _ledger_events(tmp_path)], (
        "fixture: relief must not be a flip"
    )
    usages["tok-seo"] = _usage_blob(OVER_LINE + 1.0, 97.0)  # a fresh, genuine wall, same account
    _fake_oauth(monkeypatch, usages=usages)
    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 2, (
        "a new wall after a no-flip relief must speak even with a dead stamp"
    )


def test_the_ledger_latch_without_a_promise_holds_to_the_week_and_a_crashing_reader_fails_open(
    tmp_path, monkeypatch
):
    """B21c — seat 2 #2 and #3: with `resume_epoch` None the first cut released at the 30-minute
    floor and re-broadcast forever (2/h to every mailbox); a stamp with content "0" holds a week.
    And a reader that raises anything must fail OPEN, never abort the tick's advisory."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    led = state / "rotate-ledger.jsonl"
    now = FLEET_NOW
    led.write_text(
        json.dumps(
            {
                "event": "fleet-active-wall",
                "ts": now - 2 * cr._ADVISORY_MIN_GAP_S,
                "account": "a@x",
                "resume_epoch": None,
            }
        )
        + "\n"
    )
    assert cr._advisory_ledger_latch("a@x", now) is True, (
        "no promise: latched until the week re-arm"
    )
    assert cr._advisory_ledger_latch("a@x", now + cr._FLEET_WALL_REARM_S + 1) is False

    def boom() -> Path:
        raise TypeError("synthetic non-listed failure")

    monkeypatch.setattr(cr, "_rotate_state_dir", boom)
    assert cr._advisory_ledger_latch("a@x", now) is False, "a reader fault must not reach the tick"


def test_the_status_posture_line_shows_both_bands_and_the_fleet_readings():
    """B22 — seat 1 F6: the `posture:` line's new `(account X)` and `· fleet …` segments were
    ungraded. They are the operator's answer to "why is the band GREEN beside weekly 90%"."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    now = FLEET_NOW
    posture = {
        "ts": now,
        "active": {
            "band": "GREEN",
            "band_account": "AMBER",
            "windows": {
                "five_hour": {"utilization": 11.0},
                "seven_day": {"utilization": 87.0},
                "fable": {"utilization": 62.0},
            },
        },
        "fleet": {
            "windows": {
                "five_hour": {"utilization": 0.0, "slug": "can"},
                "seven_day": {"utilization": 31.0, "slug": "ob"},
                "fable": {"utilization": 17.0, "slug": "can"},
            }
        },
    }
    line = cr._posture_status_line(posture, now)
    assert line.startswith("posture: GREEN (account AMBER) ·"), line
    assert "· fleet 5h 0% (can) weekly 31% (ob) Fable 17% (can)" in line, line
    posture["active"]["band_account"] = "GREEN"
    del posture["fleet"]["windows"]
    line = cr._posture_status_line(posture, now)
    assert line.startswith("posture: GREEN ·") and "fleet" not in line and "(account" not in line, (
        line
    )


def test_a_cap_below_the_drain_band_cannot_read_green_at_the_fleet_wall(tmp_path, monkeypatch):
    """B20g — Delta 8 seat A #1: with caps.json {active: 80} and the active at weekly 81 (5h 0%),
    `_fleet_readings` walls the active out, nobody serves 5h, and the fallback returned the
    active's RAW band — GREEN on the 85/90 line — in the tick that broadcast the ACTIVE-WALL
    advisory. Scarcity is RED, whatever the walled account's raw percentage says."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _caps(
        fleet, {"sarp@ocoron.com": 80}
    )  # the B16 idiom; the fixture's own email, not a guessed one
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(0.0, 81.0), "tok-intel": _usage_blob(95.0, 30.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    _point(fleet, "seo")
    assert cr._cmd_tick() == 0
    doc = json.loads(_posture_path(tmp_path).read_text())
    assert "five_hour" not in doc["fleet"]["windows"], doc["fleet"]["windows"]
    assert doc["active"]["band_account"] == "GREEN", (
        "fixture: the raw band must be the misleading one"
    )
    assert doc["active"]["band"] == "RED", doc["active"]


def test_the_fleet_band_reads_an_empty_map_by_who_was_measured():
    """B20h — Delta 9 seat A F1: the unknown arm was keyed on the ACTIVE account's band, so an
    unmeasured active beside a measured sibling read `?` at maximal scarcity and the hook held
    nothing. `measured` is the fleet's fact; the account's band never stands in for it."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    assert cr._fleet_band({}, None, False, 85.0, 90.0, fable=False, measured=2) == "RED"
    assert cr._fleet_band({}, "GREEN", False, 85.0, 90.0, fable=False, measured=0) is None
    assert cr._fleet_band({}, None, False, 85.0, 90.0, fable=False, measured=0) is None
    only_weekly = {"seven_day": {"utilization": 5.0, "slug": "x"}}
    assert cr._fleet_band(only_weekly, None, False, 85.0, 90.0, fable=False, measured=1) == "RED"
    rows = [
        {"email": "a@x", "five_hour": None, "seven_day": None},
        {"email": "b@x", "five_hour": None, "seven_day": {"utilization": 5.0}},
        # a dead refresh chain with COOL cached readings is not a quota fact: counting it made
        # a fleet of dead credentials read RED "out of quota" (Delta 10 seat A, #6)
        {"email": "c@x", "five_hour": {"utilization": 0.0}, "seven_day": {"utilization": 5.0}},
        "junk",
    ]
    # and a row the picture never saw (no state at all) is not one either (seat D #3)
    rows.append(
        {"email": "d@x", "five_hour": {"utilization": 1.0}, "seven_day": {"utilization": 1.0}}
    )
    pic = _pic_rows(
        ("a@x", "eligible", 99), ("b@x", "weekly-exhausted", 99), ("c@x", "unavailable", 99)
    )
    assert cr._fleet_measured(rows, pic) == 1 and cr._fleet_measured([], pic) == 0
    # `measured` is REQUIRED — a new caller that omits it must fail loudly, never revive the
    # account-keyed default arm that let three graders pin the opposite of what ships (seat D #4)
    # asserted on the SIGNATURE: a call without it raises TypeError either way (`None > 0` in the
    # body does too), so `pytest.raises` could not tell required from defaulted (Delta 11 M5)
    import inspect  # noqa: PLC0415

    assert (
        inspect.signature(cr._fleet_band).parameters["measured"].default is inspect.Parameter.empty
    )


def test_a_posture_that_cannot_be_unlinked_never_fails_the_flip(tmp_path, monkeypatch, capsys):
    """B19b — Delta 9 seat A F6: the never-raise boundary widened to `except Exception` had no
    grader; narrowed back, every suite stayed green."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    class _Stuck:
        def unlink(self, missing_ok=False):
            raise TypeError("not an OSError")

    monkeypatch.setattr(cr, "_posture_path", lambda: _Stuck())
    cr._invalidate_quota_posture("intel")  # must return, not raise
    assert "posture not invalidated after flip to intel" in capsys.readouterr().err


def test_the_status_line_reads_a_missing_or_null_map_as_scarcity_when_someone_was_measured():
    """B22c — Delta 10 seat A #4: the hook coerces a missing/null/list `windows` to `{}` and goes
    on to `measured`; `--status` coerced it to None and bailed — three of four malformed shapes
    rendered no fleet section at maximal scarcity."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    for shape in (
        {"measured": 2},
        {"measured": 2, "windows": None},
        {"measured": 2, "windows": []},
    ):
        posture = {
            "ts": FLEET_NOW,
            "active": {"band": "RED", "band_account": "GREEN", "windows": {}},
            "fleet": shape,
        }
        line = cr._posture_status_line(posture, FLEET_NOW)
        assert "fleet 5h — (nobody serves it) weekly — (nobody serves it)" in line, (shape, line)


def test_the_status_line_omits_a_present_but_unusable_fleet_reading():
    """B22b — Delta 9 seat D #2: a key PRESENT but unusable (a JSON `true`) is a malformed
    reading, not scarcity — omitted, never rendered as `nobody serves it`; no grader held the
    branch that distinguishes the two."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    posture = {
        "ts": FLEET_NOW,
        "active": {"band": "GREEN", "band_account": "GREEN", "windows": {}},
        "fleet": {
            "windows": {
                "five_hour": {"utilization": True, "slug": "seo"},
                "seven_day": {"utilization": 30.0, "slug": "intel"},
            }
        },
    }
    line = cr._posture_status_line(posture, FLEET_NOW)
    # the ACTIVE account's own `5h —` precedes the fleet section; assert on the fleet section's
    # tokens — the unusable entry's slug must not appear, and nothing may claim scarcity
    assert "nobody serves it" not in line and "(seo)" not in line, line
    assert "fleet weekly 30% (intel)" in line, line


def test_the_status_line_names_a_required_window_nobody_serves():
    """B22a — Delta 8 seat A #2: absence became load-bearing with the required-window rule, and the
    line that exists to explain the band omitted it."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    posture = {
        "ts": FLEET_NOW,
        "active": {
            "band": "RED",
            "band_account": "GREEN",
            "windows": {"five_hour": {"utilization": 10.0}, "seven_day": {"utilization": 81.0}},
        },
        "fleet": {"windows": {"seven_day": {"utilization": 30.0, "slug": "intel"}}},
    }
    line = cr._posture_status_line(posture, FLEET_NOW)
    assert (
        "posture: RED (account GREEN)" in line
        and "5h — (nobody serves it) weekly 30% (intel)" in line
    ), line


def test_a_withheld_flip_is_not_relief_so_an_oscillating_successor_cannot_storm(
    tmp_path, monkeypatch
):
    """B21d — Delta 8 seat B F1: the first cut closed the ledger episode on the DWELL branch (a
    validated successor exists but the flip is withheld) while the account was still walled, so a
    successor oscillating across the picker's bar turned every tick-pair into close→advisory: six
    broadcasts an hour with a dead stamp. Only true relief closes an episode now. The advisory is
    driven directly with a sentinel pick, because a real `_validated_pick` refuses a sibling that is
    walled at 100/100 — the first cut of this grader never reached the dwell branch at all."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)},
    )
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    monkeypatch.setattr(
        cr, "_fleet_exhaustion_stamp", lambda: tmp_path / "no-such-dir" / "fleet-exhausted"
    )
    _point(fleet, "seo")
    assert cr._cmd_tick() == 0  # the wall: one advisory, one open ledger episode, no stamp
    assert len(actions["telegrams"]) == 1
    rows_now, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    for k in range(1, 7):  # alternate: a successor named but the flip withheld / no successor
        monkeypatch.setattr(
            cr,
            "_validated_pick",
            (lambda *a, **kw: "intel@ocoron.com") if k % 2 else (lambda *a, **kw: None),
        )
        cr._fleet_active_wall_advisory(rows_now, FLEET_NOW + 300 * k, cr._rotate_threshold())
    assert len(actions["telegrams"]) == 1, (
        f"{len(actions['telegrams'])} advisories — the oscillation storm"
    )
    events = [e.get("event") for e in _ledger_events(tmp_path)]
    assert cr._EPISODE_CLOSE_EVENT not in events, (
        "a withheld flip is not relief; nothing may close the episode"
    )


def test_a_withheld_flip_cannot_storm_through_a_writable_stamp_either(tmp_path, monkeypatch):
    """B21d-2 — Delta 9 seat B F1: B21d's stamp path was a dead directory, so the dwell branch
    never cleared a stamp and never wrote its `hold-lifted` row — the row that, counted as an
    episode END, re-armed the ledger latch every tick-pair: 7 broadcasts an hour on a HEALTHY
    box. Same twelve ticks, a writable stamp, one advisory."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)},
    )
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    (tmp_path / "locks").mkdir()
    monkeypatch.setattr(
        cr, "_fleet_exhaustion_stamp", lambda: tmp_path / "locks" / "fleet-exhausted"
    )
    _point(fleet, "seo")
    assert cr._cmd_tick() == 0
    assert len(actions["telegrams"]) == 1 and (tmp_path / "locks" / "fleet-exhausted").exists()
    rows_now, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    for k in range(1, 13):
        monkeypatch.setattr(
            cr,
            "_validated_pick",
            (lambda *a, **kw: "intel@ocoron.com") if k % 2 else (lambda *a, **kw: None),
        )
        cr._fleet_active_wall_advisory(rows_now, FLEET_NOW + 300 * k, cr._rotate_threshold())
    events = [e.get("event") for e in _ledger_events(tmp_path)]
    assert "hold-lifted" in events, "the dwell branch did clear the stamp and wake"
    assert len(actions["telegrams"]) == 1, (
        f"{len(actions['telegrams'])} advisories — the dwell-site wake row re-armed the latch"
    )
    # and the HOLD survived: the last tick had NO successor and the account is still walled, so
    # the stamp `quota_stop.py` reads must be back — Delta 9 latched the message and let the
    # hold stay down for the week the latch runs (Delta 10 seat B, F1)
    stamp = tmp_path / "locks" / "fleet-exhausted"
    assert stamp.exists(), "the message is latched; the hold must not be"
    # the content is the PROMISE the episode's own ledger row carries — derived from the row, never
    # from the file itself (the first cut compared the file with itself and accepted any integer —
    # Delta 11 seat D #1); the sibling's session reset is nameable here, so the row carries a promise
    wall = next(e for e in _ledger_events(tmp_path) if e.get("event") == "fleet-active-wall")
    promised = wall.get("resume_epoch")
    expect = str(int(promised)) if isinstance(promised, (int, float)) else "0"
    assert stamp.read_text(encoding="utf-8").strip() == expect, (
        promised,
        stamp.read_text(),
    )
    assert abs(stamp.stat().st_mtime - FLEET_NOW) < 1.0, "re-armed from the row's ts, not now"


def test_the_closer_writes_its_own_fleet_wide_event_and_writes_even_when_the_ledger_is_unreadable(
    tmp_path, monkeypatch
):
    """B21e — seat B F2/F4/F5/F6: the close row is `wall-episode-closed` (never a `hold-lifted` wake
    census with hardcoded zeros), it is FLEET-wide so it ends another account's stranded episode,
    and when the ledger cannot be read the closer fails toward WRITING, never toward silence."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    led = state / "rotate-ledger.jsonl"
    now = FLEET_NOW
    led.write_text(
        json.dumps(
            {
                "event": "fleet-active-wall",
                "ts": now - 60,
                "account": "b@x",
                "resume_epoch": now + 3600,
            }
        )
        + "\n"
    )
    assert cr._advisory_ledger_latch("b@x", now) is True
    cr._close_wall_episode_without_stamp(
        "a@x", now, "relief"
    )  # relief of a DIFFERENT active account
    rows = [json.loads(ln) for ln in led.read_text().splitlines()]
    assert rows[-1]["event"] == cr._EPISODE_CLOSE_EVENT and "armed" not in rows[-1], rows[-1]
    assert cr._advisory_ledger_latch("b@x", now) is False, (
        "a fleet-wide close ends b's stranded episode"
    )
    cr._close_wall_episode_without_stamp("a@x", now, "relief")
    assert len(led.read_text().splitlines()) == 2, (
        "idempotent when readable: no open episode, no row"
    )
    assert rows[1]["closed_for"] == ["b@x"], rows[1]  # whose episodes it ended (F7, F4)
    # a REAL unreadable ledger (write-only), not a stub of the reader: the stub proved the
    # branch, not the property — a reader that reported unreadable as READABLE passed it
    # (Delta 9 seat B, F2). Root reads a 0o222 file anyway, so this arm alone is skipped there
    # — the repo's inline convention, never the whole test (Delta 10 seat B, F6).
    if os.geteuid() != 0:
        led.chmod(0o222)
        try:
            cr._close_wall_episode_without_stamp("a@x", now, "relief")
        finally:
            led.chmod(0o644)
        rows = [json.loads(ln) for ln in led.read_text().splitlines()]
        assert len(rows) == 3 and rows[-1]["event"] == cr._EPISODE_CLOSE_EVENT, (
            "unreadable ledger: write anyway"
        )
        assert rows[-1]["closed_for"] == [], rows[-1]
    # an ABSENT ledger is "nothing has ever walled", not a fault: no phantom close (F3)
    led.unlink()
    cr._close_wall_episode_without_stamp("a@x", now, "relief")
    assert not led.exists(), led.read_text()


def test_the_floor_binds_the_stamp_path_too(tmp_path, monkeypatch):
    """B21j — Delta 11 seat A A2-1: a stamp whose promised resume is ALREADY due released the
    stamp latch on the next tick, and the stamp path never consulted the 30-min floor the
    ledger latch applies — a second advisory 900 s inside it. Same wall as B21d-2, the stamp
    handed a promise that comes due 600 s in: silent at 900 s, speaks at the floor."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(OVER_LINE, 96.0), "tok-intel": _usage_blob(100.0, 100.0)},
    )
    actions = _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    (tmp_path / "locks").mkdir()
    stamp = tmp_path / "locks" / "fleet-exhausted"
    monkeypatch.setattr(cr, "_fleet_exhaustion_stamp", lambda: stamp)
    _point(fleet, "seo")
    assert cr._cmd_tick() == 0 and len(actions["telegrams"]) == 1 and stamp.exists()
    stamp.write_text(str(int(FLEET_NOW + 600)), encoding="utf-8")  # a promise, due at +600
    os.utime(stamp, (FLEET_NOW, FLEET_NOW))
    rows_now, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=False)
    monkeypatch.setattr(cr, "_validated_pick", lambda *a, **kw: None)
    cr._fleet_active_wall_advisory(rows_now, FLEET_NOW + 900, cr._rotate_threshold())
    assert len(actions["telegrams"]) == 1, "the promise is due but the floor has not passed"
    cr._fleet_active_wall_advisory(
        rows_now, FLEET_NOW + cr._ADVISORY_MIN_GAP_S - 1, cr._rotate_threshold()
    )
    assert len(actions["telegrams"]) == 1, "one second inside the floor is still inside it"
    cr._fleet_active_wall_advisory(
        rows_now, FLEET_NOW + cr._ADVISORY_MIN_GAP_S, cr._rotate_threshold()
    )
    assert len(actions["telegrams"]) == 2, (
        "AT the floor it releases — the ledger latch's own strict `<` (Delta 12 seat A, #4)"
    )
    # and that ledger latch's `<` is pinned too, on a row whose promise is already due — the arm
    # above cited it as its authority while nothing checked it (Delta 13 seat A, F3)
    led = cr._rotate_state_dir() / "rotate-ledger.jsonl"
    with led.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "event": "fleet-active-wall",
                    "ts": FLEET_NOW,
                    "account": "z@x",
                    "resume_epoch": FLEET_NOW + 600,
                }
            )
            + "\n"
        )
    assert cr._advisory_ledger_latch("z@x", FLEET_NOW + cr._ADVISORY_MIN_GAP_S - 1) is True
    assert cr._advisory_ledger_latch("z@x", FLEET_NOW + cr._ADVISORY_MIN_GAP_S) is False


def test_a_stray_ledger_line_does_not_abort_the_flip_reader(tmp_path, monkeypatch):
    """B21k — Delta 13 seat A F5: `_open_wall_rows` skips a non-dict line; its sibling reader
    `_last_switch_ts` did not, and a stray `"x"` line on the ledger raised out of it — inside a
    tick that is `INTERNAL ERROR`, no flip, no advisory, no posture."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    # the pin is load-bearing: a future-dated DICT row ends the scan fail-CLOSED (it is not skipped —
    # only a non-dict line is), and FLEET_NOW is in the real clock's future (Delta 14 seat A, F7)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    led = state / "rotate-ledger.jsonl"
    led.write_text(
        json.dumps({"event": "flip", "ts": FLEET_NOW - 600, "from": "a@x", "to": "b@x"})
        + "\n"
        + '"x"\n'
    )
    ts, degraded = cr._last_switch_ts(event="flip")
    # both fields: `degraded` is what `_flip_active` fails closed on, and a reader that reported
    # a clean read as degraded passed the first cut of this grader (Delta 14 seat B)
    assert ts == FLEET_NOW - 600 and degraded is False, (ts, degraded)
    # the EVENT selector, which the guard's grader never pinned (Delta 14 seat A, F1): a `switch`
    # row must not answer the flip clock — under a selector-less reader every dict row would
    led.write_text(
        # an OLDER flip first: the contract is the LAST match, and one flip row could not tell
        # last-match from first-match (Delta 15 seat B, #1)
        json.dumps({"event": "flip", "ts": FLEET_NOW - 3600, "from": "b@x", "to": "a@x"})
        + "\n"
        + json.dumps({"event": "flip", "ts": FLEET_NOW - 600, "from": "a@x", "to": "b@x"})
        + "\n"
        + json.dumps({"event": "switch", "ts": FLEET_NOW - 60, "from": "b@x", "to": "a@x"})
        + "\n"
    )
    assert cr._last_switch_ts(event="flip") == (FLEET_NOW - 600, False)
    # and a JSON `true` ts is an UNUSABLE ts (fail-closed), never a flip in 1970 (fail-open) — the
    # docstring forbids exactly that and the sibling readers already refuse a bool (F2)
    # and a ts at or before the epoch: the ledger cannot predate its writer, so 0 is corruption,
    # not a flip in 1970 — the type door was closed and the value door left open (Delta 16 A F3)
    led.write_text(json.dumps({"event": "flip", "ts": 0, "from": "a@x", "to": "b@x"}) + "\n")
    assert cr._last_switch_ts(event="flip")[1] is True
    # `{"ts": 1}` is `{"ts": true}`'s VALUE — a floor at 0 refused the spelling and admitted the
    # value, installing on every tick; the floor is the ledger's ERA (Delta 17 seat A, F2)
    led.write_text(json.dumps({"event": "flip", "ts": 1, "from": "a@x", "to": "b@x"}) + "\n")
    assert cr._last_switch_ts(event="flip")[1] is True
    era = cr._LEDGER_ERA_FLOOR_S + 1  # pinned from the accepting side too
    led.write_text(json.dumps({"event": "flip", "ts": era, "from": "a@x", "to": "b@x"}) + "\n")
    assert cr._last_switch_ts(event="flip") == (era, False)
    # and the floor itself is refused (`>`, not `>=`) — the boundary was ungraded, so a `>=`
    # mutant passed every arm (Delta 18 seat A, F2)
    floor = cr._LEDGER_ERA_FLOOR_S
    led.write_text(json.dumps({"event": "flip", "ts": floor, "from": "a@x", "to": "b@x"}) + "\n")
    assert cr._last_switch_ts(event="flip")[1] is True
    # a giant JSON integer raised OverflowError out of the reader — and the tick (Delta 17 A F1)
    led.write_text('{"event": "flip", "ts": 1' + "0" * 400 + ', "from": "a@x", "to": "b@x"}\n')
    assert cr._last_switch_ts(event="flip")[1] is True
    led.write_text(json.dumps({"event": "flip", "ts": True, "from": "a@x", "to": "b@x"}) + "\n")
    ts2, degraded2 = cr._last_switch_ts(event="flip")
    assert degraded2 is True, (ts2, degraded2)  # the flag alone discriminates (seat B, #2)
    # and `-Infinity`: accepted, it read as a flip infinitely long ago, fail-OPEN, and no grader
    # drove it (Delta 15 seat A, F1); the reader's own finite conjunct was dead once the floor
    # shipped, and finiteness now lives in `_usable_ts` alone (Delta 17 seat B)
    led.write_text('{"event": "flip", "ts": -Infinity, "from": "a@x", "to": "b@x"}\n')
    ts3, degraded3 = cr._last_switch_ts(event="flip")
    assert degraded3 is True, (ts3, degraded3)  # the flag alone discriminates here too (Delta 16 B)


def test_the_rearmed_stamp_carries_the_episodes_own_promise(tmp_path, monkeypatch, capsys):
    """B21i — Delta 11 seats B F1 / D #1: the re-armed stamp's CONTENT is the promise the episode's
    row carries (what `_promised_resume` reads for the next re-arm) and its mtime is the row's ts;
    B21d-2 could only see the no-promise `"0"` case, and its first cut compared the file with
    itself. A write failure is said on stderr and never raised."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    now = FLEET_NOW
    (state / "rotate-ledger.jsonl").write_text(
        json.dumps(
            {
                "event": "fleet-active-wall",
                "ts": now - 900,
                "account": "a@x",
                "resume_epoch": now + 3600,
            }
        )
        + "\n"
    )
    stamp = tmp_path / "locks" / "fleet-exhausted"
    stamp.parent.mkdir()
    cr._rearm_wall_stamp(stamp, "a@x", now)
    assert stamp.read_text(encoding="utf-8") == str(int(now + 3600)), stamp.read_text()
    assert abs(stamp.stat().st_mtime - (now - 900)) < 1.0, "mtime is the row's ts, never now"
    cr._rearm_wall_stamp(tmp_path / "no-such-dir" / "fleet-exhausted", "a@x", now)
    assert "NOT re-armed" in capsys.readouterr().err
    # and the arm this fix added: an UNREADABLE ledger is said too, not swallowed — the first
    # cut of this grader only ever reached the write-failure line (Delta 12 seat C); root reads
    # a 0o222 file anyway, so this arm alone is skipped there
    if os.geteuid() != 0:
        led = state / "rotate-ledger.jsonl"
        stamp2 = tmp_path / "locks" / "fleet-exhausted-2"
        led.chmod(0o222)
        try:
            cr._rearm_wall_stamp(stamp2, "a@x", now)
        finally:
            led.chmod(0o644)
        assert not stamp2.exists() and "ledger unreadable" in capsys.readouterr().err
    # and a huge FINITE ts: usable to the reader and open (a negative age never expires), but
    # `os.utime` refuses it with OverflowError — not OSError — so the re-arm raised out of the
    # tick and left a stamp with a FRESH mtime behind (Delta 18 seat A, F1)
    (state / "rotate-ledger.jsonl").write_text(
        json.dumps({"event": "fleet-active-wall", "ts": 1e308, "account": "a@x"}) + "\n"
    )
    stamp4 = tmp_path / "locks" / "fleet-exhausted-4"
    cr._rearm_wall_stamp(stamp4, "a@x", now)
    assert not stamp4.exists() and "NOT re-armed" in capsys.readouterr().err
    # a FAILED re-arm must never TOUCH a stamp it did not write: the stamp IS the fleet hold
    # (`quota_stop.py` allows whenever it is absent). Delta 18's unconditional unlink dropped it
    # on any un-writable stamp (Delta 19 seat A, F1); Delta 19 kept it but only AFTER the in-place
    # write had overwritten its content and mtime (Delta 20 seat C, #2). Two arms: a read-only
    # DIRECTORY (nothing can be built beside the stamp; root writes there anyway, so root skips
    # it — and a 0o444 FILE arm's `finally` chmod masked the assertion once the stamp was gone,
    # Delta 20 seat B) and a writable stamp with a ts `os.utime` refuses
    (state / "rotate-ledger.jsonl").write_text(
        json.dumps({"event": "fleet-active-wall", "ts": now - 900, "account": "a@x"}) + "\n"
    )
    held = tmp_path / "held"
    held.mkdir()
    stamp5 = held / "fleet-exhausted"
    stamp5.write_text("9999999999", encoding="utf-8")
    os.utime(stamp5, (now - 100000, now - 100000))
    before = (stamp5.read_text(encoding="utf-8"), stamp5.stat().st_mtime)
    if os.geteuid() != 0:
        held.chmod(0o555)
        try:
            cr._rearm_wall_stamp(stamp5, "a@x", now)
        finally:
            held.chmod(0o755)
        assert (stamp5.read_text(encoding="utf-8"), stamp5.stat().st_mtime) == before
        assert "NOT re-armed" in capsys.readouterr().err
    (state / "rotate-ledger.jsonl").write_text(
        json.dumps({"event": "fleet-active-wall", "ts": 1e308, "account": "a@x"}) + "\n"
    )
    cr._rearm_wall_stamp(stamp5, "a@x", now)
    assert (stamp5.read_text(encoding="utf-8"), stamp5.stat().st_mtime) == before
    assert "NOT re-armed" in capsys.readouterr().err
    assert sorted(p.name for p in held.iterdir()) == ["fleet-exhausted"], "no temp file left"
    # and a temp-file cleanup that FAILS is said, and only the TEMP file stays — never a stamp
    # (Delta 19 seat C, #1; the target of the refused unlink is our own temp file now)
    stamp6 = tmp_path / "locks" / "fleet-exhausted-6"

    def _refuse(self, missing_ok=False):
        raise PermissionError("unlink refused by the grader")

    # a CONTEXT, never a bare `monkeypatch.undo()`: undo consumes the whole shared stack and
    # unpinned every conftest box-state seam for the rest of the test — the arms below then
    # read and mkdir'd the operator's REAL state dir (Delta 20 seat A, F2)
    with monkeypatch.context() as m:
        m.setattr(type(stamp6), "unlink", _refuse)
        cr._rearm_wall_stamp(stamp6, "a@x", now)
    err6 = capsys.readouterr().err
    assert not stamp6.exists() and "NOT re-armed" in err6 and "left in place" in err6, err6
    assert stamp6.with_name(f"{stamp6.name}.{os.getpid()}.rearm").exists()
    # said FIRST — the order is the point of the fix and was ungraded (Delta 20 seat A, F4)
    assert err6.index("NOT re-armed") < err6.index("left in place"), err6
    assert os.environ["ROTATE_STATE_DIR"] == str(state), "the seams stayed pinned"
    # and a temp file a sibling's replace has already taken: the cleanup must say nothing false —
    # a shared temp name and a bare `unlink` printed `NOT re-armed` AND `left in place` for a
    # stamp that WAS armed (Delta 21 seat A, A2)
    stamp8 = tmp_path / "locks" / "fleet-exhausted-8"

    def _move_then_refuse(path, times):
        os.replace(path, stamp8)
        raise OverflowError("refused after a sibling's move")

    with monkeypatch.context() as m:
        m.setattr(cr.os, "utime", _move_then_refuse)
        cr._rearm_wall_stamp(stamp8, "a@x", now)
    err8 = capsys.readouterr().err
    assert "NOT re-armed" in err8 and "left in place" not in err8, err8
    # and a path with an EMPTY name: `with_name` raised ValueError OUTSIDE the try (A3)
    cr._rearm_wall_stamp(Path("/"), "a@x", now)
    assert "NOT re-armed" in capsys.readouterr().err
    # and the PROMISE: `Infinity` round-trips through json and raised out of `int()` with nothing
    # said; a giant int wrote a 401-digit stamp that read back as a promise that never comes;
    # the ledger latch's own `float()` of the same field raised too (Delta 21 seat A, A1 + mirror)
    for bad in ("Infinity", "NaN", "1" + "0" * 400, "true"):
        (state / "rotate-ledger.jsonl").write_text(
            '{"event": "fleet-active-wall", "ts": '
            + repr(now - 900)
            + ', "account": "a@x", "resume_epoch": '
            + bad
            + "}\n"
        )
        stamp9 = tmp_path / "locks" / "fleet-exhausted-9"
        cr._rearm_wall_stamp(stamp9, "a@x", now)
        assert stamp9.read_text(encoding="utf-8") == "0", bad
        stamp9.unlink()
        assert cr._advisory_ledger_latch("a@x", now + cr._ADVISORY_MIN_GAP_S) is True, bad
    # and a promise NOT in the future of its own row — 0, the row's ts, one second before it: the
    # stamp reader reads it as NO promise (a week's hold) while the ledger latch read it as
    # RELEASED, one field, two verdicts (Delta 22 seat A, A1); both say NO promise now
    for bad in ("0", repr(now - 900), repr(now - 901)):
        (state / "rotate-ledger.jsonl").write_text(
            '{"event": "fleet-active-wall", "ts": '
            + repr(now - 900)
            + ', "account": "a@x", "resume_epoch": '
            + bad
            + "}\n"
        )
        stamp10 = tmp_path / "locks" / "fleet-exhausted-10"
        cr._rearm_wall_stamp(stamp10, "a@x", now)
        assert stamp10.read_text(encoding="utf-8") == "0", bad
        assert cr._promised_resume(stamp10) is None, bad
        stamp10.unlink()
        assert cr._advisory_ledger_latch("a@x", now + cr._ADVISORY_MIN_GAP_S + 1) is True, bad
    # and an ORPHAN temp under a pid that never returns is swept by the next healthy re-arm —
    # the per-pid name accumulated them forever (Delta 22 seat A, A2)
    (state / "rotate-ledger.jsonl").write_text(
        json.dumps({"event": "fleet-active-wall", "ts": now - 900, "account": "a@x"}) + "\n"
    )
    orphan = tmp_path / "locks" / "fleet-exhausted-11.999999.rearm"
    orphan.write_text("junk", encoding="utf-8")
    os.utime(orphan, (1, 1))
    cr._rearm_wall_stamp(tmp_path / "locks" / "fleet-exhausted-11", "a@x", now)
    assert not orphan.exists() and (tmp_path / "locks" / "fleet-exhausted-11").exists()
    # and a NUL byte in the path, with no monkeypatch: write_text raises ValueError, which the
    # outer except must catch (Delta 19 A F5 / Delta 20 A F3) — and since nothing was written,
    # no cleanup runs and nothing claims a temp file was left (the first cut said so falsely)
    cr._rearm_wall_stamp(tmp_path / "locks" / "fleet-exhausted-7\x00x", "a@x", now)
    err7 = capsys.readouterr().err
    assert "NOT re-armed" in err7 and "left in place" not in err7, err7
    # and a stamp inside a SEALED dir (0o000): nothing may raise out of the re-arm, not even the
    # probe of the path — root traverses it anyway, so root skips it (Delta 20 seat A, F5)
    if os.geteuid() != 0:
        sealed = tmp_path / "sealed"
        sealed.mkdir()
        sealed.chmod(0o000)
        try:
            cr._rearm_wall_stamp(sealed / "fleet-exhausted", "a@x", now)
        finally:
            sealed.chmod(0o755)
        assert "NOT re-armed" in capsys.readouterr().err
    # and the ROW-GONE race: readable ledger, no open row — no stamp, and nothing said (the
    # docstring says so; the negative had no grader — Delta 14 seat A, F5)
    (state / "rotate-ledger.jsonl").write_text("")
    stamp3 = tmp_path / "locks" / "fleet-exhausted-3"
    cr._rearm_wall_stamp(stamp3, "a@x", now)
    assert not stamp3.exists() and capsys.readouterr().err == ""


def test_the_close_row_names_every_episode_it_ends(tmp_path, monkeypatch):
    """B21h — Delta 10 seat B F4: two open episodes are reachable (a hand flip writes no `flip`
    row); the fleet-wide close ends both, and the singular key named only the last."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    led = state / "rotate-ledger.jsonl"
    now = FLEET_NOW
    led.write_text(
        json.dumps({"event": "fleet-active-wall", "ts": now - 600, "account": "a@x"})
        + "\n"
        + json.dumps({"event": "fleet-active-wall", "ts": now - 60, "account": "b@x"})
        + "\n"
    )
    assert cr._advisory_ledger_latch("a@x", now) and cr._advisory_ledger_latch("b@x", now)
    cr._close_wall_episode_without_stamp("b@x", now, "relief")
    row = json.loads(led.read_text().splitlines()[-1])
    assert row["closed_for"] == ["a@x", "b@x"], row
    assert not cr._advisory_ledger_latch("a@x", now) and not cr._advisory_ledger_latch("b@x", now)
    # and SORTED, not insertion order — the first fixture wrote them already sorted (seat B, F5)
    led.write_text(
        json.dumps({"event": "fleet-active-wall", "ts": now - 600, "account": "b@x"})
        + "\n"
        + json.dumps({"event": "fleet-active-wall", "ts": now - 60, "account": "a@x"})
        + "\n"
    )
    cr._close_wall_episode_without_stamp("a@x", now, "relief")
    assert json.loads(led.read_text().splitlines()[-1])["closed_for"] == ["a@x", "b@x"]
    # a keyless open episode is NAMED — `[]` may mean only "unreadable ledger" (Delta 10 B F4;
    # the `str(k)` half had no grader, Delta 12 seat A #3); an UNHASHABLE key is skipped, where
    # it crashed the reader and the tick with it (#7)
    led.write_text(
        json.dumps({"event": "fleet-active-wall", "ts": now - 60})
        + "\n"
        + json.dumps({"event": "fleet-active-wall", "ts": now - 30, "account": ["a"]})
        + "\n"
        # every JSON shape that is unhashable, or a guard narrowed to lists survives (Delta 13 B)
        + json.dumps({"event": "fleet-active-wall", "ts": now - 20, "account": {"x": 1}})
        + "\n"
    )
    cr._close_wall_episode_without_stamp("a@x", now, "relief")
    assert json.loads(led.read_text().splitlines()[-1])["closed_for"] == ["None"]


def test_a_wall_row_the_latch_has_retired_is_not_an_open_episode_to_the_closer(
    tmp_path, monkeypatch
):
    """B21g — Delta 9 seat B F6: the latch re-arms past the week, the closer applied no age bound,
    so a relief tick wrote a close row for an episode retired days earlier."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    led = state / "rotate-ledger.jsonl"
    now = FLEET_NOW
    led.write_text(
        json.dumps(
            {"event": "fleet-active-wall", "ts": now - cr._FLEET_WALL_REARM_S - 1, "account": "b@x"}
        )
        + "\n"
    )
    assert cr._open_wall_episode("b@x", now) == (None, True)
    # an expired row for the SAME account appended after a fresh one retires it (the reader
    # pops before it decides — seat B F5, the `pop` had no grader)
    led.write_text(
        json.dumps({"event": "fleet-active-wall", "ts": now - 60, "account": "b@x"})
        + "\n"
        + json.dumps(
            {"event": "fleet-active-wall", "ts": now - cr._FLEET_WALL_REARM_S - 1, "account": "b@x"}
        )
        + "\n"
    )
    assert cr._open_wall_episode("b@x", now) == (None, True)
    led.write_text(
        json.dumps(
            {"event": "fleet-active-wall", "ts": now - cr._FLEET_WALL_REARM_S - 1, "account": "b@x"}
        )
        + "\n"
    )
    assert cr._open_wall_episode("b@x") != (None, True), "without a clock the row is open"
    # a bare NaN ts never expired (`now - nan > week` is False) and never released the latch —
    # an immortal wall row silencing that account forever (Delta 14 seat A, F6)
    led.write_text('{"event": "fleet-active-wall", "ts": NaN, "account": "b@x"}\n')
    assert cr._open_wall_episode("b@x", now) == (None, True)
    assert cr._advisory_ledger_latch("b@x", now + 8 * 86400) is False
    # every other unusable shape too — `true`, a string, null — clock or no clock: the first cut
    # expired NaN only, and a `true`-stamped row stayed open forever, a surplus close row on
    # every relief (Delta 15 seat A, F3/F4)
    # and a giant JSON integer: `math.isfinite`/`float()` raise OverflowError on it, out of every
    # ledger reader and the whole tick, forever, until hand-edited (Delta 17 seat A, F1)
    for bad in ("true", '"x"', "null", "1" + "0" * 400):
        led.write_text('{"event": "fleet-active-wall", "ts": ' + bad + ', "account": "b@x"}\n')
        # with a clock `true` (== 1, epoch 1970) also expires by AGE, so the clockless call below is
        # the one that discriminates the `usable` rule for a bool — keep both (Delta 16 seat B)
        assert cr._open_wall_episode("b@x", now) == (None, True), bad
        assert cr._open_wall_episode("b@x") == (None, True), bad
        cr._close_wall_episode_without_stamp("a@x", now, "relief")
        assert len(led.read_text().splitlines()) == 1, ("surplus close row", bad)
    cr._close_wall_episode_without_stamp("a@x", now, "relief")
    assert len(led.read_text().splitlines()) == 1, "no close row for a retired episode"
    # and an OUT-OF-ERA but usable ts: expired by AGE on a clocked call, OPEN with no clock —
    # the wall reader has no era floor, and its docstring's clause is scoped to a clock
    # (Delta 18 seat A, F3; Delta 19 seats A F2 / C #2)
    led.write_text('{"event": "fleet-active-wall", "ts": 1, "account": "b@x"}\n')
    assert cr._open_wall_episode("b@x", now) == (None, True)
    assert cr._open_wall_episode("b@x")[0] is not None


def test_the_ledger_latch_tolerates_the_stamps_clock_skew(tmp_path, monkeypatch):
    """B21f — seat B F3: the stamp tolerates 60 s of future-dating (WSL suspend / NTP); the ledger
    latch tolerated none, and its docstring claimed the two mirror. A row 30 s ahead of the clock
    is latched; 120 s ahead is not."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    led = state / "rotate-ledger.jsonl"
    now = FLEET_NOW
    led.write_text(
        json.dumps(
            {
                "event": "fleet-active-wall",
                "ts": now + 30,
                "account": "a@x",
                "resume_epoch": now + 3600,
            }
        )
        + "\n"
    )
    assert cr._advisory_ledger_latch("a@x", now) is True, (
        "30 s of skew is inside the stamp's tolerance"
    )
    led.write_text(
        json.dumps(
            {
                "event": "fleet-active-wall",
                "ts": now + 120,
                "account": "a@x",
                "resume_epoch": now + 3600,
            }
        )
        + "\n"
    )
    assert cr._advisory_ledger_latch("a@x", now) is False, (
        "beyond the tolerance a future row is invalid: speak"
    )


def test_a_json_true_utilization_from_the_endpoint_is_not_one_percent():
    """B23 — seat B, out of slice: `_usage_windows` coerced a JSON `true` to 1.0 and would have
    silenced a wall at 1%; the same bool class the hook's `_util` already refuses."""
    import scripts.sysadmin.claude_rotate as cr  # noqa: PLC0415

    w = cr._usage_windows(
        {
            "five_hour": {"utilization": True, "resets_at": "2026-09-18T00:00:00+00:00"},
            # both required keys present, or the loop returns None before the bool guard is
            # ever reached and the grader passes against a coercing reader (Delta 9 seat D)
            "seven_day": {"utilization": 20.0, "resets_at": "2026-09-18T00:00:00+00:00"},
        }
    )
    fh = (w or {}).get("five_hour") if isinstance(w, dict) else None
    assert not (isinstance(fh, dict) and fh.get("utilization") == 1.0), w
    # the same class on the `limits[]` leg: a Fable `percent: true` coerced to 1.0 upstream of
    # every guard, and a Fable session read GREEN at its wall (Delta 10 seat A, #3)
    w = cr._usage_windows(
        {
            "five_hour": {"utilization": 10.0, "resets_at": "2026-09-18T00:00:00+00:00"},
            "seven_day": {"utilization": 20.0, "resets_at": "2026-09-18T00:00:00+00:00"},
            "limits": [
                {
                    "kind": "weekly_scoped",
                    "scope": {"model": {"display_name": "Fable"}},
                    "percent": True,
                }
            ],
        }
    )
    assert isinstance(w, dict) and "Fable" not in (w.get("model_windows") or {}), w
