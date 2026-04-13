#!/bin/bash
# Create PostgreSQL development database for Fabrik projects
# Usage: ./create_pg_dev_db.sh <project-name>

if [ -z "$1" ]; then
    echo "Usage: $0 <project-name>"
    echo "Example: $0 my-api"
    exit 1
fi

PROJECT_NAME="$1"
DB_NAME="${PROJECT_NAME//-/_}_dev"

echo "Checking database: $DB_NAME"

# Check if database exists (exact match to avoid partial name collisions)
if sudo -u postgres psql -lqt 2>/dev/null | cut -d'|' -f1 | tr -d ' ' | grep -qx "$DB_NAME"; then
    echo "✅ Database $DB_NAME already exists"
else
    if sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" 2>/dev/null; then
        echo "✅ Created database: $DB_NAME"
    else
        echo "❌ Failed to create database: $DB_NAME"
        echo "   Run manually: sudo -u postgres psql -c 'CREATE DATABASE $DB_NAME;'"
        exit 1
    fi
fi

echo ""
echo "  CONNECTION: postgresql://postgres@localhost:5432/$DB_NAME"
echo "  PSQL:       psql -U postgres -d $DB_NAME"
