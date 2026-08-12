"""Behavior-Contract tests for the Fabrik capability-catalog generator (plan-2 Phase A).

Covers the risk-ordered behaviors: fail-soft broken probe (+ whole-surface guard), retired/manual
detection, the 8-key JSON schema, and the llms.txt output format.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "generate_capability_index",
    Path(__file__).resolve().parent.parent / "scripts" / "generate_capability_index.py",
)
gci = importlib.util.module_from_spec(_SPEC)
sys.modules["generate_capability_index"] = gci
_SPEC.loader.exec_module(gci)  # type: ignore

REPO = Path(__file__).resolve().parent.parent


# --- Behavior 1: a probe that errors → broken, generator does NOT crash (fail-soft) -------------------


def test_broken_probe_flagged_not_crashing() -> None:
    """A --help that exits non-zero → False (→ broken), and probing never raises."""
    # a real python invoking a non-existent module exits non-zero, not raises → broken
    assert gci._probe_help(["-m", "fabrik.cli", "definitely-not-a-verb-xyz"]) is False
    # a probe against a bogus interpreter is caught (OSError) → False, not a crash
    assert gci._probe_help(["-m", "x"], python="/nonexistent/python") is False


def test_build_catalog_completes_over_real_repo_with_broken_entries_isolated() -> None:
    """build_catalog runs to completion; any broken entry is flagged + excluded from the ok set."""
    catalog = gci.build_catalog(REPO)
    assert len(catalog) >= 250, len(catalog)
    ok = [c for c in catalog if c["status"] == "ok"]
    broken = [c for c in catalog if c["status"] == "broken"]
    assert ok, "at least the registrar/rules surfaces must be ok"
    for b in broken:
        assert b not in ok


# --- Behavior 7: whole-surface-broken → raise (not a silently-all-broken catalog) --------------------


def test_whole_surface_broken_raises(monkeypatch) -> None:
    # Force EVERY surface healthy except driver, so the raise can ONLY come from the driver surface
    # (else `cli` — which runs first — could preempt and the test would pass for the wrong reason).
    for kind in gci.KINDS:
        healthy = [gci._rec(f"{kind}-ok", kind, "", f"use {kind}", "ok")]
        monkeypatch.setitem(gci._ENUMERATORS, kind, (lambda h: lambda _root: h)(healthy))
    monkeypatch.setitem(
        gci._ENUMERATORS,
        "driver",
        lambda _root: [gci._rec("x", "driver", "", "import x", "broken")],
    )
    with pytest.raises(RuntimeError, match=r"whole-surface-broken.*driver"):
        gci.build_catalog(REPO)


def test_partial_broken_does_not_raise(monkeypatch) -> None:
    """A broken entry ALONGSIDE a healthy one (not 100% broken) → no raise, both recorded."""

    def mixed(_root):
        return [
            gci._rec("bad", "driver", "", "import bad", "broken"),
            gci._rec("good", "driver", "", "import good", "ok"),
        ]

    monkeypatch.setitem(gci._ENUMERATORS, "driver", mixed)
    cat = gci.build_catalog(REPO)
    drivers = [c for c in cat if c["kind"] == "driver"]
    assert {c["status"] for c in drivers} == {"broken", "ok"}


# --- Behavior 2/3: retired + manual detection (header markers) ---------------------------------------


def test_retired_marker_detected(tmp_path) -> None:
    f = tmp_path / "old_tool.py"
    f.write_text("# DEPRECATED — superseded by new_tool.py\nprint('x')\n")
    status, _ = gci._classify_script(f)
    assert status == "retired"


def test_manual_marker_detected(tmp_path) -> None:
    f = tmp_path / "danger.sh"
    f.write_text("#!/usr/bin/env bash\n# CATALOG-MANUAL — mutates prod, no --help\nrm -rf /x\n")
    status, _ = gci._classify_script(f)
    assert status == "manual"


def test_script_with_no_safe_probe_is_manual_not_broken(tmp_path) -> None:
    """A script with no --help/argparse/main guard can't be auto-verified → manual, not broken."""
    f = tmp_path / "bare.sh"
    f.write_text("#!/usr/bin/env bash\necho hi\n")
    status, _ = gci._classify_script(f)
    assert status == "manual"


# --- Behavior 6: capabilities.json is valid against the 8-key schema ---------------------------------


def test_json_schema_9_keys(tmp_path) -> None:
    gci.main(REPO, out_dir=tmp_path)
    payload = json.loads((tmp_path / "capabilities.json").read_text())
    assert set(payload) == {"generated_at", "capabilities"}
    assert payload["capabilities"]
    keys = {"name", "kind", "summary", "invoke", "status", "owner", "defects", "doc_link",
            "verified_at"}
    for rec in payload["capabilities"]:
        assert set(rec) == keys, set(rec) ^ keys
        assert rec["status"] in {"ok", "broken", "retired", "manual"}
        assert rec["kind"] in gci.KINDS
        assert isinstance(rec["defects"], list) and all(isinstance(x, str) for x in rec["defects"])
        assert rec["doc_link"] is None or isinstance(rec["doc_link"], str)


# --- Behavior 4/5: covers all 7 kinds + docs/CAPABILITIES.md is valid llms.txt -----------------------


def test_all_seven_kinds_present(tmp_path) -> None:
    catalog = gci.build_catalog(REPO)
    kinds = {c["kind"] for c in catalog}
    assert set(gci.KINDS) <= kinds, set(gci.KINDS) - kinds


def test_capabilities_md_is_valid_llms_txt(tmp_path) -> None:
    gci.main(REPO, out_dir=tmp_path)
    md = (tmp_path / "docs" / "CAPABILITIES.md").read_text().splitlines()
    assert md[0].startswith("# "), "llms.txt requires a single H1 first line"
    assert any(line.startswith("> ") for line in md[:6]), "llms.txt requires a blockquote summary"
    assert any(line.startswith("## ") for line in md), "llms.txt requires H2 sections"
    # each H2 section item is a markdown link-list row
    body = "\n".join(md)
    assert "](" in body, "sections must contain markdown links"


# --- Regression: summaries + marker classification (defects caught in the Phase-A review) -------------


def test_first_docline_skips_shebang(tmp_path) -> None:
    """A shebang line must NOT become the summary — the real doc/comment line does.

    Regression: `_first_docline` stripped the leading `#` before the `#!/` guard, so every shebanged
    script got `!/bin/bash` as its summary (most scripts), defeating the catalog's discovery goal.
    """
    assert (
        gci._first_docline("#!/usr/bin/env bash\n# Does the real thing.\necho hi")
        == "Does the real thing."
    )
    py = gci._first_docline('#!/usr/bin/env python3\n"""Real docstring."""\nimport os')
    assert py == "Real docstring."
    assert not py.startswith("!"), "a shebang leaked into the summary"


def test_first_docline_skips_frontmatter_fence(tmp_path) -> None:
    """A rules-pack `---` YAML front-matter fence must NOT leak as the summary — `description:` (or the
    first heading) does. Regression: all 48 rules-packs got `summary == '---'` (round-2 finding).
    """
    assert gci._first_docline("---\ndescription: My rule.\nglobs: x\n---\n# H\n") == "My rule."
    assert gci._first_docline("---\nglobs: x\n---\n# The Heading\n") == "The Heading"
    # description: with a colon in its value splits correctly
    assert gci._first_docline("---\ndescription: use foo: bar\n---\n# H\n") == "use foo: bar"
    # empty / block-scalar description falls THROUGH to the heading (not '')
    assert (
        gci._first_docline("---\ndescription:\nglobs: x\n---\n# Real Heading\n") == "Real Heading"
    )
    assert (
        gci._first_docline("---\ndescription: |\n  multi\n---\n# Real Heading\n") == "Real Heading"
    )
    # a lone leading `---` HR with NO closing fence is not front-matter → body is still parsed
    assert gci._first_docline("---\nSome real intro text.\nmore\n") == "Some real intro text."
    import glob

    rp = sorted(glob.glob(str(REPO / ".windsurf" / "rules" / "**" / "*.md"), recursive=True))
    assert rp, "expected rules-packs in the repo"
    s = gci._first_docline(gci._read_head(Path(rp[0])))
    assert s and s != "---", f"rules-pack summary leaked the front-matter fence: {s!r}"


def test_import_failure_is_failclosed_not_silently_dropped(monkeypatch, tmp_path) -> None:
    """A surface whose fabrik import fails emits a `broken` sentinel (→ whole-surface guard raises),
    never an empty list that would silently drop the whole surface from the catalog (Behavior 7)."""
    # sys.modules[name] = None makes `from <name> import …` raise ImportError (fabrik is already cached
    # from other tests, so pointing at an empty tmp root would NOT fail the import on its own).
    monkeypatch.setitem(sys.modules, "fabrik.cli", None)
    cli = gci._enum_cli(tmp_path)
    assert cli and all(c["status"] == "broken" for c in cli), cli
    monkeypatch.setitem(sys.modules, "fabrik.orchestrator.infrastructure", None)
    reg = gci._enum_registrars(tmp_path)
    assert reg and all(c["status"] == "broken" for c in reg), reg


def test_marker_mentioned_in_prose_is_not_retired(tmp_path) -> None:
    """A marker word MENTIONED mid-line (substring) must not retire the tool — only a line-start directive does.

    Regression: raw-substring matching classified the generator itself (whose source contains the
    `_RETIRED_MARKERS = ("DEPRECATED", …)` literal) as `retired` in the committed catalog.
    """
    f = tmp_path / "tool.py"
    f.write_text(
        '#!/usr/bin/env python3\n"""Live tool. Replaces an old DEPRECATED helper elsewhere."""\n'
        'markers = ("# DEPRECATED",)\nimport argparse\n'
    )
    assert gci._classify_script(f)[0] == "ok"
    # the real generator must classify itself as ok, never retired
    gen = Path(__file__).resolve().parent.parent / "scripts" / "generate_capability_index.py"
    assert gci._classify_script(gen)[0] == "ok"
    # but a genuine line-start directive still retires
    d = tmp_path / "old.py"
    d.write_text("#!/usr/bin/env python3\n# DEPRECATED: use new_tool\n")
    assert gci._classify_script(d)[0] == "retired"


def test_probe_help_timeout_returns_false(monkeypatch) -> None:
    """A hanging `--help` that hits the timeout is caught (→ broken), never propagates (fail-soft)."""
    import subprocess

    def _raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=30)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    assert gci._probe_help(["-m", "fabrik.cli", "whatever"]) is False


# --- 2026-08-12 catalog-truth fixes (operator: agent distinction will derive from the catalog) -------


def test_non_scaffold_template_dirs_not_emitted() -> None:
    """A bare templates/<helper>/ dir is not an invokable capability — no entry at all (was: 10
    kind='script' rows with a folder path as invoke, incl. templates/.archive/)."""
    catalog = gci.build_catalog(REPO)
    dir_invokes = [c for c in catalog if c["invoke"].startswith("templates/")]
    assert dir_invokes == [], dir_invokes[:3]


def test_hook_kind_covers_repo_claude_hooks() -> None:
    """.claude/hooks/*.py are catalogued (kind='hook') — they are the enforcement-mesh surface an
    ownership map must cover."""
    catalog = gci.build_catalog(REPO)
    hooks = {c["name"] for c in catalog if c["kind"] == "hook"}
    assert "mail_notify.py" in hooks and "session_orient.py" in hooks, sorted(hooks)


def test_command_kind_covers_sources_corpus() -> None:
    """commands/_sources/*.md are catalogued (kind='command', invoke '/<stem>'), summary mined from
    front-matter description — repo-deterministic (no $HOME probing)."""
    catalog = gci.build_catalog(REPO)
    cmds = {c["name"]: c for c in catalog if c["kind"] == "command"}
    assert "fabrik-review" in cmds, sorted(cmds)[:8]
    assert cmds["fabrik-review"]["invoke"] == "/fabrik-review"
    assert "Adversarial code review" in cmds["fabrik-review"]["summary"]


def test_driver_retired_marker_wins_over_import_probe(tmp_path, monkeypatch) -> None:
    """A driver whose head carries a line-start RETIRED directive is 'retired' even though it
    imports fine — org retirement must beat the mechanical probe (the stale-ok class)."""
    drv = tmp_path / "src" / "fabrik" / "drivers"
    drv.mkdir(parents=True)
    (drv / "__init__.py").write_text("")
    (drv / "deadstack.py").write_text('"""RETIRED 2026-07-19 — dead stack."""\n')
    (drv / "livestack.py").write_text('"""A live driver."""\n')
    recs = gci._enum_drivers(tmp_path)
    by = {r["name"]: r["status"] for r in recs}
    assert by["deadstack"] == "retired", by
    # the marker must not LEAK to unmarked siblings; its import-probe status in a tmp tree is
    # env-dependent (the real `fabrik` package is already cached), and probe semantics are
    # covered by the real-repo tests above — so assert only the non-leak here
    assert by["livestack"] != "retired", by


def test_benchmark_and_ops_script_subdirs_scanned() -> None:
    """scripts/{kilo-benchmarks,bootstrap,audit,credit_fetchers} are in scan scope — ownership
    can't map surfaces the catalog can't see."""
    catalog = gci.build_catalog(REPO)
    paths = " ".join(c["invoke"] for c in catalog if c["kind"] == "script")
    assert "scripts/kilo-benchmarks/" in paths, "kilo-benchmarks not scanned"
    assert "scripts/bootstrap/" in paths or not (REPO / "scripts/bootstrap").is_dir()


# --- Phase B (agent-roles wiring): the owner field --------------------------------------------


def test_every_entry_carries_a_valid_owner() -> None:
    catalog = gci.build_catalog(REPO)
    valid = {"infra", "fleet", "intel", "external:fabrik-lib", "unassigned"}
    bad = [(c["kind"], c["name"], c.get("owner")) for c in catalog if c.get("owner") not in valid]
    assert bad == [], bad[:5]


def test_owner_spot_anchors_match_the_beat_tables() -> None:
    catalog = gci.build_catalog(REPO)
    by = {(c["kind"], c["name"]): c["owner"] for c in catalog}
    assert by[("hook", "mail_notify.py")] == "infra"
    assert by[("scaffold", "python-api")] == "fleet"
    assert by[("lib-module", "subagents")] == "external:fabrik-lib"
    intel_scripts = [c for c in catalog if c["kind"] == "script"
                     and c["invoke"].find("scripts/kilo-benchmarks/") != -1]
    assert intel_scripts and all(c["owner"] == "intel" for c in intel_scripts)
    enf = [c for c in catalog if c["kind"] == "script"
           and "scripts/enforcement/" in c["invoke"]]
    assert enf and all(c["owner"] == "infra" for c in enf)


def test_unmatched_entry_falls_to_unassigned() -> None:
    rec = gci._rec("mystery", "brand-new-kind", "?", "invoke mystery", "ok")
    assert rec["owner"] == "unassigned"


def test_capabilities_md_renders_owner() -> None:
    import subprocess, sys as _sys
    r = subprocess.run([_sys.executable, str(REPO / "scripts/generate_capability_index.py"),
                        "--check"], capture_output=True, text=True, timeout=600, cwd=str(REPO))
    assert r.returncode == 0
    md = (REPO / "docs" / "CAPABILITIES.md").read_text()
    assert "owner: infra" in md or "· infra ·" in md or "(infra)" in md
