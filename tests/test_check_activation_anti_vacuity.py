"""Anti-vacuity proof for the Tier-3 checks activated on 2026-08-16.

THE FAILURE BEING FIXED: `check_docker`, `check_ports`, `check_env_contract`,
`check_deps_sync`, `check_watchdog` and `check_health` were registered in
`final_gate.py` and reported PASS while asserting nothing — each defined only
`check_file()`, with no `__main__` and no top-level call, so running them exited 0
with empty output. Six green rows, zero coverage.

So the tests that matter here are not "does the logic work" but **"can this check
actually fail"**. Every activated check gets a pair: RED on a known-bad fixture,
GREEN on a clean one. A check that passes only the GREEN half is exactly the bug.

The four checks that were UNWIRED instead still get their entry point tested — they
remain hand-runnable diagnostics, and a diagnostic that silently exits 0 is the same
trap wearing a different hat.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENFORCEMENT = REPO_ROOT / "scripts" / "enforcement"

SCRIPT_FORM = ["check_docker", "check_ports", "check_watchdog", "check_health"]
MODULE_FORM = ["check_env_contract", "check_deps_sync"]


def run_check(name: str, root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Invoke a check exactly the way `final_gate.run_optional_check` does."""
    if name in MODULE_FORM:
        cmd = [sys.executable, "-m", f"scripts.enforcement.{name}", "--root", str(root)]
        cwd = REPO_ROOT
    else:
        cmd = [sys.executable, str(ENFORCEMENT / f"{name}.py"), "--root", str(root)]
        cwd = root
    cmd.extend(extra)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=300)


# ── The vacuity regression itself ────────────────────────────────────────────────


@pytest.mark.parametrize("name", SCRIPT_FORM + MODULE_FORM)
def test_check_produces_a_verdict_not_silence(name: str, tmp_path: Path) -> None:
    """Every check must SAY something. Empty stdout was the whole bug.

    Before activation each of these printed nothing at all, which
    `run_optional_check` recorded as a pass. A verdict line is the minimum evidence
    that the check ran.
    """
    result = run_check(name, tmp_path)
    assert result.stdout.strip(), (
        f"{name} produced NO output — this is the vacuous-check regression:"
        f" stderr={result.stderr[:400]}"
    )
    assert "PASS:" in result.stdout or "FAIL:" in result.stdout, (
        f"{name} printed no verdict line: {result.stdout[:400]}"
    )


@pytest.mark.parametrize("name", SCRIPT_FORM + MODULE_FORM)
def test_check_is_green_on_an_empty_tree(name: str, tmp_path: Path) -> None:
    """No files, no findings, exit 0 — the other half of the RED/GREEN pair."""
    result = run_check(name, tmp_path)
    assert result.returncode == 0, f"{name} failed on an empty tree: {result.stdout[:400]}"
    assert "PASS:" in result.stdout


# ── check_docker: RED on a real defect ───────────────────────────────────────────


def test_check_docker_red_on_non_amd64_platform(tmp_path: Path) -> None:
    """`platform: linux/arm64` in a built compose must FAIL.

    This is the defect the activation actually surfaced: 5 fleet repos ship an arm64
    platform in a production compose deployed to an x86_64 VPS.
    """
    (tmp_path / "compose.yaml").write_text(
        "services:\n"
        "  app:\n"
        "    platform: linux/arm64\n"
        "    build:\n"
        "      context: .\n",
        encoding="utf-8",
    )
    result = run_check("check_docker", tmp_path)
    assert result.returncode == 1, f"check_docker did not fail: {result.stdout}"
    assert "amd64" in result.stdout


def test_check_docker_red_on_alpine_dockerfile(tmp_path: Path) -> None:
    """A BUILT Alpine image is still an ERROR (musl is the reason the rule exists)."""
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12-alpine\nHEALTHCHECK CMD true\n", encoding="utf-8"
    )
    result = run_check("check_docker", tmp_path)
    assert result.returncode == 1, f"check_docker did not fail: {result.stdout}"
    assert "Alpine base image" in result.stdout


def test_check_docker_green_on_compose_alpine_service_image(tmp_path: Path) -> None:
    """A PRE-BUILT upstream `image: redis:7-alpine` warns but must NOT fail.

    Demoting this from ERROR is deliberate: those are the vendors' own supported
    images, running in production on vps1 today. Gating on them would red the hub
    permanently for no correctness gain.
    """
    (tmp_path / "compose.yaml").write_text(
        "services:\n  cache:\n    image: redis:7-alpine\n", encoding="utf-8"
    )
    result = run_check("check_docker", tmp_path)
    assert result.returncode == 0, f"upstream alpine image should not fail: {result.stdout}"
    assert "1 warning" in result.stdout


def test_check_docker_green_on_compliant_compose(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text(
        "services:\n"
        "  app:\n"
        "    platform: linux/amd64\n"
        "    build:\n"
        "      context: .\n",
        encoding="utf-8",
    )
    result = run_check("check_docker", tmp_path)
    assert result.returncode == 0, result.stdout
    assert "0 error(s)" in result.stdout


# ── check_env_contract: RED on a real defect, and NOT on its two FP classes ──────


def test_check_env_contract_red_on_undeclared_compose_var(tmp_path: Path) -> None:
    """A compose-required var absent from an EXISTING .env.example must FAIL.

    This is the hub's own real finding: apps/example-api substituted
    ${POSTGRES_PASSWORD} into a DATABASE_URL fallback without declaring it, so an
    unset value silently yields an empty password.
    """
    (tmp_path / ".env.example").write_text("API_KEY=\n", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text(
        "services:\n  app:\n    environment:\n      - PW=${POSTGRES_PASSWORD}\n",
        encoding="utf-8",
    )
    result = run_check("check_env_contract", tmp_path)
    assert result.returncode == 1, f"check_env_contract did not fail: {result.stdout}"
    assert "POSTGRES_PASSWORD" in result.stdout


def test_check_env_contract_green_without_an_env_example(tmp_path: Path) -> None:
    """No .env.example means NO CONTRACT — not "every variable violates it".

    Before this fix a compose with no sibling .env.example reported every one of its
    vars as a missing-required ERROR: 13 in the hub (all from `infra/vps1/*` deploy
    units whose secrets live on the VPS) and 106 across 17 of 45 fleet repos.
    """
    (tmp_path / "compose.yaml").write_text(
        "services:\n  app:\n    environment:\n      - PW=${POSTGRES_PASSWORD}\n",
        encoding="utf-8",
    )
    result = run_check("check_env_contract", tmp_path)
    assert result.returncode == 0, f"missing .env.example must not fail: {result.stdout}"
    assert "0 error(s)" in result.stdout


def test_check_env_contract_ignores_yaml_comments(tmp_path: Path) -> None:
    """A `${VAR:?}` inside a COMMENT is documentation, not a reference.

    The scaffolder's compose template ships the literal line
    `#   3. Environment variables (use ${VAR:?} for required vars)`. Parsing it made
    17 of 45 fleet repos "require" a variable named VAR — on comment text alone.
    """
    (tmp_path / ".env.example").write_text("API_KEY=\n", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text(
        "#   3. Environment variables (use ${VAR:?} for required vars)\n"
        "services:\n"
        "  app:\n"
        "    environment:\n"
        "      # - DATABASE_URL=${DATABASE_URL}\n"
        "      - API_KEY=${API_KEY}\n",
        encoding="utf-8",
    )
    result = run_check("check_env_contract", tmp_path)
    assert result.returncode == 0, f"comment-only vars must not fail: {result.stdout}"
    assert "VAR" not in result.stdout.replace("--root", "")


# ── The runner's own contracts ───────────────────────────────────────────────────


def test_strict_promotes_warnings_to_failure(tmp_path: Path) -> None:
    """`--strict` is the documented activation switch for WARN-only findings."""
    (tmp_path / "compose.yaml").write_text(
        "services:\n  cache:\n    image: redis:7-alpine\n", encoding="utf-8"
    )
    lenient = run_check("check_docker", tmp_path)
    assert lenient.returncode == 0, lenient.stdout

    strict = run_check("check_docker", tmp_path, "--strict")
    assert strict.returncode == 1, f"--strict did not promote the WARN: {strict.stdout}"


def test_findings_are_deduplicated_across_trigger_files(tmp_path: Path) -> None:
    """One problem is reported once, however many files route to it.

    check_env_contract fires for `.env.example`, `compose.yaml` AND
    `docs/CONFIGURATION.md`, each re-deriving the same project — so the hub's single
    real defect was reported twice before dedup.
    """
    (tmp_path / ".env.example").write_text("API_KEY=\n", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text(
        "services:\n  app:\n    environment:\n      - PW=${POSTGRES_PASSWORD}\n",
        encoding="utf-8",
    )
    result = run_check("check_env_contract", tmp_path)
    assert result.stdout.count("POSTGRES_PASSWORD' in compose.yaml") == 1, result.stdout


def test_runner_skips_vendored_trees(tmp_path: Path) -> None:
    """A defect inside node_modules/.venv is not this repo's defect."""
    vendored = tmp_path / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "Dockerfile").write_text("FROM python:3.12-alpine\n", encoding="utf-8")
    result = run_check("check_docker", tmp_path)
    assert result.returncode == 0, f"vendored tree should be skipped: {result.stdout}"


# ── The two activated checks must be green on THIS repo ─────────────────────────


@pytest.mark.parametrize("name", ["check_docker", "check_env_contract"])
def test_activated_checks_are_green_on_this_repo(name: str) -> None:
    """The gate registers these to FAIL on error — so this repo must be clean.

    If this goes red, the gate is red: that is the point of activating them.
    """
    result = run_check(name, REPO_ROOT)
    assert result.returncode == 0, (
        f"{name} is RED on this repo, so final_gate --systemic is RED:\n{result.stdout}"
    )
