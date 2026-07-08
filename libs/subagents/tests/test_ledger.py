"""Phase D — ledger.py: durable append-only JSONL provenance store.

Highest-risk: durability (a fresh reader sees every appended record) and that a
record NEVER carries a secret.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

from subagents.ledger import Ledger, agent_record


def test_append_is_durable_jsonl(tmp_path: Path) -> None:
    path = str(tmp_path / "ledger.jsonl")
    Ledger(path).append({"a": 1})
    Ledger(path).append({"b": 2})

    # a fresh reader sees both, in order
    records = Ledger(path).read_all()
    assert records == [{"a": 1}, {"b": 2}]

    # the file is valid JSONL (each line parses independently)
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    assert [json.loads(ln) for ln in lines] == [{"a": 1}, {"b": 2}]


def test_read_all_missing_file_is_empty(tmp_path: Path) -> None:
    assert Ledger(str(tmp_path / "nope.jsonl")).read_all() == []


def test_ledger_creates_parent_dirs(tmp_path: Path) -> None:
    path = str(tmp_path / "deep" / "nested" / "ledger.jsonl")
    Ledger(path).append({"x": 1})
    assert Path(path).exists()


def test_agent_record_excludes_secrets(tmp_path: Path) -> None:
    """A record is a whitelist — a secret attribute on the spec never leaks in."""
    spec = SimpleNamespace(
        task="do the thing",
        model="anthropic/claude",
        owned_paths=["src/*.py"],
        api_key="sk-SECRET-DO-NOT-LOG",  # must NOT be serialized
        system="secret system prompt with sk-SECRET-DO-NOT-LOG",
    )
    result = SimpleNamespace(
        agent_id="agent-1",
        status="done",
        provider="anthropic",
        cost_usd=0.01,
        turns=3,
        diff="+++ b/src/a.py\n+x\n",
        error=None,
        text="secret leaked? sk-SECRET-DO-NOT-LOG",
    )

    record = agent_record(spec, result)
    blob = json.dumps(record)

    assert "sk-SECRET-DO-NOT-LOG" not in blob, "a secret leaked into the ledger record"
    assert "api_key" not in record
    assert "system" not in record  # system prompt is not part of the provenance record
    assert "text" not in record
    # but the useful provenance IS there
    assert record["task"] == "do the thing"
    assert record["status"] == "done"
    assert record["owned_paths"] == ["src/*.py"]
    assert "ts" in record


def test_agent_record_is_json_serializable(tmp_path: Path) -> None:
    spec = SimpleNamespace(task="t", model="m", owned_paths=[])
    result = SimpleNamespace(
        agent_id="a",
        status="error",
        provider=None,
        cost_usd=None,
        turns=0,
        diff="",
        error="boom",
    )
    path = str(tmp_path / "l.jsonl")
    led = Ledger(path)
    led.append(agent_record(spec, result))
    assert led.read_all()[0]["error"] == "boom"


def test_read_all_tolerates_corrupt_line(tmp_path: Path) -> None:
    """A crash-truncated tail line is skipped, not fatal to the whole read."""
    path = Path(tmp_path / "l.jsonl")
    led = Ledger(str(path))
    led.append({"ok": 1})
    led.append({"ok": 2})
    # a crash mid-write leaves a partial final line (no trailing newline)
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"truncated": ')
    records = led.read_all()
    assert records == [
        {"ok": 1},
        {"ok": 2},
    ]  # good records intact, partial tail skipped


def test_agent_record_redacts_secret_in_error(tmp_path: Path) -> None:
    """A token accidentally embedded in a transport error string is redacted before
    it lands in the durable on-disk log."""
    spec = SimpleNamespace(task="t", model="m", owned_paths=[])
    result = SimpleNamespace(
        agent_id="a",
        status="error",
        provider=None,
        cost_usd=None,
        turns=0,
        diff="",
        error="401 from https://x — Bearer sk-live-ABCDEF123456 rejected",
    )
    rec = agent_record(spec, result)
    assert "sk-live-ABCDEF123456" not in rec["error"]
    assert "redacted" in rec["error"]


def test_agent_record_truncates_huge_diff(tmp_path: Path) -> None:
    from types import SimpleNamespace

    spec = SimpleNamespace(task="t", model="m", owned_paths=[])
    result = SimpleNamespace(
        agent_id="a",
        status="done",
        provider=None,
        cost_usd=None,
        turns=1,
        diff="x" * 500_000,
        error=None,
    )
    rec = agent_record(spec, result)
    assert len(rec["diff"]) < 200_000
    assert "truncated" in rec["diff"]


def test_concurrent_appends_are_line_atomic(tmp_path: Path) -> None:
    """Parallel appends never interleave into a corrupt line."""
    path = str(tmp_path / "concurrent.jsonl")
    led = Ledger(path)

    def worker(i: int) -> None:
        led.append({"i": i, "payload": "x" * 500})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    records = led.read_all()
    assert len(records) == 20
    assert sorted(r["i"] for r in records) == list(range(20))
