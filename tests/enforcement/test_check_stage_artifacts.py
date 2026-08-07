# AFTER-EDIT: scripts/enforcement/check_stage_artifacts.py
"""Tests for scripts/enforcement/check_stage_artifacts.py — the stage-skip artifact gate.

Two gaps, driven over a throwaway git repo (the real script discovers artifacts via
``git status``, so these exercise the actual code path, matching tests/test_check_convergence.py's
style):

  (a) a plan NEWLY claiming CONVERGED that cites a design spec still DRAFT/missing
      (stage 1->3 skip).
  (b) docs/data-contract.md / docs/ui-design.md NEWLY claiming Status: FROZEN without
      the header fields + freeze-rule sentence their own freezing command mandates.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_stage_artifacts.py"
TEMPLATE_DOCS = Path(__file__).resolve().parents[2] / "templates" / "scaffold" / "docs"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, timeout=15, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, timeout=15)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True, timeout=15)
    return tmp_path


def _write_stage(repo: Path, files: dict[str, str]) -> None:
    for relpath, content in files.items():
        p = repo / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git(repo, "add", "-A")


def _check(repo: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout


# --- Gap (a): plan CONVERGED citing a still-DRAFT/missing design spec ----------

PLAN_PATH = "docs/development/plans/2026-08-06-plan-x.md"

CONVERGED_PLAN_TEMPLATE = """# Plan X

**Status:** CONVERGED

Design spec: [docs/superpowers/specs/2026-08-06-x-design.md](../../superpowers/specs/2026-08-06-x-design.md)

## Evidence

Grounded in src/app/handler.py:42.

```
$ python scripts/final_gate.py --lean
{{"status": "success", "passed": 15, "failed": 0}}
```

## Self-audit
Traced.
"""

DRAFT_SPEC = "# X Design\n\nStatus: DRAFT\n\n## Goal\nWIP.\n"
CONVERGED_SPEC = "# X Design\n\nStatus: CONVERGED\n\n## Goal\nDone.\n"


def test_plan_converged_citing_missing_spec_fails(repo: Path) -> None:
    _write_stage(repo, {PLAN_PATH: CONVERGED_PLAN_TEMPLATE})
    rc, out = _check(repo)
    assert rc == 1
    assert "does not exist on disk" in out


def test_plan_converged_citing_draft_spec_fails(repo: Path) -> None:
    _write_stage(
        repo,
        {
            PLAN_PATH: CONVERGED_PLAN_TEMPLATE,
            "docs/superpowers/specs/2026-08-06-x-design.md": DRAFT_SPEC,
        },
    )
    rc, out = _check(repo)
    assert rc == 1
    assert "is not itself CONVERGED" in out


def test_plan_converged_citing_converged_spec_passes(repo: Path) -> None:
    _write_stage(
        repo,
        {
            PLAN_PATH: CONVERGED_PLAN_TEMPLATE,
            "docs/superpowers/specs/2026-08-06-x-design.md": CONVERGED_SPEC,
        },
    )
    rc, out = _check(repo)
    assert rc == 0, out


def test_plan_not_claiming_converged_is_ignored(repo: Path) -> None:
    draft_plan = CONVERGED_PLAN_TEMPLATE.replace("**Status:** CONVERGED", "**Status:** DRAFT")
    _write_stage(repo, {PLAN_PATH: draft_plan})
    rc, out = _check(repo)
    assert rc == 0, out


def test_plan_citing_archived_spec_is_exempt(repo: Path) -> None:
    plan = CONVERGED_PLAN_TEMPLATE.replace(
        "docs/superpowers/specs/2026-08-06-x-design.md",
        "docs/superpowers/specs/archived/2026-01-01-old-design.md",
    ).replace(
        "../../superpowers/specs/2026-08-06-x-design.md",
        "../../superpowers/specs/archived/2026-01-01-old-design.md",
    )
    _write_stage(repo, {PLAN_PATH: plan})
    rc, out = _check(repo)
    assert rc == 0, out


def test_plan_already_converged_at_head_is_settled(repo: Path) -> None:
    # A plan already CONVERGED at HEAD (citing a missing spec) is re-touched
    # (incidental reformat) -- new-transition-only must NOT re-fail it.
    _write_stage(repo, {PLAN_PATH: CONVERGED_PLAN_TEMPLATE})
    _git(repo, "commit", "-qm", "seed converged plan")
    (repo / PLAN_PATH).write_text(CONVERGED_PLAN_TEMPLATE + "\n<!-- reformatted -->\n")
    _git(repo, "add", "-A")
    rc, out = _check(repo)
    assert rc == 0, out


def test_plan_converged_citing_now_archived_spec_settles(repo: Path) -> None:
    # F5: the citation still points at the PRE-archive path -- the real fleet
    # case (2026-06-29-plan-empire-operating-model.md cites
    # docs/superpowers/specs/2026-07-12-empire-operating-model-design.md, which
    # now lives ONLY under specs/archived/). Found by basename under
    # specs/archived/ -> archived = post-lifecycle history, settled.
    basename = "2026-07-12-empire-operating-model-design.md"
    plan = CONVERGED_PLAN_TEMPLATE.replace(
        "docs/superpowers/specs/2026-08-06-x-design.md",
        f"docs/superpowers/specs/{basename}",
    ).replace(
        "../../superpowers/specs/2026-08-06-x-design.md",
        f"../../superpowers/specs/{basename}",
    )
    _write_stage(
        repo,
        {
            PLAN_PATH: plan,
            f"docs/superpowers/specs/archived/{basename}": CONVERGED_SPEC,
        },
    )
    rc, out = _check(repo)
    assert rc == 0, out


# --- Gap (F6): "its spec" scoped to a designated citation, never a free scan ---

SPEC_FIELD_PLAN = """# Plan Z

**Status:** CONVERGED

Spec: [docs/superpowers/specs/2026-08-06-z-design.md](../../superpowers/specs/2026-08-06-z-design.md)

## Evidence

Grounded in src/app/handler.py:99.

```
$ python scripts/final_gate.py --lean
{{"status": "success", "passed": 12, "failed": 0}}
```

## Self-audit
Traced.
"""

# A body-only spec mention (no Spec:/Design spec: header field, and the
# citation sits well past the plan's first 40 lines) -- e.g. a "Notes" aside
# referencing a superseded/rejected design. Must NOT create a spec dependency.
_FILLER_LINE = "Filler context line to push the body-only citation past line 40.\n"
BODY_ONLY_MENTION_PLAN = (
    "# Plan W\n\n**Status:** CONVERGED\n\n## Context\n\n"
    + (_FILLER_LINE * 40)
    + """
## Evidence

Grounded in src/app/handler.py:7.

```
$ python scripts/final_gate.py --lean
{{"status": "success", "passed": 9, "failed": 0}}
```

## Self-audit
Traced.

## Notes
Supersedes the approach explored in
[docs/superpowers/specs/2026-01-01-old-approach.md](../../superpowers/specs/2026-01-01-old-approach.md)
(rejected; see also that design for context, never built, never depended on).
"""
)


def test_plan_spec_field_citation_is_designated_and_blocks(repo: Path) -> None:
    # F6 direction 1: a `Spec:` header-field citation IS the designated source
    # -- a missing spec behind it still blocks (mirrors the Design spec: case).
    _write_stage(repo, {PLAN_PATH: SPEC_FIELD_PLAN})
    rc, out = _check(repo)
    assert rc == 1
    assert "does not exist on disk" in out


def test_plan_body_only_spec_mention_does_not_block(repo: Path) -> None:
    # F6 direction 2: a spec citation with NO Spec:/Design spec: header field,
    # buried past the first 40 lines in a body aside (supersedes/rejected/see
    # also), must NOT become a blocking dependency -- even though the cited
    # spec (docs/superpowers/specs/2026-01-01-old-approach.md) does not exist.
    _write_stage(repo, {PLAN_PATH: BODY_ONLY_MENTION_PLAN})
    rc, out = _check(repo)
    assert rc == 0, out


# --- Gap (NEW-5): fallback scan excludes markdown TABLE ROWS ------------------

TABLE_CITE_PLAN = """# Plan Y

**Status:** CONVERGED

## Context

| See also | Link |
|---|---|
| Old design | [docs/superpowers/specs/2026-01-01-seealso-design.md](../../superpowers/specs/2026-01-01-seealso-design.md) |

## Evidence

Grounded in src/app/handler.py:11.

```
$ python scripts/final_gate.py --lean
{{"status": "success", "passed": 5, "failed": 0}}
```

## Self-audit
Traced.
"""

PROSE_CITE_PLAN = """# Plan Y2

**Status:** CONVERGED

## Context

Related work continues the direction set in
[docs/superpowers/specs/2026-01-01-seealso-design.md](../../superpowers/specs/2026-01-01-seealso-design.md).

## Evidence

Grounded in src/app/handler.py:12.

```
$ python scripts/final_gate.py --lean
{{"status": "success", "passed": 5, "failed": 0}}
```

## Self-audit
Traced.
"""


def test_plan_context_ledger_table_row_citation_does_not_block(repo: Path) -> None:
    # NEW-5: a Context-Ledger "see-also" TABLE ROW citing a sibling spec, within
    # the plan's first 40 lines and with no Spec:/Design spec: field, must NOT
    # become a blocking dependency -- even though the cited spec does not exist
    # on disk. The fallback scan (2) is prose-only; a '|'-led row is excluded.
    _write_stage(repo, {PLAN_PATH: TABLE_CITE_PLAN})
    rc, out = _check(repo)
    assert rc == 0, out


def test_plan_context_prose_citation_within_40_lines_still_blocks(repo: Path) -> None:
    # NEW-5 both-direction: the SAME citation as PROSE (not a table row), still
    # within the first 40 lines and with no Spec:/Design spec: field, keeps
    # blocking via the pre-existing fallback -- proving the table-row exclusion
    # is scoped to '|'-led lines only, not a blanket disabling of the fallback.
    _write_stage(repo, {PLAN_PATH: PROSE_CITE_PLAN})
    rc, out = _check(repo)
    assert rc == 1
    assert "does not exist on disk" in out


# --- Gap (new-2): data-contract / ui-design FROZEN header completeness ---------

DC_COMPLETE = """# Data Contract

Status: FROZEN
Version: v1
Date: 2026-08-06
Mode: A

Frozen — no agent adds a field, column, or enum value not listed here. Any change = bump
Version + re-freeze via `/fabrik-data-contract`.

## Entity: user
| GUI field | DB column | type | req | validation | PII | references |
|---|---|---|---|---|---|---|
| Email | email | text | yes | RFC5322 | personal | — |
"""

UI_COMPLETE = """# UI Design

Status: FROZEN
Version: v1
Date: 2026-08-06
Surface: web
Design system: adopted

Frozen — no agent adds a screen, flow, component, or field not listed here. Any change =
bump Version + re-freeze via `/fabrik-ui-design`.

## Screens
"""


def test_scaffold_stub_data_contract_template_is_not_a_frozen_claim(repo: Path) -> None:
    # F1 CRITICAL: the untouched scaffold stub's Status line is literally
    # "DRAFT | FROZEN" (templates/scaffold/docs/data-contract-template.md:3) --
    # the naive "frozen" substring test tripped on it, hard-failing Tier-2 for
    # EVERY newly scaffolded project fleet-wide. Prove the real template passes
    # untouched (zero findings).
    stub = (TEMPLATE_DOCS / "data-contract-template.md").read_text(encoding="utf-8")
    _write_stage(repo, {"docs/data-contract.md": stub})
    rc, out = _check(repo)
    assert rc == 0, out


def test_data_contract_frozen_with_complete_header_passes(repo: Path) -> None:
    _write_stage(repo, {"docs/data-contract.md": DC_COMPLETE})
    rc, out = _check(repo)
    assert rc == 0, out


def test_data_contract_frozen_missing_mode_fails(repo: Path) -> None:
    broken = DC_COMPLETE.replace("Mode: A\n", "")
    _write_stage(repo, {"docs/data-contract.md": broken})
    rc, out = _check(repo)
    assert rc == 1
    assert "Mode: A|B|C" in out


def test_data_contract_frozen_missing_version_fails(repo: Path) -> None:
    broken = DC_COMPLETE.replace("Version: v1\n", "")
    _write_stage(repo, {"docs/data-contract.md": broken})
    rc, out = _check(repo)
    assert rc == 1
    assert "Version: v<N>" in out


def test_data_contract_frozen_missing_date_fails(repo: Path) -> None:
    # F9: no test previously killed a dropped Date: guard.
    broken = DC_COMPLETE.replace("Date: 2026-08-06\n", "")
    _write_stage(repo, {"docs/data-contract.md": broken})
    rc, out = _check(repo)
    assert rc == 1
    assert "Date: YYYY-MM-DD" in out


def test_data_contract_frozen_missing_freeze_rule_fails(repo: Path) -> None:
    broken = DC_COMPLETE.replace(
        "Frozen — no agent adds a field, column, or enum value not listed here. "
        "Any change = bump\nVersion + re-freeze via `/fabrik-data-contract`.\n",
        "",
    )
    _write_stage(repo, {"docs/data-contract.md": broken})
    rc, out = _check(repo)
    assert rc == 1
    assert "freeze-rule sentence" in out


def test_data_contract_frozen_with_wrapped_blockquote_freeze_rule_passes(repo: Path) -> None:
    # F4: the scaffold template's REAL wrap style splits "re-freeze" and "via"
    # across two blockquote lines (data-contract-template.md:10-11) -- a naive
    # "re-freeze via" substring test misses this; whitespace-normalization must
    # catch it.
    wrapped = DC_COMPLETE.replace(
        "Frozen — no agent adds a field, column, or enum value not listed here. "
        "Any change = bump\nVersion + re-freeze via `/fabrik-data-contract`.\n",
        "> Frozen — no agent adds a field, column, or enum value not listed here. Any "
        "change = bump Version + re-freeze\n> via `/fabrik-data-contract`.\n",
    )
    _write_stage(repo, {"docs/data-contract.md": wrapped})
    rc, out = _check(repo)
    assert rc == 0, out


def test_data_contract_command_verbatim_backtick_header_passes(repo: Path) -> None:
    # F2: the command-mandated ONE-LINE, backtick-tokened header shape
    # (commands/_sources/fabrik-data-contract.md:157: "Set the header:
    # **`Status: FROZEN` . `Version: v<N>` . `Date: <YYYY-MM-DD>` . `Mode:
    # A|B|C`**") with real substituted values, all fields packed onto one line.
    dc = (
        "# Data Contract\n\n"
        "**`Status: FROZEN` · `Version: v3` · `Date: 2026-08-07` · `Mode: A`**\n\n"
        "Frozen — no agent adds a field, column, or enum value not listed here. Any change = bump\n"
        "Version + re-freeze via `/fabrik-data-contract`.\n\n"
        "## Entity: user\n"
        "| GUI field | DB column | type | req | validation | PII | references |\n"
        "|---|---|---|---|---|---|---|\n"
        "| Email | email | text | yes | RFC5322 | personal | — |\n"
    )
    _write_stage(repo, {"docs/data-contract.md": dc})
    rc, out = _check(repo)
    assert rc == 0, out


def test_data_contract_draft_is_ignored(repo: Path) -> None:
    # F9: the DRAFT fixture is deliberately header-INCOMPLETE (Mode: dropped)
    # so this test FAILS if the DRAFT skip (the `_claims_frozen` gate in
    # `_frozen_targets`) is ever removed -- a complete-header DRAFT fixture
    # would keep passing even with the skip gone, hiding the regression.
    draft = DC_COMPLETE.replace("Status: FROZEN", "Status: DRAFT").replace("Mode: A\n", "")
    _write_stage(repo, {"docs/data-contract.md": draft})
    rc, out = _check(repo)
    assert rc == 0, out


def test_data_contract_not_frozen_with_incomplete_header_produces_no_findings(repo: Path) -> None:
    # F9 target-gate: even a badly incomplete header (Version, Date, AND Mode
    # all missing) must produce ZERO findings when the file never claims FROZEN
    # in the first place -- this fails if `_claims_frozen` stops gating
    # `_frozen_targets` (e.g. every FROZEN_ARTIFACTS path enforced unconditionally).
    broken_draft = (
        DC_COMPLETE.replace("Status: FROZEN", "Status: DRAFT")
        .replace("Version: v1\n", "")
        .replace("Date: 2026-08-06\n", "")
        .replace("Mode: A\n", "")
    )
    _write_stage(repo, {"docs/data-contract.md": broken_draft})
    rc, out = _check(repo)
    assert rc == 0, out


def test_ui_design_frozen_with_complete_header_passes(repo: Path) -> None:
    _write_stage(repo, {"docs/ui-design.md": UI_COMPLETE})
    rc, out = _check(repo)
    assert rc == 0, out


def test_ui_design_frozen_missing_surface_fails(repo: Path) -> None:
    broken = UI_COMPLETE.replace("Surface: web\n", "")
    _write_stage(repo, {"docs/ui-design.md": broken})
    rc, out = _check(repo)
    assert rc == 1
    assert "Surface" in out


def test_ui_design_frozen_missing_design_system_fails(repo: Path) -> None:
    broken = UI_COMPLETE.replace("Design system: adopted\n", "")
    _write_stage(repo, {"docs/ui-design.md": broken})
    rc, out = _check(repo)
    assert rc == 1
    assert "Design system" in out


# The REAL fleet-live header shape, copied verbatim from
# /opt/trade-intelligence/docs/ui-design.md (F2) -- ONE bold, `.`-separated
# line, with the -review command cited TWICE (in "Independently reviewed:")
# BEFORE the actual freeze-rule sentence's bare `/fabrik-ui-design` mention --
# proves the word-boundary fix (F4) too: `/fabrik-ui-design` must not be
# satisfied by the two earlier `/fabrik-ui-design-review` occurrences.
UI_FLEET_LIVE = """# UI Design — Market-Entry Discovery (operator surface) · plan-00

**Status:** FROZEN · **Version:** v4 · **Date:** 2026-08-02 · **Surface:** web (Next.js/React, existing `web/` app) · **Design system:** ADOPTED — `.windsurf/rules/core/ocoron-design-system.md` (no recreation; components/tokens/states are its source of truth)
**Independently reviewed:** v2 — `/fabrik-ui-design-review` no-op 2026-08-01 (md5 `385064782`) + re-confirmed against the built backend (md5 `09266629`). **v4 — `/fabrik-ui-design-review` no-op 2026-08-02** (the v3 author-freeze of the v2 Buyer-Dossier surface, independently re-grounded: axis A all S6/S5 components ocoron-defined incl. `Tooltip`; axis B every S6/S5/S3 field resolves in data-contract v11; 1 fix → re-froze v3→v4; Pass 2 edit-free, md5 `70039465`).

> Scope: the **internal operator GUI** for plan-00 Market-Entry Discovery (operator/admin-auth; the tenant-facing self-serve wizard reuses these SAME screens later behind tenant auth). Inputs: specs `docs/superpowers/specs/2026-08-01-market-entry-discovery-design.md` + `2026-08-02-market-entry-v2-dossier-design.md` (both CONVERGED) + `docs/data-contract.md` v11 (FROZEN — the plan-00 entities + v2 `country_risk`/`market_buyer_candidates` + `grade`/`end_use_segments`/`ranked_shortlist` risk keys, §R22). Renders ONLY v11 fields.
> **Frozen — no agent adds a screen, flow, component, or field not listed here. Any change = bump Version + re-freeze via `/fabrik-ui-design`.**

---

## Screens
"""


def test_ui_design_fleet_live_header_shape_passes(repo: Path) -> None:
    _write_stage(repo, {"docs/ui-design.md": UI_FLEET_LIVE})
    rc, out = _check(repo)
    assert rc == 0, out


# --- Gap (NEW-1): the freeze-rule sentence is a footer, not header-scoped ------

# The REAL fleet shape, mirroring /opt/tryton-crm/docs/data-contract.md: header
# fields (Status/Version/Date/Mode) sit on ONE line near the top; the freeze
# rule is a separate paragraph written LATER (real file: ~line 85), well past
# the header-block's 40-line cap, with the first standalone '---' further still
# (real file: ~line 127). The old header-scoped freeze-rule scan missed this
# shape entirely and false-failed 6 of 24 real fleet frozen artifacts.
DC_FOOTER_STYLE = (
    "# Data Contract\n\n"
    "**Status:** FROZEN · **Date:** 2026-08-07 · **Mode:** A (spec-driven)\n"
    "**Version:** v3\n\n"
    + ("Filler prior-version history line to push the freeze rule past line 40.\n" * 45)
    + "\n> **Frozen — no agent adds a field, column, or enum value not listed here. Any "
    "change = bump Version + re-freeze via `/fabrik-data-contract`.**\n\n"
    "---\n\n"
    "## Entity: user\n"
)


def test_data_contract_footer_style_freeze_rule_passes(repo: Path) -> None:
    _write_stage(repo, {"docs/data-contract.md": DC_FOOTER_STYLE})
    rc, out = _check(repo)
    assert rc == 0, out


# --- Gap (NEW-2): the placeholder-form guard must not evade a real '|'-header -

DC_PIPE_HEADER_INCOMPLETE = (
    "# Data Contract\n\n"
    "**Status:** FROZEN | **Version:** v2\n\n"
    "## Entity: user\n"
)


def test_data_contract_pipe_separated_header_missing_fields_fails(repo: Path) -> None:
    # NEW-2: a header that uses '|' as its OWN field separator ("**Status:**
    # FROZEN | **Version:** v2") is a REAL (if incomplete) claim -- the old
    # `^\S+\s*\|\s*\S+` placeholder regex matched ANY two pipe-joined tokens and
    # silently skipped the WHOLE gate on this file. It must gate-fail on the
    # missing Date/Mode/freeze-rule fields instead of vanishing.
    _write_stage(repo, {"docs/data-contract.md": DC_PIPE_HEADER_INCOMPLETE})
    rc, out = _check(repo)
    assert rc == 1
    assert "Date: YYYY-MM-DD" in out


# --- Gap (NEW-3): a leading YAML frontmatter block must not empty the header --

DC_FRONTMATTER = (
    "---\n"
    "title: Data Contract\n"
    "tags: [x, y]\n"
    "---\n\n"
    "# Data Contract\n\n"
    "Status: FROZEN\n"
    "Version: v1\n"
    "Date: 2026-08-06\n\n"
    "Any change = bump Version + re-freeze via `/fabrik-data-contract`.\n"
)


def test_data_contract_frontmatter_header_missing_fields_fails(repo: Path) -> None:
    # NEW-3: a leading YAML frontmatter block's own opening '---' (line 1) must
    # not be mistaken for the header's closing rule and empty _header_block --
    # that would silently skip the FROZEN-header gate entirely, hiding this
    # fixture's missing Mode: field (rc=0 instead of the correct rc=1).
    _write_stage(repo, {"docs/data-contract.md": DC_FRONTMATTER})
    rc, out = _check(repo)
    assert rc == 1
    assert "Mode: A|B|C" in out


# --- Gap (NEW-4): pin each CRITICAL guard independently -----------------------


def test_data_contract_reversed_placeholder_order_is_not_a_frozen_claim(repo: Path) -> None:
    # NEW-4 guard-pinning: "FROZEN | DRAFT" (reversed order from the scaffold's
    # own "DRAFT | FROZEN") must ALSO be recognized as a placeholder pair. Mode:
    # is deliberately dropped so a regression (treating this as a real FROZEN
    # claim) fails LOUDLY (rc=1, missing Mode) instead of hiding behind an
    # already-complete header. Only the placeholder-pair guard catches this:
    # its first token "frozen" is not in cc._NON_CLAIM_TOKENS, so the
    # non-claim-token guard alone would NOT skip it.
    broken = DC_COMPLETE.replace("Status: FROZEN\n", "Status: FROZEN | DRAFT\n").replace("Mode: A\n", "")
    _write_stage(repo, {"docs/data-contract.md": broken})
    rc, out = _check(repo)
    assert rc == 0, out


def test_data_contract_prose_frozen_mention_after_draft_is_not_a_frozen_claim(repo: Path) -> None:
    # NEW-4 guard-pinning: "DRAFT — will be frozen after review" is NOT
    # pipe-separated, so the placeholder-pair guard never applies -- only the
    # ported cc._NON_CLAIM_TOKENS first-token check can skip it. Mode: is
    # dropped so a regression (treating "frozen" appearing later in the line as
    # a real claim) fails loudly (rc=1) instead of hiding.
    broken = DC_COMPLETE.replace(
        "Status: FROZEN\n", "Status: DRAFT — will be frozen after review\n"
    ).replace("Mode: A\n", "")
    _write_stage(repo, {"docs/data-contract.md": broken})
    rc, out = _check(repo)
    assert rc == 0, out


def test_ui_design_already_frozen_at_head_is_settled(repo: Path) -> None:
    # A FROZEN file already settled at HEAD (missing Surface -- would fail if
    # newly enforced) is merely re-touched -- new-transition-only must skip it.
    broken = UI_COMPLETE.replace("Surface: web\n", "")
    _write_stage(repo, {"docs/ui-design.md": broken})
    _git(repo, "commit", "-qm", "seed settled frozen ui-design (pre-gate)")
    (repo / "docs/ui-design.md").write_text(broken + "\n<!-- reformatted -->\n")
    _git(repo, "add", "-A")
    rc, out = _check(repo)
    assert rc == 0, out


def test_no_artifacts_passes(repo: Path) -> None:
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", "-A")
    rc, out = _check(repo)
    assert rc == 0, out
