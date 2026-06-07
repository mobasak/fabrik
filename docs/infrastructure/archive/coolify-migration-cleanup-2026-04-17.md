# Coolify Migration Cleanup Process

> **📌 ARCHIVED 2026-06-06.** Historical document preserved as-is for context. Frozen at the time of original ship. For current fleet state see [`vps-status.md`](../vps-status.md), [`vps-complete-inventory.md`](../vps-complete-inventory.md), and [`vps-fleet-architecture.md`](../vps-fleet-architecture.md). Do NOT update the content below — that would defeat the archive.

**Date:** 2026-04-17
**Purpose:** Document the cleanup process after migrating services to Coolify management

---

## Overview

After migrating services from standalone Docker Compose to Coolify-managed deployments, old containers and volumes must be removed to prevent:
- Wasted disk space
- Resource conflicts (duplicate services running)
- Confusion about which containers are active
- Unnecessary backup overhead

---

## Cleanup Checklist

### 1. Stop Old Docker Compose Stack

**Location:** `/opt/monitoring/compose.yaml`

```bash
cd /opt/monitoring
sudo docker compose down
```

This removes all containers defined in the compose file that are no longer needed.

**Services removed:**
- grafana
- prometheus
- loki
- alertmanager
- promtail
- cadvisor
- node-exporter

### 2. Remove Standalone Services

For services not in compose files (like duplicati):

```bash
sudo docker stop <container_name>
sudo docker rm <container_name>
```

### 3. Identify Old Volumes

List volumes and identify which belong to old services:

```bash
# List all volumes
sudo docker volume ls

# Find volumes for specific services
sudo docker volume ls | grep -E '(duplicati|apprise|netdata|n8n)'
```

### 4. Remove Old Service Volumes

**CRITICAL:** Only remove volumes for services that have been migrated and their data preserved in new Coolify-managed volumes.

```bash
# Remove specific old volumes
sudo docker volume rm \
  duplicati_duplicati-config \
  apprise_apprise_config \
  n8n_n8n_data \
  netdata_netdata-cache \
  netdata_netdata-config \
  netdata_netdata-lib \
  tmp_netdata-test-cache \
  tmp_netdata-test-config \
  tmp_netdata-test-lib
```

### 5. Prune Dangling Volumes

Remove volumes not attached to any container:

```bash
sudo docker volume prune -f
```

**Result:** Reclaimed 61.53MB in our case.

### 6. Prune Unused Images

Remove old Docker images no longer in use:

```bash
# Remove images not used in last 24h
sudo docker image prune -a -f --filter 'until=24h'
```

**Result:** Reclaimed 2.821GB in our case.

### 7. Verify Coolify Services Still Running

After cleanup, verify all migrated services are still healthy:

```bash
sudo docker ps --filter 'label=coolify.managed=true' --format 'table {{.Names}}\t{{.Status}}'
```

All services should show as running/healthy.

---

## Verification Steps

### Check Disk Space

```bash
df -h /
sudo docker system df
```

### Verify No Old Containers

```bash
# Should return empty
sudo docker ps -a --filter 'status=exited'
```

### Verify No Dangling Volumes

```bash
# Should return empty or minimal
sudo docker volume ls -qf dangling=true
```

### Verify Coolify Services

```bash
# All migrated services should appear
sudo docker ps --filter 'label=coolify.managed=true'
```

---

## Results (2026-04-17 Migration)

### Space Reclaimed

| Item | Size |
|------|------|
| Old service volumes | ~100MB |
| Dangling volumes | 61.53MB |
| Unused Docker images | 2.821GB |
| **Total** | **2.88GB** |

### Services Cleaned

| Service | Containers Removed | Volumes Removed |
|---------|-------------------|-----------------|
| duplicati | 1 | 1 |
| grafana | 1 | 0 (external) |
| prometheus | 1 | 0 (external) |
| loki | 1 | 0 (external) |
| alertmanager | 1 | 0 (external) |
| promtail | 1 | 0 (external) |
| cadvisor | 1 | 0 |
| node-exporter | 1 | 0 |
| netdata | 0 (already removed) | 3 |
| n8n | 0 (already removed) | 1 |
| apprise | 0 (already removed) | 1 |

**Note:** External volumes were preserved and reused by Coolify-managed containers.

---

## Safety Guidelines

### Before Removing Volumes

1. ✅ Verify service is migrated to Coolify
2. ✅ Verify new service is running and healthy
3. ✅ Verify data is accessible in new service
4. ✅ Take backup if volume contains unique data
5. ✅ Document volume name and purpose

### Volume Naming Convention

- **Old volumes:** `<service>_<volume_name>` (e.g., `n8n_n8n_data`)
- **Coolify volumes:** `<uuid>_<volume_name>` (e.g., `s8gwccsws0ccssw0wwgwsoks_n8n-data`)
- **External volumes:** `monitoring_<volume_name>` (e.g., `monitoring_prometheus-data`)

### What NOT to Remove

❌ **Never remove:**
- Volumes with `coolify` in the name
- Volumes currently in use (check with `docker volume inspect`)
- Volumes for services not yet migrated
- Database volumes without verified backup

---

## Automation Script

For future migrations, this process can be automated:

```bash
#!/bin/bash
# cleanup-after-migration.sh

set -e

SERVICE_NAME=$1
COMPOSE_DIR=$2

if [ -z "$SERVICE_NAME" ] || [ -z "$COMPOSE_DIR" ]; then
    echo "Usage: $0 <service_name> <compose_dir>"
    exit 1
fi

echo "=== Cleanup for $SERVICE_NAME ==="

# 1. Stop compose stack
cd "$COMPOSE_DIR"
sudo docker compose stop "$SERVICE_NAME"
sudo docker compose rm -f "$SERVICE_NAME"

# 2. List volumes for this service
echo "Volumes for $SERVICE_NAME:"
sudo docker volume ls | grep "$SERVICE_NAME"

# 3. Ask for confirmation
read -p "Remove these volumes? (y/N): " confirm
if [ "$confirm" = "y" ]; then
    sudo docker volume ls -q | grep "$SERVICE_NAME" | xargs -r sudo docker volume rm
    echo "✓ Volumes removed"
fi

# 4. Prune dangling volumes
echo "Pruning dangling volumes..."
sudo docker volume prune -f

echo "✓ Cleanup complete"
```

---

## Lessons Learned

1. **External volumes are preserved** - Using `external: true` in Coolify compose prevents accidental deletion
2. **Old containers can run alongside new ones** - Docker doesn't prevent duplicate services, wasting resources
3. **Prune regularly** - Dangling volumes and unused images accumulate quickly
4. **Verify before delete** - Always check service health after cleanup
5. **Document volume mappings** - Keep track of old → new volume relationships

---

## Related Documentation

- Migration summary: `docs/infrastructure/MIGRATION_SUMMARY.md`
- Coolify status: `docs/infrastructure/COOLIFY_STATUS.md`
- Migration runbook: `docs/infrastructure/archive/coolify-migration.md`
- Lessons learnt: `docs/LESSONS_LEARNT.md`
