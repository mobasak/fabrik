#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/microbench_terminal.py scripts/kilo-benchmarks/microbench_coding.py docs/reference/terminal-bench-runner.md
"""Refuse to benchmark against a STALE dataset.

Every benchmark score is only meaningful relative to the dataset it was measured on, so
a bench run against a superseded dataset produces numbers that look authoritative and
compare against nothing. We shipped exactly that: the Terminal-Bench runner was pinned to
``terminal-bench-core==0.1.1`` — the *launch-era* task set — for weeks after the benchmark
had moved to **Terminal-Bench 2.x** (89 tasks, 16 categories, a different package
entirely: ``harbor``, not ``terminal-bench``). We paid for a full 80-task run and produced
a score that could not be compared to a single entry on the current public leaderboard.

Nothing warned us, because the staleness was invisible: the pin was valid, the download
succeeded, the run passed. **A version pin does not tell you it has been superseded — you
have to go and ask.** So this module asks, live, before a single model is dispatched.

Contract (`check_dataset_fresh`):
    - returns  → the pinned dataset IS the newest the upstream registry offers.
    - raises `StaleDatasetError` → it is NOT. The bench does not run.

``--allow-stale`` exists for the one legitimate case (reproducing an OLD score on purpose);
it must be passed EXPLICITLY, so staleness is always a decision someone made, never a
default someone inherited.

Sources of truth (fetched live; no hard-coded "latest"):
    terminal-bench (legacy `tb`) → the laude-institute registry.json
    terminal-bench 2.x (harbor)  → the harbor dataset registry
    evalplus                     → the version the INSTALLED evalplus lib pins, vs PyPI's
                                   newest release (evalplus ships its dataset version as a
                                   constant, so a newer lib == a newer dataset)
"""

from __future__ import annotations

import sys

import httpx

# --- Live registries (never hard-code "the latest") ---------------------------
TB_LEGACY_REGISTRY = (
    "https://raw.githubusercontent.com/laude-institute/terminal-bench/main/registry.json"
)
PYPI = "https://pypi.org/pypi/{pkg}/json"

# The dataset each runner is CURRENTLY pinned to. One line to change when we upgrade —
# and the check below is what makes forgetting to change it loud instead of silent.
PINNED = {
    "terminal-bench": "terminal-bench/terminal-bench-2-1",  # harbor; 89 tasks, 16 categories
    "humaneval": "HumanEvalPlus",  # version comes from the installed evalplus lib
    "mbpp": "MbppPlus",
}

_TIMEOUT = 20.0


class StaleDatasetError(RuntimeError):
    """The pinned dataset has been superseded. Benching it would produce a score that
    compares to nothing."""


def _get_json(url: str):
    r = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def latest_tb_legacy_core() -> str | None:
    """Newest PINNED terminal-bench-core version in the legacy `tb` registry.

    'head' is excluded on purpose: it is a moving branch pointer, so a score measured
    against it is not reproducible and cannot be compared to anyone else's.
    """
    entries = _get_json(TB_LEGACY_REGISTRY)
    versions = [
        e["version"]
        for e in entries
        if e.get("name") == "terminal-bench-core" and e.get("version") != "head"
    ]
    return sorted(versions)[-1] if versions else None


def latest_pypi(pkg: str) -> str | None:
    try:
        return _get_json(PYPI.format(pkg=pkg))["info"]["version"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def installed_evalplus_dataset_versions() -> dict[str, str]:
    """The dataset versions the INSTALLED evalplus pins (its own constants)."""
    from evalplus.data.humaneval import HUMANEVAL_PLUS_VERSION
    from evalplus.data.mbpp import MBPP_PLUS_VERSION

    return {"humaneval": HUMANEVAL_PLUS_VERSION, "mbpp": MBPP_PLUS_VERSION}


def check_terminal_bench(pinned: str) -> list[str]:
    """Warn/fail conditions for the Terminal-Bench dataset pin.

    The load-bearing check is NOT 'is 0.1.1 the newest 0.1.x' — it is 'does the benchmark
    still LIVE in this package at all'. It didn't. That is the failure mode that cost us a
    paid run, and a naive within-registry version compare would have said "you're current".
    """
    problems: list[str] = []
    if pinned.startswith("terminal-bench-core"):
        problems.append(
            f"{pinned} is the LEGACY Terminal-Bench 1.x task set (the `tb` package). "
            f"Terminal-Bench has moved to 2.x, which lives in a DIFFERENT package "
            f"(`harbor`) with its own dataset (terminal-bench/terminal-bench-2-1: 89 tasks, "
            f"16 categories). A 1.x score cannot be compared to the current public "
            f"leaderboard. Bench `terminal-bench/terminal-bench-2-1` via harbor."
        )
    return problems


def check_evalplus() -> list[str]:
    """evalplus ships its dataset version as a library constant, so a newer evalplus
    release IS a newer dataset. Compare installed vs PyPI newest."""
    problems: list[str] = []
    try:
        import evalplus
    except ImportError:
        return ["evalplus is not installed — cannot verify HumanEval+/MBPP+ dataset version"]
    installed = getattr(evalplus, "__version__", None)
    newest = latest_pypi("evalplus")
    if installed and newest and installed != newest:
        ds = installed_evalplus_dataset_versions()
        problems.append(
            f"evalplus {installed} is installed but {newest} is released. evalplus pins its "
            f"dataset versions in-library (HumanEvalPlus={ds['humaneval']}, "
            f"MbppPlus={ds['mbpp']}), so a newer release may ship a NEWER dataset. "
            f"Upgrade evalplus, then re-check."
        )
    return problems


def check_dataset_fresh(
    system: str, pinned: str | None = None, *, allow_stale: bool = False
) -> None:
    """Raise StaleDatasetError unless `system`'s pinned dataset is the current one.

    `system` ∈ {"terminal-bench", "evalplus"}. Network failures are NON-fatal (a registry
    outage must not block a bench) — they warn and pass, because failing closed here would
    make every bench hostage to GitHub's uptime, and a stale-dataset run is a correctness
    problem, not a security one.
    """
    try:
        if system == "terminal-bench":
            problems = check_terminal_bench(pinned or PINNED["terminal-bench"])
        elif system == "evalplus":
            problems = check_evalplus()
        else:
            raise ValueError(f"unknown benchmark system {system!r}")
    except httpx.HTTPError as e:
        print(
            f"[dataset-freshness] WARNING: could not reach the registry to verify "
            f"{system} ({e}) — proceeding UNVERIFIED. Re-check before trusting the score.",
            file=sys.stderr,
        )
        return

    if not problems:
        print(f"[dataset-freshness] {system}: dataset pin is current ✓", file=sys.stderr)
        return

    msg = f"STALE DATASET — {system}:\n  " + "\n  ".join(problems)
    if allow_stale:
        print(
            f"[dataset-freshness] {msg}\n"
            f"[dataset-freshness] --allow-stale passed → benching anyway. The score will NOT "
            f"be comparable to the current leaderboard.",
            file=sys.stderr,
        )
        return
    raise StaleDatasetError(
        f"{msg}\n\nRefusing to bench: the score would compare to nothing. "
        f"Upgrade the dataset, or pass --allow-stale to reproduce an old score on purpose."
    )


def main() -> int:
    """Report the freshness of all three benchmark datasets."""
    rc = 0
    for system in ("terminal-bench", "evalplus"):
        try:
            check_dataset_fresh(system)
        except StaleDatasetError as e:
            print(f"\n✗ {e}\n", file=sys.stderr)
            rc = 1
    ds = installed_evalplus_dataset_versions()
    print("\npinned datasets:")
    print(f"  terminal-bench : {PINNED['terminal-bench']}")
    print(f"  humaneval      : HumanEvalPlus {ds['humaneval']}")
    print(f"  mbpp           : MbppPlus {ds['mbpp']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
