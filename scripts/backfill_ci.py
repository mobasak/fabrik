#!/usr/bin/env python3
# AFTER-EDIT: none
"""Backfill the fabrik-managed local CI (`scripts/ci_local.sh` + `.fabrik/run-pytest`, what
`ci_files()` emits) onto an existing project that predates it, SAFELY — the replica is a lint
ratchet (src/fabrik/ci_scaffold.py), so this also seeds `.fabrik/lint-baseline.json` at the
project's CURRENT ruff count. Result: the replica lands GREEN (debt tolerated, growth blocked)
instead of flooding red on legacy lint debt.

A project with anything at `scripts/ci_local.sh` is skipped, never rewritten; its row says when
that file is stale (no sqlfluff step, no `.fabrik/run-pytest`) or not fabrik-managed. The replica
also lints every tracked `*.sql` with sqlfluff, with no ratchet, so each target's SQL is graded
first by the pinned sqlfluff when this interpreter carries it (else the verdict is `unknown`):
`--apply` refuses a `red` or `unknown` verdict unless `--force`, and a forced row records the
verdict it went past. An existing `.fabrik/run-pytest` or lint baseline is kept (a live symlink
there included); a symlinked parent directory of a file it writes, or a dangling symlink at one,
fails that project before anything is written, and a dry run says so; each file goes in through
a fresh temp file and a rename, `scripts/ci_local.sh` last; and the
exit is 1 when `--apply` refused, failed or could not find any project.

Per-project config is grounded, not guessed:
  needs_database  ← the hub spec's shape.needs_database if a spec exists, else an uncommented
                    DATABASE_URL in the project's .env.example.
  needs_web       ← a Next.js/web frontend (package.json present AND a saas-skeleton/web type).
  db_extensions   ← ('pgvector',) when the spec/.env references pgvector.

Usage:
  python scripts/backfill_ci.py <project> [<project> ...]   # DRY-RUN (default): report only
  python scripts/backfill_ci.py <project> --apply           # write the CI files + seed baseline
                                                            #   (working tree only; NO git)
  python scripts/backfill_ci.py <project> --apply --force   # ... past a red/unknown sqlfluff
Commit is deliberately left to the caller (per-repo agent, or an explicit review) — this tool
never commits or pushes across repos.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fabrik.ci_scaffold import (  # noqa: E402
    RUFF_VERSION,
    SQLFLUFF_STEP,
    SQLFLUFF_VERSION,
    CiConfig,
    ci_files,
)


def _assert_ruff_matches_pin() -> None:
    """The baseline we seed must be counted by the SAME ruff CI pins, or the ratchet reds.

    The generated CI installs ``ruff==RUFF_VERSION``; we seed the baseline with THIS interpreter's
    ruff. If they differ, the counts differ and CI trips on the seeded floor. Fail loudly.
    """
    r = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"], capture_output=True, text=True, check=False
    )
    got = (r.stdout or "").strip().split()[-1] if r.stdout else "?"
    if got != RUFF_VERSION:
        sys.exit(
            f"ABORT: this interpreter's ruff is {got} but the generated CI pins ruff=={RUFF_VERSION}. "
            f"Seeding a baseline with a mismatched ruff would red CI. Install ruff=={RUFF_VERSION} in the "
            "hub venv (or bump RUFF_VERSION in src/fabrik/ci_scaffold.py to match) before backfilling."
        )


OPT = Path("/opt")
HUB_SPECS = Path(__file__).resolve().parents[1] / "specs" / "services"
WEB_TYPES = {"saas-skeleton", "saas"}
# The interpreter whose sqlfluff grades a target's SQL; a version other than SQLFLUFF_VERSION reads
# `unknown`, never `clean`. 180 s is final_gate.py's sqlfluff timeout; a hang reads `unknown`.
SQLFLUFF_PYTHON = sys.executable
SQLFLUFF_TIMEOUT_S = 180
RUN_PYTEST = ".fabrik/run-pytest"
BASELINE = ".fabrik/lint-baseline.json"
CI_LOCAL = "scripts/ci_local.sh"


def _tracked_sql(proj: Path) -> list[str] | None:
    """The replica's own population: `git ls-files -- '*.sql'` from the project root; None when
    git cannot list it (not a repo)."""
    r = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.sql"], cwd=proj, capture_output=True, check=False
    )
    if r.returncode != 0:
        return None
    return [p for p in r.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


def _sqlfluff_verdict(proj: Path, files: list[str] | None) -> str:
    """`-` · `clean` · `red N` · `unknown (<why>)`, from the pinned sqlfluff run the way the
    replica runs it: postgres dialect, relative paths, cwd = the project. N counts the violations
    that fail the run — a rule the project configures as a warning (`"warning": true` in the JSON)
    is printed by the replica but does not red it."""
    if files is None:
        return "unknown (no git)"
    if not files:
        return "-"
    text = {"text": True, "encoding": "utf-8", "errors": "replace"}
    try:
        v = subprocess.run(
            [SQLFLUFF_PYTHON, "-m", "sqlfluff", "--version"],
            capture_output=True,
            check=False,
            timeout=60,
            **text,
        )
    except subprocess.TimeoutExpired:
        return "unknown (timeout)"
    except OSError:
        return "unknown (no sqlfluff)"
    words = (v.stdout or "").split()
    if v.returncode != 0 or not words:
        return "unknown (no sqlfluff)"
    if words[-1] != SQLFLUFF_VERSION:
        return f"unknown (sqlfluff {words[-1]} != {SQLFLUFF_VERSION})"
    try:
        r = subprocess.run(
            [SQLFLUFF_PYTHON, "-m", "sqlfluff", "lint", "--dialect", "postgres", "--format", "json"]
            + files,
            cwd=proj,
            capture_output=True,
            check=False,
            timeout=SQLFLUFF_TIMEOUT_S,
            **text,
        )
    except subprocess.TimeoutExpired:
        return "unknown (timeout)"
    except OSError as e:  # E2BIG on a file list too long for one exec, among others
        return f"unknown (lint not run: {e.strerror or type(e).__name__})"
    if r.returncode == 0:
        return "clean"
    if r.returncode != 1:
        return f"unknown (lint failed, rc {r.returncode})"
    try:
        n = sum(
            1
            for f in json.loads(r.stdout)
            for v in (f.get("violations") or [])
            if not v.get("warning")
        )
    except (ValueError, TypeError, AttributeError):
        return "unknown (unreadable lint output)"
    return f"red {n}"


def _ci_local_state(proj: Path) -> str | None:
    """None when nothing at all is at `scripts/ci_local.sh` (a backfill target); otherwise the
    skip's ACTION text. A symlink (dangling or not), a directory or any other non-regular entry
    is skipped as not fabrik-managed, so the write never follows it."""
    path = proj / CI_LOCAL
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_file():
        return "already has CI (not fabrik-managed)"
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) < 2 or "# fabrik-managed" not in lines[1]:
        return "already has CI (not fabrik-managed)"
    stale = []
    if SQLFLUFF_STEP not in text:
        stale.append("no sqlfluff step")
    if not (proj / RUN_PYTEST).exists():
        stale.append(f"no {RUN_PYTEST}")
    return "already has CI" + (f" (stale: {', '.join(stale)})" if stale else "")


def _read_yaml(p: Path) -> dict:
    import yaml

    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return {}


def _spec_shape(name: str) -> dict | None:
    for cand in (HUB_SPECS / f"{name}.yaml", HUB_SPECS / f"{name}.yaml.draft"):
        if cand.exists():
            return _read_yaml(cand).get("shape") or {}
    return None


def _env_has_database(proj: Path) -> bool:
    ex = proj / ".env.example"
    if not ex.exists():
        return False
    for ln in ex.read_text(errors="ignore").splitlines():
        s = ln.strip()
        if s.startswith("#"):
            continue
        if s.startswith("DATABASE_URL=") and s.split("=", 1)[1].strip():
            return True
    return False


def _wants_pgvector(name: str, proj: Path) -> bool:
    blob = ""
    for f in (proj / ".env.example", proj / "requirements.txt", proj / "pyproject.toml"):
        if f.exists():
            blob += f.read_text(errors="ignore").lower()
    return "pgvector" in blob or "vector" in (
        (_spec_shape(name) or {}).get("search_backend", "") or ""
    )


def _ruff_count(proj: Path) -> int | None:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "ruff", "check", ".", "--output-format=json", "--quiet"],
            cwd=proj,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    out = (r.stdout or "").strip()
    if not out:
        return 0 if r.returncode == 0 else None
    try:
        return len(json.loads(out))
    except json.JSONDecodeError:
        return None


def plan(name: str) -> dict:
    proj = OPT / name
    if not (proj / "project.yaml").exists() and not proj.exists():
        return {"name": name, "error": "not found"}
    ptype = _read_yaml(proj / "project.yaml").get("type") or "unknown"
    shape = _spec_shape(name)
    needs_db = (
        bool(shape["needs_database"])
        if shape and "needs_database" in shape
        else _env_has_database(proj)
    )
    needs_web = (proj / "package.json").exists() and ptype in WEB_TYPES
    exts = ("pgvector",) if (needs_db and _wants_pgvector(name, proj)) else ()
    ruff = _ruff_count(proj)
    ci_state = _ci_local_state(proj)
    sql = _tracked_sql(proj)
    return {
        "name": name,
        "type": ptype,
        "needs_db": needs_db,
        "needs_web": needs_web,
        "exts": exts,
        "ruff": ruff,
        "has_ci": ci_state is not None,
        "ci_state": ci_state,
        "sql": "?" if sql is None else str(len(sql)),
        # A skipped project is never linted: nothing is written there, so its verdict decides nothing.
        "sqlfluff": "n/a" if ci_state is not None else _sqlfluff_verdict(proj, sql),
        "baseline_exists": os.path.lexists(proj / BASELINE),
        "blocker": None if ci_state is not None else _write_blocker(proj),
    }


def _refused(p: dict) -> bool:
    return p["sqlfluff"].startswith(("red", "unknown"))


def apply(name: str, p: dict) -> list[str]:
    proj = OPT / name
    cfg = CiConfig(needs_database=p["needs_db"], needs_web=p["needs_web"], db_extensions=p["exts"])
    files = dict(ci_files(cfg))
    # Seed the ratchet baseline at the current count so the replica lands GREEN.
    if p["ruff"] is not None:
        files[BASELINE] = json.dumps({"ruff_errors": p["ruff"]}) + "\n"
    blocker = _write_blocker(proj)
    if blocker:
        raise OSError(f"symlink at {blocker}")
    # scripts/ci_local.sh goes LAST: its presence is what marks the project done, so a write that
    # fails part-way leaves no ci_local.sh and the next run retries the whole backfill.
    order = sorted(files, key=lambda rel: rel == CI_LOCAL)
    written = []
    for rel in order:
        dest = proj / rel
        if os.path.lexists(dest):
            continue  # an existing marker or baseline is the project's own
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Written to a sibling temp file, made executable, then renamed into place: a failed
        # write or chmod never leaves a half-made file at the real path.
        tmp = dest.with_name(f".{dest.name}.backfill-tmp")
        if os.path.lexists(tmp):
            tmp.unlink()  # a leftover (a symlink included: unlink removes the link, never its target)
        try:
            tmp.write_text(files[rel], encoding="utf-8")
            if dest.suffix == ".sh":
                tmp.chmod(0o755)
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
        written.append(rel)
    return written


def _write_blocker(proj: Path) -> str | None:
    """The first symlink that would make a backfill write outside the project or leave a marker
    the gate reads as absent: a symlinked parent directory of any file it writes, or a dangling
    symlink at one of those files. A live symlink at a file is the project's own and is kept."""
    for rel in (RUN_PYTEST, BASELINE, CI_LOCAL):
        cur = proj
        for part in Path(rel).parts[:-1]:
            cur = cur / part
            if cur.is_symlink():
                return str(cur.relative_to(proj))
        leaf = proj / rel
        if leaf.is_symlink() and not leaf.exists():
            return rel
    return None


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    do_apply = "--apply" in sys.argv
    force = "--force" in sys.argv
    if not args:
        print(__doc__)
        return 2
    _assert_ruff_matches_pin()
    print(
        f"{'PROJECT':<30}{'TYPE':<14}{'DB':>3}{'WEB':>4}{'PGV':>4}{'RUFF':>6}{'SQL':>5}  "
        f"{'SQLFLUFF':<24}  {'CI?':<5}ACTION"
    )
    print("-" * 112)
    refused: list[str] = []
    failed: list[str] = []
    for name in args:
        try:
            p = plan(name)
            if p.get("error"):
                print(f"{name:<30}{p['error']}")
                failed.append(name)  # a mistyped project under --apply is a failure, not a pass
                continue
            act = _action(name, p, do_apply=do_apply, force=force)
        except OSError as e:  # one unwritable project never stops the rest of the batch
            print(f"{name:<30}FAILED ({type(e).__name__}: {e.strerror or e})")
            failed.append(name)
            continue
        if act.startswith(("REFUSED", "would REFUSE")):
            refused.append(name)
        pgv = "y" if p["exts"] else "-"
        print(
            f"{name:<30}{p['type']:<14}{'y' if p['needs_db'] else '-':>3}"
            f"{'y' if p['needs_web'] else '-':>4}{pgv:>4}{str(p['ruff']):>6}{p['sql']:>5}  "
            f"{p['sqlfluff']:<24}  {'yes' if p['has_ci'] else 'NO':<5}{act}"
        )
    if refused:
        print(
            f"\n{'REFUSED' if do_apply else 'WOULD REFUSE'}: {', '.join(refused)} — the replica "
            f"lints every tracked *.sql with sqlfluff {SQLFLUFF_VERSION} on every run and has no "
            "ratchet: a red verdict means its first run reds, and an unknown one means this "
            "interpreter could not tell. Get a verdict by hand in the project, then fix the SQL "
            "or re-run with --force:\n"
            f"  git ls-files -z -- '*.sql' | xargs -0 uvx sqlfluff=={SQLFLUFF_VERSION} lint "
            "--dialect postgres"
        )
    if not do_apply:
        print("\n(DRY-RUN — nothing written. Re-run with --apply to write files + seed baselines.)")
    return 1 if do_apply and (refused or failed) else 0


def _action(name: str, p: dict, *, do_apply: bool, force: bool) -> str:
    """The row's ACTION for one project; with `do_apply` it performs the write it names."""
    if p["has_ci"]:
        return p["ci_state"]
    if _refused(p) and not force:
        verb = "REFUSED" if do_apply else "would REFUSE"
        return f"{verb} (sqlfluff {p['sqlfluff']}; --force overrides)"
    forced = f" (forced past sqlfluff {p['sqlfluff']})" if _refused(p) else ""
    if not do_apply:
        if p["blocker"]:  # the dry run says what the apply will do: fail on this symlink
            return f"would FAIL (symlink at {p['blocker']})"
        if p["baseline_exists"]:
            seed = "keep its baseline"
        elif p["ruff"] is None:
            seed = "write (no ruff)"
        else:
            seed = f"seed baseline@{p['ruff']}"
        return f"would {seed}{forced}"
    written = apply(name, p)
    if BASELINE in written:
        seeded = f"+baseline@{p['ruff']}"
    elif p["baseline_exists"]:
        seeded = "(kept its baseline)"
    else:
        seeded = "(no ruff)"
    return f"WROTE {seeded}{forced}"


if __name__ == "__main__":
    sys.exit(main())
