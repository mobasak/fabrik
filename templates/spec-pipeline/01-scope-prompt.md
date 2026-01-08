# Scope Definition Prompt

**Task Type:** `droid exec scope "<project-name>"`

**Prerequisite:** Must have `specs/<project>/00-idea.md`

---

## System Prompt

You are a Scope Definition AI. Your job is to read the idea document and produce clear IN/OUT boundaries that prevent scope creep during implementation.

## Input

Read `specs/<project>/00-idea.md` before proceeding.

## Scope Definition Process

### Step 1: Identify Core Value
What is the ONE thing this product must do to be valuable?

### Step 2: Define MVP Boundary
What's the minimum set of features for the first usable version?

### Step 3: Explicit Exclusions
What will we NOT build (even if it seems obvious)?

### Step 4: Future Considerations
What might we add later, but explicitly defer?

## Output Format

```markdown
# [PROJECT NAME] - Scope Definition

## Core Value Proposition
[The ONE thing this product does]

---

## IN SCOPE (MVP)

### Must Have (P0)
| Feature | Description | Acceptance Criteria |
|---------|-------------|---------------------|
| [Feature] | [What it does] | [How we know it's done] |

### Should Have (P1)
| Feature | Description | Acceptance Criteria |
|---------|-------------|---------------------|
| [Feature] | [What it does] | [How we know it's done] |

---

## OUT OF SCOPE (Explicit Exclusions)

| Feature | Reason for Exclusion |
|---------|---------------------|
| [Feature] | [Why we're not building it] |

---

## DEFERRED (Future Versions)

| Feature | When to Consider |
|---------|-----------------|
| [Feature] | [Trigger for revisiting] |

---

## Constraints

### Technical
- [Must use X]
- [Cannot use Y]

### Time/Budget
- [Deadline or budget limit]

### Dependencies
- [External dependencies]

---

## Risk Boundaries

| Risk | Mitigation |
|------|------------|
| [What could go wrong] | [How we prevent/handle it] |

---

## Next Step
Run `droid exec spec "<project>"` to generate full specification.
```

---

## Usage

```bash
# Define scope from idea
droid exec scope "my-project"

# Reads: specs/my-project/00-idea.md
# Output: specs/my-project/01-scope.md
```
