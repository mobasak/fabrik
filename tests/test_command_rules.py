"""The lean program's rule test (W-a9b5e763 slice A): ``commands/command_rules.py`` and the
``assemble_commands.py --check`` LOSS exit. Fixture ledgers live under ``tmp_path``; the live
corpus is rendered here, never read from ``--check``'s temp dir."""

from __future__ import annotations

import hashlib
import importlib.util
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


ENTRY = {"id": "R1", "section": "## Scope", "baseline": "Never stage a sibling's file.",
         "current": "Never stage a sibling's file.", "text": ["Never stage"]}


# ── Behaviour 1 ───────────────────────────────────────────────────────────────────────────────
def test_the_live_corpus_has_no_loss(tmp_path: Path) -> None:
    ac.render(tmp_path, None, agents_dest=tmp_path / "_agents")
    assert list(tmp_path.glob("*.md")), "the render produced no command"
    counts = cr.entry_counts()
    for name, n in sorted(counts.items()):
        print(f"LEDGER {name}: {n} entries")
    assert cr.losses(tmp_path, ROOT, ac.SRC) == []


# ── Behaviour 2 ───────────────────────────────────────────────────────────────────────────────
def test_units_and_exact_match() -> None:
    text = (
        "---\nx: y\n---\n# T\n\n| a | b |\n|---|---|\n\n```bash\nrun --x\n```\n"
        "<!-- POOL OFF: Never write NO-POOL. -->\n"
        "2. Use e.g. `a.b` here. Then **stop** now.\n"
    )
    us = cr.units(text)
    kinds = [k for _h, k, _t in us]
    assert kinds == ["heading", "table", "table", "fence", "comment", "prose", "prose"], us
    assert us[5][2] == "Use e.g. `a.b` here"  # step number stripped, no split after e.g. or in backticks
    assert us[6][2] == "Then stop now"  # emphasis stripped, trailing period dropped
    assert cr.normalise("Never edit `__init__.py`.") == "Never edit `__init__.py`"
    base = cr.keys("## S\n\nNever stage it. Keep going.\n")
    assert cr.vanished(base, "## S\n\nNever   **stage** it.\nKeep going\n") == []
    assert cr.vanished(base, "## S\n\nNever stage this. Keep going.\n") == [2]
    assert cr.vanished(base, "## Other\n\nNever stage it. Keep going.\n") == [1, 2, 3]
    assert cr.vanished(base, "## S\n\n<!-- Never stage it. -->\nKeep going.\n") == [2]
    commented = cr.keys("## S\n\n<!-- dead note -->\nKeep going.\n")
    assert cr.vanished(commented, "## S\n\nKeep going.\n") == []  # a comment carries no rule to classify


# ── Behaviour 3 ───────────────────────────────────────────────────────────────────────────────
def test_each_failed_carrier_is_a_loss(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    _ledger(t, [ENTRY])
    assert _losses(t) == []
    t = _tree(tmp_path / "gone", render=SOURCE.replace("Never stage a sibling's file.", "Stage carefully."))
    _ledger(t, [ENTRY])
    assert any("`current` not found" in x for x in _losses(t))
    t = _tree(tmp_path / "phrase")
    _ledger(t, [{**ENTRY, "text": ["Never commit"]}])
    assert any("text phrase not in" in x for x in _losses(t))
    t = _tree(tmp_path / "forbid", render=SOURCE + "\n<!-- always force-push -->\n")
    _ledger(t, [{**ENTRY, "forbidden": ["force-push"]}])
    assert any("forbidden phrase present" in x for x in _losses(t))
    t = _tree(tmp_path / "commented", render=SOURCE.replace("Never stage a sibling's file.", "<!-- Never stage a sibling's file. -->"))
    _ledger(t, [ENTRY])
    assert any("`current` not found" in x for x in _losses(t))
    t = _tree(tmp_path / "section")
    _ledger(t, [{**ENTRY, "section": "## Close"}])
    assert any("`current` not found under its section" in x for x in _losses(t))
    t = _tree(tmp_path / "order")
    entries = [
        {"id": "C1", "section": "## Close", "current": "Commit by pathspec.", "text": ["Commit"]},
        {"id": "C2", "section": "## Close", "current": "Push it.", "text": ["Push"], "ordered": ["C2", "C1"]},
    ]
    _ledger(t, entries)
    assert any("out of order" in x for x in _losses(t))
    entries[1]["ordered"] = ["C1", "C2"]
    _ledger(t, entries)
    assert _losses(t) == []


# ── Behaviour 4 ───────────────────────────────────────────────────────────────────────────────
def test_classification_and_baseline_losses(tmp_path: Path) -> None:
    rewritten = SOURCE.replace("Run the probe on a copy. ", "")
    t = _tree(tmp_path, source=rewritten, render=rewritten)
    _ledger(t, [ENTRY])
    lost = _losses(t)
    assert len(lost) == 1 and "vanished, unclassified" in lost[0] and "Run the probe on a copy" in lost[0]
    line = next(i for i, k in enumerate(cr.keys(cr.own_text(SOURCE)), 1) if "Run the probe" in k)
    _ledger(t, [ENTRY], vanished={f"L{line}": "narrative"})
    assert _losses(t) == []
    _ledger(t, [ENTRY], vanished={f"L{line}": {"rule": ["R1"]}})
    assert _losses(t) == []
    for bad in ("unchanged", {"rule": ["R7"]}, {"duplicate-of": "R7"}):
        _ledger(t, [ENTRY], vanished={f"L{line}": bad})
        assert any("malformed" in x for x in _losses(t)), bad
    p = _ledger(t, [ENTRY], vanished={f"L{line}": "narrative"})
    (t["rules"] / "demo.baseline.txt").write_text("tampered\n")
    assert any("baseline_sha256 does not match" in x for x in _losses(t))
    (t["rules"] / "demo.baseline.txt").unlink()
    assert any("baseline file missing" in x for x in _losses(t))
    data = yaml.safe_load(p.read_text())
    del data["baseline_sentences"]
    p.write_text(yaml.safe_dump(data))
    assert any("baseline file missing" in x for x in _losses(t))


# ── Behaviour 5 ───────────────────────────────────────────────────────────────────────────────
def _refused(t: dict[str, Path], **override) -> str:
    p = t["rules"] / "demo.yaml"
    base = t["rules"] / "demo.baseline.txt"
    sha = cr.write_baseline(cr.own_text(SOURCE), base)
    data = {"command": "demo", "baseline_sentences": base.name, "baseline_sha256": sha, "entries": [ENTRY]}
    data.update(override)
    p.write_text(yaml.safe_dump(data, sort_keys=False) if not isinstance(data.get("raw"), str) else data["raw"])
    lost = _losses(t)
    assert len(lost) == 1 and "malformed" in lost[0], lost
    return lost[0]


def test_malformed_ledgers_are_one_loss_line_each(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    (t["rules"] / "demo.yaml").write_text("- just\n- a list\n")
    assert _losses(t) == ["LOSS demo.yaml: malformed — not a mapping"]
    (t["rules"] / "demo.yaml").write_text("command: [unclosed\n")
    assert "unreadable" in _losses(t)[0]
    assert "unknown key" in _refused(t, extra=1)
    assert "duplicate entry id" in _refused(t, entries=[ENTRY, ENTRY])
    assert "no carrier" in _refused(t, entries=[{"id": "R2", "current": "Push it."}])
    two = [ENTRY, {"id": "R3", "file": "docs/DECISIONS.md", "current": "x", "text": ["x"], "ordered": ["R1"]}]
    assert "spans files" in _refused(t, entries=two)
    assert "escapes the repo" in _refused(t, entries=[{**ENTRY, "file": "../outside.md"}])
    assert "needs a `text` carrier" in _refused(t, entries=[{"id": "R4", "current": "x", "enforced": "t.py::f"}])
    tests_dir = t["root"] / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_g.py").write_text(
        "import subprocess\n"
        "def test_prints():\n    r = subprocess.run(['gate.py'])\n    assert 'ok' in r.stdout\n"
        "def test_refuses():\n    r = subprocess.run(['gate.py', '--bad'])\n    assert r.returncode != 0\n"
        "def test_other():\n    r = subprocess.run(['other.py'])\n    assert r.returncode == 2\n"
    )
    enf = {**ENTRY, "text": ["Never stage"], "current": "Never stage a sibling's file."}
    assert "asserts no refusal" in _refused(t, entries=[{**enf, "enforced": "tests/test_g.py::test_prints"}])
    with_script = {**enf, "text": ["Never stage"]}
    assert "never invokes the script" in _refused(
        t, entries=[{**with_script, "enforced": "tests/test_g.py::test_other"}]
    )
    retired_forbidden = [{"decision": "D-0001", "entry": {"id": "R9", "forbidden": ["x"]}}]
    assert "never retired" in _refused(t, retired=retired_forbidden)
    assert "no D-row" in _refused(t, retired=[{"decision": "D-0002", "entry": {"id": "R9", "text": ["x"]}}])


def test_an_enforced_entry_passing_the_lint_loads(tmp_path: Path) -> None:
    t = _tree(tmp_path, source=SOURCE.replace("Stop at the pin.", "Run `gate.py` first."))
    (t["root"] / "tests").mkdir()
    (t["root"] / "tests" / "test_g.py").write_text(
        "import subprocess\ndef test_refuses():\n    r = subprocess.run(['gate.py', '--bad'])\n"
        "    assert r.returncode != 0\n"
    )
    entry = {"id": "R5", "section": "## Scope", "current": "Run `gate.py` first.", "text": ["`gate.py`"],
             "enforced": "tests/test_g.py::test_refuses"}
    _ledger(t, [entry], baseline_from=SOURCE.replace("Stop at the pin.", "Run `gate.py` first."))
    assert _losses(t) == []


# ── Behaviour 6 ───────────────────────────────────────────────────────────────────────────────
def test_shared_and_skipped_ledgers(tmp_path: Path) -> None:
    t = _tree(tmp_path)
    frag = t["root"] / "commands" / "_fragments" / "orient.md"
    frag.parent.mkdir(parents=True)
    frag.write_text("## Orient\n\nRead the packs first.\n")
    base = t["rules"] / "_shared" / "orient.baseline.txt"
    sha = cr.write_baseline(frag.read_text(), base)
    led = {"shared": "commands/_fragments/orient.md", "baseline_sentences": base.name, "baseline_sha256": sha,
           "entries": [{"id": "O1", "section": "## Orient", "current": "Read the packs first.", "text": ["packs"]}]}
    (t["rules"] / "_shared" / "orient.yaml").write_text(yaml.safe_dump(led))
    assert _losses(t) == []
    frag.write_text("## Orient\n\nRead the rules.\n")
    lost = _losses(t)
    assert any("orient.yaml O1" in x for x in lost) and any("vanished, unclassified" in x for x in lost)
    (t["rules"] / "_shared" / "orient.yaml").unlink()
    _ledger(t, [ENTRY])
    (t["src"] / "demo.md").unlink()
    assert _losses(t) == []  # a command ledger with no source in src_dir is skipped


# ── Behaviour 7 ───────────────────────────────────────────────────────────────────────────────
def test_check_exits_4_on_a_loss_and_1_on_drift_alone(tmp_path: Path, monkeypatch, capsys) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "broken.yaml").write_text("- not a mapping\n")
    monkeypatch.setattr(cr, "RULES", rules)
    monkeypatch.setattr(ac, "OUT", tmp_path / "installed")  # empty: every command reads as drift too
    monkeypatch.setattr(ac, "SKILLS", tmp_path / "skills")
    monkeypatch.setattr(ac, "AGENTS", tmp_path / "agents")
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 4
    out = capsys.readouterr().out
    assert out.index("LOSS:") < out.index("DRIFT:")
    (rules / "broken.yaml").unlink()
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 1
    # the main checkout's pre-commit entry passes a 4 through, so a LOSS refuses the commit
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
    sha = cr.write_baseline("## S\n\nOne. Two.\n", out)
    assert sha == hashlib.sha256(out.read_bytes()).hexdigest()
    assert out.read_text().splitlines() == ["## S ¦ ## S", "## S ¦ One", "## S ¦ Two"]
