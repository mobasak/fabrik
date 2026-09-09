"""Red-on-revert proof: each mutation is applied to a file whose pristine bytes are already on
disk in a .bak, asserted present, the named test run (expected RED), then restored and asserted."""

import pathlib
import shutil
import subprocess
import sys

CR = pathlib.Path("scripts/command_run.py")
DH = pathlib.Path("scripts/sysadmin/dispatch_headroom.py")
BAK = {p: pathlib.Path(".scratch-T10") / (p.name + ".bak") for p in (CR, DH)}
for p, b in BAK.items():
    shutil.copy2(p, b)  # backup BEFORE any mutation
    assert b.read_bytes() == p.read_bytes()

MUT = [
    (
        CR,
        'counter = int(last.get("findings", 0)) if last_confirmed is None else last_confirmed',
        'counter = int(last.get("findings", 0))',
        "test_a_last_round_stating_confirmed_ignores_zero_findings",
    ),
    (
        CR,
        "        bool(classes)\n        and not open_c\n        and counter == 0\n"
        '        and bool(last.get("swept"))  # the record\'s key; the event stream says'
        " classes_swept\n",
        "        counter == 0\n",
        "test_confirmed_zero_without_a_swept_class_is_not_terminal",
    ),
    (
        CR,
        "if rounds and all(_confirmed(r) is not None for r in rounds):",
        "if rounds and any(_confirmed(r) is not None for r in rounds):",
        "test_one_unstated_round_makes_the_advisory_read_the_findings_series or "
        "test_the_feedback_trend_falls_back_to_findings_and_the_row_records_the_gap",
    ),
    (
        CR,
        "            and any(_confirmed(r) is not None for r in rounds)\n",
        "            and True\n",
        "test_the_warning_never_fires_on_a_record_that_never_stated_confirmed",
    ),
    (
        CR,
        '"confirmed": [_confirmed(r) for r in rec.get("rounds") or []],',
        '"confirmed": [int(r.get("confirmed") or 0) for r in rec.get("rounds") or []],',
        "test_the_feedback_trend_falls_back_to_findings_and_the_row_records_the_gap",
    ),
    (
        CR,
        "                if last_confirmed is not None\n",
        "                if True\n",
        "test_findings_zero_still_closes_a_record_that_never_stated_confirmed",
    ),
    (
        DH,
        '+ ("surface with a mechanical angle" if haiku else "grounding surface")',
        '+ "grounding surface"',
        "test_the_wording_names_the_mechanical_angle_never_the_retired_phrasing",
    ),
]

rc = 0
try:
    for path, old, new, k in MUT:
        src = BAK[path].read_text()
        assert src.count(old) == 1, (path, old[:50], src.count(old))
        path.write_text(src.replace(old, new))
        assert new in path.read_text() and old not in path.read_text(), "mutation not on disk"
        for pc in pathlib.Path(".").rglob("__pycache__"):
            shutil.rmtree(pc, ignore_errors=True)
        tf = (
            "tests/test_command_run.py"
            if path is CR
            else "tests/sysadmin/test_dispatch_headroom.py"
        )
        r = subprocess.run(
            [
                "/opt/fabrik/.venv/bin/python",
                "-m",
                "pytest",
                tf,
                "-q",
                "-k",
                k,
                "--no-header",
                "-p",
                "no:cacheprovider",
            ],
            capture_output=True,
            text=True,
        )
        tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
        status = "RED (good)" if r.returncode != 0 else "GREEN - MUTANT SURVIVED"
        if r.returncode == 0:
            rc = 1
        print(f"[{status}] {old[:52]!r} -> {k[:60]}: {tail}")
finally:
    for p, b in BAK.items():
        shutil.copy2(b, p)
        assert p.read_bytes() == b.read_bytes(), f"RESTORE FAILED {p}"
    for pc in pathlib.Path(".").rglob("__pycache__"):
        shutil.rmtree(pc, ignore_errors=True)
    print("restored:", ", ".join(str(p) for p in BAK))
sys.exit(rc)
