# Document Management System Proposal

**Created:** 2026-01-05
**Status:** Draft - Pending AI Consultation

## Problem Statement

Current state:
- Cascade and droid exec handle code changes
- Documentation updates are triggered manually or via auto-review system
- No dedicated documentation agent
- User needs to approve document changes (visible in Windsurf diff view)

## Requirements

### From Fabrik Conventions (windsurfrules, AGENTS.md)

1. **Every code change requires documentation update** - No exceptions
2. **Update docs/README.md structure map** if adding/moving/deleting files
3. **Add Last Updated date** to modified docs: `**Last Updated:** YYYY-MM-DD`
4. **Archive, don't delete** obsolete docs → `docs/archive/YYYY-MM-DD-topic/`
5. **Clear title, purpose statement, runnable examples, cross-references**
6. **User must see and approve changes** before they are applied

### User Approval Workflow

The user must be able to:
1. See proposed documentation changes (diff view)
2. Approve or reject changes
3. Request modifications before approval

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CODING AGENTS                                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Cascade    │    │ droid exec  │    │  SWE-1.5    │         │
│  │  (Windsurf) │    │  (Factory)  │    │  (Windsurf) │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
│         │                  │                  │                 │
│         └──────────────────┼──────────────────┘                 │
│                            ▼                                    │
│                   ┌────────────────┐                           │
│                   │  Code Changes  │                           │
│                   └────────┬───────┘                           │
└────────────────────────────┼────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DOCUMENTATION AGENT                             │
│                                                                  │
│  Trigger: Post-edit hook detects code changes                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Option A: Second Cascade Instance (Windsurf)           │   │
│  │  - Models: GPT-5.1-Codex, DeepSeek R1, Grok Code Fast   │   │
│  │  - User sees changes in Windsurf diff view              │   │
│  │  - Native approval workflow                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Option B: droid exec with Low-Cost Model               │   │
│  │  - Models: gemini-3-flash-preview (0.2x), glm-4.7 (0.25x)│   │
│  │  - Output: Proposed changes as git patch or markdown     │   │
│  │  - Approval: Review in separate tool/UI                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Option C: Droid Skill (fabrik-documentation)           │   │
│  │  - Invoked automatically by keyword detection            │   │
│  │  - Model: glm-4.6/4.7 (0.25x) or GPT-5.1-Codex (0.5x)  │   │
│  │  - Output: Creates PR or writes to staging branch        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    USER APPROVAL                                 │
│                                                                  │
│  Method 1: Windsurf Diff View (native)                          │
│  - See all changes inline                                        │
│  - Accept/Reject per file                                        │
│  - Modify before accepting                                       │
│                                                                  │
│  Method 2: Git Branch + PR                                       │
│  - docs-update branch created                                    │
│  - PR opened for review                                          │
│  - Merge when approved                                           │
│                                                                  │
│  Method 3: Staging Directory                                     │
│  - Changes written to docs/.staging/                            │
│  - Review script shows diff                                      │
│  - Accept script moves to final location                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Option Analysis

### Option A: Second Cascade Instance

**Pros:**
- Native Windsurf approval workflow (user already familiar)
- Full IDE context for documentation
- Free models available (GPT-5.1-Codex, DeepSeek R1)

**Cons:**
- Requires manual switch between instances
- May conflict with primary Cascade session

**Implementation:**
```python
# Post-edit hook triggers documentation request
# User switches to Cascade instance 2 in Windsurf
# Cascade 2 handles only documentation
```

### Option B: droid exec with Low-Cost Model

**Pros:**
- Fully automated pipeline
- Very low cost (0.2x-0.25x credits)
- Can run in background

**Cons:**
- No native approval UI
- Requires custom review workflow

**Implementation:**
```python
# scripts/docs_updater.py
def update_docs(changed_files: list[str]):
    """Generate doc updates using low-cost droid model."""
    prompt = f"""Files changed: {changed_files}

    Update documentation following Fabrik conventions:
    1. Update docs/README.md structure map if files added/moved
    2. Update relevant docs in docs/reference/
    3. Add Last Updated date
    4. Output as git patch format for review
    """

    result = droid_exec(
        prompt=prompt,
        model="gemini-3-flash-preview",  # 0.2x cost
        autonomy="low",  # Read-only, propose changes
        output_format="json"
    )

    # Write to staging for review
    write_staging(result.changes)
    notify_user("Doc updates ready for review")
```

### Option C: Droid Skill (fabrik-documentation)

**Pros:**
- Automatic invocation on relevant keywords
- Integrated into existing droid workflow
- Can be combined with Option B

**Cons:**
- Limited control over when it triggers
- May add latency to coding tasks

**Implementation:**
```yaml
# ~/.factory/skills/fabrik-documentation.yaml
name: fabrik-documentation
triggers:
  - "document"
  - "docs"
  - "readme"
  - "update docs"
model: glm-4.7  # Low cost
autonomy: low
```

---

## Recommended Solution

### Hybrid Approach: Option B + Staging Directory

```
┌──────────────────────────────────────────────────────────────┐
│  1. Code Change (Cascade/droid exec)                         │
│     ↓                                                        │
│  2. Post-edit hook detects change                            │
│     ↓                                                        │
│  3. Queue documentation update task                          │
│     ↓                                                        │
│  4. Low-cost droid (gemini-3-flash) analyzes and proposes    │
│     ↓                                                        │
│  5. Changes written to docs/.staging/                        │
│     ↓                                                        │
│  6. Notification sent to user                                │
│     ↓                                                        │
│  7. User reviews with: python scripts/review_docs.py         │
│     - Shows diff for each file                               │
│     - Options: [A]ccept, [R]eject, [E]dit, [S]kip           │
│     ↓                                                        │
│  8. Accepted changes moved to final location                 │
└──────────────────────────────────────────────────────────────┘
```

### Model Selection

| Role | Primary Model | Fallback | Cost |
|------|---------------|----------|------|
| Documentation Analysis | gemini-3-flash-preview | glm-4.7 | 0.2x-0.25x |
| Complex Docs (API refs) | GPT-5.1-Codex | claude-haiku-4-5 | 0.4x-0.5x |
| Structure Updates | glm-4.6 | — | 0.25x |

### Approval Workflow

```bash
# After docs update runs, user sees:
$ python scripts/review_docs.py

📄 Documentation Updates Ready (3 files)

[1] docs/reference/droid-exec-usage.md
    + Added DROID_DATA_DIR environment variable section
    + Updated subprocess handling documentation

    [A]ccept [R]eject [E]dit [D]iff [S]kip?

[2] docs/ENVIRONMENT_VARIABLES.md
    + Added DROID_EXEC_TIMEOUT variable

    [A]ccept [R]eject [E]dit [D]iff [S]kip?

[3] docs/README.md
    ~ Updated structure map (no new files)

    [A]ccept [R]eject [E]dit [D]iff [S]kip?

Summary: 2 accepted, 1 skipped, 0 rejected
Apply changes? [y/N]
```

---

## Questions for AI Consultation

1. **Is staging directory the best approach for user approval, or should we use git branches/PRs?**

2. **Should documentation updates block code commits, or run asynchronously?**

3. **What's the optimal model for documentation tasks - prioritize cost or quality?**

4. **How should we handle documentation conflicts when multiple code changes occur?**

5. **Should the documentation agent have write access or only propose changes?**

---

## Next Steps

1. Get feedback from GPT, Gemini Pro, and Sonnet (thinking modes)
2. Finalize architecture based on consultation
3. Implement core components
4. Create review_docs.py script
5. Update fabrik-post-edit.py hook to trigger docs updates
