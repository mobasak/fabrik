"""api_credit.py — spend the three prepaid API credits through capped, read-only `claude -p --bare` runs (D-1196,
W-894f994f). Each test is one Behaviour of the phase-2 design. The subject runs as a subprocess against a fake `claude`
on PATH that records its argv, env and stdin and prints a configured result, so nothing here reaches a provider."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
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
import json, os, sys, time
log = os.environ["FAKE_LOG"]
with open(log, "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "env": dict(os.environ), "stdin": sys.stdin.read(),
                        "cwd": os.getcwd()}}) + "\\n")
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
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
    run = json.loads(box["ledger"].read_text(encoding="utf-8").splitlines()[0])["run"]
    # the child exited (its own settle row exists), so the console's figure may close it at once
    s = _run(box, "settle", "--run", run, "--cost", "0.4")
    assert s.returncode == 0, s.stderr
    can = _status(box)["keys"]["can"]
    assert can["provisioned_usd"] == pytest.approx(0.0) and can["spent_usd"] == pytest.approx(0.4)
    again = _run(box, "settle", "--run", run, "--cost", "0.1")
    assert again.returncode == 2 and "already has a cost" in again.stderr, "a run was settled twice"

    # a start with no exit row is a run that may still be spending: refused inside its timeout, allowed after
    live = uuid.uuid4().hex
    row = {
        "kind": "start",
        "run": live,
        "key": "can",
        "model": "haiku",
        "budget": 2.0,
        "timeout": 1800,
        "ts": time.time(),
    }
    with open(box["ledger"], "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    early = _run(box, "settle", "--run", live, "--cost", "0.2")
    assert early.returncode == 2 and "may still be running" in early.stderr, (
        "a live run was settled"
    )
    lines = box["ledger"].read_text(encoding="utf-8").splitlines()
    row["ts"] -= row["timeout"] + 120
    box["ledger"].write_text("\n".join([*lines[:-1], json.dumps(row)]) + "\n", encoding="utf-8")
    late = _run(box, "settle", "--run", live, "--cost", "0.2")
    assert late.returncode == 0, late.stderr


def test_timeout_and_error_flag_and_fallback_scrub(box: dict) -> None:
    # a timeout writes a cost-less settle: the run stays provisioned at budget + ceiling, and --out says so
    _reply(box, _ok(0.01))
    box["env"]["FAKE_SLEEP"] = "5"
    p = _launch(box, "--timeout", "1")
    assert p.returncode == 1 and "timed out" in p.stderr
    assert _status(box)["keys"]["can"]["provisioned_usd"] == pytest.approx(5.95)
    assert "timed out" in (box["tmp"] / "out.md").read_text(encoding="utf-8")
    box["env"].pop("FAKE_SLEEP")

    # is_error true with rc 0 (a bogus key's shape) is an error, and its reported cost still settles
    _reply(box, {**_ok(0.0, "Invalid API key"), "is_error": True}, rc=0)
    p = _launch(box, key="sarp")
    assert p.returncode == 1 and "ERROR" in p.stdout
    assert (
        _status(box)["keys"]["sarp"]["spent_usd"] == 0
        and _status(box)["keys"]["sarp"]["provisioned_usd"] == 0
    )

    # output that is not JSON is echoed through the scrubber: no key value survives it
    _reply(box, "boom @KEY@ sk-ant-api03-" + "W" * 40, rc=1)
    p = _launch(box, key="ozgurbasak")
    text = (box["tmp"] / "out.md").read_text(encoding="utf-8")
    assert p.returncode == 1 and "boom" in text
    assert KEYS["ozgurbasak"] not in text and "W" * 40 not in text
    # the tail kept is the last 4000 characters: a key straddling that cut must not leave its own tail behind
    _reply(box, "@KEY@" + "x" * 3990, rc=1)
    p = _launch(box, key="ozgurbasak")
    text = (box["tmp"] / "out.md").read_text(encoding="utf-8")
    # 57-character key + 3990 filler = 4047: the window keeps the key's last 10 characters unless it was scrubbed first
    assert KEYS["ozgurbasak"][-6:] not in text, (
        "a key cut by the 4000-character window leaked its tail"
    )


def test_ledger_figures_over_count_never_under(box: dict) -> None:
    run = "b" * 32
    rows = [
        {"kind": "start", "run": run, "key": "can", "model": "haiku", "budget": 5.0},
        {
            "kind": "start",
            "run": run,
            "key": "sarp",
            "model": "fable",
            "budget": 50.0,
        },  # duplicate: the first start owns the run, so its spend lands on can, never on sarp
        {"kind": "settle", "run": run, "key": "can", "cost": 2.0},
        {"kind": "settle", "run": run, "key": "can", "cost": 7.0},  # two figures: the larger counts
        {"kind": "settle", "run": run, "key": "can", "cost": 3.0},
    ]
    box["ledger"].write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    st = _status(box)["keys"]
    assert st["can"]["spent_usd"] == pytest.approx(7.0) and st["can"]["runs"] == 1
    assert st["sarp"]["spent_usd"] == 0 and st["sarp"]["runs"] == 0
    # a figure past float range is no usable cost: the run reads provisioned (first start: 5 + 0.95), no traceback
    box["ledger"].write_text(
        json.dumps(rows[0])
        + "\n"
        + '{"kind": "settle", "run": "'
        + run
        + '", "key": "can", "cost": 1'
        + "0" * 400
        + "}\n",
        encoding="utf-8",
    )
    can = _status(box)["keys"]["can"]
    assert can["spent_usd"] == 0 and can["provisioned_usd"] == pytest.approx(5.95)


def test_child_argv_env_and_no_key_leak(box: dict) -> None:
    stripped = {
        "NODE_OPTIONS": "--require /tmp/evil.js",
        "NODE_PATH": "/evil",
        "LD_PRELOAD": "/evil.so",
        "LD_AUDIT": "/evil.so",
        "GLIBC_TUNABLES": "x",
        "NODE_EXTRA_CA_CERTS": "/evil.pem",
        "SSL_CERT_FILE": "/evil.pem",
        "CURL_CA_BUNDLE": "/evil.pem",
        "HTTPS_PROXY": "http://mitm:8080",
        "https_proxy": "http://mitm:8080",
        "ANTHROPIC_BASE_URL": "http://evil.example",
        "ANTHROPIC_API_KEY_SARP": KEYS["sarp"],
        "ANTHROPIC_API_KEY": "sk-ant-api03-" + "Z" * 40,
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth-secret",
        "CLAUDE_CONFIG_DIR": "/home/someone/.claude-fleet/ob",
    }
    box["env"].update(stripped)
    box["env"].pop(
        "LD_PRELOAD"
    )  # set in the child's env only through the check below: it would load in the parent
    box["env"].pop("LD_AUDIT")
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
    for gone in stripped:
        if gone not in ("ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR", "LD_PRELOAD", "LD_AUDIT"):
            assert gone not in env, gone
    assert call["cwd"] == str((box["state"] / "api-credit" / "cwd").resolve()), call["cwd"]
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
        b'{"kind": "start", "run": "not-hex", "key": "can", "model": "haiku", "budget": 1.0}\n',
        # a settle whose start was deleted would carry spend no tally counts
        b'{"kind": "settle", "run": "' + b"a" * 32 + b'", "key": "can", "cost": 150.0}\n',
        b'{"kind": "start", "run": "'
        + b"a" * 32
        + b'", "key": "can", "model": "haiku", "budget": 1.0}\n{"kind": "settle", "run": "'
        + b"a" * 32
        + b'", "key": "sarp", "cost": 0.5}\n',
    ],
    ids=[
        "not-json",
        "empty-dict",
        "nan-budget",
        "string-cost",
        "non-utf8",
        "bad-run-id",
        "orphan-settle",
        "key-mismatch",
    ],
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
    unsafe = []
    for rel in (
        "sub/.env",
        "sub/.env.local",
        ".envrc",
        ".netrc",
        "keys/id_rsa",
        "deploy.pem",
        ".credentials.json",
        "sub/.git/config",
        ".git",
        ".ssh/known_hosts",
    ):
        d = t / ("holds-" + rel.replace("/", "_"))
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text("token=abc\n", encoding="utf-8")
        unsafe.append(str(d))
    escapes = t / "escapes"
    escapes.mkdir()
    (escapes / "link").symlink_to(t / "holds-.netrc")
    linked_root = t / "linked-root"
    clean = t / "clean"
    clean.mkdir()
    linked_root.symlink_to(clean)
    (clean / "a.py").write_text("x = 1\n", encoding="utf-8")
    (clean / ".env.example").write_text("X=\n", encoding="utf-8")
    home = t / "home"
    (home / "work").mkdir(parents=True)
    box["env"]["HOME"] = str(home)
    n = len(_calls(box))
    for bad in (*unsafe, str(escapes), str(linked_root), str(home), "relative/dir", "/"):
        r = _launch(box, "--add-dir", bad)
        assert r.returncode == 2, (bad, r.returncode, r.stderr)
        assert "Traceback" not in r.stderr, (bad, r.stderr)
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
    (tmp_path / "out-dir").mkdir()
    cases = [
        ("--out", str(tmp_path / "missing" / "out.md")),
        ("--out", str(tmp_path / "out-dir")),
        ("--timeout", str(10**20)),
        ("--max-turns", "0"),
        ("--add-dir", str(loop)),
        ("--budget", "0"),
        ("--budget", "-1"),
        ("--budget", "nan"),
        ("--budget", "0.01"),
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


def test_missing_claude_and_empty_keys_refuse_without_a_row(box: dict) -> None:
    _reply(box, _ok(0.01))
    # no `claude` on PATH: refused before the start row, so nothing is provisioned
    env = dict(box["env"])
    box["env"]["PATH"] = str(box["tmp"] / "empty-bin")
    p = _launch(box)
    assert p.returncode == 2 and "no `claude`" in p.stderr, (p.returncode, p.stderr)
    assert not box["ledger"].exists(), "a run that could not start provisioned a row"
    box["env"] = env

    # --pick passes over a key with no value; --key on that key is refused before any row
    Path(box["env"]["API_CREDIT_ENV_FILE"]).write_text(
        'export ANTHROPIC_API_KEY_CAN=""\n'
        f'export ANTHROPIC_API_KEY_SARP="{KEYS["sarp"]}" # the Sarp credit\n'
        f"ANTHROPIC_API_KEY_OZGURBASAK={KEYS['ozgurbasak']} # trailing comment\n",
        encoding="utf-8",
    )
    _seed(box, "ozgurbasak", 100.0)  # sarp has the most room among the keys present
    p = _launch(box, key="pick")
    assert p.returncode == 0, p.stderr
    assert _calls(box)[-1]["env"]["ANTHROPIC_API_KEY"] == KEYS["sarp"], (
        "export/comment parsing or pick broke"
    )
    p = _launch(box, key="ozgurbasak")
    assert p.returncode == 0 and _calls(box)[-1]["env"]["ANTHROPIC_API_KEY"] == KEYS["ozgurbasak"]
    rows = len(box["ledger"].read_text(encoding="utf-8").splitlines())
    p = _launch(box, key="can")
    assert p.returncode == 2 and "missing or empty" in p.stderr
    assert len(box["ledger"].read_text(encoding="utf-8").splitlines()) == rows


def test_child_env_strips_loader_and_runtime_families(monkeypatch: pytest.MonkeyPatch) -> None:
    # LD_* cannot be set on the subprocess the other tests start (the loader would act on the test's own python),
    # so the family rule is graded on child_env directly.
    sys.path.insert(0, str(ROOT / "scripts"))
    import api_credit

    for name in (
        "LD_PRELOAD",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "BUN_OPTIONS",
        "npm_config_registry",
        "all_proxy",
    ):
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv("KEEP_ME", "1")
    env = api_credit.child_env("sk-ant-api03-" + "K" * 40, Path("/abs/config"))
    for name in (
        "LD_PRELOAD",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "BUN_OPTIONS",
        "npm_config_registry",
        "all_proxy",
    ):
        assert name not in env, name
    assert env["KEEP_ME"] == "1" and env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"


def test_ambient_git_dir_does_not_move_the_key_file(box: dict, tmp_path: Path) -> None:
    # an ambient GIT_DIR naming another repository must not move the key file to that repository's .env
    other = tmp_path / "other"
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    env = {k: v for k, v in box["env"].items() if k != "API_CREDIT_ENV_FILE"}
    env["GIT_DIR"] = str(other / ".git")
    code = f"import sys; sys.path.insert(0, {str(ROOT / 'scripts')!r}); import api_credit as a; print(a.env_file())"
    p = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60
    )
    assert p.returncode == 0, p.stderr
    assert not p.stdout.strip().startswith(str(other)), p.stdout


def test_add_dir_inside_a_credential_directory_is_refused(box: dict) -> None:
    # the directory's own path counts: its files may carry ordinary names (`credentials`, `config`)
    _reply(box, _ok(0.01))
    for parts in ((".aws",), (".ssh",), ("repo", ".git", "objects"), (".kube", "sub")):
        d = box["tmp"].joinpath("roots", *parts)
        d.mkdir(parents=True)
        (d / "credentials").write_text("token=abc\n", encoding="utf-8")
        p = _launch(box, "--add-dir", str(d))
        assert p.returncode == 2 and "inside" in p.stderr, (parts, p.returncode, p.stderr)
    assert _calls(box) == [], "claude ran with an --add-dir inside a credential directory"


def test_a_failure_around_the_process_stays_provisioned_and_unsettleable(box: dict) -> None:
    # an unwritable config dir makes the per-run mkdtemp fail AFTER the start row: the run is not known to have
    # exited, so it stays provisioned and settle refuses it until its timeout has passed
    _reply(box, _ok(0.01))
    config = box["state"] / "api-credit" / "config"
    config.mkdir(parents=True)
    config.chmod(0o500)
    try:
        p = _launch(box)
    finally:
        config.chmod(0o700)
    assert p.returncode == 1 and "before or around the claude process" in p.stderr, (
        p.returncode,
        p.stderr,
    )
    rows = [json.loads(x) for x in box["ledger"].read_text(encoding="utf-8").splitlines()]
    assert [r["kind"] for r in rows] == ["start", "settle"]
    assert rows[1]["subtype"] == "spawn_error" and rows[1]["source"] != "run"
    assert _status(box)["keys"]["can"]["provisioned_usd"] == pytest.approx(5.95)
    early = _run(box, "settle", "--run", rows[0]["run"], "--cost", "0.1")
    assert early.returncode == 2 and "may still be running" in early.stderr, (
        "a run not known to have exited was settled"
    )
