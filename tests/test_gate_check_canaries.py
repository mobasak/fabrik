"""Canary coverage for every gate check `final_gate.py` registers.

WHY THIS FILE EXISTS. On 2026-08-16 six Tier-3 checks were found reporting PASS while
asserting nothing — no `__main__`, exit 0, empty output — and `tests/
test_check_activation_anti_vacuity.py` proved the fixed ones RED. The liveness layer then
measured the rest and reported **40 of 43 registered checks UNPROVEN**: not broken, just
never once shown able to fail. A check that cannot fail buys exactly the same green as one
that works, so "unproven" and "vacuous" are indistinguishable from the gate's output.

This file closes that gap for the whole corpus. Every entry in
`liveness_audit.CANARIES` is a PAIR — a deliberately-bad fixture the check must reject
(non-zero exit) and a clean control it must accept (exit 0) — and each is asserted here,
so the proof is a test rather than a report someone has to remember to run.

Three obligations, and they are the file's whole content:

1.  **Every canary discriminates.** The bad tree goes red, the clean tree goes green.
2.  **Every registered check is accounted for.** A new `run_optional_check(...)` in
    `final_gate.py` with no canary and no documented obstruction fails
    `test_every_registered_gate_check_is_accounted_for` — the ratchet that stops the
    40-unproven state from quietly re-accumulating.
3.  **The canaries are not themselves vacuous.** `NEUTERS` deletes one check's core rule
    and asserts its canary then goes GREEN. A canary that passes a broken check proves
    nothing about the working one, and that is the exact failure mode this whole layer
    exists to catch — so it is tested, not assumed.

The `warn_only` entries are a deliberate inversion: those checks have NO non-zero exit
path at all, their canary is EXPECTED to stay green, and the assertion is that they still
PRINT the violation. They are registered in `final_gate.py` like any other check while
being structurally unable to red it — the finding is recorded here rather than hidden.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENFORCEMENT = REPO_ROOT / "scripts" / "enforcement"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "sysadmin"))

import liveness_audit as la  # noqa: E402 — the path insert must precede the import

WARN_ONLY = sorted(n for n, c in la.CANARIES.items() if c.get("warn_only"))
FAILING = sorted(n for n, c in la.CANARIES.items() if not c.get("warn_only"))


def _run_fixture(name: str, *, bad: bool) -> subprocess.CompletedProcess[str] | None:
    """Build one half of a canary pair and run the check against it, raw."""
    canary = la.CANARIES[name]
    script = ENFORCEMENT / f"{name}.py"
    with tempfile.TemporaryDirectory() as td:
        fixture = Path(td) / "fx"
        fixture.mkdir()
        fault = la._prepare(fixture, canary, REPO_ROOT, bad=bad)
        assert not fault, f"{name}: harness fault, not a check verdict: {fault}"
        argv, cwd, env = la._argv(name, canary, script, fixture, REPO_ROOT)
        return la._run(argv, cwd=cwd, env=env, timeout=int(canary.get("timeout", 60)))


# ── 1. Every canary discriminates ────────────────────────────────────────────────


@pytest.mark.parametrize("name", FAILING)
def test_the_check_rejects_its_bad_fixture_and_accepts_the_clean_one(name: str) -> None:
    """The pair, run exactly as the liveness audit runs it.

    `run_canary` refuses to report a verdict at all unless its CONTROL first exits 0
    without a traceback — so `inst.ok` already carries "the clean tree passed", and
    `went_red` carries "the bad tree failed". Both halves, one call.
    """
    inst, went_red = la.run_canary(name, la.CANARIES[name], REPO_ROOT)
    assert inst.ok, f"{name}: the canary harness is broken, not the check: {inst.fault}"
    assert went_red, (
        f"{name} stayed GREEN on {la.CANARIES[name]['expect']} — it is registered in "
        "final_gate.py and cannot fail, which is the vacuous-check regression"
    )


@pytest.mark.parametrize("name", WARN_ONLY)
def test_a_warn_only_check_reports_the_violation_it_cannot_fail_on(name: str) -> None:
    """These CANNOT exit non-zero. The only teeth they have are their stdout — assert it.

    Registered in `final_gate.py` as ordinary checks, they occupy a green row no defect
    can turn red. Pinning the WARN text here means the day one of them grows a real exit
    path, `test_the_check_rejects_its_bad_fixture_and_accepts_the_clean_one` picks it up
    (the `warn_only` key moves) rather than the change passing unnoticed.
    """
    clean = _run_fixture(name, bad=False)
    bad = _run_fixture(name, bad=True)
    assert clean is not None and bad is not None, f"{name} could not be executed"
    assert clean.returncode == 0 and bad.returncode == 0, (
        f"{name} now has a non-zero exit path — drop its `warn_only` key in CANARIES and "
        f"let it be asserted as a real failing check (clean={clean.returncode}, "
        f"bad={bad.returncode})"
    )
    extra = (bad.stdout + bad.stderr).replace(clean.stdout + clean.stderr, "")
    assert extra.strip(), (
        f"{name} is registered in final_gate.py, cannot exit non-zero, AND says nothing "
        f"about {la.CANARIES[name]['expect']} — it is a fully silent gate row"
    )


# ── 2. The coverage ratchet ──────────────────────────────────────────────────────


def test_every_registered_gate_check_is_accounted_for() -> None:
    """A new gate check ships with a canary, or with its obstruction written down.

    This is the ratchet. The 40-unproven state did not arrive in one commit; it
    accumulated one unexamined `run_optional_check(...)` at a time.
    """
    inst, names = la.discover_registered_checks(REPO_ROOT / "scripts" / "final_gate.py")
    assert inst.ok, inst.fault
    unaccounted = sorted(set(names) - set(la.CANARIES) - set(la.UNREACHABLE))
    assert not unaccounted, (
        f"{len(unaccounted)} registered check(s) have neither a canary nor an UNREACHABLE "
        f"reason: {unaccounted}. Author the pair in liveness_audit.CANARIES, or — if a "
        "fixture genuinely cannot reach it — record WHY in UNREACHABLE."
    )


def test_unreachable_entries_name_a_real_check_and_carry_a_reason() -> None:
    for name, why in la.UNREACHABLE.items():
        assert (ENFORCEMENT / f"{name}.py").is_file(), f"{name} is not a check script"
        assert len(why) > 40, f"{name}: 'unreachable' needs the obstruction NAMED, got {why!r}"
        assert name not in la.CANARIES, f"{name} is both canaried and declared unreachable"


# ── 3. The canaries are not themselves vacuous ───────────────────────────────────

# One surgical edit per check that deletes the rule under test — not the exit code, the
# RULE. If a canary survives this, it was keying on something incidental (a crash, an
# unrelated finding) and its green was worthless.
NEUTERS: dict[str, tuple[str, str]] = {
    "check_rule_size": ("if size > MAX_SIZE_BYTES:", "if size > MAX_SIZE_BYTES * 1000:"),
    "check_print_ban": ("    if all_violations:", "    if False:"),
    "check_no_host_ports": ("    if all_violations:", "    if False:"),
    "check_user_guide": (
        "    if not has_user_guide_enabled(repo_root):",
        "    if True:",
    ),
    "check_synced_unmodified": (
        "        elif _md5(dest) != distributed_hash:",
        "        elif False:",
    ),
    "check_env_vars": ("        if r.severity == Severity.ERROR", "        if False"),
    "check_doc_index": (
        "        if p not in index_text and base not in index_text:",
        "        if False:",
    ),
}


@pytest.mark.parametrize("name", sorted(NEUTERS))
def test_the_canary_goes_green_against_a_neutered_check(name: str, tmp_path: Path) -> None:
    """Watched-fail-first, applied to the canary itself.

    A whole copy of `scripts/enforcement/` is staged in a throwaway root, ONE rule is
    deleted from ONE check, and the same canary is re-run against it. It must now pass —
    proving the red we assert above comes from that rule and nothing else. The real
    `scripts/enforcement/` is never touched.
    """
    fake_root = tmp_path / "repo"
    (fake_root / "scripts").mkdir(parents=True)
    shutil.copytree(ENFORCEMENT, fake_root / "scripts" / "enforcement")

    target = fake_root / "scripts" / "enforcement" / f"{name}.py"
    old, new = NEUTERS[name]
    text = target.read_text(encoding="utf-8")
    assert text.count(old) == 1, (
        f"{name}: the neuter anchor {old!r} no longer appears exactly once — the check was "
        "refactored, so re-derive the anchor rather than deleting this case"
    )
    target.write_text(text.replace(old, new), encoding="utf-8")

    inst, went_red = la.run_canary(name, la.CANARIES[name], fake_root)
    assert inst.ok, f"{name}: neutered copy could not be measured: {inst.fault}"
    assert not went_red, (
        f"{name}: the canary went RED against a check whose rule was DELETED — it is "
        "keying on something other than the rule, so its green proves nothing"
    )
