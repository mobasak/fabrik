#!/usr/bin/env python3
# AFTER-EDIT: tests/fixtures/lane_replay.json (re-capture it, then --check) · tests/test_lane_replay_capture.py · scripts/task_lane.py (expected_verdict delegates to classify_commit)
"""Capture the /fabrik-task lane replay fixture — read-only git, re-derivable (plan T01, spec D12 (1)).

WHAT IT WRITES — ``tests/fixtures/lane_replay.json``: one row per commit the lane spec measured
(the hub's last 300 non-merge commits ending ``c84f0b0b7``, each project repo's last 200 — fewer
when its history is shorter — and the wef1 commit), each with its repo kind (``hub``/``project``),
its ``-M -C`` name-status rows ``[letter, path, old_path]`` (paths interned per repo to fit the
500 KB large-file limit — read it with ``load()``) and its EXPECTED verdict from the closed
set ``lane`` · ``lane: full-review`` · ``chain: contract`` · ``chain: new-source``. The header
records every source's END commit, the governance-sync regex and the commit it was read at, and
the verdict rule as text (``scripts/task_lane.py::classify_commit`` is its implementation), and
``--check`` re-derives the same rows.

HOW — ``git -C <repo> log --no-merges -n <N> --name-status -M -C -z <end>``; nothing is written to
any repo. ``--check <fixture>`` re-runs the capture against the header's recorded ends and exits 1
on ANY difference (rows, verdicts, counts, the regex).

THE VERDICT RULE is ``scripts/task_lane.py::classify_commit``; ``expected_verdict`` delegates to it
(T02-O20), so the capture and the lane can never disagree on the same rows.

THE CHEAPEST WAY TO SATISFY ``--check`` WITHOUT THE OUTCOME (D-253): change the rule in
``task_lane.py`` and re-capture, so the fixture silently pins whatever the new rule says. The
counter: the fixture is COMMITTED, so a rule change reds ``tests/test_lane_replay.py`` until a
re-capture is committed beside it, and that commit's fixture diff names every verdict that moved;
the rule is also graded case by case, independently of any capture, in
``tests/test_lane_replay_capture.py`` and ``tests/test_task_lane_admission.py``.

Usage:
  python scripts/lane_replay_capture.py --out tests/fixtures/lane_replay.json
  python scripts/lane_replay_capture.py --plan plan.json --out fx.json
  python scripts/lane_replay_capture.py --check tests/fixtures/lane_replay.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _task_lane() -> Any:
    """``scripts/task_lane.py``, loaded beside this file (``sys.modules`` first, so a test that
    already loaded it shares the one object)."""
    if "task_lane" in sys.modules:
        return sys.modules["task_lane"]
    spec = importlib.util.spec_from_file_location(
        "task_lane", Path(__file__).resolve().parent / "task_lane.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("lane_replay_capture: cannot load scripts/task_lane.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["task_lane"] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules["task_lane"]
        raise
    return mod


HUB_END = "c84f0b0b79e62e230e71c6e99eadd6e7c8d1f8f6"
WEF1_SHA = "0e89dcb67641ca0131e7b9d0b8177ee44671154c"
PRECOMMIT = ".pre-commit-config.yaml"

DEFAULT_PROJECTS = (
    "/opt/web-ecommerce-factory",
    "/opt/trade-intelligence",
    "/opt/tojlo-mail",
    "/opt/seo",
)

VERDICTS = ("lane", "lane: full-review", "chain: contract", "chain: new-source")

RULE = (
    "Rows are [status letter, path, old_path] from `git log -M -C --name-status`. The verdict is "
    "scripts/task_lane.py::classify_commit — this text describes it, the code is the one "
    "implementation. The contract, sync and migration tests read BOTH the row's NEW path and, "
    "for a rename or copy, its OLD path; the docs-only, new-source and count tests read the NEW "
    "path. First match wins: "
    "(1) chain: contract — any path that starts with `specs/services/` at the repo root, or "
    "whose basename fully matches `openapi*.json`, `openapi*.yaml` or `*.schema.json` "
    "case-insensitively at any depth (not `.yml`, not `x.schema.json.bak`), never when any path "
    "SEGMENT is `node_modules`, `.venv` or `vendor` (segments matched case-insensitively); "
    "tested over every row BEFORE any exclusion. "
    "(2) docs-only — every NEW path ends `.md` or starts `.fabrik/` (or the commit has no rows): "
    "lane: full-review when it is a hub commit with any path matching the governance-sync regex "
    "(the sync test runs BEFORE this docs-only short-circuit; an empty regex matches nothing), "
    "else lane. "
    "(3) chain: new-source — more than 2 rows with status A or C whose path is not excluded, is "
    "not a test (a `tests`, `test` or `__tests__` directory segment at any depth, or a basename "
    "`test_*`, `*_test.*`, `*.test.*` or `*.spec.*`), and does not end `.md`. "
    "(4) lane: full-review — a hub commit with any path matching the governance-sync regex "
    "(header `sync_regex`; project commits never test it), or any path with a migration segment "
    "(`migrations/` or `alembic/versions/` at any depth, case-insensitively, outside the "
    "dependency segments), or more than 5 distinct counted NEW paths. "
    "(5) lane. Excluded (never counted): CHANGELOG.md, INDEX.md, docs/DECISIONS.md, "
    "docs/STRATEGIC_BACKLOG.md, docs/LESSONS_LEARNT.md, docs/CAPABILITIES.md, and anything under "
    "docs/reference/, docs/workstation/, docs/development/reviews/, .fabrik/work/."
)

# ── the verdict rule ─────────────────────────────────────────────────────────────────────


def expected_verdict(rows: list, *, kind: str, sync_regex: str) -> str:
    """The pinned verdict for one commit's name-status rows: DELEGATED to
    ``task_lane.classify_commit`` so there is exactly one implementation (T02-O20)."""
    return str(
        _task_lane().classify_commit(
            [(r[0], r[1], r[2]) for r in rows], repo_kind=kind, sync_regex=sync_regex
        )
    )


# ── read-only git ────────────────────────────────────────────────────────────────────────


def _git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, "-c", "log.showRoot=true", "-c", "core.quotePath=false", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def read_sync_regex(repo: str, rev: str) -> tuple[str, int]:
    """The `files:` scalar of the governance-sync hook in `.pre-commit-config.yaml` at `rev`."""
    text = _git(repo, "show", f"{rev}:{PRECOMMIT}")
    seen_hook = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if re.match(r"\s*-\s*id:\s*governance-sync\s*$", line):
            seen_hook = True
            continue
        if seen_hook:
            if re.match(r"\s*-\s*id:", line):
                break
            m = re.match(r"\s*files:\s*'(.*)'\s*$", line)
            if m:
                return m.group(1).replace("''", "'"), lineno
    raise SystemExit(f"lane_replay_capture: no governance-sync `files:` scalar in {repo}@{rev}")


def _log(repo: str, end: str, n: int, *, no_merges: bool = True) -> list[dict[str, Any]]:
    fmt = "--format=%x01%H %P%x02"
    args = ["log", "--no-color", "--name-status", "-M", "-C", "-z", f"-n{n}", fmt]
    if no_merges:
        args.insert(1, "--no-merges")
    out = _git(repo, *args, end)
    commits: list[dict[str, Any]] = []
    for chunk in out.split("\x01")[1:]:
        head, _, rest = chunk.partition("\x02")
        sha, *parents = head.split()
        if len(parents) > 1:
            # git log prints no diff rows for a merge, which would pin `rows: []` -> "lane" (T01-S1)
            raise SystemExit(
                f"lane_replay_capture: {sha} in {repo} is a merge commit "
                f"({len(parents)} parents) — its rows cannot be captured; refusing"
            )
        rest = rest.lstrip("\x00\n")
        tokens = list(rest.split("\x00"))
        while tokens and tokens[-1] in ("", "\n"):
            tokens.pop()
        rows: list[list[Any]] = []
        i = 0
        while i < len(tokens):
            letter = tokens[i].strip()[0]
            if letter in ("R", "C"):
                rows.append([letter, tokens[i + 2], tokens[i + 1]])
                i += 3
            else:
                rows.append([letter, tokens[i + 1], None])
                i += 2
        commits.append({"sha": sha, "rows": rows})
    return commits


# ── capture / check ──────────────────────────────────────────────────────────────────────


def default_plan() -> dict[str, Any]:
    sources = [{"name": "fabrik", "path": "/opt/fabrik", "kind": "hub", "end": HUB_END, "n": 300}]
    for path in DEFAULT_PROJECTS:
        head = _git(path, "rev-parse", "HEAD").strip()
        sources.append(
            {"name": Path(path).name, "path": path, "kind": "project", "end": head, "n": 200}
        )
    return {
        "sync": {"repo": "/opt/fabrik", "rev": HUB_END},
        "sources": sources,
        "extras": [
            {
                "label": "wef1",
                "name": "web-ecommerce-factory",
                "path": "/opt/web-ecommerce-factory",
                "kind": "project",
                "sha": WEF1_SHA,
            }
        ],
    }


def capture(plan: dict[str, Any]) -> dict[str, Any]:
    sync_repo, sync_rev = plan["sync"]["repo"], plan["sync"]["rev"]
    regex, lineno = read_sync_regex(sync_repo, sync_rev)
    sources = []
    commits: list[dict[str, Any]] = []
    for src in plan["sources"]:
        name = src.get("name") or Path(src["path"]).name
        sources.append({**src, "name": name})
        for c in _log(src["path"], src["end"], int(src["n"])):
            commits.append(
                {
                    "repo": name,
                    "kind": src["kind"],
                    "sha": c["sha"],
                    "rows": c["rows"],
                    "expected": expected_verdict(c["rows"], kind=src["kind"], sync_regex=regex),
                }
            )
    extras = []
    for ex in plan.get("extras", []):
        (c,) = _log(ex["path"], ex["sha"], 1, no_merges=False)
        extras.append(
            {
                "label": ex["label"],
                "repo": ex.get("name") or Path(ex["path"]).name,
                "path": ex["path"],
                "kind": ex["kind"],
                "sha": c["sha"],
                "rows": c["rows"],
                "expected": expected_verdict(c["rows"], kind=ex["kind"], sync_regex=regex),
            }
        )
    return {
        "header": {
            "about": (
                "The /fabrik-task lane replay (spec 2026-10-02-fabrik-task-feature-lane-design.md "
                "§ The delta D12 (1)). Written by scripts/lane_replay_capture.py; re-derive with "
                "--check. Commits are newest-first per source."
            ),
            "verdicts": list(VERDICTS),
            "rule": RULE,
            "sync_regex": regex,
            "sync_regex_source": f"{PRECOMMIT}:{lineno}",
            "sync_regex_repo": sync_repo,
            "sync_regex_commit": sync_rev,
            "sources": sources,
        },
        "commits": commits,
        "extras": extras,
    }


def _plan_from(fixture: dict[str, Any]) -> dict[str, Any]:
    h = fixture["header"]
    return {
        "sync": {"repo": h["sync_regex_repo"], "rev": h["sync_regex_commit"]},
        "sources": h["sources"],
        "extras": [
            {
                "label": e["label"],
                "name": e["repo"],
                "path": e["path"],
                "kind": e["kind"],
                "sha": e["sha"],
            }
            for e in fixture.get("extras", [])
        ],
    }


ENCODING = (
    "Paths are interned to keep the file under the 500 KB check-added-large-files limit: "
    "`path_tables[<repo>]` is that repo's sorted distinct paths, front-coded — entry i is "
    "[k, suffix], path_i = path_{i-1}[:k] + suffix — and every stored row is "
    "[letter, path index, old-path index or null]. Read it with "
    "`scripts/lane_replay_capture.py::load(path)`, which returns rows as "
    "[letter, path, old_path or null]."
)


def _compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def encode(fixture: dict[str, Any]) -> dict[str, Any]:
    """Intern every path per repo (front-coded sorted table) and store rows as indices."""
    entries = fixture["commits"] + fixture["extras"]
    paths: dict[str, set[str]] = {}
    for c in entries:
        for _letter, path, old in c["rows"]:
            paths.setdefault(c["repo"], set()).update(p for p in (path, old) if p is not None)
    tables: dict[str, list[list[Any]]] = {}
    index: dict[str, dict[str, int]] = {}
    for repo in sorted(paths):
        ordered = sorted(paths[repo])
        index[repo] = {p: i for i, p in enumerate(ordered)}
        prev, coded = "", []
        for p in ordered:
            k = len(os.path.commonprefix([prev, p]))
            coded.append([k, p[k:]])
            prev = p
        tables[repo] = coded

    def rows_of(c: dict[str, Any]) -> list[list[Any]]:
        ix = index.get(c["repo"], {})
        return [[ltr, ix[p], None if o is None else ix[o]] for ltr, p, o in c["rows"]]

    return {
        "header": {**fixture["header"], "encoding": ENCODING},
        "path_tables": tables,
        "commits": [{**c, "rows": rows_of(c)} for c in fixture["commits"]],
        "extras": [{**c, "rows": rows_of(c)} for c in fixture["extras"]],
    }


def decode(stored: dict[str, Any]) -> dict[str, Any]:
    """The inverse of ``encode``: rows back to [letter, path, old_path or None]."""
    tables: dict[str, list[str]] = {}
    for repo, coded in stored.get("path_tables", {}).items():
        prev, out = "", []
        for k, suffix in coded:
            prev = prev[:k] + suffix
            out.append(prev)
        tables[repo] = out

    def rows_of(c: dict[str, Any]) -> list[list[Any]]:
        t = tables.get(c["repo"], [])
        return [[ltr, t[p], None if o is None else t[o]] for ltr, p, o in c["rows"]]

    header = {k: v for k, v in stored["header"].items() if k != "encoding"}
    return {
        "header": header,
        "commits": [{**c, "rows": rows_of(c)} for c in stored["commits"]],
        "extras": [{**c, "rows": rows_of(c)} for c in stored.get("extras", [])],
    }


def load(path: Path) -> dict[str, Any]:
    """The fixture with plain rows — what T02's replay test reads."""
    return decode(json.loads(Path(path).read_text()))


def dumps(fixture: dict[str, Any]) -> str:
    """Encoded; one commit (and one path table) per line, so a re-capture diffs line by line."""
    stored = encode(fixture)
    parts = ["{", f' "header": {json.dumps(stored["header"], indent=2, ensure_ascii=False)},']
    parts.append(' "path_tables": {')
    tables = list(stored["path_tables"].items())
    for i, (repo, coded) in enumerate(tables):
        sep = "," if i < len(tables) - 1 else ""
        parts.append(f"  {_compact(repo)}: {_compact(coded)}{sep}")
    parts.append(" },")
    for key in ("commits", "extras"):
        rows = stored[key]
        parts.append(f' "{key}": [')
        for i, c in enumerate(rows):
            sep = "," if i < len(rows) - 1 else ""
            parts.append("  " + _compact(c) + sep)
        parts.append(" ]," if key == "commits" else " ]")
    parts.append("}")
    return "\n".join(parts) + "\n"


def check(path: Path) -> int:
    try:
        recorded = load(path)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        print(
            f"lane_replay_capture --check: fixture and re-derivation differ — unreadable: {exc!r}"
        )
        return 1
    fresh = capture(_plan_from(recorded))
    problems: list[str] = []
    if fresh["header"]["sync_regex"] != recorded["header"].get("sync_regex"):
        problems.append("sync_regex differs from the regex at the recorded commit")
    if recorded["header"].get("rule") != RULE:
        problems.append("rule text differs from RULE (the header describes a stale verdict rule)")
    for key in ("commits", "extras"):
        old, new = recorded.get(key, []), fresh[key]
        if len(old) != len(new):
            problems.append(f"{key}: fixture has {len(old)}, re-derivation has {len(new)}")
        for a, b in zip(old, new, strict=False):
            if a != b:
                problems.append(f"{key}: {b['repo']} {b['sha'][:12]} differs")
    if problems:
        print(f"lane_replay_capture --check: fixture and re-derivation differ ({len(problems)}):")
        for p in problems[:20]:
            print(f"  - {p}")
        return 1
    n = len(fresh["commits"]) + len(fresh["extras"])
    print(f"lane_replay_capture --check: OK — {n} commits re-derived identically")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--out", type=Path, help="write the fixture here")
    ap.add_argument("--plan", type=Path, help="a JSON capture plan (default: the spec's repos)")
    ap.add_argument("--check", type=Path, help="re-derive this fixture and compare")
    args = ap.parse_args(argv)
    if args.check:
        return check(args.check)
    if not args.out:
        ap.error("one of --out or --check is required")
    plan = json.loads(args.plan.read_text()) if args.plan else default_plan()
    fixture = capture(plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(dumps(fixture))
    counts: dict[str, int] = {}
    for c in fixture["commits"]:
        counts[c["repo"]] = counts.get(c["repo"], 0) + 1
    print(f"lane_replay_capture: wrote {args.out} — {counts}, extras {len(fixture['extras'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
