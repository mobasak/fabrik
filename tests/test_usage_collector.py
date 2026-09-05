"""Behavior contract for the transcript collector — the thing that outlives the Claude Manager extension.

WHY IT EXISTS, measured rather than assumed: `~/.claude/.claude-manager/usage-history.json` is written
by an EXTENSION, and on 2026-09-04 17:31 it stopped while usage carried on. The store froze with it.
Claude Code's own transcripts under `~/.claude/projects/**/*.jsonl` are the primary record — every
assistant message carries its own `usage` block — and they are written whether or not any extension
is installed.

THE ASYMMETRY THIS SUITE PINS. The transcripts are a better record of the PRESENT and a WORSE one of
the past: measured across all 112 overlapping days they hold a median 0.54x the extension's tokens
(186.8B vs 298.1B), because session files are pruned as they age. So the merge fills days the
extension never recorded and NEVER rewrites one it did — re-deriving history from transcripts would
delete ~111B tokens of it. The overlap is published as `_discrepancy` instead, and the corollary is
that this collector must run daily: it can only capture a day while that day's transcripts exist.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "claude_p_cost.py"
_spec = importlib.util.spec_from_file_location("claude_p_cost_collector", _MOD)
cpc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpc)


def _msg(day: str, model: str, mid: str, req: str, tok: int, *, sidechain: bool = False) -> str:
    """One assistant record in Claude Code's transcript shape."""
    return json.dumps(
        {
            "timestamp": f"{day}T10:00:00.000Z",
            "requestId": req,
            "isSidechain": sidechain,
            "message": {
                "id": mid,
                "model": model,
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "cache_read_input_tokens": tok - 3,
                    "cache_creation_input_tokens": 1,
                },
            },
        }
    )


def _tree(tmp_path: Path, files: dict[str, list[str]]) -> Path:
    root = tmp_path / "projects"
    for name, lines in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def test_it_sums_per_day_per_model_from_the_transcripts(tmp_path):
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                _msg("2026-09-05", "claude-opus-5", "m1", "r1", 1000),
                _msg("2026-09-05", "claude-sonnet-5", "m2", "r2", 500),
                _msg("2026-09-06", "claude-opus-5", "m3", "r3", 700),
            ]
        },
    )
    got = cpc.collect_from_transcripts(root)
    assert got == {
        "2026-09-05": {"claude-opus-5": 1000, "claude-sonnet-5": 500},
        "2026-09-06": {"claude-opus-5": 700},
    }


def test_a_message_replayed_into_another_session_file_is_counted_once(tmp_path):
    """Resume and compaction copy earlier messages into a NEW file. Without the (id, requestId)
    dedup the same spend is counted per copy — the walk over-reports and every rate derived from it
    is wrong in the same direction."""
    line = _msg("2026-09-05", "claude-opus-5", "m1", "r1", 1000)
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/original.jsonl": [line],
            "-opt-fabrik/resumed.jsonl": [
                line,
                _msg("2026-09-05", "claude-opus-5", "m2", "r2", 40),
            ],
        },
    )
    assert cpc.collect_from_transcripts(root) == {"2026-09-05": {"claude-opus-5": 1040}}


def test_subagent_sidechain_tokens_are_COUNTED(tmp_path):
    """They bill to the same subscription. The question this store answers is what the subscription
    was spent on, not what the operator typed — and fan-out is a large part of the answer."""
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                _msg("2026-09-05", "claude-opus-5", "m1", "r1", 100),
                _msg("2026-09-05", "claude-opus-5", "m2", "r2", 900, sidechain=True),
            ]
        },
    )
    assert cpc.collect_from_transcripts(root) == {"2026-09-05": {"claude-opus-5": 1000}}


def test_junk_lines_never_raise_and_never_count(tmp_path):
    """A transcript is appended to live: the tail can be a half-written line, and older records carry
    shapes this reader has never seen. Never raises is the contract."""
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                '{"message":{"usage":',  # truncated mid-write
                '{"message": {"usage": {"input_tokens": 5}}}',  # no timestamp
                '{"timestamp":"2026-09-05T10:00:00Z","message":{"usage":{"input_tokens":5}}}',  # no model
                '{"timestamp":"not-a-date","message":{"id":"x","model":"claude-opus-5","usage":{"input_tokens":5}}}',
                '{"timestamp":"2026-09-05T10:00:00Z","message":{"id":"z","model":"claude-opus-5","usage":{}}}',
                _msg("2026-09-05", "claude-opus-5", "ok", "rok", 10),
            ]
        },
    )
    assert cpc.collect_from_transcripts(root) == {"2026-09-05": {"claude-opus-5": 10}}


def test_a_missing_transcript_root_is_empty_not_an_error(tmp_path):
    assert cpc.collect_from_transcripts(tmp_path / "nope") == {}


def _store(tmp_path, monkeypatch, days: dict, source_by_day: dict | None = None) -> Path:
    p = tmp_path / "store.json"
    body: dict = {"days": days}
    if source_by_day is not None:
        body["source_by_day"] = source_by_day
    p.write_text(json.dumps(body), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_USAGE_DAILY", str(p))
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", tmp_path / "no-extension-file.json")
    return p


def test_the_merge_fills_days_the_extension_never_recorded(tmp_path, monkeypatch):
    """The live failure this was built for: the extension's file stops, and without the transcripts
    the store simply stops gaining days."""
    _store(
        tmp_path, monkeypatch, {"2026-09-04": {"claude-opus-5": 111}}, {"2026-09-04": "extension"}
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-06", "claude-opus-5", "m9", "r9", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-06"] == {"claude-opus-5": 900}
    assert store["source_by_day"]["2026-09-06"] == "transcripts"
    assert store["_transcript_added"] == 1


def test_an_extension_recorded_day_is_NOT_rewritten_by_the_transcripts(tmp_path, monkeypatch):
    """The load-bearing one. The transcripts hold more for the same day, and adopting that silently
    would restate 111 days of the operator's dashboard by 2-3x with no decision taken. The overlap is
    PUBLISHED instead, so the re-derivation can be judged on measurement."""
    _store(
        tmp_path, monkeypatch, {"2026-09-04": {"claude-opus-5": 100}}, {"2026-09-04": "extension"}
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-04", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-04"] == {"claude-opus-5": 100}, "history must stand untouched"
    assert store["source_by_day"]["2026-09-04"] == "extension"
    assert store["_discrepancy"]["2026-09-04"] == {"extension": 100, "transcripts": 900}


def test_a_transcript_sourced_day_KEEPS_refreshing(tmp_path, monkeypatch):
    """Today is partial all day. A day this collector wrote must keep being rewritten by it, or the
    first run of the day freezes that day at breakfast."""
    _store(
        tmp_path, monkeypatch, {"2026-09-06": {"claude-opus-5": 100}}, {"2026-09-06": "transcripts"}
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-06", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-06"] == {"claude-opus-5": 900}
    assert store["_transcript_refreshed"] == 1


def test_a_day_with_no_recorded_source_is_treated_as_history(tmp_path, monkeypatch):
    """Every day already in the store predates `source_by_day` and came from the extension. An absent
    marker must therefore read as "leave it alone", never as "mine to overwrite" — the fail direction
    that protects data rather than the one that rewrites it."""
    _store(tmp_path, monkeypatch, {"2026-08-01": {"claude-opus-5": 100}})  # no source_by_day at all
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-08-01", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-08-01"] == {"claude-opus-5": 100}


def test_the_calendar_reaches_today_once_the_collector_runs(tmp_path, monkeypatch):
    """End to end: the reason any of this exists is that the Usage tab stopped gaining days."""
    today = datetime.date.today().isoformat()
    _store(tmp_path, monkeypatch, {})
    monkeypatch.setattr(cpc, "_MANAGER_ACCOUNTS", tmp_path / "no-accounts")
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg(today, "claude-opus-5", "m1", "r1", 5_000_000)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    daily = cpc.per_model_spend()["daily"]

    assert daily[-1]["date"] == today and daily[-1]["tokens"] == 5_000_000
