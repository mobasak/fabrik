"""Is the kaizen_collect_v2 residue failure PRE-EXISTING? Restore the two touched scripts to HEAD
on a backed-up tree, run the two tests, then restore my versions and assert byte-identity."""

import pathlib
import shutil
import subprocess

FILES = [pathlib.Path("scripts/command_run.py"), pathlib.Path("scripts/sysadmin/dispatch_headroom.py")]
BAK = {p: pathlib.Path(".scratch-T10") / (p.name + ".mine") for p in FILES}
for p, b in BAK.items():
    shutil.copy2(p, b)
    assert b.read_bytes() == p.read_bytes()
try:
    for p in FILES:
        head = subprocess.run(
            ["git", "show", f"HEAD:{p}"], capture_output=True, text=True, check=True
        ).stdout
        p.write_text(head)
        assert "--confirmed" not in p.read_text() or p.name != "command_run.py"
    for pc in pathlib.Path(".").rglob("__pycache__"):
        shutil.rmtree(pc, ignore_errors=True)
    r = subprocess.run(
        [
            "/opt/fabrik/.venv/bin/python",
            "-m",
            "pytest",
            "tests/test_kaizen_collect_v2.py",
            "-q",
            "-k",
            "tmp_residue or replace_failure_leaves",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
    )
    print("AT HEAD (my diff reverted):", r.stdout.strip().splitlines()[-1])
finally:
    for p, b in BAK.items():
        shutil.copy2(b, p)
        assert p.read_bytes() == b.read_bytes(), f"RESTORE FAILED {p}"
    for pc in pathlib.Path(".").rglob("__pycache__"):
        shutil.rmtree(pc, ignore_errors=True)
    print("restored my versions")
