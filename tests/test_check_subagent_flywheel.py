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

CHECK = (
    Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_subagent_flywheel.py"
)


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
    monkeypatch.setattr(mod, "_pool_available", lambda: True)  # pool-equipped project
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 1_000_000.0)
    ledger = tmp_path / "ledger.jsonl"  # absent → zero in-cycle
    assert mod.check(ledger) == 1


def test_selfscope_no_pool_module_never_blocks(tmp_path, monkeypatch):
    # a project WITHOUT libs/subagents can't dispatch the pool → the gate must NOT block it (self-scope),
    # even on a huge code change with no pool runs + no declaration. This is what makes fleet distribution
    # safe: the block is a silent no-op until a project vendors the module.
    mod = _load()
    monkeypatch.setattr(mod, "_pool_available", lambda: False)
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 50)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 1_000_000.0)
    assert mod.check(tmp_path / "ledger.jsonl") == 0


def test_pass_when_pool_used_this_cycle(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(
        mod, "_pool_available", lambda: True
    )  # hermetic: exercise the real gating path
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 1_000_000.0)
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(ledger, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])  # ts >= since → in-cycle
    assert mod.check(ledger) == 0


def test_pass_when_no_pool_declared(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_pool_available", lambda: True)
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: True)  # NO-POOL: <reason> present
    assert mod.check(tmp_path / "ledger.jsonl") == 0


def test_pass_on_docs_only_below_threshold(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_pool_available", lambda: True)
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 2)  # <= threshold → not substantial
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    assert mod.check(tmp_path / "ledger.jsonl") == 0


def test_failsafe_on_git_failure(tmp_path, monkeypatch):
    # git can't determine the surface → None → must NOT block (fail-safe)
    mod = _load()
    monkeypatch.setattr(
        mod, "_pool_available", lambda: True
    )  # pool present → the code=None guard is what saves us
    monkeypatch.setattr(mod, "_changed_code_files", lambda: None)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    assert mod.check(tmp_path / "ledger.jsonl") == 0


def test_stale_ledger_prior_cycle_still_blocks(tmp_path, monkeypatch):
    # the Defect-2 fix: a pool run from a PRIOR cycle (ts < merge-base) does NOT satisfy this cycle
    mod = _load()
    monkeypatch.setattr(
        mod, "_pool_available", lambda: True
    )  # else self-scope short-circuits → 0, test fails spuriously
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 2_000_000.0)
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(
        ledger, [{"ts": _iso(1_000_000.0), "agent_id": "old"}]
    )  # ts < since → prior cycle
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
    monkeypatch.setattr(mod, "_pool_available", lambda: True)
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
    for msg in (
        "NO-POOL: mechanical rename",
        "Docs: NO-POOL: docs only",
        "chore\n\nNO-POOL : reason",
    ):
        monkeypatch.setattr(mod, "_git", lambda args, m=msg: m)
        assert mod._declared_no_pool() is True, msg


def test_regex_case_insensitive_and_underscore(monkeypatch):
    # Finding-2: the escape must be lenient — case-insensitive and hyphen-OR-underscore. `no-pool:`
    # (lowercase) and `NO_POOL:` (underscore, mirroring the FABRIK_NO_POOL env var) are REAL
    # declarations a human/agent writes; missing them = a false block. `ANO-POOL:` still must NOT match.
    mod = _load()
    monkeypatch.delenv("FABRIK_NO_POOL", raising=False)
    for msg in (
        "no-pool: lowercase rename",
        "NO_POOL: underscore mirrors the env var",
        "No-Pool: mixed",
    ):
        monkeypatch.setattr(mod, "_git", lambda args, m=msg: m)
        assert mod._declared_no_pool() is True, msg
    monkeypatch.setattr(mod, "_git", lambda args: "unrelated ANO_POOL: not a declaration")
    assert mod._declared_no_pool() is False  # mid-word (preceded by 'A') → still not a declaration


def test_declaration_scanned_across_in_cycle_commits(monkeypatch):
    # Finding-1: the surface spans base..HEAD, and per-phase commits (CLAUDE.md) declare ONCE — on an
    # earlier commit than HEAD. _declared_no_pool must scan the whole base..HEAD message blob, not
    # just `git log -1` (HEAD). Simulate: base resolves, and the phase-A commit (not HEAD) carries it.
    mod = _load()
    monkeypatch.delenv("FABRIK_NO_POOL", raising=False)
    monkeypatch.setattr(mod, "_resolve_base", lambda: "abc123")
    calls = {}

    def fake_git(args):
        calls["args"] = args
        # a base..HEAD log returns ALL in-cycle messages concatenated; the declaration is on phase A,
        # HEAD (phase C) has none
        return (
            "phase C: wire it\n\nphase B: more\n\nphase A: rename\n\nNO-POOL: mechanical rename\n"
        )

    monkeypatch.setattr(mod, "_git", fake_git)
    assert mod._declared_no_pool() is True
    assert calls["args"] == ["log", "--format=%B", "abc123..HEAD"]  # scanned the RANGE, not -1


def test_declaration_scan_all_history_when_base_unresolved(monkeypatch):
    # Pass-3 finding: when base can't be resolved (no origin/master|main), the declaration scan must go
    # maximally lenient — scan ALL reachable commit messages, SYMMETRIC with the ledger check counting
    # all rows when since_epoch is None. Reading only `git log -1` (HEAD) would miss an earlier commit's
    # NO-POOL declaration → a false block in the direction the fail-safe forbids.
    mod = _load()
    monkeypatch.delenv("FABRIK_NO_POOL", raising=False)
    monkeypatch.setattr(mod, "_resolve_base", lambda: None)  # neither origin/master nor origin/main
    calls = {}

    def fake_git(args):
        calls["args"] = args
        return "HEAD: latest, no decl\n\nearlier: NO-POOL: native-only cleanup\n"

    monkeypatch.setattr(mod, "_git", fake_git)
    assert mod._declared_no_pool() is True
    assert calls["args"] == ["log", "--format=%B"]  # ALL history, not `-1` (HEAD-only)


def test_nondict_ledger_line_counts_lenient_not_sentinel(tmp_path):
    # Finding-3: a non-object JSON ledger line (`[]`, `123`) must count leniently (n += 1) and NOT
    # blow the whole count to the 1_000_000 sentinel via an escaped AttributeError on rec.get.
    mod = _load()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("[]\n123\n" + json.dumps({"ts": _iso(1_000_500.0)}) + "\n")
    n = mod._in_cycle_pool_runs(ledger, 1_000_000.0)
    assert 0 < n < 1_000_000  # counted the lines, did not trip the disable-everything sentinel
    assert n == 3


def test_fb2_corrupt_ledger_line_counts_lenient(tmp_path):
    # FB2: a corrupt ledger line might be a real run → count it (never undercount → never false-block)
    mod = _load()
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("{ this is not valid json\n")
    assert mod._in_cycle_pool_runs(ledger, 1_000_000.0) >= 1


def test_fb3_naive_iso_ts_counts_lenient(tmp_path):
    # FB3 (corrected): a naive ISO ts is AMBIGUOUS (UTC? local?) — forcing UTC can undercount a real run
    # for a west-of-UTC writer → false-block. Fail-safe: count it regardless (lean no-block). A naive ts
    # that would fall BEFORE the since-epoch under a UTC assumption must STILL count.
    mod = _load()
    ledger = tmp_path / "ledger.jsonl"
    since = 1_700_000_000.0
    naive = (
        datetime.fromtimestamp(since - 36000, UTC).replace(tzinfo=None).isoformat()
    )  # 10h "before"
    _write_ledger(ledger, [{"ts": naive, "agent_id": "a"}])
    assert (
        mod._in_cycle_pool_runs(ledger, since) == 1
    )  # counted leniently despite appearing pre-cycle


def test_fb4_unstaged_files_excluded_from_surface(tmp_path, monkeypatch):
    # FB4: unstaged working-tree files (siblings' WIP / artifacts) must NOT inflate the surface.
    # _changed_code_files counts --cached (staged) + committed, never `git diff HEAD` (unstaged).
    mod = _load()
    calls = []

    def fake_git(args):
        calls.append(args)
        if args[:2] == ["diff", "--cached"]:
            return "a.py\nb.py\n"  # staged
        if args[0] == "merge-base":
            return "abc123\n"
        if args[:2] == ["diff", "--name-only"]:
            return "c.py\n"  # committed since base
        return ""

    monkeypatch.setattr(mod, "_git", fake_git)
    assert mod._changed_code_files() == 3  # staged(2) + committed(1); NO `git diff HEAD` call
    assert ["diff", "--name-only", "HEAD"] not in calls  # unstaged surface never queried


# ─────────────────────────── LAYER 2 — advisory (never blocks) ───────────────────────────


def _run_advisory(ledger_path: Path) -> subprocess.CompletedProcess:
    # FABRIK_NO_POOL set → Layer 1 passes → isolates the Layer-2 advisory
    env = {**os.environ, "FABRIK_NO_POOL": "test-isolate-layer1"}
    return subprocess.run(
        [sys.executable, str(CHECK), str(ledger_path)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
    )


def test_advisory_unreceipted_pool_run_is_flagged(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    _write_ledger(
        ledger, [{"agent_id": "a1", "model": "minimax/minimax-m3", "task_type": "review"}]
    )
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


def test_nested_trap_ledger_is_diagnosed_not_reported_as_zero(tmp_path, monkeypatch, capsys):
    """job-agent 01M0Z2B420: fanout(repo="<name>") from inside the repo writes the ledger to
    <root>/<name>/.tmp/subagents/ — the runs HAPPEN, the gate reads the real path, reports
    "ZERO pool runs" and blocks, and the agent's natural next move is a false NO-POOL
    declaration. Fleet sweep found the trap live in fabrik, transdoc, and tryton-crm. When
    in-cycle rows exist at the nested path, the gate must name the trap and the recovery,
    never claim zero."""
    mod = _load()
    root = tmp_path / "myrepo"
    nested = root / "myrepo" / ".tmp" / "subagents" / "ledger.jsonl"
    nested.parent.mkdir(parents=True)
    _write_ledger(nested, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])
    monkeypatch.setattr(mod, "PROJECT_ROOT", root)
    monkeypatch.setattr(mod, "_pool_available", lambda: True)
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 1_000_000.0)
    real_ledger = root / ".tmp" / "subagents" / "ledger.jsonl"  # absent
    assert mod.check(real_ledger) == 1, "a broken ledger location still blocks"
    out = capsys.readouterr().out
    assert "nested" in out.lower(), f"the trap must be named, not reported as zero:\n{out}"
    assert "ZERO OpenRouter pool" not in out, "the misleading zero-claim must not print"
    assert "repo=" in out, "the root cause (repo= misuse) must be named"
