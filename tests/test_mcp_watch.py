# AFTER-EDIT: .claude/hooks/mcp_watch.py | none
"""D-041 per-message MCP forcing layer — staleness + cached-liveness banners."""
import importlib.util
import json
import sys
import time
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "mcp_watch", Path(__file__).resolve().parent.parent / ".claude/hooks/mcp_watch.py")
watch = importlib.util.module_from_spec(_spec)
sys.modules["mcp_watch"] = watch
_spec.loader.exec_module(watch)


def test_stale_config_detected(tmp_path):
    (tmp_path / ".mcp.json").write_text("{}")
    past = time.time() - 3600
    assert watch.stale_configs(str(tmp_path), past) and "repo .mcp.json" in watch.stale_configs(str(tmp_path), past)[0]
    future = time.time() + 3600
    assert all("repo" not in s for s in watch.stale_configs(str(tmp_path), future))


def test_cache_read_shapes(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "_CACHE_DIR", tmp_path)
    f = watch._cache_file("/opt/x")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"ts": time.time(), "report": {"exa": "CONNECTED", "serena": "DEAD"}}))
    c = watch.read_cache("/opt/x")
    assert c and c["report"]["serena"] == "DEAD"
    f.write_text("garbage{")
    assert watch.read_cache("/opt/x") is None


# ── the banner is a RATIO shown to every session; both halves must mean the same ──

def test_skipped_excluded_from_both_halves_of_the_ratio():
    """Live shape (2026-08-30): 15 assigned, grafana SKIPPED (docker-run, unprobed),
    maestro genuinely dead. The banner said '1/15' — numerator over 14 measured
    servers, denominator over 15 assigned. Unprobed is not dead, and it is not a
    denominator either."""
    report = {f"s{i}": "CONNECTED" for i in range(13)}
    report["grafana"] = "SKIPPED (docker-run entry — probe would launch a live container)"
    report["maestro"] = "TIMEOUT"
    b = watch.liveness_banner(report, 5)
    assert "1/14 probed" in b, f"denominator must exclude the unprobed entry: {b}"
    assert "grafana" not in b, "an unprobed server is never named as dead"
    assert "maestro" in b


def test_all_connected_plus_a_skip_raises_no_banner():
    """A skip alone must never fire the fix-first mandate — that was the false alarm."""
    report = {"exa": "CONNECTED", "grafana": "SKIPPED (docker-run entry)"}
    assert watch.liveness_banner(report, 1) is None


def test_a_real_death_still_banners():
    assert "1/1 probed" in watch.liveness_banner({"serena": "DEAD"}, 0)
