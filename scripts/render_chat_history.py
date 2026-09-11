#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/chat-history-render.md | tests/test_render_chat_history.py
"""Render a project's FULL Claude Code chat history to markdown — the "load more" the
VS Code panel does not have.

Why this exists (measured 2026-09-11, D-235): a reloaded VS Code window resumes a session
by walking the transcript's parent links from the newest record back to a root, and every
compaction writes a `compact_boundary` record with NO parent — a new root. So the panel
renders only what came after the LAST compaction; everything earlier is on disk but never
shown, and no reload, restart or setting changes that. This script reads the same
transcripts (`~/.claude/projects/<project-key>/<session>.jsonl`, shared by every rotated
account) and writes one readable markdown per session, every compaction a dated heading,
tool calls / tool results / hook injections stripped.

Usage:
  python3 scripts/render_chat_history.py --project /opt/trade-intelligence
  python3 scripts/render_chat_history.py --project trade-intelligence --name 1991fa9b=agent-1 --name 37887efc=agent-2
  python3 scripts/render_chat_history.py --all            # every project with transcripts

Output: ~/.claude/state/history/<project-key>/<session-name-or-id8>.md + INDEX.md per project.
Incremental: a session whose transcript has not changed since its last render is skipped.
Names persist in <project>/names.json so a later run without --name keeps them.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUT_ROOT = Path.home() / ".claude" / "state" / "history"

_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
_COMMAND_NAME = re.compile(r"<command-name>(.*?)</command-name>")
_SKIP_USER_PREFIXES = ("<task-notification>", "<local-command-caveat>", "<local-command-stdout>")


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "\n".join(parts)


def _stamp(record: dict) -> str:
    return str(record.get("timestamp") or "")[:19].replace("T", " ")


def _key_for(project: str) -> str:
    """Claude's project key: the absolute path with every non-alphanumeric run turned into '-'."""
    path = project if project.startswith("/") else f"/opt/{project}"
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def _iter_records(path: Path):
    with path.open("rb") as fh:
        for raw in fh:
            try:
                yield json.loads(raw)
            except ValueError:
                continue


def render_session(path: Path, out: Path, label: str) -> dict:
    """Write the markdown for one transcript; return its index row."""
    segments: list[str] = []
    lines: list[str] = []
    n_user = n_asst = 0
    first_ts = last_ts = ""
    for r in _iter_records(path):
        kind = r.get("type")
        ts = _stamp(r)
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        if kind == "system" and r.get("subtype") == "compact_boundary":
            meta = r.get("compactMetadata") or {}
            segments.append(ts)
            lines.append(
                f"\n\n---\n\n## ⟲ Compaction #{len(segments)} — {ts} "
                f"(trigger: {meta.get('trigger')}, {meta.get('preTokens')} tokens summarised)\n"
            )
            continue
        if kind == "user":
            if r.get("toolUseResult") is not None:
                continue
            content = (r.get("message") or {}).get("content")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            text = _SYSTEM_REMINDER.sub("", _text_of(content)).strip()
            if not text or text.startswith(_SKIP_USER_PREFIXES):
                continue
            if r.get("isCompactSummary"):
                lines.append(
                    f"\n### 📋 Compaction summary ({ts})\n\n<details><summary>summary text</summary>\n\n"
                    f"{text}\n\n</details>\n"
                )
                continue
            if r.get("isMeta"):
                continue
            text = _COMMAND_NAME.sub(r"`/\1`", text)
            n_user += 1
            lines.append(f"\n**🧑 You — {ts}**\n\n{text}\n")
        elif kind == "assistant":
            text = _text_of((r.get("message") or {}).get("content")).strip()
            if not text:
                continue
            n_asst += 1
            lines.append(f"\n**🤖 Claude — {ts}**\n\n{text}\n")
    if segments:
        marker = f"## ⟲ Compaction #{len(segments)} — {segments[-1]}"
        for i in range(len(lines) - 1, -1, -1):
            if marker in lines[i]:
                lines[i] = (
                    lines[i].rstrip("\n")
                    + "\n\n> ⚠️ A reloaded VS Code window starts HERE; everything above is invisible there.\n"
                )
                break
    head = (
        f"# {label} — {path.stem[:8]}\n\n"
        f"Source: `{path}`  \nSpan: {first_ts} → {last_ts} · compactions: {len(segments)} · "
        f"your messages: {n_user} · Claude replies: {n_asst}\n\n"
        "Every `## ⟲ Compaction` heading is a point where the live window was summarised. "
        "The VS Code panel shows only what follows the LAST one; this file is the rest.\n\n---\n"
    )
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(head + "".join(lines))
    os.replace(tmp, out)  # atomic: a failed write never truncates the previous render
    return {
        "label": label,
        "id": path.stem,
        "file": out.name,
        "first": first_ts,
        "last": last_ts,
        "compactions": len(segments),
        "user": n_user,
        "assistant": n_asst,
    }


_RESERVED_LABELS = frozenset({"INDEX", "names"})


def _safe_label(label: str) -> bool:
    """A label becomes `<label>.md` inside the project folder: one path segment, never hidden,
    never one of the folder's own files."""
    return (
        bool(label)
        and "/" not in label
        and not label.startswith(".")
        and label not in _RESERVED_LABELS
    )


def _is_entry(entry: object) -> bool:
    return isinstance(entry, dict) and isinstance(entry.get("row"), dict) and "file" in entry["row"]


def _load_json(path: Path) -> dict:
    """A missing, unreadable, malformed or non-object sidecar reads as empty — never a crash.

    A file that exists but is not a JSON object is moved aside to `<name>.bad-<stamp>` with a
    WARN, so a later write of the sidecar never silently discards what was there."""
    try:
        raw = path.read_text()
    except OSError:
        return {}
    try:
        loaded = json.loads(raw)
    except ValueError:
        loaded = None
    if isinstance(loaded, dict):
        return loaded
    kept = path.with_name(f"{path.name}.bad-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    try:
        os.replace(path, kept)
        print(f"WARN: {path} is not a JSON object; moved aside to {kept.name}", file=sys.stderr)
    except OSError as exc:
        print(
            f"WARN: {path} is not a JSON object and could not be moved aside: {exc}",
            file=sys.stderr,
        )
    return {}


def render_project(key: str, names: dict[str, str]) -> int:
    src = PROJECTS_DIR / key
    transcripts = sorted(src.glob("*.jsonl"))
    if not transcripts:
        print(f"ERROR: no transcripts under {src}", file=sys.stderr)
        return 1
    out_dir = OUT_ROOT / key
    out_dir.mkdir(parents=True, exist_ok=True)
    names_path = out_dir / "names.json"
    state_path = out_dir / ".render-state.json"
    stored_names = _load_json(names_path)
    stored_names.update(names)
    if stored_names != _load_json(names_path):
        names_path.write_text(json.dumps(stored_names, indent=2, sort_keys=True) + "\n")
    state = _load_json(state_path)
    rows: list[dict] = []
    rendered = failed = 0
    labels: dict[str, str] = {}
    for path in transcripts:
        sid = path.stem
        label = next((v for k, v in stored_names.items() if sid.startswith(k)), sid[:8])
        if not _safe_label(label):  # a hand-edited names.json must not escape the folder
            print(
                f"WARN: label {label!r} for {sid[:8]} is not a safe file name; using the id",
                file=sys.stderr,
            )
            label = sid[:8]
        prev_entry = state.get(sid)
        own = prev_entry["row"].get("file") if _is_entry(prev_entry) else None
        target = out_dir / f"{label}.md"
        # One label on two sessions — in this run, or against a render whose transcript is gone
        # (an orphan is the last copy of that conversation) — never one file for both.
        if label in labels.values() or (target.exists() and target.name != own):
            print(
                f"WARN: label {label!r} is already used; {sid[:8]} renders as {label}-{sid[:8]}",
                file=sys.stderr,
            )
            label = f"{label}-{sid[:8]}"
        labels[sid] = label
    taken = {f"{label}.md" for label in labels.values()}
    for path in transcripts:
        sid = path.stem
        label = labels[sid]
        out = out_dir / f"{label}.md"
        prev = state.get(sid)
        if not _is_entry(prev):  # a half-written state entry reads as "never rendered"
            prev = None
        try:  # one unreadable or vanished transcript must not abort the batch
            st = path.stat()
            sig = f"{st.st_size}:{st.st_mtime_ns}:{label}"
            if prev and prev.get("sig") == sig and out.exists():
                rows.append(prev["row"])
                continue
            row = render_session(path, out, label)
        except OSError as exc:
            print(f"WARN: skipped {path}: {exc}", file=sys.stderr)
            failed += 1
            if prev and (out_dir / prev["row"]["file"]).exists():
                rows.append(prev["row"])  # the previous render is still there; keep its row
            continue
        old = prev.get("row", {}).get("file") if prev else None
        if old and old != out.name and old not in taken:  # only after the new render landed
            (out_dir / old).unlink(missing_ok=True)
        state[sid] = {"sig": sig, "row": row}
        rows.append(row)
        rendered += 1
    rows.sort(key=lambda r: r["last"], reverse=True)
    index = [
        f"# Chat history — {key}\n",
        f"Rendered {datetime.now().isoformat(timespec='seconds')} from `{src}` · {len(rows)} sessions · "
        f"re-run `python3 /opt/fabrik/scripts/render_chat_history.py --project {key}` to refresh.\n",
        "| session | id | last activity | first | compactions | you | Claude |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        index.append(
            f"| [{r['label']}]({r['file']}) | `{r['id'][:8]}` | {r['last']} | {r['first']} | "
            f"{r['compactions']} | {r['user']} | {r['assistant']} |"
        )
    (out_dir / "INDEX.md").write_text("\n".join(index) + "\n")
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    print(
        f"{key}: {len(rows)} sessions, {rendered} (re)rendered, {failed} skipped → {out_dir}/INDEX.md"
    )
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--project", action="append", default=[], help="repo path or /opt name (repeatable)"
    )
    ap.add_argument(
        "--all", action="store_true", help="every project directory under ~/.claude/projects"
    )
    ap.add_argument(
        "--name",
        action="append",
        default=[],
        metavar="ID-PREFIX=LABEL",
        help="name a session (e.g. 1991fa9b=agent-1); persists in names.json",
    )
    args = ap.parse_args(argv)
    names: dict[str, str] = {}
    for item in args.name:
        prefix, _, label = item.partition("=")
        if len(prefix) < 8 or not _safe_label(label):
            print(
                f"ERROR: --name expects ID-PREFIX=LABEL with at least 8 id characters and a plain "
                f"file name (no '/', not hidden, not INDEX/names), got {item!r}",
                file=sys.stderr,
            )
            return 2
        names[prefix] = label
    if args.all:
        keys = sorted(
            p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and any(p.glob("*.jsonl"))
        )
    else:
        keys = [
            p if not p.startswith("/") and (PROJECTS_DIR / p).is_dir() else _key_for(p)
            for p in args.project
        ]
    if not keys:
        ap.error("give --project <path> (repeatable) or --all")
    rc = 0
    for key in keys:
        rc = max(rc, render_project(key, names))
    return rc


if __name__ == "__main__":
    sys.exit(main())
