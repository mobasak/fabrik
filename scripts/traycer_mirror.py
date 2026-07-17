#!/usr/bin/env python3
"""traycer_mirror.py — mirror a disk artifact into the Traycer store so the
cockpit GUI renders it, WITHOUT making the pipeline depend on Traycer.

north-star R8/D4: the mirror is deterministic code the commands CALL, not prose
an agent is asked to hand-write each run. D8: disk stays source-of-truth; this is
an additive, env-guarded projection.

Behaviour:
  * If $TRAYCER_EPIC_ID is unset  -> NO-OP (headless/driver runs untouched). Exit 0.
  * If set -> write  $TRAYCER_HOME/epics/$TRAYCER_EPIC_ID/artifacts/<name>/index.md
    with Traycer frontmatter (kind/title/status). By default the mirror is a thin
    pointer to the git-tracked source (--embed to copy the body inline).

The SAME command therefore runs unchanged in any /opt project, headless or in
Traycer — the env var alone decides whether a mirror appears.

Pure stdlib. Idempotent (overwrites the mirror in place).
"""
from __future__ import annotations

import argparse
import os
import sys

_STATUS = {"0": "0", "1": "1", "2": "2",
           "todo": "0", "in-progress": "1", "in_progress": "1", "done": "2"}


def _traycer_root() -> str:
    return os.environ.get("TRAYCER_HOME") or os.path.join(os.path.expanduser("~"), ".traycer")


def mirror(src: str, name: str, kind: str, title: str | None,
           status: str, embed: bool) -> str | None:
    epic_id = os.environ.get("TRAYCER_EPIC_ID")
    if not epic_id:
        return None  # headless: no-op by design
    art_dir = os.path.join(_traycer_root(), "epics", epic_id, "artifacts", name)
    os.makedirs(art_dir, exist_ok=True)
    out = os.path.join(art_dir, "index.md")

    if title is None:
        title = name
    fm = [f"kind: {kind}", f'title: "{title}"']
    st = _STATUS.get(str(status).lower())
    if st is not None:
        fm.append(f"status: {st}")

    if embed and os.path.isfile(src):
        with open(src, encoding="utf-8") as fh:
            body = fh.read()
        # strip an existing frontmatter block from the source before embedding
        if body.startswith("---"):
            end = body.find("\n---", 3)
            if end != -1:
                body = body[end + 4:].lstrip("\n")
    else:
        rel = os.path.abspath(src)
        body = (f"> Mirror of the git-tracked source of truth:\n>\n> `{rel}`\n\n"
                f"_This artifact is a Traycer-store projection written by "
                f"`traycer_mirror.py`; edit the source, not this file._\n")

    with open(out, "w", encoding="utf-8") as fh:
        fh.write("---\n" + "\n".join(fm) + "\n---\n\n" + body)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, help="disk artifact (source of truth) to mirror")
    ap.add_argument("--name", required=True,
                    help="artifact dir name in the store (e.g. epic-1, vision, infra-decisions)")
    ap.add_argument("--kind", default="story", help="Traycer kind: story|spec|ticket|review")
    ap.add_argument("--title", default=None)
    ap.add_argument("--status", default="0", help="0/1/2 or todo/in-progress/done")
    ap.add_argument("--embed", action="store_true",
                    help="copy the source body inline instead of a pointer")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.src):
        print(f"traycer_mirror: source not found: {args.src}", file=sys.stderr)
        return 2
    out = mirror(args.src, args.name, args.kind, args.title, args.status, args.embed)
    if out is None:
        print("traycer_mirror: TRAYCER_EPIC_ID unset — mirror skipped (headless run).")
    else:
        print(f"traycer_mirror: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
