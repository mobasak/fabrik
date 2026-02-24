# Test Execution Plan

## Overview
Running comprehensive sanity checks and test suites for the Traycer/Factory proxy management system.

## Test Execution Order

### 1. System Sanity Check (sanity_check.py)
- **Default mode**: Full check with database and API calls
  - Tests: Configuration health (5 checks)
  - Tests: Database connectivity (4 checks)
  - Tests: Core API functionality (8 checks)
  - Tests: Webshare integration (3 checks)
  - Tests: System services (2 checks)
  - Tests: Simulation infrastructure (3 checks)
  - **Total**: 25 checks across 6 sections

- **Quick mode**: Fast check using simulation (skips API calls)
  - Useful for CI/CD pipelines
  - Uses SQLite + SimulatedClock instead of PostgreSQL + Webshare API

### 2. Integration Tests
Run `tests/integration_test.py` to verify:
- Proxy selection and success tracking
- Failure escalation: healthy → cooldown_1 → cooldown_2 → dead
- Time-based cooldown expiry
- Pool statistics accuracy
- Complete simulation flow (2-hour operations test)

### 3. Infrastructure Tests
Run `tests/test_infrastructure.py` to verify:
- DataSeeder functionality (proxy/service creation)
- QueryHelper functionality (database queries)
- Cooldown filtering logic
- Service isolation (YouTube ban doesn't affect website scraping)
- Ordering logic (least-used proxies first)
- Realistic scenario testing

## Output
- Summary of all test results
- Pass/fail status for each test section
- Exit codes: 0 (all passed), 1 (critical failures), 2 (warnings only)
- JSON format available for automation

## Expected Results
All tests should pass, demonstrating:
✅ Database connectivity working
✅ Service isolation functional
✅ Automatic escalation working
✅ Cooldown system operational
✅ Simulation infrastructure ready for testing