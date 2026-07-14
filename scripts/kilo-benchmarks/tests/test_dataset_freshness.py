#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/dataset_freshness.py
"""Behavior tests for the stale-dataset guard.

The bug this guard exists to prevent: we benched `terminal-bench-core==0.1.1` for weeks
after Terminal-Bench moved to 2.x (a different package), paid for a full 80-task run, and
produced a score comparable to nothing. The guard must catch exactly that, before spend.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import dataset_freshness as df  # noqa: E402


# --- The bug that cost money: the legacy 1.x pin must be REFUSED ---------------
def test_legacy_terminal_bench_core_pin_is_refused():
    """This is the exact pin we were benching. It must not be allowed to run."""
    with pytest.raises(df.StaleDatasetError) as e:
        df.check_dataset_fresh("terminal-bench", "terminal-bench-core==0.1.1")
    msg = str(e.value)
    assert "harbor" in msg  # tells you WHERE the benchmark actually lives now


@pytest.mark.parametrize("pin", ["terminal-bench-core==0.1.0", "terminal-bench-core==head"])
def test_every_legacy_core_pin_is_refused(pin):
    """Not just 0.1.1 — the whole 1.x task set is superseded, `head` included (and `head`
    is a moving branch pointer, so it isn't reproducible either)."""
    with pytest.raises(df.StaleDatasetError):
        df.check_dataset_fresh("terminal-bench", pin)


def test_superseded_generation_is_refused(monkeypatch):
    """The guard must catch the NEXT bump, not just the 1.x->2.x one it was born from.
    It didn't: it green-lit terminal-bench-2-1 while terminal-bench-3 already existed —
    reproducing, one generation later, the exact silent staleness it exists to prevent."""
    monkeypatch.setattr(df, "latest_terminal_bench_dataset", lambda: "terminal-bench-3")
    with pytest.raises(df.StaleDatasetError) as e:
        df.check_dataset_fresh("terminal-bench", "terminal-bench/terminal-bench-2-1")
    assert "terminal-bench-3" in str(e.value)  # names what to bench instead


def test_current_generation_passes(monkeypatch):
    """The newest generation must NOT be refused, or the guard blocks all work."""
    monkeypatch.setattr(df, "latest_terminal_bench_dataset", lambda: "terminal-bench-3")
    df.check_dataset_fresh("terminal-bench", "terminal-bench/terminal-bench-3")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("terminal-bench-3", (3,)),
        ("terminal-bench-2-1", (2, 1)),
        ("terminal-bench", ()),
        ("terminal-bench-core", None),
        ("something-else", None),
    ],
)
def test_generation_parsing(name, expected):
    assert df._parse_generation(name) == expected


def test_generation_ordering_is_numeric_not_lexicographic():
    """'terminal-bench-10' must beat 'terminal-bench-9' — a string compare would invert it."""
    assert df._parse_generation("terminal-bench-10") > df._parse_generation("terminal-bench-9")
    assert df._parse_generation("terminal-bench-3") > df._parse_generation("terminal-bench-2-1")


def test_evalplus_pypi_outage_is_unverified_not_current(monkeypatch, capsys):
    """latest_pypi returning None (PyPI down) used to fall through the guard and print
    'dataset pin is current ✓' — reporting a check it never performed. False confidence is
    worse than no check, because nobody re-checks a green tick."""
    monkeypatch.setattr(df, "latest_pypi", lambda pkg: None)
    df.check_dataset_fresh("evalplus")  # must not raise...
    err = capsys.readouterr().err
    assert "UNVERIFIED" in err  # ...and must NOT claim it is current
    assert "is current" not in err


def test_allow_stale_is_an_explicit_escape_hatch(capsys):
    """Reproducing an old score on purpose stays possible — but it must be a DECISION
    (an explicit flag), never a default, and it must say so loudly."""
    df.check_dataset_fresh("terminal-bench", "terminal-bench-core==0.1.1", allow_stale=True)
    err = capsys.readouterr().err
    assert "NOT be comparable" in err  # the warning is not silenceable


# --- Fail-soft on a registry outage (a bench must not be hostage to GitHub) -----
def test_registry_outage_warns_and_proceeds(monkeypatch, capsys):
    """A stale dataset is a correctness problem, not a security one — so an unreachable
    registry must WARN and proceed, not block every bench on GitHub's uptime."""

    def boom(*a, **k):
        raise httpx.ConnectError("registry unreachable")

    monkeypatch.setattr(df, "check_terminal_bench", boom)
    df.check_dataset_fresh("terminal-bench", "whatever")  # must NOT raise
    assert "UNVERIFIED" in capsys.readouterr().err


def test_unknown_system_is_a_programming_error():
    with pytest.raises(ValueError):
        df.check_dataset_fresh("not-a-benchmark")


# --- evalplus: a newer LIB means a newer DATASET (it pins versions in-library) --
def test_evalplus_stale_when_a_newer_release_exists(monkeypatch):
    """evalplus ships HumanEvalPlus/MbppPlus versions as library constants, so an
    out-of-date evalplus IS an out-of-date dataset."""
    monkeypatch.setattr(df, "latest_pypi", lambda pkg: "9.9.9")
    with pytest.raises(df.StaleDatasetError) as e:
        df.check_dataset_fresh("evalplus")
    assert "9.9.9" in str(e.value)


def test_evalplus_current_when_installed_is_newest(monkeypatch):
    import evalplus

    monkeypatch.setattr(df, "latest_pypi", lambda pkg: evalplus.__version__)
    df.check_dataset_fresh("evalplus")  # must not raise


def test_latest_tb_legacy_core_excludes_moving_head(monkeypatch):
    """'head' is a branch pointer, not a version — a score against it is unreproducible,
    so it must never be reported as the newest pinned version."""
    monkeypatch.setattr(
        df,
        "_get_json",
        lambda url: [
            {"name": "terminal-bench-core", "version": "head"},
            {"name": "terminal-bench-core", "version": "0.1.0"},
            {"name": "terminal-bench-core", "version": "0.1.1"},
            {"name": "swebench-verified", "version": "head"},
        ],
    )
    assert df.latest_tb_legacy_core() == "0.1.1"


# --- PASS-2 REVIEW: "I could not check" must NEVER print "current ✓" -----------
def test_unknown_latest_is_unverified_not_current(monkeypatch, capsys):
    """The false-confidence hole, in check_terminal_bench this time. If we cannot determine
    the current generation, an EMPTY problem list is returned to check_dataset_fresh, which
    prints 'dataset pin is current ✓' — reporting a check that never ran. (This is the same
    hole the evalplus path had; fixing one and not the other was the asymmetry.)"""
    monkeypatch.setattr(
        df,
        "latest_terminal_bench_dataset",
        lambda: (_ for _ in ()).throw(df.UnverifiedError("org unreachable")),
    )
    df.check_dataset_fresh("terminal-bench", "terminal-bench/terminal-bench-2-1")  # no raise
    err = capsys.readouterr().err
    assert "UNVERIFIED" in err
    assert "is current" not in err  # must NOT claim a pass it did not earn


def test_unparseable_pin_is_unverified_not_current(capsys):
    """A pin we cannot even parse cannot be declared current."""
    df.check_dataset_fresh("terminal-bench", "some-other-benchmark/v9")
    err = capsys.readouterr().err
    assert "UNVERIFIED" in err and "is current" not in err


def test_no_generation_repo_raises_unverified(monkeypatch):
    """An org listing with no terminal-bench-<n> repo means we don't know the latest."""
    monkeypatch.setattr(df.httpx, "get", lambda *a, **k: _FakeResp([{"name": "docs"}]))
    with pytest.raises(df.UnverifiedError):
        df.latest_terminal_bench_dataset()


class _FakeResp:
    def __init__(self, payload, link=""):
        self._p, self.headers = payload, {"link": link}

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


# --- PASS-2 REVIEW: latest_terminal_bench_dataset had ZERO direct coverage ------
def test_latest_generation_is_picked_numerically(monkeypatch):
    """A lexicographic pick would call 'terminal-bench-9' newer than 'terminal-bench-10'."""
    monkeypatch.setattr(
        df.httpx,
        "get",
        lambda *a, **k: _FakeResp(
            [
                {"name": "terminal-bench"},  # umbrella repo — not a generation
                {"name": "terminal-bench-2"},
                {"name": "terminal-bench-9"},
                {"name": "terminal-bench-10"},
                {"name": "terminal-bench-docs"},  # not a generation
            ]
        ),
    )
    assert df.latest_terminal_bench_dataset() == "terminal-bench-10"


def test_repo_list_is_paginated(monkeypatch):
    """GitHub caps a page at 100. If the newest generation sits on page 2, a single-page
    fetch returns a STALE 'latest' and the guard green-lights a superseded pin — the exact
    bug this module exists to prevent, just at a higher repo count."""
    pages = {
        "p1": _FakeResp([{"name": "terminal-bench-2"}], link='<https://x/p2>; rel="next"'),
        "https://x/p2": _FakeResp([{"name": "terminal-bench-3"}]),  # newest is on page 2
    }
    monkeypatch.setattr(df, "HARBOR_ORG_REPOS", "p1")
    monkeypatch.setattr(df.httpx, "get", lambda url, **k: pages[url])
    assert df.latest_terminal_bench_dataset() == "terminal-bench-3"
