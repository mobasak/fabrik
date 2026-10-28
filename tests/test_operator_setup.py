"""Behavior Contract — `scripts/sysadmin/operator_setup.py` (W-d6726a65, operator requirement 1.1).

The operator runs the script once. Every test drives a copy of it by subprocess from a scratch hub
checkout (`<tmp>/hub/scripts/sysadmin/`, the script's only allowed home for `--apply`) against a
scratch HOME, so no test reads or writes the real account dirs, the installed wrapper or the editor
settings.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SYSADMIN = REPO / "scripts" / "sysadmin"
COPIED = ("operator_setup.py", "claude-agent-wrapper.sh", "install_user_hooks.py")
KEY = "claudeCode.claudeProcessWrapper"
API_ALLOW = ["Bash(python3 scripts/api_write.py run *)"]


def _hub(tmp_path: Path, name: str = "sysadmin", head: str = "ref: refs/heads/master\n") -> Path:
    hub = tmp_path / "hub"
    (hub / "scripts" / name).mkdir(parents=True)
    for f in COPIED:
        shutil.copy2(SYSADMIN / f, hub / "scripts" / name / f)
    (hub / ".git").mkdir(exist_ok=True)
    (hub / ".git" / "HEAD").write_text(head)
    return hub


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude" / "bin").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))
    acct = home / ".claude-fleet" / "api-can"
    acct.mkdir(parents=True)
    (acct / ".claude.json").write_text("{}")
    (acct / "settings.json").write_text(json.dumps({"theme": "dark", "permissions": {"allow": API_ALLOW}}))
    wrapper = home / ".claude" / "bin" / "claude-agent-wrapper.sh"
    wrapper.write_text('#!/usr/bin/env bash\nexec "$@"\n')
    wrapper.chmod(0o755)
    cs = home / ".local" / "share" / "code-server" / "User"
    cs.mkdir(parents=True)
    (cs / "settings.json").write_text(
        json.dumps({"workbench.colorTheme": "Dark 2026", "files.watcherExclude": {"**/.tmp/**": True}}, indent=4) + "\n"
    )
    (home / ".vscode-server" / "data" / "Machine").mkdir(parents=True)  # parent present, file absent → created
    for d in (home, home / ".claude", home / ".claude-fleet", acct):
        d.chmod(0o700)
    return home


def _run(home: Path, hub: Path, *args: str, script: Path | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "OPERATOR_SETUP"))}
    env["HOME"] = str(home)
    env["OPERATOR_SETUP_HUB"] = str(hub)
    script = script or hub / "scripts" / "sysadmin" / "operator_setup.py"
    return subprocess.run([sys.executable, str(script), *args], env=env, capture_output=True, text=True, timeout=60)


def _digest(home: Path) -> dict[str, str]:
    return {
        str(p.relative_to(home)): (hashlib.md5(p.read_bytes()).hexdigest() if p.is_file() else "dir")
        + oct(p.lstat().st_mode)
        for p in sorted(home.rglob("*"))
    }


def _backup_dirs(home: Path) -> list[Path]:
    root = home / ".local" / "state" / "fabrik"
    return sorted(root.glob("operator-setup-*")) if root.is_dir() else []


def test_dry_run_writes_nothing_and_lists_every_change(tmp_path):
    home, hub = _home(tmp_path), _hub(tmp_path)
    before = _digest(home)
    r = _run(home, hub)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _digest(home) == before, "a dry run wrote under HOME"
    out = r.stdout
    for rel in (
        ".claude-fleet/api-can/settings.json",
        ".claude/bin/claude-agent-wrapper.sh",
        ".local/share/code-server/User/settings.json",
        ".vscode-server/data/Machine/settings.json",
    ):
        assert f"+++ {rel}" in out, f"no diff printed for {rel}"
    assert "selfwatch_check.py" in out and KEY in out and "--apply" in out


def test_apply_backs_up_every_changed_file_first(tmp_path):
    home, hub = _home(tmp_path), _hub(tmp_path)
    existed = (
        ".claude/settings.json",
        ".claude-fleet/api-can/settings.json",
        ".claude/bin/claude-agent-wrapper.sh",
        ".local/share/code-server/User/settings.json",
    )
    created = ".vscode-server/data/Machine/settings.json"
    originals = {rel: (home / rel).read_bytes() for rel in existed}
    before = _digest(home)
    r = _run(home, hub, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    dirs = _backup_dirs(home)
    assert len(dirs) == 1, dirs
    assert dirs[0].stat().st_mode & 0o777 == 0o700
    for rel, data in originals.items():
        assert (dirs[0] / rel).read_bytes() == data, f"{rel} not backed up byte for byte"
        assert (home / rel).read_bytes() != data, f"{rel} was not changed"
    assert (home / created).is_file() and not (dirs[0] / created).exists()
    restore = [ln for ln in r.stdout.splitlines() if ln.startswith(("cp -p ", "rm "))]
    assert len(restore) == len(existed) + 1, r.stdout
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    for ln in restore:
        subprocess.run(["bash", "-c", ln], env=env, check=True)
    for rel, data in originals.items():
        assert (home / rel).read_bytes() == data, f"{rel} not restored"
    assert not (home / created).exists(), "a created file survived its restore line"
    after = {k: v for k, v in _digest(home).items() if not k.startswith(".local/state")}
    assert after == {k: v for k, v in before.items()}, "the restore lines changed a mode or left a change behind"


def test_apply_installs_missing_hooks_and_keeps_other_keys(tmp_path):
    home, hub = _home(tmp_path), _hub(tmp_path)
    assert _run(home, hub, "--apply").returncode == 0
    path = home / ".claude-fleet" / "api-can" / "settings.json"
    d = json.loads(path.read_text())
    assert d["theme"] == "dark" and d["permissions"]["allow"] == API_ALLOW
    cmds = [h["command"] for es in d["hooks"].values() for e in es for h in e["hooks"]]
    assert any("selfwatch_check.py" in c for c in cmds) and any("quota_stop.py" in c for c in cmds)
    # the bytes are the installer's own output: its --check now passes on this HOME
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env["HOME"] = str(home)
    chk = subprocess.run(
        [sys.executable, str(hub / "scripts" / "sysadmin" / "install_user_hooks.py"), "--check"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert chk.returncode == 0, chk.stdout


def test_apply_installs_the_wrapper_executable(tmp_path):
    home, hub = _home(tmp_path), _hub(tmp_path)
    assert _run(home, hub, "--apply").returncode == 0
    dst = home / ".claude" / "bin" / "claude-agent-wrapper.sh"
    assert dst.read_bytes() == (SYSADMIN / "claude-agent-wrapper.sh").read_bytes()
    assert dst.stat().st_mode & 0o777 == 0o755


def test_settings_key_set_and_unparseable_file_refused(tmp_path, monkeypatch):
    home, hub = _home(tmp_path), _hub(tmp_path)
    assert _run(home, hub, "--apply").returncode == 0
    cs = json.loads((home / ".local/share/code-server/User/settings.json").read_text())
    assert cs[KEY] == str(home / ".claude" / "bin" / "claude-agent-wrapper.sh")
    assert cs["workbench.colorTheme"] == "Dark 2026" and cs["files.watcherExclude"] == {"**/.tmp/**": True}
    machine = json.loads((home / ".vscode-server/data/Machine/settings.json").read_text())
    assert machine == {KEY: str(home / ".claude" / "bin" / "claude-agent-wrapper.sh")}
    # JSONC, a duplicate key, the nested claudeCode form, a symlinked account file: rc 1, nothing written anywhere
    bad_machine = {
        "jsonc": '{\n  // c\n  "editor.fontSize": 14,\n}\n',
        "duplicate": '{"editor.fontSize": 14, "editor.fontSize": 15}\n',
        "nested": '{"claudeCode": {"claudeProcessWrapper": "/x"}}\n',
        "list": "[1, 2]\n",
    }
    for case in (*bad_machine, "account jsonc", "symlink"):
        h2 = _home(tmp_path / case.replace(" ", "-"))
        if case in bad_machine:
            (h2 / ".vscode-server/data/Machine/settings.json").write_text(bad_machine[case])
        elif case == "account jsonc":
            (h2 / ".claude-fleet/api-can/settings.json").write_text('{\n  // c\n  "theme": "dark"\n}\n')
        else:
            acct = h2 / ".claude-fleet" / "api-can" / "settings.json"
            real = h2 / "real-settings.json"
            acct.rename(real)
            acct.symlink_to(real)
        before = _digest(h2)
        r = _run(h2, hub, "--apply")
        assert r.returncode == 1, (case, r.stdout + r.stderr)
        assert "Traceback" not in r.stderr and "Nothing was written" in r.stderr, (case, r.stderr)
        if case == "account jsonc":
            assert "the installer would skip it" in r.stderr, r.stderr
        assert _digest(h2) == before, f"{case}: something was written"
    # a file edited between planning and writing is never overwritten (in-process: plan, edit, apply)
    h3 = _home(tmp_path / "race")
    spec = importlib.util.spec_from_file_location("operator_setup", hub / "scripts" / "sysadmin" / "operator_setup.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "operator_setup", mod)  # @dataclass resolves its module by name
    spec.loader.exec_module(mod)
    monkeypatch.setenv("HOME", str(h3))
    changes = mod.plan(h3)
    (h3 / ".local/share/code-server/User/settings.json").write_text('{"editor.fontSize": 20}\n')
    before = _digest(h3)
    assert mod.apply(h3, changes) == 1
    assert _digest(h3) == before, "a file edited after planning was overwritten, or a backup was made"


def test_apply_outside_the_hub_checkout_refuses(tmp_path):
    home = _home(tmp_path)
    before = _digest(home)
    evil = _hub(tmp_path / "evil")  # a `sysadmin-evil` sibling inside the SAME hub: a prefix match would pass it
    (evil / "scripts" / "sysadmin-evil").mkdir()
    for f in COPIED:
        shutil.copy2(SYSADMIN / f, evil / "scripts" / "sysadmin-evil" / f)
    cases = {
        "worktree copy": dict(hub=_hub(tmp_path), script=SYSADMIN / "operator_setup.py"),
        "sysadmin- sibling": dict(hub=evil, script=evil / "scripts" / "sysadmin-evil" / "operator_setup.py"),
        "hub off master": dict(hub=_hub(tmp_path / "branch", head="ref: refs/heads/feature\n"), script=None),
    }
    for label, c in cases.items():
        r = _run(home, c["hub"], "--apply", script=c["script"])
        assert r.returncode == 2, (label, r.stdout + r.stderr)
        assert "--apply refused" in r.stderr, label
        assert _digest(home) == before, f"{label}: something was written"


def test_second_apply_is_a_no_op(tmp_path):
    home, hub = _home(tmp_path), _hub(tmp_path)
    assert _run(home, hub, "--apply").returncode == 0
    after_first = _digest(home)
    r = _run(home, hub, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _digest(home) == after_first
    assert len(_backup_dirs(home)) == 1, "a no-op apply made a backup dir"
