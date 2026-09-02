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


def test_catalog_fail_soft(tmp_path, monkeypatch):
    """Given a malformed service_catalog.json, When loaded, Then it degrades to empty, no crash."""
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(ge, "CATALOG_PATH", bad)
    catalog, matchers = ge.load_catalog()
    assert catalog == {}
    assert matchers == []


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
    assert "*.github" not in idx and "github.com" not in idx and idx["*.resend"] == "resend"
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
        if str(path).endswith(".tmp"):  # only OUR file — the spy is process-wide (Z11)
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
    def __init__(self, text):
        self.agent_id, self.model, self.error, self.text = "a", "m", None, text


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


def test_only_list_is_never_capped(tmp_path, monkeypatch):
    """`--only` names 15 providers: all 15 are dispatched (an operator-typed list is already
    bounded) and the shared cursor stays put (AB1)."""
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
        ["--apply", "--only", ",".join(f"p{i:02d}" for i in range(15))],
        [],
    )
    monkeypatch.setattr(cs, "fanout", fake_fanout)
    assert cs.main() == 0
    assert seen == [15] and not (state / "c.json").exists()


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
    cat, _ = _classify_env(tmp_path, monkeypatch, text, ["--apply"], res)
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
