# AFTER-EDIT: scripts/kilo-benchmarks/microbench_judged.py scripts/kilo-benchmarks/correlated_prior.py
"""Free, deterministic STRUCTURAL grader for the plan / spec judged task types.

plan/spec quality is semi-subjective, so we do NOT try to score it with a paid model here.
Instead we invert the problem: a $0 deterministic STRUCTURAL FILTER acts as the objective
disqualifier (does the output even parse as a plan/spec — phases, runnable gates, resolving
path:line citations, required sections, a shape block), and the FLYWHEEL (real subagent_runs
verdicts) is the primary quality signal downstream. `score5` here is the weighted fraction of
structural checks passed × 5; a HARD-FAIL (an output with no phases/gates — or, for a spec, no
sections/shape — at all) disqualifies with score5=0.

Registered into `microbench_judged.GRADERS` on import (the Phase-B/C/D grader seam):

    GRADERS["plan"] = lambda g, c: structural_grade(g, c, "plan")
    GRADERS["spec"] = lambda g, c: structural_grade(g, c, "spec")

The harness overlays the objective cost/latency/token/n_err columns via `_finalize_scores`,
so this grader owns only `score5` / `n_graded` / `structural`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from microbench_judged import SCALE, TaskScore, register_grader

# Repo root: scripts/kilo-benchmarks/<this> → parents[2] is the project/worktree root. Citations are
# resolved relative to it. Overridable per-call (tests point it at a temp repo).
_REPO_ROOT = Path(__file__).resolve().parents[2]

# ── path:line citation resolution (bounded + containment-guarded) ───────────────────────────────
# Require a file EXTENSION so we never match a bare "10:30" time or "score5:5"; keep it to safe
# path chars. e.g. "scripts/foo/bar.py:142".
_CITATION_RE = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_./\-]*\.[A-Za-z0-9]+):(\d+)")
_MAX_CITED_LINE = (
    200_000  # refuse absurd line numbers (never stream a whole huge file for one cite)
)


def _citation_resolves(path_str: str, line_no: int, repo_root: Path) -> bool:
    """True iff `path_str:line_no` names a real line of a real file INSIDE repo_root.

    Bounded/safe: containment-guarded (no ../ escape), file-only, and the read STOPS at the cited
    line (never slurps a large file), with an absurd-line-number cap. Any I/O error → False."""
    if line_no < 1 or line_no > _MAX_CITED_LINE:
        return False
    root = repo_root.resolve()
    try:
        target = (root / path_str).resolve()
        target.relative_to(root)  # containment: reject paths that escape the repo
    except (ValueError, OSError):
        return False
    if not target.is_file():
        return False
    try:
        with target.open("r", encoding="utf-8", errors="replace") as fh:
            for i, _ in enumerate(fh, 1):
                if i == line_no:
                    return True
                if i > line_no:  # defensive — enumerate is monotonic
                    break
    except OSError:
        return False
    return False  # file has fewer lines than cited


def _citations_ok(text: str, repo_root: Path) -> bool:
    """A plan/spec must cite ≥1 real repo line, and EVERY REPO path:line it cites must resolve.

    External URLs are stripped first so a cited `https://host/x.py:42` isn't treated as a (non-resolving)
    repo citation — this grades REPO grounding, not external links (reviewer S5). A plan citing only
    external URLs has no repo grounding → fails (empty repo cites)."""
    text = re.sub(r"https?://\S+", " ", text)
    cites = _CITATION_RE.findall(text)
    if not cites:
        return False
    return all(_citation_resolves(p, int(ln), repo_root) for p, ln in cites)


# ── individual structural checks (each: (text, repo_root) -> bool) ──────────────────────────────
_PHASE_RE = re.compile(r"(?im)\bphase\s+[A-Za-z0-9]")
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
_TEST_RE = re.compile(
    r"(?i)\b(tests?|testing|behaviou?rs?|acceptance)\b"
)  # incl. plural "tests"/"testing"
# A fenced block is a runnable GATE only if it carries a command token (not just any prose in a fence).
_CMD_HINT_RE = re.compile(
    r"(?im)(?:^|\s|\$)\s*(python3?|pytest|git|bash|sh|npm|npx|ruff|mypy|pip|make|cd|curl|docker|assert)\b|\./"
)
_EVIDENCE_RE = re.compile(r"(?i)\bevidence\b")
_SHAPE_RE = re.compile(r"(?im)^\s*shape\s*:")
# A spec's required section headings — three orthogonal groups; ALL must appear as headings.
_SECTION_GROUPS = (
    re.compile(r"(?im)^#{1,4}\s*(overview|goal|summary)\b"),
    re.compile(r"(?im)^#{1,4}\s*(acceptance|behaviou?r|criteria)\b"),
    re.compile(r"(?im)^#{1,4}\s*(interface|api|schema|contract)\b"),
)


def _has_phases(text: str, _root: Path) -> bool:
    return bool(_PHASE_RE.search(text))


def _has_runnable_gate(text: str, _root: Path) -> bool:
    """≥1 fenced block that carries a COMMAND token (python/pytest/git/… or `./`) — not merely any
    non-empty prose in a fence (reviewer S8: a prose fence is not a runnable gate)."""
    return any(_CMD_HINT_RE.search(block) for block in _FENCE_RE.findall(text))


def _has_test(text: str, _root: Path) -> bool:
    return bool(_TEST_RE.search(text))


def _has_evidence(text: str, _root: Path) -> bool:
    return bool(_EVIDENCE_RE.search(text))


def _has_sections(text: str, _root: Path) -> bool:
    return all(rx.search(text) for rx in _SECTION_GROUPS)


def _has_shape(text: str, _root: Path) -> bool:
    """A `shape:` block with ≥1 flag AND an enum/constraint (the spec-contract axis)."""
    if not _SHAPE_RE.search(text):
        return False
    has_flag = bool(re.search(r"(?im)^\s*needs_\w+\s*:", text)) or bool(
        re.search(r"(?im)^\s*(is_|has_|exposes_)\w+\s*:", text)
    )
    has_enum = bool(re.search(r"(?i)enum|\[[^\]]+,[^\]]+\]", text))
    return has_flag and has_enum


_Check = tuple[str, Callable[[str, Path], bool]]

# (name, fn) in declaration order; equal-weighted. `phases`/`gates` (plan) and `sections`/`shape`
# (spec) double as the HARD-FAIL disqualifier keys.
_PLAN_CHECKS: list[_Check] = [
    ("phases", _has_phases),
    ("gates", _has_runnable_gate),
    ("citations", _citations_ok),
    ("tests", _has_test),
    ("evidence", _has_evidence),
]
_SPEC_CHECKS: list[_Check] = [
    ("sections", _has_sections),
    ("shape", _has_shape),
    ("citations", _citations_ok),
]
_CHECKS: dict[str, list[_Check]] = {"plan": _PLAN_CHECKS, "spec": _SPEC_CHECKS}


def _grade_text(text: str, kind: str, repo_root: Path) -> tuple[float, int, int]:
    """Grade one generation → (fraction_0_1, n_passed, n_total). Hard-fail → (0.0, 0, total)."""
    checks = _CHECKS[kind]
    results = {name: fn(text, repo_root) for name, fn in checks}
    total = len(checks)
    if kind == "plan" and not results["phases"] and not results["gates"]:
        return 0.0, 0, total  # disqualified: not a plan at all
    if kind == "spec" and not results["sections"] and not results["shape"]:
        return 0.0, 0, total  # disqualified: not a spec at all
    passed = sum(1 for ok in results.values() if ok)
    return passed / total, passed, total


def structural_grade(
    gens: dict[str, list],
    corpus: list[dict],  # noqa: ARG001 — signature parity with the Grader protocol (unused: $0 structural)
    kind: str = "plan",
    *,
    repo_root: Path | None = None,
) -> dict[str, TaskScore]:
    """Deterministic ($0) structural score per model for `kind` ∈ {"plan","spec"}.

    Each model's generations are graded; `score5` is the mean weighted-fraction × 5, `structural`
    reports the mean passed-checks (e.g. "4.0/5 checks"). Errored/empty slots (text is None) are
    counted as n_err, never graded 0."""
    if kind not in _CHECKS:
        raise ValueError(f"structural_grade: unknown kind {kind!r} (expected 'plan' or 'spec')")
    root = repo_root or _REPO_ROOT
    total = len(_CHECKS[kind])
    scores: dict[str, TaskScore] = {}
    for model, glist in gens.items():
        fracs: list[float] = []
        passed_counts: list[int] = []
        n_err = 0
        for g in glist:
            text = getattr(g, "text", None)
            if text is None:
                n_err += 1
                continue
            frac, passed, _ = _grade_text(text, kind, root)
            fracs.append(frac)
            passed_counts.append(passed)
        n_graded = len(fracs)
        score5 = round((sum(fracs) / n_graded) * SCALE, 3) if n_graded else 0.0
        avg_passed = (sum(passed_counts) / len(passed_counts)) if passed_counts else 0.0
        scores[model] = TaskScore(
            model=model,
            score5=score5,
            n_graded=n_graded,
            n_err=n_err,
            structural=f"{avg_passed:.1f}/{total} checks",
        )
    return scores


# ── DEFERRED SEAM: PoLL (panel-of-LLMs) semantic judge — intentionally NOT built ────────────────
# DEFERRED: a semantic judge for plan/spec quality is out of scope here. This module ships ONLY the
# free deterministic structural disqualifier/floor. A future calibration/audit pass would dispatch a
# `claude-evaluator(model="opus")` panel to spot-check the structural score against human judgement
# — but that is a nicety, not the ranker: the FLYWHEEL (real subagent_runs verdicts) is the primary
# plan/spec quality signal. Build the PoLL judge only if the flywheel proves insufficient.
FLYWHEEL_PRIMARY_NOTE = (
    "The flywheel (subagent_runs quality verdicts) is the PRIMARY plan/spec quality signal; this "
    "structural grader is a free deterministic disqualifier/floor. The PoLL semantic judge "
    "(claude-evaluator(model='opus') calibration/audit) is DEFERRED — build it only if the "
    "flywheel proves insufficient."
)


def _poll_judge_calibrate(*_args: object, **_kwargs: object) -> None:  # pragma: no cover - DEFERRED
    """DEFERRED seam: future `claude-evaluator(model="opus")` calibration/audit of the structural
    score against human judgement. Not built — the flywheel is the primary signal (FLYWHEEL_PRIMARY_NOTE)."""
    raise NotImplementedError("PoLL judge deferred — the flywheel is the primary plan/spec signal")


# Register the graders into the harness seam on import.
register_grader("plan", lambda g, c: structural_grade(g, c, "plan"))
register_grader("spec", lambda g, c: structural_grade(g, c, "spec"))
