"""Regression tests for check_schema_sync's data-contract drift WARN.

The WARN is advisory (never blocks): it fires only when a schema/migration changed, a
docs/data-contract.md exists, and that contract was NOT also staged. It must stay silent on
every other path so it doesn't cry wolf.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "enforcement"))
import check_schema_sync as c  # noqa: E402


def test_warn_fires_on_schema_change_with_stale_contract(monkeypatch, capsys) -> None:
    monkeypatch.setattr(c, "_repo_root", lambda: "/repo")
    monkeypatch.setattr(os.path, "exists", lambda _p: True)  # contract file present
    c.warn_if_data_contract_stale(["db/schema.sql"])
    out = capsys.readouterr().out
    assert "⚠" in out  # marked so final_gate surfaces it in --json
    assert "WARN" in out and c.DATA_CONTRACT_FILE in out


def test_silent_when_contract_also_staged(monkeypatch, capsys) -> None:
    monkeypatch.setattr(c, "_repo_root", lambda: "/repo")
    monkeypatch.setattr(os.path, "exists", lambda _p: True)
    c.warn_if_data_contract_stale(["db/schema.sql", c.DATA_CONTRACT_FILE])
    assert capsys.readouterr().out == ""


def test_silent_when_no_schema_change(monkeypatch, capsys) -> None:
    monkeypatch.setattr(os.path, "exists", lambda _p: True)
    c.warn_if_data_contract_stale(["src/app/main.py"])
    assert capsys.readouterr().out == ""


def test_silent_when_no_contract_file(monkeypatch, capsys) -> None:
    monkeypatch.setattr(c, "_repo_root", lambda: "/repo")
    monkeypatch.setattr(os.path, "exists", lambda _p: False)  # project has no contract
    c.warn_if_data_contract_stale(["db/schema.sql"])
    assert capsys.readouterr().out == ""


def test_py_migration_counts_as_schema_change(monkeypatch, capsys) -> None:
    monkeypatch.setattr(c, "_repo_root", lambda: "/repo")
    monkeypatch.setattr(os.path, "exists", lambda _p: True)
    c.warn_if_data_contract_stale(["db/migrations/0001_add_col.py"])
    assert "WARN" in capsys.readouterr().out
