"""D-181/D-182: `scripts/classify_services.py` — the daily chain's paid pool step — never dispatches
while the committed pool policy is OFF (the cursor is not moved either: the gate sits before
argparse, so no flag reaches the dispatch)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    for p in (str(ROOT), str(ROOT / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(
        "classify_services_under_test", ROOT / "scripts" / "classify_services.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_main_returns_zero_and_never_dispatches_while_the_policy_is_off(monkeypatch, capsys):
    cs = _load()
    calls: list = []

    def boom(*a, **k):
        calls.append(a)
        raise RuntimeError("dispatch reached")

    monkeypatch.setattr(cs, "fanout", boom)
    monkeypatch.setattr("sys.argv", ["classify_services", "--apply", "--max-per-run", "1"])
    monkeypatch.setenv("FABRIK_POOL_POLICY", "off")
    assert cs.main() == 0
    assert calls == []
    assert "OFF by ruling" in capsys.readouterr().err


def test_help_and_bad_flags_still_reach_argparse_while_the_policy_is_off(monkeypatch, capsys):
    """Review r1: the gate sits AFTER argparse — `--help` prints usage (SystemExit 0) and a bad flag
    is an argparse error (SystemExit 2), never a silent policy exit 0."""
    import pytest

    cs = _load()
    monkeypatch.setattr(
        cs, "fanout", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("dispatch reached"))
    )
    monkeypatch.setenv("FABRIK_POOL_POLICY", "off")
    monkeypatch.setattr("sys.argv", ["classify_services", "--help"])
    with pytest.raises(SystemExit) as e:
        cs.main()
    assert e.value.code == 0 and "usage" in capsys.readouterr().out.lower()
    monkeypatch.setattr("sys.argv", ["classify_services", "--bogus-flag"])
    with pytest.raises(SystemExit) as e:
        cs.main()
    assert e.value.code == 2
