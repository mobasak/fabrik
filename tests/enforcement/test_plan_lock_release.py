"""Behavior suite for `check_plan_lock_release.py` — the plan-lock release advisory gate.

Every fixture builds its corpus under `tmp_path`; nothing here reads or writes the operator's
real `.fabrik/plan-locks/`. The two risky behaviors (anchored token match, non-terminal
partition) were written FIRST against a deliberately-wrong stub so their reds landed on the
assertion rather than on an import error — see the plan's Phase A steps 0-2.
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "scripts" / "enforcement") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_plan_lock_release as cplr  # noqa: E402

# ── fixture helpers ────────────────────────────────────────────────────────────────────


def _lock(root: Path, name: str, **fields) -> Path:
    d = root / ".fabrik" / "plan-locks"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text(json.dumps(fields), encoding="utf-8")
    return p


def _plan(root: Path, stem: str, status_line: str | None, *, archived: bool = False) -> Path:
    d = root / "docs" / "development" / "plans" / ("archived" if archived else "")
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}.md"
    p.write_text(f"# {stem}\n\n{status_line}\n" if status_line else f"# {stem}\n", encoding="utf-8")
    return p


def _labels(findings) -> set[str]:
    return {f.label for f in findings}


# ── step 1: the anchored matcher (written red-first) ───────────────────────────────────


def test_finished_token_is_anchored_not_a_substring():
    """The single defect that would make the inductive limb unsafe."""
    assert cplr.finished_token("✅ EXECUTED 2026-08-14") == "EXECUTED"
    # The REAL fleet string (docs/development/plans/2026-06-29-plan-watchdog-deploy-side.md).
    # It contains "complete" MID-STRING, which is what makes it discriminate: a substring
    # search returns COMPLETE here, an anchored one returns None. An abbreviated fixture
    # without an embedded token passes against a substring implementation and proves nothing.
    assert (
        cplr.finished_token(
            "Issue 1 RESOLVED (§2.8). **Phase B complete + live-validated.** Tier-D is not yet ENABLED"
        )
        is None
    )


def test_status_value_extracts_the_value_off_a_status_line():
    assert (
        cplr.status_value("# t\n\n**Status:** ✅ EXECUTED 2026-08-14\n") == "✅ EXECUTED 2026-08-14"
    )


# ── step 2: the non-terminal partition (written red-first) ─────────────────────────────


def test_paused_lock_on_an_archived_plan_is_flagged(tmp_path):
    _plan(tmp_path, "p1", "Status: EXECUTED 2026-08-01", archived=True)
    lk = _lock(tmp_path, "p1", plan="docs/development/plans/archived/p1.md", status="paused")
    assert "STALE LOCK" in _labels(cplr.classify(tmp_path, lk))


def test_released_lock_is_skipped(tmp_path):
    _plan(tmp_path, "p2", "Status: EXECUTED 2026-08-01", archived=True)
    lk = _lock(tmp_path, "p2", plan="docs/development/plans/archived/p2.md", status="released")
    assert cplr.classify(tmp_path, lk) == []


# ── fixture a — active + archived ⇒ STALE LOCK ─────────────────────────────────────────


def test_a_active_lock_on_archived_plan(tmp_path):
    _plan(tmp_path, "a1", "Status: EXECUTED 2026-08-01", archived=True)
    lk = _lock(tmp_path, "a1", plan="docs/development/plans/archived/a1.md", status="active")
    assert "STALE LOCK" in _labels(cplr.classify(tmp_path, lk))


# ── fixture b — completion timestamp without final_commit ⇒ HALF-APPLIED FINISH ────────


def test_b_half_applied_finish_completed_at(tmp_path):
    _plan(tmp_path, "b1", "Status: CONVERGED")
    lk = _lock(
        tmp_path,
        "b1",
        plan="docs/development/plans/b1.md",
        status="active",
        completed_at="2026-08-21",
    )
    assert "HALF-APPLIED FINISH" in _labels(cplr.classify(tmp_path, lk))


# ── fixture c — un-archived plan with a finished token ⇒ LIKELY STALE LOCK ─────────────


def test_c_likely_stale_on_unarchived_finished_plan(tmp_path):
    _plan(tmp_path, "c1", "**Status:** ✅ EXECUTED 2026-08-14")
    lk = _lock(tmp_path, "c1", plan="docs/development/plans/c1.md", status="active")
    assert "LIKELY STALE LOCK" in _labels(cplr.classify(tmp_path, lk))


# ── fixture d — archived NOT_STARTED: flagged, message must not claim EXECUTED ─────────


def test_d_archived_not_started_message_quotes_the_real_status(tmp_path):
    _plan(tmp_path, "d1", "Status: NOT_STARTED", archived=True)
    lk = _lock(tmp_path, "d1", plan="docs/development/plans/archived/d1.md", status="active")
    fs = cplr.classify(tmp_path, lk)
    stale = [f for f in fs if f.label == "STALE LOCK"]
    assert stale, "an archived plan's active lock must still be flagged"
    assert "NOT_STARTED" in stale[0].detail
    assert "EXECUTED" not in stale[0].detail


# ── fixture e — archived dir with no spine ⇒ UNEVALUABLE, never terminal ───────────────


def test_e_archived_dir_without_spine_is_unevaluable(tmp_path):
    (tmp_path / "docs" / "development" / "plans" / "archived" / "e1").mkdir(parents=True)
    lk = _lock(tmp_path, "e1", plan="docs/development/plans/archived/e1", status="active")
    assert "UNEVALUABLE" in _labels(cplr.classify(tmp_path, lk))


# ── fixture f — the substring false positive ⇒ NOT flagged (NEGATIVE) ──────────────────


def test_f_resolved_inside_an_unfinished_plan_is_not_flagged(tmp_path):
    _plan(
        tmp_path,
        "f1",
        "Status: Issue 1 RESOLVED (§2.8). **Phase B complete + live-validated.** Tier-D is not yet ENABLED",
    )
    lk = _lock(tmp_path, "f1", plan="docs/development/plans/f1.md", status="active")
    assert _labels(cplr.classify(tmp_path, lk)) == set()


# ── fixture g — the sanctioned carve-out ⇒ NOT flagged (NEGATIVE) ──────────────────────


def test_g_paused_and_blocked_on_unfinished_plan_not_flagged(tmp_path):
    for i, st in enumerate(("paused", "blocked")):
        _plan(tmp_path, f"g{i}", "Status: IN-PROGRESS")
        lk = _lock(tmp_path, f"g{i}", plan=f"docs/development/plans/g{i}.md", status=st)
        assert _labels(cplr.classify(tmp_path, lk)) == set(), st


# ── fixture h — paused on an ARCHIVED plan IS flagged ──────────────────────────────────


def test_h_paused_on_archived_plan_is_flagged(tmp_path):
    _plan(tmp_path, "h1", "Status: EXECUTED 2026-08-01", archived=True)
    lk = _lock(tmp_path, "h1", plan="docs/development/plans/archived/h1.md", status="paused")
    assert "STALE LOCK" in _labels(cplr.classify(tmp_path, lk))


# ── fixture i — an unrecognised status ⇒ UNKNOWN STATUS, and it ACCUMULATES ────────────


def test_i_typo_status_is_unknown_not_silently_terminal(tmp_path):
    _plan(tmp_path, "i1", "Status: CONVERGED")
    lk = _lock(tmp_path, "i1", plan="docs/development/plans/i1.md", status="finshed")
    assert "UNKNOWN STATUS" in _labels(cplr.classify(tmp_path, lk))


def test_i2_unknown_status_accumulates_with_stale(tmp_path):
    """A misspelled non-terminal status on an archived plan yields BOTH labels."""
    _plan(tmp_path, "i2", "Status: EXECUTED 2026-08-01", archived=True)
    lk = _lock(tmp_path, "i2", plan="docs/development/plans/archived/i2.md", status="actve")
    got = _labels(cplr.classify(tmp_path, lk))
    assert "UNKNOWN STATUS" in got and "STALE LOCK" in got


# ── fixture j / released_at — the completion-timestamp FAMILY ──────────────────────────


def test_j_half_applied_finish_finished_at(tmp_path):
    _plan(tmp_path, "j1", "Status: CONVERGED")
    lk = _lock(
        tmp_path,
        "j1",
        plan="docs/development/plans/j1.md",
        status="active",
        finished_at="2026-08-21",
    )
    assert "HALF-APPLIED FINISH" in _labels(cplr.classify(tmp_path, lk))


def test_j2_half_applied_finish_released_at(tmp_path):
    _plan(tmp_path, "j2", "Status: CONVERGED")
    lk = _lock(
        tmp_path,
        "j2",
        plan="docs/development/plans/j2.md",
        status="active",
        released_at="2026-08-21",
    )
    assert "HALF-APPLIED FINISH" in _labels(cplr.classify(tmp_path, lk))


def test_j3_started_at_alone_is_not_a_completion_timestamp(tmp_path):
    """NEGATIVE: `started_at` is on 212 of ~213 fleet locks — reading the family as
    `endswith('_at')` fires HALF-APPLIED FINISH on every non-terminal lock in the fleet."""
    _plan(tmp_path, "j3", "Status: CONVERGED")
    lk = _lock(
        tmp_path,
        "j3",
        plan="docs/development/plans/j3.md",
        status="active",
        started_at="2026-08-26",
    )
    assert "HALF-APPLIED FINISH" not in _labels(cplr.classify(tmp_path, lk))


# ── fixture k / m — PLAN FIELD STALE, scoped to non-terminal ───────────────────────────


def test_k_plan_field_stale_on_non_terminal_lock(tmp_path):
    _plan(tmp_path, "k1", "Status: CONVERGED")
    lk = _lock(tmp_path, "k1", plan="docs/development/plans/archived/k1.md", status="active")
    got = _labels(cplr.classify(tmp_path, lk))
    assert "PLAN FIELD STALE" in got


def test_m_plan_field_stale_not_flagged_on_terminal_lock(tmp_path):
    """NEGATIVE: 35 of the fleet's 37 stale plan paths sit on terminal locks — dead history,
    and re-pointing a released lock destroys provenance."""
    _plan(tmp_path, "m1", "Status: EXECUTED 2026-08-01")
    lk = _lock(tmp_path, "m1", plan="docs/development/plans/archived/m1.md", status="released")
    assert "PLAN FIELD STALE" not in _labels(cplr.classify(tmp_path, lk))


# ── fixture l — FOREIGN LOCK: out of jurisdiction, never ORPHAN (NEGATIVE clause) ──────


def test_l_repo_lock_is_foreign_never_orphan(tmp_path):
    lk = _lock(
        tmp_path,
        "repo-lock-HOST-1234",
        plan="(repo-wide action) port the hub Stop hook + add 2 enforcement checks",
        owned_paths=["**"],
        status="active",
        holder="HOST:1234",
    )
    got = _labels(cplr.classify(tmp_path, lk))
    assert got == {"FOREIGN LOCK"}


def test_l2_repo_lock_with_a_separator_in_its_prose_plan(tmp_path):
    """One of fabrik-lib's seven repo-locks carries a `/` in its description — keying the
    jurisdiction test on the plan value's shape sends it to ORPHAN LOCK."""
    lk = _lock(
        tmp_path,
        "repo-lock-HOST-5678",
        plan="(repo-wide action) re-vendor scripts/enforcement/ checks",
        owned_paths=["**"],
        status="active",
        holder="HOST:5678",
    )
    assert _labels(cplr.classify(tmp_path, lk)) == {"FOREIGN LOCK"}


# ── fixture n — one lock, MULTIPLE labels ─────────────────────────────────────────────


def test_n_motivating_instance_emits_both_labels(tmp_path):
    """The kaizen-m1 shape: active + archived + completed_at + final_commit null."""
    _plan(tmp_path, "n1", "Status: EXECUTED 2026-08-21", archived=True)
    lk = _lock(
        tmp_path,
        "n1",
        plan="docs/development/plans/archived/n1.md",
        status="active",
        completed_at="2026-08-21",
        final_commit=None,
    )
    got = _labels(cplr.classify(tmp_path, lk))
    assert "STALE LOCK" in got and "HALF-APPLIED FINISH" in got


# ── ORPHAN — a plan-shaped lock whose stem resolves nowhere ────────────────────────────


def test_orphan_lock_when_no_plan_resolves(tmp_path):
    lk = _lock(tmp_path, "2026-01-01-plan-1-gone", plan="2026-01-01-plan-1-gone", status="active")
    assert "ORPHAN LOCK" in _labels(cplr.classify(tmp_path, lk))


# ── status_value grammar: fence-strip, first-line ──────────────────────────────────────


def test_status_value_prefers_the_first_status_line(tmp_path):
    """5 live fleet plans carry >1 Status-shaped line and two flip verdict first-vs-last."""
    _plan(tmp_path, "s1", "Status: IN-PROGRESS — phase 2 of 4\n\nStatus: EXECUTED 2026-07-02")
    lk = _lock(tmp_path, "s1", plan="docs/development/plans/s1.md", status="active")
    assert "LIKELY STALE LOCK" not in _labels(cplr.classify(tmp_path, lk))


def test_status_value_ignores_a_fenced_status_line(tmp_path):
    """A SQLAlchemy `status: Mapped[str] = mapped_column(` inside a fence is not a plan status."""
    d = tmp_path / "docs" / "development" / "plans" / "archived"
    d.mkdir(parents=True)
    (d / "s2.md").write_text(
        "# s2\n\n```python\nstatus: Mapped[str] = mapped_column(\n```\n", encoding="utf-8"
    )
    lk = _lock(tmp_path, "s2", plan="docs/development/plans/archived/s2.md", status="active")
    got = _labels(cplr.classify(tmp_path, lk))
    assert "UNEVALUABLE" in got


def test_spine_with_no_status_line_is_unevaluable(tmp_path):
    _plan(tmp_path, "s3", None, archived=True)
    lk = _lock(tmp_path, "s3", plan="docs/development/plans/archived/s3.md", status="active")
    assert "UNEVALUABLE" in _labels(cplr.classify(tmp_path, lk))


# ── case folding ──────────────────────────────────────────────────────────────────────


def test_uppercase_released_is_terminal(tmp_path):
    """A live `RELEASED` lock exists in tryton-crm on a correctly archived plan."""
    _plan(tmp_path, "u1", "Status: EXECUTED 2026-08-01", archived=True)
    lk = _lock(tmp_path, "u1", plan="docs/development/plans/archived/u1.md", status="RELEASED")
    assert cplr.classify(tmp_path, lk) == []


# ── malformed input never raises ──────────────────────────────────────────────────────


def test_malformed_json_is_unevaluable_not_a_traceback(tmp_path):
    d = tmp_path / ".fabrik" / "plan-locks"
    d.mkdir(parents=True)
    p = d / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert "UNEVALUABLE" in _labels(cplr.classify(tmp_path, p))


def test_non_dict_json_is_unevaluable(tmp_path):
    d = tmp_path / ".fabrik" / "plan-locks"
    d.mkdir(parents=True)
    p = d / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert "UNEVALUABLE" in _labels(cplr.classify(tmp_path, p))


# ── main(): the four end-to-end rows ──────────────────────────────────────────────────


def _run_json(root: Path, monkeypatch) -> dict:
    monkeypatch.setattr(
        sys, "argv", ["check_plan_lock_release.py", "--project-root", str(root), "--json"]
    )
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cplr.main()
    return {"rc": rc, "out": buf.getvalue()}


def test_main_returns_zero_even_with_findings(tmp_path, monkeypatch):
    """THE fleet-red guard: `return 1 if findings else 0` turns this advisory row into a
    blocking red across ~46 repos (`final_gate.py:262-270`)."""
    _plan(tmp_path, "x1", "Status: EXECUTED 2026-08-01", archived=True)
    _lock(tmp_path, "x1", plan="docs/development/plans/archived/x1.md", status="active")
    r = _run_json(tmp_path, monkeypatch)
    assert r["rc"] == 0
    assert json.loads(r["out"])["counters"]["stale"] == 1


def test_main_prints_nothing_verified_when_no_lock_is_evaluable(tmp_path, monkeypatch):
    _plan(tmp_path, "y1", "Status: EXECUTED 2026-08-01", archived=True)
    _lock(tmp_path, "y1", plan="docs/development/plans/archived/y1.md", status="released")
    r = _run_json(tmp_path, monkeypatch)
    assert r["rc"] == 0
    assert json.loads(r["out"])["verdict"] == "NOTHING VERIFIED"


def test_main_prints_ok_when_a_non_terminal_lock_evaluates_clean(tmp_path, monkeypatch):
    _plan(tmp_path, "z1", "Status: IN-PROGRESS")
    _lock(tmp_path, "z1", plan="docs/development/plans/z1.md", status="active")
    r = _run_json(tmp_path, monkeypatch)
    assert json.loads(r["out"])["verdict"] == "OK"


def test_main_is_silent_when_the_repo_has_no_lock_dir(tmp_path, monkeypatch, capsys):
    """30 of ~46 synced repos carry no `.fabrik/plan-locks/` — `warn_only` implies advisory,
    so a `NOTHING VERIFIED` block there would print on every gate run forever."""
    monkeypatch.setattr(
        sys, "argv", ["check_plan_lock_release.py", "--project-root", str(tmp_path)]
    )
    rc = cplr.main()
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_census_line_lists_all_eight_counters(tmp_path, monkeypatch):
    _plan(tmp_path, "w1", "Status: IN-PROGRESS")
    _lock(tmp_path, "w1", plan="docs/development/plans/w1.md", status="active")
    r = _run_json(tmp_path, monkeypatch)
    counters = json.loads(r["out"])["counters"]
    assert set(counters) == {
        "stale",
        "likely_stale",
        "half_applied",
        "plan_field_stale",
        "orphan",
        "foreign",
        "unknown_status",
        "unevaluable",
    }


# ── regressions kept from the Phase-A review round ────────────────────────────────────


def test_lock_without_a_status_field_is_unevaluable_not_unknown(tmp_path):
    """A MISSING field is an unasked question; `UNKNOWN STATUS` means the writer wrote a value
    we do not recognise. Conflating them mislabels the census."""
    _plan(tmp_path, "ns1", "Status: CONVERGED")
    lk = _lock(tmp_path, "ns1", plan="docs/development/plans/ns1.md")
    got = _labels(cplr.classify(tmp_path, lk))
    assert got == {"UNEVALUABLE"}


def test_terminal_but_unparseable_lock_does_not_inflate_evaluable(tmp_path, monkeypatch):
    """Deriving `evaluable` from the emitted LABELS counted an unreadable terminal lock as
    "1 non-terminal evaluated" and turned NOTHING VERIFIED into a false OK."""
    d = tmp_path / ".fabrik" / "plan-locks"
    d.mkdir(parents=True)
    (d / "broken.json").write_text('{"status": "released",}', encoding="utf-8")
    counters, findings, examined, evaluable, foreign = cplr._collect(tmp_path)
    assert (examined, evaluable) == (1, 0)
    r = _run_json(tmp_path, monkeypatch)
    assert json.loads(r["out"])["verdict"] == "NOTHING VERIFIED"


def test_finding_detail_bounds_a_long_status_value(tmp_path):
    """One real fleet status value is ~900 chars. `final_gate.py:2092` ships advisory output as
    `output[:500]`, so an unbounded quote silently truncates every finding after it."""
    _plan(tmp_path, "lg1", "Status: " + ("EXECUTED 2026-08-12 — " + "x" * 40) * 20, archived=True)
    lk = _lock(tmp_path, "lg1", plan="docs/development/plans/archived/lg1.md", status="active")
    stale = [f for f in cplr.classify(tmp_path, lk) if f.label == "STALE LOCK"]
    assert stale and len(stale[0].detail) < 160


def test_ok_line_buckets_sum_to_examined(tmp_path, capsys, monkeypatch):
    """`terminal = examined - evaluable` silently folded the 7 foreign repo-locks into the
    terminal count, so the printed buckets did not add up."""
    _plan(tmp_path, "sum1", "Status: IN-PROGRESS")
    _lock(tmp_path, "sum1", plan="docs/development/plans/sum1.md", status="active")
    _lock(tmp_path, "sum2", plan="docs/development/plans/sum2.md", status="released")
    _lock(
        tmp_path,
        "repo-lock-H-9",
        plan="(repo-wide) x",
        owned_paths=["**"],
        status="active",
        holder="H:9",
    )
    monkeypatch.setattr(
        sys, "argv", ["check_plan_lock_release.py", "--project-root", str(tmp_path)]
    )
    cplr.main()
    out_lines = capsys.readouterr().out.splitlines()
    line = [ln for ln in out_lines if ln.startswith("OK -")][0]
    nums = [int(n) for n in re.findall(r"(\d+) (?:non-terminal|terminal|foreign)", line)]
    total = int(re.search(r"of (\d+) plan lock", line).group(1))
    assert sum(nums) == total == 3, line


# ── regressions from the Phase-A native authoritative review ──────────────────────────


def test_findings_print_even_when_nothing_was_evaluable(tmp_path, capsys, monkeypatch):
    """THE worst defect this review found: `evaluable == 0` outranked real findings, so a run
    could print `1 stale` in the census and "nothing was verified" on the next line, with the
    finding, its detail and the remedy never printed at all."""
    d = tmp_path / "docs" / "development" / "plans" / "archived"
    d.mkdir(parents=True)
    (d / "x.md").write_text("# x\n", encoding="utf-8")  # archived, but NO Status: line
    _lock(tmp_path, "x", plan="docs/development/plans/archived/x.md", status="active")
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    assert cplr.main() == 0
    out = capsys.readouterr().out
    assert "STALE LOCK: x.json" in out
    assert "OWNER releases it" in out  # the remedy must reach the operator too
    assert "NOTHING VERIFIED" not in out, "a real finding must outrank 'nothing was evaluable'"
    # …and the machine-readable verdict must agree with the human one.
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path), "--json"])
    cplr.main()
    assert json.loads(capsys.readouterr().out)["verdict"] == "FINDINGS"


def test_likely_stale_detail_is_bounded_too(tmp_path):
    """`_truncate` guarded the STALE branch but not LIKELY STALE, which carries the same payload."""
    _plan(tmp_path, "lb1", "Status: " + ("EXECUTED 2026-08-12 — " + "y" * 40) * 20)
    lk = _lock(tmp_path, "lb1", plan="docs/development/plans/lb1.md", status="active")
    likely = [f for f in cplr.classify(tmp_path, lk) if f.label == "LIKELY STALE LOCK"]
    assert likely and len(likely[0].detail) < 200


def test_orphan_names_the_stem_it_actually_looked_for(tmp_path):
    """Resolution uses the PLAN FIELD's stem; the message reported the LOCK FILE's stem, sending
    the operator to look for the wrong file."""
    lk = _lock(tmp_path, "lockname", plan="does-not-exist-anywhere", status="active")
    orphan = [f for f in cplr.classify(tmp_path, lk) if f.label == "ORPHAN LOCK"]
    # Assert the STEM PHRASE, not mere containment — the candidate paths in `tried` also carry
    # the stem, so `in detail` passes even when the message names the wrong one.
    assert orphan and "for stem 'does-not-exist-anywhere'" in orphan[0].detail
    assert "for stem 'lockname'" not in orphan[0].detail


def test_absolute_plan_value_is_not_resolved_from_outside_the_root(tmp_path):
    """`Path("/a") / "/b"` == `/b`: an absolute plan value discarded `root`, so a lock pointing at
    ANOTHER repo was declared healthy on the strength of a cross-repo stat()."""
    # The STEM must resolve, or the field probe never runs — the escape is only reachable on a
    # lock whose plan IS findable in this repo while its stored path points at another one.
    _plan(tmp_path, "CLAUDE", "Status: CONVERGED")
    lk = _lock(tmp_path, "esc", plan="/opt/fabrik/CLAUDE.md", status="active")
    ref = cplr.resolve_plan(tmp_path, lk, "/opt/fabrik/CLAUDE.md")
    assert ref.location == "live", "precondition: the stem resolves inside tmp_path"
    assert ref.field_resolved is False, "an absolute path must not be probed outside root"
    assert "PLAN FIELD STALE" in _labels(cplr.classify(tmp_path, lk))


def test_unknown_flag_does_not_exit_non_zero(tmp_path, monkeypatch):
    """argparse exits 2 on an unrecognised flag, and `final_gate.py:265-269` converts any non-zero
    exit from a warn_only check into a fleet-wide blocking red."""
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path), "--bogus-flag"])
    assert cplr.main() == 0


def test_an_unmapped_label_does_not_discard_every_other_lock(tmp_path, monkeypatch):
    """The counter block sat OUTSIDE the per-lock guard, so one bad label aborted the loop and
    main's outer guard discarded EVERY lock's findings while still exiting 0."""
    _plan(tmp_path, "ok1", "Status: EXECUTED 2026-08-01", archived=True)
    _lock(tmp_path, "aaa_bad", plan="docs/development/plans/aaa_bad.md", status="active")
    _lock(tmp_path, "ok1", plan="docs/development/plans/archived/ok1.md", status="active")
    real_evaluate = cplr.evaluate

    def evil(root, lock):
        if lock.name.startswith("aaa_bad"):
            return [cplr.Finding("NOT-A-REAL-LABEL", lock.name, "boom")], False
        return real_evaluate(root, lock)

    monkeypatch.setattr(cplr, "evaluate", evil)
    counters, findings, examined, evaluable, foreign = cplr._collect(tmp_path)
    assert examined == 2
    assert any(f.label == "STALE LOCK" for f in findings), "the healthy lock's finding survived"


def test_unknown_status_lock_is_not_counted_as_evaluated(tmp_path):
    """An unrecognised status is of unknown terminality; counting it as "non-terminal evaluated"
    overstates what the run actually asked."""
    _plan(tmp_path, "us1", "Status: CONVERGED")
    lk = _lock(tmp_path, "us1", plan="docs/development/plans/us1.md", status="finshed")
    _, ok = cplr.evaluate(tmp_path, lk)
    assert ok is False


def test_tilde_and_indented_fences_are_stripped(tmp_path):
    """Only column-0 backtick fences were stripped, so a `~~~` or indented block carrying a
    `status:` line still parsed as the plan's status."""
    assert cplr.status_value("# t\n\n~~~\nstatus: Mapped[str] = mapped_column(\n~~~\n") is None
    assert cplr.status_value("# t\n\n  ```\n  status: not a real status\n  ```\n") is None


def test_main_never_raises_when_collect_explodes(tmp_path, monkeypatch, capsys):
    """The module docstring calls this guard its reason for existing; nothing tested it."""

    def boom(_root):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(cplr, "_collect", boom)
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    assert cplr.main() == 0
    assert "could not evaluate plan locks" in capsys.readouterr().out


def test_foreign_locks_are_counted_but_never_printed_as_lines(tmp_path, capsys, monkeypatch):
    """`FOREIGN LOCK` is out of jurisdiction by construction. fabrik-lib owns seven, so a per-lock
    line would print on every gate run there forever — the fires-everywhere failure this check is
    supposed to avoid. It belongs in the census, not in the line list."""
    for i in range(3):
        _lock(
            tmp_path,
            f"repo-lock-H-{i}",
            plan="(repo-wide) x",
            owned_paths=["**"],
            status="active",
            holder=f"H:{i}",
        )
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    cplr.main()
    out = capsys.readouterr().out
    # A FOREIGN-ONLY corpus has nothing ACTIONABLE to say, so the human path is now SILENT.
    # fabrik-lib holds 7 foreign repo-locks and 41 terminal plan locks: counting `foreign` as
    # "content worth printing" put two content-free lines on every gate run there, forever.
    assert out == "", "a foreign-only corpus is not worth two lines on every gate run"
    # ...but the machine payload still carries the count, so the census never lies by omission.
    out = _run_json(tmp_path, monkeypatch)["out"]
    assert json.loads(out)["counters"]["foreign"] == 3, "the census must carry the count"
    assert "FOREIGN LOCK:" not in out, "…but no per-lock line"


# ── live fleet verification (Phase B step 5) ──────────────────────────────────────────


def test_pre_archive_plan_path_resolves_to_stale_not_orphan(tmp_path):
    """The archive-resolution branch, proved in BOTH directions on a hermetic corpus.

    ⚠️ The lock corpus alone is NOT enough. A lock's `plan` field is repo-relative and points at
    the pre-archive path, so under a lock-only tmp_path all four resolution branches miss and the
    check emits ORPHAN LOCK instead of STALE LOCK — whereupon the cheapest escape is to loosen
    `resolve_plan`. The plan tree must be materialised alongside.

    ⚠️ This replaced a copy of a LIVE sibling repo's lock corpus (/opt/brand-identiy-creator).
    That corpus was another repo's mutable housekeeping, not this repo's contract: when they
    released and archived their plans the donor stopped emitting ANY finding (measured
    2026-09-01: 7 locks, 0 findings of any label) and the assertion `any("deep-research" ...)`
    failed on a name that no longer existed — a red that said nothing about `classify`. A test
    whose premise another repo can retire is not a regression guard. The shape it was reaching
    for is structural, so it is built here instead, and asserting the ORPHAN direction too makes
    it a STRICTLY stronger guard than the donor version, which only ever checked the STALE half.
    """
    # The trap: the lock points at the PRE-archive path while the plan lives in archived/.
    _plan(tmp_path, "2026-07-19-plan-1-deep-research", "Status: EXECUTED 2026-07-20", archived=True)
    lk = _lock(
        tmp_path,
        "2026-07-19-plan-1-deep-research",
        plan="docs/development/plans/2026-07-19-plan-1-deep-research.md",
        status="active",
    )
    assert "STALE LOCK" in _labels(cplr.classify(tmp_path, lk)), (
        "a lock naming the pre-archive path must resolve through the archive branch"
    )

    # ...and without the plan tree the SAME lock is an ORPHAN — the branch is load-bearing, so a
    # loosened `resolve_plan` that returned STALE unconditionally would fail here.
    bare = tmp_path / "bare"
    (bare / "docs" / "development" / "plans").mkdir(parents=True)
    lk2 = _lock(
        bare,
        "2026-07-19-plan-1-deep-research",
        plan="docs/development/plans/2026-07-19-plan-1-deep-research.md",
        status="active",
    )
    assert "ORPHAN LOCK" in _labels(cplr.classify(bare, lk2)), (
        "an unresolvable plan must stay ORPHAN — not be swept into STALE"
    )


# ── regressions from the closing non-author sweeps ────────────────────────────────────


def test_output_does_not_crash_under_an_ascii_stdout(tmp_path):
    """THE fleet-red path the guard missed: the census separator was U+00B7, and the print block
    sat OUTSIDE main()'s try. Under `PYTHONIOENCODING=ascii` it raised UnicodeEncodeError and
    exited 1 — in the exact bare-invocation mode the gate uses, in every repo holding >=1 lock."""
    import os
    import subprocess

    _plan(tmp_path, "asc", "Status: EXECUTED 2026-08-01", archived=True)
    _lock(tmp_path, "asc", plan="docs/development/plans/archived/asc.md", status="active")
    env = {**os.environ, "PYTHONIOENCODING": "ascii", "LC_ALL": "C"}
    r = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/enforcement/check_plan_lock_release.py"),
            "--project-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert r.returncode == 0, f"non-zero exit reddens ~46 repos: {r.stderr[-400:]}"
    assert "Traceback" not in r.stderr
    # rc==0 alone is NOT enough — the guard would satisfy that while the check emitted only
    # "could not evaluate plan locks: UnicodeEncodeError(...)", i.e. survived by saying nothing
    # useful. Two independent fixes are in play (an ASCII-safe separator AND the guard around the
    # whole output path); this asserts the FIRST one, so reverting it alone still goes red.
    assert "stale" in r.stdout, f"the census must still be emitted under ASCII stdout: {r.stdout!r}"
    assert "could not evaluate" not in r.stdout, "degraded to the guard's error path"
    assert "STALE LOCK" in r.stdout, "the finding must still reach the operator"


def test_module_imports_nothing_outside_the_stdlib(tmp_path):
    """`except Exception` does NOT catch SystemExit, so a sibling exiting at import time turned
    this advisory row into a blocking red (measured rc=3). It also made the doc's `stdlib only`
    contract false. The import was dead — nothing read the name it bound."""
    src = (REPO / "scripts/enforcement/check_plan_lock_release.py").read_text(encoding="utf-8")
    import ast as _ast

    mods = set()
    for node in _ast.walk(_ast.parse(src)):
        if isinstance(node, _ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, _ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"argparse", "json", "re", "sys", "dataclasses", "pathlib", "__future__"}, mods
    assert "sys.path.insert" not in src, (
        "no sys.path mutation — it existed only for the dead import"
    )


def test_the_remedy_prints_once_not_per_finding(tmp_path, capsys, monkeypatch):
    """140 chars x N blew `final_gate.py:2114`'s output[:500] budget — measured 662 chars on the
    fleet's only finding-bearing repo, cut mid-token with the second finding lost."""
    for i in range(3):
        _plan(tmp_path, f"r{i}", "Status: EXECUTED 2026-08-01", archived=True)
        _lock(tmp_path, f"r{i}", plan=f"docs/development/plans/archived/r{i}.md", status="active")
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    cplr.main()
    out = capsys.readouterr().out
    assert out.count("OWNER releases it") == 1, "the remedy must appear exactly once"
    assert len(out) < 500, f"must fit the gate's advisory budget, got {len(out)}"
    # Detail may be dropped; the EXISTENCE of a finding may not be. Whatever does not fit is
    # counted and named, so the operator can never mistake a truncation for a clean run.
    shown = out.count("STALE LOCK:")
    assert shown >= 1
    if shown < 3:
        assert f"{3 - shown} more finding(s)" in out, "the overflow must be named, not silent"


def test_archive_without_the_d_resolves(tmp_path):
    """/opt/youtube/docs/development/plans/archive/ holds 33 real plans. Hard-coding only
    'archived' downgraded a genuinely stale lock there to ORPHAN and the verdict to
    NOTHING VERIFIED."""
    d = tmp_path / "docs" / "development" / "plans" / "archive"
    d.mkdir(parents=True)
    (d / "yt.md").write_text("Status: ✅ EXECUTED 2026-05-25\n", encoding="utf-8")
    lk = _lock(tmp_path, "yt", plan="docs/development/plans/archive/yt.md", status="active")
    assert "STALE LOCK" in _labels(cplr.classify(tmp_path, lk))


def test_no_double_report_on_an_archived_plan(tmp_path):
    """One lock, one root cause. Emitting STALE LOCK *and* PLAN FIELD STALE gave two counters and
    two contradictory remedies — and the repoint advice is what the provenance rule forbids on
    finished work."""
    _plan(tmp_path, "dd", "Status: EXECUTED 2026-08-01", archived=True)
    lk = _lock(tmp_path, "dd", plan="docs/development/plans/dd.md", status="active")  # stale field
    got = _labels(cplr.classify(tmp_path, lk))
    assert "STALE LOCK" in got and "PLAN FIELD STALE" not in got


def test_all_zero_census_is_silent_but_json_still_speaks(tmp_path, capsys, monkeypatch):
    """11 of 16 lock-carrying repos hold only terminal locks — an all-zero block on every gate run
    forever is the fires-everywhere failure. `--json` is never silenced: a machine consumer asked."""
    _plan(tmp_path, "q", "Status: EXECUTED 2026-08-01", archived=True)
    _lock(tmp_path, "q", plan="docs/development/plans/archived/q.md", status="released")
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    assert cplr.main() == 0
    assert capsys.readouterr().out == "", "an all-zero human census is noise"
    r = _run_json(tmp_path, monkeypatch)
    assert json.loads(r["out"])["examined"] == 1, "--json must still report"


def test_half_applied_when_the_status_flip_is_the_missing_field(tmp_path):
    """Finish step 5 writes THREE things. Keying only on `final_commit` reported plain OK for
    {active + completed_at + final_commit} — a lock that still hard-BLOCKs an unrelated plan."""
    _plan(tmp_path, "hf", "Status: IN-PROGRESS — phase 3 of 4")
    lk = _lock(
        tmp_path,
        "hf",
        plan="docs/development/plans/hf.md",
        status="active",
        completed_at="2026-08-21",
        final_commit="abc1234",
    )
    got = [f for f in cplr.classify(tmp_path, lk) if f.label == "HALF-APPLIED FINISH"]
    assert got, "two-of-three is still a half-apply"
    assert "status flip" in got[0].detail


def test_every_finding_label_reaches_the_findings_verdict(tmp_path, monkeypatch):
    """`real` gates the verdict. A mutation narrowing it to ('STALE LOCK',) survived the whole
    suite — so nothing proved the other three labels ever produce FINDINGS."""
    _plan(tmp_path, "v1", "**Status:** ✅ EXECUTED 2026-08-14")  # -> LIKELY STALE
    _lock(tmp_path, "v1", plan="docs/development/plans/v1.md", status="active")
    r = _run_json(tmp_path, monkeypatch)
    assert json.loads(r["out"])["verdict"] == "FINDINGS"

    d2 = tmp_path / "second"
    (d2 / "docs" / "development" / "plans").mkdir(parents=True)
    (d2 / "docs/development/plans/v2.md").write_text("Status: CONVERGED\n", encoding="utf-8")
    _lock(d2, "v2", plan="docs/development/plans/v2.md", status="active", completed_at="2026-08-01")
    r2 = _run_json(d2, monkeypatch)  # -> HALF-APPLIED FINISH
    assert json.loads(r2["out"])["verdict"] == "FINDINGS"


def test_census_prints_first_and_includes_the_zeros(tmp_path, capsys, monkeypatch):
    """Mutations printing only non-zero counters, and printing the census LAST, both survived the
    suite — yet the doc calls both load-bearing (a counter that prints only when non-zero is
    indistinguishable from one that was never computed)."""
    _plan(tmp_path, "c1", "Status: EXECUTED 2026-08-01", archived=True)
    _lock(tmp_path, "c1", plan="docs/development/plans/archived/c1.md", status="active")
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    cplr.main()
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    first = lines[0]
    for key in cplr.LABELS:
        assert key.replace("_", "-") in first, f"{key} missing from the census line"
    assert first.count("0 ") >= 5, "zeros must print, not be omitted"
    assert "STALE LOCK:" not in first, "the census must come FIRST"


def test_terminal_set_and_token_list_are_complete(tmp_path):
    """Mutations dropping `completed` from TERMINAL, and 6 of 9 FINISHED_TOKENS, all survived."""
    for st in ("released", "executed", "complete", "completed"):
        _plan(tmp_path, f"t_{st}", "Status: EXECUTED 2026-08-01", archived=True)
        lk = _lock(
            tmp_path, f"t_{st}", plan=f"docs/development/plans/archived/t_{st}.md", status=st
        )
        assert cplr.classify(tmp_path, lk) == [], f"{st} must be terminal"
    # ⚠️ `for tok in cplr.FINISHED_TOKENS` iterates whatever SURVIVED, so it cannot see a token
    # that was REMOVED — the whole suite passed with 7 of the 9 deleted, while this test's own
    # docstring claimed to close that mutation. The set must be asserted LITERALLY, from outside
    # the module, or the assertion is a tautology over the thing it is meant to pin.
    assert set(cplr.FINISHED_TOKENS) == {
        "IMPLEMENTATION-CONVERGED",
        "EXECUTED",
        "COMPLETED",
        "COMPLETE",
        "CLOSED",
        "DONE",
        "SHIPPED",
        "FIXED",
        "SUPERSEDED",
    }, "a finished token was added or removed without updating this pin"
    # ...and RESOLVED/CONVERGED stay OUT: the first labels a resolved issue inside an unfinished
    # plan, the second a plan that is ready to execute, not executed.
    for absent in ("RESOLVED", "CONVERGED"):
        assert absent not in cplr.FINISHED_TOKENS
        assert cplr.finished_token(f"{absent} 2026-08-01") is None, absent
    for tok in cplr.FINISHED_TOKENS:
        assert cplr.finished_token(f"{tok} 2026-08-01") == tok, tok


def test_foreign_needs_both_holder_and_star_owned_paths(tmp_path):
    """The discriminator is an AND. Mutating it to `holder` alone survived — and would silently
    exempt any plan lock that happens to carry a holder field."""
    _plan(tmp_path, "fh", "Status: EXECUTED 2026-08-01", archived=True)
    lk = _lock(
        tmp_path, "fh", plan="docs/development/plans/archived/fh.md", status="active", holder="H:1"
    )  # holder but NOT owned_paths == ["**"]
    got = _labels(cplr.classify(tmp_path, lk))
    assert "FOREIGN LOCK" not in got and "STALE LOCK" in got


# ── round 4: the closing non-author sweep ─────────────────────────────────────────────────


def test_ok_never_stands_alone_above_an_unresolved_lock(tmp_path, capsys, monkeypatch):
    """Fail-silent-green, inside the check written to close it. `OK` is scoped to the four
    FINDINGS, but the self-reports print underneath it — so a healthy active lock plus one ORPHAN
    emitted `OK - 0 stale of 2 plan lock(s) examined` immediately above `ORPHAN LOCK: ghost.json`.
    An operator scanning an advisory row stops reading at `OK`."""
    _plan(tmp_path, "live", "Status: IN-PROGRESS")
    _lock(tmp_path, "live", plan="docs/development/plans/live.md", status="active")
    _lock(tmp_path, "ghost", plan="docs/development/plans/ghost.md", status="active")  # orphan
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    cplr.main()
    out = capsys.readouterr().out
    ok = [ln for ln in out.splitlines() if ln.startswith("OK -")][0]
    assert "ORPHAN LOCK" in out, "the self-report must still print"
    assert "could NOT be resolved" in ok, f"OK stood alone above an unresolved lock: {ok!r}"
    assert "1 lock(s)" in ok, "the count must be named, not merely hinted"
    # ...and the qualifier must NOT appear when there is genuinely nothing unresolved.
    (tmp_path / ".fabrik" / "plan-locks" / "ghost.json").unlink()
    cplr.main()
    clean = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("OK -")][0]
    assert "could NOT be resolved" not in clean, "a clean OK must not carry the qualifier"


def test_say_is_ascii_by_construction_not_by_stream_configuration(capsys):
    """`_ascii_safe_stdout` is a belt, not the brace: `reconfigure` exists only on a real
    TextIOWrapper, so under a captured/wrapped stdout it silently no-ops (its `except` is a `pass`)
    and the next `✅` from a quoted plan status raises anyway. capsys IS such a stream, so this test
    runs in exactly the configuration where the stream-level fix does nothing."""
    assert (
        not hasattr(sys.stdout, "reconfigure") or sys.stdout.__class__.__name__ != "TextIOWrapper"
    )
    cplr._say("STALE LOCK: ✅ EXECUTED 2026-08-12 — all six phases")
    out = capsys.readouterr().out
    assert out.isascii(), f"non-ASCII reached stdout: {out!r}"
    assert "\\u2705" in out, "the payload must DEGRADE to an escape, not vanish"
    assert "STALE LOCK" in out and "EXECUTED" in out, "the ASCII content must survive intact"


def test_printed_block_respects_both_gate_caps_500_chars_and_10_lines(
    tmp_path, monkeypatch, capsys
):
    """`final_gate.py:2114` cuts advisory output at `output[:500]` and `:387` prints TEN lines with
    NO ellipsis — two independent caps. The budget arithmetic charged neither the newlines nor the
    line count. Worst case measured 491 chars against a 500 cap, a 9-char margin."""
    ar = tmp_path / "docs" / "development" / "plans" / "archived"
    ar.mkdir(parents=True)
    for i in range(40):  # far more findings than can ever be printed
        (ar / f"p{i}.md").write_text("Status: " + "X" * 900 + " EXECUTED\n", encoding="utf-8")
        _lock(tmp_path, f"p{i}", plan=f"docs/development/plans/archived/p{i}.md", status="active")
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    cplr.main()
    out = capsys.readouterr().out
    assert len(out) <= 500, f"the gate would cut this mid-token at 500: {len(out)}"
    assert len(out.splitlines()) <= 10, (
        f"lines past 10 vanish with no ellipsis: {len(out.splitlines())}"
    )
    assert "more finding(s)" in out, "dropping the EXISTENCE of a finding must never be silent"
    assert out.splitlines()[0].startswith("40 stale"), "the census still leads and still counts ALL"


def test_the_line_cap_holds_when_the_char_budget_is_not_the_binding_constraint(
    tmp_path, monkeypatch, capsys
):
    """The 10-line cap (`final_gate.py:387`, no ellipsis) is a SECOND, independent limit, and today
    it is unreachable: the char budget collapses even a 40-finding corpus to 5 lines, so a test run
    at the real budget passes with the cap reverted — it proves nothing. That safety is EMERGENT,
    not stated: raising `_ADVISORY_BUDGET` alone would silently start dropping findings past line
    10 with no ellipsis and no marker. This test removes the char budget as the binding constraint
    so the line cap is the only thing left holding, which is precisely the future it guards."""
    pl = tmp_path / "docs" / "development" / "plans"
    pl.mkdir(parents=True)
    for i in range(30):
        _lock(tmp_path, f"g{i}", plan=f"docs/development/plans/g{i}.md", status="active")
    monkeypatch.setattr(cplr, "_ADVISORY_BUDGET", 100_000)  # the char cap can no longer bind
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    cplr.main()
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) <= 10, f"lines past 10 vanish with no ellipsis: emitted {len(lines)}"
    assert any("more finding(s)" in ln for ln in lines), "the truncation must still be NAMED"


def test_the_remedy_follows_the_findings_that_actually_printed(tmp_path, monkeypatch, capsys):
    """Keyed on `shown` rather than on what was EMITTED, a corpus of 9 ORPHANs plus 1 STALE printed
    `-> the plan's OWNER releases it (Finish step 5)` beneath a visible list containing no stale
    lock — the STALE line had been truncated away by the budget. The reader is then told to take
    the wrong action on the findings they can actually see: an orphan is not released, its plan
    cannot be found at all. Measured on a real fixture during the closing review round."""
    ar = tmp_path / "docs" / "development" / "plans" / "archived"
    ar.mkdir(parents=True)
    for i in range(9):  # ORPHANs carry no remedy, and they crowd out everything after them
        _lock(tmp_path, f"a{i}", plan=f"docs/development/plans/a{i}.md", status="active")
    (ar / "zz.md").write_text(
        "Status: EXECUTED\n", encoding="utf-8"
    )  # the one STALE, with a remedy
    _lock(tmp_path, "zz", plan="docs/development/plans/archived/zz.md", status="active")
    monkeypatch.setattr(sys, "argv", ["c", "--project-root", str(tmp_path)])
    cplr.main()
    out = capsys.readouterr().out
    assert "more finding(s)" in out, "fixture must actually truncate, or it proves nothing"
    assert "STALE LOCK" not in out, "fixture must truncate the ONLY remedy-bearing finding away"
    assert "OWNER releases it" not in out, (
        "a remedy printed with no visible finding it applies to, telling the reader to release "
        f"locks when every VISIBLE finding is an orphan: {out!r}"
    )
    assert "ORPHAN LOCK" in out, "the findings that did print must still print"
    # Two-sided, or `_REMEDY = ""` would satisfy the negative assertion above trivially: when the
    # remedy-bearing finding IS among the emitted ones, the trailer MUST appear.
    for f in tmp_path.glob(".fabrik/plan-locks/a*.json"):
        f.unlink()  # drop the orphans; only the STALE lock remains, so it cannot be truncated
    cplr.main()
    out2 = capsys.readouterr().out
    assert "STALE LOCK" in out2 and "OWNER releases it" in out2, (
        f"the remedy must print when its finding does: {out2!r}"
    )


def test_a_fenced_status_line_cannot_escape_via_a_mismatched_closing_marker():
    """The fence regex accepted ``` or ~~~ at BOTH ends independently, so the non-greedy `.*?`
    paired an opening ``` with an unrelated ~~~ and stripped the wrong span — leaving a `Status:`
    line that lives INSIDE a code block exposed to the anchor. A plan whose real status is
    IN-PROGRESS but which quotes `Status: EXECUTED` inside a fence then read as EXECUTED: a
    LIKELY STALE LOCK against a perfectly healthy lock, the one outcome worse than not running.
    CommonMark requires the closing marker to match the opener; the regex now does too."""
    body = "# p\n```\nx\n~~~\nStatus: EXECUTED\n```\nStatus: IN-PROGRESS\n"
    assert cplr.status_value(body) == "IN-PROGRESS", "a fenced Status: escaped its block"
    assert cplr.finished_token(cplr.status_value(body)) is None, "healthy plan read as finished"
    # An UNTERMINATED fence swallows to EOF for the same reason — better UNEVALUABLE than wrong.
    assert cplr.status_value("# p\n```\nStatus: EXECUTED\n") is None
    # Regressions: the shapes that already worked must keep working.
    assert (
        cplr.status_value("# p\n~~~\nStatus: EXECUTED\n~~~\nStatus: IN-PROGRESS\n") == "IN-PROGRESS"
    )
    assert cplr.status_value("# p\nStatus: IN-PROGRESS\n") == "IN-PROGRESS"
    # site-provisioner's real shape: a SQLAlchemy `status:` inside a python fence.
    assert (
        cplr.status_value(
            "# p\n```python\nstatus: Mapped[str] = mapped_column(\n```\nStatus: IN-PROGRESS\n"
        )
        == "IN-PROGRESS"
    )
