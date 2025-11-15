# Minecraft Plugin Manager - Quick Start Guide

**Version:** 1.0.0
**Status:** ✅ Production Ready
**Last Tested:** 2025-11-15 (100% pass rate)
**CLI Command:** `minecraft-plugin-manager`

---

## Common Commands

### Check Current Status
```bash
minecraft-plugin-manager --status
```
Shows all deployed plugins and versions across all servers.

### Check Version Consistency
```bash
minecraft-plugin-manager --audit
```
Verifies minecraft-paper-0 and minecraft-lobby-0 have matching versions.

### Check for Updates
```bash
# Stable updates only (recommended)
minecraft-plugin-manager --check

# Include SNAPSHOT/dev versions
minecraft-plugin-manager --check --force
```

### Download Updates (Safe)
```bash
# Preview what would be downloaded
minecraft-plugin-manager --download --dry-run

# Actually download (no deployment yet)
minecraft-plugin-manager --download
```

### Deploy Updates (Full Automation)
```bash
# Preview deployment (safe - no changes)
minecraft-plugin-manager --deploy --dry-run

# Execute deployment (runs all safety checks automatically)
minecraft-plugin-manager --deploy
```

**Deployment automatically includes:**
- Pre-flight checks (SSH, disk space, permissions)
- Infrastructure compatibility validation
- Automatic .BAK backups
- Server restarts
- Plugin loading verification
- Git commit for audit trail

### Emergency Rollback
```bash
# Preview rollback
minecraft-plugin-manager --rollback --dry-run

# Execute rollback
minecraft-plugin-manager --rollback
```
Restores .BAK files and restarts servers.

---

## Recommended Workflow

### Weekly Maintenance
```bash
cd /mnt/tank/faststorage/general/repo/minecraft

# 1. Check consistency
minecraft-plugin-manager --audit

# 2. Check for updates
minecraft-plugin-manager --check

# 3. If updates available, download
minecraft-plugin-manager --download

# 4. Review downloaded files
ls -lh downloads/

# 5. Deploy (includes all safety checks)
minecraft-plugin-manager --deploy

# 6. Verify status
minecraft-plugin-manager --status

# 7. Test connectivity
# Connect to mc.haymoed.com:19132 (Bedrock)
```

### Emergency Update
```bash
# Force check (includes dev builds)
minecraft-plugin-manager --check --force

# Download
minecraft-plugin-manager --download --force

# Deploy
minecraft-plugin-manager --deploy
```

### If Update Causes Issues
```bash
# Immediate rollback
minecraft-plugin-manager --rollback

# Verify rollback worked
minecraft-plugin-manager --status

# Test connectivity
# Connect to mc.haymoed.com:19132
```

---

## Currently Managed Plugins (7)

### Bedrock Cross-Play (4 plugins)
- ✅ ViaVersion (Velocity + Paper)
- ✅ Geyser-Velocity
- ✅ floodgate-velocity
- ✅ floodgate-spigot

### Tier 1 Infrastructure (3 plugins)
- ✅ LuckPerms-Bukkit
- ✅ LuckPerms-Velocity
- ✅ PlaceholderAPI

**Coverage:** 7 of 73 total plugins (9.6%)

---

## Safety Features

### Pre-Flight Checks (Automatic)
1. SSH connectivity to node
2. Disk space monitoring
3. Downloads directory writable
4. Deployment state file exists

### Infrastructure Validation (Automatic)
- Velocity version checking (Geyser requires b500+)
- Paper version checking
- Prevents incompatible deployments

### Backup System
- Automatic .BAK files before overwrite
- Timestamped backups
- Quick rollback capability

### Git Integration (Automatic)
- Auto-commit after successful deployment
- Detailed commit messages
- Complete audit trail

---

## Current System Status

**Servers:**
- minecraft-proxy-0 (Velocity 3.4.0-SNAPSHOT b557)
- minecraft-paper-0 (Paper 1.20.1)
- minecraft-lobby-0 (Paper 1.20.1)

**Bedrock Plugins:** All up to date ✅
- ViaVersion 5.5.1
- Geyser-Velocity 2.9.0-build981
- floodgate-velocity/spigot 2.2.5-build121

**Available Updates (Non-Critical):**
- LuckPerms: 5.4.154 → v5.5.17
- PlaceholderAPI: 2.11.6 → 2.11.7

**Infrastructure:** Compatible ✅
- Velocity b557 meets all requirements

---

## Important Notes

### Always Use --dry-run First
```bash
# Preview before executing
minecraft-plugin-manager --deploy --dry-run
```

### Bedrock Connectivity
After any deployment, test:
- Address: mc.haymoed.com
- Port: 19132
- Expected: Seamless connection from Bedrock clients

### Git Commits
All deployments automatically create git commits for audit trail.
No manual commit needed.

### Logs
All operations logged to:
```
bedrock-updater-YYYYMMDDHHMMSS.log
```

---

## Help & Documentation

**Full Documentation:**
- `AUTOMATION_USAGE.md` - Detailed usage guide
- `SUCCESS_REPORT.md` - Phase 1 deployment report
- `TEST_RESULTS.md` - Comprehensive test results

**Get Help:**
```bash
minecraft-plugin-manager --help
```

**Report Issues:**
Check logs in `minecraft-plugin-manager-*.log`

---

**Tool Version:** 1.0.0
**Last Updated:** 2025-11-15
**Status:** Production Ready ✅
**Installation:** Installed via venv as `minecraft-plugin-manager` command
