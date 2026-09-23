"""Pins on the D-335 review loop as a Claude Code workflow script (chunk 5, D-347/D-348).

The script is JavaScript the Workflow tool runs; nothing here executes it. These graders pin the
contract the command sources and the reviewer brief rely on: the file exists where the sources
point, its ``meta`` block is a pure literal (the tool refuses anything else), every finder call
returns a schema that REQUIRES ``files_read`` (the coverage-overclaim guard, § 4.9 finding 10), every
seat is the ``fabrik-reviewer`` agent type on a cheap model (D-344), the script never resumes a run
(resume re-runs a fan-out — finding 22), and the two partitioned sources plus the brief name it.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".claude" / "workflows" / "fabrik-review-loop.js"
SOURCES = [
    ROOT / "commands" / "_sources" / "fabrik-review.md",
    ROOT / "commands" / "_sources" / "fabrik-repo-review.md",
]
BRIEF = ROOT / "commands" / "_agents" / "fabrik-reviewer.md"
DOC = ROOT / "docs" / "reference" / "review-loop-workflow.md"
SCRIPT_PATH_TEXT = "/opt/fabrik/.claude/workflows/fabrik-review-loop.js"


def _script() -> str:
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    return SCRIPT.read_text(encoding="utf-8")


def test_the_meta_block_is_the_first_statement_and_a_pure_literal() -> None:
    body = _script()
    stripped = re.sub(r"^(//[^\n]*\n|/\*.*?\*/\s*|\s+)*", "", body, count=1, flags=re.S)
    assert stripped.startswith("export const meta = {"), stripped[:80]
    meta = stripped[: stripped.index("\n}\n") + 3]
    for forbidden in ("${", "(", "..."):
        assert forbidden not in meta, f"meta must be a pure literal, found {forbidden!r}"
    assert "name: 'fabrik-review-loop'" in meta


def test_every_finder_schema_requires_files_read_and_candidates() -> None:
    body = _script()
    m = re.search(r"const FINDINGS\s*=\s*\{(.*?)\n\}", body, re.S)
    assert m, "no FINDINGS schema"
    required = re.search(r"required:\s*\[([^\]]*)\]", m.group(1))
    assert required, "FINDINGS has no required list"
    for field in ("'files_read'", "'candidates'", "'notes'"):
        assert field in required.group(1), f"FINDINGS must require {field}"


def test_every_seat_is_the_reviewer_agent_on_a_cheap_model_and_no_run_is_resumed() -> None:
    body = _script()
    sites = [m.start() for m in re.finditer(r"\bagent\(", body)]
    assert len(sites) == 2, (
        f"exactly two agent() sites (finder map, one refuter per slice), found {len(sites)}"
    )
    for start in sites:
        opts = body[start : _call_end(body, start)]
        assert "agentType: 'fabrik-reviewer'" in opts, (
            "every seat is the fabrik-reviewer agent type"
        )
        assert re.search(r"model: (?:m|'sonnet'),", opts), (
            "seats run on the cheap models only (D-344)"
        )
        assert re.search(r"effort: '(?:low|medium|high)'", opts), (
            "every seat names its effort — an unnamed one inherits the session's (§ 4.9 finding 43)"
        )
    assert "'opus'" not in body and "'fable'" not in body, "no Opus/Fable finder (D-344)"
    code = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("//"))
    assert "resumeFromRunId" not in code and "workflow(" not in code, (
        "each pass is its own invocation"
    )


def test_the_script_diffs_files_read_against_the_slice_and_logs_the_gap() -> None:
    body = _script()
    assert "files_read" in body
    assert re.search(r"if \(gaps\.length\) log\(`[^`]*coverage gap", body), (
        "a coverage gap must be logged by its own conditional line (no silent caps)"
    )


def test_the_sources_and_the_brief_name_the_script() -> None:
    for src in SOURCES:
        text = src.read_text(encoding="utf-8")
        assert SCRIPT_PATH_TEXT in text, f"{src.name} does not launch the workflow"
    brief = BRIEF.read_text(encoding="utf-8")
    assert "files_read" in brief, "the brief must tell a finder to list every file it opened"
    assert DOC.is_file(), "the workflow's reference doc is missing"


def _call_end(body: str, start: int) -> int:
    """The index just past the `)` that closes the call opened at `start` — a balanced scan, so a `})`
    inside a comment or a string before the options object cannot truncate the window (A-S8)."""
    depth = 0
    for i in range(body.index("(", start), len(body)):
        if body[i] == "(":
            depth += 1
        elif body[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    raise AssertionError("unbalanced call")


def _run_ledger(args: dict, seat_results: dict) -> tuple[dict, str]:
    """The ledger the script returns and the log text (see `_harness`)."""
    out, log, _ = _harness(args, seat_results)
    return out, log


def _harness(
    args: dict, seat_results: dict, *, expect_fail: bool = False
) -> tuple[dict, str, dict]:
    """Execute the script's own pipeline under node with the Workflow globals stubbed: `agent` records the
    prompt it was sent and returns the canned result keyed by the call's label (`None` → a null seat),
    `parallel`/`pipeline` run the stages, `log` goes to stderr. Returns the ledger, the log text and the
    prompts by label."""
    src = _script().replace("export const meta", "const meta", 1)
    harness = f"""
globalThis.args = {json.dumps(args)};
const results = {json.dumps(seat_results)};
globalThis.log = (m) => console.error(String(m));
// the runtime's semantics (workflow docs): a throwing parallel() thunk resolves to null; a pipeline item whose
// stage throws drops to null and skips its remaining stages (A-S4)
globalThis.parallel = async (thunks) => Promise.all(thunks.map(async (t) => {{ try {{ return await t(); }} catch {{ return null; }} }}));
globalThis.pipeline = async (items, ...stages) =>
  Promise.all(items.map(async (item, i) => {{ try {{ let v = item; for (const s of stages) v = await s(v, item, i); return v; }} catch (e) {{ console.error('STAGE THREW: ' + e); return null; }} }}));
const prompts = {{}};
globalThis.agent = async (prompt, opts) => {{
  prompts[opts.label] = prompt;
  return Object.hasOwn(results, opts.label) ? results[opts.label] : null;
}};
(async () => {{ {src} }})().then((out) => console.log(JSON.stringify({{ out, prompts }})));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", harness],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if expect_fail:
        assert proc.returncode != 0, "the script was expected to refuse its args"
        return {}, proc.stderr, {}
    assert proc.returncode == 0, proc.stderr[-1500:]
    doc = json.loads(proc.stdout.strip().splitlines()[-1])
    return doc["out"], proc.stderr, doc["prompts"]


_ARGS = {
    "pass": 1,
    "surface": "t",
    "base_sha": "0",
    "digest": "0",
    "pins_dir": "/p",
    "scratch_dir": "/s",
    "brief": "b",
    "slices": [{"name": "S", "files": ["a.py", "b.py"], "priority": "p"}],
}


def _cand(cid: str, line: int, cls: str = "logic") -> dict:
    return {
        "id": cid,
        "file": "a.py",
        "line": line,
        "failure_class": cls,
        "claim": cid,
        "scenario": "s",
        "check": "true",
        "confidence": "PLAUSIBLE",
    }


def test_the_union_merges_only_across_seats_near_the_same_line_and_never_drops_a_same_seat_neighbour() -> (
    None
):
    ledger, _ = _run_ledger(
        _ARGS,
        {
            "find:S:sonnet": {
                "files_read": ["a.py", "b.py"],
                "notes": "",
                "candidates": [_cand("S-S1", 3), _cand("S-S2", 5)],
            },
            "find:S:haiku": {"files_read": ["a.py"], "notes": "", "candidates": [_cand("S-H1", 7)]},
            "refute:S": {
                "verdicts": [
                    {
                        "id": "S-S1",
                        "verdict": "confirmed",
                        "command": "c",
                        "output": "o",
                        "mechanism": "m",
                    },
                    {
                        "id": "NOT-A-CANDIDATE",
                        "verdict": "refuted",
                        "command": "c",
                        "output": "o",
                        "mechanism": "m",
                    },
                ]
            },
            # no verdict for S-S2 → the refuter did not reach it
        },
    )
    s = ledger["slices"][0]
    ids = [c["id"] for c in s["candidates"]]
    assert ids == ["S-S1", "S-S2"], f"the same seat's two neighbours are two defects, kept: {ids}"
    assert s["overlap"] == 1 and s["candidates"][0]["also"] == "S-H1", (
        "S-H1 at line 7 is S-S1's twin (cross-seat, within 5 lines)"
    )
    assert s["gaps"] == [], "b.py was read by the sonnet seat"
    verdict_ids = [v["id"] for v in s["verdicts"]]
    assert verdict_ids == ["S-S1", "S-S2"], (
        f"the verdict id is the candidate's, never the seat's echo: {verdict_ids}"
    )
    assert s["verdicts"][1]["verdict"] == "unverified", (
        "a candidate the refuter never answered is unverified, never dropped"
    )
    by_model = {x["model"]: x for x in s["seats"]}
    assert by_model["sonnet"]["confirmed"] == 1 and by_model["haiku"]["confirmed"] == 1, (
        "a shared confirmed candidate credits both seats"
    )


def test_a_null_finder_makes_every_unread_file_a_logged_gap_and_the_seat_failed() -> None:
    ledger, log = _run_ledger(
        _ARGS,
        {
            "find:S:sonnet": {"files_read": ["a.py"], "notes": "", "candidates": []},
            # find:S:haiku absent → a null finder
        },
    )
    s = ledger["slices"][0]
    assert s["gaps"] == ["b.py"], s["gaps"]
    assert ledger["dropped_seats"] == 1 and any(x["failed"] for x in s["seats"])
    assert "coverage gap" in log and "SEAT FAILED" in log, log
    assert s["verdicts"] == [], "zero candidates run zero verify seats"


def test_a_later_pass_prompt_defines_its_ledger_status_on_the_defect_and_every_seat_must_finish_structured() -> (
    None
):
    args = {**_ARGS, "pass": 2}
    args["slices"] = [
        {
            **_ARGS["slices"][0],
            "ledger": [{"id": "S-S1", "file": "a.py", "line": 3, "claim": "off by one"}],
        }
    ]
    _, _, prompts = _harness(args, {})
    finder = prompts["find:S:sonnet"]
    assert "STILL_TRUE means the defect is still there" in finder, (
        "pass ≥ 2 keys the status on the DEFECT (R-3)"
    )
    assert "NOW_FALSE means it is gone" in finder
    assert "ONLY the STILL_TRUE and NEW rows" in finder, "a fix that holds is never a candidate"
    assert "StructuredOutput" in prompts["find:S:haiku"], (
        "every finder is told to finish with the schema"
    )
    _, _, p1 = _harness(
        _ARGS,
        {
            "find:S:sonnet": {
                "files_read": ["a.py", "b.py"],
                "notes": "",
                "candidates": [_cand("S-S1", 3)],
            }
        },
    )
    assert "StructuredOutput" in p1["refute:S"], "a refuter that answers in prose is a null seat"


def _two_finders(
    cands_sonnet: list, cands_haiku: list | None = None, ledger_status: list | None = None
) -> dict:
    return {
        "find:S:sonnet": {
            "files_read": ["a.py", "b.py"],
            "notes": "",
            "candidates": cands_sonnet,
            "ledger_status": ledger_status or [],
        },
        "find:S:haiku": {"files_read": ["a.py"], "notes": "", "candidates": cands_haiku or []},
    }


def test_a_ledger_row_is_an_object_with_a_claim_or_a_plain_claim_and_anything_else_is_refused() -> (
    None
):
    """A pass-2 ledger passed as strings rendered as `undefined · undefined:undefined` and the seats worked
    from the brief instead (review of 2026-09-23, the closing pass's MACHINERY note)."""
    args = {**_ARGS, "pass": 2}
    args["slices"] = [
        {
            **_ARGS["slices"][0],
            "ledger": [
                "A-S2: row 5b names the wrong variable",
                {"id": "A-S3", "file": "a.py", "line": 9, "claim": "wrong finding cited"},
            ],
        }
    ]
    _, _, prompts = _harness(args, {})
    finder = prompts["find:S:sonnet"]
    assert "undefined" not in finder, "a ledger row rendered as undefined"
    assert (
        "A-S2: row 5b names the wrong variable" in finder
        and "A-S3 · a.py:9 · wrong finding cited" in finder
    )
    for bad in ({"id": "X", "file": "a.py", "line": 1}, 7, {"claim": ""}):
        broken = {**args, "slices": [{**args["slices"][0], "ledger": [bad]}]}
        _, err, _ = _harness(broken, {}, expect_fail=True)
        assert "ledger row" in err, f"{bad!r} must be refused by name, got: {err[-300:]}"


def test_one_refuter_per_slice_and_a_refutation_without_counter_evidence_is_unverified() -> None:
    """§ 4.9 findings 27/36: one fresh refuter per slice, and `refuted` needs the command and output that
    disprove the claim — a bare `refuted` is uncertainty, never a closed candidate."""
    ledger, _, prompts = _harness(
        _ARGS,
        {
            **_two_finders([_cand("S-S1", 3), _cand("S-S2", 30), _cand("S-S3", 60)]),
            "refute:S": {
                "verdicts": [
                    {
                        "id": "S-S1",
                        "verdict": "refuted",
                        "command": "grep x a.py",
                        "output": "0 matches",
                        "mechanism": "m",
                    },
                    {
                        "id": "S-S2",
                        "verdict": "refuted",
                        "command": "",
                        "output": "",
                        "mechanism": "looks fine",
                    },
                    {
                        "id": "S-S3",
                        "verdict": "unverified",
                        "command": "",
                        "output": "",
                        "mechanism": "timed out",
                    },
                ]
            },
        },
    )
    assert [k for k in prompts if k.startswith("refute:")] == ["refute:S"], (
        "one refuter for the slice"
    )
    for cid in ("S-S1", "S-S2", "S-S3"):
        assert cid in prompts["refute:S"], f"the refuter is handed {cid}"
    v = {x["id"]: x["verdict"] for x in ledger["slices"][0]["verdicts"]}
    assert v == {"S-S1": "refuted", "S-S2": "unverified", "S-S3": "unverified"}, v


def test_a_slice_closes_only_when_nothing_is_confirmed_unverified_unread_or_unreported() -> None:
    """The operator's ruling on ≤ 3 passes: a TARGET, never a cap — a pass that closes early is a failure,
    so the script says whether each slice may close and why not."""
    clean, _, _ = _harness(
        _ARGS,
        {
            **_two_finders([_cand("S-S1", 3)]),
            "refute:S": {
                "verdicts": [
                    {
                        "id": "S-S1",
                        "verdict": "refuted",
                        "command": "c",
                        "output": "o",
                        "mechanism": "m",
                    }
                ]
            },
        },
    )
    assert clean["closable"] is True and clean["slices"][0]["closable"] is True, clean["slices"][0][
        "open"
    ]
    for results, reason in (
        (
            {
                **_two_finders([_cand("S-S1", 3)]),
                "refute:S": {
                    "verdicts": [
                        {
                            "id": "S-S1",
                            "verdict": "confirmed",
                            "command": "c",
                            "output": "o",
                            "mechanism": "m",
                        }
                    ]
                },
            },
            "confirmed",
        ),
        (_two_finders([_cand("S-S1", 3)]), "unverified"),
        (
            {
                "find:S:sonnet": {"files_read": ["a.py"], "notes": "", "candidates": []},
                "find:S:haiku": {"files_read": ["a.py"], "notes": "", "candidates": []},
            },
            "unread",
        ),
    ):
        out, _, _ = _harness(_ARGS, results)
        s = out["slices"][0]
        assert out["closable"] is False and s["closable"] is False, reason
        assert any(reason in o for o in s["open"]), (reason, s["open"])
    args = {**_ARGS, "pass": 2}
    args["slices"] = [
        {
            **_ARGS["slices"][0],
            "ledger": [
                {"id": "S-S1", "file": "a.py", "line": 3, "claim": "c"},
                {"id": "S-S2", "file": "a.py", "line": 9, "claim": "d"},
            ],
        }
    ]
    out, _, _ = _harness(
        args,
        _two_finders(
            [], ledger_status=[{"id": "S-S1", "status": "NOW_FALSE", "command": "c", "output": "o"}]
        ),
    )
    s = out["slices"][0]
    assert s["closable"] is False and any(
        "S-S2" in o and "not re-verified" in o for o in s["open"]
    ), s["open"]


def test_a_placeholder_is_not_counter_evidence_and_conflicting_rows_are_unverified() -> None:
    """Review of 2026-09-23 A-S1/A-S2: `n/a` passed the empty-string guard as a refutation, and two verdict
    rows for one id kept whichever came first."""
    ledger, _, _ = _harness(
        _ARGS,
        {
            **_two_finders([_cand("S-S1", 3), _cand("S-S2", 30)]),
            "refute:S": {
                "verdicts": [
                    {
                        "id": "S-S1",
                        "verdict": "refuted",
                        "command": "n/a",
                        "output": " N/A ",
                        "mechanism": "m",
                    },
                    {
                        "id": "S-S2",
                        "verdict": "confirmed",
                        "command": "c",
                        "output": "o",
                        "mechanism": "m",
                    },
                    {
                        "id": "S-S2",
                        "verdict": "refuted",
                        "command": "c",
                        "output": "o",
                        "mechanism": "m",
                    },
                ]
            },
        },
    )
    v = {x["id"]: x["verdict"] for x in ledger["slices"][0]["verdicts"]}
    assert v == {"S-S1": "unverified", "S-S2": "unverified"}, v
    assert ledger["closable"] is False


def test_two_candidates_sharing_an_id_are_both_kept_under_distinct_ids() -> None:
    """A-S2: a seat that reuses an id must not have its second candidate share the first one's verdict."""
    ledger, _, prompts = _harness(
        _ARGS,
        {
            **_two_finders([_cand("S-S1", 3, "logic"), _cand("S-S1", 60, "auth")]),
            "refute:S": {
                "verdicts": [
                    {
                        "id": "S-S1",
                        "verdict": "refuted",
                        "command": "c",
                        "output": "o",
                        "mechanism": "m",
                    }
                ]
            },
        },
    )
    ids = [c["id"] for c in ledger["slices"][0]["candidates"]]
    assert len(ids) == 2 and len(set(ids)) == 2, ids
    assert all(i in prompts["refute:S"] for i in ids), "the refuter is handed both ids"
    v = {x["id"]: x["verdict"] for x in ledger["slices"][0]["verdicts"]}
    assert sorted(v.values()) == ["refuted", "unverified"], v


def test_a_ledger_id_reported_with_other_case_or_spacing_counts_as_reported() -> None:
    """A-S5: `' s-s1'` is the claim `S-S1` reported — a spelling slip must not hold a slice open forever."""
    args = {**_ARGS, "pass": 2}
    args["slices"] = [
        {**_ARGS["slices"][0], "ledger": [{"id": "S-S1", "file": "a.py", "line": 3, "claim": "c"}]}
    ]
    out, _, _ = _harness(
        args,
        _two_finders(
            [],
            ledger_status=[{"id": " s-s1", "status": "NOW_FALSE", "command": "c", "output": "o"}],
        ),
    )
    assert out["slices"][0]["closable"] is True, out["slices"][0]["open"]


def test_the_refuter_box_grows_with_the_candidates_it_must_execute() -> None:
    """B-S2: one refuter executes a slice's candidates serially; a fixed box turns a large slice into a pile of
    `unverified` rows."""
    many = [_cand(f"S-S{i}", 10 * i) for i in range(1, 11)]
    _, _, prompts = _harness({**_ARGS, "box_minutes": 12}, {**_two_finders(many)})
    box = re.search(r"HARD TIME BOX (\d+) minutes", prompts["refute:S"])
    assert box and int(box.group(1)) >= 30, box and box.group(0)


def test_the_reviewer_agent_frontmatter_is_valid_yaml_carrying_the_cache_ttl() -> None:
    """A-S6: a plain scalar holding `): a` is invalid YAML, so a strict frontmatter parser drops the block and the
    nested `experimental.cacheTtl` is never read (code.claude.com/docs/en/sub-agents: `experimental.cacheTtl`,
    `5m` or `1h`)."""
    import yaml

    text = BRIEF.read_text(encoding="utf-8")
    front = text.split("---", 2)[1]
    meta = yaml.safe_load(front)
    assert meta["name"] == "fabrik-reviewer" and meta["omitClaudeMd"] is True
    assert meta["experimental"]["cacheTtl"] == "1h"


def test_a_stage_that_throws_drops_its_slice_and_the_pass_is_not_closable() -> None:
    """A-S4: the Workflow runtime resolves a throwing parallel() thunk to null and drops a pipeline item whose
    stage throws; the harness must do the same, and a dropped slice must never read as closable."""
    ledger, log, _ = _harness(
        _ARGS,
        {**_two_finders([_cand("S-S1", 3)]), "refute:S": {"verdicts": 5}},
    )
    assert ledger["dropped_slices"] == 1 and ledger["closable"] is False, ledger
    assert "DROPPED" in log, log


def test_the_case_fold_never_merges_two_ledger_ids_that_differ_only_by_case() -> None:
    """Review pass 2, A-S7: the fold that forgives a seat's spelling slip must not let one report close two
    claims — an exact match wins, and a folded match counts only when it names exactly one claim."""
    args = {**_ARGS, "pass": 2}
    args["slices"] = [
        {**_ARGS["slices"][0], "ledger": [{"id": "X-1", "claim": "c"}, {"id": "x-1", "claim": "d"}]}
    ]
    out, _, _ = _harness(
        args,
        _two_finders(
            [], ledger_status=[{"id": "X-1", "status": "NOW_FALSE", "command": "c", "output": "o"}]
        ),
    )
    s = out["slices"][0]
    assert s["closable"] is False and any("x-1" in o for o in s["open"]), s["open"]


def test_a_real_command_whose_output_is_a_placeholder_word_still_refutes() -> None:
    """Review pass 2, A-S8: the placeholder guard reads the COMMAND — a command that genuinely prints `None` is
    counter-evidence; only a placeholder in place of the command is none."""
    ledger, _, _ = _harness(
        _ARGS,
        {
            **_two_finders([_cand("S-S1", 3)]),
            "refute:S": {
                "verdicts": [
                    {
                        "id": "S-S1",
                        "verdict": "refuted",
                        "command": "python3 -c 'print(None)'",
                        "output": "None",
                        "mechanism": "m",
                    }
                ]
            },
        },
    )
    assert ledger["slices"][0]["verdicts"][0]["verdict"] == "refuted"


def test_every_seat_is_told_never_to_write_under_the_repo_and_to_time_box_blocking_commands() -> (
    None
):
    """Two review runs of 2026-09-23 found seat files in the repo root (`pins_copy/`, two probe scripts), and one
    refuter spent 57 minutes in a single call against a 12-minute box — nothing in the Workflow API times an
    agent out, so the prompt must."""
    _, _, prompts = _harness(
        _ARGS,
        {
            "find:S:sonnet": {
                "files_read": ["a.py", "b.py"],
                "notes": "",
                "candidates": [_cand("S-S1", 3)],
            }
        },
    )
    for label in ("find:S:sonnet", "find:S:haiku", "refute:S"):
        p = prompts[label]
        assert "never write" in p and "outside SCRATCH" in p, label
        assert "timeout" in p, label
