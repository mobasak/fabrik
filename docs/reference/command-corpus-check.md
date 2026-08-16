# Command-corpus integrity check

**What it is:** the gate check that keeps the `/fabrik-*` command corpus honest — every
reference a command makes must point at something that exists. Tool:
`scripts/enforcement/check_command_corpus.py` · Gate row: *Command Corpus (references
resolve — BLOCKING)*, Tier 2 · Tests: `tests/test_check_command_corpus.py`.

## Why it exists

The corpus is the instruction set every agent on this box runs on. When a command names
something that no longer exists, **nothing fails loudly**: the agent follows the
instruction, gets a degraded result, and reports success. It is the same failure shape as
a gate check that asserts nothing — a green signal with no substance behind it.

The founding case, found by the 2026-08-16 corpus audit:

```
fanout("research", …, web_tools=["exa","brave","firecrawl","context7"])
```

Those are **provider** names. `libs/subagents/web_tools.py::WEB_TOOL_NAMES` accepts only
**tool** names, and `loop.py` filters advertised schemas by that set — an unknown name
yields an empty list, whereupon `merged.pop("tools")` runs the agent with **no tools at
all**. Four commands (`/fabrik-spec`, `/fabrik-spec-review`, `/fabrik-plan-after-chat`,
`/fabrik-plan-review`) dispatched their "live search" grounders that way. The grounders
returned confident prose, the results table looked normal, and every spec and plan
grounded that way was ungrounded. No gate, test, or review caught it while the text stood.

## What it proves

Four mechanically decidable facts — no judgement, no network:

| # | Check | Caught live |
|---|---|---|
| 1 | `web_tools=[...]` names only tools in `WEB_TOOL_NAMES` (imported live, never copied) | 4 commands, the founding case |
| 2 | Every `/fabrik-x` · `/design-review` chain reference resolves to a real source | — |
| 3 | Every `scripts/**.py` a command tells an agent to run exists | — |
| 4 | `Co-Authored-By:` in commit templates matches CLAUDE.md's canonical trailer | 6 templates naming a retired model |

BLOCKING, because each is true/false with no tolerance band — and each was found violated
in a corpus that looked healthy.

**The important negative:** path-shaped look-alikes are *not* chain references.
`/opt/fabrik-lib`, `/run/fabrik-autoheal/pause` and `docs/reference/fabrik-mail.md` all
contain a `fabrik-<word>` token. A naive matcher reports four broken chains that were
never broken, and a check that cries wolf gets ignored — which is how a real break then
ships. The boundary lookarounds in `_CHAIN_RE` encode this, and
`test_path_lookalikes_are_not_chain_references` locks it.

## Anti-vacuity

`--selftest` feeds a known-bad corpus through the same predicates and requires **each** to
fire, then a known-good one and requires silence:

```console
$ python3 scripts/enforcement/check_command_corpus.py --selftest
✓ selftest: all 4 predicates fire on bad input and stay silent on good input
```

It was also proven **discriminating on the real defect**: reverting the `web_tools` fix in
a throwaway copy of the corpus turns the check red with the exact provider names named.

Both properties matter. A check that cannot fail is not a check, and a check that only
fails on synthetic fixtures has not been shown to catch the thing it was built for. See
`docs/workstation/liveness.md` for the general three-proof discipline this follows.

## Citation style it enforces by example

Two classes of citation rot were fixed alongside it and should not be reintroduced:

- **Never cite `CHANGELOG.md:<line>`.** The file is prepend-ordered, so a line number is
  wrong by the next entry. Eight citations in `/fabrik-decommission` had drifted ~2 700
  lines, pointing at unrelated text inside a *destructive* runbook. Cite the dated entry
  title instead.
- **Prefer a section anchor to a line range** when citing another command; two
  `/fabrik-deploy-verify` self-citations had slid three lines.

## Related

- `docs/reference/ticket-breadth.md` — the sibling advisory check on plan sets
- `docs/workstation/liveness.md` — heartbeat / vacuity-canary / doc-claim-binding proofs
- `.windsurf/rules/core/62-using-subagents.md` — the canonical `web_tools` recipe
