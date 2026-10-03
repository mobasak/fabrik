"""Pins `ai/70-data-predictive.md` to the rules its 2026-10-03 currency pass set (D-528).

The pack is glob-activated on forecasting, predictive, anomaly and time-series paths (no fleet directory matches today;
it is read by citation from ai/00). Six things it states can go false with no other gate red:

1. Its frontmatter carries `currency_pass:` and `Last content verification:` parses for
   `scripts/check_ai_pack_freshness.py`.
2. A naive baseline comes first — seasonal naive for forecasts, a robust z-score for anomalies, scored on a held-out
   window after the training window, never a random split — and a heavier model ships only when it beats it.
3. No number comes from a chat LLM; an LLM may describe a forecast, never produce it.
4. The forecasting order (statsforecast, then mlforecast with LightGBM, then a foundation model), the tabular default
   (gradient-boosted trees) and the anomaly default (statistical first) hold, and the dead or unmaintained options
   (Prophet for new work, Merlion, ADTK, PostgresML) stay refused.
5. The licence trap names the non-commercial weights and tells the reader to check the exact weights.
6. No retired route (Kilo, Traycer), no version number in any shape (the detector `tests/test_vision_pack.py`
   defines), and every cited sibling pack exists.

Guards read emphasis-stripped, whitespace-collapsed text and pin the clause that carries the force, so a reversed verb
fails. The cheapest way past (4) was recommending a refused option in a new sentence; a whole-pack guard now requires every
sentence naming one to carry its refusal, so the cheapest way left is a synonym for the tool's name.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "70-data-predictive.md"
FRESH = ROOT / "scripts" / "check_ai_pack_freshness.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", text))


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _section(heading: str) -> str:
    text = _pack()
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return _plain(text[start : end if end != -1 else len(text)])


def _bullet(label: str) -> str:
    body = _pack().split("\n## Fabrik defaults\n", 1)[1].split("\n**Anti-pattern:**", 1)[0]
    return next((_plain(b) for b in body.split("\n- ")[1:] if label.lower() in _plain(b)[:60].lower()), "")


def test_stamps() -> None:
    head = _pack().split("---", 2)[1]
    assert re.search(r"^currency_pass: \d{4}-\d{2}-\d{2}$", head, re.M), "the pack lost its currency_pass stamp"
    from datetime import date

    status, age, msg = _load("fresh", FRESH).check_pack(PACK, date(2026, 10, 3))
    assert status == "fresh" and age == 0, f"the freshness checker no longer parses the pack's stamp: {msg}"


def test_baseline_first() -> None:
    b = _bullet("Beat a naive baseline first")
    assert b, "the baseline-first rule is gone"
    for phrase in (
        "Every forecast is scored against seasonal naive",
        "every anomaly detector against a robust z-score rule",
        "after the training window, never a random split",
        "Score point forecasts with MASE and probabilistic ones with CRPS or pinball loss",
        "A heavier model ships only when it beats that baseline on the project's own data",
        "the margin goes in the project's decision ledger",
    ):
        assert phrase in b, f"the baseline rule lost its force: {phrase!r}"


def test_no_numbers_from_a_chat_llm() -> None:
    b = _bullet("Never take numbers from a chat LLM")
    assert b, "the no-LLM-numbers rule is gone"
    assert "comes from a model built for it, never from prompting a general LLM with the numbers" in b
    assert "it is not a forecast" in b, "the pack no longer says an LLM judgement over numbers is not a forecast"


def test_forecasting_tabular_and_anomaly_defaults() -> None:
    f = _bullet("Forecasting, in order")
    assert "Classical models first, through Nixtla's statsforecast" in f
    assert "Then gradient-boosted trees on lag features, through mlforecast with LightGBM" in f
    assert "A pretrained time-series foundation model when there are many series, little history" in f
    assert "and only once it beats that rung on the held-out window" in f, "the foundation-model rung is no longer gated"
    assert "Prophet is in maintenance mode, so start nothing new on it" in f, "Prophet is no longer refused for new work"
    t = _bullet("Tabular prediction")
    assert "gradient-boosted trees (LightGBM, XGBoost, CatBoost) by default" in t
    assert "but only one whose weights allow commercial use" in t
    a = _bullet("Anomaly detection")
    assert "statistical first" in a
    assert "so adopt neither" in a, "Merlion and ADTK are no longer refused"
    w = _bullet("Run it in the project's own worker")
    assert "core/75-workers-jobs worker" in w and "core/76-gpu-workers" in w
    assert "so neither is a home for this work" in w, "PostgresML / TimescaleDB are no longer refused as the home"
    assert "Pin the model revision and bake the weights into the worker image" in w, "the weights-pinning rule is gone"
    assert "so it runs in that pack's forked-child isolation" in w
    m = _bullet("Managed platforms only on a recorded need")
    assert m, "the managed-platform gate is gone"
    assert "Amazon Forecast closed to new customers on 2024-07-29" in m


def test_licence_trap() -> None:
    text = _plain(_pack())
    assert "Licence trap — open code, closed weights." in text
    assert "Read the licence of the exact weights you download, not the repository's." in text
    for name in ("TimesFM", "TabPFN", "Moirai"):
        trap = text.split("Licence trap — open code, closed weights.")[1].split("## The fleet today")[0]
        assert name in trap, f"the licence trap no longer names {name}"


def test_no_retired_route_and_no_version_literal() -> None:
    text = _pack()
    for retired in ("Kilo", "Traycer"):
        assert retired not in text, f"the pack names the retired {retired}"
    vision = _load("vision_pack", ROOT / "tests" / "test_vision_pack.py")
    body = re.sub(r"Apache(?: License,?(?: Version)?)?[- ]?2\.0|[AL]?GPL-?\d\.\d|CC-BY(?:-[A-Z]+)*-? ?\d\.\d", "", text)
    found = vision.VERSION_RE.findall(body)
    assert not found, f"version literals in the pack: {found}"


def test_cited_packs_exist() -> None:
    for rel in ("ai/00-ai-model-selection.md", "core/75-workers-jobs.md", "core/76-gpu-workers.md"):
        assert (RULES / rel).exists(), f"the pack cites {rel}, which is gone"


def test_refused_options_are_never_recommended_anywhere() -> None:
    """Every sentence in the pack that names a refused option also carries its refusal."""
    refusals = {
        "Prophet": ("maintenance mode", "start nothing new"),
        "Merlion": ("archived", "adopt neither"),
        "ADTK": ("no release since", "adopt neither"),
        "PostgresML": ("went bust", "not a home"),
    }
    sentences = re.split(r"(?<=[.!?])\s+", _plain(_pack()))
    for name, markers in refusals.items():
        hits = [s for s in sentences if name in s]
        assert hits, f"the pack no longer mentions {name}, so its refusal is gone"
        for sentence in hits:
            assert any(m in sentence for m in markers), f"{name} is named without its refusal: {sentence!r}"
