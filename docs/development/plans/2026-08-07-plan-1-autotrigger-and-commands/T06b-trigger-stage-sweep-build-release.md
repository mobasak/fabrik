# T06b — TRIGGER + Stage sweep: build/certify/release/gate/utility skills (13)

Depends: —
Parallel: ⚡
Complexity: native
Docs: CHANGELOG entry via Deltas (shared with T06a — orchestrator dedupes)
Gate: python commands/assemble_commands.py --check

## Scope

Rewrite the frontmatter `description:` of the THIRTEEN remaining existing command sources with the
same TRIGGER + `Stage:` contract as T06a (EN + TR phrasings; negative boundaries — especially the
review family: review=changed-surface gate, repo-review=whole-repo audit, rules-review=pack
compliance, workflow-review=Traycer artifacts, design-review=rendered UI). Stages: execute-plan +
generate-tests = `4-build`; user-test + service-test + features = `5-certify`; release =
`6-release`; review + repo-review + rules-review + workflow-review + design-review = `gate`;
docs-review + doc-converge = `utility`. DO-NOT: change any command BODY; DO-NOT touch T06a's
files or the four new sources; keep length bands.

## Touches

- commands/_sources/fabrik-execute-plan.md
- commands/_sources/fabrik-review.md
- commands/_sources/fabrik-repo-review.md
- commands/_sources/fabrik-rules-review.md
- commands/_sources/fabrik-generate-tests.md
- commands/_sources/fabrik-docs-review.md
- commands/_sources/fabrik-doc-converge.md
- commands/_sources/fabrik-features.md
- commands/_sources/fabrik-user-test.md
- commands/_sources/fabrik-service-test.md
- commands/_sources/fabrik-release.md
- commands/_sources/fabrik-workflow-review.md
- commands/_sources/design-review.md

## Behavior Contract

- **Given** the 13 build/certify/release/gate/utility skill descriptions, **When** T06b lands, **Then** each carries a TRIGGER clause with concrete bare-prose phrasings and exactly one Stage: value (commands/_sources/fabrik-review.md:2).

## Context Files

- docs/reference/MD/ai-prompt-templates.md (Part C — distil, don't dump)
