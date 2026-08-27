"""Behaviour tests for `scripts/rivals_run.py` — the `/fabrik-rivals` hub-side driver.

This file exists because a review found 446 lines of driver shipped with ZERO tests — and the three
things it tests are precisely the three whose whole job is catching silent failure: the pre-flight,
the LLM subprocess wrapper, and the dossier renderer. Every test below pins a defect that was
reproduced live, not a hypothetical.

The driver is loaded by path (it is a `scripts/` CLI, not an importable package) and its module-level
`sys.path` insert makes the vendored engine importable, so no network, no keys and no spend are
involved anywhere in this file.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("rivals_run", REPO / "scripts" / "rivals_run.py")
assert _spec and _spec.loader
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)


def _legs() -> dict[str, object]:
    return {"firecrawl": object(), "exa": object(), "brave": object()}


def _est(free: str = "0") -> dict[str, Decimal]:
    return {"firecrawl": Decimal("0.05"), "exa": Decimal("0.01"), "brave": Decimal(free)}


def _preflight(**over):
    kw = {
        "budget": Decimal("10"),
        "legs": _legs(),
        "leg_estimates": _est(),
        "job_id": "j1",
        "checkpoint_dir": REPO / ".tmp" / "rivals" / "t",
        "product_type": "saas",
    }
    kw.update(over)
    return rr._preflight(**kw)


# ── the pre-flight: every trap that would otherwise yield a plausible EMPTY dossier ──────────


def test_budget_zero_is_rejected_not_read_as_unlimited():
    """THE fail-silent-green trap. The engine documents `total_budget_usd=0`/absent as "run NO
    research" while STILL returning a Dossier — so an operator who reads the standing "no ceiling"
    policy as "pass 0 for unlimited" gets an empty dossier that reads as a finished scan."""
    with pytest.raises(rr.PreflightError) as e:
        _preflight(budget=Decimal("0"))
    msg = str(e.value)
    assert "0" in msg and "never 0" in msg, "the error must name the fix, not just complain"
    assert rr.DEFAULT_BUDGET_USD in msg, (
        "it must point at the large-number spelling of 'no ceiling'"
    )
    # ...and a real ceiling passes.
    assert any("real ceiling" in line for line in _preflight(budget=Decimal("1")))


def test_a_negative_budget_is_rejected_too():
    """`<= 0`, not `== 0` — a negative ceiling is the same unasked question with a different sign."""
    with pytest.raises(rr.PreflightError):
        _preflight(budget=Decimal("-1"))


def test_free_leg_must_be_estimated_at_or_below_zero():
    """`brave` is the free leg. A positive estimate for it breaks the engine's ceiling arithmetic
    from the very first call — silently, because nothing raises."""
    with pytest.raises(rr.PreflightError, match="brave"):
        _preflight(leg_estimates=_est(free="0.02"))


def test_legs_keys_must_match_the_packs_leg_names():
    """The shipped packs name their legs `firecrawl`/`exa`/`brave`; a mismatch is the one wiring bug
    the engine DOES raise on, at entry. Catching it here names the fix instead of a stack trace."""
    bad = _legs()
    del bad["exa"]
    with pytest.raises(rr.PreflightError, match="exa"):
        _preflight(legs=bad)


def test_every_wired_leg_must_carry_an_estimate():
    """A missing estimate silently disables the ceiling for that leg."""
    est = _est()
    del est["firecrawl"]
    with pytest.raises(rr.PreflightError, match="firecrawl"):
        _preflight(leg_estimates=est)


def test_empty_job_id_is_rejected():
    """`job_id` is the double-book guard: without it a resume can re-bill completed work."""
    with pytest.raises(rr.PreflightError, match="job_id"):
        _preflight(job_id="   ")


def test_checkpoint_dir_must_be_repo_local():
    """The engine's constraint is a repo-local `.tmp`, never `/tmp` — a tmpfs reboot would drop the
    checkpoints that make a resume free."""
    with pytest.raises(rr.PreflightError, match="outside the repo"):
        _preflight(checkpoint_dir=Path("/tmp/rivals"))


def test_scaffold_types_are_aliased_and_unknown_types_are_rejected():
    """The engine's product-type vocabulary is its OWN, not the fabrik `SCAFFOLD_TYPES` strings, so
    a caller can pass either. `wordpress` is a real scaffold type with no engine equivalent."""
    assert rr._resolve_product_type("chrome-extension") == "extension"
    assert rr._resolve_product_type("python-api") == "headless-api"
    assert rr._resolve_product_type("saas") == "saas", "the engine's own vocabulary passes through"
    with pytest.raises(rr.PreflightError, match="wordpress"):
        _preflight(product_type=rr._resolve_product_type("wordpress"))


def test_every_scaffold_alias_lands_in_the_engines_vocabulary():
    """A mapping row that points at a value the engine does not accept would be rejected at
    pre-flight for a caller who did everything right."""
    for scaffold, product in rr.SCAFFOLD_TO_PRODUCT_TYPE.items():
        assert product in rr.PRODUCT_TYPES, f"{scaffold} -> {product} is not an engine product_type"


# ── the renderer: it reads an LLM-shaped dict, so it must never raise and never be injectable ──

HOSTILE: dict[str, dict] = {
    "empty": {},
    "competitors None": {"competitors": None},
    "competitor is a bare string": {"competitors": ["just-a-string"]},
    "competitor with None fields": {"competitors": [{"name": None, "url": None}]},
    "matrix cells is a list": {"feature_matrix": {"columns": ["A"], "rows": ["r"], "cells": []}},
    "matrix cell is a string": {
        "feature_matrix": {"columns": ["A"], "rows": ["r"], "cells": {"r␟A": "OK"}}
    },
    "beat quotes None": {"beat_list": [{"theme": "x", "quotes": None}]},
    "beat_list is a string": {"beat_list": "nope"},
    "pricing models None": {"pricing": {"models": None}},
    "white_space is not a dict": {"white_space": "nope"},
    "review_signal is not a list": {"review_signal": "nope"},
}


@pytest.mark.parametrize("name", list(HOSTILE))
def test_renderer_never_raises_on_any_engine_shape(name):
    """`render_dossier_md` runs AFTER the money is spent. Two of these shapes raised
    `AttributeError` before this review — a bare-string competitor and a non-dict `white_space` —
    and a raise there used to destroy BOTH artifacts of a paid run."""
    out = rr.render_dossier_md(HOSTILE[name])
    assert out.startswith("# Rivals dossier"), f"{name} produced no dossier header"


def test_a_zero_rival_scan_is_labelled_a_failure_not_an_empty_market():
    """The single most misreadable outcome: an empty market and a failed scan look identical."""
    out = rr.render_dossier_md({"market": "m", "competitors": []})
    assert "FAILED scan" in out and "not an empty market" in out


def test_unverified_rivals_are_marked_and_named():
    """The engine sets `verified` per rival; on the live tuning run 5 of 12 were False ("No page
    text retrieved"). An unconfirmed name sitting among real ones is how a fabricated competitor
    reaches a spec."""
    out = rr.render_dossier_md(
        {
            "competitors": [
                {"name": "Real", "url": "https://r", "verified": "True", "positioning": "p"},
                {"name": "Ghost", "url": "https://g", "verified": "False", "positioning": ""},
            ]
        }
    )
    assert "1 unconfirmed" in out, "the count must be stated"
    assert "Ghost" in out.split("unconfirmed")[1], "the unconfirmed rival must be NAMED"
    assert "❓" in out and "✅" in out, "both states must be visually distinguishable"


def test_a_bare_string_competitor_is_surfaced_not_silently_dropped():
    """Dropping it would make the rendered count disagree with the engine's own census — a quieter
    but worse failure than raising."""
    out = rr.render_dossier_md({"competitors": ["weird-shape"]})
    assert "weird-shape" in out
    assert "1 unconfirmed" in out


def test_table_cells_cannot_be_broken_out_of():
    """`_s()` escaped `|` but NOT `\\n`, so a rival name or positioning string could inject a
    markdown heading into a document a spec gets decided on — and this text is LLM- and web-sourced,
    exactly the untrusted input the command's injection fragment warns about."""
    out = rr.render_dossier_md(
        {
            "competitors": [
                {
                    "name": "A\nB",
                    "url": "u",
                    "verified": "True",
                    "positioning": "x\n## FAKE HEADING\n| evil | row |",
                }
            ]
        }
    )
    assert "\n## FAKE HEADING" not in out, "a newline escaped the table and injected a heading"
    assert "\n| evil | row |" not in out, "a newline injected a fabricated table row"
    assert "FAKE HEADING" in out, "the text must still be VISIBLE, just neutralised"


def test_pipes_are_escaped_so_a_name_cannot_add_columns():
    out = rr.render_dossier_md(
        {"competitors": [{"name": "Ev|il", "url": "u", "verified": "True", "positioning": "a|b"}]}
    )
    assert "Ev\\|il" in out


def test_matrix_states_render_from_the_unit_separator_key():
    """The engine keys `cells` "<row>\\u241f<col>" (U+241F UNIT SEPARATOR) with a dict carrying
    `state`. Guessing "<row>|<col>" rendered a full grid of ❓ — a lookup bug that reads as
    'nothing is known about any rival', which is data, not an error."""
    d = {
        "competitors": [{"name": "R", "url": "u", "verified": "True", "positioning": ""}],
        "feature_matrix": {
            "columns": ["R"],
            "rows": ["OCR"],
            "cells": {"OCR␟R": {"state": "✅", "freshness": ""}},
        },
    }
    row = [ln for ln in rr.render_dossier_md(d).splitlines() if ln.startswith("| OCR ")][0]
    assert "✅" in row, f"the real state did not render: {row!r}"
    assert "❓" not in row


def test_greenfield_empty_match_is_explained_not_left_blank():
    """`match=0` is CORRECT for `us=None` (nothing to lack). Left blank it reads as a failure."""
    out = rr.render_dossier_md({"match_list": []})
    assert "greenfield" in out.lower() and "EXPECTED" in out


def test_beat_is_labelled_tier_c():
    """BEAT is deep-research's review cards — the engine never held the raw page, so it is
    corroboration-gated, NOT quote-re-grounded like the matrix. Claiming otherwise is the overclaim
    the engine's own review had to scope out of its README."""
    out = rr.render_dossier_md({"beat_list": [{"theme": "t", "weight": 1, "quotes": ["q"]}]})
    assert "Tier-C" in out


def test_truncated_is_reported_as_budget_bound_not_completeness():
    out = rr.render_dossier_md({"truncated": True})
    assert "truncated" in out and "Partial by budget" in out


def test_scope_disclaimer_is_always_present():
    """A dossier must never be read as evidence that a market is big enough."""
    assert "NOT market-sizing" in rr.render_dossier_md({})


# ── the LLM subprocess: a wedged `claude` must not hang an unattended run ────────────────────


def test_llm_call_is_wall_clock_bounded(monkeypatch):
    """`communicate()` takes no timeout and blocks forever; the engine's ceiling bounds SPEND, not
    wall-clock, and the retry loop never reaches its next attempt. Proven live with a stub that
    never exits. Here the whole 3-attempt loop must finish well inside the test's own budget."""
    monkeypatch.setattr(rr, "_LLM_TIMEOUT_S", 0.3)
    llm = rr._make_llm("sonnet")
    # Capture the REAL spawner before patching: a stub that calls the name it is replacing
    # recurses forever, and `RecursionError` is not the failure this test claims to prove.
    real_exec = asyncio.create_subprocess_exec
    real_sleep = asyncio.sleep

    async def _stub(*_a, **_k):
        return await real_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(rr.asyncio, "create_subprocess_exec", _stub)
    # ...and the same capture for `sleep`: the lambda below called `asyncio.sleep`, which by then
    # WAS the lambda. Two adjacent lines, the same self-referential-stub bug.
    monkeypatch.setattr(rr.asyncio, "sleep", lambda *_a, **_k: real_sleep(0))

    async def _go():
        with pytest.raises(RuntimeError, match="after 3 attempts"):
            await llm("hello")

    asyncio.run(asyncio.wait_for(_go(), timeout=20))


def test_llm_raises_rather_than_returning_empty_after_exhausting_retries():
    """Both consumers sit behind never-raise boundaries that DEGRADE on an exception — an honest
    partial. Returning "" would be taken as a real (empty) answer and silently poison synthesis."""
    src = (REPO / "scripts" / "rivals_run.py").read_text(encoding="utf-8")
    assert 'raise RuntimeError(f"claude -p failed after 3 attempts' in src
    assert 'return ""' not in src.split("def _make_llm")[1].split("def ")[0]


def test_the_llm_is_subscription_claude_p_and_never_a_metered_api():
    """Operator directive: no metered LLM API and no agents for this command. `ANTHROPIC_API_KEY`
    is reserved for `fabrik ai generate` and must never reach this path."""
    src = (REPO / "scripts" / "rivals_run.py").read_text(encoding="utf-8")
    assert "openrouter.ai" not in src, "a metered LLM endpoint reappeared"
    # The NAME appears in the docstring saying it must never be used here, so assert on the USE:
    # no env read, no header. A bare substring check matched our own prose and failed vacuously.
    # Assert on the USE, not the NAME. The docstring deliberately NAMES ANTHROPIC_API_KEY to
    # record that it must never reach this path; a substring check matched our own prose and
    # failed on the very sentence that states the rule. What matters is that nothing READS it.
    assert 'getenv("ANTHROPIC_API_KEY"' not in src
    assert "ANTHROPIC_API_KEY" not in src.replace("`ANTHROPIC_API_KEY`", ""), (
        "the key is referenced outside documentary prose"
    )
    assert "pick_models" not in src, "pool/agent selection reappeared"
    assert set(rr.CLAUDE_P_MODELS) == {"fable", "opus", "sonnet", "haiku"}


def test_the_llm_actually_invokes_claude_p_with_the_expected_argv(monkeypatch):
    """BEHAVIOURAL, not a source-text grep. The previous version asserted the literal
    `'"claude", "-p"'` appeared in the file — which `ruff format` then legally split one-arg-per-line,
    failing a test whose subject had not changed. Capture the real argv instead."""
    seen: dict = {}
    real_exec = asyncio.create_subprocess_exec

    async def _capture(*argv, **kw):
        seen["argv"] = list(argv)
        seen["cwd"] = kw.get("cwd")
        return await real_exec(
            sys.executable,
            "-c",
            'print(\'{"is_error": false, "result": "OK"}\')',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(rr.asyncio, "create_subprocess_exec", _capture)
    assert asyncio.run(rr._make_llm("haiku")("a", "b")) == "OK"
    argv = seen["argv"]
    assert argv[0] == "claude" and argv[1] == "-p", f"not a claude -p invocation: {argv[:2]}"
    assert "--model" in argv and argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "a\n\nb" in argv, "the two positional parts must be JOINED, not dropped"
    assert seen["cwd"] and "_neutral_cwd" in str(seen["cwd"]), "must not run in the repo tree"


def test_claude_p_runs_from_a_neutral_cwd():
    """`claude -p` loads the CLAUDE.md of whatever tree it runs in — 33,953 cache-creation tokens
    from /opt/fabrik vs 11,611 from an empty dir, and an agent contract is not context for
    summarising review excerpts."""
    src = (REPO / "scripts" / "rivals_run.py").read_text(encoding="utf-8")
    body = src.split("def _make_llm")[1].split("\ndef ")[0]
    assert "_neutral_cwd" in body and "cwd=str(neutral)" in body


# ── the ordering guarantee: a rendering bug must never cost a PAID run its data ──────────────


def test_the_json_is_written_before_anything_that_can_raise(tmp_path, monkeypatch, capsys):
    """The money is already spent by the time we have a payload. Rendering used to run FIRST, so an
    AttributeError on an odd shape destroyed both artifacts and left a traceback for a paid scan."""
    boom = {"market": "m", "competitors": [{"name": "R", "url": "u", "verified": "True"}]}
    monkeypatch.setattr(
        rr, "render_dossier_md", lambda _d: (_ for _ in ()).throw(RuntimeError("render bug"))
    )
    out = tmp_path / "d"
    args = rr._parse_args(["--market", "m", "--greenfield", "--out", str(out)])

    # exercise the emit tail exactly as `_run` does, with a deliberately broken renderer
    data = boom
    o = Path(args.out)
    o.parent.mkdir(parents=True, exist_ok=True)
    o.with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        md = rr.render_dossier_md(data)
    except Exception as exc:  # noqa: BLE001 — mirrors the driver's own guard
        md = f"# Rivals dossier — {data.get('market', '?')}\n\n> ⚠️ ({type(exc).__name__})\n"
    o.with_suffix(".md").write_text(md, encoding="utf-8")

    assert json.loads(o.with_suffix(".json").read_text())["competitors"][0]["name"] == "R"
    assert "⚠️" in o.with_suffix(".md").read_text()


def test_driver_source_writes_json_before_rendering():
    """Pins the ORDER itself, since that is the real guarantee — the defensive renderer is the belt,
    this is the brace."""
    src = (REPO / "scripts" / "rivals_run.py").read_text(encoding="utf-8")
    tail = src.split("data = dossier.to_dict()")[1]
    assert tail.index('with_suffix(".json").write_text') < tail.index("render_dossier_md(data)"), (
        "the paid JSON must land on disk BEFORE the renderer, which can raise"
    )


def test_main_returns_2_on_a_wiring_error_and_never_a_traceback(capsys):
    """A wiring bug must be a NAMED non-zero exit, not a stack trace."""
    rc = rr.main(["--market", "x", "--greenfield", "--budget", "0", "--preflight-only"])
    assert rc == 2
    assert "WIRING ERROR (nothing was spent)" in capsys.readouterr().err


def test_main_returns_0_on_a_sound_preflight(capsys):
    rc = rr.main(["--market", "x", "--greenfield", "--preflight-only"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "wiring is sound" in out and "exiting without spending" in out


# ── pass 2: sinks the first escaping fix did not cover ──────────────────────────────────────


def test_a_rival_url_cannot_break_out_of_its_markdown_link():
    """The URL is LLM- and web-sourced and went RAW into `[name](url)`. A value like
    `http://e)vil](javascript:alert(1))` closes the link early and injects a `javascript:` target
    into a document the operator is invited to click."""
    out = rr.render_dossier_md(
        {
            "competitors": [
                {
                    "name": "X",
                    "url": "http://e)vil](javascript:alert(1))",
                    "verified": "True",
                    "positioning": "p",
                }
            ]
        }
    )
    assert "](javascript:" not in out, "a javascript: target was injected"
    assert "%29" in out, "parens must be percent-encoded so the link cannot be closed early"


def test_a_non_web_scheme_is_never_rendered_as_a_link():
    """`javascript:`/`data:` targets are dropped entirely rather than linked."""
    out = rr.render_dossier_md(
        {"competitors": [{"name": "Y", "url": "javascript:alert(1)", "verified": "True"}]}
    )
    assert "](javascript" not in out
    assert "Y ⚠️" in out, "the rival must still be listed, just not clickable"


def test_the_market_name_cannot_inject_a_heading():
    """`market` reaches an H1. It comes from the CLI or a project-authored brief — same untrusted
    class as the table cells, a different sink."""
    assert "\n## INJECTED" not in rr.render_dossier_md({"market": "m\n## INJECTED"})


def test_a_missing_field_renders_empty_not_the_word_none():
    """`_s(None)` returned the literal string "None", so a rival with no positioning advertised
    "None" as its positioning in a document a spec gets decided on."""
    out = rr.render_dossier_md(
        {
            "competitors": [
                {"name": "Z", "url": "https://z", "verified": "True", "positioning": None}
            ]
        }
    )
    row = [ln for ln in out.splitlines() if ln.startswith("| [Z")][0]
    assert "None" not in row, f"a missing field rendered as the word None: {row!r}"


# ── the untrusted-input-sink class, closed STRUCTURALLY ──────────────────────────────────────

# Every field the renderer interpolates, with a payload that tries to escape its context. This is
# table-driven on purpose: the class was reopened twice (first only table cells were escaped, then
# the URL and the H1, then the BEAT weight and the header primitives), so the guard has to be a
# sweep over ALL sinks rather than one test per defect remembered after the fact.
SINKS: dict[str, dict] = {
    "competitor name": {
        "competitors": [{"name": "n\n## X", "url": "https://u", "verified": "True"}]
    },
    "competitor positioning": {
        "competitors": [
            {"name": "n", "url": "https://u", "verified": "True", "positioning": "p\n## X"}
        ]
    },
    "competitor url": {
        "competitors": [{"name": "n", "url": "https://u\n## X", "verified": "True"}]
    },
    "market": {"market": "m\n## X"},
    "product_type": {"product_type": "saas\n## X"},
    "spend_usd": {"spend_usd": "1\n## X"},
    "partial": {"partial": "f\n## X"},
    "truncated": {"truncated": "f\n## X"},
    "matrix column": {"feature_matrix": {"columns": ["c\n## X"], "rows": ["r"], "cells": {}}},
    "matrix row": {"feature_matrix": {"columns": ["c"], "rows": ["r\n## X"], "cells": {}}},
    "matrix cell state": {
        "feature_matrix": {"columns": ["c"], "rows": ["r"], "cells": {"r␟c": {"state": "s\n## X"}}}
    },
    "match feature": {"match_list": [{"feature": "f\n## X", "detail": "d"}]},
    "match detail": {"match_list": [{"feature": "f", "detail": "d\n## X"}]},
    "beat theme": {"beat_list": [{"theme": "t\n## X", "weight": 1, "quotes": []}]},
    "beat weight": {"beat_list": [{"theme": "t", "weight": "1\n## X", "quotes": []}]},
    "beat n_sources": {
        "beat_list": [{"theme": "t", "weight": 1, "n_sources": "2\n## X", "quotes": []}]
    },
    "beat quote": {"beat_list": [{"theme": "t", "weight": 1, "quotes": ["q\n## X"]}]},
    "pricing competitor": {"pricing": {"models": [{"competitor": "c\n## X", "model": "m"}]}},
    "pricing evidence": {"pricing": {"models": [{"competitor": "c", "evidence": "e\n## X"}]}},
    "pricing source_url": {
        "pricing": {"models": [{"competitor": "c", "source_url": "https://u\n## X"}]}
    },
    "white_space need": {"white_space": {"needs": [{"need": "n\n## X", "detail": "d"}]}},
    "white_space detail": {"white_space": {"needs": [{"need": "n", "detail": "d\n## X"}]}},
}


@pytest.mark.parametrize("sink", list(SINKS))
def test_no_payload_field_can_inject_markdown_structure(sink):
    """Every value in the dossier is LLM- or web-sourced. A newline in ANY of them must not open a
    heading, a table row, or any other block-level structure in a document a spec is decided on."""
    out = rr.render_dossier_md(SINKS[sink])
    # ⚠️ Assert on the STRUCTURE, not on a literal needle. The first version looked for "\n## X" and
    # passed on the URL sink because `_url` had percent-encoded the space to "\n##%20X" — the
    # newline still broke the link open, but the needle no longer matched. A sanitiser that mangles
    # the payload must never be able to launder an escape past the test.
    assert "\n#" not in out.replace("\n# Rivals dossier", "").replace("\n## ", "\x00"), (
        f"{sink}: a raw newline reached the output and could open a block"
    )
    for line in out.splitlines():
        assert not line.startswith("## X") and not line.startswith("##%20X"), (
            f"{sink}: injected a heading line: {line!r}"
        )
    assert "X" in out, f"{sink}: the text vanished instead of being neutralised"


def test_a_missing_search_key_fails_loud_and_names_it():
    """A missing search key raises NOWHERE: the leg fails, the engine degrades, and the run returns
    an empty dossier with `partial=True` — the same fail-silent-green shape as budget-0. The engine
    cannot tell you WHICH key, so the pre-flight must."""
    with pytest.raises(rr.PreflightError, match="DEFINITELY_NOT_SET_KEY"):
        _preflight(required_keys=("DEFINITELY_NOT_SET_KEY",))
    msg = ""
    try:
        _preflight(required_keys=("DEFINITELY_NOT_SET_KEY",))
    except rr.PreflightError as e:
        msg = str(e)
    assert "never hardcode" in msg and "NEVER prompt" in msg, (
        "the remedy must forbid prompting for a key, not just report the absence"
    )


def test_the_key_check_is_not_claimed_when_it_did_not_run():
    """`search keys present ()` is a green checklist line for a question nobody asked — the exact
    shape of pass this whole pre-flight exists to prevent."""
    lines = _preflight(required_keys=())
    assert not any("search keys present" in ln for ln in lines)
    lines2 = _preflight(required_keys=("PATH",))  # PATH is always set
    assert any("search keys present (PATH)" in ln for ln in lines2)


def test_every_line_boundary_character_is_flattened_not_just_crlf():
    """Guarding only `\\r\\n` left form-feed, vertical-tab, U+2028 and U+2029 able to open a line for
    any consumer that uses `str.splitlines()` — which is every line-oriented reader of this dossier,
    including this module's own checks and the gate's doc scanners. A sanitiser whose definition of
    "a line" differs from its readers' is a sanitiser with a hole. 24 combinations leaked before."""
    sinks = {
        "name": lambda v: {
            "competitors": [{"name": f"a{v}## Z", "url": "https://u", "verified": "True"}]
        },
        "url": lambda v: {
            "competitors": [{"name": "a", "url": f"https://u{v}## Z", "verified": "True"}]
        },
        "positioning": lambda v: {
            "competitors": [
                {"name": "a", "url": "https://u", "verified": "True", "positioning": f"p{v}## Z"}
            ]
        },
        "market": lambda v: {"market": f"m{v}## Z"},
        "beat quote": lambda v: {
            "beat_list": [{"theme": "t", "weight": 1, "quotes": [f"q{v}## Z"]}]
        },
        "pricing evidence": lambda v: {
            "pricing": {"models": [{"competitor": "c", "evidence": f"e{v}## Z"}]}
        },
    }
    leaks = []
    for sname, mk in sinks.items():
        for ch in rr._LINE_BOUNDARIES:
            out = rr.render_dossier_md(mk(ch))
            for line in out.splitlines():
                if line.startswith(("## Z", "##%20Z")):
                    leaks.append(f"{sname}+U+{ord(ch):04X}")
                    break
    assert not leaks, f"line-boundary injection survived in {len(leaks)} combos: {leaks[:8]}"


def test_the_flatten_table_is_derived_not_hand_listed():
    """Hand-listing the characters is how `\\f`/`\\v`/U+2028/U+2029 were missed the first time. The
    table is derived from `str.splitlines()` itself, so it cannot drift from the definition."""
    assert len(rr._LINE_BOUNDARIES) >= 8
    for ch in ("\n", "\r", "\f", "\v", "\x1c", "\x1d", "\x1e", "\x85", " ", " "):
        assert ch in rr._LINE_BOUNDARIES, f"U+{ord(ch):04X} missing from the derived table"
