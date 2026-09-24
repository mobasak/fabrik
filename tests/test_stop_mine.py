"""stop_mine.py — the promoted research miner, sharing the Stop hook's own DEFERRAL vocabulary.

Ticket: docs/development/plans/2026-09-23-plan-1-stop-and-compaction/T05-stop-mine-and-docs.md.
Interface (T03 -> T05, spine `## Interfaces`): `.claude/hooks/final_gate_stop.py`'s `_DEFER_RE`
and `deferral_shape(text: str) -> str | None` are the ONE vocabulary the hook's DEFERRAL check
and this miner both count with — the COBRA counter-measure at hook `:1508-1512`: a reworded
deferral must show up as a falling fire rate, never a silent miss, which only holds if the miner
never re-implements the vocabulary. The seam test below proves that by IDENTITY.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "stop_mine.py"


def _load_stop_mine() -> ModuleType:
    spec = importlib.util.spec_from_file_location("stop_mine_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_miner_counts_with_the_hooks_vocabulary() -> None:
    """The T03 -> T05 seam: the miner's `_DEFER_RE` and `deferral_shape` ARE the hook's own
    objects — attribute references onto the loaded hook module, never a re-implementation that
    could drift the day the hook's vocabulary changes."""
    sm = _load_stop_mine()
    hook = sm._hook()
    assert sm._DEFER_RE is hook._DEFER_RE
    assert sm.deferral_shape is hook.deferral_shape


def _write(path: Path, *entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _asst(text: str, ts: str) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _user(text: str = "ok", ts: str = "2026-08-10T00:00:00.000Z", **extra: object) -> dict:
    return {
        "type": "user",
        "timestamp": ts,
        "message": {"content": [{"type": "text", "text": text}]},
        **extra,
    }


def test_the_backtest_counts_per_shape_and_per_repo(tmp_path: Path) -> None:
    """Two repos, one turn end per shape D1-D4, a benign true-negative turn end, a headless
    sdk-* session and an inline subagent sidechain — spec 2026-09-23 § Validation V1's first
    bullet ("report the fire rate, per shape and per repo"), and the population exclusions the
    ticket names (a subagent's sidechain row, a headless entrypoint's whole session)."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"

    # repo-a: D1, then D2, then a benign NEXT: none turn end that must not fire.
    _write(
        root / "repo-a" / "sess-a.jsonl",
        _asst(
            "Work is done for now.\n\nNEXT: operator decision — approve the migration",
            "2026-08-12T00:00:00.000Z",
        ),
        _user("thanks", "2026-08-12T00:01:00.000Z"),
        _asst(
            "Two paths remain.\n\n(a) ship now (b) wait for review\nWhich do you prefer?",
            "2026-08-12T00:02:00.000Z",
        ),
        _user("ship it", "2026-08-12T00:03:00.000Z"),
        _asst("DONE: shipped the widget.\n\nNEXT: none — terminal", "2026-08-12T00:04:00.000Z"),
        _user("great", "2026-08-12T00:05:00.000Z"),
    )
    # a headless sdk-* session, also in repo-a: its own D1 must not be counted anywhere.
    _write(
        root / "repo-a" / "sess-headless.jsonl",
        _asst("NEXT: operator decision — should never be counted", "2026-08-14T00:00:00.000Z"),
        _user("go", "2026-08-14T00:01:00.000Z", entrypoint="sdk-cli"),
    )
    # repo-b: D3, then D4 (dangling — no reply follows, the session's last turn end).
    _write(
        root / "repo-b" / "sess-b.jsonl",
        _asst("Should I proceed with the migration?", "2026-08-13T00:00:00.000Z"),
        _user("go ahead", "2026-08-13T00:01:00.000Z"),
        _asst(
            "The remaining migration needs a fresh session to finish it properly.",
            "2026-08-13T00:02:00.000Z",
        ),
    )
    # an inline subagent sidechain in repo-b: its D1 must not be counted either.
    _write(
        root / "repo-b" / "sess-b-side.jsonl",
        {
            **_asst("NEXT: operator decision — a subagent's own excuse", "2026-08-13T00:03:00.000Z"),
            "isSidechain": True,
        },
        _user("noted", "2026-08-13T00:04:00.000Z"),
    )

    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")

    assert stats["files"] == 4
    assert stats["headless_sessions"] == 1
    assert stats["turn_ends"] == 5  # D1, D2, benign (repo-a) + D3, D4 (repo-b)
    assert stats["fires"] == 4
    assert stats["by_shape"] == {"D1": 1, "D2": 1, "D3": 1, "D4": 1}
    assert stats["by_repo"]["repo-a"] == {
        "turn_ends": 3,
        "fires": 2,
        "by_shape": {"D1": 1, "D2": 1},
    }
    assert stats["by_repo"]["repo-b"] == {
        "turn_ends": 2,
        "fires": 2,
        "by_shape": {"D3": 1, "D4": 1},
    }


def test_a_turn_end_outside_the_window_is_not_counted(tmp_path: Path) -> None:
    """`--since`/`--until` bound the population on both sides (A-O37: the research copy only read
    a lower bound) — a turn end before `since` and one after `until` are both excluded."""
    sm = _load_stop_mine()
    root = tmp_path / "projects"
    _write(
        root / "repo-a" / "sess-a.jsonl",
        _asst("NEXT: operator decision — too early", "2026-07-01T00:00:00.000Z"),
        _user("ok", "2026-07-01T00:01:00.000Z"),
        _asst("NEXT: operator decision — inside the window", "2026-08-12T00:00:00.000Z"),
        _user("ok", "2026-08-12T00:01:00.000Z"),
        _asst("NEXT: operator decision — too late", "2026-10-01T00:00:00.000Z"),
        _user("ok", "2026-10-01T00:01:00.000Z"),
    )
    stats = sm.mine(root, since="2026-08-09", until="2026-09-23")
    assert stats["turn_ends"] == 1
    assert stats["fires"] == 1
    assert stats["by_shape"] == {"D1": 1}
