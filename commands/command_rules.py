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
_CARRIERS = ("text", "ordered", "forbidden", "enforced")
_REFUSAL = re.compile(r"\b(?:returncode|exit_code)\s*(?:!=\s*0\b|==\s*[1-9]\d*)")


# ── D-1236: what a reworded carrier must still hold ──────────────────────────────────────────
# Verbatim binds three classes (ban, grammar, behavioural); a ``prose`` carrier may be reworded or
# shrunk to its operative clauses. COBRA (D-253): the cheapest way past these lints is tagging every
# entry ``prose`` and labelling each shrunk clause ``narrative``; the author-blind audit pair reads
# every reworded entry old against new and each receipt states reworded/total beside its weaker-count.
_BAN = re.compile(r"\b(?:never|refus\w*|forbid\w*|must not|do not|don't|cannot|may not)\b", re.I)
_ANCHOR = re.compile(r"`[^`]+`|\b\d[\d.,]*\b|[\w.-]*/[\w./-]+|\b[\w-]+\.(?:py|md|json|sh|ya?ml|js|jsonl)\b|\b(?:never|must|only|refus\w*)\b", re.I)


def clauses_of(baseline: str) -> list[str]:
    """The baseline split at ``;`` and `` — ``, outside backticks and outside any parenthetical (a
    ``(…; …)`` aside is one clause), empty pieces dropped."""
    out, cur, in_code, depth = [], "", False, 0
    i = 0
    while i < len(baseline):
        ch = baseline[i]
        if ch == "`":
            in_code = not in_code
        elif not in_code and ch == "(":
            depth += 1
        elif not in_code and ch == ")":
            depth = max(0, depth - 1)
        if not in_code and depth == 0 and (ch == ";" or baseline.startswith(" — ", i)):
            out.append(cur)
            cur = ""
            i += 1 if ch == ";" else 3
            continue
        cur += ch
        i += 1
    out.append(cur)
    return [c.strip() for c in out if c.strip()]


_HISTORY = re.compile(r"\b[DW]-[0-9a-f]+\b|\b\d{4}-\d{2}-\d{2}\b|\b01M[0-9A-Z]{5,}\b")
_INNER_PAREN = re.compile(r"\([^()]*\)")


def _history_free(text: str) -> str:
    """``text`` with every parenthetical that cites history (a decision or work-item id, an ISO date, a
    mail id, 'measured') removed innermost-first, then the bare ids and dates (spec lever (a))."""
    mark = re.compile(r"\b[DW]-[0-9a-f]+\b|\b\d{4}-\d{2}-\d{2}\b|\b01M[0-9A-Z]{5,}\b|\bmeasured\b|\blive case\b")
    prev = None
    while prev != text:
        prev = text
        text = _INNER_PAREN.sub(lambda m: " " if mark.search(m.group(0)) else m.group(0).replace("(", "\0").replace(")", "\1"), text)
    text = text.replace("\0", "(").replace("\1", ")")
    return _HISTORY.sub(" ", text)


def _anchors(text: str) -> set[str]:
    """What a reworded clause must keep: backticked tokens, numbers, paths and never/must/only/refuse
    words. History (a decision, work-item or mail id, an ISO date, a parenthetical citing one) is no anchor."""
    text = _history_free(text)
    return {normalise(m.group(0)).lower() for m in _ANCHOR.finditer(text) if normalise(m.group(0))}


_STEM = re.compile(r"[a-z]{4,}")
_RECALL = 0.7
_SHORT = 8  # a clause of up to this many stems must be held whole


def _stems(text: str) -> set[str]:
    return {w[:5] for w in _STEM.findall(text.lower())}


def _recall(clause: str, held: str) -> float:
    """The share of ``clause``'s content stems (letters-only words of 4+ letters, cut to 5; a clause of up to 8 stems must be held whole) still in ``held``:
    the mechanical proxy for 'this reworded phrase still says it'. COBRA (D-253): the cheapest way past it is a
    carrier padded with the clause's vocabulary; the carrier is the rewritten text itself, the audit pair reads
    old against new, and a clause with an anchor must also keep every anchor."""
    want = _stems(clause)
    if not want:
        return 1.0
    share = len(want & _stems(held)) / len(want)
    return share if len(want) > _SHORT else float(share == 1.0)


def _class_problems(e: dict, ids: dict[str, dict]) -> list[str]:
    """Every D-1236 loader-lint problem of one entry that carries a ``class`` (empty when clean)."""
    cls = e["class"]
    if cls not in _CLASSES:
        return [f"class {cls!r} is not one of {list(_CLASSES)}"]
    out: list[str] = []
    phrases = [normalise(p) for p in e.get("text") or []]
    base = e.get("baseline") or ""
    if cls == "prose":
        short = [p for p in phrases if len(p.split()) < 6]
        if short:
            out.append(f"a prose `text` phrase is under 6 normalised words — {short[0][:60]}")
    labels = e.get("clauses") or {}
    if not isinstance(labels, dict):
        return out + ["`clauses` is not a mapping"]
    parts = clauses_of(base) if base else []
    # a ban token inside a clause labelled narrative or duplicate-of is history, not a ban
    live_base = " ".join(_history_free(p) for i, p in enumerate(parts, 1) if i not in labels)
    if live_base and (tokens := {m.group(0).lower() for m in _BAN.finditer(live_base)}):
        held = " ".join(phrases).lower()
        if not any(t in held for t in tokens):
            out.append(f"its baseline holds a ban token ({sorted(tokens)[0]!r}) and no `text` carrier does")
    if not base or not phrases:
        return out
    held_text = " ".join(phrases).lower().replace("`", "")
    if " ⏎ " in base:  # a fence is one unit whose ``# …`` comments are not clauses; its lines are the carrier
        return out
    for k, v in labels.items():
        if not isinstance(k, int) or not 1 <= k <= len(parts):
            out.append(f"clauses key {k!r} is not a 1-based clause of its baseline ({len(parts)} clauses)")
        elif v == "narrative":
            continue
        elif not (isinstance(v, dict) and set(v) == {"duplicate-of"} and isinstance(v["duplicate-of"], str) and v["duplicate-of"] in ids):
            out.append(f"clauses {k}: {v!r} is not narrative or duplicate-of: <live id>")
    for n, clause in enumerate(parts, 1):
        bare = re.sub(r"\(\s*[,;]?\s*\)", "", _history_free(clause))
        if n in labels or normalise(bare).lower().replace("`", "") in held_text or not re.search(r"[A-Za-z0-9]", bare):
            continue
        missing = {a for a in _anchors(clause) if a.replace("`", "") not in held_text}
        if not missing and _recall(bare, held_text) >= _RECALL:
            continue
        if missing or not _anchors(clause):
            out.append(
                f"baseline clause {n} is in no `text` phrase and not classified (narrative|duplicate-of) — "
                f"{clause[:70]}" + (f" [lost: {sorted(missing)[:3]}]" if missing else "")
            )
    return out


def _lint_class(e: dict, ids: dict[str, dict]) -> None:
    """Raise the first D-1236 loader-lint problem of one entry that carries a ``class``."""
    if problems := _class_problems(e, ids):
        raise LedgerError(f"entry {e['id']}: {problems[0]}")


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
    live = shared and path.resolve().parent == (RULES / SHARED).resolve()
    for e in ids.values():
        if live and "class" not in e:
            raise LedgerError(f"entry {e['id']}: a live shared ledger entry needs a `class` (ban|grammar|behavioural|prose)")
        if "class" in e:
            _lint_class(e, ids)
    for e in ids.values():
        order = e.get("ordered") or []
        files = {ids[o].get("file") or "render" for o in order if o in ids}
        if any(o not in ids for o in order) or len(files | {e.get("file") or "render"}) > 1:
            raise LedgerError(f"entry {e['id']}: `ordered` names an unknown id or spans files")
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
    flat_base = [normalise(b.split(" ¦ ", 1)[-1]) for b in baseline]
    for e in ledger["_ids"].values():
        if e.get("class") and e.get("baseline") and not any(normalise(e["baseline"]) in b for b in flat_base):
            loss.append(f"LOSS {name} {e['id']}: `baseline` is not text of {base.name} (the baseline is immutable)")
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
        if e.get("class") == "prose":
            whole = normalise(text)
            for ph in e.get("text") or []:
                if whole.count(normalise(ph)) > 1:
                    loss.append(f"LOSS {name} {e['id']}: prose text phrase is not unique in its file — {ph[:80]}")
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
            lines.append(f"LEDGER {path.name}: {n} entries · vanished {dict(sorted(split.items()))}")
        except Exception as exc:  # noqa: BLE001 — a report line, never a crash
            lines.append(f"LEDGER {path.name}: unreadable — {type(exc).__name__}")
    return lines
