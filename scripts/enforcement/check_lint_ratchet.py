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


def _ruff_paths() -> list[tuple[str, int]] | None:
    """Per-file diagnostic counts, repo-relative, descending — or None if ruff cannot be read.

    Called ONLY on the failure path, so the ordinary green run still costs exactly one ruff
    invocation. `_ruff_count` stays the single source of the NUMBER (and stays monkeypatchable);
    this is the same scan re-read for attribution, never a second opinion on the count.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            [sys.executable, "-m", "ruff", "check", ".", "--output-format=json", "--quiet"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        diags = json.loads((proc.stdout or "").strip() or "[]")
    except (OSError, ValueError):
        return None
    if not isinstance(diags, list):
        return None
    tracked = _tracked_files()
    tracked_abs = {str((ROOT / p).resolve()) for p in tracked} if tracked is not None else None
    counts: dict[str, int] = {}
    for d in diags:
        fn = d.get("filename") if isinstance(d, dict) else None
        if not fn:
            continue
        resolved = str(Path(fn).resolve())
        if tracked_abs is not None and resolved not in tracked_abs:
            continue
        try:
            rel = Path(resolved).relative_to(ROOT).as_posix()
        except ValueError:
            rel = fn
        counts[rel] = counts.get(rel, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def _caller_diff_paths() -> set[str]:
    """Paths this caller has touched — staged plus unstaged-tracked against HEAD.

    Three sessions share this tree, so "the count rose" is not the same claim as "YOU raised it".
    An empty set on any git failure is the honest answer: nothing is marked, nothing is blamed.
    """
    out: set[str] = set()
    for argv in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--cached", "--name-only"],
    ):
        try:
            proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
                argv, cwd=ROOT, capture_output=True, text=True, check=False
            )
        except OSError:
            continue
        if proc.returncode == 0:
            out |= {ln.strip() for ln in proc.stdout.splitlines() if ln.strip()}
    return out


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
    release widened a rule — permanent red no code change could clear).

    ⚠️ `sys.executable -m ruff`, the SAME binary `_ruff_count` runs — not a bare `ruff` off PATH
    (01M1RE497). They are routinely two different installs (here: `~/.local/bin/ruff` vs the venv's
    module), so a bare-`ruff` version described a ruleset that did not produce the count: upgrade the
    venv alone and the guard below compares the OLD version against a NEW count, reads no change, and
    charges the ruleset's delta to the caller as fresh debt. The version and the count must come from
    one process or the comparison is unfounded."""
    try:
        out = subprocess.run(  # noqa: S603 — fixed argv, no shell
            [sys.executable, "-m", "ruff", "--version"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except OSError:
        return None
    return out.split()[-1] if out else None


def _baseline_payload() -> dict | None:
    """The baseline as CI would see it: the COMMITTED blob, falling back to the working tree.

    01M22XDJ7/01M1RE497: the floor was read from the working-tree file, which is whatever the last
    process to run left there — including a sibling's uncommitted re-seed on a shared tree, and
    including this gate's OWN un-pushed tightening. CI checks out HEAD, so HEAD's blob is the floor
    that actually binds; reading anything else lets a local write move a fleet-wide bar.

    FALLBACK, stated rather than silent: no commit yet (a fresh repo), the path untracked (the first
    seed, which is never committed at the moment it is written), or git unavailable — then the
    working tree is all there is and it is used. The fallback can only ever be REACHED when HEAD
    carries no baseline at all, so it cannot be used to lower a committed floor.
    """
    rel = BASELINE.relative_to(ROOT).as_posix()
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "show", f"HEAD:{rel}"],  # noqa: S607 — git from PATH, standard tooling
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and (proc.stdout or "").strip():
            return json.loads(proc.stdout)
    except (OSError, ValueError):
        pass  # not committed / unparseable at HEAD → the working tree below
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_baseline_version() -> str | None:
    data = _baseline_payload()
    if not isinstance(data, dict):
        return None
    v = data.get("ruff_version")
    return str(v) if v else None


def _read_baseline() -> int | None:
    data = _baseline_payload()
    if not isinstance(data, dict):
        return None
    try:
        return max(int(data["ruff_errors"]), 0)
    except (ValueError, KeyError, TypeError):
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
    reseed = "--reseed" in sys.argv

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
        # A ruleset change is not debt — but it is not nothing either, and it must not be absorbed
        # SILENTLY. The old behaviour re-seeded at the current count and passed, which meant the
        # reference this check measures against could move on any run, in either direction, with no
        # act by anyone: real debt added in the same change as a ruff bump became the new floor
        # (01M1RE497 — the measured cobra path of this very ratchet, cited in CLAUDE.md § FIX
        # DIRECTIVE 5). So the re-seed still exists and is still one command — it is just no longer
        # something the gate does to you while reporting success.
        if reseed:
            if not check_only:
                _write_baseline(current)
                print(
                    f"lint-ratchet: RE-SEEDED at {current} under ruff {live_version} "
                    f"(was {baseline} under {stored_version}) — explicit, by --reseed."
                )
            else:
                # --check is read-only, so say what WOULD happen. A message claiming a write it did
                # not make is the same class of falsehood this whole row is about.
                print(
                    f"lint-ratchet: would RE-SEED at {current} under ruff {live_version} "
                    f"(was {baseline} under {stored_version}) — read-only, --check."
                )
            return 0
        print(
            f"ERROR: lint-ratchet — ruff changed {stored_version} → {live_version}, so the stored "
            f"count ({baseline}) was measured under a DIFFERENT ruleset and {current} is not "
            "comparable to it. This is not a regression and it is not a pass: re-seed explicitly "
            "with `python3 scripts/enforcement/check_lint_ratchet.py --reseed` (which records "
            f"{current} under {live_version}), in a commit that says the linter moved. Re-seeding "
            "silently is how a floor drifts — a rise landing in the same change as the bump would "
            "be absorbed into the new baseline and never seen."
        )
        return 1

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
        paths = _ruff_paths()
        if paths:
            mine = _caller_diff_paths()
            shown = paths[:10]
            for rel, n in shown:
                mark = "  ← in YOUR diff" if rel in mine else ""
                print(f"    {n:>4}  {rel}{mark}")
            if len(paths) > len(shown):
                print(
                    f"    … {len(paths) - len(shown)} more file(s) with diagnostics, of {len(paths)}"
                )
            if mine and not any(rel in mine for rel, _ in paths):
                print(
                    "    NOTE: none of the offending files is in your diff — on this shared tree "
                    "that usually means a sibling's committed work, or a ruff config change. Check "
                    "`git log -1 --stat` on the offenders before you start fixing."
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
