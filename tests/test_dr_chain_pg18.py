"""T03 — the DR chain restores `postgres18-data`, never the retired `postgres-data`.

Spec: docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md § The delta › D3
(the DR-chain hunk) + D1 step 8. `postgres-main`'s data volume moves from `postgres-data` to
`postgres18-data` on the PG18 upgrade; every DR script and doc that names the volume must follow,
or a disaster recovery run in the gap between the compose cutover and this merge restores the
WRONG (empty, pre-cutover) volume name and `postgres-main` never boots.

`postgres-data` is kept until release as the Backrest safety copy (D1 step 8), so this is a
whole-word check: `postgres18-data` must never be mistaken for a match.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

BOOTSTRAP_CONFIG = REPO_ROOT / "scripts" / "bootstrap" / "bootstrap-config.sh"
BOOTSTRAP_HUB = REPO_ROOT / "scripts" / "bootstrap" / "bootstrap-hub.sh"

# The six files T03 owns — every live `postgres-data` mention here must now read `postgres18-data`.
OWNED_FILES = [
    REPO_ROOT / "scripts" / "bootstrap" / "bootstrap-config.sh",
    REPO_ROOT / "scripts" / "bootstrap" / "bootstrap-hub.sh",
    REPO_ROOT / "src" / "fabrik" / "orchestrator" / "vultr_drill.py",
    REPO_ROOT / "docs" / "operations" / "hub-restore-inventory.md",
    REPO_ROOT / "docs" / "operations" / "disaster-recovery.md",
    REPO_ROOT / "docs" / "infrastructure" / "vps-hub-rebuild.md",
]

# Whole-word: `postgres18-data` must never match (the digits sit right after `postgres`,
# so a plain substring search would false-positive on the new name).
_POSTGRES_DATA_WHOLE_WORD = re.compile(r"(?<![\w-])postgres-data(?![\w-])")

# A whole-word "11" — a bare substring check would false-pass on "110" (B4).
_ELEVEN_WHOLE_WORD = re.compile(r"\b11\b")

# A `datname IN (...)` clause whose first literal isn't single-quoted: `remote '...'` is itself
# single-quoted, so EITHER double-quote spelling — the escaped `\"glitchtip\"` B1 found, or a bare
# `"glitchtip"` — reaches psql as a DOUBLE-QUOTED IDENTIFIER, not a string literal; the query
# errors, `dblist` comes back empty via the `|| true`/`|| echo ""` fallback, and the probe
# silently never matches anything (B1, generalized by N1). A single-quoted `'glitchtip'` is the
# only spelling that would survive.
_DATNAME_IN_NOT_SINGLE_QUOTED = re.compile(r"datname\s+IN\s*\(\s*(?!')")

# The exact, quoting-free query both postgres18-data restore probes must send — it sidesteps
# literal quoting entirely rather than getting it right inside a nested-quote remote string.
_EXPECTED_PSQL_QUERY = 'psql -U postgres -tAc "SELECT datname FROM pg_database"'

DISASTER_RECOVERY_MD = REPO_ROOT / "docs" / "operations" / "disaster-recovery.md"

# The two postgres18-data restore probe sites B1 fixed — both must require BOTH database
# names (as step_12c already did via `&&`); step_14 used to accept EITHER one via `grep -qE
# "a|b"`, which means a half-restored cluster missing one of the two databases would read as
# "intact" and skip the pg_dump fallback that would have fixed it.
_PROBE_FUNCTIONS = ("step_12c_start_core_services_drill", "step_14_pg_dump_restore_fallback")

# The live (non-comment) `if` line both probe sites must carry, requiring BOTH names — anchored
# to line start so a whole-body substring search can't be satisfied by a COMMENTED-OUT copy of
# the same text sitting beside a live broken check (N2).
_REQUIRES_BOTH_IF_LINE = re.compile(
    r'^\s*if echo "\$dblist" \| grep -qx glitchtip && echo "\$dblist" \| grep -qx site_provisioner; then',
    re.M,
)


def _strip_bash_comments(body: str) -> str:
    """Drop full-line bash comments from a function body.

    A structural check reads what the function actually RUNS; a comment — whether it shows the
    right pattern (and would wrongly pass a search over the raw body) or the old wrong pattern
    (and would wrongly fail one) — is not code (N2)."""
    return "\n".join(line for line in body.splitlines() if not line.strip().startswith("#"))


def _extract_bash_function(text: str, name: str) -> str:
    """Return the full body of a top-level `name() {` ... `}` bash function.

    bootstrap-hub.sh defines every step function with the opening brace on the `name() {`
    line and the closing brace alone on its own line at column 0 (verified: `grep -n
    '^step_12c_start_core_services_drill\\|^}'`), so a plain line scan is reliable here —
    no nested top-level function can share that column-0 closing brace.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{name}() {{")), None)
    assert start is not None, f"function {name}() not found in {BOOTSTRAP_HUB.name}"
    end = next((j for j in range(start + 1, len(lines)) if lines[j] == "}"), None)
    assert end is not None, f"no column-0 closing brace found for {name}()"
    return "\n".join(lines[start : end + 1])


def _sourced_restore_volumes() -> list[str]:
    """Source bootstrap-config.sh in bash and return FABRIK_HUB_VOLUMES_TO_RESTORE."""
    assert BOOTSTRAP_CONFIG.is_file(), f"missing {BOOTSTRAP_CONFIG}"
    script = (
        f'source "{BOOTSTRAP_CONFIG}" && printf "%s\\n" "${{FABRIK_HUB_VOLUMES_TO_RESTORE[@]}}"'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"sourcing bootstrap-config.sh failed: rc={result.returncode} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_bootstrap_config_restores_both_postgres_volumes_until_release() -> None:
    """D-647: the DR chain reached master before the hub window, so FABRIK_HUB_VOLUMES_TO_RESTORE
    carries `postgres18-data` AND `postgres-data` until PG18 release step R3 — a rebuild in the gap
    must restore the PG16 volume the live compose still mounts (without it step 13's compose-up
    fails and step 14's pg_dump fallback never runs), and a rebuild after the window the PG18 one.
    Step 12 skips the volume a snapshot does not hold, so carrying both is safe on either side."""
    volumes = _sourced_restore_volumes()
    pg = [v for v in volumes if v.startswith("postgres")]
    assert pg == ["postgres18-data", "postgres-data"], (
        f"FABRIK_HUB_VOLUMES_TO_RESTORE must restore both Postgres volumes until R3: {pg}"
    )


def test_no_owned_file_names_the_retired_postgres_data_volume() -> None:
    """Whole-word scan (so `postgres18-data` never false-matches) over every file T03 owns —
    comments, log strings, and docs included. A surviving `postgres-data` mention means a DR run
    in the gap between the compose cutover and this merge would restore the wrong volume. The one
    sanctioned exception is a line citing D-647 (the PG16 volume kept until release step R3)."""
    offenders: list[str] = []
    for path in OWNED_FILES:
        assert path.is_file(), f"missing owned file: {path}"
        text = path.read_text()
        # the DR doc's restore loop is pinned to the config list (D-647 line included) by
        # test_disaster_recovery_restore_loop_matches_bootstrap_config_volumes — defer to it
        loop = (
            re.search(r"for vol in .*?; do", text, re.DOTALL)
            if path == DISASTER_RECOVERY_MD
            else None
        )
        loop_lines = (
            set(range(text.count("\n", 0, loop.start()) + 1, text.count("\n", 0, loop.end()) + 2))
            if loop
            else set()
        )
        for lineno, line in enumerate(text.splitlines(), start=1):
            if lineno in loop_lines:
                continue
            if _POSTGRES_DATA_WHOLE_WORD.search(line) and "D-647" not in line:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, "retired `postgres-data` mention(s) survive:\n" + "\n".join(offenders)


def test_disaster_recovery_volume_count_comment_says_eleven() -> None:
    """The docker-volumes restore-loop comment must say 11 — the Backrest plan backs up both
    Postgres volumes until release (10 + 1), even though the restore loop itself only lists 10.

    Whole-word: a bare substring check for "11" false-passes on "110" (B4)."""
    lines = DISASTER_RECOVERY_MD.read_text().splitlines()
    count_lines = [line for line in lines if "docker-volumes plan" in line and "backs up" in line]
    assert count_lines, (
        "could not find the docker-volumes plan count comment in "
        f"{DISASTER_RECOVERY_MD.relative_to(REPO_ROOT)}"
    )
    assert any(_ELEVEN_WHOLE_WORD.search(line) for line in count_lines), (
        f"volume-count comment does not say 11 (whole word): {count_lines}"
    )


def test_disaster_recovery_restore_loop_matches_bootstrap_config_volumes() -> None:
    """The `for vol in ...; do` restore loop in disaster-recovery.md must restore exactly the
    volumes FABRIK_HUB_VOLUMES_TO_RESTORE names — the two lists are hand-kept in two files and
    a rename to one without the other silently restores the wrong set (B4)."""
    text = DISASTER_RECOVERY_MD.read_text()
    match = re.search(r"for vol in (.*?); do", text, re.DOTALL)
    assert match, (
        f"could not find the `for vol in ...; do` restore loop in "
        f"{DISASTER_RECOVERY_MD.relative_to(REPO_ROOT)}"
    )
    loop_volumes = set(match.group(1).replace("\\\n", " ").split())
    sourced_volumes = set(_sourced_restore_volumes())
    assert loop_volumes == sourced_volumes, (
        "disaster-recovery.md's restore loop disagrees with "
        "FABRIK_HUB_VOLUMES_TO_RESTORE — "
        f"only in the doc: {loop_volumes - sourced_volumes}; "
        f"only in bootstrap-config.sh: {sourced_volumes - loop_volumes}"
    )


def test_bootstrap_hub_probe_sites_query_datname_without_literal_quoting() -> None:
    """Each probe site must send psql a bare `SELECT datname FROM pg_database` — no `datname IN
    (...)` clause at all. EITHER double-quote spelling of its literals breaks inside the
    single-quoted `remote '...'` wrapper — the escaped `\\"glitchtip\\"` form B1 found, and a bare
    `"glitchtip"` form are equally broken, both reaching psql as a DOUBLE-QUOTED IDENTIFIER, not a
    string literal (N1, generalizing B1: CONFIRMED against a scratch cluster with the escaped form,
    `ERROR: column "glitchtip" does not exist`). The exact-string check on each probe site locks in
    the fix that sidesteps literal quoting entirely, rather than merely swapping one broken spelling
    for the other."""
    text = BOOTSTRAP_HUB.read_text()
    offenders = [
        f"{lineno}: {line.strip()}"
        for lineno, line in enumerate(text.splitlines(), start=1)
        if _DATNAME_IN_NOT_SINGLE_QUOTED.search(line)
    ]
    assert not offenders, (
        "a `datname IN (...)` clause survives without single-quoted literals:\n"
        + "\n".join(offenders)
    )
    for name in _PROBE_FUNCTIONS:
        body = _strip_bash_comments(_extract_bash_function(text, name))
        assert _EXPECTED_PSQL_QUERY in body, (
            f"{name}() does not query exactly `{_EXPECTED_PSQL_QUERY}`:\n{body}"
        )


def test_bootstrap_hub_probe_sites_require_both_databases() -> None:
    """Both postgres18-data restore probes (step_12c, step_14) must require BOTH `glitchtip`
    AND `site_provisioner` present, on a REAL (non-comment) `if` line — step_14 used to accept
    EITHER one via `grep -qE "glitchtip|site_provisioner"`, so a half-restored cluster missing one
    database would read as intact and skip the pg_dump fallback that would have fixed it (B1). A
    whole-body substring search is comment-blind: a commented-out
    `# grep -qx glitchtip && grep -qx site_provisioner` sitting beside a live broken check would
    wrongly pass it (N2)."""
    text = BOOTSTRAP_HUB.read_text()
    for name in _PROBE_FUNCTIONS:
        body = _strip_bash_comments(_extract_bash_function(text, name))
        assert _REQUIRES_BOTH_IF_LINE.search(body), (
            f"{name}() has no live (non-comment) if-line requiring BOTH "
            f"glitchtip AND site_provisioner:\n{body}"
        )
        assert "glitchtip|site_provisioner" not in body, (
            f"{name}() still carries a live either-one alternation pattern:\n{body}"
        )
