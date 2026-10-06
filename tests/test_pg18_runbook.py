"""Grader for the PostgreSQL 16 -> 18 operator runbook (plan-1 PG18, ticket T05).

The runbook is ``docs/operations/postgres-major-upgrade-runbook.md``. These tests parse it
STRUCTURALLY — headings, the prose lines of each section, and the fenced blocks per step —
so a stray word in a comment or in the wrong section cannot satisfy them.

Seams (spine § Interfaces):
- T02 -> T05: the compose the runbook installs in hub step 4 must EQUAL
  ``infra/vps1/postgres/compose.yaml``, and every ``docker run`` image in the windows must be
  the image that file pins.
- T03 -> T05: the volume hub step 8 and the V8 drill name must be the postgres volume
  ``scripts/bootstrap/bootstrap-config.sh`` restores.

Cheapest way to satisfy this grader without the outcome (CLAUDE.md § FIX DIRECTIVE 5): write
the tokens it looks for into code lines that are never meant to run (``echo adminpack``). The
counter-measure is the full /fabrik-review the plan assigns T05 — the grader proves structure
and the seams, a reviewer proves the commands are the right commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "operations" / "postgres-major-upgrade-runbook.md"
COMPOSE = ROOT / "infra" / "vps1" / "postgres" / "compose.yaml"
BOOTSTRAP_CONFIG = ROOT / "scripts" / "bootstrap" / "bootstrap-config.sh"

GATE_MARKER = "**Operator's explicit word:**"
DESTRUCTIVE = ("docker volume rm", "docker volume prune", "down -v", "pg_dropcluster")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


@dataclass
class Section:
    level: int
    title: str
    start: int  # line index of the heading
    end: int = 0  # exclusive, includes children
    own_end: int = 0  # exclusive, stops at the next heading of any level
    prose: list[str] = field(default_factory=list)  # own prose lines (outside fences)
    fences: list[str] = field(default_factory=list)  # own fenced blocks
    all_prose: list[str] = field(default_factory=list)  # prose incl. children
    all_fences: list[str] = field(default_factory=list)  # fences incl. children


def _parse(text: str) -> tuple[list[str], list[Section]]:
    lines = text.splitlines()
    sections: list[Section] = []
    in_fence = False
    fence_owner: list[int] = []  # line index -> True when the line is inside a fence
    for line in lines:
        if line.lstrip().startswith("```"):
            fence_owner.append(2)  # fence delimiter
            in_fence = not in_fence
            continue
        fence_owner.append(1 if in_fence else 0)
        if not in_fence:
            m = HEADING.match(line)
            if m:
                sections.append(Section(len(m.group(1)), m.group(2), len(fence_owner) - 1))
    assert not in_fence, "unterminated fenced block in the runbook"
    for i, sec in enumerate(sections):
        sec.own_end = sections[i + 1].start if i + 1 < len(sections) else len(lines)
        sec.end = len(lines)
        for nxt in sections[i + 1 :]:
            if nxt.level <= sec.level:
                sec.end = nxt.start
                break

    def collect(lo: int, hi: int) -> tuple[list[str], list[str]]:
        prose: list[str] = []
        fences: list[str] = []
        buf: list[str] | None = None
        for idx in range(lo + 1, hi):
            kind = fence_owner[idx]
            if kind == 2:
                if buf is None:
                    buf = []
                else:
                    fences.append("\n".join(buf))
                    buf = None
            elif kind == 1 and buf is not None:
                buf.append(lines[idx])
            elif kind == 0 and not HEADING.match(lines[idx]):
                prose.append(lines[idx])
        return prose, fences

    for sec in sections:
        sec.prose, sec.fences = collect(sec.start, sec.own_end)
        sec.all_prose, sec.all_fences = collect(sec.start, sec.end)
    return lines, sections


def _code_lines(fences: list[str]) -> list[str]:
    """Executable lines only: shell `#` / SQL `--` comment lines dropped, trailing ` # …` comments cut."""
    out = []
    for block in fences:
        for line in block.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("--"):
                continue
            s = re.sub(r"\s+#\s.*$", "", s)
            out.append(s)
    return out


def _fence_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """(opening-delimiter index, closing-delimiter index) for every fenced block."""
    out, start = [], None
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            if start is None:
                start = idx
            else:
                out.append((start, idx))
                start = None
    return out


def _preceding_prose(lines: list[str], fence_start: int) -> list[str]:
    """The prose between the previous fence (or heading) and this fence's opening line."""
    out = []
    for idx in range(fence_start - 1, -1, -1):
        line = lines[idx]
        if line.lstrip().startswith("```") or HEADING.match(line):
            break
        out.append(line)
    return out[::-1]


def _block_with(sec: Section, needle: str) -> str:
    hits = [b for b in sec.all_fences if needle in "\n".join(_code_lines([b]))]
    assert len(hits) == 1, (
        f"expected one block in '{sec.title}' running {needle!r}, found {len(hits)}"
    )
    return hits[0]


def _run_bash(script: str, env: dict[str, str]) -> str:
    import os
    import shutil
    import subprocess

    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    res = subprocess.run(
        [bash, "-c", script], env={**os.environ, **env}, capture_output=True, text=True, timeout=60
    )
    return res.stdout + res.stderr


@pytest.fixture(scope="module")
def doc() -> tuple[list[str], list[Section]]:
    assert RUNBOOK.is_file(), f"runbook missing: {RUNBOOK.relative_to(ROOT)}"
    return _parse(RUNBOOK.read_text(encoding="utf-8"))


def _top(sections: list[Section], prefix: str) -> Section:
    hits = [s for s in sections if s.level == 2 and s.title.startswith(prefix)]
    assert len(hits) == 1, f"expected one '## {prefix}…' section, found {[s.title for s in hits]}"
    return hits[0]


def _children(sections: list[Section], parent: Section, level: int) -> list[Section]:
    return [s for s in sections if parent.start < s.start < parent.end and s.level == level]


def _step_ids(children: list[Section], pattern: str) -> list[tuple[str, Section]]:
    rx = re.compile(pattern)
    out = []
    for s in children:
        m = rx.match(s.title)
        if m:
            out.append((m.group(1).lower(), s))
    return out


def _has_marker(prose: list[str], marker: str) -> bool:
    return any(
        line.strip().startswith(marker) and len(line.strip()) > len(marker) + 1 for line in prose
    )


def _hub_steps(sections: list[Section]) -> dict[str, Section]:
    hub = _top(sections, "3. Hub window")
    steps = _step_ids(_children(sections, hub, 3), r"^Hub (disk gate|step (?:\w+))\b")
    return {sid.replace("step ", ""): s for sid, s in steps}


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _dr_postgres_volume() -> str:
    text = BOOTSTRAP_CONFIG.read_text(encoding="utf-8")
    m = re.search(r"^FABRIK_HUB_VOLUMES_TO_RESTORE=\((.*?)^\)", text, re.S | re.M)
    assert m, "FABRIK_HUB_VOLUMES_TO_RESTORE array not found in bootstrap-config.sh"
    vols = [ln.split("#", 1)[0].strip() for ln in m.group(1).splitlines()]
    pg = [v for v in vols if v and "postgres" in v]
    assert len(pg) == 1, f"expected one postgres volume in the DR list, found {pg}"
    return pg[0]


# --- Behavior Contract 1: the hub window -------------------------------------------------------


def test_hub_window_has_every_d1_step_in_spec_order(doc):
    _, sections = doc
    hub = _top(sections, "3. Hub window")
    ids = [
        sid.replace("step ", "")
        for sid, _ in _step_ids(_children(sections, hub, 3), r"^Hub (disk gate|step (?:\w+))\b")
    ]
    assert ids == ["disk gate", "1", "2", "3", "4", "5", "6", "6a", "7", "8"]


def test_every_d1_step_has_a_command_block_a_verify_and_a_rollback(doc):
    _, sections = doc
    for sid, sec in _hub_steps(sections).items():
        assert _code_lines(sec.all_fences), f"hub step {sid}: no command block"
        assert _has_marker(sec.all_prose, "**Verify:**"), f"hub step {sid}: no Verify line"
        assert _has_marker(sec.all_prose, "**Rollback:**"), f"hub step {sid}: no Rollback line"


def test_step_6_verify_carries_the_compatibility_checks(doc):
    _, sections = doc
    step6 = _hub_steps(sections)["6"]
    code = " ".join(_code_lines(step6.all_fences))
    for call in ("manifest_diff", "pg_compat_checks", "test_app_role_real_pg.py"):
        assert call in code, f"hub step 6 does not run {call}"
    assert "old_snapshot_threshold" in code and "db_user_namespace" in code
    defs = _function_body(sections, "pg_compat_checks")
    for token in ("adminpack", "collisdeterministic", "indisvalid", "trgm_ops", "SCRAM-SHA-256"):
        assert token in defs, f"pg_compat_checks does not check {token}"
    manifest = _function_body(sections, "pg_manifest_cluster")
    assert "pg_auth_members" in manifest and "pg_authid" in manifest, (
        "roles/grants not in the manifest"
    )
    verify = _paragraph(step6.all_prose, "**Verify:**")
    for item in ("Compatibility checks", "restore blockers", "pg_trgm", "roles"):
        assert item in verify, f"hub step 6 Verify line does not name {item!r}"


def _paragraph(prose: list[str], marker: str) -> str:
    """The marker line plus its continuation lines, up to the next blank or bold-marker line."""
    out: list[str] = []
    for line in prose:
        s = line.strip()
        if out and (not s or s.startswith("**")):
            break
        if out or s.startswith(marker):
            out.append(s)
    return " ".join(out)


def _function_body(sections: list[Section], name: str) -> str:
    rx = re.compile(rf"^{re.escape(name)}\(\)\s*\{{", re.M)
    bodies = []
    for sec in sections:
        for block in sec.fences:
            m = rx.search(block)
            if m:
                rest = block[m.end() :]
                end = re.search(r"^\}", rest, re.M)
                bodies.append(rest[: end.start()] if end else rest)
    assert len(bodies) == 1, f"expected exactly one definition of {name}(), found {len(bodies)}"
    return "\n".join(ln for ln in bodies[0].splitlines() if not ln.strip().startswith(("#", "--")))


# --- Behavior Contract 2: the WSL window -------------------------------------------------------


def test_wsl_window_has_d2_steps_0_to_6_in_order(doc):
    _, sections = doc
    wsl = _top(sections, "2. WSL window")
    ids = [sid for sid, _ in _step_ids(_children(sections, wsl, 3), r"^WSL step (\w+)\b")]
    assert ids == ["0", "1", "2", "2a", "3", "4", "5", "6"]
    for sid, sec in _step_ids(_children(sections, wsl, 3), r"^WSL step (\w+)\b"):
        assert _code_lines(sec.fences), f"WSL step {sid}: no command block"
        assert _has_marker(sec.prose, "**Verify:**"), f"WSL step {sid}: no Verify line"
        assert _has_marker(sec.prose, "**Rollback:**"), f"WSL step {sid}: no Rollback line"


def test_wsl_stop_list_names_the_local_writers(doc):
    _, sections = doc
    wsl = _top(sections, "2. WSL window")
    step3 = dict(_step_ids(_children(sections, wsl, 3), r"^WSL step (\w+)\b"))["3"]
    code = " ".join(_code_lines(step3.all_fences))
    for writer in ("session-recall", "update_financials", "run_refresh_once"):
        assert writer in code, f"WSL step 3 does not stop {writer}"
    prose = " ".join(step3.all_prose)
    for cite in ("wsl-environment.md:52", "wsl-environment.md:66", "wsl_startup_hook.sh:231"):
        assert cite in prose, f"WSL step 3 does not cite {cite}"


def test_wsl_step_4_runs_the_compatibility_checks(doc):
    _, sections = doc
    wsl = _top(sections, "2. WSL window")
    step4 = dict(_step_ids(_children(sections, wsl, 3), r"^WSL step (\w+)\b"))["4"]
    code = " ".join(_code_lines(step4.all_fences))
    assert "manifest_diff" in code and "pg_compat_checks" in code


# --- Behavior Contract 3: release ---------------------------------------------------------------


def _release_steps(sections: list[Section]) -> list[tuple[str, Section]]:
    rel = _top(sections, "4. Release")
    return _step_ids(_children(sections, rel, 3), r"^Release step (R\d+)\b")


def test_v8_dr_drill_precedes_every_release_step(doc):
    _, sections = doc
    steps = _release_steps(sections)
    assert len(steps) >= 4
    first_id, first = steps[0]
    assert first_id == "r1" and "V8" in first.title and "drill" in first.title.lower()
    assert "fabrik vultr drill hub" in " ".join(_code_lines(first.all_fences))
    for _, sec in steps[1:]:
        assert sec.start >= first.end, "a release step sits inside or before the V8 drill"


def test_v8_drill_verifies_contents_independently_of_the_script(doc):
    """B3: step 12 counts restic rc 0 as restored and step 14 reads a psql failure as empty."""
    _, sections = doc
    r1 = _release_steps(sections)[0][1]
    code = " ".join(_code_lines(r1.all_fences))
    assert "pg18-drill-verify" in code and "--network none" in code
    assert "pg_database" in code and "count(*)" in code
    prose = " ".join(r1.all_prose)
    for cite in ("bootstrap-hub.sh:972", "bootstrap-hub.sh:1330", "bootstrap-hub.sh:1232"):
        assert cite in prose, f"V8 drill does not cite {cite}"
    assert "SELECT datname FROM pg_database" in prose


def test_release_removals_are_gated_on_the_operators_word(doc):
    _, sections = doc
    steps = dict(_release_steps(sections))
    removals = [
        s
        for s in steps.values()
        if "remove" in s.title.lower() and "backrest" not in s.title.lower()
    ]
    assert len(removals) >= 2, "release must carry the old-volume and the WSL-16-cluster removals"
    for sec in removals:
        assert _has_marker(sec.all_prose, GATE_MARKER), f"{sec.title}: no operator's-word gate"


def _destructive(text: str) -> str | None:
    norm = re.sub(r"\s+", " ", text)
    for token in DESTRUCTIVE:
        if token in norm:
            return token
    return None


def test_no_destructive_line_outside_an_operator_word_block(doc):
    """E2-1: the gate is bound to the BLOCK — the prose right before the fence holding the command
    must carry the marker line; a destructive command in prose must sit on the marker line itself."""
    lines, _ = doc
    ranges = _fence_ranges(lines)
    inside = {i: (a, b) for a, b in ranges for i in range(a + 1, b)}
    for idx, line in enumerate(lines):
        token = _destructive(line)
        if token is None:
            continue
        if idx in inside:
            start = inside[idx][0]
            assert _has_marker(_preceding_prose(lines, start), GATE_MARKER), (
                f"line {idx + 1} ({token!r}): its fenced block is not preceded by the operator's-word line"
            )
        else:
            assert line.strip().startswith(GATE_MARKER), (
                f"line {idx + 1} ({token!r}) is a destructive command in prose outside a marker line"
            )


def test_release_steps_have_command_verify_rollback(doc):
    """E2-2: R1-R4 carry their own command block, Verify and Rollback."""
    _, sections = doc
    for rid, sec in _release_steps(sections):
        assert _code_lines(sec.fences), f"release step {rid}: no command block"
        assert _has_marker(sec.prose, "**Verify:**"), f"release step {rid}: no Verify line"
        assert _has_marker(sec.prose, "**Rollback:**"), f"release step {rid}: no Rollback line"


def test_pre_window_snapshot_restore_needs_the_old_volume_name(doc):
    _, sections = doc
    rel = _top(sections, "4. Release")
    notes = [
        s for s in sections if rel.start < s.start < rel.end and "pre-window" in s.title.lower()
    ]
    assert notes, "release section has no pre-window snapshot restore note"
    code = " ".join(_code_lines(notes[0].all_fences))
    assert "--include /var/lib/docker/volumes/postgres-data" in code


# --- Review finding B2/R3: snapshot before the DR-chain merge ----------------------------------


def test_backrest_snapshot_precedes_the_dr_chain_merge(doc):
    _, sections = doc
    step8 = _hub_steps(sections)["8"]
    subs = _children(sections, step8, 4)
    snap = [s for s in subs if "backrest" in s.title.lower() and "snapshot" in s.title.lower()]
    merge = [s for s in subs if "fleet-pg18-dr" in s.title]
    assert len(snap) == 1 and len(merge) == 1
    assert snap[0].start < merge[0].start, "the DR-chain merge comes before the Backrest snapshot"
    snap_id = snap[0].title.split()[0]
    pre = [ln for ln in merge[0].prose if ln.strip().startswith("**Precondition:**")]
    assert pre and snap_id in pre[0], f"the merge step's Precondition does not name step {snap_id}"
    assert "PG_VERSION" in " ".join(_code_lines(merge[0].fences)), (
        "the merge step does not check the snapshot"
    )


def test_backrest_plan_scope_is_verified_not_assumed(doc):
    _, sections = doc
    step8 = _hub_steps(sections)["8"]
    snap = next(s for s in _children(sections, step8, 4) if "snapshot" in s.title.lower())
    code = " ".join(_code_lines(snap.fences))
    assert "/opt/backrest/config/config.json" in code
    assert ".paths" in code and "excludes" in code
    assert "postgres18-data/_data/18/docker/PG_VERSION" in code


# --- Seams ----------------------------------------------------------------------------------------


def test_seam_t02_installed_compose_equals_the_repo_compose(doc):
    _, sections = doc
    step4 = _hub_steps(sections)["4"]
    blocks = [b for b in step4.all_fences if "<<'YAML'" in b]
    assert len(blocks) == 1, "hub step 4 must install the compose from exactly one heredoc"
    body = blocks[0].split("<<'YAML'", 1)[1].split("\n", 1)[1]
    body = re.split(r"^YAML\s*$", body, maxsplit=1, flags=re.M)[0]
    assert yaml.safe_load(body) == _compose()


def test_seam_t02_every_window_image_is_the_compose_image(doc):
    _, sections = doc
    svc = _compose()["services"]["postgres-main"]
    image, mount = svc["image"], svc["volumes"][0]
    assert mount in "\n".join(_hub_steps(sections)["4"].all_fences)
    used = set()
    for prefix in ("0.", "1.", "3. Hub window", "4. Release"):
        top = _top(sections, prefix)
        for line in _code_lines(top.all_fences):
            used.update(re.findall(r"\bpostgres:\d[\w.\-]*", line))
    assert used == {image}, f"window images {used} differ from the compose image {image}"
    step3 = " ".join(_code_lines(_hub_steps(sections)["3"].all_fences))
    assert image in step3 and "pg_dumpall" in step3


def test_seam_t03_step_8_names_the_volume_the_dr_chain_restores(doc):
    _, sections = doc
    vol = _dr_postgres_volume()
    assert vol in _compose()["volumes"], "compose external volume and DR volume disagree"
    step8 = _hub_steps(sections)["8"]
    merge = next(s for s in _children(sections, step8, 4) if "fleet-pg18-dr" in s.title)
    assert vol in " ".join(_code_lines(merge.fences))
    assert vol in " ".join(_code_lines(_release_steps(sections)[0][1].all_fences))


# --- Behavior Contract 4: the appendix -------------------------------------------------------------

APPENDIX = {
    "brand-identiy-creator": (
        "src/brand_identity/models/tenant.py:27",
        "services/checkpoints.py:137,219",
        "migrations/versions/0001_initial_schema.py:20",
        "db/schema.sql:3,14",
        "README.md:117",
    ),
    "tryton-crm": (
        "compose.dev.yaml:71",
        "compose.dev.yaml:93",
        ".env.example:49",
        "trytond.conf:4",
        "docker/docker-compose.local.yml:38",
        "docker/docker-compose.local.yml:44",
    ),
    "trade-intelligence": (
        ".github/workflows/ci.yml:25",
        "scripts/verify_fresh_bootstrap.py:58",
        "scripts/run_db_suite_clean.sh:32",
        "tests/db/test_roles_sql_attributes.py:95",
        ".env.example:29",
        "web/playwright.r21-write.config.ts:13",
    ),
    "gmail-account-creator": (
        ".github/workflows/ci.yml:12",
        "scripts/ci_local.sh:8",
        "scripts/backfill_ci.py",
    ),
    "youtube": (".github/workflows/test.yml:15", "postgresql-16-pgvector"),
    "calendar-orchestration-engine": (
        "Dockerfile.scheduler:12",
        "postgresql-client-18",
        "ca-certificates",
        "gnupg",
    ),
    "fabrik-lib": ("fastapi-user-auth/README.md:791", "fastapi_user_auth/schema.sql:3"),
}


def _appendix(sections: list[Section]) -> list[Section]:
    return _children(sections, _top(sections, "5. Appendix"), 3)


@pytest.mark.parametrize("project", sorted(APPENDIX))
def test_appendix_request_names_the_projects_files(doc, project):
    _, sections = doc
    hits = [s for s in _appendix(sections) if project in s.title]
    assert len(hits) == 1, f"expected one appendix request naming {project}"
    body = "\n".join(hits[0].all_fences)
    assert "mail.py send" in body, f"{project}: no send command"
    for needle in APPENDIX[project]:
        assert needle in body, f"{project}: request does not name {needle}"


def test_appendix_pairs_and_d6(doc):
    _, sections = doc
    titles = [s.title for s in _appendix(sections)]
    assert any("tryton-crm" in t and "tojlo-mail" in t for t in titles)
    assert any("gmail-account-creator" in t and "fabrik-claim-validator" in t for t in titles)
    assert any("trade-intelligence" in t and "D6" in t for t in titles)


def test_doc_only_projects_share_one_broadcast(doc):
    _, sections = doc
    hits = [s for s in _appendix(sections) if "doc-only" in s.title.lower()]
    assert len(hits) == 1 and "27" in hits[0].title
    bodies = [b for b in hits[0].all_fences if "<<'BODY'" in b]
    assert len(bodies) == 1, "the 27 doc-only projects must share ONE broadcast body"
    assert "mail.py send" in bodies[0]


def test_appendix_send_timing_is_structural(doc):
    """E2-3: A1 (D7) goes BEFORE the WSL window; every other request AFTER the hub window."""
    _, sections = doc
    seen = {}
    for sec in _appendix(sections):
        sends = [ln.strip() for ln in sec.prose if ln.strip().startswith("**Send:**")]
        assert len(sends) == 1, f"{sec.title}: expected one **Send:** line"
        seen[sec.title.split()[0]] = sends[0].split()[1]
    assert seen.pop("A1") == "BEFORE-WSL-WINDOW"
    assert seen.pop("A9") == "NONE"
    assert seen and set(seen.values()) == {"AFTER-HUB-WINDOW"}, seen


# --- Wave-2 review fixups (pass 1) ---------------------------------------------------------------


def _wsl_step(sections: list[Section], sid: str) -> Section:
    return dict(
        _step_ids(_children(sections, _top(sections, "2. WSL window"), 3), r"^WSL step (\w+)\b")
    )[sid]


_WSL2_STUBS = r"""
pg_lsclusters() { printf '%s\n' "16 main 5432 online postgres /x" ${FAKE18:+"$FAKE18"}; }
sudo() { [ "$1" = -u ] && shift 2; "$@"; }
psql() { echo "PSQL $*" >> "$LOG"; [ "$FAKE_PSQL" = fail ] && return 2; echo "$FAKE_PSQL"; }
pg_dropcluster() { echo "DROP $*" >> "$LOG"; return "${DROP_RC:-0}"; }
"""


@pytest.mark.parametrize(
    ("fake18", "fake_psql", "drop_rc", "dropped", "port"),
    [
        ("18 main 5432 online postgres /x", "0", "0", False, None),
        ("18 main 5433 online postgres /x", "fail", "0", False, "5433"),
        ("18 main 5433 online postgres /x", "3", "0", False, "5433"),
        ("18 main 5434 online postgres /x", "0", "0", True, "5434"),
        ("18 main 5433 online postgres /x", "0", "1", True, "5433"),
        ("", "0", "0", False, None),
    ],
)
def test_wsl_step_2_never_drops_a_cluster_that_is_not_the_empty_install(
    doc, tmp_path, fake18, fake_psql, drop_rc, dropped, port
):
    """E1-1/E1-14: the guard EXECUTED with stubbed host tools — port read from pg_lsclusters, 5432
    refused, a failed query refused, a non-empty cluster refused, a failed drop reported as failed."""
    _, sections = doc
    block = _block_with(_wsl_step(sections, "2"), "pg_dropcluster")
    log = tmp_path / "log"
    log.write_text("")
    out = _run_bash(
        _WSL2_STUBS + block,
        {"FAKE18": fake18, "FAKE_PSQL": fake_psql, "DROP_RC": drop_rc, "LOG": str(log)},
    )
    calls = log.read_text()
    assert ("DROP 18 main" in calls) == dropped, out + calls
    if port:
        assert re.search(rf"PSQL .*-p {port}\b", calls), calls
    if drop_rc != "0":
        assert "dropped the empty" not in out and "FAILED" in out, out


def test_hub_step_5_ports_auto_conf_faithfully(doc):
    """E1-2: list GUCs survive — the 16 auto.conf lines are appended, never re-quoted as one value."""
    _, sections = doc
    code = _code_lines(_hub_steps(sections)["5"].all_fences)
    joined = "\n".join(code)
    assert not re.search(r"ALTER\s+SYSTEM\s+SET\s+%s", joined, re.I), (
        "settings re-quoted via printf"
    )
    src = [i for i, ln in enumerate(code) if "conf16/postgresql.auto.conf" in ln]
    app = [
        i
        for i, ln in enumerate(code)
        if re.search(r"cat\s*>>\s*\\?\"?\$PGDATA/postgresql\.auto\.conf", ln)
    ]
    chk = [i for i, ln in enumerate(code) if "pg_file_settings" in ln]
    rst = [i for i, ln in enumerate(code) if "docker restart postgres-main" in ln]
    assert src and app and chk and rst, (src, app, chk, rst)
    assert src[0] < app[0] < chk[0] < rst[0], "port, then the file-settings check, then the restart"


def test_dumps_count_only_on_exit_0_and_a_full_read(doc):
    """E1-3: every dump writes its .ok marker on exit 0, skip-guards key on the marker, the verify is
    a FULL read (pg_restore -f /dev/null), and pg_restore -l is no longer the test anywhere."""
    _, sections = doc
    hub = _hub_steps(sections)
    for sid in ("3", "6a"):
        assert not re.search(r"pg_restore\s+-l\b", " ".join(_code_lines(hub[sid].all_fences))), sid
    code = _code_lines(hub["3"].all_fences)
    dumps = [ln for ln in code if re.search(r"\bpg_dump(all)?\s+-h\b", ln)]
    assert len(dumps) == 2, dumps
    for ln in dumps:
        m = re.search(r'>\s*"(\$\w+)"\s*&&\s*touch\s+"(\$\w+)\.ok"', ln)
        assert m and m.group(1) == m.group(2), f"dump not marked .ok on exit 0: {ln}"
        assert re.match(r'\[\s*-f\s+"\$\w+\.ok"\s*\]\s*\|\|', ln), (
            f"skip-guard not on the marker: {ln}"
        )
    assert any("pg_restore -f /dev/null" in ln for ln in code)
    block = _block_with(hub["6a"], "DROP DATABASE")
    lines = _code_lines([block])
    drop = next(i for i, ln in enumerate(lines) if "DROP DATABASE" in ln)
    guard = [
        i
        for i, ln in enumerate(lines[:drop])
        if re.match(r'if\s+\[\s*-f\s+"\$\w+\.ok"\s*\]\s*&&.*pg_restore\s+-f\s+/dev/null', ln)
    ]
    assert guard, "step 6a drops glitchtip without the .ok + full-read guard"


def test_password_file_lives_in_ram_and_is_proven_and_shredded(doc):
    """E1-4/E1-5: the env file is never under /opt; it is proven before use and shredded after the dumps."""
    lines, sections = doc
    code_all = _code_lines([b for s in sections if s.level == 2 for b in s.all_fences])
    for ln in code_all:
        for arg in re.findall(r"--env-file\s+(\S+)", ln):
            assert arg == '"$PGENV"', f"--env-file not the RAM file: {ln}"
        if "PGPASSWORD=" in ln:
            m = re.search(r'>\s*"?(\S+?)"?\s*\)', ln)
            assert m and m.group(1) == "$PGENV", f"password written elsewhere: {ln}"
        if re.match(r"PGENV_DIR=", ln):
            assert re.match(r"PGENV_DIR=\$\(mktemp -d /dev/shm/", ln), ln
        assert not re.search(r"--env-file\s+\S*(/opt|\$W|\$P)\b", ln), ln
    code = _code_lines(_hub_steps(sections)["3"].all_fences)
    proof = next(i for i, ln in enumerate(code) if "SELECT 1" in ln and "PGENV" in ln)
    first_dump = next(i for i, ln in enumerate(code) if "pg_dumpall" in ln)
    last_dump = max(i for i, ln in enumerate(code) if re.search(r"\bpg_dump\s+-h\b", ln))
    shred = [i for i, ln in enumerate(code) if re.search(r'shred\s+-u\s+"\$PGENV"', ln)]
    assert proof < first_dump, "the password is not proven before the first dump"
    assert any(i > last_dump for i in shred), (
        "the password file is not shredded after the last dump"
    )


def test_wsl_step_2a_trusts_exit_status_and_reads_via_stdin(doc):
    """E1-6/E1-12: no trailer grep; dropdb only behind both .ok markers; restores read via stdin."""
    _, sections = doc
    sec = _wsl_step(sections, "2a")
    code = _code_lines(sec.fences)
    assert not any("dump complete" in ln for ln in code)
    dumps = [ln for ln in code if re.search(r"\bpg_dump\b", ln)]
    assert len(dumps) == 2 and all(re.search(r'&&\s*touch\s+"\$\w+\.ok"', ln) for ln in dumps), (
        dumps
    )
    drop = next(i for i, ln in enumerate(code) if "dropdb" in ln)
    assert any(re.search(r'-f\s+"\$D1\.ok".*-f\s+"\$D2\.ok"', ln) for ln in code[:drop]), (
        "dropdb not behind both markers"
    )
    assert not any(re.search(r"pg_restore\b[^<]*\$\w+[^<]*$", ln) and "<" not in ln for ln in code)
    rollback = _paragraph(sec.prose, "**Rollback:**")
    assert re.search(r"pg_restore[^`]*<\s*\"\$D2\"", rollback), rollback


_GO_STUB = "sudo() { return 0; }\n"


def _go_state(w: Path, drop: str | None = None) -> None:
    import os
    import time

    (w / "manifest-18").mkdir(parents=True)
    (w / "manifest-18" / "COMPLETE").write_text("5 files\n")
    old = time.time() - 100
    os.utime(w / "manifest-18" / "COMPLETE", (old, old))
    (w / "manifest-18.diffs").mkdir()
    (w / "manifest-18.diffs" / "cluster.txt").write_text("")
    (w / "restore.err").write_text('psql:<stdin>:20: ERROR:  role "postgres" already exists\n')
    (w / "compat-18.txt").write_text("trgm index|app|t_s_idx|valid=true\n")
    (w / "glitchtip-6a.ok").write_text("glitchtip wrote nothing\n")
    (w / "stopped-services.txt").write_text("app-api\n")
    if drop:
        target = w / drop
        if target.is_dir():
            for f in target.iterdir():
                f.unlink()
            target.rmdir()
        else:
            target.unlink()


@pytest.mark.parametrize(
    "missing",
    [
        None,
        "manifest-18/COMPLETE",
        "manifest-18.diffs",
        "compat-18.txt",
        "glitchtip-6a.ok",
        "restore.err",
    ],
)
def test_step_7_go_requires_every_input(doc, tmp_path, missing):
    """E1-7: the GO check EXECUTED — a missing input is a NO-GO, never a 0 that reads as GO."""
    _, sections = doc
    block = _block_with(_hub_steps(sections)["7"], "go=GO")
    _go_state(tmp_path, missing)
    out = _run_bash(_GO_STUB + block, {"W": str(tmp_path)})
    last = out.strip().splitlines()[-1]
    assert last == ("GO" if missing is None else "NO-GO"), out


def test_step_7_go_rejects_an_invalid_trgm_index_and_stale_diffs(doc, tmp_path):
    _, sections = doc
    block = _block_with(_hub_steps(sections)["7"], "go=GO")
    _go_state(tmp_path)
    (tmp_path / "compat-18.txt").write_text("trgm index|app|t_s_idx|valid=false\n")
    assert _run_bash(_GO_STUB + block, {"W": str(tmp_path)}).strip().splitlines()[-1] == "NO-GO"


def test_after_readings_are_retaken(doc):
    """E1-8: every AFTER reading of the new cluster is retaken, and the helper supports it."""
    _, sections = doc
    for code in (
        _code_lines(_hub_steps(sections)["6"].all_fences),
        _code_lines(_wsl_step(sections, "4").fences),
    ):
        calls = [ln for ln in code if re.search(r"\bpg_manifest\b.*manifest-18", ln)]
        assert calls and all("--retake" in ln for ln in calls), calls
    body = _function_body(sections, "pg_manifest")
    assert "--retake" in body and ".new" in body
    assert "COMPLETE" in _function_body(sections, "manifest_diff")


def test_every_rollback_restores_the_backup_cron_and_the_glitchtip_pin(doc):
    """E1-9: step 1's rollback and the step-7 NO-GO block put back the root crontab and the compose."""
    _, sections = doc
    hub = _hub_steps(sections)
    nogo = " ".join(_code_lines([_block_with(hub["7"], "ALTER SYSTEM RESET")]))
    rollback = _paragraph(hub["1"].all_prose, "**Rollback:**")
    for text in (nogo, rollback):
        assert re.search(r'crontab -u root "\$W/root-crontab\.before"', text), text[:200]
        assert re.search(
            r'cp -p "\$W/glitchtip-compose\.yaml\.orig" /opt/glitchtip/compose\.yaml', text
        )


def test_tunnel_is_kept_closed_through_the_window(doc):
    """E1-10: the hook's daily lock is pre-created, and the tunnel is re-checked before 7 and 8.4."""
    _, sections = doc
    hub = _hub_steps(sections)
    assert any(
        re.search(r"touch\s+\"/tmp/\.fabrik_daily_\$", ln)
        for ln in _code_lines(hub["1"].all_fences)
    )
    step84 = next(s for s in _children(sections, hub["8"], 4) if s.title.startswith("8.4"))
    for sec in (hub["7"], step84):
        assert any(ln.startswith("pgrep -af '15432:") for ln in _code_lines(sec.fences)), sec.title


def test_step_1_reports_unknown_writers_before_terminating(doc):
    """E1-11: clients are recorded and mapped BEFORE pg_terminate_backend; the count is watched."""
    _, sections = doc
    code = _code_lines(_hub_steps(sections)["1"].all_fences)
    rec = next(
        i for i, ln in enumerate(code) if "clients-at-freeze" in ln and "pg_stat_activity" in ln
    )
    rep_ = next(i for i, ln in enumerate(code) if "WRITER NOT ON THE STOP LIST" in ln)
    term = next(i for i, ln in enumerate(code) if "pg_terminate_backend" in ln)
    watch = [
        i
        for i, ln in enumerate(code)
        if re.search(r"for i in \$\(seq \d+\)", ln) and "pg_stat_activity" in ln
    ]
    assert rec < rep_ < term and watch and watch[0] > term


def test_spoke_blocks_are_labelled_where_they_run(doc):
    """E1-13: an ssh-to-spoke block runs on WSL, says so, and 8.4 reads the lists step 1 wrote."""
    lines, sections = doc
    for a, b in _fence_ranges(lines):
        body = lines[a + 1 : b]
        if body and re.search(r"#\s*on:\s*vps2", body[0]):
            assert not any("ssh" in ln for ln in body), body[0]
    hub = _hub_steps(sections)
    step84 = next(s for s in _children(sections, hub["8"], 4) if s.title.startswith("8.4"))
    w1 = " ".join(_code_lines(hub["1"].fences))
    w84 = " ".join(_code_lines(step84.fences))
    assert '"$HW/stopped-$h.txt"' in w1 and '"$HW/stopped-$h.txt"' in w84


def test_v8_drill_handles_leftovers_and_gates_its_cleanup(doc):
    """E2-4/E2-5: a non-running leftover is detected and recreated; the scratch rm is a gated command."""
    lines, sections = doc
    r1 = _release_steps(sections)[0][1]
    code = _code_lines(r1.fences)
    assert any(
        re.search(r"docker inspect -f '\{\{\.State\.Status\}\}' pg18-drill-verify", ln)
        for ln in code
    )
    assert any(re.search(r"docker rm pg18-drill-verify", ln) for ln in code)
    rm_lines = [i for i, ln in enumerate(lines) if re.search(r'sudo rm -rf -- "\$V"', ln)]
    assert len(rm_lines) == 1
    start = max(a for a, b in _fence_ranges(lines) if a < rm_lines[0] < b)
    assert _has_marker(_preceding_prose(lines, start), GATE_MARKER), "the scratch rm is not gated"
