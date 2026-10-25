"""The lean program's rule test (W-a9b5e763 slice A): ``commands/command_rules.py`` and the
``assemble_commands.py --check`` LOSS exit. Fixture ledgers live under ``tmp_path``; the live
corpus is rendered here, never read from ``--check``'s temp dir."""

from __future__ import annotations

import hashlib
import importlib.util
import os
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
         "current": "Never stage a sibling's file.", "text": ["Never stage"]}


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
def test_each_failed_carrier_is_a_loss(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    _ledger(t, [ENTRY])
    assert _losses(t) == []
    t = _tree(tmp_path / "gone", render=SOURCE.replace("Never stage a sibling's file.", "Stage carefully."))
    _ledger(t, [ENTRY])
    _one(_losses(t), "`current` is not a unit under its section")
    longer = SOURCE.replace("Never stage a sibling's file.", "Never stage a sibling's file twice.")
    t = _tree(tmp_path / "longer", render=longer)
    _ledger(t, [ENTRY])
    _one(_losses(t), "`current` is not a unit")  # a substring of a longer sentence is not the rule
    commented = SOURCE.replace("Never stage a sibling's file.", "<!-- Never stage a sibling's file. -->")
    t = _tree(tmp_path / "commented", render=commented)
    _ledger(t, [ENTRY])
    _one(_losses(t), "`current` is not a unit")
    t = _tree(tmp_path / "phrase")
    _ledger(t, [{**ENTRY, "text": ["Never commit"]}])
    _one(_losses(t), "text phrase not in `current`")
    t = _tree(tmp_path / "textonly")
    _ledger(t, [{"id": "R2", "section": "## Scope", "text": ["Never commit"]}])
    _one(_losses(t), "text phrase not under its section")  # a text carrier with no `current` is checked
    t = _tree(tmp_path / "forbid", render=SOURCE + "\n<!-- always force-\npush -->\n")
    _ledger(t, [{**ENTRY, "forbidden": ["force- push"]}])
    _one(_losses(t), "forbidden phrase present")  # comments and line wraps included
    t = _tree(tmp_path / "section")
    _ledger(t, [{**ENTRY, "section": "## Close"}])
    _one(_losses(t), "`current` is not a unit under its section")
    t = _tree(tmp_path / "nosection")
    _ledger(t, [{**ENTRY, "section": "## Absent"}])
    _one(_losses(t), "section '## Absent' missing")
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
    _one(_losses(t), "out of order or missing")
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
    for good in ("narrative", {"rule": ["R1"]}, {"duplicate-of": "R1"}):
        _ledger(t, [ENTRY], vanished={f"L{line}": good})
        assert _losses(t) == [], good
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
    # § The rule test step 8: a rule changed on purpose appends its D-row to `changed-by:`
    t = _tree(tmp_path)
    _ledger(t, [{**ENTRY, "changed-by": ["D-0001"]}])
    assert _losses(t) == []
    for bad in (["D-0404"], "D-0001", [], ["D-0001", 7]):
        _ledger(t, [{**ENTRY, "changed-by": bad}])
        _one(_losses(t), "changed-by")


def test_normalise_is_idempotent_on_every_live_unit() -> None:
    # `_check` re-normalises a stored `current`; a unit that changes on a second pass can never match
    # (a unit ending in " ." kept its space: "HTTP 404 ." -> "HTTP 404 " -> "HTTP 404")
    assert cr.normalise("HTTP 404 .") == cr.normalise(cr.normalise("HTTP 404 ."))
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
