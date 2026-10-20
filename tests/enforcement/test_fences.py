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
