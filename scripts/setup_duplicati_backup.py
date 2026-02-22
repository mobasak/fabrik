#!/usr/bin/env python3
"""Setup Duplicati backup for VPS - Full Automation."""

import argparse
import base64
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
from scripts.utils.subprocess_helper import safe_run

load_dotenv(Path(__file__).parent.parent / ".env")

B2_BUCKET = os.getenv("B2_BUCKET_NAME", "fabrik-backups")
B2_ACCOUNT_ID = os.getenv("B2_KEY_ID", "")
B2_APP_KEY = os.getenv("B2_APPLICATION_KEY", "")
DUPLICATI_PASSPHRASE = os.getenv("DUPLICATI_PASSPHRASE", "")
SERVER_DB = "/var/lib/docker/volumes/duplicati_duplicati-config/_data/Duplicati-server.sqlite"
BACKUP_DB = "/config/VPS-Complete-Backup.sqlite"
SOURCES = ["/source/opt/", "/source/docker-volumes/", "/source/data/coolify/"]
EXCLUDES = [
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/.git/**",
    "**/*.log",
    "**/venv/**",
    "**/.venv/**",
]
DBLOCK_SIZE = "1GB"


def ssh(cmd: str, timeout: int = 30, redact: bool = False) -> str:
    """Execute SSH command on VPS. If redact=True, secrets are hidden in error messages."""
    try:
        result = safe_run(["ssh", "vps", cmd], timeout=timeout)
        return (result.stdout or "").strip()
    except subprocess.TimeoutExpired as e:
        display_cmd = "[REDACTED]" if redact else cmd
        raise RuntimeError(f"Timeout executing SSH command: {display_cmd}") from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        display_cmd = "[REDACTED]" if redact else cmd
        raise RuntimeError(
            f"Error executing SSH command ({e.returncode}): {display_cmd}\n{stderr}"
        ) from e


def ssh_sql_with_secrets(db_path: str, sql: str) -> str:
    """Execute SQL on VPS via base64 to avoid leaking secrets in error messages."""
    encoded = base64.b64encode(sql.encode()).decode()
    cmd = f"echo '{encoded}' | base64 -d | sudo sqlite3 {db_path}"
    return ssh(cmd, redact=True)


def escape_sql(value: str) -> str:
    """Escape single quotes for SQL and shell metacharacters for remote execution."""
    # SQL: escape single quotes by doubling
    escaped = value.replace("'", "''")
    # Shell: escape backslashes, double quotes, $ (variable expansion), backticks (command substitution)
    escaped = (
        escaped.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    )
    return escaped


def target_url():
    """Return credential-free B2 URL. Credentials are passed via separate options."""
    return f"b2://{B2_BUCKET}/vps1-backup"


def setup_secrets_file():
    """Write protected secrets file to VPS using base64 to avoid shell injection."""
    print("Setting up secrets file on VPS...")
    secrets_content = f"""B2_ACCOUNT_ID={B2_ACCOUNT_ID}
B2_APP_KEY={B2_APP_KEY}
DUPLICATI_PASSPHRASE={DUPLICATI_PASSPHRASE}
"""
    # Base64 encode to avoid shell metacharacter issues
    encoded = base64.b64encode(secrets_content.encode()).decode()
    ssh(f"echo '{encoded}' | base64 -d | sudo tee /etc/duplicati-secrets.env > /dev/null")
    ssh(
        "sudo chmod 600 /etc/duplicati-secrets.env && sudo chown root:root /etc/duplicati-secrets.env"
    )
    print("✅ Secrets file created at /etc/duplicati-secrets.env")


def setup():
    # Set up secrets file first
    setup_secrets_file()

    print("Stopping Duplicati...")
    ssh("sudo docker stop duplicati || true")  # Non-fatal if not running
    print("Cleaning existing jobs...")
    ssh(
        f'sudo sqlite3 {SERVER_DB} "DELETE FROM Schedule; DELETE FROM Option WHERE BackupID>0; DELETE FROM Filter; DELETE FROM Source; DELETE FROM Backup;"'
    )

    print("Creating backup job...")
    target_escaped = escape_sql(target_url())
    ssh(
        f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Backup (Name,Description,Tags,TargetURL,DBPath) VALUES ('VPS Complete Backup','Full VPS backup to B2','','{target_escaped}','{BACKUP_DB}');"'''
    )
    bid_str = ssh(f'sudo sqlite3 {SERVER_DB} "SELECT MAX(ID) FROM Backup;"')
    if not bid_str or not bid_str.isdigit():
        raise RuntimeError(f"Failed to create backup job: got '{bid_str}' from MAX(ID) query")
    bid = int(bid_str)

    for s in SOURCES:
        ssh(f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Source VALUES ({bid},'{s}');"''')
    for i, e in enumerate(EXCLUDES):
        ssh(f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Filter VALUES ({bid},{i},0,'{e}');"''')
    # Insert options with secrets via base64 to avoid leaking in error messages
    for n, v in [
        ("encryption-module", "aes"),
        ("passphrase", DUPLICATI_PASSPHRASE),
        ("b2-accountid", B2_ACCOUNT_ID),
        ("b2-applicationkey", B2_APP_KEY),
        ("dblock-size", DBLOCK_SIZE),
    ]:
        # Escape single quotes for SQL only (base64 handles shell layer)
        v_sql = v.replace("'", "''")
        sql = f"INSERT INTO Option VALUES ({bid},'','{n}','{v_sql}');"
        ssh_sql_with_secrets(SERVER_DB, sql)
    ssh(
        f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Schedule VALUES ({bid},'ID={bid}',strftime('%s','now'),'1D',0,'');"'''
    )

    print("Setting up cron...")
    ssh("sudo mkdir -p /opt/scripts")
    excl = " ".join([f"--exclude='{e}'" for e in EXCLUDES])
    # Cron script sources secrets file and passes credentials via CLI flags (shell variables, not Python interpolated)
    script = f"""#!/bin/bash
source /etc/duplicati-secrets.env
docker exec duplicati /app/duplicati/duplicati-cli backup '{target_url()}' --b2-accountid="$B2_ACCOUNT_ID" --b2-applicationkey="$B2_APP_KEY" --passphrase="$DUPLICATI_PASSPHRASE" --encryption-module=aes {" ".join(SOURCES)} --dblock-size={DBLOCK_SIZE} {excl} --dbpath={BACKUP_DB} 2>&1 | logger -t duplicati-backup
"""
    # Base64 encode script to avoid shell quoting issues
    script_encoded = base64.b64encode(script.encode()).decode()
    ssh(
        f"echo '{script_encoded}' | base64 -d | sudo tee /opt/scripts/duplicati-backup.sh > /dev/null && sudo chmod +x /opt/scripts/duplicati-backup.sh"
    )
    ssh(
        """echo '0 5 * * * root /opt/scripts/duplicati-backup.sh' | sudo tee /etc/cron.d/duplicati-backup > /dev/null"""
    )

    print("Starting Duplicati...")
    ssh("sudo docker start duplicati")
    time.sleep(3)
    print(
        f"\n✅ Backup job created (ID={bid})! Run with: python setup_duplicati_backup.py --run-backup"
    )
    return bid


def run_backup():
    print("Running backup...")
    excl = " ".join([f"--exclude='{e}'" for e in EXCLUDES])
    # Source secrets file on VPS and pass credentials via CLI flags (shell variables, not Python interpolated)
    cmd = f"""source /etc/duplicati-secrets.env && sudo docker exec duplicati /app/duplicati/duplicati-cli backup '{target_url()}' --b2-accountid="$B2_ACCOUNT_ID" --b2-applicationkey="$B2_APP_KEY" --passphrase="$DUPLICATI_PASSPHRASE" --encryption-module=aes {' '.join(SOURCES)} --dblock-size={DBLOCK_SIZE} {excl} --dbpath={BACKUP_DB}"""
    try:
        result = safe_run(["ssh", "vps", cmd], timeout=300)
        output = result.stdout or ""
        print(output[-2000:] if len(output) > 2000 else output)
    except subprocess.TimeoutExpired:
        print("Backup command timed out after 300s")
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        print(f"Backup command failed: {stderr or str(e)}")


if __name__ == "__main__":
    if not B2_ACCOUNT_ID or not B2_APP_KEY or not DUPLICATI_PASSPHRASE:
        print("Error: B2_KEY_ID, B2_APPLICATION_KEY, and DUPLICATI_PASSPHRASE must all be set")
        sys.exit(1)
    p = argparse.ArgumentParser()
    p.add_argument("--run-backup", action="store_true")
    args = p.parse_args()
    if args.run_backup:
        run_backup()
    else:
        setup()
