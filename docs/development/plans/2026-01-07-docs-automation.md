# Documentation Automation Execution Plan

**Last Updated:** 2026-01-07

---

## TASK: Automated Documentation Sync System

## GOAL
Ensure documentation stays in sync with code changes automatically, with CI enforcement.
Make documentation **self-healing, enforceable, and agent-safe**.

## DONE WHEN (all true)
- [ ] `make docs-check` fails CI on doc drift
- [ ] `docs_updater.py --sync` creates missing module stubs
- [ ] `docs_updater.py --check` validates structure without modifying
- [ ] Auto-generated sections use bounded blocks (human sections preserved)
- [ ] Tests exist for idempotency and bounded-block behavior
- [ ] Plans only exist in `docs/development/plans/` with `YYYY-MM-DD-<slug>.md` naming
- [ ] All plans indexed in `docs/development/PLANS.md`
- [ ] AGENTS.md updated with canonical rules

## OUT OF SCOPE (defer to observation phase)
- Watchdog script generation
- Service detection and SERVICES.md automation
- Full compose.yaml parsing

## GLOBAL CONSTRAINTS
- Language: Python 3.12
- No new deps (use stdlib + existing)
- Integrate with existing `scripts/enforcement/validate_conventions.py`
- Idempotent: running twice = no diff
- MVP first, observe 2 weeks before expanding

## Idempotency Rule (Non-Negotiable)

Auto-generated blocks MUST NOT change unless their rendered body changes.
In particular, timestamps/stamps inside `<!-- AUTO-GENERATED:* -->` blocks MUST only update when the block body changes.

## Invariant Ownership (One Authority Per Rule)

| Invariant | Authority | NOT enforced by |
|-----------|-----------|-----------------|
| Plan location + filename | `validate_conventions.py --strict` | `docs_updater.py` |
| PLANS index completeness | `docs_updater.py --check` | `validate_conventions.py` |
| Bounded-block drift | `docs_updater.py --check` | `validate_conventions.py` |
| Module reference doc exists | `docs_updater.py --check` | `validate_conventions.py` |
| Final referee | CI via `make docs-check` | — |

---

## DESIGN PRINCIPLES (Canonical)

### Single Source of Truth
- **Filesystem structure is canonical**
- Documentation reflects structure, never the reverse
- Docs cannot "invent" architecture

### Separation of Responsibility

| Actor | Allowed to do |
|-------|---------------|
| Human (you) | Architecture, final approval |
| Cascade / droid exec | Write content, plans, explanations |
| `docs_updater.py` | Enforce structure and invariants |
| CI | Final referee |

**Agents write, tools enforce.**

---

## DOCUMENTATION TAXONOMY (Final)

| Type | Purpose | Authority |
|------|---------|-----------|
| `docs/reference/*` | What the system *is* | Enforced |
| `docs/INDEX.md` | Structure map | Auto-generated (bounded) |
| `docs/development/plans/*` | What we *intend to build* | Agent-created |
| `docs/development/PLANS.md` | Plan index | Auto-indexed (bounded) |
| `tasks.md` | What is being executed | Human / agent |
| `docs/archive/*` | Historical record | Manual move |

**There are no other doc types.**

---

## AI REVIEW CONSENSUS

| Model | Approval | Key Feedback |
|-------|----------|--------------|
| GPT 5.1 | Conditional | Integrate validate_conventions, add stub templates |
| Claude | Conditional | Start MVP, avoid over-engineering, add --dry-run |

### Incorporated Feedback
- ✅ Bounded blocks prevent overwriting human sections
- ✅ `--dry-run` flag for safe preview
- ✅ Integrate with `validate_conventions --strict`
- ✅ Stub template with Fabrik-required fields + Ownership
- ✅ Version stamps in auto-blocks
- ✅ Tests for automation scripts
- ✅ MVP approach: structure sync first, module stubs second
- ✅ Plans folder with enforced naming convention
- ✅ Public module detection (only `__all__` or `README.md`)

---

## CANONICAL GATE

```bash
cd /opt/fabrik && source .venv/bin/activate && make docs-check
```

---

## EXECUTION STEPS

### Step 0 — Plans Structure + Index

**DO:**
1. Create `docs/development/plans/` directory
2. Create `docs/development/PLANS.md` with bounded auto-index block:
   ```markdown
   # Feature Plans Index

   <!-- AUTO-GENERATED:PLANS:START -->
   <!-- AUTO-GENERATED:PLANS v1 | YYYY-MM-DDTHH:MMZ -->
   ... (auto-indexed plan list)
   <!-- AUTO-GENERATED:PLANS:END -->
   ```

**GATE:** `ls docs/development/plans/` succeeds

**EVIDENCE:**
- Directory exists
- PLANS.md has bounded block

---

### Step 1 — Move This Plan + Update AGENTS.md

**DO:**
1. Move this plan to `docs/development/plans/2026-01-07-docs-automation.md`
2. Add this exact section to `AGENTS.md`:

```md
## Authority Model

- You write content.
- Tools enforce structure.
- CI is final authority.

## Documentation Rules

1) Do NOT create markdown files in repo root.
2) Feature/Execution plans:
   - Create ONLY under `docs/development/plans/`
   - Filename: `YYYY-MM-DD-<slug>.md`
   - Include: Goal, DONE WHEN, Out of Scope, Constraints, Steps, Owner, Links
3) Every new plan MUST be added to `docs/development/PLANS.md`.
4) Do NOT create new folders under `docs/` except via existing structure.
5) If you add a module under `src/`, ensure a reference doc exists:
   - `docs/reference/<module>.md`
   - If missing, run `docs_updater.py --sync`.
6) NEVER edit inside `<!-- AUTO-GENERATED:* -->` blocks.
   - Run `docs_updater.py --sync` instead.
7) All changes MUST keep `make docs-check` passing.

Violations will fail CI and must be fixed before merge.
```

**GATE:** Plan file in correct location, AGENTS.md updated

**EVIDENCE:**
- `docs/development/plans/2026-01-07-docs-automation.md` exists
- AGENTS.md has documentation rules section

---

### Step 2 — Add Plan Validation to validate_conventions.py

**DO:**
Add these exact checks:

**2.1 Plan documents location + naming (path + filename only):**
```python
PLAN_DIR = Path("docs/development/plans")
PLAN_NAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$")

def check_plan_docs(paths: list[Path]) -> list[str]:
    """Enforce: plans folder + YYYY-MM-DD-slug.md naming."""
    errors = []

    for p in paths:
        if p.suffix != ".md":
            continue

        # Files IN plan folder must have correct naming
        if p.is_relative_to(PLAN_DIR):
            if not PLAN_NAME_RE.match(p.name):
                errors.append(f"Invalid plan filename: {p.name} (must be YYYY-MM-DD-slug.md)")

    return errors
```

**2.2 Plan docs indexing is NOT enforced here**

Index completeness is enforced by `docs_updater.py --check` (single authority for this invariant).
Do NOT add indexing checks to `validate_conventions.py` to avoid duplicated/contradictory logic.

**GATE:** `python scripts/enforcement/validate_conventions.py --strict` passes

**EVIDENCE:**
- Plan validation checks added
- Misplaced plans would fail
- (Orphan plans checked by `docs_updater.py --check`, not here)

---

### Step 3 — Operational Contracts

**DO:**
1. Create `Makefile` with targets: `install`, `test`, `lint`, `format`, `check`, `docs-check`
2. Create `scripts/check.sh` integrating:
   - `ruff format --check .`
   - `ruff check .`
   - `pytest tests/ -q`
   - `python scripts/enforcement/validate_conventions.py --strict`
   - `python scripts/docs_updater.py --check`

**GATE:** `make check` runs without error

**EVIDENCE:**
- `Makefile` exists with all targets
- `scripts/check.sh` executable and passes

---

### Step 4 — Auto-Block Markers (Migration)

**DO:**
1. Add to `docs/INDEX.md`:
   ```markdown
   <!-- AUTO-GENERATED:STRUCTURE:START -->
   <!-- AUTO-GENERATED:STRUCTURE v1 | YYYY-MM-DDTHH:MMZ -->
   ... (structure map)
   <!-- AUTO-GENERATED:STRUCTURE:END -->
   ```
2. Preserve existing manual content outside blocks

**GATE:** `grep -q "AUTO-GENERATED:STRUCTURE" docs/INDEX.md`

**EVIDENCE:**
- Markers present
- Existing content preserved

---

### Step 5 — Extend docs_updater.py (MVP)

**DO:**
Add these exact functions:

**5.1 Public module detection (noise-safe):**
```python
def is_public_module(p: Path) -> bool:
    if not (p / "__init__.py").exists():
        return False
    if (p / "README.md").exists():
        return True
    init = (p / "__init__.py").read_text(encoding="utf-8", errors="ignore")
    return "__all__" in init

def detect_new_modules() -> list[Path]:
    base = Path("src/fabrik")
    mods = []
    for d in base.iterdir():
        if d.is_dir() and is_public_module(d):
            ref = Path("docs/reference") / f"{d.name}.md"
            if not ref.exists():
                mods.append(d)
    return mods
```

**5.2 Bounded block replacement (idempotent; stamp updates only when body changes):**
```python
BLOCK_RE = re.compile(
    r"(<!-- AUTO-GENERATED:STRUCTURE:START -->).*?(<!-- AUTO-GENERATED:STRUCTURE:END -->)",
    re.S,
)

def extract_block_body(text: str) -> str | None:
    """Extract current body from bounded block (excluding stamp line)."""
    match = BLOCK_RE.search(text)
    if not match:
        return None
    content = match.group(0)
    # Remove markers and stamp line to get pure body
    lines = content.split('\n')
    body_lines = [l for l in lines if not l.startswith('<!--')]
    return '\n'.join(body_lines).strip()

def replace_block(text: str, new_body: str) -> tuple[str, bool]:
    """Replace block only if body changed. Returns (new_text, changed)."""
    current_body = extract_block_body(text)
    if current_body == new_body.strip():
        return text, False  # No change needed — idempotent

    stamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")
    gen = f"\\1\n<!-- AUTO-GENERATED:STRUCTURE v1 | {stamp} -->\n{new_body}\n\\2"
    return BLOCK_RE.sub(gen, text), True
```

**Key:** Only update timestamp when content actually changes.

**5.3 CLI flags:**
```python
parser.add_argument("--check", action="store_true")
parser.add_argument("--sync", action="store_true")
parser.add_argument("--dry-run", action="store_true")
```

Behavior:
- `--check`: no writes, exit non-zero on drift
- `--sync`: create stubs + update blocks
- `--dry-run`: print unified diff only

**5.4 Stub creation (template-driven):**
```python
def create_stub(module: Path, tpl: Path):
    out = Path("docs/reference") / f"{module.name}.md"
    if out.exists():
        return
    content = tpl.read_text().format(
        module_name=module.name,
        date=datetime.utcnow().date().isoformat(),
    )
    out.write_text(content)
```

**5.5 Plans index sync (single authority for indexing; wire into --sync/--check):**
```python
PLANS_DIR = Path("docs/development/plans")
PLANS_INDEX = Path("docs/development/PLANS.md")
PLANS_BLOCK_RE = re.compile(
    r"(<!-- AUTO-GENERATED:PLANS:START -->).*?(<!-- AUTO-GENERATED:PLANS:END -->)",
    re.S,
)

def generate_plans_table() -> str:
    """Generate markdown table of all plan files."""
    plans = sorted(PLANS_DIR.glob("*.md"))
    if not plans:
        return "| Plan | Date | Status |\n|------|------|--------|\n| (none) | - | - |"

    lines = ["| Plan | Date | Status |", "|------|------|--------|"]
    for p in plans:
        # Extract date from filename YYYY-MM-DD-slug.md
        date = p.name[:10] if len(p.name) > 10 else "-"
        lines.append(f"| [{p.name}](plans/{p.name}) | {date} | Active |")
    return '\n'.join(lines)

def sync_plans_index(dry_run: bool = False) -> tuple[bool, str]:
    """Sync PLANS.md bounded block. Returns (changed, message)."""
    if not PLANS_INDEX.exists():
        return False, "Missing docs/development/PLANS.md"

    text = PLANS_INDEX.read_text()
    new_body = generate_plans_table()
    new_text, changed = replace_block_generic(text, new_body, PLANS_BLOCK_RE)

    if not changed:
        return False, "PLANS.md already up to date"

    if dry_run:
        return True, f"Would update PLANS.md:\n{new_body}"

    PLANS_INDEX.write_text(new_text)
    return True, "Updated PLANS.md"

def validate_plans_indexed() -> list[str]:
    """Check all plan files are in PLANS.md. For --check mode."""
    if not PLANS_INDEX.exists():
        return ["Missing docs/development/PLANS.md"]

    idx = PLANS_INDEX.read_text()
    errors = []
    for p in PLANS_DIR.glob("*.md"):
        if p.name not in idx:
            errors.append(f"Plan not indexed: {p.name}")
    return errors
```

**Authority decision:** Indexing validation lives in `docs_updater.py --check` (not `validate_conventions.py`) to avoid duplicate logic.

**GATE:** `python scripts/docs_updater.py --check` returns 0

**EVIDENCE:**
- `--check` mode works
- `--sync --dry-run` shows what would change
- Idempotent (running `--sync` twice = no diff)

---

### Step 6 — Module Stub Template

**DO:**
Create `templates/docs/MODULE_REFERENCE_TEMPLATE.md`:
```markdown
# {module_name}

**Last Updated:** {date}

## Purpose

[One-line description of what this module does]

## Usage

\`\`\`python
from fabrik.{module_name} import ...
\`\`\`

## Configuration

| Env Var | Description | Default |
|---------|-------------|---------|
| ... | ... | ... |

## Ownership

- **Owner:** [team/person]
- **SLA:** [response time expectation]

## See Also

- [Related doc](../path.md)
```

**GATE:** Template exists and `create_module_stub()` uses it

**EVIDENCE:**
- Template file exists
- Generated stubs match template structure (including Ownership)

---

### Step 7 — Tests

**DO:**
Create `tests/test_docs_updater.py`:
```python
def test_sync_readme_structure_idempotent():
    """Running sync twice produces no diff."""

def test_validate_docs_detects_missing_module_doc():
    """Missing docs/reference/<module>.md flagged."""

def test_bounded_block_preserves_manual_content():
    """Content outside AUTO-GENERATED blocks unchanged."""

def test_stub_creation_skips_existing():
    """Existing docs not overwritten."""
```

**GATE:** `pytest tests/test_docs_updater.py -q` passes

**EVIDENCE:**
- All tests pass
- Coverage for edge cases

---

### Step 8 — CI Integration

**DO:**
1. Add to `.github/workflows/ci.yml`:
   ```yaml
   - name: Docs Check
     run: make docs-check
   ```

2. Optional: Add `.pre-commit-config.yaml`:
   ```yaml
   - repo: local
     hooks:
       - id: docs-check
         name: Documentation validation
         entry: python scripts/docs_updater.py --check
         language: system
         pass_filenames: false
   ```

**GATE:** CI workflow exists and would run docs-check

**EVIDENCE:**
- Workflow file updated
- `make docs-check` integrated

---

### Step 9 — Observation Phase (2 weeks)

**DO:**
- Use system normally for 2 weeks
- Track pain points:
  - Is manual stub creation burdensome?
  - Any false positives in detection?
  - Edge cases not covered?

**GATE:** After 2 weeks, decide on:
- Service detection expansion
- SERVICES.md automation
- Watchdog stub generation

**EVIDENCE:**
- Decision documented
- Expansion plan (if needed)

---

## STOP CONDITIONS

- STOP if bounded block parsing breaks existing docs
- STOP if validate_conventions integration causes circular deps
- STOP if test failures indicate fundamental design flaw

---

## FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `docs/development/plans/` | Create directory |
| `docs/development/PLANS.md` | Create (with auto-index block) |
| `docs/development/plans/2026-01-07-docs-automation.md` | Move from reference/ |
| `AGENTS.md` | Update (add documentation rules) |
| `scripts/enforcement/validate_conventions.py` | Extend (add plan validation) |
| `Makefile` | Create |
| `scripts/check.sh` | Create |
| `docs/INDEX.md` | Add markers |
| `scripts/docs_updater.py` | Extend |
| `templates/docs/MODULE_REFERENCE_TEMPLATE.md` | Create |
| `tests/test_docs_updater.py` | Create |
| `.github/workflows/ci.yml` | Modify |
