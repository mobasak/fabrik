<!-- ⚠️ NOT ORPHANED, despite zero `{{include:}}` references. This fragment is reused by INLINING:
     its content is copy-pasted into the orchestrator workflow docs and kept in sync by the version
     marker on the line below. An include-census over `commands/_sources/` cannot see that and will
     report it as dead — it has now done so twice (kaizen-shrink-audit.md:302-308 struck it as a
     census erratum; a corpus audit rediscovered it 2026-08-28). Before deleting, run:
     `rg -n "rule-grounding-cite v1" docs/orchestrator/` — non-zero hits mean it is LIVE. -->
<!-- rule-grounding-cite v1 · companion to rule-grounding-gate v1 (commands/_fragments/grounding-rules.md) -->
⚠️ **Constraints-Digest citation (BINDING):** every architecture, tool, or dependency selection in this
step cites a row of the upstream CONSTRAINTS DIGEST or states `unconstrained`; a selection that collides
with a digest row is DEAD. If no digest artifact exists upstream, STOP — run the Rule-grounding gate
before proceeding. fabrik-lib verdicts follow the same law: vendor/wrap/build cited, never assumed.
