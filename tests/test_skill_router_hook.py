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
        # /fabrik-deploy-checklist had NO stem at all, so its own trigger phrases routed nowhere —
        # found by the independent wiring pass fleet asked for (01M1HT8B89ZV6XWC1RD0G1YT95); their
        # self-check covered render, corpus, description length and NEXT, none of which look at the
        # router. It sits BEFORE deploy-verify and deploy-execution because it carries "deploy".
        ("author the deploy checklist", "deploy-checklist"),
        ("freeze the parity contract", "deploy-checklist"),
        ("what must prod contain", "deploy-checklist"),
        ("deploy kontrol listesini yaz", "deploy-checklist"),
        # the stem sits AFTER deploy-verify: placed before it, it STOLE this prompt (measured in
        # the review's pass-1 corpus walk — old verdict deploy-verify, new deploy-checklist).
        ("verify the deploy checklist", "deploy-verify"),
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
        "deploy-checklist",
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


# --- /fabrik-conformance-review: the stem must OUTRANK spec/plan/review -------


@pytest.mark.parametrize(
    "prompt",
    [
        "was everything we specced actually built?",
        "audit every spec and plan against the code",
        "run a portfolio conformance review",
        "did we actually build what the specs said",
        "spec'lediklerimiz gerçekten yapıldı mı",
        "spec ve planları kodla doğrula",
    ],
)
def test_conformance_prompts_route_to_conformance(prompt: str) -> None:
    """A conformance sweep asks 'was it BUILT', not 'write a spec' or 'review this
    code' — but it says 'spec', 'plan' and 'review' out loud, so the broad stems
    below it in KEYWORD_STEMS would swallow every one of these if the ordering
    ever changed. This test IS that ordering guarantee."""
    assert hook.first_regex_match(prompt) == "conformance"


@pytest.mark.parametrize(
    ("prompt", "stem"),
    [
        ("let's write a spec for the new API", "spec"),
        ("review this diff", "review"),
        ("make a plan for this feature", "plan"),
        ("catch this project up", "catchup"),
    ],
)
def test_conformance_stem_does_not_steal_its_neighbours(prompt: str, stem: str) -> None:
    """Placing a stem FIRST is the cheapest way to break every stem after it."""
    assert hook.first_regex_match(prompt) == stem


def test_conformance_stem_maps_to_the_installed_skill() -> None:
    """STEM_SKILLS and KEYWORD_STEMS are two hardcoded maps that must agree — a
    stem with no skill entry routes to nothing, silently."""
    assert hook.STEM_SKILLS["conformance"] == "fabrik-conformance-review"


# ── /fabrik-spec-review had no stem, so its own advertised triggers MIS-ROUTED ───────────────────
# Found auditing command 3 of 31 against docs/reference/command-evaluation-checklist.md item 6.
# The command declares TRIGGER — EN: "review/harden/converge this spec". The router resolved
# "review this spec" to the `review` stem -> fabrik-review, the CODE-DIFF reviewer, whose own SKIP
# clause says it is not for a spec. That is worse than routing nowhere: the operator types the
# command's advertised phrase and is pointed at a different gate. The other three EN triggers and
# every TR trigger resolved to nothing.


def test_review_this_spec_reaches_the_spec_reviewer_not_the_code_reviewer() -> None:
    assert hook.first_regex_match("review this spec") == "spec-review"
    assert hook.first_regex_match("harden this spec") == "spec-review"
    assert hook.first_regex_match("converge this spec") == "spec-review"
    assert hook.first_regex_match("is this spec solid") == "spec-review"


def test_the_turkish_spec_review_triggers_resolve_too() -> None:
    assert hook.first_regex_match("bu spec'i gözden geçir") == "spec-review"
    assert hook.first_regex_match("bu spec'i sağlamlaştır") == "spec-review"


def test_spec_review_does_not_swallow_the_producer_or_the_code_reviewer() -> None:
    """Precision matters more than recall here — the router's whole history is over-firing fixes.
    Adding a stem ABOVE `review` must not cannibalise its siblings."""
    assert hook.first_regex_match("let's write a spec for this") == "spec"
    assert hook.first_regex_match("draft a spec") == "spec"
    assert hook.first_regex_match("review this diff") == "review"
    assert hook.first_regex_match("code review") == "review"
    assert hook.first_regex_match("review the logs shows an OOM") != "spec-review"


def test_spec_review_stem_is_registered_and_ordered_before_review() -> None:
    assert hook.STEM_SKILLS["spec-review"] == "fabrik-spec-review"
    order = [st for _, st in hook.KEYWORD_STEMS]
    assert order.index("spec-review") < order.index("review"), "first match wins — must precede"
    assert order.index("spec-review") < order.index("spec"), "else 'spec' swallows it"


# ── two more advertised triggers routed INTO the command whose SKIP clause forbids them ──────────
# Measured 2026-08-28 by running all 71 advertised EN TRIGGER phrases through the live router:
# 21 resolved correctly, 45 resolved NOWHERE (safe), and these resolved to the WRONG gate. Both
# landed on `fabrik-review` — the command whose OWN description reads "SKIP: ... Traycer artifact
# convergence (→ /fabrik-workflow-review), rendered-UI review (→ /design-review)". Same shape as
# the spec-review mis-route above, and the same reason it matters: routing nowhere is safe, routing
# the operator's own advertised phrase to a gate that disclaims it is not.


def test_review_this_ui_reaches_design_review_not_the_code_reviewer() -> None:
    assert hook.first_regex_match("review this UI") == "design-review"
    assert hook.first_regex_match("review the UI changes") == "design-review"
    assert hook.first_regex_match("check the design and accessibility of this screen") == (
        "design-review"
    )


def test_a_traycer_artifact_review_reaches_workflow_review() -> None:
    assert hook.first_regex_match("review the epic or ticket breakdown") == "workflow-review"
    assert hook.first_regex_match("converge this workflow artifact") == "workflow-review"


def test_the_new_stems_do_not_cannibalise_the_code_reviewer() -> None:
    """The router's entire history is over-firing fixes: a stem added ABOVE `review` must leave
    every sibling phrase alone. `design-review`'s own SKIP sends non-UI code review back here."""
    assert hook.first_regex_match("review this diff") == "review"
    assert hook.first_regex_match("code review") == "review"
    assert hook.first_regex_match("is this PR safe to merge") != "design-review"
    assert hook.first_regex_match("review this spec") == "spec-review"
    assert hook.first_regex_match("review the deployment plan") != "design-review"
    # "design" as a verb about a SPEC is the producer's, not the rendered-UI gate's
    assert hook.first_regex_match("let's design and spec this out") != "design-review"


def test_both_new_stems_are_registered_and_ordered_before_review() -> None:
    assert hook.STEM_SKILLS["design-review"] == "design-review"
    assert hook.STEM_SKILLS["workflow-review"] == "fabrik-workflow-review"
    order = [st for _, st in hook.KEYWORD_STEMS]
    assert order.index("design-review") < order.index("review"), "first match wins"
    assert order.index("workflow-review") < order.index("review"), "first match wins"


def test_the_ui_contract_review_is_not_swallowed_by_the_rendered_ui_gate() -> None:
    """The first cut of the `design-review` stem above matched "review ... UI" and swallowed
    /fabrik-ui-design-review, which converges the FROZEN docs/ui-design.md — a different artifact
    from a rendered screen, and its own SKIP says so ("never a running app (→ /design-review)").
    Caught by re-measuring all 71 advertised triggers AFTER the fix, not by reading it."""
    assert hook.first_regex_match("review/harden this UI design contract") == "ui-design-review"
    assert hook.first_regex_match("is this ui-design.md ready") == "ui-design-review"
    # and the rendered-UI gate still wins for a rendered screen
    assert hook.first_regex_match("review this UI") == "design-review"
    assert hook.first_regex_match("check the design and accessibility of this screen") == (
        "design-review"
    )


def test_ui_design_review_is_registered_and_ordered_before_design_review() -> None:
    assert hook.STEM_SKILLS["ui-design-review"] == "fabrik-ui-design-review"
    order = [st for _, st in hook.KEYWORD_STEMS]
    assert order.index("ui-design-review") < order.index("design-review"), "first match wins"


# ── "fires bare-prose, no slash command needed" is a ROUTING CLAIM, and it must be true ─────────
# Five commands say it. Measured 2026-08-28: 10 of their 15 advertised phrases reached nothing, and
# /fabrik-rivals reached nothing on all three while having no stem at all. Item 6 of the command
# checklist draws the line exactly here — most TRIGGER clauses serve model-native matching only and
# that is defensible, but a description that PROMISES bare-prose routing it does not have is not.


def test_the_rivals_triggers_reach_the_rivals_command() -> None:
    assert hook.first_regex_match("who are our competitors") == "rivals"
    assert hook.first_regex_match("what do rivals do better") == "rivals"
    assert hook.first_regex_match("how do we beat X") == "rivals"


def test_the_turkish_rivals_triggers_resolve_too() -> None:
    assert hook.first_regex_match("rakiplerimiz kim") == "rivals"
    assert hook.first_regex_match("onları nasıl geçeriz") == "rivals"


def test_rivals_does_not_swallow_neighbouring_prompts() -> None:
    """Precision first, as everywhere in this router. `competitor` talk that is not a request for
    the dossier — and every unrelated 'beat'/'better' phrasing — must stay untouched."""
    assert hook.first_regex_match("this query is better now") != "rivals"
    assert hook.first_regex_match("beat the flaky test into submission") != "rivals"
    assert hook.first_regex_match("review this diff") == "review"
    assert hook.first_regex_match("let's write a spec for this") == "spec"


def test_rivals_stem_is_registered() -> None:
    assert hook.STEM_SKILLS["rivals"] == "fabrik-rivals"


# ── the TURKISH half: `gözden geçir` alone is not a code review ─────────────────────────────────
# The broad `review` stem carries a bare `\bg[öo]zden ge[çc]ir\w*` alternative, which fires on ANY
# Turkish review phrase regardless of its noun — stricter than the English side, which at least
# demands "review this/the/my". Measured 2026-08-28 across all 61 advertised TR phrases: SIX
# mis-routed. The EN pass missed them because the grader only read the `EN:` clause.


def test_turkish_review_phrases_reach_their_own_command() -> None:
    assert hook.first_regex_match("akış sözleşmesini gözden geçir") == "flows-review"
    assert hook.first_regex_match("bu planı gözden geçir") == "plan-review"
    assert hook.first_regex_match("bu planı sağlamlaştır") == "plan-review"
    assert hook.first_regex_match("tüm dokümanları gözden geçir") == "docs"
    assert hook.first_regex_match("bu UI tasarım sözleşmesini gözden geçir") == "ui-design-review"


def test_the_turkish_doc_converge_phrase_is_not_the_whole_tree_sweep() -> None:
    """`/fabrik-doc-converge` is ONE doc; `/fabrik-docs-review` is the tree sweep. Their own
    descriptions draw that line, and the TR phrase for the single-doc converge reached the sweep."""
    assert hook.first_regex_match("bu dokümanı koda göre güncelle") == "doc-converge"


def test_a_bare_turkish_review_verb_still_reaches_the_code_reviewer() -> None:
    """Precision guard: adding noun-qualified TR stems above `review` must not strand the bare
    verb, which is the code reviewer's own advertised Turkish trigger."""
    assert hook.first_regex_match("bu değişiklikleri gözden geçir") == "review"
    assert hook.first_regex_match("kodu incele") == "review"


def test_the_new_turkish_stems_are_registered() -> None:
    assert hook.STEM_SKILLS["flows-review"] == "fabrik-flows-review"
    assert hook.STEM_SKILLS["plan-review"] == "fabrik-plan-review"
    assert hook.STEM_SKILLS["doc-converge"] == "fabrik-doc-converge"
    order = [st for _, st in hook.KEYWORD_STEMS]
    for stem in ("flows-review", "plan-review", "doc-converge"):
        assert order.index(stem) < order.index("review"), f"{stem} must precede `review`"


def test_designing_screens_reaches_the_screen_contract_not_the_spec() -> None:
    """`/fabrik-ui-design`'s remaining mis-route. Distinct from the ambiguous "let's design the
    app", which /fabrik-spec also advertises and correctly wins (spec precedes screens) — "design
    the SCREENS" names ui-design's own noun, so it earns a stem instead of a phrase change."""
    assert hook.first_regex_match("bu ekranları/UI'ı tasarla") == "ui-design"
    assert hook.first_regex_match("design the screens for this") == "ui-design"
    assert hook.first_regex_match("lay out the screens") == "ui-design"


def test_the_screen_stem_does_not_swallow_the_spec_producer_or_the_ui_review() -> None:
    assert hook.first_regex_match("let's design the app") == "spec"
    assert hook.first_regex_match("bu UI tasarım sözleşmesini gözden geçir") == "ui-design-review"
    assert hook.STEM_SKILLS["ui-design"] == "fabrik-ui-design"
    order = [st for _, st in hook.KEYWORD_STEMS]
    assert order.index("ui-design-review") < order.index("ui-design"), "review twin first"
    assert order.index("ui-design") < order.index("spec"), "else `spec` swallows it"


# --- /fabrik-repo-review stem (audit cmd 25/31, 2026-08-29) -------------------------------
# Its advertised triggers ("audit the whole repo", "tüm repoyu denetle") reached NOTHING, and
# "full project code review" mis-routed to fabrik-review, whose own SKIP disclaims whole-repo
# sweeps. The stem requires a TOTALITY word + a codebase noun so module-scoped and diff-scoped
# review phrasing stays where it was.


def test_whole_repo_audit_phrases_reach_repo_review() -> None:
    assert hook.first_regex_match("audit the whole repo") == "repo-review"
    assert hook.first_regex_match("sweep the entire project for bugs") == "repo-review"
    assert hook.first_regex_match("full project code review") == "repo-review"
    assert hook.first_regex_match("do a full codebase audit") == "repo-review"
    assert hook.first_regex_match("tüm repoyu denetle") == "repo-review"
    assert hook.first_regex_match("projenin tamamını incele") == "repo-review"


def test_the_repo_review_stem_does_not_swallow_its_neighbours() -> None:
    """Precision guard: scoped review phrasing keeps its own targets, and a totality word
    attached to a PLAN noun is not a codebase sweep."""
    assert hook.first_regex_match("review this diff") == "review"
    assert hook.first_regex_match("code review") == "review"
    assert hook.first_regex_match("audit the auth module") is None
    assert hook.first_regex_match("review the deployment plan") == "deploy-plan-review"
    assert hook.first_regex_match("review this spec") == "spec-review"
    assert hook.first_regex_match("quick review of my changes") == "review-scoped"
    assert hook.first_regex_match("the whole project is slow") is None
    # pre-existing at HEAD (the plan-review stem is noun-tight); pinned so a change is loud:
    assert hook.first_regex_match("review the full project plan") == "review"


def test_the_repo_review_stem_is_registered_above_review() -> None:
    assert hook.STEM_SKILLS["repo-review"] == "fabrik-repo-review"
    order = [st for _, st in hook.KEYWORD_STEMS]
    assert order.index("repo-review") < order.index("review"), "first match wins"


# --- /fabrik-rules-review stem (audit cmd 26/31, 2026-08-29) ------------------------------
# All four advertised triggers reached nothing. The nouns are distinctive but an AUDIT-intent
# anchor is required: this box talks about editing .windsurf/rules constantly, and routing that
# chatter to a compliance gauntlet would be the wallpaper that kills the stem.


def test_rules_pack_compliance_phrases_reach_rules_review() -> None:
    assert hook.first_regex_match("check rules-pack compliance") == "rules-review"
    assert hook.first_regex_match("audit against the windsurf rule packs") == "rules-review"
    assert hook.first_regex_match("rules-pack compliance audit") == "rules-review"
    assert hook.first_regex_match("kural paketlerine uyumu denetle") == "rules-review"
    assert hook.first_regex_match("windsurf kurallarını kontrol et") == "rules-review"


def test_ordinary_windsurf_rules_chatter_does_not_route_to_the_gauntlet() -> None:
    assert hook.first_regex_match("edit the windsurf rules") is None
    assert hook.first_regex_match("update the windsurf rule for gpu workers") is None
    assert hook.first_regex_match("the windsurf rules check on line 5 is stale") is None
    assert hook.first_regex_match("sync the rule packs to the fleet") is None
    assert hook.first_regex_match("check the rules for markdown files") is None


def test_the_rules_review_stem_is_registered() -> None:
    assert hook.STEM_SKILLS["rules-review"] == "fabrik-rules-review"
    order = [st for _, st in hook.KEYWORD_STEMS]
    assert order.index("rules-review") < order.index("review"), "first match wins"


def test_the_inflected_turkish_workflow_artifact_phrase_routes(  # audit cmd 28/31
) -> None:
    """'bu workflow çıktısını sağlamlaştır' is an ADVERTISED trigger; the stem's TR noun
    required the bare nominative and the accusative suffix broke the boundary."""
    assert hook.first_regex_match("bu workflow çıktısını sağlamlaştır") == "workflow-review"
    assert hook.first_regex_match("the workflow failed on step 3") is None


def test_all_advertised_upstream_phrases_route(  # audit cmd 29/31
) -> None:
    """The description says 'fires bare-prose, no slash needed' — 4 of 5 advertised phrases
    (1 EN + 3 TR) reached nothing, which made that claim fiction."""
    assert hook.first_regex_match("file this upstream") == "upstream"
    assert hook.first_regex_match("apply the upstream proposal from transdoc") == "upstream"
    assert hook.first_regex_match("bunu üst akışa bildir") == "upstream"
    assert hook.first_regex_match("bu dosya fabrik'ten geliyor, düzeltemiyorum") == "upstream"
    assert hook.first_regex_match("projeden gelen öneriyi uygula") == "upstream"


def test_git_upstream_chatter_does_not_route() -> None:
    assert hook.first_regex_match("the upstream branch diverged") is None
    assert hook.first_regex_match("pull from upstream") is None
    assert hook.first_regex_match("merge upstream changes into master") is None
