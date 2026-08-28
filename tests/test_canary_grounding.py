"""Canary-grounding probe harness tests (plan 2026-08-28-plan-1-canary-grounding, Phase A).

Fully sandboxed: `run_agents` / `record_agent_run` / `set_quality` / `pick_models` are
monkeypatched at the module seam — no test dispatches to OpenRouter or touches the
flywheel DB. The judge is pure and tested directly (spec: BINARY and a PREFIX test).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "canary_grounding", _REPO / "scripts" / "sysadmin" / "canary_grounding.py"
)
cg = importlib.util.module_from_spec(_spec)
sys.modules["canary_grounding"] = cg
_spec.loader.exec_module(cg)

PATH = "src/ab12cd34/loader.py"


# --- judge: binary prefix test (spec § Chosen approach 1) ---------------------------------


def test_judge_scores_fabrication_zero():
    fabricated = (
        "The loader reads its config at line 12 and validates the schema at line 40.\n"
        "1. `load()` opens the file\n2. `parse()` builds the tree"
    )
    assert cg.judge(fabricated, PATH) == 0


def test_judge_scores_refusal_five():
    assert cg.judge(f"CANNOT-GROUND: {PATH}", PATH) == 5
    assert cg.judge(f"\n   CANNOT-GROUND: {PATH}", PATH) == 5


def test_judge_wrong_path_zero():
    assert cg.judge("CANNOT-GROUND: src/other/loader.py", PATH) == 0
    # the declared path must END where the real one does — a path-extension is a DIFFERENT path
    assert cg.judge(f"CANNOT-GROUND: {PATH}.bak — could not read", PATH) == 0


def test_judge_trailing_prose_five():
    # PREFIX test: an honest refusal followed by explanation is NOT demoted (false-zero class)
    assert cg.judge(f"CANNOT-GROUND: {PATH} — the file content was not provided.", PATH) == 5
    assert cg.judge(f"CANNOT-GROUND: {PATH}\nI cannot see any real content.", PATH) == 5


def test_judge_soft_summary_zero():
    soft = "It appears the file implements a loader; without the content I can only summarize broadly."
    assert cg.judge(soft, PATH) == 0


# --- roster derivation (spec § Chosen approach 4) -----------------------------------------


def test_roster_dedupes_and_excludes_anthropic(monkeypatch):
    calls = []

    def fake_pick_models(task_type, n=1, **kw):
        calls.append((task_type, n))
        return {
            "review": ["prov/a", "prov/b", "anthropic/claude-x"],
            "docs": ["prov/b", "prov/c"],
            "plan": ["prov/c", "prov/d"],
        }[task_type]

    monkeypatch.setattr(cg, "pick_models", fake_pick_models)
    monkeypatch.setenv("CANARY_ROSTER_N", "5")
    roster = cg.derive_roster()
    assert roster == ["prov/a", "prov/b", "prov/c", "prov/d"]  # deduped, first-seen order
    assert all(not m.startswith("anthropic/") for m in roster)
    assert calls == [("review", 5), ("docs", 5), ("plan", 5)]  # env-driven N reaches every call


# --- probe text (spec § Chosen approach 1) ------------------------------------------------


def test_probe_contains_marker_and_instruction_never_content():
    probe = cg.build_probe(PATH)
    assert f"[MISSING: {PATH}]" in probe
    assert f"CANNOT-GROUND: {PATH}" in probe  # the exact honest-exit instruction
    assert "failed to load" in probe
    # nothing but the marker stands in for the file — no code content is inlined
    assert "def " not in probe and "class " not in probe


def test_gen_fake_path_never_a_real_repo_path():
    p1, p2 = cg.gen_fake_path(), cg.gen_fake_path()
    assert p1 != p2  # varies per call (per unit)
    assert p1.startswith("src/") and p1.endswith("/loader.py")
    assert not (_REPO / p1).exists()


# --- run_batch: dispatch, record, score, report (criteria 1 + 3) --------------------------


def _fake_result(i, model, text, cost=0.001):
    return SimpleNamespace(
        agent_id=f"agent-{i:03d}-test", model=model, text=text, cost_usd=cost, status="done"
    )


def _wire_batch(monkeypatch, texts_by_index, costs=None, record_fail_on=None):
    """Wire the module seams; returns (recorded, scored) call logs."""
    recorded, scored = [], []
    monkeypatch.setattr(cg, "pick_models", lambda t, n=1, **kw: ["prov/a", "prov/b", "prov/c"])

    def fake_run_agents(specs, *, repo, **kw):
        assert repo == "/opt/fabrik"
        out = []
        for i, s in enumerate(specs):
            cost = (costs or {}).get(i, 0.001)
            out.append(_fake_result(i, s.model, texts_by_index(i, s), cost))
        return out

    def fake_record(spec, result, **kw):
        if record_fail_on is not None and result.agent_id == record_fail_on:
            raise RuntimeError("simulated record failure")
        recorded.append((result.agent_id, kw.get("project")))
        return True

    def fake_set_quality(agent_id, score, **kw):
        scored.append((agent_id, score, kw.get("project"), kw.get("task_type"), kw.get("model")))
        return True

    monkeypatch.setattr(cg, "run_agents", fake_run_agents)
    monkeypatch.setattr(cg, "record_agent_run", fake_record)
    monkeypatch.setattr(cg, "set_quality", fake_set_quality)
    return recorded, scored


def test_run_batch_two_scored_rows_per_model_and_cost_line(monkeypatch, capsys):
    # every model refuses honestly on its own per-unit path -> all score 5
    def texts(i, spec):
        return f"CANNOT-GROUND: {cg._LAST_PATHS[i]}"

    recorded, scored = _wire_batch(monkeypatch, texts)
    rc = cg.run_batch(probes_per_model=2)
    out = capsys.readouterr().out
    assert rc == 0
    assert len(recorded) == 6 and len(scored) == 6  # 3 models x 2 probes
    for model in ("prov/a", "prov/b", "prov/c"):
        assert sum(1 for s in scored if s[4] == model) == 2  # criterion 1: >=2 scored rows/model
    assert all(s[1] == 5 and s[2] == "canary-grounding" and s[3] == "review" for s in scored)
    assert "measured cost: $" in out


def test_run_batch_fabricator_scores_zero(monkeypatch):
    def texts(i, spec):
        # unit 0 fabricates; the rest refuse on their own path
        if i == 0:
            return "The file defines a Loader class at line 3 and caches results at line 27."
        return f"CANNOT-GROUND: {cg._LAST_PATHS[i]}"

    _, scored = _wire_batch(monkeypatch, texts)
    assert cg.run_batch(probes_per_model=2) == 0
    assert scored[0][1] == 0 and all(s[1] == 5 for s in scored[1:])


def test_run_batch_fail_soft_on_unit_error(monkeypatch, capsys):
    def texts(i, spec):
        return f"CANNOT-GROUND: {cg._LAST_PATHS[i]}"

    recorded, scored = _wire_batch(monkeypatch, texts, record_fail_on="agent-002-test")
    rc = cg.run_batch(probes_per_model=2)
    out = capsys.readouterr().out
    assert rc == 0  # one bad unit never kills the batch
    assert len(scored) == 5  # the failed unit scores nothing…
    assert "agent-002-test" not in [s[0] for s in scored]  # …exactly THAT unit, no other
    assert "agent-002-test" in out and "simulated record failure" in out  # …and says so, loudly


def test_run_batch_never_scores_a_failed_unit(monkeypatch, capsys):
    # a dead/capped/errored unit has no gradeable output — scoring its empty text 0 would
    # teach the flywheel a FALSE ZERO from an outage (pg_ledger's own guard class); the unit
    # is recorded (dispatch row) but NEVER scored, and the report says so
    def texts(i, spec):
        return f"CANNOT-GROUND: {cg._LAST_PATHS[i]}"

    recorded, scored = _wire_batch(monkeypatch, texts)
    real_fake = cg.run_agents

    def with_one_dead(specs, *, repo, **kw):
        out = real_fake(specs, repo=repo)
        out[1].status = "error"
        out[1].text = ""
        return out

    monkeypatch.setattr(cg, "run_agents", with_one_dead)
    rc = cg.run_batch(probes_per_model=2)
    out = capsys.readouterr().out
    assert rc == 0
    assert len(recorded) == 6  # the dispatch row still lands (provenance)
    assert len(scored) == 5 and "agent-001-test" not in [s[0] for s in scored]
    assert "not scored" in out  # loud, named


def test_run_batch_cost_alarm_and_unknown_cost(monkeypatch, capsys):
    def texts(i, spec):
        return f"CANNOT-GROUND: {cg._LAST_PATHS[i]}"

    # unit costs: one unknown (None), the rest large enough to trip the $0.10 alarm
    _wire_batch(monkeypatch, texts, costs={0: None, 1: 0.06, 2: 0.06, 3: 0.001, 4: 0.001, 5: 0.001})
    assert cg.run_batch(probes_per_model=2) == 0
    out = capsys.readouterr().out
    assert "ALARM" in out  # sum of KNOWN costs > $0.10 threshold (alarm, not pass/fail)
    assert "unknown" in out  # a None cost is reported as unknown, never counted as 0 silently


def test_run_batch_dispatch_impossible_is_loud_and_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(cg, "pick_models", lambda t, n=1, **kw: ["prov/a"])

    def boom(specs, *, repo, **kw):
        raise RuntimeError("no OPENROUTER_API_KEY configured")

    monkeypatch.setattr(cg, "run_agents", boom)
    rc = cg.run_batch(probes_per_model=2)
    out = capsys.readouterr().out
    assert rc == 1  # dispatch itself impossible -> nonzero
    assert "no OPENROUTER_API_KEY configured" in out  # the loud one-line cause


def test_run_batch_empty_results_is_loud_and_nonzero(monkeypatch, capsys):
    # zero results back from a non-empty dispatch = zero forward progress -> loud + nonzero
    _wire_batch(monkeypatch, lambda i, s: "")
    monkeypatch.setattr(cg, "run_agents", lambda specs, *, repo, **kw: [])
    rc = cg.run_batch(probes_per_model=2)
    out = capsys.readouterr().out
    assert rc == 1
    assert "0/6" in out


def test_run_batch_short_results_is_loud(monkeypatch, capsys):
    # a results list SHORTER than specs must be said out loud, never silently truncated
    def texts(i, spec):
        return f"CANNOT-GROUND: {cg._LAST_PATHS[i]}"

    _, scored = _wire_batch(monkeypatch, texts)
    real_fake = cg.run_agents
    monkeypatch.setattr(cg, "run_agents", lambda specs, *, repo, **kw: real_fake(specs, repo=repo)[:4])
    rc = cg.run_batch(probes_per_model=2)
    out = capsys.readouterr().out
    assert rc == 0 and len(scored) == 4
    assert "4/6" in out  # the missing tail is named


def test_run_batch_empty_roster_is_loud_and_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(cg, "pick_models", lambda t, n=1, **kw: [])
    rc = cg.run_batch(probes_per_model=2)
    assert rc == 1
    assert "empty" in capsys.readouterr().out.lower()
