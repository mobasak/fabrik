# Fabrik Development Tasks

## Phase 1: Foundation

### VPS Hardening

- [ ] Task 1.1: SSH hardening (keys only, no root, AllowUsers)
- [ ] Task 1.2: UFW firewall (22, 80, 443 only)
- [ ] Task 1.3: Fail2ban setup
- [ ] Task 1.4: Unattended upgrades
- [ ] Task 1.5: Docker log rotation

### Coolify Setup

- [ ] Task 1.6: Install Coolify
- [ ] Task 1.7: Secure Coolify (password, HTTPS)
- [ ] Task 1.8: Deploy postgres-main via UI
- [ ] Task 1.9: Deploy redis-main via UI
- [ ] Task 1.10: Configure postgres backup to B2

### Fabrik Core

- [ ] Task 1.11: Create folder structure
  - [x] Set up project per .windsurfrules
  - [ ] Initialize Python package structure
- [ ] Task 1.12: Set up secrets (platform.env)
- [ ] Task 1.13: Implement spec_loader.py
- [ ] Task 1.14: Implement dns_namecheap.py (export→diff→apply)
- [ ] Task 1.15: Implement coolify.py driver
- [ ] Task 1.16: Implement template_renderer.py
- [ ] Task 1.17: Implement `fabrik new`
- [ ] Task 1.18: Implement `fabrik plan`
- [ ] Task 1.19: Implement `fabrik apply`

### First Deployment

- [ ] Task 1.20: Create app-python template
- [ ] Task 1.21: Deploy hello-api end-to-end

### WordPress

- [ ] Task 1.22: Create wp-site template
- [ ] Task 1.23: Implement WP post-deploy hooks
- [ ] Task 1.24: Deploy test WordPress site

### Monitoring

- [ ] Task 1.25: Deploy Uptime Kuma
- [ ] Task 1.26: Configure checks + alerts

### Validation

- [ ] Task 1.27: Test backup + restore

---

## Phase 2: WordPress Automation

Status: Not started

## Phase 3: AI Content Integration

Status: Not started

## Phase 4: DNS Migration + Advanced Networking

Status: Not started

## Phase 5: Staging + Multi-Environment

Status: Not started

## Phase 6: Advanced Monitoring

Status: Not started

## Phase 7: Multi-Server Scaling

Status: Not started

## Phase 8: Business Automation (n8n)

Status: Not started
