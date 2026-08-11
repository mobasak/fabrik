"""Source-structure pins for final_gate.py's check registrations (plan-2 closing review).

Two registration regressions shipped and were caught only by later review rounds: Phase Tests
registered in the shared tier-(1,2) block (polluting --lean and falsifying doc counts), and the
FABRIK_MUTMUT env-leak orphaning a session-detached mutmut under the gate's outer timeout. Nothing
mechanically pinned either placement — these assertions do. They read the SOURCE (running the full
gate here would be a gate-inside-a-test); positional `str.index` on the tier markers is the same
containment logic a reviewer applies by eye, made mechanical.
"""

from pathlib import Path

GATE = Path(__file__).resolve().parents[2] / "scripts" / "final_gate.py"


def test_phase_tests_registered_tier2_only():
    src = GATE.read_text(encoding="utf-8")
    assert src.count("check_phase_tests.py") == 1, "exactly one registration site"
    tier2 = src.index("if tier == 2:")
    reg = src.index("check_phase_tests.py")
    tier3_after = src.index("if tier == 3", tier2)
    assert tier2 < reg < tier3_after, (
        "check_phase_tests.py must sit INSIDE the tier==2 block — the shared tier-(1,2) "
        "placement polluted --lean (shipped regression, review-caught)"
    )


def test_mutation_registration_is_env_strip_guarded():
    src = GATE.read_text(encoding="utf-8")
    assert src.count("scripts/enforcement/check_mutation.py") == 1, "exactly one registration site"
    pop = src.index('os.environ.pop("FABRIK_MUTMUT"')
    reg = src.index("scripts/enforcement/check_mutation.py")
    restore = src.index('os.environ["FABRIK_MUTMUT"] = _mutmut_leak')
    assert pop < reg < restore, (
        "the registration must run between the FABRIK_MUTMUT pop and its finally-restore — "
        "a leaked flag orphans the session-detached mutmut under the gate's outer timeout"
    )
