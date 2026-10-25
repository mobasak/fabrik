"""The lean program's size measure and L1 ceiling (``commands/command_measure.py``) and its
``assemble_commands.py --check`` exit 5 / ``--ratchet`` wiring. Fixture trees live under
``tmp_path``; the live corpus is measured against the committed ``commands/_size_ceiling.json``."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cm = _load("command_measure", "commands/command_measure.py")
cr = _load("command_rules", "commands/command_rules.py")
ac = _load("ac_measure", "commands/assemble_commands.py")

APPENDED = ("close-feedback", "agent-feedback")
FEEDBACK = "## Close-out\n\nA `seat-b` that notices a defect is an example, not a dispatch.\n"


def _w(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _tree(tmp_path: Path, render: str) -> dict[str, Path]:
    """A repo root with one command `demo`, two seats, fragments, reads and a decisions table."""
    root = tmp_path / "repo"
    src = root / "commands" / "_sources"
    out = tmp_path / "render"
    _w(src / "demo.md", "# /demo\n\n{{include:orient}}\nbody\n")
    _w(src / "other.md", "# /other\n\nfive words in this source\n")
    _w(root / "commands" / "_fragments" / "orient.md", "orient fragment words\n")
    _w(root / "commands" / "_fragments" / "close-feedback.md", FEEDBACK)
    _w(root / "commands" / "_fragments" / "agent-feedback.md", "agent feedback three\n")
    _w(root / "commands" / "_fragments" / "catalogue.md", "one two three four\n")
    _w(root / "commands" / "_agents" / "seat-a.md", "source of seat a\n")
    _w(root / "commands" / "helper.py", "print('a script is run, not read')\n")
    _w(root / "docs" / "reference" / "guide.md", "g " * 10)
    _w(root / "agents-fabrik.md", "m " * 7)
    _w(root / "CHANGELOG.md", "c " * 50)
    _w(root / "docs" / "development" / "reviews" / "r.md", "r " * 50)
    _w(root / "scripts" / "tool.py", "t " * 50)
    _w(root / "docs" / "DECISIONS.md",
       "| D-1 | d | w | raises demo; releases seat-a | y | z |\n| D-2 | d | w | names `docs/new.md` | y | z |\n"
       "| D-3 | d | w | an unrelated row | y | z |\n")
    _w(out / "demo.md", render)
    _w(out / "other.md", "# /other\n")
    _w(out / "_agents" / "seat-a.md", "rendered seat a has six words\n")
    # a rendered seat definition carries the appended agent-feedback text, as the renderer writes it
    _w(out / "_agents" / "seat-b.md", "seat b eight words in its rendered definition\nagent feedback three\n")
    return {"root": root, "src": src, "out": out, "ceiling": root / "commands" / "_size_ceiling.json"}


def _measure(t: dict[str, Path], cmd: str = "demo") -> dict:
    return cm.measure(cmd, t["out"], t["root"], t["src"], appended=APPENDED)


def _all(t: dict[str, Path]) -> dict[str, dict]:
    return cm.measure_all(t["out"], t["root"], t["src"], appended=APPENDED)


# ── Behaviour 1 ───────────────────────────────────────────────────────────────────────────────
def test_measure_splits_own_text_from_reads(tmp_path: Path) -> None:
    render = (
        "Read `commands/_fragments/catalogue.md` and ./commands/_sources/other.md first.\n"
        "Dispatch a seat-a seat. Run /seat-b for the visual pass.\n"
        "Then read docs//reference/guide.md, /opt/fabrik/agents-fabrik.md and agents-fabrik.md again.\n"
        "Never read commands/_fragments/orient.md twice; run commands/helper.py and scripts/tool.py.\n"
        "Append to CHANGELOG.md and docs/development/reviews/r.md; cite D-1 and D-9; skip ~/x/y.md, "
        "/opt/fabrik-lib/README.md, commands/_fragments/ and https://x.io/a/b.md.\n"
        "Also commands/_fragments/close-feedback.md.\n\n" + FEEDBACK
    )
    t = _tree(tmp_path, render)
    m = _measure(t)
    assert m["render"] == len(render.split())
    # own: the named catalogue and another command's source; never the included orient, the appended
    # close-feedback (named by path too), the own source or a script
    assert m["own_reads"] == {"commands/_fragments/catalogue.md": 4, "commands/_sources/other.md": 7}
    # seat-a named bare; seat-b only as /seat-b and inside the appended fragment's text
    assert m["agents"] == {"seat-a": 6}
    assert m["own"] == m["render"] + 4 + 7 + 6
    # reads: `//` collapsed, the root file under both spellings once; never a ledger, a review, a
    # script, an absent row, a home path, another repo, a directory or a URL
    # the D-1 row "| D-1 | d | w | raises demo; releases seat-a | y | z |" is 16 whitespace-split words
    assert m["reads"] == {"docs/reference/guide.md": 10, "agents-fabrik.md": 7, "docs/DECISIONS.md#D-1": 16}
    assert m["reads_total"] == sum(m["reads"].values())


def test_an_appended_fragment_is_skipped_only_where_its_text_is_read(tmp_path: Path) -> None:
    # agent-feedback rides inside seat-b's rendered definition: counted once, there
    t = _tree(tmp_path, "Use seat-b; see commands/_fragments/agent-feedback.md.\n")
    assert "commands/_fragments/agent-feedback.md" not in _measure(t)["own_reads"]
    # no seat carries it: the named file is read on its own
    t = _tree(tmp_path / "b", "See commands/_fragments/agent-feedback.md.\n")
    assert _measure(t)["own_reads"] == {"commands/_fragments/agent-feedback.md": 3}
    # close-feedback named by path while NOT appended to this render: counted, a seat or not
    t = _tree(tmp_path / "c", "Use seat-a; read commands/_fragments/close-feedback.md.\n")
    assert _measure(t)["own_reads"] == {"commands/_fragments/close-feedback.md": len(FEEDBACK.split())}


def test_seats_named_in_own_text_files_and_by_path(tmp_path: Path) -> None:
    # a seat named only inside a fragment the render points at is dispatched by the command too
    t = _tree(tmp_path, "Read commands/_fragments/catalogue.md first.\n")
    _w(t["root"] / "commands" / "_fragments" / "catalogue.md", "then dispatch a seat-a seat\n")
    m = _measure(t)
    assert m["agents"] == {"seat-a": 6} and m["own_reads"] == {"commands/_fragments/catalogue.md": 5}
    # a definition named by path counts once, as its RENDERED text; the own source never counts
    t = _tree(tmp_path / "b", "See commands/_agents/seat-b.md and commands/_sources/demo.md; use seat-b.\n")
    m = _measure(t)
    assert m["agents"] == {"seat-b": 11} and m["own_reads"] == {}


def test_zero_width_characters_do_not_merge_words() -> None:
    assert cm.words("a\u200bb a\u00a0b a\ufeffb") == 6


def test_a_non_utf8_render_is_measured_not_raised(tmp_path: Path) -> None:
    t = _tree(tmp_path, "x")
    (t["out"] / "demo.md").write_bytes(b"caf\xe9 two words\n")
    assert _measure(t)["render"] == 3


# ── Behaviour 3 ───────────────────────────────────────────────────────────────────────────────
def _ratcheted(t: dict[str, Path]) -> dict:
    cm.ratchet(_all(t), t["ceiling"])
    return json.loads(t["ceiling"].read_text())


def _rewrite(t: dict[str, Path], doc: dict) -> None:
    t["ceiling"].write_text(json.dumps(doc), encoding="utf-8")


def _breaches(t: dict[str, Path]) -> list[str]:
    return cm.ceiling_findings(_all(t), t["ceiling"], t["root"])[0]


def test_ceiling_breach_kinds(tmp_path: Path) -> None:
    t = _tree(tmp_path, "Use seat-a and read docs/reference/guide.md. Cite D-1.\n")
    doc = _ratcheted(t)
    assert _breaches(t) == []
    row = doc["commands"]["demo"]
    # own over the ceiling
    _w(t["out"] / "demo.md", "Use seat-a and read docs/reference/guide.md. Cite D-1.\n" + "grow " * 40)
    assert any("demo" in b and "> ceiling" in b and "cut it back" in b for b in _breaches(t)), _breaches(t)
    # a hand raise without raised_by, then with a missing row, then with an existing one
    row["render"] = math.ceil(row["baseline_own"] * 1.03) + 100
    _rewrite(t, doc)
    assert any("raised" in b for b in _breaches(t)), _breaches(t)
    row["raised_by"] = "D-77"
    _rewrite(t, doc)
    assert any("D-77" in b and "add `raised_by" in b for b in _breaches(t)), _breaches(t)
    row["raised_by"] = "D-3"  # a real row that does not name the command
    _rewrite(t, doc)
    assert any("name demo" in b for b in _breaches(t)), _breaches(t)
    row["raised_by"] = "D-1"
    _rewrite(t, doc)
    assert _breaches(t) == []
    # a seat dropped from the render: breach until a D-row releases it
    _w(t["out"] / "demo.md", "Read docs/reference/guide.md. Cite D-1.\n")
    assert any("seat-a" in b and "released" in b for b in _breaches(t)), _breaches(t)
    row["released"] = {"seat-a": "D-2"}  # a real row that does not name the seat
    _rewrite(t, doc)
    assert any("name seat-a" in b for b in _breaches(t)), _breaches(t)
    row["released"] = {"seat-a": "D-1"}
    _rewrite(t, doc)
    assert not any("seat-a" in b for b in _breaches(t)), _breaches(t)
    # a seat newly named but not in the row
    _w(t["out"] / "demo.md", "Read docs/reference/guide.md. Cite D-1. Use seat-b.\n")
    assert any("seat-b" in b for b in _breaches(t)), _breaches(t)
    # a new read: breach until a D-row adds it
    _w(t["root"] / "docs" / "new.md", "n " * 5)
    _w(t["out"] / "demo.md", "Read docs/reference/guide.md and docs/new.md. Cite D-1.\n")
    assert any("docs/new.md" in b for b in _breaches(t)), _breaches(t)
    row["added"] = {"docs/new.md": "D-1"}  # a real row that does not name the read
    _rewrite(t, doc)
    assert any("name docs/new.md" in b for b in _breaches(t)), _breaches(t)
    row["added"] = {"docs/new.md": "D-2"}
    # a D-row read is licensed by ANOTHER row naming its id, never by itself
    _w(t["out"] / "demo.md", "Read docs/reference/guide.md and docs/new.md. Cite D-1 and D-3.\n")
    row["added"]["docs/DECISIONS.md#D-3"] = "D-3"
    _rewrite(t, doc)
    assert any("D-3" in b and "new to the frozen set" in b for b in _breaches(t)), _breaches(t)
    _w(t["root"] / "docs" / "DECISIONS.md",
       (t["root"] / "docs" / "DECISIONS.md").read_text() + "| D-4 | d | w | adds the D-3 read | y | z |\n")
    row["added"]["docs/DECISIONS.md#D-3"] = "D-4"
    _rewrite(t, doc)
    assert not any("D-3" in b for b in _breaches(t)), _breaches(t)
    _rewrite(t, doc)
    assert not any("docs/new.md" in b for b in _breaches(t)), _breaches(t)
    # a missing row, an orphan row
    del doc["commands"]["other"]
    doc["commands"]["gone"] = dict(row)
    _rewrite(t, doc)
    found = _breaches(t)
    assert any("other" in b and "no ceiling row" in b for b in found), found
    assert any("gone" in b and "no command" in b for b in found), found
    # a malformed or missing file is one breach, never a raise, and says how to fix it
    t["ceiling"].write_text("{not json", encoding="utf-8")
    assert len(_breaches(t)) == 1 and "fix the file by hand" in _breaches(t)[0]
    for bad in ({"agents": [["x"]]}, {"reads": {"total": 1, "paths": {"a": "x"}}}, {"reads": {"paths": {}}},
                {"added": {"a": 1}}, {"baseline_own": True}):
        _rewrite(t, {"commands": {"demo": {**row, **bad}}})
        assert len(_breaches(t)) == 1 and "is not {" in _breaches(t)[0], (bad, _breaches(t))
    _rewrite(t, {"commands": {}, "retired": {"x": "big"}})
    assert len(_breaches(t)) == 1 and "retired" in _breaches(t)[0]
    t["ceiling"].unlink()
    assert len(_breaches(t)) == 1 and "missing" in _breaches(t)[0]


def test_ceiling_findings_never_raises(tmp_path: Path, monkeypatch) -> None:
    t = _tree(tmp_path, "x")

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cm, "measure_all", boom)
    out = cm.findings(t["out"], t["root"], t["src"], APPENDED, t["ceiling"])
    assert len(out[0]) == 1 and "kaboom" in out[0][0], out


# ── Behaviour 4 ───────────────────────────────────────────────────────────────────────────────
def test_ratchet_lowers_adds_never_raises(tmp_path: Path) -> None:
    t = _tree(tmp_path, "Use seat-a and read docs/reference/guide.md. " + "word " * 100)
    doc = _ratcheted(t)
    row = doc["commands"]["demo"]
    base, ceiling = row["baseline_own"], row["render"]
    assert ceiling == math.ceil(base * 1.03) and row["agents"] == ["seat-a"]
    assert row["reads"]["paths"] == {"docs/reference/guide.md": 10}
    # a shrink lowers; a regrowth does not raise
    _w(t["out"] / "demo.md", "Use seat-a and read docs/reference/guide.md. " + "word " * 50)
    low = _ratcheted(t)["commands"]["demo"]
    assert low["render"] < ceiling and low["baseline_own"] == base
    _w(t["out"] / "demo.md", "Use seat-a and read docs/reference/guide.md. " + "word " * 100)
    assert _ratcheted(t)["commands"]["demo"]["render"] == low["render"]
    # a newly named seat joins the set; a frozen reads set and raised_by are never rewritten
    doc = json.loads(t["ceiling"].read_text())
    doc["commands"]["demo"]["raised_by"] = "D-1"
    _rewrite(t, doc)
    _w(t["root"] / "docs" / "new.md", "n " * 5)
    _w(t["out"] / "demo.md", "Use seat-a, seat-b; read docs/reference/guide.md and docs/new.md.")
    row = _ratcheted(t)["commands"]["demo"]
    assert row["agents"] == ["seat-a", "seat-b"] and row["raised_by"] == "D-1"
    assert row["reads"]["paths"] == {"docs/reference/guide.md": 10}
    # an orphan row retires; a retired name comes back with its old ceiling, never a fresh one
    (t["out"] / "other.md").unlink()
    doc = _ratcheted(t)
    assert "other" not in doc["commands"] and "other" in doc["retired"]
    old = doc["retired"]["other"]
    _w(t["out"] / "other.md", "# /other\n" + "big " * 500)
    back = _ratcheted(t)["commands"]["other"]
    assert back["render"] == old and back["baseline_own"] == old, back
    assert any("other" in b and "> ceiling" in b for b in _breaches(t)), _breaches(t)
    # a retired name coming back SMALLER takes its own +3%, and the file --ratchet wrote passes --check
    doc = json.loads(t["ceiling"].read_text())
    doc["commands"].pop("other")
    doc["retired"]["other"] = 5000
    _rewrite(t, doc)
    _w(t["out"] / "other.md", "# /other\n")
    back = _ratcheted(t)["commands"]["other"]
    assert back["render"] == math.ceil(back["baseline_own"] * 1.03) < 5000, back
    assert not any("other" in b for b in _breaches(t)), _breaches(t)


def test_ratchet_is_silent_atomic_and_drops_a_stale_tombstone(tmp_path: Path) -> None:
    t = _tree(tmp_path, "Use seat-a and read docs/reference/guide.md.\n")
    _ratcheted(t)
    t["ceiling"].chmod(0o664)  # not the 0644 a new file gets, so a constant mode would fail below
    before, stat = t["ceiling"].read_bytes(), t["ceiling"].stat()
    assert cm.ratchet(_all(t), t["ceiling"]) == []
    assert t["ceiling"].read_bytes() == before and t["ceiling"].stat().st_mtime_ns == stat.st_mtime_ns
    doc = json.loads(before)
    doc["retired"]["demo"] = 7
    _rewrite(t, doc)
    t["ceiling"].chmod(0o664)
    changes = cm.ratchet(_all(t), t["ceiling"])
    assert any("stale tombstone" in c for c in changes), changes
    assert "demo" not in json.loads(t["ceiling"].read_text())["retired"]
    assert t["ceiling"].stat().st_mode & 0o777 == 0o664
    assert [p.name for p in t["ceiling"].parent.iterdir() if p.name.startswith(".size_ceiling.")] == []


def test_ratchet_cli_never_renders_the_installed_corpus(tmp_path: Path, monkeypatch) -> None:
    calls: list[Path] = []
    real = ac.render

    def spy(dest, *a, **k):
        calls.append(Path(dest))
        return real(dest, *a, **k)

    monkeypatch.setattr(ac, "render", spy)
    target = tmp_path / "ceiling.json"
    monkeypatch.setattr(cm, "CEILING", target)
    ac.ratchet_cli()
    assert calls and all(c.resolve() != ac.OUT.resolve() for c in calls), calls
    assert "fabrik-task" in json.loads(target.read_text())["commands"]


def test_ratchet_cli_reports_render_errors_and_a_malformed_file(tmp_path: Path, monkeypatch, capsys) -> None:
    target = tmp_path / "ceiling.json"
    monkeypatch.setattr(cm, "CEILING", target)
    real = ac.render

    def broken(dest, *a, **k):
        print("RENDER ERRORS:")
        print(" - demo: unknown fragment nosuch")
        raise SystemExit(2)

    monkeypatch.setattr(ac, "render", broken)
    with pytest.raises(SystemExit) as exc:
        ac.ratchet_cli()
    assert exc.value.code == 2 and "unknown fragment nosuch" in capsys.readouterr().out
    monkeypatch.setattr(ac, "render", real)
    target.write_text("{bad", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        ac.ratchet_cli()
    assert exc.value.code == 5 and "CEILING ceiling.json: unreadable" in capsys.readouterr().out
    target.unlink()

    def unwritable(*a, **k):
        raise PermissionError("read-only directory")

    monkeypatch.setattr(cm, "ratchet", unwritable)
    with pytest.raises(SystemExit) as exc:
        ac.ratchet_cli()
    assert exc.value.code == 5 and "ratchet failed — PermissionError" in capsys.readouterr().out


def test_the_modes_are_mutually_exclusive() -> None:
    import subprocess

    r = subprocess.run([sys.executable, str(ROOT / "commands" / "assemble_commands.py"), "--ratchet", "--check"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "not allowed with" in r.stderr, (r.returncode, r.stderr)


# ── Behaviour 5 ───────────────────────────────────────────────────────────────────────────────
def test_reports_never_breach(tmp_path: Path) -> None:
    t = _tree(tmp_path, "Use seat-a and read docs/reference/guide.md. " + "word " * 100)
    _ratcheted(t)
    _w(t["root"] / "docs" / "reference" / "guide.md", "g " * 30)
    _w(t["out"] / "demo.md", "Use seat-a and read docs/reference/guide.md. " + "word " * 10)
    breaches, reports = cm.ceiling_findings(_all(t), t["ceiling"], t["root"])
    assert breaches == []
    assert any("docs/reference/guide.md" in r and "10→30" in r for r in reports), reports
    assert any("demo" in r and "--ratchet" in r for r in reports), reports


# ── Behaviour 2 ───────────────────────────────────────────────────────────────────────────────
def test_check_exit_order_loss_then_ceiling_then_drift(tmp_path: Path, monkeypatch, capsys) -> None:
    inst, skills, agents = tmp_path / "installed", tmp_path / "skills", tmp_path / "agents"
    ac.render(inst, skills, agents_dest=agents)
    monkeypatch.setattr(ac, "OUT", inst)
    monkeypatch.setattr(ac, "SKILLS", skills)
    monkeypatch.setattr(ac, "AGENTS", agents)
    ceiling = tmp_path / "ceiling.json"
    monkeypatch.setattr(ac.command_measure, "CEILING", ceiling)
    ac.ratchet_cli()
    doc = json.loads(ceiling.read_text())
    capsys.readouterr()
    # 1. clean: no exit at all
    ac.check()
    assert "check OK" in capsys.readouterr().out
    # 2. a breach alone exits 5
    doc["commands"]["fabrik-task"]["render"] = 1
    doc["commands"]["fabrik-task"]["raised_by"] = "D-1216"
    ceiling.write_text(json.dumps(doc))
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 5
    out = capsys.readouterr().out
    assert "CEILING:" in out and "DRIFT:" not in out, out
    # 3. breach and drift: 5 outranks 1, printed first
    (inst / "fabrik-task.md").write_text("hand edit\n")
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 5
    out = capsys.readouterr().out
    assert out.index("CEILING:") < out.index("DRIFT:")
    # 4. a LOSS outranks the breach
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "broken.yaml").write_text("- not a mapping\n")
    monkeypatch.setattr(ac.command_rules, "RULES", rules)
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 4
    out = capsys.readouterr().out
    assert out.index("LOSS:") < out.index("CEILING:") < out.index("DRIFT:")
    # 5. a measure that raises is a breach, never a traceback (exit 5, not 1)
    monkeypatch.setattr(ac.command_rules, "RULES", tmp_path / "none")

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(ac.command_measure, "measure_all", boom)
    with pytest.raises(SystemExit) as exc:
        ac.check()
    assert exc.value.code == 5
    assert "kaboom" in capsys.readouterr().out


# ── Behaviour 6 ───────────────────────────────────────────────────────────────────────────────
def test_live_corpus_within_ceiling(tmp_path: Path) -> None:
    out = tmp_path / "render"
    ac.render(out, None, agents_dest=out / "_agents")
    measured = cm.measure_all(out, ROOT, ac.SRC, appended=(ac._CLOSE_FEEDBACK, ac._AGENT_FEEDBACK))
    breaches, reports = cm.ceiling_findings(measured, cm.CEILING, ROOT)
    assert breaches == [], breaches
    doc = json.loads(cm.CEILING.read_text(encoding="utf-8"))
    assert set(doc["commands"]) == {p.stem for p in ac.SRC.glob("*.md")}
    for line in reports:
        print(line)
