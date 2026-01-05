> **Phase Navigation:** [← Phase 4](Phase4.md) | **Phase 5** | [Phase 6 →](Phase6.md) | [All Phases](roadmap.md)

## Phase 5: Staging + Multi-Environment — Complete Narrative

**Status: ❌ Not Started** (Requires Phase 2)

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | Environment field in specs | ❌ Pending |
| 2 | Staging subdomain convention | ❌ Pending |
| 3 | Clone command | ❌ Pending |
| 4 | Database cloning | ❌ Pending |
| 5 | Sync command | ❌ Pending |
| 6 | Promote command | ❌ Pending |
| 7 | Environment isolation | ❌ Pending |

**Completion: 0/7 tasks (0%)**

---

### What We're Building in Phase 5

By the end of Phase 5, you will have:

1. **Environment field** in specs (production, staging, development)
2. **Staging subdomain convention** (staging.domain.com)
3. **Clone command** to duplicate production to staging
4. **Database cloning** with optional data anonymization
5. **Sync command** to push changes between environments
6. **Promote command** to deploy staging to production
7. **Environment isolation** — separate databases, separate containers
8. **Safe testing workflow** — test changes before affecting live sites

This transforms Fabrik from "deploy sites" to "professional development workflow with safe testing."

---

### Why Staging Environments?

**Without Staging:**
- Changes go directly to production
- Bugs affect live visitors immediately
- No way to test theme/plugin updates safely
- Client reviews happen on live site
- Rollback requires restore from backup

**With Staging:**
- Test changes in isolated environment
- Client can review before going live
- Test updates without risk
- Catch bugs before they affect visitors
- Simple promote when ready

---

### Prerequisites

Before starting Phase 5, confirm:

```
[ ] Phase 1-4 complete
[ ] At least one production WordPress site deployed
[ ] Cloudflare DNS working (for staging subdomains)
[ ] Sufficient VPS resources for duplicate environments
```

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  FABRIK CLI                                                     │
│                                                                 │
│  fabrik staging:create acme-site                                │
│  fabrik staging:sync acme-site --direction=prod-to-staging      │
│  fabrik staging:promote acme-site                               │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  ENVIRONMENT MANAGER                                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Production Environment                                 │    │
│  │                                                         │    │
│  │  Site: acme-site                                        │    │
│  │  Domain: acme.com                                       │    │
│  │  Database: acme_production                              │    │
│  │  Container: acme-site-prod                              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Staging Environment                                    │    │
│  │                                                         │    │
│  │  Site: acme-site-staging                                │    │
│  │  Domain: staging.acme.com                               │    │
│  │  Database: acme_staging                                 │    │
│  │  Container: acme-site-staging                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Sync Engine                                            │    │
│  │                                                         │    │
│  │  • Database dump/restore                                │    │
│  │  • File sync (uploads, themes, plugins)                 │    │
│  │  • URL replacement                                      │    │
│  │  • Optional data anonymization                          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  COOLIFY                                                        │
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │  acme-site-prod  │    │  acme-site-stg   │                   │
│  │  WordPress       │    │  WordPress       │                   │
│  │  Port: internal  │    │  Port: internal  │                   │
│  └────────┬─────────┘    └────────┬─────────┘                   │
│           │                       │                             │
│  ┌────────▼───────────────────────▼─────────┐                   │
│  │  Traefik                                 │                   │
│  │  acme.com → acme-site-prod               │                   │
│  │  staging.acme.com → acme-site-stg        │                   │
│  └──────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  POSTGRES                                                       │
│                                                                 │
│  ├── acme_production (live data)                                │
│  └── acme_staging (cloned data)                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Update Spec Schema with Environment Field

**Why:** Every spec needs to know which environment it belongs to. This affects naming, domains, and resource allocation.

**Code:**

```python
# Update compiler/spec_loader.py

from enum import Enum

class Environment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"

# Add to Spec class:
class Spec(BaseModel):
    id: str
    kind: Kind
    template: str
    environment: Environment = Environment.PRODUCTION  # NEW

    # ... rest of existing fields ...

    # Computed properties
    @property
    def full_id(self) -> str:
        """Get full ID including environment suffix."""
        if self.environment == Environment.PRODUCTION:
            return self.id
        return f"{self.id}-{self.environment.value[:3]}"  # e.g., acme-site-stg

    @property
    def database_name(self) -> str:
        """Get environment-specific database name."""
        base = self.id.replace('-', '_')
        if self.environment == Environment.PRODUCTION:
            return f"{base}_production"
        elif self.environment == Environment.STAGING:
            return f"{base}_staging"
        else:
            return f"{base}_development"
```

**Updated spec format:**

```yaml
# specs/acme-site/spec.yaml

id: acme-site
kind: service
template: wp-site
environment: production    # NEW: production | staging | development

domain: acme.com

# ... rest of spec ...
```

**Time:** 30 minutes

---

### Step 2: Environment Configuration Manager

**Why:** Centralize environment-specific settings (domain patterns, resource limits, database naming).

**Code:**

```python
# compiler/environments.py

from dataclasses import dataclass
from typing import Optional
from enum import Enum

class Environment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"

@dataclass
class EnvironmentConfig:
    """Configuration for a specific environment."""

    name: Environment
    domain_prefix: Optional[str]  # None for production, "staging" for staging
    resource_multiplier: float    # 1.0 for production, 0.5 for staging
    backup_enabled: bool
    indexing_enabled: bool        # Search engine indexing
    debug_enabled: bool
    ssl_mode: str                 # full, flexible

    @classmethod
    def production(cls) -> 'EnvironmentConfig':
        return cls(
            name=Environment.PRODUCTION,
            domain_prefix=None,
            resource_multiplier=1.0,
            backup_enabled=True,
            indexing_enabled=True,
            debug_enabled=False,
            ssl_mode='full'
        )

    @classmethod
    def staging(cls) -> 'EnvironmentConfig':
        return cls(
            name=Environment.STAGING,
            domain_prefix='staging',
            resource_multiplier=0.5,
            backup_enabled=False,
            indexing_enabled=False,  # Prevent search engine indexing
            debug_enabled=True,
            ssl_mode='full'
        )

    @classmethod
    def development(cls) -> 'EnvironmentConfig':
        return cls(
            name=Environment.DEVELOPMENT,
            domain_prefix='dev',
            resource_multiplier=0.25,
            backup_enabled=False,
            indexing_enabled=False,
            debug_enabled=True,
            ssl_mode='flexible'
        )

    @classmethod
    def get(cls, env: Environment) -> 'EnvironmentConfig':
        """Get config for environment."""
        configs = {
            Environment.PRODUCTION: cls.production,
            Environment.STAGING: cls.staging,
            Environment.DEVELOPMENT: cls.development,
        }
        return configs[env]()

class EnvironmentManager:
    """Manage environment-specific operations."""

    def __init__(self):
        pass

    def get_domain(self, base_domain: str, environment: Environment) -> str:
        """
        Get domain for environment.

        Production: acme.com
        Staging: staging.acme.com
        Development: dev.acme.com
        """
        config = EnvironmentConfig.get(environment)

        if config.domain_prefix:
            return f"{config.domain_prefix}.{base_domain}"
        return base_domain

    def get_site_id(self, base_id: str, environment: Environment) -> str:
        """
        Get site ID for environment.

        Production: acme-site
        Staging: acme-site-staging
        Development: acme-site-dev
        """
        if environment == Environment.PRODUCTION:
            return base_id

        suffix = {
            Environment.STAGING: 'staging',
            Environment.DEVELOPMENT: 'dev'
        }

        return f"{base_id}-{suffix[environment]}"

    def get_database_name(self, base_id: str, environment: Environment) -> str:
        """
        Get database name for environment.

        Production: acme_site_production
        Staging: acme_site_staging
        """
        base = base_id.replace('-', '_')

        suffix = {
            Environment.PRODUCTION: 'production',
            Environment.STAGING: 'staging',
            Environment.DEVELOPMENT: 'dev'
        }

        return f"{base}_{suffix[environment]}"

    def get_resources(self, base_memory: str, base_cpu: str, environment: Environment) -> dict:
        """Get scaled resources for environment."""
        config = EnvironmentConfig.get(environment)

        # Parse memory (e.g., "512M" -> 512)
        memory_value = int(base_memory.replace('M', '').replace('G', '000'))
        scaled_memory = int(memory_value * config.resource_multiplier)

        # Parse CPU
        cpu_value = float(base_cpu)
        scaled_cpu = cpu_value * config.resource_multiplier

        return {
            'memory': f"{max(scaled_memory, 128)}M",  # Minimum 128M
            'cpu': str(max(scaled_cpu, 0.1))          # Minimum 0.1
        }

    def get_wp_config_extras(self, environment: Environment) -> dict:
        """Get WordPress config constants for environment."""
        config = EnvironmentConfig.get(environment)

        extras = {}

        if config.debug_enabled:
            extras['WP_DEBUG'] = 'true'
            extras['WP_DEBUG_LOG'] = 'true'
            extras['WP_DEBUG_DISPLAY'] = 'false'
        else:
            extras['WP_DEBUG'] = 'false'

        if not config.indexing_enabled:
            extras['DISALLOW_INDEXING'] = 'true'

        return extras
```

**Time:** 1 hour

---

### Step 3: Database Clone Manager

**Why:** Staging needs a copy of production data. We need to safely clone PostgreSQL/MySQL databases.

**Code:**

```python
# compiler/database.py

import os
import subprocess
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

@dataclass
class CloneResult:
    success: bool
    source_db: str
    target_db: str
    rows_copied: Optional[int] = None
    duration_seconds: float = 0
    error: Optional[str] = None

class DatabaseManager:
    """Manage database operations for environments."""

    def __init__(self):
        self.pg_host = os.environ.get('POSTGRES_HOST', 'localhost')
        self.pg_port = int(os.environ.get('POSTGRES_PORT', '5432'))
        self.pg_user = os.environ.get('POSTGRES_USER', 'postgres')
        self.pg_password = os.environ.get('POSTGRES_PASSWORD', '')

        # For remote execution
        self.vps_ip = os.environ.get('VPS_IP')
        self.ssh_user = os.environ.get('SSH_USER', 'deploy')

    def _run_psql(self, command: str, database: str = 'postgres') -> tuple[bool, str]:
        """Execute psql command."""

        # Build connection string
        env = os.environ.copy()
        env['PGPASSWORD'] = self.pg_password

        cmd = [
            'psql',
            '-h', self.pg_host,
            '-p', str(self.pg_port),
            '-U', self.pg_user,
            '-d', database,
            '-c', command
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        return result.returncode == 0, result.stdout + result.stderr

    def _run_remote_psql(self, command: str, database: str = 'postgres') -> tuple[bool, str]:
        """Execute psql command on remote VPS."""

        # Run via SSH
        ssh_cmd = f"""ssh {self.ssh_user}@{self.vps_ip} 'PGPASSWORD="{self.pg_password}" psql -h {self.pg_host} -p {self.pg_port} -U {self.pg_user} -d {database} -c "{command}"'"""

        result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)

        return result.returncode == 0, result.stdout + result.stderr

    def database_exists(self, database: str) -> bool:
        """Check if database exists."""
        success, output = self._run_remote_psql(
            f"SELECT 1 FROM pg_database WHERE datname = '{database}';"
        )
        return success and '1' in output

    def create_database(self, database: str, owner: str = None) -> bool:
        """Create a new database."""
        owner = owner or self.pg_user

        success, _ = self._run_remote_psql(
            f"CREATE DATABASE {database} OWNER {owner};"
        )
        return success

    def drop_database(self, database: str) -> bool:
        """Drop a database."""
        # Terminate active connections first
        self._run_remote_psql(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{database}' AND pid <> pg_backend_pid();
        """)

        success, _ = self._run_remote_psql(f"DROP DATABASE IF EXISTS {database};")
        return success

    def clone_database(
        self,
        source_db: str,
        target_db: str,
        drop_existing: bool = True
    ) -> CloneResult:
        """
        Clone a database using pg_dump and pg_restore.

        This is the safest method for production cloning.
        """
        start_time = datetime.now()

        # Check source exists
        if not self.database_exists(source_db):
            return CloneResult(
                success=False,
                source_db=source_db,
                target_db=target_db,
                error=f"Source database does not exist: {source_db}"
            )

        # Drop target if exists and allowed
        if self.database_exists(target_db):
            if drop_existing:
                if not self.drop_database(target_db):
                    return CloneResult(
                        success=False,
                        source_db=source_db,
                        target_db=target_db,
                        error=f"Failed to drop existing target database: {target_db}"
                    )
            else:
                return CloneResult(
                    success=False,
                    source_db=source_db,
                    target_db=target_db,
                    error=f"Target database already exists: {target_db}"
                )

        # Create target database
        if not self.create_database(target_db):
            return CloneResult(
                success=False,
                source_db=source_db,
                target_db=target_db,
                error=f"Failed to create target database: {target_db}"
            )

        # Clone using pg_dump | pg_restore via SSH
        clone_cmd = f"""ssh {self.ssh_user}@{self.vps_ip} 'PGPASSWORD="{self.pg_password}" pg_dump -h {self.pg_host} -p {self.pg_port} -U {self.pg_user} -Fc {source_db} | PGPASSWORD="{self.pg_password}" pg_restore -h {self.pg_host} -p {self.pg_port} -U {self.pg_user} -d {target_db} --no-owner --no-acl'"""

        result = subprocess.run(clone_cmd, shell=True, capture_output=True, text=True)

        duration = (datetime.now() - start_time).total_seconds()

        if result.returncode != 0:
            # pg_restore returns non-zero for warnings too, check if db has tables
            success, output = self._run_remote_psql(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';",
                target_db
            )

            if not success or '0' in output:
                return CloneResult(
                    success=False,
                    source_db=source_db,
                    target_db=target_db,
                    duration_seconds=duration,
                    error=f"Clone failed: {result.stderr}"
                )

        return CloneResult(
            success=True,
            source_db=source_db,
            target_db=target_db,
            duration_seconds=duration
        )

    def clone_database_quick(self, source_db: str, target_db: str) -> CloneResult:
        """
        Quick clone using CREATE DATABASE ... TEMPLATE.

        Faster but requires no active connections to source.
        Best for development environments.
        """
        start_time = datetime.now()

        # Terminate connections to source
        self._run_remote_psql(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{source_db}' AND pid <> pg_backend_pid();
        """)

        # Drop target if exists
        self.drop_database(target_db)

        # Create from template
        success, output = self._run_remote_psql(
            f"CREATE DATABASE {target_db} TEMPLATE {source_db};"
        )

        duration = (datetime.now() - start_time).total_seconds()

        if not success:
            return CloneResult(
                success=False,
                source_db=source_db,
                target_db=target_db,
                duration_seconds=duration,
                error=output
            )

        return CloneResult(
            success=True,
            source_db=source_db,
            target_db=target_db,
            duration_seconds=duration
        )

class WordPressDatabaseManager(DatabaseManager):
    """WordPress-specific database operations."""

    def replace_urls(
        self,
        database: str,
        old_url: str,
        new_url: str
    ) -> bool:
        """
        Replace URLs in WordPress database.

        This handles serialized data properly using search-replace SQL.
        For complex serialized data, use WP-CLI instead.
        """

        # Tables that commonly contain URLs
        tables = [
            ('wp_options', 'option_value'),
            ('wp_posts', 'post_content'),
            ('wp_posts', 'guid'),
            ('wp_postmeta', 'meta_value'),
        ]

        for table, column in tables:
            # Simple replace (won't handle serialized data perfectly)
            self._run_remote_psql(
                f"UPDATE {table} SET {column} = REPLACE({column}, '{old_url}', '{new_url}') WHERE {column} LIKE '%{old_url}%';",
                database
            )

        return True

    def anonymize_data(self, database: str) -> bool:
        """
        Anonymize sensitive data in WordPress database.

        Use this when cloning production to staging to protect user data.
        """

        # Anonymize user emails
        self._run_remote_psql(
            "UPDATE wp_users SET user_email = CONCAT('user', ID, '@staging.local');",
            database
        )

        # Anonymize user display names
        self._run_remote_psql(
            "UPDATE wp_users SET display_name = CONCAT('User ', ID);",
            database
        )

        # Clear user passwords (set to unusable hash)
        self._run_remote_psql(
            "UPDATE wp_users SET user_pass = '$P$BxxxxxxxxxxxxxxxxxxxxxxxxxxxxX' WHERE ID > 1;",
            database
        )

        # Anonymize comments
        self._run_remote_psql(
            "UPDATE wp_comments SET comment_author_email = CONCAT('commenter', comment_ID, '@staging.local');",
            database
        )

        self._run_remote_psql(
            "UPDATE wp_comments SET comment_author_IP = '127.0.0.1';",
            database
        )

        # Clear sensitive options
        sensitive_options = [
            'admin_email',
            'mailserver_login',
            'mailserver_pass',
        ]

        for option in sensitive_options:
            self._run_remote_psql(
                f"UPDATE wp_options SET option_value = 'redacted@staging.local' WHERE option_name = '{option}';",
                database
            )

        return True
```

**Time:** 2 hours

---

### Step 4: File Sync Manager

**Why:** Staging needs production files (uploads, themes, plugins). We need to sync WordPress content directories.

**Code:**

```python
# compiler/file_sync.py

import os
import subprocess
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class SyncResult:
    success: bool
    files_copied: int = 0
    bytes_transferred: int = 0
    duration_seconds: float = 0
    error: Optional[str] = None

class FileSync:
    """Sync files between environments using rsync."""

    def __init__(self):
        self.vps_ip = os.environ.get('VPS_IP')
        self.ssh_user = os.environ.get('SSH_USER', 'deploy')

    def _get_container_path(self, site_id: str, subpath: str) -> str:
        """Get path inside container."""
        # Coolify typically mounts volumes at /var/www/html for WordPress
        return f"/var/www/html/{subpath}"

    def _get_volume_path(self, site_id: str) -> str:
        """
        Get host volume path for a site.

        Coolify stores volumes in /data/coolify/services/<uuid>/
        We need to find the right volume.
        """
        # This depends on Coolify's volume naming
        # For now, we'll use docker cp as it's more reliable
        return f"/data/coolify/applications/{site_id}"

    def sync_uploads(
        self,
        source_site: str,
        target_site: str,
        delete_extra: bool = False
    ) -> SyncResult:
        """
        Sync wp-content/uploads between sites.

        Uses docker cp to avoid volume path complexity.
        """
        start_time = datetime.now()

        # Create temp directory
        temp_dir = f"/tmp/fabrik-sync-{source_site}-{int(datetime.now().timestamp())}"

        try:
            # Find source container
            find_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker ps --filter name={source_site} --format {{{{.Names}}}} | head -1'"
            result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
            source_container = result.stdout.strip()

            if not source_container:
                return SyncResult(
                    success=False,
                    error=f"Source container not found: {source_site}"
                )

            # Find target container
            find_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker ps --filter name={target_site} --format {{{{.Names}}}} | head -1'"
            result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
            target_container = result.stdout.strip()

            if not target_container:
                return SyncResult(
                    success=False,
                    error=f"Target container not found: {target_site}"
                )

            # Copy from source to temp
            copy_out_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'mkdir -p {temp_dir} && docker cp {source_container}:/var/www/html/wp-content/uploads {temp_dir}/'"
            result = subprocess.run(copy_out_cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                return SyncResult(
                    success=False,
                    error=f"Failed to copy from source: {result.stderr}"
                )

            # Copy from temp to target
            copy_in_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker cp {temp_dir}/uploads/. {target_container}:/var/www/html/wp-content/uploads/'"
            result = subprocess.run(copy_in_cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                return SyncResult(
                    success=False,
                    error=f"Failed to copy to target: {result.stderr}"
                )

            # Fix permissions
            fix_perms_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker exec {target_container} chown -R www-data:www-data /var/www/html/wp-content/uploads'"
            subprocess.run(fix_perms_cmd, shell=True)

            # Cleanup
            cleanup_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'rm -rf {temp_dir}'"
            subprocess.run(cleanup_cmd, shell=True)

            duration = (datetime.now() - start_time).total_seconds()

            return SyncResult(
                success=True,
                duration_seconds=duration
            )

        except Exception as e:
            return SyncResult(
                success=False,
                error=str(e)
            )

    def sync_themes(
        self,
        source_site: str,
        target_site: str,
        themes: list[str] = None
    ) -> SyncResult:
        """
        Sync themes between sites.

        If themes is None, sync all non-default themes.
        """
        start_time = datetime.now()

        try:
            # Find containers
            source_container = self._find_container(source_site)
            target_container = self._find_container(target_site)

            if not source_container or not target_container:
                return SyncResult(
                    success=False,
                    error="Container not found"
                )

            temp_dir = f"/tmp/fabrik-themes-{int(datetime.now().timestamp())}"

            # If specific themes, sync only those
            if themes:
                for theme in themes:
                    copy_cmd = f"""ssh {self.ssh_user}@{self.vps_ip} '
                        mkdir -p {temp_dir} &&
                        docker cp {source_container}:/var/www/html/wp-content/themes/{theme} {temp_dir}/ &&
                        docker cp {temp_dir}/{theme} {target_container}:/var/www/html/wp-content/themes/ &&
                        docker exec {target_container} chown -R www-data:www-data /var/www/html/wp-content/themes/{theme}
                    '"""
                    subprocess.run(copy_cmd, shell=True)
            else:
                # Sync entire themes directory
                copy_cmd = f"""ssh {self.ssh_user}@{self.vps_ip} '
                    mkdir -p {temp_dir} &&
                    docker cp {source_container}:/var/www/html/wp-content/themes {temp_dir}/ &&
                    docker cp {temp_dir}/themes/. {target_container}:/var/www/html/wp-content/themes/ &&
                    docker exec {target_container} chown -R www-data:www-data /var/www/html/wp-content/themes
                '"""
                subprocess.run(copy_cmd, shell=True)

            # Cleanup
            subprocess.run(f"ssh {self.ssh_user}@{self.vps_ip} 'rm -rf {temp_dir}'", shell=True)

            duration = (datetime.now() - start_time).total_seconds()

            return SyncResult(
                success=True,
                duration_seconds=duration
            )

        except Exception as e:
            return SyncResult(
                success=False,
                error=str(e)
            )

    def sync_plugins(
        self,
        source_site: str,
        target_site: str,
        plugins: list[str] = None
    ) -> SyncResult:
        """Sync plugins between sites."""
        start_time = datetime.now()

        try:
            source_container = self._find_container(source_site)
            target_container = self._find_container(target_site)

            if not source_container or not target_container:
                return SyncResult(
                    success=False,
                    error="Container not found"
                )

            temp_dir = f"/tmp/fabrik-plugins-{int(datetime.now().timestamp())}"

            if plugins:
                for plugin in plugins:
                    copy_cmd = f"""ssh {self.ssh_user}@{self.vps_ip} '
                        mkdir -p {temp_dir} &&
                        docker cp {source_container}:/var/www/html/wp-content/plugins/{plugin} {temp_dir}/ &&
                        docker cp {temp_dir}/{plugin} {target_container}:/var/www/html/wp-content/plugins/ &&
                        docker exec {target_container} chown -R www-data:www-data /var/www/html/wp-content/plugins/{plugin}
                    '"""
                    subprocess.run(copy_cmd, shell=True)
            else:
                copy_cmd = f"""ssh {self.ssh_user}@{self.vps_ip} '
                    mkdir -p {temp_dir} &&
                    docker cp {source_container}:/var/www/html/wp-content/plugins {temp_dir}/ &&
                    docker cp {temp_dir}/plugins/. {target_container}:/var/www/html/wp-content/plugins/ &&
                    docker exec {target_container} chown -R www-data:www-data /var/www/html/wp-content/plugins
                '"""
                subprocess.run(copy_cmd, shell=True)

            subprocess.run(f"ssh {self.ssh_user}@{self.vps_ip} 'rm -rf {temp_dir}'", shell=True)

            duration = (datetime.now() - start_time).total_seconds()

            return SyncResult(
                success=True,
                duration_seconds=duration
            )

        except Exception as e:
            return SyncResult(
                success=False,
                error=str(e)
            )

    def _find_container(self, site_id: str) -> Optional[str]:
        """Find container name for a site."""
        find_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker ps --filter name={site_id} --format {{{{.Names}}}} | head -1'"
        result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip() or None
```

**Time:** 2 hours

---

### Step 5: Staging Manager

**Why:** Orchestrate all staging operations — create staging, sync, promote.

**Code:**

```python
# compiler/staging.py

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import yaml

from compiler.spec_loader import load_spec, save_spec, Spec, Environment
from compiler.environments import EnvironmentManager, EnvironmentConfig
from compiler.database import WordPressDatabaseManager, CloneResult
from compiler.file_sync import FileSync, SyncResult
from compiler.wordpress.wp_cli import WPCLIExecutor

@dataclass
class StagingCreateResult:
    success: bool
    staging_id: str
    staging_domain: str
    staging_url: str
    database_clone: Optional[CloneResult] = None
    file_sync: Optional[SyncResult] = None
    error: Optional[str] = None
    duration_seconds: float = 0

@dataclass
class StagingSyncResult:
    success: bool
    direction: str  # prod-to-staging, staging-to-prod
    database_synced: bool = False
    files_synced: bool = False
    urls_replaced: bool = False
    error: Optional[str] = None

@dataclass
class PromoteResult:
    success: bool
    source: str
    target: str
    database_promoted: bool = False
    files_promoted: bool = False
    error: Optional[str] = None

class StagingManager:
    """Manage staging environments for sites."""

    def __init__(self):
        self.env_mgr = EnvironmentManager()
        self.db_mgr = WordPressDatabaseManager()
        self.file_sync = FileSync()

    def create_staging(
        self,
        production_id: str,
        clone_database: bool = True,
        clone_files: bool = True,
        anonymize_data: bool = False
    ) -> StagingCreateResult:
        """
        Create a staging environment for a production site.

        1. Load production spec
        2. Create staging spec (modified copy)
        3. Deploy staging site
        4. Clone database
        5. Sync files
        6. Replace URLs
        7. Apply staging-specific settings
        """
        start_time = datetime.now()

        # Load production spec
        prod_spec_path = f"specs/{production_id}/spec.yaml"

        try:
            prod_spec = load_spec(prod_spec_path)
        except FileNotFoundError:
            return StagingCreateResult(
                success=False,
                staging_id="",
                staging_domain="",
                staging_url="",
                error=f"Production spec not found: {prod_spec_path}"
            )

        if prod_spec.environment != Environment.PRODUCTION:
            return StagingCreateResult(
                success=False,
                staging_id="",
                staging_domain="",
                staging_url="",
                error=f"Source must be production environment, got: {prod_spec.environment}"
            )

        # Create staging spec
        staging_id = self.env_mgr.get_site_id(production_id, Environment.STAGING)
        staging_domain = self.env_mgr.get_domain(prod_spec.domain, Environment.STAGING)

        staging_spec = self._create_staging_spec(prod_spec, staging_id, staging_domain)

        # Save staging spec
        staging_spec_dir = Path(f"specs/{staging_id}")
        staging_spec_dir.mkdir(parents=True, exist_ok=True)
        save_spec(staging_spec, str(staging_spec_dir / "spec.yaml"))

        # Deploy staging site
        from cli.apply import apply_spec

        try:
            apply_spec(staging_id)
        except Exception as e:
            return StagingCreateResult(
                success=False,
                staging_id=staging_id,
                staging_domain=staging_domain,
                staging_url=f"https://{staging_domain}",
                error=f"Failed to deploy staging: {e}"
            )

        db_result = None
        file_result = None

        # Clone database
        if clone_database:
            prod_db = self.env_mgr.get_database_name(production_id, Environment.PRODUCTION)
            staging_db = self.env_mgr.get_database_name(production_id, Environment.STAGING)

            db_result = self.db_mgr.clone_database(prod_db, staging_db)

            if not db_result.success:
                return StagingCreateResult(
                    success=False,
                    staging_id=staging_id,
                    staging_domain=staging_domain,
                    staging_url=f"https://{staging_domain}",
                    database_clone=db_result,
                    error=f"Database clone failed: {db_result.error}"
                )

            # Replace URLs in database
            self.db_mgr.replace_urls(
                staging_db,
                f"https://{prod_spec.domain}",
                f"https://{staging_domain}"
            )

            # Anonymize if requested
            if anonymize_data:
                self.db_mgr.anonymize_data(staging_db)

        # Sync files
        if clone_files:
            file_result = self.file_sync.sync_uploads(production_id, staging_id)

            if not file_result.success:
                # Non-fatal, staging can work without uploads
                print(f"Warning: File sync failed: {file_result.error}")

        # Apply staging-specific WordPress settings
        self._apply_staging_wp_settings(staging_id, staging_domain)

        duration = (datetime.now() - start_time).total_seconds()

        return StagingCreateResult(
            success=True,
            staging_id=staging_id,
            staging_domain=staging_domain,
            staging_url=f"https://{staging_domain}",
            database_clone=db_result,
            file_sync=file_result,
            duration_seconds=duration
        )

    def _create_staging_spec(self, prod_spec: Spec, staging_id: str, staging_domain: str) -> Spec:
        """Create staging spec from production spec."""

        staging_config = EnvironmentConfig.staging()

        # Copy and modify spec
        staging_data = prod_spec.dict()

        staging_data['id'] = staging_id
        staging_data['environment'] = Environment.STAGING
        staging_data['domain'] = staging_domain

        # Scale down resources
        if 'resources' in staging_data:
            prod_resources = staging_data['resources']
            staging_data['resources'] = self.env_mgr.get_resources(
                prod_resources.get('memory', '512M'),
                prod_resources.get('cpu', '0.5'),
                Environment.STAGING
            )

        # Disable backups
        if 'backup' in staging_data:
            staging_data['backup']['enabled'] = False

        # Update DNS records for staging domain
        if 'dns' in staging_data and staging_data['dns']:
            for record in staging_data['dns'].get('records', []):
                if record.get('name') == '@':
                    pass  # Keep as-is, it will resolve for staging domain
                elif record.get('name') == 'www':
                    # Remove www for staging (usually not needed)
                    pass

        # Add staging-specific env vars
        staging_data['env'] = staging_data.get('env', {})
        staging_data['env']['WP_ENVIRONMENT_TYPE'] = 'staging'
        staging_data['env']['DISALLOW_INDEXING'] = 'true'

        return Spec(**staging_data)

    def _apply_staging_wp_settings(self, staging_id: str, staging_domain: str):
        """Apply staging-specific WordPress settings."""

        try:
            wp = WPCLIExecutor(staging_id)

            # Update site URL
            wp.execute(f"option update home 'https://{staging_domain}'")
            wp.execute(f"option update siteurl 'https://{staging_domain}'")

            # Disable search engine indexing
            wp.execute("option update blog_public 0")

            # Add staging indicator
            wp.execute("option update blogdescription 'STAGING - " + staging_domain + "'")

            # Enable debug mode
            wp.execute("config set WP_DEBUG true --raw")
            wp.execute("config set WP_DEBUG_LOG true --raw")
            wp.execute("config set WP_DEBUG_DISPLAY false --raw")

        except Exception as e:
            print(f"Warning: Could not apply all staging settings: {e}")

    def sync(
        self,
        site_id: str,
        direction: str = 'prod-to-staging',  # or 'staging-to-prod'
        sync_database: bool = True,
        sync_files: bool = True,
        anonymize: bool = False
    ) -> StagingSyncResult:
        """
        Sync data between environments.

        Directions:
        - prod-to-staging: Refresh staging with production data
        - staging-to-prod: Push staging changes to production (careful!)
        """

        if direction == 'prod-to-staging':
            source_env = Environment.PRODUCTION
            target_env = Environment.STAGING
            source_id = site_id
            target_id = self.env_mgr.get_site_id(site_id, Environment.STAGING)
        elif direction == 'staging-to-prod':
            source_env = Environment.STAGING
            target_env = Environment.PRODUCTION
            source_id = self.env_mgr.get_site_id(site_id, Environment.STAGING)
            target_id = site_id
        else:
            return StagingSyncResult(
                success=False,
                direction=direction,
                error=f"Invalid direction: {direction}"
            )

        result = StagingSyncResult(
            success=True,
            direction=direction
        )

        # Sync database
        if sync_database:
            source_db = self.env_mgr.get_database_name(site_id, source_env)
            target_db = self.env_mgr.get_database_name(site_id, target_env)

            db_result = self.db_mgr.clone_database(source_db, target_db)

            if db_result.success:
                result.database_synced = True

                # Get domains for URL replacement
                prod_spec = load_spec(f"specs/{site_id}/spec.yaml")
                source_domain = self.env_mgr.get_domain(prod_spec.domain, source_env)
                target_domain = self.env_mgr.get_domain(prod_spec.domain, target_env)

                self.db_mgr.replace_urls(
                    target_db,
                    f"https://{source_domain}",
                    f"https://{target_domain}"
                )
                result.urls_replaced = True

                if anonymize and direction == 'prod-to-staging':
                    self.db_mgr.anonymize_data(target_db)
            else:
                result.success = False
                result.error = f"Database sync failed: {db_result.error}"
                return result

        # Sync files
        if sync_files:
            file_result = self.file_sync.sync_uploads(source_id, target_id)

            if file_result.success:
                result.files_synced = True
            else:
                # Non-fatal
                print(f"Warning: File sync failed: {file_result.error}")

        return result

    def promote(
        self,
        site_id: str,
        promote_database: bool = True,
        promote_files: bool = True,
        backup_production: bool = True
    ) -> PromoteResult:
        """
        Promote staging to production.

        This is a more careful version of sync(staging-to-prod).
        Includes backup of production before overwriting.
        """

        staging_id = self.env_mgr.get_site_id(site_id, Environment.STAGING)

        # Backup production first
        if backup_production:
            prod_db = self.env_mgr.get_database_name(site_id, Environment.PRODUCTION)
            backup_db = f"{prod_db}_backup_{int(datetime.now().timestamp())}"

            backup_result = self.db_mgr.clone_database(prod_db, backup_db, drop_existing=False)

            if not backup_result.success:
                return PromoteResult(
                    success=False,
                    source=staging_id,
                    target=site_id,
                    error=f"Production backup failed: {backup_result.error}"
                )

            print(f"Production backed up to: {backup_db}")

        # Sync staging to production
        sync_result = self.sync(
            site_id,
            direction='staging-to-prod',
            sync_database=promote_database,
            sync_files=promote_files,
            anonymize=False
        )

        if not sync_result.success:
            return PromoteResult(
                success=False,
                source=staging_id,
                target=site_id,
                error=sync_result.error
            )

        return PromoteResult(
            success=True,
            source=staging_id,
            target=site_id,
            database_promoted=sync_result.database_synced,
            files_promoted=sync_result.files_synced
        )

    def destroy_staging(self, site_id: str) -> bool:
        """Destroy staging environment for a site."""

        staging_id = self.env_mgr.get_site_id(site_id, Environment.STAGING)

        # Destroy via Fabrik
        from cli.destroy import destroy_spec

        try:
            destroy_spec(staging_id)
        except Exception as e:
            print(f"Warning: Could not destroy staging deployment: {e}")

        # Drop staging database
        staging_db = self.env_mgr.get_database_name(site_id, Environment.STAGING)
        self.db_mgr.drop_database(staging_db)

        # Remove staging spec
        staging_spec_dir = Path(f"specs/{staging_id}")
        if staging_spec_dir.exists():
            import shutil
            shutil.rmtree(staging_spec_dir)

        return True

    def list_staging(self, site_id: str = None) -> list[dict]:
        """List staging environments."""

        staging_sites = []
        specs_dir = Path("specs")

        for spec_path in specs_dir.glob("*/spec.yaml"):
            try:
                spec = load_spec(str(spec_path))

                if spec.environment == Environment.STAGING:
                    # Extract base site id
                    base_id = spec.id.replace('-staging', '')

                    if site_id is None or base_id == site_id:
                        staging_sites.append({
                            'staging_id': spec.id,
                            'base_id': base_id,
                            'domain': spec.domain,
                            'environment': spec.environment.value
                        })
            except:
                continue

        return staging_sites
```

**Time:** 3 hours

---

### Step 6: CLI Commands for Staging

**Why:** Expose staging operations through CLI.

**Code:**

```python
# cli/staging.py

import click
import os
from pathlib import Path

def load_env():
    """Load environment."""
    env_file = Path("secrets/platform.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v

@click.group()
def staging():
    """Staging environment management."""
    load_env()

# ─────────────────────────────────────────────────────────────
# Create Staging
# ─────────────────────────────────────────────────────────────

@staging.command('create')
@click.argument('site_id')
@click.option('--clone-db/--no-clone-db', default=True, help='Clone production database')
@click.option('--clone-files/--no-clone-files', default=True, help='Clone uploads and media')
@click.option('--anonymize/--no-anonymize', default=False, help='Anonymize user data')
def create(site_id, clone_db, clone_files, anonymize):
    """Create staging environment for a production site."""

    from compiler.staging import StagingManager

    mgr = StagingManager()

    click.echo(f"\nCreating staging environment for: {site_id}")
    click.echo("-" * 50)

    result = mgr.create_staging(
        site_id,
        clone_database=clone_db,
        clone_files=clone_files,
        anonymize_data=anonymize
    )

    if result.success:
        click.echo(f"\n✓ Staging environment created!")
        click.echo(f"\n  Staging ID:     {result.staging_id}")
        click.echo(f"  Staging Domain: {result.staging_domain}")
        click.echo(f"  Staging URL:    {result.staging_url}")

        if result.database_clone:
            click.echo(f"\n  Database:")
            click.echo(f"    Cloned in {result.database_clone.duration_seconds:.1f}s")

        if result.file_sync:
            click.echo(f"\n  Files:")
            click.echo(f"    Synced in {result.file_sync.duration_seconds:.1f}s")

        click.echo(f"\n  Total time: {result.duration_seconds:.1f}s")

        click.echo(f"""
Next steps:
  1. Visit {result.staging_url} to verify
  2. Make changes in staging
  3. Run 'fabrik staging:promote {site_id}' to deploy to production
""")
    else:
        click.echo(f"\n✗ Failed to create staging environment")
        click.echo(f"  Error: {result.error}")
        raise click.Abort()

# ─────────────────────────────────────────────────────────────
# List Staging
# ─────────────────────────────────────────────────────────────

@staging.command('list')
@click.option('--site', 'site_id', help='Filter by base site ID')
def list_staging(site_id):
    """List staging environments."""

    from compiler.staging import StagingManager

    mgr = StagingManager()

    staging_sites = mgr.list_staging(site_id)

    if not staging_sites:
        click.echo("No staging environments found.")
        return

    click.echo(f"\nStaging environments:")
    click.echo("-" * 60)

    for site in staging_sites:
        click.echo(f"  {site['staging_id']:25} → {site['domain']}")

# ─────────────────────────────────────────────────────────────
# Sync
# ─────────────────────────────────────────────────────────────

@staging.command('sync')
@click.argument('site_id')
@click.option('--direction', type=click.Choice(['prod-to-staging', 'staging-to-prod']),
              default='prod-to-staging', help='Sync direction')
@click.option('--database/--no-database', default=True, help='Sync database')
@click.option('--files/--no-files', default=True, help='Sync files')
@click.option('--anonymize/--no-anonymize', default=False, help='Anonymize user data (prod-to-staging only)')
@click.confirmation_option(prompt='This will overwrite data. Continue?')
def sync(site_id, direction, database, files, anonymize):
    """Sync data between production and staging."""

    from compiler.staging import StagingManager

    mgr = StagingManager()

    click.echo(f"\nSyncing {site_id}: {direction}")
    click.echo("-" * 50)

    if direction == 'staging-to-prod':
        click.echo("⚠ WARNING: This will overwrite production data!")
        if not click.confirm("Are you absolutely sure?"):
            raise click.Abort()

    result = mgr.sync(
        site_id,
        direction=direction,
        sync_database=database,
        sync_files=files,
        anonymize=anonymize
    )

    if result.success:
        click.echo(f"\n✓ Sync complete!")
        click.echo(f"  Database synced: {result.database_synced}")
        click.echo(f"  Files synced:    {result.files_synced}")
        click.echo(f"  URLs replaced:   {result.urls_replaced}")
    else:
        click.echo(f"\n✗ Sync failed: {result.error}")
        raise click.Abort()

# ─────────────────────────────────────────────────────────────
# Promote
# ─────────────────────────────────────────────────────────────

@staging.command('promote')
@click.argument('site_id')
@click.option('--database/--no-database', default=True, help='Promote database')
@click.option('--files/--no-files', default=True, help='Promote files')
@click.option('--backup/--no-backup', default=True, help='Backup production before promoting')
def promote(site_id, database, files, backup):
    """Promote staging to production."""

    from compiler.staging import StagingManager

    mgr = StagingManager()

    staging_id = mgr.env_mgr.get_site_id(site_id, mgr.env_mgr.Environment.STAGING)

    click.echo(f"\nPromoting staging to production")
    click.echo(f"  Source: {staging_id}")
    click.echo(f"  Target: {site_id}")
    click.echo("-" * 50)

    click.echo("\n⚠ WARNING: This will overwrite production with staging data!")
    click.echo("  Make sure you have tested staging thoroughly.")

    if not click.confirm("\nProceed with promotion?"):
        raise click.Abort()

    result = mgr.promote(
        site_id,
        promote_database=database,
        promote_files=files,
        backup_production=backup
    )

    if result.success:
        click.echo(f"\n✓ Promotion complete!")
        click.echo(f"  Database promoted: {result.database_promoted}")
        click.echo(f"  Files promoted:    {result.files_promoted}")

        if backup:
            click.echo(f"\n  Production backup available for rollback")

        click.echo(f"\n  Visit https://{site_id.replace('-', '.')}.com to verify")
    else:
        click.echo(f"\n✗ Promotion failed: {result.error}")
        raise click.Abort()

# ─────────────────────────────────────────────────────────────
# Destroy
# ─────────────────────────────────────────────────────────────

@staging.command('destroy')
@click.argument('site_id')
@click.confirmation_option(prompt='This will permanently delete the staging environment. Continue?')
def destroy(site_id):
    """Destroy staging environment."""

    from compiler.staging import StagingManager

    mgr = StagingManager()

    staging_id = mgr.env_mgr.get_site_id(site_id, mgr.env_mgr.Environment.STAGING)

    click.echo(f"\nDestroying staging environment: {staging_id}")

    if mgr.destroy_staging(site_id):
        click.echo(f"\n✓ Staging environment destroyed")
    else:
        click.echo(f"\n✗ Failed to destroy staging environment")
        raise click.Abort()

# ─────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────

@staging.command('status')
@click.argument('site_id')
def status(site_id):
    """Show staging environment status."""

    from compiler.staging import StagingManager
    from compiler.spec_loader import load_spec
    from compiler.environments import Environment

    mgr = StagingManager()

    staging_id = mgr.env_mgr.get_site_id(site_id, Environment.STAGING)

    # Check if staging exists
    try:
        staging_spec = load_spec(f"specs/{staging_id}/spec.yaml")
    except FileNotFoundError:
        click.echo(f"\nNo staging environment found for: {site_id}")
        click.echo(f"Create one with: fabrik staging:create {site_id}")
        return

    # Check production
    try:
        prod_spec = load_spec(f"specs/{site_id}/spec.yaml")
    except FileNotFoundError:
        click.echo(f"\n✗ Production site not found: {site_id}")
        raise click.Abort()

    click.echo(f"\nEnvironment Status: {site_id}")
    click.echo("=" * 60)

    click.echo(f"\n  Production:")
    click.echo(f"    ID:       {site_id}")
    click.echo(f"    Domain:   {prod_spec.domain}")
    click.echo(f"    Database: {mgr.env_mgr.get_database_name(site_id, Environment.PRODUCTION)}")

    click.echo(f"\n  Staging:")
    click.echo(f"    ID:       {staging_id}")
    click.echo(f"    Domain:   {staging_spec.domain}")
    click.echo(f"    Database: {mgr.env_mgr.get_database_name(site_id, Environment.STAGING)}")

    click.echo(f"""
Commands:
  Refresh staging:  fabrik staging:sync {site_id} --direction=prod-to-staging
  Promote to prod:  fabrik staging:promote {site_id}
  Destroy staging:  fabrik staging:destroy {site_id}
""")

if __name__ == '__main__':
    staging()
```

**Update main CLI:**

```python
# cli/main.py - add staging commands

from cli.staging import staging

cli.add_command(staging)
```

**Time:** 2 hours

---

### Step 7: URL Replacement with WP-CLI

**Why:** Database-level URL replacement doesn't handle serialized data properly. WP-CLI's search-replace command does.

**Code:**

```python
# compiler/wordpress/url_replace.py

from compiler.wordpress.wp_cli import WPCLIExecutor

class URLReplacer:
    """Replace URLs in WordPress using WP-CLI (handles serialized data)."""

    def __init__(self, site_id: str):
        self.site_id = site_id
        self.wp = WPCLIExecutor(site_id)

    def replace_url(self, old_url: str, new_url: str, dry_run: bool = False) -> dict:
        """
        Replace all instances of old_url with new_url.

        Uses WP-CLI search-replace which properly handles serialized data.
        """

        cmd = f"search-replace '{old_url}' '{new_url}' --all-tables --precise"

        if dry_run:
            cmd += " --dry-run"

        result = self.wp.execute(cmd)

        # Parse output to count replacements
        replacements = 0
        if result.success:
            # WP-CLI outputs: "Made X replacements"
            for line in result.output.split('\n'):
                if 'replacement' in line.lower():
                    try:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.isdigit():
                                replacements = int(part)
                                break
                    except:
                        pass

        return {
            'success': result.success,
            'replacements': replacements,
            'dry_run': dry_run,
            'output': result.output,
            'error': result.error
        }

    def update_home_url(self, new_url: str) -> bool:
        """Update WordPress home and site URL options."""

        # Remove trailing slash
        new_url = new_url.rstrip('/')

        result1 = self.wp.execute(f"option update home '{new_url}'")
        result2 = self.wp.execute(f"option update siteurl '{new_url}'")

        return result1.success and result2.success

    def flush_cache(self) -> bool:
        """Flush all WordPress caches after URL change."""

        # Flush rewrite rules
        self.wp.execute("rewrite flush")

        # Flush object cache if available
        self.wp.execute("cache flush")

        # Clear transients
        self.wp.execute("transient delete --all")

        return True

    def full_url_migration(
        self,
        old_url: str,
        new_url: str,
        dry_run: bool = False
    ) -> dict:
        """
        Perform complete URL migration.

        1. Search-replace in database
        2. Update home/siteurl options
        3. Flush caches
        """

        results = {
            'search_replace': None,
            'options_updated': False,
            'cache_flushed': False
        }

        # Step 1: Search-replace
        results['search_replace'] = self.replace_url(old_url, new_url, dry_run)

        if dry_run:
            return results

        if not results['search_replace']['success']:
            return results

        # Step 2: Update options (in case search-replace missed them)
        results['options_updated'] = self.update_home_url(new_url)

        # Step 3: Flush caches
        results['cache_flushed'] = self.flush_cache()

        return results
```

**Integrate into staging sync:**

```python
# In compiler/staging.py, update sync method:

def sync(self, ...):
    # After database clone, use WP-CLI for URL replacement
    if sync_database and result.database_synced:
        from compiler.wordpress.url_replace import URLReplacer

        replacer = URLReplacer(target_id)

        prod_spec = load_spec(f"specs/{site_id}/spec.yaml")
        source_url = f"https://{self.env_mgr.get_domain(prod_spec.domain, source_env)}"
        target_url = f"https://{self.env_mgr.get_domain(prod_spec.domain, target_env)}"

        url_result = replacer.full_url_migration(source_url, target_url)

        if url_result['search_replace']['success']:
            result.urls_replaced = True
```

**Time:** 1 hour

---

### Step 8: Staging Access Protection

**Why:** Staging environments should not be publicly accessible. Add basic auth or IP restriction.

**Code:**

```python
# compiler/staging_security.py

import os
import secrets
import string
from pathlib import Path

from compiler.wordpress.wp_cli import WPCLIExecutor

def generate_password(length: int = 16) -> str:
    """Generate a random password."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

class StagingSecurity:
    """Manage staging environment access security."""

    def __init__(self):
        self.vps_ip = os.environ.get('VPS_IP')
        self.ssh_user = os.environ.get('SSH_USER', 'deploy')

    def enable_basic_auth(self, site_id: str, username: str = 'staging', password: str = None) -> dict:
        """
        Enable HTTP Basic Auth for staging site.

        Uses a WordPress plugin approach since we're behind Traefik.
        """

        if password is None:
            password = generate_password()

        wp = WPCLIExecutor(site_id)

        # Install and configure HTTP Auth plugin
        # Option 1: Use a simple mu-plugin

        mu_plugin_code = f'''<?php
/*
Plugin Name: Staging Access Protection
Description: Password protect staging environment
*/

if (!defined('ABSPATH')) exit;

// Skip for WP-CLI and cron
if (defined('WP_CLI') || defined('DOING_CRON')) return;

// Check basic auth
$valid_user = '{username}';
$valid_pass = '{password}';

$user = $_SERVER['PHP_AUTH_USER'] ?? '';
$pass = $_SERVER['PHP_AUTH_PW'] ?? '';

if ($user !== $valid_user || $pass !== $valid_pass) {{
    header('WWW-Authenticate: Basic realm="Staging Access"');
    header('HTTP/1.0 401 Unauthorized');
    echo 'This is a staging environment. Access restricted.';
    exit;
}}
'''

        # Write mu-plugin to container
        import subprocess
        import base64

        encoded = base64.b64encode(mu_plugin_code.encode()).decode()

        # Find container
        find_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker ps --filter name={site_id} --format {{{{.Names}}}} | head -1'"
        result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
        container = result.stdout.strip()

        if not container:
            return {'success': False, 'error': 'Container not found'}

        # Create mu-plugins directory and write file
        write_cmd = f"""ssh {self.ssh_user}@{self.vps_ip} 'docker exec {container} sh -c "mkdir -p /var/www/html/wp-content/mu-plugins && echo {encoded} | base64 -d > /var/www/html/wp-content/mu-plugins/staging-protection.php"'"""

        result = subprocess.run(write_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            return {'success': False, 'error': result.stderr}

        # Save credentials
        creds_file = Path(f"secrets/projects/{site_id}.env")

        existing = {}
        if creds_file.exists():
            with open(creds_file) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        k, v = line.strip().split('=', 1)
                        existing[k] = v

        existing['STAGING_USER'] = username
        existing['STAGING_PASS'] = password

        with open(creds_file, 'w') as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")

        os.chmod(creds_file, 0o600)

        return {
            'success': True,
            'username': username,
            'password': password
        }

    def disable_basic_auth(self, site_id: str) -> bool:
        """Disable HTTP Basic Auth for staging site."""

        import subprocess

        find_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker ps --filter name={site_id} --format {{{{.Names}}}} | head -1'"
        result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
        container = result.stdout.strip()

        if not container:
            return False

        # Remove mu-plugin
        remove_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker exec {container} rm -f /var/www/html/wp-content/mu-plugins/staging-protection.php'"

        result = subprocess.run(remove_cmd, shell=True)

        return result.returncode == 0

    def add_staging_notice(self, site_id: str) -> bool:
        """Add visual staging notice to WordPress admin and frontend."""

        wp = WPCLIExecutor(site_id)

        notice_plugin = '''<?php
/*
Plugin Name: Staging Notice
Description: Visual indicator that this is a staging environment
*/

// Admin notice
add_action('admin_notices', function() {
    echo '<div class="notice notice-warning"><p><strong>⚠️ STAGING ENVIRONMENT</strong> - Changes here will not affect the live site.</p></div>';
});

// Frontend notice (admin bar)
add_action('admin_bar_menu', function($wp_admin_bar) {
    $wp_admin_bar->add_node([
        'id' => 'staging-notice',
        'title' => '⚠️ STAGING',
        'meta' => ['class' => 'staging-notice']
    ]);
}, 100);

// Style the notice
add_action('wp_head', function() {
    echo '<style>#wpadminbar .staging-notice { background: #ffb900 !important; }</style>';
});
add_action('admin_head', function() {
    echo '<style>#wpadminbar .staging-notice { background: #ffb900 !important; }</style>';
});
'''

        # Write via WP-CLI eval
        import subprocess
        import base64

        encoded = base64.b64encode(notice_plugin.encode()).decode()

        find_cmd = f"ssh {self.ssh_user}@{self.vps_ip} 'docker ps --filter name={site_id} --format {{{{.Names}}}} | head -1'"
        result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
        container = result.stdout.strip()

        if not container:
            return False

        write_cmd = f"""ssh {self.ssh_user}@{self.vps_ip} 'docker exec {container} sh -c "mkdir -p /var/www/html/wp-content/mu-plugins && echo {encoded} | base64 -d > /var/www/html/wp-content/mu-plugins/staging-notice.php"'"""

        result = subprocess.run(write_cmd, shell=True)

        return result.returncode == 0
```

**Add CLI commands:**

```python
# Add to cli/staging.py

@staging.command('protect')
@click.argument('site_id')
@click.option('--username', default='staging', help='Basic auth username')
@click.option('--password', help='Basic auth password (generated if not provided)')
def protect(site_id, username, password):
    """Enable password protection for staging site."""

    from compiler.staging_security import StagingSecurity
    from compiler.environments import EnvironmentManager, Environment

    env_mgr = EnvironmentManager()
    staging_id = env_mgr.get_site_id(site_id, Environment.STAGING)

    security = StagingSecurity()

    click.echo(f"\nEnabling protection for staging: {staging_id}")

    result = security.enable_basic_auth(staging_id, username, password)

    if result['success']:
        click.echo(f"\n✓ Protection enabled!")
        click.echo(f"  Username: {result['username']}")
        click.echo(f"  Password: {result['password']}")
        click.echo(f"\n  Credentials saved to: secrets/projects/{staging_id}.env")

        # Add visual notice
        security.add_staging_notice(staging_id)
        click.echo(f"  Visual staging notice added")
    else:
        click.echo(f"\n✗ Failed: {result.get('error', 'Unknown error')}")
        raise click.Abort()

@staging.command('unprotect')
@click.argument('site_id')
def unprotect(site_id):
    """Disable password protection for staging site."""

    from compiler.staging_security import StagingSecurity
    from compiler.environments import EnvironmentManager, Environment

    env_mgr = EnvironmentManager()
    staging_id = env_mgr.get_site_id(site_id, Environment.STAGING)

    security = StagingSecurity()

    if security.disable_basic_auth(staging_id):
        click.echo(f"✓ Protection disabled for {staging_id}")
    else:
        click.echo(f"✗ Failed to disable protection")
```

**Time:** 2 hours

---

### Phase 5 Complete

After completing all steps, you have:

```
✓ Environment field in specs (production, staging, development)
✓ Environment configuration manager
✓ Database clone manager with URL replacement
✓ File sync manager for uploads, themes, plugins
✓ Staging manager orchestrating all operations
✓ CLI commands for staging operations
✓ WP-CLI based URL replacement (handles serialized data)
✓ Staging access protection (basic auth)
✓ Visual staging notices
```

**New CLI commands:**

```bash
# Create staging from production
fabrik staging:create acme-site

# Create staging with anonymized data
fabrik staging:create acme-site --anonymize

# List staging environments
fabrik staging:list

# Check staging status
fabrik staging:status acme-site

# Sync production to staging (refresh)
fabrik staging:sync acme-site --direction=prod-to-staging

# Sync staging to production (careful!)
fabrik staging:sync acme-site --direction=staging-to-prod

# Promote staging to production
fabrik staging:promote acme-site

# Enable password protection
fabrik staging:protect acme-site

# Disable password protection
fabrik staging:unprotect acme-site

# Destroy staging environment
fabrik staging:destroy acme-site
```

---

### Typical Workflow

```bash
# 1. Client requests website changes
# 2. Create staging environment
fabrik staging:create client-site --anonymize

# Output:
# ✓ Staging environment created!
#   Staging URL: https://staging.client.com
#   Username: staging
#   Password: xK7mN2pQ9rT4

# 3. Make changes in staging
#    - Test theme updates
#    - Test plugin updates
#    - Test content changes

# 4. Client reviews staging
#    Share: https://staging.client.com
#    Credentials: staging / xK7mN2pQ9rT4

# 5. Client approves
fabrik staging:promote client-site

# Output:
# ✓ Promotion complete!
#   Production backup: client_site_production_backup_1699123456
#   Database promoted: ✓
#   Files promoted: ✓

# 6. (Optional) Destroy staging
fabrik staging:destroy client-site
```

---

### Phase 5 Summary

| Step | Task | Time |
|------|------|------|
| 1 | Update spec schema with environment field | 30 min |
| 2 | Environment configuration manager | 1 hr |
| 3 | Database clone manager | 2 hrs |
| 4 | File sync manager | 2 hrs |
| 5 | Staging manager | 3 hrs |
| 6 | CLI commands | 2 hrs |
| 7 | WP-CLI URL replacement | 1 hr |
| 8 | Staging access protection | 2 hrs |

**Total: ~13 hours (2-3 days)**

---

### What's Next (Phase 6 Preview)

Phase 6 adds advanced monitoring:
- Loki for log aggregation
- Prometheus for metrics
- Grafana for visualization
- Alerting on errors and performance

---
