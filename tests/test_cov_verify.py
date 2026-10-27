"""Hermetic coverage for ``fabrik.verify`` (PostconditionChecker + verify_postconditions).

No network, DNS, TLS or filesystem outside tmp_path: httpx, socket, ssl, time.sleep
and fabrik.audit / fabrik.spec_loader are all replaced.
"""

import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fabrik import verify
from fabrik.verify import (
    CheckResult,
    PostconditionChecker,
    PostconditionResult,
    get_spec_path,
    verify_postconditions,
)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(verify.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


def make_checker(tmp_path, text, context=None):
    p = tmp_path / "spec.yaml"
    p.write_text(text)
    return PostconditionChecker(p, context or {})


def result_of(name, res):
    return PostconditionResult(name, res, "m")


# ---------------------------------------------------------------- spec loading


def test_missing_spec_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        PostconditionChecker(tmp_path / "nope.yaml", {})


def test_variable_substitution_and_none_skipped(tmp_path):
    c = make_checker(
        tmp_path,
        "postconditions:\n  h:\n    url: https://${DOMAIN}/x\n    other: ${MISSING}\n",
        {"DOMAIN": "a.example.com", "MISSING": None},
    )
    cfg = c.spec["postconditions"]["h"]
    assert cfg["url"] == "https://a.example.com/x"
    assert cfg["other"] == "${MISSING}"


def test_non_string_context_value_is_stringified(tmp_path):
    c = make_checker(tmp_path, "port: ${PORT}\n", {"PORT": 8080})
    assert c.spec["port"] == 8080


def test_empty_yaml_raises_valueerror(tmp_path):
    with pytest.raises(ValueError, match="Empty"):
        make_checker(tmp_path, "")


def test_invalid_yaml_raises_valueerror(tmp_path):
    with pytest.raises(ValueError, match="Invalid YAML"):
        make_checker(tmp_path, "a: [unclosed\n")


def test_spec_path_accepts_str(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("a: 1\n")
    c = PostconditionChecker(str(p), {})
    assert isinstance(c.spec_path, Path)
    assert c.results == []


def test_get_check_config_unknown_name_is_empty(tmp_path):
    c = make_checker(tmp_path, "postconditions:\n  a:\n    url: x\n")
    assert c._get_check_config("zzz") == {}
    assert c._get_check_config("a") == {"url": "x"}


def test_get_check_config_without_postconditions_key(tmp_path):
    c = make_checker(tmp_path, "rollback:\n  default: auto\n")
    assert c._get_check_config("a") == {}


@pytest.mark.xfail(strict=True, reason="`postconditions:` with null value crashes with AttributeError")
def test_null_postconditions_section_is_tolerated(tmp_path):
    c = make_checker(tmp_path, "postconditions:\n")
    assert c.run_all() == []


# ------------------------------------------------------------------- check_http


def fake_client(monkeypatch, responses):
    """responses: list of status codes or Exceptions, consumed per .get call."""
    calls = {"n": 0, "timeouts": []}
    seq = list(responses)

    def client_factory(timeout=None):
        calls["timeouts"].append(timeout)
        client = MagicMock()

        def get(url):
            calls["n"] += 1
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return MagicMock(status_code=item)

        client.get.side_effect = get
        cm = MagicMock()
        cm.__enter__.return_value = client
        return cm

    monkeypatch.setattr(verify.httpx, "Client", client_factory)
    return calls


HTTP_SPEC = "postconditions:\n  health_check:\n    check: http_get\n    url: https://x.test/h\n"


def test_http_skip_without_url(tmp_path):
    c = make_checker(tmp_path, "postconditions:\n  health_check:\n    check: http_get\n")
    r = c.check_http()
    assert r.result == CheckResult.SKIP and r.name == "health_check"


def test_http_pass_details_and_default_timeout(tmp_path, monkeypatch):
    calls = fake_client(monkeypatch, [200])
    r = make_checker(tmp_path, HTTP_SPEC).check_http()
    assert r.result == CheckResult.PASS
    assert r.details == {"status_code": 200}
    assert "https://x.test/h" in r.message
    assert calls["timeouts"] == [30]


def test_http_custom_expect_and_timeout(tmp_path, monkeypatch):
    calls = fake_client(monkeypatch, [401])
    spec = HTTP_SPEC + "    expect: 401\n    timeout: 5\n"
    r = make_checker(tmp_path, spec).check_http()
    assert r.result == CheckResult.PASS
    assert calls["timeouts"] == [5]


def test_http_wrong_status_retries_with_backoff_then_fails(tmp_path, monkeypatch, no_sleep):
    calls = fake_client(monkeypatch, [503, 503, 503])
    r = make_checker(tmp_path, HTTP_SPEC).check_http()
    assert r.result == CheckResult.FAIL
    assert "Expected 200, got 503" in r.message
    assert r.details == {"status_code": 503, "url": "https://x.test/h"}
    assert calls["n"] == 3
    assert no_sleep == [1, 2]


def test_http_recovers_after_failure(tmp_path, monkeypatch):
    fake_client(monkeypatch, [500, 200])
    r = make_checker(tmp_path, HTTP_SPEC).check_http()
    assert r.result == CheckResult.PASS


def test_http_exception_then_success(tmp_path, monkeypatch):
    fake_client(monkeypatch, [OSError("boom"), 200])
    assert make_checker(tmp_path, HTTP_SPEC).check_http().result == CheckResult.PASS


def test_http_exception_every_attempt_fails_with_error_details(tmp_path, monkeypatch):
    calls = fake_client(monkeypatch, [OSError("down")] * 2)
    spec = HTTP_SPEC + "    retries: 2\n"
    r = make_checker(tmp_path, spec).check_http()
    assert r.result == CheckResult.FAIL
    assert r.message == "HTTP error: down"
    assert r.details == {"error": "down", "url": "https://x.test/h"}
    assert calls["n"] == 2


def test_http_zero_retries_never_calls_and_fails(tmp_path, monkeypatch):
    calls = fake_client(monkeypatch, [])
    r = make_checker(tmp_path, HTTP_SPEC + "    retries: 0\n").check_http()
    assert r.result == CheckResult.FAIL
    assert r.message == "Max retries exceeded"
    assert calls["n"] == 0


def test_http_single_retry_does_not_sleep(tmp_path, monkeypatch, no_sleep):
    fake_client(monkeypatch, [500])
    r = make_checker(tmp_path, HTTP_SPEC + "    retries: 1\n").check_http()
    assert r.result == CheckResult.FAIL
    assert no_sleep == []


# -------------------------------------------------------------------- check_ssl


def patch_tls(monkeypatch, cert=None, error=None):
    ssock = MagicMock()
    ssock.getpeercert.return_value = cert
    ssock.__enter__.return_value = ssock
    ctx = MagicMock()
    ctx.wrap_socket.return_value = ssock
    monkeypatch.setattr(verify.ssl, "create_default_context", lambda: ctx)

    def create_connection(addr, timeout=None):
        if error:
            raise error
        sock = MagicMock()
        sock.__enter__.return_value = sock
        return sock

    monkeypatch.setattr(verify.socket, "create_connection", create_connection)
    return ctx


def ssl_date(days):
    return (datetime.now(UTC) + timedelta(days=days)).strftime("%b %d %H:%M:%S %Y GMT")


SSL_SPEC = "postconditions:\n  ssl_valid:\n    check: ssl_verify\n    domain: x.test\n"


def test_ssl_skip_without_domain(tmp_path):
    c = make_checker(tmp_path, "postconditions:\n  ssl_valid:\n    check: ssl_verify\n")
    assert c.check_ssl().result == CheckResult.SKIP


def test_ssl_pass_reports_days_remaining(tmp_path, monkeypatch):
    ctx = patch_tls(monkeypatch, {"notAfter": ssl_date(60) })
    r = make_checker(tmp_path, SSL_SPEC).check_ssl()
    assert r.result == CheckResult.PASS
    assert r.details["domain"] == "x.test"
    assert 58 <= r.details["days_remaining"] <= 60
    ctx.wrap_socket.assert_called_once()
    assert ctx.wrap_socket.call_args.kwargs["server_hostname"] == "x.test"


def test_ssl_expiring_soon_fails_with_default_threshold(tmp_path, monkeypatch):
    patch_tls(monkeypatch, {"notAfter": ssl_date(5)})
    r = make_checker(tmp_path, SSL_SPEC).check_ssl()
    assert r.result == CheckResult.FAIL
    assert "threshold: 14" in r.message


def test_ssl_custom_min_days_allows_short_cert(tmp_path, monkeypatch):
    patch_tls(monkeypatch, {"notAfter": ssl_date(5)})
    r = make_checker(tmp_path, SSL_SPEC + "    min_days_remaining: 2\n").check_ssl()
    assert r.result == CheckResult.PASS


def test_ssl_expired_fails(tmp_path, monkeypatch):
    patch_tls(monkeypatch, {"notAfter": ssl_date(-3)})
    r = make_checker(tmp_path, SSL_SPEC).check_ssl()
    assert r.result == CheckResult.FAIL
    assert "EXPIRED" in r.message
    assert "expired" in r.details


def test_ssl_missing_cert_fails(tmp_path, monkeypatch):
    patch_tls(monkeypatch, None)
    r = make_checker(tmp_path, SSL_SPEC).check_ssl()
    assert r.result == CheckResult.FAIL
    assert "missing" in r.message


def test_ssl_cert_without_expiry_passes_with_issuer(tmp_path, monkeypatch):
    patch_tls(monkeypatch, {"issuer": [("O", "LE")]})
    r = make_checker(tmp_path, SSL_SPEC).check_ssl()
    assert r.result == CheckResult.PASS
    assert r.details == {"issuer": [("O", "LE")]}


def test_ssl_connection_error_fails(tmp_path, monkeypatch):
    patch_tls(monkeypatch, error=OSError("refused"))
    r = make_checker(tmp_path, SSL_SPEC).check_ssl()
    assert r.result == CheckResult.FAIL
    assert r.message == "SSL error: refused"
    assert r.details["domain"] == "x.test"


def test_ssl_unparseable_date_fails_not_raises(tmp_path, monkeypatch):
    patch_tls(monkeypatch, {"notAfter": "not a date"})
    assert make_checker(tmp_path, SSL_SPEC).check_ssl().result == CheckResult.FAIL


# ------------------------------------------------------------------- check_dns


DNS_SPEC = "postconditions:\n  dns_resolves:\n    check: dns_lookup\n    domain: x.test\n"


def test_dns_skip_without_domain(tmp_path):
    c = make_checker(tmp_path, "postconditions:\n  dns_resolves:\n    check: dns_lookup\n")
    assert c.check_dns().result == CheckResult.SKIP


def test_dns_pass_without_expected_ip(tmp_path, monkeypatch):
    monkeypatch.setattr(verify.socket, "gethostbyname", lambda d: "1.2.3.4")
    r = make_checker(tmp_path, DNS_SPEC).check_dns()
    assert r.result == CheckResult.PASS
    assert r.details == {"ip": "1.2.3.4"}


def test_dns_pass_when_ip_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(verify.socket, "gethostbyname", lambda d: "1.2.3.4")
    r = make_checker(tmp_path, DNS_SPEC + "    expect: 1.2.3.4\n").check_dns()
    assert r.result == CheckResult.PASS


def test_dns_mismatch_retries_then_fails(tmp_path, monkeypatch, no_sleep):
    n = []
    monkeypatch.setattr(verify.socket, "gethostbyname", lambda d: n.append(1) or "9.9.9.9")
    r = make_checker(tmp_path, DNS_SPEC + "    expect: 1.2.3.4\n").check_dns()
    assert r.result == CheckResult.FAIL
    assert r.details == {"expected": "1.2.3.4", "actual": "9.9.9.9"}
    assert len(n) == 5
    assert no_sleep == [1, 2, 4, 8]


def test_dns_propagates_after_initial_mismatch(tmp_path, monkeypatch):
    answers = iter(["9.9.9.9", "1.2.3.4"])
    monkeypatch.setattr(verify.socket, "gethostbyname", lambda d: next(answers))
    r = make_checker(tmp_path, DNS_SPEC + "    expect: 1.2.3.4\n").check_dns()
    assert r.result == CheckResult.PASS


def test_dns_error_every_attempt_fails(tmp_path, monkeypatch):
    def boom(d):
        raise OSError("nxdomain")

    monkeypatch.setattr(verify.socket, "gethostbyname", boom)
    r = make_checker(tmp_path, DNS_SPEC + "    retries: 2\n").check_dns()
    assert r.result == CheckResult.FAIL
    assert r.message == "DNS error: nxdomain"
    assert r.details["domain"] == "x.test"


def test_dns_zero_retries_max_exceeded(tmp_path):
    r = make_checker(tmp_path, DNS_SPEC + "    retries: 0\n").check_dns()
    assert r.result == CheckResult.FAIL and r.message == "Max retries exceeded"


# ------------------------------------------------------------ check_registrars


@pytest.fixture
def fake_audit(monkeypatch, tmp_path):
    """Replace fabrik.audit / fabrik.spec_loader and point FABRIK_ROOT at tmp_path."""
    monkeypatch.setattr(verify, "FABRIK_ROOT", tmp_path)
    (tmp_path / "specs" / "services").mkdir(parents=True)
    state = {"results": {}, "exc": None, "loaded": []}

    audit = types.ModuleType("fabrik.audit")

    def audit_all(spec):
        if state["exc"]:
            raise state["exc"]
        return state["results"]

    audit.audit_all = audit_all
    loader = types.ModuleType("fabrik.spec_loader")

    def load_spec(path):
        state["loaded"].append(path)
        return object()

    loader.load_spec = load_spec
    monkeypatch.setitem(sys.modules, "fabrik.audit", audit)
    monkeypatch.setitem(sys.modules, "fabrik.spec_loader", loader)
    return state


REG_SPEC = "postconditions:\n  registrars_present:\n    check: registrars_present\n"


def audit_result(status):
    return types.SimpleNamespace(status=status)


def test_registrars_fail_without_app_name(tmp_path, fake_audit):
    r = make_checker(tmp_path, REG_SPEC).check_registrars()
    assert r.result == CheckResult.FAIL and "APP_NAME" in r.message


def test_registrars_app_name_from_config_fallback(tmp_path, fake_audit):
    (tmp_path / "specs" / "services" / "demo.yaml").write_text("x: 1\n")
    fake_audit["results"] = {"db": audit_result("present")}
    c = make_checker(tmp_path, REG_SPEC + "    app_name: demo\n")
    assert c.check_registrars().result == CheckResult.PASS


def test_registrars_fail_when_spec_missing(tmp_path, fake_audit):
    r = make_checker(tmp_path, REG_SPEC, {"APP_NAME": "ghost"}).check_registrars()
    assert r.result == CheckResult.FAIL and "Spec not found" in r.message


def test_registrars_strips_fabrik_prefix(tmp_path, fake_audit):
    (tmp_path / "specs" / "services" / "demo.yaml").write_text("x: 1\n")
    fake_audit["results"] = {"db": audit_result("present")}
    r = make_checker(tmp_path, REG_SPEC, {"APP_NAME": "fabrik-demo"}).check_registrars()
    assert r.result == CheckResult.PASS
    assert fake_audit["loaded"][0].endswith("demo.yaml")


def test_registrars_missing_listed_sorted(tmp_path, fake_audit):
    (tmp_path / "specs" / "services" / "demo.yaml").write_text("x: 1\n")
    fake_audit["results"] = {
        "redis": audit_result("missing"),
        "db": audit_result("missing"),
        "gatus": audit_result("present"),
    }
    r = make_checker(tmp_path, REG_SPEC, {"APP_NAME": "demo"}).check_registrars()
    assert r.result == CheckResult.FAIL
    assert r.message == "Missing registrars: db, redis"


def test_registrars_unknown_and_na_do_not_fail(tmp_path, fake_audit):
    (tmp_path / "specs" / "services" / "demo.yaml").write_text("x: 1\n")
    fake_audit["results"] = {
        "a": audit_result("present"),
        "b": audit_result("unknown"),
        "c": audit_result("n/a"),
    }
    r = make_checker(tmp_path, REG_SPEC, {"APP_NAME": "demo"}).check_registrars()
    assert r.result == CheckResult.PASS
    assert r.message == "1 registrar(s) present, 2 n/a or unknown"


def test_registrars_audit_exception_is_a_failure(tmp_path, fake_audit):
    (tmp_path / "specs" / "services" / "demo.yaml").write_text("x: 1\n")
    fake_audit["exc"] = RuntimeError("kaput")
    r = make_checker(tmp_path, REG_SPEC, {"APP_NAME": "demo"}).check_registrars()
    assert r.result == CheckResult.FAIL and r.message == "Audit failed: kaput"


# ---------------------------------------------------- run_all / aggregation


def test_run_all_dispatches_each_check_type(tmp_path, monkeypatch):
    c = make_checker(
        tmp_path,
        "postconditions:\n"
        "  a: {check: http_get}\n  b: {check: ssl_verify}\n"
        "  c: {check: dns_lookup}\n  d: {check: registrars_present}\n",
    )
    for meth in ("check_http", "check_ssl", "check_dns", "check_registrars"):
        monkeypatch.setattr(c, meth, lambda name, m=meth: result_of(f"{m}:{name}", CheckResult.PASS))
    res = c.run_all()
    assert [r.name for r in res] == [
        "check_http:a",
        "check_ssl:b",
        "check_dns:c",
        "check_registrars:d",
    ]
    assert c.results is res


def test_run_all_unknown_check_type_warns(tmp_path, caplog):
    c = make_checker(tmp_path, "postconditions:\n  z: {check: telepathy}\n  y: {}\n")
    with caplog.at_level("WARNING", logger="fabrik.verify"):
        res = c.run_all()
    assert [r.result for r in res] == [CheckResult.WARN, CheckResult.WARN]
    assert res[0].message == "Unimplemented check: telepathy"
    assert "Unimplemented check type" in caplog.text


def test_run_all_resets_results(tmp_path):
    c = make_checker(tmp_path, "postconditions:\n  z: {check: telepathy}\n")
    c.run_all()
    c.run_all()
    assert len(c.results) == 1


def test_all_passed_false_when_no_results(tmp_path):
    c = make_checker(tmp_path, "a: 1\n")
    assert c.all_passed() is False


def test_all_passed_matrix(tmp_path):
    c = make_checker(tmp_path, "a: 1\n")
    P, F, S, W = CheckResult.PASS, CheckResult.FAIL, CheckResult.SKIP, CheckResult.WARN
    cases = [
        ([P], True),
        ([P, S, W], True),
        ([P, F], False),
        ([S], False),
        ([W], False),
        ([S, F], False),
    ]
    for results, expected in cases:
        c.results = [result_of(str(i), r) for i, r in enumerate(results)]
        assert c.all_passed() is expected, results


def test_get_failures_only_fail(tmp_path):
    c = make_checker(tmp_path, "a: 1\n")
    c.results = [
        result_of("p", CheckResult.PASS),
        result_of("f", CheckResult.FAIL),
        result_of("w", CheckResult.WARN),
    ]
    assert [r.name for r in c.get_failures()] == ["f"]


def test_should_rollback_matrix(tmp_path):
    fail = [result_of("f", CheckResult.FAIL)]
    ok = [result_of("p", CheckResult.PASS)]
    auto = make_checker(tmp_path, "rollback:\n  default: auto\n")
    auto.results = fail
    assert auto.should_rollback() is True
    auto.results = ok
    assert auto.should_rollback() is False

    manual = make_checker(tmp_path, "rollback:\n  default: manual\n")
    manual.results = fail
    assert manual.should_rollback() is False

    unset = make_checker(tmp_path, "a: 1\n")
    unset.results = fail
    assert unset.should_rollback() is True  # default is "auto"


def test_postcondition_result_details_default_not_shared():
    a = PostconditionResult("a", CheckResult.PASS, "m")
    b = PostconditionResult("b", CheckResult.PASS, "m")
    a.details["k"] = 1
    assert b.details == {}


def test_check_result_values():
    assert {c.value for c in CheckResult} == {"pass", "fail", "skip", "warn"}


# ---------------------------------------------------------------- get_spec_path


def test_get_spec_path_prefers_cwd(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    (cwd / "specs" / "verification").mkdir(parents=True)
    (cwd / "specs" / "verification" / "deploy.yaml").write_text("a: 1\n")
    root = tmp_path / "root"
    (root / "specs" / "verification").mkdir(parents=True)
    (root / "specs" / "verification" / "deploy.yaml").write_text("a: 1\n")
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("FABRIK_ROOT", str(root))
    assert get_spec_path("deploy") == cwd / "specs" / "verification" / "deploy.yaml"


def test_get_spec_path_uses_env_root_when_cwd_lacks_it(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    root = tmp_path / "root"
    (root / "specs" / "verification").mkdir(parents=True)
    (root / "specs" / "verification" / "deploy.yaml").write_text("a: 1\n")
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("FABRIK_ROOT", str(root))
    assert get_spec_path("deploy") == root / "specs" / "verification" / "deploy.yaml"


def test_get_spec_path_fallback_is_module_root_even_if_absent(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("FABRIK_ROOT", str(tmp_path / "none"))
    monkeypatch.setattr(verify, "FABRIK_ROOT", tmp_path / "modroot")
    p = get_spec_path("deploy")
    assert p == tmp_path / "modroot" / "specs" / "verification" / "deploy.yaml"
    assert not p.exists()


# ------------------------------------------------------ verify_postconditions


@pytest.fixture
def spec_env(tmp_path, monkeypatch):
    """cwd with specs/verification/deploy.yaml; returns a writer for its content."""
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "specs" / "verification"
    d.mkdir(parents=True)
    monkeypatch.setenv("VPS_IP", "10.0.0.9")

    def write(text):
        (d / "deploy.yaml").write_text(text)

    return write


FAILING = "postconditions:\n  z: {check: http_get}\n  y: {check: telepathy}\n"
PASSING = "postconditions:\n  y: {check: telepathy}\n"


def stub_checks(monkeypatch, outcome):
    seen = {}

    def run_all(self):
        seen["context"] = self.context
        self.results = [result_of("h", outcome)]
        return self.results

    monkeypatch.setattr(PostconditionChecker, "run_all", run_all)
    return seen


def test_decorator_returns_result_when_spec_missing(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FABRIK_ROOT", str(tmp_path / "none"))
    monkeypatch.setattr(verify, "FABRIK_ROOT", tmp_path / "none")

    @verify_postconditions("deploy")
    def deploy():
        return {"ok": True}

    with caplog.at_level("WARNING", logger="fabrik.verify"):
        assert deploy() == {"ok": True}
    assert "Verification spec not found" in caplog.text


def test_decorator_preserves_metadata_and_args(spec_env, monkeypatch):
    spec_env(PASSING)
    stub_checks(monkeypatch, CheckResult.PASS)

    @verify_postconditions()
    def deploy(a, b=0):
        """doc"""
        return a + b

    assert deploy.__name__ == "deploy" and deploy.__doc__ == "doc"
    assert deploy(1, b=2) == 3


def test_decorator_passes_context_from_dict_result(spec_env, monkeypatch):
    spec_env(PASSING)
    seen = stub_checks(monkeypatch, CheckResult.PASS)

    @verify_postconditions()
    def deploy():
        return {"domain": "d.test", "id": "svc"}

    deploy()
    assert seen["context"] == {"DOMAIN": "d.test", "APP_NAME": "svc", "TARGET_IP": "10.0.0.9"}


def test_decorator_app_name_prefers_app_name_key(spec_env, monkeypatch):
    spec_env(PASSING)
    seen = stub_checks(monkeypatch, CheckResult.PASS)

    @verify_postconditions()
    def deploy():
        return {"app_name": "named", "id": "other"}

    deploy()
    assert seen["context"]["APP_NAME"] == "named"
    assert seen["context"]["DOMAIN"] == ""


def test_decorator_empty_context_for_non_dict_result(spec_env, monkeypatch):
    spec_env(PASSING)
    seen = stub_checks(monkeypatch, CheckResult.PASS)

    @verify_postconditions()
    def deploy():
        return "string"

    assert deploy() == "string"
    assert seen["context"] == {}


def test_decorator_raises_on_failure_with_auto_rollback(spec_env, monkeypatch):
    spec_env("postconditions:\n  z: {check: http_get}\n")
    stub_checks(monkeypatch, CheckResult.FAIL)

    @verify_postconditions()
    def deploy():
        return {}

    with pytest.raises(RuntimeError, match="Postcondition failures"):
        deploy()


def test_decorator_failure_without_auto_rollback_returns_result(spec_env, monkeypatch, caplog):
    spec_env("postconditions:\n  z: {check: http_get}\n")
    stub_checks(monkeypatch, CheckResult.FAIL)

    @verify_postconditions(auto_rollback=False)
    def deploy():
        return {"v": 1}

    with caplog.at_level("ERROR", logger="fabrik.verify"):
        assert deploy() == {"v": 1}
    assert "Postcondition failures" in caplog.text


def test_decorator_manual_rollback_spec_does_not_raise(spec_env, monkeypatch):
    spec_env("rollback:\n  default: manual\npostconditions:\n  z: {check: http_get}\n")
    stub_checks(monkeypatch, CheckResult.FAIL)

    @verify_postconditions()
    def deploy():
        return 1

    assert deploy() == 1


def test_decorator_all_passing_returns_result(spec_env, monkeypatch):
    spec_env(PASSING)
    stub_checks(monkeypatch, CheckResult.PASS)

    @verify_postconditions()
    def deploy():
        return 7

    assert deploy() == 7


def test_decorator_does_not_raise_for_warn_only(spec_env):
    spec_env(PASSING)  # unimplemented -> WARN, no FAIL, so no rollback

    @verify_postconditions()
    def deploy():
        return "kept"

    assert deploy() == "kept"


def test_decorator_swallows_filenotfound_from_checker(spec_env, monkeypatch, caplog):
    spec_env(PASSING)

    def boom(self, *a, **k):
        raise FileNotFoundError("gone")

    monkeypatch.setattr(PostconditionChecker, "__init__", boom)

    @verify_postconditions()
    def deploy():
        return "ok"

    with caplog.at_level("WARNING", logger="fabrik.verify"):
        assert deploy() == "ok"
    assert "skipping" in caplog.text


def test_decorator_func_exception_propagates_before_verification(spec_env, monkeypatch):
    spec_env(PASSING)
    seen = stub_checks(monkeypatch, CheckResult.PASS)

    @verify_postconditions()
    def deploy():
        raise KeyError("x")

    with pytest.raises(KeyError):
        deploy()
    assert seen == {}
