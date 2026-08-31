"""Vulture whitelist wiring in final_gate (upstream 01M1CM6G, D-058).

The gate ran vulture with no suppression mechanism, so required-but-unused interface
parameters (Protocol stubs, callback contracts) red the gate wherever the toolchain is
actually installed — 4/4 false positives measured at web-ecommerce-factory. The adopted
fix is vulture's documented whitelist idiom: a repo-root `.vulture-whitelist.py` is scanned
alongside src/ when present. These tests pin the two load-bearing properties: the file is
included exactly when it exists, and its absence leaves the argv identical to the historic
one (the fix can never change a repo that lacks the file).
"""

import importlib.util
from pathlib import Path

GATE = Path(__file__).resolve().parents[2] / "scripts" / "final_gate.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("final_gate_under_test", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_whitelist_absent_argv_is_the_historic_invocation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fg = _load_gate()
    argv = fg._vulture_argv()
    assert ".vulture-whitelist.py" not in argv
    assert argv[1:] == [
        "-m",
        "vulture",
        "src/",
        "--min-confidence",
        "95",
        "--exclude",
        "src/fabrik/wordpress/,src/fabrik/drivers/,src/fabrik/provisioner.py",
    ]


def test_whitelist_present_is_scanned_as_a_path_not_an_option_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".vulture-whitelist.py").write_text("_.sql\n")
    fg = _load_gate()
    argv = fg._vulture_argv()
    assert ".vulture-whitelist.py" in argv
    # It must sit in the PATHS region (right after src/, before the first option) — appended
    # after --exclude it would be parsed as part of the option tail by a future refactor.
    assert argv.index(".vulture-whitelist.py") == argv.index("src/") + 1
    assert argv.index(".vulture-whitelist.py") < argv.index("--min-confidence")


def test_run_static_checks_uses_the_helper():
    # The helper is only a fix if the gate calls it: the inline vulture argv it replaced
    # must not resurface in run_static_checks (the revert shape of this change).
    src = GATE.read_text(encoding="utf-8")
    body = src[src.index("def run_static_checks") :]
    assert "_vulture_argv()" in body
    assert '"-m",\n            "vulture"' not in body
