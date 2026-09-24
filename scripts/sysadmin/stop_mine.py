#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/hooks-index.md, docs/reference/thread-anchors.md, docs/workstation/kaizen-event-stream.md
"""stop_mine — the promoted research miner (spec 2026-09-23-stop-and-compaction-enforcement-design
§ Cost, § Validation V1). Was `docs/reference/research/2026-09-23-stop-compaction/mine.py`; this
copy shares the Stop hook's own DEFERRAL vocabulary instead of a hand-rolled one, so a reworded
deferral shows up as a FALLING FIRE RATE rather than a silent miss (the COBRA counter-measure the
hook's own comment names, `.claude/hooks/final_gate_stop.py:1508-1512`).

Population: every top-level ``<root>/<repo>/<session>.jsonl`` (a subagent's transcript lives
deeper and never matches this one-level glob; an INLINE subagent sidechain row — ``isSidechain``
truthy — is skipped too). A TURN END is the last non-empty assistant text entry before the next
*real* user entry — never a tool result, an ``isMeta`` command expansion or a compaction summary,
the same test the hook's own :func:`_is_operator_row` makes, reused here by reference. A whole
session is excluded when any of its real user rows carries an ``sdk-*`` entrypoint (headless — no
operator to defer to): that mirrors the TRANSCRIPT half of the hook's own
:func:`_is_headless`, deliberately WITHOUT its ``CLAUDE_MESH_HEADLESS`` environment branch — that
branch answers "is the process running ME right now headless", which says nothing about a mined
session launched somewhere else, at some other time, under someone else's shell.

``--backtest`` reports the fire rate, per shape and per repo (spec § Validation V1's first
bullet). It counts; it never JUDGES — the judged-sample check against the committed
``docs/reference/research/2026-09-23-stop-compaction/verdict-*.json`` files already lives in
``tests/test_final_gate_stop_deferral.py`` (built with T03), and the day-7/14 outcome audit is
T06's (spec V4/V6).

    python3 scripts/sysadmin/stop_mine.py --root <projects-tree> --since 2026-08-09 --backtest
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]  # scripts/sysadmin/stop_mine.py -> repo root
_HOOK_PATH = _REPO_ROOT / ".claude" / "hooks" / "final_gate_stop.py"

_HOOK: ModuleType | None = None
_HOOK_ERR: str | None = None


def _hook() -> ModuleType:
    """The Stop hook, imported BY PATH — once per process; a failure is cached and re-raised.

    `_DEFER_RE` and `deferral_shape` below are ATTRIBUTE references onto this loaded module,
    never a re-implementation (the T03 -> T05 seam; `tests/test_stop_mine.py`)."""
    global _HOOK, _HOOK_ERR
    if _HOOK is not None:
        return _HOOK
    if _HOOK_ERR is not None:
        raise ImportError(_HOOK_ERR)
    try:
        spec = importlib.util.spec_from_file_location("_stop_mine_final_gate_stop", _HOOK_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {_HOOK_PATH}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        _HOOK_ERR = f"cannot import {_HOOK_PATH}: {type(e).__name__}: {e}"
        raise ImportError(_HOOK_ERR) from None
    _HOOK = mod
    return mod


# The ONE vocabulary (T03 -> T05 seam, spine `## Interfaces`): both names are attributes of the
# loaded hook module, not a copy of its regex text.
_DEFER_RE = _hook()._DEFER_RE
deferral_shape = _hook().deferral_shape


def _assistant_text(entry: dict[str, Any]) -> str:
    """Every text block of one assistant transcript row, joined in order — empty when the row is
    tool-use-only (no text block at all) or the row's shape is not what it claims to be."""
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text"
    )


def _session_headless(entry: dict[str, Any]) -> bool:
    """The TRANSCRIPT half of the hook's own `_is_headless` — an `sdk-*` entrypoint on a real
    user row — without its `CLAUDE_MESH_HEADLESS` environment check (that reads THIS process's
    env, not the mined session's own launch)."""
    ep = entry.get("entrypoint")
    return isinstance(ep, str) and ep.startswith("sdk-")


def _in_window(ts: str, since: str | None, until: str | None) -> bool:
    """Date-only (`YYYY-MM-DD`) comparison on the entry's own ISO timestamp — both bounds
    inclusive (A-O37: the research copy this promotes read only a lower bound). A timestamp-less
    entry is kept only when there is no lower bound to honor."""
    if not ts:
        return since is None
    day = ts[:10]
    if since is not None and day < since:
        return False
    return not (until is not None and day > until)


def mine(root: Path, *, since: str | None = None, until: str | None = None) -> dict[str, Any]:
    """Replay every interactive turn end under `root` and classify it with the hook's own
    `deferral_shape` (spec § Validation V1's first bullet: the fire rate, per shape and per
    repo). Each `<repo>/<session>.jsonl` is read line by line and fails OPEN per file — an
    unreadable file or a malformed line is skipped, never a crash of the whole run."""
    hook = _hook()
    files = sorted(root.glob("*/*.jsonl"))
    by_shape: collections.Counter[str] = collections.Counter()
    by_repo: dict[str, dict[str, Any]] = {}
    turn_ends = 0
    fires = 0
    headless_sessions = 0
    sidechain_rows_skipped = 0

    for path in files:
        repo = path.parent.name
        headless = False
        last_text: str | None = None
        pending: list[str] = []
        try:
            fh = path.open("rb")
        except OSError:
            continue
        with fh:
            for raw in fh:
                if b'"type"' not in raw:
                    continue
                try:
                    entry = json.loads(raw)
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("isSidechain"):
                        sidechain_rows_skipped += 1
                        continue
                    et = entry.get("type")
                    if et == "user":
                        if hook._is_operator_row(entry):
                            if not headless:
                                headless = _session_headless(entry)
                            if last_text is not None:
                                pending.append(last_text)
                            last_text = None
                        continue
                    if et == "assistant":
                        text = _assistant_text(entry)
                        if text.strip():
                            ts = str(entry.get("timestamp") or "")
                            last_text = text if _in_window(ts, since, until) else None
                except Exception:
                    # One malformed or unexpectedly-shaped row never disables the whole file's
                    # mining (fail-open PER LINE, spec's own "the miner reads line by line,
                    # fail-open per file" hardened one notch further).
                    continue
        if last_text is not None:
            pending.append(last_text)
        if headless:
            headless_sessions += 1
            continue
        if not pending:
            continue
        rec = by_repo.setdefault(
            repo, {"turn_ends": 0, "fires": 0, "by_shape": collections.Counter()}
        )
        for text in pending:
            turn_ends += 1
            rec["turn_ends"] += 1
            shape = deferral_shape(text)
            if shape:
                fires += 1
                rec["fires"] += 1
                rec["by_shape"][shape] += 1
                by_shape[shape] += 1

    by_repo_out = {
        r: {
            "turn_ends": rec["turn_ends"],
            "fires": rec["fires"],
            "by_shape": dict(rec["by_shape"]),
        }
        for r, rec in sorted(by_repo.items())
    }
    return {
        "root": str(root),
        "since": since,
        "until": until,
        "files": len(files),
        "headless_sessions": headless_sessions,
        "sidechain_rows_skipped": sidechain_rows_skipped,
        "turn_ends": turn_ends,
        "fires": fires,
        "fire_rate": round(fires / turn_ends, 4) if turn_ends else 0.0,
        "by_shape": dict(sorted(by_shape.items())),
        "by_repo": by_repo_out,
    }


def _format_report(stats: dict[str, Any]) -> str:
    """The human-readable V1 backtest block `--backtest` prints — fire rate, per shape and per
    repo (spec § Validation V1's first bullet)."""
    lines = [
        "V1 backtest — fire rate per shape and per repo",
        f"  window: since={stats['since'] or '(none)'} until={stats['until'] or '(none)'} — "
        f"{stats['files']} file(s), {stats['headless_sessions']} headless session(s) excluded",
        f"  overall: {stats['fires']}/{stats['turn_ends']} fired "
        f"({stats['fire_rate'] * 100:.1f}%)",
        "  by shape: "
        + (" ".join(f"{k} {v}" for k, v in stats["by_shape"].items()) or "(none fired)"),
        "  by repo:",
    ]
    for repo, rec in stats["by_repo"].items():
        rate = (rec["fires"] / rec["turn_ends"] * 100) if rec["turn_ends"] else 0.0
        shape_bits = " ".join(f"{k} {v}" for k, v in rec["by_shape"].items()) or "(none fired)"
        lines.append(
            f"    {repo}: {rec['fires']}/{rec['turn_ends']} fired ({rate:.1f}%) — {shape_bits}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--root", required=True, type=Path, help="the <repo>/<session>.jsonl population root"
    )
    p.add_argument("--since", default=None, help="YYYY-MM-DD, inclusive lower bound")
    p.add_argument("--until", default=None, help="YYYY-MM-DD, inclusive upper bound")
    p.add_argument("--backtest", action="store_true", help="print the V1 fire-rate report")
    p.add_argument("--out", default=None, type=Path, help="write the full stats JSON here")
    args = p.parse_args(argv)

    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"stop_mine: --root {root} is not a directory", file=sys.stderr)
        return 2

    stats = mine(root, since=args.since, until=args.until)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(stats, indent=1))
    summary = {
        k: stats[k]
        for k in ("root", "since", "until", "files", "headless_sessions", "turn_ends", "fires", "fire_rate")
    }
    print(json.dumps(summary))
    if args.backtest:
        print(_format_report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
