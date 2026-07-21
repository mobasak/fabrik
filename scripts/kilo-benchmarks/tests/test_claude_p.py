"""Behavior Contract — claude_p single-shot shim. Mocked subprocess, NO real Claude call."""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import claude_p  # noqa: E402


def _proc(returncode=0, stdout="", stderr=""):
    m = mock.Mock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def test_captures_snake_case_usage():
    payload = json.dumps(
        {
            "result": "hello",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 76,
                "cache_read_input_tokens": 20215,
                "cache_creation_input_tokens": 25503,
            },
        }
    )
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, payload)):
        text, usage = claude_p.claude_p_call("claude-code/haiku", "hi")
    assert text == "hello"
    assert usage == {
        "input_tokens": 10,
        "output_tokens": 76,
        "cache_read_input_tokens": 20215,
        "cache_creation_input_tokens": 25503,
    }


def test_fail_closed_on_nonzero_exit():
    with mock.patch("claude_p.subprocess.run", return_value=_proc(1, "", "auth error")):
        with pytest.raises(RuntimeError, match="exited 1"):
            claude_p.claude_p_call("claude-code/opus", "hi")


def test_fail_closed_on_bad_json():
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, "not json")):
        with pytest.raises(RuntimeError, match="json parse failed"):
            claude_p.claude_p_call("claude-code/opus", "hi")


def test_aliases_cover_all_four():
    assert set(claude_p.ALIASES) == {
        "claude-code/opus",
        "claude-code/sonnet",
        "claude-code/haiku",
        "claude-code/fable",
    }
    assert claude_p.ALIASES["claude-code/opus"] == "claude-opus-4-8"


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        claude_p.claude_p_call("claude-code/ghost", "hi")


_OK_USAGE = {
    "input_tokens": 3,
    "output_tokens": 5,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
}


def test_parity_empty_system_omits_flag_and_prompt_rides_stdin():
    payload = json.dumps({"result": "x", "usage": _OK_USAGE})
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, payload)) as run:
        claude_p.claude_p_call("claude-code/haiku", "FULL METHODOLOGY + CODE", system="")
    cmd = run.call_args[0][0]
    assert "--system-prompt" not in cmd  # parity: methodology NOT split into a system prompt
    assert (
        run.call_args[1]["input"] == "FULL METHODOLOGY + CODE"
    )  # rides in the user prompt (stdin)


def test_nonempty_system_passes_flag():
    payload = json.dumps({"result": "x", "usage": _OK_USAGE})
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, payload)) as run:
        claude_p.claude_p_call("claude-code/haiku", "prompt", system="SYS")
    cmd = run.call_args[0][0]
    assert "--system-prompt" in cmd and "SYS" in cmd


def test_fail_closed_on_missing_usage():
    # valid json, exit 0, but NO usage block → must raise (else the run scores as free $0).
    payload = json.dumps({"result": "answer"})
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, payload)):
        with pytest.raises(RuntimeError, match="no/invalid usage block"):
            claude_p.claude_p_call("claude-code/opus", "hi")


def test_fail_closed_on_nondict_usage():
    # a non-object usage (e.g. a list) → RuntimeError, NOT an uncaught AttributeError.
    payload = json.dumps({"result": "answer", "usage": [1, 2]})
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, payload)):
        with pytest.raises(RuntimeError, match="no/invalid usage block"):
            claude_p.claude_p_call("claude-code/opus", "hi")


def test_fail_closed_on_empty_result_with_output_tokens():
    # a reasoning-only response: output_tokens > 0 but empty result text → no completion → raise
    # (parity with the OpenRouter `if not r.text` path; must NOT be scored 0 in coding).
    payload = json.dumps({"result": "   ", "usage": {"input_tokens": 5, "output_tokens": 40}})
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, payload)):
        with pytest.raises(RuntimeError, match="empty text"):
            claude_p.claude_p_call("claude-code/opus", "hi")


def test_fail_closed_on_zero_output():
    payload = json.dumps({"result": "", "usage": {"input_tokens": 9, "output_tokens": 0}})
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, payload)):
        with pytest.raises(RuntimeError, match="no usable completion"):
            claude_p.claude_p_call("claude-code/opus", "hi")


def test_fail_closed_on_is_error():
    payload = json.dumps(
        {"is_error": True, "subtype": "error_max_turns", "result": "x", "usage": _OK_USAGE}
    )
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, payload)):
        with pytest.raises(RuntimeError, match="is_error"):
            claude_p.claude_p_call("claude-code/opus", "hi")


def test_fail_closed_on_non_object_json():
    with mock.patch("claude_p.subprocess.run", return_value=_proc(0, "5")):
        with pytest.raises(RuntimeError, match="non-object json"):
            claude_p.claude_p_call("claude-code/opus", "hi")
