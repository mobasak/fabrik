# AFTER-EDIT: scripts/mail.py | none
"""D-035 — the inter-agent message contract: 5W1H + factual WHY + SYSTEMIC mandatory
on substantive kinds (finding/request/upstream-feedback); advisory (warn, never refuse)."""

import importlib.util
import os
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "fabrik_mail", Path(__file__).resolve().parent.parent / "scripts/mail.py"
)
mail = importlib.util.module_from_spec(_spec)
sys.modules["fabrik_mail"] = mail
_spec.loader.exec_module(mail)

FULL = """Subject: x
WHAT: the emitter drops overlays
WHERE: scripts/x.py:12
WHEN: 2026-08-30, run N
WHO: fleet owns the consumer
WHY: root cause reproduced — the regex anchors wrong (measured)
HOW: run X; fix direction: anchor it
SYSTEMIC: whole class of anchored regexes, blast radius 3 scripts
"""


def test_full_structure_has_no_gaps():
    assert mail._structure_gaps("finding", FULL) == []


def test_missing_sections_named():
    gaps = mail._structure_gaps("finding", "Subject: x\njust prose, no structure\n")
    for k in ("WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC"):
        assert k in gaps


def test_reply_kind_exempt():
    assert mail._structure_gaps("reply", "short ack prose") == []


def test_headers_matched_loosely():
    body = "**What:** a thing\n- where: f.py:1\nWHEN: today\nwho: me\nWhy: proven\nHow: so\nSystemic: class\n"
    assert mail._structure_gaps("request", body) == []


def test_empty_headers_and_quoted_blocks_do_not_satisfy():
    """MAJOR regression: empty 'WHY:' lines, quoted forwards ('> WHY: x') and code-fence
    templates satisfied the checker — structure without content, or someone else's."""
    empty = "WHAT:\nWHERE:\nWHEN:\nWHO:\nWHY:\nHOW:\nSYSTEMIC:\n"
    assert len(mail._structure_gaps("finding", empty)) == 7
    quoted = "\n".join(
        f"> {k}: real content here"
        for k in ("WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC")
    )
    assert len(mail._structure_gaps("finding", quoted)) == 7
    fenced = (
        "```\n"
        + "\n".join(
            f"{k}: template" for k in ("WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC")
        )
        + "\n```\n"
    )
    assert len(mail._structure_gaps("finding", fenced)) == 7


# ── the two false-verdict classes, both measured live 2026-08-30 ──────────────────

QUALIFIED = """Subject: x
WHAT: the probe manufactures deaths
WHERE: scripts/sysadmin/mcp_health.py:130
WHEN: 2026-08-30
WHO: fleet
WHY (factual root cause, measured — not inferred): the budget is 8s, Claude's is 30s
HOW it bites: a compliant author is told they are non-compliant
SYSTEMIC (the class, never the instance): header-detection with a hard char budget
"""


def test_qualified_headers_are_not_false_flagged():
    """FALSE POSITIVE regression: a header may carry a qualifier.

    The contract itself invites one ("a FACTUAL root cause"), and mail.py's own
    docstring writes 'SYSTEMIC (the class, never just the instance)'. The old
    24-char budget rejected exactly those, so a fully compliant finding was told it
    was missing the sections it actually had.
    """
    assert mail._structure_gaps("finding", QUALIFIED) == []


def test_indented_example_headers_do_not_satisfy():
    """FALSE NEGATIVE regression — the worse direction, and the one that fooled me.

    A mail ABOUT the message contract quotes short example headers as evidence.
    Those are indented illustrations, not sections; counting them certified an
    unstructured mail as compliant (live: my own false-positive report passed the
    checker only because it quoted `WHY:` and `SYSTEMIC (the class):` as examples).
    """
    body = (
        "Subject: about the checker\n"
        "prose explaining the problem, with quoted examples below:\n"
        "    WHAT: example\n"
        "    WHERE: example\n"
        "    WHEN: example\n"
        "    WHO: example\n"
        "    WHY: example\n"
        "    HOW: example\n"
        "    SYSTEMIC: example\n"
    )
    assert len(mail._structure_gaps("finding", body)) == 7, (
        "indented illustrations are not section headers"
    )


def test_header_whose_body_is_a_block_on_following_lines():
    """FALSE POSITIVE #3 (live: my own duplicate-D-041 finding was flagged 'missing WHY').

    Content was required INLINE after the colon, so a section that opens with a
    command block, list or table underneath read as an empty section.
    """
    body = (
        "Subject: x\nWHAT: the thing\nWHERE: f.py:1\nWHEN: today\nWHO: fleet\n"
        "WHY (factual, reproduced):\n"
        "  $ grep -o '^| D-[0-9]*' docs/DECISIONS.md | sort | uniq -d\n"
        "  | D-041\n"
        "HOW: like so\nSYSTEMIC: the class\n"
    )
    assert mail._structure_gaps("finding", body) == []


def test_header_immediately_followed_by_another_header_is_still_empty():
    """The look-ahead must not paper over a genuinely empty section."""
    body = (
        "Subject: x\nWHAT: the thing\nWHERE: f.py:1\nWHEN: today\nWHO: fleet\n"
        "WHY:\nHOW: like so\nSYSTEMIC: the class\n"
    )
    assert mail._structure_gaps("finding", body) == ["WHY"]


# ── two accidental-verdict classes, filed 2026-09-02/03 (01M1H52X, 01M1J0KY) — seen RED first ──


def test_slash_combined_header_credits_both_keys():
    """`WHEN/WHO: 2026-09-02, intel` is the form the corpus itself invites; the checker credited
    only the first key and warned 'missing: WHO' on a compliant finding (01M1H52X)."""
    body = (
        "WHAT: a thing\nWHERE: f.py:1\nWHEN/WHO: 2026-09-02, intel (three sessions)\n"
        "WHY: proven\nHOW: so\nSYSTEMIC: class\n"
    )
    assert mail._structure_gaps("finding", body) == []
    # only the contract's own keys combine: an arbitrary prefix never credits the key (review, pass 1)
    garbage = body.replace("WHEN/WHO:", "abc/WHO:").replace(
        "WHERE: f.py:1", "WHERE: f.py:1\nWHEN: today"
    )
    assert mail._structure_gaps("finding", garbage) == ["WHO"]


def test_a_path_colon_never_credits_a_section_but_a_spaced_dash_does():
    """01M1J0KY: `WHERE — \\`scripts/x.py:496\\`:` once passed because the regex stopped at the
    `:496` colon and read the tail as content, while the six sections written identically were
    flagged — the backtick-colon rule fixed that. Since 2026-09-05 the spaced dash itself is a
    separator (site-provisioner 01M1QWM094Z6S0ZYGPKTB4NPY0), so this body now credits every
    section EXCEPT `WHAT — a` (one character is not content); the colon inside the backticks
    still credits nothing on its own."""
    body = (
        "WHAT — a\nWHERE — `scripts/sync_enforcement_to_projects.py:496`:\nWHEN — today\n"
        "WHO — me\nWHY — proven\nHOW — so\nSYSTEMIC — class\n"
    )
    assert mail._structure_gaps("finding", body) == ["WHAT"]
    colon_only = body.replace("WHERE — `", "WHERE `").replace("WHAT — a", "WHAT: a thing")
    assert "WHERE" in mail._structure_gaps("finding", colon_only)


def test_a_header_ending_in_a_spaced_dash_is_a_header():
    """`SYSTEMIC — the class…` met the D-035 contract in substance and was reported missing
    (site-provisioner 01M1QWM094Z6S0ZYGPKTB4NPY0, 2026-09-05): the checker wanted a colon. A
    spaced em/en dash is a separator; a glued hyphen (`WHY-not`) is not."""
    m = mail
    dashed = "\n".join(f"{k} — content for {k}" for k in m._STRUCTURE_KEYS)
    assert m._structure_gaps("finding", dashed) == []
    en = dashed.replace(" — ", " – ")
    assert m._structure_gaps("finding", en) == []
    # the EARLIEST separator wins: a colon inside dashed content is content (review pass 3)
    colon_inside = dashed.replace("WHY — content for WHY", "WHY — see: the measured cause")
    assert m._structure_gaps("finding", colon_inside) == []
    glued = "\n".join(f"{k}-content" for k in m._STRUCTURE_KEYS)
    assert set(m._structure_gaps("finding", glued)) == set(m._STRUCTURE_KEYS)


_BASE = (
    "WHO: the infra agent\nWHEN: today\nHOW: by hand\nWHY (factual): because\nSYSTEMIC: the class\n"
)


def test_a_spaced_slash_combines_keys_like_a_tight_one():
    """T14.1 (01M1T129A): `WHAT / WHERE:` is what authors actually write — it is the form the
    advisory itself invites by naming keys with slashes — and the tight-only pattern reported
    WHERE missing from a mail that plainly had it.

    Measured across the whole store before the fix: 41 of 4,778 message files use the spaced form
    against 53 using the tight one, so very nearly half of all slash-combined headers were being
    mis-flagged, and the author had no way to tell a real gap from this one. (Four of the 41 were
    sent by the session that then fixed it, each told it had omitted a section it had written.)"""
    for header in (
        "WHAT: the thing\nWHERE: the place",
        "WHAT/WHERE: the thing at the place",
        "WHAT / WHERE: the thing at the place",
        "WHAT / WHERE, artifact by artifact: the thing",
        "WHAT  /  WHERE: extra spaces are still one header",
        "WHAT — the thing\nWHERE — the place",
    ):
        assert mail._structure_gaps("finding", _BASE + header + "\n") == [], header


def test_a_genuinely_missing_section_is_still_reported():
    """...or the widened pattern has simply stopped detecting anything."""
    gaps = mail._structure_gaps("finding", _BASE + "nothing about what or where\n")
    assert set(gaps) == {"WHAT", "WHERE"}, gaps


def test_the_advisory_names_the_rule_not_only_the_doc():
    """The text named the contract's DOC and never the shape a header must take, so an author
    told "missing: WHERE" could not tell a formatting miss from a real omission — which is the
    position the spaced-slash defect above put every one of them in.

    ⚠️ EXECUTED, not grepped. The first cut sliced the SOURCE TEXT of `mail.py` around the
    advisory marker and asserted three substrings — so it passed with the branch that prints it
    made unreachable (`if _gaps:` -> `if False:`, executed). It proved a string literal exists,
    not that anything emits it.
    """
    import subprocess
    import sys as _sys
    import tempfile

    with tempfile.TemporaryDirectory() as root:
        (Path(root) / "fabrik" / "inbox").mkdir(parents=True)
        (Path(root) / "fabrik" / "archive").mkdir(parents=True)
        r = subprocess.run(
            [
                _sys.executable,
                "scripts/mail.py",
                "send",
                "--to",
                "fabrik",
                "--to-agent",
                "infra",
                "--kind",
                "finding",
                "--ack",
                "no",
            ],
            input="## WHAT\nbare headings, not KEY: form\n\n## WHERE\nscripts/mail.py\n",
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "FABRIK_MAIL_ROOT": root},
        )
    assert r.returncode == 0, (r.returncode, r.stderr[:200])
    advisory = r.stderr
    assert "[mail-structure advisory, D-035]" in advisory, f"no advisory emitted: {advisory!r}"
    assert "at the START of a line" in advisory, "the advisory does not say where a key must sit"
    assert "`:` or ` — `" in advisory, "the advisory does not name the separators"
    assert "spaces optional" in advisory, "the advisory does not mention the slash-combined form"
    # ...and it precedes the delivered path, which is the ordering the plan's gate step names
    assert "/inbox/" in r.stdout, r.stdout


def test_there_is_no_body_flag_and_saying_so_costs_stdout_one_line():
    """T14.2 (01M22M5E1): the body has always been stdin-only, and `--body` got argparse's exit 2
    on STDERR with an EMPTY stdout — so a caller piping stdout saw nothing at all. Adding
    `--body-file` then made `--body` a valid argparse PREFIX of it, which silently reinterpreted
    the text as a filename: a worse failure, because it looks like it acted on something."""
    import subprocess
    import sys as _sys

    r = subprocess.run(
        [
            _sys.executable,
            "scripts/mail.py",
            "send",
            "--to",
            "fabrik",
            "--kind",
            "finding",
            "--body",
            "some inline text",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 2, r.returncode
    assert "there is no --body" in r.stdout, f"stdout was {r.stdout!r}"
    assert "STDIN" in r.stdout and "--body-file" in r.stdout
    assert "some inline text" not in r.stdout, "the text was reinterpreted as a filename"


def test_body_file_is_an_accepted_source_for_the_body(tmp_path):
    """The flag exists and reads the file — graded through `main`, not by grepping the parser."""
    import subprocess
    import sys as _sys

    missing = tmp_path / "nope.md"
    r = subprocess.run(
        [
            _sys.executable,
            "scripts/mail.py",
            "send",
            "--to",
            "fabrik",
            "--kind",
            "finding",
            "--body-file",
            str(missing),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 2
    # the delivered-path contract again: a caller parsing stdout must not be told nothing happened
    assert "cannot read --body-file" in r.stdout, f"stdout was {r.stdout!r}"


def test_the_prescribed_trailer_verify_command_is_not_read_as_a_secret():
    """T14.3 (01M25EJZG): `%(trailers:key=Agent-Role,valueonly)` gives the scanner KEY from `key`,
    `=` for the separator and `Agent-Role,valueonly)` as a 20-char value — so the send was REFUSED
    outright, and that command is the one BOTH governance contracts prescribe for verifying a
    trailer block parsed. The check that certifies a commit's provenance could not be quoted in a
    message about commit provenance."""
    for verify in (
        "git log -1 --format='%(trailers:key=Agent-Role,valueonly)'",
        "%(trailers:key=Agent-Context,valueonly)",
        "git log --format='%h %s %(trailers:key=Agent-Role)'",
    ):
        assert mail._secret_level(verify) is None, (verify, mail._secret_level(verify))
    clause = Path("CLAUDE.md").read_text(encoding="utf-8").split("⚠️ **And a THIRD trap")[1][:986]
    assert mail._secret_level(clause) is None, "the governance clause itself cannot be mailed"


def test_the_carve_does_not_blunt_the_scanner():
    """⚠️ The narrowest possible carve is a fixed git-internal PREFIX, not a relaxation of the
    value pattern — loosening `\\S{16,}` to exclude commas or parens would let any secret hide by
    appending one. Real credentials must still be refused."""
    for secret in (
        "ANTHROPIC_API_KEY=sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY",
        "PASSWORD: correct-horse-battery-staple-1234",
    ):
        assert mail._secret_level(secret) == "high", secret
    # ⚠️ ALL SIX KEYWORDS, because the first cut of this grader asserted the safety property using
    # `SECRET` — one of the five for which it happened to hold — and so certified a property the
    # code did not have. `KEY` is the ONE keyword with no `_SECRET_LOW` counterpart, and it is
    # exactly the keyword the git token supplies, so the carve had been cut around the only one
    # with zero backstop: `trailers:KEY=<credential>` scored None. No refusal, no warning,
    # delivered. A grader that samples the safe cases certifies nothing.
    secret = "Zx82Kf9mQpLr7TnV4bWq"
    for keyword in ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "PWD"):
        assert mail._secret_level(f"trailers:{keyword}={secret}") == "high", keyword
    # ...and the carve has a LEFT boundary: it is the whole git token `%(trailers:`, not nine
    # characters that any text can end with.
    for prefix in ("mytrailers:", "X-Trailers:", "https://internal/p/trailers:", "_trailers:"):
        assert mail._secret_level(f"{prefix}KEY={secret}") == "high", prefix


def test_both_contracts_carry_the_third_trap_byte_identically():
    """The trailer guidance is a SHARED clause: `CLAUDE.md` is the hub's and
    `templates/governance/CLAUDE.md` is distributed to ~46 repos. A trap named in one and not the
    other is a contract that means different things in different repos."""
    a = Path("CLAUDE.md").read_text(encoding="utf-8")
    b = Path("templates/governance/CLAUDE.md").read_text(encoding="utf-8")
    marker = "⚠️ **And a THIRD trap"
    assert marker in a and marker in b, "the third trap is missing from one of the two contracts"
    ca = a[a.index(marker) : a.index("Example:", a.index(marker))]
    cb = b[b.index(marker) : b.index("Example:", b.index(marker))]
    assert ca == cb, "the shared clause has drifted between the two contracts"
    assert "interpret-trailers --parse" in ca, "the clause does not name the verify command"


def test_a_body_file_that_is_not_utf8_refuses_on_stdout_rather_than_tracebacking(tmp_path):
    """`UnicodeDecodeError` is a `ValueError`, not an `OSError`, so it escaped the handler AND
    every arm of `main`'s error ladder — a raw traceback with an EMPTY stdout, which is precisely
    the failure `--body-file` was added to remove."""
    import subprocess
    import sys as _sys

    bad = tmp_path / "cp1252.md"
    bad.write_bytes(b"WHAT: \xff\xfe bad bytes\n")
    r = subprocess.run(
        [
            _sys.executable,
            "scripts/mail.py",
            "send",
            "--to",
            "fabrik",
            "--kind",
            "finding",
            "--body-file",
            str(bad),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "FABRIK_MAIL_ROOT": str(tmp_path / "root")},
    )
    assert r.returncode == 2, r.returncode
    assert "cannot read --body-file" in r.stdout, f"stdout was {r.stdout!r}"
    assert "Traceback" not in r.stderr, r.stderr[:200]


def test_the_send_contract_line_never_hijacks_another_subcommands_stdout():
    """`read` and `list` put their PAYLOAD on stdout, so an ungated contract line meant
    `msg=$(mail.py read "$id")` with a malformed id received a paragraph about stdin AS the
    message body — the "looks like it worked on something" failure one branch later exists to
    avoid, reintroduced one branch earlier."""
    import subprocess
    import sys as _sys

    for argv in (["list", "--bogus-flag"], ["read"]):
        r = subprocess.run(
            [_sys.executable, "scripts/mail.py", *argv],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert r.returncode == 2, (argv, r.returncode)
        assert "mail.py send:" not in r.stdout, (argv, r.stdout[:160])
    # ...and `send` itself still gets it
    r = subprocess.run(
        [_sys.executable, "scripts/mail.py", "send", "--to", "fabrik"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert "mail.py send:" in r.stdout, r.stdout[:160]


def test_help_prints_cleanly_and_exits_zero():
    """argparse raises `SystemExit(0)` for --help; the interceptor must not print over it."""
    import subprocess
    import sys as _sys

    for argv in (["--help"], ["send", "--help"]):
        r = subprocess.run(
            [_sys.executable, "scripts/mail.py", *argv],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert r.returncode == 0, (argv, r.returncode)
        assert "mail.py send: the body is read from STDIN" not in r.stdout, argv


def test_the_repo_s_own_multi_key_trailer_literal_is_deliverable():
    """The multi-key form is read FROM DISK, not retyped — a grader that retypes the
    literal certifies its own copy and survives the command text drifting away from it.
    Round 1's carve refused this exact line: the second `key=` is preceded by
    `Agent-Role,`, so a `(?<!%\\(trailers:)` lookbehind never applied."""
    src = Path(__file__).resolve().parent.parent / "commands/_sources/fabrik-execute-plan.md"
    lits = [
        ln.strip()
        for ln in src.read_text(encoding="utf-8").splitlines()
        if "%(trailers:" in ln and ln.count("key=") >= 2
    ]
    assert lits, "the multi-key trailer literal vanished from fabrik-execute-plan.md"
    for lit in lits:
        assert mail._secret_level(lit) is None, f"repo's own command refused: {lit}"


def test_a_credential_in_an_unterminated_trailer_token_is_still_refused():
    """The carve's own interior. `KEY` is the one keyword of the six with no _SECRET_LOW
    backstop, so a hole here scores None — delivered silently, no refusal, no warning.
    Round 1 narrowed this hole; it did not close it."""
    secret = "Zx82Kf9mQpLr7TnV4bWq"
    for prefix in (
        "%(trailers:",
        "%%(trailers:",
        "%(TRAILERS:",
        "x%(trailers:",
        "mytrailers:",
        "X-Trailers:",
        "trailers:",
        "",
    ):
        for kw in ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "PWD"):
            assert mail._secret_level(f"{prefix}{kw}={secret}") == "high", (
                f"{prefix}{kw}= delivered a credential"
            )


def test_a_body_file_that_is_not_a_regular_file_is_bounded(tmp_path):
    """`is_file()` is False for a FIFO and for a device, so a stat-based guard short-circuits
    and the unbounded read runs anyway — and `<(cmd)`, the idiomatic shell form, IS a FIFO."""
    import subprocess

    fifo = tmp_path / "f"
    os.mkfifo(fifo)
    writer = subprocess.Popen(
        [sys.executable, "-c", f"open({str(fifo)!r},'w').write('x'*{mail.MAX_BODY * 4})"],
    )
    try:
        root = tmp_path / "root"
        proc = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent.parent / "scripts/mail.py"),
                "send",
                "--to",
                "fabrik",
                "--kind",
                "finding",
                "--body-file",
                str(fifo),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "FABRIK_MAIL_ROOT": str(root)},
        )
    finally:
        writer.kill()
        writer.wait()
    assert "body cap" in proc.stdout, f"stdout was {proc.stdout!r} / stderr {proc.stderr!r}"
    assert "Traceback" not in proc.stderr, proc.stderr
