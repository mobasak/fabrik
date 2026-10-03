"""Pins `ai/80-specialized-domains.md` to the rules its 2026-10-03 currency pass set.

The pack is glob-activated on moderation, recommendation, synthetic-data, health, edge, robotics and generative-design
paths (no fleet directory matches today; it is read by citation from ai/00). Eight things it states can go false with
no other gate red:

1. Its frontmatter carries `currency_pass:` and `Last content verification:` parses for
   `scripts/check_ai_pack_freshness.py`.
2. It routes each domain another pack owns to that pack, and every pack it names exists.
3. Moderation is layered: deterministic rules first, a classifier that only flags and routes, a person or a
   deterministic rule owning anything irreversible, and a labelled sample of the project's own content (in its own
   languages, Turkish named) before any classifier is trusted.
4. The dead or closing moderation services (Perspective API, Azure Content Moderator, Amazon Comprehend's toxicity
   detection) stay refused, and LightFM stays refused for new work.
5. Prompt injection is answered by design: no detector is a security boundary, and a detector is a signal, never the
   gate.
6. A recommender starts at a SQL baseline and a heavier model ships only when it beats it on a time-split holdout.
7. Synthetic data is neither a privacy guarantee nor a replacement for real data, and SDV's licence forbids a
   synthetic-data service.
8. A health feature that diagnoses, treats or recommends a treatment is spec-chain work, never `/task`; no retired route
   (Kilo, Traycer) and no version number in any shape (the detector `tests/test_vision_pack.py` defines).

Guards read emphasis-stripped, whitespace-collapsed text and pin the clause that carries the force, so a reversed verb
fails. The cheapest way past (4) is recommending a refused option in a new sentence; the whole-pack guard requires every
sentence naming one to carry its refusal, so the cheapest way left is a synonym for the service's name.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "80-specialized-domains.md"
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


def _bullet(label: str) -> str:
    body = _pack().split("\n## Fabrik defaults\n", 1)[1].split("\n**Anti-pattern:**", 1)[0]
    return next(
        (_plain(b) for b in body.split("\n- ")[1:] if label.lower() in _plain(b)[:70].lower()), ""
    )


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.;:])\s+", text)


def test_stamps() -> None:
    head = _pack().split("---", 2)[1]
    assert re.search(r"^currency_pass: \d{4}-\d{2}-\d{2}$", head, re.M), (
        "the pack lost its currency_pass stamp"
    )
    from datetime import date

    status, age, msg = _load("fresh", FRESH).check_pack(PACK, date(2026, 10, 3))
    assert status == "fresh" and age == 0, (
        f"the freshness checker no longer parses the pack's stamp: {msg}"
    )


def test_owning_packs_named_and_present() -> None:
    b = _bullet("Use the pack that owns the topic first")
    assert b, "the owning-pack routing rule is gone"
    for topic, pack in (
        ("Fraud, abuse and account takeover are", "saas/87-abuse-detection.md"),
        ("On-device inference is", "ai/20-vision.md"),
        ("for the app", "mobile-app/80-mobile.md"),
        ("for the app", "desktop-app/72-desktop.md"),
        ("Forecasting and anomaly detection are", "ai/70-data-predictive.md"),
        ("Prompt injection in code agents is", "ai/60-code.md"),
        ("in watchdog loops", "core/60-watchdog.md"),
    ):
        assert topic in b and pack in b, f"ai/80 no longer routes {topic!r} to {pack}"
        assert (RULES / pack).is_file(), f"ai/80 routes to {pack}, which does not exist"


def test_moderation_is_layered_and_measured() -> None:
    b = _bullet("Moderation is layered")
    assert b, "the moderation rule is gone"
    for phrase in (
        "Deterministic rules come first",
        "A classifier comes second, and it only flags and routes",
        "A person or a deterministic rule makes any decision that cannot be undone",
        "label at least 200 of the project's own items, in the project's own languages",
        "score precision and recall per harm class",
        "A vendor's benchmark is not the project's content",
        "a Turkish-language product measures on its own Turkish sample before it relies on any of them",
        "Read the exact licence before shipping any of them",
    ):
        assert phrase in b, f"the moderation rule lost: {phrase!r}"


def test_dead_options_stay_refused() -> None:
    text = _plain(_pack())
    refusal = re.compile(
        r"refused|sunsetting|ends after|deprecated|retiring|closed to new customers|English-only|no release since",
        re.I,
    )
    for name in ("Perspective", "Content Moderator", "Comprehend", "LightFM"):
        hits = [s for s in _sentences(text) if name in s]
        assert hits, f"ai/80 no longer names {name} at all"
        bare = [s for s in hits if not refusal.search(s)]
        assert not bare, f"a sentence names {name} without its refusal: {bare}"
    b = _bullet("Moderation is layered")
    assert "Refused for new work: Google's Perspective API" in b
    assert "Azure Content Moderator, deprecated and retiring on 2027-03-15" in b
    assert "LightFM is refused for new work" in _bullet("Recommendation starts")


def test_prompt_injection_by_design() -> None:
    b = _bullet("Prompt injection is answered by design")
    assert b, "the prompt-injection rule is gone"
    for phrase in (
        "No detector is a security boundary",
        "frame every piece of external content as data, never as instructions",
        "Give the model's tools the least privilege the task needs",
        "Require a person's approval before any action that cannot be undone",
        "Validate the output format before acting on it",
        "is a signal to log and route on, never the gate",
    ):
        assert phrase in b, f"the prompt-injection rule lost: {phrase!r}"


def test_recommendation_baseline_first() -> None:
    b = _bullet("Recommendation starts")
    assert b, "the recommendation rule is gone"
    for phrase in (
        "both as SQL over the project's own Postgres tables",
        "A heavier model ships only when it beats that baseline",
        "measured on a held-out window after the training window",
        "and then in an online A/B test",
        "only when the SQL baseline has plateaued and the interaction data may leave the box",
    ):
        assert phrase in b, f"the recommendation rule lost: {phrase!r}"


def test_synthetic_data_limits() -> None:
    b = _bullet("Synthetic data is neither")
    assert b, "the synthetic-data rule is gone"
    for phrase in (
        "Synthetic data is neither a privacy guarantee nor a replacement for real data",
        "Personal data stays under the project's data rules even after it is synthesised",
        "for augmentation only with the real data kept in the mix",
        "SDV is under the Business Source License, which forbids using it for a synthetic-data service",
    ):
        assert phrase in b, f"the synthetic-data rule lost: {phrase!r}"


def test_health_features_take_the_spec_chain() -> None:
    b = _bullet("Classify a health feature before you build it")
    assert b, "the health rule is gone"
    for phrase in (
        "only when it meets all four non-device criteria",
        "is not a HIPAA business associate",
        "the FTC's Health Breach Notification Rule covers health apps outside HIPAA",
        "class IIa or higher",
        "A feature that diagnoses, treats, or recommends a treatment is spec-chain work",
        "it never goes through /task",
    ):
        assert phrase in b, f"the health rule lost: {phrase!r}"


def test_territory_licence_trap() -> None:
    b = _bullet("Robotics and generative design")
    assert "does not apply in the EU, the UK or South Korea, so it cannot serve users there" in b
    assert "a full workflow needs NVIDIA's proprietary Omniverse components" in b


def test_no_retired_routes_or_version_literals() -> None:
    raw = _pack()
    for word in ("Kilo", "Traycer"):
        assert word not in raw, f"ai/80 names the retired route {word}"
    vision = _load("vision_pack", ROOT / "tests" / "test_vision_pack.py")
    found = vision.VERSION_RE.findall(_plain(raw))
    assert not found, f"version literals in ai/80: {found}"


def test_cited_packs_exist() -> None:
    for ref in set(re.findall(r"`((?:ai|core|saas|mobile-app|desktop-app)/[\w-]+\.md)`", _pack())):
        assert (RULES / ref).is_file(), f"ai/80 cites {ref}, which does not exist"
