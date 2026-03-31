# PYTHON PRODUCTION STANDARDS

Version: 1.0.1 (2025-11-06)

## 1. GOAL

Zero-error, production-grade scripts with resilience, recovery, and observability. This standard applies across web, data, scraping, media, and AI projects and must be paired with the Infrastructure Awareness Model (§13) and selection matrix (§14).

**Dependencies:** Depends on §13 and §14 for infra/tooling decisions.

Every script must handle:
- Network failures with automatic retry
- Disk space exhaustion
- Permission errors
- Rate limiting
- Concurrent access
- Data corruption
- System crashes

## 2. PRE-IMPLEMENTATION

### 2.1 Environment Discovery (MANDATORY FIRST STEP)

Before writing ANY code, document:
- Operating System: Windows version (10/11/Server), Linux distro, macOS version
- Python Version: Exact version (3.x.x) and installed packages
- File System: NTFS/ext4/APFS - affects atomic operations
- User Permissions: Admin/standard user - affects file operations
- Network Setup: Direct/proxy/VPN - affects connectivity checks
- Antivirus: Active AV software - may block operations
- Disk Space: Available space on target drives
- Concurrent Usage: Will multiple instances run? Need locking?
- Existing Infrastructure: Database schema, file structures, log format

Deliverable: Environment profile document

### 2.2 Scope Identification

Parse the target script and document:
- Task loop location: Where is the main work happening?
- I/O operations: Network calls, file reads/writes, database operations
- CPU work: Parsing, compression, encoding, computation
- Current error handling: What exists? What's missing?
- Execution mode decision:
  - io → asyncio (if library supports async)
  - mixed → threads (blocking I/O + CPU work)
  - cpu → processes (CPU-intensive work)
- Dependencies: External libraries, their stability, async support

Deliverable: Scope analysis document

### 2.3 Risk Assessment

For EACH new feature, document:
- What could break? List all failure modes
- Edge cases: Race conditions, partial failures, corruption scenarios
- Integration risks: Database schema conflicts, file format changes
- Performance impact: Latency, memory, disk I/O overhead
- Rollback plan: How to revert if it breaks?

Deliverable: Risk matrix per feature

## 3. CONFIGURATION & ARCHITECTURE

### 3.1 Standard Config Block (Top of File)

```python
"""
Script Name and Purpose
Version: X.Y.Z
Last Updated: YYYY-MM-DD
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# ========== FEATURE FLAGS (KILL SWITCHES) ==========
ENABLE_NETWORK_MONITOR = True      # Can disable if breaks
ENABLE_RECOVERY = True              # Can disable if breaks
ENABLE_ATOMIC_WRITES = True         # Can disable if breaks
ENABLE_RETRY_QUEUE = True           # Can disable if breaks
ENABLE_LOG_ROTATION = True          # Can disable if breaks
ENABLE_BACKUPS = True               # Can disable if breaks
DRY_RUN_MODE = False                # Test mode - no writes

# ========== PATHS ==========
BASE_DIR = Path(os.environ.get('APP_BASE_DIR', r"C:\App"))
DB_FILE = BASE_DIR / "db" / "app.db"
LOG_FILE = BASE_DIR / "logs" / "app.log"
BACKUP_DIR = BASE_DIR / "backups"
TEMP_DIR = BASE_DIR / "temp"

# ========== EXECUTION MODE ==========
EXECUTION_MODE = "threads"  # asyncio | threads | processes

# ========== WORKERS & CONCURRENCY ==========
MAX_WORKERS = 4                     # Thread/process pool size
MAX_BATCH_SIZE = 100                # Cap per batch to avoid overload
MAX_CONCURRENT_TASKS = 10           # Max tasks in flight

# ========== RETRY LOGIC ==========
MAX_RETRIES = 3                     # Per task
RETRY_DELAYS = [300, 900, 1800]    # 5min, 15min, 30min (seconds)
MAX_CONSECUTIVE_FAILURES = 5        # Stop if this many failures in a row

# ========== NETWORK ==========
NETWORK_CHECK_INTERVAL = 15         # Seconds between connectivity checks
NETWORK_CHECK_URL = "https://www.youtube.com/robots.txt"
NETWORK_TIMEOUT = 5                 # Seconds

# ========== LOGGING ==========
MAX_LOG_SIZE = 10 * 1024 * 1024    # 10 MB
LOG_ROTATION_COUNT = 3              # Keep 3 old logs

# ========== BACKUPS ==========
BACKUP_INTERVAL_HOURS = 24          # Daily backups
BACKUP_RETENTION_DAYS = 7           # Keep 7 days

# ========== SAFETY LIMITS ==========
MIN_DISK_SPACE_GB = 1.0            # Stop if less than this
MAX_TEMP_FILES = 100                # Clean if more than this
TASK_TIMEOUT_SECONDS = 300          # 5 minutes per task

# ========== ERROR CATEGORIES ==========
@dataclass
class ErrorCategory:
    NETWORK = "network"              # Retry with backoff
    CRITICAL = "critical"            # Stop immediately
    BLOCKED = "blocked"              # Wait longer, then retry
    RATE_LIMIT = "rate_limit"       # Auto-wait mechanism
    TRANSIENT = "transient"         # Retry immediately
    PERMANENT = "permanent"          # Skip, don't retry
    UNKNOWN = "unknown"              # Retry with caution
```

### 3.2 DB Strategy

**Default: PostgreSQL** (per CRITICAL_RULES.md §10)

One PostgreSQL 16 instance → one DB per project.

If SQLite used (dev/fallback only):

```python
import sqlite3
from contextlib import contextmanager

DB_VERSION = 3  # Increment when schema changes

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(str(DB_FILE), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """Initialize database with versioned migrations"""
    with get_db() as conn:
        # Version tracking table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        current_version = conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        ).fetchone()['v'] or 0

        # Apply migrations
        if current_version < 1:
            _migrate_to_v1(conn)
        if current_version < 2:
            _migrate_to_v2(conn)
        if current_version < 3:
            _migrate_to_v3(conn)

def _migrate_to_v1(conn):
    """Initial schema"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            error_category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            retry_after TIMESTAMP,
            result_path TEXT,
            file_size_bytes INTEGER,
            processing_time_ms INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_retry ON tasks(retry_after)")
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")

def _migrate_to_v2(conn):
    """Add tracking fields"""
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN last_error_at TIMESTAMP")
        conn.execute("ALTER TABLE tasks ADD COLUMN attempts INTEGER DEFAULT 0")
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise

def _migrate_to_v3(conn):
    """Add checksum for integrity"""
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN checksum TEXT")
        conn.execute("INSERT INTO schema_version (version) VALUES (3)")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
```

## 4. SAFE I/O OPERATIONS

### 4.1 Atomic File Operations

```python
import uuid
import hashlib
import shutil
from typing import Tuple, Optional

def atomic_write(content: str, target_path: Path,
                 validate_size: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Atomic file write with validation
    Returns: (success, error_message)
    """
    if not ENABLE_ATOMIC_WRITES:
        try:
            target_path.write_text(content, encoding='utf-8')
            return True, None
        except Exception as e:
            return False, str(e)

    temp_file = None
    try:
        temp_file = target_path.parent / f".tmp_{uuid.uuid4().hex[:8]}_{target_path.name}"

        if not check_disk_space(target_path.parent):
            return False, "Insufficient disk space"

        temp_file.write_text(content, encoding='utf-8')

        if validate_size and temp_file.stat().st_size < 50:
            temp_file.unlink()
            return False, "Output file too small (likely corrupted)"

        temp_file.replace(target_path)
        return True, None

    except Exception as e:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass
        return False, f"Atomic write failed: {e}"

def check_disk_space(path: Path, min_gb: float = MIN_DISK_SPACE_GB) -> bool:
    """Check if enough disk space available"""
    try:
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024 ** 3)
        if free_gb < min_gb:
            return False
        return True
    except Exception as e:
        return True  # Assume OK if check fails
```

### 4.2 Input Normalization

```python
def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitize filename for cross-platform compatibility"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')

    name = ''.join(char for char in name if ord(char) >= 32)

    if len(name) > max_length:
        stem = name[:max_length-10]
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
        name = f"{stem}_{hash_suffix}"

    return name.strip()
```

## 5. RESILIENCE MECHANISMS

### 5.1 Network Monitor

```python
import threading
import requests

network_online = threading.Event()
network_online.set()

def start_network_monitor():
    """Start background network monitoring"""
    if not ENABLE_NETWORK_MONITOR:
        return

    thread = threading.Thread(
        target=_network_monitor_loop,
        daemon=True,
        name="NetworkMonitor"
    )
    thread.start()

def _network_monitor_loop():
    """Background thread checking connectivity"""
    consecutive_failures = 0

    while True:
        try:
            response = requests.head(
                NETWORK_CHECK_URL,
                timeout=NETWORK_TIMEOUT,
                allow_redirects=True
            )

            if response.status_code < 500:
                if not network_online.is_set():
                    network_online.set()
                consecutive_failures = 0
            else:
                consecutive_failures += 1
        except Exception:
            consecutive_failures += 1
            if network_online.is_set() and consecutive_failures >= 3:
                network_online.clear()

        time.sleep(NETWORK_CHECK_INTERVAL)

def wait_for_network(timeout=None):
    """Wait for network availability"""
    if not ENABLE_NETWORK_MONITOR:
        return True
    return network_online.wait(timeout=timeout)
```

### 5.2 Recovery on Startup

```python
def recover_incomplete_tasks():
    """Recover interrupted tasks on startup"""
    if not ENABLE_RECOVERY:
        return

    with get_db() as conn:
        incomplete = conn.execute("""
            SELECT task_id, result_path, status
            FROM tasks
            WHERE status IN ('processing', 'uploading', 'downloading')
        """).fetchall()

        for row in incomplete:
            task_id = row['task_id']
            result_path = row['result_path']

            # Validate if result exists
            if result_path and Path(result_path).exists():
                # Mark completed if file valid
                if _validate_result_file(Path(result_path)):
                    conn.execute("""
                        UPDATE tasks
                        SET status='completed', completed_at=CURRENT_TIMESTAMP
                        WHERE task_id=?
                    """, (task_id,))
                    continue

            # Mark for retry
            conn.execute("""
                UPDATE tasks
                SET status='failed',
                    error_message='Recovered from incomplete state',
                    error_category='transient'
                WHERE task_id=?
            """, (task_id,))
```

### 5.3 Retry Queue

```python
def queue_retry(task_id, retry_count, error_category):
    """Schedule retry with backoff"""
    if error_category == 'rate_limit':
        delay_seconds = 3600
    elif error_category == 'blocked':
        delay_seconds = 1800
    elif error_category == 'network':
        delay_seconds = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS)-1)]
    else:
        delay_seconds = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS)-1)]

    retry_after = datetime.now() + timedelta(seconds=delay_seconds)

    with get_db() as conn:
        conn.execute("""
            UPDATE tasks
            SET retry_after=?, retry_count=?
            WHERE task_id=?
        """, (retry_after.isoformat(), retry_count, task_id))
```

## 6. ERROR HANDLING

### 6.1 Error Categorization

```python
def categorize_error(exception):
    """Categorize exception for handling"""
    error_str = str(exception).lower()

    if any(k in error_str for k in ['connection', 'timeout', 'network']):
        return 'network'
    if any(k in error_str for k in ['rate limit', '429', 'quota']):
        return 'rate_limit'
    if any(k in error_str for k in ['blocked', '403', 'forbidden']):
        return 'blocked'
    if any(k in error_str for k in ['permission', 'disk full', 'no space']):
        return 'critical'
    if any(k in error_str for k in ['not found', '404', 'deleted']):
        return 'permanent'
    if any(k in error_str for k in ['temporary', '503']):
        return 'transient'

    return 'unknown'
```

### 6.2 Worker Template

```python
def execute_task(task):
    """Execute task with full error handling"""
    task_id = task['task_id']

    try:
        if ENABLE_NETWORK_MONITOR and not wait_for_network(timeout=300):
            return False, "Network unavailable", 'network'

        update_task_status(task_id, 'processing')

        start_time = time.time()
        result = perform_task(task)
        processing_time = int((time.time() - start_time) * 1000)

        update_task_status(
            task_id,
            'completed',
            result_path=result.get('path'),
            processing_time_ms=processing_time
        )

        return True, None, None

    except Exception as e:
        error_category = categorize_error(e)
        error_message = str(e)

        retry_count = task.get('retry_count', 0) + 1

        if error_category == 'critical':
            update_task_status(task_id, 'failed', error_message, error_category)
            return False, error_message, error_category

        if error_category == 'permanent':
            update_task_status(task_id, 'skipped', error_message, error_category)
            return False, error_message, error_category

        if retry_count >= MAX_RETRIES:
            update_task_status(task_id, 'failed',
                             f"Max retries exceeded: {error_message}",
                             error_category)
            return False, error_message, error_category

        update_task_status(task_id, 'failed', error_message, error_category)
        queue_retry(task_id, retry_count, error_category)
        return False, error_message, error_category
```

## 7. LOGGING & MONITORING

### 7.1 Rotating Logs

```python
from logging.handlers import RotatingFileHandler

def init_logging():
    """Initialize logging with rotation"""
    logger = logging.getLogger('app')
    logger.setLevel(logging.INFO)

    # Console
    console = logging.StreamHandler()
    console_fmt = logging.Formatter('[%(asctime)s] %(message)s')
    console.setFormatter(console_fmt)
    logger.addHandler(console)

    # File with rotation
    if ENABLE_LOG_ROTATION:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_SIZE,
            backupCount=LOG_ROTATION_COUNT
        )
        file_fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

    return logger
```

### 7.2 Backup & Integrity

```python
def backup_database():
    """Create database backup"""
    if not ENABLE_BACKUPS:
        return

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUP_DIR / f"db_backup_{timestamp}.db"

    with get_db() as conn:
        backup_conn = sqlite3.connect(str(backup_file))
        conn.backup(backup_conn)
        backup_conn.close()

def verify_database_integrity():
    """Check database integrity"""
    with get_db() as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        return result[0] == 'ok'
```

## 8. ORCHESTRATION

### 8.1 Startup Sequence

```python
def startup_checks():
    """Run all startup checks"""
    init_logging()

    if not check_disk_space(BASE_DIR):
        return False

    init_database()

    if not verify_database_integrity():
        return False

    start_network_monitor()
    recover_incomplete_tasks()
    backup_database()

    return True
```

### 8.2 Main Loop

```python
def main():
    """Main entry point"""
    if not startup_checks():
        return 1

    try:
        tasks = get_pending_tasks()
        retries = get_ready_retries()

        if retries:
            tasks.extend(retries)

        if not tasks:
            return 0

        if len(tasks) > MAX_BATCH_SIZE:
            tasks = tasks[:MAX_BATCH_SIZE]

        if EXECUTION_MODE == 'threads':
            results = run_threaded_tasks(tasks)
        elif EXECUTION_MODE == 'asyncio':
            results = run_async_tasks(tasks)
        else:
            results = run_process_tasks(tasks)

        success = sum(1 for r in results if r[0])
        failed = len(results) - success

        return 0

    except KeyboardInterrupt:
        return 130
    except Exception as e:
        return 1
```

### 8.3 Threaded Execution

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_threaded_tasks(tasks):
    """Execute tasks using thread pool"""
    results = []
    consecutive_failures = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(execute_task, task): task for task in tasks}

        for future in as_completed(futures):
            task = futures[future]

            try:
                success, error, category = future.result(timeout=TASK_TIMEOUT_SECONDS)

                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1

                    if category == 'critical':
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                results.append((success, error, category))

            except TimeoutError:
                results.append((False, 'Timeout', 'unknown'))
                consecutive_failures += 1

    return results
```

## 9. VALIDATION & TESTING

### 9.1 Test Scaffold

```python
def run_validation_tests():
    """Run comprehensive validation"""
    tests = [
        test_network_failure,
        test_disk_full,
        test_atomic_write,
        test_recovery,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1

    return failed == 0
```

## 10. DEPLOYMENT

### 10.1 Pre-Deployment Checklist
- [ ] All feature flags tested
- [ ] Validation tests pass
- [ ] Backup created
- [ ] Rollback plan documented

### 10.2 Deployment Steps
1. Stop current instance
2. Backup database
3. Deploy new code
4. Run migrations
5. Run validation tests
6. Start with DRY_RUN_MODE=True
7. Monitor logs 30 minutes
8. Disable DRY_RUN_MODE

### 10.3 Post-Deployment
- Monitor error rates (<5%)
- Check disk space daily
- Verify backups running
- Review logs for patterns

## 11. DOCUMENTATION

### 11.1 Function Docstrings

```python
def function_name(param: type) -> return_type:
    """
    Brief description

    Args:
        param: Description

    Returns:
        Description

    Raises:
        ExceptionType: When

    Example:
        >>> function_name("test")
        result
    """
```

### 11.2 CHANGELOG Template

```markdown
## [2.0.0] - 2025-11-06

### Added
- Network monitor
- Atomic operations
- Recovery system

### Changed
- Database schema v3

### Fixed
- Race condition in writes

### Breaking Changes
- Migration required
```

## 12. USAGE NOTES

- Tie to CRITICAL_RULES Session Gate and Before-Writing-Code protocols
- "Minimum production bar" enforced before any code runs live
- If conflict with CRITICAL_RULES.md, CRITICAL_RULES.md wins
- Time estimates: AI minutes with confidence level only

---

**Total workflow: 5-7 hours for production-grade implementation**

Quality over speed. Never skip steps.

---

<!-- APPEND §13 START -->

# 13. INFRASTRUCTURE AWARENESS MODEL

## 13.1 Layers

* **Compute & Network:** Single Ubuntu VPS, Docker Compose, Nginx, SSH.
* **Code & CI/CD:** GitHub Actions → lint, test, build, deploy.
* **Runtime & APIs:** FastAPI, React+Vite, optional Expo.
* **Data & Storage:** Postgres 16 + pgvector, Redis; S3/MinIO; rclone mounts for GDrive/OneDrive.
* **Jobs & Pipelines:** APScheduler/RQ; cron replacement.
* **Scraping & Ingestion:** Playwright + httpx + selectolax; pdfplumber/PyMuPDF.
* **Media & Transcription:** FFmpeg; Soniox primary, WhisperX fallback.
* **AI & Search:** OpenAI/Anthropic APIs; embeddings in pgvector; small LoRA only with proven gain.
* **Observability:** Prometheus + Grafana; Loki + Promtail; Sentry; PostHog for product.
* **Security & Secrets:** Doppler or GH Secrets; UFW, fail2ban.
* **Publishing & Distribution:** Substack API, YouTube uploads, email/SMS.
* **Backups & DR:** Nightly DB dump to object store; weekly rclone to cold storage; monthly restore drill.

## 13.2 SLOs

* API p95 < 300 ms, 5xx < 1%, job success > 98%, RPO 24 h, RTO 2 h.

<!-- APPEND §13 END -->

<!-- APPEND §14 START -->

# 14. WHAT TO USE WHEN — EXTENDED MATRIX

| Need          | Balanced (default)                      | Aggressive (scale/edge)        | Upgrade trigger       |
| ------------- | --------------------------------------- | ------------------------------ | --------------------- |
| Frontend      | React + Vite + Tailwind, Radix, RHF+Zod | Next.js (ISR/SSR), shadcn      | SEO/SSR, multi-locale |
| Admin UI      | Mantine/React Admin                     | Retool/ToolJet                 | Ops needs no-code     |
| Mobile        | Expo (React Native)                     | Native modules or Flutter      | Heavy device APIs     |
| API           | FastAPI + Pydantic v2                   | Go Fiber / NestJS              | >1k RPS               |
| Auth          | OAuth2 + JWT                            | Auth0/Clerk, Ory/Keycloak      | SSO/SAML              |
| DB            | Postgres 16 + SQLAlchemy + Alembic      | Citus/Cockroach/replicas       | >100 GB, multi-region |
| Search        | pgvector                                | Opensearch/Elastic             | Complex aggregations  |
| Cache/Rate    | Redis                                   | Redis Cloud                    | Hot paths >10 ms      |
| Jobs          | APScheduler or RQ                       | Celery/Dramatiq + RabbitMQ     | Many concurrent tasks |
| Streams       | —                                       | Kafka/NATS                     | Event-driven scale    |
| Object store  | S3/MinIO                                | S3 + CloudFront                | >1 TB, global         |
| CDN           | Nginx static                            | Cloudflare                     | Global users          |
| Email         | Resend/SendGrid                         | Postmark                       | Deliverability issues |
| SMS/WA        | Twilio/Vonage                           | Gupshup/BSP                    | Heavy WhatsApp        |
| Analytics     | PostHog cloud                           | Mixpanel + dbt + WH            | Advanced funnels      |
| Errors        | Sentry                                  | Sentry + release health        | Release mapping       |
| Logs          | Loki + Promtail                         | Loki + Grafana Cloud           | Multi-host            |
| Monitoring    | Prometheus + Grafana                    | + Alertmanager, OTel collector | On-call               |
| Feature flags | Unleash OSS                             | LaunchDarkly                   | Governance            |
| A/B           | PostHog Experiments                     | GrowthBook                     | Stats rigor           |
| i18n          | i18next / gettext                       | Lokalise                       | 3+ locales            |
| Scraping      | Playwright + httpx + selectolax         | Scrapy + rotating proxies      | Anti-bot, scale       |
| PDF/OCR       | PyMuPDF/pdfplumber                      | GCV/Textract                   | OCR-heavy             |
| Inference     | OpenAI/Anthropic APIs                   | vLLM/Ollama/Triton             | API cost > $2k/mo     |
| Fine-tune     | OpenAI small FT; LoRA rented GPU        | Full SFT + RLHF                | Proven ≥10% eval lift |
| Evals         | promptfoo + RAGAS lite                  | RAGAS dashboards               | Multi-model           |
| Realtime      | SSE                                     | WebSockets + Redis pub/sub     | Live features         |
| Workflows     | Python scripts                          | Temporal                       | Complex retries       |
| BI            | Metabase on Postgres                    | DuckDB/BigQuery + dbt          | Team BI               |
| Pipelines     | APScheduler/cron                        | Prefect/Airflow                | DAGs, SLAs            |
| Docs          | MkDocs/Docusaurus                       | RTD + versioning               | Public/large          |
| Hosting       | Single VPS + Compose                    | Managed k8s + ArgoCD           | Many autoscaled       |
| Edge          | —                                       | Cloudflare Workers             | Edge logic            |
| Backups/DR    | Nightly dump + monthly restore          | WAL-G + PITR                   | Strict RPO/RTO        |
| Cost/FinOps   | Budget alerts + caps + kill-switch      | Cloud budgets + anomaly        | >$1k/mo               |
| Secrets       | Doppler/GH Secrets                      | Vault/SOPS+age                 | Audits, rotation      |
| Supply chain  | Trivy/Hadolint/Bandit/Semgrep/Syft      | Organization policy            | Vendor asks           |
| Access        | SSH keys, UFW, fail2ban                 | SSO/SCIM, bastion              | Team growth           |
| TR stack      | iyzico, e-Fatura APIs                   | Local gateways                 | Compliance            |

<!-- APPEND §14 END -->

<!-- APPEND §15 START -->

# 15. GOVERNANCE ADD-ONS

## 15.1 Ops Home

* **Dashboard tiles:** API p95, error %, job success %, queue depth, DB size, scrape ban rate, daily cost.
* **Alerts:** p95 > 300 ms for 5 m; error % > 1% for 5 m; job success % < 98% for 30 m.

## 15.2 Secrets & Access

* All secrets in Doppler or GitHub Encrypted Secrets.
* Rotation every 90 days.
* SSH keys only. UFW allow 22/80/443; fail2ban enabled.

## 15.3 Backups & DR

* Nightly `pg_dump` to object store, retention 30 days hot / 180 days cold.
* Weekly `rclone copy` to offline HDD.
* Monthly restore drill logged.

## 15.4 Data governance (KVKK-aware)

* P0 secrets, P1 personal, P2 internal, P3 public.
* Mask P0/P1 in logs. EU-region storage when possible. Vendor DPAs.

## 15.5 AI Spend Gate

* No fine-tune unless offline eval shows ≥10% gain and payback < 30 days.

<!-- APPEND §15 END -->

<!-- APPEND §16 START -->

# 16. RUNTIMES & PACKAGE MANAGEMENT

* **Node:** 20 LTS + TypeScript + pnpm + nvm.
* **Python:** 3.11 + **uv** (or Poetry) + pyenv.
* **Task runners:** Make baseline; `just` optional.
* **Pre-commit hooks:** ruff, black, isort, mypy, bandit, hadolint, semgrep, eslint, prettier.

<!-- APPEND §16 END -->

<!-- APPEND §17 START -->

# 17. PER-PROJECT SELECTION GRID

Use this grid at project kickoff. Copy and fill.

```
Project: _________  Date: _________  Owner: _________

Web: [React+Vite] / [Next.js]       Reason: _______
API: [FastAPI] / [Go/Nest]          Reason: _______
DB: [Postgres+pgvector] / [Citus]   Reason: _______
Jobs: [APScheduler/RQ] / [Celery]   Reason: _______
Search: [pgvector] / [Elastic]      Reason: _______
Scraping: [Playwright] / [Scrapy]   Reason: _______
Transcription: [Soniox] / [WhisperX] Reason: _______
Observability: [Prom+Graf+Loki+Sentry]  Alerts: p95 / error% / jobs%
Secrets: [Doppler/GH] Rotation: 90d
Backups: nightly dump; restore drill date: _______
AI: [API] / [LoRA] Gate: ≥10% lift?  □Yes □No
Compliance: PII? □Yes □No   KVKK notes: _______
```

<!-- APPEND §17 END -->

<!-- APPEND §18 START -->

# 18. 24-HOUR MICRO-WIN CHECKLIST

* Pre-commit installed and passing.
* Prometheus + Grafana + Loki + Sentry up; two alerts configured.
* `pg_dump` nightly + one successful restore to scratch DB.
* Playwright scraper stub runs via APScheduler.
* MkDocs/Docusaurus page added: "What to use when."

<!-- APPEND §18 END -->
