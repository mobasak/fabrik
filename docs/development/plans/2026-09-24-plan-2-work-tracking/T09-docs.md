# T09 — the reference doc and the four docs the change makes stale

## Scope

Implements spec § Documentation landing sites for every doc except the two contracts (T08) and the
governance files (orchestrator):

- `docs/reference/work-tracking.md` (new — `ls` first): the item schema (spec § The durable item), the
  verbs (spec § The CLI), the lock and lease, the distributor, the drift classes and the blocking rule,
  the backlog view, the Task-tools env, and adoption (spec § Lifecycle). A `## Related scripts` block
  rendered by `python3 scripts/render_doc_script_links.py` from `scripts/work.py`'s `# AFTER-EDIT:`
  header (T01a), never hand-written.
- `docs/workstation/hooks-index.md`: the `thread_anchor.py` row (`docs/workstation/hooks-index.md:171`)
  gains the unfolded work block, the harvest writing decision items with `--repo`, claim renewal at
  each Stop, and the second chance.
- `docs/reference/thread-anchors.md`: § The DECISION harvest and clear (`docs/reference/thread-anchors.md:59-74`)
  and § Compaction survival (`:37-57`) describe the item path; the Tests line (`:81`) is re-counted
  with `grep -c "^def test_" tests/test_thread_anchor.py`.
- `docs/reference/multi-agent-operating-model.md`: the distributor beside the merge owner (§ Ownership
  surfaces, `docs/reference/multi-agent-operating-model.md:80-86`; § Merge protocol, `:94-96`).
- `docs/reference/agents/intel.md:77-78`: "The epic/ticket dispatcher lane is DEFERRED until a real epic
  queue exists (recorded, not built)" becomes the built lane: intel is the hub's distributor (D-395)
  and owns `work.py assign`.

Every claim in these docs is executed against the merged code before it is written.

DO-NOT: `INDEX.md`, `docs/README.md` (governance files — the orchestrator adds the rows); any code.

Depends: T03, T04, T05, T06
Parallel: ⚡
Complexity: simple
Gate: python3 scripts/render_doc_script_links.py --check
Gate: .venv/bin/python -m pytest tests/test_work_doc_verbs.py -q
Docs: the five docs above

## Touches
- docs/reference/work-tracking.md — PRIMARY PATH (new)
- docs/workstation/hooks-index.md
- docs/reference/thread-anchors.md
- docs/reference/multi-agent-operating-model.md
- docs/reference/agents/intel.md
- tests/test_work_doc_verbs.py (new — row 2: the verbs `work.py --help` lists against the verbs the doc names)

## Behavior Contract
- **Given** the merged code, **When** `python3 scripts/render_doc_script_links.py --check` runs, **Then** it exits 0 and `docs/reference/work-tracking.md`'s `## Related scripts` block names `scripts/work.py` (spec § Documentation landing sites)
- **Given** the merged docs, **When** every verb named in `docs/reference/work-tracking.md` is run with `--help` against `scripts/work.py`, **Then** each exists, and the doc names every verb `work.py --help` lists (spec § The CLI)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/40-documentation.md
- docs/workstation/hooks-index.md
- docs/reference/thread-anchors.md
- docs/reference/multi-agent-operating-model.md
- docs/reference/agents/intel.md
