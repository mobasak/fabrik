#!/usr/bin/env python3
# AFTER-EDIT: tests/test_kaizen_shrink_audit.py, docs/workstation/kaizen-shrink-audit.md | none
"""M0 shrink audit — the usage-evidence census over every governance artifact.

WHY THIS EXISTS
---------------
Before the kaizen meter is built, the operator's question runs FIRST: should ~203
artifacts and 57 checks become 60 and 20? This script gathers the EVIDENCE for that
ruling — per artifact: invocations (both channels), applicability, liveness, mentions.
It judges nothing by itself: verdicts and the immune registry are Phase B's
(`kaizen_immune_list.py`), the ruling is the OPERATOR's.

THE HONESTY RULE (non-negotiable, inherited from kaizen_metrics.py)
-------------------------------------------------------------------
A signal that cannot be measured reports ``—`` WITH ITS REASON, never 0 — an empty
universe and a clean result are indistinguishable otherwise. Every collector returns a
:class:`Signal`; ``data is None`` + a reason IS the "—".

EVIDENCE CHANNELS (and their known edges — each hit live in the week before M0)
-------------------------------------------------------------------------------
- Invocations span BOTH channels: ``<command-name>/x`` rows (operator-typed) AND Skill
  tool_use rows keyed on JSON STRUCTURE (a quoted ``"skill":"x"`` in prose must not
  count). Measured 2026-08-17: 145 tool_use vs 4 typed rows in one session file —
  typed-only counting misses exactly the agent-initiated invocations.
- Transcripts carry UTF-8 dirt → open ``errors="replace"``, never skip-as-binary.
  They are per-session files with long-session mtime skew → ``last_seen`` is the file's
  mtime DATE (a range proxy, not a precise timestamp).
- Rule packs have no invocation channel — glob-replay measures APPLICABILITY only
  (structural = current tree; recent = files changed in the git window), never usage.
- Liveness verdicts come from RUNNING ``liveness_audit.py --json`` (nothing stores
  them); pass a saved report via ``Sources.liveness_json`` or let the collector run it.
- Run records nearly all collided into ``nosession.json`` → supplementary signal only,
  never a denominator.

Read-only over the census artifacts; writes only its own report (Phase B ``--report``).
Box-local, stdlib-only; config via env (``KAIZEN_SINCE_DAYS``), logs to stdout.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_CMD_RE = re.compile(r"<command-name>/([a-z0-9][\w.-]*)</command-name>")
_GLOB_INLINE_RE = re.compile(r"^globs:\s*\[(.*)\]\s*$", re.M)
_GLOB_ITEM_RE = re.compile(r"[\"']?([^\"',\s]+)[\"']?")


@dataclass
class Signal:
    """A measured value, or an explicit non-measurement carrying its reason."""

    data: object | None
    reason: str = ""

    @property
    def measurable(self) -> bool:
        return self.data is not None

    @classmethod
    def unavailable(cls, reason: str) -> "Signal":
        return cls(data=None, reason=reason)


@dataclass
class Sources:
    """Every evidence root, overridable so fixtures can inject temp dirs."""

    repo: Path = REPO
    transcripts: Path = field(default_factory=lambda: Path.home() / ".claude" / "projects")
    reviews_root: Path = Path("/opt")
    run_records: Path = field(
        default_factory=lambda: Path.home() / ".claude" / "state" / "command-runs"
    )
    liveness_json: Path | None = None  # saved liveness report; None -> run the audit live
    crontab_text: str | None = None  # override for tests; None -> `crontab -l`
    since_days: int = field(default_factory=lambda: int(os.getenv("KAIZEN_SINCE_DAYS", "60")))


# ── transcripts: invocations (both channels) + check activity ────────────────────────


def _transcript_files(root: Path) -> list[Path]:
    root = root.resolve()  # ~/.claude-fleet symlinks: bare walks return 0 across a symlink
    if not root.is_dir():
        return []
    out: list[Path] = []
    for proj in sorted(root.iterdir()):
        if proj.is_dir():
            out.extend(sorted(proj.glob("*.jsonl")))
    return out


def _skill_names(line: str) -> list[str]:
    """Skill tool_use invocations in one transcript row — JSON structure, never grep.

    A quoted '"skill":"x"' inside conversation TEXT must not count; only an actual
    tool_use content block with name == "Skill" is an invocation.
    """
    if '"Skill"' not in line:
        return []
    try:
        d = json.loads(line)
    except ValueError:
        return []
    msg = d.get("message") or {}
    content = msg.get("content")
    names: list[str] = []
    if isinstance(content, list):
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == "Skill"
            ):
                skill = (block.get("input") or {}).get("skill")
                if isinstance(skill, str) and skill:
                    names.append(skill)
    return names


def collect_invocations(transcripts_root: Path) -> Signal:
    """Per-command invocation counts across BOTH channels, with a last-seen date.

    data = {command: {"typed": n, "skill": n, "last_seen": "YYYY-MM-DD"}}
    """
    files = _transcript_files(transcripts_root)
    if not files:
        return Signal.unavailable(f"no transcript files under {transcripts_root}")
    counts: dict[str, dict] = {}
    files_read = 0
    for f in files:
        try:
            mday = dt.date.fromtimestamp(f.stat().st_mtime).isoformat()
        except OSError:
            continue
        try:
            with f.open(errors="replace") as fh:  # UTF-8 dirt must never skip a file
                for line in fh:
                    hits: list[tuple[str, str]] = []
                    hits += [(m, "typed") for m in _CMD_RE.findall(line)]
                    hits += [(s, "skill") for s in _skill_names(line)]
                    for name, channel in hits:
                        row = counts.setdefault(
                            name, {"typed": 0, "skill": 0, "last_seen": mday}
                        )
                        row[channel] += 1
                        row["last_seen"] = max(row["last_seen"], mday)
        except OSError:
            continue
        files_read += 1
    if not files_read:
        # files exist but none could be READ — a measurable empty universe here would
        # be a fabricated zero (the honesty rule), not a clean count
        return Signal.unavailable(
            f"{len(files)} transcript file(s) present but none readable"
        )
    return Signal(counts)


def collect_check_activity(transcripts_root: Path, check_names: list[str]) -> Signal:
    """Occurrences of gate-check names across transcripts (gate outputs are embedded in
    tool results — 2,450 hits in one session file, measured). data = {name: count}."""
    files = _transcript_files(transcripts_root)
    if not files:
        return Signal.unavailable(f"no transcript files under {transcripts_root}")
    if not check_names:
        return Signal.unavailable("no check names to search for")
    counts = dict.fromkeys(check_names, 0)
    # boundary-aware: `check_doc` must not count hits belonging to `check_doc_sync`,
    # nor `python-api` inside `python-api-gpu` (name alphabet is [\w-])
    pats = {
        n: re.compile(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])") for n in check_names
    }
    for f in files:
        try:
            with f.open(errors="replace") as fh:
                for line in fh:
                    for name in check_names:
                        if name in line:
                            counts[name] += len(pats[name].findall(line))
        except OSError:
            continue
    return Signal(counts)


# ── rule packs: applicability (never usage) ──────────────────────────────────────────


def _frontmatter_globs(text: str) -> list[str] | None:
    """The pack's frontmatter ``globs:`` list; None when the pack declares none."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    fm = text[: end if end != -1 else len(text)]
    m = _GLOB_INLINE_RE.search(fm)
    if m:
        return [g for g in _GLOB_ITEM_RE.findall(m.group(1)) if g]
    lines = fm.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("globs:"):
            globs: list[str] = []
            for follow in lines[i + 1 :]:
                s = follow.strip()
                if not s.startswith("- "):
                    break
                globs.append(s[2:].strip().strip("\"'"))
            return globs or None
    return None


def _glob_to_re(pattern: str) -> re.Pattern:
    """`**/*.py`-style glob → regex (fnmatch has no `**`; PurePath.match mishandles it)."""
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i : i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pattern[i : i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def _git_lines(repo: Path, *args: str) -> list[str] | None:
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]


def collect_applicability(repo: Path, since_days: int) -> Signal:
    """Glob-replay per pack — APPLICABILITY only, never usage.

    data = {pack_relpath: {"structural": n|None, "recent": n|None, "note": str}} where
    structural counts current-tree matches (could this pack EVER fire here) and recent
    counts matches against files changed in the last ``since_days`` days.
    """
    rules = repo / ".windsurf" / "rules"
    packs = sorted(rules.rglob("*.md")) if rules.is_dir() else []
    if not packs:
        return Signal.unavailable(f"no rule packs under {rules}")
    tracked = _git_lines(repo, "ls-files")
    if tracked is None:
        return Signal.unavailable(f"git ls-files failed in {repo} — not a repo?")
    recent_raw = _git_lines(
        repo, "log", f"--since={since_days} days", "--name-only", "--pretty=format:"
    )
    recent = set(recent_raw or [])
    out: dict[str, dict] = {}
    for pack in packs:
        rel = str(pack.relative_to(repo))
        globs = _frontmatter_globs(pack.read_text(encoding="utf-8", errors="replace"))
        if not globs:
            out[rel] = {
                "structural": None,
                "recent": None,
                "note": "no globs frontmatter — not glob-activated",
            }
            continue
        pats = [_glob_to_re(g) for g in globs]
        out[rel] = {
            "structural": sum(1 for f in tracked if any(p.match(f) for p in pats)),
            "recent": sum(1 for f in recent if any(p.match(f) for p in pats)),
            "note": "applicability-only — activation unknown until M1",
        }
    return Signal(out)


# ── liveness verdicts ────────────────────────────────────────────────────────────────


def collect_liveness(sources: Sources) -> Signal:
    """{finding_id: LIVE|DEAD|UNKNOWN|...} from a saved ``liveness_audit --json`` report,
    or from running the audit live when no report path is given."""
    if sources.liveness_json is not None:
        try:
            report = json.loads(sources.liveness_json.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return Signal.unavailable(f"liveness report unreadable: {exc}")
    else:
        script = sources.repo / "scripts" / "sysadmin" / "liveness_audit.py"
        if not script.exists():
            return Signal.unavailable(f"{script} absent")
        try:
            p = subprocess.run(
                [sys.executable, str(script), "--json"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            report = json.loads(p.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return Signal.unavailable(f"liveness audit run failed: {exc}")
    verdicts: dict[str, str] = {}
    for proof in (report.get("proofs") or {}).values():
        for f in proof.get("findings") or []:
            fid, verdict = f.get("id"), f.get("verdict")
            if isinstance(fid, str) and isinstance(verdict, str):
                verdicts[fid] = verdict
    if not verdicts:
        return Signal.unavailable("liveness report contains no findings")
    return Signal(verdicts)


# ── mentions: review ledgers fleet-wide + run records (supplementary) ────────────────


def collect_mentions(sources: Sources, names: list[str]) -> Signal:
    """{name: {"ledgers": n, "run_records": n}} — run-record counts are SUPPLEMENTARY
    (nearly all records collided into nosession.json; never a denominator)."""
    if not names:
        return Signal.unavailable("no artifact names to search for")
    ledgers = sorted(sources.reviews_root.resolve().glob("*/docs/development/reviews/*.md"))
    if not ledgers:
        return Signal.unavailable(
            f"no review ledgers under {sources.reviews_root}/*/docs/development/reviews/"
        )
    counts = {n: {"ledgers": 0, "run_records": 0} for n in names}
    for f in ledgers:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n in names:
            if n in text:
                counts[n]["ledgers"] += text.count(n)
    rr = sources.run_records
    if rr.is_dir():
        for f in sorted(rr.glob("*.json")):
            try:
                cmd = json.loads(f.read_text(encoding="utf-8", errors="replace")).get(
                    "command", ""
                )
            except (OSError, ValueError):
                continue
            for n in names:
                if isinstance(cmd, str) and n in cmd:
                    counts[n]["run_records"] += 1
    return Signal(counts)


# ── the census denominators — enumerated from live registries, never memory ──────────


def _ast_names(path: Path, symbol: str) -> list[str] | None:
    """String constants assigned to ``symbol`` in *path* (handles list/tuple/set literals
    and a frozenset(...) call wrapping one) — registry reads without importing deps."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == symbol for t in node.targets):
            continue
        value = node.value
        if isinstance(value, ast.Call) and value.args:  # frozenset([...]) / set((...))
            value = value.args[0]
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            names = []
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    names.append(elt.value)
                elif isinstance(elt, ast.Tuple) and elt.elts:
                    first = elt.elts[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        names.append(first.value)
            return names
    return None


def _crontab_lines(sources: Sources) -> list[str] | None:
    if sources.crontab_text is not None:
        text = sources.crontab_text
    else:
        try:
            p = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        if p.returncode != 0:
            return None
        text = p.stdout
    return [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#") and "/opt/fabrik" in ln
    ]


_CRON_TARGET_RE = re.compile(r"(/opt/fabrik/[^\s'\"]+|scripts/[^\s'\"]+)")


def enumerate_artifacts(sources: Sources) -> tuple[dict[str, list[str]], list[str]]:
    """(census, notes): {class: [artifact, ...]} from the live registries; a registry
    that cannot be read becomes a NOTE (visible), never a silently-absent class."""
    repo = sources.repo
    census: dict[str, list[str]] = {}
    notes: list[str] = []

    def _stems(rel: str, pattern: str) -> list[str]:
        d = repo / rel
        return sorted(f.stem for f in d.glob(pattern)) if d.is_dir() else []

    census["command"] = _stems("commands/_sources", "*.md")
    census["fragment"] = _stems("commands/_fragments", "*.md")
    rules = repo / ".windsurf" / "rules"
    census["rule-pack"] = (
        sorted(str(f.relative_to(repo)) for f in rules.rglob("*.md")) if rules.is_dir() else []
    )
    census["gate-check"] = _stems("scripts/enforcement", "check_*.py")
    hooks = repo / ".claude" / "hooks"
    census["hook"] = sorted(f.name for f in hooks.glob("*.py")) if hooks.is_dir() else []

    scaffold = repo / "src" / "fabrik" / "scaffold.py"
    types = _ast_names(scaffold, "SCAFFOLD_TYPES") if scaffold.exists() else None
    if types:
        census["scaffold-type"] = sorted(types)
    else:
        notes.append(f"scaffold-type registry unreadable ({scaffold}) — class not enumerated")

    manifest = repo / "scripts" / "fabrik_synced_manifest.py"
    core = _ast_names(manifest, "CORE_SCRIPTS") if manifest.exists() else None
    if core:
        census["core-script"] = sorted(core)
    else:
        notes.append(f"core-script registry unreadable ({manifest}) — class not enumerated")

    crons = _crontab_lines(sources)
    if crons is None:
        notes.append("crontab unreadable — cron class not enumerated")
    else:
        seen: list[str] = []
        for ln in crons:
            m = _CRON_TARGET_RE.search(ln)
            target = m.group(1) if m else ln[:80]
            if target not in seen:
                seen.append(target)
        census["cron"] = seen
    return {k: v for k, v in census.items() if v}, notes


# ── composition ──────────────────────────────────────────────────────────────────────

_CLASS_MEASURABILITY = {
    "command": "invocations (both channels) + mentions",
    "fragment": "mentions (fragments have no invocation channel)",
    "rule-pack": "applicability only — no invocation channel; activation unknown until M1",
    "gate-check": "transcript gate-output hits + liveness + mentions",
    "hook": "liveness + mentions",
    "cron": "liveness + mentions",
    "core-script": "liveness + mentions",
    "scaffold-type": "scaffold-invocation greps (transcript hits) + mentions",
}


def _note_for(sig: Signal, label: str) -> str:
    return "" if sig.measurable else f"{label}: — ({sig.reason})"


def audit(sources: Sources | None = None) -> tuple[list[dict], list[str]]:
    """The composition: every census artifact → one evidence row.

    ``immune``/``verdict`` are None here BY DESIGN — Phase A gathers evidence, Phase B
    judges (a row that judged itself would make the meter its own reviewer).
    Returns (rows, census_notes).
    """
    src = sources or Sources()
    census, notes = enumerate_artifacts(src)

    inv = collect_invocations(src.transcripts)
    app = collect_applicability(src.repo, src.since_days)
    live = collect_liveness(src)
    all_names = [a for arts in census.values() for a in arts]
    # mention search keys: basename-ish tokens (a cron line's full path would never
    # appear verbatim in a ledger; its script basename does)
    mention_key = {a: (Path(a).name if "/" in a else a) for a in all_names}
    key_owners: dict[str, int] = {}
    for k in mention_key.values():
        key_owners[k] = key_owners.get(k, 0) + 1
    men = collect_mentions(src, sorted(set(mention_key.values())))
    chk = collect_check_activity(src.transcripts, census.get("gate-check", []))
    scaffold_hits = collect_check_activity(src.transcripts, census.get("scaffold-type", []))

    rows: list[dict] = []
    for cls, artifacts in census.items():
        for a in artifacts:
            note_parts: list[str] = []
            row: dict = {
                "artifact": a,
                "cls": cls,
                "invocations": None,
                "last_seen": None,
                "applicability_structural": None,
                "applicability_recent": None,
                "liveness": None,
                "mentions": None,
                "evidence_note": "",
                "immune": None,
                "verdict": None,
            }
            if cls in ("command", "fragment"):
                if inv.measurable:
                    c = inv.data.get(a)
                    if cls == "command":
                        row["invocations"] = {
                            "typed": c["typed"] if c else 0,
                            "skill": c["skill"] if c else 0,
                        }
                        row["last_seen"] = c["last_seen"] if c else None
                else:
                    note_parts.append(_note_for(inv, "invocations"))
            if cls == "rule-pack":
                if app.measurable and a in app.data:
                    row["applicability_structural"] = app.data[a]["structural"]
                    row["applicability_recent"] = app.data[a]["recent"]
                    note_parts.append(app.data[a]["note"])
                else:
                    note_parts.append(_note_for(app, "applicability") or app.reason)
            if cls == "gate-check":
                if chk.measurable:
                    row["invocations"] = {"gate_output_hits": chk.data.get(a, 0)}
                else:
                    note_parts.append(_note_for(chk, "gate-output hits"))
            if cls == "scaffold-type":
                if scaffold_hits.measurable:
                    row["invocations"] = {"transcript_hits": scaffold_hits.data.get(a, 0)}
                else:
                    note_parts.append(_note_for(scaffold_hits, "transcript hits"))
            if live.measurable:
                key = Path(a).name if "/" in a else a
                stem = key[: -len(Path(key).suffix)] if Path(key).suffix else key
                row["liveness"] = live.data.get(a) or live.data.get(key) or live.data.get(stem)
            else:
                note_parts.append(_note_for(live, "liveness"))
            if men.measurable:
                row["mentions"] = men.data.get(mention_key[a])
                if key_owners[mention_key[a]] > 1:
                    # a textual mention cannot tell same-named artifacts apart — say so
                    # instead of silently double-attributing the count
                    row["mentions"] = dict(row["mentions"] or {})
                    note_parts.append(
                        f"mention count shared with {key_owners[mention_key[a]] - 1} "
                        f"other artifact(s) named {mention_key[a]!r}"
                    )
                if row["mentions"] and row["mentions"].get("run_records"):
                    note_parts.append("run-record count is supplementary (nosession collision)")
            else:
                note_parts.append(_note_for(men, "mentions"))
            row["evidence_note"] = "; ".join(p for p in note_parts if p)
            rows.append(row)
    return rows, notes


# ── selftest: the duplex-fixture canary (a check that cannot fail is not a check) ────


def selftest() -> int:
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        if not cond:
            failures.append(what)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # invocations — good counts, bad is unmeasurable-with-reason
        proj = tmp / "t" / "-opt-x"
        proj.mkdir(parents=True)
        good_rows = [
            json.dumps(
                {
                    "type": "user",
                    "message": {"content": "<command-name>/fabrik-review</command-name>"},
                }
            ),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "name": "Skill", "input": {"skill": "fabrik-spec"}}
                        ]
                    },
                }
            ),
        ]
        (proj / "s.jsonl").write_bytes(("\n".join(good_rows) + "\n").encode() + b"\xff\xfe\n")
        s = collect_invocations(tmp / "t")
        expect(
            s.measurable
            and s.data["fabrik-review"]["typed"] == 1
            and s.data["fabrik-spec"]["skill"] == 1,
            "invocations: good fixture must count both channels",
        )
        bad = collect_invocations(tmp / "absent")
        expect(
            not bad.measurable and bool(bad.reason),
            "invocations: empty root must be unmeasurable WITH a reason",
        )
        # applicability — good tiny repo counts, bad (no git) is unmeasurable
        repo = tmp / "repo"
        (repo / ".windsurf" / "rules").mkdir(parents=True)
        (repo / ".windsurf" / "rules" / "p.md").write_text(
            '---\nglobs: ["**/*.py"]\n---\nbody\n'
        )
        (repo / "a.py").write_text("x = 1\n")
        for cmd in (
            ["git", "init", "-q"],
            ["git", "add", "-A"],
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        ):
            subprocess.run(cmd, cwd=repo, capture_output=True, check=False)
        s = collect_applicability(repo, 60)
        expect(
            s.measurable and s.data[".windsurf/rules/p.md"]["structural"] >= 1,
            "applicability: good fixture must match the glob structurally",
        )
        norepo = tmp / "norepo"
        (norepo / ".windsurf" / "rules").mkdir(parents=True)
        (norepo / ".windsurf" / "rules" / "p.md").write_text('---\nglobs: ["*.py"]\n---\n')
        bad = collect_applicability(norepo, 60)
        expect(
            not bad.measurable and "git" in bad.reason,
            "applicability: a non-repo must be unmeasurable naming git",
        )
        # check activity — good counts, bad unmeasurable
        s = collect_check_activity(tmp / "t", ["fabrik-review"])
        expect(s.measurable, "check-activity: good fixture must be measurable")
        bad = collect_check_activity(tmp / "absent", ["x"])
        expect(not bad.measurable, "check-activity: empty root must be unmeasurable")
        # liveness — good fixture report parses, bad path unmeasurable
        rep = tmp / "liveness.json"
        rep.write_text(
            json.dumps({"proofs": {"h": {"findings": [{"id": "c1", "verdict": "LIVE"}]}}})
        )
        s = collect_liveness(Sources(repo=repo, liveness_json=rep))
        expect(
            s.measurable and s.data.get("c1") == "LIVE",
            "liveness: good report must yield verdicts",
        )
        bad = collect_liveness(Sources(repo=repo, liveness_json=tmp / "nope.json"))
        expect(not bad.measurable, "liveness: unreadable report must be unmeasurable")
        # mentions — good counts, bad unmeasurable
        led = tmp / "opt" / "proj" / "docs" / "development" / "reviews"
        led.mkdir(parents=True)
        (led / "r.md").write_text("we ran check_changelog.py twice: check_changelog.py\n")
        s = collect_mentions(
            Sources(repo=repo, reviews_root=tmp / "opt", run_records=tmp / "rr"),
            ["check_changelog.py"],
        )
        expect(
            s.measurable and s.data["check_changelog.py"]["ledgers"] == 2,
            "mentions: good fixture must count ledger hits",
        )
        bad = collect_mentions(
            Sources(repo=repo, reviews_root=tmp / "empty", run_records=tmp / "rr"), ["x"]
        )
        expect(not bad.measurable, "mentions: no ledgers must be unmeasurable")

    if failures:
        for f in failures:
            print(f"✗ selftest: {f}")
        return 1
    print("✓ selftest: all collectors fire on bad input and count on good input")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--json", action="store_true", help="run the census, print rows as JSON")
    g.add_argument("--selftest", action="store_true", help="duplex-fixture canary")
    ap.add_argument(
        "--since-days",
        type=int,
        default=int(os.getenv("KAIZEN_SINCE_DAYS", "60")),
        help="git window for applicability_recent (default 60)",
    )
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    src = Sources(since_days=args.since_days)
    rows, notes = audit(src)
    print(json.dumps({"rows": rows, "census_notes": notes, "total": len(rows)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
