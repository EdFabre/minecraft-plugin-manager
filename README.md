# Minecraft Plugin Manager

Automated plugin update management for Minecraft servers (Velocity + Paper).

## Overview

**Version:** 1.0.0
**Status:** Production Ready
**Coverage:** 7 managed plugins (Bedrock cross-play + Tier 1 infrastructure)

Manages automatic updates for:
- **Bedrock Cross-Play**: Geyser, ViaVersion, floodgate
- **Tier 1 Infrastructure**: LuckPerms, PlaceholderAPI

## Quick Start

```bash
# Install into venv
cd /mnt/tank/faststorage/general/repo
source .venv/bin/activate  # or use 'repo' alias
pip install -e projects/minecraft-plugin-manager/core/backend/

# Check status
minecraft-plugin-manager --status

# Check for updates
minecraft-plugin-manager --check

# Deploy updates (with full safety checks)
minecraft-plugin-manager --deploy
```

## Documentation

- **[Quick Start Guide](core/docs/QUICK_START.md)** - Common commands and workflows
- **[Usage Guide](core/docs/AUTOMATION_USAGE.md)** - Detailed usage documentation
- **[Test Results](core/docs/TEST_RESULTS.md)** - Comprehensive test report

## Features

- ✅ Automated update detection (Modrinth + Geyser APIs)
- ✅ SHA256/SHA512 hash verification
- ✅ Pre-flight safety checks (SSH, disk space, permissions)
- ✅ Infrastructure compatibility validation
- ✅ Automatic backups before deployment
- ✅ Emergency rollback capability
- ✅ Version consistency checking across servers
- ✅ Git integration for audit trail

## Managed Plugins (7)

### Bedrock Cross-Play (4 plugins)
- ViaVersion (Velocity + Paper)
- Geyser-Velocity
- floodgate-velocity
- floodgate-spigot

### Tier 1 Infrastructure (3 plugins)
- LuckPerms-Bukkit
- LuckPerms-Velocity
- PlaceholderAPI

## Architecture

- **Velocity Proxy**: 3.4.0-SNAPSHOT (build 557+)
- **Paper Servers**: 1.20.1
- **Deployment**: SSH-based to Pterodactyl containers
- **Node**: games-node-1 (192.168.1.71)

## Safety Systems

**5-Layer Safety**:
1. Pre-flight checks (SSH, disk, permissions)
2. Infrastructure validation (Velocity/Paper versions)
3. Deployment with automatic backups
4. Post-deployment verification
5. Emergency rollback capability

## Development

Built using lifecycle-manager pattern:
- Modular architecture (cli, updater, api_clients, deployment, config)
- Lifecycle-managed versioning
- AI workflow integration
- Git-sync deployment automation

## Migration from Legacy Tool

This tool replaces `/mnt/tank/faststorage/general/repo/minecraft/bedrock_plugin_updater.py`.

Legacy tool preserved as `bedrock_plugin_updater.legacy.py` for reference.

---

**Generated with Claude Code**
https://claude.com/claude-code
