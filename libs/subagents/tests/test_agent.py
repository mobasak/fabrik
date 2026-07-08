"""Phase E — agent.py: public surface + concurrency orchestration.

The two containment guarantees are pinned first (TDD): a diff touching a path
outside the spec's owned_paths is flagged out_of_scope (and never applied), and
overlapping specs serialize while disjoint specs run in parallel. Loop execution
is dependency-injected (``loop_fn``) so these run offline with a fake model.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from subagents.agent import AgentResult, AgentSpec, run_agents
from subagents.loop import LoopOutcome

_HAS_GIT = shutil.which("git") is not None
pytestmark = pytest.mark.skipif(not _HAS_GIT, reason="git not available")


def _init_repo(tmp_path: Path) -> str:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return str(repo)


def _outcome(
    text: str = "ok", status: str = "done", provider: str | None = "prov"
) -> LoopOutcome:
    return LoopOutcome(
        text=text,
        status=status,
        turns=1,
        cost_usd=0.002,
        transcript=[],
        provider=provider,
    )


def test_out_of_scope_flags_boundary_violation(tmp_path: Path) -> None:
    """A fake agent that writes OUTSIDE its owned_paths is flagged out_of_scope,
    and its change never lands in the caller repo."""
    repo = _init_repo(tmp_path)

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        Path(workdir, "sneaky.py").write_text("not allowed\n", encoding="utf-8")
        return _outcome()

    spec = AgentSpec(task="stay in bounds", model="m", owned_paths=["allowed/*"])
    [result] = run_agents([spec], repo=repo, loop_fn=fake_loop)

    assert result.status == "out_of_scope"
    assert not (Path(repo) / "sneaky.py").exists(), (
        "out-of-scope change leaked into repo"
    )


def test_capped_agent_out_of_scope_is_flagged(tmp_path: Path) -> None:
    """A CAPPED agent that also wrote outside its bounds is flagged out_of_scope,
    not silently returned as capped."""
    repo = _init_repo(tmp_path)

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        Path(workdir, "sneaky.py").write_text("x\n", encoding="utf-8")
        return _outcome(status="capped")

    spec = AgentSpec(task="t", model="m", owned_paths=["allowed/*"])
    [result] = run_agents([spec], repo=repo, loop_fn=fake_loop)
    assert result.status == "out_of_scope"


def test_in_scope_change_is_done(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        Path(workdir, "allowed").mkdir(exist_ok=True)
        Path(workdir, "allowed", "x.py").write_text("ok\n", encoding="utf-8")
        return _outcome()

    spec = AgentSpec(task="edit allowed", model="m", owned_paths=["allowed/*"])
    [result] = run_agents([spec], repo=repo, loop_fn=fake_loop)

    assert result.status == "done"
    assert "allowed/x.py" in result.diff


def test_overlapping_specs_are_serialized(tmp_path: Path) -> None:
    """Two specs owning the same glob must run one-after-the-other (no interleave)."""
    repo = _init_repo(tmp_path)
    order: list[str] = []
    lock = threading.Lock()

    def fake_loop(*, task, workdir, **kw):  # noqa: ANN001, ANN003
        with lock:
            order.append(f"start-{task}")
        time.sleep(0.05)
        with lock:
            order.append(f"end-{task}")
        return _outcome()

    specs = [
        AgentSpec(task="A", model="m", owned_paths=["shared/*"]),
        AgentSpec(task="B", model="m", owned_paths=["shared/*"]),
    ]
    run_agents(specs, repo=repo, max_concurrency=4, loop_fn=fake_loop)
    # serialized in index order → no interleaving
    assert order == ["start-A", "end-A", "start-B", "end-B"]


def test_disjoint_specs_run_in_parallel(tmp_path: Path) -> None:
    """Two specs with disjoint owned_paths must run concurrently — proven by a
    barrier that only releases if both are in flight at once."""
    repo = _init_repo(tmp_path)
    barrier = threading.Barrier(2, timeout=3)

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        barrier.wait()  # BrokenBarrierError (→ error status) if not truly parallel
        return _outcome()

    specs = [
        AgentSpec(task="A", model="m", owned_paths=["a/*"]),
        AgentSpec(task="B", model="m", owned_paths=["b/*"]),
    ]
    results = run_agents(specs, repo=repo, max_concurrency=2, loop_fn=fake_loop)
    assert all(r.status == "done" for r in results), "specs did not run in parallel"


def test_readers_with_empty_owned_paths_run_in_parallel(tmp_path: Path) -> None:
    """Single-shot READERS (tools_enabled=False, owned_paths=[]) must run CONCURRENTLY — they
    never write the tree, so empty owned_paths must NOT collapse them into one serial group.
    Regression for the trade-intelligence upstream fix: before it, a parallel review/research
    pool (readers with owned_paths=[]) all ran serially. The 3-way barrier releases only if all
    three are in flight at once; serialized readers would time it out → error status."""
    repo = _init_repo(tmp_path)
    barrier = threading.Barrier(3, timeout=3)

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        barrier.wait()  # BrokenBarrierError (→ error) if the readers were serialized
        return _outcome()

    specs = [
        AgentSpec(task=f"review-{i}", model="m", tools_enabled=False, owned_paths=[])
        for i in range(3)
    ]
    results = run_agents(specs, repo=repo, max_concurrency=3, loop_fn=fake_loop)
    assert all(r.status == "done" for r in results), "single-shot readers were serialized"


def test_partial_tolerance_one_failure_does_not_sink_batch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    def fake_loop(*, task, workdir, **kw):  # noqa: ANN001, ANN003
        if task == "boom":
            raise RuntimeError("agent exploded")
        return _outcome()

    specs = [
        AgentSpec(task="fine", model="m", owned_paths=["a/*"]),
        AgentSpec(task="boom", model="m", owned_paths=["b/*"]),
    ]
    results = run_agents(specs, repo=repo, loop_fn=fake_loop)
    assert results[0].status == "done"
    assert results[1].status == "error"
    assert results[1].error is not None


def test_provider_and_ledger_recorded(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    ledger_path = str(tmp_path / "runs.jsonl")

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        return _outcome(provider="anthropic")

    spec = AgentSpec(task="t", model="m", owned_paths=["a/*"])
    [result] = run_agents([spec], repo=repo, ledger_path=ledger_path, loop_fn=fake_loop)

    assert result.provider == "anthropic"
    import json

    records = [
        json.loads(ln)
        for ln in Path(ledger_path).read_text().splitlines()
        if ln.strip()
    ]
    assert len(records) == 1
    assert records[0]["status"] == "done"
    assert records[0]["task"] == "t"


def test_latency_is_populated_and_ledgered(tmp_path: Path) -> None:
    """`latency_s` is set on the result AND recorded in the ledger — the value metric that a
    future refactor dropping one of the two `_run_one` timing assignments must not silently lose."""
    import json

    repo = _init_repo(tmp_path)
    ledger_path = str(tmp_path / "l.jsonl")

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        return _outcome()

    spec = AgentSpec(task="t", model="m", task_type="spec")
    [result] = run_agents([spec], repo=repo, ledger_path=ledger_path, loop_fn=fake_loop)
    assert result.latency_s is not None and result.latency_s >= 0
    rec = json.loads(Path(ledger_path).read_text(encoding="utf-8").splitlines()[-1])
    assert isinstance(rec["latency_s"], (int, float)) and rec["latency_s"] >= 0
    assert rec["task_type"] == "spec"


def test_result_dataclass_shape() -> None:
    r = AgentResult(
        agent_id="a",
        text="",
        diff="",
        status="done",
        provider=None,
        cost_usd=None,
        turns=0,
    )
    assert r.status == "done"


def test_empty_specs_returns_empty(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert run_agents([], repo=repo) == []


def test_web_tools_calls_recorded_in_ledger(tmp_path: Path) -> None:
    """tool_calls provenance flows LoopOutcome → AgentResult → ledger record."""
    repo = _init_repo(tmp_path)
    ledger_path = str(tmp_path / "runs.jsonl")

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        return LoopOutcome(
            text="ok",
            status="done",
            turns=1,
            cost_usd=0.001,
            transcript=[],
            provider="p",
            tool_calls={"web_search": 2, "docs_lookup": 1},
        )

    spec = AgentSpec(
        task="research",
        model="m",
        owned_paths=["a/*"],
        web_tools=frozenset({"web_search", "docs_lookup"}),
    )
    [result] = run_agents([spec], repo=repo, ledger_path=ledger_path, loop_fn=fake_loop)

    assert result.tool_calls == {"web_search": 2, "docs_lookup": 1}
    import json

    rec = next(
        json.loads(ln)
        for ln in Path(ledger_path).read_text().splitlines()
        if ln.strip()
    )
    assert rec["tool_calls"] == {"web_search": 2, "docs_lookup": 1}


def test_diff_capture_failure_is_fail_closed(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """If scope can't be verified (changed_paths raises), the run is status=error
    (never a bare 'done'), but the paid cost is preserved (F2#2/#3)."""
    from subagents import workspace

    repo = _init_repo(tmp_path)

    def boom(_wt: str) -> list[str]:
        raise RuntimeError("git exploded")

    monkeypatch.setattr(workspace, "changed_paths", boom)

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        return _outcome(status="done")  # cost_usd=0.002 in _outcome

    [result] = run_agents(
        [AgentSpec(task="t", model="m", owned_paths=["a/*"])],
        repo=repo,
        loop_fn=fake_loop,
    )
    assert result.status == "error"  # fail-closed: unverified scope is not "done"
    assert result.cost_usd == 0.002  # but the paid work's cost is preserved


def test_rename_out_of_scope_is_not_bypassed(tmp_path: Path) -> None:
    """A pure git RENAME to an out-of-scope path must still be flagged — the text
    diff of a rename has no +++/--- header, so the authoritative path list matters."""
    repo = _init_repo(tmp_path)

    def fake_loop(*, workdir, **kw):  # noqa: ANN001, ANN003
        # create a committed file inside scope, then rename it OUT of scope via git,
        # producing a pure-rename staged change (no +++/--- lines)
        src = Path(workdir, "allowed")
        src.mkdir(exist_ok=True)
        f = src / "mod.py"
        f.write_text("x" * 50 + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(["git", "commit", "-qm", "seed2"], cwd=workdir, check=True)
        (Path(workdir, "escaped.py")).write_text("x" * 50 + "\n", encoding="utf-8")
        f.unlink()
        return _outcome()

    spec = AgentSpec(task="rename out", model="m", owned_paths=["allowed/*"])
    [result] = run_agents([spec], repo=repo, loop_fn=fake_loop)
    assert result.status == "out_of_scope", "a rename escaped the scope check"


def test_max_concurrency_zero_raises(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    spec = AgentSpec(task="t", model="m", owned_paths=["a/*"])
    with pytest.raises(ValueError, match="max_concurrency"):
        run_agents([spec], repo=repo, max_concurrency=0)


def test_run_agents_in_running_loop_raises(tmp_path: Path) -> None:
    import asyncio

    repo = _init_repo(tmp_path)

    async def _inner() -> None:
        with pytest.raises(RuntimeError, match="running event loop"):
            run_agents([], repo=repo)

    asyncio.run(_inner())


def test_run_agents_on_progress_tags_agent_id(tmp_path: Path) -> None:
    """End-to-end: the batch `on_progress` receives events tagged with the per-agent
    `agent_id` (the `_run_one` wrapper) through the FULL run_agents path — not just the
    thin `_invoke_loop` contract."""
    repo = _init_repo(tmp_path)
    got: list[dict] = []

    def fake_loop(*, workdir, on_progress=None, **kw):  # noqa: ANN001, ANN003
        if on_progress is not None:
            on_progress({"turns": 2, "cost_usd": 0.01, "provider": "p", "tools": ["x"]})
        return _outcome()

    spec = AgentSpec(task="t", model="m", owned_paths=["out/*"])
    run_agents([spec], repo=repo, loop_fn=fake_loop, on_progress=got.append)

    assert len(got) == 1
    assert got[0]["turns"] == 2 and got[0]["tools"] == ["x"]
    assert got[0]["agent_id"].startswith("agent-000-")


def test_results_table_renders_and_is_total() -> None:
    """results_table produces the standard report row from an AgentResult; a missing field
    renders '—' rather than raising."""
    from subagents.agent import AgentResult, results_table

    r = AgentResult("a-1", "txt", "", "done", "Minimax", 0.0209, 5, latency_s=160.0, out_tokens=14000)
    tbl = results_table(
        [{"unit": "web-quota", "model": "minimax/minimax-m3", "result": r,
          "quality": 5, "fixes": "rate-limit bypass"}]
    )
    for want in ("web-quota", "minimax/minimax-m3", "Minimax", "$0.0209", "160s", "14.0k", "5/5", "rate-limit bypass"):
        assert want in tbl, want
    # total: an error result with None cost/latency + 0 out_tokens → em-dashes, no crash
    bad = AgentResult("a-2", "", "", "error", None, None, 0)
    tbl2 = results_table([{"unit": "x", "model": "m", "result": bad}])
    assert "—" in tbl2
