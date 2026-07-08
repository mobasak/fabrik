"""Behavior contract for scripts/enforcement/check_subagent_flywheel.py (advisory flywheel gate).

The check reconciles the pool LEDGER against local RECEIPTS (a receipt is written by
record_agent_run only on a confirmed DB write) and surfaces pool runs that ran but were never
scored+recorded (ledger − receipts). It is ADVISORY: it must ALWAYS exit 0 (never block the gate)
and put any finding on stdout, which final_gate's advisory wrapper preserves as a WARN.
"""

import json
import subprocess
import sys
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_subagent_flywheel.py"


def _run(ledger_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK), str(ledger_path)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )


def _write_jsonl(p: Path, rows: list[dict]) -> None:
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_unreceipted_pool_run_is_flagged(tmp_path):
    # Given a ledger with one run whose agent_id has no matching receipt
    ledger = tmp_path / "ledger.jsonl"
    _write_jsonl(ledger, [{"agent_id": "a1", "model": "minimax/minimax-m3", "task_type": "review"}])
    # (no receipts.jsonl co-located → a1 is unrecorded)
    r = _run(ledger)
    # Then it is surfaced advisory (exit 0, never blocks) and names the run + why
    assert r.returncode == 0, r.stderr
    assert "a1" in r.stdout
    assert "never" in r.stdout.lower() and "record" in r.stdout.lower()


def test_fully_receipted_ledger_is_clean(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    receipts = tmp_path / "receipts.jsonl"
    _write_jsonl(ledger, [{"agent_id": "a1", "model": "x", "task_type": "review"}])
    _write_jsonl(receipts, [{"agent_id": "a1", "recorded": True, "project": "p"}])
    r = _run(ledger)
    assert r.returncode == 0, r.stderr
    assert "a1" not in r.stdout  # every run receipted → nothing flagged


def test_no_ledger_is_clean(tmp_path):
    # native-only work / no pool use → no ledger → silent pass
    r = _run(tmp_path / "does-not-exist.jsonl")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""


def test_corrupt_ledger_is_advisory_safe(tmp_path):
    # An EXISTING but unreadable/bad-encoding ledger makes read_text raise (UnicodeDecodeError);
    # the advisory check MUST still exit 0 (never a non-zero exit that run_optional_check would
    # treat as a blocking gate failure) and say it skipped.
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81\n")
    r = _run(ledger)
    assert r.returncode == 0, r.stderr
    assert "skipping" in r.stdout.lower()
