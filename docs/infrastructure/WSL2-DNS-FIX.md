# WSL2 DNS Resolution Fix

**Date:** 2026-03-16  
**Status:** ✅ APPLIED  
**Affects:** All WSL2 environments running Fabrik

---

## Problem

WSL2 DNS resolution was failing intermittently, causing:
- Kilo CLI unable to connect to `api.kilo.ai`
- Node.js applications failing with `FailedToOpenSocket` errors
- `ping` command failing with "Temporary failure in name resolution"
- Inconsistent behavior: `curl` and `nslookup` worked, but `ping` and Node.js failed

### Root Cause

WSL2's auto-generated `/etc/resolv.conf` has a known bug (Microsoft WSL GitHub issue #4277) where:
1. Windows DNS settings → WSL2 bridge → `/etc/resolv.conf` (auto-generated)
2. WSL2's network bridge gets confused
3. System `getaddrinfo()` function fails intermittently
4. Tools that bypass `getaddrinfo()` (curl, nslookup) continue working
5. Node.js relies on `getaddrinfo()`, so Kilo CLI fails

---

## Solution Applied

Disabled WSL2's automatic `/etc/resolv.conf` generation and created a static configuration with reliable DNS servers.

### Step 1: Disable Auto-Generation

Created `/etc/wsl.conf`:
```ini
[network]
generateResolvConf = false
```

### Step 2: Create Static DNS Configuration

Created `/etc/resolv.conf`:
```
nameserver 1.1.1.1
nameserver 8.8.8.8
options timeout:1 attempts:2
```

### Step 3: Make Immutable

Protected the file from WSL2 overwriting:
```bash
sudo chattr +i /etc/resolv.conf
```

---

## Verification

### Before Fix
```bash
$ ping api.kilo.ai
ping: api.kilo.ai: Temporary failure in name resolution

$ kilo models
Error fetching Kilo models: FailedToOpenSocket
```

### After Fix
```bash
$ ping api.kilo.ai
PING aac3036b0c2b3b1a.vercel-dns-016.com (64.239.109.193) 56(84) bytes of data.
64 bytes from 64.239.109.193: icmp_seq=1 ttl=245 time=25.3 ms
✅ SUCCESS

$ kilo models | head -3
kilo/ai21/jamba-large-1.7
kilo/aion-labs/aion-1.0
kilo/aion-labs/aion-1.0-mini
✅ SUCCESS
```

---

## DNS Servers Used

| Server | Provider | Purpose |
|--------|----------|---------|
| 1.1.1.1 | Cloudflare | Primary DNS (fast, privacy-focused) |
| 8.8.8.8 | Google | Secondary DNS (reliable fallback) |

**Options:**
- `timeout:1` - 1 second timeout per query
- `attempts:2` - Retry failed queries once

---

## Persistence

This fix is **permanent** and survives WSL restarts:
- `/etc/wsl.conf` persists across reboots
- `/etc/resolv.conf` is immutable (chattr +i)
- No need to reapply after `wsl --shutdown`

---

## Rollback (if needed)

To revert to WSL2 auto-generation:

```bash
# Remove immutable flag
sudo chattr -i /etc/resolv.conf

# Delete custom config
sudo rm /etc/resolv.conf

# Disable our setting
sudo rm /etc/wsl.conf

# Restart WSL from PowerShell
wsl --shutdown
```

---

## Related Issues

- Microsoft WSL GitHub #4277
- Affects: Node.js, Python requests library, Go net package
- Does NOT affect: curl, wget, nslookup, host

---

## Date Applied

**2026-03-16 14:20 UTC+03:00**

Applied by: Cascade AI Agent  
Verified by: Kilo CLI connectivity test
