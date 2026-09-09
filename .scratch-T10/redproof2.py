"""Red-on-revert proof for review round 1. Each mutation reverts one round-1 fix on a file whose
pristine bytes are already on disk in a .bak (written BEFORE the first mutation), asserts the
mutation landed, runs the named test expecting RED, then restores and asserts byte-identity."""

import pathlib
import shutil
import subprocess
import sys

CR = pathlib.Path("scripts/command_run.py")
HY = pathlib.Path("scripts/enforcement/check_review_hygiene.py")
BAK = {p: pathlib.Path(".scratch-T10") / (p.name + ".r1bak") for p in (CR, HY)}
for p, b in BAK.items():
    shutil.copy2(p, b)
    assert b.read_bytes() == p.read_bytes()

T_CR = "tests/test_command_run.py"
T_HY = "tests/enforcement/test_check_review_hygiene.py"

MUT = [
    # 1 — the sticky exit counter: revert to the fail-open (fall back to `findings`)
    (
        CR,
        T_CR,
        "    terminal = swept_all and not lapsed and counter == 0",
        "    terminal = swept_all and counter == 0",
        "test_an_adopted_record_cannot_close_on_findings_when_confirmed_is_omitted or "
        "test_the_sticky_exit_counter_over_every_cell_of_findings_by_prior_adoption",
    ),
    # 1b — the nudge gated on findings > 0 again (warning and TERMINAL mutually exclusive)
    (
        CR,
        T_CR,
        "        if args.confirmed is None and _adopted_at is not None:",
        "        if args.confirmed is None and _adopted_at is not None and args.findings > 0:",
        "test_round_warns_when_confirmed_is_absent_after_an_earlier_round_stated_it",
    ),
    # 2 — the advisory stops naming the series it read
    (
        CR,
        T_CR,
        "        _trend_series(rounds), str(rec.get(\"command\") or \"\"), _trend_label(rounds)",
        "        _trend_series(rounds), str(rec.get(\"command\") or \"\")",
        "test_the_oscillation_advisory_names_the_series_it_printed",
    ),
    # 3a — a negative confirmed accepted again
    (
        CR,
        T_CR,
        "        if args.confirmed is not None and args.confirmed < 0:",
        "        if False:",
        "test_a_negative_confirmed_is_refused",
    ),
    # 3b — confirmed > findings accepted again
    (
        CR,
        T_CR,
        "        if args.confirmed is not None and args.confirmed > args.findings:",
        "        if False and args.confirmed > args.findings:",
        "test_confirmed_greater_than_findings_is_refused",
    ),
    # 6 — the repeatable help text
    (
        HY,
        T_HY,
        '"--surface", action="append", default=[], help="file or dir on the surface (repeatable)"',
        '"--surface", action="append", default=[], help="file or dir on the surface"',
        "test_every_repeatable_flag_says_so_in_its_help",
    ),
]

rc = 0
try:
    for path, tf, old, new, k in MUT:
        src = BAK[path].read_text()
        assert src.count(old) == 1, (str(path), old[:60], src.count(old))
        path.write_text(src.replace(old, new))
        txt = path.read_text()
        assert new in txt and old not in txt, "mutation not on disk"
        for pc in pathlib.Path(".").rglob("__pycache__"):
            shutil.rmtree(pc, ignore_errors=True)
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
        print(f"[{status}] {old[:48]!r} -> {k[:58]}: {tail}")
finally:
    for p, b in BAK.items():
        shutil.copy2(b, p)
        assert p.read_bytes() == b.read_bytes(), f"RESTORE FAILED {p}"
    for pc in pathlib.Path(".").rglob("__pycache__"):
        shutil.rmtree(pc, ignore_errors=True)
    print("restored:", ", ".join(str(p) for p in BAK))
sys.exit(rc)
