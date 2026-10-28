"""The lean program's rule test (W-a9b5e763 slice A): ``commands/command_rules.py`` and the
``assemble_commands.py --check`` LOSS exit. Fixture ledgers live under ``tmp_path``; the live
corpus is rendered here, never read from ``--check``'s temp dir."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cr = _load("command_rules", "commands/command_rules.py")
ac = _load("ac_rules", "commands/assemble_commands.py")


# ── fixture tree: one command source, its render, a rules dir ─────────────────────────────────
SOURCE = """---
description: demo
---
# /demo

## Scope

Run the probe on a copy. Never stage a sibling's file.
{{include:orient}}
Stop at the pin.

## Close

1. Commit by pathspec.
2. Push it.
"""


def _tree(tmp_path: Path, source: str = SOURCE, render: str | None = None) -> dict[str, Path]:
    src = tmp_path / "src"
    out = tmp_path / "render"
    rules = tmp_path / "rules"
    for d in (src, out, rules, rules / "_shared", tmp_path / "docs"):
        d.mkdir(parents=True, exist_ok=True)
    (src / "demo.md").write_text(source, encoding="utf-8")
    (out / "demo.md").write_text(render if render is not None else source, encoding="utf-8")
    (tmp_path / "docs" / "DECISIONS.md").write_text("| D-0001 | 2026-10-25 | x | retires R9 | y | z |\n")
    return {"src": src, "out": out, "rules": rules, "root": tmp_path}


def _ledger(t: dict[str, Path], entries: list[dict], baseline_from: str = SOURCE, **extra) -> Path:
    base = t["rules"] / "demo.baseline.txt"
    sha = cr.write_baseline(cr.own_text(baseline_from), base)
    data = {"command": "demo", "baseline_sentences": base.name, "baseline_sha256": sha, "entries": entries}
    data.update(extra)
    p = t["rules"] / "demo.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return p


def _losses(t: dict[str, Path]) -> list[str]:
    return cr.losses(t["out"], t["root"], t["src"], rules=t["rules"])


def _one(lost: list[str], phrase: str) -> None:
    assert len(lost) == 1 and phrase in lost[0], lost


ENTRY = {"id": "R1", "section": "## Scope", "baseline": "Never stage a sibling's file.",
         "current": "Never stage a sibling's file.", "text": ["Never stage a sibling's file"]}


# ── Behaviour 1 ───────────────────────────────────────────────────────────────────────────────
def test_the_live_corpus_has_no_loss(tmp_path: Path) -> None:
    out = tmp_path / "render"
    ac.render(out, None, agents_dest=out / "_agents")
    assert (out / "fabrik-task.md").is_file(), "the render produced no fabrik-task"
    for line in cr.summary():
        print(line)
    assert cr.losses(out, ROOT, ac.SRC) == []
    # the live path is not vacuous: a ledger on a real command, asserted against the real render
    rules = tmp_path / "rules"
    rules.mkdir()
    source = (ac.SRC / "fabrik-task.md").read_text(encoding="utf-8")
    sha = cr.write_baseline(cr.own_text(source), rules / "fabrik-task.baseline.txt")
    # any real prose unit of the live source (picked, never hardcoded: the program rewrites it)
    heading, unit = next(
        (h, u) for h, k, u in cr.units(cr.own_text(source)) if k == "prose" and h.startswith("## ") and len(u) > 20
    )
    good = {"id": "T1", "section": heading, "current": unit, "text": [unit.split()[0]]}
    led = {"command": "fabrik-task", "baseline_sentences": "fabrik-task.baseline.txt", "baseline_sha256": sha,
           "entries": [good]}
    (rules / "fabrik-task.yaml").write_text(yaml.safe_dump(led, allow_unicode=True), encoding="utf-8")
    assert cr.losses(out, ROOT, ac.SRC, rules=rules) == []
    led["entries"] = [{**good, "text": ["a phrase no command says"]}]
    (rules / "fabrik-task.yaml").write_text(yaml.safe_dump(led, allow_unicode=True), encoding="utf-8")
    _one(cr.losses(out, ROOT, ac.SRC, rules=rules), "text phrase not in `current`")
    (rules / "fabrik-task.yaml").unlink()
    led["command"] = "no-such-command"
    (rules / "renamed.yaml").write_text(yaml.safe_dump(led, allow_unicode=True), encoding="utf-8")
    _one(cr.losses(out, ROOT, ac.SRC, rules=rules), "has no source in commands/_sources/")


# ── Behaviour 2 ───────────────────────────────────────────────────────────────────────────────
def test_units_and_exact_match() -> None:
    text = (
        "---\nx: y\n---\n# T\n\n| a | b |\n|---|---|\n\n```bash\nrun --x\n# note\n```\n"
        "<!-- POOL OFF: Never write NO-POOL. -->\n"
        "2. Use e.g. `a.b` here. Then **stop** now. Read `x. Y` too. Set it to 3. Then i.e. go. Done.\n"
    )
    us = cr.units(text)
    kinds = [k for _h, k, _t in us]
    assert kinds == ["heading", "table", "table", "fence", "comment"] + ["prose"] * 5, us
    assert us[3][2] == "run --x ⏎ # note"  # one unit, one line: a fence's `#` is no heading
    assert us[5][2] == "Use e.g. `a.b` here"  # step number stripped, no split after e.g.
    assert us[6][2] == "Then stop now"  # emphasis stripped, trailing period dropped
    assert us[7][2] == "Read `x. Y` too"  # never split inside a backtick span
    assert us[8][2] == "Set it to 3. Then i.e. go"  # no split after a digit-only token or i.e.
    assert us[9][2] == "Done"
    assert cr.normalise("Never edit `__init__.py`.") == "Never edit `__init__.py`"
    base = cr.keys("## S\n\nNever stage it. Keep going.\n")
    assert cr.vanished(base, "## S\n\nNever   **stage** it.\nKeep going\n") == []
    assert cr.vanished(base, "## **S**\n\nNever stage it. Keep going.\n") == []  # heading emphasis
    assert cr.vanished(base, "## S\n\nNever stage this. Keep going.\n") == [2]
    assert cr.vanished(base, "## Other\n\nNever stage it. Keep going.\n") == [1, 2, 3]
    assert cr.vanished(base, "## S\n\n<!-- Never stage it. -->\nKeep going.\n") == [2]
    commented = cr.keys("## S\n\n<!-- dead note -->\nKeep going.\n")
    assert cr.vanished(commented, "## S\n\nKeep going.\n") == []  # a comment carries no rule to classify
    twice = cr.keys("## S\n\nStop.\n\nStop.\n")
    assert cr.vanished(twice, "## S\n\nStop.\n") == [3]  # multiplicity: one copy deleted vanishes once


def test_a_fenced_baseline_round_trips(tmp_path: Path) -> None:
    src = "## A\n\n```bash\n# note\nrm -rf a\n```\n\nKeep X.\n"
    t = _tree(tmp_path, source=src, render=src)
    _ledger(t, [{"id": "R1", "section": "## A", "current": "Keep X.", "text": ["Keep"]}], baseline_from=src)
    assert _losses(t) == []  # a # line in a fence neither splits the baseline nor ends the section


# ── Behaviour 3 ───────────────────────────────────────────────────────────────────────────────
def _carriers(t: dict[str, Path]) -> list[str]:
    """The carrier and ledger LOSS lines, the D-1236 lint lines left out (their own tests grade them)."""
    return [x for x in _losses(t) if ": lint " not in x]


def test_each_failed_carrier_is_a_loss(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    _ledger(t, [ENTRY])
    assert _losses(t) == []
    t = _tree(tmp_path / "gone", render=SOURCE.replace("Never stage a sibling's file.", "Stage carefully."))
    _ledger(t, [ENTRY])
    _one(_carriers(t), "`current` is not a unit under its section")
    assert any("lint D" in x for x in _losses(t))  # the ban clause left the live text
    longer = SOURCE.replace("Never stage a sibling's file.", "Never stage a sibling's file twice.")
    t = _tree(tmp_path / "longer", render=longer)
    _ledger(t, [ENTRY])
    _one(_carriers(t), "`current` is not a unit")  # a substring of a longer sentence is not the rule
    commented = SOURCE.replace("Never stage a sibling's file.", "<!-- Never stage a sibling's file. -->")
    t = _tree(tmp_path / "commented", render=commented)
    _ledger(t, [ENTRY])
    _one(_carriers(t), "`current` is not a unit")
    t = _tree(tmp_path / "phrase")
    _ledger(t, [{**ENTRY, "text": ["Never commit"]}])
    _one(_carriers(t), "text phrase not in `current`")
    t = _tree(tmp_path / "textonly")
    _ledger(t, [{"id": "R2", "section": "## Scope", "text": ["Never commit"]}])
    _one(_carriers(t), "text phrase not under its section")  # a text carrier with no `current` is checked
    t = _tree(tmp_path / "forbid", render=SOURCE + "\n<!-- always force-\npush -->\n")
    _ledger(t, [{**ENTRY, "forbidden": ["force- push"]}])
    _one(_carriers(t), "forbidden phrase present")  # comments and line wraps included
    t = _tree(tmp_path / "section")
    _ledger(t, [{**ENTRY, "section": "## Close"}])
    _one(_carriers(t), "`current` is not a unit under its section")
    t = _tree(tmp_path / "nosection")
    _ledger(t, [{**ENTRY, "section": "## Absent"}])
    _one(_carriers(t), "section '## Absent' missing")
    deep = SOURCE.replace("## Close", "### Sub\n\nInner line.\n\n## Close")
    t = _tree(tmp_path / "deeper", source=deep, render=deep)
    _ledger(t, [{"id": "R3", "section": "## Scope", "current": "Inner line.", "text": ["Inner"]}], baseline_from=deep)
    assert _losses(t) == []  # a deeper heading stays inside its parent section
    t = _tree(tmp_path / "order")
    entries = [
        {"id": "C1", "section": "## Close", "current": "Commit by pathspec.", "text": ["Commit"]},
        {"id": "C2", "section": "## Close", "current": "Push it.", "text": ["Push"], "ordered": ["C2", "C1"]},
    ]
    _ledger(t, entries)
    _one(_carriers(t), "out of order or missing")
    entries[1]["ordered"] = ["C1", "C2"]
    _ledger(t, entries)
    assert _losses(t) == []
    gone = SOURCE.replace("1. Commit by pathspec.\n", "")
    t = _tree(tmp_path / "ordergone", source=SOURCE, render=gone)
    _ledger(t, entries)
    lost = _losses(t)
    assert any("out of order or missing" in x for x in lost) and len(lost) == 2, lost
    dup = "## Pre\n\nX rule.\n\n## A\n\nY rule.\n\n## B\n\nX rule.\n"
    t = _tree(tmp_path / "orderscope", source=dup, render=dup)
    two = [{"id": "Y", "section": "## A", "current": "Y rule.", "text": ["Y"], "ordered": ["Y", "X"]},
           {"id": "X", "section": "## B", "current": "X rule.", "text": ["X"]}]
    _ledger(t, two, baseline_from=dup)
    assert _losses(t) == []  # `ordered` reads the occurrence under each entry's own section


def test_agents_files_resolve_in_the_render(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    (t["out"] / "_agents").mkdir()
    (t["out"] / "_agents" / "seat.md").write_text("## Seat\n\nRead only.\n")
    seat = {"id": "A1", "file": "_agents/seat.md", "section": "## Seat", "current": "Read only.", "text": ["Read"]}
    _ledger(t, [seat])
    assert _losses(t) == []


# ── Behaviour 4 ───────────────────────────────────────────────────────────────────────────────
def test_classification_and_baseline_losses(tmp_path: Path) -> None:
    rewritten = SOURCE.replace("Run the probe on a copy. ", "")
    t = _tree(tmp_path, source=rewritten, render=rewritten)
    _ledger(t, [ENTRY])
    lost = _losses(t)
    _one(lost, "vanished, unclassified")
    assert "Run the probe on a copy" in lost[0]
    line = next(i for i, k in enumerate(cr.keys(cr.own_text(SOURCE)), 1) if "Run the probe" in k)
    _ledger(t, [ENTRY], vanished={f"L{line}": "narrative"})
    assert _losses(t) == []
    for unrelated in ({"rule": ["R1"]}, {"duplicate-of": "R1"}):  # W-34d76a7a: R1 carries another rule
        _ledger(t, [ENTRY], vanished={f"L{line}": unrelated})
        assert any("vanished as" in x and "lint B" in x for x in _losses(t)), unrelated
    retired = [{"decision": "D-0001", "entry": {"id": "R9", "text": ["x"]}}]
    for bad in ("unchanged", {"rule": ["R7"]}, {"rule": []}, {"duplicate-of": "R7"}, {"rule": ["R9"]}):
        _ledger(t, [ENTRY], vanished={f"L{line}": bad}, retired=retired)
        _one(_losses(t), "malformed")
    for key in ("42", "L0", "Lx"):
        _ledger(t, [ENTRY], vanished={key: "narrative"})
        _one(_losses(t), "is not a baseline line")
    p = _ledger(t, [ENTRY], vanished={f"L{line}": "narrative"})
    base = t["rules"] / "demo.baseline.txt"
    kept = base.read_bytes()
    base.write_text("tampered\n")
    _one(_losses(t), "baseline_sha256 does not match")
    base.write_bytes(kept)
    data = yaml.safe_load(p.read_text())
    del data["baseline_sentences"]
    p.write_text(yaml.safe_dump(data))
    _one(_losses(t), "baseline file missing")  # the file exists; the KEY is what is missing
    data["baseline_sentences"] = "demo.baseline.txt"
    p.write_text(yaml.safe_dump(data))
    base.unlink()
    _one(_losses(t), "baseline file missing")


# ── Behaviour 5 ───────────────────────────────────────────────────────────────────────────────
def _refused(t: dict[str, Path], **override) -> str:
    p = t["rules"] / "demo.yaml"
    base = t["rules"] / "demo.baseline.txt"
    sha = cr.write_baseline(cr.own_text(SOURCE), base)
    data = {"command": "demo", "baseline_sentences": base.name, "baseline_sha256": sha, "entries": [ENTRY]}
    data.update(override)
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    lost = _losses(t)
    assert len(lost) == 1 and "malformed" in lost[0], lost
    return lost[0]


def test_malformed_ledgers_are_one_loss_line_each(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    p = t["rules"] / "demo.yaml"
    p.write_text("- just\n- a list\n")
    assert _losses(t) == ["LOSS demo.yaml: malformed — not a mapping"]
    p.write_text("command: [unclosed\n")
    _one(_losses(t), "unreadable")
    p.write_text("command: demo\ncommand: other\n")
    _one(_losses(t), "duplicate key 'command'")
    p.write_bytes(b"command: \xff\n")
    _one(_losses(t), "unreadable")
    assert "unknown key" in _refused(t, extra=1)
    assert "entry R1: unknown key" in _refused(t, entries=[{**ENTRY, "note": 1}])
    assert "not a mapping with a string id" in _refused(t, entries=[{"id": 7, "text": ["x"]}])
    assert "duplicate entry id" in _refused(t, entries=[ENTRY, ENTRY])
    assert "no carrier" in _refused(t, entries=[{"id": "R2", "current": "Push it."}])
    assert "non-empty list" in _refused(t, entries=[{**ENTRY, "text": [""]}])
    assert "non-empty list" in _refused(t, entries=[{**ENTRY, "text": "Never stage"}])
    assert "`entries` is not a list" in _refused(t, entries=5)
    assert "must be a quoted string" in _refused(t, baseline_sha256=1234)
    assert "is not a non-empty string" in _refused(t, command=None)
    two = [ENTRY, {"id": "R3", "file": "docs/DECISIONS.md", "current": "x", "text": ["x"], "ordered": ["R1"]}]
    assert "spans files" in _refused(t, entries=two)
    assert "unknown id" in _refused(t, entries=[{**ENTRY, "ordered": ["R404"]}])
    assert "escapes the repo" in _refused(t, entries=[{**ENTRY, "file": "../outside.md"}])
    assert "escapes the render's _agents/" in _refused(t, entries=[{**ENTRY, "file": "_agents/../../x.md"}])
    assert "needs a `text` carrier" in _refused(t, entries=[{"id": "R4", "current": "x", "enforced": "t.py::f"}])
    p.write_text("entries: 5\n")
    assert all(x.startswith("LEDGER ") for x in cr.summary(t["rules"]))  # the report never crashes
    (t["rules"] / "demo.yml").write_text("command: demo\n")
    assert any("demo.yml: malformed — a ledger is named *.yaml" in x for x in _losses(t))


def test_the_enforced_lint(tmp_path: Path) -> None:
    base_src = SOURCE.replace("Stop at the pin.", "Run `gate.py` first.")
    t = _tree(tmp_path, source=base_src)
    tests_dir = t["root"] / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_g.py").write_text(
        "import subprocess\n"
        "def test_prints():\n    r = subprocess.run(['gate.py'])\n    assert 'ok' in r.stdout\n"
        "def test_refuses():\n    r = subprocess.run(['gate.py', '--bad'])\n    assert r.returncode != 0\n"
        "def test_other():\n    r = subprocess.run(['other.py'])\n    assert r.returncode == 2\n"
        "def test_string_only():\n    'returncode != 0'\n    r = subprocess.run(['gate.py'])\n    assert r.ok\n"
        "def test_suffix():\n    r = subprocess.run(['data_gate.py', '--bad'])\n    assert r.returncode == 1\n"
    )
    enf = {"id": "R5", "section": "## Scope", "current": "Run `gate.py` first.", "text": ["`gate.py`"]}
    _ledger(t, [{**enf, "enforced": "tests/test_g.py::test_refuses"}], baseline_from=base_src)
    assert _losses(t) == []
    for node, why in (
        ("tests/test_g.py::test_prints", "asserts no refusal"),
        ("tests/test_g.py::test_string_only", "asserts no refusal"),  # a string is no assert
        ("tests/test_g.py::test_other", "never invokes the script"),
        ("tests/test_g.py::test_suffix", "never invokes the script"),  # data_gate.py is not gate.py
        ("tests/test_g.py::test_absent", "0 functions"),
        ("tests/nope.py::test_x", "names no test file"),
    ):
        _ledger(t, [{**enf, "enforced": node}], baseline_from=base_src)
        _one(_losses(t), why)


def test_retired_rows(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    ok = [{"decision": "D-0001", "entry": {"id": "R9", "text": ["x"]}}]
    _ledger(t, [ENTRY], retired=ok)
    assert _losses(t) == []
    assert "never retired" in _refused(t, retired=[{"decision": "D-0001", "entry": {"id": "R9", "forbidden": ["x"]}}])
    assert "no D-row" in _refused(t, retired=[{"decision": "D-0002", "entry": {"id": "R9", "text": ["x"]}}])
    (t["root"] / "docs" / "DECISIONS.md").write_text("| D-0001 | 2026-10-25 | x | retires R90 | y | z |\n")
    assert "no D-row" in _refused(t, retired=ok)  # R9 is not R90
    assert "full entry" in _refused(t, retired=[{"decision": "D-0001"}])


def test_losses_never_raises(tmp_path: Path, monkeypatch) -> None:
    t = _tree(tmp_path)
    _ledger(t, [ENTRY])

    def boom(*_a, **_k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cr, "_check", boom)
    assert _losses(t) == ["LOSS demo.yaml: unreadable — RuntimeError: kaboom"]


# ── Behaviour 6 ───────────────────────────────────────────────────────────────────────────────
def test_shared_and_skipped_ledgers(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    frag = t["root"] / "commands" / "_fragments" / "orient.md"
    frag.parent.mkdir(parents=True)
    frag.write_text("## Orient\n\nRead the packs first.\n")
    base = t["rules"] / "_shared" / "orient.baseline.txt"
    sha = cr.write_baseline(frag.read_text(), base)
    entry = {"id": "O1", "section": "## Orient", "current": "Read the packs first.", "text": ["packs"]}
    led = {"shared": "commands/_fragments/orient.md", "baseline_sentences": base.name, "baseline_sha256": sha,
           "entries": [entry]}
    shared = t["rules"] / "_shared" / "orient.yaml"
    shared.write_text(yaml.safe_dump(led))
    assert _losses(t) == []
    frag.write_text("## Orient\n\nRead the rules.\n")
    lost = _losses(t)
    assert len(lost) == 2 and any("_shared/orient.yaml O1" in x for x in lost), lost
    led["entries"] = [{**entry, "file": "render"}]
    shared.write_text(yaml.safe_dump(led))
    _one(_losses(t), "a shared ledger has no `render`")
    led["entries"] = [entry]
    led["shared"] = "../escape.md"
    shared.write_text(yaml.safe_dump(led))
    _one(_losses(t), "escapes the repo")
    shared.unlink()
    _ledger(t, [ENTRY])
    (t["src"] / "demo.md").unlink()
    assert _losses(t) == []  # a command ledger with no source in a FIXTURE src_dir is skipped


# ── Behaviour 7 ───────────────────────────────────────────────────────────────────────────────
def test_check_exits_4_on_a_loss_and_1_on_drift_alone(tmp_path: Path, monkeypatch, capsys) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "broken.yaml").write_text("- not a mapping\n")
    monkeypatch.setattr(cr, "RULES", rules)
    # 1. LOSS alone: the installed corpus is an exact render, so there is no drift
    inst, skills, agents = tmp_path / "installed", tmp_path / "skills", tmp_path / "agents"
    ac.render(inst, skills, agents_dest=agents)
    monkeypatch.setattr(ac, "OUT", inst)
    monkeypatch.setattr(ac, "SKILLS", skills)
    monkeypatch.setattr(ac, "AGENTS", agents)
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 4
    out = capsys.readouterr().out
    assert "LOSS:" in out and "DRIFT:" not in out, out
    # 2. LOSS and drift: 4 outranks 1, LOSS printed first
    (inst / "fabrik-task.md").write_text("hand edit\n")
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 4
    out = capsys.readouterr().out
    assert out.index("LOSS:") < out.index("DRIFT:")
    # 3. drift alone
    (rules / "broken.yaml").unlink()
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 1


@pytest.mark.skipif(
    not Path("/opt/fabrik").is_dir()
    or not (ROOT / ".pre-commit-config.yaml").is_file()
    or "assemble_commands.py --check" not in (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"),
    reason="the hub's corpus-check hook runs only in /opt/fabrik",
)
def test_the_corpus_check_hook_passes_a_loss_exit_through(tmp_path: Path) -> None:
    entry = next(
        h["entry"]
        for repo in yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())["repos"]
        for h in repo.get("hooks", [])
        if "assemble_commands.py --check" in str(h.get("entry", ""))
    )
    stub = tmp_path / "stub.py"
    stub.write_text("import sys\nsys.exit(4)\n")
    shell = entry.removeprefix("bash -c ").strip("'").replace(
        "/opt/fabrik/commands/assemble_commands.py --check", str(stub)
    )
    assert str(stub) in shell, entry
    r = subprocess.run(["bash", "-c", shell], cwd="/opt/fabrik", capture_output=True, text=True)
    assert r.returncode == 4, (r.returncode, r.stderr)


def test_baseline_file_is_hashed_as_written(tmp_path: Path) -> None:
    out = tmp_path / "b.txt"
    sha = cr.write_baseline("## S\n\nOne. Two.\n\n```\na\nb\n```\n", out)
    assert sha == hashlib.sha256(out.read_bytes()).hexdigest()
    assert cr._read_baseline(out.read_bytes()) == ["## S ¦ ## S", "## S ¦ One", "## S ¦ Two", "## S ¦ a ⏎ b"]


# ── review pass 2: own-fix regressions and the reasons no test triggered ──────────────────────
def test_ordered_compares_whole_file_positions(tmp_path: Path) -> None:
    nested = "## X\n\n### Sub\n\nBeta rule two.\n\nAlpha rule one.\n"
    t = _tree(tmp_path, source=nested, render=nested)
    a = {"id": "A", "section": "## X", "current": "Alpha rule one.", "text": ["Alpha"]}
    b = {"id": "B", "section": "### Sub", "current": "Beta rule two.", "text": ["Beta"]}
    _ledger(t, [{**a, "ordered": ["A", "B"]}, b], baseline_from=nested)
    _one(_losses(t), "out of order")  # B precedes A in the file, parent and child sections alike
    _ledger(t, [{**a, "ordered": ["B", "A"]}, b], baseline_from=nested)
    assert _losses(t) == []
    flat = "## A\n\nX rule.\n\n## B\n\nY rule.\n\nZ rule.\n"
    t = _tree(tmp_path / "mixed", source=flat, render=flat)
    w = {"id": "W", "current": "Z rule.", "text": ["Z"]}  # no section: the whole file
    sec = {"id": "S", "section": "## B", "current": "Y rule.", "text": ["Y"]}
    _ledger(t, [{**w, "ordered": ["W", "S"]}, sec], baseline_from=flat)
    _one(_losses(t), "out of order")
    _ledger(t, [{**w, "ordered": ["S", "W"]}, sec], baseline_from=flat)
    assert _losses(t) == []


def test_fenced_units_match_and_survive_whitespace(tmp_path: Path) -> None:
    src = "## A\n\n```\nrm -x a.\necho  hi\n```\n"
    t = _tree(tmp_path, source=src, render=src.replace("echo  hi", "echo hi"))
    fence = {"id": "F", "section": "## A", "current": "rm -x a. ⏎ echo hi", "text": ["rm -x"]}
    _ledger(t, [fence], baseline_from=src)
    assert _losses(t) == []  # a fence is a `current`; interior whitespace is no change
    assert cr.vanished(cr.keys(src), src.replace("echo  hi", "echo   hi")) == []


def test_an_empty_own_text_has_an_empty_baseline(tmp_path: Path) -> None:
    sha = cr.write_baseline("", tmp_path / "b.txt")
    assert (tmp_path / "b.txt").read_bytes() == b"" and cr._read_baseline(b"") == []
    assert sha == hashlib.sha256(b"").hexdigest()


def test_the_enforced_lint_reads_call_arguments_only(tmp_path: Path) -> None:
    base_src = SOURCE.replace("Stop at the pin.", "Run `gate.py` first.")
    t = _tree(tmp_path, source=base_src)
    (t["root"] / "tests").mkdir()
    (t["root"] / "tests" / "test_g.py").write_text(
        "import subprocess\n"
        "def test_doc():\n    '''see gate.py for the refusal'''\n    r = subprocess.run(['other.py'])\n"
        "    assert r.returncode == 2\n"
        "def test_http():\n    r = subprocess.run(['gate.py'])\n    assert r.code == 200\n"
        "def test_kw():\n    r = subprocess.run(args=['gate.py', '-x'])\n    assert r.returncode != 0\n"
        "def test_dup():\n    pass\n"
        "class K:\n    def test_dup(self):\n        pass\n"
    )
    (t["root"] / "tests" / "test_bad.py").write_text("def broken(:\n")
    enf = {"id": "R5", "section": "## Scope", "current": "Run `gate.py` first.", "text": ["`gate.py`"]}
    _ledger(t, [{**enf, "enforced": "tests/test_g.py::test_kw"}], baseline_from=base_src)
    assert _losses(t) == []  # a keyword argument is a call argument
    for node, why in (
        ("tests/test_g.py::test_doc", "never invokes the script"),  # a docstring is not a call
        ("tests/test_g.py::test_http", "asserts no refusal"),  # `code == 200` is not an exit code
        ("tests/test_g.py::test_dup", "2 functions"),
        ("tests/test_bad.py::broken", "does not parse"),
    ):
        _ledger(t, [{**enf, "enforced": node}], baseline_from=base_src)
        _one(_losses(t), why)


def test_more_malformed_shapes(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    assert "not a bare command name" in _refused(t, command="../demo")
    assert "not a file beside the ledger" in _refused(t, baseline_sentences="../demo.baseline.txt")
    assert "`retired` is not a list" in _refused(t, retired={"a": 1})
    assert "`vanished` is not a dict" in _refused(t, vanished=["L1"])
    assert "`current` is not a string" in _refused(t, entries=[{**ENTRY, "current": 5}])
    live = [{"decision": "D-0001", "entry": {"id": "R9", "text": ["x"]}}]
    assert "also a live entry" in _refused(t, entries=[ENTRY, {**ENTRY, "id": "R9"}], retired=live)
    p = t["rules"] / "demo.yaml"
    p.write_text("command: demo\ncommand: other\n")
    assert cr.summary(t["rules"]) == ["LEDGER demo.yaml: unreadable — LedgerError"]


def test_missing_files_and_whole_file_text(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    _ledger(t, [{"id": "A1", "file": "_agents/absent.md", "current": "x.", "text": ["x"]}])
    _one(_losses(t), "file absent.md missing")
    _ledger(t, [{"id": "W1", "text": ["no such words"]}])
    _one(_losses(t), "text phrase not in its file")
    frag = t["root"] / "commands" / "_fragments" / "gone.md"
    frag.parent.mkdir(parents=True)
    frag.write_text("## G\n\nKeep.\n")
    base = t["rules"] / "_shared" / "gone.baseline.txt"
    sha = cr.write_baseline(frag.read_text(), base)
    led = {"shared": "commands/_fragments/gone.md", "baseline_sentences": base.name, "baseline_sha256": sha,
           "entries": [{"id": "G1", "text": ["Keep"]}]}
    (t["rules"] / "_shared" / "gone.yaml").write_text(yaml.safe_dump(led))
    frag.unlink()
    assert any("its own text gone.md is missing" in x for x in _losses(t))


def test_scope_edges(tmp_path: Path) -> None:
    src = "## Scope\n\nA rule.\n<!-- Never push. -->\n\n## Close\n\nPush it.\n"
    t = _tree(tmp_path, source=src, render=src)
    _ledger(t, [{"id": "C", "section": "## Scope", "text": ["Never push"]}], baseline_from=src)
    _one(_losses(t), "text phrase not under its section")  # a comment never carries a text phrase
    _ledger(t, [{"id": "S", "section": "## Scope", "current": "Push it.", "text": ["Push"]}], baseline_from=src)
    _one(_losses(t), "`current` is not a unit under its section")  # a sibling section ends the scope
    _ledger(t, [{"id": "H", "section": "## **Scope**.", "current": "A rule.", "text": ["rule"]}], baseline_from=src)
    assert _losses(t) == []  # a `section` is matched after the same normalisation as units
    t = _tree(tmp_path / "xr", source=SOURCE)
    (t["root"] / "docs" / "DECISIONS.md").write_text("| D-0001 | 2026-10-25 | x | retires XR9 | y | z |\n")
    assert "no D-row" in _refused(t, retired=[{"decision": "D-0001", "entry": {"id": "R9", "text": ["x"]}}])


def test_the_enforced_lint_refusal_shapes(tmp_path: Path) -> None:
    base_src = SOURCE.replace("Stop at the pin.", "Run `gate.py` first.")
    t = _tree(tmp_path, source=base_src)
    (t["root"] / "tests").mkdir()
    (t["root"] / "tests" / "test_s.py").write_text(
        "import subprocess, pytest\n"
        "def test_absent(tmp_path):\n    subprocess.run(['gate.py', '--bad'])\n    assert not (tmp_path / 'out').exists()\n"
        "def test_raises():\n    with pytest.raises(SystemExit):\n        subprocess.run(['gate.py'])\n"
        "@pytest.mark.parametrize('x', [1])\ndef test_param(x):\n    r = subprocess.run(['gate.py'])\n    assert r.returncode != 0\n"
        "class TestK:\n    def test_m(self):\n        r = subprocess.run(['gate.py'])\n        assert r.returncode == 3\n"
    )
    enf = {"id": "R5", "section": "## Scope", "current": "Run `gate.py` first.", "text": ["`gate.py`"]}
    for node in ("tests/test_s.py::test_absent", "tests/test_s.py::test_raises",
                 "tests/test_s.py::test_param[1]", "tests/test_s.py::TestK::test_m"):
        _ledger(t, [{**enf, "enforced": node}], baseline_from=base_src)
        assert _losses(t) == [], node


def test_review_pass_3_fixes(tmp_path: Path) -> None:
    base_src = SOURCE.replace("Stop at the pin.", "Run `gate.py` first.")
    t = _tree(tmp_path, source=base_src)
    (t["root"] / "tests").mkdir()
    (t["root"] / "tests" / "test_p.py").write_text(
        "import subprocess\n"
        "def test_print():\n    print('gate.py')\n    r = subprocess.run(['other.py'])\n    assert r.returncode == 2\n"
    )
    enf = {"id": "R5", "section": "## Scope", "current": "Run `gate.py` first.", "text": ["`gate.py`"],
           "enforced": "tests/test_p.py::test_print"}
    _ledger(t, [enf], baseline_from=base_src)
    _one(_losses(t), "never invokes the script")  # a print() names the script; it runs nothing
    t = _tree(tmp_path / "fields")
    for field in ("file", "section", "baseline", "enforced"):
        assert f"`{field}` is not a string" in _refused(t, entries=[{**ENTRY, field: 5}])


def test_review_pass_3_survivors(tmp_path: Path) -> None:
    sib = "## B\n\nX rule.\n\n## A\n\nY rule.\n"
    t = _tree(tmp_path, source=sib, render=sib)
    y = {"id": "Y", "section": "## A", "current": "Y rule.", "text": ["Y"], "ordered": ["Y", "X"]}
    x = {"id": "X", "section": "## B", "current": "X rule.", "text": ["X"]}
    _ledger(t, [y, x], baseline_from=sib)
    _one(_losses(t), "out of order")  # sibling sections in reverse: X's section comes first
    flat = "## A\n\nX rule.\n\n## B\n\nY rule.\n"
    t = _tree(tmp_path / "heading", source=flat, render=flat)
    w = {"id": "W", "current": "## B", "text": ["B"]}  # the heading unit itself, no section
    s = {"id": "S", "section": "## B", "current": "Y rule.", "text": ["Y"], "ordered": ["S", "W"]}
    _ledger(t, [w, s], baseline_from=flat)
    _one(_losses(t), "out of order")  # a section's first unit sits after its own heading
    fence = "## A\n\n```\nrm a.\n```\n"
    t = _tree(tmp_path / "fence", source=fence, render=fence)
    _ledger(t, [{"id": "F", "section": "## A", "current": "rm a.", "text": ["rm"]}], baseline_from=fence)
    assert _losses(t) == []  # a fence keeps its trailing period, so `current` is matched as written
    t = _tree(tmp_path / "names")
    for bad in ("a/b", "a\\b", ".hid"):
        assert "not a bare command name" in _refused(t, command=bad)
        assert "not a file beside the ledger" in _refused(t, baseline_sentences=bad)


def test_an_unreadable_shared_dir_is_a_loss(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    (t["rules"] / "_shared" / "s.yaml").write_text("- not a mapping\n")
    (t["rules"] / "_shared").chmod(0)
    try:
        if os.access(t["rules"] / "_shared", os.R_OK):
            pytest.skip("running as a user who reads a mode-0 directory")
        _one(_losses(t), "LOSS rules: unreadable — PermissionError")
    finally:
        (t["rules"] / "_shared").chmod(0o755)


def test_losses_survives_an_unreadable_rules_dir(tmp_path: Path, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise PermissionError("denied")

    monkeypatch.setattr(cr, "ledgers", boom)
    assert cr.losses(tmp_path, tmp_path, tmp_path) == ["LOSS rules: unreadable — PermissionError: denied"]


# ── W-a9b5e763 slice C: the light form's generator and two slice-A residuals ─────────────────
def test_generate_unchanged_ledgers_pass_on_the_live_corpus(tmp_path: Path) -> None:
    out = tmp_path / "render"
    ac.render(out, None, agents_dest=out / "_agents")
    rules = tmp_path / "rules"
    rules.mkdir()
    total = 0
    for src in sorted(ac.SRC.glob("*.md")):
        own = cr.own_text(src.read_text(encoding="utf-8"))
        base = rules / f"{src.stem}.baseline.txt"
        sha = cr.write_baseline(own, base)
        entries = cr.generate_unchanged(base, own)
        assert entries, f"{src.stem}: no entry generated"
        total += len(entries)
        led = {"command": src.stem, "baseline_sentences": base.name, "baseline_sha256": sha, "entries": entries}
        (rules / f"{src.stem}.yaml").write_text(yaml.safe_dump(led, allow_unicode=True), encoding="utf-8")
    assert cr.losses(out, ROOT, ac.SRC, rules=rules) == []
    print(f"generated {total} entries over {len(list(ac.SRC.glob('*.md')))} commands")


def test_changed_by_lists_existing_decision_rows(tmp_path: Path) -> None:
    # § The rule test step 8: a rule changed on purpose appends its D-row to `changed-by:` — distinct
    # rows that exist AND name the entry, as a `retired` row's decision must
    t = _tree(tmp_path)
    with (t["root"] / "docs" / "DECISIONS.md").open("a") as fh:
        fh.write("| D-0002 | 2026-10-25 | x | changes R1 | y | z |\n| D-0003 | 2026-10-25 | x | changes R1 again | y | z |\n")
    _ledger(t, [{**ENTRY, "changed-by": ["D-0002", "D-0003"]}])
    assert _losses(t) == []
    for bad in (["D-0404"], "D-0002", [], ["D-0002", 7], ["D-0001"], ["D-0002", "D-0002"]):
        _ledger(t, [{**ENTRY, "changed-by": bad}])
        _one(_losses(t), "changed-by")
    retired = [{"decision": "D-0001", "entry": {"id": "R9", "text": ["x"], "changed-by": ["D-0002"]}}]
    _ledger(t, [ENTRY], retired=retired)
    _one(_losses(t), "changed-by")


def test_a_phrase_that_normalises_to_nothing_is_refused(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    for ph in ("...", "**", ". ."):
        _ledger(t, [{**ENTRY, "text": [ph]}])
        _one(_losses(t), "normalises to nothing")
    # `forbidden` is matched raw: "**" is a real absence pin, absent from SOURCE, so no LOSS
    _ledger(t, [{**ENTRY, "forbidden": ["**"]}])
    assert _losses(t) == []


def test_a_raw_forbidden_phrase_present_in_the_render_is_a_loss(tmp_path: Path) -> None:
    t = _tree(tmp_path, render=SOURCE + "\n**bold**\n")
    _ledger(t, [{**ENTRY, "forbidden": ["**"]}])
    _one(_losses(t), "forbidden phrase present")


def test_normalise_is_idempotent_on_every_live_unit() -> None:
    # `_check` re-normalises a stored `current`; a unit that changes on a second pass can never match
    # (a unit ending in " ." kept its space: "HTTP 404 ." -> "HTTP 404 " -> "HTTP 404"; emphasis
    # re-formed by one strip: "_**_" -> "__" -> "")
    for raw in ("HTTP 404 .", "ends with dots ..", "_**_", "a *_*_* b", "x __**__ y."):
        once = cr.normalise(raw)
        assert cr.normalise(once) == once, (raw, once)
    assert cr.normalise("ends with dots ..") == "ends with dots"
    bad = [
        (src.stem, u)
        for src in sorted(ac.SRC.glob("*.md"))
        for _h, k, u in cr.units(cr.own_text(src.read_text(encoding="utf-8")))
        if k != "fence" and cr.normalise(u) != u
    ]
    assert bad == [], bad[:3]


def test_generate_unchanged_keeps_only_surviving_units(tmp_path: Path) -> None:
    base = tmp_path / "b.txt"
    cr.write_baseline(cr.own_text(SOURCE), base)
    rewrite = SOURCE.replace("Never stage a sibling's file.", "Never stage another session's file.")
    entries = cr.generate_unchanged(base, cr.own_text(rewrite))
    currents = [e["current"] for e in entries]
    assert "Run the probe on a copy" in currents and "Stop at the pin" in currents
    assert not any("sibling" in c for c in currents)
    assert not any(c.startswith("#") for c in currents), "a heading unit is never an entry"
    e = next(e for e in entries if e["current"] == "Push it")
    assert e["section"] == "## Close" and e["file"] == "render" and e["text"] == ["Push it"]
    assert e["baseline"] == e["current"] and e["id"].startswith("u-L")
    assert len({x["id"] for x in entries}) == len(entries)
    # multiplicity: a unit the baseline holds twice and the rewrite once yields one entry
    twice = SOURCE + "\n## Again\n\nStop at the pin.\n"
    cr.write_baseline(cr.own_text(twice), base)
    once = [e for e in cr.generate_unchanged(base, cr.own_text(SOURCE)) if e["current"] == "Stop at the pin"]
    assert len(once) == 1


def test_generate_unchanged_section_pins_resolve_to_their_own_unit(tmp_path: Path) -> None:
    # a repeated heading, a spliced include, a literal marker-like line, an indented (unspliced)
    # include, and an include inside a comment: every generated entry must pass its own gate
    src = (
        "# /demo\n\n## Notes\n\nAlpha rule.\n\n## Other\n\nOther rule.\n\n## Notes\n\nBeta rule.\n\n"
        "## Spliced\n\nBefore it.\n\n{{include:orient}}\n\nAfter it.\n\n"
        "## Literal\n\n⟪include⟫\n\nAfter a literal.\n\n  {{include:orient}}\n\nAfter an indent.\n\n"
        "<!--\n{{include:orient}}\n-->\n\nAfter a comment.\n"
    )
    t = _tree(tmp_path, source=src, render=src.replace("{{include:orient}}\n\nAfter it.", "## Orient\n\nAfter it."))
    base = t["rules"] / "demo.baseline.txt"
    sha = cr.write_baseline(cr.own_text(src), base)
    entries = cr.generate_unchanged(base, cr.own_text(src))
    by = {e["current"]: e for e in entries}
    assert "section" not in by["Alpha rule"] and "section" not in by["Beta rule"]  # repeated heading
    assert by["Other rule"]["section"] == "## Other" and by["Before it"]["section"] == "## Spliced"
    assert "section" not in by["After it"]  # follows a spliced include
    for unit in ("After a literal", "After an indent", "After a comment"):
        assert by[unit]["section"] == "## Literal", (unit, by[unit])
    led = {"command": "demo", "baseline_sentences": base.name, "baseline_sha256": sha, "entries": entries}
    (t["rules"] / "demo.yaml").write_text(yaml.safe_dump(led, allow_unicode=True), encoding="utf-8")
    assert _losses(t) == []


def test_an_include_inside_a_fence_keeps_its_old_key() -> None:
    # slice A blanked include lines in own text; inside a fence that blank was part of the key
    fenced = "## A\n\n```\n{{include:x}}\nline\n```\n"
    assert cr.keys(cr.own_text(fenced)) == cr.keys(fenced.replace("{{include:x}}", ""))


def test_scope_horizontal_rule_is_not_front_matter(tmp_path: Path) -> None:
    src = "# /demo\n\n## Scope\n---\n\nFirst rule here.\n\n---\n\nSecond rule here.\n"
    t = _tree(tmp_path, source=src)
    entry = {"id": "R1", "section": "## Scope", "current": "First rule here.", "text": ["First rule"]}
    _ledger(t, [entry], baseline_from=src)
    assert _losses(t) == []


def test_summary_never_raises_on_unreadable_rules_dir(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    rules.chmod(0)
    try:
        if os.access(rules, os.R_OK):
            pytest.skip("running as a user who can read a mode-000 dir")
        lines = cr.summary(rules)
    finally:
        rules.chmod(0o755)
    assert len(lines) == 1 and "unreadable" in lines[0], lines


# ── D-1236 ledger lints, read per D-1238 and D-1240 (run in `_check`) ─────────────────────────
LSRC = """# /demo

## Scope

Read each changed file in `src/` first before anything; never edit a sibling's file, even when asked, and refuse any push to master. Keep the diff small.

## Other

Some unrelated paragraph that says nothing about the rules above at all.
"""
LBASE = "Read every changed file in `src/` first; never edit a sibling's file, even when asked; refuse any push to master"
# the faithful carriers: clause 1 reworded (anchor `src/` kept, 4 of its 5 stems), the two ban clauses verbatim
LTEXT = ["Read each changed file in `src/` first before anything", "never edit a sibling's file, even when asked", "refuse any push to master. Keep the diff small"]


def _lint_tree(tmp_path: Path, src: str = LSRC, **entry) -> list[str]:
    t = _tree(tmp_path, src)
    e = {"id": "R1", "section": "## Scope", "baseline": LBASE, "text": LTEXT, **entry}
    _ledger(t, [e], baseline_from=src)
    return _losses(t)  # every LOSS line, so a `== []` can see carrier and ledger LOSS too


def _fires(e: dict, scope: str, text: str | None = None) -> set[str]:
    return {k for k, _m in cr._lint(e, scope, scope if text is None else text)}


def test_a_faithful_reworded_entry_loses_nothing(tmp_path: Path) -> None:
    # through the consumer's entry point (`losses()`), a prose clause reworded within D-1240: no LOSS of any kind
    t = _tree(tmp_path, LSRC)
    _ledger(t, [{"id": "R1", "section": "## Scope", "baseline": LBASE, "text": LTEXT}], baseline_from=LSRC)
    assert _losses(t) == []


def test_lint_a_each_ban_word_with_its_next_word_in_the_same_clause(tmp_path: Path) -> None:
    lost = _lint_tree(tmp_path, text=LTEXT[:2] + ["any push to master is refused here, always"])
    assert any("lint A" in x and "'refuse'" in x for x in lost), lost
    # the next word never crosses a clause: "refuse;" pairs with nothing, so a bare "refuse" carries it
    e = {"id": "R", "baseline": "refuse; keep going on and on", "text": ["we refuse to do it here", "keep going on and on"]}
    assert "A" not in _fires(e, "we refuse to do it here. keep going on and on")
    # the carrier holds the SAME ban word, not any ban word (D-1238 point 2)
    m = {"id": "R", "baseline": "never push to master", "text": ["you must push to master only by review"]}
    assert "A" in _fires(m, "you must push to master only by review")


def test_ban_words_are_never_must_only_refuse_in_any_case() -> None:
    for ban in ("NEVER push", "Never push", "you must read", "MUST read", "only on master", "refuse it", "it refuses", "refused", "a refusal"):
        assert cr.entry_class({"baseline": ban}) == "ban", ban
    for not_ban in ("do not push", "it stays put", "tie a knot", "refusing it", "nevertheless", "mustard", "set `never-route` here", "pass `--only x`"):
        assert cr.entry_class({"baseline": not_ban}) == "prose", not_ban
    assert cr.entry_class({"baseline": "Do _NEVER_ push"}) == "ban"  # single-underscore emphasis dropped


def test_a_class_never_switches_off_a_ban_clause(tmp_path: Path) -> None:
    reworded = LSRC.replace("never edit a sibling's file", "avoid editing a sibling's file")
    for cls in ("prose", "grammar", "behavioural", "ban"):
        lost = _lint_tree(tmp_path / cls, src=reworded, **{"class": cls})
        assert any("lint D" in x and "clause 2" in x for x in lost), (cls, lost)


def test_lint_b_coverage_is_anchors_plus_seventy_percent_of_eight_stems() -> None:
    clause = "alpha bravo charlie delta echoes foxtrot golfs hotel india juliet"  # 10 stems, the first 8 count
    e = {"id": "R", "class": "prose", "baseline": clause}
    six = "alpha bravo charlie delta echoes foxtrot"  # 6 of the first 8 = 75%
    five = "alpha bravo charlie delta echoes plus"  # 5 of 8 = 62.5%
    assert "B" not in _fires({**e, "text": [six]}, six)
    assert "B" in _fires({**e, "text": [five]}, five)
    late = "india juliet alpha bravo charlie delta echoes"  # stems past the first 8 earn nothing
    assert "B" in _fires({**e, "text": [late]}, late)
    # per phrase, never pooled: two phrases of four stems each cover nothing
    assert "B" in _fires({**e, "text": ["alpha bravo charlie delta now", "echoes foxtrot golfs hotel now"]}, "x")
    # an anchor dropped fails however many stems survive
    a = {"id": "R", "class": "prose", "baseline": "run `make gate` on 2 machines before tagging"}
    assert "B" in _fires({**a, "text": ["run the gate on 2 machines before tagging"]}, "x")
    assert "B" in _fires({**a, "text": ["run `make gate` on two machines before tagging"]}, "x")
    assert "B" not in _fires({**a, "text": ["run `make gate` on 2 machines prior to tagging"]}, "x")
    assert cr.STEM_RECALL == 0.7 and cr.STEM_CAP == 8  # D-1240's starting value, changed only by a D-row
    # an anchor is held where it stands whatever its edges: a path of numbers, a code span, a parenthetical
    path = "every ledger lives under commands/_rules/ beside its baseline file"  # de-emphasis would eat the `_`
    assert "B" not in _fires({"id": "R", "class": "prose", "baseline": path, "text": [path]}, path)
    two = "bare rows inside a ```text fence grade on nothing; `a.py`'s `_X_ROW` passes when the row is bare"
    assert "B" not in _fires({"id": "R", "class": "prose", "baseline": two, "text": [two]}, two)  # a ``` run flips parity
    for clause in ("three runs found 0/5/0 across the same surface", "run `make`s twice and check them all before merging", "pass `--json` to every gate run you make", "this rule holds (see D-9) for every seat"):
        assert "B" not in _fires({"id": "R", "class": "prose", "baseline": clause, "text": [clause]}, clause), clause
    assert cr._anchors("found 0/5/0 here") == {"0/5/0"}
    # `_whole` demands a word boundary only at an edge that is a word character, on either side
    assert re.search(cr._whole("`x`"), "a`x`b") and re.search(cr._whole("(see D-9)"), "rule(see D-9)s")
    assert not re.search(cr._whole("run it"), "rerun it") and not re.search(cr._whole("run it"), "run its")


def test_lint_b_a_narrative_label_releases_a_clause(tmp_path: Path) -> None:
    lost = _lint_tree(tmp_path, text=LTEXT[1:])
    assert any("lint B" in x and "clause 1" in x for x in lost), lost
    assert _lint_tree(tmp_path / "n", text=LTEXT[1:], clauses={1: "narrative"}) == []


def test_lint_d_binds_a_ban_clause_from_its_ban_word_to_its_end() -> None:
    base = "Agents never edit a sibling's file, even when asked (D-9 says so). Then rest"
    e = {"id": "R", "baseline": base, "text": ["never edit a sibling's file, even when asked (D-9 says so)"]}
    ok = "Builders never edit a sibling's file, even when asked (D-9 says so). Then rest"
    assert "D" not in _fires(e, ok)  # the words before the ban word may change
    assert "D" in _fires(e, ok.replace(", even when asked", ""))  # a comma does not end the span
    assert "D" in _fires(e, ok.replace(" (D-9 says so)", ""))  # nor does a parenthetical
    assert "D" not in _fires(e, ok.replace("Then rest", "Then the rest"))  # the sentence end does
    # D-1238 point 1: the ban entry's other clauses are under coverage, not verbatim
    two = {"id": "R", "baseline": "Read every changed file before you start; never push to master", "text": ["Read each changed file before you start", "never push to master"]}
    assert "D" not in _fires(two, "Read each changed file before you start; never push to master")


def test_lint_d_grammar_and_behavioural_bind_every_clause_prose_may_reword() -> None:
    e = {"id": "R", "baseline": "Write each heading in sentence case with no trailing period", "text": ["Write every heading in sentence case with no trailing period"]}
    live = "Write every heading in sentence case with no trailing period"
    for cls in ("grammar", "behavioural"):
        assert "D" in _fires({**e, "class": cls}, live), cls
        assert "D" not in _fires({**e, "class": cls}, e["baseline"]), cls
    assert "D" not in _fires({**e, "class": "prose"}, live)


def test_lint_c_six_whitespace_words_unique_in_the_file() -> None:
    e = {"id": "R", "class": "prose", "baseline": "w0 w1 w2 w3 w4 w5"}
    assert "C" in _fires({**e, "text": ["w0 w1 w2 w3 w4"]}, "w0 w1 w2 w3 w4 w5")
    assert "C" not in _fires({**e, "text": ["w0 w1 w2 w3 w4 w5"]}, "w0 w1 w2 w3 w4 w5")
    assert "C" in _fires({**e, "text": ["`a/b/c/d/e/f`"]}, "`a/b/c/d/e/f`")  # one token is one word
    once = "run the tests before you push"
    p = {"id": "R", "class": "prose", "baseline": once + " now", "text": [once]}
    assert "C" not in _fires(p, once + " now", "## A\n\n" + once + " now\n\n## B\n\nrerun the tests before you push")
    assert "C" in _fires(p, once + " now", "## A\n\n" + once + " now\n\n## B\n\n" + once)  # unique in its FILE
    assert "C" in _fires(p, "nothing here", "nothing here")  # 0x
    # C binds prose carriers only: a grammar pin (a front-matter line, a script path) is short by nature
    for cls in ("grammar", "behavioural", "ban"):
        assert "C" not in _fires({"id": "R", "class": cls, "baseline": "model: inherit", "text": ["model: inherit"]}, "model: inherit"), cls
    # a phrase equal to the whole `current` unit is exempt: `_check` proves that unit is live
    assert "C" not in _fires({**p, "baseline": "Push it", "current": "Push it.", "text": ["Push it"]}, "Push it.")


def test_clauses_labels_are_validated(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    plain = {**ENTRY, "baseline": "Run the probe on a copy; stop at the pin", "current": "Run the probe on a copy.", "text": ["Run the probe on a copy"]}
    _ledger(t, [{**plain, "clauses": {1: {"duplicate-of": "NOPE"}}}])
    _one(_losses(t), "duplicate-of unknown id")
    _ledger(t, [{**plain, "clauses": {1: {"duplicate-of": "R1"}}}])
    _one(_losses(t), "duplicate-of unknown id")  # itself
    _ledger(t, [{**plain, "clauses": {99: "narrative"}}])
    _one(_losses(t), "past the baseline")
    _ledger(t, [{**ENTRY, "clauses": {1: "narrative"}}])
    _one(_losses(t), "holds a ban word")
    other = {"id": "R2", "section": "## Scope", "current": "Stop at the pin.", "text": ["Stop at the pin"]}
    _ledger(t, [{**ENTRY, "clauses": {1: {"duplicate-of": "R2"}}}, other])
    _one(_losses(t), "holds a ban word")  # a ban clause is no duplicate either (D-1238 point 1)
    _ledger(t, [{**plain, "clauses": {2: {"duplicate-of": "R2"}}}, other])
    assert [x for x in _losses(t) if "malformed" in x] == []  # R2 covers "stop at the pin"
    _ledger(t, [{**plain, "clauses": {1: {"duplicate-of": "R2"}}}, other])
    _one(_losses(t), "does not cover it")
    _ledger(t, [{**{k: v for k, v in plain.items() if k != "baseline"}, "clauses": {1: "narrative"}}])
    _one(_losses(t), "needs a `baseline`")


def test_a_provenance_clause_owes_its_id_parentheticals_nothing(tmp_path: Path) -> None:
    # D-1255: a parenthetical of ids alone leaves the clause's anchors; the rest of the clause is still measured
    base = "Keep the receipt beside the review file (D-1240, W-96f36043, 2026-10-26)"
    text = ["Keep the receipt beside the review file"]
    e = {"id": "R", "class": "prose", "baseline": base, "text": text}
    assert "B" in _fires(e, text[0])  # unlabelled: the ids are anchors no carrier holds
    assert "B" not in _fires({**e, "clauses": {1: "provenance"}}, text[0])
    assert "B" in _fires({**e, "clauses": {1: "provenance"}, "text": ["Keep the file"]}, "Keep the file")  # the words still owe
    # a clause that is nothing but such a parenthetical owes no carrier at all
    alone = {"id": "R", "class": "prose", "baseline": "Keep the receipt beside the review file; (D-1240 / 3607c5d23 · §4.2)", "text": text}
    assert "B" not in _fires({**alone, "clauses": {2: "provenance"}}, text[0])
    # the id tokens, one by one; a hex-letter word is no SHA and a § heading of two words is words
    for ids in ("D-1", "W-0c38115e", "2026-10-26", "0c70b53", "§ Behavior", "§2", "D-181/D-182", "D-9; D-10"):
        assert cr._strip_provenance(f"do it ({ids})") == "do it ", ids
    for words in ("D-181, mechanism revised", "operator, 2026-09-07", "defaced", "1234567", "D-٣", "§ Binding field block", "see D-9", "D-9 says so", "`D-9`"):
        assert cr._strip_provenance(f"do it ({words})") == f"do it ({words})", words
    assert cr._strip_provenance("run `x (D-1)` now") == "run `x (D-1)` now"  # inside a code span: code, never provenance
    assert cr._strip_provenance("set_version(2026-10-26)") == "set_version(2026-10-26)"  # a call's argument (a fenced line)
    assert cr._strip_provenance("ship it (D-1) (0c70b53)") == "ship it  "  # each aside stripped
    sha256 = "0c70b5366" + "a" * 55
    assert cr._strip_provenance(f"do it ({sha256})") == "do it " and cr._strip_provenance(f"do it ({sha256}b)") != "do it "
    # an operative number in an aside stays an anchor the carrier owes
    num = {"id": "R", "class": "prose", "baseline": "Cap the upload size (1048576)", "text": ["Cap the upload size"], "clauses": {1: "provenance"}}
    assert "B" in _fires(num, "Cap the upload size")
    # in classes grammar and behavioural lint D still reads the whole clause, its ids included (D-1256)
    g = {**e, "class": "grammar", "clauses": {1: "provenance"}}
    assert "B" not in _fires(g, base) and "D" in _fires(g, text[0]) and "D" not in _fires(g, base)


def test_provenance_labels_are_refused_on_a_ban_clause_or_a_clause_without_ids(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    plain = {**ENTRY, "baseline": "Run the probe on a copy; stop at the pin", "current": "Run the probe on a copy.", "text": ["Run the probe on a copy"]}
    _ledger(t, [{**plain, "clauses": {2: "provenance"}}])
    _one(_losses(t), "no parenthetical of ids alone")
    _ledger(t, [{**plain, "baseline": "Run the probe on a copy; stop at the pin (see D-9)", "clauses": {2: "provenance"}}])
    _one(_losses(t), "no parenthetical of ids alone")  # a word beside the id is no provenance
    _ledger(t, [{**ENTRY, "baseline": "Never stage a sibling's file (D-9)", "clauses": {1: "provenance"}}])
    _one(_losses(t), "holds a ban word")  # D-1238 point 1: a ban clause takes no label, provenance included
    _ledger(t, [{**plain, "baseline": "Run the probe on a copy; stop at the pin (D-9)", "clauses": {2: "provenance", "2": "narrative"}}])
    _one(_losses(t), "`clauses` is not")  # `2:` and `"2":` name one clause: never two labels for it
    _ledger(t, [{**plain, "baseline": "Run the probe on a copy; stop at the pin (D-9)", "clauses": {"2": "provenance", "1٠": "narrative"}}])
    _one(_losses(t), "`clauses` is not")  # a non-ASCII digit key is no clause number
    _ledger(t, [{**plain, "baseline": "Run the probe on a copy; stop at the pin (D-9)", "clauses": {2: "provenance"}}])
    assert [x for x in _losses(t) if "malformed" in x] == []
    assert cr.summary(t["rules"])[0].endswith("· provenance 1")


def test_clause_split() -> None:
    assert cr._clauses("Run it first -- then post") == ["Run it first", "then post"]
    assert cr._clauses("Run it first – then post") == ["Run it first", "then post"]
    assert cr._clauses("never push—or edit; keep small") == ["never push", "or edit", "keep small"]
    assert cr._clauses("see `a; b — c` now") == ["see `a; b — c` now"]
    assert cr._clauses("use ``a;b`` here; keep it short") == ["use ``a;b`` here", "keep it short"]
    assert cr._clauses("keep it (a; b) small; then go") == ["keep it (a; b) small", "then go"]
    assert cr._clauses("a stray ` tick; then go") == ["a stray ` tick", "then go"]
    assert cr._clauses("a;; b;") == ["a", "b"]
    assert cr._baseline_clauses("echo a; b ⏎ # c — d") == ["echo a; b", "# c — d"]


def test_legacy_entries_are_never_newly_linted() -> None:
    legacy = {"id": "R2", "baseline": "Stop at the pin.", "current": "Stop at the pin.", "text": ["Stop at"]}
    assert cr._lint(legacy, "Stop at the pin.", "Stop at the pin.") == []
    assert cr._lint({**legacy, "pins": ["tests/x.py::t"]}, "Stop at the pin.", "Stop at the pin.") == []  # pins predate D-1236
    assert cr._lint({"id": "R3", "text": ["Stop at the pin"]}, "Stop at the pin", "Stop at the pin") == []  # no baseline
    assert "C" in _fires({**legacy, "class": "prose"}, "Stop at the pin.")  # opted in by `class:`
    # "not" is no ban word, so a legacy "do not" entry stays unlinted (D-1238 point 2)
    assert cr._lint({**legacy, "baseline": "Do not stage it.", "current": "Do not stage it."}, "Do not stage it.", "x") == []


def test_class_validated_and_counted_in_the_summary(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    _ledger(t, [{**ENTRY, "class": "bogus"}])
    _one(_losses(t), "`class` is not one of")
    _ledger(t, [{**ENTRY, "pins": [3]}])
    _one(_losses(t), "`pins` is not")
    _ledger(t, [{**ENTRY, "clauses": {1: "maybe"}}])
    _one(_losses(t), "`clauses` is not")
    stop = {**ENTRY, "id": "R2", "baseline": "Stop at the pin", "current": "Stop at the pin", "text": ["Stop at the pin"]}
    _ledger(t, [{**ENTRY, "class": "grammar"}, stop])
    line = cr.summary(t["rules"])[0]
    assert line == "LEDGER demo.yaml: 2 entries · classes {'grammar': 1, 'prose': 1} · vanished {} · provenance 0", line


def test_summary_survives_malformed_entries(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "bad.yaml").write_text("entries: [{id: R1, baseline: 5, text: [x]}, {id: R2, class: [a], baseline: x}]\n", encoding="utf-8")
    (rules / "good.yaml").write_text("entries: [{id: R1, baseline: NEVER x, text: [x]}]\n", encoding="utf-8")
    lines = cr.summary(rules)
    assert lines == [
        "LEDGER bad.yaml: 2 entries · classes {'prose': 2} · vanished {} · provenance 0",
        "LEDGER good.yaml: 1 entries · classes {'ban': 1} · vanished {} · provenance 0",
    ], lines


def test_a_faithful_prose_entry_passes_c_through_losses(tmp_path: Path) -> None:
    src = "# /demo\n\n## Scope\n\nRead each changed file in `src/` first before anything at all.\n"
    t = _tree(tmp_path, src)
    e = {"id": "R1", "section": "## Scope", "class": "prose", "baseline": "Read every changed file in `src/` first",
         "text": ["Read each changed file in `src/` first before anything"]}
    _ledger(t, [e], baseline_from=src)
    assert _losses(t) == []
    _ledger(t, [{**e, "text": ["Read each changed file"]}], baseline_from=src)
    assert any("lint C" in x and "under 6 words" in x for x in _losses(t))


def test_pass2_matcher_shapes() -> None:
    # every ban word's span is checked, not only the first one's
    e = {"id": "R", "baseline": "Never edit a sibling's file. Refuse any push to master", "text": ["Never edit a sibling's file. Refuse any push to master"]}
    assert "D" in _fires(e, "Never edit a sibling's file. Refuse any push.")
    assert "D" not in _fires(e, "Never edit a sibling's file. Refuse any push to master.")
    # an abbreviation's period and a period inside a parenthetical end no span
    p = {"id": "R", "baseline": "never push (e.g. to master) or tags", "text": ["never push (e.g. to master) or tags"]}
    assert "D" in _fires(p, "never push (e.g. to main) or tags")
    assert "D" not in _fires(p, "never push (e.g. to master) or tags")
    # an abbreviation before a capital, or a sentence break inside a parenthetical, ends no span
    for base in ("never use tools, e.g. Grep and Glob, in a seat", "never push (see it. Then wait) or tags"):
        assert cr._ban_span(base, cr._ban_hits(base)[0]) == base, base
    # a sentence that opens with code still ends the span before it; a `.` inside code ends nothing
    c = {"id": "R", "baseline": "Never paste the grammar. `_x` strips it", "text": ["Never paste the grammar"]}
    assert cr._ban_span(c["baseline"], cr._ban_hits(c["baseline"])[0]) == "Never paste the grammar."
    assert "D" not in _fires(c, "Never paste the grammar. `_y` strips it")
    assert cr._ban_span("never run `a. B` twice", cr._ban_hits("never run `a. B` twice")[0]) == "never run `a. B` twice"
    # a clause with no stem and no anchor needs its own words, whole, in one phrase
    s = {"id": "R", "class": "prose", "baseline": "Do it now"}
    assert "B" in _fires({**s, "text": ["unrelated words about something else entirely"]}, "x")
    assert "B" not in _fires({**s, "text": ["then do it now, before the gate"]}, "x")
    # punctuation never pads C's minimum
    assert "C" in _fires({"id": "R", "class": "prose", "baseline": "Run gate", "text": ["Run gate - - - -"]}, "Run gate - - - -")
    # an inline ```code``` line is prose, never a fence marker
    assert "D" not in _fires({"id": "R", "baseline": "Never push it", "text": ["Never push it"]}, "```code``` Never push it")
    # a lone backtick is literal; an unbalanced `(` holds nothing back
    assert cr._clauses("use ` here; keep ``b`` ok; stop") == ["use ` here", "keep ``b`` ok", "stop"]
    assert cr._clauses("See (draft; NEVER push to master; stop") == ["See (draft", "NEVER push to master", "stop"]
    # stems are letters-only whole words, any script
    assert cr._stems("v2beta résumé reviews") == ["résum", "revie"]
    # a phrase equal to `current` keeps the uniqueness rule
    w = {"id": "R", "class": "prose", "baseline": "Push it", "current": "Push it.", "text": ["Push it"]}
    assert "C" in _fires(w, "Push it.", "## A\n\nPush it.\n\n## B\n\nPush it.")


def test_pass3_shapes(tmp_path: Path) -> None:
    span = lambda s: cr._ban_span(s, cr._ban_hits(s)[0])  # noqa: E731
    # the span is the sentence units() cuts: never after a bare number, never inside code a lone backtick opens
    assert span("Never push at step 3. Then wait") == "Never push at step 3. Then wait"
    assert span("Never push ` here. Then wait") == "Never push ` here. Then wait"
    d = {"id": "R", "baseline": "Never push at step 3. Then wait", "text": ["Never push at step 3. Then wait"]}
    assert "D" in _fires(d, "Never push at step 3. Then go")
    # a trailing ! or ? is punctuation the span keeps
    bang = {"id": "R", "baseline": "Never push to master!", "text": ["Never push to master!"]}
    assert "D" in _fires(bang, "Never push to master?") and "D" not in _fires(bang, "Never push to master!")
    # an underscore is no word for C's minimum
    assert "C" in _fires({"id": "R", "class": "prose", "baseline": "Run gate", "text": ["Run gate _ _ _ _"]}, "Run gate _ _ _ _")
    # a fence unit equal to `current` is counted as the live lines it joins
    f = {"id": "R", "class": "prose", "baseline": "x1 y ⏎ x2 z", "current": "x1 y ⏎ x2 z", "text": ["x1 y ⏎ x2 z"]}
    assert "C" not in _fires(f, "```\nx1 y\nx2 z\n```", "```\nx1 y\nx2 z\n```")
    # only matched parentheses protect: a stray ) or ( holds nothing back and unprotects nothing
    assert cr._clauses("Step 1) never push; (see D-9; also stop") == ["Step 1) never push", "(see D-9", "also stop"]
    assert cr._clauses("Never edit (a file; even when asked) ok; stop)") == ["Never edit (a file; even when asked) ok", "stop)"]
    # a lone backtick never hides an emphasised ban word
    assert cr.entry_class({"baseline": "a ` tick; _never_ push to master"}) == "ban"
    # a wordless clause is covered by nothing and needs nothing; NFD text yields the same stems as NFC
    assert cr._covered("...", []) and cr._stems("résumé reviews") == ["résum", "revie"]
    # `_lint_tree` returns carrier LOSS too
    assert any("text phrase not under its section" in x for x in _lint_tree(tmp_path, text=LTEXT + ["a phrase no command says"]))


def test_a_heading_word_never_makes_its_unit_a_ban_line(tmp_path: Path) -> None:
    src = SOURCE.replace("## Close", "## Only for builders")
    t = _tree(tmp_path, source=src.replace("2. Push it.", ""))
    base = t["rules"] / "demo.baseline.txt"
    sha = cr.write_baseline(cr.own_text(src), base)
    lines = cr._read_baseline(base.read_bytes())
    n = next(i for i, ln in enumerate(lines, 1) if ln.endswith("Push it"))
    assert lines[n - 1] == "## Only for builders ¦ Push it"  # the positive control: the heading holds the ban word
    other = {"id": "R2", "section": "## Scope", "current": "Stop at the pin.", "text": ["Stop at the pin"]}
    data = {"command": "demo", "baseline_sentences": base.name, "baseline_sha256": sha, "entries": [other], "vanished": {f"L{n}": "narrative"}}
    (t["rules"] / "demo.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert not any("vanish" in x for x in _losses(t)), _losses(t)


def test_a_ban_line_never_vanishes_as_narrative(tmp_path: Path) -> None:
    t = _tree(tmp_path, source=SOURCE.replace("Never stage a sibling's file.", ""))
    base = t["rules"] / "demo.baseline.txt"
    sha = cr.write_baseline(cr.own_text(SOURCE), base)
    n = next(i for i, ln in enumerate(cr._read_baseline(base.read_bytes()), 1) if "Never stage" in ln)
    other = {"id": "R2", "section": "## Scope", "current": "Stop at the pin.", "text": ["Stop at the pin"]}
    data = {"command": "demo", "baseline_sentences": base.name, "baseline_sha256": sha, "entries": [other], "vanished": {f"L{n}": "narrative"}}
    (t["rules"] / "demo.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    _one(_losses(t), "holds a ban word and cannot vanish as narrative")
    data["vanished"] = {f"L{n}": {"rule": ["R2"]}}  # classified to a rule instead: R2 must carry it (W-34d76a7a)
    (t["rules"] / "demo.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    lost = _losses(t)
    assert not any("cannot vanish as narrative" in x for x in lost) and any("vanished as rule" in x for x in lost), lost


def test_a_fence_marker_does_not_flip_code_parity_for_the_prose_beside_it() -> None:
    e = {"id": "R", "class": "prose", "baseline": "Run the full test suite now", "text": ["Run the full test suite now"]}
    assert "C" not in _fires(e, "```\nRun **the** full test suite now")


def test_a_lint_loss_exits_the_corpus_check_with_4(tmp_path: Path, monkeypatch, capsys) -> None:
    # through the consumer's entry point: a real command's ban unit carried by a stub fails `--check`
    own = cr.own_text((ac.SRC / "fabrik-task.md").read_text(encoding="utf-8"))
    heading, unit = next(
        (h, u) for h, k, u in cr.units(own) if k == "prose" and h.startswith("## ") and cr._ban_hits(u) and len(u.split()) > 8
    )
    rules = tmp_path / "rules"
    rules.mkdir()
    sha = cr.write_baseline(own, rules / "fabrik-task.baseline.txt")
    stub = " ".join(w for w in unit.split() if not cr._is_ban(w))
    entry = {"id": "T1", "section": heading, "baseline": unit, "current": unit, "text": [stub]}
    led = {"command": "fabrik-task", "baseline_sentences": "fabrik-task.baseline.txt", "baseline_sha256": sha, "entries": [entry]}
    (rules / "fabrik-task.yaml").write_text(yaml.safe_dump(led, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(cr, "RULES", rules)
    inst, skills, agents = tmp_path / "installed", tmp_path / "skills", tmp_path / "agents"
    ac.render(inst, skills, agents_dest=agents)
    monkeypatch.setattr(ac, "OUT", inst)
    monkeypatch.setattr(ac, "SKILLS", skills)
    monkeypatch.setattr(ac, "AGENTS", agents)
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc:
        ac.check()
    out = capsys.readouterr().out
    assert exc.value.code == 4 and "lint A" in out, out


# ── W-34d76a7a: a vanished `rule:`/`duplicate-of:` label is proven, never merely pointed ─────────
def _gone(old: str, new: str, entries: list[dict], key_part: str, label: object, tmp: Path) -> list[str]:
    """The LOSS lines when the ``old`` source's unit holding ``key_part`` vanished into ``new`` under ``label``."""
    t = _tree(tmp, source=new, render=new)
    n = next(i for i, k in enumerate(cr.keys(cr.own_text(old)), 1) if key_part in k)
    assert n in cr.vanished(cr.keys(cr.own_text(old)), cr.own_text(new)), "the fixture's line must vanish"
    _ledger(t, entries, baseline_from=old, vanished={f"L{n}": label})
    return _losses(t)


def _vanished_lines(lost: list[str]) -> list[str]:
    return [x for x in lost if "vanished as" in x]


def test_a_vanished_rule_label_must_be_covered(tmp_path: Path) -> None:
    old = SOURCE.replace("Run the probe on a copy.", "Run the probe on a copy; record the verdict.")
    new = SOURCE.replace("Run the probe on a copy. ", "").replace("Stop at the pin.", "Stop at the pin. Then run the probe on a copy.\n\nWe record the verdict here.")
    probe = {"id": "P", "section": "## Scope", "text": ["run the probe on a copy"]}
    verdict = {"id": "V", "section": "## Scope", "text": ["We record the verdict here"]}
    # the cheap path: a real id that carries another rule
    for label, says in (({"rule": ["R1"]}, "vanished as rule ['R1'] — lint B"), ({"duplicate-of": "R1"}, "vanished as duplicate-of R1 — lint B")):
        lost = _vanished_lines(_gone(old, new, [ENTRY], "Run the probe", label, tmp_path / f"r1-{len(str(label))}"))
        assert len(lost) == 2 and all(says in x for x in lost), lost  # both clauses of the line, each named by its label
    # covered clause by clause across two named entries: nothing
    assert _gone(old, new, [ENTRY, probe, verdict], "Run the probe", {"rule": ["P", "V"]}, tmp_path / "pv") == []
    # one entry carries only one clause: the other clause is the LOSS
    lost = _vanished_lines(_gone(old, new, [ENTRY, probe, verdict], "Run the probe", {"rule": ["P"]}, tmp_path / "p"))
    assert len(lost) == 1 and "record the verdict" in lost[0], lost
    # never one clause from two phrases: per phrase, as `_covered`
    halves = {"id": "H", "section": "## Scope", "text": ["run the probe", "on a copy", "We record the verdict here"]}
    lost = _vanished_lines(_gone(old, new, [ENTRY, halves], "Run the probe", {"rule": ["H"]}, tmp_path / "h"))
    assert len(lost) == 1 and "Run the probe on a copy" in lost[0], lost
    # a named entry whose section is missing: its own LOSS, never a second one for the line
    absent = {"id": "X", "section": "## Absent", "text": ["run the probe on a copy"]}
    lost = _gone(old, new, [ENTRY, absent, verdict], "Run the probe", {"rule": ["X", "V"]}, tmp_path / "x")
    assert len(lost) == 1 and "section '## Absent' missing" in lost[0], lost


def test_a_vanished_line_with_its_own_entry_is_linted_once(tmp_path: Path) -> None:
    new = SOURCE.replace("Run the probe on a copy. ", "Always probe the change on a copy before you trust it. ")
    own = {"id": "O", "section": "## Scope", "class": "prose", "baseline": "Run the probe on a copy",
           "text": ["probe the change on a copy before you trust it"]}
    assert _gone(SOURCE, new, [ENTRY, own], "Run the probe", {"rule": ["O"]}, tmp_path / "ok") == []
    # its own entry is the proof: an uncovered line prints once, from the entry's lint, never again for the label
    weak = {**own, "text": ["the change on a copy before you trust it"]}  # live, but holds no "probe"
    for spelling in ("Run the probe on a copy", "Run the _probe_ on a copy", "Run the **probe** on a copy"):
        lost = _gone(SOURCE, new, [ENTRY, {**weak, "baseline": spelling}], "Run the probe", {"rule": ["O"]}, tmp_path / f"w{len(spelling)}{spelling[8]}")
        assert len(lost) == 1 and "O: lint B" in lost[0] and not _vanished_lines(lost), (spelling, lost)
    # an equal-baseline entry the lints never read (no class, no clauses, no ban word) earns no pass
    legacy = {k: v for k, v in weak.items() if k != "class"}
    lost = _gone(SOURCE, new, [ENTRY, legacy], "Run the probe", {"rule": ["O"]}, tmp_path / "legacy")
    assert len(lost) == 1 and "vanished as rule ['O'] — lint B" in lost[0], lost


def test_a_vanished_ban_line_keeps_its_span_verbatim(tmp_path: Path) -> None:
    merged = SOURCE.replace("Never stage a sibling's file.", "Never stage a sibling's file or a stranger's.")
    carrier = {"id": "M", "section": "## Scope", "text": ["Never stage a sibling's file or a stranger's"]}
    assert _gone(SOURCE, merged, [carrier], "Never stage", {"rule": ["M"]}, tmp_path / "ok") == []
    reworded = SOURCE.replace("Never stage a sibling's file.", "Stage no sibling's file, never.")
    loose = {"id": "M", "section": "## Scope", "text": ["Stage no sibling's file, never"]}
    lost = _vanished_lines(_gone(SOURCE, reworded, [loose], "Never stage", {"rule": ["M"]}, tmp_path / "rw"))
    assert any("lint D" in x for x in lost) and any("lint A" in x for x in lost), lost
    # the span never reads across two named sections
    # every named section is read: the carrier may be the SECOND named entry, in another section
    across = SOURCE.replace(" Never stage a sibling's file.", "").replace("2. Push it.", "2. Push it. Never stage a sibling's file or a stranger's.")
    pin = {"id": "F", "section": "## Scope", "text": ["Stop at the pin"]}
    close = {"id": "C", "section": "## Close", "text": ["Never stage a sibling's file or a stranger's"]}
    for order in (["F", "C"], ["C", "F"]):  # the carrier last, then first: no named section is ever skipped
        assert _gone(SOURCE, across, [pin, close], "Never stage", {"rule": order}, tmp_path / f"across-{order[0]}") == []
    # the first section ENDS on "never" and the next STARTS on its object: each section stays its own paragraph
    # (every `_scope` body starts and ends with a newline, so the blank-line join is defensive, never the only guard)
    split = SOURCE.replace(" Never stage a sibling's file.", "").replace("Stop at the pin.", "Stop at the pin. Keep going and never")
    split = split.replace("## Close\n\n", "## Close\n\nstage a sibling's file today.\n\n")
    tail = {"id": "T", "section": "## Scope", "text": ["Keep going and never"]}
    head = {"id": "S", "section": "## Close", "text": ["stage a sibling's file today"]}
    lost = _vanished_lines(_gone(SOURCE, split, [tail, head], "Never stage", {"rule": ["T", "S"]}, tmp_path / "split"))
    assert any("lint D" in x for x in lost), lost


# ── W-5dc4163d: `superseded: D-n` — a line master rewrote after the lean baseline tag ─────────────────────────
MASTER_SRC = SOURCE.replace("Stop at the pin.", "Stop at the pinned base.")  # master's reviewed rewrite of one line
LEAN_SRC = MASTER_SRC.replace("Run the probe on a copy. ", "")  # the lean side cuts another line on its branch


_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_AUTHOR_DATE": "2026-10-27T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-27T00:00:00Z",  # same shas every run
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",  # no box signing, hooks or default-branch config
}  # fmt: skip


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env={**os.environ, **_GIT_ENV}).stdout.strip()


def _short(sha: str, n: int = 9) -> str:
    """The shortest prefix of ``sha`` from ``n`` chars that holds a letter AND a digit — the only shape a D-row's
    commit token takes (`command_rules._SHA`), so no fixture sha reads as a plain number."""
    return next(sha[:k] for k in range(n, len(sha) + 1) if re.search("[a-f]", sha[:k]) and re.search("[0-9]", sha[:k]))


def _commit(t: dict[str, Path], text: str, msg: str) -> str:
    (t["src"] / "demo.md").write_text(text, encoding="utf-8")
    _git(t["root"], "add", "src/demo.md")
    _git(t["root"], "commit", "-q", "-m", msg)
    return _git(t["root"], "rev-parse", "HEAD")


def _history(tmp: Path, own: str = LEAN_SRC) -> tuple[dict[str, Path], dict[str, str]]:
    """A repo at the fixture root. "Run the probe on a copy." is cut by: a commit BEFORE the tag (restored by the tagged
    commit), a side branch merged into master (so only the MERGE is named in a test), and a lean branch never merged.
    Master's one-parent commit after the tag rewrites "Stop at the pin.". The working tree (the ledger's own text) is
    ``own``; the baseline is the tagged SOURCE."""
    t = _tree(tmp, source=SOURCE, render=own)
    no_probe = SOURCE.replace("Run the probe on a copy. ", "")
    _git(t["root"], "init", "-q", "-b", "master")
    _commit(t, SOURCE, "first")
    shas = {"pre_tag": _commit(t, no_probe, "pre-tag cut")}
    shas["base"] = _commit(t, SOURCE, "restored")
    _git(t["root"], "tag", cr.LEAN_BASELINE_TAG)
    shas["master"] = _commit(t, MASTER_SRC, "master rewrite")
    _git(t["root"], "checkout", "-q", "-b", "side", shas["base"])
    shas["side"] = _commit(t, no_probe, "side cut")
    _git(t["root"], "checkout", "-q", "master")
    _git(t["root"], "merge", "-q", "--no-ff", "-m", "merge side", "side")
    shas["merge"] = _git(t["root"], "rev-parse", "HEAD")
    _git(t["root"], "checkout", "-q", "-b", "lean", shas["master"])
    shas["lean"] = _commit(t, LEAN_SRC, "lean cut")
    (t["src"] / "demo.md").write_text(own, encoding="utf-8")
    return t, shas


def _line(part: str) -> int:
    return next(i for i, k in enumerate(cr.keys(cr.own_text(SOURCE)), 1) if part in k)


def _superseded(t: dict[str, Path], rows: dict[str, str], vanished: dict[str, object]) -> list[str]:
    (t["root"] / "docs" / "DECISIONS.md").write_text(
        "".join(f"| {d} | 2026-10-27 | x | {what} | y | z |\n" for d, what in rows.items()), encoding="utf-8"
    )
    _ledger(t, [ENTRY], baseline_from=SOURCE, vanished=vanished)
    return _losses(t)


PIN, PROBE = _line("Stop at the pin"), _line("Run the probe")


def test_superseded_carried_by_the_master_commit_its_row_names(tmp_path: Path) -> None:
    t, s = _history(tmp_path)
    lost = _superseded(t, {"D-0002": f"master rewrote demo.md in {s['master']}", "D-0003": f"lean cut demo.md ({_short(s['lean'])})"},
                       {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert lost == [], lost
    # a short sha in the row is enough; tokens that do not qualify (a merge, a branch cut) are skipped, never fatal
    lost = _superseded(t, {"D-0002": f"demo.md · {_short(s['merge'])} {_short(s['lean'])} {_short(s['master'])}"},
                       {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert lost == [], lost
    assert any("'superseded': 1" in x for x in cr.summary(t["rules"])), cr.summary(t["rules"])


def test_superseded_ignores_an_inherited_git_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    t, s = _history(tmp_path / "repo")
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "master")  # a hook's GIT_DIR pointing elsewhere never answers for the root
    # a replace ref swapping master's blob for the OLD text would make master read as still holding the line
    old = tmp_path / "old.md"
    old.write_text(SOURCE, encoding="utf-8")
    blob = _git(t["root"], "hash-object", "-w", str(old))
    _git(t["root"], "replace", _git(t["root"], "rev-parse", "master:src/demo.md"), blob)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert lost == [], lost


def test_superseded_in_a_shared_ledger(tmp_path: Path) -> None:
    t, s = _history(tmp_path)
    pin = next(i for i, k in enumerate(cr.keys(SOURCE), 1) if "Stop at the pin" in k)  # a shared source is read raw
    probe = next(i for i, k in enumerate(cr.keys(SOURCE), 1) if "Run the probe" in k)
    (t["root"] / "docs" / "DECISIONS.md").write_text(f"| D-0002 | 2026-10-27 | x | demo.md {s['master']} | y | z |\n", encoding="utf-8")
    base = t["rules"] / "_shared" / "demo.baseline.txt"
    data = {"shared": "src/demo.md", "baseline_sentences": base.name, "baseline_sha256": cr.write_baseline(SOURCE, base),
            "entries": [{"id": "S1", "section": "## Scope", "text": ["Never stage a sibling's file"]}],
            "vanished": {f"L{pin}": {"superseded": "D-0002"}, f"L{probe}": "narrative"}}
    (t["rules"] / "_shared" / "demo.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    assert _losses(t) == [], _losses(t)


def test_superseded_refused_when_master_still_holds_the_line_or_lost_the_file(tmp_path: Path) -> None:
    t, s = _history(tmp_path)
    _git(t["root"], "checkout", "-q", "master")
    _commit(t, SOURCE.replace("Run the probe on a copy. ", ""), "master restores the pin line")  # master holds L{PIN} again
    _git(t["root"], "checkout", "-q", "lean")
    (t["src"] / "demo.md").write_text(LEAN_SRC, encoding="utf-8")
    lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert len(lost) == 1 and "still holds this line" in lost[0], lost
    t, s = _history(tmp_path / "renamed")
    _git(t["root"], "checkout", "-q", "master")
    _git(t["root"], "mv", "src/demo.md", "src/other.md")
    _git(t["root"], "commit", "-q", "-m", "master renames the source")
    _git(t["root"], "checkout", "-q", "lean")
    (t["src"] / "demo.md").write_text(LEAN_SRC, encoding="utf-8")
    lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert len(lost) == 1 and "master no longer holds src/demo.md" in lost[0], lost


def test_superseded_refused_for_a_commit_whose_parent_already_lacked_the_line(tmp_path: Path) -> None:
    t, s = _history(tmp_path)
    _git(t["root"], "checkout", "-q", "master")  # after the merge master already lacks "Run the probe on a copy."
    later = _commit(t, MASTER_SRC.replace("Run the probe on a copy. ", "").replace("2. Push it.", "2. Push it now."), "later")
    _git(t["root"], "checkout", "-q", "lean")
    (t["src"] / "demo.md").write_text(LEAN_SRC.replace("2. Push it.", "2. Push it now."), encoding="utf-8")
    lost = _superseded(t, {"D-0002": f"demo.md {later}"},
                       {f"L{PIN}": "narrative", f"L{PROBE}": {"superseded": "D-0002"}, f"L{_line('Push it')}": "narrative"})
    assert len(lost) == 1 and "no commit D-0002 names removed this line on master" in lost[0], lost


def test_superseded_refused_for_a_branch_cut_or_a_merge(tmp_path: Path) -> None:
    t, s = _history(tmp_path)
    for sha in (s["lean"], s["merge"]):  # a branch-only cut; a merge commit (its diff spans a whole branch)
        lost = _superseded(t, {"D-0002": f"demo.md {sha}"}, {f"L{PIN}": "narrative", f"L{PROBE}": {"superseded": "D-0002"}})
        assert len(lost) == 1 and f"L{PROBE}" in lost[0] and "no commit D-0002 names removed this line on master" in lost[0], lost


def test_superseded_refused_for_a_pre_tag_commit_or_one_not_removing_the_line(tmp_path: Path) -> None:
    t, s = _history(tmp_path)
    for sha in (s["pre_tag"], s["master"]):  # an ancestor of the tag that DID cut it; a master commit rewriting ANOTHER line
        lost = _superseded(t, {"D-0002": f"demo.md {sha}"}, {f"L{PIN}": "narrative", f"L{PROBE}": {"superseded": "D-0002"}})
        assert len(lost) == 1 and "no commit D-0002 names removed this line on master" in lost[0], lost
    # a W-item's hex is never read as a commit, even when it is one's prefix
    lost = _superseded(t, {"D-0002": f"demo.md W-{_short(s['master'], 8)}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert len(lost) == 1 and "no commit D-0002 names removed this line on master" in lost[0], lost


def test_superseded_refused_when_masters_replacement_is_not_carried(tmp_path: Path) -> None:
    t, s = _history(tmp_path, own=LEAN_SRC.replace("Stop at the pinned base.", "Stop."))
    lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert len(lost) == 1 and "master's replacement" in lost[0] and "Stop at the pinned base" in lost[0], lost
    # master later moves its replacement under another heading: it is still owed, wherever it now sits
    moved = MASTER_SRC.replace("Run the probe on a copy. ", "").replace("Stop at the pinned base.", "").replace("2. Push it.", "2. Push it.\n\nStop at the pinned base.")
    t, s = _history(tmp_path / "moved", own=LEAN_SRC.replace("Stop at the pinned base.", ""))
    _git(t["root"], "checkout", "-q", "master")
    _commit(t, moved, "master moves the rewrite under Close")
    _git(t["root"], "checkout", "-q", "lean")
    (t["src"] / "demo.md").write_text(LEAN_SRC.replace("Stop at the pinned base.", ""), encoding="utf-8")
    lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert len(lost) == 1 and "master's replacement" in lost[0] and "## Close" in lost[0], lost


def test_superseded_label_shape_row_and_mixing(tmp_path: Path) -> None:
    t, s = _history(tmp_path)
    for label in ({"superseded": "D-9999"}, {"superseded": "1251"}, {"superseded": ["D-0002"]}, {"superseded": "D-0002", "rule": ["R1"]}):
        lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": label, f"L{PROBE}": "narrative"})
        assert len(lost) == 1 and "malformed" in lost[0], (label, lost)
    for names in ("another.md", "ademo.md", "demo.md.bak"):  # the source by name, never a longer name holding it
        lost = _superseded(t, {"D-0002": f"{names} {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
        assert len(lost) == 1 and "malformed" in lost[0] and "demo.md" in lost[0], (names, lost)
    lost = _superseded(t, {"D-0002": f"master rewrote demo.md. See {s['master']}."}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert lost == [], lost  # a sentence ending on the name still names it
    # mixed with a failing `rule:` label: both LOSS lines print, neither hides the other
    lost = _superseded(t, {"D-0002": f"demo.md {s['lean']}"}, {f"L{PIN}": {"rule": ["R1"]}, f"L{PROBE}": {"superseded": "D-0002"}})
    assert any("vanished as rule ['R1']" in x for x in lost) and any("superseded by D-0002" in x for x in lost), lost


def test_superseded_fails_closed_without_git_history(tmp_path: Path) -> None:
    # an enclosing repo with a full history (the tag, master, the named commit) must never answer for the fixture root
    _outer, s = _history(tmp_path / "outer")
    t = _tree(tmp_path / "outer" / "inner", source=SOURCE, render=LEAN_SRC)
    (t["src"] / "demo.md").write_text(LEAN_SRC, encoding="utf-8")
    lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert len(lost) == 1 and "no git history readable" in lost[0], lost
    # a repo with no master ref, and one with no baseline tag: each a LOSS naming it
    t, s = _history(tmp_path / "trunk")
    _git(t["root"], "branch", "-m", "master", "trunk")
    lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert len(lost) == 1 and "no master ref" in lost[0], lost
    t, s = _history(tmp_path / "untagged")
    _git(t["root"], "tag", "-d", cr.LEAN_BASELINE_TAG)
    lost = _superseded(t, {"D-0002": f"demo.md {s['master']}"}, {f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    assert len(lost) == 1 and f"the tag {cr.LEAN_BASELINE_TAG} is not in the history" in lost[0], lost
    # a command source outside the repo root: no commit of the root can name it
    t, s = _history(tmp_path / "inside")
    outside = tmp_path / "outside-src"
    outside.mkdir()
    (outside / "demo.md").write_text(LEAN_SRC, encoding="utf-8")
    (t["root"] / "docs" / "DECISIONS.md").write_text(f"| D-0002 | 2026-10-27 | x | demo.md {s['master']} | y | z |\n", encoding="utf-8")
    _ledger(t, [ENTRY], baseline_from=SOURCE, vanished={f"L{PIN}": {"superseded": "D-0002"}, f"L{PROBE}": "narrative"})
    lost = cr.losses(t["out"], t["root"], outside, rules=t["rules"])
    assert len(lost) == 1 and "is outside the repo" in lost[0], lost


# ── W-f5a1eec9: losses() caches its pure text views; a cache never changes a LOSS line ───────────────────────
_CACHED = ("normalise", "_units", "_file_paras", "_live_paras")


@pytest.fixture(autouse=True)
def _cold_caches():
    """Every test starts on empty caches, so no test's result depends on which test warmed them."""
    for n in _CACHED:
        f = getattr(cr, n, None)
        if hasattr(f, "cache_clear"):
            f.cache_clear()


def _many(tmp_path: Path, n: int = 4) -> dict[str, Path]:
    """One file, ``n`` lintable entries under ONE section of it (a sectioned entry's scope is never the whole
    text, so only lint C reads the whole file's paragraphs), and a render that yields several LOSS lines."""
    src = SOURCE.replace("Stop at the pin.", f"Stop at the pin {tmp_path.name}.")
    t = _tree(tmp_path, source=src, render=src.replace("Never stage a sibling's file.", "Stage carefully."))
    entries = [{**ENTRY, "id": f"R{i}"} for i in range(1, n + 1)]
    entries.append({"id": "P1", "section": "## Scope", "class": "prose", "baseline": "Run the probe on a copy.",
                    "text": ["probe"]})
    _ledger(t, entries, baseline_from=src)
    return t


def test_lint_builds_each_texts_paragraph_views_once(tmp_path: Path, monkeypatch) -> None:
    t = _many(tmp_path)
    text = (t["out"] / "demo.md").read_text(encoding="utf-8")
    seen: list[str] = []
    real = cr._paras

    def spy(s: str) -> list[str]:
        seen.append(s)
        return real(s)

    monkeypatch.setattr(cr, "_paras", spy)
    assert _losses(t)
    # five lintable entries on one file: its whole-text paragraphs are split once, never once per entry
    assert seen.count(text) == 1, seen.count(text)


def test_losses_identical_cold_warm_and_uncached(tmp_path: Path, monkeypatch) -> None:
    t = _many(tmp_path)
    with monkeypatch.context() as m:  # the reference: the same functions with every cache bypassed
        for n in _CACHED:
            m.setattr(cr, n, getattr(cr, n).__wrapped__)
        want = _losses(t)
    assert len(want) >= 3 and len(set(want)) == len(want), want
    assert _losses(t) == want  # cold (the autouse fixture emptied the caches)
    assert _losses(t) == want  # warm


def test_units_returns_a_fresh_list() -> None:
    text = "## S\n\nKeep going. Stop here.\n"
    first = cr.units(text)
    want = list(first)
    first.append(("x", "prose", "y"))
    first[0] = ("z", "heading", "z")
    assert cr.units(text) == want


def test_lint_c_counts_a_phrase_per_paragraph_over_the_whole_file() -> None:
    once = "run the tests before you push"
    p = {"id": "R", "class": "prose", "baseline": once, "text": [once]}

    def c(text: str, e: dict = p) -> list[str]:
        return [m for k, m in cr._lint(e, text, text) if k == "C"]

    assert c("## A\n\nnothing here") == [f"text phrase appears 0x in its file, need exactly once — {once}"]
    assert c(f"## A\n\n{once}\n\n## B\n\n{once}") == [f"text phrase appears 2x in its file, need exactly once — {once}"]
    assert c(f"## A\n\n{once} and {once}, then {once}") == [f"text phrase appears 3x in its file, need exactly once — {once}"]
    assert c(f"## A\n\n{once}") == []
    assert c(f"## A\n\n{once}\n\n## B\n\n{once.capitalize()}") == []  # the count is case-sensitive
    split = "## A\n\nrun the tests before\n\nyou push"  # a phrase across a paragraph break is not in the file
    assert c(split) == [f"text phrase appears 0x in its file, need exactly once — {once}"]
    # a `current`-equal phrase whose pattern normalises to nothing: the empty pattern counts per paragraph
    empty = {"id": "R", "class": "prose", "baseline": "x", "current": " ⏎ ", "text": [" ⏎ "]}
    assert c("ab\n\ncd", empty) == ["text phrase appears 6x in its file, need exactly once —  ⏎ "]
