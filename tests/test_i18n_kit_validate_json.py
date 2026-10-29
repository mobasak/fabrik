"""templates/i18n-kit/scripts/validate_i18n.py reads the model's JSON out of a noisy reply.

The Level-3 critique asks for {"issues": [...]}, and each issue's `fix` is a UI string that can hold
ICU placeholders such as `{count}`, which puts a real reply three braces deep. The old one-level regex
returned the inner issue dict, so llm_critique found no "issues" key and reported zero issues
(fabrik-lib finding 01M478ZH; ported from fabrik-lib aff75aeb, D-401).
"""

import importlib.util
import json
import types
from pathlib import Path
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "i18n-kit"
    / "scripts"
    / "validate_i18n.py"
)


def _load() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("i18n_kit_validate_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_noisy_reply_with_placeholder_braces_keeps_the_issues_wrapper() -> None:
    m = _load()
    reply = (
        "Here is the result:\n"
        '{"issues": [{"key": "queue.delete_count", "type": "WRONG_MEANING", '
        '"problem": "bad", "fix": "Sil {count} öğe"}]}\nThanks!'
    )
    parsed = m.extract_json_from_text(reply)
    assert isinstance(parsed, dict) and "issues" in parsed
    assert parsed["issues"][0]["fix"] == "Sil {count} öğe"


def test_an_earlier_json_fragment_in_the_prose_does_not_win() -> None:
    m = _load()
    reply = 'I format counts like {"count": 1}.\n\n{"issues": [{"key": "k", "fix": "x {n}"}]}'
    assert m.extract_json_from_text(reply) == {"issues": [{"key": "k", "fix": "x {n}"}]}


def test_a_longer_echoed_input_object_does_not_beat_the_keyed_payload() -> None:
    m = _load()
    reply = (
        'Reviewing: {"en": "Delete the selected items from the queue now please", '
        '"tr": "Kuyruktan secili ogeleri simdi sil lutfen"}\n{"issues": [{"key": "k"}]}'
    )
    assert m.extract_json_from_text(reply, expected_keys=("issues", "errors")) == {
        "issues": [{"key": "k"}]
    }
    # without a hint the generic fallback takes the longest object
    assert "en" in m.extract_json_from_text(reply)


def test_clean_and_fenced_replies_still_parse_and_no_json_raises() -> None:
    m = _load()
    assert m.extract_json_from_text('{"issues": []}') == {"issues": []}
    assert m.extract_json_from_text('```json\n{"issues": []}\n```') == {"issues": []}
    with pytest.raises(ValueError):
        m.extract_json_from_text("no json here {at all")


def test_llm_critique_reports_the_issue_past_placeholders_and_an_echoed_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The consumer's entry point: the Kilo reply carries prose, an echoed sample and a `{count}` fix."""
    m = _load()
    (tmp_path / "en.json").write_text(
        json.dumps({"q": {"del": "Delete {count} items from the queue"}})
    )
    (tmp_path / "tr.json").write_text(json.dumps({"q": {"del": "Kuyruktan {count} oge sil"}}))
    reply = (
        'Reviewing: {"en": "Delete {count} items from the queue now please", "tr": "Kuyruktan {count} oge"}\n'
        '{"issues": [{"key": "q.del", "type": "GRAMMAR", "problem": "p", "fix": "Kuyruktan {count} öğe sil"}]}'
    )

    def fake_run_kilo(prompt: str, **kw: Any) -> dict[str, Any]:
        return {"result": reply, "cost": 0.0, "session_id": "s"}

    monkeypatch.setattr(m, "I18N_DIR", tmp_path)
    monkeypatch.setattr(m, "_find_kilo", lambda: "kilo")
    monkeypatch.setattr(m, "run_kilo", fake_run_kilo)
    issues, _session = m.llm_critique("tr")
    assert len(issues) == 1 and issues[0].startswith("GRAMMAR: q.del"), issues


@pytest.mark.parametrize("where", ["before", "after"])
def test_a_worked_example_beside_the_answer_is_ambiguous_and_raises(where: str) -> None:
    """No position rule tells an answer from a same-shaped example placed before or after it (a
    trailing `{"issues": []}` would read as PASS): two different keyed objects raise."""
    m = _load()
    example = '{"issues": []}'
    real = '{"issues": [{"key": "q.del", "fix": "y {count}"}]}'
    reply = (
        f"For example: {example}\nMy answer: {real}"
        if where == "before"
        else (f"My answer: {real}\nAn empty result looks like {example}")
    )
    with pytest.raises(ValueError, match="ambiguous"):
        m.extract_json_from_text(reply, expected_keys=("issues", "errors"))


def test_a_repeated_identical_answer_is_not_ambiguous() -> None:
    m = _load()
    real = '{"issues": [{"key": "q.del", "fix": "y"}]}'
    got = m.extract_json_from_text(f"{real}\nAgain: {real}", expected_keys=("issues",))
    assert got == {"issues": [{"key": "q.del", "fix": "y"}]}


def test_a_fenced_worked_example_beside_the_fenced_answer_raises() -> None:
    """The fence path follows the same rule: it no longer returns the first fenced block blindly."""
    m = _load()
    reply = (
        'For example:\n```json\n{"issues": [{"key": "EXAMPLE", "fix": "X"}]}\n```\n'
        'My answer:\n```json\n{"issues": [{"key": "q.del", "fix": "y {count}"}]}\n```'
    )
    with pytest.raises(ValueError, match="ambiguous"):
        m.extract_json_from_text(reply, expected_keys=("issues", "errors"))


def test_a_reply_nested_past_the_recursion_limit_raises_value_error() -> None:
    m = _load()
    deep = '{"a": ' * 12000 + "1"  # truncated, and deeper than the C decoder's recursion limit
    with pytest.raises(ValueError):
        m.extract_json_from_text("note: " + deep)


def _stub_kilo(
    m: types.ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reply: str
) -> None:
    monkeypatch.setattr(m, "I18N_DIR", tmp_path)
    monkeypatch.setattr(m, "_find_kilo", lambda: "kilo")
    monkeypatch.setattr(
        m, "run_kilo", lambda prompt, **kw: {"result": reply, "cost": 0.0, "session_id": "s"}
    )


def test_llm_critique_reports_an_error_when_the_reply_has_no_issues_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prose-wrapped bare list leaves one issue dict with no 'issues' key: an error, never zero issues."""
    m = _load()
    (tmp_path / "en.json").write_text(json.dumps({"q": {"del": "Delete {count} items"}}))
    (tmp_path / "tr.json").write_text(json.dumps({"q": {"del": "Kuyruktan {count} oge sil"}}))
    _stub_kilo(
        m, monkeypatch, tmp_path, 'Here: [{"key": "q.del", "type": "GRAMMAR", "fix": "f {count}"}]'
    )
    issues, _session = m.llm_critique("tr")
    assert len(issues) == 1 and issues[0].startswith("CRITIQUE_ERROR:"), issues


@pytest.mark.parametrize(
    ("reply", "expect_error"),
    [
        ('Sure: {"auth.login": "Sign in to your {count} accounts"}', False),
        (
            'The strings were: {"auth.login": "Hesabiniza {count} giris yapin lutfen simdi"}\n'
            '{"auth.login": "Sign in to your {count} accounts"}',
            True,
        ),
    ],
)
def test_back_translate_reads_its_answer_and_never_silently_takes_an_echo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reply: str, expect_error: bool
) -> None:
    """back_translate names the keys it asked for: a prose-wrapped answer reads clean, and an echoed
    input beside the answer is an error — before, the longer echo silently won and read as drift."""
    m = _load()
    (tmp_path / "en.json").write_text(
        json.dumps({"auth": {"login": "Sign in to your {count} accounts"}})
    )
    (tmp_path / "tr.json").write_text(
        json.dumps({"auth": {"login": "Hesabiniza {count} giris yapin lutfen simdi"}})
    )
    _stub_kilo(m, monkeypatch, tmp_path, reply)
    got = m.back_translate("tr")
    if expect_error:
        assert len(got) == 1 and got[0].startswith("BACK_TRANSLATE_ERROR: ambiguous"), got
    else:
        assert got == [], got


@pytest.mark.parametrize(
    "critique",
    [
        (["GRAMMAR: q.del\n  Problem: p\n  Fix: f"], "s"),
        (["CRITIQUE_ERROR: reply has no 'issues' or 'errors' key"], ""),
    ],
)
def test_validate_exits_one_on_a_level_three_issue_or_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, critique: tuple[list[str], str]
) -> None:
    """A Level-3 issue or error fails the run; before, both printed ALL CHECKS PASSED and exited 0."""
    m = _load()
    (tmp_path / "en.json").write_text(json.dumps({"q": {"del": "Delete"}}))
    (tmp_path / "tr.json").write_text(
        json.dumps({"_meta": {"completeness": 1.0}, "q": {"del": "Sil"}})
    )
    monkeypatch.setattr(m, "I18N_DIR", tmp_path)
    monkeypatch.setattr(m, "back_translate", lambda lang: [])
    monkeypatch.setattr(m, "llm_critique", lambda lang: critique)
    monkeypatch.setattr(m, "apply_critique_fixes", lambda lang, issues: 0)
    monkeypatch.setattr(m.sys, "argv", ["validate_i18n.py", "--validate", "tr"])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == 1


def test_validate_exits_one_on_a_level_two_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = _load()
    (tmp_path / "en.json").write_text(json.dumps({"q": {"del": "Delete"}}))
    (tmp_path / "tr.json").write_text(
        json.dumps({"_meta": {"completeness": 1.0}, "q": {"del": "Sil"}})
    )
    monkeypatch.setattr(m, "I18N_DIR", tmp_path)
    monkeypatch.setattr(m, "back_translate", lambda lang: ["DRIFT: q.del"])
    monkeypatch.setattr(m, "llm_critique", lambda lang: ([], "s"))
    monkeypatch.setattr(m.sys, "argv", ["validate_i18n.py", "--validate", "tr"])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == 1


def test_a_fragment_quoting_part_of_the_answer_is_not_a_competitor() -> None:
    m = _load()
    answer = '{"a.b": "Sign in", "a.c": "Log out"}'
    reply = f'About {{"a.b": "Sign in"}} - here is all of it: {answer}'
    got = m.extract_json_from_text(reply, expected_keys=("a.b", "a.c"))
    assert got == {"a.b": "Sign in", "a.c": "Log out"}


def test_an_incidental_keyed_object_with_other_content_stays_ambiguous() -> None:
    """By design: an object naming `errors` beside the `issues` answer is refused, never guessed."""
    m = _load()
    reply = 'Note {"errors": "see docs"}\n{"issues": [{"key": "q.del", "fix": "y"}]}'
    with pytest.raises(ValueError, match="ambiguous"):
        m.extract_json_from_text(reply, expected_keys=("issues", "errors"))


def test_an_unkeyed_fenced_block_does_not_hide_the_keyed_answer_in_prose() -> None:
    m = _load()
    reply = 'Input was:\n```json\n{"en": "Delete"}\n```\nAnswer: {"issues": [{"key": "q.del", "fix": "y"}]}'
    got = m.extract_json_from_text(reply, expected_keys=("issues", "errors"))
    assert got == {"issues": [{"key": "q.del", "fix": "y"}]}


def test_back_translate_reports_an_error_when_the_reply_carries_none_of_its_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A wrapper object with none of the asked-for keys is an error, never zero drift."""
    m = _load()
    (tmp_path / "en.json").write_text(json.dumps({"auth": {"login": "Sign in"}}))
    (tmp_path / "tr.json").write_text(json.dumps({"auth": {"login": "Giris yap"}}))
    _stub_kilo(m, monkeypatch, tmp_path, '{"translations": {"auth.login": "Sign in"}}')
    got = m.back_translate("tr")
    assert len(got) == 1 and got[0].startswith("BACK_TRANSLATE_ERROR:"), got


def test_validate_exits_one_on_a_drift_whose_text_quotes_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SKIP is the outcome's prefix, not a substring: a drift quoting 'SKIP:' still fails the run."""
    m = _load()
    (tmp_path / "en.json").write_text(json.dumps({"q": {"del": "Delete"}}))
    (tmp_path / "tr.json").write_text(
        json.dumps({"_meta": {"completeness": 1.0}, "q": {"del": "Sil"}})
    )
    monkeypatch.setattr(m, "I18N_DIR", tmp_path)
    monkeypatch.setattr(m, "back_translate", lambda lang: ["SEMANTIC_DRIFT: q.del 'SKIP: intro'"])
    monkeypatch.setattr(m, "llm_critique", lambda lang: ([], "s"))
    monkeypatch.setattr(m.sys, "argv", ["validate_i18n.py", "--validate", "tr"])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == 1


def test_validate_exits_one_on_a_level_three_finding_the_model_typed_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model names each issue's type: a finding typed SKIP is a finding, not the skip outcome."""
    m = _load()
    (tmp_path / "en.json").write_text(json.dumps({"q": {"del": "Delete"}}))
    (tmp_path / "tr.json").write_text(
        json.dumps({"_meta": {"completeness": 1.0}, "q": {"del": "Sil"}})
    )
    monkeypatch.setattr(m, "I18N_DIR", tmp_path)
    monkeypatch.setattr(m, "back_translate", lambda lang: [])
    monkeypatch.setattr(
        m, "llm_critique", lambda lang: (["SKIP: q.del\n  Problem: p\n  Fix: f"], "s")
    )
    monkeypatch.setattr(m, "apply_critique_fixes", lambda lang, issues: 0)
    monkeypatch.setattr(m.sys, "argv", ["validate_i18n.py", "--validate", "tr"])
    with pytest.raises(SystemExit) as exc:
        m.main()
    assert exc.value.code == 1
