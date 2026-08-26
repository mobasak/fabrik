"""pack_layout_audit — a pack CLAIMING a scaffold type but matching zero paths that
type actually emits is a silently-inert governance surface (transdoc: 19 dead frontend
calls + 14 orphan endpoints + an empty beat loop, gate green throughout — because
`core/75-workers-jobs.md` and `core/app-audit-log.md` matched zero real paths).

Fixtures never touch the LIVE pack corpus (which changes under this test) — every pack
is synthesized under `tmp_path/.windsurf/rules/...`, and `_emitted_paths_for_type` is
monkeypatched to a fixed path tuple per scaffold type so no test invokes the real
`fabrik` scaffolder (slow, and would silently start depending on template drift).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))
sys.path.insert(0, str(REPO / "scripts"))

import pack_layout_audit as pla  # noqa: E402


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
    """Stand in for `_emitted_paths_for_type` — no real scaffold call, no cache pollution
    across tests (the real function is `functools.lru_cache`d at module scope; patching
    the whole callable, not the cache, sidesteps that entirely)."""
    monkeypatch.setattr(pla, "_emitted_paths_for_type", lambda t: mapping.get(t, ()))


def test_applicability_comes_from_applies_to_not_globs(tmp_path, monkeypatch):
    """Rule 1: a pack's applicability is its declared `applies_to:`, never derived from
    whether its globs happen to match. Two packs, IDENTICAL non-matching globs:
    one declares applies_to=["file-worker"] (claims the type -> Finding), the other
    declares applies_to=[] (claims nothing -> silent, even though the glob is just as
    dead). If applicability were derived from the globs, both would be indistinguishable
    (glob-matches-nothing) and the rule would collapse to "every non-matching glob is
    a finding" — exactly the circularity the ticket forbids."""
    _write_pack(
        tmp_path,
        "core/claims-nothing.md",
        globs=["**/totally-nonexistent-xyz/**"],
        applies_to=[],
    )
    _write_pack(
        tmp_path,
        "core/claims-file-worker.md",
        globs=["**/totally-nonexistent-xyz/**"],
        applies_to=["file-worker"],
    )
    _patch_emitted(monkeypatch, {"file-worker": ("worker/main.py", "Dockerfile")})

    findings = pla.audit_layout(tmp_path, ["file-worker"])

    packs_flagged = {f.pack for f in findings}
    assert "core/claims-file-worker.md" in packs_flagged
    assert "core/claims-nothing.md" not in packs_flagged
    assert len(findings) == 1


def test_manual_activation_excluded_entirely(tmp_path, monkeypatch):
    """Rule 2: `activation: manual` packs are never reported, never counted inert, even
    when they explicitly claim a type via applies_to and their globs match nothing.
    Mirrors the four real `00-domain-*` packs (saas/00-domain-saas.md lines 1-20:
    NOT glob-activated on purpose, loaded by path, not by touching a file)."""
    _write_pack(
        tmp_path,
        "core/manual-pack.md",
        globs=["**/never-matches-anything/**"],
        activation="manual",
        applies_to=["file-worker"],
    )
    _patch_emitted(monkeypatch, {"file-worker": ("worker/main.py",)})

    findings = pla.audit_layout(tmp_path, ["file-worker"])

    assert findings == []


def test_one_row_per_claimed_pack_type_pair(tmp_path, monkeypatch):
    """Rule 3: a pack claiming TWO types gets independently judged per type — one row
    for the type its globs miss, none for the type they hit. Never per-glob (the pack
    below carries two globs; only the per-TYPE aggregate verdict is reported)."""
    _write_pack(
        tmp_path,
        "core/two-types.md",
        globs=["**/worker.py", "**/worker/**"],
        applies_to=["file-worker", "node-api"],
    )
    _patch_emitted(
        monkeypatch,
        {
            # file-worker's real scaffold emits a `worker/` dir — `_tree_paths` lists
            # directory entries too (real os.walk dirnames), so "worker" itself (not
            # just its files) is a genuine emitted path; "**/worker/**" matches it.
            "file-worker": ("worker", "worker/main.py", "worker/logger.py", "Dockerfile"),
            # node-api's scaffold has no worker/job files at all — neither glob hits.
            "node-api": ("src/index.js", "src/logger.js", "package.json"),
        },
    )

    findings = pla.audit_layout(tmp_path, ["file-worker", "node-api"])

    by_type = {f.scaffold_type: f for f in findings}
    assert "file-worker" not in by_type, "one of its two globs matched — not inert for this type"
    assert "node-api" in by_type, "neither glob matches anything node-api emits — inert for this type"
    assert len(findings) == 1
    assert by_type["node-api"].pack == "core/two-types.md"
    assert set(by_type["node-api"].globs) == {"**/worker.py", "**/worker/**"}


def test_no_applies_to_field_claims_nothing(tmp_path, monkeypatch):
    """A pack with no `applies_to:` at all (the corpus state BEFORE this ticket's fix)
    claims zero types and can never produce a Finding — the exact fail-silent-green gap
    the ticket calls out: "without at least one pack declaring applies_to, the check
    ships asking nothing.\""""
    _write_pack(tmp_path, "core/legacy-no-claim.md", globs=["**/workers/**"], applies_to=None)
    _patch_emitted(monkeypatch, {"file-worker": ("worker/main.py",)})

    findings = pla.audit_layout(tmp_path, ["file-worker"])

    assert findings == []


def test_real_corpus_after_fix_has_no_findings_for_declared_types():
    """Integration check against the ACTUAL two packs this ticket fixes AND the REAL
    scaffolder (no monkeypatch here — the slow, honest path): `core/75-workers-jobs.md`
    must declare `applies_to` including `file-worker` and match something a fresh
    `file-worker` scaffold emits; `core/app-audit-log.md` must declare `applies_to`
    including `saas-skeleton` and match something a fresh `saas-skeleton` scaffold
    emits. RED before the frontmatter fix (no `applies_to:` on either pack -> the pack
    claims nothing -> this assertion fails because the FIRST assert below — that the
    pack actually declared the type — is what catches it); GREEN after."""
    packs = {rel: (globs, activation, applies_to) for rel, globs, activation, applies_to in pla._packs_with_meta(REPO)}

    # A bare packs[...] raises KeyError, which reads as a test bug rather than the real
    # cause (pack renamed/removed). Name the cause. (D7 test-honesty finding, 2026-08-25.)
    for required in ("core/75-workers-jobs.md", "core/app-audit-log.md"):
        assert required in packs, (
            f"{required} is not in the corpus — renamed or removed? This plan's glob fix "
            f"targets it by name, so the fix is now untested. corpus has {len(packs)} packs."
        )

    globs_75, _activation_75, applies_to_75 = packs["core/75-workers-jobs.md"]
    assert "file-worker" in applies_to_75, "75-workers-jobs.md must declare applies_to: [..., \"file-worker\", ...]"

    globs_audit, _activation_audit, applies_to_audit = packs["core/app-audit-log.md"]
    assert "saas-skeleton" in applies_to_audit, "app-audit-log.md must declare applies_to: [..., \"saas-skeleton\", ...]"

    findings = pla.audit_layout(REPO, ["file-worker", "saas-skeleton"])

    flagged = {(f.pack, f.scaffold_type) for f in findings}
    assert ("core/75-workers-jobs.md", "file-worker") not in flagged
    assert ("core/app-audit-log.md", "saas-skeleton") not in flagged


def test_applies_to_accepts_bare_yaml_items() -> None:
    """`applies_to: [file-worker]` is legal YAML and MUST parse.

    A quotes-only regex yielded [] for the bare form, so the pack was skipped and could
    never produce a Finding — this check's own fail-silent-green, inside the check built to
    close that class. An author writing correct YAML would have had their declaration
    silently ignored (review finding, 2026-08-25).
    """
    from pack_layout_audit import _parse_extra_frontmatter

    for frontmatter, expected in (
        ('applies_to: ["file-worker"]', ["file-worker"]),
        ("applies_to: ['file-worker']", ["file-worker"]),
        ("applies_to: [file-worker]", ["file-worker"]),                      # the bare form
        ("applies_to: [file-worker, saas-skeleton]", ["file-worker", "saas-skeleton"]),
        ('applies_to: [file-worker, "saas-skeleton"]', ["file-worker", "saas-skeleton"]),
        ("applies_to: []", []),
    ):
        activation, applies_to = _parse_extra_frontmatter(
            f"---\nactivation: glob\n{frontmatter}\n---\n"
        )
        assert activation == "glob"
        assert applies_to == expected, f"{frontmatter!r} parsed to {applies_to!r}"


def test_activation_regex_is_line_anchored() -> None:
    """`activation:` inside a description must NOT be read as the pack's activation.

    Raised as a candidate in review and REFUTED here rather than argued: the regex is
    line-anchored under MULTILINE, so a mid-line occurrence cannot collide. Pinned so a
    future loosening of the anchor is caught.
    """
    from pack_layout_audit import _parse_extra_frontmatter

    activation, applies_to = _parse_extra_frontmatter(
        '---\nactivation: glob\n'
        'description: "Uses activation: manual strategy internally"\n'
        'applies_to: ["file-worker"]\n---\n'
    )
    assert activation == "glob"
    assert applies_to == ["file-worker"]


def test_applies_to_accepts_yaml_block_sequence() -> None:
    """The BLOCK-SEQUENCE form must parse — it is what a YAML author writes for a list.

        applies_to:
          - file-worker
          - saas-skeleton

    The flow-style regex silently yielded [] for it, so such a pack was skipped, never
    counted, and the run printed "no pack declares applies_to yet" — flatly false. Same
    fail-silent-green class as the quotes-only bug, in a second legal form that fix did
    not cover (D7 whole-plan validation, 2026-08-25).
    """
    from pack_layout_audit import _parse_extra_frontmatter

    activation, applies_to = _parse_extra_frontmatter(
        "---\nactivation: glob\napplies_to:\n  - file-worker\n  - saas-skeleton\n---\n"
    )
    assert activation == "glob"
    assert applies_to == ["file-worker", "saas-skeleton"]


def test_unscaffoldable_type_yields_no_paths_instead_of_crashing() -> None:
    """A registry type with no scaffolder must contribute 0 paths, never raise.

    `wordpress` is in SCAFFOLD_TYPES (which the docs tell pack authors to choose from)
    but `create_project` raises NotImplementedError for it. Uncaught, that propagated out
    of an ADVISORY check — and warn_only fails the gate on ANY non-zero exit, so one pack
    annotating that type would have hard-failed the gate in ~46 repos.
    """
    from pack_layout_audit import _emitted_paths_for_type

    # cache_clear FIRST: _emitted_paths_for_type is @functools.cache'd, and a sibling test
    # that monkeypatched it can leave a stale entry. Proven order-dependent — this test
    # passed forward and FAILED in reverse until the clear was added. (D7 round 6.)
    _emitted_paths_for_type.cache_clear()

    # None, not (): "cannot evaluate this type" is NOT "evaluated, emits nothing". Returning
    # () made every pack claiming an unbuildable type report UNREACHABLE — a false finding
    # at fleet scale (finding 14). The distinction is the whole point of the sentinel.
    assert _emitted_paths_for_type("wordpress") is None


def test_satisfying_path_returns_the_evidence_not_just_a_bool() -> None:
    """A clear must be explainable: return WHICH path satisfied the glob.

    The denominator over-states reachability — a fresh scaffold carries copied hub
    boilerplate (`Dockerfile`, `libs/subagents`, `db/schema.sql`), so a pack can clear
    without matching any type-specific source. Measured for `docusaurus`:
    `core/30-ops.md` clears on `Dockerfile`, `core/62-using-subagents.md` on
    `libs/subagents` — the latter satisfying its own claim with its own copied file.

    A bare bool hides that; the path reveals it. (D7 whole-plan validation, 2026-08-25.)
    """
    from pack_layout_audit import _satisfying_path

    paths = ("worker", "worker/main.py", "Dockerfile")
    assert _satisfying_path(paths, ["**/worker.py"]) is None
    assert _satisfying_path(paths, ["**/worker/**"]) == "worker"
    assert _satisfying_path(paths, ["**/main.py"]) == "worker/main.py"
    # a boilerplate-only clear is still a clear — but now it is VISIBLE as one
    assert _satisfying_path(paths, ["**/Dockerfile"]) == "Dockerfile"


def test_fixtures_cover_the_shapes_the_real_denominator_contains(tmp_path, monkeypatch) -> None:
    """Feed the audit the path shapes every OTHER fixture omits.

    The hermetic fixtures elsewhere in this file hand-write tuples like
    ("worker", "worker/main.py", "Dockerfile") — no copied hub boilerplate, no excluded
    directory, no wildcard-only glob. That is exactly why the denominator contamination
    and the wildcard asymmetry survived the suite: no test ever fed the engine a shape
    that could expose them. Fixtures that mirror the implementation's own blind spots
    prove only that it is self-consistent. (D7 test-honesty finding, 2026-08-25.)

    Pins the three shapes as they ACTUALLY behave, so a future change to any of them is a
    deliberate decision rather than a silent drift.
    """
    from pack_layout_audit import _matches_any_emitted, _satisfying_path

    # 1. BOILERPLATE-ONLY clear — real, and now visible via the satisfying path.
    boilerplate = ("Dockerfile", "compose.yaml", "libs/subagents", "db/schema.sql")
    assert _matches_any_emitted(boilerplate, ["**/Dockerfile"]) is True
    assert _satisfying_path(boilerplate, ["**/Dockerfile"]) == "Dockerfile"

    # 2. WILDCARD-ONLY globs — the asymmetry: `**/` is non-matching, `/**` and `**` match
    #    everything. Documented in _matches_any_emitted; pinned here.
    assert _matches_any_emitted(boilerplate, ["**/"]) is False
    assert _matches_any_emitted(boilerplate, ["/**"]) is True
    assert _matches_any_emitted(boilerplate, ["**"]) is True

    # 3. An EXCLUDED-dir glob can never match, because _tree_paths prunes it during the
    #    walk — the false-INERT direction of the contamination.
    import rules_match

    assert "templates" in rules_match._EXCLUDE
    walked = rules_match._tree_paths(tmp_path)
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "welcome_email.html").write_text("x")
    rules_match._tree_paths.cache_clear()
    walked = rules_match._tree_paths(tmp_path)
    assert not any("templates" in w for w in walked), (
        "templates/ is pruned, so **/templates/*email* can never match — a pack globbing "
        "it would be falsely reported INERT"
    )


def test_both_helpers_tolerate_the_cannot_evaluate_sentinel() -> None:
    """`_matches_any_emitted` and `_satisfying_path` must agree on the None sentinel.

    None means "cannot evaluate this type here" (no scaffolder), distinct from () meaning
    "evaluated, emits nothing". `_satisfying_path` already returned None for it while
    `_matches_any_emitted` raised TypeError — latent, since every call site guards, but two
    sibling helpers with different None-tolerance is the exact trap that produced finding
    13's cascade: a fix returned () where None was meant and every annotated pack was
    condemned UNREACHABLE across 46 repos. "Cannot evaluate" is never "matched".
    """
    from pack_layout_audit import _matches_any_emitted, _satisfying_path

    assert _matches_any_emitted(None, ["**/anything.py"]) is False
    assert _satisfying_path(None, ["**/anything.py"]) is None
    # and () still means "evaluated, matched nothing" — NOT the same input, same answer
    assert _matches_any_emitted((), ["**/anything.py"]) is False
    assert _satisfying_path((), ["**/anything.py"]) is None


def test_unknown_scaffold_type_does_not_crash_the_advisory_check() -> None:
    """`create_project` rejecting an unknown type must yield the sentinel, never a crash.

    `--types` is USER-SUPPLIED and is never validated against the registry before use, so
    `create_project` raises ValueError for a bogus value. Uncaught, that escaped an ADVISORY
    check as a non-zero exit, and `warn_only=True` fails the gate on ANY non-zero exit —
    the third instance of "an uncaught exception escapes an advisory check" in this plan
    (cf. the wordpress NotImplementedError and the explicit-`--types` RuntimeError).

    A round-6 finder examined this exact path and DISMISSED it, reasoning that
    "audit_layout only calls this for types in SCAFFOLD_TYPES, pre-validated". That premise
    is false. A direct probe crashed it. (D7 round 7, finding 16.)
    """
    from pack_layout_audit import _emitted_paths_for_type

    _emitted_paths_for_type.cache_clear()
    try:
        assert _emitted_paths_for_type("not-a-real-scaffold-type") is None
    finally:
        _emitted_paths_for_type.cache_clear()


def test_applies_to_accepts_every_legal_yaml_shape() -> None:
    """All four ways a human writes `applies_to` must parse; absent/empty must stay empty.

    This parser dropped a legal form to [] THREE separate times, and each time the pack was
    skipped, never counted, and the run reported OK — the exact fail-silent-green defect the
    check exists to close, in the check's own parser:

      * quotes-only regex   -> `[file-worker]` (unquoted) dropped        (per-ticket review)
      * flow-style only     -> block sequence dropped                    (D7 round 4)
      * list forms only     -> bare/quoted SCALAR dropped                (D7 round 9)

    Enumerating every shape in one table is the fix for the CLASS, not the third instance:
    a fourth form now has an obvious place to be added, and a regression in any one of them
    fails here rather than silently returning [].
    """
    from pack_layout_audit import _parse_extra_frontmatter

    def parsed(body: str) -> list[str]:
        return _parse_extra_frontmatter(f"---\nactivation: glob\n{body}\n---\n")[1]

    # every form that MUST yield the claim
    assert parsed("applies_to: [file-worker]") == ["file-worker"]
    assert parsed('applies_to: ["file-worker", "saas-skeleton"]') == ["file-worker", "saas-skeleton"]
    assert parsed("applies_to: [file-worker, saas-skeleton]") == ["file-worker", "saas-skeleton"]
    assert parsed("applies_to:\n  - file-worker\n  - saas-skeleton") == ["file-worker", "saas-skeleton"]
    assert parsed("applies_to: file-worker") == ["file-worker"], "bare scalar is legal YAML"
    assert parsed('applies_to: "file-worker"') == ["file-worker"], "quoted scalar is legal YAML"

    # and every form that MUST yield nothing — absence is opt-out, not a parse failure
    assert parsed("description: x") == []
    assert parsed("applies_to: []") == []


def test_any_scaffolder_failure_is_unevaluable_not_a_gate_failure(monkeypatch) -> None:
    """ANY exception while probing a scaffold means "cannot evaluate" — never a traceback.

    This guard was patched three times, one exception type at a time:
      NotImplementedError  — `wordpress` is in SCAFFOLD_TYPES with no scaffolder  (round 4)
      RuntimeError         — explicit `--types` on a project without the hub      (round 5)
      ValueError           — a bogus `--types` value create_project rejects       (round 7)
    and round 11 then pointed at FileNotFoundError from a missing template. Enumerating
    exception types is the same instance-by-instance patching that let the `applies_to`
    parser drop three legal YAML forms in a row, so the guard now catches the CLASS.

    Why that is safe rather than sloppy: this check is ADVISORY and wired `warn_only=True`,
    which fails the gate on ANY non-zero exit — so an escaping exception reddens ~46 repos,
    while a swallowed one costs only an honest "NOT EVALUATED". `_scaffold_and_walk` does
    nothing but scaffold and walk, so there is no unrelated logic for the broad except to
    hide. This test asserts the CLASS by using an exception type nobody enumerated.
    """
    import pack_layout_audit as _pla

    def _explode(*_a, **_kw):
        def _cp(*_aa, **_kk):
            raise FileNotFoundError("scaffold template missing — a type nobody enumerated")

        return _cp

    monkeypatch.setattr(_pla, "_import_create_project", _explode)
    _pla._emitted_paths_for_type.cache_clear()
    try:
        assert _pla._emitted_paths_for_type("file-worker") is None
    finally:
        _pla._emitted_paths_for_type.cache_clear()


def test_broken_scaffolder_import_is_unevaluable_not_a_gate_failure(monkeypatch) -> None:
    """A scaffolder that EXISTS but fails to import must yield the sentinel, not a crash.

    Two guards wrap the scaffolder: locating it (`_import_create_project`) and running it
    (`_scaffold_and_walk`). Round 11 widened the RUN guard to catch the class; the LOCATE
    guard stayed narrow at `except RuntimeError` — by oversight, not design. But
    `from src.fabrik.scaffold import create_project` raises ImportError when the module is
    present and a transitive dependency is missing, and that escaped uncaught -> non-zero
    exit -> `warn_only=True` reds the gate in ~46 repos.

    Fifth instance of "an uncaught exception escapes an advisory check", and the first at
    the LOCATE step rather than the RUN step — which is why widening one guard did not cover
    it. (D7 round 15.)
    """
    import pack_layout_audit as _pla

    def _broken_import(*_a, **_kw):
        raise ImportError("no module named 'somedep' — scaffolder present but unimportable")

    monkeypatch.setattr(_pla, "_import_create_project", _broken_import)
    _pla._emitted_paths_for_type.cache_clear()
    _pla._UNEVALUABLE_REASONS.clear()
    try:
        assert _pla._emitted_paths_for_type("file-worker") is None
        assert "ImportError" in _pla._UNEVALUABLE_REASONS["file-worker"], (
            "the swallowed import failure must be reportable, not silent"
        )
    finally:
        _pla._emitted_paths_for_type.cache_clear()
        _pla._UNEVALUABLE_REASONS.clear()


def test_unparseable_applies_to_is_flagged_not_swallowed() -> None:
    """An `applies_to:` line no form can parse must be REPORTED, not silently emptied.

    `applies_to: [file-worker` (missing bracket) returned `[]` — byte-identical to a pack
    that never declared anything. So a typo made the pack silently unexamined while the run
    reported OK. FOURTH shape of this same fail-silent-green defect in this one parser
    (quotes-only, flow-only, list-only, and now malformed), which is why the fix is a
    distinguishable sentinel rather than another accepted spelling.

    Also strips stray brackets, so `applies_to: file-worker]` yields the real type instead of
    carrying `file-worker]` forward as a phantom. (D7 round 17.)
    """
    from pack_layout_audit import _MALFORMED_SENTINEL, _parse_extra_frontmatter

    def parsed(body: str) -> list[str]:
        return _parse_extra_frontmatter(f"---\nactivation: glob\n{body}\n---\n")[1]

    assert parsed("applies_to: [file-worker") == [_MALFORMED_SENTINEL], "no closing bracket"
    assert parsed("applies_to:") == [_MALFORMED_SENTINEL], "key present, value absent"
    assert parsed("applies_to: file-worker]") == ["file-worker"], "stray bracket stripped"

    # absence is a legitimate opt-out and must stay distinguishable from a broken line
    assert parsed("description: x") == []
