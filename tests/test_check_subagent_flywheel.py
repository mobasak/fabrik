"""Behavior contract for scripts/enforcement/check_subagent_flywheel.py (advisory flywheel gate).

The check reconciles the pool LEDGER against local RECEIPTS (a receipt is written by
record_agent_run only on a confirmed DB write) and surfaces pool runs that ran but were never
scored+recorded (ledger − receipts). It is ADVISORY: it must ALWAYS exit 0 (never block the gate)
and put any finding on stdout, which final_gate's advisory wrapper preserves as a WARN.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_subagent_flywheel.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_subagent_flywheel_mod", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def test_no_ledger_never_blocks_nor_false_flags(tmp_path):
    # native-only work / no pool use → no ledger → never blocks the gate, and never a false
    # "ran but was never recorded" flag (that message requires an actual ledger run). A big changed
    # surface MAY trigger the separate all-native advisory — surface-controlled coverage below.
    r = _run(tmp_path / "does-not-exist.jsonl")
    assert r.returncode == 0, r.stderr
    assert "never" not in r.stdout.lower()  # the unrecorded-run flag says "never" — must not false-fire


def test_all_native_gap_warns_on_big_surface(tmp_path, monkeypatch, capsys):
    # A substantial changed surface (> threshold) with NO pool ledger → advisory nudge that the pool
    # breadth layer was likely skipped (the all-native miss the ledger↔receipt reconciliation can't see).
    mod = _load_module()
    monkeypatch.setattr(mod, "_changed_file_count", lambda: mod._REVIEW_SURFACE_THRESHOLD + 17)
    rc = mod.check(tmp_path / "no-ledger.jsonl")
    out = capsys.readouterr().out
    assert rc == 0  # advisory: never blocks
    assert "ZERO pool subagent runs" in out
    assert "pool breadth layer" in out.lower()


def test_all_native_gap_quiet_on_small_surface(tmp_path, monkeypatch, capsys):
    # A small changed surface with no ledger is normal native-only work → no nudge, fully silent.
    mod = _load_module()
    monkeypatch.setattr(mod, "_changed_file_count", lambda: 2)
    rc = mod.check(tmp_path / "no-ledger.jsonl")
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == ""


def test_corrupt_ledger_is_advisory_safe(tmp_path):
    # An EXISTING but unreadable/bad-encoding ledger makes read_text raise (UnicodeDecodeError);
    # the advisory check MUST still exit 0 (never a non-zero exit that run_optional_check would
    # treat as a blocking gate failure) and say it skipped.
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81\n")
    r = _run(ledger)
    assert r.returncode == 0, r.stderr
    assert "skipping" in r.stdout.lower()
