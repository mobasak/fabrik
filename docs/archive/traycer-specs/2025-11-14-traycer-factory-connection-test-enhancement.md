# Traycer → Factory Connection Test Spec

## Context

Based on my analysis of the existing system:
- ✅ Basic connection test already exists (`/opt/proxy/tests/traycer_factory_connection_test.py`)
- ✅ Previous test validated file system access and Factory AI communication
- ✅ Proxy system is database-backed with full service isolation
- ⚠️ Current test does NOT validate actual proxy operations or database connectivity

## Proposed Enhancement

I'll create an **enhanced connection test** that validates the complete Traycer → Factory → Proxy System workflow:

### Test Scenarios

#### 1. **Basic System Access** (Already Working ✅)
- File system access validation
- Project structure verification
- Python environment check

#### 2. **Environment Configuration** (NEW)
- Check if environment variables are properly set
- Validate database configuration (without connecting)
- Verify WEBSHARE_API_KEY availability
- Test environment file loading

#### 3. **Proxy System Initialization** (NEW)
- Test `DbProxyManager` can be imported
- Test `ProxyClient` wrapper can be imported
- Validate configuration module loads correctly
- Check for required Python dependencies (psycopg2, requests)

#### 4. **Database Connectivity** (NEW - CONDITIONAL)
- Attempt PostgreSQL connection
- Query service list from database
- Check proxy_service_status table
- **Note**: Will gracefully skip if DB not available (like in simulation tests)

#### 5. **Proxy Client Operations** (NEW - CONDITIONAL)
- Initialize ProxyClient for test service
- Test get_proxy() method
- Validate proxy URL format
- Test mark_success() / mark_failure() reporting
- **Note**: Will skip if no API key or DB unavailable

#### 6. **Error Handling Validation** (NEW)
- Test proper error messages when env vars missing
- Test graceful degradation when DB unavailable
- Test retry logic on connection failures
- Validate structured logging output

### Test Structure

```python
#!/usr/bin/env python3
"""
Enhanced Traycer → Factory Connection Test
==========================================
Validates complete proxy system integration from Traycer's perspective
"""

Test Categories:
1. System Access (3 tests) - File system, permissions, Python
2. Configuration (3 tests) - Environment variables, config loading
3. Module Imports (3 tests) - Proxy manager, client, dependencies
4. Database Connectivity (3 tests) - Connection, queries, health
5. Proxy Operations (4 tests) - Client init, get proxy, mark status
6. Error Handling (3 tests) - Missing config, failed connections, retries

Total: ~19 test cases
```

### Key Features

- **Graceful Degradation**: Tests skip cleanly if dependencies unavailable
- **Clear Status Icons**: ✅ PASS, ❌ FAIL, ⏭️ SKIP, ⚠️ PARTIAL
- **Detailed Reporting**: Each test includes reason for skip/failure
- **Reusable**: Can run in any environment (dev, staging, production)
- **Non-Destructive**: Only reads data, doesn't modify proxy states
- **Comprehensive Summary**: Overall health score + recommendations

### Output Format

```
======================================================================
🔗 ENHANCED TRAYCER → FACTORY CONNECTION TEST
======================================================================

📊 Test Results by Category:

[1] System Access
✅ File System Access: PASS
✅ Project Structure: PASS
✅ Python Environment: PASS

[2] Configuration
✅ Environment Variables: PASS (DB_PASSWORD set)
⏭️ Webshare API Key: SKIP (Not required for basic tests)
✅ Config Module Loading: PASS

[3] Module Imports
✅ DbProxyManager Import: PASS
✅ ProxyClient Import: PASS
⚠️ Database Driver: PARTIAL (psycopg2 available, no connection)

[4] Database Connectivity
⏭️ Database Connection: SKIP (PostgreSQL not available)
⏭️ Service List Query: SKIP (No DB connection)
⏭️ Status Table Query: SKIP (No DB connection)

[5] Proxy Operations
⏭️ Client Initialization: SKIP (No DB connection)
⏭️ Get Proxy: SKIP (Client not initialized)
⏭️ Mark Success: SKIP (Client not initialized)
⏭️ Mark Failure: SKIP (Client not initialized)

[6] Error Handling
✅ Missing Config Detection: PASS
✅ Connection Retry Logic: PASS
✅ Structured Logging: PASS

======================================================================
📈 Summary: 9 passed, 0 failed, 10 skipped
Health Score: 90% (9/10 available tests passed)
======================================================================
```

### File Locations

- **Test Script**: `/opt/proxy/tests/traycer_factory_connection_test_v2.py` (NEW)
- **Results Document**: `/opt/proxy/TRAYCER_FACTORY_CONNECTION_V2_RESULTS.md` (NEW)
- **Keep Original**: `/opt/proxy/tests/traycer_factory_connection_test.py` (PRESERVED)

### Benefits

1. **Complete Validation**: Tests entire stack from file system → database → proxy operations
2. **Environment Agnostic**: Works in dev/staging/prod with different availability levels
3. **Actionable Results**: Clear indication of what works and what needs configuration
4. **Traycer Confidence**: Validates Traycer can successfully interact with all system layers
5. **Documentation**: Generates comprehensive results document for reference

### Implementation Approach

1. Create new test file (keep original unchanged)
2. Implement test categories sequentially with proper error handling
3. Add dependency checks before each test category
4. Generate detailed results markdown document
5. Execute test and capture full output
6. Create summary document with recommendations

---

**Ready to implement?** This will create a comprehensive connection test that validates the entire Traycer → Factory → Proxy System workflow.
