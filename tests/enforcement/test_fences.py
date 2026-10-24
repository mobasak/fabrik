"""W-276255e7: `scripts/enforcement/_fences.py` — one linear scanner with the EXACT match set of the fence regexes it
replaced. The old regexes are kept here, and only here, as the oracle: their block alternative backtracked over
every backtick-run length and scanned to the end of the text per opener (15.7 s on 81 KB, 10.2 s on one 200 KB
run), and `FENCE_BLOCK`/`_HTML_COMMENT` were quadratic on the same check_convergence path."""

from __future__ import annotations

import importlib
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENF = ROOT / "scripts" / "enforcement"
if str(ENF) not in sys.path:
    sys.path.insert(0, str(ENF))

OLD_STRIP = re.compile(r"(?:^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$|```[^`\n]+```)", re.M | re.S)
OLD_CONTENTS = re.compile(
    r"^[ \t]*(`{3,})[^\n]*\n(.*?)^[ \t]*\1[ \t]*$|```([^`\n]+)```", re.M | re.S
)
OLD_INFO = re.compile(r"^[ \t]*(`{3,})([^\n]*)\n(.*?)^[ \t]*\1[ \t]*$", re.M | re.S)
OLD_FENCE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.S)
OLD_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# The inputs the two critique seats built by hand, beyond what the fuzz alphabet reaches.
FIXTURES = [
    "",
    "\n",
    "```\n```",
    "```\r\nx\r\n```\r\n",
    "```\r\nx\n```\n",
    "a\n```py\nbody\n```",
    "```\nunclosed",
    "````\na\n```\nb\n````\n",
    "`````\nx\n```\n",
    "````\nx\n```\nmore\n",
    "\t ```\nx\n \t```\t\n",
    "```é\n中 x\n```\n",
    " ```\nx\n```\n",
    "```a``` tail\n```\nb\n```\n",
    "```\n```\n```\n```\n",
    "x ```a``` y ```b```\n```\nz\n```\n```c```",
    "```\nbody\n```\n```d```",
    "``````\nx\n``````",
    "```a\rb```",
    "<!-- a --> b <!-- c",
    "<!--<!-- -->-->",
    "```\n<!-- x\n```\n-->",
]


def _fences():
    return importlib.import_module("_fences")


def _assert_same(f, t: str) -> None:
    assert f.strip(t) == OLD_STRIP.sub("", t), repr(t)
    assert f.FENCE_STRIP.sub(" FENCED ", t) == OLD_STRIP.sub(" FENCED ", t), repr(t)
    contents = [m.group(2) or m.group(3) or "" for m in OLD_CONTENTS.finditer(t)]
    assert [(b.body if b else inl) or "" for _, _, inl, b in f.fence_spans(t)] == contents, repr(t)
    assert [(b.run, b.info, b.body) for b in f.fence_blocks(t)] == OLD_INFO.findall(t), repr(t)
    assert f.fence_block_bodies(t) == OLD_FENCE_BLOCK.findall(t), repr(t)
    assert f.strip_html_comments(t) == OLD_HTML_COMMENT.sub("", t), repr(t)


def test_scanner_equals_the_old_regexes_on_fuzz_and_fixtures() -> None:
    f = _fences()
    for t in FIXTURES:
        _assert_same(f, t)
    rng = random.Random(276255)
    tokens = [
        "`",
        "``",
        "```",
        "````",
        "`````",
        " ",
        "\t",
        "\n",
        "\n",
        "\n",
        "a",
        "b c",
        "\r",
        "~~~",
        "> ",
        "<!--",
        "-->",
    ]
    for _ in range(20000):
        _assert_same(f, "".join(rng.choice(tokens) for _ in range(rng.randint(0, 40))))


WORST = {
    "400 distinct-length backtick lines": "\n".join("`" * (3 + i) for i in range(400)) + "\n",
    "one 200 KB backtick run": "`" * 200_000,
    "a 200 KB backtick run and a newline": "`" * 200_000 + "\n",
    "20 000 unclosed openers": "```x\n" * 20_000,
    "50 000 comment openers": "<!--" * 50_000,
}


@pytest.mark.parametrize("label", list(WORST))
def test_scanner_is_linear_on_the_old_regexes_worst_inputs(label: str) -> None:
    """Each input cost the old regexes seconds (10-16 s for the first three); the bound is far below that and
    far above the scanner's milliseconds, so a busy box does not flake it."""
    f = _fences()
    sys.path.insert(0, str(ROOT))
    from scripts.enforcement import check_convergence as cc

    t = WORST[label]
    start = time.perf_counter()
    f.strip(t)
    f.fence_block_bodies(t)
    f.strip_html_comments(t)
    cc._blank_quoted(t)
    cc._nontrivial_fences(t)
    cc._elided_probes(t)
    assert time.perf_counter() - start < 2.0, label


CONSUMERS = (
    "check_plan_tickets",
    "check_plan_quality",
    "check_ticket_breadth",
    "check_test_proposal",
)
OLD_TEXTS = (
    r"(?:^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$|```[^`\n]+```)",
    r"^[ \t]*(`{3,})[^\n]*\n(.*?)^[ \t]*\1[ \t]*$|```([^`\n]+)```",
    r"^[ \t]*(`{3,})([^\n]*)\n(.*?)^[ \t]*\1[ \t]*$",
    r"```[^\n]*\n(.*?)```",
    r"<!--.*?-->",
)


def test_every_consumer_uses_the_shared_scanner() -> None:
    f = _fences()
    sys.path.insert(0, str(ROOT))
    for name in CONSUMERS:
        mod = importlib.import_module(f"scripts.enforcement.{name}")
        assert mod._FENCE_RE is f.FENCE_STRIP, name
    cc = importlib.import_module("scripts.enforcement.check_convergence")
    assert cc.FENCE_STRIP is f.FENCE_STRIP
    for path in [ENF / f"{n}.py" for n in (*CONSUMERS, "check_convergence")] + [
        ROOT / "scripts" / "docs_updater.py"
    ]:
        src = path.read_text(encoding="utf-8")
        for old in OLD_TEXTS:
            assert old not in src, (path.name, old)


def test_fence_strip_sub_refuses_a_backslash_repl() -> None:
    with pytest.raises(ValueError):
        _fences().FENCE_STRIP.sub(r"\1", "```a```")


def test_docs_updater_imports_the_scanner_lazily(tmp_path: Path) -> None:
    """A project whose scripts/enforcement/ lacks _fences.py still imports docs_updater (its --sync, renders and
    merge-owner adoption need no fence); only the parse that needs the scanner fails, naming the file."""
    scripts = tmp_path / "scripts"
    (scripts / "enforcement").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "docs_updater.py", scripts / "docs_updater.py")
    prog = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('du_probe', {str(scripts / 'docs_updater.py')!r})\n"
        "mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)\n"
        "print('IMPORTED')\n"
        "try:\n"
        "    mod._strip_quoted('x')\n"
        "except ImportError as exc:\n"
        "    print('PARSE-ERROR', exc)\n"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", prog], capture_output=True, text=True, timeout=60, check=False
    )
    assert "IMPORTED" in out.stdout, out.stderr[-800:]
    assert "PARSE-ERROR" in out.stdout and "scripts/enforcement/_fences.py" in out.stdout, (
        out.stdout + out.stderr[-800:]
    )


def test_docs_updater_names_a_scanner_without_the_span_blanker(tmp_path: Path) -> None:
    """W-b9af1d47: a _fences.py that predates blank_code_spans is present but lacks the name; docs_updater's span
    blanking raises its named ImportError, as for a missing file, never a bare AttributeError."""
    scripts = tmp_path / "scripts"
    (scripts / "enforcement").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "docs_updater.py", scripts / "docs_updater.py")
    (scripts / "enforcement" / "_fences.py").write_text(
        "def strip(text, repl=''):\n    return text\n"
    )
    prog = (
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('du_probe', {str(scripts / 'docs_updater.py')!r})\n"
        "mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)\n"
        "try:\n"
        "    mod._blank_code_spans('`x`')\n"
        "except ImportError as exc:\n"
        "    print('NAMED', exc)\n"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-B", "-c", prog],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "NAMED" in out.stdout and "no blank_code_spans" in out.stdout, (
        out.stdout + out.stderr[-800:]
    )


# ── W-d2eef742: the plan checks' three fence strips ────────────────────────────────────────────────────────────
# The regexes they replaced, kept as the oracle. plan_appetite's pair took 15.8 s on a 40 KB backtick run, a newline
# and 40 KB of text; check_phase_tests' backreference pair and check_plan_lock_release's run-length `_FENCE`
# backtracked the same way on unclosed openers and on one long run with no newline.
OLD_PA_BACKTICK = re.compile(r"^[ \t]*`{3,}[^\n]*\n.*?^[ \t]*`{3,}[ \t]*$", re.M | re.S)
OLD_PA_TILDE = re.compile(r"^[ \t]*~{3,}[^\n]*\n.*?^[ \t]*~{3,}[ \t]*$", re.M | re.S)
OLD_PA_OPEN = re.compile(r"^[ \t]*(?:`{3,}|~{3,})[^\n]*$", re.M)
OLD_LOCK = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n(?:.*?^[ \t]*\1[ \t]*$|.*\Z)", re.M | re.S)
OLD_PHASE = r"(?ms)^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*$"


def _old_plan_appetite_strip(text: str) -> str:
    text = OLD_PA_TILDE.sub("", OLD_PA_BACKTICK.sub("", text))
    dangling = OLD_PA_OPEN.search(text)
    return text[: dangling.start()] if dangling else text


def _plan_strips() -> dict:
    sys.path.insert(0, str(ROOT))
    from scripts.enforcement import check_plan_lock_release as lr
    from scripts.enforcement import plan_appetite as pa

    return {
        "plan_appetite": (pa.strip_fences, _old_plan_appetite_strip),
        "lock_release": (lr._strip_fences, lambda t: OLD_LOCK.sub("", t)),
        "phase_tests": (_fences().strip_three_marker_fences, lambda t: re.sub(OLD_PHASE, "", t)),
    }


PLAN_FIXTURES = [
    "",
    "```\na\n```\n",
    "```py\nStatus: EXECUTED\n```\nStatus: IN-PROGRESS\n",
    "~~~\nx\n~~~~\nafter",
    "````\nx\n```\ny\n````\nz",
    "```\nx\n~~~\ny\n```\n",
    "```\n~~~\nAppetite: 1\n```\n~~~\nAppetite: 2\n",
    "  ```\n\tx\n ```  \nrest",
    "```\nunclosed\nStatus: EXECUTED\n",
    "~~~",
    "```x\r\nbody\r\n```\r\nafter\r\n",
    "text\n```",
    "```\n```\n```\n",
    "```\x0b\nx\n```\x0c\n ```\n",
]


@pytest.mark.parametrize("name", ["plan_appetite", "lock_release", "phase_tests"])
def test_plan_strips_equal_the_old_regexes(name: str) -> None:
    new, old = _plan_strips()[name]
    for t in PLAN_FIXTURES:
        assert new(t) == old(t), (name, t)
    rng = random.Random(0xD2EEF742)
    tokens = [
        "`",
        "``",
        "```",
        "````",
        "~",
        "~~~",
        "~~~~",
        " ",
        "\t",
        "\n",
        "\n",
        "\n",
        "a",
        "\r",
        "> ",
    ]
    for _ in range(20000):
        t = "".join(rng.choice(tokens) for _ in range(rng.randint(0, 40)))
        assert new(t) == old(t), (name, t)


PLAN_WORST = {
    "a 40 KB backtick run, a newline and 40 KB of text": "`" * 40_000 + "\n" + "x" * 40_000,
    "one 200 KB backtick run, no newline": "`" * 200_000,
    "20 000 unclosed ``` openers": "```x\n" * 20_000,
    "20 000 unclosed ~~~ openers": "~~~x\n" * 20_000,
}
# Which strip each input was slow for before W-d2eef742 (seconds on this box): plan_appetite 15.8 on the first and
# about 15 on the last two, check_phase_tests about 15 on the last two, check_plan_lock_release about 20 on the second.
PLAN_WORST_FOR = {
    "a 40 KB backtick run, a newline and 40 KB of text": ("plan_appetite",),
    "one 200 KB backtick run, no newline": ("lock_release",),
    "20 000 unclosed ``` openers": ("plan_appetite", "phase_tests"),
    "20 000 unclosed ~~~ openers": ("plan_appetite", "phase_tests"),
}


@pytest.mark.parametrize("label", list(PLAN_WORST))
def test_plan_strips_are_linear_on_the_slow_inputs(label: str) -> None:
    """The bound is test_scanner_is_linear's: far below the old regexes' seconds, far above the milliseconds."""
    t = PLAN_WORST[label]
    for name, (new, _) in _plan_strips().items():
        start = time.perf_counter()
        new(t)
        assert time.perf_counter() - start < 2.0, (name, label, PLAN_WORST_FOR[label])


def test_plan_strip_consumers_dropped_the_old_regexes() -> None:
    olds = (OLD_PA_BACKTICK.pattern, OLD_PA_TILDE.pattern, OLD_LOCK.pattern, OLD_PHASE)
    for rel in ("plan_appetite.py", "check_plan_lock_release.py", "check_phase_tests.py"):
        src = (ENF / rel).read_text(encoding="utf-8")
        for old in olds:
            assert old not in src, (rel, old)


def test_phase_tests_fails_soft_without_the_scanner(tmp_path: Path) -> None:
    """check_phase_tests is a warn_only gate row, and a warn_only row that exits non-zero is a blocking red
    (final_gate.py's run_optional_check). Where _fences.py is missing it must still exit 0: the module never imports
    the scanner at load, and the import inside _contract_regions fails under the per-lock guard. check_plan_tickets
    is a stub here — the real one imports _fences at load, and its failure would reach the guard first — so the
    `_fences` error on stderr is _contract_regions' own, reached by the live lock below."""
    enf = tmp_path / "scripts" / "enforcement"
    enf.mkdir(parents=True)
    shutil.copy(ENF / "check_phase_tests.py", enf / "check_phase_tests.py")
    (enf / "check_plan_tickets.py").write_text(
        'import re\nGIVEN_ROW_RE = re.compile(r"^\\s*[-*]\\s+(.*Given.*)$", re.M)\n',
        encoding="utf-8",
    )
    locks = tmp_path / ".fabrik" / "plan-locks"
    locks.mkdir(parents=True)
    plan = tmp_path / "docs" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        "# Plan\n\n## Behavior Contract\n\n- **Given** a, when b, then c\n", encoding="utf-8"
    )
    (locks / "p.json").write_text(
        '{"status": "active", "plan": "docs/plan.md", "owned_paths": ["src/**"], "baseline_commit": "HEAD"}',
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-I", str(enf / "check_phase_tests.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stdout + out.stderr[-800:]
    assert "No module named '_fences'" in out.stderr, (
        "the live lock never reached the scanner",
        out.stdout,
        out.stderr[-800:],
    )


def test_the_span_blanker_has_one_copy() -> None:
    """W-b9af1d47: docs_updater blanks inline code spans with `_fences.blank_code_spans`, and check_doc_links and
    check_doc_index blank fences then spans with `_fences.blank_code_examples` (W-85bd72fa) — two copies of one
    parser drift (Lesson 103), so no caller keeps its own scan."""
    du_src = (ROOT / "scripts" / "docs_updater.py").read_text(encoding="utf-8")
    cdl_src = (ENF / "check_doc_links.py").read_text(encoding="utf-8")
    for name in (
        "_BACKTICK_RUN_RE =",
        "_LINK_TAIL_RE =",
        "_BLOCK_START_RE =",
        "_ONE_LINE_BLOCK_RE =",
    ):
        assert name not in du_src and name not in cdl_src, name
    assert 'getattr(_fences_module(), "blank_code_spans"' in du_src
    # W-85bd72fa: both link checks blank code examples (fences, then spans) through one function
    cdi_src = (ENF / "check_doc_index.py").read_text(encoding="utf-8")
    for src in (cdl_src, cdi_src):
        assert 'getattr(_fences, "blank_code_examples"' in src
        assert "def blank_code_spans" not in src and "in_fence ^= toggle" not in src


def test_the_fence_toggle_has_one_live_copy() -> None:
    """W-85bd72fa: check_doc_links skips fenced lines with `_fences.fence_toggle` when `_fences` loads; its
    local predicate is only the no-`_fences` fallback, held equal here so the two cannot drift (Lesson 103)."""
    import _fences
    import check_doc_links as cdl

    src = (ENF / "check_doc_links.py").read_text(encoding="utf-8")
    assert 'getattr(_fences, "fence_toggle"' in src
    lines = [
        "```",
        "```python",
        "   ```",
        "```text more",
        "````",
        "```x```",
        "```inline``` tail",
        "``` `x` ```",
        "```js `x`",
        "~~~",
        "``",
        "plain",
        "",
        "\t```",
        "\f```",
        " ```",
        " ```",
    ]
    for line in lines:
        assert cdl._local_fence_toggle(line) == _fences.fence_toggle(line), repr(line)


# W-753040b8: CommonMark's backslash parity for a span OPENER — an odd run of backslashes escapes the run's first
# backtick only (the rest still opens), an even run is escaped backslashes and leaves the backtick live; a backslash
# before a CLOSER is span content (no escapes inside a code span). Expected values are hand-derived from CommonMark.
_B = "\\"


def _blanked(text: str) -> str:
    return _fences().blank_code_spans(text)


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("x `a|b` y", "`a|b`"),
        ("x " + _B + "`a|b` y", None),
        ("x " + _B * 2 + "`a|b` y", "`a|b`"),
        ("x " + _B * 3 + "`a|b` y", None),
        ("x " + _B * 4 + "`a|b` y", "`a|b`"),
    ],
)
def test_blank_code_spans_backslash_parity(text: str, span: str | None) -> None:
    out = _blanked(text)
    if span is None:
        assert out == text
    else:
        start = text.index(span)
        assert out == text[:start] + " " * len(span) + text[start + len(span) :]


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        (
            "x " + _B + "``a` y",
            4,
            7,
        ),  # an escaped double opens a single-backtick span one character later
        ("x " + _B + "```a`` y", 4, 9),  # an escaped triple opens a double
        ("x " + _B * 3 + "``a` y", 6, 9),
    ],
)
def test_blank_code_spans_escaped_run_opens_with_the_rest(text: str, start: int, end: int) -> None:
    assert _blanked(text) == text[:start] + " " * (end - start) + text[end:]


@pytest.mark.parametrize(
    "text", ["x `a" + _B + "` y", "x `a" + _B * 2 + "` y", "x ``a" + _B + "`` y"]
)
def test_blank_code_spans_backslash_before_a_closer_is_content(text: str) -> None:
    out = _blanked(text)
    assert out[:2] == "x " and out[-2:] == " y" and set(out[2:-2]) == {" "}, repr(out)


def test_blank_code_spans_agrees_with_commonmark_on_inline_fuzz() -> None:
    """Single-line inline inputs read the same code spans as markdown-it's CommonMark preset. The alphabet has no
    `[` (link tails) and no block starts (their rules are graded above); an input opening with an unmatched ```
    is skipped — markdown-it reads the tail after it inconsistently with the same tail alone (W-753040b8 measure)."""
    markdown_it = pytest.importorskip(
        "markdown_it", reason="an independent CommonMark parser grades the span model"
    )
    md = markdown_it.MarkdownIt("commonmark")
    fx = _fences()
    real = fx._blank_span

    def ours(text: str) -> list[str]:
        fx._blank_span = lambda t: "\x00" * len(t)
        try:
            out = fx.blank_code_spans(text)
        finally:
            fx._blank_span = real
        spans, k = [], 0
        while k < len(out):
            if out[k] != "\x00":
                k += 1
                continue
            e = k
            while e < len(out) and out[e] == "\x00":
                e += 1
            raw = text[k:e]
            n = len(raw) - len(raw.lstrip("`"))
            body = (
                raw[n : len(raw) - n].replace("\r\n", " ").replace("\n", " ")
            )  # CommonMark: a line ending is a space
            if len(body) >= 2 and body[0] == " " and body[-1] == " " and body.strip(" "):
                body = body[1:-1]
            spans.append(body)
            k = e
        return spans

    def commonmark(text: str) -> list[str]:
        # md.parse, not parseInline: a line break inside a paragraph is read as the block parser reads it
        return [
            c.content
            for t in md.parse(text)
            if t.type == "inline"
            for c in (t.children or [])
            if c.type == "code_inline"
        ]

    rng = random.Random(0x753040B8)
    tokens = ["`", "``", "```", _B, _B * 2, "a", " ", "b", "\n", "\r\n"]
    seen = 0
    for _ in range(6000):
        text = "".join(rng.choice(tokens) for _ in range(rng.randint(1, 14)))
        lines = text.replace("\r\n", "\n").split("\n")
        # one paragraph only: no blank line, no edge whitespace, no fence-opening line (block rules are not
        # this fuzz's subject)
        if any(not ln.strip() or ln != ln.strip() or ln.startswith("```") for ln in lines):
            continue
        assert ours(text) == commonmark(text), repr(text)
        seen += 1
    assert seen > 1500, seen
