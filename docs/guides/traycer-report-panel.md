# Traycer Report Panel

**Last Updated:** 2026-03-20

> **Purpose:** Windsurf extension that displays Traycer CLI agent execution reports with full history browsing.

---

## Overview

The Traycer Report Panel is a VS Code/Windsurf extension that:
- **Captures agent reports** from Traycer CLI agent stdout
- **Stores reports** with timestamps and slugs in `.droid/traycer-reports/`
- **Displays reports** in Windsurf sidebar with full history
- **Notifies** when new reports arrive

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Traycer Submits Job                                      │
│    factory_submit.py → .droid/queue/{job_id}.json          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Factory Processes Job                                     │
│    factory_wait.py picks up job from queue                  │
│    Executes Kilo CLI agent with prompt template             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Prompt Template Enforces Report Block                    │
│    ~/.traycer/prompt-templates/*.md includes:               │
│                                                              │
│    ## MANDATORY: Output Report Block (FINAL STEP)           │
│    BEGIN_TRAYCER_REPORT_MD                                  │
│    <agent execution report>                                 │
│    END_TRAYCER_REPORT_MD                                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Agent Outputs Report                                      │
│    Agent follows prompt → outputs delimited markdown block  │
│    factory_wait.py captures stdout                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Report Extraction                                         │
│    factory_wait.py pipes stdout to:                         │
│    scripts/traycer_write_report.py --slug {task_slug}       │
│                                                              │
│    Extraction logic:                                         │
│    - Finds BEGIN_TRAYCER_REPORT_MD / END_TRAYCER_REPORT_MD  │
│    - Extracts content between delimiters                    │
│    - Sanitizes slug (lowercase, alphanumeric + dash)        │
│    - Generates timestamp with microseconds                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Atomic Write to Disk                                      │
│    Writes to two locations:                                  │
│                                                              │
│    A) Timestamped file:                                      │
│       .droid/traycer-reports/YYYY-MM-DD-HHMMSS-µs-slug.md   │
│                                                              │
│    B) Latest symlink (atomic):                               │
│       .droid/traycer-reports/latest.md                       │
│       (temp file with PID → rename)                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Extension Detects New File                                │
│    FileSystemWatcher on .droid/traycer-reports/*.md         │
│    Ignores latest.md to avoid duplicate notifications       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. User Notification                                         │
│    Popup: "New Traycer report: {filename}" [View]           │
│    Click [View] → opens sidebar + displays report           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. Sidebar Display                                           │
│    Left sidebar icon (📄) → opens panel:                    │
│                                                              │
│    ┌─ Report History ──────────────────┐                    │
│    │ 🔄 Refresh  🗑️ Clear All           │                    │
│    │ ├─ auth-v2 (Mar 6, 11:15:23 PM)   │ ◄── Click to view │
│    │ ├─ manual-test (Mar 6, 10:47 PM)  │                    │
│    │ └─ feature-x (Mar 6, 09:32 PM)    │                    │
│    └────────────────────────────────────┘                    │
│                                                              │
│    ┌─ Report Content ──────────────────┐                    │
│    │ 2026-03-06-231523-...-auth-v2.md  │                    │
│    │                                    │                    │
│    │ # Execution Report                │                    │
│    │ ## ✅ COMPLETE                     │                    │
│    │ ...                                │                    │
│    └────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
/opt/{project}/
├── .droid/
│   ├── .gitignore                      # Track structure, ignore .md
│   ├── queue/                          # Traycer job queue
│   └── traycer-reports/
│       ├── .gitignore                  # Ignore *.md
│       ├── latest.md                   # Latest report (atomic write)
│       ├── 2026-03-06-231523-123456-auth-v2.md
│       ├── 2026-03-06-104711-987654-manual-test.md
│       └── 2026-03-06-093245-456789-feature-x.md
│
├── factory_wait.py                     # Integrates report extraction
├── scripts/
│   └── traycer_write_report.py        # Report extraction script
│
~/.traycer/
├── prompt-templates/
│   ├── Execute by Coder.md                          # Includes report block
│   ├── Phased YOLO Execute by Coder.md              # Includes report block
│   └── Reviewer.md                                  # Includes report block
│
~/traycer-report-panel/                 # Extension source (not in repo)
└── traycer-report-panel-0.2.0.vsix     # Installable extension
```

---

## Component Details

### 1. Report Extraction (`scripts/traycer_write_report.py`)

**Input:** Agent stdout (via stdin)

**Behavior:**
```python
# Extract content between delimiters
report_content = extract_between(
    stdout,
    "BEGIN_TRAYCER_REPORT_MD",
    "END_TRAYCER_REPORT_MD"
)

# Sanitize slug
slug = sanitize_slug(args.slug)  # lowercase, alphanumeric + dash

# Generate unique timestamp
timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")

# Write timestamped file
write_to_file(f"{timestamp}-{slug}.md", report_content)

# Atomic write to latest.md
temp_file = f".latest.md.tmp.{os.getpid()}"
write_to_file(temp_file, report_content)
rename(temp_file, "latest.md")  # Atomic on POSIX
```

**Output:**
- `.droid/traycer-reports/YYYY-MM-DD-HHMMSS-MICROSECONDS-slug.md`
- `.droid/traycer-reports/latest.md` (atomic symlink)

**Error Handling:**
- Missing delimiters → silent fail (no report written)
- Extraction errors → logged to stderr, never fails pipeline

---

### 2. Factory Integration (`factory_wait.py`)

**Location:** Lines 104-126

**Behavior:**
```python
# After agent execution
proc = subprocess.run(cmd, capture_output=True, text=True)
job["factory_stdout"] = proc.stdout

# Extract report (non-blocking, never fails job)
try:
    slug = os.getenv("TRAYCER_TASK_ID") or "traycer-task"
    report_writer = Path(__file__).resolve().parent / "scripts" / "traycer_write_report.py"

    report_proc = subprocess.run(
        [sys.executable, str(report_writer), "--slug", slug],
        input=proc.stdout,
        text=True,
        capture_output=True,
        timeout=10
    )

    # Make failures observable (but don't fail job)
    if report_proc.returncode != 0:
        job["factory_stderr"] += f"\n[WARN] Report extraction failed"
except Exception as e:
    job["factory_stderr"] += f"\n[WARN] Report extraction error: {e}"
```

**Key Properties:**
- Uses **absolute path** to script (works from any cwd)
- **10-second timeout** prevents hanging
- **Never fails job** even if report extraction fails
- Failures logged to `factory_stderr` for observability

---

### 3. Prompt Templates

**Location:** `~/.traycer/prompt-templates/`

**Modified Templates:**
1. `Execute by Coder.md`
2. `Phased YOLO Execute by Coder.md`
3. `Reviewer.md`

**Mandatory Section Added:**
```markdown
---

## MANDATORY: Output Report Block (FINAL STEP)

After producing your final execution report, output the full report wrapped in these exact delimiters (no modification allowed):

```
BEGIN_TRAYCER_REPORT_MD
<your full execution report content here>
END_TRAYCER_REPORT_MD
```

This enables traycer_write_report.py to extract and write .droid/traycer-reports/latest.md, which the Windsurf Report Panel watches and displays automatically.

If these delimiters are absent, the panel will not update (no pipeline failure, but report is lost).

---

{{planMarkdown}}
```

**Purpose:** Forces agents to wrap their reports in extractable delimiters.

---

### 4. Windsurf Extension

**Location:** `~/traycer-report-panel/` (outside repo)

**Architecture:**
- **TreeView:** Report history list (sorted by timestamp, newest first)
- **WebView:** Report content viewer (markdown rendered as escaped pre-text)
- **FileSystemWatcher:** Detects new `.md` files (ignores `latest.md`)
- **Commands:** Refresh, Open Report, Clear All

**Placement:** Activity bar (left sidebar) as `📄 Traycer Reports`

**Installation:**
```bash
# Extension is NOT part of Fabrik repo
# Must be installed manually in Windsurf
Extensions → Install from VSIX → traycer-report-panel-0.2.0.vsix
```

---

## Inheritance by Fabrik Projects

**Question:** Do all projects created via `fabrik scaffold` inherit this feature?

**Answer:** Partially.

| Component | Inherited? | How |
|-----------|------------|-----|
| `.droid/` structure | ✅ Yes | Created by `factory_submit.py` on first job |
| `.droid/traycer-reports/` | ✅ Yes | Created by `traycer_write_report.py` on first report |
| `factory_wait.py` integration | ✅ Yes | Lives in `/opt/fabrik/`, shared by all projects |
| `traycer_write_report.py` | ✅ Yes | Lives in `/opt/fabrik/scripts/`, shared by all projects |
| Prompt templates | ✅ Yes | Lives in `~/.traycer/`, shared globally |
| Windsurf extension | ⚠️ Manual | Must be installed once in Windsurf (affects all workspaces) |

**Summary:**
- **Report extraction works automatically** for all Fabrik projects
- **Extension must be installed once** (then works for all projects)

---

## Usage

### For Users

1. **Install Extension** (one-time):
   ```
   Extensions → Install from VSIX → traycer-report-panel-0.2.0.vsix
   ```

2. **Run Traycer Task:**
   ```bash
   # Example: Traycer submits a Kilo CLI review job
   traycer yolo "Review auth changes"
   ```

3. **View Report:**
   - Notification appears: "New Traycer report: 2026-03-06-..." [View]
   - Click [View] or click 📄 icon in sidebar
   - Click any report in history to view it

### For Developers

**Adding report extraction to new agents:**

Prompt template must include:
```markdown
## MANDATORY: Output Report Block (FINAL STEP)

BEGIN_TRAYCER_REPORT_MD
<report content>
END_TRAYCER_REPORT_MD
```

No other changes needed - extraction is automatic.

---

## Security

- **No JavaScript execution** in webview (CSP enforced)
- **HTML escaped** to prevent XSS
- **Reports stored locally** in project `.droid/` directory
- **No external network calls** from extension

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Extension not in sidebar | Not installed or wrong version | Uninstall all → Install v0.2.0 → Reload |
| No reports showing | No jobs run yet | Run a Traycer job |
| Report not extracted | Missing delimiters | Check prompt template includes report block |
| Extension shows old panel | Cached | Restart Windsurf completely |
| "latest.md" shown | Old extension (v0.1.0) | Uninstall → Install v0.2.0 |

---

## Changelog

**2026-03-06:** Initial implementation
- Created `traycer_write_report.py` for report extraction
- Integrated into `factory_wait.py` with absolute paths
- Updated 3 prompt templates with mandatory report blocks
- Created Windsurf extension v0.1.0 (panel placement)
- Redesigned extension v0.2.0 (sidebar placement + history)

---

## References

- **Implementation:** `/opt/fabrik/scripts/traycer_write_report.py`
- **Integration:** `/opt/fabrik/factory_wait.py` (lines 104-126)
- **Prompt Templates:** `~/.traycer/prompt-templates/`
- **Extension Source:** `~/traycer-report-panel/src/extension.ts`
- **CHANGELOG:** `/opt/fabrik/CHANGELOG.md`
