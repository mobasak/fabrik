"""Behavior contract for scripts/enforcement/check_subagent_flywheel.py.

Two layers:
- LAYER 1 (BLOCKING, "pool-or-declare"): a substantial CODE change with ZERO in-cycle pool runs and no
  NO-POOL declaration → exit 1. Fail-safe: any git/parse/exception trouble → exit 0 (never a false block).
- LAYER 2 (ADVISORY): reconciles the ledger vs receipts, WARNs on unrecorded pool runs, never blocks.

Layer-1 tests import the module and monkeypatch the git-facing helpers so the verdict is deterministic
(the raw script would read the REAL repo's git state). Layer-2 tests run the script via subprocess with
FABRIK_NO_POOL set so Layer 1 always passes and only the advisory is exercised.
"""

import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_subagent_flywheel.py"


def _load():
    spec = importlib.util.spec_from_file_location("csf_mod", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


def _write_ledger(p: Path, rows: list[dict]) -> None:
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


# ─────────────────────────── LAYER 1 — blocking pool-or-declare ───────────────────────────

def test_block_big_code_no_pool_no_declare(tmp_path, monkeypatch):
    # substantial code change, zero in-cycle pool runs, no declaration → BLOCK (exit 1)
    mod = _load()
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 1_000_000.0)
    ledger = tmp_path / "ledger.jsonl"  # absent → zero in-cycle
    assert mod.check(ledger) == 1


def test_pass_when_pool_used_this_cycle(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 1_000_000.0)
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(ledger, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])  # ts >= since → in-cycle
    assert mod.check(ledger) == 0


def test_pass_when_no_pool_declared(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: True)  # NO-POOL: <reason> present
    assert mod.check(tmp_path / "ledger.jsonl") == 0


def test_pass_on_docs_only_below_threshold(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 2)  # <= threshold → not substantial
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    assert mod.check(tmp_path / "ledger.jsonl") == 0


def test_failsafe_on_git_failure(tmp_path, monkeypatch):
    # git can't determine the surface → None → must NOT block (fail-safe)
    mod = _load()
    monkeypatch.setattr(mod, "_changed_code_files", lambda: None)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    assert mod.check(tmp_path / "ledger.jsonl") == 0


def test_stale_ledger_prior_cycle_still_blocks(tmp_path, monkeypatch):
    # the Defect-2 fix: a pool run from a PRIOR cycle (ts < merge-base) does NOT satisfy this cycle
    mod = _load()
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 2_000_000.0)
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(ledger, [{"ts": _iso(1_000_000.0), "agent_id": "old"}])  # ts < since → prior cycle
    assert mod.check(ledger) == 1


def test_failsafe_on_check_exception(tmp_path, monkeypatch):
    # if the blocking layer itself raises, the gate must NOT be blocked (fail-safe)
    mod = _load()
    def boom(_):
        raise RuntimeError("boom")
    monkeypatch.setattr(mod, "_pool_or_declare", boom)
    assert mod.check(tmp_path / "ledger.jsonl") == 0


def test_unbounded_cycle_is_lenient(tmp_path, monkeypatch):
    # merge-base epoch unknown (None) → can't bound the cycle → count all rows → no block (fail-safe)
    mod = _load()
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: None)
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(ledger, [{"ts": _iso(1.0), "agent_id": "whenever"}])
    assert mod.check(ledger) == 0


# ─────────────── LAYER 1 — fixes from the adversarial pool review (false-block paths) ───────────────

def test_fb1_git_log_failure_treated_as_declared(monkeypatch):
    # FB1: if `git log` can't read the commit message, _declared_no_pool must fail-safe to True (no block)
    mod = _load()
    monkeypatch.delenv("FABRIK_NO_POOL", raising=False)
    monkeypatch.setattr(mod, "_git", lambda args: None)  # every git call fails
    assert mod._declared_no_pool() is True


def test_mb3_no_pool_word_boundary_not_substring(monkeypatch):
    # MB3: word-boundary — 'ANO-POOL:' must NOT match; but a real declaration with a prefix
    # ('Docs: NO-POOL:') and a space-before-colon ('NO-POOL :') MUST match (lenient on the escape).
    mod = _load()
    monkeypatch.delenv("FABRIK_NO_POOL", raising=False)
    monkeypatch.setattr(mod, "_git", lambda args: "Fix ANO-POOL: compat issue")
    assert mod._declared_no_pool() is False  # mid-word → not a declaration
    for msg in ("NO-POOL: mechanical rename", "Docs: NO-POOL: docs only", "chore\n\nNO-POOL : reason"):
        monkeypatch.setattr(mod, "_git", lambda args, m=msg: m)
        assert mod._declared_no_pool() is True, msg


def test_fb2_corrupt_ledger_line_counts_lenient(tmp_path):
    # FB2: a corrupt ledger line might be a real run → count it (never undercount → never false-block)
    mod = _load()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text('{ this is not valid json\n')
    assert mod._in_cycle_pool_runs(ledger, 1_000_000.0) >= 1


def test_fb3_naive_iso_ts_counts_lenient(tmp_path):
    # FB3 (corrected): a naive ISO ts is AMBIGUOUS (UTC? local?) — forcing UTC can undercount a real run
    # for a west-of-UTC writer → false-block. Fail-safe: count it regardless (lean no-block). A naive ts
    # that would fall BEFORE the since-epoch under a UTC assumption must STILL count.
    mod = _load()
    ledger = tmp_path / "ledger.jsonl"
    since = 1_700_000_000.0
    naive = datetime.fromtimestamp(since - 36000, UTC).replace(tzinfo=None).isoformat()  # 10h "before"
    _write_ledger(ledger, [{"ts": naive, "agent_id": "a"}])
    assert mod._in_cycle_pool_runs(ledger, since) == 1  # counted leniently despite appearing pre-cycle


def test_fb4_unstaged_files_excluded_from_surface(tmp_path, monkeypatch):
    # FB4: unstaged working-tree files (siblings' WIP / artifacts) must NOT inflate the surface.
    # _changed_code_files counts --cached (staged) + committed, never `git diff HEAD` (unstaged).
    mod = _load()
    calls = []
    def fake_git(args):
        calls.append(args)
        if args[:2] == ["diff", "--cached"]:
            return "a.py\nb.py\n"           # staged
        if args[0] == "merge-base":
            return "abc123\n"
        if args[:2] == ["diff", "--name-only"]:
            return "c.py\n"                  # committed since base
        return ""
    monkeypatch.setattr(mod, "_git", fake_git)
    assert mod._changed_code_files() == 3   # staged(2) + committed(1); NO `git diff HEAD` call
    assert ["diff", "--name-only", "HEAD"] not in calls  # unstaged surface never queried


# ─────────────────────────── LAYER 2 — advisory (never blocks) ───────────────────────────

def _run_advisory(ledger_path: Path) -> subprocess.CompletedProcess:
    # FABRIK_NO_POOL set → Layer 1 passes → isolates the Layer-2 advisory
    env = {**os.environ, "FABRIK_NO_POOL": "test-isolate-layer1"}
    return subprocess.run(
        [sys.executable, str(CHECK), str(ledger_path)],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env,
    )


def test_advisory_unreceipted_pool_run_is_flagged(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(ledger, [{"agent_id": "a1", "model": "minimax/minimax-m3", "task_type": "review"}])
    r = _run_advisory(ledger)
    assert r.returncode == 0, r.stderr
    assert "a1" in r.stdout and "never" in r.stdout.lower()


def test_advisory_fully_receipted_is_clean(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    receipts = tmp_path / "receipts.jsonl"
    _write_ledger(ledger, [{"agent_id": "a1", "model": "x", "task_type": "review"}])
    _write_ledger(receipts, [{"agent_id": "a1", "recorded": True, "project": "p"}])
    r = _run_advisory(ledger)
    assert r.returncode == 0, r.stderr
    assert "a1" not in r.stdout


def test_advisory_corrupt_ledger_is_safe(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81\n")
    r = _run_advisory(ledger)
    assert r.returncode == 0, r.stderr  # advisory never blocks, even on a corrupt ledger
