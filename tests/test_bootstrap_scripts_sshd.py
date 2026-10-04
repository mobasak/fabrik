"""The three bootstrap scripts harden sshd the way core/90-bootstrap-scripts.md Rule 1 prescribes (W-1c322b9e).

sshd keeps the FIRST value it reads, and Ubuntu reads ``/etc/ssh/sshd_config.d/*.conf`` before the main file in
lexical order, so a cloud image's ``50-cloud-init.conf`` saying ``PasswordAuthentication yes`` beat both the old
``99-fabrik-hardening.conf`` and the ``sed`` on the main file. These tests run each script's ``step_01_harden_ssh``
with ``remote`` stubbed, so they read the remote programs the script would actually send, then execute the
effective-value assertion against a fake ``sshd -T``. A static grep would pass a script that writes the right file
name and never checks the result; executing the assertion is what catches that.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / "scripts" / "bootstrap"
SCRIPTS = {n: BOOT / f"bootstrap-{n}.sh" for n in ("vps", "hub", "spoke-restore")}
VPS = SCRIPTS["vps"]
HUB = SCRIPTS["hub"]


def _function(path: Path, name: str) -> str:
    """The text of shell function ``name`` (its definition line through the first line that is exactly ``}``)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(f"{name}()"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
    return "\n".join(lines[start : end + 1])


def _run_step_01(path: Path, fail_at: int = 0) -> tuple[list[str], int]:
    """Run ``step_01_harden_ssh`` with ``remote`` stubbed: every command it would send, in order, and the
    step's exit status. The stub's ``fail_at``-th call (1-based) returns 1, as a failed ssh would."""
    script = "\n".join(
        [
            "log() { :; }; ok() { :; }; warn() { :; }; err() { :; }; dim() { :; }; elapsed() { echo 0; }",
            f"DRY_RUN=false; FABRIK_SUDOER_USER=ozgur; _n=0; _fail={fail_at}",
            'remote() { _n=$((_n+1)); printf \'%s\\0\' "$*"; [ "$_n" -ne "$_fail" ]; }',
            _function(path, "step_01_harden_ssh"),
            "step_01_harden_ssh; printf 'rc=%s' \"$?\"",
        ]
    )
    out = subprocess.run(["bash", "-c", script], capture_output=True, check=False).stdout.decode()
    *programs, tail = out.split("\0")
    return programs, int(tail.removeprefix("rc="))


def _remote_programs(path: Path) -> list[str]:
    return _run_step_01(path)[0]


def _fake_bin(tmp: Path, sshd_output: str = "", sshd_config: Path | None = None) -> dict[str, str]:
    """A PATH whose ``sudo`` runs its arguments (reading ``sshd_config`` in place of the real
    ``/etc/ssh/sshd_config``) and whose ``sshd -T`` prints ``sshd_output``."""
    bin_dir = tmp / "bin"
    bin_dir.mkdir(exist_ok=True)
    swap = sshd_config or tmp / "absent"
    (bin_dir / "sudo").write_text(
        "#!/bin/bash\nargs=()\n"
        f'for a in "$@"; do [ "$a" = /etc/ssh/sshd_config ] && a="{swap}"; args+=("$a"); done\n'
        'exec "${args[@]}"\n'
    )
    (bin_dir / "sshd").write_text(f"#!/bin/sh\ncat <<'EOF'\n{sshd_output}\nEOF\n")
    for f in bin_dir.iterdir():
        f.chmod(f.stat().st_mode | stat.S_IXUSR)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_hardening_lands_in_a_low_numbered_drop_in(name: str) -> None:
    programs = _remote_programs(SCRIPTS[name])
    joined = "\n".join(programs)
    assert "/etc/ssh/sshd_config.d/01-fabrik-hardening.conf" in joined, name
    assert re.search(r"rm -f /etc/ssh/sshd_config\.d/99-fabrik-hardening\.conf", joined), (
        f"{name}: an old 99- drop-in stays behind and still documents the wrong layer"
    )
    for line in ("PermitRootLogin no", "PasswordAuthentication no"):
        assert line in joined, (name, line)
    for program in programs:
        # on stdin: `bash -n` only parses, and conftest's fleet guard reads a `-c` string's command names
        parsed = subprocess.run(["bash", "-n"], input=program, capture_output=True, text=True)
        assert parsed.returncode == 0, (
            f"{name}: a remote program does not parse:\n{program}\n{parsed.stderr}"
        )


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_effective_value_is_asserted_before_reload(name: str, tmp_path: Path) -> None:
    programs = _remote_programs(SCRIPTS[name])
    checks = [i for i, p in enumerate(programs) if "sshd -T" in p]
    reloads = [i for i, p in enumerate(programs) if "systemctl reload" in p]
    assert checks and reloads and checks[0] < reloads[0], (
        f"{name}: no sshd -T assertion before the reload"
    )
    check = programs[checks[0]]

    # sshd -T prints lowercase keywords; keywords are case-insensitive, so a mixed-case line still counts
    for good in (
        "port 22\npermitrootlogin no\npasswordauthentication no\npubkeyauthentication yes",
        "PermitRootLogin no\nPasswordAuthentication no",
    ):
        rc = subprocess.run(["bash", "-c", check], env=_fake_bin(tmp_path, good)).returncode
        assert rc == 0, f"{name}: the assertion rejected a hardened config {good!r}"

    # a cloud drop-in that sorts first wins: the effective value is still yes, and the step must fail;
    # the last two keep the anchors honest (a commented line, and a value that merely starts with "no")
    for bad in (
        "permitrootlogin no\npasswordauthentication yes",
        "permitrootlogin prohibit-password\npasswordauthentication no",
        "permitrootlogin no",
        "#passwordauthentication no\npasswordauthentication yes\npermitrootlogin no",
        "permitrootlogin no\npasswordauthentication nonsense",
    ):
        rc = subprocess.run(
            ["bash", "-c", check], env=_fake_bin(tmp_path, bad), capture_output=True
        ).returncode
        assert rc != 0, f"{name}: the assertion accepted an effective config of {bad!r}"


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_include_probe_refuses_a_config_that_would_ignore_the_drop_in(
    name: str, tmp_path: Path
) -> None:
    programs = _remote_programs(SCRIPTS[name])
    probe = programs[0]
    assert "Include" in probe and "01-fabrik-hardening" not in probe, (
        f"{name}: the Include probe is not first"
    )
    cfg = tmp_path / "sshd_config"
    for text, want in (
        ("Include /etc/ssh/sshd_config.d/*.conf\nPort 22\n", 0),
        ("include   /etc/ssh/sshd_config.d/*.conf\n", 0),  # keywords are case-insensitive
        ("Port 22\nPermitRootLogin no\n", 1),
        ("#Include /etc/ssh/sshd_config.d/*.conf\n", 1),
    ):
        cfg.write_text(text)
        rc = subprocess.run(
            ["bash", "-c", probe], env=_fake_bin(tmp_path, sshd_config=cfg)
        ).returncode
        assert (rc == 0) == (want == 0), f"{name}: Include probe rc {rc} for {text!r}"


@pytest.mark.parametrize("name", sorted(SCRIPTS))
@pytest.mark.parametrize("fail_at", [1, 2, 3, 4])
def test_any_failed_call_stops_the_step(name: str, fail_at: int) -> None:
    """Include probe, write, assertion, reload: a failure at any of them fails the step and sends nothing more."""
    programs, rc = _run_step_01(SCRIPTS[name], fail_at)
    assert rc != 0, f"{name}: step_01 succeeded although remote call {fail_at} failed"
    assert len(programs) == fail_at, f"{name}: step_01 kept sending after call {fail_at} failed"
    _, ok_rc = _run_step_01(SCRIPTS[name])
    assert ok_rc == 0


def test_verify_reads_the_effective_config() -> None:
    body = _function(VPS, "run_verify")
    assert "sshd -T" in body
    assert not re.search(r"grep[^\n]*/etc/ssh/sshd_config['\"]", body), (
        "--verify still greps the main file, which cannot see a drop-in override"
    )


def test_spoke_installs_claude_with_the_native_installer() -> None:
    text = VPS.read_text(encoding="utf-8")
    assert "npm install -g" not in text and "@anthropic-ai/claude-code" not in text
    assert "curl -fsSL https://claude.ai/install.sh | bash" in text
    # a failed download pipes nothing into bash, which exits 0: only the test -x keeps the symlink honest
    for path in (VPS, HUB):
        assert re.search(
            r'test -x "\$HOME/\.local/bin/claude" &&\s*\\?\s*sudo ln -sfn "\$HOME/\.local/bin/claude" /usr/local/bin/claude',
            path.read_text(encoding="utf-8"),
        ), f"{path.name}: the /usr/local/bin/claude symlink is missing or not guarded by test -x"
    assert re.search(r"remote 'claude --version' \\\n\s*\|\| \{ err [^}]*return 1; \}", text), (
        "step 14a must fail when claude does not run — the sysadmin bot needs it"
    )
    assert "claude setup-token" in text, (
        "the closing message still sends a headless box to an interactive login"
    )
    hub_header = "\n".join(HUB.read_text(encoding="utf-8").splitlines()[:80])
    assert "npm install -g" not in hub_header, (
        "bootstrap-hub.sh's header still describes the npm install"
    )


def test_fail2ban_figures_and_comments() -> None:
    for name, path in SCRIPTS.items():
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\b3[- ]failures?\b", text), (
            f"{name} still cites a three-failure threshold"
        )
    assert "sshd reads /etc/ssh/sshd_config.d/*.conf last" not in HUB.read_text(encoding="utf-8")
    assert "dashes" not in VPS.read_text(encoding="utf-8").splitlines()[102], (
        "bootstrap-vps.sh line 103 describes a spoke-name regex that allows dashes; line 104 does not"
    )


@pytest.mark.parametrize(
    ("flags", "want"),
    [
        ("false false false false", ""),
        ("false false true true", "--skip-mesh --skip-dns "),
        ("true false false false", "--dry-run "),
        ("false true false false", "--verify "),
        ("true true true true", "--dry-run --verify --skip-mesh --skip-dns "),
    ],
)
def test_rerun_hint_keeps_the_operators_flags(flags: str, want: str) -> None:
    """``preflight`` runs after the top-level parser has shifted every argument away, so ``$@`` there is
    empty. The exact string matters: it is spliced in front of ``ozgur@<host>`` with no separator."""
    assert '"$@"' not in _function(VPS, "preflight")
    dry, verify, mesh, dns = flags.split()
    script = "\n".join(
        [
            f"DRY_RUN={dry}; VERIFY={verify}; SKIP_MESH={mesh}; SKIP_DNS={dns}",
            _function(VPS, "_rerun_flags"),
            'printf "[%s]" "$(_rerun_flags)"',
        ]
    )
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout
    assert out == f"[{want}]"
    assert 'flags="$(_rerun_flags)"' in _function(VPS, "preflight")
