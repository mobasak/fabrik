#!/usr/bin/env python3
# AFTER-EDIT: scripts/final_gate.py, docs/TROUBLESHOOTING.md
"""Repo-wide lint RATCHET — the count of ruff errors may only ever go DOWN.

WHY THIS EXISTS. `final_gate` lints only the files the current diff TOUCHED (`final_gate.py`'s ruff
step). That is correct for the auto-fixer — it must not red the gate on a pre-existing or Fabrik-synced
line the change never touched — but it means **repo-wide lint debt is invisible to the gate**. A project
accumulates thousands of errors, every local gate run stays green, and then its CI (`ruff check .`, whole
repo) goes red. Fleet snapshot on landing: ~5,000 ruff errors across ~30 repos, none of them visible to a
per-diff gate.

THE MECHANISM — a ratchet, not a flag-day. Fixing 5,000 errors before enforcing anything is impossible;
blocking every project with debt on day one is a fleet outage. So instead:

  • First run in a repo SEEDS a baseline at the current count and PASSES (nothing is blocked).
  • A later run that RAISES the count FAILS — an agent can never *add* a new lint error again.
  • A run that LOWERS the count tightens the baseline to the new floor (it can only shrink).
  • When the baseline reaches 0 it stays there — zero-tolerance, locked, permanently.

So zero-tolerance arrives per repo, AS EACH IS CLEANED, with no coordinated cutover and no cross-repo
editing. The baseline lives in the project (`.fabrik/lint-baseline.json`, tracked) so it travels with the
repo — CI, a teammate, and every agent see the same floor.

CI-PARITY. We run `ruff check .` exactly as a project's `ci.yml` does. Ruff respects `.gitignore` by
default, so the Fabrik-synced / vendored dirs (which are gitignored in a project and therefore absent from
CI's clean checkout) are excluded automatically — the count reflects the project's OWN code, which is what
CI grades. Diagnostics in UNTRACKED files are excluded for the same reason: CI's clean checkout contains
only tracked files, so an untracked file (e.g. a sibling agent's in-progress scratch on a shared tree) can
never raise CI's count — counting it locally breaks parity and blames the wrong session (live incident
2026-07-18: a sibling's untracked WIP raised the local count 119→121 while CI would still see 119).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# scripts/enforcement/<this>.py → parents[2] is the project root.
ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / ".fabrik" / "lint-baseline.json"


def _ruff_count() -> int | None:
    """Repo-wide ruff error count, or None if ruff cannot be run (→ the check skips, non-blocking).

    Uses the same interpreter the gate invoked us with (`final_gate` runs the project's venv python), so
    this is the project's OWN ruff + config. `--output-format=json` gives one object per diagnostic.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            [sys.executable, "-m", "ruff", "check", ".", "--output-format=json", "--quiet"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    out = (proc.stdout or "").strip()
    if not out:
        # Empty stdout + rc 0 = genuinely clean; rc≠0 with no JSON = ruff missing / a usage error we
        # cannot interpret as a count. Distinguish: a clean repo really is 0.
        return 0 if proc.returncode == 0 else None
    try:
        diags = json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(diags, list):  # a future ruff JSON shape change must not crash the gate
        return None
    tracked = _tracked_files()
    if tracked is None:  # git unavailable → fall back to the raw working-tree count
        return len(diags)
    # CI-parity: count only diagnostics in TRACKED files — CI's clean checkout has no untracked file,
    # so an untracked file (a sibling agent's WIP on a shared tree) can never raise CI's count.
    # Compare RESOLVED-absolute to RESOLVED-absolute so a symlinked repo root / symlinked path
    # can't silently drop a tracked diagnostic (undercount → spurious RISE on a later run).
    tracked_abs = {str((ROOT / p).resolve()) for p in tracked}
    n = 0
    for d in diags:
        fn = d.get("filename")
        if not fn:
            n += 1  # unattributable diagnostic — count it (fail-closed)
            continue
        if str(Path(fn).resolve()) in tracked_abs:
            n += 1
    return n


def _tracked_files() -> set[str] | None:
    """Set of git-tracked paths (repo-relative, POSIX), or None if git can't answer."""
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "ls-files", "-z"],  # noqa: S607 — git resolved from PATH, standard tooling
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return {p for p in proc.stdout.split("\0") if p}


def _baseline_is_gitignored() -> bool:
    """Is the baseline path excluded from the repo? Then it won't travel to CI or a fresh clone.

    ⚠️ CI-PARITY DEPENDS ON THIS. The ratchet enforces in CI only if CI's clean checkout HAS the
    baseline — i.e. it is committed. A project that wholesale-ignores `.fabrik/` (wpf does) can't commit
    it, so the ratchet degrades to LOCAL-working-tree enforcement only (still valuable — the acting agent
    cannot add debt and pass their own gate — but CI stops backstopping). We surface that loudly rather
    than let it fail open silently.
    """
    try:
        return (
            subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["git", "check-ignore", "-q", str(BASELINE.relative_to(ROOT))],
                cwd=ROOT,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except OSError:  # git missing → can't tell; don't crash the whole ratchet over a warning
        return False


def _ruff_version() -> str | None:
    """The linter's version — an ABSOLUTE stored count is only comparable under the same ruleset
    (youtube 01M1H0D5: 390 vs a stored 388 on the baseline's OWN seeding commit after a ruff
    release widened a rule — permanent red no code change could clear)."""
    try:
        out = subprocess.run(
            ["ruff", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip()
    except OSError:
        return None
    return out.split()[-1] if out else None


def _read_baseline_version() -> str | None:
    try:
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        v = data.get("ruff_version")
        return str(v) if v else None
    except (OSError, ValueError, AttributeError):
        return None


def _read_baseline() -> int | None:
    try:
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        val = int(data["ruff_errors"])
        return max(val, 0)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_baseline(count: int) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"ruff_errors": count}
    version = _ruff_version()
    if version:
        payload["ruff_version"] = version
    BASELINE.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    # Stage it so the tightened floor rides along with the change that lowered it. Best-effort: if git is
    # unavailable the write still stands and `final_gate`'s own auto-stage covers it.
    try:
        subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "add", "--", str(BASELINE.relative_to(ROOT))],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
    except OSError:  # git missing — the baseline file write above still stands
        pass


def main() -> int:
    check_only = "--check" in sys.argv

    current = _ruff_count()
    if current is None:
        print("⚠ lint-ratchet — ruff unavailable / unparseable; skipped (CI still runs ruff).")
        return 0

    if _baseline_is_gitignored():
        print(
            "⚠ lint-ratchet — `.fabrik/lint-baseline.json` is gitignored in this repo, so it cannot "
            "be committed: the ratchet enforces LOCALLY but not in CI (a fresh checkout has no baseline). "
            "Un-ignore it (drop the `.fabrik/` ignore, or `git add -f` won't help while the dir is "
            "excluded) to restore CI-parity."
        )

    baseline = _read_baseline()
    stored_version, live_version = _read_baseline_version(), _ruff_version()
    if baseline is not None and stored_version and live_version and stored_version != live_version:
        # A ruleset change is not debt: re-seed LOUDLY at the new count and pass. The next run
        # ratchets from here under the new version. Asymmetric drift (a REMOVED rule silently
        # lowering the floor) is covered too — the floor is re-taken at the measured count.
        print(
            f"⚠ lint-ratchet — ruff changed {stored_version} → {live_version}; the stored count "
            f"({baseline}) was measured under the OLD ruleset. RE-SEEDING the baseline at the "
            f"current count ({current}) and passing — not a regression, a new floor."
        )
        if not check_only:
            _write_baseline(current)
        return 0

    if baseline is None:
        # SEED. First run in this repo — record the floor and pass. Nothing is ever blocked on the run
        # that establishes the baseline.
        if not check_only:
            _write_baseline(current)
            print(f"lint-ratchet: baseline SEEDED at {current} (.fabrik/lint-baseline.json).")
        else:
            print(f"lint-ratchet: no baseline yet — would seed at {current} (read-only, --check).")
        return 0

    if current > baseline:
        print(
            f"ERROR: lint-ratchet — ruff errors ROSE {baseline} → {current} (+{current - baseline}). "
            "New lint debt is not allowed: the repo-wide count may only go DOWN. Run `ruff check . --fix`, "
            f"then fix the remainder until you are at or below {baseline}. (This is CI-parity — your "
            "`ci.yml` runs the same `ruff check .`.)"
        )
        return 1

    if current < baseline:
        if not check_only:
            _write_baseline(current)
            print(f"lint-ratchet: ratcheted DOWN {baseline} → {current}. New floor committed.")
        else:
            print(
                f"lint-ratchet: OK — {current} ≤ baseline {baseline} (would tighten to {current})."
            )
        return 0

    lock = " — zero-tolerance LOCKED" if baseline == 0 else ""
    print(f"lint-ratchet: OK — {current} == baseline{lock}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
