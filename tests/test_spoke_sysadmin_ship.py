"""Spokes receive every repo file their sysadmin cron jobs read (W-922fbee1).

Every host installs the cron set in ``scripts/bootstrap/templates/sysadmin-cron.template``; its jobs read a few
repo files outside ``scripts/sysadmin/`` (the audit scripts and their checklists). The two paths that put files on a
spoke — bootstrap step 14 and ``scripts/sync-vps-sysadmin.sh``'s spoke loop — must ship them. The required set is
derived from the cron targets, never listed by hand, and both entry points are driven with ``ssh``/``rsync``/``scp``
stubbed, so nothing leaves the machine.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / "scripts" / "bootstrap"
CRON = BOOT / "templates" / "sysadmin-cron.template"
SPOKES = ("vps2", "vps3")
_REF = re.compile(r"(?:\$PROJECT_DIR|\$\{PROJECT_DIR\}|/opt/fabrik)/([A-Za-z0-9_./-]+)")
_SYNC = ROOT / "scripts" / "sync-vps-sysadmin.sh"


def _required(cron_text: str | None = None, callees: tuple[str, ...] | None = None) -> set[str]:
    """Tracked repo files outside scripts/sysadmin/ that a cron target, or what it calls, reads (host state such as
    logs/ and .env* drops out because git does not track it). The callees are vps_script_drift.TIER1_DEPENDENCIES,
    the executed closure that module keeps; the scan matches $PROJECT_DIR/ and /opt/fabrik/ references only, so a
    callee reading a repo file through Path(__file__).parents[N] would escape it."""
    if callees is None:
        spec = importlib.util.spec_from_file_location(
            "vps_script_drift", ROOT / "scripts/sysadmin/vps_script_drift.py"
        )
        drift = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(drift)
        callees = drift.TIER1_DEPENDENCIES
    text = CRON.read_text() if cron_text is None else cron_text
    targets = set(re.findall(r"/opt/fabrik/scripts/sysadmin/([^\s>|;]+)", text))
    targets |= {d.removeprefix("scripts/sysadmin/") for d in callees}
    tracked = set(
        subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
    )
    need: set[str] = set()
    for t in targets:
        for ref in _REF.findall((ROOT / "scripts" / "sysadmin" / t).read_text(errors="replace")):
            ref = ref.rstrip(".")
            if not ref.startswith("scripts/sysadmin") and ref in tracked:
                need.add(ref)
    return need


def _function(path: Path, name: str) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(f"{name}()"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
    return "\n".join(lines[start : end + 1])


def test_required_set_is_derived_from_the_cron_targets():
    assert _required() == {
        "scripts/audit/03-security.sh",
        "scripts/audit/06-backup.sh",
        "docs/infrastructure/audit-prompts/03-security-hardening.md",
        "docs/infrastructure/audit-prompts/06-backup-disaster-recovery.md",
    }


def test_required_set_follows_the_cron_template_it_is_given():
    """A template naming only the weekly security job needs only that job's two files: the set is derived."""
    one_job = (
        "30 8 * * 1 root /opt/fabrik/scripts/sysadmin/weekly-security.sh >> /var/log/x.log 2>&1\n"
    )
    assert _required(cron_text=one_job, callees=()) == {
        "scripts/audit/03-security.sh",
        "docs/infrastructure/audit-prompts/03-security-hardening.md",
    }


def _run_sync(tmp_path, fail_host: str = "") -> tuple[list[str], subprocess.CompletedProcess]:
    """Run the sync script with ssh and rsync stubbed: every call is logged; a call naming ``fail_host`` exits 255."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    for tool in ("rsync", "ssh"):
        stub = bin_dir / tool
        stub.write_text(
            f'#!/bin/sh\nprintf "%s\\n" "{tool} $*" >> "{log}"\n'
            + (f'case "$*" in *{fail_host}*) exit 255;; esac\n' if fail_host else "")
            + "exit 0\n"
        )
        stub.chmod(0o755)
    run = subprocess.run(
        ["bash", str(_SYNC)],
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "FABRIK_ROOT": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return log.read_text().splitlines(), run


def _ships(calls: list[str], spoke: str, d: str) -> bool:
    """An rsync that recreates ``d/`` under the spoke's /opt/fabrik, either -R into the root or straight to the dir."""
    for c in calls:
        if not c.startswith("rsync ") or f" {d}/ " not in f"{c} ":
            continue
        if f"{spoke}:/opt/fabrik/{d}/" in c or (" -R " in f"{c} " and f"{spoke}:/opt/fabrik/" in c):
            # -R without --no-implied-dirs copies this checkout's modes onto the spoke's existing parents
            if " -R " in f"{c} ":
                assert " --no-implied-dirs " in f"{c} ", c
            assert " --delete " in f"{c} ", c
            return True
    return False


def test_sync_script_ships_what_spoke_cron_reads(tmp_path):
    calls, run = _run_sync(tmp_path)
    assert run.returncode == 0, run.stderr
    for spoke in SPOKES:
        for rel in sorted(_required()):
            d = rel.rsplit("/", 1)[0]
            assert _ships(calls, spoke, d), f"{rel}: no rsync of {d}/ to {spoke}\n" + "\n".join(
                calls
            )


def test_an_unreachable_spoke_does_not_stop_the_others(tmp_path):
    calls, run = _run_sync(tmp_path, fail_host="vps2")
    assert run.returncode == 0, run.stderr
    assert "vps2 audit sync failed" in run.stdout, run.stdout
    for rel in sorted(_required()):
        assert _ships(calls, "vps3", rel.rsplit("/", 1)[0]), "\n".join(calls)
    assert any(c.startswith("rsync ") and "vps3:/tmp/fabrik-autoheal" in c for c in calls), (
        "autoheal loop never ran"
    )


def _step_14(tmp_path: Path) -> tuple[list[str], Path]:
    """Run step 14 with ``remote`` and ``scp`` stubbed: the programs it sends to the spoke, in order, and the directory
    holding what it scp'd (the step's own trap deletes its staging dir, so the stub copies at call time)."""
    staged = tmp_path / "staged"
    staged.mkdir()
    remote_log = tmp_path / "remote"
    script = "\n".join(
        [
            "log() { :; }; ok() { :; }; warn() { :; }; err() { :; }; dim() { :; }",
            "DRY_RUN=false; SPOKE_NAME=vps2; SPOKE_MESH_IP=10.99.0.2; FABRIK_WG_HUB_IP=10.99.0.1",
            f"SCRIPT_DIR={BOOT}; EFFECTIVE_REMOTE=spoke",
            f"SYSADMIN_SOURCE={ROOT}/scripts/sysadmin/",
            f"AUDIT_SOURCE={ROOT}/scripts/audit/",
            f"AUDIT_PROMPTS_SOURCE={ROOT}/docs/infrastructure/audit-prompts/",
            f"remote() {{ printf '%s\\0' \"$*\" >> {remote_log}; return 0; }}",
            # scp's last argument is the destination; copy every source into the capture dir as it would land in /tmp
            f'scp() {{ local a=(); for x in "$@"; do case "$x" in -*) ;; *) a+=("$x");; esac; done; '
            f'unset "a[${{#a[@]}}-1]"; cp -r "${{a[@]}}" {staged}/; printf "SCP\\0" >> {remote_log}; }}',
            _function(BOOT / "bootstrap-vps.sh", "step_14_install_sysadmin_pack"),
            "step_14_install_sysadmin_pack",
        ]
    )
    # the program goes on stdin, as tests/test_bootstrap_scripts_sshd.py does: conftest's fleet guard reads a
    # `-c` string's command names, and here `scp` is a shell function and `rsync` copies between local directories
    subprocess.run(
        ["bash", "-s"],
        input=script.encode(),
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        check=True,
        timeout=60,
    )
    return [c for c in remote_log.read_text().split("\0") if c], staged


def test_bootstrap_step_14_ships_what_spoke_cron_reads(tmp_path):
    calls, staged = _step_14(tmp_path)
    scp_at = calls.index("SCP")
    # scp merges into an existing /tmp/<name>; the staging names are cleared on the spoke before the copy
    assert any(
        "rm -rf" in c and "/tmp/audit " in f"{c} " and "/tmp/audit-prompts" in c
        for c in calls[:scp_at]
    ), calls[:scp_at]
    installs = [c for c in calls if c != "SCP"]
    for (
        program
    ) in installs:  # every program step 14 sends must at least parse (bootstrap pack Rule 2)
        parsed = subprocess.run(["bash", "-n"], input=program, capture_output=True, text=True)
        assert parsed.returncode == 0, f"{parsed.stderr}\n{program}"
    install = next(c for c in installs if "/tmp/sysadmin/" in c)
    # the directories the install creates under /opt/fabrik/docs end up owned by the sync user
    assert "chown ozgur:ozgur /opt/fabrik/docs /opt/fabrik/docs/infrastructure" in install, install
    for rel in sorted(_required()):
        d, name = rel.rsplit("/", 1)
        landed = [p for p in staged.rglob(name) if p.read_bytes() == (ROOT / rel).read_bytes()]
        assert landed, f"{rel}: not staged (staged: {sorted(p.name for p in staged.rglob('*'))})"
        rel_staged = landed[0].relative_to(staged).parent.as_posix()
        assert f"rsync -a --delete /tmp/{rel_staged}/ /opt/fabrik/{d}/" in install, (
            f"{rel}: staged as /tmp/{rel_staged}/ but never installed into /opt/fabrik/{d}/"
        )
        assert "mkdir -p" in install and f"/opt/fabrik/{d}" in install.split("mkdir -p", 1)[1]
        assert f"/opt/fabrik/{d}" in install.split("chown -R ozgur:ozgur", 1)[1].split("&&")[0], (
            f"/opt/fabrik/{d} is created but never chowned to the sync user"
        )


def test_a_failed_install_rsync_fails_step_14s_remote_command(tmp_path):
    """The install program is one `&&` chain; a failing `sudo rsync` must make it exit non-zero, never be swallowed by
    the `|| true` that keeps a missing-glob chmod quiet."""
    installs = [c for c in _step_14(tmp_path)[0] if c != "SCP"]
    program = next(c for c in installs if "/tmp/sysadmin/" in c)
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "sudo").write_text('#!/bin/sh\ncase "$1" in rsync) exit 23;; esac\nexit 0\n')
    (shim / "rm").write_text("#!/bin/sh\nexit 0\n")
    for tool in ("sudo", "rm"):
        (shim / tool).chmod(0o755)
    run = subprocess.run(
        ["bash", "-s"],
        input=program,
        env={"PATH": f"{shim}:/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode != 0, "a failed rsync was swallowed by the install chain"
