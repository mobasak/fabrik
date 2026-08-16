# T02 — Import-graph audit: the completeness mechanism for the move-set

## Scope

Build the tool that decides, mechanically, what may leave fabrik and what must stay. Hand-enumeration
provably fails here — the prior HARDENED plan needed 7 review rounds and still kept missing members, the
last being a live runtime subsystem. A **path-grep is not sufficient either**: it misses the
`sys.path.insert()` + bare-`import` idiom and `importlib.spec_from_file_location` computed paths, which is
exactly how the live Traycer coding-router reaches into the engine invisibly.

So: trace the REAL import graph from every retained fabrik entry-point, then classify every reached node
against the 7 inherited rules (delivered artifact · retained consumer · engine code · engine-describing doc ·
historical/immutable · retained consumer with an engine-INTERNAL import → vendor it · retained consumer with
an engine-resident DATA-FILE dep → relocate it). The tool **fails loud on any node it cannot classify** —
an unclassified node is the defect, not an acceptable residual.

**Pin the output, or nothing can consume it.** The classification is written to a named artifact
(`scripts/catalog-contract-audit.json`) with a stated schema — one record per node:
path, rule number, verdict, and for rule-7 whether the relocation is already SATISFIED. An unspecified blob
that no code reads for weeks is how stored-and-never-read actually materialises.

DO-NOT: this ticket ships the AUDIT only. It must not move, delete, or rewrite a single engine file — the
excise itself is a later plan, gated on this tool's output.

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/catalog_contract/test_audit.py -q
Docs: INDEX.md (files added) — orchestrator-applied via Deltas

## Touches
- scripts/catalog_contract_audit.py — PRIMARY PATH; carries the mandatory `# AFTER-EDIT:` header
- tests/catalog_contract/test_audit.py
- scripts/catalog-contract-audit.json

## Behavior Contract
- **Given** `scripts/kilo_auto_route.py` inserts the engine dir on `sys.path` and then bare-imports, **When** the audit runs, **Then** `classify_ticket`, `db_models` and `kilo_telemetry` are reported as rule-6 RETAIN nodes (scripts/kilo_auto_route.py:55)
- **Given** a retained consumer that resolves an engine-resident data file by path, **When** the audit runs, **Then** it is reported as a rule-7 RELOCATE node (scripts/claude_p_cost.py:53)
- **Given** a reached node matching none of the 7 rules, **When** the audit runs, **Then** the tool prints that node and exits non-zero (scripts/catalog_contract_audit.py:1)
- **Given** a node reachable ONLY via `sys.path.insert` + bare import, **When** the audit runs, **Then** it appears in the graph (a path-grep baseline would miss it) (scripts/kilo_auto_route.py:55)
- **Given** the audit completes with every node classified, **When** it exits, **Then** it writes `scripts/catalog-contract-audit.json` with one record per node (path, rule, verdict) for the later excise plan to consume (scripts/catalog_contract_audit.py:1)
- **Given** a rule-7 data-file dep whose consumer-dir copy already exists, **When** the audit runs, **Then** it is emitted as rule-7 SATISFIED rather than an open RELOCATE (scripts/claude_p_cost.py:53)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-07-26-catalog-extraction-design.md
- docs/development/plans/archived/2026-07-26-plan-1-ai-model-catalog-extraction.md
- scripts/kilo_auto_route.py
- scripts/coding-auto.sh
- scripts/claude_p_cost.py
- scripts/generate_kilo_agents.py
- scripts/enforcement/check_script_headers.py
