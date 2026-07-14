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
    terminal-bench (harbor)      → the harbor-framework GitHub org's repo list (each
                                   dataset generation is its own repo; there is no
                                   queryable registry API — verified live)
    evalplus                     → the version the INSTALLED evalplus lib pins, vs PyPI's
                                   newest release (evalplus ships its dataset version as a
                                   constant, so a newer lib == a newer dataset)
"""

from __future__ import annotations

import re
import sys

import httpx

# --- Live registries (never hard-code "the latest") ---------------------------
TB_LEGACY_REGISTRY = (
    "https://raw.githubusercontent.com/laude-institute/terminal-bench/main/registry.json"
)
PYPI = "https://pypi.org/pypi/{pkg}/json"
# No queryable harbor dataset registry exists (hub.harborframework.com/api/* 404s — checked
# live 2026-07-14), so the org's repo list IS the source of truth for "what generation is
# current": each ships as its own repo (terminal-bench-2, terminal-bench-2-1, terminal-bench-3).
HARBOR_ORG_REPOS = "https://api.github.com/orgs/harbor-framework/repos?per_page=100"

# The dataset each runner is CURRENTLY pinned to. One line to change when we upgrade —
# and the check below is what makes forgetting to change it loud instead of silent.
PINNED = {
    # harbor. Bumped 2-1 -> 3 by the review: the org already published terminal-bench-3,
    # and the guard's own generation check (check_terminal_bench) now refuses 2-1.
    "terminal-bench": "terminal-bench/terminal-bench-3",
    "humaneval": "HumanEvalPlus",  # version comes from the installed evalplus lib
    "mbpp": "MbppPlus",
}

_TIMEOUT = 20.0


class StaleDatasetError(RuntimeError):
    """The pinned dataset has been superseded. Benching it would produce a score that
    compares to nothing."""


class UnverifiedError(RuntimeError):
    """We could not determine what the current dataset IS, so the pin is UNVERIFIED.

    This is NOT the same as "current", and conflating the two is the bug this class exists
    to make impossible: a check that cannot run must say so, because a green tick is the one
    thing nobody ever re-checks. Both fallible checks raise this rather than returning an
    empty problem list — an empty list means "verified, and it's fine".

    (It is also NOT an `httpx.HTTPError`: raising a transport exception for a logic
    condition would mask a genuine network fault as a merely-unverified one.)
    """


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
    """Newest released version of `pkg`, or None if PyPI could not be consulted.

    ⚠️ None means **UNVERIFIED**, not "current". Callers must not treat it as a pass — see
    `check_evalplus`, where swallowing it silently printed "dataset pin is current ✓" for a
    check that never actually ran.
    """
    try:
        return _get_json(PYPI.format(pkg=pkg))["info"]["version"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def installed_evalplus_dataset_versions() -> dict[str, str]:
    """The dataset versions the INSTALLED evalplus pins (its own constants)."""
    from evalplus.data.humaneval import HUMANEVAL_PLUS_VERSION
    from evalplus.data.mbpp import MBPP_PLUS_VERSION

    return {"humaneval": HUMANEVAL_PLUS_VERSION, "mbpp": MBPP_PLUS_VERSION}


def _parse_generation(name: str) -> tuple[int, ...] | None:
    """'terminal-bench-2-1' -> (2, 1); 'terminal-bench-3' -> (3,); 'terminal-bench' -> ()."""
    m = re.fullmatch(r"terminal-bench(?:-(\d+(?:-\d+)*))?", name)
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split("-")) if m.group(1) else ()


def latest_terminal_bench_dataset() -> str:
    """The newest Terminal-Bench dataset generation, from the harbor-framework GitHub org.

    There is no queryable harbor dataset registry (`hub.harborframework.com/api/...` 404s —
    checked live), so the org's own repo list IS the source of truth: each generation ships
    as its own repo (`terminal-bench-2`, `terminal-bench-2-1`, `terminal-bench-3`, …).

    **Paginated.** A single `per_page=100` page silently truncates once the org passes 100
    repos, and the newest generation could sit on page 2 — which would make this function
    return a stale "latest" and the guard green-light a superseded pin. That is the exact
    bug class this module exists to prevent, so it follows GitHub's `Link: rel="next"`
    rather than assuming one page is enough.

    Raises `UnverifiedError` if no generation repo can be found — "I don't know what the
    latest is" must never be reported to the caller as "your pin is fine".
    """
    gens: list[tuple[tuple[int, ...], str]] = []
    url: str | None = HARBOR_ORG_REPOS
    while url:
        r = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        for repo in r.json():
            g = _parse_generation(repo.get("name", ""))
            if g:  # non-empty: a real generation, not the bare 'terminal-bench' umbrella repo
                gens.append((g, repo["name"]))
        m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("link", ""))
        url = m.group(1) if m else None

    if not gens:
        raise UnverifiedError(
            "no terminal-bench-<n> repo found in the harbor-framework org — cannot "
            "determine the current dataset generation"
        )
    return max(gens)[1]


def check_terminal_bench(pinned: str) -> list[str]:
    """Fail conditions for the Terminal-Bench dataset pin.

    TWO checks, because the first one alone is what let this module go stale about itself:

    1. **Wrong package** — a `terminal-bench-core==*` pin is the LEGACY 1.x task set, which
       lives in the retired `tb` package. This is the failure that cost us a paid 80-task run.
    2. **Superseded generation** — compare the pinned generation against the newest one the
       harbor-framework org actually publishes, LIVE. The original version of this function
       only did check 1, so it happily green-lit `terminal-bench-2-1` while
       **`terminal-bench-3` already existed and had superseded it** — reproducing, one
       generation later, the exact silent staleness the module was written to prevent. A
       guard that only knows about yesterday's bump is not a guard.
    """
    problems: list[str] = []
    if pinned.startswith("terminal-bench-core"):
        problems.append(
            f"{pinned} is the LEGACY Terminal-Bench 1.x task set (the `tb` package). "
            f"Terminal-Bench has moved on, and lives in a DIFFERENT package (`harbor`) with "
            f"its own datasets. A 1.x score cannot be compared to the current public "
            f"leaderboard. Bench the current dataset via harbor."
        )
        return problems

    name = pinned.split("/")[-1]  # 'terminal-bench/terminal-bench-2-1' -> 'terminal-bench-2-1'
    pinned_gen = _parse_generation(name)
    if pinned_gen is None:
        # We cannot even parse the pin, so we cannot say it is current. Saying nothing here
        # would return an EMPTY problem list, which the caller prints as "current ✓" — the
        # same false-confidence hole that check_evalplus had.
        raise UnverifiedError(f"unrecognized Terminal-Bench dataset pin {pinned!r}")
    latest = latest_terminal_bench_dataset()  # raises UnverifiedError if it cannot tell
    latest_gen = _parse_generation(latest)
    if latest_gen and pinned_gen < latest_gen:
        problems.append(
            f"{pinned} is SUPERSEDED: harbor-framework now publishes `{latest}` "
            f"(https://github.com/harbor-framework/{latest}). A score measured on an older "
            f"generation cannot be compared to the current leaderboard. Bench "
            f"`terminal-bench/{latest}` via harbor, or pass --allow-stale to reproduce an "
            f"old score on purpose."
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
    if not newest:
        # PyPI unreachable. This MUST surface as UNVERIFIED, never as a pass: the old code
        # let `newest is None` fall through the `if installed and newest and ...` guard and
        # then printed "dataset pin is current ✓" — reporting a check it had not performed.
        # False confidence is worse than no check, because nobody re-checks a green tick.
        raise UnverifiedError("PyPI unreachable — evalplus dataset version NOT verified")
    if installed and installed != newest:
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
    except (httpx.HTTPError, UnverifiedError) as e:
        print(
            f"[dataset-freshness] WARNING: could not verify "
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
