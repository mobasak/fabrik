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

import pytest

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


def test_pass_with_nested_ledger_present_still_warns(tmp_path, monkeypatch, capsys):
    """Partial-split edge (review round 1): rows recorded to BOTH the real and the nested
    path make the gate pass on the real rows — and silently strand the nested ones. A pass
    with a nested ledger present must still say so (⚠-prefixed, so final_gate --json
    surfaces it), or the stranded rows are invisible until the next zero-cycle."""
    mod = _load()
    root = tmp_path / "myrepo"
    nested = root / "myrepo" / ".tmp" / "subagents" / "ledger.jsonl"
    nested.parent.mkdir(parents=True)
    _write_ledger(nested, [{"ts": _iso(1_000_500.0), "agent_id": "stranded"}])
    real = root / ".tmp" / "subagents" / "ledger.jsonl"
    real.parent.mkdir(parents=True)
    _write_ledger(real, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])
    monkeypatch.setattr(mod, "PROJECT_ROOT", root)
    monkeypatch.setattr(mod, "_pool_available", lambda: True)
    monkeypatch.setattr(mod, "_changed_code_files", lambda: 20)
    monkeypatch.setattr(mod, "_declared_no_pool", lambda: False)
    monkeypatch.setattr(mod, "_merge_base_epoch", lambda: 1_000_000.0)
    assert mod.check(real) == 0, "real in-cycle rows still pass the gate"
    out = capsys.readouterr().out
    assert "⚠" in out and "nested" in out.lower(), f"a silent pass strands the nested rows:\n{out}"


def test_unrecorded_warn_names_the_absent_dsn_when_that_is_the_cause(tmp_path, monkeypatch, capsys):
    """job-agent 01M12K8RRD: a repo with NO SUBAGENT_RUNS_DSN in its .env cannot record ANY
    fanout (record_agent_run fail-opens False, silently) — every dispatch piles into the
    unrecorded warning, and score() later blames "project=None". When the DSN is absent, the
    advisory must say THAT is the cause — the runs were never recordable, not never scored."""
    mod = _load()
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / ".env").write_text("OPENROUTER_API_KEY=x\n", encoding="utf-8")
    ledger = root / ".tmp" / "subagents" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    _write_ledger(ledger, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])
    monkeypatch.setattr(mod, "PROJECT_ROOT", root)
    import types
    fake = types.SimpleNamespace(audit_unrecorded=lambda p: [{"agent_id": "a1"}])
    monkeypatch.setitem(sys.modules, "libs.subagents", fake)
    # hermetic: the hub test process itself may carry a real DSN (conftest/.env autoload),
    # and the check honors the process env by design — clear it so ABSENT is actually absent
    monkeypatch.delenv("SUBAGENT_RUNS_DSN", raising=False)
    # hermetic against the FLEET-WIDE fallback too: the real ~/.config/fabrik/subagents.env on
    # this box carries the DSN, and the check now honors it (as the runtime does) — point the
    # resolver at a nonexistent file so "absent" means absent across every layer.
    monkeypatch.setenv("SUBAGENTS_ENV_FILE", str(tmp_path / "no-such-shared.env"))
    mod._warn_unrecorded(ledger)
    out = capsys.readouterr().out
    assert "SUBAGENT_RUNS_DSN" in out, f"the absent-DSN cause must be named:\n{out}"
    assert "cannot record" in out.lower() or "unrecordable" in out.lower()


def test_shared_fallback_dsn_suppresses_unrecordable(tmp_path, monkeypatch, capsys):
    """intel 01M12SZVRD (2026-08-28): the advisory read ONLY the process env + the repo .env, so a
    repo with a clean .env that records fine via the fleet-wide ~/.config/fabrik/subagents.env
    fallback (what load_env actually honors) was falsely told "UNRECORDABLE — ask infra". That false
    alarm cost a cross-agent finding. When the DSN resolves via the shared file, the advisory MUST NOT
    claim the runs are unrecordable — it keeps the generic "ran but never scored" message."""
    import types

    mod = _load()
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / ".env").write_text("OPENROUTER_API_KEY=x\n", encoding="utf-8")  # clean .env — no DSN
    ledger = root / ".tmp" / "subagents" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    _write_ledger(ledger, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])
    monkeypatch.setattr(mod, "PROJECT_ROOT", root)
    fake = types.SimpleNamespace(audit_unrecorded=lambda p: [{"agent_id": "a1"}])
    monkeypatch.setitem(sys.modules, "libs.subagents", fake)
    monkeypatch.delenv("SUBAGENT_RUNS_DSN", raising=False)  # not in process env either
    shared = tmp_path / "subagents.env"  # the operator's fleet-wide file DOES carry the DSN
    shared.write_text("SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics\n", encoding="utf-8")
    monkeypatch.setenv("SUBAGENTS_ENV_FILE", str(shared))
    mod._warn_unrecorded(ledger)
    out = capsys.readouterr().out
    assert "UNRECORDABLE" not in out, f"shared-file DSN not honored — false unrecordable claim:\n{out}"


@pytest.mark.parametrize(
    "dsn_line",
    [
        "export SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics",  # shell-export form
        "    SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics",  # leading indentation
        "\texport  SUBAGENT_RUNS_DSN=postgresql:///fabrik_analytics",  # tab + export + extra space
    ],
)
def test_dsn_detection_matches_runtime_parser_on_export_and_whitespace(
    tmp_path, monkeypatch, capsys, dsn_line
):
    """Native review 2026-08-28: the raw startswith missed `export SUBAGENT_RUNS_DSN=` and indented
    lines, but the runtime parser (_dotenv._parse_env_text) strips whitespace + a leading `export `,
    so such a repo records fine yet the check falsely printed UNRECORDABLE — re-exposing the exact
    false alarm on the new shared-file layer. The check must agree with what load_env actually loads."""
    import types

    mod = _load()
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / ".env").write_text("OPENROUTER_API_KEY=x\n", encoding="utf-8")  # clean repo .env
    ledger = root / ".tmp" / "subagents" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    _write_ledger(ledger, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])
    monkeypatch.setattr(mod, "PROJECT_ROOT", root)
    fake = types.SimpleNamespace(audit_unrecorded=lambda p: [{"agent_id": "a1"}])
    monkeypatch.setitem(sys.modules, "libs.subagents", fake)
    monkeypatch.delenv("SUBAGENT_RUNS_DSN", raising=False)
    shared = tmp_path / "subagents.env"
    shared.write_text(dsn_line + "\n", encoding="utf-8")
    monkeypatch.setenv("SUBAGENTS_ENV_FILE", str(shared))
    mod._warn_unrecorded(ledger)
    out = capsys.readouterr().out
    assert "UNRECORDABLE" not in out, f"runtime-parseable DSN line missed by the check:\n{dsn_line!r}\n{out}"


@pytest.mark.parametrize("commented", ["SUBAGENT_RUNS_DSN=# not set yet", "SUBAGENT_RUNS_DSN=#todo"])
def test_commented_out_dsn_value_is_not_counted_present(tmp_path, monkeypatch, capsys, commented):
    """Closing review 2026-08-28: a value that is ENTIRELY a `#`-comment is a commented-out placeholder
    the runtime parser (_dotenv._parse_env_text) treats as empty → NOT loaded → the repo is genuinely
    unrecordable. The check must NOT count it as a present DSN (that would fail-silent, suppressing a
    real advisory). So a `#`-only value keeps the UNRECORDABLE advisory."""
    import types

    mod = _load()
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / ".env").write_text("OPENROUTER_API_KEY=x\n", encoding="utf-8")
    ledger = root / ".tmp" / "subagents" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    _write_ledger(ledger, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])
    monkeypatch.setattr(mod, "PROJECT_ROOT", root)
    fake = types.SimpleNamespace(audit_unrecorded=lambda p: [{"agent_id": "a1"}])
    monkeypatch.setitem(sys.modules, "libs.subagents", fake)
    monkeypatch.delenv("SUBAGENT_RUNS_DSN", raising=False)
    shared = tmp_path / "subagents.env"
    shared.write_text(commented + "\n", encoding="utf-8")
    monkeypatch.setenv("SUBAGENTS_ENV_FILE", str(shared))
    mod._warn_unrecorded(ledger)
    out = capsys.readouterr().out
    assert "UNRECORDABLE" in out, f"commented-out DSN value wrongly counted as present:\n{commented!r}\n{out}"


def test_dsn_detection_survives_bom_and_honors_process_env(tmp_path, monkeypatch, capsys):
    """Review round 1 (2026-08-28): a UTF-8 BOM on the DSN line broke startswith (false
    "unrecordable" on a provisioned repo), and a repo whose DSN arrives via the process
    environment (CI, secrets manager) with a clean .env was also mis-flagged. Both states
    must keep the GENERIC advisory, not the absent-DSN claim."""
    import types

    mod = _load()
    root = tmp_path / "myrepo"
    root.mkdir()
    ledger = root / ".tmp" / "subagents" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    _write_ledger(ledger, [{"ts": _iso(1_000_500.0), "agent_id": "a1"}])
    monkeypatch.setattr(mod, "PROJECT_ROOT", root)
    fake = types.SimpleNamespace(audit_unrecorded=lambda p: [{"agent_id": "a1"}])
    monkeypatch.setitem(sys.modules, "libs.subagents", fake)

    (root / ".env").write_text("\ufeffSUBAGENT_RUNS_DSN=postgresql://x\n", encoding="utf-8")
    monkeypatch.delenv("SUBAGENT_RUNS_DSN", raising=False)
    mod._warn_unrecorded(ledger)
    out = capsys.readouterr().out
    assert "UNRECORDABLE" not in out, f"BOM-prefixed DSN line read as absent:\n{out}"

    (root / ".env").write_text("OPENROUTER_API_KEY=x\n", encoding="utf-8")
    monkeypatch.setenv("SUBAGENT_RUNS_DSN", "postgresql://from-ci")
    mod._warn_unrecorded(ledger)
    out = capsys.readouterr().out
    assert "UNRECORDABLE" not in out, f"process-env DSN not honored:\n{out}"
