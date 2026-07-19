## extract_ports_from_compose

**Signature:**

```python
def extract_ports_from_compose(project_dir: Path) -> list[int]:
```

**Description:** Extracts host port mappings from a `compose.yaml` file by parsing `HOST_PORT` environment variable references and explicit `host:container` port declarations.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_dir` | `Path` | Yes | — | Path to the project directory containing `compose.yaml` |

**Returns:**

- `list[int]` — Sorted list of unique host port integers found in the compose file. Returns empty list if file doesn't exist or no ports found.

**Raises:**

- No exceptions — silently returns empty list on errors or missing file

**Example:**

```python
from pathlib import Path
from scripts.seed_real_ports import extract_ports_from_compose

project = Path("/opt/myapp")
ports = extract_ports_from_compose(project)
print(ports)  # [8080, 9000]
```

---

## extract_port_from_env

**Signature:**

```python
def extract_port_from_env(project_dir: Path) -> int | None:
```

**Description:** Extracts the primary service port from `.env.example` or `.env` files, filtering out common database/SMTP ports that are not service ports.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_dir` | `Path` | Yes | — | Path to the project directory |

**Returns:**

- `int` — The port number if found and not in the excluded list
- `None` — If no port variable found or file missing

**Raises:**

- No exceptions — returns `None` on errors

**Example:**

```python
from pathlib import Path
from scripts.seed_real_ports import extract_port_from_env

project = Path("/opt/myapp")
port = extract_port_from_env(project)
if port:
    print(f"Service runs on port {port}")
```

---

## detect_project_type

**Signature:**

```python
def detect_project_type(project_dir: Path) -> str:
```

**Description:** Detects whether a project is a Node.js or Python application based on the presence of `package.json`.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_dir` | `Path` | Yes | — | Path to the project directory |

**Returns:**

- `"node"` — If `package.json` exists in the project directory
- `"python"` — Default if no `package.json` found

**Example:**

```python
from pathlib import Path
from scripts.seed_real_ports import detect_project_type

project = Path("/opt/myapp")
project_type = detect_project_type(project)
if project_type == "node":
    port_range = (3000, 3099)
else:
    port_range = (8000, 8099)
```

---

## determine_ports

**Signature:**

```python
def determine_ports(name: str, project_dir: Path, used_ports: set[int]) -> list[int]:
```

**Description:** Determines the correct host port(s) for a project by checking known production ports, extracting from configuration files, or auto-allocating from the appropriate range.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | `str` | Yes | — | Project name (used for known ports lookup) |
| `project_dir` | `Path` | Yes | — | Path to the project directory |
| `used_ports` | `set[int]` | Yes | — | Set of already allocated ports to avoid conflicts |

**Returns:**

- `list[int]` — List of one or more port integers assigned to this project

**Raises:**

- No exceptions — falls back to overflow port if range exhausted

**Example:**

```python
from pathlib import Path
from scripts.seed_real_ports import determine_ports

used = {8000, 8001}
project_name = "myapp"
project_dir = Path("/opt/myapp")
ports = determine_ports(project_name, project_dir, used)
print(ports)  # [8002]
```

---

## main (seed_real_ports)

**Signature:**

```python
def main() -> int:
```

**Description:** Entry point for the port seeding utility. Scans all projects under `/opt`, extracts or allocates accurate host ports, and updates each project's `project.yaml` file. Performs dry-run by default; use `--apply` to write changes.

**Returns:**

- `0` — Success (all projects processed, report printed)

**Raises:**

- No exceptions — all errors are caught and logged as warnings

**Example:**

```bash
# Dry-run to see proposed changes
python scripts/seed_real_ports.py

# Apply changes to all project.yaml files
python scripts/seed_real_ports.py --apply
```

---

## extract_metadata_from_readme

**Signature:**

```python
def extract_metadata_from_readme(project_dir: Path) -> dict:
```

**Description:** Extracts project metadata from `README.md` frontmatter-style badges and headings, including description, URL, status, and technology stack.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_dir` | `Path` | Yes | — | Path to the project directory containing `README.md` |

**Returns:**

- `dict` — Dictionary with keys: `description`, `url`, `status`, `stack` (all values are strings, empty if not found)

**Raises:**

- No exceptions — returns empty dict on errors or missing file

**Example:**

```python
from pathlib import Path
from scripts.sync_projects import extract_metadata_from_readme

project = Path("/opt/myapp")
metadata = extract_metadata_from_readme(project)
print(metadata.get("status"))  # "Production"
```

---

## extract_metadata_from_compose

**Signature:**

```python
def extract_metadata_from_compose(project_dir: Path) -> dict:
```

**Description:** Extracts service metadata from `compose.yaml`, primarily the container port from the first service's port mapping, and infers project type from `Dockerfile` base image.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_dir` | `Path` | Yes | — | Path to the project directory containing `compose.yaml` |

**Returns:**

- `dict` — Dictionary with keys: `container_port` (int) and `type` (str: `"python-api"`, `"node-app"`, or `"unknown"`)

**Raises:**

- No exceptions — defaults to empty dict on errors

**Example:**

```python
from pathlib import Path
from scripts.sync_projects import extract_metadata_from_compose

project = Path("/opt/myapp")
info = extract_metadata_from_compose(project)
print(info.get("container_port"))  # 8000
```

---

## extract_metadata_from_env

**Signature:**

```python
def extract_metadata_from_env(project_dir: Path) -> dict:
```

**Description:** Extracts runtime variable keys from `.env.example` to build a comma-separated list of configuration variables required by the project.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_dir` | `Path` | Yes | — | Path to the project directory |

**Returns:**

- `dict` — Dictionary with key `variables` containing a sorted, comma-separated string of variable names (e.g., `"DB_HOST,PORT,API_KEY"`)

**Raises:**

- No exceptions — returns empty dict if no `.env.example` found

**Example:**

```python
from pathlib import Path
from scripts.sync_projects import extract_metadata_from_env

project = Path("/opt/myapp")
env_info = extract_metadata_from_env(project)
print(env_info.get("variables"))  # "DB_HOST,DB_PORT,SECRET_KEY"
```

---

## sync_projects

**Signature:**

```python
def sync_projects(dry_run: bool = False) -> dict:
```

**Description:** Scans all project directories under `/opt`, aggregates metadata from `README.md`, `compose.yaml`, `.env.example`, and `project.yaml`, and updates `docs/BUSINESS_MODEL.md` with an auto-generated project catalog table.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `dry_run` | `bool` | No | `False` | If `True`, prints changes without writing to `BUSINESS_MODEL.md` |

**Returns:**

- `dict` — Summary with keys: `projects_found`, `projects_updated`, `status` (`"UPDATED"`, `"NO_CHANGES"`, or `"ERROR"`)

**Raises:**

- No exceptions — errors are caught and reported in return dict

**Example:**

```python
from scripts.sync_projects import sync_projects

result = sync_projects(dry_run=True)
print(result["status"])  # "NO_CHANGES"
```

---

## main (sync_projects)

**Signature:**

```python
def main() -> int:
```

**Description:** Command-line entry point for `sync_projects.py`. Parses `--dry-run` flag and invokes the sync operation, printing a summary to stdout.

**Returns:**

- `0` — Success
- `1` — Error (exception raised or sync failed)

**Raises:**

- No exceptions — catches all and returns error code

**Example:**

```bash
# Preview changes without writing
python scripts/sync_projects.py --dry-run

# Apply changes to BUSINESS_MODEL.md
python scripts/sync_projects.py
```

---

## scan_health

**Signature:**

```python
def scan_health(root: Path = Path("/opt")) -> list[dict[str, object]]:
```

**Description:** Scans project directories and reports scaffold health status by checking for essential files. Each project is categorized as `healthy`, `warnings`, or `missing` based on how many essential scaffold files are absent.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `root` | `Path` | No | `Path("/opt")` | Base directory to scan for project folders |

**Returns:**

- `list[dict[str, object]]` — List of dicts with keys: `project` (str), `path` (str), `missing` (list[str]), `status` (str: `"healthy"`, `"warnings"`, or `"missing"`)

**Example:**

```python
from scripts.health_summary import scan_health
from pathlib import Path

results = scan_health(root=Path("/opt"))
for r in results:
    print(f"{r['project']}: {r['status']}")
```

```bash
# Table output (default)
python scripts/health_summary.py

# JSON output for automation
python scripts/health_summary.py --json

# Scan a different root directory
python scripts/health_summary.py --base /some/path
```

**Workflow Doc:** `docs/workflows/HEALTH_SUMMARY_WORKFLOW.md`
