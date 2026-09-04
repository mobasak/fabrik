#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook — bilingual (EN+TR) skill router.

Injects a directive-with-escape ("this matches /fabrik-X — invoke it, or say
why not") into context when a raw prompt clearly matches a pipeline stage, so
the operator doesn't have to remember the slash command. NEVER blocks, NEVER
rewrites the prompt — inject-only, fail-open on every error (same posture as
final_gate_stop.py).

Two tiers:
  Tier 1 (regex): a small, STABLE bilingual keyword->stem map (spec/design,
    plan, review, docs, test/certify, release, deploy-plan,
    deploy-plan-review, deploy, deploy-verify, catchup,
    retire, upstream). The map's VALUES rarely change; what's dynamic is the
    live skill roster (``~/.claude/skills/fabrik-*``) it resolves against at
    fire time — a stem only fires once its target skill actually exists, so
    a sibling ticket's brand-new command auto-enrolls the moment it lands,
    with zero edits here.
  Tier 2 (Haiku, regex-miss only, OPT-IN — env ``FABRIK_ROUTER_HAIKU=1``):
    fires ONLY when Tier 1 found no keyword match at all (a
    resolved-but-not-yet-built Tier-1 stem is a Tier-1 miss-with-a-name and
    stays silent — it NEVER falls through to Tier 2, round-2 review finding
    F2) AND the operator has opted in via ``FABRIK_ROUTER_HAIKU=1``.
    DEFAULT: OFF (regex-only; a Tier-1 miss stays silent). Round-3
    dispatcher ruling (2026-08-07): measured cold-start latency for the
    exact isolated flag set below ranged 8.6s-10.7s across two independent
    measurement passes — over the plan's FROZEN "<=8s" bound. This hook runs
    SYNCHRONOUSLY on every ``UserPromptSubmit``, so an always-on Tier 2
    would tax EVERY unmatched prompt in EVERY project with a ~10s stall —
    worse than the routings it recovers. The mechanism itself is fully
    built and unit/integration tested (see the Tier-2 tests in
    ``tests/test_skill_router_hook.py``); an operator who wants the
    fallback back sets ``FABRIK_ROUTER_HAIKU=1``. Offers Haiku a CURATED
    roster — the intersection of the live skill roster with the same stems
    Tier 1 can ever resolve to (STEM_SKILLS' values + the two dynamic test
    skills, F6) — via ``claude -p --model haiku`` classifying the prompt
    against that subset's names + ``Stage:`` lines. The child is fully
    isolated from this project (scratch cwd, closed stdin, settings/MCP/
    tools all switched off — see ``haiku_classify`` docstring, F1) so it can
    never load THIS project's hooks or boot its MCP servers. Hard
    ``HAIKU_TIMEOUT`` cap (killing the whole process group on expiry, N1);
    any error, timeout, or off-roster answer -> no match (silent).

Exemptions (checked first, silent on all): prompt already starts with ``/``;
cwd is not a fabrik-style project (no ``scripts/final_gate.py``); any
internal error (fail-open).

``design-review`` is DELIBERATELY excluded from the roster/router — it is a
pipeline-invoked GUI sub-gate (spine's own TRIGGER clause serves model-native
matching only), never prompt-auto-triggered. It lives outside
``~/.claude/skills/fabrik-*`` so the glob skips it structurally.

Contract (verified live against https://code.claude.com/docs/en/hooks,
2026-08-07 — corroborated across the fetched doc excerpt, a public hooks
schema gist, and independent third-party guides since the live page itself
truncates before the dedicated UserPromptSubmit section):
- stdin JSON: ``prompt`` (the submitted prompt text), ``session_id``, ``cwd``,
  ``transcript_path``, ``permission_mode``, ``hook_event_name``.
- Expansion order (round-2 review finding F8, verified live 2026-08-07 with a
  throwaway UserPromptSubmit hook that dumped its own stdin to a file, fired
  via ``claude -p "/fabrik-review"``): the RAW slash text arrives —
  ``"prompt":"/fabrik-review"`` — not an already-expanded skill body. The
  existing leading-``/`` exemption is therefore correct as written; no
  expansion-order guard is needed. Re-run independently on a fixup pass
  (2026-08-07, same throwaway-hook technique from a fresh scratch dir): the
  captured stdin envelope was
  ``{"session_id":..., "transcript_path":..., "cwd":..., "prompt_id":...,
  "permission_mode":"bypassPermissions", "hook_event_name":"UserPromptSubmit",
  "prompt":"/fabrik-review"}`` — same verdict, raw unexpanded text.
- inject: print
  ``{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
  "additionalContext": "..."}}`` on stdout, exit 0. NEVER print a top-level
  ``decision``/``reason`` here — this hook only injects, it never blocks.
- silent: exit 0 with empty stdout.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

# seconds — hard cap on the Tier-2 fallback classifier, RESTORED to the
# plan's FROZEN "<=8s" bound (round-3 dispatcher ruling). Every measurement
# pass to date agrees the honest cold-call cost is close to or over 8s:
# round-2 review F1 (2026-08-07) saw 10 cold isolated calls of
# `claude -p --model haiku --setting-sources "" --strict-mcp-config
# --tools "" --no-session-persistence "reply OK"` range 7.70s-8.99s (mean
# ~8.24s); a round-2 fixup re-measurement saw 3 more calls range 8.58s-9.38s
# (mean ~8.85s); the round-3 fixup's own probe (2026-08-07, identical
# isolated flag set) saw 8.6s-10.7s. The round-2 fixup's response was to
# raise this constant to 12s so the cap would "fit" the slow case — that was
# the wrong lever: it just made the synchronous stall on every unmatched
# prompt longer. The frozen bound stays 8; the fix for the latency problem
# is making Tier 2 opt-in (see the module docstring's round-3 dispatcher
# ruling), not inflating the timeout it runs under.
HAIKU_TIMEOUT = 8

# Stem -> canonical target skill name. Stable table (ticket: "stable stem
# semantics"); existence in the live roster is checked at fire time (see
# resolve_target), which is what makes a not-yet-built sibling command
# auto-enroll instead of needing an edit here.
STEM_SKILLS: dict[str, str] = {
    "spec": "fabrik-spec",
    "spec-review": "fabrik-spec-review",
    "plan": "fabrik-plan-after-chat",
    "review-scoped": "fabrik-review-scoped",
    "rules-review": "fabrik-rules-review",
    "repo-review": "fabrik-repo-review",
    "review": "fabrik-review",
    # Both sit ABOVE `review` in KEYWORD_STEMS: each is a phrase `fabrik-review`'s own SKIP
    # clause disclaims, so letting the broad `review` stem win points the operator at a gate
    # that says it is not the one (measured 2026-08-28 across all 71 advertised EN triggers).
    "rivals": "fabrik-rivals",
    # /fabrik-data-contract advertised 5 trigger phrases and reached NOTHING (audit 2026-08-28,
    # command 7 of 31). Only the DISTINCTIVE noun is matched — `data contract` / `veri sözleşme`.
    # The generic halves of its own trigger ("map these fields to the DB", "what are our field
    # names") are deliberately NOT patterned: "fields" appears in ordinary schema talk, and
    # check_trigger_routing's design is explicit that closing a nowhere-gap with a loose pattern
    # is worse than the gap. `data contract` cannot collide with the ui-design stem above, whose
    # nouns are `design contract` / `ui design contract`.
    "data-contract": "fabrik-data-contract",
    # /fabrik-features advertised 5 trigger phrases and reached NOTHING (audit 11/31).
    # A bare `features` stem would be a disaster — "add a features section", "the features
    # of this API", "feature flag rollout" are ordinary English. Only DISTINCTIVE noun
    # phrases are matched, probed against 7 adversarial strings with 0 over-fires.
    "features": "fabrik-features",
    # The Turkish half. `gözden geçir` alone lives in the broad `review` stem and fires on ANY
    # Turkish review phrase regardless of noun — looser than the English side, which at least
    # requires "review this/the/my". Six advertised TR phrases reached the wrong command until
    # these were added (2026-08-28); each is noun-qualified so the bare verb still reaches
    # /fabrik-review, which is its own advertised trigger.
    "ui-design": "fabrik-ui-design",
    "flows-review": "fabrik-flows-review",
    "plan-review": "fabrik-plan-review",
    "doc-converge": "fabrik-doc-converge",
    "ui-design-review": "fabrik-ui-design-review",
    "design-review": "design-review",
    "workflow-review": "fabrik-workflow-review",
    "docs": "fabrik-docs-review",
    "release": "fabrik-release",
    "deploy-plan": "fabrik-deploy-plan",
    "deploy-plan-review": "fabrik-deploy-plan-review",
    "deploy-checklist": "fabrik-deploy-checklist",
    "deploy": "fabrik-deploy",
    "deploy-verify": "fabrik-deploy-verify",
    "conformance": "fabrik-conformance-review",
    "catchup": "fabrik-catchup",
    "retire": "fabrik-decommission",
    "upstream": "fabrik-upstream",
}

# "test/certify" resolves DYNAMICALLY by project shape (UI-bearing vs
# headless), never a static stem->name entry — see resolve_target(). Only the
# headless set is needed: anything NOT in it (incl. an unknown/missing type)
# defaults to the UI-bearing skill, per CLAUDE.md's own SCAFFOLD_TYPES split
# ({saas-skeleton, chrome-extension, mobile-app, desktop-app, static-site,
# docusaurus} are UI-bearing; wordpress is OUT of fabrik entirely — /opt/wpf was
# archived 2026-08-07, so its type survives only for legacy shape routing and is
# never test-routed).
_HEADLESS_TYPES = {"python-api", "python-api-gpu", "node-api", "file-api", "file-worker"}

# Bilingual EN+TR keyword regexes -> stem. First match wins; order follows the
# ticket's own category list. Deliberately no entry maps to "design-review".
#
# Round-2 review F3: the highest-frequency bare EN words (test, plan, review,
# docs, design; idea dropped entirely) collide with ordinary dev prose
# ("fix this failing test", "plan B: just restart the container", "review of
# the logs shows an OOM", "the design of this function is wrong", "any idea
# why the import fails?") and are now gated behind an intent-anchor verb (or,
# for docs, a definite-article object) — unambiguous technical nouns
# (certify/certification, code review) stay bare. "publish"/"ship"/"release"
# get the same anchor treatment ("publish the package to npm" is not a
# release request).
#
# Round-2 review F5: TR forms use a PREFIX match (\w* suffix) instead of a
# trailing \b, so inflected verb forms ("inceleyelim", "güncellemek",
# "planlamayı", "yayınlıyoruz") still fire — a trailing \b only matched the
# bare dictionary form.
#
# Round-3 review N3-N6 (precision/recall/TR-anchor rebalance, 2026-08-07):
#   N3: "test" now fires ONLY on certification-intent phrasing (e2e,
#     end-to-end, certify/certification, user test, service test, full test
#     pass, TR uçtan uca / sertifika / kullanıcı testi / servis testi) — a
#     bare "run/create/need/start...test(s)" verb-anchor was still firing on
#     ordinary pytest prose ("run the tests and fix the failures", "start a
#     test container for postgres"); dropped.
#   N4: TR anchors tightened to match their EN twins' intent-gating — bare
#     "kaldır" (retire), "incele" (review), and bare "güncel" (catchup) were
#     firing on unrelated objects ("bu satırı kaldır", "logları incele",
#     "güncelleme var mı"); each now requires its real-world object in the
#     same clause (a service/project noun, a code/PR/diff noun, a project
#     noun respectively). "belge" (docs) is dropped outright — same call as
#     bare "docs" below.
#   N5: bare "spec|specification" now requires the same design-intent
#     verb-anchor as "design" ("the OpenAPI spec is out of date" / "per the
#     spec the field..." are prose, not a design request); bare
#     "the docs|documentation" (any reading context: "check the docs for...")
#     is dropped in favor of update/converge intent OR an object-first
#     "docs/documentation need(s) updating"; "catch...up" is tightened to
#     adjacent "catch(ing) up" (+ the literal "catch this/the project up")
#     so "catch the timeout error and clean up" no longer fires; TR "fikir"
#     (spec) is dropped entirely — same call as the already-dropped EN
#     "idea".
#   N6: imperative object-anchored forms restored for recall ("plan the
#     migration", "plan this feature out", "a/the review of...", "review
#     pass", "cut a release", "ship it") alongside the existing verb-anchor
#     forms.
#
# Round-4 dispatcher ruling (2026-08-07, TR parity + dormant-stem pre-arming):
#   NEW-1: TR bare stems (tasarım, planla, döküman, yayın) collided with
#     ordinary TR prose the same way the round-2/3 EN pass fixed (F3/N3-N6)
#     — "veritabanı tasarımı yüzünden sorgu yavaş", "planlanan bakım
#     penceresi ne zaman", "dökümanda yazan şey yanlış", "yeni yayın
#     notlarını oku" all matched a bare noun with zero routing intent. Each
#     TR token now requires the same kind of intent anchor its EN twin
#     already has: tasarım -> the volitional/imperative verb stem
#     "tasarla-" itself (tasarlayalım), OR the object "tasarım" collocated
#     with a generic "yap-" (do) verb ("tasarım yapalım"); planla- -> the
#     bare stem MINUS its Turkish passive infix "-n-" (planlanan/
#     planlanmış/planlanacak describe something already scheduled, never a
#     request — excluding just that infix keeps the volitional/nominal
#     forms — planlayalım, planlama, planlamayı — firing for free); döküman
#     -> the object collocated with "güncelle-" (update) in either word
#     order; yayın -> the volitional verb "yayınla-" (unchanged) plus the
#     idiom "yayına al-" ("yayına alalım") — the bare noun "yayın" alone no
#     longer fires.
#   NEW-2: the two DORMANT stems (\bupstream\b and
#     \b(retire|deprecate|decommission|sunset)\b) resolve to skills
#     (fabrik-upstream, fabrik-decommission) that don't exist in the live
#     roster yet, so resolve_target() silences them today regardless — but
#     first_regex_match() itself is unit-tested independent of the roster,
#     and the moment a sibling ticket lands either skill this table goes
#     live with ZERO further edits (the whole point of the stem/roster
#     split). Arm the anchors NOW so there's no live-fire window between
#     that ship and a review catching the bare match: upstream requires a
#     propose/file/send/submit/push verb near "upstream" (with a negative
#     lookahead blocking "<verb> from upstream" — "sync this file from
#     upstream" is RECEIVING from upstream, not proposing something TO it)
#     or the idiom "upstream this/it/that" (upstream used AS the verb);
#     retire/deprecate/decommission/sunset require a
#     service/project/app/application object in the same clause —
#     deliberately NOT "endpoint" ("we should deprecate that endpoint
#     eventually" stays silent: an endpoint deprecation is a code-level
#     change, not the whole-service retirement fabrik-decommission
#     targets).
#   NEW-3: bare \be2e\b fired on "we should add an e2e test for this
#     later" (bare test-authoring, not a request to RUN the certification
#     gauntlet) — anchored to a "run"/"do" verb near "e2e" (or the "e2e
#     run" collocation itself); "test this end to end" keeps firing
#     unchanged via the separate end-to-end pattern.
KEYWORD_STEMS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(data[- ]contract(\.md)?|veri\s+s[öo]zle[şs]me\w*)\b",
            re.I,
        ),
        "data-contract",
    ),
    (
        re.compile(
            r"\bFEATURES\.md\b|\bfeature\s+(inventory|contract)\b|\bfeatures\s+list\b"
            r"|\b(product'?s?|[üu]r[üu]n[üu]n)\s+(features|[öo]zellikleri)\b",
            re.I,
        ),
        "features",
    ),
    # BEFORE design-review: /fabrik-ui-design-review converges the FROZEN docs/ui-design.md, not a
    # rendered screen — its own SKIP says "never a running app (→ /design-review)". The first cut of
    # the design-review stem below matched "review ... UI" and swallowed it; the CONTRACT nouns
    # (contract / ui-design.md / design system) are what separate the two.
    (
        re.compile(
            r"\b(review|harden|converge|sa[ğg]laml[aá]?[şs]t[ıi]r\w*|g[öo]zden\s+ge[çc]ir\w*)\b"
            r"[^.]{0,40}\b(ui[- ]design(\.md)?|ui\s+design\s+contract|design\s+contract"
            r"|design\s+system|ekran\s+s[öo]zle[şs]mesi)\b"
            r"|\b(ui[- ]design(\.md)?|ui\s+design\s+contract|design\s+contract)\b[^.]{0,40}"
            r"\b(review|harden|converge|ready|haz[ıi]r\s*m[ıi]|incele\w*)\b"
            # Turkish names the artifact "UI tasarım sözleşmesi" and puts the verb LAST; the
            # English alternations above match neither word order nor the inflected noun.
            r"|\bui\s+tasar[ıi]m\s+s[öo]zle[şs]me\w*"
            r"|\bekran\s+s[öo]zle[şs]me\w*",
            re.I,
        ),
        "ui-design-review",
    ),
    # SCREENS are /fabrik-ui-design's own noun. Ordered AFTER ui-design-review (the review twin
    # wins on "review this UI design contract") and BEFORE `spec` — otherwise the broad design/spec
    # stem swallows it, which is how "bu ekranları/UI'ı tasarla" reached /fabrik-spec. The
    # deliberately ambiguous "let's design the app" is NOT matched here: /fabrik-spec advertises it
    # too and correctly wins, because a spec precedes screens in the pipeline.
    (
        re.compile(
            r"\b(design|lay\s+out|mock\s+up|wireframe)\b[^.]{0,25}\b(screens?|the\s+ui)\b"
            r"|\bekranlar[ıi]?\b[^.]{0,25}\btasarla\w*"
            r"|\bekran\w*\s*/\s*ui'?[ıi]?\s+tasarla\w*",
            re.I,
        ),
        "ui-design",
    ),
    # BEFORE both `spec` and `review`, because first match wins and BOTH would swallow this.
    # /fabrik-spec-review advertises TRIGGER "review/harden/converge this spec"; without this entry
    # "review this spec" resolved to the `review` stem -> fabrik-review, the CODE-DIFF reviewer,
    # whose own SKIP clause says it is not for a spec. Routing the operator's own advertised phrase
    # to the WRONG gate is worse than routing nowhere (audit of command 3 of 31, 2026-08-27).
    #
    # Deliberately NARROW: it requires a spec/design NOUN in the same clause as a
    # review/harden/converge VERB, so "review this diff", "code review" and "let's write a spec"
    # are untouched — the router's standing precision problem is over-firing, not under-firing.
    (
        re.compile(
            r"\b(review|harden|converge|stress|adversarial\w*|gozden|gözden)\b"
            r"[^.]{0,30}\b(spec|specification|spec'?[iıu]|tasar[ıi]m\w*)\b"
            r"|\b(spec|specification|tasar[ıi]m\w*)\b[^.]{0,30}"
            r"\b(gözden\s+ge[çc]ir\w*|sa[ğg]laml[aá]?[şs]t[ıi]r\w*|harden|converge)\w*"
            r"|\bis\s+(this|the|my)\s+(spec|specification|design)\b[^.]{0,30}"
            r"\b(solid|ready|sound|good|done)\b"
            r"|\b(spec|specification|design)\s+review\b"
        ),
        "spec-review",
    ),
    # THEN: the broad "spec" / "plan" / "review" stems below would
    # otherwise swallow "audit every spec and plan against the code", which is a
    # conformance sweep, not a spec-authoring or code-review request.
    (
        re.compile(
            r"\bconformance\b"
            r"|\bspecs?\b[^.]{0,20}\b(and|\+)\b[^.]{0,12}\bplans?\b[^.]{0,40}"
            r"\b(against|vs\.?|verify|verified|audit|conform\w*)\b"
            r"|\bwas\s+everything\b[^.]{0,40}\b(spec\w*|built|implemented)\b"
            r"|\bdid\s+we\s+(actually\s+)?(build|implement)\b[^.]{0,40}\bspec\w*"
            r"|\bspec\w*\b[^.]{0,40}\bactually\s+(built|implemented)\b"
            r"|\bspec\w*\b[^.]{0,30}\bger[çc]ekten\b[^.]{0,25}\byap[ıi]ld\w*"
            r"|\bspec\w*\b[^.]{0,20}\bplan\w*\b[^.]{0,30}\bdo[ğg]rula\w*",
            re.I,
        ),
        "conformance",
    ),
    (
        re.compile(
            r"\b(write|draft|create|do|start|need|let'?s|time to)\b[^.]{0,30}\b(spec|specification)\b"
            r"|\bspec\s+this\s+out\b"
            r"|\bspec(ification)?\s+for\s+(a|an|the)\b"
            r"|\b(write|create|do|start|need|let'?s|time to)\b[^.]{0,30}\bdesign\b"
            r"|\btasarla\w*"
            r"|\btasar[ıi]m\w*\b[^.]{0,20}\byap\w*",
            re.I,
        ),
        "spec",
    ),
    # Deploy-triad stems sit BEFORE the generic plan/review entries: first
    # match wins, and "plan the deployment" / "review the deployment plan"
    # would otherwise be swallowed by the generic patterns below (proven
    # live). The review stem precedes the authoring stem for the same
    # reason ("deploy plan" appears in both).
    (
        re.compile(
            r"\b(review|converge)\b[^.]{0,30}\bdeploy(ment)?\s+plan\b"
            r"|\bdeploy(ment)?\s+plan\b[^.]{0,30}\b(review|converge)\b"
            r"|\bda[ğg][ıi]t[ıi]m\s+plan[ıi]n[ıi]?\b[^.]{0,20}\bg[öo]zden ge[çc]ir\w*",
            re.I,
        ),
        "deploy-plan-review",
    ),
    (
        re.compile(
            r"\bplan\s+(the|this|a|an|our)\b[^.]{0,20}\bdeploy(ment)?\b"
            r"|\b(write|create|draft|author|make|need|let'?s|time to)\b[^.]{0,30}\bdeploy(ment)?\s+plan\b"
            r"|\bda[ğg][ıi]t[ıi]m[ıi]?\b[^.]{0,20}\bplanla(?!n)\w*",
            re.I,
        ),
        "deploy-plan",
    ),
    (
        re.compile(
            r"\b(make|write|create|do|start|need|let'?s|time to)\b[^.]{0,30}\bplan(ning)?\b"
            r"|\bplan\s+(the|this|a|an)\b"
            r"|\bplanla(?!n)\w*",
            re.I,
        ),
        "plan",
    ),
    # Noun-qualified TURKISH review/converge stems, all above the broad `review`.
    (
        # `\w*` not `\b`: Turkish is agglutinative — "sözleşme" appears as "sözleşmesini" here,
        # and a word-boundary anchor after the stem matches none of its inflected forms.
        re.compile(r"\bak[ıi][şs]\s+s[öo]zle[şs]me\w*|\byolculuklar\b[^.]{0,25}\beksiksiz\b", re.I),
        "flows-review",
    ),
    # The ENGLISH half, and it must sit ABOVE the broad `review` stem for the same reason
    # the two ui-design entries do: "review the flows contract" is a phrase /fabrik-review's
    # own SKIP clause DISCLAIMS, so letting `review` win points the operator at a gate that
    # says it is not the one. Only the TR half existed, so the EN triggers mis-routed.
    #
    # Why check_trigger_routing scored this 0 mis-routed: it grades the LITERAL advertised
    # string, `"review/harden the flows contract"` — which contains a slash, matches nothing,
    # and lands in the tolerated nowhere bucket. The phrase an operator actually types is the
    # EXPANSION, "review the flows contract", and that reached fabrik-review. The check says
    # so about itself ("cannot tell whether the phrase is one an operator would ever type");
    # this is what that limitation costs. (audit cmd 10/31, 2026-08-28)
    (
        re.compile(
            r"\b(review|harden|converge)\b[^.]{0,30}"
            r"\b(flows?(\.md)?\s+contract|journey\s+contract|flows\.md)\b",
            re.I,
        ),
        "flows-review",
    ),
    (
        re.compile(
            r"\bplan[ıi]?\b[^.]{0,25}\b(g[öo]zden\s+ge[çc]ir\w*|sa[ğg]laml[aá]?[şs]t[ıi]r\w*)"
            r"|\bplan\b[^.]{0,25}\buygulamaya\s+haz[ıi]r\b",
            re.I,
        ),
        "plan-review",
    ),
    (
        # ONE doc reconciled to the code — not the whole-tree sweep (/fabrik-docs-review).
        # "bu dokümanı" is singular; the sweep's own phrase is "tüm dokümanları".
        # EN patterns are DOC-SHAPED on purpose (found at cmd 23/31: the description's own two
        # EN triggers routed to NOTHING while the TR one routed): "converge <a doc>" must never
        # capture "converge the deploy plan" (deploy-plan-review's phrase) — so the object must
        # be doc-like (the word doc, a docs/ path, or a NAME.md), and the update form requires
        # a .md object with match/sync intent.
        re.compile(
            r"\bconverge\b[^.]{0,24}\b(?:docs?\b|docs/[\w.-]+|[A-Z][A-Z_]+\.md)"
            r"|\bupdate\b[^.]{0,30}\.md\b[^.]{0,24}\b(?:match|sync\w*|truth)"
            r"|\bbu\s+d[öo]k[üu]man[ıi]\b[^.]{0,30}\b(koda|g[üu]ncelle\w*|senkron\w*)",
            re.I,
        ),
        "doc-converge",
    ),
    (
        # The whole-tree sweep, above `review` so the bare verb does not swallow it. EN forms
        # added at cmd 23/31 (found while widening doc-converge: docs-review's own advertised
        # triggers "review all the docs" / "are the docs still accurate" routed to NOTHING).
        re.compile(
            r"\bt[üu]m\s+d[öo]k[üu]manlar[ıi]\b|\bd[öo]k[üu]manlar\b[^.]{0,25}\bkodla\b"
            r"|\breview\s+(?:all\s+)?the\s+docs\b"
            r"|\bare\s+the\s+docs\b[^.]{0,20}\b(?:accurate|current|up.to.date)",
            re.I,
        ),
        "docs",
    ),
    # /fabrik-rivals had NO stem while its description promised "fires bare-prose, no slash command
    # needed" — 0 of its 3 advertised phrases reached anything. The nouns are unusually distinctive
    # (competitor/rival/rakip), so this is one of the few places a stem can be added without the
    # over-firing risk that keeps the other 42 unrouted phrases deliberately unrouted.
    (
        re.compile(
            r"\b(competitors?|rivals?|rakip(ler)?\w*)\b"
            r"[^.]{0,40}\b(who|what|which|how|kim|ne\w*|nas[ıi]l|better|beat|ge[çc]\w*|do)\b"
            r"|\b(who|what|which|how)\b[^.]{0,30}\b(competitors?|rivals?)\b"
            r"|\bhow\s+do\s+we\s+beat\b"
            r"|\bonlar[ıi]\s+nas[ıi]l\s+ge[çc]er\w*"
            r"|\brakiplerimiz\s+kim",
            re.I,
        ),
        "rivals",
    ),
    # /design-review advertises "review this UI" and "check the design and accessibility of this
    # screen"; both fell to the broad `review` stem -> fabrik-review, whose SKIP clause literally
    # says "rendered-UI review (→ /design-review)". Narrow by construction: a UI/screen/visual NOUN
    # must sit in the same clause as the verb, so "review this diff" and "code review" are untouched.
    (
        re.compile(
            r"\b(review|check|audit|look at)\b[^.]{0,30}"
            r"\b(ui|screen|screens|frontend|front-end|visual|a11y|accessibility|styling)\b"
            r"|\b(ui|screen|frontend|front-end|visual|a11y|accessibility)\b[^.]{0,30}"
            r"\b(review|incele\w*|g[öo]zden\s+ge[çc]ir\w*)\b"
            r"|\bbu\s+aray[üu]z[üu]\s+incele\w*"
            r"|\btasar[ıi]m[ıi]?\s+ve\s+eri[şs]ilebilirli[ğg]i\w*",
            re.I,
        ),
        "design-review",
    ),
    # /fabrik-workflow-review advertises "review the epic or ticket breakdown" and "converge this
    # workflow artifact" — Traycer ARTIFACTS, which fabrik-review's SKIP also disclaims. Requires an
    # epic/ticket/workflow-artifact noun, so a plain "review" never reaches it.
    (
        re.compile(
            r"\b(review|converge|harden|sa[ğg]laml[aá]?[şs]t[ıi]r\w*|g[öo]zden\s+ge[çc]ir\w*)\b"
            r"[^.]{0,40}\b(epic|ticket\s+breakdown|ticket\s+outline|workflow\s+artifact"
            r"|decisions[- ]lock)\b"
            r"|\b(epic|ticket\s+breakdown|workflow\s+[çc][ıi]kt[ıi]\w*|workflow\s+artifact)\b"
            r"[^.]{0,40}\b(review|converge|incele\w*|sa[ğg]laml[aá]?[şs]t[ıi]r\w*)\b",
            re.I,
        ),
        "workflow-review",
    ),
    (
        # /fabrik-rules-review's advertised triggers all reached nothing (audit cmd 26/31,
        # 2026-08-29). The nouns (rule pack / windsurf rules / kural paket) are distinctive, but an
        # AUDIT-intent anchor is still required so "edit the windsurf rules" and ordinary
        # .windsurf/rules chatter never route to a compliance gauntlet; "check" is forward-only —
        # in the reverse direction it is too weak ("the windsurf rules check on line 5").
        re.compile(
            r"\b(audit|check|complian\w*)\b[^.]{0,30}\b(rules?[- ]packs?|windsurf\s+rules?)\b"
            r"|\b(rules?[- ]packs?|windsurf\s+rules?)\b[^.]{0,30}\b(audit\w*|complian\w*)\b"
            r"|\bkural\s+paket\w*\b[^.]{0,25}\b(uyum\w*|denetle\w*|kontrol\w*)"
            r"|\bwindsurf\s+kural\w*\b[^.]{0,25}\b(kontrol\w*|denetle\w*|uyum\w*)",
            re.I,
        ),
        "rules-review",
    ),
    (
        # ABOVE the generic review stem: /fabrik-repo-review's advertised triggers ("audit the
        # whole repo", "tüm repoyu denetle") reached NOTHING (audit cmd 25/31, 2026-08-29), and
        # "full project code review" mis-routed to fabrik-review, whose own SKIP disclaims
        # whole-repo sweeps. A TOTALITY word (whole/entire/full/tüm/tamamı) + a codebase noun is
        # required, so "audit the auth module" and "review this diff" still miss it.
        re.compile(
            r"\b(audit|sweep|review)\b[^.]{0,30}\b(whole|entire|full)\s+(repo(sitory)?|project|codebase)\b(?!\s*plan)"
            r"|\b(whole|entire|full)\s+(repo(sitory)?|project|codebase)\b(?!\s*plan)[^.]{0,30}\b(audit|sweep|review|bugs?)\b"
            r"|\bt[üu]m\s+(repo\w*|proje\w*|kod\w*)\b[^.]{0,25}\b(denetle\w*|incele\w*)"
            r"|\bprojenin\s+tamam\w*\b[^.]{0,25}\b(incele\w*|denetle\w*)",
            re.I,
        ),
        "repo-review",
    ),
    (
        # ABOVE the generic review stem (first match wins — the spec-review mis-route lesson):
        # the light sibling for spontaneous work; the Stop hook's unreviewed-spontaneous block
        # names these exact phrases.
        re.compile(
            r"\b(?:scoped|quick|lite)\s+review\b"
            r"|\breview\s+(?:my|this)\s+(?:small\s+)?change\w*"
            r"|\bh[ıi]zl[ıi]\s+incele\w*",
            re.I,
        ),
        "review-scoped",
    ),
    (
        re.compile(
            r"\bcode review\b"
            r"|\breview\s+(this|the|my|it)\b"
            r"|\b(a|the)\s+review\s+of\b"
            r"|\breview\s+pass\b"
            r"|\b(can you|please|let'?s|do a|run a|start a)\b[^.]{0,30}\breview\b"
            r"|\b(kodu|pr'?[ıi]|diff'?i)\s+incele\w*"
            r"|\bg[öo]zden ge[çc]ir\w*",
            re.I,
        ),
        "review",
    ),
    (
        re.compile(
            r"\b(update|write|create|do|start|need|let'?s|time to)\b[^.]{0,30}\b(docs|documentation)\b"
            r"|\b(docs|documentation)\b[^.]{0,20}\bneeds?\s+updat\w*"
            r"|\bd[öo]k[üu]man\w*\b[^.]{0,20}\bg[üu]ncelle\w*"
            r"|\bg[üu]ncelle\w*\b[^.]{0,20}\bd[öo]k[üu]man\w*",
            re.I,
        ),
        "docs",
    ),
    (
        re.compile(
            r"\b(run|do)\b[^.]{0,20}\be2e\b"
            r"|\be2e\s+run\b"
            r"|\bend[- ]to[- ]end\b"
            r"|\b(certify|certification)\b"
            r"|\buser test\b"
            r"|\bservice test\b"
            r"|\bfull test pass\b"
            r"|\bu[çc]tan\s+u[çc]a\b"
            r"|\bsertifika\w*"
            r"|\bkullan[ıi]c[ıi]\s+testi\b"
            r"|\bservis\s+testi\b",
            re.I,
        ),
        "test",
    ),
    (
        re.compile(
            r"\b(time to|let'?s|ready to|please|do a|start a)\b[^.]{0,30}\b(release|ship|publish)\b"
            r"|\bcut\s+a\s+release\b"
            r"|\bship\s+it\b"
            r"|\byay[ıi]nla\w*|\byay[ıi]na\s+al\w*",
            re.I,
        ),
        "release",
    ),
    # Sits BEFORE deploy-verify and the deploy-execution rule: "deploy checklist" carries the word
    # "deploy", and this must win it. No clash either way — deploy-verify's regex needs BOTH
    # "deploy" and "verify", and the execution rule needs "deploy it/this/now" or run/execute + a
    # deploy PLAN, neither of which any phrase here matches.
    (
        re.compile(
            r"\bdeploy(ment)?\s+checklist\b"
            r"|\bparity\s+contract\b"
            r"|\bwhat\s+must\s+prod(uction)?\s+(contain|have)\b"
            r"|\bdeploy\s+kontrol\s+listesi\w*"
            r"|\bprod'?da\s+ne\s+olmal[ıi]",
            re.I,
        ),
        "deploy-checklist",
    ),
    (
        re.compile(
            r"\bdeploy(ment)?\b.*\bverify\b|\bverify\b.*\bdeploy(ment)?\b|"
            r"\bda[ğg][ıi]t[ıi]m[ıi]?\b.*\bdo[ğg]rula\b|\bdo[ğg]rula\b.*\bda[ğg][ıi]t[ıi]m[ıi]?\b",
            re.I,
        ),
        "deploy-verify",
    ),
    # Deploy EXECUTION sits AFTER deploy-verify (its regex needs both words,
    # so "verify the deploy" keeps routing to deploy-verify) and after the
    # deploy-plan pair above. Bare TR "dağıt" is word-bounded — it never
    # matches "dağıtım"-prefixed forms.
    (
        re.compile(
            r"\bdeploy\s+(it|this|now)\b"
            r"|\b(run|execute)\b[^.]{0,30}\bdeploy(ment)?\s+plan\b"
            r"|\bda[ğg][ıi]t\b"
            r"|\bdeploy\s+plan[ıi]n[ıi]?\s+[çc]al[ıi][şs]t[ıi]r\w*",
            re.I,
        ),
        "deploy",
    ),
    # "docs" is checked BEFORE "catchup" above, so "döküman güncelle" still
    # resolves to docs, not catchup, on the keyword overlap.
    (
        re.compile(
            r"\bcatchup\b"
            r"|\bcatch(ing)?\s+up\b"
            r"|\bcatch\s+(this|the)\s+project\s+up\b"
            r"|\bproje\w*\b[^.]{0,20}\bg[üu]ncel\w*"
            r"|\bg[üu]ncel\w*\b[^.]{0,20}\bproje\w*",
            re.I,
        ),
        "catchup",
    ),
    (
        re.compile(
            r"\b(retire|deprecate|decommission|sunset)\b[^.]{0,30}\b(service|project|app|application)\b"
            r"|\b(service|project|app|application)\b[^.]{0,30}\b(retire|deprecate|decommission|sunset)\b"
            r"|\b(servisi|projeyi|uygulamay[ıi])\s+kald[ıi]r\w*"
            r"|\bemekliye\s+ay[ıi]r\w*"
            r"|\bdevre\s+d[ıi][şs][ıi]\s+b[ıi]rak\w*",
            re.I,
        ),
        "retire",
    ),
    (
        re.compile(
            r"\b(propose|file|send|submit|push)\b(?!\s+from\b)(\s+\w+){0,3}\s+upstream\b"
            r"|\bupstream\s+(this|it|that)\b"
            # audit cmd 29/31: the description advertises bare-prose firing, but 4 of 5
            # advertised phrases (1 EN + 3 TR) reached nothing. Each added form matches the
            # advertised phrasing tightly — "upstream proposal" as a noun (HUB mode's ask),
            # and the three TR idioms — so ordinary "upstream" chatter still misses.
            r"|\bupstream\s+proposal\w*\b"
            r"|\b[üu]st\s+ak[ıi][şs]a\s+bildir\w*"
            r"|\bfabrik'?ten\s+geliyor\b"
            r"|\bprojeden\s+gelen\s+[öo]neri\w*",
            re.I,
        ),
        "upstream",
    ),
]

# Round-2 review F6: Tier 2 (Haiku) must only ever be offered the SAME
# curated set Tier 1 can resolve to — STEM_SKILLS' targets plus the two
# dynamically-resolved test skills — never the full live roster. Without
# this a pipeline-only skill (execute-plan, generate-tests, repo-review,
# workflow-review, ui-design-review) that was never meant to be
# prompt-auto-triggered could still get matched by the fallback tier.
_TIER2_ROSTER: frozenset[str] = frozenset(STEM_SKILLS.values()) | {
    "fabrik-user-test",
    "fabrik-service-test",
}

_TYPE_RE = re.compile(r"^\s*type:\s*[\"']?([a-z0-9_-]+)[\"']?\s*$", re.I | re.M)
_STAGE_RE = re.compile(r"\bStage:\s*([A-Za-z0-9][A-Za-z0-9_-]*)")


# --- pure decision helpers (unit-tested) --------------------------------------


def first_regex_match(prompt: str) -> str | None:
    """Tier 1: first keyword-stem whose pattern is found in ``prompt``."""
    for pattern, stem in KEYWORD_STEMS:
        if pattern.search(prompt):
            return stem
    return None


def resolve_target(
    stem: str,
    roster_names: set[str],
    project_type: str | None,
    project_yaml_exists: bool = True,
) -> str | None:
    """Stem -> a skill name that ACTUALLY exists in the live roster (else None).

    "test" is the one dynamic case: headless project types route to
    fabrik-service-test, everything else (incl. a present-but-unrecognized
    type) to fabrik-user-test — mirrors CLAUDE.md's own UI-bearing/headless
    SCAFFOLD_TYPES split. Round-3 review F3-residual: when ``project.yaml``
    is ABSENT altogether (the hub repo, a non-scaffolded dir) the "test"
    stem must NOT route at all — there is no project to certify, so
    defaulting to fabrik-user-test would be a false positive, not a safe
    fallback. ``project_yaml_exists`` defaults True so every OTHER stem
    (and every existing caller that never had to think about this) is
    unaffected; only the "test" branch reads it.
    """
    if stem == "test":
        if not project_yaml_exists:
            return None
        if project_type == "wordpress":
            return None  # deploy-only type: no gauntlet exists for it
        target = "fabrik-service-test" if project_type in _HEADLESS_TYPES else "fabrik-user-test"
    else:
        target = STEM_SKILLS.get(stem)
    if target and target in roster_names:
        return target
    return None


def build_injection(skill_name: str, stage: str | None) -> dict:
    """The documented NESTED UserPromptSubmit injection shape (directive-with-escape)."""
    stage_label = stage or "unknown"
    message = (
        f"This request matches /{skill_name} (Stage: {stage_label}) — invoke the skill, "
        "or state in one line why it does not apply."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": message,
        }
    }


# --- filesystem probes (fail-open on any error) --------------------------------


def _roster_names(skills_dir: Path) -> set[str]:
    try:
        return {p.name for p in skills_dir.glob("fabrik-*") if (p / "SKILL.md").is_file()}
    except OSError:
        return set()


def _skill_stage(skills_dir: Path, skill_name: str) -> str | None:
    try:
        text = (skills_dir / skill_name / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return None
    m = _STAGE_RE.search(text)
    return m.group(1) if m else None


def _project_type(cwd: Path) -> str | None:
    try:
        text = (cwd / "project.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    m = _TYPE_RE.search(text)
    return m.group(1) if m else None


# --- Tier 2: Haiku fallback classifier (regex miss only) -----------------------

_CLASSIFY_INSTRUCTIONS = (
    "You are a strict router. Given a user's raw prompt and a list of available "
    "skills (name, pipeline stage), reply with EXACTLY ONE skill name from the "
    "list (e.g. fabrik-review) if the prompt clearly matches its purpose, or "
    "reply with the single word NONE if nothing clearly matches. Reply with "
    "nothing else — no punctuation, no explanation."
)


def _haiku_prompt(prompt: str, roster: list[tuple[str, str | None]]) -> str:
    lines = [f"- {name} (Stage: {stage or 'unknown'})" for name, stage in roster]
    return f"{_CLASSIFY_INSTRUCTIONS}\n\nSkills:\n" + "\n".join(lines) + f"\n\nUser prompt: {prompt!r}"


def haiku_classify(
    prompt: str,
    roster: list[tuple[str, str | None]],
    popen=subprocess.Popen,
) -> str | None:
    """Tier 2: ``claude -p --model haiku`` one-liner classifier. Empty-on-any-error.

    Round-2 review F1: the child MUST NOT inherit this project's cwd, or it
    loads THIS project's ``.claude/settings.json``, fires the nested
    SessionStart hook (an orphaned ``final_gate.py --lean`` run), and boots
    every configured MCP server — all cost, zero value, and it can never
    answer inside the timeout. Isolation, verified live against
    ``claude --help`` (v2.1.219, 2026-08-07):
      cwd=tempfile.gettempdir()  -> not a fabrik project; also makes any
                                    nested router/DoD hook that DOES fire
                                    hit its own non-fabrik-cwd exemption.
      stdin=subprocess.DEVNULL   -> nothing to read, never blocks on stdin.
      --setting-sources ""       -> INTENDED to load none of user/project/
                                    local settings. Round-3 review N2
                                    (evidence honesty): the CLI's own help
                                    text only documents the comma-separated
                                    LIST form — "Comma-separated list of
                                    setting sources to load (user, project,
                                    local)" — it never states empty-string
                                    none-semantics; that reading is an
                                    INFERENCE, and a live A/B probe (with vs
                                    without the flag) was inconclusive on
                                    this box. Treat this flag as best-effort
                                    defense-in-depth, NOT a verified
                                    guarantee — the load-bearing isolations
                                    are the scratch cwd above (independently
                                    verified: a nested hook there hits its
                                    own non-fabrik-cwd exemption) and
                                    --strict-mcp-config below (verified
                                    against its own help text).
      --strict-mcp-config        -> real flag: "Only use MCP servers from
                                    --mcp-config, ignoring all other MCP
                                    configurations"; --mcp-config is omitted
                                    here, so zero MCP servers load.
      --tools ""                 -> real flag: "... Use \"\" to disable all
                                    tools"; the classifier never needs one.
      --no-session-persistence   -> real flag: "Disable session persistence
                                    ... (only works with --print)"; nothing
                                    written to disk.
    ``--bare`` is deliberately NOT used (forces ANTHROPIC_API_KEY auth,
    off-limits for operational paths per CLAUDE.md). Measured cold-call
    latency with this exact flag set: see the ``HAIKU_TIMEOUT`` comment.

    Round-3 review N1: ``subprocess.run(timeout=)`` only kills the immediate
    child on expiry — the underlying ``claude`` CLI can fork/exec helpers
    that outlive it, leaking a process past the hard timeout. Spawn via
    ``Popen(start_new_session=True)`` (its own process group) and, on a
    ``communicate()`` timeout, SIGKILL the whole group
    (``os.killpg(os.getpgid(pid), signal.SIGKILL)``, guarded — the pid may
    already be gone) followed by a short bounded ``communicate(timeout=2)``
    to reap it. Either way the function returns None on timeout; the second
    ``communicate`` is cleanup only, its output is never read.
    """
    if not roster:
        return None
    try:
        proc = popen(
            [
                "claude",
                "-p",
                "--model",
                "haiku",
                "--setting-sources",
                "",
                "--strict-mcp-config",
                "--tools",
                "",
                "--no-session-persistence",
                _haiku_prompt(prompt, roster),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=tempfile.gettempdir(),
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return None
    try:
        stdout, _stderr = proc.communicate(timeout=HAIKU_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass  # process (group) already gone, or we lack permission — either way, give up cleanly
        try:
            proc.communicate(timeout=2)  # reap only; output is discarded, this call already timed out
        except Exception:
            pass
        return None
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    out = (stdout or "").strip()
    if not out or out.upper() == "NONE":
        return None
    candidate = out.splitlines()[0].strip().lstrip("/").strip()
    names = {name for name, _ in roster}
    return candidate if candidate in names else None


# --- entrypoint ------------------------------------------------------------


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        prompt = str(data.get("prompt") or "")
        cwd = Path(data.get("cwd") or os.getcwd()).resolve()

        if not prompt.strip():
            return 0
        if prompt.lstrip().startswith("/"):
            return 0  # explicit slash command — never override the operator
        if not (cwd / "scripts" / "final_gate.py").exists():
            return 0  # not a fabrik-style project → nothing to route

        skills_dir = Path.home() / ".claude" / "skills"
        roster_names = _roster_names(skills_dir)
        if not roster_names:
            return 0

        target: str | None = None
        stem = first_regex_match(prompt)
        if stem is not None:
            # Tier 1 HIT: resolve against the live roster, or stay silent.
            # F2: a resolved-but-not-yet-built stem (a sibling command that
            # hasn't landed) is a Tier-1 miss WITH a name — it must NEVER
            # fall through to Tier 2, which is regex-miss-only by contract.
            target = resolve_target(
                stem, roster_names, _project_type(cwd), (cwd / "project.yaml").exists()
            )
        elif os.environ.get("FABRIK_ROUTER_HAIKU") == "1":
            # Tier 1 MISS + opt-in: fall back to Haiku over the curated (F6)
            # roster. Round-3 dispatcher ruling: OFF by default — a Tier-1
            # miss with the env var unset stays silent WITHOUT ever spawning
            # a subprocess (see the module docstring + HAIKU_TIMEOUT comment
            # for the measured-latency rationale).
            roster_meta = [
                (n, _skill_stage(skills_dir, n)) for n in sorted(roster_names) if n in _TIER2_ROSTER
            ]
            candidate = haiku_classify(prompt, roster_meta)
            if candidate in roster_names:
                target = candidate
        # else: Tier 1 miss, Tier 2 not opted in -> stay silent (no subprocess)

        if not target:
            return 0  # no match on either tier → silence

        payload = build_injection(target, _skill_stage(skills_dir, target))
        sys.stdout.write(json.dumps(payload) + "\n")
        return 0
    except Exception as e:  # fail-open — never trap or block the prompt on a hook bug
        sys.stderr.write(f"[skill_router hook] error, staying silent: {e}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
