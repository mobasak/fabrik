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
