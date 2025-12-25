#!/usr/bin/env python3
"""
Setup Duplicati backup job via web API.
Creates a backup job for VPS data to Backblaze B2.
"""

import requests
import json
import hashlib
import base64
from urllib.parse import urljoin

DUPLICATI_URL = "https://backup.vps1.ocoron.com"
PASSWORD = "fabrik2025"

# B2 Configuration
B2_BUCKET = "vps1-ocoron-backups"
B2_ACCOUNT_ID = "0044e7ca36a086b0000000001"
B2_APP_KEY = "K004hcjQVRBA8hLY0uZzzKEYg4crlq8"

# Backup sources
SOURCES = [
    "/source/opt/traefik/",
    "/source/opt/captcha/",
    "/source/opt/emailgateway/",
    "/source/opt/translator/",
    "/source/opt/namecheap/",
    "/source/opt/proxy/",
    "/source/opt/redis/",
    "/source/opt/netdata/",
    "/source/opt/duplicati/",
    "/source/opt/email-reader/",
    "/source/opt/youtube/",
    "/source/docker-volumes/coolify-db/",
    "/source/docker-volumes/proxy_postgres_data/",
]

# Exclude filters
EXCLUDES = [
    "**/node_modules/",
    "**/__pycache__/",
    "**/.git/",
    "**/*.log",
    "**/*.pyc",
    "**/venv/",
    "**/.venv/",
    "**/.cache/",
]

def get_session():
    """Create authenticated session with Duplicati."""
    session = requests.Session()
    
    # Get the initial page to get nonce
    resp = session.get(DUPLICATI_URL)
    
    # Try to login
    login_url = urljoin(DUPLICATI_URL, "/api/v1/auth/login")
    
    # Duplicati uses a salted password hash
    # First get server state to check if password is needed
    state_resp = session.get(urljoin(DUPLICATI_URL, "/api/v1/serverstate"))
    
    if state_resp.status_code == 200:
        print("Already authenticated or no password required")
        return session
    
    # Try password login
    login_data = {"password": PASSWORD}
    login_resp = session.post(login_url, json=login_data)
    
    if login_resp.status_code == 200:
        print("Login successful")
        return session
    else:
        print(f"Login failed: {login_resp.status_code} - {login_resp.text}")
        return None

def create_backup_job(session):
    """Create the backup job configuration."""
    
    backup_config = {
        "Backup": {
            "Name": "VPS Daily Backup",
            "Description": "Full VPS backup to B2 - configs, volumes, databases",
            "Tags": [],
            "TargetURL": f"b2://{B2_BUCKET}/duplicati?b2-accountid={B2_ACCOUNT_ID}&b2-applicationkey={B2_APP_KEY}",
            "DBPath": "",
            "Sources": SOURCES,
            "Settings": [
                {"Name": "passphrase", "Value": "fabrik2025backup"},
                {"Name": "retention-policy", "Value": "7D:1D"},
                {"Name": "dblock-size", "Value": "50mb"},
            ],
            "Filters": [{"Expression": f"-{e}", "Include": False} for e in EXCLUDES],
            "Metadata": {}
        },
        "Schedule": {
            "ID": 1,
            "Tags": [],
            "Time": "02:00",
            "Repeat": "1D",
            "LastRun": None,
            "Rule": "",
            "AllowedDays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        }
    }
    
    # Create backup via API
    create_url = urljoin(DUPLICATI_URL, "/api/v1/backups")
    resp = session.post(create_url, json=backup_config)
    
    if resp.status_code in [200, 201]:
        print("Backup job created successfully!")
        return resp.json()
    else:
        print(f"Failed to create backup: {resp.status_code} - {resp.text}")
        return None

def run_backup(session, backup_id):
    """Trigger a backup run."""
    run_url = urljoin(DUPLICATI_URL, f"/api/v1/backup/{backup_id}/run")
    resp = session.post(run_url)
    
    if resp.status_code == 200:
        print("Backup started!")
        return True
    else:
        print(f"Failed to start backup: {resp.status_code} - {resp.text}")
        return False

def main():
    print("Setting up Duplicati backup job...")
    
    session = get_session()
    if not session:
        print("Failed to authenticate")
        return 1
    
    result = create_backup_job(session)
    if result:
        backup_id = result.get("ID", 1)
        print(f"Backup job created with ID: {backup_id}")
        
        print("Starting first backup...")
        run_backup(session, backup_id)
    
    return 0

if __name__ == "__main__":
    exit(main())
