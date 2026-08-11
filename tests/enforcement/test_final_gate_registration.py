"""Semantic pins for final_gate.py's check registrations (plan-2 closing review, hardened).

Two registration regressions shipped and were caught only by later review rounds: Phase Tests
registered in the shared tier-(1,2) block (polluting --lean and falsifying doc counts), and the
FABRIK_MUTMUT env-leak orphaning a session-detached mutmut under the gate's outer timeout. The
first pin attempt asserted textual POSITION (`str.index` ordering) and a follow-up review round
live-simulated two mutants that defeat it: de-indenting the registration to run unconditionally
while staying between the tier markers, and flattening the try/finally while keeping line order.
These pins are AST-based — block MEMBERSHIP and exception-safety STRUCTURE — and each test also
feeds its defeating mutant to its own helper to prove discriminating power (built-in red).
"""

import ast
from pathlib import Path

GATE = Path(__file__).resolve().parents[2] / "scripts" / "final_gate.py"


def _contains_str(node: ast.AST, needle: str) -> bool:
    return any(
        isinstance(x, ast.Constant) and isinstance(x.value, str) and needle in x.value
        for x in ast.walk(node)
    )


def _phase_tests_in_tier2_only(src: str) -> bool:
    """True iff every 'check_phase_tests.py' string literal sits INSIDE the body of an
    `if tier == 2:` statement (and at least one exists)."""
    tree = ast.parse(src)
    total = sum(
        1
        for x in ast.walk(tree)
        if isinstance(x, ast.Constant)
        and isinstance(x.value, str)
        and "check_phase_tests.py" in x.value
    )
    inside = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            t = node.test
            if (
                isinstance(t, ast.Compare)
                and isinstance(t.left, ast.Name)
                and t.left.id == "tier"
                and len(t.ops) == 1
                and isinstance(t.ops[0], ast.Eq)
                and isinstance(t.comparators[0], ast.Constant)
                and t.comparators[0].value == 2
            ):
                for stmt in node.body:
                    if _contains_str(stmt, "check_phase_tests.py"):
                        inside += 1
    return total >= 1 and inside == total


def _mutation_registration_guarded(src: str) -> bool:
    """True iff the check_mutation.py registration executes inside a Try whose FINALLY
    restores FABRIK_MUTMUT, with an os.environ.pop("FABRIK_MUTMUT", …) before that Try."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Try) and node.finalbody):
            continue
        body = ast.Module(body=node.body, type_ignores=[])
        fin = ast.Module(body=node.finalbody, type_ignores=[])
        if not (
            _contains_str(body, "scripts/enforcement/check_mutation.py")
            and _contains_str(fin, "FABRIK_MUTMUT")
        ):
            continue
        for call in ast.walk(tree):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "pop"
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and call.args[0].value == "FABRIK_MUTMUT"
                and call.lineno < node.lineno
            ):
                return True
    return False


# The two live-simulated mutants that DEFEATED the positional pins — each helper must
# reject its mutant or the pin is vacuous.
_MUTANT_UNCONDITIONAL = """
def run_consistency_checks(tier=2):
    results = []
    if tier == 2:
        pass  # registration de-indented OUT of the block but still between the markers
    results.append(run_optional_check("scripts/enforcement/check_phase_tests.py", "Phase Tests"))
    if tier == 3:
        pass
    return results
"""

_MUTANT_FLAT_GUARD = """
def run_consistency_checks(tier=2):
    results = []
    _mutmut_leak = os.environ.pop("FABRIK_MUTMUT", None)
    results.append(run_optional_check("scripts/enforcement/check_mutation.py", "Mutation"))
    if _mutmut_leak is not None:
        os.environ["FABRIK_MUTMUT"] = _mutmut_leak
    return results
"""


def test_phase_tests_registered_tier2_only():
    src = GATE.read_text(encoding="utf-8")
    assert _phase_tests_in_tier2_only(src), (
        "check_phase_tests.py must be registered INSIDE an `if tier == 2:` body — the shared "
        "tier-(1,2) placement polluted --lean (shipped regression, review-caught)"
    )
    assert not _phase_tests_in_tier2_only(_MUTANT_UNCONDITIONAL), (
        "pin is vacuous: it accepted the de-indented (unconditional) mutant"
    )


def test_mutation_registration_is_env_strip_guarded():
    src = GATE.read_text(encoding="utf-8")
    assert _mutation_registration_guarded(src), (
        "the check_mutation.py registration must run inside a Try whose finally restores "
        "FABRIK_MUTMUT, after an os.environ.pop — a leaked flag orphans the session-detached "
        "mutmut under the gate's outer timeout"
    )
    assert not _mutation_registration_guarded(_MUTANT_FLAT_GUARD), (
        "pin is vacuous: it accepted the flattened (no try/finally) mutant"
    )
