"""Coverage for fabrik.orchestrator.gpu_metrics: collect, render, write_textfile."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta

import pytest

from fabrik.orchestrator import gpu_metrics, gpu_rent, gpu_state


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolate state + history log + metrics file under tmp_path."""
    log = tmp_path / "gpu-rent.jsonl"
    state: dict = {}
    monkeypatch.setattr(gpu_rent, "GPU_RENT_LOG", log)
    monkeypatch.setattr(gpu_state, "load_state", lambda: state)
    monkeypatch.setattr(gpu_metrics, "METRICS_FILE", tmp_path / "logs" / "m.prom")
    return log, state


def _write_log(log, recs):
    log.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in recs) + "\n")


# ---- _escape_label / _line -------------------------------------------------


def test_escape_label_handles_backslash_quote_newline():
    assert gpu_metrics._escape_label('a\\b"c\nd') == 'a\\\\b\\"c\\nd'


def test_escape_label_backslash_escaped_first():
    # a quote must become \" and not \\" (no double escaping of the added backslash)
    assert gpu_metrics._escape_label('"') == '\\"'


def test_line_without_labels():
    assert gpu_metrics._line("m", {}, 3) == "m 3"


def test_line_with_labels_in_order():
    assert gpu_metrics._line("m", {"a": "x", "b": "y"}, 1.5) == 'm{a="x",b="y"} 1.5'


def test_line_escapes_label_values_and_stringifies():
    assert gpu_metrics._line("m", {"k": 'v"1'}, 0) == 'm{k="v\\"1"} 0'
    assert gpu_metrics._line("m", {"k": 5}, 0) == 'm{k="5"} 0'


def test_line_positive_and_negative_infinity():
    assert gpu_metrics._line("m", {}, math.inf) == "m +Inf"
    assert gpu_metrics._line("m", {"a": "b"}, -math.inf) == 'm{a="b"} -Inf'


# ---- collect ---------------------------------------------------------------


def test_collect_empty_state_no_log(env):
    m = gpu_metrics.collect()
    assert m["sessions_total"] == {}
    assert m["cost_total"] == {}
    assert m["active_per_provider"] == {}
    assert m["destroy_pending_per_provider"] == {}
    assert m["last_reconcile_age_seconds"] == math.inf


def test_collect_counts_sessions_by_label_tuple(env):
    log, _ = env
    _write_log(
        log,
        [
            {"provider": "runpod", "kind": "pod", "workload": "train", "success": True},
            {"provider": "runpod", "kind": "pod", "workload": "train", "success": True},
            {"provider": "runpod", "kind": "pod", "workload": "train", "success": False},
        ],
    )
    m = gpu_metrics.collect()
    assert m["sessions_total"][("runpod", "pod", "train", "true")] == 2
    assert m["sessions_total"][("runpod", "pod", "train", "false")] == 1


def test_collect_missing_fields_default_unknown(env):
    log, _ = env
    _write_log(log, [{}])
    m = gpu_metrics.collect()
    assert m["sessions_total"] == {("unknown", "unknown", "unknown", "false"): 1}


def test_collect_skips_blank_and_malformed_lines(env):
    log, _ = env
    _write_log(log, ["", "   ", "{not json", {"provider": "p", "success": True}])
    m = gpu_metrics.collect()
    assert sum(m["sessions_total"].values()) == 1


def test_collect_sums_positive_cost_only(env):
    log, _ = env
    base = {"provider": "p", "kind": "k", "workload": "w", "success": True}
    _write_log(
        log,
        [
            {**base, "cost_actual_usd": 1.25},
            {**base, "cost_actual_usd": 0.75},
            {**base, "cost_actual_usd": 0},
            {**base, "cost_actual_usd": None},
            {**base, "cost_actual_usd": -5},
            base,
        ],
    )
    m = gpu_metrics.collect()
    assert m["cost_total"] == {("p", "k", "w"): pytest.approx(2.0)}
    assert sum(m["sessions_total"].values()) == 6


def test_collect_active_excludes_destroyed(env):
    _, state = env
    state["sessions"] = {
        "a": {"provider": "runpod"},
        "b": {"provider": "runpod", "destroyed_at": "2026-01-01T00:00:00+00:00"},
        "c": {"provider": "vast"},
        "d": {},
    }
    m = gpu_metrics.collect()
    assert m["active_per_provider"] == {"runpod": 1, "vast": 1, "unknown": 1}


def test_collect_destroy_pending_counts_only_live_pending(env):
    _, state = env
    state["sessions"] = {
        "a": {"provider": "runpod", "destroy_pending": True},
        "b": {"provider": "runpod", "destroy_pending": True},
        "c": {"provider": "runpod"},
        "d": {"provider": "vast", "destroy_pending": True, "destroyed_at": "x"},
    }
    m = gpu_metrics.collect()
    assert m["destroy_pending_per_provider"] == {"runpod": 2}
    assert m["active_per_provider"] == {"runpod": 3}


def test_collect_reconcile_age_from_aware_timestamp(env):
    _, state = env
    state["last_reconciled"] = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    age = gpu_metrics.collect()["last_reconcile_age_seconds"]
    assert 119 <= age < 180


def test_collect_reconcile_age_unparseable_is_inf(env):
    _, state = env
    state["last_reconciled"] = "not-a-date"
    assert gpu_metrics.collect()["last_reconcile_age_seconds"] == math.inf


def test_collect_reconcile_age_empty_string_is_inf(env):
    _, state = env
    state["last_reconciled"] = ""
    assert gpu_metrics.collect()["last_reconcile_age_seconds"] == math.inf


@pytest.mark.xfail(
    strict=True,
    reason="naive last_reconciled makes aware-naive subtraction raise TypeError (gpu_metrics.py:113)",
)
def test_collect_reconcile_age_naive_timestamp_does_not_crash(env):
    _, state = env
    state["last_reconciled"] = "2026-01-01T00:00:00"
    age = gpu_metrics.collect()["last_reconcile_age_seconds"]
    assert age > 0


# ---- render ----------------------------------------------------------------


def _metrics(**over):
    base = {
        "sessions_total": {},
        "cost_total": {},
        "active_per_provider": {},
        "destroy_pending_per_provider": {},
        "last_reconcile_age_seconds": 10.0,
    }
    base.update(over)
    return base


def test_render_empty_emits_zero_defaults_and_trailing_newline():
    text = gpu_metrics.render(_metrics())
    assert text.endswith("\n")
    assert 'gpu_rent_active{provider="runpod"} 0' in text
    assert 'gpu_rent_destroy_pending{provider="runpod"} 0' in text
    assert "gpu_rent_last_reconcile_age_seconds 10.0" in text


def test_render_help_and_type_lines_present():
    text = gpu_metrics.render(_metrics())
    for name, kind in [
        ("gpu_rent_sessions_total", "counter"),
        ("gpu_rent_cost_usd_total", "counter"),
        ("gpu_rent_active", "gauge"),
        ("gpu_rent_destroy_pending", "gauge"),
        ("gpu_rent_last_reconcile_age_seconds", "gauge"),
    ]:
        assert f"# TYPE {name} {kind}" in text
        assert f"# HELP {name} " in text


def test_render_sessions_and_cost_labels():
    text = gpu_metrics.render(
        _metrics(
            sessions_total={("runpod", "pod", "train", "true"): 3},
            cost_total={("runpod", "pod", "train"): 1.5},
        )
    )
    assert (
        'gpu_rent_sessions_total{provider="runpod",kind="pod",workload="train",success="true"} 3'
        in text
    )
    assert 'gpu_rent_cost_usd_total{provider="runpod",kind="pod",workload="train"} 1.5' in text


def test_render_active_nonempty_suppresses_zero_default():
    text = gpu_metrics.render(
        _metrics(active_per_provider={"vast": 2}, destroy_pending_per_provider={"vast": 1})
    )
    assert 'gpu_rent_active{provider="vast"} 2' in text
    assert 'gpu_rent_active{provider="runpod"} 0' not in text
    assert 'gpu_rent_destroy_pending{provider="vast"} 1' in text
    assert 'gpu_rent_destroy_pending{provider="runpod"} 0' not in text


def test_render_infinite_age_uses_prometheus_spelling():
    text = gpu_metrics.render(_metrics(last_reconcile_age_seconds=math.inf))
    assert "gpu_rent_last_reconcile_age_seconds +Inf" in text
    assert "inf\n" not in text.replace("+Inf", "")


def test_render_escapes_hostile_label_values():
    text = gpu_metrics.render(_metrics(active_per_provider={'we"ird\nname': 1}))
    assert 'gpu_rent_active{provider="we\\"ird\\nname"} 1' in text


def test_render_none_calls_collect(monkeypatch):
    monkeypatch.setattr(gpu_metrics, "collect", lambda: _metrics(active_per_provider={"zz": 7}))
    assert 'gpu_rent_active{provider="zz"} 7' in gpu_metrics.render()


def test_render_end_to_end_from_collect(env):
    log, state = env
    _write_log(
        log,
        [
            {
                "provider": "runpod",
                "kind": "pod",
                "workload": "w",
                "success": True,
                "cost_actual_usd": 2.0,
            }
        ],
    )
    state["sessions"] = {"a": {"provider": "runpod", "destroy_pending": True}}
    text = gpu_metrics.render()
    assert 'gpu_rent_cost_usd_total{provider="runpod",kind="pod",workload="w"} 2.0' in text
    assert 'gpu_rent_destroy_pending{provider="runpod"} 1' in text
    assert "gpu_rent_last_reconcile_age_seconds +Inf" in text


# ---- write_textfile --------------------------------------------------------


def test_write_textfile_creates_parent_and_returns_path(env, tmp_path):
    out = gpu_metrics.write_textfile()
    assert out == tmp_path / "logs" / "m.prom"
    assert out.read_text() == gpu_metrics.render()


def test_write_textfile_leaves_no_tmp_and_overwrites(env, tmp_path):
    gpu_metrics.METRICS_FILE.parent.mkdir(parents=True)
    gpu_metrics.METRICS_FILE.write_text("stale")
    gpu_metrics.write_textfile()
    assert "stale" not in gpu_metrics.METRICS_FILE.read_text()
    assert not list((tmp_path / "logs").glob("*.tmp"))


def test_write_textfile_propagates_render_error(env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("render failed")

    monkeypatch.setattr(gpu_metrics, "render", boom)
    with pytest.raises(RuntimeError, match="render failed"):
        gpu_metrics.write_textfile()
