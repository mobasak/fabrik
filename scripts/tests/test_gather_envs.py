#!/usr/bin/env python3
# AFTER-EDIT: scripts/gather_envs.py scripts/classify_services.py
"""Behavior-Contract regression tests for the env consolidator + classifier (Phase A).

Guards the two bugs that slipped this build: the empty-value false-merge and the
idempotency-compare defect. Loads the scripts by path (scripts/ is not a package).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

needs_rg = pytest.mark.skipif(shutil.which("rg") is None, reason="the scan shells out to ripgrep")

SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ge = _load("gather_envs")
cs = _load("classify_services")
rs = _load(
    "registry_sync"
)  # the #svc consumer — its SVC_RE must read every line svc_line emits (AP2)


def _envs(tmp_path: Path, projects: dict[str, str]) -> list[Path]:
    """projects: {project_name: env_file_text} -> list of the .env Paths."""
    files = []
    for proj, text in projects.items():
        d = tmp_path / proj
        d.mkdir()
        f = d / ".env"
        f.write_text(text, encoding="utf-8")
        files.append(f)
    return files


def test_empty_values_never_merge(tmp_path):
    """Given two projects with empty *_API_KEY/*_PASSWORD, When consolidated,
    Then the empty values are skipped and never fused into one entry (the 22-way bug)."""
    files = _envs(
        tmp_path,
        {
            "proj_a": "ANTHROPIC_API_KEY=\nDB_PASSWORD=\n",
            "proj_b": "OPENAI_API_KEY=\nSMTP_PASSWORD=\n",
        },
    )
    body, stats = ge.consolidate(files)
    assert stats["skipped_empty"] == 4
    # No secret line should carry another key as an alias (the false-merge signature).
    assert "aliases:" not in body
    assert "ANTHROPIC_API_KEY" not in body  # empty -> skipped entirely


def test_idempotent_body(tmp_path):
    """Given unchanged input, When consolidate runs twice, Then the body is byte-identical."""
    files = _envs(tmp_path, {"proj_a": "FOO_API_KEY=sk-realvalue-1234567890\nPORT=8000\n"})
    body1, _ = ge.consolidate(files)
    body2, _ = ge.consolidate(files)
    assert body1 == body2


def test_read_existing_body_roundtrip_the_real_idempotency_guard(tmp_path):
    """Given a written all-envs.env, When read_existing_body reads it back, Then it equals the
    freshly-generated body — the ACTUAL guard for the read_existing_body split bug that dropped the
    leading '# ' and made every cron run rewrite the file (consolidate() determinism alone missed it)."""
    files = _envs(tmp_path, {"proj_a": "FOO_API_KEY=sk-realvalue-1234567890\nPORT=8000\n"})
    body, _ = ge.consolidate(files)
    out = tmp_path / "all-envs.env"
    out.write_text("# AUTO-GENERATED\n# Generated: 2026-01-01\n#\n" + body + "\n", encoding="utf-8")
    # If the bug returned (split mid-line at the first ═), the '# ' prefix is dropped → not equal.
    assert ge.read_existing_body(out).rstrip() == body.rstrip()


def test_alias_merge_same_value_different_name(tmp_path):
    """Given the same secret under two different names, When consolidated,
    Then it collapses to one entry with the other name as an alias."""
    val = "sk-shared-abcdef1234567890"
    files = _envs(
        tmp_path,
        {"proj_a": f"OPENROUTER_API_KEY={val}\n", "proj_b": f"WATCHDOG_OPENROUTER_KEY={val}\n"},
    )
    body, _ = ge.consolidate(files)
    assert "aliases:" in body
    assert body.count(val) == 1  # one line, not two


def test_distinct_values_kept_separate(tmp_path):
    """Given the same key with two different values, When consolidated, Then both are kept."""
    files = _envs(
        tmp_path,
        {
            "proj_a": "SONIOX_API_KEY=aaaa1111bbbb2222cccc\n",
            "proj_b": "SONIOX_API_KEY=zzzz9999yyyy8888xxxx\n",
        },
    )
    body, _ = ge.consolidate(files)
    assert "aaaa1111bbbb2222cccc" in body
    assert "zzzz9999yyyy8888xxxx" in body


def test_catalog_fails_closed_on_malformed_json(tmp_path, monkeypatch):
    """Given a malformed service_catalog.json, When loaded, Then it is `CatalogError` — never a
    silently empty catalog that the sync would treat as "every vendor unknown" (BS2)."""
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(ge, "CATALOG_PATH", bad)
    with pytest.raises(ge.CatalogError, match="unreadable"):
        ge.load_catalog()


def test_classify_input_has_no_secret_values(tmp_path):
    """Given a flagged provider block, When flagged_providers parses it, Then only var NAMES
    (and public URL values) are collected — never a secret value (no leak to the pool)."""
    all_envs = tmp_path / "all-envs.env"
    bar = "═" * 20  # PRODUCTION uses Unicode ═, not ASCII = — the boundary check keys on "# ═"
    all_envs.write_text(
        f"# {bar} NEEDS-TRIAGE (category=?) {bar}\n"
        '#svc name=zari category=? cost=? capability="?" url=? status=?\n'
        "ZARI_API_KEY=super-secret-value-xyz   # used by: trade-intelligence\n"
        "ZARI_API_URL=https://api.zari.example/v1/sometoken   # used by: trade-intelligence\n"
        f"# {bar} internal-config (NOT a service) {bar}\n"
        "PORT=8000\n",
        encoding="utf-8",
    )
    provs = cs.flagged_providers(all_envs)
    assert "zari" in provs
    assert "ZARI_API_KEY" in provs["zari"]["names"]
    # The section boundary MUST be honored — the internal-config PORT is NOT captured under zari.
    assert "PORT" not in provs["zari"]["names"]
    blob = repr(provs["zari"])
    assert "super-secret-value-xyz" not in blob  # secret value never captured
    assert "sometoken" not in blob  # only scheme+host sent — the URL path token must NOT leak
    assert provs["zari"]["urls"] == ["https://api.zari.example"]


def test_tombstone_leaves_needs_triage_closing_the_daily_rebill_loop(tmp_path, monkeypatch):
    """C2 regression — the REAL re-bill invariant is gather_envs' NEEDS-TRIAGE bucketing,
    which keys SOLELY on category=='?' (gather_envs.py render loop), NOT on match-prefix.

    So a tombstone MUST carry a non-'?' category (classify writes 'unidentified') to render
    in its own section and drop OUT of NEEDS-TRIAGE — the block classify_services.flagged_providers
    re-dispatches (re-bills) from. A category='?' stub would STAY in triage and re-bill forever
    (the exact defect the earlier match_provider-only test failed to catch)."""
    cat = tmp_path / "service_catalog.json"
    cat.write_text(
        json.dumps({"weirdvendor": cs.tombstone_entry("weirdvendor")}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    files = _envs(
        tmp_path,
        {"proj": "WEIRDVENDOR_API_KEY=sk-tombstoned-001\nBRANDNEWTHING_API_KEY=tok-fresh-002\n"},
    )
    body, _ = ge.consolidate(files)
    assert "NEEDS-TRIAGE" in body
    above, triage = body.split("NEEDS-TRIAGE", 1)
    # tombstoned provider renders ABOVE (its own 'unidentified' section) — not in triage
    assert "WEIRDVENDOR_API_KEY" in above
    assert "WEIRDVENDOR_API_KEY" not in triage
    # a genuinely-uncatalogued key still lands in triage (billed once, correctly). Because
    # flagged_providers reads ONLY the triage block, the tombstoned provider is never re-picked.
    assert "BRANDNEWTHING_API_KEY" in triage


def test_build_proposals_tombstones_no_json_but_spares_transport_errors():
    """Pass-2 fix: the re-bill loop must close for a COMPLETED-but-no-JSON response too, not just
    an explicit category='?'. build_proposals exempts ONLY true transport errors (r.error set) from
    the tombstone path; a completed response with unparseable text is a genuine unidentifiable
    outcome and must fall through to be tombstoned (else it re-bills every daily run forever)."""
    from types import SimpleNamespace

    def _res(error, text):  # minimal stand-in for libs.subagents.AgentResult
        return SimpleNamespace(error=error, text=text)

    names = ["goodvendor", "nojsonvendor", "transportfail"]
    results = [
        _res(None, '{"category":"ai-llm","cost":"$","capability":"x","url":"u","status":"active"}'),
        _res(None, "Sorry, I really can't tell what this service is."),  # completed, no JSON
        _res("timeout after 600s", ""),  # true transport failure
    ]
    proposals, errored = cs.build_proposals(names, results)
    # transport failure is exempt (retries next run); the no-JSON one is NOT (it gets tombstoned)
    assert errored == {"transportfail"}
    assert "nojsonvendor" not in errored  # the closed re-bill hole
    # the no-JSON vendor falls back to category='?' → flows to the tombstone loop
    assert proposals["nojsonvendor"]["category"] == "?"
    assert proposals["goodvendor"]["category"] == "ai-llm"  # valid JSON parsed through


def test_tombstone_entry_is_non_question_category_with_scoped_prefix():
    """C2+C5: the tombstone classify writes must use a non-'?' category (else it never leaves
    NEEDS-TRIAGE) and a FULL-name match prefix (else `aws_bedrock` swallows every AWS_* key)."""
    entry = cs.tombstone_entry("aws_bedrock")
    assert entry["category"] not in (None, "?")  # C2: must exit the category=='?' triage bucket
    assert entry["category"] == "unidentified"
    assert entry["match"] == ["AWS_BEDROCK"]  # C5: scoped to the compound name, not ["AWS"]
    assert entry["status"] == "unidentified"


# ── the second input: code call sites (2026-09-02) ───────────────────────────────────────────


def test_host_sld_and_ignore_rules():
    """Registrable label + the three ignore classes (own/placeholder/reference-only unless api.)."""
    assert ge.host_sld("api.posthog.com") == "posthog"
    assert ge.host_sld("foo.co.uk") == "foo"
    assert ge.host_sld("posthog.com") == "posthog"
    assert ge.ignored_host("api.ocoron.com") and ge.ignored_host("ocoron.com")  # own + apex
    assert not ge.ignored_host("notocoron.com")  # a suffix match must respect the dot (H16)
    assert ge.ignored_host("evil.example")  # placeholder TLD
    assert ge.ignored_host("company.com")  # placeholder label
    assert ge.ignored_host("t.co")  # one-letter label = fixture/shortener
    assert not ge.ignored_host("qq.com")  # two-letter vendors exist
    assert ge.ignored_host("github.com")  # reference-only …
    assert not ge.ignored_host("api.github.com")  # … unless it is the API host
    # a vendor's own domain is NEVER reference-only; its docs subdomain is ignored by prefix
    assert not ge.ignored_host("graph.microsoft.com")
    assert not ge.ignored_host("registry-1.docker.io")
    assert not ge.ignored_host("sentry.io")
    assert ge.ignored_host("learn.microsoft.com")
    assert ge.ignored_host("docs.docker.com")
    assert not ge.ignored_host("api.posthog.com")
    assert ge.ignored_host("10.99.0.1")


def _repo(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    d = tmp_path / name
    (d / ".git").mkdir(parents=True)
    for rel, text in files.items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return d


@needs_rg
def test_code_hosts_attribute_catalog_provider_and_flag_unknown(tmp_path, monkeypatch):
    """Given a repo with NO .env that calls resend (catalogued, by url domain) and posthog
    (uncatalogued), When consolidated with code_dirs, Then resend gains the repo in used_by
    with a CODE_HOST_URL line, and posthog lands in NEEDS-TRIAGE with its url — the same
    queue the classifier drains. Runs the real ripgrep scan."""
    monkeypatch.setattr(ge, "OPT", tmp_path)
    monkeypatch.setattr(
        ge,
        "load_catalog",
        lambda: (
            {
                "resend": {
                    "category": "email",
                    "cost": "freemium",
                    "capability": "email",
                    "url": "https://resend.com",
                    "status": "active",
                    "match": ["RESEND"],
                }
            },
            [("RESEND", "resend")],
        ),
    )
    repo = _repo(
        tmp_path,
        "keyless-app",
        {
            "app.py": 'r = httpx.post("https://api.resend.com/emails")\nph = "https://us.i.posthog.com/i/v0/e"\n',
        },
    )
    body, stats = ge.consolidate([], code_dirs=[repo])
    assert "#svc name=resend category=email" in body and "used_by=keyless-app" in body
    assert "CODE_HOST_URL=https://api.resend.com   # used by: keyless-app" in body
    triage = body.split("NEEDS-TRIAGE", 1)[1]
    assert "#svc name=posthog category=?" in triage and "url=https://us.i.posthog.com" in triage
    assert stats["code_hosts"] == 2 and stats["code_only"] == 2


@needs_rg
def test_scan_skips_tests_docs_placeholders_and_reference_links(tmp_path, monkeypatch):
    """Fixtures, docs and reference links are NOT external systems — and github.com is a
    link while api.github.com is a call."""
    monkeypatch.setattr(ge, "OPT", tmp_path)
    repo = _repo(
        tmp_path,
        "app",
        {
            "svc.py": 'a = "https://api.github.com/repos"\nb = "https://github.com/org/repo"\n'
            'c = "https://evil.example/x"\nd = "https://api.stripe.com/v1"\n',
            "tests/test_x.py": 'u = "https://api.paddle.com/should-not-count"\n',
            "docs/notes.py": 'u = "https://api.axiom.co/not-a-call-site"\n',
            "README.md": "https://api.slack.com/md-files-are-not-source\n",
        },
    )
    hosts = ge.scan_code_hosts([repo])
    assert set(hosts) == {"api.github.com", "api.stripe.com"}
    assert hosts["api.stripe.com"]["projects"] == {"app"}


def test_consolidate_without_code_dirs_never_scans(tmp_path, monkeypatch):
    """code_dirs=None (every pre-existing caller/test) must not touch ripgrep at all."""
    monkeypatch.setattr(
        ge, "scan_code_hosts", lambda dirs: (_ for _ in ()).throw(AssertionError("scanned"))
    )
    body, stats = ge.consolidate(
        _envs(tmp_path, {"p": "RESEND_API_KEY=re_abcdefghijklmnopqrstuvwxyz123456\n"})
    )
    assert "CODE_HOST_URL" not in body and stats["code_hosts"] == 0


def test_classify_bound_is_sorted_and_zero_means_unlimited():
    provs = {n: {} for n in ("zeta", "alpha", "mid", "beta")}
    kept, deferred, cursor = cs.bound_flagged(provs, 2)
    assert list(kept) == ["alpha", "beta"] and deferred == 2 and cursor == "beta"
    assert cs.bound_flagged(provs, 0) == (provs, 0, None)
    assert cs.bound_flagged(provs, 10) == (provs, 0, None)


@needs_rg
def test_platform_domains_are_never_credited_to_one_vendor(tmp_path, monkeypatch):
    """`*.amazonaws.com` / `*.googleapis.com` name a cloud, not a product: an RDS truststore
    fetch must not become `aws-ses` usage; the service label is kept for triage instead."""
    monkeypatch.setattr(ge, "OPT", tmp_path)
    monkeypatch.setattr(
        ge,
        "load_catalog",
        lambda: (
            {
                "aws-ses": {
                    "category": "email",
                    "cost": "paid",
                    "capability": "email",
                    "url": "https://aws.amazon.com/ses",
                    "status": "active",
                    "match": ["SES", "AWS_SES"],
                }
            },
            [("AWS_SES", "aws-ses"), ("SES", "aws-ses")],
        ),
    )
    repo = _repo(
        tmp_path,
        "svc",
        {
            "db.py": 'u = "https://truststore.pki.rds.amazonaws.com/x"\ng = "https://gmail.googleapis.com/v1"\n',
        },
    )
    body, _ = ge.consolidate([], code_dirs=[repo])
    assert "#svc name=aws-ses" not in body
    triage = body.split("NEEDS-TRIAGE", 1)[1]
    assert "#svc name=truststore.amazonaws category=?" in triage
    assert "#svc name=gmail.googleapis category=?" in triage


def test_scan_failure_is_fail_closed_nothing_written(tmp_path, monkeypatch):
    """rg missing/timeout/exit-2 must RAISE, and main() must exit 1 without touching the output —
    a silently empty scan would drop every code host and hand registry_sync a mass delete."""
    monkeypatch.setattr(
        ge.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("rg"))
    )
    with pytest.raises(ge.CodeScanError):
        ge.scan_code_hosts([tmp_path])

    class _CP:
        returncode = 2
        stdout = ""
        stderr = "rg: error"

    monkeypatch.setattr(ge.subprocess, "run", lambda *a, **k: _CP())
    with pytest.raises(ge.CodeScanError):
        ge.scan_code_hosts([tmp_path])
    out = tmp_path / "all-envs.env"
    out.write_text("# previous\n", encoding="utf-8")
    monkeypatch.setattr(ge, "OUTPUT", out)
    monkeypatch.setattr(ge, "project_env_files", lambda: [tmp_path / "p" / ".env"])
    monkeypatch.setattr(ge, "project_dirs", lambda: [tmp_path])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    assert ge.main() == 1
    assert out.read_text(encoding="utf-8") == "# previous\n"


def test_classify_bound_walks_the_queue_from_a_cursor_under_churn():
    """The window resumes AFTER the last processed name and wraps. Property under churn
    (providers leave and arrive between runs): until the walk wraps, no provider is picked
    twice, and every provider present at the start that never left is picked before ANY
    repeat — i.e. one lap covers the queue, however N moves (review S3/O6, tightened G15)."""
    provs = {f"p{i:02d}": {} for i in range(23)}
    start_set = set(provs)
    seen: list[str] = []
    cursor = None
    left: set[str] = set()
    for run in range(4):
        kept, deferred, cursor = cs.bound_flagged(provs, 10, after=cursor)
        assert len(kept) == 10 and deferred == len(provs) - 10
        seen += list(kept)
        for gone in list(kept)[:2]:  # churn: two classified leave, one new arrives
            provs.pop(gone)
            left.add(gone)
        provs[f"q{run}"] = {}
    first_repeat = next((i for i, n in enumerate(seen) if n in seen[:i]), len(seen))
    assert first_repeat >= 20, (
        f"a provider repeated before the walk wrapped: {seen[: first_repeat + 1]}"
    )
    survivors = start_set - left
    assert survivors <= set(seen[:first_repeat]), (
        "a start-set survivor was not reached within one lap"
    )
    assert cs.bound_flagged(provs, 0) == (provs, 0, None)


def test_classify_error_budget_tombstones_after_three_consecutive_errors():
    counts, exhausted = cs.apply_error_budget({"a", "b"}, ["a", "b", "c"], {"a": 2, "c": 1})
    assert counts == {"a": 3, "b": 1} and exhausted == {"a"}  # c ran clean → reset


def test_unit_prompt_branches_for_code_only_providers():
    p = cs.unit_prompt(
        "posthog", {"names": ["CODE_HOST_URL"], "urls": ["https://us.i.posthog.com"]}
    )
    assert "call sites" in p and "Env vars" not in p
    q = cs.unit_prompt("foo", {"names": ["FOO_API_KEY"], "urls": []})
    assert "Env vars: FOO_API_KEY" in q


def test_catalog_index_drops_ambiguous_labels_and_keeps_exact_hosts():
    """backrest's url is a github.com repo link: `api.github.com` must credit `github`, never the
    first entry in JSON order; a label owned by one vendor still attributes by domain."""
    catalog = {
        "backrest": {"url": "https://github.com/garethgeorge/backrest", "match": ["BACKREST"]},
        "github": {"url": "https://github.com", "match": ["GITHUB"]},
        "resend": {"url": "https://resend.com", "match": ["RESEND"]},
    }
    idx = ge.catalog_url_index(catalog)
    assert (
        "*.github.com" not in idx and "github.com" not in idx and idx["*.resend.com"] == "resend"
    )  # wildcards carry the TLD (C5)
    matchers = [("BACKREST", "backrest"), ("GITHUB", "github"), ("RESEND", "resend")]
    assert ge.provider_for_host("api.github.com", catalog, idx, matchers) == "github"
    assert ge.provider_for_host("api.resend.com", catalog, idx, matchers) == "resend"


def test_platform_service_already_in_catalog_leaves_triage():
    """A classified/tombstoned platform service (`gmail.googleapis`) keeps its catalog entry —
    otherwise it is re-billed on every lap forever (review O1)."""
    catalog = {"gmail.googleapis": {"category": "email", "url": "?", "match": ["GMAIL.GOOGLEAPIS"]}}
    assert ge.provider_for_host("gmail.googleapis.com", catalog, {}, []) == "gmail.googleapis"
    assert ge.provider_for_host("people.googleapis.com", catalog, {}, []) is None


def test_scan_partial_error_keeps_matches_and_names_the_path(tmp_path, monkeypatch):
    """rg exit 2 WITH matches (one unreadable dir) = partial scan: matches kept, rg's own error
    text surfaced; exit 2 WITHOUT matches = failure carrying that text (review O3)."""
    monkeypatch.setattr(ge, "OPT", tmp_path)
    repo = tmp_path / "app"
    (repo / ".git").mkdir(parents=True)

    class _CP:
        returncode = 2
        stdout = "app/x.py:https://api.posthog.com/i\n"
        stderr = "rg: app/locked: Permission denied (os error 13)"

    monkeypatch.setattr(ge.subprocess, "run", lambda *a, **k: _CP())
    hosts = ge.scan_code_hosts([repo])
    assert set(hosts) == {"api.posthog.com"}
    assert hosts["api.posthog.com"]["projects"] == {"app"}  # relative `<repo>/…` paths (F1)

    class _Empty(_CP):
        stdout = ""

    monkeypatch.setattr(ge.subprocess, "run", lambda *a, **k: _Empty())
    with pytest.raises(ge.CodeScanError, match="Permission denied"):
        ge.scan_code_hosts([repo])


def test_output_file_is_0600_from_creation(tmp_path, monkeypatch):
    """The secrets file is created with mode 0600 (never write-then-chmod, review O13)."""
    out = tmp_path / "all-envs.env"
    monkeypatch.setattr(ge, "OUTPUT", out)
    monkeypatch.setattr(
        ge,
        "project_env_files",
        lambda: _envs(tmp_path, {"p": "RESEND_API_KEY=re_abcdefghijklmnopqrstuvwxyz123456\n"}),
    )
    monkeypatch.setattr(ge, "project_dirs", lambda: [])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    modes: list[int] = []
    real_open = os.open

    def spy(path, flags, mode=0o777, *a, **k):
        if ".tmp" in str(
            path
        ):  # only OUR file (per-process name, AW1) — the spy is process-wide (Z11)
            modes.append(mode)
        return real_open(path, flags, mode, *a, **k)

    monkeypatch.setattr(ge.os, "open", spy)
    assert ge.main() == 0
    assert modes == [0o600], modes
    assert oct(out.stat().st_mode & 0o777) == "0o600"


@needs_rg
def test_env_derived_unknown_gains_the_code_host_url(tmp_path, monkeypatch):
    """POSTHOG_KEY (flagged `?`) + a posthog call site share one bucket: the #svc header must
    carry the concrete host, not `url=?` (review S4)."""
    monkeypatch.setattr(ge, "OPT", tmp_path)
    monkeypatch.setattr(ge, "load_catalog", lambda: ({}, []))
    files = _envs(tmp_path, {"web": "POSTHOG_KEY=phc_abcdefghijklmnopqrstuvwxyz0123456789\n"})
    repo = _repo(tmp_path, "web2", {"a.py": 'u = "https://us.i.posthog.com/i/v0/e"\n'})
    body, _ = ge.consolidate(files, code_dirs=[repo])
    assert '#svc name=posthog category=? cost=? capability="?" url=https://us.i.posthog.com' in body


@needs_rg
def test_jest_dirs_and_dockerfiles(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "OPT", tmp_path)
    repo = _repo(
        tmp_path,
        "app",
        {
            "Dockerfile": "RUN curl -fsSL https://api.vendor-x.com/install.sh | sh\n",
            "__tests__/helpers.ts": 'const u = "https://graph.microsoft.com/v1.0"\n',
            "src/build/x.py": 'u = "https://api.axiom.co/v1"\n',
            "build/out.js": 'const u = "https://api.should-be-excluded.com"\n',
            "cache/c.py": 'u = "https://api.also-excluded.com"\n',
        },
    )
    hosts = ge.scan_code_hosts([repo])
    # root build/ + cache/ excluded, src/build kept (rg anchors `/` to the cwd — measured)
    assert set(hosts) == {"api.vendor-x.com", "api.axiom.co"}
    assert hosts["api.axiom.co"]["projects"] == {"app"}


def test_classify_skips_when_another_run_holds_the_lock(tmp_path, monkeypatch):
    """A manual run racing the daily one must not process the same slice (review pass 2)."""
    import fcntl

    monkeypatch.setattr(cs, "STATE_DIR", tmp_path)
    monkeypatch.setattr(cs, "ALL_ENVS", tmp_path / "all-envs.env")
    (tmp_path / "all-envs.env").write_text(
        '# ═ NEEDS-TRIAGE ═\n#svc name=foo category=? cost=? capability="?" url=? status=? used_by=-\nFOO_API_KEY=x\n',
        encoding="utf-8",
    )
    with open(tmp_path / "classify.lock", "w", encoding="utf-8") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(
            cs,
            "fanout",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("dispatched despite the lock")),
        )
        monkeypatch.setattr(sys, "argv", ["classify_services.py"])
        assert cs.main() == 0


def test_host_re_skips_userinfo():
    """`https://allowed.com@evil.com` names evil.com — userinfo is never the host (G2)."""
    assert ge.HOST_RE.search("x https://allowed.com@evil.com/p").group(1) == "evil.com"
    assert ge.HOST_RE.search("https://user:pw@api.vendor.com/v1").group(1) == "api.vendor.com"
    assert ge.HOST_RE.search("https://api.vendor.com:8443/v1").group(1) == "api.vendor.com"


def test_internal_config_name_beats_a_catalog_match_prefix(tmp_path, monkeypatch):
    """ALLOWED_ORIGINS is internal config even when a tombstone `allowed` carries match ALLOWED (G1b)."""
    monkeypatch.setattr(
        ge,
        "load_catalog",
        lambda: (
            {
                "allowed": {
                    "category": "unidentified",
                    "cost": "?",
                    "capability": "?",
                    "url": "?",
                    "status": "unidentified",
                    "match": ["ALLOWED"],
                }
            },
            [("ALLOWED", "allowed")],
        ),
    )
    body, stats = ge.consolidate(_envs(tmp_path, {"api": "ALLOWED_ORIGINS=*\nallowed_origins=*\n"}))
    internal = body.split("internal-config", 1)[1]
    assert "#svc name=allowed" not in body
    assert "ALLOWED_ORIGINS=*" in internal and "allowed_origins=*" in internal  # lowercase too (H3)
    # an INTERNAL_SUBSTR name (…_TIMEOUT) under a vendor prefix is config, never a credential (H3)
    monkeypatch.setattr(
        ge,
        "load_catalog",
        lambda: (
            {
                "anthropic": {
                    "category": "ai-llm",
                    "cost": "paid",
                    "capability": "llm",
                    "url": "https://www.anthropic.com",
                    "status": "active",
                    "match": ["ANTHROPIC"],
                }
            },
            [("ANTHROPIC", "anthropic")],
        ),
    )
    (tmp_path / "b").mkdir()
    body, _ = ge.consolidate(_envs(tmp_path / "b", {"svc": "ANTHROPIC_READ_TIMEOUT=30\n"}))
    assert "#svc name=anthropic" not in body
    assert "ANTHROPIC_READ_TIMEOUT=30" in body.split("internal-config", 1)[1]
    # … but a vendor-prefixed SECRET that carries a config token stays the vendor's (the mirror)
    monkeypatch.setattr(
        ge,
        "load_catalog",
        lambda: (
            {
                "supabase": {
                    "category": "data",
                    "cost": "freemium",
                    "capability": "db",
                    "url": "https://supabase.com",
                    "status": "retiring",
                    "match": ["SUPABASE"],
                }
            },
            [("SUPABASE", "supabase")],
        ),
    )
    (tmp_path / "c").mkdir()
    body, _ = ge.consolidate(
        _envs(
            tmp_path / "c",
            {
                "svc": "SUPABASE_DB_PASSWORD=JIbqttnjVAj45oK5abcdef\nSUPABASE_DB_URL=postgresql://postgres:JIbqttnjVAj45oK5@db.x.supabase.co:5432/postgres\n"
            },
        )
    )
    svc_block = body.split("#svc name=supabase", 1)[1].split("# ═", 1)[0]
    assert "SUPABASE_DB_PASSWORD=" in svc_block and "SUPABASE_DB_URL=" in svc_block


def test_code_only_entries_carry_no_match_prefix():
    assert cs.code_only_provider({"names": ["CODE_HOST_URL"], "urls": ["https://x.io"]})
    assert not cs.code_only_provider({"names": ["CODE_HOST_URL", "X_API_KEY"], "urls": []})
    assert cs.tombstone_entry("allowed", code_only=True)["match"] == []
    assert cs.tombstone_entry("foo")["match"] == ["FOO"]


def test_error_budget_forgets_providers_that_left_the_queue():
    counts, exhausted = cs.apply_error_budget(set(), ["b"], {"a": 2, "b": 1}, flagged={"b"})
    assert counts == {} and exhausted == set()  # a left the queue → its count is gone; b ran clean


def test_state_reads_are_typed(tmp_path):
    f = tmp_path / "cursor.json"
    f.write_text('"apple"', encoding="utf-8")  # a bare string where a dict is expected
    assert cs._read_json(f, {}) == {}
    f.write_text("[1, 2]", encoding="utf-8")
    assert cs._read_json(f, {}) == {}
    f.write_text('{"after": "x"}', encoding="utf-8")
    assert cs._read_json(f, {}) == {"after": "x"}


def test_leftover_tmp_from_a_crashed_run_is_recreated_0600(tmp_path, monkeypatch):
    out = tmp_path / "all-envs.env"
    leftover = tmp_path / "all-envs.env.tmp"
    leftover.write_text("stale", encoding="utf-8")
    leftover.chmod(0o644)
    import os
    import time

    os.utime(
        leftover, (time.time() - 7200, time.time() - 7200)
    )  # a crashed run's leftover is HOURS old (BB7)
    monkeypatch.setattr(ge, "OUTPUT", out)
    monkeypatch.setattr(
        ge,
        "project_env_files",
        lambda: _envs(tmp_path, {"p": "RESEND_API_KEY=re_abcdefghijklmnopqrstuvwxyz123456\n"}),
    )
    monkeypatch.setattr(ge, "project_dirs", lambda: [])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    assert ge.main() == 0
    assert oct(out.stat().st_mode & 0o777) == "0o600" and not leftover.exists()


@needs_rg
def test_env_derived_unknown_adopts_the_catalogued_vendor_its_host_names(tmp_path, monkeypatch):
    """RESEND_TOKEN misses the catalog `match`, but the repo calls api.resend.com: the bucket
    adopts the catalog meta and leaves NEEDS-TRIAGE instead of being re-billed (G8)."""
    monkeypatch.setattr(ge, "OPT", tmp_path)
    monkeypatch.setattr(
        ge,
        "load_catalog",
        lambda: (
            {
                "resend": {
                    "category": "email",
                    "cost": "freemium",
                    "capability": "email",
                    "url": "https://resend.com",
                    "status": "active",
                    "match": ["RESEND_API"],
                }
            },
            [("RESEND_API", "resend")],
        ),
    )
    files = _envs(tmp_path, {"web": "RESEND_TOKEN=re_abcdefghijklmnopqrstuvwxyz123456\n"})
    repo = _repo(tmp_path, "web2", {"m.py": 'u = "https://api.resend.com/emails"\n'})
    body, _ = ge.consolidate(files, code_dirs=[repo])
    assert "#svc name=resend category=email" in body and "NEEDS-TRIAGE" not in body


def _classify_env(tmp_path, monkeypatch, envs_text: str, argv: list[str], results):
    cat = tmp_path / "catalog.json"
    cat.write_text("{}", encoding="utf-8")
    envs = tmp_path / "all-envs.env"
    envs.write_text(envs_text, encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    for name, val in (
        ("CATALOG_PATH", cat),
        ("ALL_ENVS", envs),
        ("STATE_DIR", state),
        ("CURSOR_PATH", state / "c.json"),
        ("ERRORS_PATH", state / "e.json"),
        ("LAST_RUN_PATH", state / "l.json"),
    ):
        monkeypatch.setattr(cs, name, val)

    def fake_fanout(*a, **k):
        units = k["units"]
        assert len(results) >= len(units), "fixture: one result per dispatched unit"
        return [results[i] for i in range(len(units))], ""  # by POSITION — never broadcast [0]

    monkeypatch.setattr(cs, "fanout", fake_fanout)
    monkeypatch.setattr(cs, "set_quality", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["classify_services.py", *argv])
    return cat, state


class _Res:
    def __init__(self, text, error=None):
        self.agent_id, self.model, self.error, self.text = "a", "m", error, text


def test_identified_code_only_providers_get_no_match_prefix(tmp_path, monkeypatch):
    """The IDENTIFIED path (not only the tombstone path) writes `match: []` for a code-only
    provider — nine such entries were minted with prefixes before the guard (H2/H10)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=algolia category=? cost=? capability="?" url=https://www.algolia.com status=? used_by=web\n'
        "CODE_HOST_URL=https://www.algolia.com   # used by: web\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "algolia",
                    "category": "search",
                    "cost": "freemium",
                    "capability": "search",
                    "url": "https://www.algolia.com",
                    "status": "active",
                }
            )
        ),
        _Res(
            json.dumps(
                {
                    "name": "foo",
                    "category": "search",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://foo.io",
                    "status": "active",
                }
            )
        ),
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert out["algolia"]["match"] == [] and out["foo"]["match"] == ["FOO"]


def test_only_run_never_moves_the_shared_cursor(tmp_path, monkeypatch):
    """`--only …` is the hand-picked escape hatch: it must not overwrite the daily cursor (H15)."""
    text = "# ═ NEEDS-TRIAGE ═\n" + "".join(
        f'#svc name=p{i:02d} category=? cost=? capability="?" url=? status=? used_by=-\nP{i:02d}_API_KEY=x\n'
        for i in range(12)
    )
    cat, state = _classify_env(
        tmp_path,
        monkeypatch,
        text,
        ["--apply", "--only", ",".join(f"p{i:02d}" for i in range(11))],
        [_Res("not json") for _ in range(11)],
    )
    (state / "c.json").write_text('{"after": "zzz"}', encoding="utf-8")
    assert cs.main() == 0
    assert json.loads((state / "c.json").read_text(encoding="utf-8")) == {"after": "zzz"}


def test_daily_slice_keeps_the_error_budget_of_deferred_providers(tmp_path, monkeypatch):
    """A daily lap classifies 10 of 15: the counts of the five DEFERRED providers must survive
    (`all_flagged` is the whole queue, not the slice — Z2, made discriminating in AC2), and a
    `--only` run records no budget at all (AC10)."""
    text = "# ═ NEEDS-TRIAGE ═\n" + "".join(
        f'#svc name=p{i:02d} category=? cost=? capability="?" url=? status=? used_by=-\nP{i:02d}_API_KEY=x\n'
        for i in range(15)
    )
    cat, state = _classify_env(
        tmp_path, monkeypatch, text, ["--apply"], [_Res("not json") for _ in range(10)]
    )
    (state / "e.json").write_text(json.dumps({"p12": 2, "p13": 2}), encoding="utf-8")
    assert cs.main() == 0
    counts = json.loads((state / "e.json").read_text(encoding="utf-8"))
    assert counts["p12"] == 2 and counts["p13"] == 2  # deferred this lap → untouched
    # --only: neither budget nor cursor, own last-run file
    (state / "e.json").write_text(json.dumps({"p00": 2, "p01": 2}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["classify_services.py", "--apply", "--only", "p04"])
    monkeypatch.setattr(cs, "fanout", lambda *a, **k: ([_Res("not json") for _ in k["units"]], ""))
    assert cs.main() == 0
    assert json.loads((state / "e.json").read_text(encoding="utf-8")) == {"p00": 2, "p01": 2}
    assert (
        state / "classify_last_only.json"
    ).exists()  # the daily lap wrote l.json earlier; --only writes its own


def test_a_catalog_entry_left_at_question_mark_is_restubbed(tmp_path, monkeypatch):
    """A catalog entry whose category is `?` sits in NEEDS-TRIAGE forever and was skipped by the
    tombstone loop → re-billed every lap (pass 5, Z10)."""
    text = '# ═ NEEDS-TRIAGE ═\n#svc name=zzz category=? cost=? capability="?" url=? status=? used_by=-\nZZZ_API_KEY=x\n'
    cat, _ = _classify_env(
        tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], [_Res("not json")]
    )
    cat.write_text(json.dumps({"zzz": {"category": "?", "match": ["ZZZ"]}}), encoding="utf-8")
    assert cs.main() == 0
    assert json.loads(cat.read_text(encoding="utf-8"))["zzz"]["category"] == "unidentified"


def test_only_list_is_never_capped(tmp_path, monkeypatch, capsys):
    """`--only` names 15 providers: all 15 are dispatched (an operator-typed list is already
    bounded) and the shared cursor stays put (AB1); a name that is not flagged is reported with
    the queue's denominator, never silently dropped (AF12)."""
    text = "# ═ NEEDS-TRIAGE ═\n" + "".join(
        f'#svc name=p{i:02d} category=? cost=? capability="?" url=? status=? used_by=-\nP{i:02d}_API_KEY=x\n'
        for i in range(15)
    )
    seen: list[int] = []

    def fake_fanout(*a, **k):
        seen.append(len(k["units"]))
        return [_Res("not json") for _ in k["units"]], ""

    cat, state = _classify_env(
        tmp_path,
        monkeypatch,
        text,
        ["--apply", "--only", ",".join(f"p{i:02d}" for i in range(15)) + ",nope"],
        [],
    )
    monkeypatch.setattr(cs, "fanout", fake_fanout)
    assert cs.main() == 0
    assert seen == [15] and not (state / "c.json").exists()
    assert "--only: ['nope'] are not in NEEDS-TRIAGE (15 flagged)" in capsys.readouterr().err


def test_identified_platform_host_merges_into_the_existing_catalog_entry(tmp_path, monkeypatch):
    """`safebrowsing.googleapis` identified as `google-safe-browsing` (already catalogued) becomes
    a `hosts` entry of that vendor, not a duplicate key re-billed every lap (AB3)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=safebrowsing.googleapis category=? cost=? capability="?" url=https://safebrowsing.googleapis.com status=? used_by=site-provisioner\n'
        "CODE_HOST_URL=https://safebrowsing.googleapis.com   # used by: site-provisioner\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "google-safe-browsing",
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://developers.google.com/safe-browsing",
                    "status": "active",
                }
            )
        )
    ]
    # the DAILY argv: with --tombstone-unresolved a merged host must not ALSO be stubbed (AF2)
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], res)
    cat.write_text(
        json.dumps(
            {
                "google-safe-browsing": {
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://developers.google.com/safe-browsing",
                    "status": "active",
                    "match": ["GOOGLE_SAFE_BROWSING"],
                }
            }
        ),
        encoding="utf-8",
    )
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert "safebrowsing.googleapis" not in out
    assert out["google-safe-browsing"]["hosts"] == ["safebrowsing.googleapis.com"]
    # and the scan now attributes that host to the entry, so it leaves triage
    idx = ge.catalog_url_index(out)
    assert (
        ge.provider_for_host(
            "safebrowsing.googleapis.com",
            out,
            idx,
            [("GOOGLE_SAFE_BROWSING", "google-safe-browsing")],
        )
        == "google-safe-browsing"
    )


def test_numbered_keys_belong_to_one_provider():
    """GROQ_API_KEY_2 is groq's second key, not a vendor of its own (AC1)."""
    assert ge.derive_provider("GROQ_API_KEY_2") == "groq" == ge.derive_provider("GROQ_API_KEY")
    assert ge.derive_provider("MISTRAL_API_KEYS") == "mistral"


def test_explicit_internal_prefix_wins_even_for_a_secret_shaped_value(tmp_path, monkeypatch):
    """`M365_CERT_THUMBPRINT` (INTERNAL_PREFIX `M365_CERT`, a 40-hex PUBLIC fingerprint) stays
    internal; the value tiebreak applies only to generic substr tokens (AC7)."""
    monkeypatch.setattr(
        ge,
        "load_catalog",
        lambda: (
            {
                "microsoft-365": {
                    "category": "infra",
                    "cost": "paid",
                    "capability": "m365",
                    "url": "https://learn.microsoft.com/graph",
                    "status": "active",
                    "match": ["M365"],
                }
            },
            [("M365", "microsoft-365")],
        ),
    )
    body, _ = ge.consolidate(
        _envs(tmp_path, {"svc": "M365_CERT_THUMBPRINT=AB12CD34EF56AB12CD34EF56AB12CD34EF56AB12\n"})
    )
    assert "M365_CERT_THUMBPRINT=" in body.split("internal-config", 1)[1]


def test_cursor_is_persisted_before_the_paid_dispatch(tmp_path, monkeypatch):
    """A `timeout` kill mid-dispatch must not re-bill the same slice tomorrow (AC5)."""
    text = "# ═ NEEDS-TRIAGE ═\n" + "".join(
        f'#svc name=p{i:02d} category=? cost=? capability="?" url=? status=? used_by=-\nP{i:02d}_API_KEY=x\n'
        for i in range(12)
    )
    cat, state = _classify_env(tmp_path, monkeypatch, text, ["--apply"], [])
    monkeypatch.setattr(cs, "fanout", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        cs.main()
    assert json.loads((state / "c.json").read_text(encoding="utf-8")) == {"after": "p09"}


def test_restub_keeps_a_curated_match_list(tmp_path, monkeypatch):
    text = '# ═ NEEDS-TRIAGE ═\n#svc name=zzz category=? cost=? capability="?" url=? status=? used_by=-\nZZZ_API_KEY=x\n'
    cat, _ = _classify_env(
        tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], [_Res("not json")]
    )
    cat.write_text(
        json.dumps({"zzz": {"category": "?", "match": ["ZZZ", "ZZZ_LEGACY"]}}), encoding="utf-8"
    )
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))["zzz"]
    assert out["category"] == "unidentified" and out["match"] == ["ZZZ", "ZZZ_LEGACY"]


def test_identified_env_keyed_provider_joins_the_existing_vendors_match_list(tmp_path, monkeypatch):
    """`OPENAI2_API_KEY` (flagged `openai2`) identified as `openai` (catalogued) lends its prefix to
    openai's `match` list instead of minting a second vendor (AD2)."""
    text = '# ═ NEEDS-TRIAGE ═\n#svc name=openai2 category=? cost=? capability="?" url=? status=? used_by=web\nOPENAI2_API_KEY=x\n'
    res = [
        _Res(
            json.dumps(
                {
                    "name": "openai",
                    "category": "ai-llm",
                    "cost": "paid",
                    "capability": "llm",
                    "url": "https://openai.com",
                    "status": "active",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    cat.write_text(
        json.dumps(
            {
                "openai": {
                    "category": "ai-llm",
                    "cost": "paid",
                    "capability": "llm",
                    "url": "https://openai.com",
                    "status": "active",
                    "match": ["OPENAI"],
                }
            }
        ),
        encoding="utf-8",
    )
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert (
        "openai2" not in out
        and out["openai"]["match"] == ["OPENAI"]
        and out["openai"]["merged_match"] == ["OPENAI2"]
    )
    # and the scan MATCHES on the merged prefix — the whole point of the merge (AD2/BH1)
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    _, matchers = ge.load_catalog()
    assert ge.match_provider("OPENAI2_API_KEY", matchers) == "openai"


def test_only_run_with_a_transport_error_records_and_tombstones_nothing(tmp_path, monkeypatch):
    """`--only p04` whose unit transport-errors: no budget row for p04, no tombstone even after
    three such runs — a hand-picked run is not a lap (AC10, made discriminating in AF5)."""
    text = "# ═ NEEDS-TRIAGE ═\n" + "".join(
        f'#svc name=p{i:02d} category=? cost=? capability="?" url=? status=? used_by=-\nP{i:02d}_API_KEY=x\n'
        for i in range(5)
    )
    cat, state = _classify_env(
        tmp_path,
        monkeypatch,
        text,
        ["--apply", "--tombstone-unresolved", "--only", "p04"],
        [_Res("", error="timeout")],
    )
    (state / "e.json").write_text(json.dumps({"p04": 2}), encoding="utf-8")
    for _ in range(3):
        assert cs.main() == 0
    assert json.loads((state / "e.json").read_text(encoding="utf-8")) == {"p04": 2}
    assert "p04" not in json.loads(cat.read_text(encoding="utf-8"))


def test_dry_run_moves_no_cursor(tmp_path, monkeypatch):
    """The documented dry run prints proposals and writes NOTHING — including the cursor (AF3)."""
    text = "# ═ NEEDS-TRIAGE ═\n" + "".join(
        f'#svc name=p{i:02d} category=? cost=? capability="?" url=? status=? used_by=-\nP{i:02d}_API_KEY=x\n'
        for i in range(12)
    )
    cat, state = _classify_env(
        tmp_path, monkeypatch, text, [], [_Res("not json") for _ in range(10)]
    )
    assert cs.main() == 0
    assert not (state / "c.json").exists() and json.loads(cat.read_text(encoding="utf-8")) == {}


def test_identified_curated_entry_keeps_its_match_and_hosts(tmp_path, monkeypatch):
    text = '# ═ NEEDS-TRIAGE ═\n#svc name=zzz category=? cost=? capability="?" url=? status=? used_by=-\nZZZ_API_KEY=x\n'
    res = [
        _Res(
            json.dumps(
                {
                    "name": "zzz",
                    "category": "search",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://zzz.io",
                    "status": "active",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    cat.write_text(
        json.dumps(
            {"zzz": {"category": "?", "match": ["ZZZ", "ZZZ_LEGACY"], "hosts": ["api.zzz.io"]}}
        ),
        encoding="utf-8",
    )
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))["zzz"]
    assert (
        out["category"] == "search"
        and out["match"] == ["ZZZ", "ZZZ_LEGACY"]
        and out["hosts"] == ["api.zzz.io"]
    )


def test_generic_internal_prefix_never_hides_a_credential_shaped_secret(tmp_path, monkeypatch):
    """`PROXY_API_KEY=<secret>` under the generic INTERNAL_PREFIX `PROXY_` stays the catalogued
    vendor's (AF9); `M365_CERT_KEY_FILE=/opt/…/cert.pem` under the explicit prefix `M365_CERT`
    stays internal — the name says KEY but the value is a path, and the test is two-factor (AJ1)."""
    assert "PROXY_" in ge.INTERNAL_PREFIX and "M365_CERT" in ge.INTERNAL_PREFIX
    monkeypatch.setattr(
        ge,
        "load_catalog",
        lambda: (
            {
                "proxyvendor": {
                    "category": "proxies",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://proxyvendor.io",
                    "status": "active",
                    "match": ["PROXY"],
                },
                "microsoft-365": {
                    "category": "infra",
                    "cost": "paid",
                    "capability": "m365",
                    "url": "https://learn.microsoft.com/graph",
                    "status": "active",
                    "match": ["M365"],
                },
            },
            [("PROXY", "proxyvendor"), ("M365", "microsoft-365")],
        ),
    )
    body, _ = ge.consolidate(
        _envs(
            tmp_path,
            {
                "svc": "PROXY_API_KEY=pk_abcdefghijklmnopqrstuvwxyz0123456789\n"
                "M365_CERT_KEY_FILE=/opt/fabrik/certs/m365-cert-2026.pem\n"
            },
        )
    )
    assert (
        "#svc name=proxyvendor" in body
        and "PROXY_API_KEY=" in body.split("#svc name=proxyvendor", 1)[1].split("# ═", 1)[0]
    )
    assert "#svc name=microsoft-365" not in body
    assert "M365_CERT_KEY_FILE=" in body.split("internal-config", 1)[1]


def test_a_hand_edited_scalar_hosts_entry_is_tolerated_on_both_paths(tmp_path, monkeypatch):
    """`"hosts": "api.v.io"` (a scalar, not a list) must index as ONE host — never as one-char
    keys — and the classify merge must append to it, not crash on `str.append` (AF14)."""
    idx = ge.catalog_url_index({"v": {"url": "https://v.io", "hosts": "api.v.io"}})
    assert idx["api.v.io"] == "v" and not [k for k in idx if len(k) == 1]
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=safebrowsing.googleapis category=? cost=? capability="?" url=https://safebrowsing.googleapis.com status=? used_by=site-provisioner\n'
        "CODE_HOST_URL=https://safebrowsing.googleapis.com   # used by: site-provisioner\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "google-safe-browsing",
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://developers.google.com/safe-browsing",
                    "status": "active",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], res)
    cat.write_text(
        json.dumps(
            {
                "google-safe-browsing": {
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://developers.google.com/safe-browsing",
                    "status": "active",
                    "match": ["GOOGLE_SAFE_BROWSING"],
                    "hosts": "old.googleapis.com",
                }
            }
        ),
        encoding="utf-8",
    )
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert out["google-safe-browsing"]["hosts"] == [
        "old.googleapis.com",
        "safebrowsing.googleapis.com",
    ]


def test_path_rule_rejects_paths_but_not_a_slash_bearing_base64_secret():
    """A file path is never credential-grade; a base64 secret that happens to start with `/` and
    carry another `/` (no `+`/`=`) still is — its first segment is mixed-case (AL1)."""
    for path in ("/opt/fabrik/certs/m365-cert-2026.pem", "~/.ssh/id_ed25519", "./data/keys/x.json"):
        assert not ge.credential_grade(path), path
    assert ge.credential_grade("/aB3dEf9GhIjK/LmN0pQrStUvWxYz1234567")
    assert ge.credential_grade(
        "/zq8/XyWvUtSrQpOnMlKjIhGfEdCbA9876543"
    )  # one lowercase segment is not a path
    assert not ge.credential_grade("/a/b")  # too short to be a credential anyway
    assert ge.credential_grade(
        "/xk9m2p7q4z8w1n5aa"
    )  # ONE segment is not a path — the rule is ≥2 (AO1)


def test_a_model_authored_url_must_be_http_or_https(tmp_path, monkeypatch):
    """`javascript:…` (or any non-http scheme) from the pool model never reaches the catalog, the
    registry or the dashboard page — it is written as `?` (AM4)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "foo",
                    "category": "search",
                    "cost": 'x"><svg/onload=alert(1)>',
                    "capability": "x",
                    "url": "javascript:alert(1)",
                    "status": "active (beta)",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))["foo"]
    assert out["url"] == "?"
    # the enum fields are model-authored too: an out-of-enum cost/status/category is `?` /
    # `active`, never an attribute-breaking string for the dashboard's class token (AP1)
    assert (
        out["cost"] == "?" and out["status"] == "?" and out["category"] == "search"
    )  # BB4: unknown, not active


def test_svc_line_never_emits_a_token_the_consumer_cannot_parse():
    """`cost="free tier"`, a newline in `capability`: the #svc line stays one `\\S+`-token line that
    registry_sync.SVC_RE reads — an unreadable line now fails the sync closed (AP2)."""
    line = ge.svc_line(
        "acme",
        {
            "category": "ai llm",
            "cost": "free tier",
            "capability": "l1\nl2",
            "url": "https://x.test /docs",
            "status": "active (beta)",
        },
        {"p"},
    )
    assert "\n" not in line and rs.SVC_RE.match(line), line
    m = rs.SVC_RE.match(line).groupdict()
    assert m["cost"] == "free_tier" and m["category"] == "ai_llm" and m["used_by"] == "p"
    # the two fields _svc_token did not cover: the provider NAME (a bad one would fail the sync
    # closed every day, AS3) and each used_by member (a bad one silently mis-attributed, AS4)
    line = ge.svc_line("pro v", {"category": "search"}, {"pro j", "b"})
    m = rs.SVC_RE.match(line).groupdict()
    assert m["name"] == "pro_v" and m["used_by"] == "b,pro_j"


def test_a_model_answer_the_enum_flattens_is_not_identified(tmp_path, monkeypatch):
    """`AI-LLM` / `Freemium` are the enum values (normalised); `ai llm` is not, and a provider the
    enum flattens to `?` must NOT count as identified — it would stay in NEEDS-TRIAGE and be
    re-billed every day (the C2 loop, re-opened by the enum guard — AS1): on the daily argv it is
    tombstoned instead."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
        '#svc name=bar category=? cost=? capability="?" url=? status=? used_by=web\n'
        "BAR_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "foo",
                    "category": "AI-LLM",
                    "cost": "Freemium ",
                    "capability": "x",
                    "url": "https://foo.test",
                    "status": "Active",
                }
            )
        ),
        _Res(
            json.dumps(
                {
                    "name": "bar",
                    "category": "ai llm",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://bar.test",
                    "status": "active",
                }
            )
        ),
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], res)
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert (
        out["foo"]["category"] == "ai-llm"
        and out["foo"]["cost"] == "freemium"
        and out["foo"]["status"] == "active"
    )
    assert out["bar"]["category"] not in ("?", "ai llm"), out[
        "bar"
    ]  # tombstoned, so it leaves triage


def test_an_enum_rejected_answer_never_merges_reports_or_scores_as_identified(
    tmp_path, monkeypatch
):
    """A model answer the enum rejects must not: merge into a CURATED entry via `name` (AU1),
    appear in classify_last.json / the alert as classified (AU2), or score 5 in the flywheel
    (AU5). It is tombstoned on the daily argv."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=gamma category=? cost=? capability="?" url=? status=? used_by=web\n'
        "GAMMA_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "openai",
                    "category": "totally-not-an-enum",
                    "cost": "???",
                    "capability": "x",
                    "url": "https://x.test",
                    "status": "nope",
                }
            )
        )
    ]
    cat, state = _classify_env(
        tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], res
    )
    cat.write_text(
        json.dumps(
            {
                "openai": {
                    "category": "ai-llm",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://openai.com",
                    "status": "active",
                    "match": ["OPENAI"],
                }
            }
        ),
        encoding="utf-8",
    )
    scores: list[int] = []
    monkeypatch.setattr(cs, "set_quality", lambda agent_id, score, **kw: scores.append(score))
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert out["openai"]["match"] == ["OPENAI"] and "merged_match" not in out["openai"], out[
        "openai"
    ]  # never merged (AU1)
    assert out["gamma"]["category"] == "unidentified"  # tombstoned, leaves triage
    last = json.loads((state / "l.json").read_text(encoding="utf-8"))
    assert last["identified"] == [] and last["tombstoned"] == ["gamma"], last  # AU2
    assert scores == [2], scores  # AU5


def test_metadata_keys_survive_classify_and_never_crash_it(tmp_path, monkeypatch):
    """`_README` (a string, not an entry) is kept aside and written back first; a model naming a
    string-valued key (`note`, AY8 — or `_readme`) cannot make classify call `.setdefault` on a string (AU9)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "note",
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://foo.test",
                    "status": "active",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    cat.write_text(
        json.dumps(
            {
                "_readme": "metadata text",
                "note": "a string under a non-underscore key (AY8)",
                "bar": {
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://bar.test",
                    "status": "active",
                    "match": ["BAR"],
                },
            }
        ),
        encoding="utf-8",
    )
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert (
        list(out)[0] == "_readme"
        and out["_readme"] == "metadata text"
        and out["foo"]["category"] == "search"
    )
    assert (
        out["note"] == "a string under a non-underscore key (AY8)"
    )  # kept as metadata, never a provider


def test_triage_starts_at_the_header_never_at_a_value(tmp_path):
    """A VALUE containing `NEEDS-TRIAGE` before the header must not open the triage block — a
    curated vendor would be dispatched to the paid pool and overwritten (AU11)."""
    f = tmp_path / "all-envs.env"
    f.write_text(
        "# ═ ai-llm ═\n"
        '#svc name=openai category=ai-llm cost=paid capability="x" url=https://openai.com status=active used_by=web\n'
        "OPENAI_NOTE=see NEEDS-TRIAGE below\n"
        '#svc name=anthropic category=ai-llm cost=paid capability="x" url=https://anthropic.com status=active used_by=web\n'
        "ANTHROPIC_API_KEY=x\n"
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n",
        encoding="utf-8",
    )
    assert list(cs.flagged_providers(f)) == ["foo"]


def test_underscore_prefixed_key_never_mints_an_invisible_provider():
    """`_MYVENDOR_API_KEY` → `myvendor`: a `_`-prefixed provider would be dropped by load_catalog
    (metadata convention) and re-billed forever once tombstoned (AU4)."""
    assert ge.derive_provider("_MYVENDOR_API_KEY") == "myvendor"
    assert (
        ge.derive_provider("__API_KEY") == "api_key"
    )  # the fallback must not restore the prefix (AY3)
    for k in ("_", "__", "___TOKEN", "__API_KEY"):
        assert ge.derive_provider(k) and not ge.derive_provider(k).startswith("_"), k


def test_catalog_keys_with_whitespace_fail_closed(tmp_path, monkeypatch):
    """A hand-edited key `pro v` would be emitted as `pro_v` and read back as a DIFFERENT provider
    (re-billed daily, upserted under a new name): load_catalog refuses it loudly (AU7)."""
    cat = tmp_path / "catalog.json"
    cat.write_text(
        json.dumps({"pro v": {"category": "search", "match": ["PRO"]}}), encoding="utf-8"
    )
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    with pytest.raises(ValueError, match="single tokens"):
        ge.load_catalog()
    # a non-dict value under a provider key is metadata, not a provider (AY8)
    cat.write_text(
        json.dumps({"note": "text", "ok": {"category": "search", "match": ["OK"]}}),
        encoding="utf-8",
    )
    catalog, matchers = ge.load_catalog()
    assert list(catalog) == ["ok"] and matchers == [("OK", "ok")]


def test_per_key_used_by_note_is_tokenised_like_the_svc_line(tmp_path, monkeypatch):
    """The per-key `used by:` note (registry_sync prefers it over the #svc used_by) carries the
    same tokens — a project dir with whitespace attributes identically on both paths (AU6)."""
    monkeypatch.setattr(ge, "load_catalog", lambda: ({}, []))
    body, _ = ge.consolidate(
        _envs(
            tmp_path,
            {"pro j": "FOO_API_KEY=abcdefghijklmnop\n", "a,b": "BAR_API_KEY=abcdefghijklmnop\n"},
        )
    )
    assert "used by: pro_j" in body and "used_by=pro_j" in body and "pro j" not in body
    assert "used by: a_b" in body and "a,b" not in body  # `,` is the consumer's delimiter (AY7)


def test_secret_file_tmp_never_outlives_a_failed_write(tmp_path, monkeypatch):
    """A failure between open and replace unlinks the 0600 tmp — the full credential set never
    sits beside the target after a crash (AU10)."""
    out = tmp_path / "all-envs.env"
    monkeypatch.setattr(ge.os, "replace", lambda a, b: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        ge.write_secret_file(out, "SECRET=1\n")
    assert not list(tmp_path.glob("all-envs.env.tmp*")) and not out.exists()


def test_secret_file_tmp_is_per_process_and_a_live_siblings_tmp_is_never_touched(tmp_path):
    """Two writers (a manual run racing the cron) must never share a tmp name — with one shared
    `.tmp` the second unlinked the first's in-progress file and the first's rename installed the
    second's PARTIAL file as the secrets file (AW1). A fresh sibling tmp survives; a stale one
    (a SIGKILLed run, > 1 h) is swept."""
    import os
    import time

    out = tmp_path / "all-envs.env"
    fresh = tmp_path / "all-envs.env.tmp.424242"
    fresh.write_text("partial", encoding="utf-8")
    stale = tmp_path / "all-envs.env.tmp.1"
    stale.write_text("old", encoding="utf-8")
    os.utime(stale, (time.time() - 7200, time.time() - 7200))
    assert (
        ge.sweep_stale_tmp(out) == 1
    )  # the crashed run's leftover is swept, the fresh sibling is not
    ge.write_secret_file(out, "SECRET=1\n")
    assert out.read_text(encoding="utf-8") == "SECRET=1\n"
    assert fresh.read_text(encoding="utf-8") == "partial"  # a live sibling's tmp is untouched
    assert not stale.exists()
    assert not (tmp_path / f"all-envs.env.tmp.{os.getpid()}").exists()  # ours was renamed away


def test_a_bad_catalog_key_is_a_one_line_exit_1_never_a_traceback(tmp_path, monkeypatch, capsys):
    """`load_catalog`'s ValueError (AU7) reaches the chain as the same shape as a scan failure:
    one line on stderr, exit 1, nothing written (AY4)."""
    cat = tmp_path / "catalog.json"
    cat.write_text(json.dumps({"pro v": {"category": "search"}}), encoding="utf-8")
    out = tmp_path / "all-envs.env"
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    monkeypatch.setattr(ge, "OUTPUT", out)
    monkeypatch.setattr(
        ge, "project_env_files", lambda: _envs(tmp_path, {"p": "X_API_KEY=abcdefghijklmnop\n"})
    )
    monkeypatch.setattr(ge, "project_dirs", lambda: [])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    assert ge.main() == 1
    assert "single tokens" in capsys.readouterr().err and not out.exists()


def test_stale_tmp_is_swept_on_a_no_change_day_and_a_sibling_race_is_not_a_traceback(
    tmp_path, monkeypatch
):
    """A SIGKILLed run's hour-old leftover is swept even when today's body is unchanged (BA2), and
    a sibling unlinking the same leftover between glob and stat is skipped, never raised (BA1)."""
    import os
    import time

    out = tmp_path / "all-envs.env"
    stale = tmp_path / "all-envs.env.tmp.1"
    stale.write_text("old", encoding="utf-8")
    os.utime(stale, (time.time() - 7200, time.time() - 7200))
    monkeypatch.setattr(ge, "OUTPUT", out)
    monkeypatch.setattr(ge, "load_catalog", lambda: ({}, []))
    envs = _envs(tmp_path, {"p": "FOO_API_KEY=abcdefghijklmnop\n"})
    monkeypatch.setattr(ge, "project_env_files", lambda: envs)
    monkeypatch.setattr(ge, "project_dirs", lambda: [])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    assert ge.main() == 0  # first run writes
    stale.write_text("old", encoding="utf-8")
    os.utime(stale, (time.time() - 7200, time.time() - 7200))
    assert ge.main() == 0  # NO-CHANGE run
    assert not stale.exists()  # swept anyway (BA2)
    # the race: a sibling unlinks the leftover between glob and stat
    gone = tmp_path / "all-envs.env.tmp.2"
    gone.write_text("old", encoding="utf-8")
    real_lstat = ge.Path.lstat

    def racing_lstat(self, *a, **k):
        if self.name == "all-envs.env.tmp.2" and os.path.lexists(self):
            os.unlink(self)  # the sibling got there first
        return real_lstat(self, *a, **k)

    monkeypatch.setattr(ge.Path, "lstat", racing_lstat)
    assert ge.sweep_stale_tmp(out) == 0 and not gone.exists()  # skipped, not raised (BA1)
    monkeypatch.setattr(ge.Path, "lstat", real_lstat)
    # BB2: a leftover under OUR OWN pid (a reused pid after a reboot) is swept like any other
    mine = tmp_path / f"all-envs.env.tmp.{os.getpid()}"
    mine.write_text("old", encoding="utf-8")
    os.utime(mine, (time.time() - 7200, time.time() - 7200))
    assert ge.sweep_stale_tmp(out) == 1 and not mine.exists()
    ge.write_secret_file(out, "SECRET=2\n")  # and O_EXCL does not fail on it
    # BB3: a symlink is judged by ITS OWN age (lstat, never followed) and is never unlinked even
    # when old — the dashed-off `all-envs.env.tmp.9` links to an hours-old real file, then is aged
    # itself; a directory matching the glob is skipped, never raised
    old_target = tmp_path / "some-old-file"
    old_target.write_text("x", encoding="utf-8")
    os.utime(old_target, (time.time() - 7200, time.time() - 7200))
    link = tmp_path / "all-envs.env.tmp.9"
    link.symlink_to(old_target)
    assert (
        ge.sweep_stale_tmp(out) == 0 and link.is_symlink()
    )  # fresh link, old target: lstat keeps it (BD2)
    os.utime(link, (time.time() - 7200, time.time() - 7200), follow_symlinks=False)
    assert (
        ge.sweep_stale_tmp(out) == 0 and link.is_symlink()
    )  # old link: not a regular file, kept (BD2)
    (tmp_path / "all-envs.env.tmp.dir").mkdir()
    os.utime(tmp_path / "all-envs.env.tmp.dir", (time.time() - 7200, time.time() - 7200))
    assert ge.sweep_stale_tmp(out) == 0 and (tmp_path / "all-envs.env.tmp.dir").is_dir()
    link.unlink()
    # BB7: a FRESH legacy-named tmp (a pre-AW1 writer on an old checkout) is a live sibling
    legacy = tmp_path / "all-envs.env.tmp"
    legacy.write_text("in progress", encoding="utf-8")
    assert ge.sweep_stale_tmp(out) == 0 and legacy.read_text(encoding="utf-8") == "in progress"


def test_a_malformed_url_never_kills_classify_or_the_scan(tmp_path, monkeypatch):
    """`http://a]b` makes urlsplit raise: a model answer with it is written as `?` and the batch
    survives (BB5); a project's own malformed `*_URL` does not kill the triage parse (BB5); a
    catalog entry with it is skipped by the url index, not a traceback (BB6)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
        "FOO_API_URL=http://a]b\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "foo",
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "http://a]b",
                    "status": "active",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    assert cs.flagged_providers(tmp_path / "all-envs.env")["foo"]["urls"] == []
    assert cs.main() == 0
    assert json.loads(cat.read_text(encoding="utf-8"))["foo"]["url"] == "?"
    idx = ge.catalog_url_index({"bad": {"url": "http://a]b"}, "ok": {"url": "https://ok.test"}})
    assert idx == {"ok.test": "ok", "*.ok.test": "ok"}


def test_only_the_typed_catalog_error_is_a_one_liner(tmp_path, monkeypatch, capsys):
    """An unrelated ValueError inside the scan is a BUG and keeps its traceback — main's one-line
    exit is reserved for CatalogError (BB6/BD1)."""
    monkeypatch.setattr(ge, "OUTPUT", tmp_path / "all-envs.env")
    monkeypatch.setattr(
        ge, "consolidate", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom"))
    )
    monkeypatch.setattr(
        ge, "project_env_files", lambda: _envs(tmp_path, {"p": "X_API_KEY=abcdefghijklmnop\n"})
    )
    monkeypatch.setattr(ge, "project_dirs", lambda: [])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    with pytest.raises(ValueError, match="boom"):
        ge.main()


def test_a_fresh_leftover_under_our_own_pid_never_blocks_the_write(tmp_path):
    """A crash followed by a pid reuse within the sweep's hour: the leftover carries OUR pid and
    no other live process can — it is removed before O_EXCL instead of failing the run (BD4)."""
    import os

    out = tmp_path / "all-envs.env"
    mine = tmp_path / f"all-envs.env.tmp.{os.getpid()}"
    mine.write_text("partial", encoding="utf-8")
    ge.write_secret_file(out, "SECRET=1\n")
    assert out.read_text(encoding="utf-8") == "SECRET=1\n" and not mine.exists()


def test_a_scalar_match_is_one_prefix_on_both_sides(tmp_path, monkeypatch):
    """`"match": "OPENAI"` (a hand-edited scalar): load_catalog reads ONE prefix, never six letters
    that hijack `N_KEY` and un-match the vendor's own keys (BE4); the classify merge path appends
    to it instead of crashing on `str.append` after the paid batch is spent (BE3)."""
    cat = tmp_path / "catalog.json"
    cat.write_text(
        json.dumps(
            {"openai": {"category": "ai-llm", "match": "OPENAI", "url": "https://openai.com"}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    catalog, matchers = ge.load_catalog()
    assert matchers == [("OPENAI", "openai")]
    assert (
        ge.match_provider("OPENAI_API_KEY", matchers) == "openai"
        and ge.match_provider("N_KEY", matchers) is None
    )
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=kagi category=? cost=? capability="?" url=? status=? used_by=web\n'
        "KAGI_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "brave",
                    "category": "search",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://brave.com",
                    "status": "active",
                }
            )
        )
    ]
    sub = tmp_path / "c"
    sub.mkdir()
    cat2, _ = _classify_env(sub, monkeypatch, text, ["--apply"], res)
    cat2.write_text(
        json.dumps(
            {
                "brave": {
                    "category": "search",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://brave.com",
                    "status": "active",
                    "match": "BRAVE",
                }
            }
        ),
        encoding="utf-8",
    )
    assert cs.main() == 0
    out2 = json.loads(cat2.read_text(encoding="utf-8"))["brave"]
    assert out2["match"] == "BRAVE" and out2["merged_match"] == [
        "KAGI"
    ]  # merged prefixes are segregated (BH1)


def test_an_omitted_status_is_unknown_and_ipv6_hosts_keep_their_brackets(tmp_path, monkeypatch):
    """A model answer WITHOUT `status` is `?`, never `active` (BE5); a project's IPv6 `*_URL`
    reaches the pool prompt as `https://[::1]`, a value `_host` can read back (BE8)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
        "FOO_API_URL=https://[::1]:8443/x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "foo",
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://foo.test",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    urls = cs.flagged_providers(tmp_path / "all-envs.env")["foo"]["urls"]
    assert urls == ["https://[::1]"] and cs._host(urls[0]) == "::1"
    assert cs.main() == 0
    assert json.loads(cat.read_text(encoding="utf-8"))["foo"]["status"] == "?"


def test_an_unreadable_catalog_is_refused_before_the_paid_dispatch(tmp_path, monkeypatch):
    """A catalog the classifier cannot read must fail BEFORE fanout — after it, the cursor has
    moved and the whole paid slice is lost for a lap (BH2)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
    )
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], [])
    cat.write_text('{"truncated": ', encoding="utf-8")
    calls: list[int] = []
    monkeypatch.setattr(cs, "fanout", lambda *a, **k: calls.append(1) or ([], ""))
    assert cs.main() == 1 and calls == []


def test_hostile_catalog_shapes_fail_closed_never_tracebacks(tmp_path, monkeypatch):
    """An undecodable file (BH3) and a top-level list (BH6) are `CatalogError` — the scan fails
    CLOSED and `main` exits 1 (BS2): degraded to "everything flagged" they exited 0 past the chain
    gate, and the sync blanked every vendor, stored every credential unattributed and pruned 22
    providers under the bound. A `null`/list category is `?`; an empty match prefix is skipped (BH8)."""
    cat = tmp_path / "catalog.json"
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    cat.write_bytes(b'{"a": "\xe9"}')
    with pytest.raises(ge.CatalogError, match="unreadable"):
        ge.load_catalog()
    cat.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ge.CatalogError, match="not a JSON object"):
        ge.load_catalog()
    cat.unlink()
    with pytest.raises(ge.CatalogError, match="unreadable"):
        ge.load_catalog()  # a missing catalog is not an empty one
    cat.write_text(json.dumps({"v": {"category": None, "match": ["", "V"]}}), encoding="utf-8")
    catalog, matchers = ge.load_catalog()
    assert matchers == [("V", "v")]
    monkeypatch.setattr(ge, "load_catalog", lambda: (catalog, matchers))
    body, _ = ge.consolidate(_envs(tmp_path, {"p": "V_API_KEY=abcdefghijklmnop\n"}))
    assert "#svc name=v category=?" in body and "None" not in body


def test_a_null_match_merges_as_empty_not_the_word_none(tmp_path, monkeypatch):
    """`"match": null` on a curated entry becomes `[]` + the merged prefix, never `["None", …]`
    (BH5)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=kagi category=? cost=? capability="?" url=? status=? used_by=web\n'
        "KAGI_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "brave",
                    "category": "search",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://brave.com",
                    "status": "active",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    cat.write_text(
        json.dumps(
            {
                "brave": {
                    "category": "search",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://brave.com",
                    "status": "active",
                    "match": None,
                    "hosts": None,
                    "merged_match": None,
                }
            }
        ),
        encoding="utf-8",
    )
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))["brave"]
    assert (
        out["merged_match"] == ["KAGI"] and out["match"] is None
    )  # merged prefixes never touch the curated list (BH1/BH5)


def test_the_shipped_merged_prefix_reader_feeds_the_fetcher_gate(tmp_path, monkeypatch):
    """`registry_sync.merged_prefixes()` reads `merged_match` from the REAL catalog file — the
    security gate's input, exercised through the shipped reader, not a monkeypatched list (BJ1)."""
    cat = tmp_path / "catalog.json"
    cat.write_text(
        json.dumps(
            {
                "deepl": {
                    "category": "ai-translate",
                    "match": ["DEEPL"],
                    "merged_match": ["AAA", None, ""],
                },
                "exa": {"category": "search", "match": ["EXA"], "merged_match": "BBB"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    assert ge.merged_matchers(ge.load_catalog()[0]) == [("AAA", "deepl"), ("BBB", "exa")]
    prov = rs.catalog_provenance()
    assert prov is not None and prov[1] == {("AAA", "deepl"), ("BBB", "exa")}
    merged = prov
    assert not rs.owned_by("AAA_API_KEY", "deepl", merged) and not rs.owned_by(
        "BBB_API_KEY", "exa", merged
    )
    assert not rs.owned_by(
        "AAA_API_KEY", "exa", merged
    )  # claimed by ANY merged prefix → model-attributed (BJ4)
    assert rs.owned_by("DEEPL_API_KEY", "deepl", merged) and rs.owned_by(
        "HF_TOKEN", "huggingface", merged
    )


def test_the_cursor_never_moves_when_the_catalog_probe_fails(tmp_path, monkeypatch):
    """An unreadable catalog aborts BEFORE the cursor write — the slice is not skipped for a lap
    (BK4)."""
    text = "# ═ NEEDS-TRIAGE ═\n" + "".join(
        f'#svc name=p{i:02d} category=? cost=? capability="?" url=? status=? used_by=-\nP{i:02d}_API_KEY=x\n'
        for i in range(12)
    )
    cat, state = _classify_env(tmp_path, monkeypatch, text, ["--apply", "--max-per-run", "5"], [])
    cat.write_text('{"truncated": ', encoding="utf-8")
    monkeypatch.setattr(cs, "fanout", lambda *a, **k: ([], ""))
    assert cs.main() == 1 and not (state / "c.json").exists()


def test_a_hand_edit_during_the_paid_dispatch_survives_the_write(tmp_path, monkeypatch):
    """The pre-dispatch parse is a probe; the merge re-reads the catalog, so an edit made while
    the pool ran is never reverted by the write (BK6)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
    )
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], [])
    cat.write_text(json.dumps({"bar": {"category": "search", "match": ["BAR"]}}), encoding="utf-8")

    def editing_fanout(*a, **k):  # the operator edits the catalog while the pool runs
        cat.write_text(
            json.dumps({"bar": {"category": "search", "match": ["BAR"], "note": "edited"}}),
            encoding="utf-8",
        )
        return [
            _Res(
                json.dumps(
                    {
                        "name": "foo",
                        "category": "search",
                        "cost": "free",
                        "capability": "x",
                        "url": "https://foo.test",
                        "status": "active",
                    }
                )
            )
        ], ""

    monkeypatch.setattr(cs, "fanout", editing_fanout)
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert out["bar"].get("note") == "edited" and out["foo"]["category"] == "search"


def test_a_merged_prefix_survives_a_rewrite_of_its_target(tmp_path, monkeypatch):
    """The merge target is itself in the batch (a `?` entry): its rewrite keeps `merged_match`,
    else the merged provider returns to triage and is re-billed forever (BK2)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=aaa category=? cost=? capability="?" url=? status=? used_by=web\n'
        "AAA_API_KEY=x\n"
        '#svc name=tgt category=? cost=? capability="?" url=? status=? used_by=web\n'
        "TGT_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "tgt",
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://tgt.test",
                    "status": "active",
                }
            )
        ),
        _Res(
            json.dumps(
                {
                    "name": "tgt",
                    "category": "search",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://tgt.test",
                    "status": "active",
                }
            )
        ),
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], res)
    cat.write_text(json.dumps({"tgt": {"category": "?", "match": ["TGT"]}}), encoding="utf-8")
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert (
        out["tgt"]["merged_match"] == ["AAA"]
        and out["tgt"]["category"] == "search"
        and "aaa" not in out
    )


def test_wildcard_attribution_keys_on_the_registrable_domain(tmp_path, monkeypatch, capsys):
    """`api.foo.org` is a different organisation from the vendor at `foo.com`: the wildcard is
    `*.foo.com`, so the `.org` host goes to triage, never to `foo` (C5)."""
    idx = ge.catalog_url_index({"foo": {"url": "https://foo.com"}})
    assert idx == {"foo.com": "foo", "*.foo.com": "foo"}
    cat = {"foo": {"url": "https://foo.com"}}
    assert ge.provider_for_host("api.foo.com", cat, idx, []) == "foo"
    assert (
        ge.provider_for_host("api.foo.org", cat, idx, [("FOO", "foo")]) is None
    )  # the label fallback respects the entry's own domain — with the vendor's OWN prefix in the
    # matchers, the production shape: falling through to `FOO_API_KEY` re-credited it (BS3)
    err = capsys.readouterr().err  # … and says so, naming the fix (BW1)
    assert "WARNING: host api.foo.org carries catalogued label foo" in err and "`hosts`" in err, err
    # the refused host is never filed under the vendor's own name (the classifier would overwrite
    # the curated entry with its answer) — its block is the registrable domain (BW1)
    assert ge.code_only_block_name("api.foo.org", cat) == "foo-org"
    assert ge.code_only_block_name("api.bar.org", cat) == "bar"
    assert (
        ge.provider_for_host("api.foo.org", {"foo": {}}, idx, []) == "foo"
    )  # no url on the entry: the label is the only evidence
    assert (
        ge.host_domain("x.foo.co.uk") == "foo.co.uk" and ge.host_domain("api.foo.org") == "foo.org"
    )


def test_a_url_with_a_comma_survives_the_svc_line_and_state_files_are_typed(tmp_path, monkeypatch):
    """A catalog url may carry a legal `,` (only whitespace breaks the token, C7); a wrong-typed
    cursor or error count is the default, never a TypeError (C2)."""
    line = ge.svc_line("acme", {"category": "search", "url": "https://x.test/a,b"}, {"p"})
    assert rs.SVC_RE.match(line).groupdict()["url"] == "https://x.test/a,b"
    text = "# ═ NEEDS-TRIAGE ═\n" + "".join(
        f'#svc name=p{i:02d} category=? cost=? capability="?" url=? status=? used_by=-\nP{i:02d}_API_KEY=x\n'
        for i in range(4)
    )
    cat, state = _classify_env(
        tmp_path, monkeypatch, text, ["--apply", "--max-per-run", "2"], [_Res("not json")] * 4
    )
    (state / "c.json").write_text(json.dumps({"after": 123}), encoding="utf-8")
    (state / "e.json").write_text(json.dumps({"p00": "3", "p01": 1}), encoding="utf-8")
    assert cs.main() == 0  # neither state file crashes the run
    assert cs.apply_error_budget({"p00"}, ["p00"], {"p00": "3"})[0] == {"p00": 1}


def test_only_with_no_flagged_name_is_a_failure(tmp_path, monkeypatch):
    """`--only TYPO --apply`: nothing dispatched must be exit 1, never a silent 0 (C6)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
    )
    _classify_env(tmp_path, monkeypatch, text, ["--apply", "--only", "typo"], [])
    assert cs.main() == 1


def test_a_catalog_broken_during_the_dispatch_merges_onto_the_probe(tmp_path, monkeypatch, capsys):
    """The catalog becomes unreadable while the pool runs: the paid batch is merged onto the
    pre-dispatch probe copy and written, never discarded (BM3)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=web\n'
        "FOO_API_KEY=x\n"
    )
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], [])
    cat.write_text(json.dumps({"bar": {"category": "search", "match": ["BAR"]}}), encoding="utf-8")

    def corrupting_fanout(*a, **k):
        cat.write_text('{"truncated": ', encoding="utf-8")
        return [
            _Res(
                json.dumps(
                    {
                        "name": "foo",
                        "category": "search",
                        "cost": "free",
                        "capability": "x",
                        "url": "https://foo.test",
                        "status": "active",
                    }
                )
            )
        ], ""

    monkeypatch.setattr(cs, "fanout", corrupting_fanout)
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert out["foo"]["category"] == "search" and out["bar"]["match"] == ["BAR"]
    err = capsys.readouterr().err
    assert "merging onto the pre-dispatch copy" in err
    # the failure path REVERTS any catalog edit landed since the probe — the warning must say so
    # and date the copy it merged onto (BR7)
    assert "DISCARDED" in err and re.search(r"read at \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC", err), (
        err
    )  # labelled UTC like every other chain stamp — a bare local time mis-sized the window by 3 h (BS10)


def test_a_prefix_two_vendors_claim_routes_to_neither():
    """Equal-length prefixes of two providers: the key is attributed to NEITHER, in either list
    order — the first hit of a stable longest-first sort gave it to whichever vendor sorted first,
    i.e. one vendor's secret filed under the other (BQ1)."""
    for order in ([("XY", "aaa"), ("XY", "zzz")], [("XY", "zzz"), ("XY", "aaa")]):
        assert ge.match_provider("XY_API_KEY", order) is None, order
    assert (
        ge.match_provider("XY_API_KEY", [("XY", "aaa"), ("XY_API", "zzz")]) == "zzz"
    )  # longer wins
    assert (
        ge.match_provider("XY_API_KEY", [("XY", "aaa"), ("XY", "aaa")]) == "aaa"
    )  # one vendor twice
    assert (
        ge.match_provider("XYZ_API_KEY", [("XY", "aaa"), ("XY", "zzz")]) is None
    )  # token boundary
    # `EXA_` is the SAME token as `EXA`: a trailing `_` is not a longer prefix (BS4)
    for order in ([("EXA", "exa"), ("EXA_", "evil")], [("EXA_", "evil"), ("EXA", "exa")]):
        assert ge.match_provider("EXA_API_KEY", order) is None, order
    assert ge.prefix_hits("EXA_API_KEY", [("EXA_", "exa")]) == [("EXA", "exa")]
    assert ge.match_provider("EXA_API_KEY", [("EXA_", "exa"), ("EXA", "exa")]) == "exa"


def test_a_prefix_two_vendors_claim_fails_the_scan(tmp_path, monkeypatch):
    """A tie costs money daily (the derived block is re-flagged for paid triage every run, and
    tombstone/merge are both inert for it) — load_catalog REFUSES the catalog, naming the prefix and
    both claimants (BS5/BW5)."""
    cat = tmp_path / "catalog.json"
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    cat.write_text(
        json.dumps({"aaa": {"match": ["XY"]}, "zzz": {"match": ["XY_"]}, "ok": {"match": ["OK"]}}),
        encoding="utf-8",
    )
    with pytest.raises(ge.CatalogError, match=r"XY \(aaa, zzz\)") as info:
        ge.load_catalog()  # FAILS the scan — the chain alerts; a stderr line was no channel (BW5)
    assert "OK" not in str(info.value).replace("XY", "")  # an unshared prefix is never named
    cat.write_text(
        json.dumps({"aaa": {"match": ["_", "AAA"]}, "zzz": {"match": ["__"]}}), encoding="utf-8"
    )
    _, matchers = ge.load_catalog()  # an all-`_` prefix claims nothing and routes nothing (BW6)
    assert (
        ge.prefix_hits("_FOO_KEY", matchers) == []
        and ge.match_provider("_FOO_KEY", matchers) is None
    )


def test_a_malformed_catalog_url_never_crashes_the_label_fallback():
    """A hand-edited catalog url `urlsplit` rejects (`https://[foo].com`) is skipped by the url
    index (BB6) and then reached the label fallback UNGUARDED — a plain ValueError past `main`'s
    except, the chain DEAD every day until the file was repaired (BR1)."""
    catalog = {"foo": {"url": "https://[foo].com"}}
    assert ge.provider_for_host("api.foo.com", catalog, {}, []) == "foo"  # the label still decides


def test_a_relocated_copy_writes_under_itself_and_still_skips_the_hub_env(tmp_path):
    """The invariant EXECUTED on a relocated copy (in the real checkout `REPO/…` and the old
    hardcode are the same Path, so equality proved nothing — BV3): a copy of this module under
    another root derives its write target from ITS file, and still excludes the FLEET hub's env —
    `/opt/fabrik/.env` is never a project's, wherever the copy lives (BS17/BW3)."""
    import importlib.util

    root = tmp_path / "elsewhere"
    (root / "scripts").mkdir(parents=True)
    copy = root / "scripts" / "gather_envs.py"
    copy.write_text(Path(ge.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("gather_envs_relocated", copy)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert root / "secrets" / "all-envs.env" == mod.OUTPUT and root == mod.REPO
    opt = tmp_path / "opt"
    for name in ("fabrik", "proj", "_parked"):
        (opt / name).mkdir(parents=True)
        (opt / name / ".env").write_text("A=1\n", encoding="utf-8")
    mod.OPT = opt
    assert mod.project_env_files() == [opt / "proj" / ".env"]


def test_the_live_catalog_claims_every_sibling_domain_host():
    """The 14 live hosts of 8 vendors whose url sits on another registrable domain
    (`fal.run` for fal.ai, `replicate.delivery`, `youtube.com`, `supabase.co`, `siliconflow.com`,
    `bfl.ai`, `kilo.ai`, `openpagerank.com`) are claimed through the entry's `hosts` — the label
    guard (BS3) refuses them by design, so the catalog must name them (BW1)."""
    catalog, matchers = ge.load_catalog()
    idx = ge.catalog_url_index(catalog)
    expected = {
        "api.bfl.ai": "bfl",
        "bfl.ai": "bfl",
        "playground.bfl.ai": "bfl",
        "api.kilo.ai": "kilo",
        "kilo.ai": "kilo",
        "api.siliconflow.com": "siliconflow",
        "fal.run": "fal",
        "queue.fal.run": "fal",
        "img.youtube.com": "youtube",
        "www.youtube.com": "youtube",
        "youtube.com": "youtube",
        "openpagerank.com": "openpagerank",
        "replicate.delivery": "replicate",
        "your-project.supabase.co": "supabase",
    }
    got = {h: ge.provider_for_host(h, catalog, idx, matchers) for h in expected}
    assert got == expected, {h: (got[h], v) for h, v in expected.items() if got[h] != v}


def test_a_merged_copy_of_a_curated_token_is_dropped_on_both_sides(tmp_path, monkeypatch):
    """`HF_` curated and `HF` merged are ONE token: the merged copy adds no routing and would
    disown the vendor's own keys through registry_sync's merged check — `merged_matchers` drops it
    at read time, and the classifier's merge path never mints it (BW4)."""
    assert ge.merged_matchers({"hf": {"match": ["HF_"], "merged_match": ["HF", "HFX"]}}) == [
        ("HFX", "hf")
    ]
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=hf category=? cost=? capability="?" url=? status=? used_by=web\n'
        "HF_TOKEN=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "huggingface",
                    "category": "ai-llm",
                    "cost": "freemium",
                    "capability": "models",
                    "url": "https://huggingface.co",
                    "status": "active",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
    cat.write_text(
        json.dumps(
            {
                "huggingface": {
                    "category": "ai-llm",
                    "cost": "freemium",
                    "capability": "models",
                    "url": "https://huggingface.co",
                    "status": "active",
                    "match": ["HF_", "HUGGINGFACE"],
                }
            }
        ),
        encoding="utf-8",
    )
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))
    assert "hf" not in out and out["huggingface"].get("merged_match", []) == [], out["huggingface"]


def test_only_on_a_curated_name_is_refused_and_the_scan_never_flags_it(tmp_path, monkeypatch):
    """`--only <name>` on a name that is not in NEEDS-TRIAGE is refused before any paid dispatch —
    a real-category curated entry is never there (the scan files its key under the entry, CC1, graded
    by `test_a_key_named_for_a_catalogued_vendor_files_under_its_entry`). This grader proves only the
    refusal (the pre-existing triage filter, C6); the fixture's triage block carries `other`, not `kilo`."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=other category=? cost=? capability="?" url=? status=? used_by=web\n'
        "OTHER_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "kilo",
                    "category": "ai-llm",
                    "cost": "paid",
                    "capability": "x",
                    "url": "https://kilo.ai",
                    "status": "active",
                }
            )
        )
    ]
    curated = {
        "category": "ai-coding",
        "cost": "?",
        "capability": "the operator's words",
        "url": "https://kilocode.ai",
        "status": "retired",
        "match": ["KILO_"],
    }
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply", "--only", "kilo"], res)
    cat.write_text(json.dumps({"kilo": curated}), encoding="utf-8")
    assert cs.main() == 1 and json.loads(cat.read_text(encoding="utf-8"))["kilo"] == curated


def test_an_emptied_catalog_is_refused_when_the_last_consolidation_knew_vendors(
    tmp_path, monkeypatch
):
    """`{}` is a legitimate bootstrap (BR3) — but a catalog that just lost its vendors would blank
    every one of them to `?`: when the previous consolidation carries catalogued `#svc` lines the
    scan fails closed and the previous file stands (BW11)."""
    cat = tmp_path / "catalog.json"
    cat.write_text("{}", encoding="utf-8")
    out = tmp_path / "all-envs.env"
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    monkeypatch.setattr(ge, "OUTPUT", out)
    out.write_text(
        "# header\n# ═══ ai-llm ═══\n"
        '#svc name=deepl category=ai-translate cost=freemium capability="x" url=https://deepl.com status=active used_by=p\n',
        encoding="utf-8",
    )
    with pytest.raises(ge.CatalogError, match="knew 1 catalogued vendor"):
        ge.refuse_emptied_catalog()
    kept = out.read_text(encoding="utf-8")
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / ".env").write_text("FOO_API_KEY=x\n", encoding="utf-8")
    monkeypatch.setattr(ge, "project_env_files", lambda: [tmp_path / "p" / ".env"])
    monkeypatch.setattr(ge, "project_dirs", lambda: [])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    assert ge.main() == 1 and out.read_text(encoding="utf-8") == kept  # nothing written
    out.write_text(
        "# header\n# ═══ NEEDS-TRIAGE ═══\n"
        '#svc name=foo category=? cost=? capability="?" url=? status=? used_by=p\n',
        encoding="utf-8",
    )
    ge.refuse_emptied_catalog()  # nothing catalogued before: a bootstrap, not a loss
    assert ge.main() == 0


def test_a_tombstone_retried_into_another_vendor_leaves_no_tie_behind(tmp_path, monkeypatch):
    """A tombstoned `gemini` (its own `match: ["GEMINI"]`) re-tried and answered `name: google-ai`:
    the merge writes `GEMINI` into google-ai's `merged_match` — leaving the tombstone behind made a
    cross-provider tie that fails EVERY later scan, permanently (BX8, the cascade BW5's fail-closed
    posture created). The TOMBSTONE is removed; a CURATED source never is (CA3); the catalog loads
    clean either way."""

    def run(catalog: dict, answer: str = "google-ai"):
        text = (
            "# ═ NEEDS-TRIAGE ═\n"
            '#svc name=gemini category=? cost=? capability="?" url=? status=? used_by=web\n'
            "GEMINI_API_KEY=x\n"
        )
        res = [
            _Res(
                json.dumps(
                    {
                        "name": answer,
                        "category": "ai-llm",
                        "cost": "freemium",
                        "capability": "gemini models",
                        "url": "https://ai.google.dev",
                        "status": "active",
                    }
                )
            )
        ]
        cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
        cat.write_text(json.dumps(catalog), encoding="utf-8")
        assert cs.main() == 0
        monkeypatch.setattr(ge, "CATALOG_PATH", cat)
        out = json.loads(cat.read_text(encoding="utf-8"))
        _, matchers = ge.load_catalog()  # never a tie → never a CatalogError
        return out, matchers

    google = {
        "category": "ai-llm",
        "cost": "freemium",
        "capability": "gemini models",
        "url": "https://ai.google.dev",
        "status": "active",
        "match": ["GOOGLE_AI"],
    }
    # 1. a tombstone source is popped; its token becomes the target's merged prefix
    out, matchers = run(
        {
            "google-ai": google,
            "gemini": {"category": "unidentified", "status": "unidentified", "match": ["GEMINI"]},
        }
    )
    assert "gemini" not in out and out["google-ai"]["merged_match"] == ["GEMINI"], out
    assert ge.match_provider("GEMINI_API_KEY", matchers) == "google-ai"
    # 2. a CURATED source is never popped, and its token is never minted onto the target — the
    #    operator's `match` keeps routing the key to the operator's entry (CA3; at dd55ca81 the
    #    curated `captcha` entry vanished and CAPTCHA_API_KEY routed to anticaptcha)
    curated = {
        "category": "captcha",
        "status": "active",
        "match": ["GEMINI"],
        "url": "https://g.example",
    }
    out, matchers = run({"google-ai": google, "gemini": curated})
    assert (
        out["gemini"]["match"] == ["GEMINI"] and out["google-ai"].get("merged_match", []) == []
    ), out
    assert ge.match_provider("GEMINI_API_KEY", matchers) == "gemini"
    # 3. a token ANOTHER entry carries — curated OR merged (CA4) — is never minted: merged without
    #    a prefix (the curator keeps routing the key), no orphan entry duplicating the target's url
    #    (CA5's did, and de-attributed the target's host — CC3)
    for holder in ({"match": ["GEMINI_"]}, {"merged_match": ["GEMINI"]}):
        out, matchers = run(
            {
                "google-ai": google,
                "vertex": {"category": "ai-llm", "status": "active", "match": ["VERTEX"], **holder},
            }
        )
        assert out["google-ai"].get("merged_match", []) == [] and "gemini" not in out, out
        assert ge.match_provider("GEMINI_API_KEY", matchers) == "vertex"
    # 4. a CURATED source whose own token is NOT one of its prefixes: the merge mints the token onto
    #    the target and the pop guard keeps the operator's entry — 89 of 89 tests stayed green when
    #    the guard was removed at 32493a98 (CC2)
    curated = {
        "category": "captcha",
        "status": "active",
        "match": ["GOOGLE_GEMINI"],
        "url": "https://g.example",
    }
    out, matchers = run({"google-ai": google, "gemini": curated})
    # …and is never folded into another vendor by a model's word at all: the identified path keeps
    # the operator's entry (category included), nothing is minted onto the target (CE2)
    # (the classifier's enum verdict lands on `category` — the operator's other fields stand, CE3;
    # a real-category entry cannot reach here in production, CC1 adopts it before triage)
    assert out["gemini"]["match"] == ["GOOGLE_GEMINI"] and out["gemini"]["category"] == "ai-llm", (
        out
    )
    assert out["google-ai"].get("merged_match", []) == [], out
    assert ge.match_provider("GOOGLE_GEMINI_API_KEY", matchers) == "gemini"
    # 5. a `?` placeholder the operator left with curated routing is not a tombstone (CC4)
    placeholder = {"category": "?", "match": ["GOOGLE_GEMINI"], "hosts": ["g.example"]}
    out, _ = run({"google-ai": google, "gemini": placeholder})
    assert out["gemini"]["match"] == ["GOOGLE_GEMINI"], out
    # …and it LEAVES triage: the model's category lands on the placeholder itself (never merged
    # away — merged, it stayed `?` and was re-billed every lap, CE2)
    assert (
        out["gemini"]["category"] == "ai-llm" and out["google-ai"].get("merged_match", []) == []
    ), out
    # 6. …and when its curated prefix IS its own name, the merge path must apply the SAME rule: the
    #    inline test on the old rule minted GEMINI onto the target while the pop left the entry —
    #    a tie, every later scan dead (CD1)
    out, matchers = run(
        {
            "google-ai": google,
            "gemini": {"category": "?", "match": ["GEMINI"], "url": "https://g.example"},
        }
    )
    assert (
        out["gemini"]["match"] == ["GEMINI"] and out["google-ai"].get("merged_match", []) == []
    ), out
    assert ge.match_provider("GEMINI_API_KEY", matchers) == "gemini"


def test_a_key_named_for_a_catalogued_vendor_files_under_its_entry(tmp_path, monkeypatch):
    """`HUGGINGFACE_API_KEY` under an entry `huggingface` that curates only `HF_`: the derived name
    IS the catalog key, so the scan files the key under the entry — catalogued, never NEEDS-TRIAGE,
    never a paid dispatch (17 of 109 live entries curate no prefix for their own key; rounds 22–24
    fought over what the classifier should do with such a block — it never gets one, CC1)."""
    cat = tmp_path / "catalog.json"
    cat.write_text(
        json.dumps(
            {
                "huggingface": {
                    "category": "ai-llm",
                    "cost": "freemium",
                    "capability": "models",
                    "url": "https://huggingface.co",
                    "status": "active",
                    "match": ["HF_"],
                },
                "zed": {"category": "unidentified", "status": "unidentified", "match": []},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    env = tmp_path / "p" / ".env"
    env.parent.mkdir()
    env.write_text(
        "HUGGINGFACE_API_KEY=abc\nZED_API_KEY=def\nNEWVENDOR_API_KEY=ghi\n", encoding="utf-8"
    )
    body, stats = ge.consolidate([env])
    assert (
        '#svc name=huggingface category=ai-llm cost=freemium capability="models" url=https://huggingface.co status=active'
        in body
    ), body
    assert "#svc name=zed category=unidentified" in body  # a tombstone is adopted too: no re-bill
    assert (
        "#svc name=newvendor category=?" in body
    )  # pre-existing: an unknown name still goes to triage (not CC1's)


def test_a_placeholder_with_routing_keeps_the_operators_fields_when_dispatched(
    tmp_path, monkeypatch, capsys
):
    """The ONE curated shape the classifier still receives: a `?` placeholder the operator left with
    curated routing routes its own key, so its block is in triage and dispatched — the operator's
    `cost`/`capability`/`url`/`status` stand, the model fills `category` (and any `?`), `--only` on it
    behaves the same (CD2; at 993872de the model flipped `retired` to `active` and replaced the url)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=acme category=? cost=free capability="OPERATOR words" url=https://acme.example status=retired used_by=web\n'
        "ACME_API_KEY=x\n"
    )
    res = [
        _Res(
            json.dumps(
                {
                    "name": "acme",
                    "category": "ai-llm",
                    "cost": "paid",
                    "capability": "model answer",
                    "url": "https://wrong.example",
                    "status": "active",
                }
            )
        )
    ]
    placeholder = {
        "category": "?",
        "cost": "free",
        "capability": "OPERATOR words",
        "url": "https://acme.example",
        "status": "retired",
        "match": ["ACME"],
        "hosts": ["acme.example"],
    }
    for argv in (["--apply"], ["--apply", "--only", "acme"]):
        cat, _ = _classify_env(tmp_path, monkeypatch, text, argv, res)
        cat.write_text(json.dumps({"acme": placeholder}), encoding="utf-8")
        assert cs.main() == 0
        out = json.loads(cat.read_text(encoding="utf-8"))["acme"]
        assert {k: out[k] for k in ("cost", "capability", "url", "status", "match", "hosts")} == {
            k: placeholder[k] for k in ("cost", "capability", "url", "status", "match", "hosts")
        }, (argv, out)
        assert out["category"] == "ai-llm", out  # the unknown was filled
        assert (
            "acme: kept the operator's" in capsys.readouterr().out
        )  # said beside the proposal (CE5/CJ2)


def test_a_write_failure_is_one_line_and_the_previous_file_stands(tmp_path, monkeypatch, capsys):
    """Disk full / permission lost on `secrets/`: exit 1 with a one-line ERROR, never a traceback —
    the alert says the step's stderr names the cause, and a traceback's first line named nothing
    (CD4). The adoption summary is printed on the success path (CD3)."""
    cat = tmp_path / "catalog.json"
    cat.write_text(
        json.dumps({"hf": {"category": "ai-llm", "status": "active", "match": ["HFX_"]}}),
        encoding="utf-8",
    )
    out = tmp_path / "all-envs.env"
    env = tmp_path / "p" / ".env"
    env.parent.mkdir()
    env.write_text("HF_API_KEY=x\n", encoding="utf-8")
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    monkeypatch.setattr(ge, "OUTPUT", out)
    monkeypatch.setattr(ge, "project_env_files", lambda: [env])
    monkeypatch.setattr(ge, "project_dirs", lambda: [])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])

    def no_space(path, content):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(ge, "write_secret_file", no_space)
    assert ge.main() == 1 and not out.exists()
    captured = capsys.readouterr()
    assert (
        captured.err.startswith("ERROR: cannot read or write") and "Traceback" not in captured.err
    ), captured.err
    assert (
        "entries adopted by a key named for them: hf" in captured.out
    )  # said BEFORE the write (CE6)
    # the previous file unreadable / the directory unwritable: the same one line (CE7)
    monkeypatch.setattr(
        ge, "read_existing_body", lambda p: (_ for _ in ()).throw(PermissionError(13, "denied"))
    )
    assert ge.main() == 1
    captured = capsys.readouterr()
    assert (
        captured.err.startswith("ERROR: cannot read or write") and "Traceback" not in captured.err
    ), captured.err
    monkeypatch.undo()
    monkeypatch.setattr(ge, "CATALOG_PATH", cat)
    monkeypatch.setattr(ge, "OUTPUT", out)
    monkeypatch.setattr(ge, "project_env_files", lambda: [env])
    monkeypatch.setattr(ge, "project_dirs", lambda: [])
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    assert ge.main() == 0
    assert "entries adopted by a key named for them: hf" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["gather_envs.py"])  # the dry-run says it too (CE6)
    assert (
        ge.main() == 0 and "entries adopted by a key named for them: hf" in capsys.readouterr().out
    )
    # the emptied-catalog guard reads the PREVIOUS file before the write: unreadable, the same one
    # line — it sat outside the handler (CJ1)
    monkeypatch.setattr(sys, "argv", ["gather_envs.py", "--apply"])
    monkeypatch.setattr(
        ge, "read_existing_body", lambda p: (_ for _ in ()).throw(PermissionError(13, "denied"))
    )
    assert out.exists() and ge.main() == 1
    captured = capsys.readouterr()
    assert (
        captured.err.startswith("ERROR: cannot read or write") and "Traceback" not in captured.err
    ), captured.err


def test_a_placeholders_operator_words_survive_an_unidentifiable_answer_and_a_list_category(
    tmp_path, monkeypatch, capsys
):
    """The tombstone branch (an enum-rejected answer under `--tombstone-unresolved`) kept only the
    routing fields and erased the operator's cost/capability/url/status — a lost `url` also loses
    the C5 wildcard credit (CE4). And the identified keep never copies a hand-edited non-str
    `category` back over the classifier's verdict — that re-flagged the block every lap (CE3)."""
    text = (
        "# ═ NEEDS-TRIAGE ═\n"
        '#svc name=acme category=? cost=paid capability="OPERATOR words" url=https://acme.example status=retired used_by=web\n'
        "ACME_API_KEY=x\n"
    )
    placeholder = {
        "category": "?",
        "cost": "paid",
        "capability": "OPERATOR words",
        "url": "https://acme.example",
        "status": "retired",
        "match": ["ACME"],
        "hosts": ["cdn.acme.example"],
    }
    bad = [
        _Res(
            json.dumps(
                {
                    "name": "acme",
                    "category": "nonsense",
                    "cost": "?",
                    "capability": "?",
                    "url": "?",
                    "status": "?",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], bad)
    cat.write_text(json.dumps({"acme": placeholder}), encoding="utf-8")
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))["acme"]
    assert out["category"] == "unidentified", out
    assert {k: out[k] for k in ("cost", "capability", "url", "status", "match", "hosts")} == {
        k: placeholder[k] for k in ("cost", "capability", "url", "status", "match", "hosts")
    }, out
    # …and the tombstone branch applies the scan's own predicate: a list category buckets to `?`
    # there, so an unidentifiable answer must stub it or it is re-billed daily (CJ3)
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], bad)
    cat.write_text(json.dumps({"acme": {**placeholder, "category": ["ai-llm"]}}), encoding="utf-8")
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))["acme"]
    assert out["category"] == "unidentified" and out["url"] == placeholder["url"], out
    for degenerate in ("", None):  # the other non-real shapes the scan buckets to `?` (CM3)
        cat, _ = _classify_env(
            tmp_path, monkeypatch, text, ["--apply", "--tombstone-unresolved"], bad
        )
        cat.write_text(
            json.dumps({"acme": {**placeholder, "category": degenerate}}), encoding="utf-8"
        )
        assert cs.main() == 0
        assert json.loads(cat.read_text(encoding="utf-8"))["acme"]["category"] == "unidentified", (
            degenerate
        )
    good = [
        _Res(
            json.dumps(
                {
                    "name": "acme",
                    "category": "ai-llm",
                    "cost": "free",
                    "capability": "x",
                    "url": "https://acme.example",
                    "status": "active",
                }
            )
        )
    ]
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], good)
    cat.write_text(json.dumps({"acme": {**placeholder, "category": ["ai-llm"]}}), encoding="utf-8")
    assert cs.main() == 0
    out = json.loads(cat.read_text(encoding="utf-8"))["acme"]
    assert out["category"] == "ai-llm" and out["cost"] == "paid", (
        out
    )  # the verdict is the classifier's, the words the operator's
    assert "acme: kept the operator's" in capsys.readouterr().out
    # an entry with NOTHING to keep never claims a keep (CJ2)
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], good)
    cat.write_text(json.dumps({"acme": {"category": ["ai-llm"]}}), encoding="utf-8")
    assert cs.main() == 0 and "kept the operator's" not in capsys.readouterr().out


def test_the_category_predicate_is_one_and_the_guard_counts_the_field(tmp_path, monkeypatch):
    """`real_category` is the single predicate behind the bucketing and the `catalogued` stat — a
    block never counts as catalogued while rendering under NEEDS-TRIAGE (CM3). And the emptied-
    catalog guard counts the `category` FIELD, never the literal anywhere on the line (CM6)."""
    for cat, real in (
        ("ai-llm", True),
        ("?", False),
        ("", False),
        (None, False),
        (["ai-llm"], False),
        ("   ", True),
    ):
        assert ge.real_category(cat) is real, cat
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps({"listy": {"category": ["ai-llm"], "match": ["LISTY"]}}), encoding="utf-8"
    )
    monkeypatch.setattr(ge, "CATALOG_PATH", catalog)
    env = tmp_path / "p" / ".env"
    env.parent.mkdir()
    env.write_text("LISTY_API_KEY=x\n", encoding="utf-8")
    body, stats = ge.consolidate([env])
    assert stats["catalogued"] == 0 and stats["flagged"] == 1 and "NEEDS-TRIAGE" in body
    out = tmp_path / "all-envs.env"
    monkeypatch.setattr(ge, "OUTPUT", out)
    catalog.write_text("{}", encoding="utf-8")
    out.write_text(
        "# ═══ ai-llm ═══\n"
        '#svc name=foo category=ai-llm cost=? capability="category=? in prose" url=? status=? used_by=p\n',
        encoding="utf-8",
    )
    with pytest.raises(ge.CatalogError, match="knew 1 catalogued vendor"):
        ge.refuse_emptied_catalog()  # the FIELD is real; the literal in the capability once hid it


def test_undecodable_ripgrep_output_is_a_scan_that_could_not_run(tmp_path, monkeypatch):
    """A non-UTF-8 path in rg's output raised `UnicodeDecodeError` — a `ValueError`, past every
    handler — so the chain paged "inputs refused (catalog, ripgrep, env files)" for a traceback
    that matched none; it is the documented "ripgrep cannot run" cause (CM4). And an OSError from
    the scan itself is never blamed on the output file: only the emptied-catalog guard's read
    shares that one line (CM5)."""

    def bad_decode(*a, **k):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(ge.subprocess, "run", bad_decode)
    with pytest.raises(ge.CodeScanError):
        ge.scan_code_hosts([tmp_path])
    monkeypatch.setattr(
        ge, "project_dirs", lambda: (_ for _ in ()).throw(PermissionError(13, "denied", "/opt"))
    )
    monkeypatch.setattr(ge, "project_env_files", lambda: [tmp_path / "p" / ".env"])
    monkeypatch.setattr(ge, "OUTPUT", tmp_path / "all-envs.env")
    monkeypatch.setattr(ge, "CATALOG_PATH", tmp_path / "catalog.json")
    (tmp_path / "catalog.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["gather_envs.py"])
    with pytest.raises(PermissionError):  # not caught as "cannot read or write <OUTPUT>"
        ge.main()
