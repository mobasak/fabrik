"""Regression: doc placeholders (your-key-here, <token>, changeme…) are not real secrets and must
not trip check_secrets — while real credentials still are flagged."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "enforcement"))
import check_secrets as cs  # noqa: E402


def _scan(tmp_path, text):
    p = tmp_path / "doc.md"
    p.write_text(text)
    return [r.message for r in cs.check_file(p)]


def test_placeholders_are_skipped(tmp_path):
    for v in [
        'API_KEY="your-key-here"',
        'api_key="changeme"',
        'token="<your-token>"',
        'secret="{{VAULT_SECRET}}"',
        'password="xxxxxxxx"',
        'api_key="placeholder"',
    ]:
        assert _scan(tmp_path, v) == [], v


def test_real_credentials_still_flagged(tmp_path):
    for v in ['api_key="hunter2RealPassw0rd"', 'password="s3cr3tP@ssvalue"']:
        assert _scan(tmp_path, v), f"MISSED real secret: {v}"


def test_real_provider_keys_still_flagged(tmp_path):
    assert _scan(tmp_path, 'k = "sk-ant-' + "a" * 40 + '"')


def test_example_dsn_credentials_are_skipped(tmp_path):
    # Backtick-wrapped connection-string EXAMPLES in reference docs — placeholder creds.
    for v in [
        "Connection String: `postgresql://user:pass@host:port/db`",
        "URI: `postgresql://user:password@host:5432/db`",
        "`mongodb://user:pwd@host:27017/db`",
        "`mongodb+srv://user:password@cluster/db`",
    ]:
        assert _scan(tmp_path, v) == [], v


def test_real_dsn_password_still_flagged(tmp_path):
    for v in [
        "url = `postgresql://admin:Xk9d2RealPw@host:5432/db`",
        "`mongodb://root:s3cr3tValue@host:27017/db`",
    ]:
        assert _scan(tmp_path, v), f"MISSED real DSN secret: {v}"


def test_bare_shell_variable_reference_is_skipped(tmp_path):
    # Live false-positive 2026-08-07: RESTIC_PASSWORD="$RESTIC_PW" (a sibling's
    # sysadmin script) — a bare $VAR reference is an expansion, not a hardcoded
    # secret, exactly like the ${VAR} and $(cmd) forms already exempted.
    for v in [
        'RESTIC_PASSWORD="$RESTIC_PW"',
        'password="$PGPASS"',
        'secret="${VAULT_TOKEN}"',
        'token="$(cat /run/secret)"',
    ]:
        assert _scan(tmp_path, v) == [], v


def test_dollar_prefixed_but_literal_password_still_flagged(tmp_path):
    # Discriminates the exemption BOUNDARY: $ followed by a non-name char
    # (digit) is NOT a shell reference — must still be flagged. Also a
    # mid-string $ never engages the lookahead.
    assert _scan(tmp_path, 'password="$19.99longvalue"')
    assert _scan(tmp_path, 'password="hunter2$altyValue"')


def test_dsn_command_substitution_is_skipped(tmp_path):
    # Reciprocal half of the $-reference stance: the DSN patterns must exempt
    # $(cmd) exactly like the credential pattern does.
    assert _scan(tmp_path, "postgresql://user:$(vault_read_pw)@host:5432/db") == []
    assert _scan(tmp_path, "mongodb://user:$(op read pw)@host/db") == []


def test_dsn_real_password_still_flagged(tmp_path):
    assert _scan(tmp_path, "postgresql://user:Xk9realpw2@host:5432/db")


# ── vendor tokens this box issues (added after a LIVE MISS, 2026-08-30) ───────────
# A literal Grafana token reached a commit in scripts/sysadmin/mcp_defs.json and only
# GitHub push protection stopped it: check_secrets had no Grafana pattern. These pin
# the gap closed, and pin that the ${VAR} form the catalog uses stays clean.


def test_grafana_service_account_token_is_caught(tmp_path):
    """The exact miss: a glsa_ literal in the MCP catalog must not reach a commit."""
    f = tmp_path / "mcp_defs.json"
    f.write_text(
        '{"env": {"GRAFANA_SERVICE_ACCOUNT_TOKEN": '
        '"glsa_FAKEfake0123456789abcdefFAKEfake_12ab34cd"}}'
    )
    assert cs.check_file(f), "a literal glsa_ token must be caught"


def test_openrouter_and_firecrawl_keys_are_caught(tmp_path):
    f = tmp_path / "conf.json"
    f.write_text(
        '{"OPENROUTER_API_KEY": "sk-or-v1-' + "0123456789abcdef" * 4 + '",\n'
        ' "FIRECRAWL_API_KEY": "fc-' + "0123456789abcdef" * 2 + '"}'
    )
    assert len(cs.check_file(f)) >= 2, "both vendor keys must be caught"


def test_placeholder_form_of_those_keys_is_clean(tmp_path):
    """The catalog's real shape — ${VAR} references — must stay green, or the check
    is wallpaper the next author learns to ignore."""
    f = tmp_path / "mcp_defs.json"
    f.write_text(
        '{"env": {"GRAFANA_SERVICE_ACCOUNT_TOKEN": "${GRAFANA_SERVICE_ACCOUNT_TOKEN}",'
        ' "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}",'
        ' "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"}}'
    )
    assert cs.check_file(f) == [], "placeholders are the CORRECT form"


def test_credential_pattern_requires_matching_quotes():
    """01M1GNV1 (youtube, 2026-08-31): `PW=$(grep -E '^X_PASSWORD=' .env | cut -d= -f2-)"` on ONE
    line — a single-quoted grep pattern followed later by a double quote — matched the credential
    regex, which accepted any quote type at either end. Only a matching pair is a literal."""
    import re as _re

    mixed = "PW=$(grep -E '^PAYMENTS_SERVICE_DB_PASSWORD=' .env | cut -d= -f2-)\"\n"
    real = "password = 'hunter2hunter2'\n"
    hits_mixed = [name for pat, name in cs.SECRET_PATTERNS if _re.search(pat, mixed)]
    hits_real = [name for pat, name in cs.SECRET_PATTERNS if _re.search(pat, real)]
    assert not hits_mixed, hits_mixed
    assert hits_real, "a real quoted password must still match"


def _git(repo, *args):
    import subprocess  # noqa: PLC0415

    # stdin=DEVNULL: `git hash-object --stdin` below reads fd 0, and under `pytest -s` (or any
    # runner that leaves fd 0 a live pipe) it blocks forever — measured, a 25s timeout expired.
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )


def test_a_changed_tracked_file_that_is_not_utf8_does_not_crash_the_secrets_leg(
    tmp_path, monkeypatch
):
    """Reported by web-ecommerce-factory (01M2X0ZQX8YMZX022R9TC1E3M6).

    `main()` passes `_changed_line_numbers(rel)` as the ARGUMENT to `check_file`, so it runs
    before `check_file` can skip anything — and it shelled out to `git diff` with `text=True`
    and no `errors=`, i.e. strict UTF-8. A tracked file whose first 8000 bytes hold no NUL is
    classified TEXT by git's own heuristic and diffs as text, so an uncompressed PDF (or an .ico,
    a font, latin-1 prose) raised `UnicodeDecodeError` out of `subprocess._translate_newlines`.
    That is neither `CalledProcessError` nor `FileNotFoundError`, so the function's two fail-open
    arms never saw it and the whole "Secrets (Zero Hardcoding)" gate leg crashed for every agent
    in the repo — over a file class `check_file` never scans anyway.

    The fix is NOT the reporter's suffix pre-filter. A review seat measured why: over four
    NUL-free non-UTF-8 files that git diffs as TEXT, the suffix list rescues 1 of 4 (`.pdf`)
    while `.ico`, a font and latin-1 prose still raise; tolerant decoding covers 4 of 4.
    ⚠️ This test does NOT exercise `check_file`'s own `except (OSError, UnicodeDecodeError)`
    guard — the `.pdf` fixture is filtered by the suffix check at `:127` before `read_text` runs,
    so that guard is asserted by `test_check_file_is_total_over_undecodable_files` below, not here.
    """
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    # high bytes, NO NUL in the first 8000 → git calls it TEXT and diffs it as text
    blob = (b"%PDF-1.4\n\x89\xe5\xd0\xd4" + b"A" * 200 + b"\n") * 40
    doc = repo / "sub" / "doc.pdf"
    doc.write_bytes(blob)
    _git(repo, "add", "sub/doc.pdf")
    _git(repo, "commit", "-qm", "base")
    assert b"\x00" not in blob[:8000], "fixture must be NUL-free or git calls it binary"
    doc.write_bytes(blob + b"%PDF-1.4\n\xc3\x28 trailing\n")
    numstat = _git(repo, "diff", "HEAD", "--numstat", "--", "sub/doc.pdf").stdout
    assert numstat.split()[0].isdigit(), f"git must diff it as TEXT, got {numstat!r}"

    monkeypatch.chdir(repo)
    # the unit: it must RETURN, and return the changed-line set rather than the None that
    # a catch-and-fail-open would give (None means "scan the whole file", which is the
    # false-positive class the scoping exists to prevent)
    changed = cs._changed_line_numbers("sub/doc.pdf")
    assert isinstance(changed, set) and changed, changed
    # and end to end, the way final_gate invokes it: the leg exits 0, not a traceback
    assert cs.main() == 0


def _repo(tmp_path, name="repo"):
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    return repo


def test_a_secret_in_a_non_ascii_path_is_still_reported(tmp_path, monkeypatch):
    """Found reviewing the UnicodeDecodeError fix — the same class, failing SILENTLY instead.

    On git's DEFAULT config `git diff --name-only` QUOTES a path containing a non-ASCII byte,
    a quote or a backslash: `café.txt` comes back as the 15-char literal `"caf\303\251.txt"`.
    `Path(that).is_file()` is False, so `main()` skipped the file and reported nothing — a
    hardcoded secret in any accented, Cyrillic, CJK or emoji path went unreported in every repo,
    with no error and no unusual configuration. A crash is loud; this was not.

    `-z` turns quoting OFF and `errors="surrogateescape"` round-trips raw path bytes, so the same
    change also closes the crash on an undecodable path when `core.quotePath=false`.
    """
    repo = _repo(tmp_path)
    for name in ("ascii.txt", "café.txt", 'q"uote.txt', "back\\slash.txt"):
        (repo / name).write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    for name in ("ascii.txt", "café.txt", 'q"uote.txt', "back\\slash.txt"):
        (repo / name).write_text('x = 1\npassword = "Sup3rSecretPW9"\n')

    monkeypatch.chdir(repo)
    seen = set(cs._changed_files())
    assert "café.txt" in seen, f"the quoted path never round-tripped: {sorted(seen)}"
    assert not any(f.startswith('"') for f in seen), f"a quoted literal leaked through: {seen}"
    assert cs.main() == 1, "a secret in a non-ASCII path must still fail the gate"


def test_a_binary_diffed_file_does_not_silence_the_scan(tmp_path, monkeypatch):
    """Found reviewing the same fix. `_changed_line_numbers` returns an EMPTY set whenever the
    diff carries no `@@` header — and an empty set means ALLOW NOTHING downstream, not "scan
    everything". Git emits no hunk header for a file it treats as binary, so one `.gitattributes`
    line (`*.cfg -diff`) or a single NUL byte silenced every finding in that file while the gate
    reported success. `None` is the documented fail-open for "no usable diff"; `set()` must mean
    only "nothing changed".
    """
    repo = _repo(tmp_path, "binrepo")
    (repo / ".gitattributes").write_text("*.cfg -diff\n")
    (repo / "marked.cfg").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    (repo / "marked.cfg").write_text('x = 1\npassword = "Sup3rSecretPW9"\n')

    monkeypatch.chdir(repo)
    scope = cs._changed_line_numbers("marked.cfg")
    assert scope != set(), "an empty scope silences the file; None is the fail-open"
    assert cs.main() == 1, "a secret in a binary-diffed file must still fail the gate"


def test_check_file_is_total_over_undecodable_files(tmp_path):
    """The claim the suffix-pre-filter refusal rests on: `check_file` returns `[]` for ANY
    undecodable file, not just the five suffixes it names. A seat found this guard was
    mutation-untested — narrowing it to `except OSError` left the whole suite green.
    """
    cases = {
        "icon.ico": b"\x00\x00\x01\x00" + b"\xff" * 64,
        "font.ttf": b"\x00\x01\x00\x00" + b"\xe9\xe8" * 32,
        "latin1.txt": "password = 'Sup3rSecretPW9'\n".encode("latin-1") + b"\xe9caf\xe9\n",
        "utf16.txt": "password = 'Sup3rSecretPW9'\n".encode("utf-16"),
    }
    for name, blob in cases.items():
        f = tmp_path / name
        f.write_bytes(blob)
        assert cs.check_file(f) == [], f"{name} must yield no findings, not raise"


def test_an_undecodable_path_does_not_crash_the_leg(tmp_path, monkeypatch):
    """`core.quotePath=false` hands raw path bytes back, and `subprocess.run(text=True)` decodes
    BOTH streams inside `communicate()` before `.returncode` is ever read — so even the
    `git ls-files --error-unmatch` call, whose stdout this module discards, raised
    `UnicodeDecodeError` on a latin-1 filename (tracked: from stdout; untracked: from stderr).
    Without this test that half of the decode fix is ungraded, which a seat proved by removing
    it and watching the suite stay green.
    """
    import os  # noqa: PLC0415

    repo = _repo(tmp_path, "q")
    _git(repo, "config", "core.quotePath", "false")
    # ⚠️ RAW BYTES on disk. `b"caf\xe9.txt".decode("latin-1")` is the STRING "café.txt", which
    # Python then writes back as VALID UTF-8 — the fixture would decode cleanly and the test
    # would pass against a strict decoder, which is exactly how the first cut of this grader let
    # `errors="surrogateescape"` be removed with the suite green.
    raw = os.path.join(os.fsencode(str(repo)), b"caf\xe9.txt")
    with open(raw, "wb") as fh:
        fh.write(b"x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    with open(raw, "wb") as fh:
        fh.write(b'x = 1\npassword = "Sup3rSecretPW9"\n')

    monkeypatch.chdir(repo)
    name = os.fsdecode(b"caf\xe9.txt")  # the surrogateescape form the module must round-trip
    assert name in set(cs._changed_files()), "the undecodable path never round-tripped"
    assert cs._changed_line_numbers(name) is not None  # must not raise out of either call

    # ⚠️ A REAL SUBPROCESS, not `cs.main()` in-process. pytest replaces `sys.stdout` with a writer
    # built `errors="replace"`, so an in-process call passes even when the shipped code raises
    # `UnicodeEncodeError` printing a surrogate path — which is how the first cut of this grader
    # blessed a fix that still lost EVERY finding under `final_gate`'s real pipe (executed:
    # green under capture, red under `-s`). This runs it the way final_gate does.
    import subprocess as _sp  # noqa: PLC0415

    mod = str(Path(cs.__file__).resolve())
    r = _sp.run([sys.executable, mod], capture_output=True, cwd=repo, stdin=_sp.DEVNULL)
    assert r.returncode == 1, (r.returncode, r.stdout[-400:], r.stderr[-400:])
    assert b"Traceback" not in r.stderr, r.stderr[-400:]
    assert b"Hardcoded credential" in r.stdout, (r.stdout[-400:], r.stderr[-400:])


def test_a_fake_hunk_header_inside_content_cannot_allocate_without_bound(tmp_path, monkeypatch):
    """`str.splitlines()` splits on more than `\n` — `\r`, `\x0b`, `\x0c`, `\x1c`-`\x1e`, `\x85`,
    U+2028 and U+2029 all break a line — so a CHANGED CONTENT LINE can present its tail to
    `_HUNK_RE` as a hunk header. A seat weaponised that: a line carrying
    `\x0b@@ -1,1 +1,900000000 @@` drove `range(start, start + count)` into MemoryError in under
    a second, uncaught, killing the gate leg on a box three sessions share.
    """
    repo = _repo(tmp_path, "hunk")
    (repo / "notes.md").write_text("intro\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    (repo / "notes.md").write_text("intro\nreal\x0b@@ -1,1 +1,900000000 @@ x\n")

    monkeypatch.chdir(repo)
    # ⚠️ `None`, not a truncated set. The first cut did `count = min(count, _MAX_HUNK_LINES)` and
    # this assertion read `is not None` — i.e. it PINNED the truncation, which silently drops
    # every finding past the cut (see the companion test below). Failing open is the fix, so the
    # grader has to assert the fail-open.
    assert cs._changed_line_numbers("notes.md") is None

    # and the AGGREGATE: one changed line can manufacture MANY headers, so a per-header bound
    # leaves the accumulated set unbounded — 300 segments reached MemoryError under a 2 GB cap.
    (repo / "notes.md").write_text(
        "intro\nreal" + "".join(f"\x0b@@ -1,1 +{i}000000,999999 @@ x" for i in range(300)) + "\n"
    )
    assert cs._changed_line_numbers("notes.md") is None

    # the real constant must still be a sane bound, asserted absolutely so raising it is not a fix
    assert cs._MAX_HUNK_LINES <= 1_000_000


def test_a_secret_past_the_scope_bound_is_still_reported(tmp_path, monkeypatch):
    """The mirror of the clamp: narrowing a scope is a MISSED SECRET, not a safe default.

    A seat proved the truncating cut regressed detection against the previous release — a real
    credential at line 1,000,003 of a staged 1,000,005-line file was reported before and silently
    dropped after. The bound is exercised through a monkeypatched `_MAX_HUNK_LINES` so the case
    costs milliseconds instead of a million-line fixture; the real constant's sanity is asserted
    in the test above.
    """
    monkeypatch.setattr(cs, "_MAX_HUNK_LINES", 10)
    repo = _repo(tmp_path, "past")
    (repo / "seed.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    body = [f"x = {i}" for i in range(40)]
    body[35] = 'password = "Sup3rSecretPW9"'
    (repo / "dump.sql").write_text("\n".join(body) + "\n")
    _git(repo, "add", "dump.sql")

    monkeypatch.chdir(repo)
    assert cs._changed_line_numbers("dump.sql") is None, "an over-bound scope must fail OPEN"
    assert cs.main() == 1, "a secret past the scope bound must still be reported"


def test_every_changed_file_probe_is_wired(tmp_path, monkeypatch):
    """`_changed_files` runs three probes — unstaged, staged, untracked — and a seat showed that
    dropping `-z` from either the staged or the untracked one lost a whole file class with the
    suite still green. Only the plain-diff probe was graded. Each gets its own case here.
    """
    repo = _repo(tmp_path, "probes")
    (repo / "seed.txt").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    monkeypatch.chdir(repo)

    (repo / "untracked.py").write_text('password = "Sup3rSecretPW9"\n')
    assert cs.main() == 1, "untracked probe"
    (repo / "untracked.py").unlink()

    (repo / "staged.py").write_text('password = "Sup3rSecretPW9"\n')
    _git(repo, "add", "staged.py")
    assert cs.main() == 1, "staged probe"
    _git(repo, "rm", "-q", "--cached", "staged.py")
    (repo / "staged.py").unlink()

    (repo / "seed.txt").write_text('x\npassword = "Sup3rSecretPW9"\n')
    assert cs.main() == 1, "unstaged probe"


def test_an_overlong_path_in_the_index_does_not_crash_the_leg(tmp_path, monkeypatch):
    """`Path.is_file()` propagates `OSError(ENAMETOOLONG)` — Python only swallows
    ENOENT/ENOTDIR/EBADF/ELOOP. A seat found the filesystem cannot produce such a path
    (`git add` fails first) but the PLUMBING can: `git update-index --add --cacheinfo` accepts a
    5000-char path at rc 0 and `git diff --staged --name-only` then emits it. That plumbing call
    is exactly the private-index commit recipe `CLAUDE.md` mandates for shared-append files, so
    the hub's own contract is the delivery vehicle for this crash.
    """
    repo = _repo(tmp_path, "long")
    (repo / "seed.txt").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    blob = _git(repo, "hash-object", "-w", "--stdin").stdout  # empty stdin → the empty blob
    blob = blob.strip() or "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    # must EXCEED PATH_MAX (4096 on Linux) or `is_file()` simply answers False without
    # raising — the first cut of this fixture was 284 chars and passed against the bug
    long_path = "d/" * 600 + "x" * 4000 + ".txt"
    r = _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{long_path}")
    if r.returncode != 0:  # a git that refuses it leaves nothing to test
        import pytest as _pytest  # noqa: PLC0415

        _pytest.skip(f"git refused the cacheinfo path: {r.stderr.strip()[:80]}")

    monkeypatch.chdir(repo)
    # the guard's VALUE, not just the absence of a crash: returning True also yields main()==0
    # (check_file's own read_text guard absorbs it), so a seat's mutant survived on that alone.
    assert cs._is_file(Path(long_path)) is False
    assert cs.main() == 0, "an unreachable overlong path must be skipped, not raise"


def test_an_unusable_git_is_loud_not_silently_clean(tmp_path, monkeypatch):
    """Two rulings, one test. The fail-open arms promised "git unavailable" but implemented only
    ABSENT: a `git` that exists and cannot be executed (noexec mount, broken PATH shim, ENOMEM on
    fork) raises `PermissionError`, an `OSError`, so the leg CRASHED where its docstring said it
    degrades. Widening the arms fixed that — and a seat then showed the widening was worse: the
    scan saw zero files and returned 0, i.e. "I could not look" reading as "I looked and found
    nothing", on a SECRETS gate whose runner discards stdout on rc 0. So an unusable git inside a
    work tree is now a LOUD failure, while a plain non-repo directory stays the silent fail-open.
    """
    # ⚠️ build the repo BEFORE breaking PATH — the first cut of this test created it afterwards,
    # so every `git` call in the fixture silently failed and the assertion tested nothing.
    repo = _repo(tmp_path, "live")
    (repo / "seed.txt").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "git").write_text("#!/bin/sh\nexit 0\n")
    (shim / "git").chmod(0o000)
    monkeypatch.setenv("PATH", str(shim))

    # no usable git AND no detectable work tree → the documented fail-open, silent
    monkeypatch.chdir(tmp_path)
    assert cs._changed_line_numbers("anything.txt") is None
    assert cs.main() == 0

    # but inside a real work tree, "could not look" must not read as "nothing to find"
    # ⚠️ NO monkeypatch of `_inside_work_tree`. The first cut replaced it with `lambda: True`,
    # which is precisely the function whose real behaviour was broken — it shelled out to the
    # same unusable git, so it answered False exactly when the guard had to fire, and the mutant
    # `return False` survived the whole suite. It is filesystem-based now, so the shipped
    # predicate runs here.
    monkeypatch.chdir(repo)
    assert cs.main() == 1, "an unusable git inside a repo must fail loud, not pass clean"
