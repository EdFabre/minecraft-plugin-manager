# Bedrock Plugin Updater - Usage Guide

**Tool:** `bedrock_plugin_updater.py`
**Purpose:** Automated checking and updating of Bedrock-critical Minecraft plugins
**Created:** 2025-11-15

---

## Quick Reference

### Available Flags

| Flag | Description | Mode |
|------|-------------|------|
| `--audit` | Check version consistency across servers | Read-only |
| `--check` | Check for available updates | Read-only |
| `--download` | Download available updates | Downloads files |
| `--deploy` | Deploy updates to servers | **Changes servers** |
| `--force` | Force update even if versions match | Modifier |
| `--dry-run` | Simulate actions without changes | Safety |
| `--status` | Show current plugin versions | Read-only |

### Safety Modes

**Dry Run (Safest):**
```bash
python3 bedrock_plugin_updater.py --check --dry-run
# Shows: Mode: DRY RUN
# Result: No changes, just reports what would happen
```

**Live Mode:**
```bash
python3 bedrock_plugin_updater.py --check
# Shows: Mode: LIVE
# Result: Actually executes actions (check only is still safe)
```

---

## Usage Examples

### 0. Check Version Consistency (NEW - Recommended First Step)

**Check if all servers of the same type have matching plugin versions:**
```bash
python3 bedrock_plugin_updater.py --audit
```

**Output when all versions match:**
```
======================================================================
Checking version consistency across servers...
======================================================================

Platform 'velocity': Only 1 server, skipping consistency check

Platform 'paper': Checking 2 servers

✓ All servers have consistent plugin versions!
```

**Output when version drift detected:**
```
======================================================================
Checking version consistency across servers...
======================================================================

Platform 'paper': Checking 2 servers
  ⚠ DRIFT DETECTED: ViaVersion
    minecraft-paper-0: 5.5.1
    minecraft-lobby-0: 5.3.2

  ⚠ MISSING: floodgate-spigot (installed: 2.2.5-build121)
    minecraft-lobby-0: NOT INSTALLED

✗ Found 2 plugin(s) with version inconsistencies
Recommendation: Use --download and --deploy to sync versions across servers
```

**When to use:**
- Before making any updates (detect current drift)
- After manual plugin changes on individual servers
- As part of regular maintenance checks
- To verify deployment success

---

### 1. Check for Updates (Safe)

**Normal check - skips if up to date:**
```bash
python3 bedrock_plugin_updater.py --check
```

**Output when up to date:**
```
======================================================================
Checking for plugin updates...
======================================================================

Checking: ViaVersion
  Current version: 5.5.1
  Latest version: 5.5.1
  ✓ Already up to date

Checking: Geyser-Velocity
  Current version: 2.9.0-build981
  Latest version: 2.9.0-b981
  ✓ Already up to date

✓ All plugins are up to date!
```

### 2. Force Check (Shows All Versions)

**Check even if versions match:**
```bash
python3 bedrock_plugin_updater.py --check --force
```

**Output:**
```
Mode: LIVE
Force: True

4 update(s) available:
  • ViaVersion: 5.5.1 → 5.5.2-SNAPSHOT+859
  • Geyser-Velocity: 2.9.0-build981 → 2.9.0-b981
  • floodgate-velocity: 2.2.5-build121 → 2.2.5-b121
  • floodgate-spigot: 2.2.5-build121 → 2.2.5-b121
```

**Note:** Force mode includes SNAPSHOT versions (dev builds)

### 3. Dry Run (Test Mode)

**Simulate without making changes:**
```bash
python3 bedrock_plugin_updater.py --check --dry-run
```

**When to use:**
- Testing the tool
- Verifying what would happen
- Safe exploration

**Output:**
```
Mode: DRY RUN
Force: False

[DRY RUN] Stopping here. Use --apply to download and deploy.
```

### 4. Download Updates

**Download new plugin versions:**
```bash
python3 bedrock_plugin_updater.py --download
```

**What happens:**
1. Checks for updates
2. Downloads new JAR files to `downloads/`
3. Verifies SHA256/SHA512/SHA1 hashes
4. Stops before deploying

**Output when downloading:**
```
======================================================================
Downloading updates...
======================================================================

Downloading: ViaVersion-5.5.2-SNAPSHOT.jar
  URL: https://cdn.modrinth.com/data/P1OZGk5p/versions/...
  Downloaded: 5,903,943 bytes
  ✓ SHA512 verified: 1c2a8a517712459e...

✓ ViaVersion downloaded successfully

Next steps:
  1. Copy JARs to shared-plugins directories
  2. Update manifest (shared-plugins.json)
  3. Deploy to servers
  4. Commit to git

Run with --deploy to execute deployment
```

### 5. Show Current Versions

**Display installed versions:**
```bash
python3 bedrock_plugin_updater.py --status
```

**Output:** (TODO - not yet implemented)
```
Current Plugin Versions:
========================

minecraft-proxy-0 (Velocity):
  • Geyser-Velocity: 2.9.0-build981
  • floodgate-velocity: 2.2.5-build121
  • ViaVersion: 5.5.1

minecraft-paper-0 (Paper 1.20.1):
  • floodgate-spigot: 2.2.5-build121
  • ViaVersion: 5.5.1

minecraft-lobby-0 (Paper 1.20.1):
  • floodgate-spigot: 2.2.5-build121
  • ViaVersion: 5.5.1
```

---

## Advanced Usage

### Combining Flags

**Safe exploration with force:**
```bash
python3 bedrock_plugin_updater.py --check --force --dry-run
```
- Checks all versions (including SNAPSHOTs)
- Shows what would be updated
- Makes no actual changes

**Download with force:**
```bash
python3 bedrock_plugin_updater.py --download --force
```
- Downloads even if versions match
- Useful for re-downloading corrupted files
- Downloads to `downloads/` directory

### Logging

**All operations are logged to:**
```
bedrock-updater-YYYYMMDDHHMMSS.log
```

**Log location:**
```bash
ls -lh bedrock-updater-*.log
```

**View latest log:**
```bash
tail -f $(ls -t bedrock-updater-*.log | head -1)
```

---

## Understanding Output

### Version Normalization

The tool automatically normalizes version strings:

| Manifest Format | API Format | Normalized |
|----------------|------------|------------|
| `2.9.0-build981` | `2.9.0-b981` | `2.9.0-b981` |
| `2.2.5-build121` | `2.2.5-b121` | `2.2.5-b121` |

**Why:** Different APIs use different naming conventions. The tool handles this automatically.

### Hash Verification

**Supported hash types:**
- SHA256 (preferred)
- SHA512 (Modrinth fallback)
- SHA1 (legacy)

**Example output:**
```
Downloaded: 18,245,997 bytes
✓ SHA256 verified: d133faa5c9a94411...
```

**If hash fails:**
```
✗ SHA256 mismatch!
  Expected: d133faa5c9a94411...
  Got:      abc123def456...
```
**Action:** Download is deleted, update aborted

### Infrastructure Compatibility Checking (Phase 2 Part 3)

**Automatic pre-flight checks before deployment:**

The tool automatically verifies infrastructure compatibility to prevent deployment failures like the Phase 1 Geyser incident.

**Example output (compatible):**
```
======================================================================
Checking infrastructure compatibility...
======================================================================

Detected Velocity build: 557
✓ Geyser-Velocity: Compatible with Velocity build 557 (requires 500+)
✓ floodgate-velocity: Compatible with Velocity build 557 (requires 400+)

✓ All infrastructure compatibility checks passed
```

**Example output (incompatible - would abort deployment):**
```
======================================================================
Checking infrastructure compatibility...
======================================================================

Detected Velocity build: 459
✗ Geyser-Velocity: Requires Velocity build 500+, but detected build 459
  Reason: Geyser 2.9.0+ requires Adventure library API (ComponentFlattener.nestingLimit)
  Solution: Update Velocity proxy first using ./update-velocity.sh

✗ Found 1 compatibility issue(s)
Cannot proceed with deployment until infrastructure is updated

✗ Deployment aborted due to infrastructure compatibility issues
```

**Compatibility Matrix:**
| Plugin | Infrastructure Requirement | Minimum Version | Reason |
|--------|---------------------------|-----------------|---------|
| Geyser-Velocity | Velocity proxy | Build 500+ | Adventure library API |
| floodgate-velocity | Velocity proxy | Build 400+ | Velocity 3.4.0+ required |

**What happens:**
1. Before deployment, tool reads server logs via SSH
2. Extracts Velocity/Paper versions
3. Compares against compatibility matrix
4. Aborts deployment if requirements not met
5. Provides clear instructions for updating infrastructure

**Lesson Learned from Phase 1:**
The Geyser 2.9.0 update failed because Velocity build 459 lacked the required Adventure library API. The tool now prevents this scenario automatically.

---

## Current Limitations (TODO)

### Not Yet Implemented

1. **--deploy flag** ✅ IMPLEMENTED (Phase 2 Part 2)
   - Full SSH-based deployment automation
   - Automatic backups, restart, and verification
   - Infrastructure compatibility pre-flight checks

2. **--status flag**
   - Shows "TODO - not yet implemented"
   - Will display current versions from deployment-state.json

3. **Git integration**
   - No automatic commits yet
   - Must manually commit changes

4. **Compatibility checking** ✅ IMPLEMENTED (Phase 2 Part 3)
   - Automatically verifies Velocity version before Geyser deployment
   - Prevents Phase 1 failure scenario (Geyser 2.9.0 requires Velocity b500+)
   - Pre-flight checks run before every deployment
   - Aborts deployment if infrastructure incompatible

5. **Rollback capability**
   - Must use manual script: `./manual-bedrock-update.sh --rollback`

---

## Workflow Examples

### Scenario 1: Regular Weekly Check

```bash
# Monday morning routine
cd /mnt/tank/faststorage/general/repo/minecraft

# 1. Check version consistency across servers
python3 bedrock_plugin_updater.py --audit

# 2. Check for updates
python3 bedrock_plugin_updater.py --check

# If updates found:
# 3. Download updates
python3 bedrock_plugin_updater.py --download

# 4. (TODO) Deploy updates
# python3 bedrock_plugin_updater.py --deploy

# For now, use manual deployment:
./manual-bedrock-update.sh --dry-run   # Preview
./manual-bedrock-update.sh             # Deploy

# 5. Restart servers
./restart-and-verify.sh

# 6. Verify consistency after deployment
python3 bedrock_plugin_updater.py --audit

# 7. Test Bedrock connectivity
# Connect to mc.haymoed.com:19132
```

### Scenario 2: Emergency Geyser Update

```bash
# Geyser released critical security update

# 1. Force check to see latest (including dev builds)
python3 bedrock_plugin_updater.py --check --force

# 2. If critical update exists, download
python3 bedrock_plugin_updater.py --download --force

# 3. Verify Velocity compatibility FIRST (learned from Phase 1!)
ssh root@192.168.1.71 "grep 'Booting up Velocity' /var/lib/pterodactyl/volumes/b57a0213-6e24-429a-9fdd-241f82c397d1/logs/latest.log | tail -1"

# 4. Deploy if compatible
./manual-bedrock-update.sh

# 5. Verify
./restart-and-verify.sh
```

### Scenario 3: Rollback After Bad Update

```bash
# Update caused issues

# 1. Quick rollback (uses .BAK files)
./manual-bedrock-update.sh --rollback

# 2. Restart servers
ssh root@192.168.1.71 "docker restart \$(docker ps -q)"

# 3. Verify old version working
./restart-and-verify.sh

# 4. Document issue
echo "Update X caused issue Y" >> deployment-issues.log

# 5. Update git
git add checksums/deployment-state.json
git commit -m "Rollback: Issue with version X"
```

---

## Safety Checklist

Before running updates:

- [ ] **Backup exists:** `.BAK` files from last deployment
- [ ] **Git committed:** No uncommitted changes
- [ ] **Dry run tested:** Ran with `--dry-run` first
- [ ] **Velocity checked:** Verify Velocity version if updating Geyser
- [ ] **Low traffic time:** Update during low-activity hours
- [ ] **Rollback ready:** Know how to rollback quickly

After running updates:

- [ ] **Logs checked:** No critical errors
- [ ] **Bedrock tested:** Connected with Bedrock client
- [ ] **Java tested:** Connected with Java client
- [ ] **Git committed:** Documented deployment
- [ ] **Notify users:** If any downtime occurred

---

## Troubleshooting

### "No versions found"

**Cause:** API temporarily unavailable
**Solution:** Wait and retry

### "SHA256 mismatch"

**Cause:** Corrupted download or API issue
**Solution:**
1. Delete corrupted file: `rm downloads/plugin-name.jar`
2. Re-download: `python3 bedrock_plugin_updater.py --download`

### "All plugins up to date" but expecting update

**Cause:** Version normalization hiding update
**Solution:** Use `--force` flag to see all versions

### Download stuck

**Cause:** Slow network or large file
**Solution:** Wait or Ctrl+C and retry

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error occurred |
| 130 | Interrupted by user (Ctrl+C) |

---

## File Locations

```
minecraft/
├── bedrock_plugin_updater.py           # This tool
├── bedrock-updater-*.log               # Log files
├── downloads/                          # Downloaded JARs
│   ├── ViaVersion-5.5.1.jar
│   ├── Geyser-Velocity_2.9.0-build981.jar
│   └── ...
├── shared-plugins/
│   ├── shared-plugins.json             # Plugin manifest
│   ├── velocity/*.jar                  # Velocity plugins
│   └── paper/*.jar                     # Paper plugins
└── checksums/
    ├── deployment-state.json           # What's actually deployed
    └── bedrock-plugins.sha256          # Integrity hashes
```

---

## Next Steps

See `SUCCESS_REPORT.md` for Phase 1 deployment results.

**Phase 2 Roadmap:**
- [x] Update checking
- [x] Download system
- [ ] Deployment automation
- [ ] Git integration
- [ ] Compatibility checking
- [ ] Rollback automation

---

**Last Updated:** 2025-11-15
**Tool Version:** Phase 2 Foundation (v0.1)
