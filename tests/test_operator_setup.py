"""Behavior Contract — `scripts/sysadmin/operator_setup.py` (W-d6726a65, operator requirement 1.1).

The operator runs the script once. Every test drives a copy of it by subprocess from a scratch hub
checkout (`<tmp>/hub/scripts/sysadmin/`, the script's only allowed home for `--apply`) against a
scratch HOME, so no test reads or writes the real account dirs, the installed wrapper or the editor
settings. `systemctl --user`, `loginctl` and `systemd-analyze --user` ignore HOME and would reach the
operator's real user manager, so every run puts the stateful stubs below first on PATH; their state
lives in `<tmp>/stub-state/`, outside the scratch HOME, and every call is logged there.
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
COPIED = ("operator_setup.py", "claude-agent-wrapper.sh", "install_user_hooks.py", "install_session_archive_timer.sh")
UNITS = ("session-archive-alert.service", "session-archive.service", "session-archive.timer")
UNIT_DIR = ".config/systemd/user"

# The stub user manager: `enable --now` flips the timer to enabled+active, `daemon-reload` loads the
# installed archive unit (so `show -p OnFailure` reads the LOADED value), and a flag file in the state dir
# makes `daemon-reload` fail (`fail-daemon-reload`), cuts the bus (`nobus`), fails `show` alone (`show-error`),
# makes `enable` a silent no-op (`enable-noop`) or turns linger off (`linger-off`).
STUBS = {
    "systemctl": r"""#!/usr/bin/env bash
s="${STUB_STATE:?}"
printf 'systemctl %s\n' "$*" >> "$s/calls.log"
if [ -e "$s/nobus" ]; then echo "Failed to connect to bus: No medium found" >&2; exit 1; fi
[ "$1" = "--user" ] && shift
cfg="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
case "$1" in
  is-enabled) if [ -e "$s/enabled" ]; then echo enabled; else echo disabled; exit 1; fi ;;
  is-active) if [ -e "$s/enabled" ]; then echo active; else echo inactive; exit 3; fi ;;
  show) if [ -e "$s/show-error" ]; then echo "Failed to get properties: Access denied" >&2; exit 1; fi
        if [ -e "$s/loaded" ]; then sed -n 's/^OnFailure=//p' "$s/loaded" | tail -n 1; else echo; fi ;;
  daemon-reload) [ -e "$s/fail-daemon-reload" ] && exit 1; cp "$cfg/session-archive.service" "$s/loaded" ;;
  enable) [ -e "$s/enable-noop" ] || touch "$s/enabled" ;;
  disable) rm -f "$s/enabled" ;;
  list-timers) : ;;
  *) echo "stub systemctl: unexpected $*" >&2; exit 1 ;;
esac
""",
    "loginctl": r"""#!/usr/bin/env bash
printf 'loginctl %s\n' "$*" >> "${STUB_STATE:?}/calls.log"
if [ -e "$STUB_STATE/linger-off" ]; then echo Linger=no; else echo Linger=yes; fi
""",
    "systemd-analyze": r"""#!/usr/bin/env bash
printf 'systemd-analyze %s\n' "$*" >> "${STUB_STATE:?}/calls.log"
""",
}
KEY = "claudeCode.claudeProcessWrapper"
API_ALLOW = ["Bash(python3 scripts/api_write.py run *)"]


def _hub(tmp_path: Path, name: str = "sysadmin", head: str = "ref: refs/heads/master\n") -> Path:
    hub = tmp_path / "hub"
    (hub / "scripts" / name).mkdir(parents=True)
    for f in COPIED:
        shutil.copy2(SYSADMIN / f, hub / "scripts" / name / f)
    shutil.copytree(SYSADMIN / "systemd", hub / "scripts" / name / "systemd", dirs_exist_ok=True)
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
    # the live box: the archive service installed before its OnFailure= line, no alert unit, the timer current,
    # enabled and active, the loaded service without OnFailure=
    (home / UNIT_DIR).mkdir(parents=True)
    (home / UNIT_DIR / "session-archive.service").write_text("[Service]\nExecStart=/bin/true\n")
    shutil.copy(SYSADMIN / "systemd" / "session-archive.timer", home / UNIT_DIR / "session-archive.timer")
    for u in ("session-archive.service", "session-archive.timer"):
        (home / UNIT_DIR / u).chmod(0o644)
    state, stubs = tmp_path / "stub-state", tmp_path / "stub-bin"
    state.mkdir()
    stubs.mkdir()
    (state / "enabled").touch()
    (state / "loaded").write_text("[Service]\n")
    for name, body in STUBS.items():
        (stubs / name).write_text(body)
        (stubs / name).chmod(0o755)
    for d in (home, home / ".claude", home / ".claude-fleet", acct):
        d.chmod(0o700)
    return home


def _env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "OPERATOR_SETUP", "XDG_CONFIG"))}
    env["HOME"] = str(home)
    env["STUB_STATE"] = str(home.parent / "stub-state")
    env["PATH"] = f"{home.parent / 'stub-bin'}{os.pathsep}{env.get('PATH', '')}"
    return env


def _calls(home: Path) -> list[str]:
    log = home.parent / "stub-state" / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def _manager_writes(home: Path) -> list[str]:
    return [c for c in _calls(home) if c.startswith("systemctl --user ") and c.split()[2] in ("daemon-reload", "enable", "disable")]


def _run(home: Path, hub: Path, *args: str, script: Path | None = None) -> subprocess.CompletedProcess:
    env = _env(home)
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
        f"{UNIT_DIR}/session-archive-alert.service",
        f"{UNIT_DIR}/session-archive.service",
    ):
        assert f"+++ {rel}" in out, f"no diff printed for {rel}"
    assert f"+++ {UNIT_DIR}/session-archive.timer" not in out, "an unchanged unit was planned"
    assert "selfwatch_check.py" in out and KEY in out and "--apply" in out
    assert "== archive: installer run" in out, out
    assert not _manager_writes(home), f"a dry run touched the user manager: {_calls(home)}"


def test_apply_backs_up_every_changed_file_first(tmp_path):
    home, hub = _home(tmp_path), _hub(tmp_path)
    existed = (
        ".claude/settings.json",
        ".claude-fleet/api-can/settings.json",
        ".claude/bin/claude-agent-wrapper.sh",
        ".local/share/code-server/User/settings.json",
    )
    created = ".vscode-server/data/Machine/settings.json"
    existed += (f"{UNIT_DIR}/session-archive.service",)
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
    restore = [ln for ln in r.stdout.splitlines() if ln.startswith(("cp -p ", "rm ", "systemctl "))]
    files = [ln for ln in restore if not ln.startswith("systemctl ")]
    assert len(files) == len(existed) + 2, r.stdout  # + the Machine settings and the alert unit, both created
    assert restore[-1] == "systemctl --user daemon-reload", r.stdout
    env = _env(home)  # the systemctl lines run against the stubs
    for ln in restore:
        subprocess.run(["bash", "-c", ln], env=env, check=True)
    for rel, data in originals.items():
        assert (home / rel).read_bytes() == data, f"{rel} not restored"
    assert not (home / created).exists(), "a created file survived its restore line"
    assert not (home / UNIT_DIR / "session-archive-alert.service").exists(), "the installed alert unit survived its restore line"
    after = {k: v for k, v in _digest(home).items() if not k.startswith(".local/state")}
    assert after == before,"the restore lines changed a mode or left a change behind"


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


def test_apply_installs_the_wrapper_and_the_archive_timer(tmp_path):
    home, hub = _home(tmp_path), _hub(tmp_path)
    r = _run(home, hub, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    dst = home / ".claude" / "bin" / "claude-agent-wrapper.sh"
    assert dst.read_bytes() == (SYSADMIN / "claude-agent-wrapper.sh").read_bytes()
    assert dst.stat().st_mode & 0o777 == 0o755
    for u in UNITS:
        installed = home / UNIT_DIR / u
        assert installed.read_bytes() == (SYSADMIN / "systemd" / u).read_bytes(), u
        assert installed.stat().st_mode & 0o777 == 0o644, u
    assert "systemctl --user enable --now session-archive.timer" in _calls(home), _calls(home)
    assert r.stdout.index("installer exit 0") < r.stdout.index("wrote "), "the installer did not run first"
    # linger off, or no user manager: refused at planning, nothing written, the manager never touched
    for flag, said in (
        ("linger-off", "loginctl enable-linger"),
        ("nobus", "cannot reach the user systemd manager"),
        ("show-error", "cannot reach the user systemd manager"),  # one read fails with stdout empty: never "not set"
    ):
        h = _home(tmp_path / flag)
        (h.parent / "stub-state" / flag).touch()
        before = _digest(h)
        r = _run(h, hub, "--apply")
        assert r.returncode == 1 and said in r.stderr, (flag, r.stdout + r.stderr)
        assert _digest(h) == before, f"{flag}: something was written"
        assert not _manager_writes(h), (flag, _calls(h))
    # the installer dies after writing the units (daemon-reload fails, it prints nothing): steps 1-3 stay
    # unwritten, and the restore lines name exactly the units it changed
    h = _home(tmp_path / "reload-fails")
    (h.parent / "stub-state" / "fail-daemon-reload").touch()
    wrapper_before = (h / ".claude" / "bin" / "claude-agent-wrapper.sh").read_bytes()
    r = _run(h, hub, "--apply")
    assert r.returncode == 1, r.stdout + r.stderr
    assert (h / ".claude" / "bin" / "claude-agent-wrapper.sh").read_bytes() == wrapper_before, "step 2 ran after a failed installer"
    named = sorted(ln.split("/")[-1].strip("'\"") for ln in r.stdout.splitlines() if ln.startswith(("cp -p ", "rm ")))
    assert named == ["session-archive-alert.service", "session-archive.service"], r.stdout
    # the installer exits 0 but the timer never got enabled: the run's verify reads the manager and fails it
    h = _home(tmp_path / "enable-noop")
    (h.parent / "stub-state" / "enabled").unlink()
    (h.parent / "stub-state" / "enable-noop").touch()
    r = _run(h, hub, "--apply")
    assert r.returncode == 1 and "VERIFY FAILED — archive" in r.stderr, r.stdout + r.stderr


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
        if case == "symlink":
            assert "is a symlink" in r.stderr, r.stderr
        assert _digest(h2) == before, f"{case}: something was written"
    # a file edited between planning and writing is never overwritten (in-process: plan, edit, apply)
    h3 = _home(tmp_path / "race")
    spec = importlib.util.spec_from_file_location("operator_setup", hub / "scripts" / "sysadmin" / "operator_setup.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "operator_setup", mod)  # @dataclass resolves its module by name
    spec.loader.exec_module(mod)
    for k, v in _env(h3).items():
        monkeypatch.setenv(k, v)
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
        "worktree copy": {"hub": _hub(tmp_path), "script": SYSADMIN / "operator_setup.py"},
        "sysadmin- sibling": {"hub": evil, "script": evil / "scripts" / "sysadmin-evil" / "operator_setup.py"},
        "hub off master": {"hub": _hub(tmp_path / "branch", head="ref: refs/heads/feature\n"), "script": None},
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
    assert "installer exit" not in r.stdout, "a no-op apply re-ran the archive installer"
    # equal unit files are not "in place" when the manager disagrees: an unreloaded unit, a disabled timer
    state = home.parent / "stub-state"
    loaded = (state / "loaded").read_bytes()
    for breaks, why in (("loaded", "loaded OnFailure=(empty)"), ("enabled", "timer disabled")):
        if breaks == "loaded":
            (state / "loaded").write_text("[Service]\n")
        else:
            (state / "enabled").unlink()
        r = _run(home, hub)
        assert r.returncode == 0 and "== archive: installer run (" in r.stdout and why in r.stdout, (breaks, r.stdout)
        (state / "loaded").write_bytes(loaded)
        (state / "enabled").touch()
