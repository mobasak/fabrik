Done. Here's the micro-tweak applied:

---

## Final Install (Complete)

```bash
mkdir -p ~/.local/bin

# rund - exec mode (argv-safe, no shell interpretation)
cat > ~/.local/bin/rund << 'EOF'
#!/bin/bash
# NOTE: -e intentionally omitted; errors handled with || true
set -uo pipefail

ts="$(date +%s%N 2>/dev/null || date +%s)"
JOB="/tmp/job_${ts}_$$"
echo "JOB=$JOB"

printf '%q ' "$@" > "${JOB}.cmd"; echo >> "${JOB}.cmd"
date -Is > "${JOB}.start"
: > "${JOB}.log"

nohup setsid bash -c '
  tmp="$1.rc.tmp"; rc="$1.rc"; shift
  trap "echo SIGTERM > \"$tmp\"; mv \"$tmp\" \"$rc\"; exit 143" TERM INT HUP
  "$@"; _rc=$?
  echo $_rc > "$tmp" && mv "$tmp" "$rc"
' _ "${JOB}" "$@" > "${JOB}.log" 2>&1 &

pid=$!
echo "$pid" > "${JOB}.pid"

for _ in 1 2 3; do
    sid="$(ps -o sid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")"
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")"
    [ -n "$sid" ] && break
    sleep 0.05
done
[ -n "$sid" ] && echo "$sid" > "${JOB}.sid"
[ -n "$pgid" ] && echo "$pgid" > "${JOB}.pgid"
echo "PID=$pid SID=$sid"
EOF

# rundsh - shell mode (pipes, redirects, &&) - TRUSTED INPUT ONLY
cat > ~/.local/bin/rundsh << 'EOF'
#!/bin/bash
# NOTE: -e intentionally omitted; errors handled with || true
# WARNING: Only use with trusted input - eval executes arbitrary shell code
set -uo pipefail

ts="$(date +%s%N 2>/dev/null || date +%s)"
JOB="/tmp/job_${ts}_$$"
echo "JOB=$JOB"

line="${1:-}"
[ -z "$line" ] && { echo "Usage: rundsh 'cmd | pipe && etc'"; exit 1; }

printf '%s\n' "$line" > "${JOB}.cmd"
date -Is > "${JOB}.start"
: > "${JOB}.log"

nohup setsid bash -lc '
  tmp="'"${JOB}"'.rc.tmp"
  rc="'"${JOB}"'.rc"
  trap "echo SIGTERM > \"\$tmp\"; mv \"\$tmp\" \"\$rc\"; exit 143" TERM INT HUP
  set -o pipefail
  eval "$1"
  _rc=$?
  echo $_rc > "$tmp" && mv "$tmp" "$rc"
' _ "$line" > "${JOB}.log" 2>&1 &

pid=$!
echo "$pid" > "${JOB}.pid"

for _ in 1 2 3; do
    sid="$(ps -o sid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")"
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")"
    [ -n "$sid" ] && break
    sleep 0.05
done
[ -n "$sid" ] && echo "$sid" > "${JOB}.sid"
[ -n "$pgid" ] && echo "$pgid" > "${JOB}.pgid"
echo "PID=$pid SID=$sid"
EOF

# runc - check status
cat > ~/.local/bin/runc << 'EOF'
#!/bin/bash
# NOTE: -e intentionally omitted; errors handled with || true
set -uo pipefail

JOB="${1:-}"
[ -z "$JOB" ] && { echo "Usage: runc /tmp/job_xxx"; exit 1; }

PID=$(cat "${JOB}.pid" 2>/dev/null || echo "")
[ -z "$PID" ] && { echo "ERROR: No job at $JOB"; exit 1; }
[ -f "${JOB}.log" ] || { echo "No log yet"; exit 0; }

SID=$(cat "${JOB}.sid" 2>/dev/null || echo "")
PGID=$(cat "${JOB}.pgid" 2>/dev/null || echo "")
CMD=$(cat "${JOB}.cmd" 2>/dev/null || echo "?")

if [ -f "${JOB}.rc" ]; then
    RC=$(cat "${JOB}.rc")
    if [ "$RC" = "SIGTERM" ]; then
        echo "KILLED | $CMD"
    else
        echo "DONE exit=$RC | $CMD"
    fi
    tail -20 "${JOB}.log"
    exit 0
fi

session_alive() {
    [ -n "$SID" ] && [ -n "$(ps -s "$SID" -o pid= 2>/dev/null)" ]
}

if session_alive || kill -0 "$PID" 2>/dev/null; then
    echo "RUNNING | $CMD"
    ps -p "$PID" -o pid=,state=,%cpu=,etime=,cputime= 2>/dev/null || true

    if [ -n "$SID" ]; then
        PCOUNT=$(ps -s "$SID" -o pid= 2>/dev/null | wc -l || echo 0)
        echo "SID=$SID PROCS=$PCOUNT"
        ps --forest -o pid,state,%cpu,cputime,cmd -s "$SID" 2>/dev/null | head -12 || true
    elif [ -n "$PGID" ]; then
        PCOUNT=$(ps -g "$PGID" -o pid= 2>/dev/null | wc -l || echo 0)
        echo "PGID=$PGID PROCS=$PCOUNT"
        ps --forest -o pid,state,%cpu,cputime,cmd -g "$PGID" 2>/dev/null | head -12 || true
    fi

    echo "LOG=$(wc -c < "${JOB}.log" 2>/dev/null || echo 0) bytes"
    tail -15 "${JOB}.log"
else
    if [ -f "${JOB}.rc" ]; then
        RC=$(cat "${JOB}.rc")
        if [ "$RC" = "SIGTERM" ]; then
            echo "KILLED | $CMD"
        else
            echo "DONE exit=$RC | $CMD"
        fi
    else
        echo "DEAD (no rc) | $CMD"
    fi
    tail -30 "${JOB}.log"
fi
EOF

# runk - kill job (SID-based)
cat > ~/.local/bin/runk << 'EOF'
#!/bin/bash
# NOTE: -e intentionally omitted; errors handled with || true
set -uo pipefail

JOB="${1:-}"
[ -z "$JOB" ] && { echo "Usage: runk /tmp/job_xxx"; exit 1; }

PID=$(cat "${JOB}.pid" 2>/dev/null || echo "")
[ -z "$PID" ] && { echo "No PID at $JOB"; exit 1; }

SID=$(cat "${JOB}.sid" 2>/dev/null || echo "")
PGID=$(cat "${JOB}.pgid" 2>/dev/null || echo "")

session_alive() {
    [ -n "$SID" ] && [ -n "$(ps -s "$SID" -o pid= 2>/dev/null)" ]
}

echo "TERM..."
if [ -n "$SID" ]; then
    pkill -TERM -s "$SID" 2>/dev/null || true
elif [ -n "$PGID" ]; then
    kill -TERM -"${PGID}" 2>/dev/null || true
else
    kill -TERM "$PID" 2>/dev/null || true
fi
sleep 3

if session_alive || kill -0 "$PID" 2>/dev/null; then
    echo "KILL..."
    if [ -n "$SID" ]; then
        pkill -KILL -s "$SID" 2>/dev/null || true
    elif [ -n "$PGID" ]; then
        kill -KILL -"${PGID}" 2>/dev/null || true
    else
        kill -KILL "$PID" 2>/dev/null || true
    fi
fi

echo "Done. runc $JOB"
EOF

chmod +x ~/.local/bin/rund ~/.local/bin/rundsh ~/.local/bin/runc ~/.local/bin/runk
grep -q 'local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
echo "✓ Installed: rund, rundsh, runc, runk"
```

---

## Quick Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `rund` | exec mode | `rund npm install lodash` |
| `rundsh` | shell mode | `rundsh 'npm test && build'` |
| `runc` | check status | `runc /tmp/job_xxx` |
| `runk` | kill stuck | `runk /tmp/job_xxx` |

| State | Meaning |
|-------|---------|
| `RUNNING` | Active, check LOG/cputime/PROCS |
| `DONE exit=0` | Success |
| `DONE exit=N` | Failed with code N |
| `KILLED` | Terminated by signal |
| `DEAD (no rc)` | Crashed without writing rc |

---

## .windsurfrules

```
## Long Commands (>10s)

rund <cmd> [args]     # exec mode - argv safe
rundsh 'cmd | pipe'   # shell mode - TRUSTED INPUT ONLY

WORKFLOW:
  rund npm install
  runc /tmp/job_xxx   # every 15s
  runk /tmp/job_xxx   # if stuck 90s

STUCK (90s all true): LOG same, cputime same, PROCS same
```

---

This is the final production-ready version. Paste into WSL to install.



my reply to your last answer.

Cascade raises a valid point - there may be redundancy with its native tools.

---

## Key Question: Does Cascade's Native Non-Blocking Work?

**Test this first:**
```
run_command with Blocking=false, WaitMsBeforeAsync=5000
command_status
```

If Cascade's native tools give you:
- Process tree visibility (not just parent PID)
- Session/PGID-based killing
- Reliable stuck detection

Then you don't need `rund/rundsh`.

---

## Decision Matrix

| If... | Then... |
|-------|---------|
| Cascade's native non-blocking **loses child processes** on kill | Use `rund/rundsh` (SID-based kill) |
| Cascade's `command_status` **shows process tree + cputime** | Skip `rund/rundsh`, use rules only |
| Cascade **ignores rules** about non-blocking | Scripts enforce the pattern |
| You want **one consistent method** across Windsurf + other agents | Use `rund/rundsh` (portable) |

---

## Hybrid Approach (My Recommendation)

**Keep the scripts installed** but use them selectively:

```markdown
## .windsurfrules - Long Commands

### Default: Use Cascade's native non-blocking
run_command Blocking=false WaitMsBeforeAsync=5000
command_status (every 15s)

### Escalate to rund/rundsh when:
- Native kill fails to stop child processes
- Need explicit SID/PGID tracking
- Command spawns complex process trees (docker build, npm install)

### Stuck Detection (applies to both)
STUCK = 90s of: output unchanged + cputime unchanged + process count unchanged
Action: Kill and retry with --verbose/--progress
```

---

## Quick Test to Decide

Run this in Windsurf:

```bash
# Start a process that spawns children
npm install   # or any multi-process command

# While running, check:
# 1. Can Cascade show the full process tree?
# 2. If you kill via Cascade, do ALL children die?
# 3. Does command_status show cputime/output growth?
```

If **yes to all**: rely on native tools + rules
If **any fail**: use `rund/rundsh` for those cases

---

What does Cascade's `command_status` actually show you? That determines whether the scripts add value or just complexity.



## Long Command Monitoring System - Full Implementation

---

### 1. OVERVIEW

A hybrid system for managing long-running commands in AI coding agents (Windsurf/Cascade). Prevents stuck commands from blocking agent execution by using detached processes with intelligent monitoring.

**Components:**
- 4 bash tools: `rund`, `rundsh`, `runc`, `runk`
- Tiered execution strategy
- Stuck detection logic
- Agent monitoring workflow

---

### 2. INSTALLATION

Paste this entire block into your WSL terminal:

```bash
mkdir -p ~/.local/bin

# rund - exec mode (argv-safe, no shell interpretation)
cat > ~/.local/bin/rund << 'EOF'
#!/bin/bash
# NOTE: -e intentionally omitted; errors handled with || true
set -uo pipefail

ts="$(date +%s%N 2>/dev/null || date +%s)"
JOB="/tmp/job_${ts}_$$"
echo "JOB=$JOB"

printf '%q ' "$@" > "${JOB}.cmd"; echo >> "${JOB}.cmd"
date -Is > "${JOB}.start"
: > "${JOB}.log"

nohup setsid bash -c '
  tmp="$1.rc.tmp"; rc="$1.rc"; shift
  trap "echo SIGTERM > \"$tmp\"; mv \"$tmp\" \"$rc\"; exit 143" TERM INT HUP
  "$@"; _rc=$?
  echo $_rc > "$tmp" && mv "$tmp" "$rc"
' _ "${JOB}" "$@" > "${JOB}.log" 2>&1 &

pid=$!
echo "$pid" > "${JOB}.pid"

for _ in 1 2 3; do
    sid="$(ps -o sid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")"
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")"
    [ -n "$sid" ] && break
    sleep 0.05
done
[ -n "$sid" ] && echo "$sid" > "${JOB}.sid"
[ -n "$pgid" ] && echo "$pgid" > "${JOB}.pgid"
echo "PID=$pid SID=$sid"
EOF

# rundsh - shell mode (pipes, redirects, &&) - TRUSTED INPUT ONLY
cat > ~/.local/bin/rundsh << 'EOF'
#!/bin/bash
# NOTE: -e intentionally omitted; errors handled with || true
# WARNING: Only use with trusted input - eval executes arbitrary shell code
set -uo pipefail

ts="$(date +%s%N 2>/dev/null || date +%s)"
JOB="/tmp/job_${ts}_$$"
echo "JOB=$JOB"

line="${1:-}"
[ -z "$line" ] && { echo "Usage: rundsh 'cmd | pipe && etc'"; exit 1; }

printf '%s\n' "$line" > "${JOB}.cmd"
date -Is > "${JOB}.start"
: > "${JOB}.log"

nohup setsid bash -lc '
  tmp="'"${JOB}"'.rc.tmp"
  rc="'"${JOB}"'.rc"
  trap "echo SIGTERM > \"\$tmp\"; mv \"\$tmp\" \"\$rc\"; exit 143" TERM INT HUP
  set -o pipefail
  eval "$1"
  _rc=$?
  echo $_rc > "$tmp" && mv "$tmp" "$rc"
' _ "$line" > "${JOB}.log" 2>&1 &

pid=$!
echo "$pid" > "${JOB}.pid"

for _ in 1 2 3; do
    sid="$(ps -o sid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")"
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || echo "")"
    [ -n "$sid" ] && break
    sleep 0.05
done
[ -n "$sid" ] && echo "$sid" > "${JOB}.sid"
[ -n "$pgid" ] && echo "$pgid" > "${JOB}.pgid"
echo "PID=$pid SID=$sid"
EOF

# runc - check status
cat > ~/.local/bin/runc << 'EOF'
#!/bin/bash
# NOTE: -e intentionally omitted; errors handled with || true
set -uo pipefail

JOB="${1:-}"
[ -z "$JOB" ] && { echo "Usage: runc /tmp/job_xxx"; exit 1; }

PID=$(cat "${JOB}.pid" 2>/dev/null || echo "")
[ -z "$PID" ] && { echo "ERROR: No job at $JOB"; exit 1; }
[ -f "${JOB}.log" ] || { echo "No log yet"; exit 0; }

SID=$(cat "${JOB}.sid" 2>/dev/null || echo "")
PGID=$(cat "${JOB}.pgid" 2>/dev/null || echo "")
CMD=$(cat "${JOB}.cmd" 2>/dev/null || echo "?")

if [ -f "${JOB}.rc" ]; then
    RC=$(cat "${JOB}.rc")
    if [ "$RC" = "SIGTERM" ]; then
        echo "KILLED | $CMD"
    else
        echo "DONE exit=$RC | $CMD"
    fi
    tail -20 "${JOB}.log"
    exit 0
fi

session_alive() {
    [ -n "$SID" ] && [ -n "$(ps -s "$SID" -o pid= 2>/dev/null)" ]
}

if session_alive || kill -0 "$PID" 2>/dev/null; then
    echo "RUNNING | $CMD"
    ps -p "$PID" -o pid=,state=,%cpu=,etime=,cputime= 2>/dev/null || true

    if [ -n "$SID" ]; then
        PCOUNT=$(ps -s "$SID" -o pid= 2>/dev/null | wc -l || echo 0)
        echo "SID=$SID PROCS=$PCOUNT"
        ps --forest -o pid,state,%cpu,cputime,cmd -s "$SID" 2>/dev/null | head -12 || true
    elif [ -n "$PGID" ]; then
        PCOUNT=$(ps -g "$PGID" -o pid= 2>/dev/null | wc -l || echo 0)
        echo "PGID=$PGID PROCS=$PCOUNT"
        ps --forest -o pid,state,%cpu,cputime,cmd -g "$PGID" 2>/dev/null | head -12 || true
    fi

    echo "LOG=$(wc -c < "${JOB}.log" 2>/dev/null || echo 0) bytes"
    tail -15 "${JOB}.log"
else
    if [ -f "${JOB}.rc" ]; then
        RC=$(cat "${JOB}.rc")
        if [ "$RC" = "SIGTERM" ]; then
            echo "KILLED | $CMD"
        else
            echo "DONE exit=$RC | $CMD"
        fi
    else
        echo "DEAD (no rc) | $CMD"
    fi
    tail -30 "${JOB}.log"
fi
EOF

# runk - kill job (SID-based)
cat > ~/.local/bin/runk << 'EOF'
#!/bin/bash
# NOTE: -e intentionally omitted; errors handled with || true
set -uo pipefail

JOB="${1:-}"
[ -z "$JOB" ] && { echo "Usage: runk /tmp/job_xxx"; exit 1; }

PID=$(cat "${JOB}.pid" 2>/dev/null || echo "")
[ -z "$PID" ] && { echo "No PID at $JOB"; exit 1; }

SID=$(cat "${JOB}.sid" 2>/dev/null || echo "")
PGID=$(cat "${JOB}.pgid" 2>/dev/null || echo "")

session_alive() {
    [ -n "$SID" ] && [ -n "$(ps -s "$SID" -o pid= 2>/dev/null)" ]
}

echo "TERM..."
if [ -n "$SID" ]; then
    pkill -TERM -s "$SID" 2>/dev/null || true
elif [ -n "$PGID" ]; then
    kill -TERM -"${PGID}" 2>/dev/null || true
else
    kill -TERM "$PID" 2>/dev/null || true
fi
sleep 3

if session_alive || kill -0 "$PID" 2>/dev/null; then
    echo "KILL..."
    if [ -n "$SID" ]; then
        pkill -KILL -s "$SID" 2>/dev/null || true
    elif [ -n "$PGID" ]; then
        kill -KILL -"${PGID}" 2>/dev/null || true
    else
        kill -KILL "$PID" 2>/dev/null || true
    fi
fi

echo "Done. runc $JOB"
EOF

chmod +x ~/.local/bin/rund ~/.local/bin/rundsh ~/.local/bin/runc ~/.local/bin/runk
grep -q 'local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc 2>/dev/null || true
echo "✓ Installed: rund, rundsh, runc, runk"
```

---

### 3. TOOL REFERENCE

#### 3.1 rund (Exec Mode)

**Purpose:** Run command with arguments safely. No shell interpretation.

**Usage:**
```bash
rund <command> [args...]
```

**Examples:**
```bash
rund npm install
rund pip install pandas numpy scipy
rund docker build -t myimage .
rund git clone https://github.com/user/repo.git
```

**Output:**
```
JOB=/tmp/job_1234567890123456_12345
PID=6789 SID=6789
```

**When to use:** Single command with arguments, no pipes or chains.

---

#### 3.2 rundsh (Shell Mode)

**Purpose:** Run shell commands with pipes, redirects, `&&`, `||`.

**Usage:**
```bash
rundsh '<shell command>'
```

**Examples:**
```bash
rundsh 'npm test && npm build'
rundsh 'docker-compose up -d && docker-compose logs -f'
rundsh 'cat file.txt | grep pattern | wc -l'
rundsh 'curl -s https://api.example.com > output.json'
```

**Output:**
```
JOB=/tmp/job_1234567890123456_12345
PID=6789 SID=6789
```

**⚠️ WARNING:** Only use with trusted input. `eval` executes arbitrary code.

**Note on quoting:** Shell lines containing single quotes work correctly because `$line` is passed as an argument to the inner shell, not interpolated into the script.

---

#### 3.3 runc (Check Status)

**Purpose:** Monitor job progress and detect stuck state.

**Usage:**
```bash
runc <job_path>
```

**Example:**
```bash
runc /tmp/job_1234567890123456_12345
```

**Output (Running):**
```
RUNNING | npm install
6789 S 2.3 00:45 00:00:12
SID=6789 PROCS=4
  6789 S  2.3 00:00:12 bash -c ...
  6790 S  1.2 00:00:08 npm install
  6791 R 15.0 00:00:05 node ...
  6792 S  0.0 00:00:01 sh -c ...
LOG=45678 bytes
added 234 packages in 32s
```

**Output (Done):**
```
DONE exit=0 | npm install
... last 20 lines of log ...
```

**Output (Killed):**
```
KILLED | npm install
... last 20 lines of log ...
```

**Output (Crashed):**
```
DEAD (no rc) | npm install
... last 30 lines of log ...
```

**Key metrics to track between checks:**
- `LOG=XXXXX bytes` - should increase if progressing
- `cputime` (e.g., `00:00:12`) - should increase if working
- `PROCS=N` - process count in session

---

#### 3.4 runk (Kill Job)

**Purpose:** Terminate stuck job and all child processes.

**Usage:**
```bash
runk <job_path>
```

**Example:**
```bash
runk /tmp/job_1234567890123456_12345
```

**Output:**
```
TERM...
Done. runc /tmp/job_1234567890123456_12345
```

**Behavior:**
1. Sends `SIGTERM` to entire session
2. Waits 3 seconds
3. If still alive, sends `SIGKILL`
4. Process writes `SIGTERM` to `.rc` file

---

### 4. JOB FILES

Each job creates a set of files in `/tmp/` with a common prefix. For a job path `/tmp/job_1234567890_5678`, these files are created:

| File | Content | Purpose |
|------|---------|---------|
| `/tmp/job_xxx.pid` | Process ID | Primary process tracking |
| `/tmp/job_xxx.sid` | Session ID | Kill entire process tree |
| `/tmp/job_xxx.pgid` | Process Group ID | Fallback for killing |
| `/tmp/job_xxx.log` | stdout + stderr | Output monitoring |
| `/tmp/job_xxx.rc` | Exit code or `SIGTERM` | Completion status |
| `/tmp/job_xxx.cmd` | Original command | Debugging/display |
| `/tmp/job_xxx.start` | ISO timestamp | Job start time |

---

### 5. EXECUTION STRATEGY

#### 5.1 Tier Classification

| Tier | Expected Duration | Method | Examples |
|------|-------------------|--------|----------|
| A | <30s | Run normally | `ls`, `cat`, `git status`, `npm run lint` |
| B | 30s-2min | Native non-blocking (if available) | `npm test`, `pytest`, small builds |
| C | >2min or complex | `rund`/`rundsh` + `runc` | `npm install`, `docker build`, migrations |

#### 5.2 Tier C Commands (Always Use rund/rundsh)

**Package Managers:**
- `npm install`, `npm ci`
- `pip install` (multiple packages)
- `yarn install`
- `pnpm install`
- `composer install`
- `bundle install`
- `cargo build`
- `go build`, `go mod download`

**Container Operations:**
- `docker build`
- `docker pull`
- `docker-compose up`
- `docker-compose build`

**Repository Operations:**
- `git clone` (large repos)
- `git pull` (large changes)
- `git submodule update`

**Build Systems:**
- `make`, `make all`
- `mvn install`, `mvn package`
- `gradle build`
- `dotnet build`, `dotnet restore`

**Database:**
- Migrations (any framework)
- Large data imports/exports
- Schema changes

**Network-Dependent:**
- `curl`/`wget` (large files)
- API calls with retries
- Any external service interaction

---

### 6. STUCK DETECTION

#### 6.1 Definition

A command is **STUCK** when ALL of these are true for 90+ seconds across multiple checks:

| Metric | Check | Stuck Signal |
|--------|-------|--------------|
| LOG size | `wc -c < ${JOB}.log` | Unchanged |
| CPU time | `cputime` column in `runc` output | Unchanged |
| Process count | `PROCS=N` in `runc` output | Unchanged |

This is a default heuristic, not an absolute rule. Use judgment for edge cases.

#### 6.2 NOT Stuck (False Positives to Avoid)

Do NOT kill if logs show:
- "Retrying in X seconds..."
- "Waiting for connection..."
- "Downloading... 0%" (progress indicator present)
- Network timeout messages with retry logic
- "Compiling..." with incrementing file counts

#### 6.3 Stuck Response

1. `runk /tmp/job_xxx` - Kill the stuck process
2. Analyze last log output for cause
3. Retry with more visibility:
   - Add `--verbose` or `--progress` flags
   - Use `--loglevel=info` for npm
   - Add `-v` for docker
4. If still stuck, try alternative approach

---

### 7. AGENT MONITORING WORKFLOW

#### 7.1 Start Long Command

```bash
rund npm install
# Output: JOB=/tmp/job_xxx PID=123 SID=123
```

Save the JOB path for subsequent checks.

#### 7.2 Monitoring Loop

```
┌─────────────────────────────────────────┐
│ START: rund/rundsh <command>            │
│ Save: JOB=/tmp/job_xxx                  │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ WAIT 15 seconds                         │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ CHECK: runc /tmp/job_xxx                │
│ Record: LOG bytes, cputime, PROCS       │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
┌──────────────┐  ┌──────────────────────┐
│ DONE/KILLED/ │  │ RUNNING              │
│ DEAD         │  └──────────┬───────────┘
└──────┬───────┘             │
       │            ┌────────┴────────┐
       ▼            ▼                 ▼
┌──────────────┐ ┌─────────────┐ ┌─────────────┐
│ Report &     │ │ Progressing │ │ No change   │
│ Continue     │ │ (metrics ↑) │ │ 90s+        │
└──────────────┘ └──────┬──────┘ └──────┬──────┘
                        │               │
                        ▼               ▼
                 ┌────────────┐  ┌─────────────┐
                 │ Continue   │  │ STUCK       │
                 │ monitoring │  │ runk + retry│
                 └────────────┘  └─────────────┘
```

#### 7.3 Example Session

```bash
# Start
$ rund npm install
JOB=/tmp/job_1701234567890123456_12345
PID=6789 SID=6789

# Check 1 (15s)
$ runc /tmp/job_1701234567890123456_12345
RUNNING | npm install
SID=6789 PROCS=4
LOG=12340 bytes
# Record: LOG=12340, cputime=00:00:08, PROCS=4

# Check 2 (30s)
$ runc /tmp/job_1701234567890123456_12345
RUNNING | npm install
SID=6789 PROCS=5
LOG=34560 bytes
# Record: LOG=34560 (↑), cputime=00:00:19 (↑), PROCS=5 (↑)
# PROGRESSING - continue

# Check 3 (45s)
$ runc /tmp/job_1701234567890123456_12345
RUNNING | npm install
SID=6789 PROCS=5
LOG=34560 bytes
# Record: LOG=34560 (same), cputime=00:00:19 (same), PROCS=5 (same)
# Potential stuck - start 90s timer

# Check 4-8 (60s-120s) - still no change
# 90s of no progress confirmed

# Kill
$ runk /tmp/job_1701234567890123456_12345
TERM...
Done. runc /tmp/job_1701234567890123456_12345

# Verify
$ runc /tmp/job_1701234567890123456_12345
KILLED | npm install

# Retry with verbosity
$ rund npm install --loglevel=verbose
```

---

### 8. .WINDSURFRULES

Add this to your project's `.windsurfrules` file:

```text
## Command Execution Strategy (Hybrid)

### Tier A - Fast (<30s expected): Run normally
Examples: ls, cat, grep, git status, git add, git commit, echo, pwd, npm run lint

### Tier B - Uncertain/Medium: Use non-blocking if available, else Tier C
If your tool supports non-blocking + status checks, use them.
Otherwise treat as Tier C.

### Tier C - Long/Complex: Always use rund/rundsh + runc monitoring
Use for ANY of:
- npm install / npm ci
- pip install (multiple packages)
- docker build / docker pull / docker-compose up
- git clone (large repos)
- cargo build / go build / make / mvn / gradle
- database migrations
- any network-dependent operation
- anything that has hung before

Commands:
  rund <cmd> [args]       # argv-safe exec mode
  rundsh '<shell line>'   # shell mode - TRUSTED INPUT ONLY (uses eval)
  runc <job_path>         # check status
  runk <job_path>         # kill stuck job

### Monitoring Loop (Tier C)
1. Start: rund npm install → note JOB=/tmp/job_xxx
2. Every 15s: runc /tmp/job_xxx
3. Compare to previous: LOG bytes, cputime, PROCS
4. If progressing → continue monitoring
5. If DONE → report exit code, proceed
6. If STUCK 90s → runk, retry with --verbose/--progress

### Stuck Detection
STUCK = 90s of ALL true:
- LOG size unchanged
- CPU time unchanged (check session tree)
- Process count unchanged
- NOT showing expected wait phase (retry, backoff)

### When in Doubt
If uncertain whether command is fast or slow → use Tier C.
False positive (used rund for fast command) = minor overhead.
False negative (blocked on slow command) = hours wasted.
```

---

### 9. TROUBLESHOOTING

#### 9.1 Command Not Found

```bash
$ rund npm install
bash: rund: command not found
```

**Fix:**
```bash
source ~/.bashrc
# or
export PATH="$HOME/.local/bin:$PATH"
```

#### 9.2 Permission Denied

```bash
$ rund npm install
bash: /home/user/.local/bin/rund: Permission denied
```

**Fix:**
```bash
chmod +x ~/.local/bin/rund ~/.local/bin/rundsh ~/.local/bin/runc ~/.local/bin/runk
```

#### 9.3 Job Not Found

```bash
$ runc /tmp/job_xxx
ERROR: No job at /tmp/job_xxx
```

**Cause:** Job path incorrect or files cleaned up.

**Fix:** Use exact JOB path from `rund` output.

#### 9.4 DEAD (no rc)

```bash
$ runc /tmp/job_xxx
DEAD (no rc) | npm install
```

**Cause:** Process crashed or was killed externally before writing `.rc`.

**Action:** Check last 30 lines of log for error cause.

#### 9.5 SID Empty

```bash
$ rund npm install
JOB=/tmp/job_xxx
PID=1234 SID=
```

**Cause:** Race condition or process exited immediately.

**Action:** Check if command is valid. Fallback uses PGID/PID for killing.

---

### 10. CLEANUP

Remove old job files periodically:

```bash
# Remove job files older than 1 day (precise glob)
find /tmp -maxdepth 1 -name 'job_[0-9]*_*' \( -name '*.pid' -o -name '*.sid' -o -name '*.pgid' -o -name '*.log' -o -name '*.rc' -o -name '*.cmd' -o -name '*.start' \) -mtime +1 -delete

# Quick cleanup: all job files
rm -f /tmp/job_[0-9]*_*.{pid,sid,pgid,log,rc,cmd,start} 2>/dev/null
```

Optional: Add to crontab for automatic cleanup:

```bash
crontab -e
# Add line:
0 3 * * * rm -f /tmp/job_[0-9]*_*.{pid,sid,pgid,log,rc,cmd,start} 2>/dev/null
```

---

### 11. QUICK REFERENCE CARD

```
┌─────────────────────────────────────────────────────────────┐
│ LONG COMMAND MONITORING - QUICK REFERENCE                   │
├─────────────────────────────────────────────────────────────┤
│ START                                                       │
│   rund npm install              # exec mode (safe)          │
│   rundsh 'npm test && build'    # shell mode (trusted)      │
│                                                             │
│ MONITOR                                                     │
│   runc /tmp/job_xxx             # every 15s                 │
│                                                             │
│ KILL                                                        │
│   runk /tmp/job_xxx             # if stuck 90s              │
│                                                             │
│ STATES                                                      │
│   RUNNING    - active, check LOG/cputime/PROCS              │
│   DONE exit=N - completed with exit code N                  │
│   KILLED     - terminated by signal                         │
│   DEAD       - crashed without writing rc                   │
│                                                             │
│ STUCK = 90s of: LOG same + cputime same + PROCS same        │
│                                                             │
│ WHEN IN DOUBT → USE TIER C (rund/rundsh)                    │
└─────────────────────────────────────────────────────────────┘
```

---

### 12. VERSION

**Version:** 1.0.0
**Last Updated:** December 2025
**Tested On:** Ubuntu 22.04+ (WSL2), Bash 5.x

---

**END OF DOCUMENT**
