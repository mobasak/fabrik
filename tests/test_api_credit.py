"""api_credit.py — spend the three prepaid API credits through capped, read-only `claude -p --bare` runs (D-1196,
W-894f994f). Each test is one Behaviour of the phase-2 design. The subject runs as a subprocess against a fake `claude`
on PATH that records its argv, env and stdin and prints a configured result, so nothing here reaches a provider."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "api_credit.py"

KEYS = {
    "can": "sk-ant-api03-" + "C" * 40 + "can0",
    "sarp": "sk-ant-api03-" + "S" * 40 + "sarp",
    "ozgurbasak": "sk-ant-api03-" + "O" * 40 + "ozgb",
}
ENV_NAME = {
    "can": "ANTHROPIC_API_KEY_CAN",
    "sarp": "ANTHROPIC_API_KEY_SARP",
    "ozgurbasak": "ANTHROPIC_API_KEY_OZGURBASAK",
}

FAKE_CLAUDE = """#!{python}
import json, os, sys
log = os.environ["FAKE_LOG"]
with open(log, "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "env": dict(os.environ), "stdin": sys.stdin.read()}}) + "\\n")
reply = open(os.environ["FAKE_REPLY"], encoding="utf-8").read()
reply = reply.replace("@KEY@", os.environ.get("ANTHROPIC_API_KEY", ""))
sys.stdout.write(reply)
sys.exit(int(os.environ.get("FAKE_RC", "0")))
"""


@pytest.fixture()
def box(tmp_path: Path) -> dict:
    state = tmp_path / "state"
    state.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(FAKE_CLAUDE.format(python=sys.executable), encoding="utf-8")
    fake.chmod(0o755)
    env_file = tmp_path / "dot.env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=\n" + "".join(f'{ENV_NAME[k]}="{v}"\n' for k, v in KEYS.items()),
        encoding="utf-8",
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Say ok.", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "ROTATE_STATE_DIR": str(state),
        "API_CREDIT_ENV_FILE": str(env_file),
        "FAKE_LOG": str(tmp_path / "fake.log"),
        "FAKE_REPLY": str(tmp_path / "reply.json"),
    }
    env.pop("FAKE_RC", None)
    return {
        "tmp": tmp_path,
        "state": state,
        "env": env,
        "prompt": prompt,
        "ledger": state / "api-credit.jsonl",
    }


def _reply(box: dict, obj: object | str, rc: int = 0) -> None:
    text = obj if isinstance(obj, str) else json.dumps(obj)
    Path(box["env"]["FAKE_REPLY"]).write_text(text, encoding="utf-8")
    box["env"]["FAKE_RC"] = str(rc)


def _ok(cost: float, result: str = "ok") -> dict:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result,
        "total_cost_usd": cost,
        "num_turns": 1,
    }


def _run(box: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        env=box["env"],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _launch(
    box: dict, *extra: str, key: str = "can", model: str = "haiku"
) -> subprocess.CompletedProcess:
    sel = ["--pick"] if key == "pick" else ["--key", key]
    return _run(
        box,
        "run",
        *sel,
        "--model",
        model,
        "--prompt-file",
        str(box["prompt"]),
        "--out",
        str(box["tmp"] / "out.md"),
        *extra,
    )


def _calls(box: dict) -> list[dict]:
    log = Path(box["env"]["FAKE_LOG"])
    if not log.exists():
        return []
    return [
        json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _seed(box: dict, key: str, cost: float, model: str = "haiku") -> None:
    run = uuid.uuid4().hex
    rows = [
        {"kind": "start", "run": run, "key": key, "model": model, "budget": 5.0},
        {
            "kind": "settle",
            "run": run,
            "key": key,
            "cost": cost,
            "is_error": False,
            "subtype": "success",
            "rc": 0,
        },
    ]
    with open(box["ledger"], "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _status(box: dict) -> dict:
    p = _run(box, "status", "--json")
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_run_settles_cost_and_status_reads_it(box: dict) -> None:
    _reply(box, _ok(1.25, "the answer"))
    p = _launch(box)
    assert p.returncode == 0, p.stderr
    assert (box["tmp"] / "out.md").read_text(encoding="utf-8").strip() == "the answer"
    st = _status(box)
    assert st["keys"]["can"]["spent_usd"] == pytest.approx(1.25)
    assert st["keys"]["can"]["provisioned_usd"] == pytest.approx(0.0)
    assert st["keys"]["can"]["runs"] == 1
    assert st["keys"]["sarp"]["spent_usd"] == 0


def test_key_at_cap_is_refused_before_claude(box: dict) -> None:
    _seed(box, "can", 195.0)  # cap 200 − margin 5 − 195 = 0 left
    before = box["ledger"].read_text(encoding="utf-8")
    _reply(box, _ok(0.01))
    p = _launch(box)
    assert p.returncode == 3, (p.returncode, p.stderr)
    assert _calls(box) == [], "claude was started for a key at its cap"
    assert box["ledger"].read_text(encoding="utf-8") == before, "a refused run wrote a ledger row"
    assert "can" in p.stderr and "cap" in p.stderr.lower()


def test_budget_clamped_to_available_minus_ceiling(box: dict) -> None:
    _seed(box, "can", 180.0)  # available 200 − 5 − 180 = 15; sonnet's per-call ceiling 3.78 → 11.22
    _reply(box, _ok(0.5))
    p = _launch(box, "--budget", "50", model="sonnet")
    assert p.returncode == 0, p.stderr
    argv = _calls(box)[0]["argv"]
    assert argv[argv.index("--max-budget-usd") + 1] == "11.22"
    start = [json.loads(x) for x in box["ledger"].read_text(encoding="utf-8").splitlines()][-2]
    assert start["kind"] == "start" and start["budget"] == pytest.approx(11.22)


def test_unsettled_run_counts_at_budget_plus_ceiling(box: dict) -> None:
    _reply(box, "this is not json", rc=1)
    p = _launch(box)  # haiku, default budget 5, ceiling 0.95
    assert p.returncode == 1
    can = _status(box)["keys"]["can"]
    assert can["provisioned_usd"] == pytest.approx(5.95)
    assert can["spent_usd"] == 0
    lines = box["ledger"].read_text(encoding="utf-8").splitlines()
    start = json.loads(lines[0])
    run = start["run"]
    early = _run(box, "settle", "--run", run, "--cost", "0.4")
    assert early.returncode == 2 and "may still be running" in early.stderr, (
        "a run inside its timeout was settled"
    )
    start["ts"] -= start["timeout"] + 120  # the run's timeout has now passed
    box["ledger"].write_text("\n".join([json.dumps(start), *lines[1:]]) + "\n", encoding="utf-8")
    s = _run(box, "settle", "--run", run, "--cost", "0.4")
    assert s.returncode == 0, s.stderr
    can = _status(box)["keys"]["can"]
    assert can["provisioned_usd"] == pytest.approx(0.0) and can["spent_usd"] == pytest.approx(0.4)
    again = _run(box, "settle", "--run", run, "--cost", "0.1")
    assert again.returncode != 0, "a run with a finite cost was settled twice"


def test_child_argv_env_and_no_key_leak(box: dict) -> None:
    box["env"].update(
        NODE_OPTIONS="--require /tmp/evil.js",
        HTTPS_PROXY="http://mitm:8080",
        https_proxy="http://mitm:8080",
        ANTHROPIC_API_KEY="sk-ant-api03-" + "Z" * 40,
        CLAUDE_CODE_OAUTH_TOKEN="oauth-secret",
        CLAUDE_CONFIG_DIR="/home/someone/.claude-fleet/ob",
    )
    foreign = (
        "sk-ant-api03-" + "F" * 40
    )  # a key this script never loaded: only the pattern can catch it
    _reply(box, _ok(0.02, f"leaked @KEY@ and {foreign} here"))
    p = _launch(box)
    assert p.returncode == 0, p.stderr
    call = _calls(box)[0]
    argv, env = call["argv"], call["env"]
    for flag in ("-p", "--bare", "--restricted", "--strict-mcp-config", "--no-session-persistence"):
        assert flag in argv, flag
    assert argv[argv.index("--tools") + 1] == "Read,Grep,Glob"
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv[argv.index("--permission-prompts") + 1] == "none"
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[-1].startswith("-") or argv[-2].startswith("--"), "a bare positional ends the argv"
    assert call["stdin"] == "Say ok."
    assert env["ANTHROPIC_API_KEY"] == KEYS["can"]
    assert env["FABRIK_HEADLESS"] == "1"
    for gone in ("NODE_OPTIONS", "HTTPS_PROXY", "https_proxy", "CLAUDE_CODE_OAUTH_TOKEN"):
        assert gone not in env, gone
    cfg = Path(env["CLAUDE_CONFIG_DIR"])
    assert str(cfg).startswith(str(box["state"])) and not cfg.exists(), (
        "per-run config dir not under state or not removed"
    )
    seen = (
        p.stdout
        + p.stderr
        + (box["tmp"] / "out.md").read_text(encoding="utf-8")
        + box["ledger"].read_text(encoding="utf-8")
    )
    for k in (*KEYS.values(), foreign):
        assert k not in seen, "a key value reached an output"
    assert "leaked" in (box["tmp"] / "out.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "bad",
    [
        b"not json at all\n",
        b"{}\n",
        b'{"kind": "start", "run": "'
        + b"a" * 32
        + b'", "key": "can", "model": "haiku", "budget": NaN}\n',
        b'{"kind": "settle", "run": "' + b"a" * 32 + b'", "key": "can", "cost": "12"}\n',
        b"\xff\xfe broken bytes\n",
    ],
    ids=["not-json", "empty-dict", "nan-budget", "string-cost", "non-utf8"],
)
def test_corrupt_ledger_refuses(box: dict, bad: bytes) -> None:
    box["ledger"].write_bytes(bad)
    _reply(box, _ok(0.01))
    p = _launch(box)
    assert p.returncode == 1, (p.returncode, p.stderr)
    assert "Traceback" not in p.stderr
    assert _calls(box) == []
    s = _run(box, "status", "--json")
    assert s.returncode == 1 and "Traceback" not in s.stderr


def test_pick_and_add_dir_vetting(box: dict) -> None:
    _seed(box, "can", 100.0)
    _seed(box, "sarp", 10.0)
    _seed(box, "ozgurbasak", 50.0)
    _reply(box, _ok(0.01))
    p = _launch(box, key="pick")
    assert p.returncode == 0, p.stderr
    assert _calls(box)[-1]["env"]["ANTHROPIC_API_KEY"] == KEYS["sarp"]

    t = box["tmp"]
    holds_env = t / "holds-env"
    (holds_env / "sub").mkdir(parents=True)
    (holds_env / "sub" / ".env").write_text("X=1\n", encoding="utf-8")
    checkout = t / "checkout"
    (checkout / ".git").mkdir(parents=True)
    escapes = t / "escapes"
    escapes.mkdir()
    (escapes / "link").symlink_to(t / "holds-env")
    clean = t / "clean"
    clean.mkdir()
    (clean / "a.py").write_text("x = 1\n", encoding="utf-8")
    (clean / ".env.example").write_text("X=\n", encoding="utf-8")
    n = len(_calls(box))
    for bad in (str(holds_env), str(checkout), str(escapes), "relative/dir", "/"):
        r = _launch(box, "--add-dir", bad)
        assert r.returncode == 2, (bad, r.returncode, r.stderr)
    assert len(_calls(box)) == n, "claude ran with an unsafe --add-dir"
    ok = _launch(box, "--add-dir", str(clean))
    assert ok.returncode == 0, ok.stderr
    argv = _calls(box)[-1]["argv"]
    assert argv[argv.index("--add-dir") + 1] == str(clean)


def test_bad_inputs_refuse_before_claude_and_budget_floors_to_cents(
    box: dict, tmp_path: Path
) -> None:
    _reply(box, _ok(0.01))
    loop = tmp_path / "loop"
    loop.mkdir()
    (loop / "a").symlink_to(loop / "a")
    cases = [
        ("--out", str(tmp_path / "missing" / "out.md")),
        ("--timeout", str(10**20)),
        ("--max-turns", "0"),
        ("--add-dir", str(loop)),
    ]
    for flag, value in cases:
        sel = ["--key", "can", "--model", "haiku", "--prompt-file", str(box["prompt"])]
        out = [] if flag == "--out" else ["--out", str(box["tmp"] / "out.md")]
        p = _run(box, "run", *sel, *out, flag, value)
        assert p.returncode == 2, (flag, p.returncode, p.stderr)
        assert "Traceback" not in p.stderr, (flag, p.stderr)
    assert _calls(box) == [] and not box["ledger"].exists(), (
        "a refused input started claude or wrote a row"
    )

    _reply(box, {**_ok(0.01), "subtype": "success sk-ant-api03-" + "Q" * 40})
    p = _launch(box, "--budget", "1.006")
    assert p.returncode == 0, p.stderr
    argv = _calls(box)[-1]["argv"]
    assert argv[argv.index("--max-budget-usd") + 1] == "1.00"
    rows = [json.loads(x) for x in box["ledger"].read_text(encoding="utf-8").splitlines()]
    assert rows[0]["budget"] == 1.0, (
        "the ledger provisions a different budget from the one the child received"
    )
    assert rows[1]["subtype"] is None and "Q" * 40 not in p.stdout, (
        "an unexpected subtype was stored or echoed"
    )
