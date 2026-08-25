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

    assert _emitted_paths_for_type("wordpress") == ()


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
