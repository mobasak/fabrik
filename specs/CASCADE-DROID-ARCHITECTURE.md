# Architecture Recommendation: Windsurf + Fabrik Integration

## 1. Executive Summary

This architecture solves the 12KB Windsurf context limit by splitting the monolithic `.windsurfrules` into modular, role-based rule files while establishing `AGENTS.md` as the canonical source of truth for all AI agents. It introduces a shared enforcement layer to ensure consistency between Windsurf (IDE) and Droid (CLI).

## 2. File Structure Strategy

We will move from a single 50KB file to a tiered structure.

### Level 1: Canonical Rules (All Agents)
*   **File:** `/opt/fabrik/AGENTS.md`
*   **Purpose:** Universal truths, architectural patterns, and documentation standards.
*   **Deployment:** Symlinked to project root as `AGENTS.md`.
*   **Size:** ~17KB (Keep <20KB).
*   **Access:** Referenced by Windsurf rules; read directly by Droid.

### Level 2: Windsurf Context Rules (Split <12KB)
*   **Directory:** `/opt/fabrik/.windsurf/rules/` (Symlinked to `.windsurf/rules/` in projects)
*   **Strategy:** Load only relevant rules based on file type or context.

| File | Content Focus | Trigger/Glob | Est. Size |
| :--- | :--- | :--- | :--- |
| `00-critical.md` | **Behavioral Core.** Execution tiers (A/B/C), Security (Credentials), "Stop-Wait" protocols, Port management. **Must include: "Read AGENTS.md first".** | *Always On* | 8KB |
| `10-python.md` | Python standards, venv, pip, FastAPI, Pydantic patterns. | `**/*.py`, `**/*.toml` | 8KB |
| `20-typescript.md` | Next.js, React, Tailwind, Node.js patterns. | `**/*.ts`, `**/*.tsx`, `**/*.js` | 6KB |
| `30-ops.md` | Docker, Coolify, Deployment checklists, Watchdogs, Microservices. | `Dockerfile`, `compose.yaml` | 10KB |
| `90-automation.md` | Droid interactions, Skills, Auto-run levels, Batch scripts. | Manual / `@droid` | 5KB |

### Level 3: Shared Enforcement
*   **Script:** `/opt/fabrik/scripts/enforcement/validate_conventions.py`
*   **Purpose:** Programmatic validation of rules (e.g., "Is port registered?", "Are secrets in 2 places?").
*   **Usage:**
    *   **Windsurf:** Invoked via rule trigger: "Run validation script before commit".
    *   **Droid:** Invoked as a Hook (`fabrik-conventions.py`).
    *   **CI:** Invoked in GitHub Actions.

## 3. Content Mapping & Deduplication

### Deduplication Principle
*   **AGENTS.md** defines *WHAT* and *WHY* (Architecture, Layout, Docs Standards).
*   **Windsurf Rules** define *HOW* (Command execution, IDE behavior, TUI interactions).

| Topic | Primary Location (Source of Truth) | Reference Location (Pointer) |
| :--- | :--- | :--- |
| **Command Tiers (A/B/C)** | `.windsurf/rules/00-critical.md` | `AGENTS.md` (Brief mention) |
| **Env Vars & Secrets** | `AGENTS.md` (The standard) | `00-critical.md` (Enforcement) |
| **Documentation Rules** | `AGENTS.md` | `00-critical.md` ("Update docs or stop") |
| **Project Layout** | `AGENTS.md` | `10-python.md` / `20-typescript.md` |
| **Deployment Checklist** | `30-ops.md` (Actionable list) | `AGENTS.md` (Overview) |
| **Fabrik Skills** | `AGENTS.md` | `90-automation.md` |
| **Watchdog Scripts** | `30-ops.md` (Template) | `AGENTS.md` (Requirement) |

## 4. Detailed Component Specs

### A. The Critical Rule File (`00-critical.md`)
Must be lean and authoritative.
1.  **Directive:** "First, read `AGENTS.md` in the root."
2.  **Command Execution:** The Tiers A/B/C definitions. (Unique to Windsurf's interactive nature).
3.  **Security:** "Check secrets in BOTH .env files."
4.  **Protocol:** "Before-Code" and "When-Stuck" steps.
5.  **Ports:** "Check PORTS.md before assigning."

### B. The Ops Rule File (`30-ops.md`)
Contains the heavy templates that bloat the current file.
1.  Dockerfile templates (Python/Node).
2.  Compose.yaml template.
3.  Watchdog script template.
4.  Deployment compliance checklist.

### C. The Enforcement Script (`validate_conventions.py`)
Instead of asking LLMs to "check if X follows convention", run code:
```python
def check_ports():
    # Parses PORTS.md and checks for conflicts
def check_secrets():
    # Verifies .env and master .env sync
def check_docker_health():
    # Verifies HEALTHCHECK instruction exists
```

## 5. Migration Plan

1.  **Prepare Directory:** Create `/opt/fabrik/.windsurf/rules/`.
2.  **Split Content:** Extract sections from `.windsurfrules` into the 5 target files.
3.  **Update AGENTS.md:** Ensure it covers any "Context" removed from rules, but keep it high-level.
4.  **Create Symlinks:**
    *   `/opt/fabrik/.windsurf/rules/` -> Project `.windsurf/rules/`
    *   `/opt/fabrik/AGENTS.md` -> Project `AGENTS.md`
5.  **Deprecate:** Remove `/opt/fabrik/windsurfrules` (the file) and replacing it with the directory structure.
6.  **Verify:** Test in a sample project to ensure Windsurf picks up the glob-based rules.

## 6. Gaps & Risk Mitigation

*   **Windsurf Glob Support:** Verification needed that Windsurf adheres to directory-based rule splitting with globs. *Fallback: If not supported, we must use a concatenation script to generate a single context file for the session, but splitting is preferred.*
*   **Context Fragmentation:** Risk of the agent missing a rule because it's in `30-ops.md` but the user is editing `main.py`.
    *   *Mitigation:* `00-critical.md` must link to others: "If touching deployment, Read `30-ops.md`".
*   **Symlink Complexity:** Windows/WSL symlinks can be tricky.
    *   *Mitigation:* Fabrik runs in WSL, so standard Linux symlinks work fine.

## 7. Recommendation

Proceed with the **Split & Link** strategy. The 50KB file is unsustainable. Moving to specific, loaded-on-demand rule files is the only way to respect the 12KB limit while maintaining the complexity of the Fabrik ecosystem.
