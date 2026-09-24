#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/hooks-index.md, docs/reference/thread-anchors.md, docs/workstation/kaizen-event-stream.md
"""stop_mine — the promoted research miner (spec 2026-09-23-stop-and-compaction-enforcement-design
§ Cost, § Validation V1). Was `docs/reference/research/2026-09-23-stop-compaction/mine.py`; this
copy shares the Stop hook's own DEFERRAL vocabulary instead of a hand-rolled one, so a reworded
deferral shows up as a FALLING FIRE RATE rather than a silent miss (the COBRA counter-measure the
hook's own comment names, `.claude/hooks/final_gate_stop.py:1508-1512`).

**Parity with the hook is the contract — the hook's own rules are the truth, this miner's job is
to replay them over history, never to approximate them:**

- Population: every top-level ``<root>/<repo>/<session>.jsonl`` (a subagent's transcript lives
  deeper and never matches this one-level glob; an INLINE subagent sidechain row —
  ``isSidechain`` truthy — is skipped too). A non-regular path (a directory literally named
  ``x.jsonl``, a FIFO, a socket) is skipped and reported, never opened.
- A TURN END is the last non-empty assistant text entry before the next row that is real
  OPERATOR TEXT by the hook's own :func:`_operator_text` — never a tool result, an ``isMeta``
  expansion, a compaction summary, or a harness row (``<system-reminder>``, ``Stop hook
  feedback:``, …) with nothing left after stripping.
- HEADLESS is decided PER TURN END, exactly like the hook's own :func:`_is_headless`: the LAST
  real operator row (:func:`_is_operator_row`, structural — independent of whether it carries
  operator TEXT) at or before that turn end's opening prompt carries an ``sdk-*`` entrypoint. A
  session that starts ``sdk-cli`` and later continues interactively excludes only its headless
  turn ends, never the whole session — deliberately WITHOUT the hook's own
  ``CLAUDE_MESH_HEADLESS`` environment branch, which answers "is the process running ME right now
  headless", not "was the mined session headless at that turn".
- The population window (``--since``/``--until``, both YYYY-MM-DD, both inclusive) compares the
  entry's own ISO timestamp on its UTC CALENDAR DATE — an ISO offset is converted to UTC first, so
  a ``+03:00`` stamp near midnight lands on the correct day, never a naive slice of the string.

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
import re
import sys
from datetime import UTC, datetime
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
    tool-use-only (no text block at all) or the row's shape is not what it claims to be. A bare
    STRING `message.content` is text as-is (A-S4: the hook's own `_operator_text` treats a string
    content the same way; assistant rows mirror that instead of silently reading "")."""
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text"
    )


def _row_is_headless(entry: dict[str, Any]) -> bool:
    """The TRANSCRIPT half of the hook's own `_is_headless` — an `sdk-*` entrypoint on a real
    user row — without its `CLAUDE_MESH_HEADLESS` environment check (that reads THIS process's
    env, not the mined session's own launch)."""
    ep = entry.get("entrypoint")
    return isinstance(ep, str) and ep.startswith("sdk-")


def _utc_date(ts: str) -> str | None:
    """The ISO timestamp's calendar date, converted to UTC first (A-O2/A-O3) — a `+03:00` stamp
    near midnight must not land on the wrong day by a naive string slice. None when `ts` is
    missing or unparsable."""
    if not ts:
        return None
    s = ts.strip()
    if s[-1:] in ("Z", "z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).date().isoformat()


def _in_window(ts: str, since: str | None, until: str | None) -> bool:
    """Both bounds inclusive (A-O4/A-S3), compared on the timestamp's UTC calendar date. A
    timestamp this cannot parse is kept only when NEITHER bound is set — an unverifiable date
    must never silently pass a real window."""
    if since is None and until is None:
        return True
    day = _utc_date(ts)
    if day is None:
        return False
    if since is not None and day < since:
        return False
    return not (until is not None and day > until)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date_arg(value: str) -> str:
    """argparse `type=` for `--since`/`--until` (A-O2): strict `YYYY-MM-DD`, and a real calendar
    date (`2026-13-40` is the right shape and still not a date)."""
    if not _DATE_RE.match(value):
        raise argparse.ArgumentTypeError(f"{value!r} is not YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"{value!r} is not a valid calendar date: {e}") from e
    return value


def mine(root: Path, *, since: str | None = None, until: str | None = None) -> dict[str, Any]:
    """Replay every interactive turn end under `root` and classify it with the hook's own
    `deferral_shape` (spec § Validation V1's first bullet: the fire rate, per shape and per
    repo). Each `<repo>/<session>.jsonl` is opened and read line by line INSIDE one try — a
    non-regular path, an unreadable file, a bad-encoding read, a malformed line or an
    unexpectedly-shaped row is skipped (A-S2/A-O5/A-O8), never a crash of the whole run."""
    hook = _hook()
    all_paths = sorted(root.glob("*/*.jsonl"))
    by_shape: collections.Counter[str] = collections.Counter()
    by_repo: dict[str, dict[str, Any]] = {}
    turn_ends = 0
    fires = 0
    headless_turn_ends = 0
    sidechain_rows_skipped = 0
    skipped_files = 0
    mined_files = 0

    for path in all_paths:
        if not path.is_file():
            skipped_files += 1
            continue
        repo = path.parent.name
        last_operator_headless = False
        last_turn: tuple[str, bool] | None = None  # (text, headless-at-open)
        pending: list[tuple[str, bool]] = []
        try:
            with path.open("rb") as fh:
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
                                last_operator_headless = _row_is_headless(entry)
                            if hook._operator_text(entry):
                                if last_turn is not None:
                                    pending.append(last_turn)
                                last_turn = None
                            continue
                        if et == "assistant":
                            text = _assistant_text(entry)
                            if text.strip():
                                ts = str(entry.get("timestamp") or "")
                                last_turn = (
                                    (text, last_operator_headless)
                                    if _in_window(ts, since, until)
                                    else None
                                )
                    except Exception:
                        # One malformed or unexpectedly-shaped row never disables the whole
                        # file's mining (fail-open PER LINE, A-S2/A-O5).
                        continue
        except (OSError, ValueError):
            skipped_files += 1
            continue
        mined_files += 1
        if last_turn is not None:
            pending.append(last_turn)
        if not pending:
            continue
        rec = by_repo.setdefault(
            repo, {"turn_ends": 0, "fires": 0, "by_shape": collections.Counter()}
        )
        for text, headless in pending:
            if headless:
                headless_turn_ends += 1
                continue
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
        "files": mined_files,
        "skipped_files": skipped_files,
        "headless_turn_ends": headless_turn_ends,
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
        f"{stats['files']} file(s) mined, {stats['skipped_files']} skipped, "
        f"{stats['headless_turn_ends']} headless turn end(s) excluded",
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
    p.add_argument("--since", default=None, type=_date_arg, help="YYYY-MM-DD, inclusive lower bound")
    p.add_argument("--until", default=None, type=_date_arg, help="YYYY-MM-DD, inclusive upper bound")
    p.add_argument("--backtest", action="store_true", help="print the V1 fire-rate report")
    p.add_argument("--out", default=None, type=Path, help="write the full stats JSON here")
    args = p.parse_args(argv)

    if args.since is not None and args.until is not None and args.since > args.until:
        print(f"stop_mine: --since {args.since} is after --until {args.until}", file=sys.stderr)
        return 2

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
        for k in (
            "root",
            "since",
            "until",
            "files",
            "skipped_files",
            "headless_turn_ends",
            "turn_ends",
            "fires",
            "fire_rate",
        )
    }
    print(json.dumps(summary))
    if args.backtest:
        print(_format_report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
