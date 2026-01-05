#!/usr/bin/env python3
"""Setup Duplicati backup for VPS - Full Automation."""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

B2_BUCKET = os.getenv("B2_BUCKET_NAME", "vps1-ocoron-backups")
B2_ACCOUNT_ID = os.getenv("B2_KEY_ID", "")
B2_APP_KEY = os.getenv("B2_APPLICATION_KEY", "")
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


def ssh(cmd):
    return subprocess.run(["ssh", "vps", cmd], capture_output=True, text=True).stdout.strip()


def target_url():
    return (
        f"b2://{B2_BUCKET}/vps1-backup?b2-accountid={B2_ACCOUNT_ID}&b2-applicationkey={B2_APP_KEY}"
    )


def setup():
    print("Stopping Duplicati...")
    ssh("sudo docker stop duplicati")
    print("Cleaning existing jobs...")
    ssh(
        f'sudo sqlite3 {SERVER_DB} "DELETE FROM Schedule; DELETE FROM Option WHERE BackupID>0; DELETE FROM Filter; DELETE FROM Source; DELETE FROM Backup;"'
    )

    print("Creating backup job...")
    ssh(
        f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Backup (Name,Description,Tags,TargetURL,DBPath) VALUES ('VPS Complete Backup','Full VPS backup to B2','','{target_url()}','{BACKUP_DB}');"'''
    )
    bid = int(ssh(f'sudo sqlite3 {SERVER_DB} "SELECT MAX(ID) FROM Backup;"'))

    for s in SOURCES:
        ssh(f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Source VALUES ({bid},'{s}');"''')
    for i, e in enumerate(EXCLUDES):
        ssh(f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Filter VALUES ({bid},{i},0,'{e}');"''')
    for n, v in [
        ("encryption-module", ""),
        ("no-encryption", "true"),
        ("dblock-size", DBLOCK_SIZE),
    ]:
        ssh(f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Option VALUES ({bid},'','{n}','{v}');"''')
    ssh(
        f'''sudo sqlite3 {SERVER_DB} "INSERT INTO Schedule VALUES ({bid},'ID={bid}',strftime('%s','2025-01-01 05:00:00'),'1D',0,'');"'''
    )

    print("Setting up cron...")
    ssh("sudo mkdir -p /opt/scripts")
    excl = " ".join([f"--exclude='{e}'" for e in EXCLUDES])
    script = f"""docker exec duplicati /app/duplicati/duplicati-cli backup '{target_url()}' {" ".join(SOURCES)} --no-encryption --dblock-size={DBLOCK_SIZE} {excl} --dbpath={BACKUP_DB} 2>&1 | logger -t duplicati-backup"""
    ssh(
        f"""echo '#!/bin/bash\n{script}' | sudo tee /opt/scripts/duplicati-backup.sh > /dev/null && sudo chmod +x /opt/scripts/duplicati-backup.sh"""
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
    cmd = f"sudo docker exec duplicati /app/duplicati/duplicati-cli backup '{target_url()}' {' '.join(SOURCES)} --no-encryption --dblock-size={DBLOCK_SIZE} {excl} --dbpath={BACKUP_DB}"
    r = subprocess.run(["ssh", "vps", cmd], capture_output=True, text=True)
    print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)


if __name__ == "__main__":
    if not B2_ACCOUNT_ID or not B2_APP_KEY:
        print("Error: B2 credentials missing")
        sys.exit(1)
    p = argparse.ArgumentParser()
    p.add_argument("--run-backup", action="store_true")
    args = p.parse_args()
    if args.run_backup:
        run_backup()
    else:
        setup()
