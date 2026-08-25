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
