# PROJECT WORKFLOWS

## New Project (With Planning) - RECOMMENDED

```bash
# 1. Define problem and explore approaches
planning-session

# 2. Create project from planning session
project-create-from-plan ./planning-session-*

# 3. Continue work
continue-project my-project
```

**What happens:**
- Structured problem definition with constraints
- AI consultation explores 3-5 approaches
- Decision matrix scores and selects best approach
- Complexity assessment (simple/medium/complex)
- Template auto-applied based on complexity
- Full project structure created
- Auto-checkpoint service enabled

---

## Quick Script (No Planning) - For Trivial Cases

```bash
project-create-quick my-script "One-file automation"
```

**Use when:**
- Single-file scripts (<200 lines)
- No external dependencies
- Throwaway automation
- Quick experiments

---

## Continue Existing Project

```bash
continue-project my-project
```

**Shows:**
- Current version and phase
- Planning artifacts (if any)
- Features built
- Project structure
- Recent context

---

## Key Commands

### Planning Phase
- `planning-session` - Start structured planning session
- `score-approaches` - Evaluate multiple approaches with criteria
- `synthesize-approaches` - Combine best ideas from multiple approaches

### Project Creation
- `project-create-from-plan` - Build project from planning artifacts
- `project-create-quick` - Bypass planning (simple scripts only)
- `generate-project-docs` - Generate documentation from plan

### Project Management
- `continue-project` - Resume work on existing project
- `ccli` - Context-aware CLI commands
- `bump-version` - Semantic version management

---

## Templates Available

### Simple (simple.yaml)
- Single file
- <200 lines
- No external dependencies
- Basic logging
- Quick automation scripts

### Medium (medium.yaml)
- 2-5 files
- <1000 lines
- 1-2 external dependencies
- Structured logging
- Config management
- CLI tools, scrapers, API clients

### Complex (complex.yaml)
- Multi-module architecture
- >1000 lines
- Database integration
- Multiple dependencies
- Production logging
- Error recovery
- Web services, production systems

---

## Workflow Rules

See CRITICAL_RULES.md §22 for mandatory protocols:
- New projects MUST use planning-session
- Templates auto-selected by complexity
- Quick path only for trivial scripts
- Planning artifacts preserved in project

---

## Examples

### Example 1: Web Scraper (Medium Complexity)
```bash
# Planning
planning-session
# Define: Scrape product prices from 3 sites
# Approaches: requests+bs4, scrapy, playwright
# Decision: requests+bs4 (simplest, sufficient)

# Creation
project-create-from-plan ./planning-session-20251107-1234/
# → Creates: /opt/price-scraper/ with medium template
# → Includes: main.py, config.py, scraper.py
# → Auto-checkpoint enabled

# Continue
continue-project price-scraper
# → Shows planning decision: "requests+bs4"
# → Shows structure and status
```

### Example 2: Quick Log Parser (Simple)
```bash
# No planning needed for trivial script
project-create-quick log-parser "Parse nginx logs"
# → Creates: /opt/log-parser/ with simple template
# → Single main.py file
```

---

## Integration Points

- **CRITICAL_RULES.md §22**: Mandatory project creation protocol
- **PYTHON_PRODUCTION_STANDARDS.md**: Production code requirements
- **AI_TAXONOMY.md**: AI tool selection (for AI projects)
- **Templates**: Simple, Medium, Complex project structures

---

**Last Updated**: 2025-11-07
**Version**: 2.1.0

---

## Technical Notes

### Tool Implementation
Planning tools in `/opt/tools/` are **wrapper scripts** (not symlinks) that call the actual tools in `/opt/context-management/planning/tools/`. This ensures proper path resolution for schemas and dependencies.

**Why wrappers instead of symlinks?**
The planning tools use `dirname "${BASH_SOURCE[0]}"` for path resolution, which breaks with symlinks. Wrapper scripts maintain proper directory context.
