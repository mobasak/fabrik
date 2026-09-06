# The doc↔script coupling — one declaration, rendered both ways

**What it answers:** *"which scripts implement this document, and which document must I update
when I change this script?"* Both directions, from **one** declaration.

Operator ask, 2026-09-06: *"in each doc, indicate the related scripts, in each script indicate the
related document to be kept always uptodate."*

## The one rule

**The `# AFTER-EDIT:` header in the script is the declaration. The doc side is generated from it.**

Nothing about a coupling is ever written twice. A doc's `## Related scripts` block is rendered
from the headers and is not hand-editable; to add a link, add the doc to the *script's* header.

This is the whole design, and it is a reaction to a measured failure. Hours before this was
built, `docs/workstation/claude-account-rotation.md` was found restating `~/.claude-fleet/caps.json`'s
values in prose — and **both** numbers it named had drifted, one of them the same day, in the very
commit that changed the value. Two places holding the same fact is not redundancy; it is a
guarantee that one of them is wrong and no one can tell which. So the header is the fact, and
every other surface derives from it. (`scripts/enforcement/_doc_registry.py` uses the same shape
for project docs: *"every surface DERIVES from PROJECT_DOCS here, so they can never drift again"*.)

## The two halves

| Direction | Mechanism | Enforced by |
|---|---|---|
| script → doc | `# AFTER-EDIT: <files>` in the first 25 lines, as a **comment** (never inside a docstring) | `scripts/enforcement/check_script_headers.py` — WARNs when a staged script has no header, or names a coupled file that was not staged in the same change |
| doc → script | a generated `## Related scripts` block between HTML markers | `scripts/render_doc_script_links.py --check` — fails when a page's block disagrees with the headers |

Both are **advisory (WARN)** rows in `final_gate.py`. Neither can turn a gate red today.

## Using it

```bash
python3 scripts/render_doc_script_links.py            # render the doc side
python3 scripts/render_doc_script_links.py --check    # verify only; mutates nothing, exit 1 if stale
```

Add a coupling by editing the **script**:

```python
#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/claude-account-rotation.md | tests/test_claude_rotate_v2.py
```

Separators `,` and `|` both work. `none` is a valid, honest answer — and the right one for a
script no document describes. Re-run the renderer and the page picks it up.

## What is deliberately NOT rendered

A `# AFTER-EDIT:` target is "what must I update when this changes", which is a wider question than
"what documents me". Four classes of target are real couplings that the doc side still skips, each
for a reason worth keeping:

| Skipped | Why |
|---|---|
| `commands/_sources/**` | the command corpus is **rendered box-wide** — a generated block here ships into every installed command and skill on the machine |
| `templates/**` | **fleet-synced** into ~46 project repos by the post-commit governance sync |
| `docs/development/plans/**`, `docs/superpowers/specs/**` | frozen artifacts: a CONVERGED status is an md5 of the content, and `check_convergence.py` reads the shape — appending voids both |
| `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `DECISIONS.md`, `LESSONS_LEARNT.md` | Doc Sync Matrix targets and append-only ledgers, named by dozens of scripts each; "the related scripts of CHANGELOG.md" is every script there is, which informs nobody |

Two more are reported rather than rendered, because they cannot be inverted onto a single page:

- **`NOT-A-PAGE`** — a directory (`docs/orchestrator/`) or glob (`docs/**`) target.
- **`MISSING`** — a named `.md` that does not exist. It is never created: conjuring the file would
  make a typo look correct forever. On its first real run this caught three scripts still naming a
  plan that had been moved to `archived/`.

**Symlinked scripts are skipped entirely.** A symlink's couplings belong to its target's world:
`scripts/verify_prod_parity.py` points at a scaffold template naming `docs/DEPLOYMENT.md`, which
every seeded project has and the hub does not. Reported as `MISSING` it would be a finding that is
always wrong — and an always-wrong finding is how a report stops being read.

## Coverage

| | |
|---|---|
| live tracked scripts carrying a header | **212 of 212** (hub, 2026-09-06) — ratchet LOCKED at zero |
| documentation pages carrying a rendered block | **42** |

## Backfill is retroactive, and ratcheted

Operator ruling 2026-09-06: *"it must force agents to backfill backwards, as most of the documents
and scripts dont have this."* `check_script_headers.py` is touch-on-change by its own design — *"a
script gains its header the next time it is edited"* — which grandfathers every script nobody
happens to touch. That was 427 of them across 36 of 44 repos at the last audit.

So coverage is ratcheted, on the contract `check_lint_ratchet.py` already proves here:

```bash
python3 scripts/render_doc_script_links.py --coverage          # ratchet (writes the baseline)
python3 scripts/render_doc_script_links.py --coverage --check   # report only
```

* the first run in a repo **seeds** at today's count and blocks nothing;
* a run that **raises** the headerless count **fails** — it names the files and the fix is one line;
* a run that lowers it **tightens** the floor, so the debt cannot be re-borrowed;
* **0 locks permanently.**

The baseline lives at `.fabrik/doc-script-baseline.json` (tracked, so it travels with the repo).
This row is **blocking** in `final_gate.py`, unlike the two advisory rows above.

⚠️ **The declaration must be a real COMMENT.** An `# AFTER-EDIT:` line inside the module docstring
declares nothing, and the parser is right to ignore it — it reads comment *tokens*, so a docstring's
example can never be mistaken for a declaration. Three hub scripts were wrong this way, and because
a naive `grep '#\s*AFTER-EDIT'` counts them, the first backfill of this very subsystem reported
**212 of 212 when the truth was 209**. A grader now pins the distinction.

The header side reaching 212/212 is the precondition `check_script_headers.py`'s own docstring
defers promotion-to-ERROR on. It is met **in the hub only** — fleet-wide the count was 427
headerless scripts across 36 of 44 repos at the last audit — so both rows stay advisory until
that is measured again.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/render_doc_script_links.py`
<!-- END related-scripts -->
