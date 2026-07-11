"""Behavior Contract for scripts/doc_reconcile.py — all pool calls stubbed (no live models)."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.doc_reconcile as dr  # noqa: E402


# ── fixtures / helpers ────────────────────────────────────────────────────────
def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _mk_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.dev")
    _git(tmp_path, "config", "user.name", "t")
    return tmp_path


def _fake_result(diff: str = "", model: str = "stub/model") -> object:
    return types.SimpleNamespace(
        diff=diff, status="done", model=model, cost_usd=0.0, turns=1,
        agent_id="a1", error=None, latency_s=0.1, out_tokens=10, provider="stub", tool_calls=[],
    )


def _docrow(name: str = "docs/QUICKSTART.md") -> object:
    return types.SimpleNamespace(name=name, template=None, applies_to=frozenset(), trigger="x", fills="agent")


def _diff_for(repo: Path, relpath: str, new_content: str) -> str:
    """Produce a real git diff that turns the committed file into ``new_content``, then reset it."""
    p = repo / relpath
    original = p.read_text()
    p.write_text(new_content)
    diff = subprocess.run(
        ["git", "-C", str(repo), "diff", "--", relpath], capture_output=True, text=True
    ).stdout
    p.write_text(original)  # reset — reconcile will re-apply via the captured patch
    return diff


def _stub_pool(monkeypatch, *, diff: str, recorder: dict | None = None) -> None:
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["stub/model"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [_fake_result(diff=diff)])
    if dr.AgentSpec is None:  # ensure the reconcile path isn't short-circuited
        monkeypatch.setattr(dr, "AgentSpec", lambda **k: types.SimpleNamespace(**k))

    def _rec(spec, result, **k):
        if recorder is not None:
            recorder["quality_score"] = k.get("quality_score")
            recorder["project"] = k.get("project")
            recorder["spec"] = spec  # capture positional identity to prove arg ORDER (spec, result)
            recorder["result"] = result
        return True

    monkeypatch.setattr(dr, "record_agent_run", _rec)


# ── Behavior 1 (riskiest, TDD anchor): no-op convergence on a matching doc ─────
def test_loop_converges_on_matching_doc(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    doc = repo / "docs" / "QUICKSTART.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("hello world\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    _stub_pool(monkeypatch, diff="")  # empty diff = doc already matches → zero edits

    before = hashlib.md5(doc.read_bytes()).hexdigest()
    out = dr.reconcile_loop([_docrow()], "some code diff", repo)
    after = hashlib.md5(doc.read_bytes()).hexdigest()

    assert before == after  # md5-verified: the loop made ZERO edits
    assert out["status"] == "converged"
    assert out["rounds"] == 1
    assert out["docs"]["docs/QUICKSTART.md"].status == "noop"  # per-doc: reconcile ran, no change
    assert out["docs"]["docs/QUICKSTART.md"].applied is False


# ── Behavior 2: verified structured patch is applied + one flywheel row recorded ─
def test_structured_patch_applied_and_flywheel_recorded(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro line\n")
    (repo / "app.py").write_text("def real_symbol():\n    return 1\n")  # symbol EXISTS in the repo
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    diff = _diff_for(repo, "docs/QUICKSTART.md", "intro line\ncall `real_symbol` to run\n")
    recorder: dict = {}
    _stub_pool(monkeypatch, diff=diff, recorder=recorder)

    res = dr.reconcile_doc(_docrow(), "code diff", repo)  # default mechanical verify

    assert "real_symbol" in (repo / "docs" / "QUICKSTART.md").read_text()  # patch APPLIED
    assert res.applied is True
    assert res.status == "applied"
    assert recorder.get("quality_score") == 4.0  # flywheel recorded with the applied-quality signal
    assert recorder.get("project") == "doc-reconcile"
    # arg ORDER: record_agent_run(spec, result, ...) — the 1st positional is the spec, 2nd the result
    assert hasattr(recorder["spec"], "task") and hasattr(recorder["spec"], "model")
    assert hasattr(recorder["result"], "diff")


# ── Behavior 3: a verify_fn reporting drift → re-author, do NOT apply ──────────
def test_drift_verify_does_not_apply(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    diff = _diff_for(repo, "docs/QUICKSTART.md", "intro\nnew line\n")
    _stub_pool(monkeypatch, diff=diff)

    res = dr.reconcile_doc(_docrow(), "code diff", repo, verify_fn=lambda *a, **k: False)

    assert (repo / "docs" / "QUICKSTART.md").read_text() == "intro\n"  # NOT applied
    assert res.applied is False
    assert res.status == "drift"


# ── Behavior 4: the DEFAULT mechanical verify flags an absent symbol, passes a present one ─
def test_default_mechanical_verify(tmp_path):
    repo = _mk_repo(tmp_path)
    (repo / "app.py").write_text("def real_symbol():\n    pass\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")

    present = "+++ b/docs/QUICKSTART.md\n+use `real_symbol` here\n"
    absent = "+++ b/docs/QUICKSTART.md\n+use `imaginary_zebra_func` here\n"
    no_code = "+++ b/docs/QUICKSTART.md\n+just prose, no backticks\n"

    assert dr._default_verify(present, _docrow(), repo) is True
    assert dr._default_verify(absent, _docrow(), repo) is False
    assert dr._default_verify(no_code, _docrow(), repo) is True  # nothing to prove → pass


# ── Behavior 5: fired_docs is registry-driven (real detectors) ────────────────
def test_fired_docs_registry_driven():
    assert dr.fired_docs([]) == []  # nothing changed → nothing fired
    env_fired = {getattr(r, "name", "") for r in dr.fired_docs([".env.example"])}
    assert "docs/CONFIGURATION.md" in env_fired  # env change fires CONFIGURATION
    compose_fired = {getattr(r, "name", "") for r in dr.fired_docs(["compose.yaml"])}
    assert "docs/SERVICES.md" in compose_fired  # compose change fires SERVICES/OPERATIONS
    schema_fired = {getattr(r, "name", "") for r in dr.fired_docs(["db/schema.sql"])}
    assert "docs/data-contract.md" in schema_fired  # a .sql change fires the data contract


# ── Behavior 6: pool not vendored (ImportError) → graceful skip, no crash ──────
def test_pool_import_missing_graceful(tmp_path, monkeypatch):
    monkeypatch.setattr(dr, "run_agents", None)
    monkeypatch.setattr(dr, "AgentSpec", None)
    monkeypatch.setattr(dr, "pick_models", None)
    res = dr.reconcile_doc(_docrow(), "diff", tmp_path)
    assert res.applied is False
    assert res.status == "skipped"


# ── Behavior 7: any error inside the loop degrades, never raises ──────────────
def test_reconcile_loop_failsafe(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(dr, "_docset_md5", _boom)
    out = dr.reconcile_loop([_docrow()], "diff", Path("."))
    assert out["status"] == "degraded"  # outer fail-safe caught it


# ── Behavior 8: an empty fired-doc set converges immediately (0 rounds) ────────
def test_empty_docset_converges():
    out = dr.reconcile_loop([], "diff", Path("."))
    assert out["status"] == "converged"
    assert out["rounds"] == 0


# ── Behavior 9 (regression): persistent drift must RE-AUTHOR, never falsely converge ─
def test_loop_reauthors_on_persistent_drift(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    diff = _diff_for(repo, "docs/QUICKSTART.md", "intro\nnew\n")
    calls = {"n": 0}

    def _run(specs, **k):
        calls["n"] += 1
        return [_fake_result(diff=diff)]

    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", _run)
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    # verify ALWAYS reports drift → md5 never changes, but the doc is NOT done: the loop must keep
    # re-authoring to max_rounds, NOT declare a false "converged" on round 1.
    out = dr.reconcile_loop(
        [_docrow()], "code diff", repo, verify_fn=lambda *a, **k: False, max_rounds=3
    )
    assert out["status"] == "max_rounds"  # did NOT falsely converge
    assert out["rounds"] == 3  # kept re-authoring every round
    assert calls["n"] == 3  # one pool dispatch per round
    assert (repo / "docs" / "QUICKSTART.md").read_text() == "intro\n"  # never applied a bad patch


# ── Behavior 10: a non-"done" pool run (partial / not scope-guarded diff) is NEVER applied ─
def test_non_done_status_not_applied(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    (repo / "app.py").write_text("def real_symbol():\n    return 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    diff = _diff_for(repo, "docs/QUICKSTART.md", "intro\ncall `real_symbol`\n")
    err = types.SimpleNamespace(
        diff=diff, status="error", model="m", cost_usd=0.0, turns=1, agent_id="a",
        error="boom", latency_s=0.1, out_tokens=1, provider="s", tool_calls=[],
    )
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [err])
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    res = dr.reconcile_doc(_docrow(), "d", repo)
    assert res.status == "drift"  # "error" is not scope-guarded → never applied
    assert res.applied is False
    assert (repo / "docs" / "QUICKSTART.md").read_text() == "intro\n"


# ── Behavior 10b: a "capped" run IS scope-guarded (agent.py:348) → its verified patch applies ─
def test_capped_status_is_applied(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    (repo / "app.py").write_text("def real_symbol():\n    return 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    diff = _diff_for(repo, "docs/QUICKSTART.md", "intro\ncall `real_symbol`\n")
    capped = types.SimpleNamespace(
        diff=diff, status="capped", model="m", cost_usd=0.2, turns=8, agent_id="a",
        error=None, latency_s=0.1, out_tokens=50, provider="s", tool_calls=[],
    )
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [capped])
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    res = dr.reconcile_doc(_docrow(), "d", repo)
    assert res.applied is True  # capped is scope-guarded → a verified patch still lands
    assert "real_symbol" in (repo / "docs" / "QUICKSTART.md").read_text()


# ── Behavior 11: a patch touching a NON-owned path is rejected (scope guard) ──
def test_patch_targeting_other_path_rejected(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    (repo / "secrets.py").write_text("KEY = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    evil = _diff_for(repo, "secrets.py", "KEY = 999\n")  # patch edits secrets.py, NOT the owned doc
    _stub_pool(monkeypatch, diff=evil)

    res = dr.reconcile_doc(_docrow("docs/QUICKSTART.md"), "d", repo)
    assert res.status == "drift"  # rejected — out of owned scope
    assert (repo / "secrets.py").read_text() == "KEY = 1\n"  # untouched


# ── Behavior 12: run_agents returning [] is a FAILED dispatch → degraded (not a false noop) ──
def test_empty_pool_result_degrades(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [])  # pool returned nothing
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    res = dr.reconcile_doc(_docrow(), "d", repo)
    assert res.status == "degraded"  # NOT "noop" — an empty result is a failed dispatch
    assert res.applied is False


# ── Behavior 12b: an empty diff from a non-"done" status is degraded, not a false no-op ──
def test_empty_diff_error_status_degrades(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    err = types.SimpleNamespace(
        diff="", status="error", model="m", cost_usd=0.0, turns=1, agent_id="a",
        error="rate limited", latency_s=0.1, out_tokens=0, provider="s", tool_calls=[],
    )
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [err])
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    res = dr.reconcile_doc(_docrow(), "d", repo)
    assert res.status == "degraded"  # a failed dispatch must NOT read as "doc already correct"
    assert res.applied is False


# ── Behavior 13: a raising record_agent_run must NOT turn an applied result into degraded ─
def test_flywheel_record_raise_does_not_break(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    (repo / "app.py").write_text("def real_symbol():\n    return 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    diff = _diff_for(repo, "docs/QUICKSTART.md", "intro\ncall `real_symbol`\n")

    def _boom(*a, **k):
        raise RuntimeError("flywheel db down")

    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [_fake_result(diff=diff)])
    monkeypatch.setattr(dr, "record_agent_run", _boom)

    res = dr.reconcile_doc(_docrow(), "d", repo)
    assert res.applied is True and res.status == "applied"  # the recording failure was swallowed
    assert "real_symbol" in (repo / "docs" / "QUICKSTART.md").read_text()


# ── Behavior 14: a stale patch that fails git apply → degraded, but STILL records the flywheel ─
def test_stale_patch_apply_failure_degrades_and_records(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    (repo / "app.py").write_text("def real_symbol():\n    return 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    # references a real symbol (passes verify) but its context does not exist → git apply fails
    bad = (
        "diff --git a/docs/QUICKSTART.md b/docs/QUICKSTART.md\n"
        "--- a/docs/QUICKSTART.md\n+++ b/docs/QUICKSTART.md\n"
        "@@ -50,1 +50,2 @@\n nonexistent context line\n+see `real_symbol`\n"
    )
    recorded: dict = {}
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [_fake_result(diff=bad)])
    monkeypatch.setattr(dr, "record_agent_run", lambda spec, result, **k: recorded.update(k) or True)

    res = dr.reconcile_doc(_docrow(), "d", repo)
    assert res.applied is False
    assert res.status == "degraded"  # apply failed
    assert recorded.get("project") == "doc-reconcile"  # the flywheel STILL recorded the paid run
    assert (repo / "docs" / "QUICKSTART.md").read_text() == "intro\n"  # unchanged


# ── Behavior 15: run_agents is called with the REAL keyword contract (repo=, disjoint owned_paths) ─
def test_run_agents_call_shape(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    seen: dict = {}

    def _run(specs, **k):
        seen["kwargs"] = k
        seen["spec0"] = specs[0]
        return [_fake_result(diff="")]

    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", _run)
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    dr.reconcile_doc(_docrow(), "d", repo)
    assert "repo" in seen["kwargs"]  # the real signature is run_agents(specs, *, repo=...)
    assert seen["spec0"].owned_paths == ["docs/QUICKSTART.md"]  # one disjoint owned path per doc
    assert seen["spec0"].task_type == "docs"


# ── Behavior 16: main() CLI drives a range, returns 0, never raises ───────────
def test_main_cli_range(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / ".env.example").write_text("A=1\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "CONFIGURATION.md").write_text("config\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    (repo / ".env.example").write_text("A=1\nB=2\n")  # env change → CONFIGURATION trigger fires
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "envchange")
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [_fake_result(diff="")])  # matches → noop
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    assert dr.main(["--range", "HEAD~1..HEAD", "--root", str(repo)]) == 0


# ── Behavior 17 (F1 regression): applied is STICKY across rounds ──────────────
def test_applied_is_sticky_across_rounds(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    (repo / "app.py").write_text("def real_symbol():\n    return 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    diff = _diff_for(repo, "docs/QUICKSTART.md", "intro\ncall `real_symbol`\n")
    calls = {"n": 0}

    def _run(specs, **k):
        calls["n"] += 1
        # round 1: the real patch (applies → md5 changes → a 2nd round); round 2: doc matches → empty
        return [_fake_result(diff=diff if calls["n"] == 1 else "")]

    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", _run)
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    out = dr.reconcile_loop([_docrow()], "d", repo, max_rounds=3)
    assert out["status"] == "converged"
    assert out["rounds"] == 2  # applied round 1, noop round 2
    assert out["docs"]["docs/QUICKSTART.md"].applied is True  # STICKY — round-2 noop did not erase it


# ── Behavior 18 (C1 regression): persistent "degraded" must NOT falsely converge ──────
def test_loop_reauthors_on_persistent_degraded(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [])  # every round → degraded (no result)
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    out = dr.reconcile_loop([_docrow()], "d", repo, max_rounds=3)
    # md5 never changes (nothing applied), but a degraded round is UNRESOLVED — must not converge.
    assert out["status"] == "max_rounds"
    assert out["rounds"] == 3
    assert out["docs"]["docs/QUICKSTART.md"].status == "degraded"


# ── Behavior 19 (C2): _patch_targets_only uses git's parser — no header-format bypass ─────
def test_patch_targets_only_scope_guard(tmp_path):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    (repo / "secrets.py").write_text("KEY = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")

    # (a) a legitimate single-doc patch → accepted
    good = _diff_for(repo, "docs/QUICKSTART.md", "intro\nmore\n")
    assert dr._patch_targets_only(good, "docs/QUICKSTART.md", repo) is True

    # (b) a two-file patch whose foreign file uses a b/-LESS header → git's parser still sees it → rejected
    bypass = (
        "diff --git a/docs/QUICKSTART.md b/docs/QUICKSTART.md\n"
        "--- a/docs/QUICKSTART.md\n+++ b/docs/QUICKSTART.md\n"
        "@@ -1 +1,2 @@\n intro\n+line\n"
        "diff --git a/secrets.py b/secrets.py\n"
        "--- a/secrets.py\n+++ secrets.py\n"
        "@@ -1 +1 @@\n-KEY = 1\n+KEY = 999\n"
    )
    assert dr._patch_targets_only(bypass, "docs/QUICKSTART.md", repo) is False

    # (c) a rename-only diff (no +++ lines at all) → rejected (touches two paths / vacuous)
    rename = (
        "diff --git a/secrets.py b/pwn.py\n"
        "similarity index 100%\nrename from secrets.py\nrename to pwn.py\n"
    )
    assert dr._patch_targets_only(rename, "docs/QUICKSTART.md", repo) is False

    # (d) an unparseable patch → fail-CLOSED (reject)
    assert dr._patch_targets_only("not a patch at all", "docs/QUICKSTART.md", repo) is False


# ── Behavior 20: a "capped" run with an EMPTY diff is degraded (not a trusted no-op) ──
# Locks the intentional asymmetry: a non-empty capped diff is trusted (test 10b), but a capped
# run concluding "nothing to do" is NOT — else a budget-capped stall would masquerade as converged.
def test_capped_empty_diff_degrades(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    capped_empty = types.SimpleNamespace(
        diff="", status="capped", model="m", cost_usd=0.2, turns=8, agent_id="a",
        error=None, latency_s=0.1, out_tokens=0, provider="s", tool_calls=[],
    )
    monkeypatch.setattr(dr, "pick_models", lambda *a, **k: ["m"])
    monkeypatch.setattr(dr, "run_agents", lambda specs, **k: [capped_empty])
    monkeypatch.setattr(dr, "record_agent_run", lambda *a, **k: True)

    res = dr.reconcile_doc(_docrow(), "d", repo)
    assert res.status == "degraded"  # only a clean "done" empty diff is a trusted no-op


# ── Behavior 21: pool-not-vendored → every doc "skipped" → loop converges (does NOT spin) ──
def test_loop_all_skipped_converges(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "i")
    monkeypatch.setattr(dr, "run_agents", None)  # pool not vendored
    monkeypatch.setattr(dr, "AgentSpec", None)
    monkeypatch.setattr(dr, "pick_models", None)

    out = dr.reconcile_loop([_docrow()], "d", repo, max_rounds=3)
    assert out["status"] == "converged"  # "skipped" is resolved → converge, not spin to max_rounds
    assert out["rounds"] == 1
    assert out["docs"]["docs/QUICKSTART.md"].status == "skipped"
