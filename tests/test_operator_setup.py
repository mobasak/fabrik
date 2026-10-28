"""Behavior Contract — `scripts/sysadmin/operator_setup.py` (W-d6726a65, operator requirement 1.1).

The operator runs the script once. Every test drives a copy of it from a scratch hub checkout
(`<tmp>/hub/scripts/sysadmin/`, the script's only allowed home for `--apply`) against a scratch HOME, so no
test reads or writes the real account dirs, the installed wrapper or the editor settings. The copy runs by
subprocess, except the in-process interleavings in `test_settings_key_set_and_unparseable_file_refused` (an
edit, a symlink, an interrupt or a hub pull between planning and writing), which load that same copy. `systemctl --user`, `loginctl` and `systemd-analyze --user` ignore HOME and would reach the
operator's real user manager, so every run puts the stateful stubs below first on PATH; their state
lives in `<tmp>/stub-state/`, outside the scratch HOME, and every call is logged there.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SYSADMIN = REPO / "scripts" / "sysadmin"
COPIED = ("operator_setup.py", "claude-agent-wrapper.sh", "install_user_hooks.py", "install_session_archive_timer.sh")
UNITS = ("session-archive-alert.service", "session-archive.service", "session-archive.timer")
UNIT_DIR = ".config/systemd/user"

# The stub user manager, modelled on systemd 255's answers (stdout, exit code, silent stderr — systemctl-is-enabled.c,
# systemctl-is-active.c, systemctl-show.c at v255): `is-enabled` reads `enabled` (`not-found`, exit 4, when the timer
# file is absent), `is-active` reads `active` on its own, `enable --now` sets both, `disable` clears `enabled`, `stop`
# clears `active`, and `daemon-reload` loads the installed archive unit, so `show -p OnFailure` reads the LOADED
# value. A flag file in the state dir makes `daemon-reload` fail (`fail-daemon-reload`), cuts the bus (`nobus`), fails
# `show` alone (`show-error`), adds a second OnFailure= unit (`extra-onfailure`), makes `enable` a silent no-op
# (`enable-noop`), makes `enable` overwrite the file named in `edit-during` (an editor saving mid-run), makes
# `systemd-analyze verify` speak (`verify-noise`, the installer then refuses before any write) or turns linger off
# (`linger-off`).
STUBS = {
    "systemctl": r"""#!/usr/bin/env bash
s="${STUB_STATE:?}"
printf 'systemctl %s\n' "$*" >> "$s/calls.log"
if [ -e "$s/nobus" ]; then echo "Failed to connect to bus: No medium found" >&2; exit 1; fi
[ "$1" = "--user" ] && shift
cfg="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
case "$1" in
  is-enabled) if [ ! -e "$cfg/$2" ]; then echo not-found; exit 4; fi
              if [ -e "$s/enabled" ]; then echo enabled; else echo disabled; exit 1; fi ;;
  is-active) if [ -e "$s/active" ]; then echo active; else echo inactive; exit 3; fi ;;
  show) if [ -e "$s/show-error" ]; then echo "Failed to get properties: Access denied" >&2; exit 1; fi
        if [ -e "$s/loaded" ]; then v=$(sed -n 's/^OnFailure=//p' "$s/loaded" | tail -n 1); else v=; fi
        if [ -e "$s/extra-onfailure" ]; then v="$v other-alert.service"; fi
        echo "$v" ;;
  daemon-reload) [ -e "$s/fail-daemon-reload" ] && exit 1; cp "$cfg/session-archive.service" "$s/loaded" ;;
  enable) [ -e "$s/edit-during" ] && printf '{"edited": true}\n' > "$(cat "$s/edit-during")"
          [ -e "$s/enable-noop" ] || touch "$s/enabled" "$s/active" ;;
  disable) rm -f "$s/enabled" ;;
  stop) rm -f "$s/active" ;;
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
if [ -e "$STUB_STATE/verify-noise" ]; then echo "session-archive.service:3: Unknown key name 'Bogus'"; fi
""",
    # the ssh step grades with ssh's own resolver; the conftest's fleet shim refuses every ssh, so this stub (first
    # on PATH) passes ONLY `-G` — resolve the config and print it, never connect — to the real binary and refuses
    # the rest as the shim does. COBRA (D-253): widening this to any other mode would reopen the fleet; the test
    # configs carry no `Match exec` and no CanonicalizeHostname, so `-G` touches neither a command nor DNS.
    "ssh": r"""#!/usr/bin/env bash
printf 'ssh %s\n' "$*" >> "${STUB_STATE:?}/calls.log"
[ "$1" = "-G" ] || { echo "stub ssh: only -G passes" >&2; exit 255; }
exec /usr/bin/ssh "$@"
""",
}
KEY = "claudeCode.claudeProcessWrapper"
API_ALLOW = ["Bash(python3 scripts/api_write.py run *)"]
SSH_CONFIG = ".ssh/config"
GH = "git@github.com"

# the ssh step grades with the real `ssh -G -F <copy>` (it never connects), reached through the `ssh` stub below
pytestmark = pytest.mark.skipif(not Path("/usr/bin/ssh").exists(), reason="the ssh step grades with the real ssh -G")

_RESOLVE = """import subprocess, sys
r = subprocess.run(["ssh", "-G", "-F", sys.argv[1], sys.argv[2]], capture_output=True, text=True,
                   stdin=subprocess.DEVNULL, timeout=30, check=True)
v = dict(line.split(" ", 1) for line in r.stdout.splitlines() if " " in line)
print(v.get("serveraliveinterval"), v.get("serveralivecountmax"))
"""


def _resolved(cfg: Path, home: Path, host: str = GH) -> tuple[str, str]:
    """(ServerAliveInterval, ServerAliveCountMax) ssh resolves for `host` from `cfg` alone — run in a child Python
    through the `ssh` stub, as the script runs it (this process's fleet guard refuses any ssh it starts)."""
    r = subprocess.run([sys.executable, "-c", _RESOLVE, str(cfg), host], env=_env(home), capture_output=True,
                       text=True, timeout=60, check=True)
    interval, count = r.stdout.split()
    return interval, count


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
    (state / "active").touch()
    (state / "loaded").write_text("[Service]\n")
    for name, body in STUBS.items():
        (stubs / name).write_text(body)
        (stubs / name).chmod(0o755)
    (home / ".ssh").mkdir()  # present and empty: the ssh step creates the config
    for d in (home, home / ".claude", home / ".claude-fleet", acct, home / ".ssh"):
        d.chmod(0o700)
    return home


def _env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "OPERATOR_SETUP", "XDG_CONFIG"))}
    env["HOME"] = str(home)
    env["STUB_STATE"] = str(home.parent / "stub-state")
    env["PATH"] = f"{home.parent / 'stub-bin'}{os.pathsep}{env.get('PATH', '')}"
    env["OPERATOR_SETUP_SSH_HOME"] = "1"  # the scratch HOME is not the passwd home ssh reads
    return env


def _calls(home: Path) -> list[str]:
    log = home.parent / "stub-state" / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def _manager_writes(home: Path) -> list[str]:
    return [c for c in _calls(home) if c.startswith("systemctl --user ") and c.split()[2] in ("daemon-reload", "enable", "disable", "stop")]


def _restore(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if ln.startswith(("cp -p ", "rm ", "systemctl "))]


def _run(home: Path, hub: Path, *args: str, script: Path | None = None, **extra: str) -> subprocess.CompletedProcess:
    env = _env(home)
    env.update(extra)
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
        SSH_CONFIG,
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
    assert len(files) == len(existed) + 3, r.stdout  # + the Machine settings, the alert unit and the ssh config, all created
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
    (h / UNIT_DIR / "session-archive.timer").chmod(0o600)  # right bytes, wrong mode: the installer's 0644 is a change too
    steps_1_to_3 = (
        ".claude/settings.json",
        ".claude-fleet/api-can/settings.json",
        ".claude/bin/claude-agent-wrapper.sh",
        ".local/share/code-server/User/settings.json",
    )
    untouched = {rel: (h / rel).read_bytes() for rel in steps_1_to_3}
    r = _run(h, hub, "--apply")
    assert r.returncode == 1, r.stdout + r.stderr
    for rel, data in untouched.items():
        assert (h / rel).read_bytes() == data, f"{rel} was written after a failed installer"
    assert not (h / ".vscode-server/data/Machine/settings.json").exists(), "step 3 created a file after a failed installer"
    assert not (h / SSH_CONFIG).exists(), "the ssh step wrote after a failed installer"
    named = sorted(ln.split("/")[-1].strip("'\"") for ln in r.stdout.splitlines() if ln.startswith(("cp -p ", "rm ")))
    assert named == ["session-archive-alert.service", "session-archive.service", "session-archive.timer"], r.stdout
    # the installer refuses before writing anything (its verify speaks): no file joins the undo lines
    h = _home(tmp_path / "verify-noise")
    (h.parent / "stub-state" / "verify-noise").touch()
    r = _run(h, hub, "--apply")
    assert r.returncode == 1, r.stdout + r.stderr
    assert not [ln for ln in _restore(r.stdout) if not ln.startswith("systemctl ")], r.stdout
    # the installer exits 0 but the timer never got enabled: the run's verify reads the manager and fails it;
    # the undo lines disable the timer BEFORE the unit files go, since a removed unit cannot be disabled
    h = _home(tmp_path / "enable-noop")
    (h.parent / "stub-state" / "enabled").unlink()
    (h.parent / "stub-state" / "enable-noop").touch()
    r = _run(h, hub, "--apply")
    assert r.returncode == 1 and "VERIFY FAILED — archive" in r.stderr, r.stdout + r.stderr
    undo = _restore(r.stdout)
    assert undo[0] == "systemctl --user disable session-archive.timer", r.stdout
    assert "systemctl --user stop session-archive.timer" not in undo, "a timer that was active is stopped by the undo"
    assert undo[-1] == "systemctl --user daemon-reload", r.stdout
    # a fresh box (no unit installed, the timer not-found): installed whole; the undo disables and stops it first
    h = _home(tmp_path / "fresh")
    for u in ("session-archive.service", "session-archive.timer"):
        (h / UNIT_DIR / u).unlink()
    for f in ("enabled", "active"):
        (h.parent / "stub-state" / f).unlink()
    r = _run(h, hub, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    assert all((h / UNIT_DIR / u).read_bytes() == (SYSADMIN / "systemd" / u).read_bytes() for u in UNITS)
    undo = _restore(r.stdout)
    assert undo[:2] == ["systemctl --user disable session-archive.timer", "systemctl --user stop session-archive.timer"], r.stdout
    # an editor saving its settings while the installer runs: never overwritten, the run stops
    h = _home(tmp_path / "edit-during")
    cs = h / ".local/share/code-server/User/settings.json"
    (h.parent / "stub-state" / "edit-during").write_text(str(cs))
    r = _run(h, hub, "--apply")
    assert r.returncode == 1 and "changed since it was planned" in r.stderr, r.stdout + r.stderr
    assert cs.read_text() == '{"edited": true}\n', "an editor's mid-run save was overwritten"
    # a wrapper with the right bytes but the wrong mode is repaired, and the dry run says so
    h = _home(tmp_path / "wrapper-mode")
    w = h / ".claude" / "bin" / "claude-agent-wrapper.sh"
    shutil.copy(SYSADMIN / "claude-agent-wrapper.sh", w)
    w.chmod(0o644)
    r = _run(h, hub)
    assert "== wrapper: .claude/bin/claude-agent-wrapper.sh" in r.stdout and "mode 644 -> 755" in r.stdout, r.stdout
    # a unit dir spelled with `..` resolves outside the backup dir's tree: refused
    h = _home(tmp_path / "dotdot")
    r = _run(h, hub, XDG_CONFIG_HOME=f"{h}/../home/.config")
    assert r.returncode == 1 and "Nothing was written" in r.stderr, r.stdout + r.stderr


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
    for case in (*bad_machine, "account jsonc", "account duplicate", "symlink"):
        h2 = _home(tmp_path / case.replace(" ", "-"))
        if case in bad_machine:
            (h2 / ".vscode-server/data/Machine/settings.json").write_text(bad_machine[case])
        elif case == "account jsonc":
            (h2 / ".claude-fleet/api-can/settings.json").write_text('{\n  // c\n  "theme": "dark"\n}\n')
        elif case == "account duplicate":  # the installer would keep the last value and drop the other silently
            (h2 / ".claude-fleet/api-can/settings.json").write_text('{"theme": "dark", "theme": "light"}\n')
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
    # in-process, this test's fleet guard refuses every ssh the planner starts; the ssh step has its own
    # subprocess tests below, so these interleavings of the other steps run without it
    monkeypatch.setattr(mod, "plan_ssh", lambda home: [])
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)  # the subprocess env strips it; so must this one
    for k, v in _env(h3).items():
        monkeypatch.setenv(k, v)
    changes = mod.plan(h3)
    (h3 / ".local/share/code-server/User/settings.json").write_text('{"editor.fontSize": 20}\n')
    before = _digest(h3)
    assert mod.apply(h3, changes) == 1
    assert _digest(h3) == before, "a file edited after planning was overwritten, or a backup was made"
    # a target that turns into a symlink after planning: a refusal, not a traceback
    h4 = _home(tmp_path / "late-symlink")
    for k, v in _env(h4).items():
        monkeypatch.setenv(k, v)
    p4 = mod.plan(h4)
    cs = h4 / ".local/share/code-server/User/settings.json"
    real = h4 / "real-cs.json"
    cs.rename(real)
    cs.symlink_to(real)
    assert mod.apply(h4, p4) == 1
    assert any(b.startswith("vscode: ") and "is a symlink" in b for b in mod.verify(h4)), "verify raised or passed"
    # the installer interrupted after writing the units: the undo lines still name every unit it wrote
    h5 = _home(tmp_path / "interrupt")
    for k, v in _env(h5).items():
        monkeypatch.setenv(k, v)
    p5 = mod.plan(h5)

    def dies_after_writing(argv, *a, **k):
        for u in UNITS:
            shutil.copy(SYSADMIN / "systemd" / u, h5 / UNIT_DIR / u)
        (h5 / UNIT_DIR / UNITS[0]).chmod(0o000)  # a unit the undo set cannot read back: still listed, never raising
        raise KeyboardInterrupt

    real_run = subprocess.run
    monkeypatch.setattr(mod.subprocess, "run", dies_after_writing)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), pytest.raises(KeyboardInterrupt):
            mod.apply(h5, p5)
    finally:
        (h5 / UNIT_DIR / UNITS[0]).chmod(0o644)
        monkeypatch.setattr(mod.subprocess, "run", real_run)  # never monkeypatch.undo(): it would bring back XDG_CONFIG_HOME
    named = sorted(ln.split("/")[-1].strip("'\"") for ln in out.getvalue().splitlines() if ln.startswith(("cp -p ", "rm ")))
    assert named == ["session-archive-alert.service", "session-archive.service"], out.getvalue()
    # a source unit that changes, or goes, between planning and the installer run (a hub pull): nothing written
    for label, move in (("source-moved", "edit"), ("source-gone", "delete")):
        h6 = _home(tmp_path / label)
        for k, v in _env(h6).items():
            monkeypatch.setenv(k, v)
        p6 = mod.plan(h6)
        src = hub / "scripts" / "sysadmin" / "systemd" / "session-archive.service"
        kept = src.read_bytes()
        if move == "edit":
            src.write_bytes(kept + b"# pulled\n")
        else:
            src.unlink()
        before = _digest(h6)
        assert mod.apply(h6, p6) == 1, label
        assert _digest(h6) == before, f"{label}: a hub pull since planning still reached the installer, or a backup was made"
        src.write_bytes(kept)


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
    for breaks, why in (
        ("loaded", "loaded OnFailure=(empty)"),
        ("enabled", "timer disabled"),
        ("active", "timer inactive"),
    ):
        if breaks == "loaded":
            (state / "loaded").write_text("[Service]\n")
        else:
            (state / breaks).unlink()
        r = _run(home, hub)
        assert r.returncode == 0 and "== archive: installer run (" in r.stdout and why in r.stdout, (breaks, r.stdout)
        (state / "loaded").write_bytes(loaded)
        (state / "enabled").touch()
        (state / "active").touch()
    # a second OnFailure= unit (a drop-in) beside the alert one still reads as in place
    (state / "extra-onfailure").touch()
    r = _run(home, hub)
    assert r.returncode == 0 and "Nothing to do" in r.stdout, r.stdout


SECTIONS = b"Host vps\n    HostName 10.0.0.1\n    ServerAliveInterval 30\n\nHost github.com\n    HostName github.com\n"


def test_ssh_keepalive_planned_applied_and_verified(tmp_path):
    # the operator's shape: sections only, a github.com block with no keepalive; ssh resolves 0/3 before
    home, hub = _home(tmp_path), _hub(tmp_path)
    cfg = home / SSH_CONFIG
    cfg.write_bytes(SECTIONS)
    cfg.chmod(0o640)  # not the created file's 0600: the write keeps the file's own mode
    assert _resolved(cfg, home) == ("0", "3")
    r = _run(home, hub, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VERIFY FAILED" not in r.stderr
    assert _resolved(cfg, home) == ("15", "4"), cfg.read_text()
    text = cfg.read_bytes()
    assert text.startswith(b"# operator_setup (W-030ac2fe)") and text.endswith(SECTIONS), text  # before the first section
    assert cfg.stat().st_mode & 0o777 == 0o640
    assert any(ln.startswith("cp -p ") and ln.endswith(SSH_CONFIG) for ln in _restore(r.stdout)), r.stdout  # backup restore
    assert _resolved(cfg, home, "vps")[0] == "30", "another host's keepalive changed"
    again = _run(home, hub)
    assert ".ssh/config" not in again.stdout and "Nothing to do" in again.stdout, again.stdout  # in place: a no-op
    # verify() reads the live file: back to no keepalive, it names the ssh step (child Python: the guard here refuses ssh)
    cfg.write_bytes(SECTIONS)
    probe = ("import importlib.util, sys; from pathlib import Path\n"
             "s = importlib.util.spec_from_file_location('operator_setup', sys.argv[1]); m = importlib.util.module_from_spec(s)\n"
             "sys.modules['operator_setup'] = m; s.loader.exec_module(m)\n"
             "print([b.split(':')[0] for b in m.verify(Path(sys.argv[2]))])\n")
    v = subprocess.run([sys.executable, "-c", probe, str(hub / "scripts/sysadmin/operator_setup.py"), str(home)],
                       env=_env(home), capture_output=True, text=True, timeout=60)
    assert v.stdout.strip() == "['ssh']", v.stdout + v.stderr
    # no ~/.ssh at all: created 0700, the config 0600, and the undo line removes the created config
    h2 = _home(tmp_path / "no-ssh-dir")
    shutil.rmtree(h2 / ".ssh")
    r = _run(h2, hub, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (h2 / ".ssh").stat().st_mode & 0o777 == 0o700
    assert (h2 / SSH_CONFIG).stat().st_mode & 0o777 == 0o600
    assert _resolved(h2 / SSH_CONFIG, h2) == ("15", "4")
    assert f'rm -f "$HOME"/{SSH_CONFIG}' in r.stdout, r.stdout
    # a CRLF file gets a CRLF block, and ssh still resolves it
    h3 = _home(tmp_path / "crlf")
    crlf = h3 / SSH_CONFIG
    crlf.write_bytes(b"Host *\r\n    ServerAliveInterval 30\r\n")
    crlf.chmod(0o600)
    r = _run(h3, hub, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    data = crlf.read_bytes()
    assert b"\n" not in data.replace(b"\r\n", b""), data  # no bare LF line ending
    assert _resolved(crlf, h3) == ("15", "4")
    # more shapes, each written and resolved 15/4 by ssh: a file with no section gets the block appended; a
    # leading Match section gets the block before it (after it, its CountMax 9 would win)
    for label, body in (
        ("no-section", b"# my settings\nForwardAgent no"),
        ("match-first", b"Match all\n    ServerAliveCountMax 9\n\nHost x\n    HostName y\n"),
    ):
        h = _home(tmp_path / label)
        c = h / SSH_CONFIG
        c.write_bytes(body)
        c.chmod(0o600)
        r = _run(h, hub, "--apply")
        assert r.returncode == 0, (label, r.stdout + r.stderr)
        assert _resolved(c, h) == ("15", "4"), (label, c.read_text())
        assert body.rstrip(b"\n") in c.read_bytes(), (label, "the file's own lines were not kept")
    # an operator's own tighter keepalive is in place and never overridden — globally or under Host github.com
    for label, body in (
        ("tighter-global", b"ServerAliveInterval 10\nServerAliveCountMax 3\n\nHost vps\n    HostName x\n"),
        ("tighter-host", b"Host github.com\n    ServerAliveInterval 10\n    ServerAliveCountMax 3\n"),
    ):
        h = _home(tmp_path / label)
        c = h / SSH_CONFIG
        c.write_bytes(body)
        c.chmod(0o600)
        r = _run(h, hub)
        assert r.returncode == 0 and "== ssh:" not in r.stdout, (label, r.stdout + r.stderr)
        assert c.read_bytes() == body
    # a looser one is not: an interval over 15 s, or interval x count over 60 s — the block is planned above it
    for label, interval, count in (("interval-30", 30, 1), ("product-90", 10, 9)):
        h = _home(tmp_path / label)
        c = h / SSH_CONFIG
        c.write_bytes(f"Host github.com\n    ServerAliveInterval {interval}\n    ServerAliveCountMax {count}\n".encode())
        c.chmod(0o600)
        r = _run(h, hub)
        assert r.returncode == 0 and "== ssh: .ssh/config" in r.stdout, (label, r.stdout + r.stderr)


def test_ssh_keepalive_refusals_write_nothing(tmp_path):
    hub = _hub(tmp_path)
    inc = tmp_path / "included.conf"
    inc.write_text("Host *\n    ServerAliveInterval 30\n")
    inc.chmod(0o600)
    git_only = tmp_path / "git-user.conf"  # applies to git's own identity only: a bare-host grade would read 15/4
    git_only.write_text("Match user git\n    ServerAliveInterval 30\n")
    git_only.chmod(0o600)
    cases = {
        "match-user-git": (f"Include {git_only}\n\nHost vps\n    HostName x\n".encode(), 0o600,
                           "ServerAliveInterval 30/ServerAliveCountMax 4 for git@github.com"),
        # a value read before any section: no insert can precede it without re-scoping it
        "global": (b"ServerAliveInterval 60\n\nHost github.com\n    User git\n", 0o600, "from a line read before the inserted block"),
        "include": (f"Include {inc}\n\nHost vps\n    HostName x\n".encode(), 0o600, "from a line read before the inserted block"),
        # ssh refuses a group-writable config outright (`-F` skips that check): never "in place", never written
        "writable": (b"Host github.com\n    ServerAliveInterval 15\n    ServerAliveCountMax 4\n", 0o664, "chmod 600"),
    }
    for label, (body, mode, said) in cases.items():
        h = _home(tmp_path / label)
        cfg = h / SSH_CONFIG
        cfg.write_bytes(body)
        cfg.chmod(mode)
        before = _digest(h)
        r = _run(h, hub, "--apply")
        assert r.returncode == 1 and said in r.stderr and "Nothing was written" in r.stderr, (label, r.stdout + r.stderr)
        assert "Traceback" not in r.stderr, (label, r.stderr)
        assert _digest(h) == before, f"{label}: something was written"
        assert not _manager_writes(h), (label, _calls(h))
    # a ~/.ssh the write would fail in, or a config it cannot read: refused at planning, never a traceback mid-apply
    # after the other steps are written
    for label in ("ssh-dir-read-only", "ssh-dir-is-a-file", "ssh-dir-dangling-link", "config-unreadable"):
        h = _home(tmp_path / label)
        d = h / ".ssh"
        if label == "ssh-dir-read-only":
            d.chmod(0o500)
        elif label == "ssh-dir-is-a-file":
            d.rmdir()
            d.write_text("not a dir\n")
        elif label == "ssh-dir-dangling-link":
            d.rmdir()
            d.symlink_to(h / "gone")
        else:
            (d / "config").write_text("Host x\n")
            (d / "config").chmod(0o200)
        before = _digest(h) if label != "config-unreadable" else None
        r = _run(h, hub, "--apply")
        after = _digest(h) if before is not None else None
        if label == "ssh-dir-read-only":
            d.chmod(0o700)  # after the digest, so pytest can clean the tree up
        assert r.returncode == 1 and "Nothing was written" in r.stderr and "Traceback" not in r.stderr, (label, r.stderr)
        assert "wrote " not in r.stdout, (label, r.stdout)
        assert after == before, f"{label}: something was written"
    # $HOME is not the passwd home ssh reads, and no override (only "1" overrides): refused
    for value in ("", "0"):
        h = _home(tmp_path / f"home-mismatch-{value or 'empty'}")
        before = _digest(h)
        r = _run(h, hub, OPERATOR_SETUP_SSH_HOME=value)
        assert r.returncode == 1 and "passwd home" in r.stderr, (value, r.stdout + r.stderr)
        assert _digest(h) == before


def test_ssh_config_owned_by_another_user_refused(tmp_path, monkeypatch):
    # ssh refuses a config another (non-root) user owns, so it is never "in place"; the owner is read before any
    # ssh runs, so this in-process run (where the fleet guard refuses ssh) reaches it by giving the process another uid
    home, hub = _home(tmp_path), _hub(tmp_path)
    cfg = home / SSH_CONFIG
    cfg.write_bytes(b"Host github.com\n    ServerAliveInterval 15\n    ServerAliveCountMax 4\n")
    cfg.chmod(0o600)
    spec = importlib.util.spec_from_file_location("operator_setup", hub / "scripts" / "sysadmin" / "operator_setup.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "operator_setup", mod)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("OPERATOR_SETUP_SSH_HOME", "1")
    monkeypatch.setattr(mod.os, "getuid", lambda: cfg.stat().st_uid + 1)
    with pytest.raises(mod.PlanError, match="owned by another user"):
        mod.plan_ssh(home)
