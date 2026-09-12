#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/chat-history-render.md | tests/test_render_chat_history.py
"""Render a project's FULL Claude Code chat history to markdown — the "load more" the
VS Code panel does not have.

Why this exists (measured 2026-09-11, D-235/D-236): a reloaded VS Code window's panel is
rebuilt by the extension host, which walks the transcript's `parentUuid` links from the
newest record back to a root; every compaction writes a `compact_boundary` record with NO
parent — a new root — and the loader re-parents that boundary's preserved messages onto the
compaction summary. So the panel renders only what came after the LAST compaction; everything
earlier is on disk but never shown, and no reload, restart or setting changes that. This
script reads the same transcripts (`~/.claude/projects/<project-key>/<session>.jsonl`, shared
by every rotated account) and writes one readable markdown per session, every compaction a
dated heading, tool calls / tool results / hook injections stripped.

Usage:
  python3 scripts/render_chat_history.py --project /opt/trade-intelligence
  python3 scripts/render_chat_history.py --project trade-intelligence --name 1991fa9b=agent-1 --name 37887efc=agent-2
  python3 scripts/render_chat_history.py --all            # every project with transcripts

Output: ~/.claude/state/history/<project-key>/<session-name-or-id8>.md + INDEX.md per project.
Incremental: a session whose transcript size and mtime are unchanged since its last render is
skipped. Names persist in <project>/names.json so a later run without --name keeps them.
Every failure is contained at the smallest unit — a record, a transcript, a project — with a
WARN on stderr and a non-zero exit at the end; nothing here aborts a batch.
"""

from __future__ import annotations

import argparse
import fcntl
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
_RECORD_TYPES = frozenset({"user", "assistant", "progress", "system", "attachment"})
_RESERVED_LABELS = frozenset({"INDEX", "names"})
# One path segment that is also a clean markdown link target: letters, digits, dot, dash,
# underscore; not hidden; at most 120 characters; never one of the folder's own files.
_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}")
_KEY_RE = re.compile(r"[A-Za-z0-9-][A-Za-z0-9._-]*")  # Claude keys start with '-'
_ROW_KEYS = ("label", "id", "file", "first", "last", "compactions", "user", "assistant", "dropped")
_COLUMNS = "| session | id | last activity | first | compactions | you | Claude | dropped |"


def _warn(text: str) -> None:
    print(f"WARN: {text}", file=sys.stderr)


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "\n".join(parts)


def _stamp(record: dict) -> str:
    """`YYYY-MM-DD HH:MM:SS` from an ISO timestamp string; anything else is no stamp at all."""
    ts = record.get("timestamp")
    return ts[:19].replace("T", " ") if isinstance(ts, str) else ""


def _key_for(project: str) -> str:
    """Claude's project key: the absolute path with every non-alphanumeric CHARACTER turned
    into '-' (per character, not per run: `/opt/a--b` → `-opt-a--b`)."""
    path = project if project.startswith("/") else f"/opt/{project}"
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def _safe_key(key: str) -> bool:
    return bool(key) and bool(_KEY_RE.fullmatch(key)) and key not in {".", ".."}


def _safe_label(label: object) -> bool:
    """A label becomes `<label>.md` inside the project folder and a markdown link target."""
    return (
        isinstance(label, str)
        and bool(_LABEL_RE.fullmatch(label))
        and label not in _RESERVED_LABELS
    )


def _owner_of(path: Path) -> str | None:
    """The session id8 a render belongs to, read from its own first line (`# <label> — <id8>`)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline()
    except OSError:
        return None
    return first.rsplit(" — ", 1)[-1].strip() if first.startswith("# ") and " — " in first else None


def _default_label(sid: str) -> str:
    """The first 8 characters of the session id, made a safe label (a transcript name may be
    anything the filesystem allows — a leading dot would make a hidden, unusable render)."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", sid[:8]).lstrip("._-")
    return cleaned or "session"


def _is_entry(entry: object) -> bool:
    """A state entry is usable only when its row carries every column the index prints."""
    if not isinstance(entry, dict) or not isinstance(entry.get("row"), dict):
        return False
    row = entry["row"]
    return (
        all(key in row for key in _ROW_KEYS)
        and all(isinstance(row[key], str) for key in ("label", "id", "file", "first", "last"))
        and row["file"].endswith(".md")
        and _safe_label(row["file"][:-3])
    )


def _write_atomic(path: Path, text: str) -> None:
    """Write via a per-process temp file + rename: a failed write never truncates the previous
    file, two processes never share a temp name, and no temp file outlives a failure."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8", errors="replace")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _load_json(path: Path) -> dict:
    """A missing sidecar reads as empty. One that exists but is not a JSON object (bad bytes,
    malformed, a list…) is moved aside to `<name>.bad-<stamp>` with a WARN, so a later write
    never silently discards what was there."""
    try:
        raw = path.read_bytes()
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
        _warn(f"{path} is not a JSON object; moved aside to {kept.name}")
    except OSError as exc:
        _warn(f"{path} is not a JSON object and could not be moved aside: {exc}")
    return {}


def _iter_records(path: Path, dropped: list[int]):
    """Yield every JSON-object record of a transcript; count the lines that are not one."""
    with path.open("rb") as fh:
        for raw in fh:
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except ValueError:
                dropped[0] += 1
                continue
            if isinstance(record, dict):
                yield record
            else:
                dropped[0] += 1


def render_session(path: Path, out: Path, label: str) -> dict:
    """Write the markdown for one transcript; return its index row."""
    segments: list[str] = []
    lines: list[str] = []
    n_user = n_asst = 0
    first_ts = last_ts = ""
    dropped = [0]
    for r in _iter_records(path, dropped):
        kind = r.get("type")
        ts = _stamp(r)
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        if kind == "system" and r.get("subtype") == "compact_boundary":
            meta = _as_dict(r.get("compactMetadata"))
            segments.append(ts)
            lines.append(
                f"\n\n---\n\n## ⟲ Compaction #{len(segments)} — {ts} "
                f"(trigger: {meta.get('trigger')}, {meta.get('preTokens')} tokens summarised)\n"
            )
            continue
        if kind == "user":
            if r.get("toolUseResult") is not None:
                continue
            content = _as_dict(r.get("message")).get("content")
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
            text = _text_of(_as_dict(r.get("message")).get("content")).strip()
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
    if dropped[0]:
        _warn(f"{path}: {dropped[0]} unparseable record(s) skipped")
    head = (
        f"# {label} — {path.stem[:8]}\n\n"
        f"Source: `{path}`  \nSpan: {first_ts} → {last_ts} · compactions: {len(segments)} · "
        f"your messages: {n_user} · Claude replies: {n_asst} · unparseable records: {dropped[0]}\n\n"
        "Every `## ⟲ Compaction` heading is a point where the live window was summarised. "
        "The VS Code panel shows only what follows the LAST one; this file is the rest.\n\n---\n"
    )
    _write_atomic(out, head + "".join(lines))
    return {
        "label": label,
        "id": path.stem,
        "file": out.name,
        "first": first_ts,
        "last": last_ts,
        "compactions": len(segments),
        "user": n_user,
        "assistant": n_asst,
        "dropped": dropped[0],
    }


def _assign_labels(
    transcripts: list[Path], stored_names: dict, state: dict, out_dir: Path
) -> dict[str, str]:
    """One label per session, unique among this run's sessions AND against every `.md` already
    on disk that this session does not own (an orphan is the last copy of a deleted
    conversation). A colliding label is suffixed with more and more of the session id, then a
    counter, until it is free — every suffixed form checked again, never trusted — and a session
    that finds no free name in 104 candidates is left OUT of the returned map (skipped, WARNed)."""
    labels: dict[str, str] = {}
    for path in transcripts:
        sid = path.stem
        # the longest matching prefix wins, whatever order names.json was written in
        prefix = max((k for k in stored_names if sid.startswith(k)), key=len, default=None)
        wanted = stored_names[prefix] if prefix is not None else _default_label(sid)
        if not _safe_label(wanted):  # a hand-edited names.json must not escape the folder
            _warn(f"label {wanted!r} for {sid[:8]} is not a usable file name; using the id")
            wanted = _default_label(sid)
        own = state[sid]["row"]["file"] if _is_entry(state.get(sid)) else None

        def taken(candidate: str, own: str | None = own, sid8: str = sid[:8]) -> bool:
            file = f"{candidate}.md"
            if candidate in labels.values():
                return True
            try:
                if not (out_dir / file).exists():
                    return False
            except OSError:
                return True  # an unstat-able name is not a name we take
            # ours by the state entry, or — with no usable entry — by the render's own header
            return file != own and _owner_of(out_dir / file) != sid8

        label = wanted
        if taken(label):
            suffixes = [sid[:n] for n in (8, 12, 16, 36)] + [f"{sid}-{n}" for n in range(1, 101)]
            # the suffixed name must still obey the label rule (≤ 120 chars), or the state row
            # written with it is rejected on every later run and the session re-renders forever
            candidates = [f"{wanted[: 119 - len(sfx)]}-{sfx}" for sfx in suffixes]
            label = next((c for c in candidates if not taken(c)), None)
            if label is None:  # bounded: a filesystem that rejects every name never spins the run
                _warn(
                    f"{sid[:8]}: no free file name for label {wanted!r} after 104 candidates; skipped"
                )
                continue
            if f"{label}.md" != own:  # warn when a collision is first resolved, not on every run
                _warn(f"label {wanted!r} is already used; {sid[:8]} renders as {label}")
        labels[sid] = label
    return labels


def render_project(key: str, names: dict[str, str]) -> int:
    src = PROJECTS_DIR / key
    transcripts = sorted(p for p in src.glob("*.jsonl") if p.is_file() or p.is_symlink())
    if not transcripts:
        print(f"ERROR: no transcripts under {src}", file=sys.stderr)
        return 1
    out_dir = OUT_ROOT / key
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = (out_dir / ".render.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        _warn(f"{key}: another render of this project is running; skipped")
        lock.close()
        return 1
    try:
        return _render_project_locked(key, src, out_dir, transcripts, names)
    finally:
        lock.close()  # releases the flock


def _render_project_locked(
    key: str, src: Path, out_dir: Path, transcripts: list[Path], names: dict[str, str]
) -> int:
    names_path = out_dir / "names.json"
    state_path = out_dir / ".render-state.json"
    stored_names = _load_json(names_path)
    # Only a name whose session lives HERE is persisted here (--all hands every project the
    # same --name list).
    stored_names.update(
        {k: v for k, v in names.items() if any(p.stem.startswith(k) for p in transcripts)}
    )
    if stored_names != _load_json(names_path):
        _write_atomic(names_path, json.dumps(stored_names, indent=2, sort_keys=True) + "\n")
    state = _load_json(state_path)
    labels = _assign_labels(transcripts, stored_names, state, out_dir)
    taken_files = {f"{label}.md" for label in labels.values()}
    rows: list[dict] = []
    rendered = failed = 0
    for path in transcripts:
        sid = path.stem
        prev = state.get(sid) if _is_entry(state.get(sid)) else None
        if sid not in labels:  # no usable file name this run (warned above)
            failed += 1
            if prev and (out_dir / prev["row"]["file"]).exists():
                rows.append(prev["row"])
            continue
        label = labels[sid]
        out = out_dir / f"{label}.md"
        try:  # one unreadable, vanished or malformed transcript never aborts the batch
            st = path.stat()
            sig = f"{st.st_size}:{st.st_mtime_ns}:{label}"
            if prev and prev.get("sig") == sig and out.exists():
                rows.append(prev["row"])
                continue
            row = render_session(path, out, label)
        except OSError as exc:  # every other shape is validated before it reaches here
            _warn(f"skipped {path}: {type(exc).__name__}: {exc}")
            failed += 1
            if prev and (out_dir / prev["row"]["file"]).exists():
                rows.append(prev["row"])  # the previous render is still there; keep its row
            continue
        old = prev["row"]["file"] if prev else None
        if old and old != out.name and old not in taken_files:  # only after the new render landed
            (out_dir / old).unlink(missing_ok=True)
        state[sid] = {"sig": sig, "row": row}
        rows.append(row)
        rendered += 1
    rows.sort(key=lambda r: r["last"], reverse=True)
    index = [
        f"# Chat history — {key}\n",
        f"Rendered {datetime.now().isoformat(timespec='seconds')} from `{src}` · {len(rows)} sessions · "
        f"re-run `python3 /opt/fabrik/scripts/render_chat_history.py --project {key}` to refresh.\n",
        _COLUMNS,
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        index.append(
            f"| [{r['label']}]({r['file']}) | `{r['id'][:8]}` | {r['last']} | {r['first']} | "
            f"{r['compactions']} | {r['user']} | {r['assistant']} | {r['dropped']} |"
        )
    _write_atomic(out_dir / "INDEX.md", "\n".join(index) + "\n")
    _write_atomic(state_path, json.dumps(state, indent=1, sort_keys=True) + "\n")
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
                f"file name (letters, digits, '.', '_', '-'; not INDEX/names), got {item!r}",
                file=sys.stderr,
            )
            return 2
        names[prefix] = label
    if args.all:
        keys = sorted(
            p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and any(p.glob("*.jsonl"))
        )
    else:
        keys = []
        for p in args.project:
            key = p if not p.startswith("/") and (PROJECTS_DIR / p).is_dir() else _key_for(p)
            if not p or not _safe_key(key):
                print(f"ERROR: {p!r} is not a project path or key", file=sys.stderr)
                return 2
            keys.append(key)
    if not keys:
        ap.error("give --project <path> (repeatable) or --all")
    rc = 0
    for key in keys:
        try:
            rc = max(rc, render_project(key, names))
        except Exception as exc:  # noqa: BLE001 — one broken project never stops the rest
            _warn(f"{key}: {type(exc).__name__}: {exc}")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
