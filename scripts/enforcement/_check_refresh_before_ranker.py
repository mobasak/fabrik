#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/daily_refresh.sh, scripts/wsl_startup_hook.sh (the two entry points this asserts the shape of) | tests/test_refresh_before_ranker.py
"""Assert the cost-sidecar rebuild runs BEFORE the ranking regen — in BOTH pipeline entry points.

`rank_task_subagents.py` renders the amortized rate from `claude_p_cost.json` into
`TASK_SUBAGENT_SELECTION.md`, the doc `pick_models` reads fleet-wide. A rebuild wired AFTER it
publishes the previous day's figure for a full cycle. Phase C of
`docs/development/plans/2026-09-05-plan-1-windowed-cost-sidecar.md`.

⚠️ TWO ENTRY POINTS, NOT ONE — and wiring only one is a documented repeat offence here.
`daily_refresh.sh` (cron, 06:00) and `wsl_startup_hook.sh` (boot) BOTH run the ranker, so a step
wired into one of them is absent from the other's pipeline. `wsl_startup_hook.sh:216-232` records two
earlier instances of exactly this asymmetry; the Phase-C commit `5fd58526` shipped a third by wiring
the refresh into the cron path alone.

⚠️ THE MECHANISM IS NOT A RACE, and the first version of this docstring said it was — inheriting the
belief from `:216-218` and propagating it into five new surfaces before a finder disproved it. The
shared daily lock `/tmp/.fabrik_daily_<UTC>` only makes the two exclusive WITHIN one uptime: `/tmp` is
cleared at boot (`/usr/lib/tmpfiles.d/tmp.conf`), so a reboot drops the lock and both run. Measured
2026-09-04 — the cron completed 03:08 UTC and the boot pipeline 17:49 UTC the SAME day, with zero
"already ran today" lines in any retained log. That makes wiring both paths MORE necessary, not less:
the boot path runs on every boot, not only on days the cron loses.

WHAT IS MATCHED, and why it is not shell-aware. A line counts as an invocation when its logical line
(continuations joined) names the SCRIPT PATH — `claude_p_cost.py` plus the `--refresh` flag for the
rebuild, `rank_task_subagents.py` for the ranker — outside a comment and outside a here-doc body.

Three deliberate choices, each bought by a defect an author-blind pass demonstrated on the previous
revision of this file:

  * THE FLAG IS REQUIRED. Matching the bare substring `claude_p_cost` let a step that merely READS
    the sidecar satisfy the gate — a false green on the exact condition it exists to prevent, since
    without `--refresh` the module falls through to stdin and writes nothing.
  * THE `.py` IS REQUIRED, and the `_step` prefix is NOT. Anchoring on `lstrip().startswith("_step")`
    both false-RED the boot path (which invokes the interpreter directly, with no `_step` at all) and
    false-RED a legitimately line-wrapped step; anchoring on the bare name let a step LABEL
    (`_step "verify_rank_task_subagents_inputs"`) win `next()` and report a nonsense ordering.
  * QUOTES ARE NOT TRACKED, on purpose. `wsl_startup_hook.sh:162` opens `nohup bash -c "` and its
    ENTIRE pipeline body — every line this gate must read — lives inside that double-quoted string.
    A quote-aware matcher would therefore skip the whole boot path and report green on an empty
    reading. The residual is honest and stated rather than papered over: a line sitting inside some
    OTHER quoted string can still be counted. Here-docs ARE skipped (unambiguous, and cheap).

Exit 0 = every present entry point is correctly ordered. Exit 1 = missing or out of order in at
least one. Exit 2 = neither entry point exists (wrong repo, or run from the wrong directory).
"""

from __future__ import annotations

import pathlib
import re
import sys

# Anchored on THIS file, never on the caller's cwd: the previous revision resolved a relative path
# and so exit-2'd from any directory but the repo root — or, on a box carrying subagent worktrees,
# silently checked a DIFFERENT copy of the script.
_REPO = pathlib.Path(__file__).resolve().parent.parent.parent

_ENTRY_POINTS = (
    "scripts/kilo-benchmarks/daily_refresh.sh",
    "scripts/wsl_startup_hook.sh",
)

_HEREDOC = re.compile(r"<<-?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?")


def _strip_trailing_comment(raw: str) -> str:
    """Drop a trailing `# …` comment, respecting quotes.

    Quote state is tracked HERE and nowhere else, and the distinction matters: the module refuses to
    track quotes for MATCHING (the boot hook's whole body lives inside one `bash -c "…"`, so a
    quote-aware matcher would see nothing), but a `#` inside quotes is data — a URL fragment, a colour
    literal — and cutting there would truncate a real command. Tracking it for this one purpose is
    local and cannot blind the matcher, because the enclosing string's own quote opens before any
    line this function sees.
    """
    out, quote = [], ""
    for i, c in enumerate(raw):
        if quote:
            if c == quote and raw[i - 1 : i] != "\\":
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == "#" and (not out or out[-1].isspace()):
            break
        out.append(c)
    return "".join(out)


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """(1-based start line, joined text) for each executable logical line.

    Continuations are joined so a wrapped command is one line; comment lines and here-doc BODIES are
    dropped. Quotes are deliberately not tracked — see the module docstring.
    """
    out: list[tuple[int, str]] = []
    delim: str | None = None
    buf: list[str] = []
    start = 0
    for n, raw in enumerate(text.splitlines(), 1):
        if delim is not None:  # inside a here-doc body
            if raw.strip() == delim:
                delim = None
            continue
        # TRAILING comments too, not just whole-line ones: `_step "noop" … # TODO: wire
        # claude_p_cost.py --refresh here` false-GREENED the gate while nothing rebuilt, and both
        # entry points are unusually comment-dense (362 and 187 whole-line comments). Split on an
        # unquoted `#` only — a `#` inside quotes is data (URL fragments, colour literals), and
        # stripping it would truncate real commands.
        raw = _strip_trailing_comment(raw)
        stripped = raw.strip()
        if not buf and not stripped:
            continue
        if not buf:
            start = n
        if raw.rstrip().endswith("\\"):
            buf.append(raw.rstrip()[:-1])
            continue
        buf.append(raw)
        joined = " ".join(buf)
        buf = []
        # a here-doc opened on this logical line swallows the following lines
        m = _HEREDOC.search(joined)
        if m:
            delim = m.group(1)
        out.append((start, joined))
    if buf:  # a trailing continuation with no terminator
        out.append((start, " ".join(buf)))
    return out


def _site(lines: list[tuple[int, str]], *tokens: str) -> int | None:
    """First logical line containing EVERY token; its 1-based physical start line."""
    return next((n for n, text in lines if all(t in text for t in tokens)), None)


def _check(rel: str) -> tuple[bool, str]:
    """(ok, message) for one entry point. A file that does not exist is not this gate's business."""
    path = _REPO / rel
    lines = _logical_lines(path.read_text(encoding="utf-8"))
    refresh = _site(lines, "claude_p_cost.py", "--refresh")
    ranker = _site(lines, "rank_task_subagents.py")
    if ranker is None:
        return False, (
            f"{rel}: no invocation of rank_task_subagents.py — the ranking is never regenerated "
            "here, so pick_models reads whatever the selection doc last happened to contain"
        )
    if refresh is None:
        return False, (
            f"{rel}: runs rank_task_subagents.py at line {ranker} but never invokes "
            "`claude_p_cost.py --refresh` — this entry point ranks from a sidecar it did not "
            "rebuild. Both entry points run the ranker independently — the shared daily lock only "
            "makes them exclusive within one uptime, since /tmp is cleared at boot — so this "
            "path ranks from a stale sidecar every time it runs."
        )
    if refresh == ranker:
        return False, (
            f"{rel}: both run on one logical line at {refresh}, so their order cannot be read "
            "statically — split them into separate invocations"
        )
    if refresh > ranker:
        return False, (
            f"{rel}: the rebuild is at line {refresh}, rank_task_subagents.py at {ranker} — the "
            "rebuild must come FIRST, or the ranking renders the previous day's rate for a cycle"
        )
    return True, f"{rel}: rebuild at {refresh} precedes the ranking at {ranker}"


def main() -> int:
    present = [rel for rel in _ENTRY_POINTS if (_REPO / rel).is_file()]
    if not present:
        print(
            f"none of the pipeline entry points exist under {_REPO} "
            f"({', '.join(_ENTRY_POINTS)}) — wrong repo?",
            file=sys.stderr,
        )
        return 2
    failures = []
    for rel in present:
        ok, msg = _check(rel)
        (print(msg) if ok else failures.append(msg))
    for msg in failures:
        print(msg, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
