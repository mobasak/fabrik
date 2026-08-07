"""Tests for the Claude Code UserPromptSubmit hook (.claude/hooks/skill_router.py).

Highest-risk paths (mirrors tests/test_final_gate_stop_hook.py's style):
- Tier 1 regex->stem->skill resolution is pure and unit-tested directly.
- Tier 2 (Haiku) is exercised with a STUBBED subprocess run — no real `claude` call.
- Exemptions (explicit `/command`, non-fabrik cwd) and fail-open (bad stdin, no
  matching skill) never block — the hook only ever injects or stays silent.
- A real-shape stdin replay proves the wiring end to end.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "skill_router.py"
_spec = importlib.util.spec_from_file_location("skill_router", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


# --- Tier 1: pure regex -> stem ------------------------------------------------


@pytest.mark.parametrize(
    "prompt,expected_stem",
    [
        ("let's write a design spec for this", "spec"),
        ("yeni bir özellik için tasarım yapalım", "spec"),
        ("make a plan for this feature", "plan"),
        ("bunun için bir planlama yapalım", "plan"),
        ("can you review this code", "review"),
        ("bu kodu incele", "review"),
        ("update the docs for this", "docs"),
        ("döküman güncelle", "docs"),  # both "döküman" and "güncelle" present — docs is checked first
        ("run the certification test suite", "test"),
        ("bunun için sertifika testi", "test"),
        ("time to release this", "release"),
        ("bunu yayınla", "release"),
        ("please deploy and verify the service", "deploy-verify"),
        ("dağıtım doğrula", "deploy-verify"),
        ("catch this project up", "catchup"),
        ("bu proje güncel mi", "catchup"),
        ("let's retire this old service", "retire"),
        ("bu servisi kaldır", "retire"),
    ],
)
def test_first_regex_match_bilingual(prompt: str, expected_stem: str) -> None:
    assert hook.first_regex_match(prompt) == expected_stem


def test_first_regex_match_no_keyword_returns_none() -> None:
    assert hook.first_regex_match("what's the weather like today") is None


def test_first_regex_match_docs_checked_before_catchup_on_overlap() -> None:
    # "güncelle" alone (no docs keyword) is unambiguous catchup.
    assert hook.first_regex_match("projeyi güncelle") == "catchup"
    # "döküman güncelle" contains BOTH a docs and a catchup keyword — docs wins
    # because it's earlier in KEYWORD_STEMS (list-order = priority).
    assert hook.first_regex_match("döküman güncelle") == "docs"


# --- F3 (round 2): bare-word precision — realistic NEGATIVE prompts must NOT
# inject. Reviewer's own table, verbatim. ------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        "fix this failing test in tests/…",
        "add a test for the new endpoint",
        "any idea why the import fails?",
        "the design of this function is wrong, refactor it",
        "review of the logs shows an OOM",
        "plan B: just restart the container",
        "add a docs link to the header",
        "publish the package to npm",
        # --- round-3 review N3: certification-intent test stem, not pytest verbs
        "run the tests and fix the failures",
        "let's run the unit tests before committing",
        "create a test for the new endpoint",
        "we need to test the retry path",
        "start a test container for postgres",
        # --- round-3 review N4: TR anchoring parity (object-anchored, not bare verb)
        "bu satırı kaldır",
        "bu importu kaldır",
        "logları incele",
        "belgeyi oku",
        "güncelleme var mı",
        # --- round-3 review N5: remaining EN FPs + TR asymmetry
        "the OpenAPI spec is out of date",
        "per the spec the field is required",
        "check the docs for the new endpoint",
        "the docs say this is deprecated",
        "catch the timeout error and clean up",
        # --- round-3 review N5: TR "fikir" dropped, same call as EN "idea"
        "bu konuda bir fikir yazalım",
        # --- round-4 fixup NEW-1: TR bare-stem anchoring parity (tasarım/
        # planla/döküman/yayın) — bare nouns/passive forms with zero
        # routing intent must stay silent.
        "veritabanı tasarımı yüzünden sorgu yavaş",
        "planlanan bakım penceresi ne zaman",
        "dökümanda yazan şey yanlış",
        "yeni yayın notlarını oku",
        # --- round-4 fixup NEW-2: dormant \bupstream\b anchor — bare mentions
        # of "upstream" (as an adjective/noun, or receiving FROM upstream)
        # must stay silent; only propose/file/send-upstream intent fires.
        "the upstream nginx returned a 502",
        "upstream API changed its response shape",
        # moved from the positive table (round-3) — "sync ... from upstream"
        # is RECEIVING from upstream, not proposing something TO it, so the
        # round-4 anchor (with its "from" lookahead) correctly silences it.
        "sync this file from upstream",
        # --- round-4 fixup NEW-2: dormant retire-family anchor — an object
        # OTHER than service/project/app/application (here: "endpoint",
        # "the need for...") must not fire; deprecating an endpoint or a
        # cache need is a code-level change, not a whole-service retirement.
        "we should deprecate that endpoint eventually",
        "this cache will sunset the need for the extra query",
        # --- round-4 fixup NEW-3: bare \be2e\b anchor — mentioning "e2e"
        # while just talking about authoring a test must stay silent; only
        # a run/do-e2e request fires.
        "we should add an e2e test for this later",
    ],
)
def test_first_regex_match_negative_prompts_no_injection(prompt: str) -> None:
    assert hook.first_regex_match(prompt) is None


# --- F5 (round 2): TR inflected forms — a trailing \b killed suffixed verbs.


@pytest.mark.parametrize(
    "prompt,expected_stem",
    [
        ("bu kodu inceleyelim", "review"),
        ("projeyi güncellemek istiyorum", "catchup"),
        ("planlamayı bitir", "plan"),
    ],
)
def test_first_regex_match_turkish_inflected_forms(prompt: str, expected_stem: str) -> None:
    assert hook.first_regex_match(prompt) == expected_stem


# --- N6 (round 3): recall regressions restored — imperative/object-anchored
# forms the round-2 precision pass had over-tightened away. ------------------


@pytest.mark.parametrize(
    "prompt,expected_stem",
    [
        ("plan the migration", "plan"),
        ("plan this feature out", "plan"),
        ("I'd like a review of the diff", "review"),
        ("adversarial review pass on this ticket", "review"),
        ("cut a release", "release"),
        ("ship it", "release"),
        ("documentation needs updating", "docs"),
        ("test this end to end", "test"),  # N3: certification-intent phrasing
    ],
)
def test_first_regex_match_recall_restored(prompt: str, expected_stem: str) -> None:
    assert hook.first_regex_match(prompt) == expected_stem


# --- round-4 fixup NEW-1: TR bare-stem anchors still fire on genuine intent ----


@pytest.mark.parametrize(
    "prompt,expected_stem",
    [
        ("bunu tasarlayalım", "spec"),
        ("hadi bunu planlayalım", "plan"),
        ("dökümanı güncelleyelim", "docs"),
        ("yayına alalım", "release"),
    ],
)
def test_first_regex_match_turkish_anchor_positives_round4(prompt: str, expected_stem: str) -> None:
    assert hook.first_regex_match(prompt) == expected_stem


# --- round-4 fixup NEW-2/NEW-3: dormant-stem + e2e anchors still fire on
# genuine intent (pre-armed ahead of fabrik-upstream/fabrik-decommission
# landing in the live roster). ------------------------------------------------


@pytest.mark.parametrize(
    "prompt,expected_stem",
    [
        ("propose this upstream", "upstream"),
        ("file upstream", "upstream"),
        ("upstream this fix", "upstream"),
        ("do an e2e run of the signup journey", "test"),
    ],
)
def test_first_regex_match_dormant_stem_anchor_positives_round4(prompt: str, expected_stem: str) -> None:
    assert hook.first_regex_match(prompt) == expected_stem


# --- Tier 1: stem -> target skill resolution -----------------------------------


def test_resolve_target_returns_skill_present_in_roster() -> None:
    roster = {"fabrik-review", "fabrik-spec"}
    assert hook.resolve_target("review", roster, project_type=None) == "fabrik-review"


def test_resolve_target_future_command_not_yet_built_returns_none() -> None:
    # deploy-verify's target isn't in the roster yet (sibling ticket hasn't landed)
    # -> silent, not a crash. This is the "future commands auto-enroll" contract.
    roster = {"fabrik-review", "fabrik-spec"}
    assert hook.resolve_target("deploy-verify", roster, project_type=None) is None


def test_resolve_target_unknown_stem_returns_none() -> None:
    assert hook.resolve_target("not-a-real-stem", {"fabrik-review"}, project_type=None) is None


def test_resolve_target_test_stem_headless_routes_service_test() -> None:
    roster = {"fabrik-user-test", "fabrik-service-test"}
    assert hook.resolve_target("test", roster, project_type="python-api") == "fabrik-service-test"


def test_resolve_target_test_stem_ui_bearing_routes_user_test() -> None:
    roster = {"fabrik-user-test", "fabrik-service-test"}
    assert hook.resolve_target("test", roster, project_type="saas-skeleton") == "fabrik-user-test"


def test_resolve_target_test_stem_present_but_unknown_type_defaults_user_test() -> None:
    # project.yaml EXISTS (default project_yaml_exists=True) but its type
    # is unrecognized/unset -> still the safe UI-bearing default.
    roster = {"fabrik-user-test", "fabrik-service-test"}
    assert hook.resolve_target("test", roster, project_type=None) == "fabrik-user-test"


def test_resolve_target_test_stem_missing_project_yaml_returns_none() -> None:
    # F3-residual (round 3): when project.yaml is ABSENT altogether (hub repo,
    # non-scaffolded dir) the "test" stem must NOT route at all — flipped
    # from the old (wrong) assumption that a missing project.yaml should
    # still default to fabrik-user-test.
    roster = {"fabrik-user-test", "fabrik-service-test"}
    assert (
        hook.resolve_target("test", roster, project_type=None, project_yaml_exists=False) is None
    )


def test_resolve_target_all_stem_skills_have_a_mapping() -> None:
    # Every ticket-listed category (except the dynamic "test") owns exactly one
    # stable stem->skill entry.
    for stem in (
        "spec",
        "plan",
        "review",
        "docs",
        "release",
        "deploy-verify",
        "catchup",
        "retire",
        "upstream",
    ):
        assert stem in hook.STEM_SKILLS


# --- injection shape -----------------------------------------------------------


def test_build_injection_nested_shape_and_directive_wording() -> None:
    payload = hook.build_injection("fabrik-review", "4-build")
    assert payload == {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                "This request matches /fabrik-review (Stage: 4-build) — invoke the "
                "skill, or state in one line why it does not apply."
            ),
        }
    }


def test_build_injection_never_emits_decision_or_reason() -> None:
    payload = hook.build_injection("fabrik-review", "4-build")
    assert "decision" not in payload
    assert "reason" not in payload


def test_build_injection_unknown_stage_label() -> None:
    payload = hook.build_injection("fabrik-spec", None)
    assert "(Stage: unknown)" in payload["hookSpecificOutput"]["additionalContext"]


# --- filesystem probes ----------------------------------------------------------


def test_skill_stage_parses_inline_sentence(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    d = skills / "fabrik-catchup"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        '---\nname: fabrik-catchup\ndescription: "Resume fast. Stage: utility. NEXT: whatever."\n---\n'
    )
    assert hook._skill_stage(skills, "fabrik-catchup") == "utility"


def test_skill_stage_parses_hyphenated_numeric_stage(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    d = skills / "fabrik-spec"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text('---\ndescription: "Turn an idea into a spec. Stage: 1-design."\n---\n')
    assert hook._skill_stage(skills, "fabrik-spec") == "1-design"


def test_skill_stage_missing_file_returns_none(tmp_path: Path) -> None:
    assert hook._skill_stage(tmp_path / "skills", "fabrik-nonexistent") is None


def test_roster_names_filters_fabrik_prefixed_with_skill_md(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    (skills / "fabrik-review").mkdir(parents=True)
    (skills / "fabrik-review" / "SKILL.md").write_text("---\n---\n")
    (skills / "fabrik-empty").mkdir(parents=True)  # no SKILL.md -> excluded
    (skills / "design-review").mkdir(parents=True)  # not fabrik-prefixed -> excluded
    (skills / "design-review" / "SKILL.md").write_text("---\n---\n")
    assert hook._roster_names(skills) == {"fabrik-review"}


def test_roster_names_missing_dir_returns_empty_set(tmp_path: Path) -> None:
    assert hook._roster_names(tmp_path / "nope") == set()


def test_project_type_parses_yaml_line(tmp_path: Path) -> None:
    (tmp_path / "project.yaml").write_text("name: demo\ntype: python-api\nother: x\n")
    assert hook._project_type(tmp_path) == "python-api"


def test_project_type_missing_file_returns_none(tmp_path: Path) -> None:
    assert hook._project_type(tmp_path) is None


# --- Tier 2: Haiku fallback, STUBBED Popen (no real `claude` call) -------------
#
# Round-3 review N1: the real implementation now spawns via
# ``Popen(start_new_session=True)`` + bounded ``communicate()`` (so a timeout
# can SIGKILL the whole process group), replacing ``subprocess.run(timeout=)``.
# The injectable seam is still a plain callable (``popen=``) — same DI shape,
# just returning a Popen-like stub instead of a completed-process-like stub.


class _StubPopen:
    """Popen-shaped stub: `.pid`, `.returncode`, `.communicate(timeout=)`.

    `raise_timeout_once=True` makes the FIRST `communicate()` call raise
    `subprocess.TimeoutExpired` (mirrors the real timeout path); the SECOND
    call (the post-kill reap) returns normally, matching the real cleanup
    call's contract.
    """

    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "",
        pid: int = 999999,
        raise_timeout_once: bool = False,
    ) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self.pid = pid
        self._raise_timeout_once = raise_timeout_once
        self._calls = 0

    def communicate(self, timeout=None):
        self._calls += 1
        if self._raise_timeout_once and self._calls == 1:
            raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)
        return (self._stdout, "")


def test_haiku_classify_returns_matched_roster_name() -> None:
    roster = [("fabrik-review", "4-build"), ("fabrik-spec", "1-design")]

    def stub_popen(*_a, **_k):
        return _StubPopen(returncode=0, stdout="fabrik-review\n")

    assert hook.haiku_classify("do a review please", roster, popen=stub_popen) == "fabrik-review"


def test_haiku_classify_none_response_returns_none() -> None:
    roster = [("fabrik-review", "4-build")]

    def stub_popen(*_a, **_k):
        return _StubPopen(returncode=0, stdout="NONE\n")

    assert hook.haiku_classify("random unrelated prompt", roster, popen=stub_popen) is None


def test_haiku_classify_off_roster_hallucination_returns_none() -> None:
    roster = [("fabrik-review", "4-build")]

    def stub_popen(*_a, **_k):
        return _StubPopen(returncode=0, stdout="fabrik-made-up-skill\n")

    assert hook.haiku_classify("something", roster, popen=stub_popen) is None


def test_haiku_classify_nonzero_returncode_returns_none() -> None:
    roster = [("fabrik-review", "4-build")]

    def stub_popen(*_a, **_k):
        return _StubPopen(returncode=1, stdout="fabrik-review\n")

    assert hook.haiku_classify("something", roster, popen=stub_popen) is None


def test_haiku_classify_timeout_fails_open() -> None:
    roster = [("fabrik-review", "4-build")]

    def stub_popen(*_a, **_k):
        return _StubPopen(raise_timeout_once=True)

    assert hook.haiku_classify("something", roster, popen=stub_popen) is None


def test_haiku_classify_missing_binary_fails_open() -> None:
    roster = [("fabrik-review", "4-build")]

    def stub_popen(*_a, **_k):
        raise FileNotFoundError("no such file: claude")

    assert hook.haiku_classify("something", roster, popen=stub_popen) is None


def test_haiku_classify_empty_roster_never_calls_run() -> None:
    called = {"n": 0}

    def stub_popen(*_a, **_k):
        called["n"] += 1
        return _StubPopen(returncode=0, stdout="NONE\n")

    assert hook.haiku_classify("something", [], popen=stub_popen) is None
    assert called["n"] == 0


def test_haiku_classify_uses_hard_timeout_cap() -> None:
    roster = [("fabrik-review", "4-build")]
    seen_kwargs = {}

    class _StubPopenCapturingTimeout(_StubPopen):
        def communicate(self, timeout=None):
            seen_kwargs["timeout"] = timeout
            return super().communicate(timeout=timeout)

    def stub_popen(*_a, **_k):
        return _StubPopenCapturingTimeout(returncode=0, stdout="fabrik-review\n")

    hook.haiku_classify("something", roster, popen=stub_popen)
    assert seen_kwargs.get("timeout") == hook.HAIKU_TIMEOUT == 8


def test_haiku_classify_child_is_isolated_from_project_cwd_and_stdin() -> None:
    # F1: the child must never inherit this project's cwd (would load THIS
    # project's .claude/settings.json and fire the nested SessionStart hook)
    # or read stdin (nothing to read, must never block on it). N1: it must
    # also run in its OWN process group (start_new_session=True) so a
    # timeout can kill the whole group, not just the immediate child.
    import subprocess as _subprocess
    import tempfile

    roster = [("fabrik-review", "4-build")]
    seen_kwargs = {}
    seen_argv = []

    def stub_popen(argv, **kwargs):
        seen_argv.extend(argv)
        seen_kwargs.update(kwargs)
        return _StubPopen(returncode=0, stdout="fabrik-review\n")

    hook.haiku_classify("something", roster, popen=stub_popen)
    assert seen_kwargs.get("cwd") == tempfile.gettempdir()
    assert seen_kwargs.get("stdin") == _subprocess.DEVNULL
    assert seen_kwargs.get("start_new_session") is True
    # isolation flags actually present on the child's argv
    assert "--setting-sources" in seen_argv
    assert "--strict-mcp-config" in seen_argv
    assert "--tools" in seen_argv
    assert "--no-session-persistence" in seen_argv
    assert "--bare" not in seen_argv


def test_haiku_classify_timeout_kills_process_group(monkeypatch: pytest.MonkeyPatch) -> None:
    # N1: on a communicate() timeout, the real implementation SIGKILLs the
    # whole process group via os.killpg(os.getpgid(pid), SIGKILL), then
    # reaps with a second bounded communicate(timeout=2).
    roster = [("fabrik-review", "4-build")]
    calls: dict[str, object] = {}

    def fake_getpgid(pid):
        calls["getpgid_pid"] = pid
        return 4242

    def fake_killpg(pgid, sig):
        calls["killpg"] = (pgid, sig)

    monkeypatch.setattr(hook.os, "getpgid", fake_getpgid)
    monkeypatch.setattr(hook.os, "killpg", fake_killpg)

    def stub_popen(*_a, **_k):
        return _StubPopen(pid=1234, raise_timeout_once=True)

    result = hook.haiku_classify("something", roster, popen=stub_popen)
    assert result is None
    assert calls["getpgid_pid"] == 1234
    assert calls["killpg"] == (4242, hook.signal.SIGKILL)


def test_haiku_classify_timeout_killpg_failure_is_guarded() -> None:
    # A stub pid that doesn't correspond to a real process — os.getpgid/
    # os.killpg raising (ProcessLookupError et al) must never propagate out
    # of haiku_classify; it must still fail open (return None).
    roster = [("fabrik-review", "4-build")]

    def stub_popen(*_a, **_k):
        return _StubPopen(pid=999999999, raise_timeout_once=True)

    assert hook.haiku_classify("something", roster, popen=stub_popen) is None


# --- integration: real subprocess, controlled HOME + PATH ----------------------


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    p = tmp_path / "proj"
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "final_gate.py").write_text("# stub\n")
    return p


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    return home


def _write_skill(home: Path, name: str, stage: str = "4-build") -> None:
    d = home / ".claude" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f'---\nname: {name}\ndescription: "does things. Stage: {stage}."\n---\n')


# F4-residual (round 3): the safe default PATH base for `_run_router` — a
# curated set of standard system dirs, NOT the inherited (real) PATH. Verified
# live on this box: the real `claude` CLI lives in ~/.local/bin and
# /usr/local/bin, never in any of these — but they still hold `/usr/bin/env`
# and `python3`, so a fake-`claude`-stub's `#!/usr/bin/env python3` shebang
# (used by `_write_fake_claude` / the inline sentinel scripts below) still
# resolves. A test that forgets to pass `extra_path` for a `claude` stub now
# fails CLOSED (FileNotFoundError inside the hook -> silent, per its own
# fail-open contract) instead of silently shelling out to whatever real
# `claude` binary happens to be on this box's PATH (the exact bug F4, round
# 2, caught and fixed for one test — this makes it structurally impossible
# for any future test to reintroduce it).
_SAFE_SYSTEM_PATH_DIRS = [d for d in ("/usr/bin", "/bin", "/usr/sbin", "/sbin") if os.path.isdir(d)]


def _run_router(
    project: Path,
    home: Path,
    payload: dict,
    *,
    extra_path: Path | None = None,
    extra_env: dict[str, str | None] | None = None,
) -> str:
    path_parts = ([str(extra_path)] if extra_path is not None else []) + _SAFE_SYSTEM_PATH_DIRS
    env = {**os.environ, "HOME": str(home), "PATH": os.pathsep.join(path_parts)}
    if extra_env:
        for key, value in extra_env.items():
            if value is None:
                env.pop(key, None)  # force-absent, regardless of the host's own environment
            else:
                env[key] = value
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 0, f"hook must always exit 0, got {proc.returncode}: {proc.stderr}"
    return proc.stdout.strip()


def test_explicit_slash_command_stays_silent(fake_project: Path, fake_home: Path) -> None:
    _write_skill(fake_home, "fabrik-review")
    out = _run_router(fake_project, fake_home, {"cwd": str(fake_project), "prompt": "/fabrik-review"})
    assert out == ""


def test_non_fabrik_cwd_stays_silent(tmp_path: Path, fake_home: Path) -> None:
    not_a_project = tmp_path / "not-fabrik"
    not_a_project.mkdir()
    _write_skill(fake_home, "fabrik-review")
    out = _run_router(not_a_project, fake_home, {"cwd": str(not_a_project), "prompt": "please review this"})
    assert out == ""


def test_empty_roster_stays_silent(fake_project: Path, fake_home: Path) -> None:
    out = _run_router(fake_project, fake_home, {"cwd": str(fake_project), "prompt": "please review this"})
    assert out == ""


def test_regex_match_injects_directive(fake_project: Path, fake_home: Path) -> None:
    _write_skill(fake_home, "fabrik-review", stage="4-build")
    out = _run_router(fake_project, fake_home, {"cwd": str(fake_project), "prompt": "can you review this diff"})
    assert out
    payload = json.loads(out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "/fabrik-review" in ctx and "Stage: 4-build" in ctx
    assert "decision" not in payload


def test_turkish_regex_match_injects_directive(fake_project: Path, fake_home: Path) -> None:
    _write_skill(fake_home, "fabrik-review", stage="4-build")
    out = _run_router(fake_project, fake_home, {"cwd": str(fake_project), "prompt": "bu kodu incele lütfen"})
    assert out
    payload = json.loads(out)
    assert "/fabrik-review" in payload["hookSpecificOutput"]["additionalContext"]


def test_test_stem_stays_silent_without_project_yaml(fake_project: Path, fake_home: Path) -> None:
    # F3-residual (round 3), end to end: fake_project (fixture) never writes a
    # project.yaml — the hub repo / non-scaffolded-dir case. A certification
    # prompt must NOT route to fabrik-user-test just because the default
    # "unknown type" behavior used to apply to a missing file too.
    _write_skill(fake_home, "fabrik-user-test", stage="5-certify")
    out = _run_router(fake_project, fake_home, {"cwd": str(fake_project), "prompt": "certify this end to end"})
    assert out == ""


def test_test_stem_routes_when_project_yaml_present_with_unknown_type(
    fake_project: Path, fake_home: Path
) -> None:
    # Present-but-unknown project type keeps the UI-bearing default.
    (fake_project / "project.yaml").write_text("name: demo\ntype: some-future-type\n")
    _write_skill(fake_home, "fabrik-user-test", stage="5-certify")
    out = _run_router(fake_project, fake_home, {"cwd": str(fake_project), "prompt": "certify this end to end"})
    assert out
    payload = json.loads(out)
    assert "/fabrik-user-test" in payload["hookSpecificOutput"]["additionalContext"]


def test_upstream_stem_autoenrolls_on_future_roster_positive(fake_project: Path, fake_home: Path) -> None:
    # round-4 fixup NEW-2, "both directions": a FAKE roster with
    # fabrik-upstream present (the auto-enrollment scenario — the skill
    # hasn't landed live yet, but the anchor is armed) fires on genuine
    # propose/file/send-upstream intent.
    _write_skill(fake_home, "fabrik-upstream", stage="utility")
    out = _run_router(fake_project, fake_home, {"cwd": str(fake_project), "prompt": "let's propose this upstream"})
    assert out
    payload = json.loads(out)
    assert "/fabrik-upstream" in payload["hookSpecificOutput"]["additionalContext"]


def test_upstream_stem_autoenrolls_on_future_roster_negative(fake_project: Path, fake_home: Path) -> None:
    # Same FAKE roster, but a bare/receiving mention of "upstream" must stay
    # silent even though the target skill now exists.
    _write_skill(fake_home, "fabrik-upstream", stage="utility")
    out = _run_router(
        fake_project, fake_home, {"cwd": str(fake_project), "prompt": "the upstream nginx returned a 502"}
    )
    assert out == ""


def test_retire_stem_autoenrolls_on_future_roster_positive(fake_project: Path, fake_home: Path) -> None:
    # round-4 fixup NEW-2, "both directions": a FAKE roster with
    # fabrik-decommission present fires on genuine service-retirement intent.
    _write_skill(fake_home, "fabrik-decommission", stage="utility")
    out = _run_router(
        fake_project, fake_home, {"cwd": str(fake_project), "prompt": "let's retire this old service"}
    )
    assert out
    payload = json.loads(out)
    assert "/fabrik-decommission" in payload["hookSpecificOutput"]["additionalContext"]


def test_retire_stem_autoenrolls_on_future_roster_negative(fake_project: Path, fake_home: Path) -> None:
    # Same FAKE roster, but a non-service object (endpoint) must stay silent
    # even though the target skill now exists.
    _write_skill(fake_home, "fabrik-decommission", stage="utility")
    out = _run_router(
        fake_project,
        fake_home,
        {"cwd": str(fake_project), "prompt": "we should deprecate that endpoint eventually"},
    )
    assert out == ""


def test_regex_hit_with_unresolved_target_stays_silent_without_tier2(
    fake_project: Path, fake_home: Path, tmp_path: Path
) -> None:
    # roster has fabrik-review only; deploy-verify keyword hits but target skill
    # isn't built yet. F2: this is a Tier-1 miss-WITH-a-name, so it must stay
    # silent WITHOUT ever calling Tier 2. F4: the old version of this test had
    # no extra_path, so PATH was inherited and it shelled out to the REAL
    # `claude` binary on the box — prove the fix with a `claude` stub that
    # writes a sentinel and exits 1: if Tier 2 fired at all, the sentinel
    # would exist (and previously, without extra_path, it would have hit the
    # network). Round 3: FABRIK_ROUTER_HAIKU=1 is set here DELIBERATELY —
    # without it, the opt-in gate alone would keep this green even if the F2
    # short-circuit itself regressed, which would defeat the point of the
    # test.
    _write_skill(fake_home, "fabrik-review")
    bin_dir = tmp_path / "bin"
    sentinel = tmp_path / "haiku_was_called.sentinel"
    bin_dir.mkdir(parents=True)
    script = bin_dir / "claude"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(sentinel)!r}).write_text('called')\n"
        "sys.exit(1)\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    out = _run_router(
        fake_project,
        fake_home,
        {"cwd": str(fake_project), "prompt": "please deploy and verify this"},
        extra_path=bin_dir,
        extra_env={"FABRIK_ROUTER_HAIKU": "1"},
    )
    assert out == ""
    assert not sentinel.exists(), "a regex hit with an unresolved target must never call Tier 2"


def test_malformed_stdin_fails_open(fake_project: Path, fake_home: Path) -> None:
    _write_skill(fake_home, "fabrik-review")
    env = {**os.environ, "HOME": str(fake_home)}
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="{not valid json",
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_missing_prompt_field_fails_open(fake_project: Path, fake_home: Path) -> None:
    _write_skill(fake_home, "fabrik-review")
    out = _run_router(fake_project, fake_home, {"cwd": str(fake_project)})
    assert out == ""


def test_real_shape_stdin_replay(fake_project: Path, fake_home: Path) -> None:
    # The documented UserPromptSubmit input envelope (verified live against
    # https://code.claude.com/docs/en/hooks, 2026-08-07): session_id, prompt_id,
    # transcript_path, cwd, permission_mode, hook_event_name, prompt.
    _write_skill(fake_home, "fabrik-spec", stage="1-design")
    payload = {
        "session_id": "abc123",
        "prompt_id": "550e8400-e29b-41d4-a716-446655440000",
        "transcript_path": str(fake_project / "transcript.jsonl"),
        "cwd": str(fake_project),
        "permission_mode": "default",
        "hook_event_name": "UserPromptSubmit",
        "prompt": "let's write a design spec for the new billing feature",
    }
    out = _run_router(fake_project, fake_home, payload)
    assert out
    got = json.loads(out)
    assert got["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "/fabrik-spec" in got["hookSpecificOutput"]["additionalContext"]
    assert "Stage: 1-design" in got["hookSpecificOutput"]["additionalContext"]


def _write_fake_claude(bin_dir: Path, response: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "claude"
    script.write_text(f"#!/usr/bin/env python3\nimport sys\nprint({response!r})\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_haiku_tier_fires_only_on_regex_miss_and_injects(fake_project: Path, fake_home: Path, tmp_path: Path) -> None:
    # Round-3 dispatcher ruling: Tier 2 is opt-in — must set FABRIK_ROUTER_HAIKU=1.
    _write_skill(fake_home, "fabrik-catchup", stage="utility")
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, "fabrik-catchup")
    out = _run_router(
        fake_project,
        fake_home,
        {"cwd": str(fake_project), "prompt": "hey what's the state of this repo overall"},
        extra_path=bin_dir,
        extra_env={"FABRIK_ROUTER_HAIKU": "1"},
    )
    assert out
    payload = json.loads(out)
    assert "/fabrik-catchup" in payload["hookSpecificOutput"]["additionalContext"]


def test_tier2_disabled_by_default_regex_miss_never_spawns_subprocess(
    fake_project: Path, fake_home: Path, tmp_path: Path
) -> None:
    # Round-3 dispatcher ruling: WITHOUT FABRIK_ROUTER_HAIKU set, a Tier-1
    # miss must stay silent and never even attempt to spawn `claude` — proved
    # with a sentinel-writing `claude` stub, same technique as F4/F7.
    _write_skill(fake_home, "fabrik-catchup", stage="utility")
    bin_dir = tmp_path / "bin"
    sentinel = tmp_path / "haiku_was_called.sentinel"
    bin_dir.mkdir(parents=True)
    script = bin_dir / "claude"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(sentinel)!r}).write_text('called')\n"
        "print('fabrik-catchup')\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    out = _run_router(
        fake_project,
        fake_home,
        {"cwd": str(fake_project), "prompt": "hey what's the state of this repo overall"},
        extra_path=bin_dir,
        extra_env={"FABRIK_ROUTER_HAIKU": None},  # force-absent, regardless of the host's own env
    )
    assert out == ""
    assert not sentinel.exists(), "Tier 2 must never spawn a subprocess when FABRIK_ROUTER_HAIKU is unset"


def test_haiku_tier_roster_excludes_pipeline_only_skills(
    fake_project: Path, fake_home: Path, tmp_path: Path
) -> None:
    # F6: Tier 2 must only ever be OFFERED (and accept) the curated router-eligible
    # roster (STEM_SKILLS values + the two test skills) — a pipeline-only skill like
    # fabrik-execute-plan is in the live roster (agents may invoke it directly) but
    # was never meant to be prompt-auto-triggered. A fake `claude` that "hallucinates"
    # exactly that name must still be rejected (fails open, stays silent) even though
    # the name is present in the live roster directory.
    _write_skill(fake_home, "fabrik-review", stage="4-build")
    _write_skill(fake_home, "fabrik-execute-plan", stage="4-build")
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, "fabrik-execute-plan")
    out = _run_router(
        fake_project,
        fake_home,
        {"cwd": str(fake_project), "prompt": "totally unrelated prompt with no keywords"},
        extra_path=bin_dir,
        extra_env={"FABRIK_ROUTER_HAIKU": "1"},
    )
    assert out == ""


def test_haiku_tier_none_response_stays_silent(fake_project: Path, fake_home: Path, tmp_path: Path) -> None:
    _write_skill(fake_home, "fabrik-catchup", stage="utility")
    bin_dir = tmp_path / "bin"
    _write_fake_claude(bin_dir, "NONE")
    out = _run_router(
        fake_project,
        fake_home,
        {"cwd": str(fake_project), "prompt": "totally unrelated prompt with no keywords"},
        extra_path=bin_dir,
        extra_env={"FABRIK_ROUTER_HAIKU": "1"},
    )
    assert out == ""


def test_regex_hit_never_shells_out_to_haiku(fake_project: Path, fake_home: Path, tmp_path: Path) -> None:
    # A fake `claude` that always errors would fail the test if Tier 2 fired —
    # proves the regex tier short-circuits Tier 2 on a hit. F7: also write a
    # sentinel file so this can't pass by accident (e.g. a revert that still
    # happens to leave the injected payload looking correct) — assert the
    # sentinel directly, not just the output.
    _write_skill(fake_home, "fabrik-review", stage="4-build")
    bin_dir = tmp_path / "bin"
    sentinel = tmp_path / "haiku_was_called.sentinel"
    bin_dir.mkdir(parents=True)
    script = bin_dir / "claude"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(sentinel)!r}).write_text('called')\n"
        "sys.exit(1)\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    out = _run_router(
        fake_project,
        fake_home,
        {"cwd": str(fake_project), "prompt": "review this"},
        extra_path=bin_dir,
        extra_env={"FABRIK_ROUTER_HAIKU": "1"},  # opt-in ON — proves the Tier-1 short-circuit, not the gate
    )
    assert not sentinel.exists(), "Tier 2 (Haiku) must never fire on a resolved Tier-1 regex hit"
    payload = json.loads(out)
    assert "/fabrik-review" in payload["hookSpecificOutput"]["additionalContext"]


def test_hook_never_exits_nonzero_even_on_internal_error(fake_project: Path, fake_home: Path) -> None:
    # cwd that doesn't even exist as a Path -> resolve() still succeeds on most
    # platforms, but final_gate.py check will just be False -> silent, exit 0.
    env = {**os.environ, "HOME": str(fake_home)}
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps({"cwd": "/definitely/not/a/real/path", "prompt": "review this"}),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_wordpress_type_never_test_routed() -> None:
    """wordpress is deploy-only — the `test` stem must not route it to any gauntlet
    (the code comment promised this; this test pins it)."""
    roster = {"fabrik-user-test", "fabrik-service-test"}
    assert hook.resolve_target("test", roster, "wordpress", True) is None
