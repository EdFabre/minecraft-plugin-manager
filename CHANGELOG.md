# Changelog - Minecraft Plugin Manager

All notable changes to this project will be documented in this file.

## [1.0.1] - 2025-11-23

### Added
- **JAR Manifest Fallback for Version Detection** (`deployment.py:338-357`)
  - Reads Velocity version from JAR manifest when logs unavailable
  - Prevents deployment failures when servers haven't restarted recently
  - Automatically falls back to manifest if "Booting up Velocity" not found in logs

- **Active Server Configuration** (`updater.py:247`, `config.yaml`)
  - Added `active` flag to server configuration
  - Only deploys to servers marked `active: true`
  - Gracefully skips inactive/development servers
  - Backward compatible (defaults to `true` if not specified)

- **Graceful Handling of Unconfigured Servers** (`deployment.py:137-143`)
  - Checks for plugins directory existence before deployment
  - Logs warning instead of error for missing directories
  - Returns False for graceful skip instead of raising exception

- **Improved Deployment Reporting** (`updater.py:249-283`)
  - Tracks success, skip, and failure counts separately
  - Distinguishes between skipped servers (unconfigured) vs failed servers (errors)
  - Only reports deployment failure if zero servers updated
  - Clear, informative messages for partial deployments

- **Complete Server Configuration** (`config.py:151-177`)
  - Added minecraft-db-0 and minecraft-paper-1 to SERVERS dictionary
  - Added `active` flag to all server definitions
  - Added descriptive comments for production vs development servers

### Changed
- Server targeting now respects `active` flag in configuration
- Deployment continues on partial success (some servers updated)
- Infrastructure compatibility checks use JAR manifest as fallback
- Logging levels adjusted (warnings for expected conditions, errors for failures)

### Fixed
- KeyError when deploying to servers in config YAML but not in SERVERS dict
- Deployment failures when Velocity server hasn't restarted recently
- Complete deployment failure when some servers lack `/plugins` directories
- False negative deployments (failing when critical servers actually updated)

### Technical Details

**Files Modified:**
- `deployment.py` - JAR manifest fallback + directory existence check
- `updater.py` - Active server filtering + improved reporting
- `config.py` - Complete server definitions + active flags
- `config.yaml` - Active flags + server descriptions

**Lines Changed:** ~80 lines added/modified
**Backward Compatible:** Yes (all changes additive/refinements)
**Breaking Changes:** None

### Production Servers (active=true)
- minecraft-proxy-0 - Velocity proxy (**CRITICAL for Bedrock**)
- minecraft-paper-0 - Primary Paper server
- minecraft-lobby-0 - Lobby server

### Development Servers (active=false)
- minecraft-db-0 - Database server (not configured)
- minecraft-paper-1 - Development server (node 2)

---

## [1.0.0] - 2025-11-15

### Initial Release
- Automatic update detection for 7 managed plugins
- Bedrock cross-play plugins (Geyser, ViaVersion, floodgate)
- Tier 1 infrastructure plugins (LuckPerms, PlaceholderAPI)
- SHA512/SHA256 hash verification
- Pre-flight safety checks (SSH, disk space, permissions)
- Infrastructure compatibility validation (Velocity version)
- Automatic backups before deployment
- Server restart automation
- Multi-server deployment support

### Managed Plugins (7 total)

**Bedrock Cross-Play (Critical):**
- ViaVersion
- Geyser-Velocity
- floodgate-velocity
- floodgate-spigot

**Tier 1 Infrastructure:**
- LuckPerms-Velocity
- LuckPerms-Bukkit
- PlaceholderAPI

### Safety Features
- 5-layer safety system
- Pre-flight checks
- Infrastructure validation
- Automatic backups
- Hash verification
- Post-deployment verification

---

## Future Enhancements

**Planned Improvements:**
1. Config validation (detect servers in YAML but missing from SERVERS dict)
2. Server health checks (pre-flight validation)
3. Parallel deployment (deploy to multiple servers simultaneously)
4. Deployment retry (automatic retry on transient failures)
5. State file updates (update deployment-state.json after success)
6. Automated weekly checks (cron job integration)
7. Notification system (Slack/Discord alerts for available updates)
8. Automated rollback (rollback on deployment failure)

---

**Generated with Claude Code**
https://claude.com/claude-code
