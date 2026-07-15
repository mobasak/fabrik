#!/usr/bin/env python3
# AFTER-EDIT: none
"""Backfill the fabrik-managed CI (`.github/workflows/ci.yml` + `scripts/ci_local.sh`) onto an
existing project that predates it, SAFELY — the generated CI is a lint ratchet
(src/fabrik/ci_scaffold.py), so this also seeds `.fabrik/lint-baseline.json` at the project's
CURRENT ruff count. Result: CI lands GREEN (debt tolerated, growth blocked) instead of flooding
red on legacy lint debt.

Per-project config is grounded, not guessed:
  needs_database  ← the hub spec's shape.needs_database if a spec exists, else an uncommented
                    DATABASE_URL in the project's .env.example.
  needs_web       ← a Next.js/web frontend (package.json present AND a saas-skeleton/web type).
  db_extensions   ← ('pgvector',) when the spec/.env references pgvector.

Usage:
  python scripts/backfill_ci.py <project> [<project> ...]   # DRY-RUN (default): report only
  python scripts/backfill_ci.py <project> --apply           # write the 2 files + seed baseline
                                                            #   (working tree only; NO git)
Commit is deliberately left to the caller (per-repo agent, or an explicit review) — this tool
never commits or pushes across repos.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fabrik.ci_scaffold import CiConfig, ci_files  # noqa: E402

OPT = Path("/opt")
HUB_SPECS = Path(__file__).resolve().parents[1] / "specs" / "services"
WEB_TYPES = {"saas-skeleton", "saas"}


def _read_yaml(p: Path) -> dict:
    import yaml
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return {}


def _spec_shape(name: str) -> dict | None:
    for cand in (HUB_SPECS / f"{name}.yaml", HUB_SPECS / f"{name}.yaml.draft"):
        if cand.exists():
            return (_read_yaml(cand).get("shape") or {})
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
    return "pgvector" in blob or "vector" in ((_spec_shape(name) or {}).get("search_backend", "") or "")


def _ruff_count(proj: Path) -> int | None:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "ruff", "check", ".", "--output-format=json", "--quiet"],
            cwd=proj, capture_output=True, text=True, check=False,
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
    ptype = (_read_yaml(proj / "project.yaml").get("type") or "unknown")
    shape = _spec_shape(name)
    needs_db = bool(shape["needs_database"]) if shape and "needs_database" in shape else _env_has_database(proj)
    needs_web = (proj / "package.json").exists() and ptype in WEB_TYPES
    exts = ("pgvector",) if (needs_db and _wants_pgvector(name, proj)) else ()
    ruff = _ruff_count(proj)
    return {
        "name": name, "type": ptype, "needs_db": needs_db, "needs_web": needs_web,
        "exts": exts, "ruff": ruff,
        "has_ci": (proj / ".github/workflows/ci.yml").exists(),
        "baseline_exists": (proj / ".fabrik/lint-baseline.json").exists(),
    }


def apply(name: str, p: dict) -> list[str]:
    proj = OPT / name
    cfg = CiConfig(needs_database=p["needs_db"], needs_web=p["needs_web"], db_extensions=p["exts"])
    written = []
    for rel, content in ci_files(cfg).items():
        dest = proj / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        if dest.suffix == ".sh":
            dest.chmod(0o755)
        written.append(rel)
    # Seed the ratchet baseline at the current count so CI lands GREEN.
    if p["ruff"] is not None:
        bl = proj / ".fabrik" / "lint-baseline.json"
        bl.parent.mkdir(parents=True, exist_ok=True)
        bl.write_text(json.dumps({"ruff_errors": p["ruff"]}) + "\n", encoding="utf-8")
        written.append(".fabrik/lint-baseline.json")
    return written


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    do_apply = "--apply" in sys.argv
    if not args:
        print(__doc__)
        return 2
    print(f"{'PROJECT':<30}{'TYPE':<14}{'DB':>3}{'WEB':>4}{'PGV':>4}{'RUFF':>6}  {'CI?':<5}ACTION")
    print("-" * 82)
    for name in args:
        p = plan(name)
        if p.get("error"):
            print(f"{name:<30}{p['error']}")
            continue
        pgv = "y" if p["exts"] else "-"
        act = "already has CI" if p["has_ci"] else (
            f"WROTE {'+baseline@'+str(p['ruff']) if p['ruff'] is not None else '(no ruff)'}"
            if do_apply else f"would seed baseline@{p['ruff']}")
        if do_apply and not p["has_ci"]:
            apply(name, p)
        print(f"{name:<30}{p['type']:<14}{'y' if p['needs_db'] else '-':>3}"
              f"{'y' if p['needs_web'] else '-':>4}{pgv:>4}{str(p['ruff']):>6}  "
              f"{'yes' if p['has_ci'] else 'NO':<5}{act}")
    if not do_apply:
        print("\n(DRY-RUN — nothing written. Re-run with --apply to write files + seed baselines.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
