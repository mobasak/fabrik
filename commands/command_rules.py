# AFTER-EDIT: docs/reference/command-corpus-check.md
"""The lean program's rule test: a command's text split into keyed units, a rewrite diffed against
its baseline, and every rule ledger under ``commands/_rules/`` asserted against a render.

Spec: the lean command corpus design (W-96f36043) § The rule test.
``assemble_commands.py --check`` and ``tests/test_command_rules.py`` both call ``losses()``, the one
place the rule lives. ``losses()`` never raises: a malformed ledger is one LOSS line.

COBRA (D-253): the cheapest passes are writing no ledger (kaizen's per-phase test closes it), a
ledger with no baseline or an ``unchanged`` or empty label on a vanished unit (refused here),
labelling every vanished unit ``narrative`` (``summary()`` prints the split for the classifier
seats and the audit pair), and an ``enforced:`` naming a refusal test on an unrelated call (the
lint ties the test's own asserts to the script the ``text`` carrier names; the audit pair reads it).
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent  # commands/
RULES = ROOT / "_rules"
SRC_DIR = ROOT / "_sources"
SHARED = "_shared"

# ── units ─────────────────────────────────────────────────────────────────────────────────────
# U2 (recorded with the tooling): EXACT match after normalisation. A unit is keyed by its nearest
# (normalised) heading, so a move across sections vanishes; a comment body never carries a rule;
# a fenced block is one unit whose lines are joined by " ⏎ ", so every key is one line. The split
# and the normalisation are the ledger's key contract and change only with a D-row.
_ABBREV = re.compile(r"\b(?:e\.g|i\.e|etc|vs|cf)\.$")
_BOUNDARY = re.compile(r"[.!?](?=\s+[A-Z0-9`*(\[\"“⚠])")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_EMPHASIS = re.compile(r"\*\*|__")
_INCLUDE = re.compile(r"^\s*\{\{include:[^}]+\}\}\s*$")
_FENCE_JOIN = " ⏎ "
# the renderer splices ONLY this exact line (assemble_commands.py render(): `^\{\{include:([\w-]+)\}\}$`)
_SPLICE = re.compile(r"^\{\{include:[\w-]+\}\}$")


def _outside_code(s: str, fn) -> str:
    parts = s.split("`")
    return "`".join(fn(p) if i % 2 == 0 else p for i, p in enumerate(parts))


def normalise(s: str) -> str:
    # idempotent, because `_check` re-normalises a stored `current` (W-a9b5e763 slice C): emphasis is
    # stripped to a fixed point ("_**_" leaves "__"), then trailing periods AND the spaces before them
    # ("404 ." would otherwise give "404 ", then "404")
    prev = None
    while s != prev:
        prev, s = s, _outside_code(s, lambda p: _EMPHASIS.sub("", p))
    return " ".join(s.split()).rstrip(" .")


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


def _is_heading(s: str) -> bool:
    return bool(re.match(r"#{1,6}\s", s))


def units(text: str, front_matter: bool = True, splices: bool = False) -> list[tuple[str, str, str]]:
    """``(heading, kind, text)`` for every unit, in order; kind is heading|table|fence|comment|prose.
    A leading ``---`` block is front matter only for a whole file (``front_matter``); a section
    body that opens with a ``---`` rule keeps every unit. An ``{{include:…}}`` line is no unit (the
    fragment's text is its own; inside a fence the line is blanked); with ``splices`` each line the
    renderer splices also yields a ``splice`` unit, so a caller sees where a fragment lands."""
    lines = text.splitlines()
    if front_matter and lines and lines[0].strip() == "---":
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
                out.append((heading, "fence", _FENCE_JOIN.join(fence)))
                fence = None
            else:
                fence.append("" if _INCLUDE.match(s) else " ".join(s.split()))
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
            if s and splices and _SPLICE.match(line):
                out.append((heading, "splice", s))
        elif _is_heading(s):
            flush()
            heading = normalise(s)
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
        out.append((heading, "fence", _FENCE_JOIN.join(fence)))
    if comment is not None:
        out.append((heading, "comment", " ".join(comment)))
    flush()
    return [(h, k, n) for h, k, t in out if (n := normalise(t) if k != "fence" else t)]


def keys(text: str) -> list[str]:
    """The comparable keys of ``text``: ``<heading> ¦ <unit>``, comments excluded; one line each."""
    return [f"{h} ¦ {t}" for h, k, t in units(text) if k != "comment"]


def vanished(baseline: list[str], current_text: str) -> list[int]:
    """1-based baseline line numbers whose key has no exact match left in ``current_text``,
    counted with multiplicity: a unit the baseline holds twice and the rewrite once vanishes once."""
    have = Counter(keys(current_text))
    out = []
    for i, k in enumerate(baseline, 1):
        if have[k] > 0:
            have[k] -= 1
        else:
            out.append(i)
    return out


def generate_unchanged(baseline_path: Path, new_own_text: str) -> list[dict[str, Any]]:
    """The light form's generated entries (§ The rule test step 9): one ``text`` carrier per
    baseline prose or table unit whose key survives in ``new_own_text``, with multiplicity — a unit
    the baseline holds twice and the rewrite once yields one entry. Heading units are skipped (a
    heading is not inside its own section's scope), and so are fences (no single sentence) and
    comments (they carry no rule). Each entry is ``{id: u-L<n>, file: render, section, baseline,
    current, text}``. ``section`` is omitted — the unit pinned to the whole file instead — for a unit
    under no heading, for a unit that follows a spliced ``{{include:…}}`` line inside its section (the
    render splices the fragment there, and a heading inside it re-parents what follows), and for a
    unit under a heading the file repeats (``_scope`` resolves a section name to its FIRST heading)."""
    found = units(new_own_text, splices=True)
    repeated = {h for h, n in Counter(h for h, k, _t in found if k == "heading").items() if n > 1}
    seen: dict[str, list[tuple[str, bool]]] = {}
    after = False
    for h, k, t in found:
        if k == "heading":
            after = False
        elif k == "splice":
            after = True
        elif k != "comment":
            seen.setdefault(f"{h} ¦ {t}", []).append((k, after))
    out: list[dict[str, Any]] = []
    for i, key in enumerate(_read_baseline(baseline_path.read_bytes()), 1):
        if not seen.get(key):
            continue
        kind, spliced = seen[key].pop(0)
        if kind not in ("prose", "table"):
            continue
        heading, unit = key.split(" ¦ ", 1)
        entry: dict[str, Any] = {"id": f"u-L{i}", "file": "render"}
        if heading and not spliced and heading not in repeated:
            entry["section"] = heading
        entry.update(baseline=unit, current=unit, text=[unit])
        out.append(entry)
    return out


def own_text(source: str) -> str:
    """A command source's own text. An ``{{include:…}}`` line stays as a marker (``units()`` skips
    it, so the fragment's text is never own text; ``generate_unchanged`` reads where it splices)."""
    return "\n".join(source.splitlines())


def _read_baseline(raw: bytes) -> list[str]:
    text = raw.decode("utf-8")
    if not text:
        return []
    lines = text.split("\n")
    return lines[:-1] if lines[-1] == "" else lines


def write_baseline(text: str, out: Path) -> str:
    """Write ``text``'s keys, one per line, to ``out``; return its sha256 for ``baseline_sha256:``."""
    ks = keys(text)
    data = ("\n".join(ks) + "\n" if ks else "").encode("utf-8")
    out.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


# ── ledgers ───────────────────────────────────────────────────────────────────────────────────
_TOP = {"command", "shared", "baseline_sentences", "baseline_sha256", "entries", "retired", "vanished"}
_ENTRY = {"id", "file", "section", "baseline", "current", "text", "ordered", "forbidden", "enforced", "pins", "changed-by", "class", "clauses"}
_CLASSES = ("ban", "grammar", "behavioural", "prose")
# D-1236 lint A: a baseline holding one of these is class ban unless the entry says otherwise
# NEVER and MUST are the decision's capitalised tokens (case-sensitive); the lowercase four match any case
_BAN = re.compile(r"(?<!\w)(?:NEVER|MUST|(?i:only|not|refus\w*|stays))(?!\w)")
_EMPH1 = re.compile(r"(?<!\w)_+(?=\w)|(?<=\w)_+(?!\w)")  # single-underscore emphasis: _NOT_, _never_
LINTS = True  # the D-1236 ledger lints (run in `_check`); the older fixture tests switch them off, the lint tests on
_WORD = re.compile(r"\w+(?:['’]\w+)*")
_CARRIERS = ("text", "ordered", "forbidden", "enforced")
_REFUSAL = re.compile(r"\b(?:returncode|exit_code)\s*(?:!=\s*0\b|==\s*[1-9]\d*)")


class LedgerError(Exception):
    pass


class _NoDupLoader(yaml.SafeLoader):
    """A SafeLoader that refuses a duplicate mapping key instead of keeping the last one."""


def _no_dup_mapping(loader: _NoDupLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise LedgerError(f"duplicate key {key!r}")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_NoDupLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dup_mapping)


def _live_lines(text: str) -> list[str]:
    """``text``'s lines with HTML comments blanked and fenced lines marked (prefixed ``\0``). A
    comment is what ``units()`` calls one: a block whose first line STARTS with ``<!--``, through the
    line holding ``-->``, outside a fence; an inline ``<!-- … -->`` (a code span naming one) stays
    text, or a unit carrying it could never be found as a ``current``."""
    out, fence, comment = [], False, False
    for ln in text.split("\n"):
        st = ln.strip()
        if comment:
            out.append("")
            comment = "-->" not in st
        elif st.startswith("```"):
            fence = not fence
            out.append("\0" + ln)
        elif fence:
            out.append("\0" + ln)
        elif st.startswith("<!--"):
            out.append("")
            comment = "-->" not in st
        else:
            out.append(ln)
    return out


def _scope(text: str, section: str | None) -> tuple[str, int] | None:
    """``(body, line)``: the live text under the heading ``section`` (up to the next heading of the
    same or a higher level, fenced lines never read as headings) and the heading's line index, or
    the whole live file and 0; comments removed."""
    lines = _live_lines(text)
    if not section:
        return "\n".join(ln.lstrip("\0") for ln in lines), 0
    want = normalise(section)
    level = len(section.strip()) - len(section.strip().lstrip("#"))
    for i, ln in enumerate(lines):
        if not ln.startswith("\0") and _is_heading(ln.strip()) and normalise(ln.strip()) == want:
            body = []
            for nxt in lines[i + 1 :]:
                st = nxt.strip()
                if not nxt.startswith("\0") and _is_heading(st) and len(st) - len(st.lstrip("#")) <= level:
                    break
                body.append(nxt.lstrip("\0"))
            return "\n".join(body), i
    return None


def _lint_enforced(node: str, root: Path, phrases: list[str]) -> str | None:
    path, _, rest = node.partition("::")
    func = rest.rsplit("::", 1)[-1].split("[", 1)[0]
    p = (root / path).resolve()
    if not func or not p.is_file() or root.resolve() not in p.parents:
        return f"enforced {node!r} names no test file"
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return f"enforced {node!r} does not parse ({type(exc).__name__})"
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func]
    if len(fns) != 1:
        return f"enforced {node!r}: {len(fns)} functions named {func!r}, need exactly one"
    fn = fns[0]
    # Only the function's own asserts and `with pytest.raises(...)` items count — never a string,
    # a comment, a docstring or an unrelated variable.
    refusal = False
    for n in ast.walk(fn):
        if isinstance(n, ast.Assert):
            src = ast.unparse(n.test)
            if _REFUSAL.search(src) or re.match(r"not\s+.+\.exists\(\)$", src):
                refusal = True
        elif isinstance(n, ast.With):
            for item in n.items:
                if re.match(r"pytest\.raises\(\s*SystemExit", ast.unparse(item.context_expr)):
                    refusal = True
    if not refusal:
        return f"enforced {node!r} asserts no refusal (a printed-text assert is a text pin)"
    named = {Path(m).name for ph in phrases for m in re.findall(r"[\w./-]+\.(?:py|sh)\b", ph)}
    # only a call that RUNS something — a subprocess/runner callee, never print() or a logger
    called = {
        Path(tok).name
        for call in ast.walk(fn)
        if isinstance(call, ast.Call) and _runner(call)
        for arg in [*call.args, *(k.value for k in call.keywords)]
        for n in ast.walk(arg)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        for tok in n.value.split()
    }
    if not named & called:
        return f"enforced {node!r} never invokes the script its text carrier names"
    return None


_RUNNERS = {"run", "Popen", "call", "check_call", "check_output", "invoke", "main", "spawn", "exec"}


def _runner(call: ast.Call) -> bool:
    f = call.func
    name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
    return name in _RUNNERS or name.startswith("run_") or name.endswith("_run")


def _decision_rows(root: Path) -> dict[str, str]:
    p = root / "docs" / "DECISIONS.md"
    rows: dict[str, str] = {}
    if p.is_file():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\|\s*(D-\d+)\s*\|", ln)
            if m:
                rows[m.group(1)] = ln
    return rows


def _strs(v: Any) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(x, str) and x.strip() for x in v)


def _inside(path: Path, base: Path) -> bool:
    return base.resolve() == path.resolve() or base.resolve() in path.resolve().parents


def _changed_by(e: dict, rows: dict[str, str], label: str) -> None:
    """§ The rule test step 8: a rule changed on purpose lists each D-row that changed it — distinct
    rows of docs/DECISIONS.md, each naming the entry id (as a `retired` row's decision must)."""
    if "changed-by" not in e:
        return
    cb = e["changed-by"]
    pat = rf"(?<![\w-]){re.escape(e['id'])}(?![\w-])"
    if not (_strs(cb) and len(set(cb)) == len(cb) and all(d in rows and re.search(pat, rows[d]) for d in cb)):
        raise LedgerError(f"{label} {e['id']}: `changed-by` is not a list of distinct D-rows in docs/DECISIONS.md naming {e['id']}")


def load_ledger(path: Path, root: Path) -> dict[str, Any]:
    """The validated ledger at ``path``; raises ``LedgerError`` with the reason."""
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_NoDupLoader)  # noqa: S506 # nosec B506 — a SafeLoader subclass
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise LedgerError(f"unreadable ({type(exc).__name__})") from exc
    if not isinstance(data, dict):
        raise LedgerError("not a mapping")
    if unknown := set(data) - _TOP:
        raise LedgerError(f"unknown key(s) {sorted(map(str, unknown))}")
    shared = path.parent.name == SHARED
    if shared != ("shared" in data) or ("command" in data) == shared:
        raise LedgerError("a ledger names exactly one of `command:` (commands/_rules/) or `shared:` (commands/_rules/_shared/)")
    name = data.get("shared") if shared else data.get("command")
    if not isinstance(name, str) or not name.strip():
        raise LedgerError("`command:`/`shared:` is not a non-empty string")
    if shared and not _inside(root / name, root):
        raise LedgerError(f"shared {name!r} escapes the repo")
    if not shared and ("/" in name or "\\" in name or name.startswith(".")):
        raise LedgerError(f"command {name!r} is not a bare command name")
    bs = data.get("baseline_sentences")
    if isinstance(bs, str) and ("/" in bs or "\\" in bs or bs.startswith(".")):
        raise LedgerError(f"baseline_sentences {bs!r} is not a file beside the ledger")
    for k in ("baseline_sentences", "baseline_sha256"):
        if k in data and not isinstance(data[k], str):
            raise LedgerError(f"`{k}` must be a quoted string")
    for k, kind in (("entries", list), ("retired", list), ("vanished", dict)):
        if data.get(k) is not None and not isinstance(data[k], kind):
            raise LedgerError(f"`{k}` is not a {kind.__name__}")
    ids: dict[str, dict] = {}
    for e in data.get("entries") or []:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str):
            raise LedgerError("an entry is not a mapping with a string id")
        if unknown := set(e) - _ENTRY:
            raise LedgerError(f"entry {e['id']}: unknown key(s) {sorted(map(str, unknown))}")
        if e["id"] in ids:
            raise LedgerError(f"duplicate entry id {e['id']}")
        if not any(e.get(c) for c in _CARRIERS):
            raise LedgerError(f"entry {e['id']}: no carrier")
        for c in ("text", "forbidden", "ordered", "pins"):
            if c in e and not _strs(e[c]):
                raise LedgerError(f"entry {e['id']}: `{c}` is not a non-empty list of non-empty strings")
        # a `text` phrase is compared AFTER normalise, so one that normalises to nothing ("...", "**")
        # matches every unit; a `forbidden` phrase is matched raw, so "**" is a legitimate absence pin
        if "text" in e and not all(normalise(p) for p in e["text"]):
            raise LedgerError(f"entry {e['id']}: a `text` phrase normalises to nothing, so it matches every text")
        if "class" in e and e["class"] not in _CLASSES:
            raise LedgerError(f"entry {e['id']}: `class` is not one of {'|'.join(_CLASSES)}")
        if "clauses" in e:
            cl = e["clauses"]
            ok = isinstance(cl, dict) and bool(cl) and all(
                re.fullmatch(r"[1-9]\d*", str(k))
                and (v == "narrative" or (isinstance(v, dict) and set(v) == {"duplicate-of"} and isinstance(v["duplicate-of"], str)))
                for k, v in cl.items()
            )
            if not ok:
                raise LedgerError(f"entry {e['id']}: `clauses` is not {{<n>: narrative | duplicate-of: id}}")
        for c in ("file", "section", "baseline", "current", "enforced"):
            if c in e and not isinstance(e[c], str):
                raise LedgerError(f"entry {e['id']}: `{c}` is not a string")
        if e.get("enforced") and not e.get("text"):
            raise LedgerError(f"entry {e['id']}: `enforced` needs a `text` carrier naming the invocation")
        f = e.get("file") or ""
        if shared and f == "render":
            raise LedgerError(f"entry {e['id']}: a shared ledger has no `render` (its file is the shared file)")
        if f.startswith("_agents/"):
            if not _inside(Path("/r") / f, Path("/r/_agents")) or ".." in Path(f).parts:
                raise LedgerError(f"entry {e['id']}: file {f!r} escapes the render's _agents/")
        elif f and f != "render" and not _inside(root / f, root):
            raise LedgerError(f"entry {e['id']}: file {f!r} escapes the repo")
        if e.get("enforced") and (why := _lint_enforced(e["enforced"], root, e["text"])):
            raise LedgerError(f"entry {e['id']}: {why}")
        ids[e["id"]] = e
    for e in ids.values():
        order = e.get("ordered") or []
        files = {ids[o].get("file") or "render" for o in order if o in ids}
        if any(o not in ids for o in order) or len(files | {e.get("file") or "render"}) > 1:
            raise LedgerError(f"entry {e['id']}: `ordered` names an unknown id or spans files")
    for e in ids.values():
        _check_clauses(e, ids)
    rows = _decision_rows(root)
    for e in ids.values():
        _changed_by(e, rows, "entry")
    retired: set[str] = set()
    for r in data.get("retired") or []:
        ent = r.get("entry") if isinstance(r, dict) else None
        if not isinstance(ent, dict) or not isinstance(ent.get("id"), str):
            raise LedgerError("a retired row keeps its full entry under `entry:`")
        if ent.get("forbidden"):
            raise LedgerError(f"retired {ent['id']}: an absence pin is never retired")
        _changed_by(ent, rows, "retired")
        row = rows.get(str(r.get("decision") or ""))
        if row is None or not re.search(rf"(?<![\w-]){re.escape(ent['id'])}(?![\w-])", row):
            raise LedgerError(f"retired {ent['id']}: decision {r.get('decision')!r} has no D-row naming it")
        if ent["id"] in ids:
            raise LedgerError(f"retired {ent['id']}: also a live entry")
        retired.add(ent["id"])
    for key, label in (data.get("vanished") or {}).items():
        if not isinstance(key, str) or not re.fullmatch(r"L[1-9]\d*", key):
            raise LedgerError(f"vanished key {key!r} is not a baseline line (L<n>)")
        if label == "narrative":
            continue
        if isinstance(label, dict) and set(label) == {"rule"} and _strs(label["rule"]):
            named = label["rule"]
        elif isinstance(label, dict) and set(label) == {"duplicate-of"} and isinstance(label["duplicate-of"], str):
            named = [label["duplicate-of"]]
        else:
            raise LedgerError(f"vanished {key}: label {label!r} is not rule: [ids], duplicate-of: id or narrative")
        if bad := [n for n in named if n not in ids or n in retired]:
            raise LedgerError(f"vanished {key}: names unknown or retired id(s) {bad}")
    data["_ids"] = ids
    return data


def _deemph(s: str) -> str:
    return _outside_code(s, lambda p: _EMPH1.sub("", p))


def _words(s: str) -> list[str]:
    """Normalised lowercase words (curly apostrophes read straight, single-underscore emphasis dropped)."""
    return _WORD.findall(_deemph(normalise(s)).lower().replace("’", "'"))


def _has_run(hay: list[str], needle: list[str]) -> bool:
    n = len(needle)
    return bool(n) and any(hay[i : i + n] == needle for i in range(len(hay) - n + 1))


def _is_ban(baseline: object) -> bool:
    return isinstance(baseline, str) and bool(_BAN.search(_deemph(baseline)))


def entry_class(e: dict) -> str:
    """The entry's class: its `class:` field, else `ban` when its baseline holds a ban token, else `prose`.
    Total on malformed YAML (an invalid `class:` falls back to inference; `load_ledger` is what refuses it)."""
    c = e.get("class")
    if isinstance(c, str) and c in _CLASSES:
        return c
    return "ban" if _is_ban(e.get("baseline")) else "prose"


_SEP = re.compile(r"`[^`]*`|;|\s[–—]\s|—|\s--\s")


def _clauses(baseline: str) -> list[str]:
    """Split at `;`, a spaced `—` `–` `--` or an unspaced `—`, never inside a backtick code span."""
    out, last = [], 0
    for m in _SEP.finditer(baseline):
        if m.group(0).startswith("`"):
            continue
        out.append(baseline[last : m.start()])
        last = m.end()
    out.append(baseline[last:])
    return [c.strip() for c in out if c.strip()]


def _check_clauses(e: dict, ids: dict[str, dict]) -> None:
    cl = e.get("clauses")
    if not cl:
        return
    parts = _clauses(e["baseline"]) if isinstance(e.get("baseline"), str) else []
    if not parts:
        raise LedgerError(f"entry {e['id']}: `clauses` needs a `baseline`")
    for k, v in cl.items():
        n = int(k)
        if n > len(parts):
            raise LedgerError(f"entry {e['id']}: `clauses` key {n} is past the baseline's {len(parts)} clause(s)")
        if v == "narrative":
            if _is_ban(parts[n - 1]):
                raise LedgerError(f"entry {e['id']}: clause {n} holds a ban token and cannot be `narrative`")
        elif v["duplicate-of"] not in ids or v["duplicate-of"] == e["id"]:
            raise LedgerError(f"entry {e['id']}: clause {n} is a duplicate-of unknown id {v['duplicate-of']!r}")


def _covered(clause: str, phrases: list[list[str]]) -> bool:
    cw = _words(clause)
    for pw in phrases:
        if _has_run(pw, cw):
            return True
        if len(cw) >= 6 and any(_has_run(pw, cw[i : i + 6]) for i in range(len(cw) - 5)):
            return True
    return False


def _paras(scope: str) -> list[str]:
    """Blank-line paragraphs: an odd backtick in one (a fence line) must not flip code parity in the rest."""
    return re.split(r"\n\s*\n", scope)


def _lintable(e: dict) -> bool:
    """Entries written under D-1236 only: a `class:`, `clauses:` or `pins:`, or a ban-token baseline.
    A legacy prose entry with none of these is never newly failed."""
    return bool(e.get("baseline")) and bool(e.get("class") or e.get("clauses") or e.get("pins") or _is_ban(e["baseline"]))


def _lint(e: dict, scope: str) -> list[tuple[str, str]]:
    """D-1236 lints on one entry, ``scope`` being the live text under its section (or the whole file):
    ``(lint, message)`` pairs. A: every (ban token, next word) pair of the baseline is in a text carrier.
    B: each clause is covered by a text phrase (whole, or a 6-word window) or labelled in `clauses:`.
    C: a text phrase is >=6 words and appears once as whole words in ``scope`` (a phrase equal to the whole
    `current` unit is exempt: the unit match anchors it). D: in classes ban/grammar/behavioural each
    unlabelled clause stays verbatim in the LIVE ``scope``, with or without a `current`.
    COBRA (D-253): the cheapest abuse is a stub carrier, then a reworded clause; A and B read the immutable
    `baseline`, C and D the live file, the author-blind audit pair reads each reworded entry. The cheapest
    pass left is a `duplicate-of` label to a live id (checked at load), or no `class:` on a baseline with
    no ban token, which is the decision's own scope."""
    if not _lintable(e):
        return []
    out: list[tuple[str, str]] = []
    phrases = e.get("text") or []
    cur = normalise(e["current"]) if e.get("current") else None
    paras = [normalise(p) for p in _paras(scope)]
    for ph in phrases:
        if cur is not None and normalise(ph) == cur:
            continue
        if len(_words(ph)) < 6:
            out.append(("C", f"text phrase under 6 words — {ph[:80]}"))
        elif (n := sum(len(re.findall(rf"(?<!\w){re.escape(normalise(ph))}(?!\w)", p)) for p in paras)) != 1:
            out.append(("C", f"text phrase appears {n}x in its section, need exactly once — {ph[:80]}"))
    base = e["baseline"]
    cls = entry_class(e)
    pw = [_words(p) for p in phrases]
    if cls == "ban":
        db, pairs = _deemph(base), set()
        for m in _BAN.finditer(db):
            nxt = _words(db[m.end() :])[:1]
            pairs.add((m.group(0).lower(), nxt[0] if nxt else None))
        for tok, nxt in sorted(pairs, key=str):
            need = [tok] + ([nxt] if nxt else [])
            if not any(_has_run(w, need) for w in pw):
                out.append(("A", f"ban token {tok!r} (with the word after it) is in no text carrier"))
    cl = {str(k) for k in (e.get("clauses") or {})}
    live = [w for p in _paras(scope) for w in _words(p)]
    for n, clause in enumerate(_clauses(base), 1):
        if str(n) in cl or not _words(clause):
            continue
        if not _covered(clause, pw):
            out.append(("B", f"baseline clause {n} is in no text phrase and is not classified — {clause[:80]}"))
        elif cls != "prose" and not _has_run(live, _words(clause)):
            out.append(("D", f"class {cls}: clause {n} is not verbatim in the live text — {clause[:80]}"))
    return out


def _resolve(entry: dict, ledger: dict, render_dir: Path, root: Path) -> Path:
    f = entry.get("file") or ""
    if "shared" in ledger and not f:
        return root / ledger["shared"]
    if not f or f == "render":
        return render_dir / f"{ledger['command']}.md"
    return render_dir / f if f.startswith("_agents/") else root / f


def _check(ledger: dict, path: Path, render_dir: Path, root: Path, src_dir: Path) -> list[str]:
    name = path.name if path.parent.name != SHARED else f"{SHARED}/{path.name}"
    base = path.parent / (ledger.get("baseline_sentences") or "")
    if not ledger.get("baseline_sentences") or not base.is_file():
        return [f"LOSS {name}: baseline file missing"]
    raw = base.read_bytes()
    if hashlib.sha256(raw).hexdigest() != (ledger.get("baseline_sha256") or ""):
        return [f"LOSS {name}: baseline_sha256 does not match {base.name}"]
    baseline = _read_baseline(raw)
    own_path = root / ledger["shared"] if "shared" in ledger else src_dir / f"{ledger['command']}.md"
    if not own_path.is_file():
        return [f"LOSS {name}: its own text {own_path.name} is missing"]
    own = own_path.read_text(encoding="utf-8")
    own = own if "shared" in ledger else own_text(own)
    loss: list[str] = []
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
        flat_all = " ".join(text.split())
        for ph in e.get("forbidden") or []:
            if " ".join(ph.split()) in flat_all:
                loss.append(f"LOSS {name} {e['id']}: forbidden phrase present — {ph[:80]}")
        found = _scope(text, e.get("section"))
        if found is None:
            loss.append(f"LOSS {name} {e['id']}: section {e['section']!r} missing")
            continue
        scope, start = found
        for lint, msg in _lint(e, scope) if LINTS else []:
            loss.append(f"LOSS {name} {e['id']}: lint {lint} — {msg}")
        where = "under its section" if e.get("section") else "in its file"
        cur = e.get("current")
        if cur:
            mine = [t for _h, k, t in units(scope, front_matter=not e.get("section")) if k != "comment"]
            want = next((c for c in (normalise(cur), " ".join(cur.split())) if c in mine), None)
            if want is None:
                loss.append(f"LOSS {name} {e['id']}: `current` is not a unit {where}")
                continue
            # `ordered` compares each entry's unit index in the WHOLE live file: the units before
            # its section's heading line (heading included), plus its index inside the section
            before = units("\n".join(ln.lstrip("\0") for ln in _live_lines(text)[: start + 1])) if e.get("section") else []
            positions[e["id"]] = len([u for u in before if u[1] != "comment"]) + mine.index(want)
            for ph in e.get("text") or []:
                if normalise(ph) not in want:
                    loss.append(f"LOSS {name} {e['id']}: text phrase not in `current` — {ph[:80]}")
        else:
            flat = normalise(scope)
            for ph in e.get("text") or []:
                if normalise(ph) not in flat:
                    loss.append(f"LOSS {name} {e['id']}: text phrase not {where} — {ph[:80]}")
    for e in ledger["_ids"].values():
        seq = [positions.get(o) for o in e.get("ordered") or []]
        at = [p for p in seq if p is not None]
        if seq and (len(at) < len(seq) or at != sorted(at)):
            loss.append(f"LOSS {name} {e['id']}: `ordered` entries out of order or missing")
    return loss


def ledgers(rules: Path | None = None) -> list[Path]:
    rules = RULES if rules is None else rules
    if not rules.is_dir():
        return []
    found: list[Path] = []
    for d in (rules, rules / SHARED):
        if d.exists():
            names = os.listdir(d)  # raises on an unreadable dir, where Path.glob returns nothing
            found += sorted(d / n for n in names if (d / n).is_file() and Path(n).suffix in (".yaml", ".yml"))
    return found


def losses(render_dir: Path, root: Path, src_dir: Path, rules: Path | None = None) -> list[str]:
    """Every LOSS line for the ledgers under ``rules``; never raises. A command ledger whose
    command has no source in a FIXTURE ``src_dir`` is skipped (a fixture tree never meets the live
    ledgers); against the live ``commands/_sources/`` a missing source is a LOSS."""
    out: list[str] = []
    try:
        live = src_dir.resolve() == SRC_DIR.resolve()
        paths = ledgers(rules)
    except Exception as exc:  # noqa: BLE001 — losses() never raises
        return [f"LOSS rules: unreadable — {type(exc).__name__}: {exc}"]
    for path in paths:
        try:
            if path.suffix == ".yml":
                raise LedgerError("a ledger is named *.yaml")
            led = load_ledger(path, root)
            if "command" in led and not (src_dir / f"{led['command']}.md").is_file():
                if live:
                    out.append(f"LOSS {path.name}: command {led['command']!r} has no source in commands/_sources/")
                continue
            out += _check(led, path, render_dir, root, src_dir)
        except LedgerError as exc:
            out.append(f"LOSS {path.name}: malformed — {exc}")
        except Exception as exc:  # noqa: BLE001 — losses() never raises: a crash is a LOSS, not drift
            out.append(f"LOSS {path.name}: unreadable — {type(exc).__name__}: {exc}")
    return out


def summary(rules: Path | None = None) -> list[str]:
    """One line per ledger — entry count and the vanished-label split — never raising (kaizen's
    ledger-size trigger and the classifier seats read it)."""
    lines = []
    try:
        paths = ledgers(rules)
    except Exception as exc:  # noqa: BLE001 — a report line, never a crash
        return [f"LEDGER rules: unreadable — {type(exc).__name__}"]
    for path in paths:
        try:
            data = yaml.load(path.read_text(encoding="utf-8"), Loader=_NoDupLoader) or {}  # noqa: S506 # nosec B506 — a SafeLoader subclass
            entries = data.get("entries") if isinstance(data, dict) else None
            van = data.get("vanished") if isinstance(data, dict) else None
            n = len(entries) if isinstance(entries, list) else 0
            split = Counter(
                v if isinstance(v, str) else (next(iter(v)) if isinstance(v, dict) and v else "?")
                for v in (van.values() if isinstance(van, dict) else [])
            )
            cls = Counter(entry_class(x) for x in entries if isinstance(x, dict)) if isinstance(entries, list) else {}
            lines.append(f"LEDGER {path.name}: {n} entries · classes {dict(sorted(cls.items()))} · vanished {dict(sorted(split.items()))}")
        except Exception as exc:  # noqa: BLE001 — a report line, never a crash
            lines.append(f"LEDGER {path.name}: unreadable — {type(exc).__name__}")
    return lines
