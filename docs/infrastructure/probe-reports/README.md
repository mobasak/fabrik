# Infrastructure Probe Reports

YAML snapshots of live VPS state captured by [`scripts/audit_infra_vs_docs.py`](../../../scripts/audit_infra_vs_docs.py).

## Purpose

Per [Lesson 66](../../LESSONS_LEARNT.md), every "verified live" claim in `docs/infrastructure/vps-*.md` must be backed by a probe report committed alongside the doc edit citing it. Symptom-grep cannot find an absence; presence-probing can. This directory is the canonical home of those reports.

## Filename convention

`infra-probe-<UTC timestamp>.yaml` — e.g., `infra-probe-2026-05-31T22-36Z.yaml`. Timestamp is from `date -u +%Y-%m-%dT%H-%MZ`.

## How to add a new report

```bash
.venv/bin/python scripts/audit_infra_vs_docs.py
# Writes the YAML here automatically; also emits a Markdown table to stdout
# that you can paste into the cited doc's verification section.
```

## How to consume

Each infra doc that asserts live state has a header line:

```markdown
**Last probe report:** [`probe-reports/infra-probe-YYYY-MM-DDTHH-MMZ.yaml`](probe-reports/infra-probe-YYYY-MM-DDTHH-MMZ.yaml)
```

The probe-audit script's `--check` mode verifies that link resolves to a file present in this directory.

## Retention

Keep all reports — they're small (~2 KB each), tell a story over time, and are the only durable record of "what the fleet looked like on date X." No rotation needed for now.
