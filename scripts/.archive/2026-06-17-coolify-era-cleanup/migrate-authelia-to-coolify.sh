#!/bin/bash
#
# Authelia Migration to Coolify - Phase 12
# Automated migration script with safety checks
#
# Usage: ./scripts/migrate-authelia-to-coolify.sh [phase]
# Phases: test | bypass | cutover | rollback
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
VPS_HOST="vps"
BACKUP_DIR="/tmp/authelia-backup-$(date +%Y%m%d-%H%M%S)"
STANDALONE_PATH="/opt/authelia"
TEST_DOMAIN="auth-test.vps1.ocoron.com"
PROD_DOMAIN="auth.vps1.ocoron.com"

# Functions
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check SSH access
    if ! ssh $VPS_HOST "echo 'SSH OK'" > /dev/null 2>&1; then
        log_error "Cannot SSH to VPS"
        exit 1
    fi

    # Check standalone Authelia is running
    if ! ssh $VPS_HOST "sudo docker ps | grep -q 'authelia'" > /dev/null 2>&1; then
        log_error "Standalone Authelia not running"
        exit 1
    fi

    log_info "Prerequisites OK"
}

backup_config() {
    log_info "Creating backup..."
    ssh $VPS_HOST "sudo tar -czf $BACKUP_DIR.tar.gz $STANDALONE_PATH/config/"
    log_info "Backup created: $BACKUP_DIR.tar.gz"
}

phase_test() {
    log_info "=== PHASE 12A: Test Instance Deployment ==="

    check_prerequisites
    backup_config

    log_warn "Manual step required:"
    echo ""
    echo "1. Open Coolify UI: https://coolify.vps1.ocoron.com"
    echo "2. Navigate to fabrik-services project"
    echo "3. Click '+ New Resource' > 'Docker Compose'"
    echo "4. Name: authelia-test"
    echo "5. Paste compose from: specs/infrastructure/authelia-coolify.yaml"
    echo "6. Click 'Save' then 'Deploy'"
    echo ""
    read -p "Press ENTER when deployment is complete..."

    # Wait for container
    log_info "Waiting for container to start..."
    sleep 10

    # Get container name
    CONTAINER=$(ssh $VPS_HOST "sudo docker ps | grep authelia-test | grep -v grep | awk '{print \$NF}'" | tr -d '\r\n')

    if [ -z "$CONTAINER" ]; then
        log_error "Container not found. Check Coolify deployment."
        exit 1
    fi

    log_info "Container found: $CONTAINER"

    # Copy config files
    log_info "Copying configuration files..."
    ssh $VPS_HOST "sudo docker cp $STANDALONE_PATH/config/configuration.yml $CONTAINER:/config/"
    ssh $VPS_HOST "sudo docker cp $STANDALONE_PATH/config/users_database.yml $CONTAINER:/config/"
    ssh $VPS_HOST "sudo docker cp $STANDALONE_PATH/config/db.sqlite3 $CONTAINER:/config/"

    # Restart container
    log_info "Restarting container to load config..."
    ssh $VPS_HOST "sudo docker restart $CONTAINER"
    sleep 15

    # Check health
    log_info "Checking health endpoint..."
    if curl -f -s "https://$TEST_DOMAIN/api/health" > /dev/null 2>&1; then
        log_info "Health check passed!"
    else
        log_warn "Health check failed. Container may still be starting..."
        log_warn "Check manually: curl https://$TEST_DOMAIN/api/health"
    fi

    log_info "=== Phase 12A Complete ==="
    echo ""
    log_warn "Next steps:"
    echo "1. Test login at: https://$TEST_DOMAIN"
    echo "2. Verify 2FA works"
    echo "3. Run: ./scripts/migrate-authelia-to-coolify.sh bypass"
}

phase_bypass() {
    log_info "=== PHASE 12B: IP Bypass Configuration ==="

    # Get WSL IP
    WSL_IP=$(curl -s ifconfig.me)
    log_info "Your WSL IP: $WSL_IP"

    log_warn "Manual configuration required:"
    echo ""
    echo "Add this to BOTH Authelia instances' configuration.yml:"
    echo ""
    echo "access_control:"
    echo "  default_policy: deny"
    echo "  rules:"
    echo "    # SAFETY NET - Remove after migration"
    echo "    - domain: \"*.vps1.ocoron.com\""
    echo "      policy: bypass"
    echo "      networks:"
    echo "        - \"$WSL_IP/32\""
    echo ""
    echo "Standalone: ssh $VPS_HOST \"sudo nano $STANDALONE_PATH/config/configuration.yml\""
    echo "Test instance: Edit via Coolify UI or docker exec"
    echo ""
    read -p "Press ENTER when both configs are updated..."

    # Restart both
    log_info "Restarting both instances..."
    ssh $VPS_HOST "cd $STANDALONE_PATH && sudo docker compose restart"

    CONTAINER=$(ssh $VPS_HOST "sudo docker ps | grep authelia-test | grep -v grep | awk '{print \$NF}'" | tr -d '\r\n')
    ssh $VPS_HOST "sudo docker restart $CONTAINER"

    sleep 10

    log_info "=== Phase 12B Complete ==="
    echo ""
    log_warn "Test bypass:"
    echo "1. Access https://monitor.vps1.ocoron.com from WSL"
    echo "2. Should load WITHOUT 2FA prompt"
    echo "3. If working, run: ./scripts/migrate-authelia-to-coolify.sh cutover"
}

phase_cutover() {
    log_info "=== PHASE 12C: Production Cutover ==="

    log_error "⚠️  HIGH RISK OPERATION ⚠️"
    echo ""
    echo "This will:"
    echo "1. Stop standalone Authelia"
    echo "2. Switch test instance to production domain"
    echo "3. Update all protected services"
    echo ""
    echo "Rollback available via: ./scripts/migrate-authelia-to-coolify.sh rollback"
    echo ""
    read -p "Type 'PROCEED' to continue: " confirm

    if [ "$confirm" != "PROCEED" ]; then
        log_warn "Cutover cancelled"
        exit 0
    fi

    # Stop standalone
    log_info "Stopping standalone Authelia..."
    ssh $VPS_HOST "cd $STANDALONE_PATH && sudo docker compose down"

    log_warn "Manual steps required:"
    echo ""
    echo "1. In Coolify UI, edit authelia-test service"
    echo "2. Change domain from $TEST_DOMAIN to $PROD_DOMAIN"
    echo "3. Redeploy service"
    echo "4. Wait for Let's Encrypt cert (~2 min)"
    echo ""
    read -p "Press ENTER when domain is updated and deployed..."

    # Get new container name
    CONTAINER=$(ssh $VPS_HOST "sudo docker ps | grep authelia | grep -v grep | awk '{print \$NF}'" | tr -d '\r\n')
    log_info "New container: $CONTAINER"

    # Test production domain
    log_info "Testing production domain..."
    sleep 30

    if curl -f -s "https://$PROD_DOMAIN/api/health" > /dev/null 2>&1; then
        log_info "Production domain health check passed!"
    else
        log_error "Production domain health check failed!"
        log_error "Run rollback: ./scripts/migrate-authelia-to-coolify.sh rollback"
        exit 1
    fi

    log_info "=== Phase 12C Complete ==="
    echo ""
    log_warn "Final steps:"
    echo "1. Test all dashboards (n8n, Grafana, Netdata, Backrest, Apprise)"
    echo "2. Remove IP bypass from config"
    echo "3. Test 2FA from incognito browser"
    echo "4. Update documentation"
}

phase_rollback() {
    log_error "=== ROLLBACK: Restoring Standalone Authelia ==="

    # Restore standalone
    log_info "Starting standalone Authelia..."
    ssh $VPS_HOST "cd $STANDALONE_PATH && sudo docker compose up -d"

    sleep 15

    # Check health
    if curl -f -s "https://$PROD_DOMAIN/api/health" > /dev/null 2>&1; then
        log_info "Standalone Authelia restored successfully!"
    else
        log_error "Rollback failed. Manual intervention required."
        exit 1
    fi

    log_info "=== Rollback Complete ==="
    echo ""
    log_warn "Cleanup:"
    echo "1. Delete authelia-test service from Coolify UI"
    echo "2. Review what went wrong"
}

# Main
case "${1:-}" in
    test)
        phase_test
        ;;
    bypass)
        phase_bypass
        ;;
    cutover)
        phase_cutover
        ;;
    rollback)
        phase_rollback
        ;;
    *)
        echo "Usage: $0 {test|bypass|cutover|rollback}"
        echo ""
        echo "Phases:"
        echo "  test     - Deploy test instance on auth-test.vps1.ocoron.com"
        echo "  bypass   - Add IP bypass for safety"
        echo "  cutover  - Switch to production domain"
        echo "  rollback - Restore standalone Authelia"
        exit 1
        ;;
esac
