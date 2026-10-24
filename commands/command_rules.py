# AFTER-EDIT: docs/reference/command-corpus-check.md
"""The lean program's rule test: a command's text split into keyed units, a rewrite diffed against
its baseline, and every rule ledger under ``commands/_rules/`` asserted against a render.

Spec: docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md § The rule test.
``assemble_commands.py --check`` and ``tests/test_command_rules.py`` both call ``losses()``, the one
place the rule lives. ``losses()`` never raises: a malformed ledger is one LOSS line.

COBRA (D-253): the cheapest passes are writing no ledger (kaizen's per-phase test closes it), a
ledger with no baseline or an ``unchanged`` label on a vanished unit (refused here), labelling every
vanished unit ``narrative`` (``class_counts`` prints the split for the classifier seats and the
audit pair), and an ``enforced:`` naming a refusal test on an unrelated call (the lint ties the
test to the script the ``text`` carrier names; the audit pair reads the test).
"""

from __future__ import annotations

import ast
import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent  # commands/
RULES = ROOT / "_rules"
SHARED = "_shared"

# ── units ─────────────────────────────────────────────────────────────────────────────────────
# U2 (recorded with the tooling): EXACT match after normalisation. A unit is keyed by its nearest
# heading, so a move across sections vanishes; a comment body never carries a rule. The split and
# the normalisation are the ledger's key contract and change only with a D-row.
_ABBREV = re.compile(r"\b(?:e\.g|i\.e|etc|vs|cf)\.$")
_BOUNDARY = re.compile(r"[.!?](?=\s+[A-Z0-9`*(\[\"“⚠])")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_EMPHASIS = re.compile(r"\*\*|__")
_INCLUDE = re.compile(r"^\s*\{\{include:[^}]+\}\}\s*$")


def _outside_code(s: str, fn) -> str:
    parts = s.split("`")
    return "`".join(fn(p) if i % 2 == 0 else p for i, p in enumerate(parts))


def normalise(s: str) -> str:
    s = _outside_code(s, lambda p: _EMPHASIS.sub("", p))
    s = " ".join(s.split())
    return s[:-1] if s.endswith(".") else s


def _split_prose(text: str) -> list[str]:
    text = " ".join(text.split())
    out, start, in_code = [], 0, False
    for i, ch in enumerate(text):
        if ch == "`":
            in_code = not in_code
        if in_code or ch not in ".!?" or not _BOUNDARY.match(text, i):
            continue
        piece = text[start : i + 1]
        last = piece.rsplit(" ", 1)[-1]
        if _ABBREV.search(last) or last[:-1].isdigit():
            continue
        out.append(piece)
        start = i + 1
    out.append(text[start:])
    return [p for p in (x.strip() for x in out) if p]


def units(text: str) -> list[tuple[str, str, str]]:
    """``(heading, kind, text)`` for every unit, in order; kind is heading|table|fence|comment|prose."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        lines = lines[end + 1 :] if end is not None else lines
    out: list[tuple[str, str, str]] = []
    heading = ""
    block: list[str] = []
    fence: list[str] | None = None
    comment: list[str] | None = None

    def flush() -> None:
        if block:
            out.extend((heading, "prose", s) for s in _split_prose(" ".join(block)))
            block.clear()

    for line in lines:
        s = line.strip()
        if fence is not None:
            if s.startswith("```"):
                out.append((heading, "fence", "\n".join(fence)))
                fence = None
            else:
                fence.append(s)
            continue
        if comment is not None:
            comment.append(s)
            if "-->" in s:
                out.append((heading, "comment", " ".join(comment)))
                comment = None
            continue
        if s.startswith("```"):
            flush()
            fence = []
        elif s.startswith("<!--"):
            flush()
            if "-->" in s:
                out.append((heading, "comment", s))
            else:
                comment = [s]
        elif not s or _INCLUDE.match(s):
            flush()
        elif s.startswith("#"):
            flush()
            heading = s
            out.append((heading, "heading", s))
        elif s.startswith("|"):
            flush()
            out.append((heading, "table", s))
        elif _LIST.match(line):
            flush()
            block.append(_LIST.sub("", line, count=1))
        else:
            block.append(s)
    if fence is not None:
        out.append((heading, "fence", "\n".join(fence)))
    if comment is not None:
        out.append((heading, "comment", " ".join(comment)))
    flush()
    return [(h, k, n) for h, k, t in out if (n := normalise(t) if k != "fence" else t)]


def keys(text: str) -> list[str]:
    """The comparable keys of ``text``: ``<heading> ¦ <unit>``, comments excluded."""
    return [f"{h} ¦ {t}" for h, k, t in units(text) if k != "comment"]


def vanished(baseline: list[str], current_text: str) -> list[int]:
    """1-based baseline line numbers whose key has no exact match in ``current_text``."""
    have = set(keys(current_text))
    return [i for i, k in enumerate(baseline, 1) if k not in have]


def own_text(source: str) -> str:
    """A command source's own text: every ``{{include:…}}`` line blanked (the fragment is its own)."""
    return "\n".join("" if _INCLUDE.match(ln) else ln for ln in source.splitlines())


# ── ledgers ───────────────────────────────────────────────────────────────────────────────────
_TOP = {"command", "shared", "baseline_sentences", "baseline_sha256", "entries", "retired", "vanished"}
_ENTRY = {"id", "file", "section", "baseline", "current", "text", "ordered", "forbidden", "enforced", "pins"}
_CARRIERS = ("text", "ordered", "forbidden", "enforced")
_REFUSAL_SHAPES = (
    re.compile(r"\b(?:returncode|exit_code)\s*(?:!=\s*0\b|==\s*[1-9]\d*)"),
    re.compile(r"pytest\.raises\(\s*SystemExit"),
    re.compile(r"assert\s+not\s+[\w.\[\]()'\"/ ]+\.exists\(\)"),
)


class Malformed(Exception):
    pass


def _strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _section_text(text: str, section: str) -> str | None:
    """The body under the heading line ``section`` (up to the next heading of the same or a higher level)."""
    lines = text.splitlines()
    want = section.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == want:
            level = len(want) - len(want.lstrip("#"))
            body = []
            for nxt in lines[i + 1 :]:
                st = nxt.strip()
                if st.startswith("#") and len(st) - len(st.lstrip("#")) <= level:
                    break
                body.append(nxt)
            return "\n".join(body)
    return None


def _lint_enforced(node: str, root: Path, phrases: list[str]) -> str | None:
    path, _, func = node.partition("::")
    p = (root / path).resolve()
    if not func or not p.is_file() or root.resolve() not in p.parents:
        return f"enforced {node!r} names no test file"
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return f"enforced {node!r} does not parse ({exc.msg})"
    fn = next(
        (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func),
        None,
    )
    if fn is None:
        return f"enforced {node!r}: no function {func!r}"
    body = ast.get_source_segment(p.read_text(encoding="utf-8"), fn) or ""
    body = "\n".join(ln.split("#", 1)[0] for ln in body.splitlines())
    if not any(r.search(body) for r in _REFUSAL_SHAPES):
        return f"enforced {node!r} asserts no refusal (a printed-text assert is a text pin)"
    scripts = {m for ph in phrases for m in re.findall(r"[\w./-]+\.(?:py|sh)\b", ph)}
    if not any(Path(s).name in body for s in scripts):
        return f"enforced {node!r} never invokes the script its text carrier names"
    return None


def _decision_rows(root: Path) -> dict[str, str]:
    p = root / "docs" / "DECISIONS.md"
    rows: dict[str, str] = {}
    if p.is_file():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\|\s*(D-\d+)\s*\|", ln)
            if m:
                rows[m.group(1)] = ln
    return rows


def load_ledger(path: Path, root: Path) -> dict[str, Any]:
    """The validated ledger at ``path``; raises ``Malformed`` with the reason."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise Malformed(f"unreadable ({type(exc).__name__})") from exc
    if not isinstance(data, dict):
        raise Malformed("not a mapping")
    if unknown := set(data) - _TOP:
        raise Malformed(f"unknown key(s) {sorted(unknown)}")
    shared = path.parent.name == SHARED
    if shared != ("shared" in data) or ("command" in data) == shared:
        raise Malformed("a ledger names exactly one of `command:` (commands/_rules/) or `shared:` (commands/_rules/_shared/)")
    ids: dict[str, dict] = {}
    for e in data.get("entries") or []:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str):
            raise Malformed("an entry is not a mapping with an id")
        if unknown := set(e) - _ENTRY:
            raise Malformed(f"entry {e['id']}: unknown key(s) {sorted(unknown)}")
        if e["id"] in ids:
            raise Malformed(f"duplicate entry id {e['id']}")
        if not any(e.get(c) for c in _CARRIERS):
            raise Malformed(f"entry {e['id']}: no carrier")
        if e.get("enforced") and not e.get("text"):
            raise Malformed(f"entry {e['id']}: `enforced` needs a `text` carrier naming the invocation")
        for c in ("text", "forbidden", "ordered", "pins"):
            if c in e and not (isinstance(e[c], list) and all(isinstance(x, str) for x in e[c])):
                raise Malformed(f"entry {e['id']}: `{c}` is not a list of strings")
        f = str(e.get("file") or "")
        if f and f != "render" and not f.startswith("_agents/"):
            rp = (root / f).resolve()
            if root.resolve() not in rp.parents:
                raise Malformed(f"entry {e['id']}: file {f!r} escapes the repo")
        if e.get("enforced") and (why := _lint_enforced(str(e["enforced"]), root, e["text"])):
            raise Malformed(f"entry {e['id']}: {why}")
        ids[e["id"]] = e
    for e in ids.values():
        files = {str(ids[o].get("file") or "render") for o in e.get("ordered") or [] if o in ids}
        if len(files | {str(e.get("file") or "render")}) > 1 or any(o not in ids for o in e.get("ordered") or []):
            raise Malformed(f"entry {e['id']}: `ordered` names an unknown id or spans files")
    rows = _decision_rows(root)
    retired: set[str] = set()
    for r in data.get("retired") or []:
        ent = r.get("entry") if isinstance(r, dict) else None
        if not isinstance(ent, dict) or not isinstance(ent.get("id"), str):
            raise Malformed("a retired row keeps its full entry under `entry:`")
        if ent.get("forbidden"):
            raise Malformed(f"retired {ent['id']}: an absence pin is never retired")
        row = rows.get(str(r.get("decision") or ""))
        if row is None or ent["id"] not in row:
            raise Malformed(f"retired {ent['id']}: decision {r.get('decision')!r} has no D-row naming it")
        retired.add(ent["id"])
    for key, label in (data.get("vanished") or {}).items():
        if not re.fullmatch(r"L\d+", str(key)):
            raise Malformed(f"vanished key {key!r} is not a baseline line (L<n>)")
        if label == "narrative":
            continue
        if isinstance(label, dict) and set(label) == {"rule"} and isinstance(label["rule"], list):
            named = label["rule"]
        elif isinstance(label, dict) and set(label) == {"duplicate-of"}:
            named = [label["duplicate-of"]]
        else:
            raise Malformed(f"vanished {key}: label {label!r} is not rule: [ids], duplicate-of: id or narrative")
        if bad := [n for n in named if n not in ids or n in retired]:
            raise Malformed(f"vanished {key}: names unknown or retired id(s) {bad}")
    data["_ids"] = ids
    return data


def _resolve(entry: dict, ledger: dict, render_dir: Path, root: Path) -> Path:
    f = str(entry.get("file") or "")
    if not f:
        return root / ledger["shared"] if "shared" in ledger else render_dir / f"{ledger['command']}.md"
    if f == "render":
        return render_dir / f"{ledger['command']}.md"
    return render_dir / f if f.startswith("_agents/") else root / f


def _check(ledger: dict, path: Path, render_dir: Path, root: Path, src_dir: Path) -> list[str]:
    name = path.relative_to(path.parents[1] if path.parent.name == SHARED else path.parent)
    loss: list[str] = []
    base = path.parent / str(ledger.get("baseline_sentences") or "")
    if not ledger.get("baseline_sentences") or not base.is_file():
        return [f"LOSS {name}: baseline file missing"]
    raw = base.read_bytes()
    if hashlib.sha256(raw).hexdigest() != str(ledger.get("baseline_sha256") or ""):
        return [f"LOSS {name}: baseline_sha256 does not match {base.name}"]
    baseline = raw.decode("utf-8").splitlines()
    if "shared" in ledger:
        own = (root / ledger["shared"]).read_text(encoding="utf-8") if (root / ledger["shared"]).is_file() else None
    else:
        src = src_dir / f"{ledger['command']}.md"
        own = own_text(src.read_text(encoding="utf-8")) if src.is_file() else None
    if own is None:
        return [f"LOSS {name}: its own text is missing"]
    labels = ledger.get("vanished") or {}
    for n in vanished(baseline, own):
        if f"L{n}" not in labels:
            loss.append(f"LOSS {name}: baseline L{n} vanished, unclassified — {baseline[n - 1][:120]}")
    positions: dict[str, int] = {}
    for e in ledger["_ids"].values():
        f = _resolve(e, ledger, render_dir, root)
        if not f.is_file():
            loss.append(f"LOSS {name} {e['id']}: file {f.name} missing")
            continue
        text = f.read_text(encoding="utf-8")
        live = _strip_comments(text)
        for ph in e.get("forbidden") or []:
            if ph in text:
                loss.append(f"LOSS {name} {e['id']}: forbidden phrase present — {ph[:80]}")
        cur = e.get("current")
        if not cur:
            continue
        scope = _section_text(live, e["section"]) if e.get("section") else live
        if scope is None:
            loss.append(f"LOSS {name} {e['id']}: section {e['section']!r} missing")
            continue
        flat = " ".join(scope.split())
        want = " ".join(str(cur).split())
        at = flat.find(want)
        if at < 0:
            loss.append(f"LOSS {name} {e['id']}: `current` not found under its section")
            continue
        positions[e["id"]] = " ".join(live.split()).find(want)
        for ph in e.get("text") or []:
            if " ".join(ph.split()) not in want:
                loss.append(f"LOSS {name} {e['id']}: text phrase not in `current` — {ph[:80]}")
    for e in ledger["_ids"].values():
        seq = [positions.get(o, -1) for o in e.get("ordered") or []]
        if seq and (min(seq) < 0 or seq != sorted(seq)):
            loss.append(f"LOSS {name} {e['id']}: `ordered` entries out of order or missing")
    return loss


def class_counts(ledger: dict) -> Counter:
    return Counter(
        "narrative" if v == "narrative" else next(iter(v)) for v in (ledger.get("vanished") or {}).values()
    )


def ledgers(rules: Path | None = None) -> list[Path]:
    rules = RULES if rules is None else rules
    if not rules.is_dir():
        return []
    return sorted(rules.glob("*.yaml")) + sorted((rules / SHARED).glob("*.yaml"))


def losses(render_dir: Path, root: Path, src_dir: Path, rules: Path | None = None) -> list[str]:
    """Every LOSS line for the ledgers under ``rules``; never raises. A command ledger whose command
    has no source in ``src_dir`` is skipped (a fixture tree never meets the live ledgers)."""
    out: list[str] = []
    for path in ledgers(rules):
        try:
            led = load_ledger(path, root)
            if "command" in led and not (src_dir / f"{led['command']}.md").is_file():
                continue
            out += _check(led, path, render_dir, root, src_dir)
        except Malformed as exc:
            out.append(f"LOSS {path.name}: malformed — {exc}")
        except Exception as exc:  # noqa: BLE001 — losses() never raises: a crash is a LOSS, not drift
            out.append(f"LOSS {path.name}: unreadable — {type(exc).__name__}: {exc}")
    return out


def entry_counts(rules: Path | None = None) -> dict[str, int]:
    """Each ledger's entry count (kaizen's ledger-size trigger reads the printed form)."""
    counts: dict[str, int] = {}
    for path in ledgers(rules):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            counts[path.name] = len(data.get("entries") or []) if isinstance(data, dict) else 0
        except (OSError, yaml.YAMLError):
            counts[path.name] = 0
    return counts


def write_baseline(text: str, out: Path) -> str:
    """Write ``text``'s keys, one per line, to ``out``; return its sha256 for ``baseline_sha256:``."""
    data = ("\n".join(keys(text)) + "\n").encode("utf-8")
    out.write_bytes(data)
    return hashlib.sha256(data).hexdigest()
