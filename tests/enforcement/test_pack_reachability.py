"""check_pack_reachability — the gate-facing ADVISORY wrapper around
`pack_layout_audit.audit_layout()`.

Three Behavior-Contract rows (ticket T03):
1. A pack whose applies_to names a scaffold type it cannot match -> REPORTED, and
   applicability is NOT derived from the globs under test (proven directly against
   `select_rules.collect()` — the non-circularity contrast below).
2. A pack with NO applies_to field -> passes silently (no Finding), so the field can
   land incrementally across the corpus without turning the fleet red on day one.
3. The check reports the COUNT OF PACKS IT ACTUALLY EXAMINED, so a corpus where nobody
   declares applies_to reads as "0 examined" rather than as a pass.

Fixtures never touch the LIVE pack corpus (which changes under this test) — every pack
is synthesized under `tmp_path/.windsurf/rules/...`, and `_emitted_paths_for_type` is
monkeypatched to a fixed path tuple per scaffold type so no test invokes the real
`fabrik` scaffolder.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))
sys.path.insert(0, str(REPO / "scripts"))

import check_pack_reachability as cpr  # noqa: E402
import pack_layout_audit as pla  # noqa: E402
import select_rules  # noqa: E402


def _write_pack(
    root: Path,
    rel: str,
    *,
    globs: list[str],
    activation: str = "glob",
    applies_to: list[str] | None = None,
) -> None:
    p = root / ".windsurf" / "rules" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    globs_yaml = ", ".join(f'"{g}"' for g in globs)
    applies_to_line = ""
    if applies_to is not None:
        applies_to_yaml = ", ".join(f'"{t}"' for t in applies_to)
        applies_to_line = f"applies_to: [{applies_to_yaml}]\n"
    p.write_text(
        f"---\nactivation: {activation}\nglobs: [{globs_yaml}]\n{applies_to_line}"
        f'description: "test pack"\n---\n\n# Test Pack\n\nBody text.\n',
        encoding="utf-8",
    )


def _patch_emitted(monkeypatch, mapping: dict[str, tuple[str, ...]]) -> None:
    """Stand in for `_emitted_paths_for_type` on the SHARED engine module — the wrapper
    calls `pla.audit_layout`, which reads the module-global name, so patching `pla`'s
    attribute is sufficient (no separate patch point needed in check_pack_reachability)."""
    monkeypatch.setattr(pla, "_emitted_paths_for_type", lambda t: mapping.get(t, ()))


def _run_json(root: Path, types: list[str]) -> dict:
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["check_pack_reachability.py", "--project-root", str(root), "--types", *types, "--json"]
    try:
        with redirect_stdout(buf):
            rc = cpr.main()
    finally:
        sys.argv = argv
    assert rc == 0, "advisory contract: a completed run always exits 0"
    return json.loads(buf.getvalue())


# ---------------------------------------------------------------------------
# Row 1 — reported, and NOT derived from the globs under test
# ---------------------------------------------------------------------------


def test_row1_unreachable_applies_to_is_reported(tmp_path, monkeypatch):
    _write_pack(
        tmp_path,
        "core/claims-file-worker.md",
        globs=["**/totally-nonexistent-xyz/**"],
        applies_to=["file-worker"],
    )
    _patch_emitted(monkeypatch, {"file-worker": ("worker/main.py", "Dockerfile")})

    result = _run_json(tmp_path, ["file-worker"])

    flagged = {(f["pack"], f["scaffold_type"]) for f in result["findings"]}
    assert ("core/claims-file-worker.md", "file-worker") in flagged
    assert result["examined_count"] == 1
    assert result["examined_packs"] == ["core/claims-file-worker.md"]


def test_row1_non_circularity_check_reports_select_rules_calls_it_available(tmp_path, monkeypatch):
    """THE ticket's reason to exist, made an executable fact: a pack whose globs match
    NOTHING in the tmp project tree (so `select_rules.collect()` puts it in AVAILABLE,
    never ACTIVE) still gets REPORTED by check_pack_reachability because its `applies_to`
    independently claims a type. If applicability were derived from the ACTIVE set (the
    circular design this ticket forbids), this pack could never be examined at all —
    a broken glob drops it to AVAILABLE, and the obvious check's search space (ACTIVE
    AND matches-zero) is empty by construction."""
    _write_pack(
        tmp_path,
        "core/circularity-trap.md",
        globs=["**/totally-nonexistent-xyz/**"],
        applies_to=["file-worker"],
    )
    # No file in the tmp project tree matches the pack's glob -> select_rules.collect()
    # (the REAL, unpatched ACTIVE/AVAILABLE split — no monkeypatch on this call) puts it
    # in AVAILABLE.
    collected = select_rules.collect(tmp_path)
    available_packs = {e["pack"] for e in collected["available"]}
    active_packs = {e["pack"] for e in collected["active"]}
    assert "core/circularity-trap.md" in available_packs
    assert "core/circularity-trap.md" not in active_packs

    # Yet the reachability check — driven by applies_to, not by select_rules' ACTIVE set
    # — still examines and flags it.
    _patch_emitted(monkeypatch, {"file-worker": ("worker/main.py",)})
    result = _run_json(tmp_path, ["file-worker"])

    flagged = {(f["pack"], f["scaffold_type"]) for f in result["findings"]}
    assert ("core/circularity-trap.md", "file-worker") in flagged
    assert result["examined_count"] == 1


# ---------------------------------------------------------------------------
# Row 2 — no applies_to -> silent pass
# ---------------------------------------------------------------------------


def test_row2_no_applies_to_passes_silently(tmp_path, monkeypatch):
    _write_pack(tmp_path, "core/legacy-no-claim.md", globs=["**/workers/**"], applies_to=None)
    _patch_emitted(monkeypatch, {"file-worker": ("worker/main.py",)})

    result = _run_json(tmp_path, ["file-worker"])

    assert result["findings"] == []
    assert result["examined_count"] == 0
    assert result["examined_packs"] == []


# ---------------------------------------------------------------------------
# Row 3 — the examined count is the denominator, distinct from a bare pass
# ---------------------------------------------------------------------------


def test_row3_zero_declared_reads_as_zero_examined_not_a_pass(tmp_path, monkeypatch, capsys):
    """A corpus where NOBODY has declared applies_to must not print an unqualified
    success line — the exact "reports SUCCESS when it cannot ask its question" defect
    this check exists to avoid on itself."""
    _write_pack(tmp_path, "core/no-claim-one.md", globs=["**/a/**"], applies_to=None)
    _write_pack(tmp_path, "core/no-claim-two.md", globs=["**/b/**"], applies_to=[])
    _patch_emitted(monkeypatch, {"file-worker": ("worker/main.py",)})

    argv = sys.argv
    sys.argv = ["check_pack_reachability.py", "--project-root", str(tmp_path), "--types", "file-worker"]
    try:
        rc = cpr.main()
    finally:
        sys.argv = argv
    out = capsys.readouterr().out

    assert rc == 0
    assert "Examined 0 pack(s)" in out
    assert "NOTHING TO CHECK" in out
    assert "OK —" not in out, "zero examined must never read as a pass"


def test_row3_examined_count_matches_declared_packs(tmp_path, monkeypatch):
    """examined_count reflects packs whose applies_to reaches one of the CHECKED types —
    not the whole corpus size, and not a pack whose applies_to names a type outside the
    types actually being checked this run."""
    _write_pack(tmp_path, "core/reaches.md", globs=["**/worker.py"], applies_to=["file-worker"])
    _write_pack(tmp_path, "core/out-of-scope.md", globs=["**/x/**"], applies_to=["node-api"])
    _write_pack(tmp_path, "core/silent.md", globs=["**/y/**"], applies_to=None)
    _patch_emitted(monkeypatch, {"file-worker": ("worker.py",)})

    result = _run_json(tmp_path, ["file-worker"])

    assert result["examined_count"] == 1
    assert result["examined_packs"] == ["core/reaches.md"]
    assert result["findings"] == []  # "**/worker.py" matches the emitted "worker.py"


# ---------------------------------------------------------------------------
# Manual activation stays excluded (inherited from the shared engine — sanity check
# that the wrapper doesn't double-count it into "examined").
# ---------------------------------------------------------------------------


def test_manual_activation_never_counted_examined(tmp_path, monkeypatch):
    _write_pack(
        tmp_path,
        "core/manual-pack.md",
        globs=["**/never-matches/**"],
        activation="manual",
        applies_to=["file-worker"],
    )
    _patch_emitted(monkeypatch, {"file-worker": ("worker/main.py",)})

    result = _run_json(tmp_path, ["file-worker"])

    assert result["examined_count"] == 0
    assert result["findings"] == []


# ---------------------------------------------------------------------------
# Integration: run against the real corpus, advisory contract holds.
# ---------------------------------------------------------------------------


def test_real_corpus_advisory_exit_and_examined_count():
    """Against the LIVE corpus (no monkeypatch — the real scaffolder), the check always
    exits 0 (advisory) and reports a real examined_count > 0 (the two packs this ticket's
    sibling fix already annotated: core/75-workers-jobs.md, core/app-audit-log.md)."""
    result = _run_json(REPO, ["file-worker", "saas-skeleton"])

    # NOT `examined_count >= 2`: that passes the moment ANY two packs anywhere gain an
    # applies_to, without either NAMED pack still being reachable — a test whose pass does
    # not depend on the thing it claims to check (D7 test-honesty finding, 2026-08-25).
    for pack in ("core/75-workers-jobs.md", "core/app-audit-log.md"):
        assert pack in result["examined_packs"], (
            f"{pack} is no longer examined — it lost its applies_to, was renamed, or turned "
            f"manual. examined_packs={result['examined_packs']}"
        )
    unreachable = {f["pack"] for f in result.get("findings", [])}
    for pack in ("core/75-workers-jobs.md", "core/app-audit-log.md"):
        assert pack not in unreachable, (
            f"{pack} is EXAMINED but UNREACHABLE — the glob fix this plan landed has "
            f"regressed. findings={result.get('findings')}"
        )
    assert not result.get("unknown_types"), (
        f"a pack declares a type that is not a scaffold type: {result.get('unknown_types')}"
    )


def test_unavailable_scaffolder_is_a_quiet_no_op_not_a_gate_failure(monkeypatch, capsys) -> None:
    """Where the hub scaffolder is unreachable the check must exit 0, saying "0 examined".

    This file is governance-synced to ~46 repos; the scaffolder is HUB-ONLY. The check is
    wired as `run_optional_check(..., warn_only=True)`, and that contract fails the gate on
    ANY non-zero exit — so returning 1 here would turn an ADVISORY row RED on every repo
    that cannot see the hub. Verified live before the fix: the old path returned 1.
    (D7 whole-plan validation finding, 2026-08-25.)

    It exits 0 AND states its denominator. A silent pass is only honest when it says what it
    examined — "0 examined, scaffolder unavailable" can never read as "every pack is fine",
    which is the exact fail-silent-green class this whole plan exists to close.
    """
    import sys

    import check_pack_reachability as cpr
    import pack_layout_audit as pla

    def _unavailable():
        raise RuntimeError("fabrik scaffolder not found — hub only")

    monkeypatch.setattr(pla, "_import_create_project", _unavailable)
    # main() reads sys.argv; under pytest that holds pytest's own args and argparse aborts.
    monkeypatch.setattr(sys, "argv", ["check_pack_reachability.py"])
    pla._emitted_paths_for_type.cache_clear()

    rc = cpr.main()

    assert rc == 0, "an advisory check that cannot ask its question must NOT fail the gate"
    out = capsys.readouterr().out
    assert "0 pack(s) examined" in out, "the denominator must be stated, not implied"
    assert "unavailable" in out.lower(), "it must say WHY it examined nothing"


def test_unavailable_scaffolder_with_explicit_types_is_not_a_crash_and_not_a_pass(
    tmp_path, monkeypatch, capsys
) -> None:
    """`--types` explicitly + no scaffolder must exit 0, report NOTHING VERIFIED, and flag
    no false UNREACHABLE.

    Three defects in one path, all found in the D7 confirming round (finding 13):

    1. main() guarded the scaffolder only on the `--types` DEFAULT branch. Passing `--types`
       — exactly what the reference doc tells a pack author to do to confirm an annotation —
       skipped the guard, the RuntimeError escaped main() uncaught, and `warn_only=True`
       turned that traceback into a HARD gate failure in every repo that cannot see the hub.
    2. The first fix returned `()`, so every annotated pack matched zero paths and was
       reported UNREACHABLE — false findings at fleet scale.
    3. The second fix then printed "OK — every examined pack's claim reaches..." after
       evaluating NOTHING: this plan's own fail-silent-green, committed by the fix for it.

    The honest contract, pinned here: exit 0 (advisory), no findings, and a denominator that
    says nothing was verified.
    """
    import pack_layout_audit as _pla

    def _no_scaffolder(*_a, **_kw):
        raise RuntimeError("fabrik scaffolder not found — simulated project context")

    monkeypatch.setattr(_pla, "_import_create_project", _no_scaffolder)
    _pla._emitted_paths_for_type.cache_clear()

    rules = tmp_path / ".windsurf" / "rules" / "core"
    rules.mkdir(parents=True)
    (rules / "p.md").write_text(
        '---\nactivation: glob\nglobs: ["**/x.py"]\napplies_to: ["file-worker"]\n'
        "description: d\n---\nbody\n"
    )

    argv = sys.argv
    sys.argv = ["check_pack_reachability.py", "--project-root", str(tmp_path),
                "--types", "file-worker"]
    try:
        rc = cpr.main()
    finally:
        sys.argv = argv
        _pla._emitted_paths_for_type.cache_clear()

    out = capsys.readouterr().out
    assert rc == 0, "advisory: an unbuildable type must never fail the gate"
    assert "UNREACHABLE" not in out, "must not condemn a pack it could not evaluate"
    assert "NOT EVALUATED" in out, "must name the type it could not build"
    assert "NOTHING VERIFIED" in out, "0 verified is not OK — it is an unasked question"
    assert "OK —" not in out


def test_unevaluable_type_is_not_reported_unreachable_and_not_counted_verified(
    tmp_path, monkeypatch, capsys
) -> None:
    """A pack claiming an UNBUILDABLE type must be skipped, not condemned — and the summary
    must not claim it was verified.

    Two defects, both live before this (D7 round 6, finding 14):

    1. The None sentinel was applied to the RuntimeError branch but NOT to the
       NotImplementedError branch, which still returned `()`. So a pack claiming
       `wordpress` was printed as "globs match ZERO paths that type emits" — when the truth
       is that the type cannot be built here at all. A FALSE finding, at fleet scale.
    2. The summary then said "every EXAMINED pack's claim reaches at least one emitted
       path" while 2 were examined and only 1 verified. The parenthetical was honest; the
       sentence was not.
    """
    import pack_layout_audit as _pla

    _pla._emitted_paths_for_type.cache_clear()
    rules = tmp_path / ".windsurf" / "rules" / "core"
    rules.mkdir(parents=True)
    (rules / "good.md").write_text(
        '---\nactivation: glob\nglobs: ["**/worker/**"]\napplies_to: ["file-worker"]\n'
        "description: g\n---\nbody\n"
    )
    (rules / "wp.md").write_text(
        '---\nactivation: glob\nglobs: ["**/nothing-xyz.php"]\napplies_to: ["wordpress"]\n'
        "description: w\n---\nbody\n"
    )

    argv = sys.argv
    sys.argv = ["check_pack_reachability.py", "--project-root", str(tmp_path),
                "--types", "file-worker", "wordpress"]
    try:
        rc = cpr.main()
    finally:
        sys.argv = argv
        _pla._emitted_paths_for_type.cache_clear()

    out = capsys.readouterr().out
    assert rc == 0
    assert "wp.md" not in out.split("NOT EVALUATED")[-1].split("Examined")[0] or \
        "UNREACHABLE: core/wp.md" not in out, "must not condemn a pack whose type is unbuildable"
    assert "UNREACHABLE" not in out, "an unbuildable type yields no findings at all"
    assert "NOT EVALUATED: scaffold type 'wordpress'" in out
    assert "1 of 2 examined pack(s) verified" in out, (
        "the summary must state verified-of-examined, not claim every examined pack passed"
    )


def test_pack_count_and_claim_pair_count_are_reported_separately(tmp_path, monkeypatch) -> None:
    """`examined_count` counts PACKS; `claim_pairs` counts (pack, type) PAIRS. Both reported.

    `_examined_packs` uses `any(t in types for t in applies_to)` — one row per PACK — while
    `audit_layout` loops per type and evaluates `scaffold_type in applies_to` — one per
    PAIR. An earlier docstring claimed the former "mirrors the exact condition" of the
    latter; it does not, and that was the FIFTH false claim in this change.

    They coincide for a single-type pack and DIVERGE when a pack claims two types and only
    one is evaluable: 1 pack examined, 2 pairs considered, 1 skipped. Reporting only the
    pack count would understate what was actually asked — the same denominator dishonesty
    this whole plan exists to close, one level down. (D7 round 8.)
    """
    import pack_layout_audit as _pla

    _pla._emitted_paths_for_type.cache_clear()
    rules = tmp_path / ".windsurf" / "rules" / "core"
    rules.mkdir(parents=True)
    (rules / "two.md").write_text(
        '---\nactivation: glob\nglobs: ["**/worker/**"]\n'
        'applies_to: ["file-worker", "wordpress"]\ndescription: t\n---\nbody\n'
    )
    try:
        result = _run_json(tmp_path, ["file-worker", "wordpress"])
    finally:
        _pla._emitted_paths_for_type.cache_clear()

    assert result["examined_count"] == 1, "one PACK declares a checked type"
    assert result["claim_pairs"] == 2, "but it makes TWO (pack, type) claims"
    assert result["unevaluable_types"] == ["wordpress"]
    assert result["examined_count"] != result["claim_pairs"], (
        "this fixture exists to catch the two counts being collapsed back into one"
    )


def test_duplicate_applies_to_entries_count_once(tmp_path, monkeypatch) -> None:
    """A repeated `applies_to` entry is ONE distinct claim, not two.

    `applies_to: [file-worker, file-worker]` reported `claim_pairs=2` and listed the pack
    twice in `cleared`. A denominator OVER-count — introduced one round after, and by the
    fix for, a denominator UNDER-count. Both directions of the same mistake, in the same
    number, in consecutive rounds. (D7 round 10.)
    """
    import pack_layout_audit as _pla

    _pla._emitted_paths_for_type.cache_clear()
    rules = tmp_path / ".windsurf" / "rules" / "core"
    rules.mkdir(parents=True)
    (rules / "dup.md").write_text(
        '---\nactivation: glob\nglobs: ["**/worker/**"]\n'
        "applies_to: [file-worker, file-worker]\ndescription: d\n---\nbody\n"
    )
    try:
        result = _run_json(tmp_path, ["file-worker"])
    finally:
        _pla._emitted_paths_for_type.cache_clear()

    assert result["examined_count"] == 1
    assert result["claim_pairs"] == 1, "a duplicate entry is one claim, not two"
    assert not result["findings"]


def test_masked_scaffolder_failure_is_reported_not_silent(tmp_path, monkeypatch, capsys) -> None:
    """The broad `except` must RECORD what it swallowed, not hide it.

    `_emitted_paths_for_type` catches Exception deliberately: under `warn_only=True` any
    escaping exception reds the gate in ~46 repos, and for this check every failure genuinely
    means "cannot evaluate". But an earlier comment justified the breadth by claiming
    `_scaffold_and_walk` "only scaffolds and walks, so there is no unrelated logic for a
    broad except to mask" — FALSE. `create_project` runs git init, git checkout -b, template
    copying and a pre-commit install; a real bug in any of them is swallowed here.

    A masked failure you can SEE is an accepted trade; one you cannot see is the defect this
    plan exists to close. So the exception type and message are recorded and printed.
    (D7 round 12.)
    """
    import pack_layout_audit as _pla

    _pla._emitted_paths_for_type.cache_clear()
    _pla._UNEVALUABLE_REASONS.clear()
    rules = tmp_path / ".windsurf" / "rules" / "core"
    rules.mkdir(parents=True)
    (rules / "wp.md").write_text(
        '---\nactivation: glob\nglobs: ["**/x.php"]\napplies_to: [wordpress]\n'
        "description: w\n---\nbody\n"
    )

    argv = sys.argv
    sys.argv = ["check_pack_reachability.py", "--project-root", str(tmp_path),
                "--types", "wordpress"]
    try:
        rc = cpr.main()
    finally:
        sys.argv = argv
        _pla._emitted_paths_for_type.cache_clear()
        _pla._UNEVALUABLE_REASONS.clear()

    out = capsys.readouterr().out
    assert rc == 0
    assert "NOT EVALUATED" in out
    assert "NotImplementedError" in out, (
        "the swallowed exception TYPE must appear — a broad except that reports nothing is "
        "indistinguishable from the failure never happening"
    )


def test_duplicate_types_argument_yields_one_finding(tmp_path, monkeypatch) -> None:
    """`--types X X` must produce ONE finding, matching the claim count.

    Duplicates in `--types` made `audit_layout` iterate the type twice and append the SAME
    Finding twice, while `known = set(types)` counted the claim once: findings=2 against
    claim_pairs=1. Content and count disagreeing is the denominator integrity this check
    exists to enforce, one level further out. Deduped at the input boundary so a future call
    site cannot reintroduce it. (D7 round 13.)
    """
    import pack_layout_audit as _pla

    _pla._emitted_paths_for_type.cache_clear()
    rules = tmp_path / ".windsurf" / "rules" / "core"
    rules.mkdir(parents=True)
    (rules / "p.md").write_text(
        '---\nactivation: glob\nglobs: ["**/zzz-nope.py"]\napplies_to: [file-worker]\n'
        "description: p\n---\nbody\n"
    )
    try:
        result = _run_json(tmp_path, ["file-worker", "file-worker"])
    finally:
        _pla._emitted_paths_for_type.cache_clear()

    assert len(result["findings"]) == 1, "a repeated --types value is one type, not two"
    assert result["claim_pairs"] == 1
    assert len(result["findings"]) == result["claim_pairs"], "content and count must agree"


def test_unknown_type_is_judged_against_the_registry_not_the_types_subset(
    tmp_path, monkeypatch, capsys
) -> None:
    """"Unknown" must mean NOT A SCAFFOLD TYPE — never "not in the --types I was given".

    The round-6 unknown-type fix compared each claim to `known = set(types)`, the SUBSET
    being checked. So a pack claiming a perfectly valid type that simply was not in this
    run's `--types` got accused:

        $ check_pack_reachability --types file-worker
        UNKNOWN TYPE: core/wp.md declares applies_to: 'wordpress', which is not a scaffold type

    Flatly false — `wordpress` is in SCAFFOLD_TYPES. A check built to stop false claims was
    emitting one, and the fix for a fail-silent-green defect had introduced a fail-LOUD-wrong
    one. Now judged against the real registry; where the registry is unreachable (a synced
    project) the question is unaskable and simply is not answered. (D7 round 16.)
    """
    import pack_layout_audit as _pla

    _pla._emitted_paths_for_type.cache_clear()
    rules = tmp_path / ".windsurf" / "rules" / "core"
    rules.mkdir(parents=True)
    (rules / "wp.md").write_text(
        '---\nactivation: glob\nglobs: ["**/x.php"]\napplies_to: [wordpress]\n'
        "description: w\n---\nbody\n"
    )
    (rules / "typo.md").write_text(
        '---\nactivation: glob\nglobs: ["**/y.py"]\napplies_to: [saas_skeleton]\n'
        "description: t\n---\nbody\n"
    )

    argv = sys.argv
    sys.argv = ["check_pack_reachability.py", "--project-root", str(tmp_path),
                "--types", "file-worker"]
    try:
        rc = cpr.main()
    finally:
        sys.argv = argv
        _pla._emitted_paths_for_type.cache_clear()

    out = capsys.readouterr().out
    assert rc == 0
    assert "'wordpress', which is not a scaffold type" not in out, (
        "a VALID type outside the --types subset must never be called unknown"
    )
    assert "'saas_skeleton'" in out, "a genuine typo must still be caught"


def test_corpus_is_parsed_exactly_once_per_run(tmp_path, monkeypatch) -> None:
    """One `_packs_with_meta` call per run — three independent reads can see three states.

    Round 8 collapsed two calls into one; the unevaluable-types scan added at round 12 then
    made it THREE, and `_examined_packs` had always done its own. Same shape as the
    LOCATE/RUN guard asymmetry: fix one instance of a duplication class and leave — or
    create — the others. Counting the calls is the only way to keep it at one, since the
    symptom (a torn read between two parses) needs a concurrent corpus change to appear.
    (D7 round 19.)
    """
    import pack_layout_audit as _pla

    _pla._emitted_paths_for_type.cache_clear()
    rules = tmp_path / ".windsurf" / "rules" / "core"
    rules.mkdir(parents=True)
    (rules / "p.md").write_text(
        '---\nactivation: glob\nglobs: ["**/worker/**"]\napplies_to: [file-worker]\n'
        "description: p\n---\nbody\n"
    )

    calls = {"n": 0}
    real = _pla._packs_with_meta

    def counting(root):
        calls["n"] += 1
        return real(root)

    monkeypatch.setattr(_pla, "_packs_with_meta", counting)
    try:
        _run_json(tmp_path, ["file-worker"])
    finally:
        _pla._emitted_paths_for_type.cache_clear()

    assert calls["n"] == 1, (
        f"the corpus was parsed {calls['n']}x in one run; thread the single parse to every "
        "consumer instead of re-reading"
    )
