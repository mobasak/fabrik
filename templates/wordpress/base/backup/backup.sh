#!/bin/sh
# Fabrik WordPress Backup Script
# Usage: backup.sh [daily|weekly]

set -e

BACKUP_TYPE="${1:-daily}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_BACKUP="${BACKUP_DIR}/${SITE_NAME}_db_${TIMESTAMP}.sql.gz"
FILES_BACKUP="${BACKUP_DIR}/${SITE_NAME}_files_${TIMESTAMP}.tar.gz"

echo "[$(date)] Starting ${BACKUP_TYPE} backup for ${SITE_NAME}"

# Database backup
echo "[$(date)] Dumping database..."
mysqldump -h "${DB_HOST}" -u "${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}" | gzip > "${DB_BACKUP}"
echo "[$(date)] Database dump complete: ${DB_BACKUP}"

# Upload DB backup to R2
echo "[$(date)] Uploading database backup to R2..."
aws s3 cp "${DB_BACKUP}" "s3://${R2_BUCKET}/wordpress/${SITE_NAME}/${BACKUP_TYPE}/db/" \
    --endpoint-url "${R2_ENDPOINT}"

# Weekly: Full files backup
if [ "${BACKUP_TYPE}" = "weekly" ]; then
    echo "[$(date)] Creating files backup..."
    tar -czf "${FILES_BACKUP}" -C /wordpress wp-content/uploads wp-content/plugins wp-content/themes 2>/dev/null || true
    
    echo "[$(date)] Uploading files backup to R2..."
    aws s3 cp "${FILES_BACKUP}" "s3://${R2_BUCKET}/wordpress/${SITE_NAME}/${BACKUP_TYPE}/files/" \
        --endpoint-url "${R2_ENDPOINT}"
    
    rm -f "${FILES_BACKUP}"
fi

# Cleanup local backups older than 7 days
find "${BACKUP_DIR}" -name "*.gz" -mtime +7 -delete

# Cleanup R2: Keep 7 daily, 4 weekly
echo "[$(date)] Cleaning up old R2 backups..."
# List and delete old daily backups (keep last 7)
aws s3 ls "s3://${R2_BUCKET}/wordpress/${SITE_NAME}/daily/db/" --endpoint-url "${R2_ENDPOINT}" | \
    sort -r | tail -n +8 | awk '{print $4}' | \
    xargs -I {} aws s3 rm "s3://${R2_BUCKET}/wordpress/${SITE_NAME}/daily/db/{}" --endpoint-url "${R2_ENDPOINT}" 2>/dev/null || true

rm -f "${DB_BACKUP}"

echo "[$(date)] Backup complete for ${SITE_NAME}"
