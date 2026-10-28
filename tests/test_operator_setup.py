"""Behavior Contract — `scripts/sysadmin/operator_setup.py` (W-d6726a65, operator requirement 1.1).

The operator runs the script once; every test drives it by subprocess against a scratch HOME, so no
test reads or writes the real account dirs, the installed wrapper or the editor settings.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "operator_setup.py"
WRAPPER_SRC = REPO / "scripts" / "sysadmin" / "claude-agent-wrapper.sh"
KEY = "claudeCode.claudeProcessWrapper"


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude" / "bin").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))
    acct = home / ".claude-fleet" / "api-can"
    acct.mkdir(parents=True)
    (acct / ".claude.json").write_text("{}")
    (acct / "settings.json").write_text(
        json.dumps({"theme": "dark", "permissions": {"allow": ["Bash(python3 scripts/api_write.py run *)"]}})
    )
    (home / ".claude" / "bin" / "claude-agent-wrapper.sh").write_text("#!/usr/bin/env bash\nexec \"$@\"\n")
    (home / ".claude" / "bin" / "claude-agent-wrapper.sh").chmod(0o755)
    cs = home / ".local" / "share" / "code-server" / "User"
    cs.mkdir(parents=True)
    (cs / "settings.json").write_text(json.dumps({"workbench.colorTheme": "Dark 2026", "files.watcherExclude": {"**/.tmp/**": True}}, indent=4) + "\n")
    return home


def _run(home: Path, *args: str, hub: Path | None = REPO) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "OPERATOR_SETUP"))}
    env["HOME"] = str(home)
    if hub is not None:
        env["OPERATOR_SETUP_HUB"] = str(hub)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=60
    )


def _digest(home: Path) -> dict[str, str]:
    return {
        str(p.relative_to(home)): hashlib.md5(p.read_bytes()).hexdigest() + oct(p.stat().st_mode)
        for p in sorted(home.rglob("*"))
        if p.is_file() and not p.is_symlink()
    }


def _backup_dirs(home: Path) -> list[Path]:
    root = home / ".claude" / "backups"
    return sorted(root.glob("operator-setup-*")) if root.is_dir() else []


def test_dry_run_writes_nothing_and_lists_every_change(tmp_path):
    home = _home(tmp_path)
    before = _digest(home)
    r = _run(home)
    assert r.returncode == 0, r.stderr
    assert _digest(home) == before, "a dry run wrote a file"
    out = r.stdout
    assert ".claude-fleet/api-can/settings.json" in out and "missing" in out
    assert "claude-agent-wrapper.sh" in out and "+++" in out, "the wrapper diff is not printed"
    assert KEY in out and "code-server" in out
    assert "--apply" in out


def test_apply_backs_up_every_changed_file_first(tmp_path):
    home = _home(tmp_path)
    originals = {
        rel: (home / rel).read_bytes()
        for rel in (
            ".claude/settings.json",
            ".claude-fleet/api-can/settings.json",
            ".claude/bin/claude-agent-wrapper.sh",
            ".local/share/code-server/User/settings.json",
        )
    }
    r = _run(home, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    dirs = _backup_dirs(home)
    assert len(dirs) == 1, dirs
    for rel, data in originals.items():
        assert (dirs[0] / rel).read_bytes() == data, f"{rel} not backed up byte for byte"
        assert (home / rel).read_bytes() != data, f"{rel} was not changed"
    assert f"cp -a {dirs[0]}/." in r.stdout, "the restore line is not printed"


def test_apply_installs_missing_hooks_and_keeps_other_keys(tmp_path):
    home = _home(tmp_path)
    assert _run(home, "--apply").returncode == 0
    d = json.loads((home / ".claude-fleet" / "api-can" / "settings.json").read_text())
    assert d["theme"] == "dark"
    assert d["permissions"]["allow"] == ["Bash(python3 scripts/api_write.py run *)"]
    cmds = [h["command"] for es in d["hooks"].values() for e in es for h in e["hooks"]]
    assert any("selfwatch_check.py" in c for c in cmds) and any("quota_stop.py" in c for c in cmds)


def test_apply_installs_the_wrapper_executable(tmp_path):
    home = _home(tmp_path)
    assert _run(home, "--apply").returncode == 0
    dst = home / ".claude" / "bin" / "claude-agent-wrapper.sh"
    assert dst.read_bytes() == WRAPPER_SRC.read_bytes()
    assert dst.stat().st_mode & 0o777 == 0o755


def test_settings_key_set_and_unparseable_file_refused(tmp_path):
    home = _home(tmp_path)
    machine = home / ".vscode-server" / "data" / "Machine"
    machine.mkdir(parents=True)
    jsonc = '{\n  // a comment\n  "editor.fontSize": 14,\n}\n'
    (machine / "settings.json").write_text(jsonc)
    r = _run(home, "--apply")
    assert r.returncode == 1, "an unparseable settings file must fail the run"
    assert (machine / "settings.json").read_text() == jsonc, "an unparseable file was rewritten"
    assert KEY in r.stdout + r.stderr
    cs = json.loads((home / ".local/share/code-server/User/settings.json").read_text())
    assert cs[KEY] == str(home / ".claude" / "bin" / "claude-agent-wrapper.sh")
    assert cs["workbench.colorTheme"] == "Dark 2026" and cs["files.watcherExclude"] == {"**/.tmp/**": True}


def test_apply_outside_the_hub_checkout_refuses(tmp_path):
    home = _home(tmp_path)
    before = _digest(home)
    r = _run(home, "--apply", hub=tmp_path / "not-the-hub")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "--apply refused" in r.stderr and "main checkout" in r.stderr
    assert _digest(home) == before
    assert not _backup_dirs(home)


def test_second_apply_is_a_no_op(tmp_path):
    home = _home(tmp_path)
    assert _run(home, "--apply").returncode == 0
    after_first = _digest(home)
    r = _run(home, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _digest(home) == after_first
    assert len(_backup_dirs(home)) == 1, "a no-op apply made a backup dir"
