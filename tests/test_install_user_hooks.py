"""Behavior Contract — `scripts/sysadmin/install_user_hooks.py` (review 2026-09-06, B10/O6).

The three user-level hook entries were hand-written into the canonical ~/.claude/settings.json
and pushed by --sync-shared: no creator, no verifier, no restorer. A sixth account, a DR restore,
or a stale canonical silently strips every window of the arm check, the MCP banner and the quota
hold — and check_hooks_index derives its `required` set FROM the file, so it cannot see a
MISSING entry. This installer is idempotent and `--check` fails on absence.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "install_user_hooks.py"
spec = importlib.util.spec_from_file_location("install_user_hooks", SCRIPT)
iuh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iuh)


def _home(tmp_path: Path, dirs=("ob", "can")) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"Stop": []}, "permissions": {"defaultMode": "auto"}})
    )
    for d in dirs:
        (tmp_path / ".claude-fleet" / d).mkdir(parents=True)
        (tmp_path / ".claude-fleet" / d / "settings.json").write_text(json.dumps({"hooks": {}}))
    return tmp_path


def _has(path: Path) -> dict:
    d = json.loads(path.read_text())
    got = {
        ev: [h["command"] for e in entries for h in e.get("hooks", [])]
        for ev, entries in d.get("hooks", {}).items()
    }
    return got


def test_check_fails_when_an_entry_is_missing_and_install_makes_it_pass(tmp_path, monkeypatch):
    home = _home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    assert iuh.run(["--check"]) == 1, "absence must be a failure, not a derived requirement"
    assert iuh.run([]) == 0
    assert iuh.run(["--check"]) == 0
    for f in (
        home / ".claude" / "settings.json",
        home / ".claude-fleet" / "ob" / "settings.json",
        home / ".claude-fleet" / "can" / "settings.json",
    ):
        got = _has(f)
        assert any("selfwatch_check.py" in c for c in got.get("UserPromptSubmit", []))
        assert any(
            "user_hook_gate.py" in c and "mcp_watch.py" in c
            for c in got.get("UserPromptSubmit", [])
        )
        assert any(
            "user_hook_gate.py" in c and "quota_stop.py" in c for c in got.get("PreToolUse", [])
        )


def test_install_is_idempotent_and_preserves_other_hooks(tmp_path, monkeypatch):
    home = _home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    iuh.run([])
    before = (home / ".claude" / "settings.json").read_text()
    iuh.run([])
    after = (home / ".claude" / "settings.json").read_text()
    assert before == after, "a second run must change nothing"
    d = json.loads(after)
    assert d["hooks"]["Stop"] == [] and d["permissions"]["defaultMode"] == "auto", (
        "other keys untouched"
    )


def test_registration_timeout_exceeds_the_gates_inner_timeout(tmp_path, monkeypatch):
    """B8: the live registration said timeout 30 while the gate's inner subprocess allowed 120 —
    the harness killed the gate first and orphaned the child. Registration > inner (8 s)."""
    home = _home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    iuh.run([])
    d = json.loads((home / ".claude" / "settings.json").read_text())
    tos = [
        h["timeout"]
        for e in d["hooks"]["PreToolUse"]
        for h in e["hooks"]
        if "user_hook_gate" in h["command"]
    ]
    assert tos and all(t > 8 for t in tos)


def test_a_fleet_dir_added_later_is_covered_by_the_next_run(tmp_path, monkeypatch):
    home = _home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    iuh.run([])
    (home / ".claude-fleet" / "new").mkdir()
    (home / ".claude-fleet" / "new" / "settings.json").write_text("{}")
    assert iuh.run(["--check"]) == 1
    iuh.run([])
    assert iuh.run(["--check"]) == 0


def _entries(path: Path):
    return json.loads(path.read_text())["hooks"]


def test_check_sees_a_timeout_below_the_gates_inner_timeout_and_a_stale_path(tmp_path, monkeypatch):
    """P2-7/P2-8: `--check` compared command SUBSTRINGS — a timeout of 1 s (below the gate's 8 s)
    passed, and a moved checkout's stale registration stayed beside the new one, firing forever."""
    home = _home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    assert iuh.run([]) == 0
    f = home / ".claude" / "settings.json"
    d = json.loads(f.read_text())
    for ev in d["hooks"]:
        for e in d["hooks"][ev]:
            for h in e["hooks"]:
                h["timeout"] = 1
    f.write_text(json.dumps(d))
    assert iuh.run(["--check"]) == 1, "a timeout below the gate's inner timeout must fail --check"
    assert iuh.run([]) == 0 and iuh.run(["--check"]) == 0
    d = json.loads(f.read_text())
    d["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] = (
        "python3 /opt/OLDPATH/scripts/sysadmin/selfwatch_check.py"
    )
    f.write_text(json.dumps(d))
    assert iuh.run(["--check"]) == 1, "a stale path for the same script must fail --check"
    assert iuh.run([]) == 0
    cmds = [h["command"] for e in _entries(f)["UserPromptSubmit"] for h in e["hooks"]]
    assert sum("selfwatch_check.py" in c for c in cmds) == 1, cmds
    assert not any("OLDPATH" in c for c in cmds), (
        "the stale registration must be REPLACED, not joined"
    )


def test_a_missing_settings_file_in_an_account_dir_is_created(tmp_path, monkeypatch):
    """P2-9: the restorer's own motivating cases (a sixth account dir, a DR restore) had no
    settings.json — and the restorer skipped them."""
    home = _home(tmp_path)
    (home / ".claude-fleet" / "new").mkdir()
    (home / ".claude-fleet" / "new" / ".claude.json").write_text("{}")
    monkeypatch.setenv("HOME", str(home))
    assert iuh.run(["--check"]) == 1
    assert iuh.run([]) == 0
    assert (home / ".claude-fleet" / "new" / "settings.json").exists()
    assert iuh.run(["--check"]) == 0


def test_a_list_shaped_hooks_value_is_replaced_not_a_traceback(tmp_path, monkeypatch):
    """P2-3 (installer half): `hooks: [...]` escaped run() as AttributeError."""
    home = _home(tmp_path)
    (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": [1, 2]}))
    monkeypatch.setenv("HOME", str(home))
    assert iuh.run(["--check"]) == 1
    assert iuh.run([]) == 0 and isinstance(_entries(home / ".claude" / "settings.json"), dict)
